param([string]$SourceDir = $PSScriptRoot)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path (Split-Path $SourceDir -Parent) -Parent
$runner = Join-Path $SourceDir 'invoke-known-agent-repair.ps1'
$checks = New-Object System.Collections.Generic.List[object]

function Add-Check {
    param([string]$Name,[bool]$Pass,[string]$Detail)
    $checks.Add([pscustomobject]@{ name=$Name; status=$(if ($Pass) { 'PASS' } else { 'FAIL' }); detail=$Detail })
}

$scripts = @(
    $runner,
    (Join-Path $SourceDir 'request-known-agent-repair.ps1'),
    (Join-Path $SourceDir 'manfred-supervisor.ps1'),
    (Join-Path $SourceDir 'install-manfred-supervisor.ps1')
)
foreach ($script in $scripts) {
    $tokens=$null; $errors=$null
    [void][Management.Automation.Language.Parser]::ParseFile($script,[ref]$tokens,[ref]$errors)
    Add-Check -Name ('parser-' + (Split-Path $script -Leaf)) -Pass ($errors.Count -eq 0) -Detail $(if ($errors.Count) { ($errors | ForEach-Object Message) -join ' | ' } else { 'PowerShell parser PASS' })
}

$runnerText = Get-Content -LiteralPath $runner -Raw
Add-Check -Name 'known-agents-only' -Pass ($runnerText.Contains("AI3D = [pscustomobject]") -and $runnerText.Contains("Documents = [pscustomobject]") -and $runnerText.Contains("if (-not `$knownRepairs.ContainsKey")) -Detail 'only fixed AI3D/Documents identities and allowlisted repair IDs'
Add-Check -Name 'allowed-script-prefixes-only' -Pass ($runnerText.Contains("tools/manfred-supervisor/maintenance/*") -and $runnerText.Contains("tools/documents-agent/*")) -Detail 'repair paths restricted to approved repository prefixes'
Add-Check -Name 'no-command-field' -Pass ($runnerText -notmatch 'request\.(command|arguments|shell)') -Detail 'request schema exposes no command, arguments or shell field'
Add-Check -Name 'blob-and-origin-bound' -Pass ($runnerText.Contains('Skript-Blob ist nicht allowlisted') -and $runnerText.Contains('Unerwartetes Ziel-Origin')) -Detail 'execution requires fixed Git blob and expected worker origin'
Add-Check -Name 'backup-parser-stash' -Pass ($runnerText.Contains('ParseFile($agent.watcher') -and $runnerText.Contains('stash push -u') -and $runnerText.Contains('$audit.backups')) -Detail 'parsercheck, stash and backups precede allowlisted child execution'

$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ('manfred-r04-test-' + [Guid]::NewGuid().ToString('N'))
try {
    $fixtureRepo = Join-Path $tempRoot 'source'
    $fixtureRoot = Join-Path $tempRoot 'manfred'
    New-Item -ItemType Directory -Force -Path (Join-Path $fixtureRepo 'tools\documents-agent'),$fixtureRoot | Out-Null
    Copy-Item -LiteralPath (Join-Path $repoRoot 'tools\documents-agent\hotfix-documents-r02.3-hidden-loop-guard.ps1') -Destination (Join-Path $fixtureRepo 'tools\documents-agent\hotfix-documents-r02.3-hidden-loop-guard.ps1')
    & git.exe -C $fixtureRepo init -q
    & git.exe -C $fixtureRepo config user.name 'MANFRED Test'
    & git.exe -C $fixtureRepo config user.email 'manfred-test@example.invalid'
    & git.exe -C $fixtureRepo remote add origin 'https://github.com/h4rdstyle1988/AI3D-Model.git'
    & git.exe -C $fixtureRepo add .
    & git.exe -C $fixtureRepo commit -q -m 'fixture'
    $commit = (& git.exe -C $fixtureRepo rev-parse HEAD | Out-String).Trim()
    & git.exe -C $fixtureRepo update-ref refs/remotes/origin/master $commit

    $requestPath = Join-Path $tempRoot 'request.json'
    $request = [ordered]@{ schema_version=1; request_id='fixture-valid'; repair_id='documents-r02.3-hidden-loop-guard'; target_agent='Documents'; source_commit=$commit }
    [IO.File]::WriteAllText($requestPath,($request | ConvertTo-Json),(New-Object Text.UTF8Encoding($false)))
    $valid = & $runner -RequestPath $requestPath -Root $fixtureRoot -SourceRepository $fixtureRepo -ValidateOnly
    Add-Check -Name 'allowlisted-fixture-validates' -Pass ($valid.status -eq 'VALIDATED') -Detail $valid.reason

    $request.repair_id = 'not-allowlisted'
    [IO.File]::WriteAllText($requestPath,($request | ConvertTo-Json),(New-Object Text.UTF8Encoding($false)))
    $rejected = & $runner -RequestPath $requestPath -Root $fixtureRoot -SourceRepository $fixtureRepo -ValidateOnly
    Add-Check -Name 'unknown-repair-rejected' -Pass ($rejected.status -eq 'BLOCKED' -and $rejected.reason -match 'nicht erlaubt') -Detail $rejected.reason

    Add-Content -LiteralPath (Join-Path $fixtureRepo 'tools\documents-agent\hotfix-documents-r02.3-hidden-loop-guard.ps1') -Value '# changed blob'
    & git.exe -C $fixtureRepo add .
    & git.exe -C $fixtureRepo commit -q -m 'changed blob'
    $changedCommit = (& git.exe -C $fixtureRepo rev-parse HEAD | Out-String).Trim()
    & git.exe -C $fixtureRepo update-ref refs/remotes/origin/master $changedCommit
    $request.repair_id = 'documents-r02.3-hidden-loop-guard'
    $request.source_commit = $changedCommit
    [IO.File]::WriteAllText($requestPath,($request | ConvertTo-Json),(New-Object Text.UTF8Encoding($false)))
    $changed = & $runner -RequestPath $requestPath -Root $fixtureRoot -SourceRepository $fixtureRepo -ValidateOnly
    Add-Check -Name 'changed-blob-rejected' -Pass ($changed.status -eq 'BLOCKED' -and $changed.reason -match 'nicht allowlisted') -Detail $changed.reason
}
catch {
    Add-Check -Name 'dynamic-fixture' -Pass $false -Detail $_.Exception.Message
}
finally {
    $tempPrefix = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    $full = [IO.Path]::GetFullPath($tempRoot)
    if ($full.StartsWith($tempPrefix,[StringComparison]::OrdinalIgnoreCase) -and (Split-Path $full -Leaf).StartsWith('manfred-r04-test-')) {
        Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$failures = @($checks | Where-Object status -eq 'FAIL')
$result = [ordered]@{ schema_version=1; suite='manfred-maintenance-r01.1'; status=$(if($failures.Count){'FAIL'}else{'PASS'}); checks=@($checks | ForEach-Object { $_ }); failure_count=$failures.Count }
$result | ConvertTo-Json -Depth 6
if ($failures.Count) { exit 1 }
