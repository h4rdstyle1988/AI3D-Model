$ErrorActionPreference = 'Stop'
$AgentRoot = 'D:\AI3D-Agent'
$WorkerDir = Join-Path $AgentRoot 'worker\AI3D-Model-worker'
$RuntimeWatcher = Join-Path $AgentRoot 'runtime\ruediger-agent-watch.ps1'
$StateFile = Join-Path $AgentRoot 'state\ruediger-task-state.json'
$TaskPath = 'tasks/TASK-HERBST-IGEL-R02-ENVELOPE-REBUILD-R16.md'
$TaskBlob = '5d2d6ab9d3d2cb522e65e8a1de57dddc3e872e62'
$Branch = 'ruediger/task-herbst-igel-r02-envelope-rebuild-r16-5d2d6ab9'
$ExpectedSubject = "Ruediger result for $TaskPath"
$SchedulerTask = 'AI3D-Ruediger-Agent'

function Run-Git([string[]]$Args) {
    $out = @(& git.exe @Args 2>&1)
    if ($LASTEXITCODE -ne 0) { throw "git $($Args -join ' ') :: $($out -join ' | ')" }
    return (($out | ForEach-Object { $_.ToString() }) -join "`r`n")
}

Write-Host '1/7 Stoppe alten Watcher...'
Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match 'ruediger-agent-watch\.ps1' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

if (-not (Test-Path (Join-Path $WorkerDir '.git'))) { throw "Worker fehlt: $WorkerDir" }

Write-Host '2/7 Hole aktuellen master...'
Run-Git @('-C',$WorkerDir,'fetch','origin','master') | Out-Null

Write-Host '3/7 Prüfe lokales R16-Ergebnis...'
& git.exe -C $WorkerDir show-ref --verify --quiet "refs/heads/$Branch"
if ($LASTEXITCODE -ne 0) { throw "Lokaler R16-Branch fehlt: $Branch" }
$Commit = (Run-Git @('-C',$WorkerDir,'rev-parse',$Branch)).Trim()
$Subject = (Run-Git @('-C',$WorkerDir,'log','-1','--format=%s',$Commit)).Trim()
if ($Subject -ne $ExpectedSubject) { throw "Lokaler R16-Commit ist nicht eindeutig als fertiges Ergebnis erkennbar. Subject='$Subject'" }

Write-Host "4/7 R16 lokal gefunden: $Commit"
Run-Git @('-C',$WorkerDir,'checkout',$Branch) | Out-Null
$dirty = (Run-Git @('-C',$WorkerDir,'status','--porcelain')).Trim()
if ($dirty) { throw 'R16-Branch ist dirty; automatischer Rescue abgebrochen, um Ergebnis nicht zu beschädigen.' }

Write-Host '5/7 Pushe ausschließlich vorhandenes R16-Ergebnis...'
# Remote-Branch war bisher nicht vorhanden; kein Force nötig.
Run-Git @('-C',$WorkerDir,'push','-u','origin',$Branch) | Out-Null
$remoteLine = (Run-Git @('-C',$WorkerDir,'ls-remote','--heads','origin',"refs/heads/$Branch")).Trim()
if (-not $remoteLine) { throw 'Remote-Branch fehlt nach Push.' }
$RemoteCommit = ($remoteLine -split '\s+')[0]
if ($RemoteCommit -ne $Commit) { throw "Remote-SHA ungleich: lokal=$Commit remote=$RemoteCommit" }

Write-Host '6/7 Markiere R16 nur nach Remote-Verifikation als verarbeitet...'
if (Test-Path $StateFile) {
    $state = Get-Content $StateFile -Raw | ConvertFrom-Json
} else {
    $state = [pscustomobject]@{schema_version=3;processed=@();failures=@()}
}
$state.schema_version = 3
$state.processed = @($state.processed)
$state.failures = @($state.failures)
$key = "$TaskPath|$TaskBlob"
if (-not (@($state.processed | ForEach-Object { $_.key }) -contains $key)) {
    $state.processed += [pscustomobject]@{
        key=$key; task=$TaskPath; blob=$TaskBlob; source='TASK_QUEUE';
        branch=$Branch; remote_commit=$Commit; verified_at=(Get-Date).ToString('o')
    }
}
$state.failures = @($state.failures | Where-Object { $_.key -ne $key })
$state | ConvertTo-Json -Depth 10 | Set-Content $StateFile -Encoding UTF8

Write-Host '7/7 Installiere Watcher R03.9 aus master und starte Scheduler...'
$watcherText = Run-Git @('-C',$WorkerDir,'show','origin/master:tools/ruediger-agent-watch.ps1')
[IO.File]::WriteAllText($RuntimeWatcher,$watcherText + "`r`n",(New-Object Text.UTF8Encoding($false)))
Start-ScheduledTask -TaskName $SchedulerTask
Start-Sleep -Seconds 3

Write-Host "PASS: R16 remote verifiziert ($Commit), State aktualisiert, R03.9 installiert und Watcher gestartet."
