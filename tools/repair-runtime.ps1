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

function Get-ProcessTable {
    return @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
}

function Get-WatcherProcesses {
    $all = Get-ProcessTable
    return @($all | Where-Object {
        $_.ProcessId -ne $PID -and $_.CommandLine -and $_.CommandLine -match "ruediger-agent-watch\.ps1"
    })
}

function Test-ActiveRuedigerCodex {
    $all = Get-ProcessTable
    $watchers = @($all | Where-Object {
        $_.ProcessId -ne $PID -and $_.CommandLine -and $_.CommandLine -match "ruediger-agent-watch\.ps1"
    })
    if ($watchers.Count -eq 0) { return $false }

    $ids = New-Object System.Collections.Generic.HashSet[int]
    $frontier = New-Object System.Collections.Generic.List[int]
    foreach ($w in $watchers) {
        [void]$ids.Add([int]$w.ProcessId)
        $frontier.Add([int]$w.ProcessId)
    }

    for ($i=0; $i -lt $frontier.Count; $i++) {
        $parent = $frontier[$i]
        foreach ($child in @($all | Where-Object { [int]$_.ParentProcessId -eq $parent })) {
            $cid = [int]$child.ProcessId
            if ($ids.Add($cid)) { $frontier.Add($cid) }
        }
    }

    foreach ($p in $all) {
        if ($ids.Contains([int]$p.ProcessId)) {
            if ($p.Name -match "^codex" -or ($p.CommandLine -and $p.CommandLine -match "codex")) {
                return $true
            }
        }
    }
    return $false
}

function Test-WorkerSafeToStop {
    if (-not (Test-Path (Join-Path $worker ".git"))) { return $true }

    $porcelain = (& git -C $worker status --porcelain 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { return $false }
    if ($porcelain) { return $false }

    $head = (& git -C $worker rev-parse HEAD 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $head) { return $false }

    $master = (& git -C $worker rev-parse origin/master 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -eq 0 -and $master -and $head -eq $master) { return $true }

    $branch = (& git -C $worker symbolic-ref -q --short HEAD 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $branch) {
        return $true
    }

    $remoteLine = (& git -C $worker ls-remote --heads origin "refs/heads/$branch" 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -eq 0 -and $remoteLine) {
        $remoteHead = ($remoteLine -split "\s+")[0]
        if ($remoteHead -eq $head) { return $true }
    }

    return $false
}

function Stop-WatcherSafely {
    param($ScheduledTask)

    $announced = $false
    while ((Test-ActiveRuedigerCodex) -or -not (Test-WorkerSafeToStop)) {
        if (-not $announced) {
            Write-Output "Laufender Ruediger-Auftrag erkannt. Migration wartet automatisch auf einen sicheren, gepushten Worker-Zustand."
            $announced = $true
        }
        Start-Sleep -Seconds 2
    }

    if ($ScheduledTask) {
        Stop-ScheduledTask -InputObject $ScheduledTask -ErrorAction SilentlyContinue
    }
    else {
        foreach ($p in (Get-WatcherProcesses)) {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }

    Start-Sleep -Seconds 2
}

$task = Get-ScheduledTask -TaskName $SchedulerTaskName -ErrorAction SilentlyContinue
Stop-WatcherSafely -ScheduledTask $task

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
    $task = Get-ScheduledTask -TaskName $SchedulerTaskName -ErrorAction Stop
    Start-ScheduledTask -InputObject $task
    Write-Output "Scheduler gestartet: $SchedulerTaskName"
}
else {
    Write-Warning "Scheduler '$SchedulerTaskName' wurde nicht gefunden. Runtime ist repariert, automatischer Start fehlt."
}

Write-Output "REPAIR PASS"
