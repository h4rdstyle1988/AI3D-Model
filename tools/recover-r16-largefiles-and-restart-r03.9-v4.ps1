$ErrorActionPreference = 'Stop'
$AgentRoot = 'D:\AI3D-Agent'
$WorkerDir = Join-Path $AgentRoot 'worker\AI3D-Model-worker'
$RuntimeWatcher = Join-Path $AgentRoot 'runtime\ruediger-agent-watch.ps1'
$StateFile = Join-Path $AgentRoot 'state\ruediger-task-state.json'
$ArchiveRoot = 'D:\3D-Models\generated\_ruediger-local-large-artifacts\herbst-igel-r16'
$TaskPath = 'tasks/TASK-HERBST-IGEL-R02-ENVELOPE-REBUILD-R16.md'
$TaskBlob = '5d2d6ab9d3d2cb522e65e8a1de57dddc3e872e62'
$Branch = 'ruediger/task-herbst-igel-r02-envelope-rebuild-r16-5d2d6ab9'
$ExpectedSubject = "Ruediger result for $TaskPath"
$SchedulerTask = 'AI3D-Ruediger-Agent'
$env:GIT_TERMINAL_PROMPT = '0'

function Run-Git {
    param([Parameter(Mandatory=$true)][string[]]$GitArgs)
    $old = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $out = @(& git.exe @GitArgs 2>&1)
        $exit = [int]$LASTEXITCODE
    } finally {
        $ErrorActionPreference = $old
    }
    $text = (($out | ForEach-Object { $_.ToString() }) -join "`r`n")
    if ($exit -ne 0) { throw "git $($GitArgs -join ' ') :: $text" }
    return $text
}

Write-Host '1/9 Stoppe alten Watcher...'
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'ruediger-agent-watch\.ps1' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

if (-not (Test-Path (Join-Path $WorkerDir '.git'))) { throw "Worker fehlt: $WorkerDir" }

Write-Host '2/9 Hole aktuellen master...'
Run-Git -GitArgs @('-C',$WorkerDir,'fetch','origin','master') | Out-Null

Write-Host '3/9 Pruefe lokales R16-Ergebnis eindeutig...'
& git.exe -C $WorkerDir show-ref --verify --quiet "refs/heads/$Branch"
if ($LASTEXITCODE -ne 0) { throw "Lokaler R16-Branch fehlt: $Branch" }
Run-Git -GitArgs @('-C',$WorkerDir,'checkout',$Branch) | Out-Null
$Commit = (Run-Git -GitArgs @('-C',$WorkerDir,'rev-parse','HEAD')).Trim()
$Subject = (Run-Git -GitArgs @('-C',$WorkerDir,'log','-1','--format=%s','HEAD')).Trim()
if ($Subject -ne $ExpectedSubject) { throw "Lokaler R16-Commit ist nicht eindeutig als fertiges Ergebnis erkennbar. Subject='$Subject'" }
$CommitTaskBlob = (Run-Git -GitArgs @('-C',$WorkerDir,'rev-parse',"HEAD:$TaskPath")).Trim()
if ($CommitTaskBlob -ne $TaskBlob) { throw "Lokaler R16-Commit gehoert nicht zur freigegebenen Task-Revision: erwartet=$TaskBlob ist=$CommitTaskBlob" }

$targetFiles = @(
 'outputs/herbst-igel-r02-envelope-rebuild-r16/masterform/herbst-igel-r02-r16-envelope-coarse-a-200mm.ply',
 'outputs/herbst-igel-r02-envelope-rebuild-r16/masterform/herbst-igel-r02-r16-envelope-fine-b-200mm.ply',
 'outputs/herbst-igel-r02-envelope-rebuild-r16/masterform/herbst-igel-r02-r16-envelope-fine-c-no-close-200mm.ply'
)

Write-Host '4/9 Sichere grosse Zwischenmeshes ausserhalb des Repositories...'
New-Item -ItemType Directory -Force -Path $ArchiveRoot | Out-Null
foreach ($rel in $targetFiles) {
    $src = Join-Path $WorkerDir ($rel -replace '/','\')
    if (Test-Path -LiteralPath $src -PathType Leaf) {
        $name = Split-Path $src -Leaf
        Copy-Item -LiteralPath $src -Destination (Join-Path $ArchiveRoot $name) -Force
    }
}

Write-Host '5/9 Entferne nur diese nicht verpflichtenden Zwischenmeshes aus dem Git-Commit...'
$removed = 0
foreach ($rel in $targetFiles) {
    & git.exe -C $WorkerDir ls-files --error-unmatch -- $rel 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Run-Git -GitArgs @('-C',$WorkerDir,'rm','--cached','--ignore-unmatch','--',$rel) | Out-Null
        $removed++
        $infoExclude = Join-Path $WorkerDir '.git\info\exclude'
        $current = if (Test-Path $infoExclude) { Get-Content $infoExclude -Raw } else { '' }
        if ($current -notmatch [regex]::Escape($rel)) { Add-Content -LiteralPath $infoExclude -Value $rel -Encoding UTF8 }
    }
}
if ($removed -eq 0) { throw 'Keines der bekannten grossen R16-Zwischenmeshes war im Commit; automatischer Rescue gestoppt.' }

Write-Host '6/9 Amend nur des R16-Ergebnis-Commits; Produktdaten bleiben unveraendert...'
Run-Git -GitArgs @('-C',$WorkerDir,'commit','--amend','--no-edit') | Out-Null
$NewCommit = (Run-Git -GitArgs @('-C',$WorkerDir,'rev-parse','HEAD')).Trim()
$NewTaskBlob = (Run-Git -GitArgs @('-C',$WorkerDir,'rev-parse',"HEAD:$TaskPath")).Trim()
if ($NewTaskBlob -ne $TaskBlob) { throw 'Task-Blob wurde beim Amend unerwartet veraendert.' }

Write-Host '7/9 Pruefe GitHub-Hardlimit vor Push...'
$tree = Run-Git -GitArgs @('-C',$WorkerDir,'ls-tree','-r','-l','HEAD')
$tooLarge = @()
foreach ($line in ($tree -split "`r?`n")) {
    if ($line -match '^\d+\s+blob\s+[0-9a-f]+\s+(\d+)\t(.+)$') {
        $size = [int64]$matches[1]; $path = $matches[2]
        if ($size -ge 100000000) { $tooLarge += "$path ($size bytes)" }
    }
}
if ($tooLarge.Count -gt 0) { throw "Weitere Dateien ueberschreiten GitHubs 100-MB-Limit: $($tooLarge -join '; ')" }

Write-Host '8/9 Pushe bereinigtes R16-Ergebnis und verifiziere Remote-SHA...'
Run-Git -GitArgs @('-C',$WorkerDir,'push','-u','origin',"${Branch}:refs/heads/$Branch",'--force-with-lease') | Out-Null
$remoteLine = (Run-Git -GitArgs @('-C',$WorkerDir,'ls-remote','--heads','origin',"refs/heads/$Branch")).Trim()
if (-not $remoteLine) { throw 'Remote-Branch fehlt nach Push.' }
$RemoteCommit = ($remoteLine -split '\s+')[0]
if ($RemoteCommit -ne $NewCommit) { throw "Remote-SHA ungleich: lokal=$NewCommit remote=$RemoteCommit" }

Write-Host '9/9 Markiere R16 verarbeitet, installiere R03.9 und starte Watcher...'
if (Test-Path $StateFile) { $state = Get-Content $StateFile -Raw | ConvertFrom-Json } else { $state = [pscustomobject]@{schema_version=3;processed=@();failures=@()} }
$state.schema_version = 3; $state.processed = @($state.processed); $state.failures = @($state.failures)
$key = "$TaskPath|$TaskBlob"
if (-not (@($state.processed | ForEach-Object { $_.key }) -contains $key)) {
    $state.processed += [pscustomobject]@{key=$key;task=$TaskPath;blob=$TaskBlob;source='TASK_QUEUE';branch=$Branch;remote_commit=$NewCommit;verified_at=(Get-Date).ToString('o')}
}
$state.failures = @($state.failures | Where-Object { $_.key -ne $key })
$tmpState = "$StateFile.tmp"; $state | ConvertTo-Json -Depth 10 | Set-Content $tmpState -Encoding UTF8; Move-Item -LiteralPath $tmpState -Destination $StateFile -Force
$watcherText = Run-Git -GitArgs @('-C',$WorkerDir,'show','origin/master:tools/ruediger-agent-watch.ps1')
[IO.File]::WriteAllText($RuntimeWatcher,$watcherText + "`r`n",(New-Object Text.UTF8Encoding($false)))
Start-ScheduledTask -TaskName $SchedulerTask
Start-Sleep -Seconds 3
Write-Host "PASS: R16 remote verifiziert ($NewCommit). Grosse Zwischenmeshes lokal archiviert unter '$ArchiveRoot'. Watcher gestartet."