param(
    [string]$InstallRoot = 'D:\Manfred-Supervisor',
    [string]$TaskName = 'MANFRED-Supervisor',
    [string]$SourceUrl = 'https://raw.githubusercontent.com/h4rdstyle1988/AI3D-Model/master/tools/manfred-supervisor/manfred-supervisor.ps1'
)

$ErrorActionPreference = 'Stop'

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'MANFRED installation requires an elevated PowerShell.'
}

$RuntimeDir = Join-Path $InstallRoot 'runtime'
$LogsDir = Join-Path $InstallRoot 'logs'
$StateDir = Join-Path $InstallRoot 'state'
New-Item -ItemType Directory -Force -Path $InstallRoot,$RuntimeDir,$LogsDir,$StateDir | Out-Null

$Target = Join-Path $RuntimeDir 'manfred-supervisor.ps1'
$Temp = $Target + '.download'

Invoke-WebRequest -UseBasicParsing -Uri $SourceUrl -OutFile $Temp

$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile($Temp,[ref]$tokens,[ref]$errors) | Out-Null
if ($errors.Count -gt 0) {
    Remove-Item -LiteralPath $Temp -Force -ErrorAction SilentlyContinue
    throw ('Downloaded MANFRED runtime failed PowerShell parser validation: ' + ($errors | ForEach-Object Message -join '; '))
}

if (Test-Path -LiteralPath $Target) {
    Copy-Item -LiteralPath $Target -Destination ($Target + '.previous') -Force
}
Move-Item -LiteralPath $Temp -Destination $Target -Force

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$ps = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$arguments = '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -Root "{1}" -PollSeconds 60' -f $Target,$InstallRoot
$action = New-ScheduledTaskAction -Execute $ps -Argument $arguments
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'DAUMKI Engineering MANFRED Supervisor R01' | Out-Null
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 5

$proc = @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -match [regex]::Escape($Target) })
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop

if ($proc.Count -ne 1) {
    throw "MANFRED installation completed but expected exactly one supervisor process; found $($proc.Count)."
}

Write-Host ''
Write-Host 'MANFRED SUPERVISOR R01 INSTALL PASS' -ForegroundColor Green
Write-Host ('Task:    {0} ({1})' -f $TaskName,$task.State)
Write-Host ('Runtime: {0}' -f $Target)
Write-Host ('PID:     {0}' -f $proc[0].ProcessId)
Write-Host ('State:   {0}' -f (Join-Path $StateDir 'MANFRED_STATUS.json'))
Write-Host ('Logs:    {0}' -f $LogsDir)
