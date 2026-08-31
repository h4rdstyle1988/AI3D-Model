$ErrorActionPreference = 'Stop'
$AgentRoot = 'D:\AI3D-Agent'
$WorkerDir = Join-Path $AgentRoot 'worker\AI3D-Model-worker'
$RuntimeDir = Join-Path $AgentRoot 'runtime'
$SchedulerTaskName = 'AI3D-Ruediger-Agent'
$env:GIT_TERMINAL_PROMPT = '0'

function Run-Git {
    param([Parameter(Mandatory=$true)][string[]]$GitArgs)
    $old = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $out = @(& git.exe @GitArgs 2>&1)
        $exit = [int]$LASTEXITCODE
    }
    finally { $ErrorActionPreference = $old }
    $text = (($out | ForEach-Object { $_.ToString() }) -join "`r`n")
    if ($exit -ne 0) { throw "git $($GitArgs -join ' ') :: $text" }
    return $text
}

Write-Host '1/8 Stoppe Scheduler-Instanz kontrolliert...'
$task = Get-ScheduledTask -TaskName $SchedulerTaskName -ErrorAction Stop
if ($task.State -eq 'Running') {
    Stop-ScheduledTask -InputObject $task -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

Write-Host '2/8 Stoppe verbliebene Hannes/Legacy-Watcher-Prozesse...'
Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -and (
            $_.CommandLine -match 'ruediger-agent-watch\.ps1' -or
            $_.CommandLine -match 'restart-runtime-watcher\.ps1'
        )
    } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

if (-not (Test-Path (Join-Path $WorkerDir '.git'))) { throw "Worker fehlt: $WorkerDir" }

Write-Host '3/8 Hole aktuellen master...'
Run-Git -GitArgs @('-C',$WorkerDir,'fetch','origin','master') | Out-Null

Write-Host '4/8 Installiere aktuelle Runtime-Dateien...'
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
foreach ($name in @('ruediger-agent-watch.ps1','restart-runtime-watcher.ps1','cad-toolchain-preflight.ps1','repair-runtime.ps1')) {
    $txt = Run-Git -GitArgs @('-C',$WorkerDir,'show',"origin/master:tools/$name")
    [IO.File]::WriteAllText((Join-Path $RuntimeDir $name),$txt + "`r`n",(New-Object Text.UTF8Encoding($false)))
}

Write-Host '5/8 Starte Scheduler frisch...'
Start-ScheduledTask -TaskName $SchedulerTaskName -ErrorAction Stop
Start-Sleep -Seconds 8

Write-Host '6/8 Pruefe Scheduler...'
$task = Get-ScheduledTask -TaskName $SchedulerTaskName -ErrorAction Stop
$info = Get-ScheduledTaskInfo -TaskName $SchedulerTaskName -ErrorAction Stop
Write-Host ("SchedulerState={0}; LastTaskResult=0x{1:X8}" -f $task.State,[uint32]$info.LastTaskResult)

Write-Host '7/8 Pruefe laufenden Watcher-Prozess...'
$watchers = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'ruediger-agent-watch\.ps1' })
if ($watchers.Count -ne 1) {
    $launcherLog = Join-Path $AgentRoot 'logs\ruediger-launcher.log'
    $tail = ''
    if (Test-Path $launcherLog) { $tail = (Get-Content $launcherLog -Tail 30 -ErrorAction SilentlyContinue) -join "`r`n" }
    throw "Hannes-Watcher-Prozessanzahl=$($watchers.Count), erwartet=1.`r`nLauncher-Log:`r`n$tail"
}
Write-Host "WatcherPid=$($watchers[0].ProcessId)"

Write-Host '8/8 Runtime-Version pruefen...'
$watcherPath = Join-Path $RuntimeDir 'ruediger-agent-watch.ps1'
$versionLine = (Select-String -LiteralPath $watcherPath -Pattern '\$WatcherVersion\s*=\s*"([^"]+)"' | Select-Object -First 1).Line
Write-Host $versionLine
Write-Host 'PASS: Hannes-Runtime frisch installiert, Scheduler aktiv und genau ein Watcher-Prozess laeuft.'
