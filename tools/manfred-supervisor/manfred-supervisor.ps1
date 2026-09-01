param(
    [string]$Root = 'D:\Manfred-Supervisor',
    [int]$PollSeconds = 60
)

$ErrorActionPreference = 'Stop'
$StateDir = Join-Path $Root 'state'
$LogDir   = Join-Path $Root 'logs'
$MaintenanceDir = Join-Path $Root 'maintenance'
New-Item -ItemType Directory -Force -Path $StateDir,$LogDir,$MaintenanceDir | Out-Null

$LogFile = Join-Path $LogDir ('manfred-' + (Get-Date -Format 'yyyy-MM-dd') + '.log')
$StateFile = Join-Path $StateDir 'MANFRED_STATUS.json'
$MaintenanceRequestFile = Join-Path $MaintenanceDir 'REQUEST.json'
$MaintenanceRunner = Join-Path $PSScriptRoot 'invoke-known-agent-repair.ps1'

$agents = @(
    [pscustomobject]@{
        Name = 'AI3D'
        TaskName = 'AI3D-Ruediger-Agent'
        WatchPattern = 'D:\\AI3D-Agent\\runtime\\ruediger-agent-watch\.ps1'
    },
    [pscustomobject]@{
        Name = 'Documents'
        TaskName = 'Documents-Ruediger-Agent'
        WatchPattern = 'D:\\Documents-Controlling-Agent\\runtime\\documents-agent-watch\.ps1'
    }
)

function Write-ManfredLog {
    param([string]$Level,[string]$Message)
    $line = '{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'),$Level,$Message
    Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
}

function Get-Watchers {
    param([string]$Pattern)
    @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match $Pattern })
}

function Invoke-ManfredMaintenance {
    if (-not (Test-Path -LiteralPath $MaintenanceRequestFile -PathType Leaf)) {
        return [pscustomobject]@{ status='NONE'; request_id=$null; repair_id=$null; target_agent=$null; reason='Kein lokaler Maintenance-Request.' }
    }
    if (-not (Test-Path -LiteralPath $MaintenanceRunner -PathType Leaf)) {
        $reason = "Allowlist-Runner fehlt: $MaintenanceRunner"
        Write-ManfredLog 'ERROR' $reason
        return [pscustomobject]@{ status='BLOCKED'; request_id=$null; repair_id=$null; target_agent=$null; reason=$reason }
    }

    try {
        $result = & $MaintenanceRunner -RequestPath $MaintenanceRequestFile -Root $Root -SourceRepository 'D:\AI3D-Agent\worker\AI3D-Model-worker'
        $level = $(if ($result.status -eq 'PASS') { 'INFO' } else { 'ERROR' })
        Write-ManfredLog $level ("Maintenance {0}: {1} ({2})" -f $result.repair_id,$result.status,$result.reason)
        return $result
    }
    catch {
        $reason = 'Maintenance-Runner fehlgeschlagen: ' + $_.Exception.Message
        Write-ManfredLog 'ERROR' $reason
        return [pscustomobject]@{ status='BLOCKED'; request_id=$null; repair_id=$null; target_agent=$null; reason=$reason }
    }
}

function Repair-Agent {
    param($Agent)

    $actions = New-Object System.Collections.Generic.List[string]
    $watchers = @(Get-Watchers -Pattern $Agent.WatchPattern)

    if ($watchers.Count -eq 0) {
        Write-ManfredLog 'WARN' ("{0}: Watcher fehlt. Starte Scheduled Task {1}." -f $Agent.Name,$Agent.TaskName)
        try {
            Start-ScheduledTask -TaskName $Agent.TaskName -ErrorAction Stop
            Start-Sleep -Seconds 8
            $watchers = @(Get-Watchers -Pattern $Agent.WatchPattern)
            if ($watchers.Count -eq 0) {
                $actions.Add('restart_failed')
                Write-ManfredLog 'ERROR' ("{0}: Watcher nach Task-Start weiterhin nicht vorhanden." -f $Agent.Name)
            } else {
                $actions.Add('restarted')
                Write-ManfredLog 'INFO' ("{0}: Watcher erfolgreich neu gestartet (PID {1})." -f $Agent.Name,$watchers[0].ProcessId)
            }
        } catch {
            $actions.Add('restart_error')
            Write-ManfredLog 'ERROR' ("{0}: Start-ScheduledTask fehlgeschlagen: {1}" -f $Agent.Name,$_.Exception.Message)
        }
    }

    if ($watchers.Count -gt 1) {
        $ordered = @($watchers | Sort-Object CreationDate,ProcessId)
        $keeper = $ordered[0]
        $extras = @($ordered | Select-Object -Skip 1)
        foreach ($extra in $extras) {
            try {
                Stop-Process -Id $extra.ProcessId -Force -ErrorAction Stop
                $actions.Add('duplicate_removed')
                Write-ManfredLog 'WARN' ("{0}: Doppelwatcher PID {1} beendet; PID {2} bleibt aktiv." -f $Agent.Name,$extra.ProcessId,$keeper.ProcessId)
            } catch {
                $actions.Add('duplicate_remove_failed')
                Write-ManfredLog 'ERROR' ("{0}: Doppelwatcher PID {1} konnte nicht beendet werden: {2}" -f $Agent.Name,$extra.ProcessId,$_.Exception.Message)
            }
        }
        $watchers = @(Get-Watchers -Pattern $Agent.WatchPattern)
    }

    $taskState = $null
    try { $taskState = (Get-ScheduledTask -TaskName $Agent.TaskName -ErrorAction Stop).State.ToString() } catch { $taskState = 'MISSING' }

    [pscustomobject]@{
        name = $Agent.Name
        scheduler = $Agent.TaskName
        scheduler_state = $taskState
        watcher_count = $watchers.Count
        watcher_pids = @($watchers | ForEach-Object { [int]$_.ProcessId })
        actions = @($actions)
        healthy = ($watchers.Count -eq 1 -and $taskState -ne 'MISSING')
    }
}

function Write-State {
    param($Results,$Maintenance)
    $codex = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq 'codex.exe' -and $_.CommandLine -and $_.CommandLine -match 'AI3D-Agent|Documents-Controlling-Agent' } |
        ForEach-Object { [pscustomobject]@{ pid=[int]$_.ProcessId; command=$_.CommandLine } })

    $state = [ordered]@{
        schema_version = 1
        supervisor = 'MANFRED'
        version = 'R01.1'
        updated_at = (Get-Date).ToString('o')
        machine = $env:COMPUTERNAME
        healthy = (@($Results | Where-Object { -not $_.healthy }).Count -eq 0)
        agents = @($Results)
        codex_workers = $codex
        maintenance = $Maintenance
        policy = [ordered]@{
            project_code_changes = $false
            remote_shell = $false
            create_project_tasks = $false
            maintenance_allowlist_only = $true
            maintenance_request_local_only = $true
            herbst_igel_after_r19 = 'HOLD'
        }
    }
    $tmp = $StateFile + '.tmp'
    $state | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $tmp -Encoding UTF8
    Move-Item -LiteralPath $tmp -Destination $StateFile -Force
}

Write-ManfredLog 'INFO' 'MANFRED Supervisor R01.1 gestartet.'

while ($true) {
    try {
        $maintenance = Invoke-ManfredMaintenance
        $results = @()
        foreach ($agent in $agents) {
            $results += Repair-Agent -Agent $agent
        }
        Write-State -Results $results -Maintenance $maintenance
    } catch {
        Write-ManfredLog 'ERROR' ('Supervisor-Zyklus fehlgeschlagen: ' + $_.Exception.Message)
    }
    Start-Sleep -Seconds $PollSeconds
}
