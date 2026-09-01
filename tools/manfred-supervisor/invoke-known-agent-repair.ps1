param(
    [Parameter(Mandatory=$true)]
    [string]$RequestPath,
    [string]$Root = 'D:\Manfred-Supervisor',
    [string]$SourceRepository = 'D:\AI3D-Agent\worker\AI3D-Model-worker',
    [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'

function Get-NormalizedGitUrl {
    param([string]$Url)
    (($Url.Trim() -replace '\\','/') -replace '/$','' -replace '\.git$','').ToLowerInvariant()
}

function Get-NormalizedPath {
    param([string]$Path)
    [IO.Path]::GetFullPath($Path).TrimEnd('\')
}

function Invoke-GitText {
    param([string[]]$Arguments)
    $output = @(& git.exe -C $SourceRepository @Arguments 2>&1)
    if ($LASTEXITCODE -ne 0) { throw "Git fehlgeschlagen: git $($Arguments -join ' ') :: $($output -join ' | ')" }
    ($output -join "`n").Trim()
}

$knownAgents = @{
    AI3D = [pscustomobject]@{
        root = 'D:\AI3D-Agent'
        worker = 'D:\AI3D-Agent\worker\AI3D-Model-worker'
        scheduler = 'AI3D-Ruediger-Agent'
        origin = 'https://github.com/h4rdstyle1988/AI3D-Model'
        watcher = 'D:\AI3D-Agent\runtime\ruediger-agent-watch.ps1'
        state = 'D:\AI3D-Agent\state\task-state.json'
    }
    Documents = [pscustomobject]@{
        root = 'D:\Documents-Controlling-Agent'
        worker = 'D:\Documents-Controlling-Agent\worker\Documents-Controlling-clear-worker'
        scheduler = 'Documents-Ruediger-Agent'
        origin = 'https://github.com/h4rdstyle1988/Documents-Controlling-clear'
        watcher = 'D:\Documents-Controlling-Agent\runtime\documents-agent-watch.ps1'
        state = 'D:\Documents-Controlling-Agent\state\documents-task-state.json'
    }
}

# A repair is executable only when its ID, target, repository path and Git blob
# all match this local allowlist. Updating this list requires a controlled
# MANFRED bootstrap; a GitHub change alone cannot add executable maintenance.
$knownRepairs = @{
    'documents-r02.3-hidden-loop-guard' = [pscustomobject]@{
        agent = 'Documents'
        script_path = 'tools/documents-agent/hotfix-documents-r02.3-hidden-loop-guard.ps1'
        script_blob = 'c0eea92eaeb62ba7f6898c95917fc3f23d4e6ea6'
    }
}

$maintenanceRoot = Join-Path $Root 'maintenance'
$resultsDir = Join-Path $maintenanceRoot 'results'
$archiveDir = Join-Path $maintenanceRoot 'archive'
$backupRoot = Join-Path $maintenanceRoot 'backups'
$tempDir = Join-Path $maintenanceRoot 'temp'
$audit = [ordered]@{
    schema_version = 1
    supervisor = 'MANFRED'
    supervisor_version = 'R01.1'
    request_id = $null
    repair_id = $null
    target_agent = $null
    source_commit = $null
    script_path = $null
    script_blob = $null
    status = 'BLOCKED'
    started_at = (Get-Date).ToString('o')
    completed_at = $null
    validate_only = [bool]$ValidateOnly
    stash = $null
    backups = @()
    scheduler = $null
    output = @()
    reason = $null
}

try {
    if (-not (Test-Path -LiteralPath $RequestPath -PathType Leaf)) { throw "Maintenance-Request fehlt: $RequestPath" }
    $request = Get-Content -LiteralPath $RequestPath -Raw | ConvertFrom-Json
    if ([int]$request.schema_version -ne 1) { throw 'Unbekannte Maintenance-Request-Schemaversion.' }
    if ([string]$request.request_id -notmatch '^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$') { throw 'Ungueltige request_id.' }
    if ([string]$request.source_commit -notmatch '^[0-9a-fA-F]{40}$') { throw 'source_commit muss ein voller Git-SHA sein.' }

    $audit.request_id = [string]$request.request_id
    $audit.repair_id = [string]$request.repair_id
    $audit.source_commit = ([string]$request.source_commit).ToLowerInvariant()

    if (-not $knownRepairs.ContainsKey($audit.repair_id)) { throw "Repair-ID ist nicht erlaubt: $($audit.repair_id)" }
    $repair = $knownRepairs[$audit.repair_id]
    $agent = $knownAgents[$repair.agent]
    if (-not $agent) { throw "Repair verweist nicht auf einen bekannten Agenten: $($repair.agent)" }
    if ($request.target_agent -and [string]$request.target_agent -ne $repair.agent) { throw 'Request-Ziel stimmt nicht mit der Repair-Allowlist ueberein.' }

    $audit.target_agent = $repair.agent
    $audit.script_path = $repair.script_path
    $audit.script_blob = $repair.script_blob
    $audit.scheduler = $agent.scheduler

    $allowedPrefix = ($repair.script_path -like 'tools/manfred-supervisor/maintenance/*' -or $repair.script_path -like 'tools/documents-agent/*')
    if (-not $allowedPrefix -or $repair.script_path -match '(^|/)\.\.(/|$)') { throw "Repair-Skriptpfad ist nicht erlaubt: $($repair.script_path)" }

    $sourceFull = Get-NormalizedPath $SourceRepository
    $expectedSource = Get-NormalizedPath $knownAgents.AI3D.worker
    if (-not $sourceFull.Equals($expectedSource,[StringComparison]::OrdinalIgnoreCase) -and -not $ValidateOnly) {
        throw "SourceRepository ist nicht der bekannte AI3D-Worker: $sourceFull"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $sourceFull '.git') -PathType Container)) { throw "SourceRepository ist kein Git-Repo: $sourceFull" }
    $sourceOrigin = (& git.exe -C $sourceFull remote get-url origin 2>$null | Out-String).Trim()
    if ((Get-NormalizedGitUrl $sourceOrigin) -ne (Get-NormalizedGitUrl $knownAgents.AI3D.origin)) { throw "Unerwartetes Source-Origin: $sourceOrigin" }

    [void](Invoke-GitText -Arguments @('cat-file','-e',"$($audit.source_commit)^{commit}"))
    & git.exe -C $sourceFull merge-base --is-ancestor $audit.source_commit 'refs/remotes/origin/master' 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'source_commit ist kein nachgewiesener Vorfahr von origin/master.' }
    $actualBlob = (Invoke-GitText -Arguments @('rev-parse',"$($audit.source_commit):$($repair.script_path)")).ToLowerInvariant()
    if ($actualBlob -ne $repair.script_blob) { throw "Skript-Blob ist nicht allowlisted: erwartet=$($repair.script_blob) ist=$actualBlob" }

    $scriptText = Invoke-GitText -Arguments @('cat-file','blob',$actualBlob)
    $tokens = $null; $errors = $null
    [void][Management.Automation.Language.Parser]::ParseInput($scriptText,[ref]$tokens,[ref]$errors)
    if ($errors.Count -gt 0) { throw ('Maintenance-Skript Parser-FEHLER: ' + (($errors | ForEach-Object Message) -join ' | ')) }

    $workerFull = Get-NormalizedPath $agent.worker
    $expectedWorkerRoot = (Get-NormalizedPath (Join-Path $agent.root 'worker')) + '\'
    if (-not $workerFull.StartsWith($expectedWorkerRoot,[StringComparison]::OrdinalIgnoreCase)) { throw "Worker liegt nicht im bekannten AgentRoot: $workerFull" }
    if (-not (Test-Path -LiteralPath (Join-Path $workerFull '.git') -PathType Container)) { throw "Ziel-Worker ist kein Git-Repo: $workerFull" }
    $targetOrigin = (& git.exe -C $workerFull remote get-url origin 2>$null | Out-String).Trim()
    if ((Get-NormalizedGitUrl $targetOrigin) -ne (Get-NormalizedGitUrl $agent.origin)) { throw "Unerwartetes Ziel-Origin: $targetOrigin" }
    if (-not (Test-Path -LiteralPath $agent.watcher -PathType Leaf)) { throw "Ziel-Watcher fehlt: $($agent.watcher)" }

    $watchTokens = $null; $watchErrors = $null
    [void][Management.Automation.Language.Parser]::ParseFile($agent.watcher,[ref]$watchTokens,[ref]$watchErrors)
    if ($watchErrors.Count -gt 0) { throw ('Bestehender Ziel-Watcher Parser-FEHLER: ' + (($watchErrors | ForEach-Object Message) -join ' | ')) }

    if ($ValidateOnly) {
        $audit.status = 'VALIDATED'
        $audit.reason = 'Allowlist, AgentRoot, Worker-Pfad, Origins, Git-Blob und Parserchecks PASS; keine lokale Aenderung ausgefuehrt.'
    }
    else {
        New-Item -ItemType Directory -Force -Path $resultsDir,$archiveDir,$backupRoot,$tempDir | Out-Null
        $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
        $requestBackupDir = Join-Path $backupRoot ("$($audit.request_id)-$stamp")
        New-Item -ItemType Directory -Force -Path $requestBackupDir | Out-Null

        $dirty = (& git.exe -C $workerFull status --porcelain | Out-String).Trim()
        if ($dirty) {
            $audit.stash = "manfred-$($audit.request_id)-$stamp"
            & git.exe -C $workerFull stash push -u -m $audit.stash | Out-Null
            if ($LASTEXITCODE -ne 0) { throw 'Laufende ungesicherte Worker-Arbeit konnte nicht gestasht werden.' }
        }

        $watcherBackup = Join-Path $requestBackupDir (Split-Path $agent.watcher -Leaf)
        Copy-Item -LiteralPath $agent.watcher -Destination $watcherBackup -Force
        $audit.backups += $watcherBackup
        if (Test-Path -LiteralPath $agent.state -PathType Leaf) {
            $stateBackup = Join-Path $requestBackupDir (Split-Path $agent.state -Leaf)
            Copy-Item -LiteralPath $agent.state -Destination $stateBackup -Force
            $audit.backups += $stateBackup
        }

        $tempScript = Join-Path $tempDir ("$($audit.request_id)-$actualBlob.ps1")
        [IO.File]::WriteAllText($tempScript,$scriptText,(New-Object Text.UTF8Encoding($false)))
        $childOutput = @(& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $tempScript -AgentRoot $agent.root -SchedulerTaskName $agent.scheduler 2>&1)
        $childExit = $LASTEXITCODE
        $audit.output = @($childOutput | ForEach-Object { [string]$_ })
        if ($childExit -ne 0) { throw "Allowlisted Maintenance-Skript Exit $childExit" }
        $audit.status = 'PASS'
        $audit.reason = 'Allowlisted, blobgebundenes Maintenance-Skript erfolgreich ausgefuehrt.'
    }
}
catch {
    $audit.status = 'BLOCKED'
    $audit.reason = $_.Exception.Message
}
finally {
    $audit.completed_at = (Get-Date).ToString('o')
    if (-not $ValidateOnly) {
        New-Item -ItemType Directory -Force -Path $resultsDir,$archiveDir | Out-Null
        $safeId = $(if ($audit.request_id) { $audit.request_id } else { 'invalid-' + (Get-Date -Format 'yyyyMMdd-HHmmss') })
        $resultPath = Join-Path $resultsDir "$safeId.json"
        [IO.File]::WriteAllText($resultPath,($audit | ConvertTo-Json -Depth 8),(New-Object Text.UTF8Encoding($false)))
        if (Test-Path -LiteralPath $RequestPath -PathType Leaf) {
            $archivePath = Join-Path $archiveDir ("$safeId-request.json")
            Move-Item -LiteralPath $RequestPath -Destination $archivePath -Force
        }
    }
}

[pscustomobject]$audit
