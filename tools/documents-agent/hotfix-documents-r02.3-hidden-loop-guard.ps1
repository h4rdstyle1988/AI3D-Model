param(
    [string]$AgentRoot = "D:\Documents-Controlling-Agent",
    [string]$SchedulerTaskName = "Documents-Ruediger-Agent"
)

$ErrorActionPreference = "Stop"
$runtimeWatcher = Join-Path $AgentRoot "runtime\documents-agent-watch.ps1"
$worker = Join-Path $AgentRoot "worker\Documents-Controlling-clear-worker"
$stateFile = Join-Path $AgentRoot "state\documents-task-state.json"

if (-not (Test-Path -LiteralPath $runtimeWatcher -PathType Leaf)) { throw "Runtime-Watcher fehlt: $runtimeWatcher" }
if (-not (Test-Path -LiteralPath (Join-Path $worker '.git') -PathType Container)) { throw "Documents-Worker fehlt oder ist kein Git-Repo: $worker" }
$origin = (& git.exe -C $worker remote get-url origin 2>$null | Out-String).Trim()
if ($origin -notmatch '(?i)h4rdstyle1988/Documents-Controlling-clear(?:\.git)?$') { throw "Unerwartetes Worker-Origin: $origin" }

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = "$runtimeWatcher.r02.3-backup-$stamp"
Copy-Item -LiteralPath $runtimeWatcher -Destination $backup -Force

# Stop only the dedicated Documents scheduler/watcher and its Codex child processes.
Stop-ScheduledTask -TaskName $SchedulerTaskName -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and (
        $_.CommandLine -match 'documents-agent-watch\.ps1' -or
        (($_.Name -match 'codex|cmd|powershell') -and $_.CommandLine -like "*$worker*")
    )
} | ForEach-Object {
    try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {}
}
Start-Sleep -Seconds 2

# Preserve any unverified work instead of deleting/resetting it.
$dirty = (& git.exe -C $worker status --porcelain | Out-String).Trim()
if ($dirty) {
    & git.exe -C $worker stash push -u -m "documents-r02.3-pre-hotfix-$stamp" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Worker-Zustand konnte nicht als Stash gesichert werden." }
}

$text = Get-Content -LiteralPath $runtimeWatcher -Raw

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
            Publish-Status -Phase $phase -Task $task -Branch $branch -Detail $detail
            $delay = [Math]::Min(300,[Math]::Max($PollSeconds,$PollSeconds * [Math]::Pow(2,[Math]::Min(4,$infrastructureFailures-1))))
            Write-Log "$phase Infrastruktur/Workflow: $detail; naechster Versuch fruehestens in $([int]$delay)s." $(if ($hardInfrastructureBlock) { "ERROR" } else { "WARN" })
            if ($hardInfrastructureBlock) {
                # Do not spin forever. Keep publishing a stable blocked state until an operator/revision changes the task/runtime.
                while ($true) {
                    Start-Sleep -Seconds 300
                    Publish-Status -Phase "BLOCKIERT" -Task $task -Branch $branch -Detail $detail
                }
            }
            Start-Sleep -Seconds ([int]$delay)
'@
if (-not $text.Contains($old)) { throw "Erwarteter Infrastruktur-Catch wurde nicht gefunden; Hotfix nicht angewendet." }
$text = $text.Replace($old,$new)

# Persist the attempt before launching Codex so a new PID can never masquerade as the same attempt.
$oldAttempt = @'
            $infrastructureFailures = 0

            $prompt = @"
'@
$newAttempt = @'
            $infrastructureFailures = 0
            $failure.attempts = $attempt
            Set-TaskFailure -State $state -Task $task -Failure $failure

            $prompt = @"
'@
if (-not $text.Contains($oldAttempt)) { throw "Attempt-Persistenz-Einfuegepunkt wurde nicht gefunden; Hotfix nicht angewendet." }
$text = $text.Replace($oldAttempt,$newAttempt)

[IO.File]::WriteAllText($runtimeWatcher,$text,(New-Object Text.UTF8Encoding($false)))

# Parser check before restart.
$tokens = $null; $errors = $null
[void][Management.Automation.Language.Parser]::ParseFile($runtimeWatcher,[ref]$tokens,[ref]$errors)
if ($errors.Count -gt 0) {
    Copy-Item -LiteralPath $backup -Destination $runtimeWatcher -Force
    throw ("PowerShell-Parser FAIL; Backup wiederhergestellt: " + (($errors | ForEach-Object Message) -join ' | '))
}

# Keep a local state backup; do not erase processed/failure history.
if (Test-Path -LiteralPath $stateFile) { Copy-Item -LiteralPath $stateFile -Destination "$stateFile.r02.3-backup-$stamp" -Force }

Start-ScheduledTask -TaskName $SchedulerTaskName
Start-Sleep -Seconds 5
$task = Get-ScheduledTask -TaskName $SchedulerTaskName -ErrorAction Stop
Write-Host "DOCUMENTS R02.3 HOTFIX PASS"
Write-Host "Watcher: $runtimeWatcher"
Write-Host "Backup:  $backup"
Write-Host "TaskState: $($task.State)"
