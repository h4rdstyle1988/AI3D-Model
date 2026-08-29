param(
    [string]$RepoUrl = "https://github.com/h4rdstyle1988/AI3D-Model.git",
    [string]$AgentRoot = "D:\AI3D-Agent",
    [string]$SchedulerTaskName = "AI3D-Ruediger-Agent"
)

$ErrorActionPreference = "Stop"
$worker = Join-Path $AgentRoot "worker\AI3D-Model-worker"
$runtime = Join-Path $AgentRoot "runtime"
$state = Join-Path $AgentRoot "state"
$logs = Join-Path $AgentRoot "logs"

New-Item -ItemType Directory -Force -Path $AgentRoot,(Join-Path $AgentRoot "worker"),$runtime,$state,$logs,(Join-Path $AgentRoot "temp"),(Join-Path $AgentRoot "toolchain") | Out-Null

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "Git fehlt." }
if (-not (Get-Command codex -ErrorAction SilentlyContinue)) { throw "Codex CLI fehlt." }

$task = Get-ScheduledTask -TaskName $SchedulerTaskName -ErrorAction SilentlyContinue
if ($task) {
    Stop-ScheduledTask -InputObject $task -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

if (-not (Test-Path (Join-Path $worker ".git"))) {
    if (Test-Path $worker) {
        $backup = "$worker.invalid-{0}" -f (Get-Date -Format "yyyyMMdd-HHmmss")
        Move-Item -LiteralPath $worker -Destination $backup
        Write-Output "Ungueltiger Worker gesichert: $backup"
    }
    git clone $RepoUrl $worker
    if ($LASTEXITCODE -ne 0) { throw "Worker-Neuaufbau fehlgeschlagen." }
}

git -C $worker fetch origin master
if ($LASTEXITCODE -ne 0) { throw "Git-Fetch fehlgeschlagen." }

git -C $worker checkout --detach origin/master
if ($LASTEXITCODE -ne 0) { throw "Checkout origin/master fehlgeschlagen." }

$installer = Join-Path $worker "tools\install-runtime-watcher.ps1"
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $installer -RepoRoot $worker -AgentRoot $AgentRoot -SchedulerTaskName $SchedulerTaskName
if ($LASTEXITCODE -ne 0) { throw "Runtime-Installation fehlgeschlagen." }

$preflight = Join-Path $runtime "cad-toolchain-preflight.ps1"
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $preflight -AgentRoot $AgentRoot
if ($LASTEXITCODE -ne 0) { throw "Preflight STOPP." }

if ($task) {
    try {
        $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$runtime\ruediger-agent-watch.ps1`" -AgentRoot `"$AgentRoot`" -WorkerDir `"$worker`" -SchedulerTaskName `"$SchedulerTaskName`""
        Set-ScheduledTask -TaskName $SchedulerTaskName -Action $action | Out-Null
        Write-Output "Scheduler-Aktion auf aktuelle Runtime gesetzt."
    }
    catch {
        Write-Warning "Scheduler-Aktion konnte nicht geaendert werden: $($_.Exception.Message)"
    }
    Start-ScheduledTask -InputObject $task
    Write-Output "Scheduler gestartet: $SchedulerTaskName"
}
else {
    Write-Warning "Scheduler '$SchedulerTaskName' wurde nicht gefunden. Runtime ist repariert, automatischer Start fehlt."
}

Write-Output "REPAIR PASS"
