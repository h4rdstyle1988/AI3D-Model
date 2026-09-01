param(
    [string]$RepoUrl = "https://github.com/h4rdstyle1988/Documents-Controlling-clear.git",
    [string]$BaseBranch = "main",
    [string]$AgentRoot = "D:\Documents-Controlling-Agent",
    [string]$WorkerDir = "",
    [string]$SchedulerTaskName = "Documents-Ruediger-Agent",
    [string]$LiveStatusBranch = "ruediger/live-status",
    [int]$PollSeconds = 30,
    [int]$HeartbeatSeconds = 90,
    [int]$FetchRetryCount = 3,
    [int]$LogRetentionDays = 7,
    [switch]$StartAfterInstall
)

$ErrorActionPreference = "Stop"
if (-not $WorkerDir) { $WorkerDir = Join-Path $AgentRoot "worker\Documents-Controlling-clear-worker" }
$repair = Join-Path $PSScriptRoot "repair-documents-agent.ps1"
if (-not (Test-Path -LiteralPath $repair -PathType Leaf)) { throw "Repair-Skript fehlt: $repair" }

$repairArgs = @(
    "-NoProfile",
    "-NonInteractive",
    "-ExecutionPolicy", "Bypass",
    "-File", $repair,
    "-SourceDir", $PSScriptRoot,
    "-RepoUrl", $RepoUrl,
    "-BaseBranch", $BaseBranch,
    "-AgentRoot", $AgentRoot,
    "-WorkerDir", $WorkerDir,
    "-SchedulerTaskName", $SchedulerTaskName,
    "-LiveStatusBranch", $LiveStatusBranch,
    "-PollSeconds", [string]$PollSeconds,
    "-HeartbeatSeconds", [string]$HeartbeatSeconds,
    "-FetchRetryCount", [string]$FetchRetryCount,
    "-LogRetentionDays", [string]$LogRetentionDays
)
if ($StartAfterInstall) { $repairArgs += "-StartAfterRepair" }

& powershell.exe @repairArgs

if ($LASTEXITCODE -ne 0) { throw "Documents-Agent-Installation fehlgeschlagen (Exit $LASTEXITCODE)." }
Write-Output "DOCUMENTS AGENT INSTALL PASS"
