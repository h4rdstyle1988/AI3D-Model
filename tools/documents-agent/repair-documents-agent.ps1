param(
    [string]$SourceDir = $PSScriptRoot,
    [string]$RepoUrl = "https://github.com/h4rdstyle1988/Documents-Controlling-clear.git",
    [string]$BaseBranch = "main",
    [string]$AgentRoot = "D:\Documents-Controlling-Agent",
    [string]$WorkerDir = "",
    [string]$SchedulerTaskName = "Documents-Ruediger-Agent",
    [string]$LiveStatusBranch = "ruediger/live-status",
    [int]$PollSeconds = 30,
    [int]$HeartbeatSeconds = 90,
    [int]$FetchRetryCount = 3,
    [int]$MaxCodexFailuresWithoutCheckpoint = 3,
    [int]$LogRetentionDays = 7,
    [switch]$StartAfterRepair
)

$ErrorActionPreference = "Stop"
if (-not $WorkerDir) { $WorkerDir = Join-Path $AgentRoot "worker\Documents-Controlling-clear-worker" }

$currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal($currentIdentity)
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Installation/Repair muss in einer als Administrator gestarteten PowerShell ausgefuehrt werden."
}

function Get-FullNormalizedPath {
    param([string]$Path)
    return [IO.Path]::GetFullPath($Path).TrimEnd('\')
}

function Assert-DedicatedPaths {
    $rootFull = Get-FullNormalizedPath $AgentRoot
    $workerFull = Get-FullNormalizedPath $WorkerDir
    $workerRoot = (Join-Path $rootFull "worker").TrimEnd('\') + '\'
    if ($rootFull -eq [IO.Path]::GetPathRoot($rootFull).TrimEnd('\')) { throw "AgentRoot darf kein Laufwerksstamm sein." }
    if (-not $workerFull.StartsWith($workerRoot,[StringComparison]::OrdinalIgnoreCase)) {
        throw "WorkerDir muss innerhalb des dedizierten AgentRoot\worker liegen."
    }
}

function Get-NormalizedGitUrl {
    param([string]$Url)
    return (($Url.Trim() -replace '\\','/') -replace '/$','' -replace '\.git$','').ToLowerInvariant()
}

Assert-DedicatedPaths

$runtimeDir = Join-Path $AgentRoot "runtime"
$stateDir = Join-Path $AgentRoot "state"
$logDir = Join-Path $AgentRoot "logs"
$tempDir = Join-Path $AgentRoot "temp"
New-Item -ItemType Directory -Force -Path $AgentRoot,(Join-Path $AgentRoot "worker"),$runtimeDir,$stateDir,$logDir,$tempDir | Out-Null

if (-not (Get-Command git.exe -ErrorAction SilentlyContinue) -and -not (Get-Command git -ErrorAction SilentlyContinue)) { throw "Git fehlt." }

function Get-ProcessTable {
    return @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
}

function Get-DocumentsWatcherProcesses {
    $rootPattern = [Regex]::Escape($AgentRoot)
    return @(Get-ProcessTable | Where-Object {
        $_.ProcessId -ne $PID -and $_.CommandLine -and
        $_.CommandLine -match 'documents-agent-watch\.ps1' -and $_.CommandLine -match $rootPattern
    })
}

function Test-ActiveDocumentsCodex {
    $all = Get-ProcessTable
    $rootPattern = [Regex]::Escape($AgentRoot)
    $watchers = @($all | Where-Object {
        $_.ProcessId -ne $PID -and $_.CommandLine -and
        $_.CommandLine -match 'documents-agent-watch\.ps1' -and $_.CommandLine -match $rootPattern
    })
    if ($watchers.Count -eq 0) { return $false }
    $ids = New-Object 'System.Collections.Generic.HashSet[int]'
    $frontier = New-Object 'System.Collections.Generic.List[int]'
    foreach ($watcher in $watchers) {
        [void]$ids.Add([int]$watcher.ProcessId)
        $frontier.Add([int]$watcher.ProcessId)
    }
    for ($index=0; $index -lt $frontier.Count; $index++) {
        $parent = $frontier[$index]
        foreach ($child in @($all | Where-Object { [int]$_.ParentProcessId -eq $parent })) {
            $childId = [int]$child.ProcessId
            if ($ids.Add($childId)) { $frontier.Add($childId) }
        }
    }
    foreach ($process in $all) {
        if ($ids.Contains([int]$process.ProcessId) -and ($process.Name -match '^codex' -or ($process.CommandLine -and $process.CommandLine -match 'codex'))) {
            return $true
        }
    }
    return $false
}

function Test-WorkerSafeToStop {
    if (-not (Test-Path -LiteralPath (Join-Path $WorkerDir ".git") -PathType Container)) { return $true }
    $porcelain = (& git.exe -C $WorkerDir status --porcelain 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $porcelain) { return $false }
    $head = (& git.exe -C $WorkerDir rev-parse HEAD 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $head) { return $false }
    $base = (& git.exe -C $WorkerDir rev-parse "origin/$BaseBranch" 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -eq 0 -and $base -and $head -eq $base) { return $true }
    $branch = (& git.exe -C $WorkerDir symbolic-ref -q --short HEAD 2>$null | Out-String).Trim()
    if (-not $branch) { return $true }
    $remoteLine = (& git.exe -C $WorkerDir ls-remote --heads origin "refs/heads/$branch" 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -eq 0 -and $remoteLine -and ($remoteLine -split '\s+')[0] -eq $head) { return $true }
    return $false
}

$scheduledTask = Get-ScheduledTask -TaskName $SchedulerTaskName -ErrorAction SilentlyContinue
$watcherProcesses = @(Get-DocumentsWatcherProcesses)
if (($scheduledTask -and $scheduledTask.State -eq "Running") -or $watcherProcesses.Count -gt 0) {
    $announced = $false
    while ((Test-ActiveDocumentsCodex) -or -not (Test-WorkerSafeToStop)) {
        if (-not $announced) {
            Write-Output "Laufender Documents-Auftrag erkannt. Repair wartet auf einen sicheren, gepushten Worker-Zustand."
            $announced = $true
        }
        Start-Sleep -Seconds 2
    }
    if ($scheduledTask -and $scheduledTask.State -eq "Running") {
        Stop-ScheduledTask -InputObject $scheduledTask -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
    foreach ($process in (Get-DocumentsWatcherProcesses)) {
        Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

$gitDir = Join-Path $WorkerDir ".git"
if (Test-Path -LiteralPath $gitDir -PathType Container) {
    $origin = (& git.exe -C $WorkerDir remote get-url origin 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or (Get-NormalizedGitUrl $origin) -ne (Get-NormalizedGitUrl $RepoUrl)) {
        throw "Vorhandener Documents-Worker hat unerwartetes origin und wird nicht veraendert: '$origin'"
    }
}
else {
    if (Test-Path -LiteralPath $WorkerDir) {
        $backup = "$WorkerDir.invalid-{0}" -f (Get-Date -Format "yyyyMMdd-HHmmss")
        Move-Item -LiteralPath $WorkerDir -Destination $backup
        Write-Output "Ungueltiger dedizierter Worker gesichert: $backup"
    }
    & git.exe clone --branch $BaseBranch --single-branch $RepoUrl $WorkerDir
    if ($LASTEXITCODE -ne 0) { throw "Worker-Neuaufbau fehlgeschlagen." }
}

& git.exe -C $WorkerDir fetch origin $BaseBranch
if ($LASTEXITCODE -ne 0) { throw "Git-Fetch fehlgeschlagen." }
if (-not (Test-WorkerSafeToStop)) { throw "Worker enthaelt ein nicht remote gesichertes Ergebnis; Repair stoppt ohne Aenderung." }
Assert-DedicatedPaths
& git.exe -C $WorkerDir checkout --detach "origin/$BaseBranch"
if ($LASTEXITCODE -ne 0) { throw "Checkout origin/$BaseBranch fehlgeschlagen." }

$runtimeFiles = @(
    "documents-agent-watch.ps1",
    "documents-agent-workflow.ps1",
    "documents-agent-launcher.ps1",
    "documents-agent-preflight.ps1",
    "repair-documents-agent.ps1",
    "documents-agent-profile.json"
)
foreach ($name in $runtimeFiles) {
    $source = Join-Path $SourceDir $name
    $target = Join-Path $runtimeDir $name
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Runtime-Quelle fehlt: $source" }
    if ((Get-FullNormalizedPath $source) -ne (Get-FullNormalizedPath $target)) {
        if (Test-Path -LiteralPath $target -PathType Leaf) { Copy-Item -LiteralPath $target -Destination "$target.previous" -Force }
        Copy-Item -LiteralPath $source -Destination $target -Force
    }
}

$preflight = Join-Path $runtimeDir "documents-agent-preflight.ps1"
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $preflight -AgentRoot $AgentRoot
if ($LASTEXITCODE -ne 0) { throw "Documents-Preflight STOP." }

$launcher = Join-Path $runtimeDir "documents-agent-launcher.ps1"
$actionArguments = @(
    "-NoProfile","-NonInteractive","-WindowStyle","Hidden","-ExecutionPolicy","Bypass","-File",('"' + $launcher + '"'),
    "-RepoUrl",('"' + $RepoUrl + '"'),"-BaseBranch",('"' + $BaseBranch + '"'),
    "-AgentRoot",('"' + $AgentRoot + '"'),"-WorkerDir",('"' + $WorkerDir + '"'),
    "-SchedulerTaskName",('"' + $SchedulerTaskName + '"'),"-LiveStatusBranch",('"' + $LiveStatusBranch + '"'),
    "-PollSeconds",$PollSeconds,"-HeartbeatSeconds",$HeartbeatSeconds,
    "-FetchRetryCount",$FetchRetryCount,"-MaxCodexFailuresWithoutCheckpoint",$MaxCodexFailuresWithoutCheckpoint,
    "-LogRetentionDays",$LogRetentionDays
) -join ' '
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $actionArguments
$identity = $currentIdentity.Name
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable
Register-ScheduledTask -TaskName $SchedulerTaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Write-Output "Scheduler installiert/aktualisiert: $SchedulerTaskName"

if ($StartAfterRepair) {
    Start-ScheduledTask -TaskName $SchedulerTaskName
    Start-Sleep -Seconds 3
    $taskAfterStart = Get-ScheduledTask -TaskName $SchedulerTaskName -ErrorAction Stop
    if ($taskAfterStart.State -ne "Running") { throw "Documents-Watcher ist nach Aktivierung nicht im Status Running." }
    Write-Output "Scheduler gestartet: $SchedulerTaskName"
}
else {
    Write-Output "Scheduler wurde nicht gestartet. Aktivierung: Start-ScheduledTask -TaskName '$SchedulerTaskName'"
}

Write-Output "DOCUMENTS AGENT REPAIR PASS"
