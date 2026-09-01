param(
    [string]$RepoUrl = "https://github.com/h4rdstyle1988/Documents-Controlling-clear.git",
    [string]$BaseBranch = "main",
    [string]$AgentRoot = "D:\Documents-Controlling-Agent",
    [string]$WorkerDir = "",
    [string]$SchedulerTaskName = "Documents-Ruediger-Agent",
    [string]$LiveStatusBranch = "ruediger/live-status",
    [int]$PollSeconds = 30,
    [int]$HeartbeatSeconds = 90,
    [int]$FetchRetryCount = 3,
    [int]$MaxCodexFailuresWithoutCheckpoint = 3,
    [int]$LogRetentionDays = 7,
    [switch]$DiagnosticOnly,
    [switch]$SelectionTestOnly
)

$ErrorActionPreference = "Continue"
$PSDefaultParameterValues["*:ErrorAction"] = "Stop"
$WatcherVersion = "DOCUMENTS-R02"
$env:GIT_TERMINAL_PROMPT = "0"

if ($PollSeconds -lt 5) { throw "PollSeconds muss mindestens 5 sein." }
if ($HeartbeatSeconds -lt 60 -or $HeartbeatSeconds -gt 120) { throw "HeartbeatSeconds muss zwischen 60 und 120 liegen." }
if ($FetchRetryCount -lt 1) { throw "FetchRetryCount muss mindestens 1 sein." }
if ($MaxCodexFailuresWithoutCheckpoint -lt 1) { throw "MaxCodexFailuresWithoutCheckpoint muss mindestens 1 sein." }
if (-not $WorkerDir) { $WorkerDir = Join-Path $AgentRoot "worker\Documents-Controlling-clear-worker" }

$workflowModule = Join-Path $PSScriptRoot "documents-agent-workflow.ps1"
if (-not (Test-Path -LiteralPath $workflowModule -PathType Leaf)) { throw "Workflow-Modul fehlt: $workflowModule" }
. $workflowModule

function Get-FullNormalizedPath {
    param([string]$Path)
    return [IO.Path]::GetFullPath($Path).TrimEnd('\')
}

function Assert-DedicatedPaths {
    $rootFull = Get-FullNormalizedPath $AgentRoot
    $workerFull = Get-FullNormalizedPath $WorkerDir
    $workerRoot = (Join-Path $rootFull "worker").TrimEnd('\') + '\'
    if ($rootFull -eq [IO.Path]::GetPathRoot($rootFull).TrimEnd('\')) {
        throw "AgentRoot darf kein Laufwerksstamm sein: $rootFull"
    }
    if (-not $workerFull.StartsWith($workerRoot,[StringComparison]::OrdinalIgnoreCase)) {
        throw "WorkerDir muss innerhalb des dedizierten AgentRoot\worker liegen: $workerFull"
    }
}

Assert-DedicatedPaths

$stateDir = Join-Path $AgentRoot "state"
$stateFile = Join-Path $stateDir "documents-task-state.json"
$logDir = Join-Path $AgentRoot "logs"
$runtimeDir = Join-Path $AgentRoot "runtime"
$tempDir = Join-Path $AgentRoot "temp"
$lockPath = Join-Path $stateDir "documents-agent-watcher.lock"

New-Item -ItemType Directory -Force -Path $AgentRoot,$stateDir,$logDir,$runtimeDir,$tempDir | Out-Null
$logFile = Join-Path $logDir ("documents-agent-watch-{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))

try {
    $lockStream = [IO.File]::Open($lockPath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
}
catch {
    Write-Host "Documents-Watcher laeuft bereits. Zweite Instanz beendet."
    exit 0
}

function Write-Log {
    param([string]$Message,[string]$Level="INFO")
    $line = "{0} [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff zzz"),$Level,$Message
    Add-Content -LiteralPath $script:logFile -Value $line -Encoding UTF8
    Write-Host $line
}

function Remove-ExpiredLogs {
    $cutoff = (Get-Date).AddDays(-$LogRetentionDays)
    Get-ChildItem -LiteralPath $logDir -File -Filter "documents-agent-watch-*.log" -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt $cutoff } |
        Remove-Item -Force -ErrorAction SilentlyContinue
}

function Get-NormalizedGitUrl {
    param([string]$Url)
    if (-not $Url) { return "" }
    return (($Url.Trim() -replace '\\','/') -replace '/$','' -replace '\.git$','').ToLowerInvariant()
}

function Invoke-GitSafe {
    param(
        [Parameter(Mandatory=$true)][string[]]$GitArgs,
        [int]$Retries = 1
    )
    $lastMessage = ""
    $isPush = ($GitArgs -contains "push")
    $attempt = 0
    while ($true) {
        $attempt++
        $oldPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            $rawOutput = @(& git.exe @GitArgs 2>&1)
            $gitExitCode = [int]$LASTEXITCODE
            $output = (($rawOutput | ForEach-Object { $_.ToString() }) -join "`r`n")
        }
        finally {
            $ErrorActionPreference = $oldPreference
        }

        if ($gitExitCode -eq 0) {
            if ($output.Trim()) { Write-Log ("git: " + $output.Trim()) "DEBUG" }
            return $output
        }

        $lastMessage = $output.Trim()
        if ($isPush -and $lastMessage -match '(?i)stale info' -and ($GitArgs -contains "--force-with-lease")) {
            $pushIndex = [Array]::IndexOf($GitArgs,"push")
            $remoteSeen = $false
            $branchName = ""
            for ($i=$pushIndex+1; $i -lt $GitArgs.Count; $i++) {
                $arg = [string]$GitArgs[$i]
                if ($arg.StartsWith("-")) { continue }
                if (-not $remoteSeen) { $remoteSeen = $true; continue }
                $branchName = $arg
                break
            }
            if ($branchName) {
                if ($branchName.Contains(":")) { $branchName = ($branchName -split ':')[-1] }
                $branchName = $branchName -replace '^refs/heads/',''
                $oldRefreshPreference = $ErrorActionPreference
                try {
                    $ErrorActionPreference = "Continue"
                    $refreshOutput = @(& git.exe -C $WorkerDir fetch origin "refs/heads/${branchName}:refs/remotes/origin/${branchName}" 2>&1)
                    $refreshExit = [int]$LASTEXITCODE
                }
                finally {
                    $ErrorActionPreference = $oldRefreshPreference
                }
                if ($refreshExit -eq 0) {
                    Write-Log "Force-with-lease aktualisiert: origin/$branchName"
                }
                else {
                    Write-Log ("Lease-Refresh fehlgeschlagen: " + (($refreshOutput | ForEach-Object { $_.ToString() }) -join " | ")) "WARN"
                }
            }
        }

        if ($attempt -ge $Retries) {
            throw "git failed after $attempt attempt(s): git $($GitArgs -join ' ') :: $lastMessage"
        }
        Write-Log "Git-Versuch $attempt/$Retries fehlgeschlagen; erneuter Versuch." "WARN"
        Start-Sleep -Seconds ([Math]::Min(30,[Math]::Max(2,2*$attempt)))
    }
}

function Ensure-Worker {
    $gitDir = Join-Path $WorkerDir ".git"
    if (Test-Path -LiteralPath $gitDir -PathType Container) {
        $origin = (& git.exe -C $WorkerDir remote get-url origin 2>$null | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or (Get-NormalizedGitUrl $origin) -ne (Get-NormalizedGitUrl $RepoUrl)) {
            throw "Dedizierter Worker hat unerwartetes origin und wird nicht automatisch veraendert: '$origin'"
        }
        return
    }
    if (Test-Path -LiteralPath $WorkerDir) {
        $backup = "$WorkerDir.invalid-{0}" -f (Get-Date -Format "yyyyMMdd-HHmmss")
        Move-Item -LiteralPath $WorkerDir -Destination $backup
        Write-Log "Ungueltiger dedizierter Worker wurde gesichert: $backup" "WARN"
    }
    New-Item -ItemType Directory -Force -Path (Split-Path $WorkerDir -Parent) | Out-Null
    Invoke-GitSafe -GitArgs @("clone","--branch",$BaseBranch,"--single-branch",$RepoUrl,$WorkerDir) -Retries $FetchRetryCount | Out-Null
}

function Fetch-Base {
    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"fetch","origin",$BaseBranch) -Retries $FetchRetryCount | Out-Null
}

function Fetch-TaskBranch {
    param([string]$Branch)
    $oldPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = @(& git.exe -C $WorkerDir fetch origin "+refs/heads/${Branch}:refs/remotes/origin/${Branch}" 2>&1)
        $exitCode = [int]$LASTEXITCODE
    }
    finally { $ErrorActionPreference = $oldPreference }
    if ($exitCode -eq 0) { return $true }
    $text = (($output | ForEach-Object { $_.ToString() }) -join " | ")
    if ($text -match '(?i)couldn.t find remote ref|remote ref does not exist') {
        & git.exe -C $WorkerDir update-ref -d "refs/remotes/origin/$Branch" 2>$null
        return $false
    }
    throw "Task-Branch-Fetch fehlgeschlagen: $text"
}

function Read-State {
    if (-not (Test-Path -LiteralPath $stateFile)) {
        return [pscustomobject]@{schema_version=2;processed=@();failures=@()}
    }
    try {
        $state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
        if ($state.schema_version -notin @(1,2)) { throw "Schema-Version $($state.schema_version)" }
        $state.processed = @($state.processed)
        $state.failures = @($state.failures)
        $state.schema_version = 2
        return $state
    }
    catch {
        $backup = "$stateFile.corrupt-{0}" -f (Get-Date -Format "yyyyMMdd-HHmmss")
        Copy-Item -LiteralPath $stateFile -Destination $backup -Force -ErrorAction SilentlyContinue
        throw "Task-Zustand unlesbar; Sicherung: $backup :: $($_.Exception.Message)"
    }
}

function Write-State {
    param($State)
    $State.schema_version = 2
    $temporary = "$stateFile.tmp"
    $previous = "$stateFile.previous"
    if (Test-Path -LiteralPath $stateFile) { Copy-Item -LiteralPath $stateFile -Destination $previous -Force }
    [IO.File]::WriteAllText($temporary,($State | ConvertTo-Json -Depth 10),(New-Object Text.UTF8Encoding($false)))
    Move-Item -LiteralPath $temporary -Destination $stateFile -Force
}

function Get-RemoteText {
    param([string]$Path)
    $value = (& git.exe -C $WorkerDir show "origin/${BaseBranch}:$Path" 2>$null | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "Remote-Datei fehlt: $Path" }
    return $value
}

function Select-Task {
    param($State)
    $done = @($State.processed | ForEach-Object { $_.key })
    $items = @()
    foreach ($line in ((Get-RemoteText "tasks/TASK_QUEUE.txt") -split "`r?`n")) {
        $path = $line.Trim()
        if ($path -and -not $path.StartsWith("#")) {
            $items += [pscustomobject]@{path=$path;source="TASK_QUEUE"}
        }
    }
    foreach ($item in $items) {
        if (-not $item.path.StartsWith("tasks/") -or $item.path.Contains("..")) {
            throw "Ungueltiger Task-Pfad: $($item.path)"
        }
        $blob = (& git.exe -C $WorkerDir rev-parse "origin/${BaseBranch}:$($item.path)" 2>$null | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $blob) { throw "Task fehlt: $($item.path)" }
        $key = "$($item.path)|$blob"
        if ($done -notcontains $key) {
            return [pscustomobject]@{path=$item.path;blob=$blob;key=$key;source=$item.source}
        }
    }
    return $null
}

function Publish-Status {
    param(
        [string]$Phase,
        $Task = $null,
        [string]$Branch = "",
        [string]$Detail = "",
        [int]$Attempt = 0,
        [int]$RetryCount = 0,
        [string]$CheckpointSha = "",
        [int]$CheckpointNumber = 0
    )
    try {
        if (-not (Test-Path -LiteralPath (Join-Path $WorkerDir ".git") -PathType Container)) { return }
        $status = [ordered]@{
            schema_version = 2
            watcher_version = $WatcherVersion
            profile = "documents-controlling"
            updated_at = (Get-Date).ToString("o")
            phase = $Phase
            task = $(if ($Task) { $Task.path } else { $null })
            task_blob = $(if ($Task) { $Task.blob } else { $null })
            branch = $(if ($Branch) { $Branch } else { $null })
            attempt = $Attempt
            retry_count = $RetryCount
            last_verified_checkpoint_sha = $(if ($CheckpointSha) { $CheckpointSha } else { $null })
            checkpoint_number = $(if ($CheckpointNumber -gt 0) { $CheckpointNumber } else { $null })
            detail = $(if ($Detail) { $Detail } else { $null })
            machine = $env:COMPUTERNAME
            pid = $PID
        }
        $statusPath = Join-Path $tempDir "RUEDIGER_STATUS.json"
        [IO.File]::WriteAllText($statusPath,($status | ConvertTo-Json -Depth 6),(New-Object Text.UTF8Encoding($false)))
        $blob = (& git.exe -C $WorkerDir hash-object -w $statusPath | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $blob) { throw "hash-object" }
        $treeLine = "100644 blob $blob`tRUEDIGER_STATUS.json"
        $tree = ($treeLine | & git.exe -C $WorkerDir mktree | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $tree) { throw "mktree" }
        $commit = ("Documents Ruediger live status: $Phase" | & git.exe -C $WorkerDir commit-tree $tree | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $commit) { throw "commit-tree" }
        & git.exe -C $WorkerDir push origin "${commit}:refs/heads/${LiveStatusBranch}" --force 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "status push" }
    }
    catch {
        Write-Log "Live-Status konnte nicht publiziert werden: $($_.Exception.Message)" "WARN"
    }
}

function Run-Codex {
    param([string]$Exe,[string]$Prompt,$Task,[string]$Branch,$Audit)
    $promptFile = Join-Path $tempDir "documents-codex-prompt-$PID.txt"
    $stdoutFile = Join-Path $tempDir "documents-codex-last.stdout.log"
    $stderrFile = Join-Path $tempDir "documents-codex-last.stderr.log"
    $combinedFile = Join-Path $logDir "documents-codex-last-error.log"
    $script:LastCodexError = ""
    [IO.File]::WriteAllText($promptFile,$Prompt,(New-Object Text.UTF8Encoding($false)))
    Remove-Item -LiteralPath $stdoutFile,$stderrFile -Force -ErrorAction SilentlyContinue
    try {
        $processInfo = New-Object Diagnostics.ProcessStartInfo
        $processInfo.FileName = "cmd.exe"
        $processInfo.Arguments = "/d /s /c `"`"$Exe`" -c windows.sandbox=`"unelevated`" --sandbox workspace-write --ask-for-approval never exec --skip-git-repo-check -C `"$WorkerDir`" < `"$promptFile`" > `"$stdoutFile`" 2> `"$stderrFile`"`""
        $processInfo.WorkingDirectory = $WorkerDir
        $processInfo.UseShellExecute = $false
        $processInfo.CreateNoWindow = $true
        $process = New-Object Diagnostics.Process
        $process.StartInfo = $processInfo
        if (-not $process.Start()) { throw "Codex-Start fehlgeschlagen" }
        Publish-Status -Phase "ARBEITET" -Task $Task -Branch $Branch -Detail "Codex pid=$($process.Id)" -Attempt $Audit.attempt -RetryCount $Audit.retry_count -CheckpointSha $Audit.checkpoint_sha -CheckpointNumber $Audit.checkpoint_number
        $heartbeat = (Get-Date).AddSeconds($HeartbeatSeconds)
        while (-not $process.HasExited) {
            if ((Get-Date) -ge $heartbeat) {
                Write-Log "ARBEITET: Codex pid=$($process.Id)"
                Publish-Status -Phase "ARBEITET" -Task $Task -Branch $Branch -Detail "Codex pid=$($process.Id)" -Attempt $Audit.attempt -RetryCount $Audit.retry_count -CheckpointSha $Audit.checkpoint_sha -CheckpointNumber $Audit.checkpoint_number
                $heartbeat = (Get-Date).AddSeconds($HeartbeatSeconds)
            }
            Start-Sleep -Seconds 5
        }
        $process.WaitForExit()
        $exitCode = [int]$process.ExitCode
        if ($exitCode -ne 0) {
            $stderr = ""
            $stdout = ""
            if (Test-Path -LiteralPath $stderrFile) { $stderr = Get-Content -LiteralPath $stderrFile -Raw -ErrorAction SilentlyContinue }
            if (Test-Path -LiteralPath $stdoutFile) { $stdout = Get-Content -LiteralPath $stdoutFile -Raw -ErrorAction SilentlyContinue }
            $full = ("STDERR:`r`n$stderr`r`nSTDOUT:`r`n$stdout").Trim()
            [IO.File]::WriteAllText($combinedFile,$full,(New-Object Text.UTF8Encoding($false)))
            $brief = $full -replace "`r?`n"," | "
            if ($brief.Length -gt 1800) { $brief = $brief.Substring($brief.Length-1800) }
            $script:LastCodexError = $brief
            Write-Log "Codex Exit ${exitCode}: $brief" "ERROR"
        }
        return $exitCode
    }
    finally {
        Remove-Item -LiteralPath $promptFile -Force -ErrorAction SilentlyContinue
    }
}

function Verify-Remote {
    param([string]$Branch)
    $local = (& git.exe -C $WorkerDir rev-parse HEAD | Out-String).Trim()
    $line = (& git.exe -C $WorkerDir ls-remote --heads origin "refs/heads/$Branch" | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $line) { throw "Remote-Branch fehlt" }
    $remote = ($line -split '\s+')[0]
    if ($remote -ne $local) { throw "Remote-SHA ungleich: lokal=$local remote=$remote" }
    Write-Log "Remote-Verifikation PASS: $Branch @ $local"
    return $local
}

function Get-TaskBranch {
    param($Task)
    $stem = [IO.Path]::GetFileNameWithoutExtension($Task.path).ToLowerInvariant() -replace '[^a-z0-9-]+','-'
    return "ruediger/$stem-$($Task.blob.Substring(0,8))"
}

function Complete-TaskState {
    param($Task,[string]$Branch,[string]$Sha,$State,[string]$Detail)
    $State.processed += [pscustomobject]@{
        key=$Task.key;task=$Task.path;blob=$Task.blob;source=$Task.source;
        branch=$Branch;remote_commit=$Sha;verified_at=(Get-Date).ToString("o")
    }
    $State.failures = @($State.failures | Where-Object { $_.key -ne $Task.key })
    Write-State $State
    Publish-Status -Phase "FERTIG" -Task $Task -Branch $Branch -Detail $Detail
    Write-Log "FERTIG: $($Task.path) @ $Sha"
}

function Try-RecoverFinalResult {
    param($Task,[string]$Branch,$State)
    [void](Fetch-TaskBranch $Branch)
    $remoteRef = "refs/remotes/origin/$Branch"
    $remoteExists = (Invoke-DocumentsGit -Repository $WorkerDir -Arguments @("show-ref","--verify","--quiet",$remoteRef) -AllowFailure).ExitCode -eq 0
    $remoteFinal = Find-VerifiedTaskCommit -Repository $WorkerDir -Ref $remoteRef -TaskPath $Task.path -TaskBlob $Task.blob -Kind final
    if ($remoteFinal) {
        $remoteHead = (& git.exe -C $WorkerDir rev-parse $remoteRef | Out-String).Trim()
        if ($remoteHead -ne $remoteFinal.sha) { return $false }
        if (-not (Test-RemoteBranchSha -Repository $WorkerDir -Branch $Branch -ExpectedSha $remoteFinal.sha)) { throw "Finaler Remote-SHA nicht verifiziert." }
        Complete-TaskState -Task $Task -Branch $Branch -Sha $remoteFinal.sha -State $State -Detail "Bereits remote verifiziertes finales Ergebnis wiederverwendet: $($remoteFinal.sha)"
        return $true
    }
    if ($remoteExists) { return $false }

    & git.exe -C $WorkerDir show-ref --verify --quiet "refs/heads/$Branch"
    if ($LASTEXITCODE -ne 0) { return $false }
    $localFinal = Find-VerifiedTaskCommit -Repository $WorkerDir -Ref "refs/heads/$Branch" -TaskPath $Task.path -TaskBlob $Task.blob -Kind final
    if (-not $localFinal) { return $false }
    $localHead = (& git.exe -C $WorkerDir rev-parse "refs/heads/$Branch" | Out-String).Trim()
    if ($localHead -ne $localFinal.sha) { return $false }
    Preserve-UnverifiedWorktree -Task $Task
    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"checkout",$Branch) | Out-Null
    Publish-Status -Phase "FEHLER_RETRY" -Task $Task -Branch $Branch -Detail "Verifiziertes lokales Endergebnis; Remote-Push wird wiederholt."
    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"push","-u","origin",$Branch,"--force-with-lease") -Retries $FetchRetryCount | Out-Null
    $sha = Verify-Remote $Branch
    if ($sha -ne $localFinal.sha) { throw "Recovery-Remote-SHA weicht vom lokalen Ergebnis ab." }
    Complete-TaskState -Task $Task -Branch $Branch -Sha $sha -State $State -Detail "Lokales Endergebnis remote verifiziert: $sha"
    return $true
}

function Get-TaskFailure {
    param($State,$Task)
    $record = @($State.failures | Where-Object { $_.key -eq $Task.key } | Select-Object -Last 1)
    if ($record.Count -eq 0) {
        return [pscustomobject]@{key=$Task.key;task=$Task.path;attempts=0;codex_failures_without_checkpoint=0;last_checkpoint_sha="";last_checkpoint_number=0;blocked=$false;reason=""}
    }
    $item = $record[0]
    $attempts = $(if ($item.PSObject.Properties.Name -contains "attempts" -and $null -ne $item.attempts) { [int]$item.attempts } else { 0 })
    $failureCount = $(if ($item.PSObject.Properties.Name -contains "codex_failures_without_checkpoint" -and $null -ne $item.codex_failures_without_checkpoint) { [int]$item.codex_failures_without_checkpoint } else { $attempts })
    $checkpointSha = $(if ($item.PSObject.Properties.Name -contains "last_checkpoint_sha" -and $item.last_checkpoint_sha) { [string]$item.last_checkpoint_sha } else { "" })
    $checkpointNumber = $(if ($item.PSObject.Properties.Name -contains "last_checkpoint_number" -and $item.last_checkpoint_number) { [int]$item.last_checkpoint_number } else { 0 })
    $isBlocked = $(if ($item.PSObject.Properties.Name -contains "blocked") { [bool]$item.blocked } else { $false })
    $failureReason = $(if ($item.PSObject.Properties.Name -contains "reason" -and $item.reason) { [string]$item.reason } else { "" })
    return [pscustomobject]@{
        key=$Task.key;task=$Task.path
        attempts=$attempts
        codex_failures_without_checkpoint=$failureCount
        last_checkpoint_sha=$checkpointSha
        last_checkpoint_number=$checkpointNumber
        blocked=$isBlocked
        reason=$failureReason
    }
}

function Set-TaskFailure {
    param($State,$Task,$Failure)
    $State.failures = @($State.failures | Where-Object { $_.key -ne $Task.key })
    $State.failures += [pscustomobject]@{
        key=$Task.key;task=$Task.path;occurred_at=(Get-Date).ToString("o");attempts=$Failure.attempts;
        codex_failures_without_checkpoint=$Failure.codex_failures_without_checkpoint;
        last_checkpoint_sha=$Failure.last_checkpoint_sha;last_checkpoint_number=$Failure.last_checkpoint_number;
        blocked=[bool]$Failure.blocked;reason=$Failure.reason
    }
    Write-State $State
}

function Preserve-UnverifiedWorktree {
    param($Task)
    $dirty = (& git.exe -C $WorkerDir status --porcelain | Out-String).Trim()
    if (-not $dirty) { return }
    Assert-DedicatedPaths
    $label = "unverified-$($Task.blob.Substring(0,8))-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"stash","push","-u","-m",$label) | Out-Null
    Write-Log "Dirty/unverifizierter Zustand wurde nicht als Checkpoint akzeptiert und als Stash '$label' gesichert." "WARN"
}

function Prepare-TaskBranch {
    param($Task,[string]$Branch,$Resolution)
    if ($Resolution.status -eq "REJECTED") { throw "CHECKPOINT_BLOCKIERT: $($Resolution.reason)" }
    Preserve-UnverifiedWorktree -Task $Task
    Assert-DedicatedPaths
    if ($Resolution.status -eq "FOUND") {
        $checkpoint = $Resolution.checkpoint
        if ($Resolution.source -eq "remote") {
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"checkout","-B",$Branch,"refs/remotes/origin/$Branch") | Out-Null
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"reset","--hard",$checkpoint.sha) | Out-Null
        }
        else {
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"checkout",$Branch) | Out-Null
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"reset","--hard",$checkpoint.sha) | Out-Null
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"push","-u","origin",$Branch) -Retries $FetchRetryCount | Out-Null
            if (-not (Test-RemoteBranchSha -Repository $WorkerDir -Branch $Branch -ExpectedSha $checkpoint.sha)) { throw "Lokaler Checkpoint konnte nicht remote verifiziert werden." }
        }
        Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"clean","-fd") | Out-Null
        return $checkpoint
    }

    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"checkout","--detach","origin/$BaseBranch") | Out-Null
    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"reset","--hard","origin/$BaseBranch") | Out-Null
    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"clean","-fd") | Out-Null
    & git.exe -C $WorkerDir branch -D $Branch 2>$null | Out-Null
    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"checkout","-b",$Branch,"origin/$BaseBranch") | Out-Null
    return $null
}

function Compact-Worker {
    Assert-DedicatedPaths
    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"checkout","--detach","origin/$BaseBranch") | Out-Null
}

try {
    if (-not (Get-Command git.exe -ErrorAction SilentlyContinue) -and -not (Get-Command git -ErrorAction SilentlyContinue)) { throw "Git fehlt" }
    Ensure-Worker
    Remove-ExpiredLogs
    Write-Log "START Watcher=$WatcherVersion AgentRoot='$AgentRoot' WorkerDir='$WorkerDir' BaseBranch='$BaseBranch'"
    Fetch-Base

    if ($SelectionTestOnly) {
        $selectionState = Read-State
        $selection = Select-Task $selectionState
        if ($selection) { $selection | ConvertTo-Json -Compress } else { '{"selection":null}' }
        exit 0
    }

    $codexCommand = Get-Command codex.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $codexCommand) { $codexCommand = Get-Command codex -ErrorAction SilentlyContinue | Select-Object -First 1 }
    if (-not $codexCommand) { throw "Codex fehlt" }
    $CodexExe = $codexCommand.Source
    if (-not (Test-Path -LiteralPath (Join-Path (Split-Path $CodexExe -Parent) "codex-code-mode-host.exe") -PathType Leaf)) {
        throw "Codex Code-Mode-Host fehlt"
    }

    if ($DiagnosticOnly) {
        $preflight = Join-Path $runtimeDir "documents-agent-preflight.ps1"
        if (-not (Test-Path -LiteralPath $preflight -PathType Leaf)) { $preflight = Join-Path $PSScriptRoot "documents-agent-preflight.ps1" }
        & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $preflight -AgentRoot $AgentRoot
        if ($LASTEXITCODE -ne 0) { throw "Documents-Preflight STOP" }
        Publish-Status -Phase "DIAGNOSTIC_PASS" -Detail "Git und Codex erreichbar; kein CAD-Preflight."
        Write-Log "DIAGNOSTIC PASS"
        exit 0
    }

    Publish-Status -Phase "START" -Detail "Watcher $WatcherVersion aktiv."

    $infrastructureFailures = 0
    while ($true) {
        $task = $null
        $branch = ""
        try {
            Fetch-Base
            $state = Read-State
            $task = Select-Task $state
            if (-not $task) {
                Compact-Worker
                Publish-Status -Phase "WARTET" -Detail "Keine unverarbeitete freigegebene Queue-Task."
                Write-Log "WARTET: keine unverarbeitete freigegebene Queue-Task"
                Start-Sleep -Seconds $PollSeconds
                continue
            }

            $branch = Get-TaskBranch $task
            if (Try-RecoverFinalResult -Task $task -Branch $branch -State $state) {
                Compact-Worker
                $infrastructureFailures = 0
                continue
            }

            [void](Fetch-TaskBranch $branch)
            $resolution = Resolve-TaskCheckpoint -Repository $WorkerDir -Branch $branch -TaskPath $task.path -TaskBlob $task.blob
            $failure = Get-TaskFailure -State $state -Task $task
            if ($resolution.status -eq "REJECTED") {
                $failure.blocked = $true
                $failure.reason = $resolution.reason
                Set-TaskFailure -State $state -Task $task -Failure $failure
                Publish-Status -Phase "BLOCKIERT" -Task $task -Branch $branch -Detail $resolution.reason -Attempt $failure.attempts -RetryCount $failure.codex_failures_without_checkpoint -CheckpointSha $failure.last_checkpoint_sha -CheckpointNumber $failure.last_checkpoint_number
                Write-Log "BLOCKIERT: $($resolution.reason)" "ERROR"
                Start-Sleep -Seconds $PollSeconds
                continue
            }

            $resolvedSha = $(if ($resolution.checkpoint) { $resolution.checkpoint.sha } else { "" })
            if ($failure.blocked -and $resolvedSha -and $resolvedSha -ne $failure.last_checkpoint_sha) {
                $failure.blocked = $false
                $failure.codex_failures_without_checkpoint = 0
                $failure.last_checkpoint_sha = $resolvedSha
                $failure.last_checkpoint_number = $resolution.checkpoint.number
                $failure.reason = "Neuer verifizierter Checkpoint; Retry-Budget zurueckgesetzt."
                Set-TaskFailure -State $state -Task $task -Failure $failure
            }
            elseif ($failure.blocked) {
                Publish-Status -Phase "BLOCKIERT" -Task $task -Branch $branch -Detail $failure.reason -Attempt $failure.attempts -RetryCount $failure.codex_failures_without_checkpoint -CheckpointSha $failure.last_checkpoint_sha -CheckpointNumber $failure.last_checkpoint_number
                Write-Log "BLOCKIERT: Retry-Budget fuer $($task.path) erschoepft; kein neuer verifizierter Checkpoint." "WARN"
                Start-Sleep -Seconds $PollSeconds
                continue
            }

            Publish-Status -Phase "TASK_GEFUNDEN" -Task $task -Branch $branch -Detail "Freigegebene FIFO-Queue; $($resolution.reason)" -Attempt ($failure.attempts + 1) -RetryCount $failure.codex_failures_without_checkpoint -CheckpointSha $resolvedSha -CheckpointNumber $(if ($resolution.checkpoint) { $resolution.checkpoint.number } else { 0 })
            $checkpoint = Prepare-TaskBranch -Task $task -Branch $branch -Resolution $resolution
            $baseSha = $(if ($checkpoint) { $checkpoint.base_sha } else { (& git.exe -C $WorkerDir rev-parse "origin/$BaseBranch" | Out-String).Trim() })
            if ($checkpoint) {
                Publish-Status -Phase "CHECKPOINT" -Task $task -Branch $branch -Detail "Resume von verifiziertem $($resolution.source)-Checkpoint." -Attempt ($failure.attempts + 1) -RetryCount $failure.codex_failures_without_checkpoint -CheckpointSha $checkpoint.sha -CheckpointNumber $checkpoint.number
            }
            $attempt = $failure.attempts + 1
            $audit = [pscustomobject]@{
                attempt=$attempt
                retry_count=$failure.codex_failures_without_checkpoint
                checkpoint_sha=$(if ($checkpoint) { $checkpoint.sha } else { "" })
                checkpoint_number=$(if ($checkpoint) { $checkpoint.number } else { 0 })
            }
            $infrastructureFailures = 0

            $prompt = @"
Lies zuerst AGENTS.md und danach die freigegebene Auftragsdatei '$($task.path)' vollstaendig.
Fuehre genau diesen Auftrag aus. Keine neuen Funktionen oder stillen Annahmen.
Fasse bestaetigte Inhalte, Strukturen und Nutzervorgaben nicht eigenmaechtig um.
Loese reine Script-, Toolchain-, Format-, Validierungs- und Berechnungsprobleme selbststaendig, solange die freigegebene Produktidee unveraendert bleibt.
Bei echter Nutzerentscheidung STOPP/OFFEN und NUTZERENTSCHEIDUNG_ERFORDERLICH dokumentieren.
Erzeuge die geforderten Dokument-, Pruef- und Revisionsdateien sowie den maschinenlesbaren Ergebnisstatus.
Keine finale Nutzerfreigabe behaupten. Nur taskbezogene Dateien aendern.

Software-Workflow fuer diesen Versuch:
- Task-Branch: $branch; verbindlicher Task-Blob: $($task.blob); Basis-SHA: $baseSha.
- Zerlege groessere Aufgaben intern in wenige logisch abgeschlossene Schritte. Keine Mikro-Commits.
- Fuehre vor jedem Zwischen-Checkpoint die relevanten zielgerichteten Tests aus.
- Ein Checkpoint-Commit muss diese Trailer exakt enthalten:
  Ruediger-Task-Path: $($task.path)
  Ruediger-Task-Blob: $($task.blob)
  Ruediger-Base-SHA: $baseSha
  Ruediger-Checkpoint: <fortlaufende positive Nummer>
  Ruediger-Checkpoint-Verified: true
- Push jeden solchen Checkpoint auf origin/$branch. Nur bestandene, logisch abgeschlossene Teilabschnitte checkpointen.
- Vor dem finalen Ergebnis den vollstaendigen relevanten Testlauf ausfuehren. Finale Aenderungen fuer den Watcher uncommitted lassen; keinen finalen Ergebnis-Commit selbst erzeugen.
- Optimieren nur bei messbarem Problem, wiederholtem Fehler oder klarer Zeit-/Robustheitsverbesserung. Keine Refactor-Schleifen ohne konkreten Nutzen. Nach PASS den funktionierenden Workflow nicht weiter refactoren.
"@

            Push-Location $WorkerDir
            try { $code = Run-Codex -Exe $CodexExe -Prompt $prompt -Task $task -Branch $branch -Audit $audit }
            finally { Pop-Location }

            if ($code -ne 0) {
                [void](Fetch-TaskBranch $branch)
                $afterFailure = Resolve-TaskCheckpoint -Repository $WorkerDir -Branch $branch -TaskPath $task.path -TaskBlob $task.blob
                $currentCheckpoint = $(if ($afterFailure.status -eq "FOUND") { $afterFailure.checkpoint } else { $checkpoint })
                $currentSha = $(if ($currentCheckpoint) { $currentCheckpoint.sha } else { "" })
                $decision = Get-CodexRetryDecision -PreviousFailures $failure.codex_failures_without_checkpoint -PreviousCheckpointSha $failure.last_checkpoint_sha -CurrentCheckpointSha $currentSha -MaximumFailures $MaxCodexFailuresWithoutCheckpoint
                $reason = "Codex Exit $code"
                if ($script:LastCodexError) { $reason += " :: $script:LastCodexError" }
                $failure.attempts = $attempt
                $failure.codex_failures_without_checkpoint = $decision.failures_without_checkpoint
                $failure.last_checkpoint_sha = $decision.checkpoint_sha
                $failure.last_checkpoint_number = $(if ($currentCheckpoint) { $currentCheckpoint.number } else { $failure.last_checkpoint_number })
                $failure.blocked = $decision.blocked
                $failure.reason = $reason
                Set-TaskFailure -State $state -Task $task -Failure $failure
                if ($decision.new_checkpoint) {
                    Publish-Status -Phase "CHECKPOINT" -Task $task -Branch $branch -Detail "Neuer verifizierter Checkpoint trotz Codex-Fehler; Retry-Budget neu begonnen." -Attempt $attempt -RetryCount $failure.codex_failures_without_checkpoint -CheckpointSha $failure.last_checkpoint_sha -CheckpointNumber $failure.last_checkpoint_number
                }
                $phase = $(if ($failure.blocked) { "BLOCKIERT" } else { "FEHLER_RETRY" })
                Publish-Status -Phase $phase -Task $task -Branch $branch -Detail $reason -Attempt $attempt -RetryCount $failure.codex_failures_without_checkpoint -CheckpointSha $failure.last_checkpoint_sha -CheckpointNumber $failure.last_checkpoint_number
                Write-Log "$phase nach Codex-Fehler $($failure.codex_failures_without_checkpoint)/$MaxCodexFailuresWithoutCheckpoint ohne neuen Checkpoint." $(if ($failure.blocked) { "ERROR" } else { "WARN" })
                Start-Sleep -Seconds $PollSeconds
                continue
            }

            $dirtyResult = (& git.exe -C $WorkerDir status --porcelain | Out-String).Trim()
            if (-not $dirtyResult) { throw "Keine uncommitteten finalen Ergebnisdateien nach erfolgreichem Codex-Lauf." }
            $taskBlobAtHead = (& git.exe -C $WorkerDir rev-parse "HEAD:$($task.path)" | Out-String).Trim()
            if ($taskBlobAtHead -ne $task.blob) { throw "Task-Blob wurde im Arbeitsbranch veraendert." }

            Publish-Status -Phase "VALIDIERUNG" -Task $task -Branch $branch -Detail "Codex-Volltest beendet; finales Ergebnis wird committed und remote verifiziert." -Attempt $attempt -RetryCount $failure.codex_failures_without_checkpoint -CheckpointSha $(if ($checkpoint) { $checkpoint.sha } else { "" }) -CheckpointNumber $(if ($checkpoint) { $checkpoint.number } else { 0 })
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"add","-A") | Out-Null
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"commit","-m","Ruediger result for $($task.path)","-m","Ruediger-Task-Path: $($task.path)`nRuediger-Task-Blob: $($task.blob)`nRuediger-Base-SHA: $baseSha`nRuediger-Final: true") | Out-Null
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"push","-u","origin",$branch,"--force-with-lease") -Retries $FetchRetryCount | Out-Null
            $sha = Verify-Remote $branch
            $verifiedFinal = Get-VerifiedTaskCommit -Repository $WorkerDir -Commit $sha -TaskPath $task.path -TaskBlob $task.blob -Kind final
            if (-not $verifiedFinal) { throw "Finaler Commit besitzt keine gueltige Task-Identitaet." }
            Complete-TaskState -Task $task -Branch $branch -Sha $sha -State $state -Detail "Remote-Verifikation PASS: $sha"
            Compact-Worker
            $infrastructureFailures = 0
        }
        catch {
            $reason = $_.Exception.Message
            $infrastructureFailures++
            $phase = $(if ($reason.StartsWith("CHECKPOINT_BLOCKIERT:")) { "BLOCKIERT" } else { "FEHLER_RETRY" })
            Publish-Status -Phase $phase -Task $task -Branch $branch -Detail $reason
            $delay = [Math]::Min(300,[Math]::Max($PollSeconds,$PollSeconds * [Math]::Pow(2,[Math]::Min(4,$infrastructureFailures-1))))
            Write-Log "$phase Infrastruktur/Workflow: $reason; naechster Versuch fruehestens in $([int]$delay)s." "WARN"
            Start-Sleep -Seconds ([int]$delay)
        }
    }
}
finally {
    if ($lockStream) {
        try { $lockStream.Close(); $lockStream.Dispose() } catch {}
    }
}
