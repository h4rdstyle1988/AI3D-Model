param(
    [string]$RepoUrl = "https://github.com/h4rdstyle1988/AI3D-Model.git",
    [string]$WorkerDir = "$env:USERPROFILE\Documents\ChatGPT\AI3D Model-worker",
    [int]$PollSeconds = 60,
    [switch]$DiagnosticOnly
)

$ErrorActionPreference = "Stop"

# Task Scheduler / non-interactive shells can start without HOME even though USERPROFILE exists.
# Codex needs a resolvable home directory for its config/auth state and PATH aliases.
if ([string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
    $env:USERPROFILE = [Environment]::GetFolderPath("UserProfile")
}
if ([string]::IsNullOrWhiteSpace($env:HOME)) {
    $env:HOME = $env:USERPROFILE
}
if ([string]::IsNullOrWhiteSpace($env:USERPROFILE) -or -not (Test-Path $env:USERPROFILE)) {
    throw "Gueltiges Benutzerprofil konnte nicht ermittelt werden. USERPROFILE='$env:USERPROFILE' HOME='$env:HOME'"
}

# Falls der Default-Workerpfad wegen eines beim Start fehlenden USERPROFILE leer/falsch gebildet wurde,
# korrigiere nur diesen Default. Ein explizit uebergebener WorkerDir bleibt unveraendert.
if ([string]::IsNullOrWhiteSpace($WorkerDir) -or $WorkerDir -eq "\Documents\ChatGPT\AI3D Model-worker") {
    $WorkerDir = Join-Path $env:USERPROFILE "Documents\ChatGPT\AI3D Model-worker"
}

$stateDir = Join-Path $env:LOCALAPPDATA "AI3D-Model"
$stateFile = Join-Path $stateDir "ruediger-last-task.txt"
$logFile = Join-Path $stateDir "ruediger-agent-watch.log"
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

function Write-WatcherLog {
    param(
        [Parameter(Mandatory = $true)][string]$Message,
        [ValidateSet("INFO", "WARN", "ERROR")][string]$Level = "INFO"
    )

    $line = "{0} [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff zzz"), $Level, $Message
    Add-Content -Path $logFile -Value $line -Encoding UTF8
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

try {
    Write-WatcherLog "START process=$PID user=$([Environment]::UserName) machine=$env:COMPUTERNAME diagnostic=$DiagnosticOnly"
    Write-WatcherLog "ENV USERPROFILE='$env:USERPROFILE' HOME='$env:HOME' LOCALAPPDATA='$env:LOCALAPPDATA' WorkerDir='$WorkerDir'"

    $gitCommand = Get-Command git -ErrorAction SilentlyContinue
    if (-not $gitCommand) {
        throw "Git wurde nicht gefunden. PATH='$env:PATH'"
    }
    $GitExe = $gitCommand.Source
    if ([string]::IsNullOrWhiteSpace($GitExe)) {
        $GitExe = $gitCommand.Path
    }
    Write-WatcherLog "Git CLI: $GitExe"

    $codexCommand = Get-Command codex -ErrorAction SilentlyContinue
    if (-not $codexCommand) {
        throw "Codex CLI wurde nicht gefunden. PATH='$env:PATH'"
    }
    $CodexExe = $codexCommand.Source
    if ([string]::IsNullOrWhiteSpace($CodexExe)) {
        $CodexExe = $codexCommand.Path
    }
    if ([string]::IsNullOrWhiteSpace($CodexExe) -or -not (Test-Path $CodexExe)) {
        throw "Codex CLI wurde aufgeloest, aber die EXE ist nicht erreichbar: '$CodexExe'"
    }
    Write-WatcherLog "Codex CLI: $CodexExe"
    Write-WatcherLog "Codex HOME: $env:HOME"

    if ($DiagnosticOnly) {
        Write-WatcherLog "DIAGNOSTIC PASS: Scheduler-Kontext kann PowerShell, Benutzerprofil, Logpfad, Git und Codex CLI erreichen. Keine Task verarbeitet."
        exit 0
    }

    if (-not (Test-Path (Join-Path $WorkerDir ".git"))) {
        if (Test-Path $WorkerDir) {
            throw "WorkerDir existiert bereits, ist aber kein Git-Repository: $WorkerDir"
        }
        Invoke-Git -GitArgs @("clone", $RepoUrl, $WorkerDir)
    }

    Write-WatcherLog "Ruediger-Watcher aktiv. Worker: $WorkerDir"

    while ($true) {
        try {
            Invoke-Git -GitArgs @("-C", $WorkerDir, "fetch", "origin", "master")

            $taskPath = (& git -C $WorkerDir show "origin/master:tasks/CURRENT_TASK.txt" 2>$null | Out-String).Trim()
            if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($taskPath) -or $taskPath -eq "NONE") {
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
                Start-Sleep -Seconds $PollSeconds
                continue
            }

            # DEDIZIERTER Worker: Hier sind Reset/Clean erlaubt, der normale Benutzer-Arbeitsbaum bleibt unberuehrt.
            Invoke-Git -GitArgs @("-C", $WorkerDir, "checkout", "--detach", "origin/master")
            Invoke-Git -GitArgs @("-C", $WorkerDir, "reset", "--hard", "origin/master")
            Invoke-Git -GitArgs @("-C", $WorkerDir, "clean", "-fd")

            $stem = [IO.Path]::GetFileNameWithoutExtension($taskPath).ToLowerInvariant() -replace '[^a-z0-9-]+','-'
            $shortBlob = $taskBlob.Substring(0, [Math]::Min(8, $taskBlob.Length))
            $branch = "ruediger/$stem-$shortBlob"

            # Nur loeschen, wenn der lokale Branch wirklich existiert. Ein erstmaliger Lauf darf hier nicht abbrechen.
            & git -C $WorkerDir show-ref --verify --quiet "refs/heads/$branch"
            $branchExists = ($LASTEXITCODE -eq 0)
            if ($branchExists) {
                Invoke-Git -GitArgs @("-C", $WorkerDir, "branch", "-D", $branch)
            }

            Invoke-Git -GitArgs @("-C", $WorkerDir, "checkout", "-b", $branch, "origin/master")

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
                & $CodexExe --sandbox workspace-write --ask-for-approval never exec $prompt
                $codexExit = $LASTEXITCODE
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

            Set-Content -Path $stateFile -Value $taskKey -Encoding UTF8
            Write-WatcherLog "Task abgeschlossen und gepusht: $branch"
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
        # Letzter Rueckfall, falls selbst der Logpfad nicht schreibbar ist.
        Write-Error $_
    }
    exit 1
}
