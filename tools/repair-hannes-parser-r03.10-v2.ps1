$ErrorActionPreference = 'Stop'
$Repo = 'https://github.com/h4rdstyle1988/AI3D-Model.git'
$AgentRoot = 'D:\AI3D-Agent'
$WorkerDir = Join-Path $AgentRoot 'worker\AI3D-Model-worker'
$RuntimeDir = Join-Path $AgentRoot 'runtime'
$SchedulerTask = 'AI3D-Ruediger-Agent'
$TempRoot = Join-Path $env:TEMP ('hannes-repair-' + [guid]::NewGuid().ToString('N'))
$CloneDir = Join-Path $TempRoot 'repo'
$TargetRel = 'tools/ruediger-agent-watch.ps1'
$Target = Join-Path $CloneDir $TargetRel
$RuntimeWatcher = Join-Path $RuntimeDir 'ruediger-agent-watch.ps1'
$env:GIT_TERMINAL_PROMPT = '0'

function Run-Git {
    param([Parameter(Mandatory=$true)][string[]]$GitArgs)
    $old = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $raw = @(& git.exe @GitArgs 2>&1)
        $code = [int]$LASTEXITCODE
    }
    finally { $ErrorActionPreference = $old }
    $text = (($raw | ForEach-Object { $_.ToString() }) -join "`r`n")
    if ($code -ne 0) { throw "git $($GitArgs -join ' ') :: $text" }
    return $text
}

Write-Host '1/9 Stoppe Scheduler und alte Watcher...'
try { Stop-ScheduledTask -TaskName $SchedulerTask -ErrorAction SilentlyContinue } catch {}
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'ruediger-agent-watch\.ps1' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep 2

Write-Host '2/9 Erzeuge sauberen temporären master-Clone...'
New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null
Run-Git -GitArgs @('clone','--branch','master','--single-branch',$Repo,$CloneDir) | Out-Null
if (-not (Test-Path -LiteralPath $Target)) { throw "Watcher-Datei fehlt im Clone: $Target" }

Write-Host '3/9 Ersetze Recovery-Funktion strukturell und setze R03.10...'
$text = Get-Content -LiteralPath $Target -Raw
$text = $text -replace '\$WatcherVersion\s*=\s*"R03\.9"','$WatcherVersion = "R03.10"'
$replacement = @'
function Try-RecoverLocalResult {
    param($Task,[string]$Branch,$State)

    & git.exe -C $WorkerDir show-ref --verify --quiet "refs/heads/$Branch"
    if ($LASTEXITCODE -ne 0) { return $false }

    $commit = (& git.exe -C $WorkerDir rev-parse $Branch | Out-String).Trim()
    if (-not $commit) { return $false }

    $subject = (& git.exe -C $WorkerDir log -1 --format=%s $commit | Out-String).Trim()
    $expectedSubject = "Ruediger result for $($Task.path)"
    if ($subject -ne $expectedSubject) { return $false }

    $commitTaskBlob = (& git.exe -C $WorkerDir rev-parse "${commit}:$($Task.path)" 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $commitTaskBlob -or $commitTaskBlob -ne $Task.blob) { return $false }

    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"checkout",$Branch) | Out-Null
    if ((& git.exe -C $WorkerDir status --porcelain | Out-String).Trim()) {
        throw "Lokales abgeschlossenes Ergebnis ist unerwartet dirty: $Branch"
    }

    Publish-Status -Phase "PUSH_RETRY" -Task $Task -Branch $Branch -Detail "Lokales abgeschlossenes Ergebnis zur exakten Task-Revision erkannt; nur Remote-Push wird wiederholt."
    Write-Log "PUSH_RETRY: vorhandenes lokales Ergebnis wird wiederverwendet: $Branch @ $commit"
    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"push","-u","origin",$Branch,"--force-with-lease") -Retries $FetchRetryCount | Out-Null
    $sha = Verify-Remote $Branch
    if ($sha -ne $commit) { throw "Recovery-Remote-SHA weicht vom lokalen Ergebnis ab: lokal=$commit remote=$sha" }

    $State.processed += [pscustomobject]@{
        key=$Task.key;task=$Task.path;blob=$Task.blob;source=$Task.source;
        branch=$Branch;remote_commit=$sha;verified_at=(Get-Date).ToString("o")
    }
    $State.failures = @($State.failures | Where-Object { $_.key -ne $Task.key })
    Write-State $State
    Publish-Status -Phase "FERTIG" -Task $Task -Branch $Branch -Detail "Lokales Ergebnis wiederverwendet; Remote-Verifikation PASS: $sha"
    Write-Log "FERTIG aus lokalem Recovery: $($Task.path) @ $sha"
    return $true
}

function Compact {
'@
$pattern = '(?s)function\s+Try-RecoverLocalResult\s*\{.*?function\s+Compact\s*\{'
$matches = [regex]::Matches($text,$pattern)
if ($matches.Count -ne 1) { throw "Recovery-Funktionsbereich nicht eindeutig gefunden: Treffer=$($matches.Count)" }
$text = [regex]::Replace($text,$pattern,[System.Text.RegularExpressions.MatchEvaluator]{ param($m) $replacement },1)
[IO.File]::WriteAllText($Target,$text,(New-Object Text.UTF8Encoding($false)))

Write-Host '4/9 Parserprüfung...'
$tokens=$null; $errors=$null
[System.Management.Automation.Language.Parser]::ParseFile($Target,[ref]$tokens,[ref]$errors) | Out-Null
if ($errors.Count -gt 0) {
    $msg = ($errors | ForEach-Object { "Zeile $($_.Extent.StartLineNumber): $($_.Message)" }) -join ' | '
    throw "Parser FAIL: $msg"
}
Write-Host 'Parser PASS.'

Write-Host '5/9 Committe und pushe R03.10 auf master...'
Run-Git -GitArgs @('-C',$CloneDir,'add',$TargetRel) | Out-Null
$status = (Run-Git -GitArgs @('-C',$CloneDir,'status','--porcelain')).Trim()
if ($status) {
    Run-Git -GitArgs @('-C',$CloneDir,'commit','-m','Fix Hannes watcher parser and local recovery R03.10') | Out-Null
    Run-Git -GitArgs @('-C',$CloneDir,'push','origin','master') | Out-Null
}
$masterSha = (Run-Git -GitArgs @('-C',$CloneDir,'rev-parse','HEAD')).Trim()
Write-Host "master=$masterSha"

Write-Host '6/9 Installiere exakt geprüfte Runtime...'
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
Copy-Item -LiteralPath $Target -Destination $RuntimeWatcher -Force
$tokens2=$null; $errors2=$null
[System.Management.Automation.Language.Parser]::ParseFile($RuntimeWatcher,[ref]$tokens2,[ref]$errors2) | Out-Null
if ($errors2.Count -gt 0) { throw 'Installierte Runtime ist trotz Vorprüfung nicht parsebar.' }

Write-Host '7/9 Starte Scheduler frisch...'
Start-ScheduledTask -TaskName $SchedulerTask
Start-Sleep 5

Write-Host '8/9 Prüfe genau einen Hannes-Watcher-Prozess...'
$watchers = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'ruediger-agent-watch\.ps1' })
if ($watchers.Count -ne 1) {
    $launcherLog = Join-Path $AgentRoot 'logs\ruediger-launcher.log'
    $tail = ''
    if (Test-Path $launcherLog) { $tail = (Get-Content $launcherLog -Tail 40) -join "`r`n" }
    throw "Hannes-Watcher-Prozessanzahl=$($watchers.Count), erwartet=1.`r`nLauncher-Log:`r`n$tail"
}
Write-Host "Hannes PID=$($watchers[0].ProcessId)"

Write-Host '9/9 Abschluss...'
$task = Get-ScheduledTask -TaskName $SchedulerTask -ErrorAction Stop
$info = Get-ScheduledTaskInfo -TaskName $SchedulerTask -ErrorAction Stop
Write-Host "SchedulerState=$($task.State); LastTaskResult=0x{0:X8}" -f ([uint32]$info.LastTaskResult)
Write-Host "PASS: Hannes R03.10 parsergeprüft, auf master gepusht, lokal installiert und genau einmal gestartet."

Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
