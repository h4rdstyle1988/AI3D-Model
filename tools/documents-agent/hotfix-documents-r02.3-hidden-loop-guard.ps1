param(
    [string]$AgentRoot = "D:\Documents-Controlling-Agent",
    [string]$SchedulerTaskName = "Documents-Ruediger-Agent",
    [switch]$ValidateOnly
)

$ErrorActionPreference = "Stop"
$runtimeWatcher = Join-Path $AgentRoot "runtime\documents-agent-watch.ps1"
$worker = Join-Path $AgentRoot "worker\Documents-Controlling-clear-worker"
$stateFile = Join-Path $AgentRoot "state\documents-task-state.json"

if (-not (Test-Path -LiteralPath $runtimeWatcher -PathType Leaf)) { throw "Runtime-Watcher fehlt: $runtimeWatcher" }
if (-not (Test-Path -LiteralPath (Join-Path $worker '.git') -PathType Container)) { throw "Documents-Worker fehlt oder ist kein Git-Repo: $worker" }
$expectedWorker = [IO.Path]::GetFullPath((Join-Path $AgentRoot "worker\Documents-Controlling-clear-worker")).TrimEnd('\')
$actualWorker = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $worker).Path).TrimEnd('\')
if (-not $actualWorker.Equals($expectedWorker,[StringComparison]::OrdinalIgnoreCase)) { throw "Unerwarteter Worker-Pfad: $actualWorker" }
if ($SchedulerTaskName -ne 'Documents-Ruediger-Agent') { throw "Unerwarteter Scheduler: $SchedulerTaskName" }
$origin = (& git.exe -C $worker remote get-url origin 2>$null | Out-String).Trim()
if ($origin -notmatch '(?i)h4rdstyle1988/Documents-Controlling-clear(?:\.git)?$') { throw "Unerwartetes Worker-Origin: $origin" }

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = "$runtimeWatcher.r02.3-backup-$stamp"
$stateBackup = $(if (Test-Path -LiteralPath $stateFile) { "$stateFile.r02.3-backup-$stamp" } else { $null })
$text = (Get-Content -LiteralPath $runtimeWatcher -Raw) -replace "`r`n","`n"

# Version marker.
$text = $text -replace '\$WatcherVersion = "DOCUMENTS-R02"', '$WatcherVersion = "DOCUMENTS-R02.3"'

# Add a hard guard against endless infrastructure/post-validation retries.
$old = @'
            $infrastructureFailures++
            $phase = $(if ($reason.StartsWith("CHECKPOINT_BLOCKIERT:")) { "BLOCKIERT" } else { "FEHLER_RETRY" })
            Publish-Status -Phase $phase -Task $task -Branch $branch -Detail $reason
            $delay = [Math]::Min(300,[Math]::Max($PollSeconds,$PollSeconds * [Math]::Pow(2,[Math]::Min(4,$infrastructureFailures-1))))
            Write-Log "$phase Infrastruktur/Workflow: $reason; naechster Versuch fruehestens in $([int]$delay)s." "WARN"
            Start-Sleep -Seconds ([int]$delay)
'@
$new = @'
            $infrastructureFailures++
            $hardInfrastructureBlock = ($infrastructureFailures -ge 3)
            $phase = $(if ($reason.StartsWith("CHECKPOINT_BLOCKIERT:") -or $hardInfrastructureBlock) { "BLOCKIERT" } else { "FEHLER_RETRY" })
            $detail = $(if ($hardInfrastructureBlock) { "R02.3 LOOP-GUARD nach $infrastructureFailures aufeinanderfolgenden Infrastruktur/Post-Validation-Fehlern: $reason" } else { $reason })
            if ($hardInfrastructureBlock -and $task -and $failure) {
                $failure.blocked = $true
                $failure.reason = $detail
                Set-TaskFailure -State $state -Task $task -Failure $failure
            }
            Publish-Status -Phase $phase -Task $task -Branch $branch -Detail $detail -Attempt $(if ($failure) { $failure.attempts } else { 0 }) -RetryCount $(if ($failure) { $failure.codex_failures_without_checkpoint } else { 0 }) -CheckpointSha $(if ($failure) { $failure.last_checkpoint_sha } else { '' }) -CheckpointNumber $(if ($failure) { $failure.last_checkpoint_number } else { 0 })
            $delay = [Math]::Min(300,[Math]::Max($PollSeconds,$PollSeconds * [Math]::Pow(2,[Math]::Min(4,$infrastructureFailures-1))))
            Write-Log "$phase Infrastruktur/Workflow: $detail; naechster Versuch fruehestens in $([int]$delay)s." $(if ($hardInfrastructureBlock) { "ERROR" } else { "WARN" })
            if ($hardInfrastructureBlock) {
                # Do not spin forever. Keep publishing a stable blocked state until an operator/revision changes the task/runtime.
                while ($true) {
                    Start-Sleep -Seconds 300
                    Publish-Status -Phase "BLOCKIERT" -Task $task -Branch $branch -Detail $detail -Attempt $(if ($failure) { $failure.attempts } else { 0 }) -RetryCount $(if ($failure) { $failure.codex_failures_without_checkpoint } else { 0 }) -CheckpointSha $(if ($failure) { $failure.last_checkpoint_sha } else { '' }) -CheckpointNumber $(if ($failure) { $failure.last_checkpoint_number } else { 0 })
                }
            }
            Start-Sleep -Seconds ([int]$delay)
'@
$old = $old -replace "`r`n","`n"
$new = $new -replace "`r`n","`n"
if (-not $text.Contains($old)) { throw "Erwarteter Infrastruktur-Catch wurde nicht gefunden; Hotfix nicht angewendet." }
$text = $text.Replace($old,$new)

$oldLoopState = @'
    while ($true) {
        $task = $null
        $branch = ""
'@
$newLoopState = @'
    while ($true) {
        $task = $null
        $failure = $null
        $branch = ""
'@
$oldLoopState = $oldLoopState -replace "`r`n","`n"
$newLoopState = $newLoopState -replace "`r`n","`n"
if (-not $text.Contains($oldLoopState)) { throw "Loop-State-Einfuegepunkt wurde nicht gefunden; Hotfix nicht angewendet." }
$text = $text.Replace($oldLoopState,$newLoopState)

# Persist the attempt before launching Codex so a new PID can never masquerade as the same attempt.
$oldAttempt = @'
            $infrastructureFailures = 0

            $prompt = @"
'@
$newAttempt = @'
            # Persist the attempt before Codex starts. Infrastructure/post-validation
            # failures must remain consecutive across successful Codex exits.
            $failure.attempts = $attempt
            Set-TaskFailure -State $state -Task $task -Failure $failure

            $prompt = @"
'@
$oldAttempt = $oldAttempt -replace "`r`n","`n"
$newAttempt = $newAttempt -replace "`r`n","`n"
if (-not $text.Contains($oldAttempt)) { throw "Attempt-Persistenz-Einfuegepunkt wurde nicht gefunden; Hotfix nicht angewendet." }
$text = $text.Replace($oldAttempt,$newAttempt)

# A genuine Codex failure uses the separate retry budget and interrupts the
# infrastructure-failure sequence.
$oldCodexFailure = @'
            if ($code -ne 0) {
                [void](Fetch-TaskBranch $branch)
'@
$newCodexFailure = @'
            if ($code -ne 0) {
                # A genuine Codex failure is accounted for by the separate retry
                # budget and interrupts an infrastructure-failure sequence.
                $infrastructureFailures = 0
                [void](Fetch-TaskBranch $branch)
'@
$oldCodexFailure = $oldCodexFailure -replace "`r`n","`n"
$newCodexFailure = $newCodexFailure -replace "`r`n","`n"
if (-not $text.Contains($oldCodexFailure)) { throw "Codex-Fehler-Einfuegepunkt wurde nicht gefunden; Hotfix nicht angewendet." }
$text = $text.Replace($oldCodexFailure,$newCodexFailure)

# Validate the complete candidate before stopping anything or changing runtime files.
$tokens = $null; $errors = $null
[void][Management.Automation.Language.Parser]::ParseInput($text,[ref]$tokens,[ref]$errors)
if ($errors.Count -gt 0) {
    throw ("PowerShell-Kandidat FAIL; Runtime unveraendert: " + (($errors | ForEach-Object Message) -join ' | '))
}
if ($ValidateOnly) {
    Write-Host 'DOCUMENTS R02.3 HOTFIX VALIDATION PASS'
    Write-Host "Watcher: $runtimeWatcher"
    Write-Host 'Keine Datei geaendert; kein Prozess oder Scheduler gestoppt/gestartet.'
    return
}

# Preserve all current work and runtime/state before any stop or restart.
$dirty = (& git.exe -C $worker status --porcelain | Out-String).Trim()
$stashName = $null
if ($dirty) {
    $stashName = "documents-r02.3-pre-hotfix-$stamp"
    & git.exe -C $worker stash push -u -m $stashName | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Worker-Zustand konnte nicht als Stash gesichert werden." }
}
Copy-Item -LiteralPath $runtimeWatcher -Destination $backup -Force
if ($stateBackup) { Copy-Item -LiteralPath $stateFile -Destination $stateBackup -Force }

# Stop only the dedicated Documents scheduler/watcher and descendants tied to
# the verified Documents worker.
Stop-ScheduledTask -TaskName $SchedulerTaskName -ErrorAction Stop
$rootPattern = [Regex]::Escape([IO.Path]::GetFullPath($AgentRoot).TrimEnd('\'))
$stoppedPids = New-Object System.Collections.Generic.List[int]
Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and $_.CommandLine -match $rootPattern -and (
        $_.CommandLine -match 'documents-agent-watch\.ps1' -or
        (($_.Name -match 'codex|cmd|powershell') -and $_.CommandLine -like "*$worker*")
    )
} | ForEach-Object {
    try {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
        $stoppedPids.Add([int]$_.ProcessId)
    } catch {}
}
Start-Sleep -Seconds 2

[IO.File]::WriteAllText($runtimeWatcher,$text,(New-Object Text.UTF8Encoding($false)))

# Parser check before restart.
$tokens = $null; $errors = $null
[void][Management.Automation.Language.Parser]::ParseFile($runtimeWatcher,[ref]$tokens,[ref]$errors)
if ($errors.Count -gt 0) {
    Copy-Item -LiteralPath $backup -Destination $runtimeWatcher -Force
    throw ("PowerShell-Parser FAIL; Backup wiederhergestellt: " + (($errors | ForEach-Object Message) -join ' | '))
}

Start-ScheduledTask -TaskName $SchedulerTaskName
Start-Sleep -Seconds 5
$task = Get-ScheduledTask -TaskName $SchedulerTaskName -ErrorAction Stop
$watchers = @(Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and $_.CommandLine -match $rootPattern -and $_.CommandLine -match 'documents-agent-watch\.ps1'
})
if ($task.State -ne 'Running') { throw "Documents-Scheduler ist nach Neustart nicht aktiv: $($task.State)" }
if ($watchers.Count -ne 1) { throw "Nach Neustart wurde genau ein Documents-Watcher erwartet; gefunden: $($watchers.Count)" }
Write-Host "DOCUMENTS R02.3 HOTFIX PASS"
Write-Host "Watcher: $runtimeWatcher"
Write-Host "Backup:  $backup"
Write-Host "StateBackup: $stateBackup"
Write-Host "Stash:   $stashName"
Write-Host "StoppedPIDs: $($stoppedPids -join ',')"
Write-Host "TaskState: $($task.State)"
Write-Host "WatcherPID: $($watchers[0].ProcessId)"
