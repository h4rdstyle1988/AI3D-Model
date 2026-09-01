param(
    [string]$AgentRoot = "D:\Documents-Controlling-Agent",
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
if (-not $OutputPath) {
    $OutputPath = Join-Path $AgentRoot "state\documents-agent-preflight.json"
}

$checks = @()

function Add-Check {
    param(
        [string]$Name,
        [bool]$Required,
        [bool]$Passed,
        [string]$Detail
    )
    $script:checks += [pscustomobject]@{
        name = $Name
        required = $Required
        passed = $Passed
        detail = $Detail
    }
}

$psPass = $PSVersionTable.PSVersion -ge [Version]"5.1"
Add-Check -Name "powershell" -Required $true -Passed $psPass -Detail $PSVersionTable.PSVersion.ToString()

$gitCommand = Get-Command git.exe -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $gitCommand) { $gitCommand = Get-Command git -ErrorAction SilentlyContinue | Select-Object -First 1 }
Add-Check -Name "git" -Required $true -Passed ([bool]$gitCommand) -Detail $(if ($gitCommand) { "available" } else { "not found" })

$codexCommand = Get-Command codex.exe -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $codexCommand) { $codexCommand = Get-Command codex -ErrorAction SilentlyContinue | Select-Object -First 1 }
$codexPath = $null
if ($codexCommand -and $codexCommand.Source -and (Test-Path -LiteralPath $codexCommand.Source -PathType Leaf)) {
    $codexPath = $codexCommand.Source
}
if (-not $codexPath) {
    $localBase = $env:LOCALAPPDATA
    if (-not $localBase -and $env:USERPROFILE) { $localBase = Join-Path $env:USERPROFILE "AppData\Local" }
    if ($localBase) {
        $searchRoot = Join-Path $localBase "OpenAI\Codex\bin"
        if (Test-Path -LiteralPath $searchRoot -PathType Container) {
            $candidates = @(Get-ChildItem -LiteralPath $searchRoot -Filter "codex.exe" -File -Recurse -ErrorAction SilentlyContinue |
                Sort-Object LastWriteTime -Descending)
            foreach ($candidate in $candidates) {
                if (Test-Path -LiteralPath (Join-Path $candidate.DirectoryName "codex-code-mode-host.exe") -PathType Leaf) {
                    $codexPath = $candidate.FullName
                    break
                }
            }
        }
    }
}
Add-Check -Name "codex" -Required $true -Passed ([bool]$codexPath) -Detail $(if ($codexPath) { "available" } else { "not found" })

$hostPath = $null
if ($codexPath) {
    $hostPath = Join-Path (Split-Path $codexPath -Parent) "codex-code-mode-host.exe"
}
$hostPass = [bool]($hostPath -and (Test-Path -LiteralPath $hostPath -PathType Leaf))
Add-Check -Name "codex-code-mode-host" -Required $true -Passed $hostPass -Detail $(if ($hostPass) { "available next to Codex" } else { "not found next to Codex" })

$gitName = ""
$gitEmail = ""
if ($gitCommand) {
    $gitName = (& $gitCommand.Source config --get user.name 2>$null | Out-String).Trim()
    $gitEmail = (& $gitCommand.Source config --get user.email 2>$null | Out-String).Trim()
}
Add-Check -Name "git-identity" -Required $true -Passed ([bool]($gitName -and $gitEmail)) -Detail $(if ($gitName -and $gitEmail) { "git user.name/user.email configured" } else { "git user.name/user.email incomplete" })

$pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $pythonCommand) { $pythonCommand = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1 }
Add-Check -Name "python" -Required $false -Passed ([bool]$pythonCommand) -Detail $(if ($pythonCommand) { "available but not required by the watcher" } else { "not required by the watcher" })

Add-Check -Name "cad-toolchain" -Required $false -Passed $true -Detail "not applicable to Documents agent"

$requiredFailures = @($checks | Where-Object { $_.required -and -not $_.passed })
$report = [ordered]@{
    schema_version = 1
    generated_at = (Get-Date).ToString("o")
    profile = "documents-controlling"
    status = $(if ($requiredFailures.Count -eq 0) { "PASS" } else { "STOP" })
    agent_root = $AgentRoot
    checks = @($checks)
    required_failure_count = $requiredFailures.Count
    cad_preflight_used = $false
}

$parent = Split-Path $OutputPath -Parent
if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
[IO.File]::WriteAllText($OutputPath,($report | ConvertTo-Json -Depth 8),(New-Object Text.UTF8Encoding($false)))
$report | ConvertTo-Json -Depth 8

if ($requiredFailures.Count -gt 0) { exit 1 }
exit 0
