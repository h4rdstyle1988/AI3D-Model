param(
    [string]$AgentRoot = "D:\AI3D-Agent",
    [string]$SchedulerTaskName = "AI3D-Ruediger-Agent"
)

$ErrorActionPreference = "Stop"
$runtimeWatcher = Join-Path $AgentRoot "runtime\ruediger-agent-watch.ps1"
$workerDir = Join-Path $AgentRoot "worker\AI3D-Model-worker"
$logDir = Join-Path $AgentRoot "logs"
$hotfixLog = Join-Path $logDir ("hotfix-r03.8-push-loop-{0}.log" -f (Get-Date -Format "yyyyMMdd-HHmmss"))

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
function Log([string]$m) {
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff zzz"),$m
    Add-Content -LiteralPath $hotfixLog -Value $line -Encoding UTF8
    Write-Host $line
}

if (-not (Test-Path -LiteralPath $runtimeWatcher -PathType Leaf)) {
    throw "Runtime-Watcher fehlt: $runtimeWatcher"
}
if (-not (Test-Path (Join-Path $workerDir ".git"))) {
    throw "Worker fehlt: $workerDir"
}

Log "Hotfix startet. Lokale CAD-/Ergebnisdaten werden nicht geloescht oder neu erzeugt."

# Diagnose des aktuell ausgecheckten Ergebnisstands vor jeder Prozessaenderung.
$branch = (& git.exe -C $workerDir branch --show-current 2>&1 | Out-String).Trim()
$head = (& git.exe -C $workerDir rev-parse HEAD 2>&1 | Out-String).Trim()
$status = (& git.exe -C $workerDir status --porcelain 2>&1 | Out-String).Trim()
Log "Worker branch='$branch' HEAD='$head' dirty=$([bool]$status)"

# Ein einzelner Diagnose-Push, um den echten Git-/LFS-Fehler sichtbar zu machen.
if ($branch) {
    $raw = @(& git.exe -C $workerDir push -u origin $branch --force-with-lease 2>&1)
    $pushExit = [int]$LASTEXITCODE
    $pushText = (($raw | ForEach-Object { $_.ToString() }) -join " | ").Trim()
    Log "Diagnose-Push exit=$pushExit :: $pushText"
    if ($pushExit -eq 0) {
        Log "Diagnose-Push war erfolgreich. Der Ergebnis-Branch ist remote vorhanden; Hotfix wird trotzdem installiert, damit R03.8 nicht erneut endlos haengt."
    }
}

# Laufenden festgefahrenen Watcher beenden. Andere PowerShell-Prozesse bleiben unangetastet.
Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match 'ruediger-agent-watch\.ps1' } |
    ForEach-Object {
        try {
            Log "Beende Watcher PID=$($_.ProcessId)"
            Stop-Process -Id $_.ProcessId -Force
        }
        catch {
            Log "WARN Stop PID=$($_.ProcessId): $($_.Exception.Message)"
        }
    }

Start-Sleep -Seconds 2

# Runtime-Watcher lokal und reversibel patchen. Backup bleibt erhalten.
$backup = "$runtimeWatcher.pre-hotfix-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
Copy-Item -LiteralPath $runtimeWatcher -Destination $backup -Force
$text = Get-Content -LiteralPath $runtimeWatcher -Raw

if ($text -notmatch '\$WatcherVersion = "R03\.8"') {
    Log "WARN Erwartete R03.8-Versionszeile nicht gefunden; vorhandene Datei wird nur gepatcht, wenn die Zielmuster eindeutig sind."
}
$text = $text -replace '\$WatcherVersion = "R03\.8"', '$WatcherVersion = "R03.9-HOTFIX"'

$oldPushBlock = @'
        if ($isPush) {
            Write-Log "Git-Push fehlgeschlagen; lokales CAD-Ergebnis bleibt erhalten. Nur der Push wird erneut versucht (Versuch $attempt)." "WARN"
            Start-Sleep -Seconds ([Math]::Min(30,[Math]::Max(2,2*$attempt)))
            continue
        }

        if ($attempt -ge $Retries) {
            throw "git failed: git $($GitArgs -join ' ') :: $lastMessage"
        }
'@
$newPushBlock = @'
        if ($attempt -ge $Retries) {
            if ($isPush) {
                throw "git push failed after $attempt/$Retries attempts: git $($GitArgs -join ' ') :: $lastMessage"
            }
            throw "git failed: git $($GitArgs -join ' ') :: $lastMessage"
        }

        if ($isPush) {
            Write-Log "Git-Push fehlgeschlagen; lokales CAD-Ergebnis bleibt erhalten. Erneuter Versuch $attempt/$Retries. Ursache: $lastMessage" "WARN"
            Start-Sleep -Seconds ([Math]::Min(10,[Math]::Max(2,2*$attempt)))
            continue
        }
'@

if (-not $text.Contains($oldPushBlock)) {
    throw "Hotfix abgebrochen: R03.8 Push-Block wurde nicht eindeutig gefunden. Backup: $backup"
}
$text = $text.Replace($oldPushBlock,$newPushBlock)

# Verhindert, dass origin/master R03.8 den lokalen Notfallfix direkt beim Neustart wieder ueberschreibt.
$syncNeedle = 'function Sync-RuntimeFromRemote {'
$syncReplacement = @'
function Sync-RuntimeFromRemote {
    if ($WatcherVersion -eq "R03.9-HOTFIX") { return $false }
'@
if (-not $text.Contains($syncNeedle)) {
    throw "Hotfix abgebrochen: Sync-RuntimeFromRemote nicht gefunden. Backup: $backup"
}
$text = $text.Replace($syncNeedle,$syncReplacement.TrimEnd())

[IO.File]::WriteAllText($runtimeWatcher,$text,(New-Object Text.UTF8Encoding($false)))
Log "Runtime-Watcher gepatcht; Backup: $backup"

# PowerShell-Syntax vor Neustart pruefen.
$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile($runtimeWatcher,[ref]$tokens,[ref]$errors) | Out-Null
if ($errors.Count -gt 0) {
    Copy-Item -LiteralPath $backup -Destination $runtimeWatcher -Force
    throw "Syntaxpruefung fehlgeschlagen; Original wiederhergestellt: $($errors[0].Message)"
}
Log "Syntaxpruefung PASS."

Start-ScheduledTask -TaskName $SchedulerTaskName
Log "Scheduled Task '$SchedulerTaskName' gestartet. Hotfix abgeschlossen."
Write-Host "HOTFIX PASS"
Write-Host "Log: $hotfixLog"
