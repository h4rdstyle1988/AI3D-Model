param(
    [string]$WatcherPath = (Join-Path $PSScriptRoot "ruediger-agent-watch.ps1")
)

$ErrorActionPreference = "Stop"
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ("ai3d-watcher-recovery-{0}" -f [guid]::NewGuid().ToString("N"))
$script:PushCalls = 0
$script:PushRetries = $null
$script:StateWrites = 0
$script:VerifySha = ""

function Assert-True {
    param([bool]$Condition,[string]$Message)
    if (-not $Condition) { throw "ASSERT: $Message" }
}

function Invoke-TestGit {
    param([Parameter(ValueFromRemainingArguments=$true)][string[]]$GitArgs)
    $oldErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = @(& git.exe @GitArgs 2>&1)
        $gitExitCode = [int]$LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $oldErrorActionPreference
    }
    if ($gitExitCode -ne 0) {
        throw "git $($GitArgs -join ' ') fehlgeschlagen: $($output -join ' | ')"
    }
    return (($output | ForEach-Object { $_.ToString() }) -join "`n").Trim()
}

try {
    if (-not (Test-Path -LiteralPath $WatcherPath -PathType Leaf)) { throw "Watcher fehlt: $WatcherPath" }
    if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) { throw "git.exe fehlt" }

    $tokens = $null
    $parseErrors = $null
    $watcherAst = [Management.Automation.Language.Parser]::ParseFile($WatcherPath,[ref]$tokens,[ref]$parseErrors)
    Assert-True ($parseErrors.Count -eq 0) "Watcher hat PowerShell-Syntaxfehler."

    $requiredFunctions = @("Get-TaskBranch","Try-RecoverLocalResult")
    foreach ($functionName in $requiredFunctions) {
        $functionAst = $watcherAst.Find({
            param($node)
            $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $functionName
        },$true)
        Assert-True ($null -ne $functionAst) "Funktion $functionName fehlt."
        Invoke-Expression $functionAst.Extent.Text
    }

    function Invoke-GitSafe {
        param([string[]]$GitArgs,[int]$Retries = 1)
        if ($GitArgs -contains "checkout") {
            Invoke-TestGit @GitArgs | Out-Null
            return
        }
        if ($GitArgs -contains "push") {
            $script:PushCalls++
            $script:PushRetries = $Retries
            return
        }
        throw "Unerwarteter Invoke-GitSafe-Aufruf: $($GitArgs -join ' ')"
    }
    function Publish-Status { param($Phase,$Task,$Branch,$Detail) }
    function Write-Log { param($Message,$Level) }
    function Verify-Remote { param($Branch); return $script:VerifySha }
    function Write-State { param($State); $script:StateWrites++ }

    New-Item -ItemType Directory -Path $testRoot | Out-Null
    $WorkerDir = Join-Path $testRoot "repo"
    New-Item -ItemType Directory -Path $WorkerDir | Out-Null
    Invoke-TestGit -C $WorkerDir init -b master | Out-Null
    Invoke-TestGit -C $WorkerDir config user.name "Watcher Smoke Test" | Out-Null
    Invoke-TestGit -C $WorkerDir config user.email "watcher-smoke@example.invalid" | Out-Null

    $taskPath = "tasks/TASK-SMOKE.md"
    New-Item -ItemType Directory -Path (Join-Path $WorkerDir "tasks") | Out-Null
    Set-Content -LiteralPath (Join-Path $WorkerDir $taskPath) -Value "freigegebene Revision" -Encoding UTF8
    Invoke-TestGit -C $WorkerDir add -- $taskPath | Out-Null
    Invoke-TestGit -C $WorkerDir commit -m "Add smoke task" | Out-Null
    $taskBlob = Invoke-TestGit -C $WorkerDir rev-parse "HEAD:$taskPath"

    $Task = [pscustomobject]@{
        path = $taskPath
        blob = $taskBlob
        key = "$taskPath|$taskBlob"
        source = "TASK_QUEUE"
    }
    $expectedBranch = Get-TaskBranch $Task
    Invoke-TestGit -C $WorkerDir checkout -b $expectedBranch | Out-Null
    Set-Content -LiteralPath (Join-Path $WorkerDir "result.txt") -Value "fertiges lokales Ergebnis" -Encoding UTF8
    Invoke-TestGit -C $WorkerDir add -- result.txt | Out-Null
    Invoke-TestGit -C $WorkerDir commit -m "Ruediger result for $taskPath" | Out-Null
    $resultCommit = Invoke-TestGit -C $WorkerDir rev-parse HEAD

    Invoke-TestGit -C $WorkerDir checkout master | Out-Null
    Set-Content -LiteralPath (Join-Path $WorkerDir "workflow.txt") -Value "master ist weitergelaufen" -Encoding UTF8
    Invoke-TestGit -C $WorkerDir add -- workflow.txt | Out-Null
    Invoke-TestGit -C $WorkerDir commit -m "Advance workflow on master" | Out-Null
    & git.exe -C $WorkerDir merge-base --is-ancestor master $resultCommit 2>$null
    Assert-True ($LASTEXITCODE -ne 0) "Smoke-Setup bildet keinen weitergelaufenen master ab."

    $FetchRetryCount = 3
    $cleanState = [pscustomobject]@{processed=@();failures=@()}
    $wrongBranchRecovered = Try-RecoverLocalResult -Task $Task -Branch "ruediger/falscher-branch" -State $cleanState
    Assert-True (-not $wrongBranchRecovered) "Falscher Branch wurde wiederverwendet."

    $wrongBlob = "0000000000000000000000000000000000000000"
    $wrongBlobTask = [pscustomobject]@{
        path = $taskPath
        blob = $wrongBlob
        key = "$taskPath|$wrongBlob"
        source = "TASK_QUEUE"
    }
    $wrongBlobBranch = Get-TaskBranch $wrongBlobTask
    Invoke-TestGit -C $WorkerDir branch $wrongBlobBranch $resultCommit | Out-Null
    $wrongBlobRecovered = Try-RecoverLocalResult -Task $wrongBlobTask -Branch $wrongBlobBranch -State $cleanState
    Assert-True (-not $wrongBlobRecovered) "Falscher Task-Blob wurde wiederverwendet."

    Invoke-TestGit -C $WorkerDir checkout -b smoke-wrong-subject $resultCommit | Out-Null
    Set-Content -LiteralPath (Join-Path $WorkerDir "wrong-subject.txt") -Value "falsches Subject" -Encoding UTF8
    Invoke-TestGit -C $WorkerDir add -- wrong-subject.txt | Out-Null
    Invoke-TestGit -C $WorkerDir commit -m "Wrong result subject" | Out-Null
    $wrongSubjectCommit = Invoke-TestGit -C $WorkerDir rev-parse HEAD
    Invoke-TestGit -C $WorkerDir checkout master | Out-Null
    Invoke-TestGit -C $WorkerDir branch -f $expectedBranch $wrongSubjectCommit | Out-Null
    $wrongSubjectRecovered = Try-RecoverLocalResult -Task $Task -Branch $expectedBranch -State $cleanState
    Assert-True (-not $wrongSubjectRecovered) "Falsches Commit-Subject wurde wiederverwendet."
    Invoke-TestGit -C $WorkerDir branch -f $expectedBranch $resultCommit | Out-Null

    Set-Content -LiteralPath (Join-Path $WorkerDir "dirty.txt") -Value "dirty" -Encoding UTF8
    $dirtyHead = Invoke-TestGit -C $WorkerDir rev-parse HEAD
    $dirtyRecovered = Try-RecoverLocalResult -Task $Task -Branch $expectedBranch -State $cleanState
    Assert-True (-not $dirtyRecovered) "Dirty Working Tree wurde wiederverwendet."
    Assert-True ((Invoke-TestGit -C $WorkerDir rev-parse HEAD) -eq $dirtyHead) "Dirty-Pruefung hat den Branch gewechselt."
    Remove-Item -LiteralPath (Join-Path $WorkerDir "dirty.txt") -Force

    $script:VerifySha = "1111111111111111111111111111111111111111"
    $script:PushCalls = 0
    $script:StateWrites = 0
    $mismatchThrown = $false
    try {
        Try-RecoverLocalResult -Task $Task -Branch $expectedBranch -State ([pscustomobject]@{processed=@();failures=@()}) | Out-Null
    }
    catch {
        $mismatchThrown = $_.Exception.Message -match "Remote-SHA"
    }
    Assert-True $mismatchThrown "Remote-SHA-Mismatch wurde nicht abgewiesen."
    Assert-True ($script:StateWrites -eq 0) "State wurde vor strikter Remote-SHA-Verifikation geschrieben."

    Invoke-TestGit -C $WorkerDir checkout master | Out-Null
    $script:VerifySha = $resultCommit
    $script:PushCalls = 0
    $script:PushRetries = $null
    $script:StateWrites = 0
    $successState = [pscustomobject]@{processed=@();failures=@([pscustomobject]@{key=$Task.key})}
    $recovered = Try-RecoverLocalResult -Task $Task -Branch $expectedBranch -State $successState
    Assert-True $recovered "Exaktes lokales Ergebnis wurde bei weitergelaufenem master nicht wiederverwendet."
    Assert-True ($script:PushCalls -eq 1) "Recovery hat nicht genau einen begrenzten Push-Aufruf ausgeloest."
    Assert-True ($script:PushRetries -eq $FetchRetryCount) "Recovery-Push verwendet nicht die konfigurierte Retry-Grenze."
    Assert-True ($script:StateWrites -eq 1) "State wurde nach erfolgreicher Remote-Verifikation nicht genau einmal geschrieben."
    Assert-True ($successState.processed.Count -eq 1) "Task wurde nach erfolgreicher Verifikation nicht verarbeitet markiert."
    Assert-True ($successState.processed[0].remote_commit -eq $resultCommit) "State enthaelt nicht den verifizierten Ergebnis-Commit."

    [pscustomobject]@{
        status = "PASS"
        watcher = (Split-Path $WatcherPath -Leaf)
        cases = @(
            "master_advanced_without_ancestor_dependency",
            "exact_branch_required",
            "exact_task_blob_required",
            "exact_commit_subject_required",
            "dirty_worktree_rejected_before_checkout",
            "remote_sha_mismatch_blocks_state",
            "bounded_push_retry_value_preserved",
            "exact_result_recovered_and_processed"
        )
    } | ConvertTo-Json -Depth 4
}
finally {
    if (Test-Path -LiteralPath $testRoot) {
        $resolvedTestRoot = [IO.Path]::GetFullPath($testRoot)
        $resolvedTempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
        if (-not $resolvedTestRoot.StartsWith($resolvedTempRoot,[StringComparison]::OrdinalIgnoreCase)) {
            throw "Unsicheres Smoke-Test-Aufraeumziel: $resolvedTestRoot"
        }
        Remove-Item -LiteralPath $resolvedTestRoot -Recurse -Force
    }
}
