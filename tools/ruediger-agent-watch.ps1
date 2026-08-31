param(
    [string]$RepoUrl = "https://github.com/h4rdstyle1988/AI3D-Model.git",
    [string]$AgentRoot = "D:\AI3D-Agent",
    [string]$WorkerDir = "",
    [string]$SchedulerTaskName = "AI3D-Ruediger-Agent",
    [int]$PollSeconds = 30,
    [int]$HeartbeatSeconds = 90,
    [int]$PreflightMaxAgeMinutes = 360,
    [int]$FetchRetryCount = 3,
    [int]$LogRetentionDays = 7,
    [switch]$DiagnosticOnly,
    [switch]$SelectionTestOnly,
    [switch]$NoSelfUpdate
)

$ErrorActionPreference = "Continue"
$PSDefaultParameterValues["*:ErrorAction"] = "Stop"
$WatcherVersion = "R03.11"
$env:GIT_TERMINAL_PROMPT = "0"

if ($PollSeconds -lt 5) { throw "PollSeconds muss mindestens 5 sein." }
if ($HeartbeatSeconds -lt 60 -or $HeartbeatSeconds -gt 120) { throw "HeartbeatSeconds muss zwischen 60 und 120 liegen." }
if ($FetchRetryCount -lt 1) { throw "FetchRetryCount muss mindestens 1 sein." }
if (-not $WorkerDir) { $WorkerDir = Join-Path $AgentRoot "worker\AI3D-Model-worker" }
if (-not (Test-Path -LiteralPath $AgentRoot -PathType Container)) { throw "AgentRoot fehlt: $AgentRoot" }

$stateDir = Join-Path $AgentRoot "state"
$stateFile = Join-Path $stateDir "ruediger-task-state.json"
$preflightCache = Join-Path $stateDir "toolchain-preflight.json"
$logDir = Join-Path $AgentRoot "logs"
$runtimeDir = Join-Path $AgentRoot "runtime"
$tempDir = Join-Path $AgentRoot "temp"
$lockPath = Join-Path $stateDir "ruediger-watcher.lock"

New-Item -ItemType Directory -Force -Path $stateDir,$logDir,$runtimeDir,$tempDir,(Join-Path $AgentRoot "toolchain") | Out-Null
$logFile = Join-Path $logDir ("ruediger-agent-watch-{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))

try {
    $lockStream = [System.IO.File]::Open($lockPath,[System.IO.FileMode]::OpenOrCreate,[System.IO.FileAccess]::ReadWrite,[System.IO.FileShare]::None)
}
catch {
    Write-Host "Ruediger-Watcher laeuft bereits. Zweite Instanz beendet."
    exit 0
}

function Write-Log {
    param([string]$Message,[string]$Level="INFO")
    $line = "{0} [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff zzz"),$Level,$Message
    Add-Content -LiteralPath $script:logFile -Value $line -Encoding UTF8
    Write-Host $line
}

function Remove-ExpiredLogs {
    $cutoff = (Get-Date).AddDays(-$LogRetentionDays)
    Get-ChildItem -LiteralPath $logDir -File -Filter "ruediger-agent-watch-*.log" -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt $cutoff } |
        Remove-Item -Force -ErrorAction SilentlyContinue
}

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
            Write-Log "Git-Push fehlgeschlagen; lokales CAD-Ergebnis bleibt erhalten (Versuch $attempt/$Retries)." "WARN"
            if ($attempt -ge $Retries) {
                throw "git push failed after $attempt attempt(s): git $($GitArgs -join ' ') :: $lastMessage"
            }
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

function Ensure-Worker {
    if (Test-Path (Join-Path $WorkerDir ".git")) { return }
    if (Test-Path $WorkerDir) {
        $backup = "$WorkerDir.invalid-{0}" -f (Get-Date -Format "yyyyMMdd-HHmmss")
        Move-Item -LiteralPath $WorkerDir -Destination $backup
        Write-Log "Ungueltiger Worker wurde gesichert: $backup" "WARN"
    }
    New-Item -ItemType Directory -Force -Path (Split-Path $WorkerDir -Parent) | Out-Null
    Invoke-GitSafe -GitArgs @("clone",$RepoUrl,$WorkerDir) -Retries $FetchRetryCount | Out-Null
}

function Fetch-Master {
    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"fetch","origin","master") -Retries $FetchRetryCount | Out-Null
}

function Read-State {
    if (-not (Test-Path -LiteralPath $stateFile)) {
        return [pscustomobject]@{schema_version=3;processed=@();failures=@()}
    }
    try {
        $s = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
        if ($s.schema_version -ne 2 -and $s.schema_version -ne 3) { throw "Schema-Version $($s.schema_version)" }
        $s.schema_version = 3
        $s.processed = @($s.processed)
        $s.failures = @($s.failures)
        return $s
    }
    catch {
        $backup = "$stateFile.corrupt-{0}" -f (Get-Date -Format "yyyyMMdd-HHmmss")
        Copy-Item -LiteralPath $stateFile -Destination $backup -Force -ErrorAction SilentlyContinue
        throw "Task-Zustand unlesbar; Sicherung: $backup :: $($_.Exception.Message)"
    }
}

function Write-State {
    param($State)
    $State.schema_version = 3
    $tmp = "$stateFile.tmp"
    $bak = "$stateFile.previous"
    if (Test-Path $stateFile) { Copy-Item -LiteralPath $stateFile -Destination $bak -Force }
    $State | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $tmp -Encoding UTF8
    Move-Item -LiteralPath $tmp -Destination $stateFile -Force
}

function Remote-Text {
    param([string]$Path)
    $v = (& git -C $WorkerDir show "origin/master:$Path" 2>$null | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "Remote-Datei fehlt: $Path" }
    return $v
}

function Select-Task {
    param($State)
    $done = @($State.processed | ForEach-Object { $_.key })
    $items = @()
    foreach ($line in ((Remote-Text "tasks/TASK_QUEUE.txt") -split "`r?`n")) {
        $p = $line.Trim()
        if ($p -and -not $p.StartsWith("#")) {
            $items += [pscustomobject]@{path=$p;source="TASK_QUEUE"}
        }
    }
    foreach ($i in $items) {
        if (-not $i.path.StartsWith("tasks/") -or $i.path.Contains("..")) { throw "Ungueltiger Task-Pfad: $($i.path)" }
        $blob = (& git -C $WorkerDir rev-parse "origin/master:$($i.path)" 2>$null | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $blob) { throw "Task fehlt: $($i.path)" }
        $key = "$($i.path)|$blob"
        if ($done -notcontains $key) {
            return [pscustomobject]@{path=$i.path;blob=$blob;key=$key;source=$i.source}
        }
    }
    return $null
}

function Test-PreflightCache {
    if (-not (Test-Path $preflightCache)) { return $false }
    try {
        $p = Get-Content -LiteralPath $preflightCache -Raw | ConvertFrom-Json
        if ($p.status -ne "PASS") { return $false }
        $generated = [DateTimeOffset]::Parse($p.generated_at)
        return (([DateTimeOffset]::Now - $generated).TotalMinutes -lt $PreflightMaxAgeMinutes)
    }
    catch { return $false }
}

function Ensure-Preflight {
    param([switch]$Force)
    if (-not $Force -and (Test-PreflightCache)) {
        Write-Log "Preflight-Cache PASS; erneuter Volltest nicht notwendig."
        return
    }
    $p = Join-Path $WorkerDir "tools\cad-toolchain-preflight.ps1"
    if (-not (Test-Path $p)) { throw "Preflight fehlt: $p" }
    & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $p -AgentRoot $AgentRoot -OutputPath $preflightCache
    if ($LASTEXITCODE -ne 0) { throw "Preflight STOPP" }
    Write-Log "Preflight PASS und Cache aktualisiert."
}

function Publish-Status {
    param(
        [string]$Phase,
        $Task = $null,
        [string]$Branch = "",
        [string]$Detail = ""
    )
    try {
        if (-not (Test-Path (Join-Path $WorkerDir ".git"))) { return }
        $obj = [ordered]@{
            schema_version = 1
            watcher_version = $WatcherVersion
            updated_at = (Get-Date).ToString("o")
            phase = $Phase
            task = $(if ($Task) { $Task.path } else { $null })
            task_blob = $(if ($Task) { $Task.blob } else { $null })
            branch = $(if ($Branch) { $Branch } else { $null })
            detail = $(if ($Detail) { $Detail } else { $null })
            machine = $env:COMPUTERNAME
            pid = $PID
        }
        $statusPath = Join-Path $tempDir "RUEDIGER_STATUS.json"
        [IO.File]::WriteAllText($statusPath,($obj | ConvertTo-Json -Depth 6),(New-Object Text.UTF8Encoding($false)))
        $blob = (& git -C $WorkerDir hash-object -w $statusPath | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $blob) { throw "hash-object" }
        $treeLine = "100644 blob $blob`tRUEDIGER_STATUS.json"
        $tree = ($treeLine | & git -C $WorkerDir mktree | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $tree) { throw "mktree" }
        $commit = ("Ruediger live status: $Phase" | & git -C $WorkerDir commit-tree $tree | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $commit) { throw "commit-tree" }
        & git -C $WorkerDir push origin "${commit}:refs/heads/ruediger/live-status" --force 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "status push" }
    }
    catch {
        Write-Log "Live-Status konnte nicht publiziert werden: $($_.Exception.Message)" "WARN"
    }
}

function Get-NormalizedText {
    param([string]$Text)
    if ($null -eq $Text) { return "" }
    return ($Text -replace "`r`n","`n").TrimEnd("`n")
}

function Sync-RuntimeFromRemote {
    if ($NoSelfUpdate) { return $false }
    $names = @(
        "ruediger-agent-watch.ps1",
        "cad-toolchain-preflight.ps1",
        "repair-runtime.ps1",
        "restart-runtime-watcher.ps1"
    )
    $watcherChanged = $false
    foreach ($name in $names) {
        $remote = (& git -C $WorkerDir show "origin/master:tools/$name" 2>$null | Out-String)
        if ($LASTEXITCODE -ne 0) { continue }
        $target = Join-Path $runtimeDir $name
        $local = ""
        if (Test-Path $target) { $local = Get-Content -LiteralPath $target -Raw }
        if ((Get-NormalizedText $remote) -ne (Get-NormalizedText $local)) {
            $tmp = "$target.new"
            [IO.File]::WriteAllText($tmp,(Get-NormalizedText $remote) + "`r`n",(New-Object Text.UTF8Encoding($false)))
            Move-Item -LiteralPath $tmp -Destination $target -Force
            Write-Log "Runtime aktualisiert: $name"
            if ($name -eq "ruediger-agent-watch.ps1") { $watcherChanged = $true }
        }
    }
    if (-not $watcherChanged) { return $false }

    Publish-Status -Phase "RESTARTING" -Detail "Neue Watcher-Version aus origin/master installiert; Launcher-Reload angefordert."
    Write-Log "Selbstupdate installiert; Launcher-Reload-Code 75 wird angefordert."
    return $true
}

function Run-Codex {
    param([string]$Exe,[string]$Prompt,$Task,[string]$Branch)
    $localGeneratedDir = "D:\3D-Models\generated"
    $pf = Join-Path $tempDir "codex-prompt-$PID.txt"
    $codexOut = Join-Path $tempDir "codex-last.stdout.log"
    $codexErr = Join-Path $tempDir "codex-last.stderr.log"
    $codexCombined = Join-Path $logDir "codex-last-error.log"
    $script:LastCodexError = ""
    [IO.File]::WriteAllText($pf,$Prompt,(New-Object Text.UTF8Encoding($false)))
    Remove-Item -LiteralPath $codexOut,$codexErr -Force -ErrorAction SilentlyContinue
    try {
        if (-not (Test-Path -LiteralPath $localGeneratedDir -PathType Container)) {
            New-Item -ItemType Directory -Path $localGeneratedDir | Out-Null
        }
        $psi = New-Object Diagnostics.ProcessStartInfo
        $psi.FileName = "cmd.exe"
        $psi.Arguments = "/d /s /c `"`"$Exe`" -c windows.sandbox=`"unelevated`" --sandbox workspace-write --ask-for-approval never --add-dir `"$localGeneratedDir`" exec --skip-git-repo-check -C `"$WorkerDir`" < `"$pf`" > `"$codexOut`" 2> `"$codexErr`"`""
        $psi.WorkingDirectory = $WorkerDir
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $proc = New-Object Diagnostics.Process
        $proc.StartInfo = $psi
        if (-not $proc.Start()) { throw "Codex-Start fehlgeschlagen" }
        Publish-Status -Phase "ARBEITET" -Task $Task -Branch $Branch -Detail "Codex pid=$($proc.Id)"
        $heartbeat = (Get-Date).AddSeconds($HeartbeatSeconds)
        while (-not $proc.HasExited) {
            if ((Get-Date) -ge $heartbeat) {
                Write-Log "ARBEITET: Codex pid=$($proc.Id)"
                Publish-Status -Phase "ARBEITET" -Task $Task -Branch $Branch -Detail "Codex pid=$($proc.Id)"
                $heartbeat = (Get-Date).AddSeconds($HeartbeatSeconds)
            }
            Start-Sleep 5
        }
        $proc.WaitForExit()
        $exitCode = [int]$proc.ExitCode
        if ($exitCode -ne 0) {
            $stderr = ""
            $stdout = ""
            if (Test-Path -LiteralPath $codexErr) { $stderr = Get-Content -LiteralPath $codexErr -Raw -ErrorAction SilentlyContinue }
            if (Test-Path -LiteralPath $codexOut) { $stdout = Get-Content -LiteralPath $codexOut -Raw -ErrorAction SilentlyContinue }
            $full = ("STDERR:`r`n$stderr`r`nSTDOUT:`r`n$stdout").Trim()
            [IO.File]::WriteAllText($codexCombined,$full,(New-Object Text.UTF8Encoding($false)))
            $brief = $full -replace "`r?`n"," | "
            if ($brief.Length -gt 1800) { $brief = $brief.Substring($brief.Length-1800) }
            $script:LastCodexError = $brief
            Write-Log "Codex Exit ${exitCode}: $brief" "ERROR"
        }
        return $exitCode
    }
    finally {
        Remove-Item -LiteralPath $pf -Force -ErrorAction SilentlyContinue
    }
}

function Verify-Remote {
    param([string]$Branch)
    $local = (& git -C $WorkerDir rev-parse HEAD | Out-String).Trim()
    $line = (& git -C $WorkerDir ls-remote --heads origin "refs/heads/$Branch" | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $line) { throw "Remote-Branch fehlt" }
    $remote = ($line -split '\s+')[0]
    if ($remote -ne $local) { throw "Remote-SHA ungleich: lokal=$local remote=$remote" }
    Write-Log "Remote-Verifikation PASS: $Branch @ $local"
    return $local
}

function Get-TaskBranch {
    param($Task)
    $stem = [IO.Path]::GetFileNameWithoutExtension($Task.path).ToLowerInvariant() -replace '[^a-z0-9-]+','-'
    return "ruediger/$stem-$($Task.blob.Substring(0,8))"
}

function Try-RecoverLocalResult {
    param($Task,[string]$Branch,$State)

    $expectedBranch = Get-TaskBranch $Task
    if ($Branch -cne $expectedBranch) { return $false }

    $dirty = (& git.exe -C $WorkerDir status --porcelain | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $dirty) { return $false }

    & git.exe -C $WorkerDir show-ref --verify --quiet "refs/heads/$Branch"
    if ($LASTEXITCODE -ne 0) { return $false }

    $commit = (& git.exe -C $WorkerDir rev-parse --verify "${Branch}^{commit}" 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $commit) { return $false }

    $subject = (& git.exe -C $WorkerDir log -1 --format=%s $commit | Out-String).Trim()
    $expectedSubject = "Ruediger result for $($Task.path)"
    if ($subject -ne $expectedSubject) { return $false }

    $commitTaskBlob = (& git.exe -C $WorkerDir rev-parse "${commit}:$($Task.path)" 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $commitTaskBlob -or $commitTaskBlob -ne $Task.blob) { return $false }

    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"checkout",$Branch) | Out-Null
    $checkedOutCommit = (& git.exe -C $WorkerDir rev-parse --verify HEAD | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $checkedOutCommit -ne $commit) {
        throw "Recovery-Checkout weicht vom geprueften Ergebnis-Commit ab: erwartet=$commit ist=$checkedOutCommit"
    }
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
    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"checkout","--detach","origin/master") | Out-Null
    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"sparse-checkout","init","--cone") | Out-Null
    Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"sparse-checkout","set","tasks","tools","library","status") | Out-Null
}

try {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "Git fehlt" }
    $cc = Get-Command codex -ErrorAction SilentlyContinue
    if (-not $cc) { throw "Codex fehlt" }
    $CodexExe = $cc.Source
    if (-not (Test-Path (Join-Path (Split-Path $CodexExe -Parent) "codex-code-mode-host.exe"))) { throw "Codex Code-Mode-Host fehlt" }

    Ensure-Worker
    Remove-ExpiredLogs
    Write-Log "START Watcher=$WatcherVersion AgentRoot='$AgentRoot' WorkerDir='$WorkerDir'"
    Fetch-Master

    if ($DiagnosticOnly) {
        Ensure-Preflight -Force
        Publish-Status -Phase "DIAGNOSTIC_PASS" -Detail "Git, Codex und Preflight erreichbar."
        Write-Log "DIAGNOSTIC PASS"
        exit 0
    }

    Publish-Status -Phase "START" -Detail "Watcher $WatcherVersion aktiv."

    while ($true) {
        $task = $null
        $branch = ""
        try {
            Fetch-Master

            if (Sync-RuntimeFromRemote) {
                exit 75
            }

            $state = Read-State
            $task = Select-Task $state

            if ($SelectionTestOnly) {
                if ($task) { $task | ConvertTo-Json -Compress } else { '{"selection":null}' }
                exit 0
            }

            if (-not $task) {
                Compact
                Publish-Status -Phase "WARTET" -Detail "Keine unverarbeitete freigegebene Queue-Task."
                Write-Log "WARTET: keine unverarbeitete freigegebene Queue-Task"
                Start-Sleep $PollSeconds
                continue
            }

            $branch = Get-TaskBranch $task
            if (Try-RecoverLocalResult -Task $task -Branch $branch -State $state) {
                Compact
                continue
            }

            Publish-Status -Phase "TASK_GEFUNDEN" -Task $task -Detail "Freigegebene FIFO-Queue."
            & git.exe -C $WorkerDir sparse-checkout disable 2>$null
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"checkout","--detach","origin/master") | Out-Null
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"reset","--hard","origin/master") | Out-Null
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"clean","-fd") | Out-Null

            & git.exe -C $WorkerDir branch -D $branch 2>$null | Out-Null
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"checkout","-b",$branch,"origin/master") | Out-Null

            Ensure-Preflight

            $prompt = @"
Lies zuerst AGENTS.md und danach die freigegebene Auftragsdatei '$($task.path)' vollstaendig.
Fuehre genau diesen Auftrag aus. Keine neuen Funktionen oder stillen Annahmen.
Schuetze bestaetigte Geometrie und Nutzermasse.
Loese reine CAD-, Mesh-, Script-, Toolchain-, Support-, Druckorientierungs- und Berechnungsprobleme selbststaendig, solange die freigegebene Produktidee unveraendert bleibt.
Bei echter Nutzerentscheidung STOPP/OFFEN und NUTZERENTSCHEIDUNG_ERFORDERLICH dokumentieren.
Erzeuge geforderte CAD-/STL-/Pruef-/Revisionsdateien und den maschinenlesbaren Ergebnisstatus.
Keine finale Nutzerfreigabe behaupten. Nur taskbezogene Dateien aendern.
"@

            Push-Location $WorkerDir
            try { $code = Run-Codex -Exe $CodexExe -Prompt $prompt -Task $task -Branch $branch }
            finally { Pop-Location }

            if ($code -ne 0) {
                Ensure-Preflight -Force
                if ($script:LastCodexError) { throw "Codex Exit $code :: $script:LastCodexError" }
                throw "Codex Exit $code"
            }
            if (-not ((& git -C $WorkerDir status --porcelain | Out-String).Trim())) { throw "Keine Ergebnisdateien" }

            Publish-Status -Phase "VALIDIERT" -Task $task -Branch $branch -Detail "Codex beendet; Ergebnis wird committed und remote verifiziert."
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"add","-A") | Out-Null
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"commit","-m","Ruediger result for $($task.path)") | Out-Null
            Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"push","-u","origin",$branch,"--force-with-lease") -Retries $FetchRetryCount | Out-Null
            $sha = Verify-Remote $branch

            $state.processed += [pscustomobject]@{
                key=$task.key;task=$task.path;blob=$task.blob;source=$task.source;
                branch=$branch;remote_commit=$sha;verified_at=(Get-Date).ToString("o")
            }
            $state.failures = @($state.failures | Where-Object { $_.key -ne $task.key })
            Write-State $state
            Publish-Status -Phase "FERTIG" -Task $task -Branch $branch -Detail "Remote-Verifikation PASS: $sha"
            Write-Log "FERTIG: $($task.path); naechste Queue-Task wird sofort bewertet."
            Compact
            continue
        }
        catch {
            $reason = $_.Exception.Message
            try {
                $fs = Read-State
                if ($task) {
                    $old = @($fs.failures | Where-Object { $_.key -eq $task.key } | Select-Object -Last 1)
                    $attempts = 1
                    if ($old.Count -gt 0 -and $old[0].attempts) { $attempts = [int]$old[0].attempts + 1 }
                    $fs.failures = @($fs.failures | Where-Object { $_.key -ne $task.key })
                    $fs.failures += [pscustomobject]@{
                        key=$task.key;task=$task.path;occurred_at=(Get-Date).ToString("o");
                        attempts=$attempts;reason=$reason
                    }
                    Write-State $fs
                }
            }
            catch { Write-Log "Fehlerstatus nicht schreibbar: $($_.Exception.Message)" "ERROR" }

            Publish-Status -Phase "FEHLER_RETRY" -Task $task -Branch $branch -Detail $reason
            Write-Log "FEHLER: $reason; automatischer Retry folgt." "WARN"
            Start-Sleep $PollSeconds
        }
    }
}
finally {
    try { $lockStream.Close(); $lockStream.Dispose() } catch {}
}
