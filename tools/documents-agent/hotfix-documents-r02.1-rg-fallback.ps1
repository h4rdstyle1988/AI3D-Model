param(
    [string]$AgentRoot = "D:\Documents-Controlling-Agent",
    [string]$SchedulerTaskName = "Documents-Ruediger-Agent",
    [int]$GraceSeconds = 30
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

$rootPattern = [Regex]::Escape($AgentRoot)
function Get-DocumentsWatchers {
    return @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -and $_.CommandLine -match 'documents-agent-watch\.ps1' -and $_.CommandLine -match $rootPattern
    })
}
function Get-ActiveDocumentsCodex {
    return @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -and $_.CommandLine -match $rootPattern -and
        ($_.Name -match '^codex' -or $_.CommandLine -match 'codex(?:\.exe)?')
    })
}

# R02.2: Erst den Produzenten neuer Codex-Prozesse stilllegen. Dadurch gibt es kein Rennen
# zwischen Hotfix und Watcher. Der bereits seit >30 Minuten festhaengende, checkpointlose
# Documents-Codex darf danach kontrolliert beendet werden; betroffen sind ausschliesslich
# Prozesse, deren CommandLine auf diesen AgentRoot zeigt.
Write-Output "Documents-Agent wird fuer den Hotfix kontrolliert angehalten."
Stop-ScheduledTask -TaskName $SchedulerTaskName -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
$watchers = @(Get-DocumentsWatchers)
foreach ($watcher in $watchers) {
    Stop-Process -Id $watcher.ProcessId -Force -ErrorAction SilentlyContinue
}

$deadline = (Get-Date).AddSeconds([Math]::Max(0,$GraceSeconds))
while ((Get-Date) -lt $deadline) {
    if (@(Get-ActiveDocumentsCodex).Count -eq 0) { break }
    Start-Sleep -Seconds 2
}

$activeCodex = @(Get-ActiveDocumentsCodex)
if ($activeCodex.Count -gt 0) {
    Write-Output "Checkpointloser Documents-Codex blieb nach Stop des Watchers aktiv; beende nur diese AgentRoot-gebundenen Prozesse."
    foreach ($proc in $activeCodex) {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
}
if (@(Get-ActiveDocumentsCodex).Count -ne 0) {
    throw "Documents-Codex konnte nicht sicher beendet werden. Hotfix stoppt ohne State-Aenderung."
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
    Copy-Item -LiteralPath $runtimeFile -Destination "$runtimeFile.previous-r02.2" -Force
    $text = $text.Replace($marker,$addition.TrimEnd())
    [IO.File]::WriteAllText($runtimeFile,$text,(New-Object Text.UTF8Encoding($false)))
}

$tokens = $null; $errors = $null
[void][Management.Automation.Language.Parser]::ParseFile($runtimeFile,[ref]$tokens,[ref]$errors)
if ($errors.Count -gt 0) {
    throw "Gepatchter Watcher hat Parserfehler: $((@($errors) | ForEach-Object { $_.Message }) -join '; ')"
}

foreach ($failure in $failures) {
    if ($failure -eq $rgFailures[0]) {
        $failure.attempts = 0
        $failure.codex_failures_without_checkpoint = 0
        $failure.last_checkpoint_sha = ""
        $failure.last_checkpoint_number = 0
        $failure.blocked = $false
        $failure.reason = "R02.2: technischer rg-Abhaengigkeitsfehler behoben; Retry-Budget kontrolliert zurueckgesetzt."
    }
}
$state.failures = $failures
Copy-Item -LiteralPath $stateFile -Destination "$stateFile.previous-r02.2" -Force
[IO.File]::WriteAllText($stateFile,($state | ConvertTo-Json -Depth 12),(New-Object Text.UTF8Encoding($false)))

Start-ScheduledTask -TaskName $SchedulerTaskName
Start-Sleep -Seconds 5
$watchers = @(Get-DocumentsWatchers)
if ($watchers.Count -ne 1) { throw "Nach Hotfix wurden $($watchers.Count) Documents-Watcher gefunden; erwartet: 1." }

Write-Output "DOCUMENTS R02.2 RG-FALLBACK HOTFIX PASS"
Write-Output "Watcher PID: $($watchers[0].ProcessId)"
Write-Output "Retry-State fuer R01 kontrolliert zurueckgesetzt."
