param(
    [string]$AgentRoot = "D:\AI3D-Agent",
    [string]$RepoUrl = "https://github.com/h4rdstyle1988/AI3D-Model.git",
    [switch]$RegisterScheduledTask,
    [switch]$SchedulerDiagnosticOnly,
    [string]$TaskName = "AI3D-Ruediger-Agent"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $AgentRoot -PathType Container)) { throw "Der bestaetigte Stammordner fehlt: $AgentRoot" }
$dirs = @("worker", "outputs", "logs", "cache", "temp", "toolchain", "state") | ForEach-Object { Join-Path $AgentRoot $_ }
New-Item -ItemType Directory -Force -Path $dirs | Out-Null
$worker = Join-Path $AgentRoot "worker\AI3D-Model-worker"
if (-not (Test-Path (Join-Path $worker ".git"))) {
    if (Test-Path $worker) { throw "Worker-Ziel existiert, ist aber kein Git-Repository: $worker" }
    & git clone $RepoUrl $worker
    if ($LASTEXITCODE -ne 0) { throw "Clone nach D: fehlgeschlagen." }
}
$watcher = Join-Path $worker "tools\ruediger-agent-watch.ps1"
if ($RegisterScheduledTask) {
    $diagnosticArgument = if ($SchedulerDiagnosticOnly) { " -DiagnosticOnly" } else { "" }
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$watcher`" -AgentRoot `"$AgentRoot`"$diagnosticArgument" -WorkingDirectory $worker
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Description "AI3D Ruediger watcher on D drive" -Force | Out-Null
}
Write-Output "AgentRoot=$AgentRoot"
Write-Output "WorkerDir=$worker"
Write-Output "SchedulerUpdated=$([bool]$RegisterScheduledTask)"
Write-Output "SchedulerDiagnosticOnly=$([bool]$SchedulerDiagnosticOnly)"
