param(
    [string]$AgentRoot = "D:\AI3D-Agent",
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($OutputPath)) { $OutputPath = Join-Path $AgentRoot "state\toolchain-preflight.json" }

function Resolve-Tool {
    param([string]$Name, [string[]]$KnownPaths = @())
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd) { return $cmd.Source }
    foreach ($path in $KnownPaths) { if (Test-Path $path -PathType Leaf) { return $path } }
    return $null
}

$openScad = Resolve-Tool "openscad" @("C:\Program Files\OpenSCAD\openscad.exe", "C:\Program Files (x86)\OpenSCAD\openscad.exe")
$python = Resolve-Tool "python"
if (-not $python) {
    $pythonRegistryRoots = @("HKCU:\Software\Python\PythonCore", "HKLM:\Software\Python\PythonCore", "HKLM:\Software\WOW6432Node\Python\PythonCore")
    foreach ($root in $pythonRegistryRoots) {
        if (-not (Test-Path $root)) { continue }
        foreach ($version in Get-ChildItem $root -ErrorAction SilentlyContinue | Sort-Object PSChildName -Descending) {
            $installPath = (Get-ItemProperty (Join-Path $version.PSPath "InstallPath") -ErrorAction SilentlyContinue).'(default)'
            $candidate = if ($installPath) { Join-Path $installPath "python.exe" } else { $null }
            if ($candidate -and (Test-Path $candidate -PathType Leaf)) { $python = $candidate; break }
        }
        if ($python) { break }
    }
}
$slicerCandidates = @(
    "C:\Program Files\AnycubicSlicerNext\AnycubicSlicerNext.exe",
    "C:\Program Files\Anycubic Slicer Next\AnycubicSlicerNext.exe",
    "C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer-console.exe"
)
$slicer = Resolve-Tool "prusa-slicer-console" $slicerCandidates
$cadQuery = $false
$meshModules = @()
if ($python) {
    & $python -c "import cadquery" 2>$null
    $cadQuery = ($LASTEXITCODE -eq 0)
    foreach ($module in @("trimesh", "numpy", "meshio")) {
        & $python -c "import $module" 2>$null
        if ($LASTEXITCODE -eq 0) { $meshModules += $module }
    }
}

$tools = [ordered]@{
    git = [ordered]@{ required = $true; available = [bool](Resolve-Tool "git"); path = Resolve-Tool "git" }
    codex = [ordered]@{ required = $true; available = [bool](Resolve-Tool "codex"); path = Resolve-Tool "codex" }
    openscad = [ordered]@{ required = $false; available = [bool]$openScad; path = $openScad }
    python = [ordered]@{ required = $false; available = [bool]$python; path = $python }
    cadquery = [ordered]@{ required = $false; available = $cadQuery; python = $python }
    mesh_validation = [ordered]@{ required = $false; available = ($meshModules.Count -gt 0); modules = $meshModules }
    cli_slicer = [ordered]@{ required = $false; available = [bool]$slicer; path = $slicer }
}
$requiredPass = $tools.git.available -and $tools.codex.available
$result = [ordered]@{
    schema_version = 1
    generated_at = (Get-Date).ToString("o")
    agent_root = $AgentRoot
    status = $(if ($requiredPass) { "PASS" } else { "STOPP" })
    policy = "Optionale Werkzeuge blockieren nicht, wenn ein reproduzierbarer Ersatzweg vorhanden ist."
    tools = $tools
}
$parent = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $parent | Out-Null
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Write-Output $OutputPath
if (-not $requiredPass) { exit 2 }
