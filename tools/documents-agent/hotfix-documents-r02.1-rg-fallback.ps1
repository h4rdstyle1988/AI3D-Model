param(
    [string]$AgentRoot = "D:\Documents-Controlling-Agent",
    [string]$SchedulerTaskName = "Documents-Ruediger-Agent"
)

$ErrorActionPreference = "Stop"

$currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal($currentIdentity)
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Hotfix muss in einer als Administrator gestarteten PowerShell ausgefuehrt werden."
}

$runtimeFile = Join-Path $AgentRoot "runtime\documents-agent-watch.ps1"
$stateFile = Join-Path $AgentRoot "state\documents-task-state.json"
if (-not (Test-Path -LiteralPath $runtimeFile -PathType Leaf)) { throw "Documents Runtime fehlt: $runtimeFile" }
if (-not (Test-Path -LiteralPath $stateFile -PathType Leaf)) { throw "Documents State fehlt: $stateFile" }

# Nur bei sicherem, nicht laufendem Codex-Zustand patchen.
$all = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
$rootPattern = [Regex]::Escape($AgentRoot)
$activeCodex = @($all | Where-Object {
    $_.CommandLine -and $_.CommandLine -match $rootPattern -and
    ($_.Name -match '^codex' -or $_.CommandLine -match 'codex(?:\.exe)?')
})
if ($activeCodex.Count -gt 0) {
    throw "Aktiver Documents-Codex erkannt. Hotfix stoppt ohne Aenderung."
}

$state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
$failures = @($state.failures)
$rgFailures = @($failures | Where-Object {
    $_.blocked -eq $true -and
    $_.task -eq 'tasks/R01_GENERIC_VALIDATION_CORE.md' -and
    [string]$_.reason -match '(?i)rg.+(nicht als Name|CommandNotFound|not recognized|not found)'
})
if ($rgFailures.Count -ne 1) {
    throw "Erwarteter eindeutig technischer rg-Blocker nicht gefunden. State wird nicht veraendert."
}

$text = Get-Content -LiteralPath $runtimeFile -Raw
if ($text -notmatch 'DOCUMENTS-R02') { throw "Unerwartete Watcher-Version; Hotfix nicht angewendet." }

$marker = '- Optimieren nur bei messbarem Problem, wiederholtem Fehler oder klarer Zeit-/Robustheitsverbesserung. Keine Refactor-Schleifen ohne konkreten Nutzen. Nach PASS den funktionierenden Workflow nicht weiter refactoren.'
$addition = @"
$marker
- Verlasse dich nicht auf optionale Kommandozeilenwerkzeuge wie rg/ripgrep. Wenn rg nicht vorhanden ist, nutze git ls-files, Get-ChildItem, Select-String oder andere vorhandene Bordmittel und setze den Auftrag fort. Das Fehlen von rg ist keine Nutzerentscheidung und kein fachlicher Blocker.
"@
if ($text -notmatch 'Verlasse dich nicht auf optionale Kommandozeilenwerkzeuge wie rg/ripgrep') {
    if (-not $text.Contains($marker)) { throw "Prompt-Marker im Runtime-Watcher nicht gefunden." }
    Copy-Item -LiteralPath $runtimeFile -Destination "$runtimeFile.previous-r02.1" -Force
    $text = $text.Replace($marker,$addition.TrimEnd())
    [IO.File]::WriteAllText($runtimeFile,$text,(New-Object Text.UTF8Encoding($false)))
}

# Parser-Check vor State-Aenderung.
$tokens = $null; $errors = $null
[void][Management.Automation.Language.Parser]::ParseFile($runtimeFile,[ref]$tokens,[ref]$errors)
if ($errors.Count -gt 0) {
    throw "Gepatchter Watcher hat Parserfehler: $((@($errors) | ForEach-Object { $_.Message }) -join '; ')"
}

# Nur den eindeutig identifizierten rg-Fehlerdatensatz zuruecksetzen.
foreach ($failure in $failures) {
    if ($failure -eq $rgFailures[0]) {
        $failure.attempts = 0
        $failure.codex_failures_without_checkpoint = 0
        $failure.last_checkpoint_sha = ""
        $failure.last_checkpoint_number = 0
        $failure.blocked = $false
        $failure.reason = "R02.1: technischer rg-Abhaengigkeitsfehler behoben; Retry-Budget kontrolliert zurueckgesetzt."
    }
}
$state.failures = $failures
Copy-Item -LiteralPath $stateFile -Destination "$stateFile.previous-r02.1" -Force
[IO.File]::WriteAllText($stateFile,($state | ConvertTo-Json -Depth 12),(New-Object Text.UTF8Encoding($false)))

# Watcher sauber neu starten. Kein Codex laeuft an dieser Stelle.
Stop-ScheduledTask -TaskName $SchedulerTaskName -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -match 'documents-agent-watch\.ps1' -and $_.CommandLine -match $rootPattern } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2
Start-ScheduledTask -TaskName $SchedulerTaskName
Start-Sleep -Seconds 4

$watchers = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and $_.CommandLine -match 'documents-agent-watch\.ps1' -and $_.CommandLine -match $rootPattern
})
if ($watchers.Count -ne 1) { throw "Nach Hotfix wurden $($watchers.Count) Documents-Watcher gefunden; erwartet: 1." }

Write-Output "DOCUMENTS R02.1 RG-FALLBACK HOTFIX PASS"
Write-Output "Watcher PID: $($watchers[0].ProcessId)"
Write-Output "Retry-State fuer R01 kontrolliert zurueckgesetzt."
