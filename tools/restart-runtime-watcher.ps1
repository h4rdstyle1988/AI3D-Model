param(
    [int]$ParentPid = 0,
    [string]$AgentRoot = "D:\AI3D-Agent",
    [string]$WorkerDir = "",
    [string]$SchedulerTaskName = "AI3D-Ruediger-Agent"
)

$ErrorActionPreference = "Stop"
if (-not $WorkerDir) { $WorkerDir = Join-Path $AgentRoot "worker\AI3D-Model-worker" }

function Resolve-CodexExe {
    $cmd = Get-Command codex -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd -and $cmd.Source -and (Test-Path -LiteralPath $cmd.Source -PathType Leaf)) {
        return $cmd.Source
    }

    $root = Join-Path $env:LOCALAPPDATA "OpenAI\Codex\bin"
    if (-not (Test-Path -LiteralPath $root -PathType Container)) { return $null }

    $candidates = @(Get-ChildItem -LiteralPath $root -Filter "codex.exe" -File -Recurse -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending)

    foreach ($candidate in $candidates) {
        $host = Join-Path $candidate.DirectoryName "codex-code-mode-host.exe"
        if (Test-Path -LiteralPath $host -PathType Leaf) {
            return $candidate.FullName
        }
    }

    if ($candidates.Count -gt 0) { return $candidates[0].FullName }
    return $null
}

if ($ParentPid -gt 0) {
    $ErrorActionPreference = "SilentlyContinue"
    try { Wait-Process -Id $ParentPid -Timeout 60 } catch {}
    Start-Sleep -Seconds 2

    try {
        $task = Get-ScheduledTask -TaskName $SchedulerTaskName -ErrorAction Stop
        Start-ScheduledTask -InputObject $task -ErrorAction Stop
        exit 0
    }
    catch {}

    $self = $MyInvocation.MyCommand.Path
    $args = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$self`" -AgentRoot `"$AgentRoot`" -WorkerDir `"$WorkerDir`" -SchedulerTaskName `"$SchedulerTaskName`""
    Start-Process -FilePath "powershell.exe" -ArgumentList $args -WindowStyle Hidden
    exit 0
}

$codex = Resolve-CodexExe
if (-not $codex) {
    throw "Codex CLI nicht gefunden. Erwartet unter PATH oder '$env:LOCALAPPDATA\OpenAI\Codex\bin\*\codex.exe'."
}

$codexDir = Split-Path $codex -Parent
$env:Path = "$codexDir;$env:Path"
if (-not $env:HOME -and $env:USERPROFILE) { $env:HOME = $env:USERPROFILE }

$watcher = Join-Path $AgentRoot "runtime\ruediger-agent-watch.ps1"
if (-not (Test-Path -LiteralPath $watcher -PathType Leaf)) {
    throw "Ruediger-Watcher fehlt: $watcher"
}

Write-Output "Ruediger-Launcher: Codex='$codex'"
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $watcher -AgentRoot $AgentRoot -WorkerDir $WorkerDir -SchedulerTaskName $SchedulerTaskName
exit $LASTEXITCODE
