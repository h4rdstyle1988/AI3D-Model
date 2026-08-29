param(
    [string]$RepoUrl = "https://github.com/h4rdstyle1988/AI3D-Model.git",
    [string]$WorkerDir = "$env:USERPROFILE\Documents\ChatGPT\AI3D Model-worker",
    [int]$PollSeconds = 60
)

$ErrorActionPreference = "Stop"
$stateDir = Join-Path $env:LOCALAPPDATA "AI3D-Model"
$stateFile = Join-Path $stateDir "ruediger-last-task.txt"
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

function Invoke-Git([string[]]$Args) {
    & git @Args
    if ($LASTEXITCODE -ne 0) { throw "git failed: git $($Args -join ' ')" }
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git wurde nicht gefunden."
}
if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
    throw "Codex CLI wurde nicht gefunden."
}

if (-not (Test-Path (Join-Path $WorkerDir ".git"))) {
    if (Test-Path $WorkerDir) {
        throw "WorkerDir existiert bereits, ist aber kein Git-Repository: $WorkerDir"
    }
    Invoke-Git @("clone", $RepoUrl, $WorkerDir)
}

Write-Host "Ruediger-Watcher aktiv. Worker: $WorkerDir"

while ($true) {
    try {
        Invoke-Git @("-C", $WorkerDir, "fetch", "origin", "master")

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
        Invoke-Git @("-C", $WorkerDir, "checkout", "--detach", "origin/master")
        Invoke-Git @("-C", $WorkerDir, "reset", "--hard", "origin/master")
        Invoke-Git @("-C", $WorkerDir, "clean", "-fd")

        $stem = [IO.Path]::GetFileNameWithoutExtension($taskPath).ToLowerInvariant() -replace '[^a-z0-9-]+','-'
        $shortBlob = $taskBlob.Substring(0, [Math]::Min(8, $taskBlob.Length))
        $branch = "ruediger/$stem-$shortBlob"

        # Nur loeschen, wenn der lokale Branch wirklich existiert. Ein erstmaliger Lauf darf hier nicht abbrechen.
        & git -C $WorkerDir show-ref --verify --quiet "refs/heads/$branch"
        $branchExists = ($LASTEXITCODE -eq 0)
        if ($branchExists) {
            Invoke-Git @("-C", $WorkerDir, "branch", "-D", $branch)
        }

        Invoke-Git @("-C", $WorkerDir, "checkout", "-b", $branch, "origin/master")

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
            & codex --sandbox workspace-write --ask-for-approval never exec $prompt
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

        Invoke-Git @("-C", $WorkerDir, "add", "-A")
        Invoke-Git @("-C", $WorkerDir, "commit", "-m", "Ruediger result for $taskPath")
        Invoke-Git @("-C", $WorkerDir, "push", "-u", "origin", $branch, "--force-with-lease")

        Set-Content -Path $stateFile -Value $taskKey -Encoding UTF8
        Write-Host "Task abgeschlossen und gepusht: $branch"
    }
    catch {
        Write-Warning $_
    }

    Start-Sleep -Seconds $PollSeconds
}
