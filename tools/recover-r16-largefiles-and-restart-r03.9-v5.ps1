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
$BackupRoot = 'D:\3D-Models\generated\_ruediger-local-large-artifacts\herbst-igel-r16'
$env:GIT_TERMINAL_PROMPT = '0'

function Run-Git {
    param([Parameter(Mandatory=$true)][string[]]$GitArgs)
    $old = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $out = @(& git.exe @GitArgs 2>&1)
        $exit = [int]$LASTEXITCODE
    } finally { $ErrorActionPreference = $old }
    $text = (($out | ForEach-Object { $_.ToString() }) -join "`r`n")
    if ($exit -ne 0) { throw "git $($GitArgs -join ' ') :: $text" }
    return $text
}

Write-Host '1/10 Stoppe alten Watcher...'
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match 'ruediger-agent-watch\.ps1' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

if (-not (Test-Path (Join-Path $WorkerDir '.git'))) { throw "Worker fehlt: $WorkerDir" }

Write-Host '2/10 Hole aktuellen master...'
Run-Git -GitArgs @('-C',$WorkerDir,'fetch','origin','master') | Out-Null

Write-Host '3/10 Pruefe lokales R16-Ergebnis...'
& git.exe -C $WorkerDir show-ref --verify --quiet "refs/heads/$Branch"
if ($LASTEXITCODE -ne 0) { throw "Lokaler R16-Branch fehlt: $Branch" }
$Commit = (Run-Git -GitArgs @('-C',$WorkerDir,'rev-parse',$Branch)).Trim()
$Subject = (Run-Git -GitArgs @('-C',$WorkerDir,'log','-1','--format=%s',$Commit)).Trim()
if ($Subject -ne $ExpectedSubject) { throw "Lokaler R16-Commit nicht eindeutig: Subject='$Subject'" }
$CommitTaskBlob = (Run-Git -GitArgs @('-C',$WorkerDir,'rev-parse',"${Commit}:$TaskPath")).Trim()
if ($CommitTaskBlob -ne $TaskBlob) { throw "R16-Commit gehoert nicht zur freigegebenen Task-Revision." }
Run-Git -GitArgs @('-C',$WorkerDir,'checkout',$Branch) | Out-Null
$dirty = (Run-Git -GitArgs @('-C',$WorkerDir,'status','--porcelain')).Trim()
if ($dirty) { throw 'R16-Branch ist dirty; Rescue stoppt zum Schutz des Ergebnisses.' }

Write-Host '4/10 Ermittle alle GitHub-Hardlimit-Dateien...'
$ls = Run-Git -GitArgs @('-C',$WorkerDir,'ls-tree','-r','-l','HEAD')
$oversize = @()
foreach ($line in ($ls -split "`r?`n")) {
    if ($line -match '^\d+\s+blob\s+[0-9a-f]+\s+(\d+)\t(.+)$') {
        $size = [int64]$Matches[1]; $path = $Matches[2]
        if ($size -gt 100000000) { $oversize += [pscustomobject]@{Path=$path;Size=$size} }
    }
}
if ($oversize.Count -eq 0) { Write-Host 'Keine >100MB-Dateien mehr vorhanden.' }

Write-Host '5/10 Sichere alle >100MB-Dateien lokal und entferne sie nur aus Git...'
New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
$manifest = @()
foreach ($item in $oversize) {
    $src = Join-Path $WorkerDir ($item.Path -replace '/','\')
    if (-not (Test-Path -LiteralPath $src -PathType Leaf)) { throw "Erwartete grosse Datei fehlt lokal: $($item.Path)" }
    $dest = Join-Path $BackupRoot ([IO.Path]::GetFileName($src))
    Copy-Item -LiteralPath $src -Destination $dest -Force
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $dest).Hash.ToLowerInvariant()
    $manifest += [pscustomobject]@{path=$item.Path;bytes=$item.Size;sha256=$hash;local_backup=$dest}
    Run-Git -GitArgs @('-C',$WorkerDir,'rm','-f','--',$item.Path) | Out-Null
}

Write-Host '6/10 Dokumentiere ausgelagerte Artefakte im Ergebnis...'
$manifestPath = Join-Path $WorkerDir 'outputs\herbst-igel-r02-envelope-rebuild-r16\LOCAL-LARGE-ARTIFACTS.json'
$manifestDir = Split-Path $manifestPath -Parent
New-Item -ItemType Directory -Force -Path $manifestDir | Out-Null
$manifestObj = [ordered]@{
  schema_version = 1
  reason = 'GitHub hard limit >100MB; raw PLY artifacts remain preserved locally, not product geometry changes.'
  task = $TaskPath
  task_blob = $TaskBlob
  artifacts = $manifest
}
[IO.File]::WriteAllText($manifestPath,($manifestObj | ConvertTo-Json -Depth 8),(New-Object Text.UTF8Encoding($false)))
Run-Git -GitArgs @('-C',$WorkerDir,'add','--',$manifestPath) | Out-Null

Write-Host '7/10 Amend R16-Commit ohne Produktgeometrie-Aenderung...'
Run-Git -GitArgs @('-C',$WorkerDir,'commit','--amend','--no-edit') | Out-Null
$Commit = (Run-Git -GitArgs @('-C',$WorkerDir,'rev-parse','HEAD')).Trim()

Write-Host '8/10 Pruefe Hardlimit erneut...'
$ls2 = Run-Git -GitArgs @('-C',$WorkerDir,'ls-tree','-r','-l','HEAD')
$still = @()
foreach ($line in ($ls2 -split "`r?`n")) {
    if ($line -match '^\d+\s+blob\s+[0-9a-f]+\s+(\d+)\t(.+)$') {
        $size = [int64]$Matches[1]; $path = $Matches[2]
        if ($size -gt 100000000) { $still += "$path ($size bytes)" }
    }
}
if ($still.Count -gt 0) { throw "Noch immer >100MB: $($still -join '; ')" }

Write-Host '9/10 Push + Remote-Verifikation...'
Run-Git -GitArgs @('-C',$WorkerDir,'push','-u','origin',"${Branch}:refs/heads/$Branch",'--force-with-lease') | Out-Null
$remoteLine = (Run-Git -GitArgs @('-C',$WorkerDir,'ls-remote','--heads','origin',"refs/heads/$Branch")).Trim()
if (-not $remoteLine) { throw 'Remote-Branch fehlt nach Push.' }
$RemoteCommit = ($remoteLine -split '\s+')[0]
if ($RemoteCommit -ne $Commit) { throw "Remote-SHA ungleich: lokal=$Commit remote=$RemoteCommit" }

if (Test-Path $StateFile) { $state = Get-Content $StateFile -Raw | ConvertFrom-Json } else { $state = [pscustomobject]@{schema_version=3;processed=@();failures=@()} }
$state.schema_version = 3; $state.processed=@($state.processed); $state.failures=@($state.failures)
$key = "$TaskPath|$TaskBlob"
if (-not (@($state.processed | ForEach-Object { $_.key }) -contains $key)) {
  $state.processed += [pscustomobject]@{key=$key;task=$TaskPath;blob=$TaskBlob;source='TASK_QUEUE';branch=$Branch;remote_commit=$Commit;verified_at=(Get-Date).ToString('o')}
}
$state.failures = @($state.failures | Where-Object { $_.key -ne $key })
$tmpState = "$StateFile.tmp"; $state | ConvertTo-Json -Depth 10 | Set-Content $tmpState -Encoding UTF8; Move-Item -LiteralPath $tmpState -Destination $StateFile -Force

Write-Host '10/10 Installiere R03.9 und starte Scheduler...'
$watcherText = Run-Git -GitArgs @('-C',$WorkerDir,'show','origin/master:tools/ruediger-agent-watch.ps1')
[IO.File]::WriteAllText($RuntimeWatcher,$watcherText + "`r`n",(New-Object Text.UTF8Encoding($false)))
Start-ScheduledTask -TaskName $SchedulerTask
Start-Sleep -Seconds 3
Write-Host "PASS: R16 remote verifiziert ($Commit); alle >100MB-Artefakte lokal gesichert, State aktualisiert, R03.9 gestartet."
