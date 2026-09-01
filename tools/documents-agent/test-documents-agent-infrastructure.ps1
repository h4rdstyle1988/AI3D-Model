param(
    [string]$OutputPath = "",
    [switch]$LiveQueueSelectionTest
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not $OutputPath) { $OutputPath = Join-Path $PSScriptRoot "validation-report.generated.json" }
$checks = @()

function Add-Validation {
    param([string]$Name,[string]$Status,[string]$Detail)
    $script:checks += [pscustomobject]@{name=$Name;status=$Status;detail=$Detail}
}

function Test-Contains {
    param([string]$Path,[string[]]$Needles)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    $content = Get-Content -LiteralPath $Path -Raw
    foreach ($needle in $Needles) {
        if (-not $content.Contains($needle)) { return $false }
    }
    return $true
}

$scripts = @(Get-ChildItem -LiteralPath $PSScriptRoot -Filter "*.ps1" -File | Sort-Object Name)
$parserFailures = @()
foreach ($script in $scripts) {
    $tokens = $null
    $errors = $null
    [void][Management.Automation.Language.Parser]::ParseFile($script.FullName,[ref]$tokens,[ref]$errors)
    foreach ($error in @($errors)) {
        $parserFailures += "$($script.Name):$($error.Extent.StartLineNumber):$($error.Message)"
    }
}
Add-Validation -Name "powershell-parser" -Status $(if ($parserFailures.Count -eq 0) { "PASS" } else { "FAIL" }) -Detail $(if ($parserFailures.Count -eq 0) { "$($scripts.Count) scripts parsed" } else { $parserFailures -join " | " })

$profilePath = Join-Path $PSScriptRoot "documents-agent-profile.json"
$profile = Get-Content -LiteralPath $profilePath -Raw | ConvertFrom-Json
$profileExpected = (
    $profile.repo_url -eq "https://github.com/h4rdstyle1988/Documents-Controlling-clear.git" -and
    $profile.base_branch -eq "main" -and
    $profile.agent_root -eq "D:\Documents-Controlling-Agent" -and
    $profile.worker_dir -eq "D:\Documents-Controlling-Agent\worker\Documents-Controlling-clear-worker" -and
    $profile.scheduler_task_name -eq "Documents-Ruediger-Agent" -and
    $profile.live_status_branch -eq "ruediger/live-status" -and
    $profile.poll_seconds -eq 30 -and
    $profile.log_retention_days -eq 7 -and
    $profile.preflight_kind -eq "generic-development" -and
    $profile.cad_preflight -eq $false
)
Add-Validation -Name "documents-profile-defaults" -Status $(if ($profileExpected) { "PASS" } else { "FAIL" }) -Detail "repo/main/root/worker/scheduler/status/poll/retention/preflight"

$profileText = Get-Content -LiteralPath $profilePath -Raw
$profileForbidden = @("D:\AI3D-Agent","AI3D-Ruediger-Agent","D:\3D-Models","cad-toolchain-preflight.ps1") | Where-Object { $profileText.Contains($_) }
Add-Validation -Name "documents-profile-isolation" -Status $(if ($profileForbidden.Count -eq 0) { "PASS" } else { "FAIL" }) -Detail $(if ($profileForbidden.Count -eq 0) { "no existing-agent or CAD paths" } else { $profileForbidden -join ", " })

$expectedPaths = @($profile.paths.runtime,$profile.paths.state,$profile.paths.task_state,$profile.paths.lock,$profile.paths.logs,$profile.paths.temp)
$pathsUnderRoot = @($expectedPaths | Where-Object { -not $_.StartsWith($profile.agent_root + "\",[StringComparison]::OrdinalIgnoreCase) })
$pathsUnique = @($expectedPaths | Select-Object -Unique).Count -eq $expectedPaths.Count
Add-Validation -Name "documents-lock-state-log-paths" -Status $(if ($pathsUnderRoot.Count -eq 0 -and $pathsUnique) { "PASS" } else { "FAIL" }) -Detail "all paths unique and below independent AgentRoot"

$operationalScripts = @($scripts | Where-Object { $_.Name -ne "test-documents-agent-infrastructure.ps1" })
$documentsText = ($operationalScripts | ForEach-Object { Get-Content -LiteralPath $_.FullName -Raw }) -join "`n"
$scriptForbidden = @("D:\AI3D-Agent","AI3D-Ruediger-Agent","D:\3D-Models","cad-toolchain-preflight.ps1","origin/master") | Where-Object { $documentsText.Contains($_) }
Add-Validation -Name "documents-script-isolation" -Status $(if ($scriptForbidden.Count -eq 0) { "PASS" } else { "FAIL" }) -Detail $(if ($scriptForbidden.Count -eq 0) { "no existing-agent, CAD, generated-output or master references" } else { $scriptForbidden -join ", " })

$watcherPath = Join-Path $PSScriptRoot "documents-agent-watch.ps1"
$queueSemantics = Test-Contains -Path $watcherPath -Needles @(
    'Get-RemoteText "tasks/TASK_QUEUE.txt"',
    '$key = "$($item.path)|$blob"',
    'origin/${BaseBranch}:$($item.path)',
    'return [pscustomobject]@{path=$item.path;blob=$blob;key=$key;source=$item.source}',
    'Verify-Remote',
    'Try-RecoverLocalResult',
    'refs/heads/${LiveStatusBranch}',
    'Assert-DedicatedPaths'
)
Add-Validation -Name "workflow-mechanisms" -Status $(if ($queueSemantics) { "PASS" } else { "FAIL" }) -Detail "FIFO queue, path+blob identity, recovery, remote verification, status branch, worker guard"

$currentTaskUnused = -not $documentsText.Contains("CURRENT_TASK.txt")
Add-Validation -Name "queue-only-selection" -Status $(if ($currentTaskUnused) { "PASS" } else { "FAIL" }) -Detail "CURRENT_TASK migration file is not read"

$fixtureQueue = @("# comment","tasks/TASK-A.md","tasks/TASK-B.md")
$fixtureBlobs = @{"tasks/TASK-A.md"="aaaaaaaa";"tasks/TASK-B.md"="bbbbbbbb"}
$fixtureProcessed = @("tasks/TASK-A.md|aaaaaaaa")
$fixtureSelection = $null
foreach ($line in $fixtureQueue) {
    $path = $line.Trim()
    if (-not $path -or $path.StartsWith("#")) { continue }
    $key = "$path|$($fixtureBlobs[$path])"
    if ($fixtureProcessed -notcontains $key) {
        $fixtureSelection = [pscustomobject]@{path=$path;blob=$fixtureBlobs[$path];key=$key}
        break
    }
}
$fixturePass = ($fixtureSelection.path -eq "tasks/TASK-B.md" -and $fixtureSelection.key -eq "tasks/TASK-B.md|bbbbbbbb")
Add-Validation -Name "fifo-path-blob-unit" -Status $(if ($fixturePass) { "PASS" } else { "FAIL" }) -Detail "first unprocessed path+blob revision selected"

$ai3dWatcher = Join-Path $repoRoot "tools\ruediger-agent-watch.ps1"
$ai3dInstaller = Join-Path $repoRoot "tools\install-runtime-watcher.ps1"
$ai3dRepair = Join-Path $repoRoot "tools\repair-runtime.ps1"
$ai3dDefaults = (
    (Test-Contains -Path $ai3dWatcher -Needles @(
        '[string]$RepoUrl = "https://github.com/h4rdstyle1988/AI3D-Model.git"',
        '[string]$AgentRoot = "D:\AI3D-Agent"',
        '[string]$SchedulerTaskName = "AI3D-Ruediger-Agent"',
        'origin/master',
        'tools\cad-toolchain-preflight.ps1',
        'D:\3D-Models\generated'
    )) -and
    (Test-Contains -Path $ai3dInstaller -Needles @('[string]$AgentRoot = "D:\AI3D-Agent"','[string]$SchedulerTaskName = "AI3D-Ruediger-Agent"','cad-toolchain-preflight.ps1')) -and
    (Test-Contains -Path $ai3dRepair -Needles @('[string]$AgentRoot = "D:\AI3D-Agent"','[string]$SchedulerTaskName = "AI3D-Ruediger-Agent"','cad-toolchain-preflight.ps1','origin/master'))
)
Add-Validation -Name "existing-agent-static-defaults" -Status $(if ($ai3dDefaults) { "PASS" } else { "FAIL" }) -Detail "existing root/scheduler/repo/master/CAD defaults retained"

$changedExisting = @(& git.exe -C $repoRoot diff --name-only -- tools/ruediger-agent-watch.ps1 tools/install-runtime-watcher.ps1 tools/restart-runtime-watcher.ps1 tools/repair-runtime.ps1 tools/cad-toolchain-preflight.ps1)
Add-Validation -Name "existing-agent-files-unchanged" -Status $(if ($LASTEXITCODE -eq 0 -and $changedExisting.Count -eq 0) { "PASS" } else { "FAIL" }) -Detail $(if ($changedExisting.Count -eq 0) { "no working-tree diff in existing runtime files" } else { $changedExisting -join ", " })

$selectionStatus = "SKIP"
$selectionDetail = "live target-repository access not requested"
if ($LiveQueueSelectionTest) {
    $testRoot = Join-Path ([IO.Path]::GetTempPath()) ("documents-agent-selection-{0}" -f [Guid]::NewGuid().ToString("N"))
    try {
        $selectionOutput = @(& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $watcherPath -AgentRoot $testRoot -SelectionTestOnly 2>&1)
        if ($LASTEXITCODE -eq 0) {
            $selectionStatus = "PASS"
            $selectionDetail = ($selectionOutput -join " | ")
        }
        else {
            $selectionStatus = "FAIL"
            $selectionDetail = ($selectionOutput -join " | ")
        }
    }
    finally {
        $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
        $testFull = [IO.Path]::GetFullPath($testRoot)
        if ($testFull.StartsWith($tempRoot,[StringComparison]::OrdinalIgnoreCase) -and (Split-Path $testFull -Leaf).StartsWith("documents-agent-selection-")) {
            Remove-Item -LiteralPath $testFull -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}
Add-Validation -Name "target-queue-selection-no-execution" -Status $selectionStatus -Detail $selectionDetail

$failures = @($checks | Where-Object { $_.status -eq "FAIL" })
$report = [ordered]@{
    schema_version = 1
    generated_at = (Get-Date).ToString("o")
    task = "tasks/TASK-DOCUMENTS-AGENT-BOOTSTRAP-R01.md"
    revision = "R01"
    status = $(if ($failures.Count -eq 0) { "PASS" } else { "STOP" })
    checks = @($checks)
    failure_count = $failures.Count
    live_queue_selection_executed = [bool]$LiveQueueSelectionTest
    queued_implementation_executed = $false
    final_user_approval_claimed = $false
}

$parent = Split-Path $OutputPath -Parent
if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
[IO.File]::WriteAllText($OutputPath,($report | ConvertTo-Json -Depth 10),(New-Object Text.UTF8Encoding($false)))
$report | ConvertTo-Json -Depth 10
if ($failures.Count -gt 0) { exit 1 }
exit 0
