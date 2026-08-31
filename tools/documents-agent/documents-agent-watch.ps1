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
    [int]$LogRetentionDays = 7,
    [switch]$DiagnosticOnly,
    [switch]$SelectionTestOnly
)

$ErrorActionPreference = "Continue"
$PSDefaultParameterValues["*:ErrorAction"] = "Stop"
$WatcherVersion = "DOCUMENTS-R01"
$env:GIT_TERMINAL_PROMPT = "0"

if ($PollSeconds -lt 5) { throw "PollSeconds muss mindestens 5 sein." }
if ($HeartbeatSeconds -lt 60 -or $HeartbeatSeconds -gt 120) { throw "HeartbeatSeconds muss zwischen 60 und 120 liegen." }
if ($FetchRetryCount -lt 1) { throw "FetchRetryCount muss mindestens 1 sein." }
if (-not $WorkerDir) { $WorkerDir = Join-Path $AgentRoot "worker\Documents-Controlling-clear-worker" }

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

function Read-State {
    if (-not (Test-Path -LiteralPath $stateFile)) {
        return [pscustomobject]@{schema_version=1;processed=@();failures=@()}
    }
    try {
        $state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
        if ($state.schema_version -ne 1) { throw "Schema-Version $($state.schema_version)" }
        $state.processed = @($state.processed)
        $state.failures = @($state.failures)
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
    $State.schema_version = 1
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
        [string]$Detail = ""
    )
    try {
        if (-not (Test-Path -LiteralPath (Join-Path $WorkerDir ".git") -PathType Container)) { return }
        $status = [ordered]@{
            schema_version = 1
            watcher_version = $WatcherVersion
            profile = "documents-controlling"
            updated_at = (Get-Date).ToString("o")
            phase = $Phase
            task = $(if ($Task) { $Task.path } else { $null })
            task_blob = $(if ($Task) { $Task.blob } else { $null })
            branch = $(if ($Branch) { $Branch } else { $null })
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
    param([string]$Exe,[string]$Prompt,$Task,[string]$Branch)
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
        Publish-Status -Phase "ARBEITET" -Task $Task -Branch $Branch -Detail "Codex pid=$($process.Id)"
        $heartbeat = (Get-Date).AddSeconds($HeartbeatSeconds)
        while (-not $process.HasExited) {
            if ((Get-Date) -ge $heartbeat) {
                Write-Log "ARBEITET: Codex pid=$($process.Id)"
                Publish-Status -Phase "ARBEITET" -Task $Task -Branch $Branch -Detail "Codex pid=$($process.Id)"
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

function Try-RecoverLocalResult {
    param($Task,[string]$Branch,$State)
    & git.exe -C $WorkerDir show-ref --verify --quiet "refs/heads/$Branch"
    if ($LASTEXITCODE -ne 0) { return $false }
    $commit = (& git.exe -C $WorkerDir rev-parse $Branch | Out-String).Trim()
    if (-not $commit) { return $false }
    $subject = (& git.exe -C $WorkerDir log -1 --format=%s $commit | Out-String).Trim()
    if ($subject -ne "Ruediger result for $($Task.path)") { return $false }
    $commitTaskBlob = (& git.exe -C $WorkerDir rev-parse "${commit}:$($Task.path)" 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $commitTaskBlob -or $commitTaskBlob -ne $Task.blob) { return $false }
    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"checkout",$Branch) | Out-Null
    if ((& git.exe -C $WorkerDir status --porcelain | Out-String).Trim()) {
        throw "Lokales abgeschlossenes Ergebnis ist unerwartet dirty: $Branch"
    }
    Publish-Status -Phase "FEHLER_RETRY" -Task $Task -Branch $Branch -Detail "Exaktes lokales Ergebnis erkannt; nur Remote-Push wird wiederholt."
    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"push","-u","origin",$Branch,"--force-with-lease") -Retries $FetchRetryCount | Out-Null
    $sha = Verify-Remote $Branch
    if ($sha -ne $commit) { throw "Recovery-Remote-SHA weicht vom lokalen Ergebnis ab: lokal=$commit remote=$sha" }
    $State.processed += [pscustomobject]@{
        key=$Task.key;task=$Task.path;blob=$Task.blob;source=$Task.source;
        branch=$Branch;remote_commit=$sha;verified_at=(Get-Date).ToString("o")
    }
    $State.failures = @($State.failures | Where-Object { $_.key -ne $Task.key })
    Write-State $State
    Publish-Status -Phase "FERTIG" -Task $Task -Branch $Branch -Detail "Lokales Ergebnis wiederverwendet; Remote-Verifikation PASS: $sha"
    Write-Log "FERTIG aus lokalem Recovery: $($Task.path) @ $sha"
    return $true
}

function Compact-Worker {
    Assert-DedicatedPaths
    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"checkout","--detach","origin/$BaseBranch") | Out-Null
    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"sparse-checkout","init","--cone") | Out-Null
    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"sparse-checkout","set","tasks","tools") | Out-Null
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
            if (Try-RecoverLocalResult -Task $task -Branch $branch -State $state) {
                Compact-Worker
                continue
            }

            Publish-Status -Phase "TASK_GEFUNDEN" -Task $task -Detail "Freigegebene FIFO-Queue."
            Assert-DedicatedPaths
            & git.exe -C $WorkerDir sparse-checkout disable 2>$null
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"checkout","--detach","origin/$BaseBranch") | Out-Null
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"reset","--hard","origin/$BaseBranch") | Out-Null
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"clean","-fd") | Out-Null
            & git.exe -C $WorkerDir branch -D $branch 2>$null | Out-Null
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"checkout","-b",$branch,"origin/$BaseBranch") | Out-Null

            $prompt = @"
Lies zuerst AGENTS.md und danach die freigegebene Auftragsdatei '$($task.path)' vollstaendig.
Fuehre genau diesen Auftrag aus. Keine neuen Funktionen oder stillen Annahmen.
Fasse bestaetigte Inhalte, Strukturen und Nutzervorgaben nicht eigenmaechtig um.
Loese reine Script-, Toolchain-, Format-, Validierungs- und Berechnungsprobleme selbststaendig, solange die freigegebene Produktidee unveraendert bleibt.
Bei echter Nutzerentscheidung STOPP/OFFEN und NUTZERENTSCHEIDUNG_ERFORDERLICH dokumentieren.
Erzeuge die geforderten Dokument-, Pruef- und Revisionsdateien sowie den maschinenlesbaren Ergebnisstatus.
Keine finale Nutzerfreigabe behaupten. Nur taskbezogene Dateien aendern.
"@

            Push-Location $WorkerDir
            try { $code = Run-Codex -Exe $CodexExe -Prompt $prompt -Task $task -Branch $branch }
            finally { Pop-Location }

            if ($code -ne 0) {
                if ($script:LastCodexError) { throw "Codex Exit $code :: $script:LastCodexError" }
                throw "Codex Exit $code"
            }
            if (-not ((& git.exe -C $WorkerDir status --porcelain | Out-String).Trim())) { throw "Keine Ergebnisdateien" }

            Publish-Status -Phase "VALIDIERT" -Task $task -Branch $branch -Detail "Codex beendet; Ergebnis wird committed und remote verifiziert."
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"add","-A") | Out-Null
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"commit","-m","Ruediger result for $($task.path)") | Out-Null
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"push","-u","origin",$branch,"--force-with-lease") -Retries $FetchRetryCount | Out-Null
            $sha = Verify-Remote $branch

            $state.processed += [pscustomobject]@{
                key=$task.key;task=$task.path;blob=$task.blob;source=$task.source;
                branch=$branch;remote_commit=$sha;verified_at=(Get-Date).ToString("o")
            }
            $state.failures = @($state.failures | Where-Object { $_.key -ne $task.key })
            Write-State $state
            Publish-Status -Phase "FERTIG" -Task $task -Branch $branch -Detail "Remote-Verifikation PASS: $sha"
            Write-Log "FERTIG: $($task.path); naechste Queue-Task wird sofort bewertet."
            Compact-Worker
        }
        catch {
            $reason = $_.Exception.Message
            try {
                $failureState = Read-State
                if ($task) {
                    $old = @($failureState.failures | Where-Object { $_.key -eq $task.key } | Select-Object -Last 1)
                    $attempts = 1
                    if ($old.Count -gt 0 -and $old[0].attempts) { $attempts = [int]$old[0].attempts + 1 }
                    $failureState.failures = @($failureState.failures | Where-Object { $_.key -ne $task.key })
                    $failureState.failures += [pscustomobject]@{
                        key=$task.key;task=$task.path;occurred_at=(Get-Date).ToString("o");attempts=$attempts;reason=$reason
                    }
                    Write-State $failureState
                }
            }
            catch { Write-Log "Fehlerstatus nicht schreibbar: $($_.Exception.Message)" "ERROR" }
            Publish-Status -Phase "FEHLER_RETRY" -Task $task -Branch $branch -Detail $reason
            Write-Log "FEHLER: $reason; automatischer Retry folgt." "WARN"
            Start-Sleep -Seconds $PollSeconds
        }
    }
}
finally {
    if ($lockStream) {
        try { $lockStream.Close(); $lockStream.Dispose() } catch {}
    }
}
