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
    $profile.max_codex_failures_without_checkpoint -eq 3 -and
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
    'Resolve-TaskCheckpoint',
    'Get-CodexRetryDecision',
    'MaxCodexFailuresWithoutCheckpoint',
    'Publish-Status -Phase "CHECKPOINT"',
    '"BLOCKIERT"',
    'refs/heads/${LiveStatusBranch}',
    'Assert-DedicatedPaths'
)
Add-Validation -Name "workflow-mechanisms" -Status $(if ($queueSemantics) { "PASS" } else { "FAIL" }) -Detail "FIFO, path+blob checkpoints, bounded retry, audit phases, remote verification, worker guard"

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

$workflowPath = Join-Path $PSScriptRoot "documents-agent-workflow.ps1"
. $workflowPath
$gitFixtureRoot = Join-Path ([IO.Path]::GetTempPath()) ("documents-agent-r02-{0}" -f [Guid]::NewGuid().ToString("N"))
try {
    $fixtureStep = "initialize"
    $worker = Join-Path $gitFixtureRoot "worker"
    New-Item -ItemType Directory -Force -Path $gitFixtureRoot,$worker | Out-Null
    $fixtureStep = "git init worker"
    & git.exe -C $worker init 2>$null | Out-Null
    & git.exe -C $worker config user.name "Documents Agent Test"
    & git.exe -C $worker config user.email "documents-agent-test@example.invalid"
    New-Item -ItemType Directory -Force -Path (Join-Path $worker "tasks") | Out-Null
    Set-Content -LiteralPath (Join-Path $worker "tasks/TASK-A.md") -Value "approved task" -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $worker "app.txt") -Value "base" -Encoding UTF8
    & git.exe -C $worker add -A
    $fixtureStep = "git commit base"
    & git.exe -C $worker commit -m "base" 2>$null | Out-Null
    & git.exe -C $worker branch -M main
    $taskPath = "tasks/TASK-A.md"
    $taskBlob = (& git.exe -C $worker rev-parse "HEAD:$taskPath" | Out-String).Trim()
    $baseSha = (& git.exe -C $worker rev-parse HEAD | Out-String).Trim()
    & git.exe -C $worker update-ref refs/remotes/origin/main $baseSha

    $first = Resolve-TaskCheckpoint -Repository $worker -Branch "ruediger/test-first" -TaskPath $taskPath -TaskBlob $taskBlob
    Add-Validation -Name "checkpoint-first-run-base" -Status $(if ($first.status -eq "START_BASE" -and -not $first.checkpoint) { "PASS" } else { "FAIL" }) -Detail "first run without checkpoint selects origin/main base"

    $resumeBranch = "ruediger/test-resume"
    Invoke-DocumentsGit -Repository $worker -Arguments @("checkout","-b",$resumeBranch,"main") | Out-Null
    Set-Content -LiteralPath (Join-Path $worker "app.txt") -Value "checkpoint one" -Encoding UTF8
    & git.exe -C $worker add app.txt
    $checkpointOneMessage = "Ruediger checkpoint 1 for $taskPath`n`nRuediger-Task-Path: $taskPath`nRuediger-Task-Blob: $taskBlob`nRuediger-Base-SHA: $baseSha`nRuediger-Checkpoint: 1`nRuediger-Checkpoint-Verified: true"
    & git.exe -C $worker commit -m $checkpointOneMessage 2>$null | Out-Null
    $checkpointOneSha = (& git.exe -C $worker rev-parse HEAD | Out-String).Trim()
    & git.exe -C $worker update-ref "refs/remotes/origin/$resumeBranch" $checkpointOneSha
    Set-Content -LiteralPath (Join-Path $worker "app.txt") -Value "checkpoint two local" -Encoding UTF8
    & git.exe -C $worker add app.txt
    $checkpointTwoMessage = "Ruediger checkpoint 2 for $taskPath`n`nRuediger-Task-Path: $taskPath`nRuediger-Task-Blob: $taskBlob`nRuediger-Base-SHA: $baseSha`nRuediger-Checkpoint: 2`nRuediger-Checkpoint-Verified: true"
    & git.exe -C $worker commit -m $checkpointTwoMessage 2>$null | Out-Null
    $checkpointTwoSha = (& git.exe -C $worker rev-parse HEAD | Out-String).Trim()
    Set-Content -LiteralPath (Join-Path $worker "unverified.txt") -Value "dirty partial work" -Encoding UTF8
    $resume = Resolve-TaskCheckpoint -Repository $worker -Branch $resumeBranch -TaskPath $taskPath -TaskBlob $taskBlob
    $resumePass = $resume.status -eq "FOUND" -and $resume.source -eq "remote" -and $resume.checkpoint.sha -eq $checkpointOneSha -and $resume.local_dirty
    Add-Validation -Name "checkpoint-remote-resume" -Status $(if ($resumePass) { "PASS" } else { "FAIL" }) -Detail "same task path+blob resumes verified remote checkpoint and rejects dirty worktree as evidence"
    & git.exe -C $worker add unverified.txt
    & git.exe -C $worker commit -m "unverified commit above checkpoint" 2>$null | Out-Null
    $unverifiedHead = (& git.exe -C $worker rev-parse HEAD | Out-String).Trim()
    & git.exe -C $worker update-ref "refs/remotes/origin/$resumeBranch" $unverifiedHead
    $inconsistent = Resolve-TaskCheckpoint -Repository $worker -Branch $resumeBranch -TaskPath $taskPath -TaskBlob $taskBlob
    Add-Validation -Name "checkpoint-inconsistent-head-rejected" -Status $(if ($inconsistent.status -eq "REJECTED" -and -not $inconsistent.checkpoint) { "PASS" } else { "FAIL" }) -Detail "verified ancestor is not adopted when remote HEAD itself is unverified"

    & git.exe -C $worker reset --hard main 2>$null | Out-Null
    & git.exe -C $worker clean -fd 2>$null | Out-Null
    $dirtyBranch = "ruediger/test-dirty"
    Invoke-DocumentsGit -Repository $worker -Arguments @("checkout","-b",$dirtyBranch,"main") | Out-Null
    Set-Content -LiteralPath (Join-Path $worker "app.txt") -Value "unverified only" -Encoding UTF8
    $dirtyResolution = Resolve-TaskCheckpoint -Repository $worker -Branch $dirtyBranch -TaskPath $taskPath -TaskBlob $taskBlob
    Add-Validation -Name "checkpoint-dirty-not-trusted" -Status $(if ($dirtyResolution.status -eq "START_BASE" -and $dirtyResolution.local_dirty -and -not $dirtyResolution.checkpoint) { "PASS" } else { "FAIL" }) -Detail "dirty/unverified state is not silently accepted as checkpoint"

    & git.exe -C $worker reset --hard main 2>$null | Out-Null
    $foreignBranch = "ruediger/test-foreign"
    Invoke-DocumentsGit -Repository $worker -Arguments @("checkout","-B",$foreignBranch,"main") | Out-Null
    Set-Content -LiteralPath (Join-Path $worker "app.txt") -Value "foreign" -Encoding UTF8
    & git.exe -C $worker add app.txt
    $foreignMessage = "foreign checkpoint`n`nRuediger-Task-Path: $taskPath`nRuediger-Task-Blob: 0000000000000000000000000000000000000000`nRuediger-Base-SHA: $baseSha`nRuediger-Checkpoint: 1`nRuediger-Checkpoint-Verified: true"
    & git.exe -C $worker commit -m $foreignMessage 2>$null | Out-Null
    $foreignSha = (& git.exe -C $worker rev-parse HEAD | Out-String).Trim()
    & git.exe -C $worker update-ref "refs/remotes/origin/$foreignBranch" $foreignSha
    $foreign = Resolve-TaskCheckpoint -Repository $worker -Branch $foreignBranch -TaskPath $taskPath -TaskBlob $taskBlob
    Add-Validation -Name "checkpoint-foreign-blob-rejected" -Status $(if ($foreign.status -eq "REJECTED" -and -not $foreign.checkpoint) { "PASS" } else { "FAIL" }) -Detail "foreign task blob is never resumed"

    $retry1 = Get-CodexRetryDecision -PreviousFailures 0 -MaximumFailures 3
    $retry2 = Get-CodexRetryDecision -PreviousFailures $retry1.failures_without_checkpoint -MaximumFailures 3
    $retry3 = Get-CodexRetryDecision -PreviousFailures $retry2.failures_without_checkpoint -MaximumFailures 3
    Add-Validation -Name "retry-budget-blocks-third-error" -Status $(if (-not $retry1.blocked -and -not $retry2.blocked -and $retry3.blocked -and $retry3.failures_without_checkpoint -eq 3) { "PASS" } else { "FAIL" }) -Detail "third consecutive Codex error without checkpoint becomes BLOCKIERT"
    $verifiedSecond = Get-VerifiedTaskCommit -Repository $worker -Commit $checkpointTwoSha -TaskPath $taskPath -TaskBlob $taskBlob -Kind checkpoint
    $retryReset = Get-CodexRetryDecision -PreviousFailures 2 -PreviousCheckpointSha $checkpointOneSha -CurrentCheckpointSha $verifiedSecond.sha -MaximumFailures 3
    Add-Validation -Name "retry-budget-reset-on-checkpoint" -Status $(if ($retryReset.new_checkpoint -and -not $retryReset.blocked -and $retryReset.failures_without_checkpoint -eq 1) { "PASS" } else { "FAIL" }) -Detail "new verified checkpoint starts a fresh bounded failure sequence"

    & git.exe -C $worker reset --hard main 2>$null | Out-Null
    $finalBranch = "ruediger/test-final"
    Invoke-DocumentsGit -Repository $worker -Arguments @("checkout","-B",$finalBranch,"main") | Out-Null
    Set-Content -LiteralPath (Join-Path $worker "app.txt") -Value "final" -Encoding UTF8
    & git.exe -C $worker add app.txt
    $finalMessage = "Ruediger result for $taskPath`n`nRuediger-Task-Path: $taskPath`nRuediger-Task-Blob: $taskBlob`nRuediger-Base-SHA: $baseSha`nRuediger-Final: true"
    & git.exe -C $worker commit -m $finalMessage 2>$null | Out-Null
    $finalSha = (& git.exe -C $worker rev-parse HEAD | Out-String).Trim()
    & git.exe -C $worker update-ref "refs/remotes/origin/$finalBranch" $finalSha
    $finalIdentity = Get-VerifiedTaskCommit -Repository $worker -Commit $finalSha -TaskPath $taskPath -TaskBlob $taskBlob -Kind final
    $remoteTrackingSha = (& git.exe -C $worker rev-parse "refs/remotes/origin/$finalBranch" | Out-String).Trim()
    $verifyRemoteStatic = Test-Contains -Path $watcherPath -Needles @('ls-remote --heads origin "refs/heads/$Branch"','if ($remote -ne $local) { throw "Remote-SHA ungleich: lokal=$local remote=$remote" }')
    Add-Validation -Name "final-result-remote-sha" -Status $(if ($finalIdentity -and $remoteTrackingSha -eq $finalSha -and $verifyRemoteStatic) { "PASS" } else { "FAIL" }) -Detail "synthetic remote ref plus production ls-remote exact-SHA verification"
}
catch {
    Add-Validation -Name "checkpoint-synthetic-fixture" -Status "FAIL" -Detail "$fixtureStep :: $($_.Exception.Message)"
}
finally {
    $tempRootPrefix = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    $fixtureFull = [IO.Path]::GetFullPath($gitFixtureRoot)
    if ($fixtureFull.StartsWith($tempRootPrefix,[StringComparison]::OrdinalIgnoreCase) -and (Split-Path $fixtureFull -Leaf).StartsWith("documents-agent-r02-")) {
        Remove-Item -LiteralPath $fixtureFull -Recurse -Force -ErrorAction SilentlyContinue
    }
}

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
    task = "tasks/TASK-DOCUMENTS-SOFTWARE-WORKFLOW-R02.md"
    revision = "R02"
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
