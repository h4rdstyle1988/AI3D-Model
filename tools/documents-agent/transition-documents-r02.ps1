param(
    [string]$AgentRoot = "D:\Documents-Controlling-Agent",
    [string]$WorkerDir = "D:\Documents-Controlling-Agent\worker\Documents-Controlling-clear-worker",
    [string]$SchedulerTaskName = "Documents-Ruediger-Agent",
    [string]$DocumentsRepo = "https://github.com/h4rdstyle1988/Documents-Controlling-clear.git",
    [string]$TaskPath = "tasks/R01_GENERIC_VALIDATION_CORE.md",
    [int]$PollSeconds = 10
)

$ErrorActionPreference = "Stop"
$sourceDir = $PSScriptRoot
$repair = Join-Path $sourceDir "repair-documents-agent.ps1"
if (-not (Test-Path -LiteralPath $repair -PathType Leaf)) { throw "R02 repair script missing: $repair" }

function Write-Step([string]$Text) {
    Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Text)
}

function Get-DocumentsCodexProcesses {
    @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -match '^codex(?:\.exe)?$' -or $_.CommandLine -match 'codex(?:\.exe)?'
    } | Where-Object {
        $_.CommandLine -and ($_.CommandLine -like "*$WorkerDir*" -or $_.CommandLine -match 'Documents-Controlling-clear-worker')
    })
}

Write-Step "R02 transition armed. R01 is paused in the remote queue; current attempt may finish safely."
while ($true) {
    $procs = Get-DocumentsCodexProcesses
    if ($procs.Count -eq 0) { break }
    $ids = ($procs | ForEach-Object { $_.ProcessId }) -join ','
    Write-Step "Current Documents Codex still active (pid=$ids); waiting without interruption."
    Start-Sleep -Seconds $PollSeconds
}

Write-Step "No Documents Codex process active. Deploying frozen R02 runtime without starting scheduler yet."
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $repair -SourceDir $sourceDir
if ($LASTEXITCODE -ne 0) { throw "R02 repair/deploy failed with exit $LASTEXITCODE" }

Write-Step "R02 deployed. Re-queueing R01 on Documents main."
$temp = Join-Path $env:TEMP ("documents-r02-requeue-" + [guid]::NewGuid().ToString('N'))
try {
    & git.exe clone --depth 1 --branch main $DocumentsRepo $temp
    if ($LASTEXITCODE -ne 0) { throw "Documents repo clone failed" }
    $queue = Join-Path $temp "tasks\TASK_QUEUE.txt"
    if (-not (Test-Path -LiteralPath $queue)) { throw "Queue file missing: $queue" }
    $lines = @(Get-Content -LiteralPath $queue -ErrorAction Stop | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($lines -notcontains $TaskPath) {
        Add-Content -LiteralPath $queue -Value $TaskPath -Encoding UTF8
        & git.exe -C $temp add tasks/TASK_QUEUE.txt
        & git.exe -C $temp commit -m "Resume R01 under Documents workflow R02"
        if ($LASTEXITCODE -ne 0) { throw "Queue commit failed" }
        & git.exe -C $temp push origin main
        if ($LASTEXITCODE -ne 0) { throw "Queue push failed" }
    }
    else {
        Write-Step "R01 already present in queue; no duplicate added."
    }
}
finally {
    Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Step "Starting Documents scheduler with R02 runtime."
Start-ScheduledTask -TaskName $SchedulerTaskName
Start-Sleep -Seconds 3
$task = Get-ScheduledTask -TaskName $SchedulerTaskName -ErrorAction Stop
$info = Get-ScheduledTaskInfo -TaskName $SchedulerTaskName -ErrorAction Stop
Write-Step ("Transition complete. SchedulerState={0}; LastTaskResult={1}" -f $task.State,$info.LastTaskResult)
Write-Output "DOCUMENTS R02 TRANSITION PASS"
