param(
    [string]$RepoRoot = (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)),
    [string]$OutputPath = (Join-Path $env:LOCALAPPDATA "AI3D-Model\toolchain-preflight.json")
)

$ErrorActionPreference = "Stop"

function Find-Executable {
    param([string[]]$Names, [string[]]$Candidates = @())
    foreach ($name in $Names) {
        $command = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($command) {
            $path = if ($command.Source) { $command.Source } else { $command.Path }
            try {
                if ($path -and (Test-Path -LiteralPath $path -PathType Leaf -ErrorAction Stop)) { return $path }
            }
            catch { }
        }
    }
    foreach ($candidate in $Candidates) {
        try {
            if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf -ErrorAction Stop)) {
                return (Resolve-Path -LiteralPath $candidate -ErrorAction Stop).Path
            }
        }
        catch { }
    }
    return $null
}

function Get-VersionText {
    param([string]$Executable, [string[]]$Arguments)
    if (-not $Executable) { return $null }
    try {
        $text = (& $Executable @Arguments 2>&1 | Select-Object -First 1 | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) { return $null }
        return $text
    }
    catch { return $null }
}

$git = Find-Executable @("git")
$codex = Find-Executable @("codex")
$openscad = Find-Executable @("openscad") @(
    "$env:LOCALAPPDATA\Programs\OpenSCAD\openscad.exe",
    "$env:ProgramFiles\OpenSCAD\openscad.exe",
    "${env:ProgramFiles(x86)}\OpenSCAD\openscad.exe"
)
$python = Find-Executable @("python") @(
    (Join-Path $RepoRoot ".venv-cadquery\Scripts\python.exe"),
    "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
)
if (-not $python) {
    $launcher = Find-Executable @("py")
    if ($launcher) {
        try {
            $candidate = (& $launcher -3 -c "import sys; print(sys.executable)" 2>$null | Select-Object -First 1)
            if ($LASTEXITCODE -eq 0 -and $candidate -and (Test-Path -LiteralPath $candidate -ErrorAction SilentlyContinue)) { $python = $candidate }
        }
        catch { }
    }
}

$cadquery = $false
$meshChecks = @()
if ($python) {
    try {
        $probe = & $python -c "import importlib.util,json; print(json.dumps({n: bool(importlib.util.find_spec(n)) for n in ('cadquery','trimesh','meshio')}))" 2>$null | ConvertFrom-Json
        $cadquery = [bool]$probe.cadquery
        if ($probe.trimesh) { $meshChecks += "Python/trimesh" }
        if ($probe.meshio) { $meshChecks += "Python/meshio" }
    }
    catch { }
}
if ($openscad) { $meshChecks += "OpenSCAD CLI render/export" }

$slicerCandidates = @(
    "$env:LOCALAPPDATA\Programs\AnycubicSlicerNext\AnycubicSlicerNext.exe",
    "$env:ProgramFiles\AnycubicSlicerNext\AnycubicSlicerNext.exe",
    "$env:LOCALAPPDATA\Programs\OrcaSlicer\orca-slicer.exe",
    "$env:ProgramFiles\OrcaSlicer\orca-slicer.exe",
    "$env:ProgramFiles\Prusa3D\PrusaSlicer\prusa-slicer-console.exe"
)
$slicer = Find-Executable @("orca-slicer", "prusa-slicer-console", "AnycubicSlicerNext") $slicerCandidates

$requiredReady = [bool]($git -and $codex)
$optionalMissing = @()
if (-not $openscad) { $optionalMissing += "openscad" }
if (-not $python) { $optionalMissing += "python" }
elseif (-not $cadquery) { $optionalMissing += "cadquery" }
if ($meshChecks.Count -eq 0) { $optionalMissing += "mesh_checker" }
if (-not $slicer) { $optionalMissing += "slicer_cli" }

$result = [ordered]@{
    schema_version = 1
    generated_at = (Get-Date).ToString("o")
    repo_root = (Resolve-Path -LiteralPath $RepoRoot -ErrorAction Stop).Path
    overall = if ($requiredReady) { "PASS" } else { "STOPP" }
    blocking_missing = @($(if (-not $git) { "git" }; if (-not $codex) { "codex" }))
    optional_missing = $optionalMissing
    tools = [ordered]@{
        git = @{ status = $(if ($git) { "PASS" } else { "STOPP" }); path = $git; version = Get-VersionText $git @("--version") }
        codex = @{ status = $(if ($codex) { "PASS" } else { "STOPP" }); path = $codex; version = Get-VersionText $codex @("--version") }
        openscad = @{ status = $(if ($openscad) { "PASS" } else { "OFFEN" }); path = $openscad; version = Get-VersionText $openscad @("--version") }
        python = @{ status = $(if ($python) { "PASS" } else { "OFFEN" }); path = $python; version = Get-VersionText $python @("--version") }
        cadquery = @{ status = $(if ($cadquery) { "PASS" } else { "OFFEN" }); available = $cadquery }
        mesh_check = @{ status = $(if ($meshChecks.Count) { "PASS" } else { "OFFEN" }); methods = $meshChecks }
        slicer_cli = @{ status = $(if ($slicer) { "PASS" } else { "OFFEN" }); path = $slicer; note = "Eine gefundene GUI-EXE gilt erst nach separat erfolgreichem CLI-Smoke-Test als automatisierbar." }
    }
}

$parent = Split-Path -Parent $OutputPath
if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
$result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Write-Output $OutputPath
if (-not $requiredReady) { exit 2 }
