param([string]$RepoRoot=(Split-Path $PSScriptRoot -Parent),[string]$AgentRoot="D:\AI3D-Agent")
$ErrorActionPreference="Stop"
$runtime=Join-Path $AgentRoot "runtime"
if(-not(Test-Path -LiteralPath $AgentRoot -PathType Container)){throw "AgentRoot fehlt: $AgentRoot"}
New-Item -ItemType Directory -Force -Path $runtime|Out-Null
foreach($name in @("ruediger-agent-watch.ps1","cad-toolchain-preflight.ps1")){
 $source=Join-Path $RepoRoot "tools\$name";$target=Join-Path $runtime $name
 if(-not(Test-Path -LiteralPath $source -PathType Leaf)){throw "Quelldatei fehlt: $source"}
 if(Test-Path -LiteralPath $target -PathType Leaf){Copy-Item -LiteralPath $target -Destination "$target.previous" -Force}
 Copy-Item -LiteralPath $source -Destination $target -Force
}
Write-Output "Runtime-Skripte installiert: $runtime"
Write-Output "Ein bereits laufender Watcher muss kontrolliert ueber seinen vorhandenen Scheduler neu gestartet werden."
