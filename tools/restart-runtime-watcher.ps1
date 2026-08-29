param(
    [Parameter(Mandatory=$true)][int]$ParentPid,
    [string]$AgentRoot = "D:\AI3D-Agent",
    [string]$WorkerDir = "",
    [string]$SchedulerTaskName = "AI3D-Ruediger-Agent"
)

$ErrorActionPreference = "SilentlyContinue"
if (-not $WorkerDir) { $WorkerDir = Join-Path $AgentRoot "worker\AI3D-Model-worker" }

try { Wait-Process -Id $ParentPid -Timeout 60 } catch {}
Start-Sleep -Seconds 2

try {
    $task = Get-ScheduledTask -TaskName $SchedulerTaskName -ErrorAction Stop
    Start-ScheduledTask -InputObject $task -ErrorAction Stop
    exit 0
}
catch {}

$watcher = Join-Path $AgentRoot "runtime\ruediger-agent-watch.ps1"
$args = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$watcher`" -AgentRoot `"$AgentRoot`" -WorkerDir `"$WorkerDir`" -SchedulerTaskName `"$SchedulerTaskName`""
Start-Process -FilePath "powershell.exe" -ArgumentList $args -WindowStyle Hidden
