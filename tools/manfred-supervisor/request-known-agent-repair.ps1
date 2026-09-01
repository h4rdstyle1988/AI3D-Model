param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('documents-r02.3-hidden-loop-guard')]
    [string]$RepairId,
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string]$SourceCommit,
    [string]$Root = 'D:\Manfred-Supervisor'
)

$ErrorActionPreference = 'Stop'
$targets = @{
    'documents-r02.3-hidden-loop-guard' = 'Documents'
}
$maintenanceRoot = Join-Path $Root 'maintenance'
$requestPath = Join-Path $maintenanceRoot 'REQUEST.json'
New-Item -ItemType Directory -Force -Path $maintenanceRoot | Out-Null
if (Test-Path -LiteralPath $requestPath) { throw "Es liegt bereits ein Maintenance-Request vor: $requestPath" }

$request = [ordered]@{
    schema_version = 1
    request_id = ('{0}-{1}' -f $RepairId,(Get-Date -Format 'yyyyMMdd-HHmmss'))
    repair_id = $RepairId
    target_agent = $targets[$RepairId]
    source_commit = $SourceCommit.ToLowerInvariant()
    requested_at = (Get-Date).ToString('o')
}
$temp = "$requestPath.tmp"
[IO.File]::WriteAllText($temp,($request | ConvertTo-Json -Depth 4),(New-Object Text.UTF8Encoding($false)))
Move-Item -LiteralPath $temp -Destination $requestPath
Write-Host "MANFRED Maintenance-Request bereitgestellt: $requestPath"

