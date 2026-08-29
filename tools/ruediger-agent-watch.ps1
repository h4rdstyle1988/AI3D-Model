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
    [switch]$DiagnosticOnly,
    [switch]$SelectionTestOnly,
    [switch]$NoSelfUpdate
)

$ErrorActionPreference = "Stop"
$WatcherVersion = "R03.1"

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
    Write-Host "Ruediger-Watcher laeuft bereits. Zweite Instanz beendet."
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
        [int]$Retries = 1
    )
    $lastMessage = ""
    for ($attempt=1; $attempt -le $Retries; $attempt++) {
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
            if ($output.Trim()) { Write-Log ("git: " + $output.Trim()) "DEBUG" }
            return $output
        }
        $lastMessage = $output.Trim()
        if ($attempt -lt $Retries) {
            Write-Log "Git-Versuch $attempt/$Retries fehlgeschlagen; erneuter Versuch." "WARN"
            Start-Sleep -Seconds ([Math]::Min(10,2*$attempt))
        }
    }
    throw "git failed: git $($GitArgs -join ' ') :: $lastMessage"
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
        $commit = ("Ruediger live status: $Phase" | & git -C $WorkerDir commit-tree $tree | Out-String).Trim()
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

    $helper = Join-Path $runtimeDir "restart-runtime-watcher.ps1"
    if (-not (Test-Path $helper)) {
        Write-Log "Watcher aktualisiert, Restart-Helper fehlt; Neustart wird nicht automatisch ausgefuehrt." "WARN"
        return $false
    }

    Publish-Status -Phase "RESTARTING" -Detail "Neue Watcher-Version aus origin/master installiert."
    $restartArgs = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$helper`" -ParentPid $PID -AgentRoot `"$AgentRoot`" -WorkerDir `"$WorkerDir`" -SchedulerTaskName `"$SchedulerTaskName`""
    Start-Process -FilePath "powershell.exe" -ArgumentList $restartArgs -WindowStyle Hidden
    Write-Log "Selbstupdate installiert; kontrollierter Neustart eingeleitet."
    return $true
}

function Run-Codex {
    param([string]$Exe,[string]$Prompt,$Task,[string]$Branch)
    $pf = Join-Path $tempDir "codex-prompt-$PID.txt"
    [IO.File]::WriteAllText($pf,$Prompt,(New-Object Text.UTF8Encoding($false)))
    try {
        $psi = New-Object Diagnostics.ProcessStartInfo
        $psi.FileName = "cmd.exe"
        $psi.Arguments = "/d /s /c `"`"$Exe`" --sandbox workspace-write --ask-for-approval never exec < `"$pf`"`""
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
        return [int]$proc.ExitCode
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

function Compact {
    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"checkout","--detach","origin/master") | Out-Null
    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"sparse-checkout","init","--cone") | Out-Null
    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"sparse-checkout","set","tasks","tools","library","status") | Out-Null
}

try {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "Git fehlt" }
    $cc = Get-Command codex -ErrorAction SilentlyContinue
    if (-not $cc) { throw "Codex fehlt" }
    $CodexExe = $cc.Source
    if (-not (Test-Path (Join-Path (Split-Path $CodexExe -Parent) "codex-code-mode-host.exe"))) { throw "Codex Code-Mode-Host fehlt" }

    Ensure-Worker
    Remove-ExpiredLogs
    Write-Log "START Watcher=$WatcherVersion AgentRoot='$AgentRoot' WorkerDir='$WorkerDir'"
    Fetch-Master

    if ($DiagnosticOnly) {
        Ensure-Preflight -Force
        Publish-Status -Phase "DIAGNOSTIC_PASS" -Detail "Git, Codex und Preflight erreichbar."
        Write-Log "DIAGNOSTIC PASS"
        exit 0
    }

    Publish-Status -Phase "START" -Detail "Watcher $WatcherVersion aktiv."

    while ($true) {
        $task = $null
        $branch = ""
        try {
            Fetch-Master

            if (Sync-RuntimeFromRemote) {
                break
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

            Publish-Status -Phase "TASK_GEFUNDEN" -Task $task -Detail "Freigegebene FIFO-Queue."
            & git.exe -C $WorkerDir sparse-checkout disable 2>$null
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"checkout","--detach","origin/master") | Out-Null
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"reset","--hard","origin/master") | Out-Null
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"clean","-fd") | Out-Null

            $stem = [IO.Path]::GetFileNameWithoutExtension($task.path).ToLowerInvariant() -replace '[^a-z0-9-]+','-'
            $branch = "ruediger/$stem-$($task.blob.Substring(0,8))"
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
                throw "Codex Exit $code"
            }
            if (-not ((& git -C $WorkerDir status --porcelain | Out-String).Trim())) { throw "Keine Ergebnisdateien" }

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
            Compact
            continue
        }
        catch {
            $reason = $_.Exception.Message
            try {
                $fs = Read-State
                if ($task) {
                    $old = @($fs.failures | Where-Object { $_.key -eq $task.key } | Select-Object -Last 1)
                    $attempts = 1
                    if ($old.Count -gt 0 -and $old[0].attempts) { $attempts = [int]$old[0].attempts + 1 }
                    $fs.failures = @($fs.failures | Where-Object { $_.key -ne $task.key })
                    $fs.failures += [pscustomobject]@{
                        key=$task.key;task=$task.path;occurred_at=(Get-Date).ToString("o");
                        attempts=$attempts;reason=$reason
                    }
                    Write-State $fs
                }
            }
            catch { Write-Log "Fehlerstatus nicht schreibbar: $($_.Exception.Message)" "ERROR" }

            Publish-Status -Phase "FEHLER_RETRY" -Task $task -Branch $branch -Detail $reason
            Write-Log "FEHLER: $reason; automatischer Retry folgt." "WARN"
            Start-Sleep $PollSeconds
        }
    }
}
finally {
    try { $lockStream.Close(); $lockStream.Dispose() } catch {}
}