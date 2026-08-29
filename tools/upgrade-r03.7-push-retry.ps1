param(
    [string]$AgentRoot = "D:\AI3D-Agent",
    [string]$WorkerDir = "D:\AI3D-Agent\worker\AI3D-Model-worker",
    [string]$SchedulerTaskName = "AI3D-Ruediger-Agent"
)

$ErrorActionPreference = "Stop"

function Get-ProcessDescendants {
    param([int]$RootPid,[object[]]$Snapshot)
    $result = New-Object System.Collections.Generic.List[int]
    $queue = New-Object System.Collections.Generic.Queue[int]
    $queue.Enqueue($RootPid)
    while ($queue.Count -gt 0) {
        $parent = $queue.Dequeue()
        foreach ($p in @($Snapshot | Where-Object { [int]$_.ParentProcessId -eq $parent })) {
            $pidValue = [int]$p.ProcessId
            if (-not $result.Contains($pidValue)) {
                $result.Add($pidValue)
                $queue.Enqueue($pidValue)
            }
        }
    }
    return @($result)
}

Write-Host "R03.7: laufenden Ruediger-Auftrag kontrolliert beenden..."
$statusPath = Join-Path $AgentRoot "temp\RUEDIGER_STATUS.json"
$watcherPid = 0
if (Test-Path -LiteralPath $statusPath) {
    try {
        $status = Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json
        if ($status.pid) { $watcherPid = [int]$status.pid }
    }
    catch {}
}

$processSnapshot = @(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CommandLine)
$descendants = @()
if ($watcherPid -gt 0) {
    $descendants = @(Get-ProcessDescendants -RootPid $watcherPid -Snapshot $processSnapshot)
}

Stop-ScheduledTask -TaskName $SchedulerTaskName -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

foreach ($pidValue in @($descendants | Sort-Object -Descending)) {
    Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
}
if ($watcherPid -gt 0) {
    Stop-Process -Id $watcherPid -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 1

Write-Host "R03.7: aktuellen master laden; irrelevanten Wuerfel-Workerstand verwerfen..."
& git.exe -C $WorkerDir fetch origin master
if ($LASTEXITCODE -ne 0) { throw "git fetch origin master fehlgeschlagen." }
& git.exe -C $WorkerDir reset --hard
if ($LASTEXITCODE -ne 0) { throw "git reset --hard fehlgeschlagen." }
& git.exe -C $WorkerDir clean -fd
if ($LASTEXITCODE -ne 0) { throw "git clean fehlgeschlagen." }
& git.exe -C $WorkerDir checkout --detach origin/master
if ($LASTEXITCODE -ne 0) { throw "Checkout origin/master fehlgeschlagen." }

$file = Join-Path $WorkerDir "tools\ruediger-agent-watch.ps1"
$text = Get-Content -LiteralPath $file -Raw
if ($text -notmatch '\$WatcherVersion = "R03\.6"') {
    throw "Erwartete Watcher-Version R03.6 nicht gefunden."
}
$text = $text.Replace('$WatcherVersion = "R03.6"','$WatcherVersion = "R03.7"')

$newInvokeGitSafe = @'
function Invoke-GitSafe {
    param(
        [Parameter(Mandatory=$true)][string[]]$GitArgs,
        [int]$Retries = 1
    )
    $lastMessage = ""
    $isPush = ($GitArgs -contains "push")
    $attempt = 0

    while ($true) {
        $attempt++
        $oldErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            $rawOutput = @(& git.exe @GitArgs 2>&1)
            $gitExitCode = [int]$LASTEXITCODE
            $output = (($rawOutput | ForEach-Object { $_.ToString() }) -join "`r`n")
        }
        finally {
            $ErrorActionPreference = $oldErrorActionPreference
        }

        if ($gitExitCode -eq 0) {
            if ($output.Trim()) { Write-Log ("git: " + $output.Trim()) "DEBUG" }
            return $output
        }

        $lastMessage = $output.Trim()

        if ($isPush -and $lastMessage -match '(?i)stale info' -and ($GitArgs -contains "--force-with-lease")) {
            try {
                $pushIndex = [Array]::IndexOf($GitArgs,"push")
                $remoteSeen = $false
                $branchName = ""
                for ($i=$pushIndex+1; $i -lt $GitArgs.Count; $i++) {
                    $arg = [string]$GitArgs[$i]
                    if ($arg.StartsWith("-")) { continue }
                    if (-not $remoteSeen) {
                        $remoteSeen = $true
                        continue
                    }
                    $branchName = $arg
                    break
                }
                if ($branchName) {
                    if ($branchName.Contains(":")) { $branchName = ($branchName -split ':')[-1] }
                    $branchName = $branchName -replace '^refs/heads/',''
                    $oldRefreshPreference = $ErrorActionPreference
                    try {
                        $ErrorActionPreference = "Continue"
                        $refreshOutput = @(& git.exe -C $WorkerDir fetch origin "refs/heads/${branchName}:refs/remotes/origin/${branchName}" 2>&1)
                        $refreshExit = [int]$LASTEXITCODE
                    }
                    finally {
                        $ErrorActionPreference = $oldRefreshPreference
                    }
                    if ($refreshExit -eq 0) {
                        Write-Log "Force-with-lease aktualisiert: origin/$branchName" "INFO"
                    }
                    else {
                        Write-Log ("Lease-Refresh fehlgeschlagen: " + (($refreshOutput | ForEach-Object { $_.ToString() }) -join " | ")) "WARN"
                    }
                }
            }
            catch {
                Write-Log "Lease-Refresh Ausnahme: $($_.Exception.Message)" "WARN"
            }
        }

        if ($isPush) {
            Write-Log "Git-Push fehlgeschlagen; lokales CAD-Ergebnis bleibt erhalten. Nur der Push wird erneut versucht (Versuch $attempt)." "WARN"
            Start-Sleep -Seconds ([Math]::Min(30,[Math]::Max(2,2*$attempt)))
            continue
        }

        if ($attempt -ge $Retries) {
            throw "git failed: git $($GitArgs -join ' ') :: $lastMessage"
        }

        Write-Log "Git-Versuch $attempt/$Retries fehlgeschlagen; erneuter Versuch." "WARN"
        Start-Sleep -Seconds ([Math]::Min(10,2*$attempt))
    }
}
'@

$rx = New-Object System.Text.RegularExpressions.Regex(
    'function Invoke-GitSafe \{.*?\r?\n\}\r?\n\r?\nfunction Ensure-Worker \{',
    [System.Text.RegularExpressions.RegexOptions]::Singleline
)
if ($rx.Matches($text).Count -ne 1) {
    throw "Invoke-GitSafe-Block nicht eindeutig gefunden."
}
$replacement = $newInvokeGitSafe.TrimEnd() + "`r`n`r`nfunction Ensure-Worker {"
$text = $rx.Replace($text,[System.Text.RegularExpressions.MatchEvaluator]{ param($m) $replacement },1)

[IO.File]::WriteAllText($file,$text,(New-Object System.Text.UTF8Encoding($false)))

$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile($file,[ref]$tokens,[ref]$errors) | Out-Null
if ($errors.Count -gt 0) {
    $errors | Format-List *
    throw "R03.7 PowerShell-Syntaxpruefung fehlgeschlagen."
}
Write-Host "R03.7 Syntaxpruefung: PASS"

& git.exe -C $WorkerDir diff --check
if ($LASTEXITCODE -ne 0) { throw "git diff --check fehlgeschlagen." }
& git.exe -C $WorkerDir add -- "tools/ruediger-agent-watch.ps1"
if ($LASTEXITCODE -ne 0) { throw "git add fehlgeschlagen." }
& git.exe -C $WorkerDir commit -m "Preserve CAD results across Git push retries in R03.7"
if ($LASTEXITCODE -ne 0) { throw "R03.7 Commit fehlgeschlagen." }
& git.exe -C $WorkerDir push origin HEAD:master
if ($LASTEXITCODE -ne 0) { throw "R03.7 Push auf master fehlgeschlagen." }

Copy-Item -LiteralPath $file -Destination (Join-Path $AgentRoot "runtime\ruediger-agent-watch.ps1") -Force
Write-Host "R03.7 Runtime installiert."

Start-ScheduledTask -TaskName $SchedulerTaskName
Start-Sleep -Seconds 6
$task = Get-ScheduledTask -TaskName $SchedulerTaskName
$taskInfo = Get-ScheduledTaskInfo -TaskName $SchedulerTaskName
Write-Host ("Scheduler: State={0}; LastTaskResult={1}" -f $task.State,$taskInfo.LastTaskResult)
if ($task.State -ne "Running") {
    throw "R03.7 Scheduler laeuft nach Neustart nicht."
}

Write-Host "R03.7 Upgrade abgeschlossen. Der Wuerfel ist aus der Queue; naechster freigegebener Auftrag ist der Kuerbis."
