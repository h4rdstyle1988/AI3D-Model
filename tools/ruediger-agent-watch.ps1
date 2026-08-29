param(
    [string]$RepoUrl = "https://github.com/h4rdstyle1988/AI3D-Model.git",
    [string]$AgentRoot = "D:\AI3D-Agent",
    [string]$WorkerDir = "",
    [int]$PollSeconds = 60,
    [int]$LogRetentionDays = 7,
    [switch]$DiagnosticOnly,
    [int]$HeartbeatSeconds = 90
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
    $env:USERPROFILE = [Environment]::GetFolderPath("UserProfile")
}
if ([string]::IsNullOrWhiteSpace($env:HOME)) {
    $env:HOME = $env:USERPROFILE
}
if ([string]::IsNullOrWhiteSpace($env:USERPROFILE) -or -not (Test-Path $env:USERPROFILE)) {
    throw "Gueltiges Benutzerprofil konnte nicht ermittelt werden. USERPROFILE='$env:USERPROFILE' HOME='$env:HOME'"
}
if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
    throw "LOCALAPPDATA konnte nicht ermittelt werden."
}

if ([string]::IsNullOrWhiteSpace($WorkerDir)) {
    $WorkerDir = Join-Path $AgentRoot "worker\AI3D-Model-worker"
}

$stateDir = Join-Path $AgentRoot "state"
$stateFile = Join-Path $stateDir "ruediger-last-task.txt"
$logDir = Join-Path $AgentRoot "logs"
$libraryOutputDir = Join-Path $AgentRoot "outputs\project-library"
$cacheDir = Join-Path $AgentRoot "cache"
$tempDir = Join-Path $AgentRoot "temp"
$toolchainDir = Join-Path $AgentRoot "toolchain"
if (-not (Test-Path $AgentRoot -PathType Container)) {
    throw "Verbindlicher AgentRoot fehlt: $AgentRoot"
}
New-Item -ItemType Directory -Force -Path $stateDir, $logDir, $libraryOutputDir, $cacheDir, $tempDir, $toolchainDir | Out-Null

function Remove-ExpiredLogs {
    $cutoff = (Get-Date).AddDays(-$LogRetentionDays)
    Get-ChildItem -Path $logDir -File -Filter "ruediger-agent-watch-*.log" -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt $cutoff } |
        Remove-Item -Force -ErrorAction SilentlyContinue
}

Remove-ExpiredLogs
$logFile = Join-Path $logDir ("ruediger-agent-watch-{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))
$lastLogCleanupDate = (Get-Date).Date

function Write-WatcherLog {
    param(
        [Parameter(Mandatory = $true)][string]$Message,
        [ValidateSet("INFO", "WARN", "ERROR")][string]$Level = "INFO"
    )

    $line = "{0} [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff zzz"), $Level, $Message
    Add-Content -Path $script:logFile -Value $line -Encoding UTF8
    if ($Level -eq "WARN") {
        Write-Warning $Message
    }
    elseif ($Level -eq "ERROR") {
        Write-Error $Message
    }
    else {
        Write-Host $Message
    }
}

function Invoke-Git {
    param([Parameter(Mandatory = $true)][string[]]$GitArgs)

    & git @GitArgs
    if ($LASTEXITCODE -ne 0) {
        throw "git failed: git $($GitArgs -join ' ')"
    }
}

function Enter-CompactWorkerMode {
    if (-not (Test-Path (Join-Path $WorkerDir ".git"))) { return }

    # Im Ruhezustand bleiben nur Steuerdateien und die kleine Bibliothek ausgecheckt.
    # Projektordner wie outputs/ und work/ verschwinden aus dem lokalen Arbeitsbaum.
    Invoke-Git -GitArgs @("-C", $WorkerDir, "sparse-checkout", "init", "--cone")
    Invoke-Git -GitArgs @("-C", $WorkerDir, "sparse-checkout", "set", "tasks", "tools", "library")
    Write-WatcherLog "Worker im kompakten Ruhemodus: Projekt-Arbeitsordner sind nicht lokal ausgecheckt."
}

function Exit-CompactWorkerMode {
    if (-not (Test-Path (Join-Path $WorkerDir ".git"))) { return }
    & git -C $WorkerDir sparse-checkout disable 2>$null
    if ($LASTEXITCODE -ne 0) {
        # Kein aktiver Sparse-Checkout ist kein Fehler.
        $LASTEXITCODE = 0
    }
}

function Update-LocalProjectLibrary {
    $builder = Join-Path $WorkerDir "tools\build-project-library.ps1"
    if (-not (Test-Path $builder)) {
        Write-WatcherLog -Level "WARN" -Message "Bibliotheksgenerator fehlt im Worker: $builder"
        return
    }

    $indexPath = & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $builder -RepoRoot $WorkerDir -OutputDir $libraryOutputDir | Select-Object -Last 1
    if ($LASTEXITCODE -ne 0) {
        throw "Lokale Projektbibliothek konnte nicht erzeugt werden."
    }
    Write-WatcherLog "Projektbibliothek aktualisiert: $indexPath"
}

function Assert-RemoteBranchContainsHead {
    param([Parameter(Mandatory = $true)][string]$Branch)

    $localHead = (& git -C $WorkerDir rev-parse HEAD | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($localHead)) {
        throw "Lokaler Ergebnis-Commit konnte nicht ermittelt werden."
    }

    $remoteLine = (& git -C $WorkerDir ls-remote --heads origin "refs/heads/$Branch" | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($remoteLine)) {
        throw "Remote-Verifikation fehlgeschlagen: Branch '$Branch' ist auf GitHub nicht nachweisbar."
    }

    $remoteHead = ($remoteLine -split '\s+')[0]
    if ($remoteHead -ne $localHead) {
        throw "Remote-Verifikation fehlgeschlagen: lokal=$localHead remote=$remoteHead"
    }

    Write-WatcherLog "Remote-Verifikation PASS: $Branch @ $localHead"
}

function Invoke-ToolchainPreflight {
    $preflight = Join-Path $WorkerDir "tools\cad-toolchain-preflight.ps1"
    $preflightOutput = Join-Path $stateDir "toolchain-preflight.json"
    if (-not (Test-Path $preflight)) {
        Write-WatcherLog -Level "WARN" -Message "Toolchain-Preflight fehlt: $preflight"
        return
    }
    & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $preflight -AgentRoot $AgentRoot -OutputPath $preflightOutput
    if ($LASTEXITCODE -ne 0) { throw "Toolchain-Preflight fehlgeschlagen." }
    Write-WatcherLog "Toolchain-Preflight: $preflightOutput"
}

function Invoke-CodexWithHeartbeat {
    param([string]$Executable, [string]$PromptText)

    $job = Start-Job -ScriptBlock {
        param($Exe, $Prompt)
        & $Exe --sandbox workspace-write --ask-for-approval never exec $Prompt
        [pscustomobject]@{ RuedigerCodexExitCode = $LASTEXITCODE }
    } -ArgumentList $Executable, $PromptText
    $nextHeartbeat = (Get-Date).AddSeconds($HeartbeatSeconds)
    $exitCode = $null
    try {
        while ($job.State -in @("Running", "NotStarted")) {
            if ((Get-Date) -ge $nextHeartbeat) {
                Write-WatcherLog "ARBEITET: Codex laeuft fuer Task weiter (job=$($job.Id))."
                $nextHeartbeat = (Get-Date).AddSeconds($HeartbeatSeconds)
            }
            Start-Sleep -Seconds 5
        }
        $remaining = @(Receive-Job -Job $job)
        foreach ($item in $remaining) {
            if ($null -ne $item.RuedigerCodexExitCode) { $exitCode = [int]$item.RuedigerCodexExitCode }
            else { Write-Output $item }
        }
        if ($job.State -ne "Completed") { throw "Codex-Job Status=$($job.State)" }
        if ($null -eq $exitCode) { throw "Codex-Exitcode fehlt." }
        return $exitCode
    }
    finally { Remove-Job -Job $job -Force -ErrorAction SilentlyContinue }
}

try {
    Write-WatcherLog "START process=$PID user=$([Environment]::UserName) machine=$env:COMPUTERNAME diagnostic=$DiagnosticOnly"
    Write-WatcherLog "ENV USERPROFILE='$env:USERPROFILE' HOME='$env:HOME' LOCALAPPDATA='$env:LOCALAPPDATA' AgentRoot='$AgentRoot' WorkerDir='$WorkerDir'"
    Write-WatcherLog "Log-Aufbewahrung: $LogRetentionDays Tage"

    $gitCommand = Get-Command git -ErrorAction SilentlyContinue
    if (-not $gitCommand) {
        throw "Git wurde nicht gefunden. PATH='$env:PATH'"
    }
    $GitExe = $gitCommand.Source
    if ([string]::IsNullOrWhiteSpace($GitExe)) { $GitExe = $gitCommand.Path }
    Write-WatcherLog "Git CLI: $GitExe"

    $codexCommand = Get-Command codex -ErrorAction SilentlyContinue
    if (-not $codexCommand) {
        throw "Codex CLI wurde nicht gefunden. PATH='$env:PATH'"
    }
    $CodexExe = $codexCommand.Source
    if ([string]::IsNullOrWhiteSpace($CodexExe)) { $CodexExe = $codexCommand.Path }
    if ([string]::IsNullOrWhiteSpace($CodexExe) -or -not (Test-Path $CodexExe)) {
        throw "Codex CLI wurde aufgeloest, aber die EXE ist nicht erreichbar: '$CodexExe'"
    }
    Write-WatcherLog "Codex CLI: $CodexExe"
    Write-WatcherLog "Codex HOME: $env:HOME"

    if ($DiagnosticOnly) {
        Invoke-ToolchainPreflight
        Write-WatcherLog "DIAGNOSTIC PASS: Scheduler-Kontext kann PowerShell, Benutzerprofil, D:-Ablage, Logpfad, Git und Codex CLI erreichen. Keine Task verarbeitet."
        exit 0
    }

    if (-not (Test-Path (Join-Path $WorkerDir ".git"))) {
        if (Test-Path $WorkerDir) {
            throw "WorkerDir existiert bereits, ist aber kein Git-Repository: $WorkerDir"
        }
        Invoke-Git -GitArgs @("clone", $RepoUrl, $WorkerDir)
    }

    Write-WatcherLog "Ruediger-Watcher aktiv. Worker: $WorkerDir"
    $compactReady = $false

    while ($true) {
        try {
            if ((Get-Date).Date -ne $lastLogCleanupDate) {
                Remove-ExpiredLogs
                $script:logFile = Join-Path $logDir ("ruediger-agent-watch-{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))
                $lastLogCleanupDate = (Get-Date).Date
            }

            Invoke-Git -GitArgs @("-C", $WorkerDir, "fetch", "origin", "master")

            $taskPath = (& git -C $WorkerDir show "origin/master:tasks/CURRENT_TASK.txt" 2>$null | Out-String).Trim()
            if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($taskPath) -or $taskPath -eq "NONE") {
                if (-not $compactReady) {
                    Invoke-Git -GitArgs @("-C", $WorkerDir, "checkout", "--detach", "origin/master")
                    Enter-CompactWorkerMode
                    Update-LocalProjectLibrary
                    $compactReady = $true
                }
                Start-Sleep -Seconds $PollSeconds
                continue
            }

            $taskBlob = (& git -C $WorkerDir rev-parse "origin/master:$taskPath" 2>$null | Out-String).Trim()
            if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($taskBlob)) {
                throw "Aktive Task existiert im Remote nicht: $taskPath"
            }

            $taskKey = "$taskPath|$taskBlob"
            $lastKey = if (Test-Path $stateFile) { (Get-Content $stateFile -Raw).Trim() } else { "" }
            if ($taskKey -eq $lastKey) {
                if (-not $compactReady) {
                    Invoke-Git -GitArgs @("-C", $WorkerDir, "checkout", "--detach", "origin/master")
                    Enter-CompactWorkerMode
                    Update-LocalProjectLibrary
                    $compactReady = $true
                }
                Start-Sleep -Seconds $PollSeconds
                continue
            }

            $compactReady = $false
            Exit-CompactWorkerMode

            # DEDIZIERTER Worker: Reset/Clean nur hier, niemals im normalen Benutzer-Arbeitsbaum.
            Invoke-Git -GitArgs @("-C", $WorkerDir, "checkout", "--detach", "origin/master")
            Invoke-Git -GitArgs @("-C", $WorkerDir, "reset", "--hard", "origin/master")
            Invoke-Git -GitArgs @("-C", $WorkerDir, "clean", "-fd")

            $stem = [IO.Path]::GetFileNameWithoutExtension($taskPath).ToLowerInvariant() -replace '[^a-z0-9-]+','-'
            $shortBlob = $taskBlob.Substring(0, [Math]::Min(8, $taskBlob.Length))
            $branch = "ruediger/$stem-$shortBlob"

            & git -C $WorkerDir show-ref --verify --quiet "refs/heads/$branch"
            if ($LASTEXITCODE -eq 0) {
                Invoke-Git -GitArgs @("-C", $WorkerDir, "branch", "-D", $branch)
            }

            Invoke-Git -GitArgs @("-C", $WorkerDir, "checkout", "-b", $branch, "origin/master")
            Invoke-ToolchainPreflight

            $prompt = @"
Lies zuerst AGENTS.md und danach die aktive Auftragsdatei '$taskPath' vollstaendig.
Fuehre genau diesen Auftrag im aktuellen Repository aus.
Keine neuen Funktionen oder stillen Annahmen erfinden.
Schuetze bestaetigte Geometrie und Nutzermaße.
Wenn ein laut Task konstruktiv relevanter Punkt offen ist, dokumentiere STOPP/OFFEN statt zu raten.
Erzeuge alle im Auftrag geforderten CAD-/STL-/Pruef-/Revisionsdateien im Repository.
Fuehre technische Validierungen aus, soweit die lokale Toolchain sie erlaubt.
Keine finale Nutzerfreigabe behaupten.
Aendere ausschliesslich Dateien, die fuer diesen Auftrag erforderlich sind.
"@

            Push-Location $WorkerDir
            try {
                Write-WatcherLog "Starte Codex fuer: $taskPath"
                $codexExit = Invoke-CodexWithHeartbeat -Executable $CodexExe -PromptText $prompt
            }
            finally {
                Pop-Location
            }

            if ($codexExit -ne 0) {
                throw "Codex-Lauf fehlgeschlagen (Exit $codexExit)."
            }

            $changes = (& git -C $WorkerDir status --porcelain | Out-String).Trim()
            if ([string]::IsNullOrWhiteSpace($changes)) {
                throw "Codex hat keine Ergebnisdateien erzeugt."
            }

            Invoke-Git -GitArgs @("-C", $WorkerDir, "add", "-A")
            Invoke-Git -GitArgs @("-C", $WorkerDir, "commit", "-m", "Ruediger result for $taskPath")
            Invoke-Git -GitArgs @("-C", $WorkerDir, "push", "-u", "origin", $branch, "--force-with-lease")
            Assert-RemoteBranchContainsHead -Branch $branch

            Set-Content -Path $stateFile -Value $taskKey -Encoding UTF8
            Write-WatcherLog "Task abgeschlossen und auf GitHub verifiziert: $branch"

            # Erst NACH verifiziertem Remote-Push lokale Projekt-Arbeitsdaten aus dem sichtbaren Worker entfernen.
            Invoke-Git -GitArgs @("-C", $WorkerDir, "checkout", "--detach", "origin/master")
            Enter-CompactWorkerMode
            Update-LocalProjectLibrary
            $compactReady = $true
        }
        catch {
            Write-WatcherLog -Level "WARN" -Message ("LOOP ERROR: " + $_.Exception.Message)
        }

        Start-Sleep -Seconds $PollSeconds
    }
}
catch {
    try {
        Write-WatcherLog -Level "ERROR" -Message ("FATAL: " + $_.Exception.Message)
    }
    catch {
        Write-Error $_
    }
    exit 1
}
