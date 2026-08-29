param([string]$AgentRoot="D:\AI3D-Agent", [switch]$Execute)
$ErrorActionPreference="Stop"
$commands=@(
    "winget install --exact --id OpenSCAD.OpenSCAD --source winget --scope user --accept-source-agreements --accept-package-agreements",
    "winget install --exact --id Python.Python.3.11 --source winget --scope user --accept-source-agreements --accept-package-agreements",
    "py -3.11 -m venv `"$AgentRoot\toolchains\cadquery-venv`"",
    "`"$AgentRoot\toolchains\cadquery-venv\Scripts\python.exe`" -m pip install --upgrade pip cadquery"
)
if(-not $Execute){$commands; Write-Output "DRY-RUN: Mit -Execute ausdrücklich ausführen."; exit 0}
$winget=Get-Command winget.exe -ErrorAction SilentlyContinue
if(-not $winget){throw "winget fehlt; keine automatische Installation möglich. App Installer über den unterstützten Microsoft-Weg bereitstellen."}
New-Item -ItemType Directory -Force -Path (Join-Path $AgentRoot "toolchains") | Out-Null
& $winget.Source install --exact --id OpenSCAD.OpenSCAD --source winget --scope user --accept-source-agreements --accept-package-agreements
if($LASTEXITCODE -ne 0){throw "OpenSCAD-Installation fehlgeschlagen."}
& $winget.Source install --exact --id Python.Python.3.11 --source winget --scope user --accept-source-agreements --accept-package-agreements
if($LASTEXITCODE -ne 0){throw "Python-Installation fehlgeschlagen."}
$py=Get-Command py.exe -ErrorAction Stop
& $py.Source -3.11 -m venv (Join-Path $AgentRoot "toolchains\cadquery-venv")
if($LASTEXITCODE -ne 0){throw "venv-Erzeugung fehlgeschlagen."}
$venvPython=Join-Path $AgentRoot "toolchains\cadquery-venv\Scripts\python.exe"
& $venvPython -m pip install --upgrade pip cadquery
if($LASTEXITCODE -ne 0){throw "CadQuery-Installation fehlgeschlagen."}
