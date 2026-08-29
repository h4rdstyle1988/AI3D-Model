param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$OutputPath = "",
    [switch]$FailOnRequired
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $RepoRoot "work\toolchain-preflight.json"
}

function Resolve-Executable {
    param([string[]]$Names, [string[]]$Candidates = @())
    foreach ($name in $Names) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    foreach ($candidate in $Candidates) {
        $expanded = [Environment]::ExpandEnvironmentVariables($candidate)
        if (Test-Path -LiteralPath $expanded -PathType Leaf) { return (Resolve-Path -LiteralPath $expanded).Path }
    }
    return $null
}

function Tool-Record {
    param([string]$Name, [string]$Path, [bool]$Required, [string]$Note = "", [bool]$ProbeVersion = $true)
    $version = $null
    if ($Path -and $ProbeVersion) {
        try {
            $version = (& $Path --version 2>&1 | Select-Object -First 1 | Out-String).Trim()
        } catch { $version = $null }
    }
    [ordered]@{ name=$Name; required=$Required; available=[bool]$Path; path=$Path; version=$version; note=$Note }
}

$openScadCandidates = @(
    "$env:ProgramFiles\OpenSCAD\openscad.exe",
    "${env:ProgramFiles(x86)}\OpenSCAD\openscad.exe",
    "$env:LOCALAPPDATA\Programs\OpenSCAD\openscad.exe",
    "D:\AI3D-Agent\toolchains\OpenSCAD\openscad.exe"
)
$slicerCandidates = @(
    "D:\Program Files\AnycubicSlicerNext\AnycubicSlicerNext.exe",
    "$env:ProgramFiles\AnycubicSlicerNext\AnycubicSlicerNext.exe",
    "$env:LOCALAPPDATA\Programs\AnycubicSlicerNext\AnycubicSlicerNext.exe"
)
$python = Resolve-Executable @("python.exe", "python3.exe")
if (-not $python) {
    $launcher = Resolve-Executable @("py.exe")
    if ($launcher) {
        $oldPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $candidate = (& $launcher -3 -c "import sys; print(sys.executable)" 2>$null | Select-Object -First 1)
        $ErrorActionPreference = $oldPreference
        if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $candidate)) { $python = $candidate }
    }
}

$tools = @(
    (Tool-Record "git" (Resolve-Executable @("git.exe")) $true),
    (Tool-Record "codex" (Resolve-Executable @("codex.exe")) $true),
    (Tool-Record "openscad" (Resolve-Executable @("openscad.exe") $openScadCandidates) $false),
    (Tool-Record "python" $python $false),
    (Tool-Record "anycubic_slicer_next" (Resolve-Executable @("AnycubicSlicerNext.exe") $slicerCandidates) $false "GUI presence does not prove a supported CLI" $false)
)

$cadquery = [ordered]@{ name="cadquery"; required=$false; available=$false; python=$python; version=$null; note="isolated environment expected under D:\AI3D-Agent\toolchains\cadquery-venv" }
if ($python) {
    try {
        $cq = (& $python -c "import cadquery; print(getattr(cadquery, '__version__', 'unknown'))" 2>$null | Select-Object -First 1)
        if ($LASTEXITCODE -eq 0) { $cadquery.available=$true; $cadquery.version=$cq }
    } catch {}
}

$meshPaths = @()
foreach ($relative in @("work\validate_anycubic_roundtrip.py", "work\validate_benchmark_b_candidate.py")) {
    $full = Join-Path $RepoRoot $relative
    if (Test-Path -LiteralPath $full) { $meshPaths += $relative.Replace('\','/') }
}
$requiredMissing = @($tools | Where-Object { $_.required -and -not $_.available } | ForEach-Object { $_.name })
$result = [ordered]@{
    schema_version="1.0"; generated_at=(Get-Date).ToString("o"); repo_root=(Resolve-Path $RepoRoot).Path
    status=if ($requiredMissing.Count) { "STOPP" } else { "PASS" }
    required_missing=$requiredMissing; tools=$tools; cadquery=$cadquery
    mesh_validation=[ordered]@{ available=[bool]($meshPaths.Count -and $python); repo_paths=$meshPaths; note=if($python){"Python available"}else{"Scripts present, but no Python runtime"} }
}
$parent = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $parent | Out-Null
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Write-Output (Resolve-Path -LiteralPath $OutputPath).Path
if ($FailOnRequired -and $requiredMissing.Count) { exit 2 }
