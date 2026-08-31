param(
    [string]$RepoUrl = "https://github.com/h4rdstyle1988/AI3D-Model.git",
    [string]$AgentRoot = "D:\AI3D-Agent",
    [string]$WorkerDir = "",
    [string]$SchedulerTaskName = "AI3D-Ruediger-Agent",
    [int]$PollSeconds = 30,
    [int]$HeartbeatSeconds = 90,
    [int]$PreflightMaxAgeMinutes = 360,
    [int]$FetchRetryCount = 3,
    [int]$LogRetentionDays = 7,
    [string]$LocalLargeArtifactRoot = "D:\3D-Models\generated\_ruediger-local-large-artifacts",
    [switch]$DiagnosticOnly,
    [switch]$SelectionTestOnly,
    [switch]$HardlimitSelfTestOnly,
    [switch]$NoSelfUpdate
)

$ErrorActionPreference = "Continue"
$PSDefaultParameterValues["*:ErrorAction"] = "Stop"
$WatcherVersion = "R03.11"
$AgentName = "Hannes"
$NormalArtifactLimitBytes = [int64]90000000
$GitHubHardLimitBytes = [int64]100000000
$env:GIT_TERMINAL_PROMPT = "0"

if ($PollSeconds -lt 5) { throw "PollSeconds muss mindestens 5 sein." }
if ($HeartbeatSeconds -lt 60 -or $HeartbeatSeconds -gt 120) { throw "HeartbeatSeconds muss zwischen 60 und 120 liegen." }
if ($FetchRetryCount -lt 1) { throw "FetchRetryCount muss mindestens 1 sein." }
if (-not $WorkerDir) { $WorkerDir = Join-Path $AgentRoot "worker\AI3D-Model-worker" }
if (-not (Test-Path -LiteralPath $AgentRoot -PathType Container)) { throw "AgentRoot fehlt: $AgentRoot" }

$stateDir = Join-Path $AgentRoot "state"
$stateFile = Join-Path $stateDir "ruediger-task-state.json"
$preflightCache = Join-Path $stateDir "toolchain-preflight.json"
$logDir = Join-Path $AgentRoot "logs"
$runtimeDir = Join-Path $AgentRoot "runtime"
$tempDir = Join-Path $AgentRoot "temp"
$lockPath = Join-Path $stateDir "ruediger-watcher.lock"

New-Item -ItemType Directory -Force -Path $stateDir,$logDir,$runtimeDir,$tempDir,(Join-Path $AgentRoot "toolchain") | Out-Null
$logFile = Join-Path $logDir ("ruediger-agent-watch-{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))

try {
    $lockStream = [System.IO.File]::Open($lockPath,[System.IO.FileMode]::OpenOrCreate,[System.IO.FileAccess]::ReadWrite,[System.IO.FileShare]::None)
}
catch {
    Write-Host "Hannes-Watcher laeuft bereits. Zweite Instanz beendet."
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
    Get-ChildItem -LiteralPath $logDir -File -Filter "ruediger-agent-watch-*.log" -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt $cutoff } |
        Remove-Item -Force -ErrorAction SilentlyContinue
}

function Invoke-GitSafe {
    param(
        [Parameter(Mandatory=$true)][string[]]$GitArgs,
        [int]$Retries = 1,
        [switch]$Quiet
    )
    $lastMessage = ""
    $isPush = ($GitArgs -contains "push")
    $attempt = 0

    while ($true) {
        $attempt++
        $oldErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            $rawOutput = @(& git.exe @GitArgs 2>&1)
            $gitExitCode = [int]$LASTEXITCODE
            $output = (($rawOutput | ForEach-Object { $_.ToString() }) -join "`r`n")
        }
        finally {
            $ErrorActionPreference = $oldErrorActionPreference
        }

        if ($gitExitCode -eq 0) {
            if (-not $Quiet -and $output.Trim()) { Write-Log ("git: " + $output.Trim()) "DEBUG" }
            return $output
        }

        $lastMessage = $output.Trim()

        if ($isPush -and $lastMessage -match '(?i)stale info' -and ($GitArgs -contains "--force-with-lease")) {
            try {
                $pushIndex = [Array]::IndexOf($GitArgs,"push")
                $remoteSeen = $false
                $branchName = ""
                for ($i=$pushIndex+1; $i -lt $GitArgs.Count; $i++) {
                    $arg = [string]$GitArgs[$i]
                    if ($arg.StartsWith("-")) { continue }
                    if (-not $remoteSeen) {
                        $remoteSeen = $true
                        continue
                    }
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
                        Write-Log "Force-with-lease aktualisiert: origin/$branchName" "INFO"
                    }
                    else {
                        Write-Log ("Lease-Refresh fehlgeschlagen: " + (($refreshOutput | ForEach-Object { $_.ToString() }) -join " | ")) "WARN"
                    }
                }
            }
            catch {
                Write-Log "Lease-Refresh Ausnahme: $($_.Exception.Message)" "WARN"
            }
        }

        if ($isPush) {
            Write-Log "Git-Push fehlgeschlagen; lokales CAD-Ergebnis bleibt erhalten (Versuch $attempt/$Retries)." "WARN"
            if ($attempt -ge $Retries) {
                throw "git push failed after $attempt attempt(s): git $($GitArgs -join ' ') :: $lastMessage"
            }
            Start-Sleep -Seconds ([Math]::Min(30,[Math]::Max(2,2*$attempt)))
            continue
        }

        if ($attempt -ge $Retries) {
            throw "git failed: git $($GitArgs -join ' ') :: $lastMessage"
        }

        Write-Log "Git-Versuch $attempt/$Retries fehlgeschlagen; erneuter Versuch." "WARN"
        Start-Sleep -Seconds ([Math]::Min(10,2*$attempt))
    }
}

function Ensure-Worker {
    if (Test-Path (Join-Path $WorkerDir ".git")) { return }
    if (Test-Path $WorkerDir) {
        $backup = "$WorkerDir.invalid-{0}" -f (Get-Date -Format "yyyyMMdd-HHmmss")
        Move-Item -LiteralPath $WorkerDir -Destination $backup
        Write-Log "Ungueltiger Worker wurde gesichert: $backup" "WARN"
    }
    New-Item -ItemType Directory -Force -Path (Split-Path $WorkerDir -Parent) | Out-Null
    Invoke-GitSafe -GitArgs @("clone",$RepoUrl,$WorkerDir) -Retries $FetchRetryCount | Out-Null
}

function Fetch-Master {
    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"fetch","origin","master") -Retries $FetchRetryCount | Out-Null
}

function Read-State {
    if (-not (Test-Path -LiteralPath $stateFile)) {
        return [pscustomobject]@{schema_version=3;processed=@();failures=@()}
    }
    try {
        $s = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
        if ($s.schema_version -ne 2 -and $s.schema_version -ne 3) { throw "Schema-Version $($s.schema_version)" }
        $s.schema_version = 3
        $s.processed = @($s.processed)
        $s.failures = @($s.failures)
        return $s
    }
    catch {
        $backup = "$stateFile.corrupt-{0}" -f (Get-Date -Format "yyyyMMdd-HHmmss")
        Copy-Item -LiteralPath $stateFile -Destination $backup -Force -ErrorAction SilentlyContinue
        throw "Task-Zustand unlesbar; Sicherung: $backup :: $($_.Exception.Message)"
    }
}

function Write-State {
    param($State)
    $State.schema_version = 3
    $tmp = "$stateFile.tmp"
    $bak = "$stateFile.previous"
    if (Test-Path $stateFile) { Copy-Item -LiteralPath $stateFile -Destination $bak -Force }
    $State | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $tmp -Encoding UTF8
    Move-Item -LiteralPath $tmp -Destination $stateFile -Force
}

function Remote-Text {
    param([string]$Path)
    $v = (& git -C $WorkerDir show "origin/master:$Path" 2>$null | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "Remote-Datei fehlt: $Path" }
    return $v
}

function Select-Task {
    param($State)
    $done = @($State.processed | ForEach-Object { $_.key })
    $items = @()
    foreach ($line in ((Remote-Text "tasks/TASK_QUEUE.txt") -split "`r?`n")) {
        $p = $line.Trim()
        if ($p -and -not $p.StartsWith("#")) {
            $items += [pscustomobject]@{path=$p;source="TASK_QUEUE"}
        }
    }
    foreach ($i in $items) {
        if (-not $i.path.StartsWith("tasks/") -or $i.path.Contains("..")) { throw "Ungueltiger Task-Pfad: $($i.path)" }
        $blob = (& git -C $WorkerDir rev-parse "origin/master:$($i.path)" 2>$null | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $blob) { throw "Task fehlt: $($i.path)" }
        $key = "$($i.path)|$blob"
        if ($done -notcontains $key) {
            return [pscustomobject]@{path=$i.path;blob=$blob;key=$key;source=$i.source}
        }
    }
    return $null
}

function Test-PreflightCache {
    if (-not (Test-Path $preflightCache)) { return $false }
    try {
        $p = Get-Content -LiteralPath $preflightCache -Raw | ConvertFrom-Json
        if ($p.status -ne "PASS") { return $false }
        $generated = [DateTimeOffset]::Parse($p.generated_at)
        return (([DateTimeOffset]::Now - $generated).TotalMinutes -lt $PreflightMaxAgeMinutes)
    }
    catch { return $false }
}

function Ensure-Preflight {
    param([switch]$Force)
    if (-not $Force -and (Test-PreflightCache)) {
        Write-Log "Preflight-Cache PASS; erneuter Volltest nicht notwendig."
        return
    }
    $p = Join-Path $WorkerDir "tools\cad-toolchain-preflight.ps1"
    if (-not (Test-Path $p)) { throw "Preflight fehlt: $p" }
    & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $p -AgentRoot $AgentRoot -OutputPath $preflightCache
    if ($LASTEXITCODE -ne 0) { throw "Preflight STOPP" }
    Write-Log "Preflight PASS und Cache aktualisiert."
}

function Publish-Status {
    param(
        [string]$Phase,
        $Task = $null,
        [string]$Branch = "",
        [string]$Detail = ""
    )
    try {
        if (-not (Test-Path (Join-Path $WorkerDir ".git"))) { return }
        $obj = [ordered]@{
            schema_version = 1
            agent_name = $AgentName
            watcher_version = $WatcherVersion
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
        [IO.File]::WriteAllText($statusPath,($obj | ConvertTo-Json -Depth 6),(New-Object Text.UTF8Encoding($false)))
        $blob = (& git -C $WorkerDir hash-object -w $statusPath | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $blob) { throw "hash-object" }
        $treeLine = "100644 blob $blob`tRUEDIGER_STATUS.json"
        $tree = ($treeLine | & git -C $WorkerDir mktree | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $tree) { throw "mktree" }
        $commit = ("Hannes live status: $Phase" | & git -C $WorkerDir commit-tree $tree | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $commit) { throw "commit-tree" }
        & git -C $WorkerDir push origin "${commit}:refs/heads/ruediger/live-status" --force 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "status push" }
    }
    catch {
        Write-Log "Live-Status konnte nicht publiziert werden: $($_.Exception.Message)" "WARN"
    }
}

function Get-NormalizedText {
    param([string]$Text)
    if ($null -eq $Text) { return "" }
    return ($Text -replace "`r`n","`n").TrimEnd("`n")
}

function Sync-RuntimeFromRemote {
    if ($NoSelfUpdate) { return $false }
    $names = @(
        "ruediger-agent-watch.ps1",
        "cad-toolchain-preflight.ps1",
        "repair-runtime.ps1",
        "restart-runtime-watcher.ps1"
    )
    $watcherChanged = $false
    foreach ($name in $names) {
        $remote = (& git -C $WorkerDir show "origin/master:tools/$name" 2>$null | Out-String)
        if ($LASTEXITCODE -ne 0) { continue }
        $target = Join-Path $runtimeDir $name
        $local = ""
        if (Test-Path $target) { $local = Get-Content -LiteralPath $target -Raw }
        if ((Get-NormalizedText $remote) -ne (Get-NormalizedText $local)) {
            $tmp = "$target.new"
            [IO.File]::WriteAllText($tmp,(Get-NormalizedText $remote) + "`r`n",(New-Object Text.UTF8Encoding($false)))
            Move-Item -LiteralPath $tmp -Destination $target -Force
            Write-Log "Runtime aktualisiert: $name"
            if ($name -eq "ruediger-agent-watch.ps1") { $watcherChanged = $true }
        }
    }
    if (-not $watcherChanged) { return $false }

    Publish-Status -Phase "RESTARTING" -Detail "Neue Watcher-Version aus origin/master installiert; Launcher-Reload angefordert."
    Write-Log "Selbstupdate installiert; Launcher-Reload-Code 75 wird angefordert."
    return $true
}

function Run-Codex {
    param([string]$Exe,[string]$Prompt,$Task,[string]$Branch)
    $localGeneratedDir = "D:\3D-Models\generated"
    $pf = Join-Path $tempDir "codex-prompt-$PID.txt"
    $codexOut = Join-Path $tempDir "codex-last.stdout.log"
    $codexErr = Join-Path $tempDir "codex-last.stderr.log"
    $codexCombined = Join-Path $logDir "codex-last-error.log"
    $script:LastCodexError = ""
    [IO.File]::WriteAllText($pf,$Prompt,(New-Object Text.UTF8Encoding($false)))
    Remove-Item -LiteralPath $codexOut,$codexErr -Force -ErrorAction SilentlyContinue
    try {
        if (-not (Test-Path -LiteralPath $localGeneratedDir -PathType Container)) {
            New-Item -ItemType Directory -Path $localGeneratedDir | Out-Null
        }
        $psi = New-Object Diagnostics.ProcessStartInfo
        $psi.FileName = "cmd.exe"
        $psi.Arguments = "/d /s /c `"`"$Exe`" -c windows.sandbox=`"unelevated`" --sandbox workspace-write --ask-for-approval never --add-dir `"$localGeneratedDir`" exec --skip-git-repo-check -C `"$WorkerDir`" < `"$pf`" > `"$codexOut`" 2> `"$codexErr`"`""
        $psi.WorkingDirectory = $WorkerDir
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $proc = New-Object Diagnostics.Process
        $proc.StartInfo = $psi
        if (-not $proc.Start()) { throw "Codex-Start fehlgeschlagen" }
        Publish-Status -Phase "ARBEITET" -Task $Task -Branch $Branch -Detail "Codex pid=$($proc.Id)"
        $heartbeat = (Get-Date).AddSeconds($HeartbeatSeconds)
        while (-not $proc.HasExited) {
            if ((Get-Date) -ge $heartbeat) {
                Write-Log "ARBEITET: Codex pid=$($proc.Id)"
                Publish-Status -Phase "ARBEITET" -Task $Task -Branch $Branch -Detail "Codex pid=$($proc.Id)"
                $heartbeat = (Get-Date).AddSeconds($HeartbeatSeconds)
            }
            Start-Sleep 5
        }
        $proc.WaitForExit()
        $exitCode = [int]$proc.ExitCode
        if ($exitCode -ne 0) {
            $stderr = ""
            $stdout = ""
            if (Test-Path -LiteralPath $codexErr) { $stderr = Get-Content -LiteralPath $codexErr -Raw -ErrorAction SilentlyContinue }
            if (Test-Path -LiteralPath $codexOut) { $stdout = Get-Content -LiteralPath $codexOut -Raw -ErrorAction SilentlyContinue }
            $full = ("STDERR:`r`n$stderr`r`nSTDOUT:`r`n$stdout").Trim()
            [IO.File]::WriteAllText($codexCombined,$full,(New-Object Text.UTF8Encoding($false)))
            $brief = $full -replace "`r?`n"," | "
            if ($brief.Length -gt 1800) { $brief = $brief.Substring($brief.Length-1800) }
            $script:LastCodexError = $brief
            Write-Log "Codex Exit ${exitCode}: $brief" "ERROR"
        }
        return $exitCode
    }
    finally {
        Remove-Item -LiteralPath $pf -Force -ErrorAction SilentlyContinue
    }
}

function Verify-Remote {
    param([string]$Branch)
    $local = (& git -C $WorkerDir rev-parse HEAD | Out-String).Trim()
    $line = (& git -C $WorkerDir ls-remote --heads origin "refs/heads/$Branch" | Out-String).Trim()
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
    $expectedSubject = "Hannes result for $($Task.path)"
    $legacySubject = "Ruediger result for $($Task.path)"
    if ($subject -ne $expectedSubject -and $subject -ne $legacySubject) { return $false }

    $commitTaskBlob = (& git.exe -C $WorkerDir rev-parse "${commit}:$($Task.path)" 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $commitTaskBlob -or $commitTaskBlob -ne $Task.blob) { return $false }

    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"checkout",$Branch) | Out-Null
    if ((& git.exe -C $WorkerDir status --porcelain | Out-String).Trim()) {
        throw "Lokales abgeschlossenes Ergebnis ist unerwartet dirty: $Branch"
    }

    Assert-CommitTreeLimit -LimitBytes $GitHubHardLimitBytes -Label "GitHub-100-MB-Hardlimit"
    Assert-CommitTreeLimit -LimitBytes $NormalArtifactLimitBytes -Label "90-MB-Sicherheitsgrenze"
    Publish-Status -Phase "PUSH_RETRY" -Task $Task -Branch $Branch -Detail "Lokales abgeschlossenes Ergebnis zur exakten Task-Revision erkannt; nur Remote-Push wird wiederholt."
    Write-Log "PUSH_RETRY: vorhandenes lokales Ergebnis wird wiederverwendet: $Branch @ $commit"
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

function Compact {
    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"checkout","--detach","origin/master") | Out-Null
    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"sparse-checkout","init","--cone") | Out-Null
    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"sparse-checkout","set","tasks","tools","library","status") | Out-Null
}

function Invoke-WatcherMain {
try {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "Git fehlt" }
    if ($HardlimitSelfTestOnly) {
        Invoke-HardlimitSelfTest
        exit 0
    }
    $cc = Get-Command codex -ErrorAction SilentlyContinue
    if (-not $cc) { throw "Codex fehlt" }
    $CodexExe = $cc.Source
    if (-not (Test-Path (Join-Path (Split-Path $CodexExe -Parent) "codex-code-mode-host.exe"))) { throw "Codex Code-Mode-Host fehlt" }

    Ensure-Worker
    Remove-ExpiredLogs
    Write-Log "START Agent=$AgentName Watcher=$WatcherVersion AgentRoot='$AgentRoot' WorkerDir='$WorkerDir'"
    Fetch-Master

    if ($DiagnosticOnly) {
        Ensure-Preflight -Force
        Publish-Status -Phase "DIAGNOSTIC_PASS" -Detail "Git, Codex und Preflight erreichbar."
        Write-Log "DIAGNOSTIC PASS"
        exit 0
    }

    Publish-Status -Phase "START" -Detail "$AgentName Watcher $WatcherVersion aktiv."

    while ($true) {
        $task = $null
        $branch = ""
        try {
            Fetch-Master

            if (Sync-RuntimeFromRemote) {
                exit 75
            }

            $state = Read-State
            $task = Select-Task $state

            if ($SelectionTestOnly) {
                if ($task) { $task | ConvertTo-Json -Compress } else { '{"selection":null}' }
                exit 0
            }

            if (-not $task) {
                Compact
                Publish-Status -Phase "WARTET" -Detail "Keine unverarbeitete freigegebene Queue-Task."
                Write-Log "WARTET: keine unverarbeitete freigegebene Queue-Task"
                Start-Sleep $PollSeconds
                continue
            }

            $branch = Get-TaskBranch $task
            $terminalFailure = @($state.failures | Where-Object { $_.key -eq $task.key -and $_.terminal } | Select-Object -Last 1)
            if ($terminalFailure.Count -gt 0) {
                Publish-Status -Phase "STOPP" -Task $task -Branch $branch -Detail $terminalFailure[0].reason
                Write-Log "STOPP: $($terminalFailure[0].reason)" "ERROR"
                Start-Sleep $PollSeconds
                continue
            }
            if (Try-RecoverLocalResult -Task $task -Branch $branch -State $state) {
                Compact
                continue
            }

            Publish-Status -Phase "TASK_GEFUNDEN" -Task $task -Detail "Freigegebene FIFO-Queue."
            & git.exe -C $WorkerDir sparse-checkout disable 2>$null
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"checkout","--detach","origin/master") | Out-Null
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"reset","--hard","origin/master") | Out-Null
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"clean","-fd") | Out-Null

            & git.exe -C $WorkerDir branch -D $branch 2>$null | Out-Null
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"checkout","-b",$branch,"origin/master") | Out-Null

            Ensure-Preflight

            $prompt = @"
Lies zuerst AGENTS.md und danach die freigegebene Auftragsdatei '$($task.path)' vollstaendig.
Fuehre genau diesen Auftrag aus. Keine neuen Funktionen oder stillen Annahmen.
Schuetze bestaetigte Geometrie und Nutzermasse.
Loese reine CAD-, Mesh-, Script-, Toolchain-, Support-, Druckorientierungs- und Berechnungsprobleme selbststaendig, solange die freigegebene Produktidee unveraendert bleibt.
Bei echter Nutzerentscheidung STOPP/OFFEN und NUTZERENTSCHEIDUNG_ERFORDERLICH dokumentieren.
Erzeuge geforderte CAD-/STL-/Pruef-/Revisionsdateien und den maschinenlesbaren Ergebnisstatus.
Keine finale Nutzerfreigabe behaupten. Nur taskbezogene Dateien aendern.
"@

            Push-Location $WorkerDir
            try { $code = Run-Codex -Exe $CodexExe -Prompt $prompt -Task $task -Branch $branch }
            finally { Pop-Location }

            if ($code -ne 0) {
                Ensure-Preflight -Force
                if ($script:LastCodexError) { throw "Codex Exit $code :: $script:LastCodexError" }
                throw "Codex Exit $code"
            }
            if (-not ((& git -C $WorkerDir status --porcelain | Out-String).Trim())) { throw "Keine Ergebnisdateien" }

            $manifest = Resolve-LargeResultArtifacts -Task $task
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"add","-A") | Out-Null
            Assert-StagedArtifactLimit
            $validationDetail = "Codex beendet; 90-MB-Pruefung PASS; Ergebnis wird committed und remote verifiziert."
            if ($manifest) { $validationDetail += " Grossartefakt-Manifest: $manifest" }
            Publish-Status -Phase "VALIDIERT" -Task $task -Branch $branch -Detail $validationDetail
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"commit","-m","Hannes result for $($task.path)") | Out-Null
            Assert-CommitTreeLimit -LimitBytes $GitHubHardLimitBytes -Label "GitHub-100-MB-Hardlimit"
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
            Compact
            continue
        }
        catch {
            $reason = $_.Exception.Message
            $isHardLimitStop = $reason -match '^GIT_HARDLIMIT_STOPP:'
            try {
                $fs = Read-State
                if ($task) {
                    $old = @($fs.failures | Where-Object { $_.key -eq $task.key } | Select-Object -Last 1)
                    $attempts = 1
                    if ($old.Count -gt 0 -and $old[0].attempts) { $attempts = [int]$old[0].attempts + 1 }
                    $fs.failures = @($fs.failures | Where-Object { $_.key -ne $task.key })
                    $fs.failures += [pscustomobject]@{
                        key=$task.key;task=$task.path;occurred_at=(Get-Date).ToString("o");
                        attempts=$attempts;reason=$reason;terminal=$isHardLimitStop;
                        category=$(if ($isHardLimitStop) { "GIT_HARDLIMIT_STOPP" } else { "TECHNICAL_RETRY" })
                    }
                    Write-State $fs
                }
            }
            catch { Write-Log "Fehlerstatus nicht schreibbar: $($_.Exception.Message)" "ERROR" }

            if ($isHardLimitStop) {
                Publish-Status -Phase "STOPP" -Task $task -Branch $branch -Detail $reason
                Write-Log "STOPP: $reason; lokales Ergebnis bleibt erhalten, kein Push und kein automatischer Task-Neulauf." "ERROR"
            }
            else {
                Publish-Status -Phase "FEHLER_RETRY" -Task $task -Branch $branch -Detail $reason
                Write-Log "FEHLER: $reason; automatischer Retry folgt." "WARN"
            }
            Start-Sleep $PollSeconds
        }
    }
}
finally {
    try { $lockStream.Close(); $lockStream.Dispose() } catch {}
}
}

function Get-TaskSlug {
    param($Task)
    $stem = [IO.Path]::GetFileNameWithoutExtension([string]$Task.path).ToLowerInvariant()
    $stem = $stem -replace '^task-','' -replace '[^a-z0-9-]+','-'
    return ($stem.Trim('-') + '-' + ([string]$Task.blob).Substring(0,8))
}

function Get-ChangedResultPaths {
    $paths = @()
    $tracked = Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"-c","core.quotepath=false","diff","--name-only","--diff-filter=ACMR","origin/master","--") -Quiet
    $untracked = Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"-c","core.quotepath=false","ls-files","--others","--exclude-standard") -Quiet
    foreach ($line in (($tracked + "`n" + $untracked) -split "`r?`n")) {
        $path = $line.Trim()
        if ($path -and $paths -notcontains $path) { $paths += $path }
    }
    return @($paths)
}

function Test-TemporaryDiagnosticArtifact {
    param([string]$RelativePath)
    $p = $RelativePath.Replace('\','/')
    if ($p -match '(?i)(^|/)(work|tmp|temp|diagnostics?|debug|cache)(/|$)') { return $true }
    $leaf = [IO.Path]::GetFileName($p)
    if ($leaf -match '(?i)(^|[-_.])(intermediate|diagnostic|debug|scratch|cache|temporary|temp)([-_.]|$)') { return $true }
    if ([IO.Path]::GetExtension($leaf) -match '(?i)^\.(log|tmp|bak|cache)$') { return $true }
    return $false
}

function Test-TaskRequiresArtifact {
    param([string]$RelativePath,[string]$TaskText)
    $p = $RelativePath.Replace('\','/')
    $leaf = [IO.Path]::GetFileName($p)
    if ($TaskText.IndexOf($p,[StringComparison]::OrdinalIgnoreCase) -ge 0) { return $true }
    if ($TaskText.IndexOf($leaf,[StringComparison]::OrdinalIgnoreCase) -ge 0) { return $true }

    $extensionTerms = @{
        '.stl'='\bSTL\b'; '.3mf'='\b3MF\b'; '.glb'='\bGLB\b'; '.gltf'='\bGLTF\b';
        '.step'='\bSTEP\b'; '.stp'='\bSTP\b'; '.scad'='\b(OpenSCAD|SCAD)\b';
        '.fcstd'='\b(FreeCAD|FCStd)\b'; '.blend'='\b(Blender|BLEND)\b';
        '.obj'='\bOBJ\b'; '.ply'='\bPLY\b'; '.gcode'='\bG-?Code\b'
    }
    $ext = [IO.Path]::GetExtension($leaf).ToLowerInvariant()
    if ($extensionTerms.ContainsKey($ext) -and $TaskText -match ('(?i)' + $extensionTerms[$ext])) { return $true }
    return $false
}

function Write-LargeArtifactManifest {
    param($Task,[string]$ManifestRelativePath,[object[]]$Artifacts,[int64]$NormalLimitBytes,[int64]$HardLimitBytes)
    $manifestPath = Join-Path $WorkerDir ($ManifestRelativePath -replace '/','\')
    New-Item -ItemType Directory -Force -Path (Split-Path $manifestPath -Parent) | Out-Null
    $manifest = [ordered]@{
        schema_version = 1
        agent_name = $AgentName
        task = $Task.path
        task_blob = $Task.blob
        generated_at = (Get-Date).ToString('o')
        normal_artifact_limit_bytes = $NormalLimitBytes
        github_hard_limit_bytes = $HardLimitBytes
        artifacts = @($Artifacts)
    }
    [IO.File]::WriteAllText($manifestPath,($manifest | ConvertTo-Json -Depth 10),(New-Object Text.UTF8Encoding($false)))
}

function Move-LargeArtifactToLocalStorage {
    param([string]$SourcePath,[string]$RelativePath,[string]$TaskStorageRoot,[string]$Sha256)
    $destination = Join-Path $TaskStorageRoot ($RelativePath -replace '/','\')
    New-Item -ItemType Directory -Force -Path (Split-Path $destination -Parent) | Out-Null
    if (Test-Path -LiteralPath $destination -PathType Leaf) {
        $existingHash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($existingHash -ne $Sha256) {
            $destination = "$destination.$($Sha256.Substring(0,12))"
        }
    }
    if (Test-Path -LiteralPath $destination -PathType Leaf) {
        $existingHash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($existingHash -ne $Sha256) { throw "Lokales Grossartefakt-Ziel kollidiert: $destination" }
        Remove-Item -LiteralPath $SourcePath -Force
    }
    else {
        Move-Item -LiteralPath $SourcePath -Destination $destination
    }
    return $destination
}

function New-VerifiedLosslessExchange {
    param([string]$SourcePath,[string]$SourceSha256,[int64]$LimitBytes)
    $archivePath = "$SourcePath.zip"
    if (Test-Path -LiteralPath $archivePath) { $archivePath = "$SourcePath.hannes-exchange.zip" }
    $verifyDir = Join-Path $tempDir ("hardlimit-exchange-verify-" + [Guid]::NewGuid().ToString('N'))
    try {
        Compress-Archive -LiteralPath $SourcePath -DestinationPath $archivePath -CompressionLevel Optimal
        $archive = Get-Item -LiteralPath $archivePath
        if ($archive.Length -gt $LimitBytes) {
            Remove-Item -LiteralPath $archivePath -Force
            return $null
        }
        New-Item -ItemType Directory -Force -Path $verifyDir | Out-Null
        Expand-Archive -LiteralPath $archivePath -DestinationPath $verifyDir
        $expanded = @(Get-ChildItem -LiteralPath $verifyDir -Recurse -File)
        if ($expanded.Count -ne 1) { throw "Austauscharchiv enthaelt nicht genau eine Datei." }
        $expandedHash = (Get-FileHash -LiteralPath $expanded[0].FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($expandedHash -ne $SourceSha256) { throw "SHA-256 der Rueckgewinnung stimmt nicht ueberein." }
        return $archivePath
    }
    catch {
        if (Test-Path -LiteralPath $archivePath -PathType Leaf) { Remove-Item -LiteralPath $archivePath -Force }
        Write-Log "Verlustfreie Austauschdarstellung fehlgeschlagen: $($_.Exception.Message)" "WARN"
        return $null
    }
    finally {
        if (Test-Path -LiteralPath $verifyDir -PathType Container) {
            $resolvedVerify = [IO.Path]::GetFullPath($verifyDir)
            $resolvedTemp = [IO.Path]::GetFullPath($tempDir).TrimEnd('\') + '\'
            if ($resolvedVerify.StartsWith($resolvedTemp,[StringComparison]::OrdinalIgnoreCase)) {
                Remove-Item -LiteralPath $resolvedVerify -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

function Resolve-LargeResultArtifacts {
    param($Task,[int64]$NormalLimitBytes=$NormalArtifactLimitBytes,[int64]$HardLimitBytes=$GitHubHardLimitBytes)
    $taskPath = Join-Path $WorkerDir (([string]$Task.path) -replace '/','\')
    $taskText = Get-Content -LiteralPath $taskPath -Raw
    $taskSlug = Get-TaskSlug $Task
    $taskStorageRoot = Join-Path $LocalLargeArtifactRoot $taskSlug
    $manifestRelativePath = "outputs/infrastructure/hannes-large-artifacts/$taskSlug/LOCAL-LARGE-ARTIFACTS.json"
    $artifacts = @()

    foreach ($relativePath in @(Get-ChangedResultPaths)) {
        $sourcePath = Join-Path $WorkerDir ($relativePath -replace '/','\')
        if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) { continue }
        $file = Get-Item -LiteralPath $sourcePath
        if ($file.Length -le $NormalLimitBytes) { continue }

        $sha256 = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
        $isTemporary = Test-TemporaryDiagnosticArtifact $relativePath
        $isRequired = Test-TaskRequiresArtifact -RelativePath $relativePath -TaskText $taskText
        if ($isRequired) { $isTemporary = $false }
        $exchangeRelativePath = $null
        $exchangeSha256 = $null
        $reason = "Temporaeres/diagnostisches Grossartefakt oberhalb der 90-MB-Sicherheitsgrenze."
        $mode = "local_only"

        if (-not $isTemporary) {
            $exchangePath = New-VerifiedLosslessExchange -SourcePath $sourcePath -SourceSha256 $sha256 -LimitBytes $NormalLimitBytes
            if (-not $exchangePath) {
                throw "GIT_HARDLIMIT_STOPP: Verbindliche oder nicht eindeutig temporaere Datei kann nicht verlustfrei unter $NormalLimitBytes Bytes dargestellt werden: $relativePath ($($file.Length) Bytes). Original bleibt lokal erhalten."
            }
            $exchangeRelativePath = $exchangePath.Substring($WorkerDir.TrimEnd('\').Length).TrimStart('\').Replace('\','/')
            $exchangeSha256 = (Get-FileHash -LiteralPath $exchangePath -Algorithm SHA256).Hash.ToLowerInvariant()
            $reason = "Verbindliche oder nicht eindeutig temporaere Grossdatei; verifizierte verlustfreie ZIP-Austauschdarstellung im Git-Ergebnis."
            $mode = "lossless_exchange"
        }

        $localPath = Move-LargeArtifactToLocalStorage -SourcePath $sourcePath -RelativePath $relativePath -TaskStorageRoot $taskStorageRoot -Sha256 $sha256
        $artifacts += [pscustomobject][ordered]@{
            original_path = $relativePath.Replace('\','/')
            local_path = $localPath
            size_bytes = [int64]$file.Length
            sha256 = $sha256
            reason = $reason
            handling = $mode
            required_final_or_unknown = (-not $isTemporary)
            exchange_path = $exchangeRelativePath
            exchange_sha256 = $exchangeSha256
        }
        Write-LargeArtifactManifest -Task $Task -ManifestRelativePath $manifestRelativePath -Artifacts $artifacts -NormalLimitBytes $NormalLimitBytes -HardLimitBytes $HardLimitBytes
        Write-Log "Grossartefakt gesichert: $relativePath -> $localPath ($mode)" "INFO"
    }
    if ($artifacts.Count -gt 0) { return $manifestRelativePath }
    return $null
}

function Assert-StagedArtifactLimit {
    param([int64]$LimitBytes=$NormalArtifactLimitBytes)
    $changed = Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"-c","core.quotepath=false","diff","--cached","--name-only","--diff-filter=ACMR","origin/master","--") -Quiet
    $oversize = @()
    foreach ($line in ($changed -split "`r?`n")) {
        $relativePath = $line.Trim()
        if (-not $relativePath) { continue }
        $path = Join-Path $WorkerDir ($relativePath -replace '/','\')
        if ((Test-Path -LiteralPath $path -PathType Leaf) -and (Get-Item -LiteralPath $path).Length -gt $LimitBytes) {
            $oversize += "$relativePath ($((Get-Item -LiteralPath $path).Length) Bytes)"
        }
    }
    if ($oversize.Count -gt 0) {
        throw "GIT_HARDLIMIT_STOPP: Dateien oberhalb der 90-MB-Sicherheitsgrenze sind noch fuer den Commit vorgemerkt: $($oversize -join '; ')"
    }
    Write-Log "90-MB-Pruefung PASS: alle neuen/geaenderten Ergebnisdateien <= $LimitBytes Bytes."
}

function Assert-CommitTreeLimit {
    param([int64]$LimitBytes,[string]$Label)
    $tree = Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"-c","core.quotepath=false","ls-tree","-r","-l","HEAD") -Quiet
    $oversize = @()
    foreach ($line in ($tree -split "`r?`n")) {
        if ($line -match '^\d+\s+blob\s+[0-9a-f]+\s+(\d+)\t(.+)$') {
            $size = [int64]$Matches[1]
            $path = $Matches[2]
            if ($size -gt $LimitBytes) { $oversize += "$path ($size Bytes)" }
        }
    }
    if ($oversize.Count -gt 0) {
        throw "GIT_HARDLIMIT_STOPP: $Label blockiert den Push; Commit enthaelt: $($oversize -join '; ')"
    }
    Write-Log "$Label PASS: Commit-Baum enthaelt keine Datei > $LimitBytes Bytes."
}

function Invoke-HardlimitSelfTest {
    $originalWorker = $script:WorkerDir
    $originalLocalRoot = $script:LocalLargeArtifactRoot
    $testRoot = Join-Path $tempDir ("hannes-hardlimit-selftest-" + [Guid]::NewGuid().ToString('N'))
    try {
        if ($NormalArtifactLimitBytes -ne 90000000 -or $GitHubHardLimitBytes -ne 100000000) { throw "Produktive Grenzwerte sind falsch." }
        $script:WorkerDir = Join-Path $testRoot "repo"
        $script:LocalLargeArtifactRoot = Join-Path $testRoot "local-large"
        New-Item -ItemType Directory -Force -Path $script:WorkerDir | Out-Null
        Invoke-GitSafe -GitArgs @("-C",$script:WorkerDir,"init") | Out-Null
        Invoke-GitSafe -GitArgs @("-C",$script:WorkerDir,"config","user.name","Hannes Selftest") | Out-Null
        Invoke-GitSafe -GitArgs @("-C",$script:WorkerDir,"config","user.email","hannes-selftest@localhost") | Out-Null
        New-Item -ItemType Directory -Force -Path (Join-Path $script:WorkerDir "tasks") | Out-Null
        [IO.File]::WriteAllText((Join-Path $script:WorkerDir "tasks\TASK-SELFTEST.md"),"Finale Austauschdatei: outputs/final-large.bin`n",(New-Object Text.UTF8Encoding($false)))
        Invoke-GitSafe -GitArgs @("-C",$script:WorkerDir,"add","-A") | Out-Null
        Invoke-GitSafe -GitArgs @("-C",$script:WorkerDir,"commit","-m","selftest base") | Out-Null
        Invoke-GitSafe -GitArgs @("-C",$script:WorkerDir,"branch","-M","master") | Out-Null
        Invoke-GitSafe -GitArgs @("-C",$script:WorkerDir,"update-ref","refs/remotes/origin/master","HEAD") | Out-Null
        $blob = (Invoke-GitSafe -GitArgs @("-C",$script:WorkerDir,"rev-parse","HEAD:tasks/TASK-SELFTEST.md")).Trim()
        $task = [pscustomobject]@{path="tasks/TASK-SELFTEST.md";blob=$blob;key="selftest|$blob";source="SELFTEST"}

        New-Item -ItemType Directory -Force -Path (Join-Path $script:WorkerDir "work"),(Join-Path $script:WorkerDir "outputs") | Out-Null
        foreach ($path in @((Join-Path $script:WorkerDir "work\diagnostic-large.bin"),(Join-Path $script:WorkerDir "outputs\final-large.bin"))) {
            $stream = [IO.File]::Open($path,[IO.FileMode]::Create,[IO.FileAccess]::Write,[IO.FileShare]::None)
            try { $stream.SetLength(900001) } finally { $stream.Dispose() }
        }
        $boundaryPath = Join-Path $script:WorkerDir "outputs\boundary.bin"
        $stream = [IO.File]::Open($boundaryPath,[IO.FileMode]::Create,[IO.FileAccess]::Write,[IO.FileShare]::None)
        try { $stream.SetLength(900000) } finally { $stream.Dispose() }
        $manifestRelative = Resolve-LargeResultArtifacts -Task $task -NormalLimitBytes 900000 -HardLimitBytes 1000000
        if (-not $manifestRelative) { throw "Manifest wurde nicht erzeugt." }
        $manifest = Get-Content -LiteralPath (Join-Path $script:WorkerDir ($manifestRelative -replace '/','\')) -Raw | ConvertFrom-Json
        if (@($manifest.artifacts).Count -ne 2) { throw "Manifest enthaelt nicht zwei Testartefakte." }
        if (Test-Path -LiteralPath (Join-Path $script:WorkerDir "work\diagnostic-large.bin")) { throw "Diagnostikdatei blieb im Repository." }
        if (Test-Path -LiteralPath (Join-Path $script:WorkerDir "outputs\final-large.bin")) { throw "Finale Originaldatei blieb unkomprimiert im Repository." }
        if (-not (Test-Path -LiteralPath (Join-Path $script:WorkerDir "outputs\final-large.bin.zip"))) { throw "Verlustfreie Austauschdatei fehlt." }
        if (-not (Test-Path -LiteralPath $boundaryPath)) { throw "Datei exakt auf der Sicherheitsgrenze wurde faelschlich entfernt." }
        Invoke-GitSafe -GitArgs @("-C",$script:WorkerDir,"add","-A") | Out-Null
        Assert-StagedArtifactLimit -LimitBytes 900000
        Invoke-GitSafe -GitArgs @("-C",$script:WorkerDir,"commit","-m","selftest protected result") | Out-Null
        Assert-CommitTreeLimit -LimitBytes 1000000 -Label "GitHub-Hardlimit-Selbsttest"

        $stoppPath = Join-Path $script:WorkerDir "outputs\final-stopp.bin"
        $randomBytes = New-Object byte[] 900001
        $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
        try { $rng.GetBytes($randomBytes) } finally { $rng.Dispose() }
        [IO.File]::WriteAllBytes($stoppPath,$randomBytes)
        $stopped = $false
        try { Resolve-LargeResultArtifacts -Task $task -NormalLimitBytes 900000 -HardLimitBytes 1000000 | Out-Null }
        catch { if ($_.Exception.Message -match '^GIT_HARDLIMIT_STOPP:') { $stopped = $true } else { throw } }
        if (-not $stopped -or -not (Test-Path -LiteralPath $stoppPath -PathType Leaf)) {
            throw "Nicht verkleinerbare geschuetzte Grossdatei wurde nicht mit erhaltenem Original gestoppt."
        }

        $hardFile = Join-Path $script:WorkerDir "hardlimit.bin"
        $stream = [IO.File]::Open($hardFile,[IO.FileMode]::Create,[IO.FileAccess]::Write,[IO.FileShare]::None)
        try { $stream.SetLength(1000001) } finally { $stream.Dispose() }
        Invoke-GitSafe -GitArgs @("-C",$script:WorkerDir,"add","hardlimit.bin") | Out-Null
        Invoke-GitSafe -GitArgs @("-C",$script:WorkerDir,"commit","-m","selftest forbidden commit") | Out-Null
        $blocked = $false
        try { Assert-CommitTreeLimit -LimitBytes 1000000 -Label "GitHub-Hardlimit-Selbsttest" }
        catch { if ($_.Exception.Message -match '^GIT_HARDLIMIT_STOPP:') { $blocked = $true } else { throw } }
        if (-not $blocked) { throw "Commit mit Datei oberhalb des Hardlimits wurde nicht blockiert." }
        [pscustomobject][ordered]@{
            agent_name = $AgentName
            watcher_version = $WatcherVersion
            status = "PASS"
            normal_limit_bytes = $NormalArtifactLimitBytes
            github_hard_limit_bytes = $GitHubHardLimitBytes
            temporary_artifact_relocated = $true
            exact_boundary_accepted = $true
            lossless_exchange_verified = $true
            unshrinkable_final_stopped_with_original = $true
            oversized_commit_blocked = $true
        } | ConvertTo-Json -Compress
    }
    finally {
        $script:WorkerDir = $originalWorker
        $script:LocalLargeArtifactRoot = $originalLocalRoot
        if (Test-Path -LiteralPath $testRoot -PathType Container) {
            $resolvedTest = [IO.Path]::GetFullPath($testRoot)
            $resolvedTemp = [IO.Path]::GetFullPath($tempDir).TrimEnd('\') + '\'
            if ($resolvedTest.StartsWith($resolvedTemp,[StringComparison]::OrdinalIgnoreCase)) {
                Remove-Item -LiteralPath $resolvedTest -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

Invoke-WatcherMain
