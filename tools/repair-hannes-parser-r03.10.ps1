$ErrorActionPreference = 'Stop'
$Repo = 'https://github.com/h4rdstyle1988/AI3D-Model.git'
$AgentRoot = 'D:\AI3D-Agent'
$WorkerDir = Join-Path $AgentRoot 'worker\AI3D-Model-worker'
$RuntimeWatcher = Join-Path $AgentRoot 'runtime\ruediger-agent-watch.ps1'
$SchedulerTask = 'AI3D-Ruediger-Agent'
$TempRoot = Join-Path $AgentRoot 'temp\hannes-r0310-repair'
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

Write-Host '1/9 Stoppe Scheduler und alte Watcher...'
Stop-ScheduledTask -TaskName $SchedulerTask -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'ruediger-agent-watch\.ps1' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep 2

Write-Host '2/9 Erzeuge sauberen temporären master-Clone...'
if (Test-Path $TempRoot) { Remove-Item $TempRoot -Recurse -Force }
New-Item -ItemType Directory -Force -Path (Split-Path $TempRoot -Parent) | Out-Null
Run-Git -GitArgs @('clone','--branch','master','--single-branch',$Repo,$TempRoot) | Out-Null
$watcherPath = Join-Path $TempRoot 'tools\ruediger-agent-watch.ps1'
if (-not (Test-Path $watcherPath)) { throw 'Watcher-Datei im Clone fehlt.' }
$text = Get-Content $watcherPath -Raw

Write-Host '3/9 Repariere Parserfehler und härte lokale Recovery...'
$text = $text -replace '\$WatcherVersion = "R03\.9"','$WatcherVersion = "R03.10"'
$oldBlock = @'
    $exists = (& git -C $WorkerDir show-ref --verify --quiet "refs/heads/$Branch"; $LASTEXITCODE)
    if ([int]$exists -ne 0) { return $false }

    $commit = (& git -C $WorkerDir rev-parse $Branch | Out-String).Trim()
    if (-not $commit) { return $false }
    $subject = (& git -C $WorkerDir log -1 --format=%s $commit | Out-String).Trim()
    $expectedSubject = "Ruediger result for $($Task.path)"
    if ($subject -ne $expectedSubject) { return $false }

    & git -C $WorkerDir merge-base --is-ancestor origin/master $commit 2>$null
    if ($LASTEXITCODE -ne 0) { return $false }
'@
$newBlock = @'
    & git -C $WorkerDir show-ref --verify --quiet "refs/heads/$Branch"
    if ($LASTEXITCODE -ne 0) { return $false }

    $commit = (& git -C $WorkerDir rev-parse $Branch | Out-String).Trim()
    if (-not $commit) { return $false }
    $subject = (& git -C $WorkerDir log -1 --format=%s $commit | Out-String).Trim()
    $expectedSubject = "Ruediger result for $($Task.path)"
    if ($subject -ne $expectedSubject) { return $false }

    $commitTaskBlob = (& git -C $WorkerDir rev-parse "${commit}:$($Task.path)" 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $commitTaskBlob -or $commitTaskBlob -ne $Task.blob) { return $false }
'@
if (-not $text.Contains($oldBlock)) { throw 'Erwarteter Recovery-Block wurde nicht exakt gefunden; keine unsichere Patch-Anwendung.' }
$text = $text.Replace($oldBlock,$newBlock)
$text = $text.Replace('Ruediger-Watcher','Hannes-Watcher').Replace('Ruediger live status:','Hannes live status:')
[IO.File]::WriteAllText($watcherPath,$text,(New-Object Text.UTF8Encoding($false)))

Write-Host '4/9 PowerShell-Parserprüfung...'
$tokens=$null; $errors=$null
[System.Management.Automation.Language.Parser]::ParseFile($watcherPath,[ref]$tokens,[ref]$errors) | Out-Null
if ($errors.Count -gt 0) { throw ('Parser FAIL: ' + (($errors | ForEach-Object { $_.Message }) -join ' | ')) }
Write-Host 'Parser PASS.'

Write-Host '5/9 Committe nur Watcher-Reparatur auf master...'
Run-Git -GitArgs @('-C',$TempRoot,'add','tools/ruediger-agent-watch.ps1') | Out-Null
Run-Git -GitArgs @('-C',$TempRoot,'commit','-m','Fix Hannes watcher parser and local recovery R03.10') | Out-Null
Run-Git -GitArgs @('-C',$TempRoot,'push','origin','master') | Out-Null
$remoteSha = (Run-Git -GitArgs @('-C',$TempRoot,'rev-parse','HEAD')).Trim()
Write-Host "master=$remoteSha"

Write-Host '6/9 Installiere exakt diese Runtime lokal...'
New-Item -ItemType Directory -Force -Path (Split-Path $RuntimeWatcher -Parent) | Out-Null
Copy-Item $watcherPath $RuntimeWatcher -Force
$tokens=$null; $errors=$null
[System.Management.Automation.Language.Parser]::ParseFile($RuntimeWatcher,[ref]$tokens,[ref]$errors) | Out-Null
if ($errors.Count -gt 0) { throw 'Installierte Runtime ist syntaktisch ungültig.' }

Write-Host '7/9 Starte Scheduler...'
Start-ScheduledTask -TaskName $SchedulerTask
Start-Sleep 5

Write-Host '8/9 Prüfe genau einen Watcher-Prozess...'
$watchers = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'ruediger-agent-watch\.ps1' })
if ($watchers.Count -ne 1) {
    $log = Join-Path $AgentRoot 'logs\ruediger-launcher.log'
    $tail = if (Test-Path $log) { (Get-Content $log -Tail 80) -join "`r`n" } else { '<kein Launcher-Log>' }
    throw "Hannes-Watcher-Prozessanzahl=$($watchers.Count), erwartet=1.`r`n$tail"
}
Write-Host "WatcherPID=$($watchers[0].ProcessId)"

Write-Host '9/9 Cleanup...'
Remove-Item $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
Write-Host 'PASS: Hannes R03.10 Parser/Recovery repariert, master gepusht, Runtime installiert und genau ein Watcher aktiv.'
