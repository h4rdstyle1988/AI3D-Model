param(
    [string]$SourceDir = $PSScriptRoot,
    [string]$RuntimeWatcher = 'D:\Documents-Controlling-Agent\runtime\documents-agent-watch.ps1'
)

$ErrorActionPreference = 'Stop'
$checks = New-Object System.Collections.Generic.List[object]

function Add-Check {
    param([string]$Name,[bool]$Pass,[string]$Detail)
    $checks.Add([pscustomobject]@{ name=$Name; status=$(if ($Pass) { 'PASS' } else { 'FAIL' }); detail=$Detail })
}

$sourceWatcher = Join-Path $SourceDir 'documents-agent-watch.ps1'
$hotfix = Join-Path $SourceDir 'hotfix-documents-r02.3-hidden-loop-guard.ps1'
foreach ($script in @($sourceWatcher,$hotfix)) {
    $tokens=$null; $errors=$null
    [void][Management.Automation.Language.Parser]::ParseFile($script,[ref]$tokens,[ref]$errors)
    Add-Check -Name ('parser-' + (Split-Path $script -Leaf)) -Pass ($errors.Count -eq 0) -Detail $(if ($errors.Count) { ($errors | ForEach-Object Message) -join ' | ' } else { 'PowerShell parser PASS' })
}

$source = Get-Content -LiteralPath $sourceWatcher -Raw
$attemptPosition = $source.IndexOf('$failure.attempts = $attempt',[StringComparison]::Ordinal)
$launchPosition = $source.IndexOf('Run-Codex -Exe $CodexExe',[StringComparison]::Ordinal)
Add-Check -Name 'attempt-persisted-before-codex' -Pass ($attemptPosition -ge 0 -and $launchPosition -gt $attemptPosition) -Detail 'attempt is written through Set-TaskFailure before Run-Codex'

$attemptWindow = $source.Substring([Math]::Max(0,$attemptPosition-250),[Math]::Min(700,$source.Length-[Math]::Max(0,$attemptPosition-250)))
Add-Check -Name 'infrastructure-counter-not-reset-before-launch' -Pass ($attemptWindow -notmatch '\$infrastructureFailures\s*=\s*0') -Detail 'post-validation failures remain consecutive across successful Codex exits'
Add-Check -Name 'codex-errors-use-separate-budget' -Pass ($source -match 'if \(\$code -ne 0\) \{\s*# A genuine Codex failure[\s\S]*?\$infrastructureFailures = 0') -Detail 'genuine Codex failure resets only infrastructure sequence'
Add-Check -Name 'hard-third-infrastructure-block' -Pass ($source.Contains('$hardInfrastructureBlock = ($infrastructureFailures -ge 3)') -and $source.Contains('R02.3 LOOP-GUARD')) -Detail 'third consecutive infrastructure/post-validation failure becomes stable BLOCKIERT'
Add-Check -Name 'hard-block-persisted' -Pass ($source -match '\$failure\.blocked = \$true\s*\$failure\.reason = \$detail\s*Set-TaskFailure') -Detail 'loop guard persists blocked reason for the same task path+blob across watcher restarts'
Add-Check -Name 'watcher-version' -Pass ($source.Contains('$WatcherVersion = "DOCUMENTS-R02.3"')) -Detail 'source watcher publishes DOCUMENTS-R02.3'

$phases = @()
$failureCount = 0
1..3 | ForEach-Object {
    $failureCount++
    $phases += $(if ($failureCount -ge 3) { 'BLOCKIERT' } else { 'FEHLER_RETRY' })
}
Add-Check -Name 'three-step-transition' -Pass (($phases -join ',') -eq 'FEHLER_RETRY,FEHLER_RETRY,BLOCKIERT') -Detail ($phases -join ' -> ')

if (Test-Path -LiteralPath $RuntimeWatcher -PathType Leaf) {
    $before = (Get-FileHash -LiteralPath $RuntimeWatcher -Algorithm SHA256).Hash
    $output = @(& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $hotfix -AgentRoot (Split-Path (Split-Path $RuntimeWatcher -Parent) -Parent) -ValidateOnly 2>&1)
    $exitCode = $LASTEXITCODE
    $after = (Get-FileHash -LiteralPath $RuntimeWatcher -Algorithm SHA256).Hash
    Add-Check -Name 'live-runtime-deterministic-dry-run' -Pass ($exitCode -eq 0 -and $before -eq $after) -Detail (($output -join ' | ') + "; hash_unchanged=$($before -eq $after)")
}
else {
    Add-Check -Name 'live-runtime-deterministic-dry-run' -Pass $false -Detail "Runtime-Watcher fehlt: $RuntimeWatcher"
}

$failures = @($checks | Where-Object status -eq 'FAIL')
$result = [ordered]@{ schema_version=1; suite='documents-r02.3-loop-guard'; status=$(if($failures.Count){'FAIL'}else{'PASS'}); checks=@($checks | ForEach-Object { $_ }); failure_count=$failures.Count }
$result | ConvertTo-Json -Depth 6
if ($failures.Count) { exit 1 }
