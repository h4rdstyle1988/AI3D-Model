param(
    [string]$RepoRoot = (Split-Path $PSScriptRoot -Parent),
    [string]$AgentRoot = "D:\AI3D-Agent",
    [string]$SchedulerTaskName = "AI3D-Ruediger-Agent",
    [switch]$RestartScheduler
)

$ErrorActionPreference = "Stop"
$runtime = Join-Path $AgentRoot "runtime"
if (-not (Test-Path -LiteralPath $AgentRoot -PathType Container)) { throw "AgentRoot fehlt: $AgentRoot" }
New-Item -ItemType Directory -Force -Path $runtime | Out-Null

$names = @(
    "ruediger-agent-watch.ps1",
    "cad-toolchain-preflight.ps1",
    "repair-runtime.ps1",
    "restart-runtime-watcher.ps1"
)

foreach ($name in $names) {
    $source = Join-Path $RepoRoot "tools\$name"
    $target = Join-Path $runtime $name
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Quelldatei fehlt: $source" }
    if (Test-Path -LiteralPath $target -PathType Leaf) {
        Copy-Item -LiteralPath $target -Destination "$target.previous" -Force
    }
    Copy-Item -LiteralPath $source -Destination $target -Force
}

Write-Output "Runtime-Skripte installiert: $runtime"

if ($RestartScheduler) {
    $task = Get-ScheduledTask -TaskName $SchedulerTaskName -ErrorAction Stop
    Stop-ScheduledTask -InputObject $task -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Start-ScheduledTask -InputObject $task
    Write-Output "Scheduler neu gestartet: $SchedulerTaskName"
}
else {
    Write-Output "Laufender Watcher aktualisiert sich ab R03 selbst. Fuer den einmaligen Wechsel von R02 auf R03 ist ein kontrollierter Neustart erforderlich."
}
