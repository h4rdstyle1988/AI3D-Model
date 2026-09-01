param(
    [string]$RepoUrl = "https://github.com/h4rdstyle1988/Documents-Controlling-clear.git",
    [string]$BaseBranch = "main",
    [string]$AgentRoot = "D:\Documents-Controlling-Agent",
    [string]$WorkerDir = "",
    [string]$SchedulerTaskName = "Documents-Ruediger-Agent",
    [string]$LiveStatusBranch = "ruediger/live-status",
    [int]$PollSeconds = 30,
    [int]$HeartbeatSeconds = 90,
    [int]$FetchRetryCount = 3,
    [int]$LogRetentionDays = 7
)

$ErrorActionPreference = "Stop"
if (-not $WorkerDir) { $WorkerDir = Join-Path $AgentRoot "worker\Documents-Controlling-clear-worker" }

$logDir = Join-Path $AgentRoot "logs"
$tempDir = Join-Path $AgentRoot "temp"
New-Item -ItemType Directory -Force -Path $logDir,$tempDir | Out-Null
$launcherLog = Join-Path $logDir "documents-agent-launcher.log"

function Write-LauncherLog {
    param([string]$Message,[string]$Level="INFO")
    $line = "{0} [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff zzz"),$Level,$Message
    Add-Content -LiteralPath $launcherLog -Value $line -Encoding UTF8
}

function Resolve-CodexExe {
    $command = Get-Command codex.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $command) { $command = Get-Command codex -ErrorAction SilentlyContinue | Select-Object -First 1 }
    if ($command -and $command.Source -and (Test-Path -LiteralPath $command.Source -PathType Leaf)) {
        return $command.Source
    }

    $localBase = $env:LOCALAPPDATA
    if (-not $localBase -and $env:USERPROFILE) { $localBase = Join-Path $env:USERPROFILE "AppData\Local" }
    if (-not $localBase) { return $null }
    $searchRoot = Join-Path $localBase "OpenAI\Codex\bin"
    if (-not (Test-Path -LiteralPath $searchRoot -PathType Container)) { return $null }
    $candidates = @(Get-ChildItem -LiteralPath $searchRoot -Filter "codex.exe" -File -Recurse -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending)
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath (Join-Path $candidate.DirectoryName "codex-code-mode-host.exe") -PathType Leaf) {
            return $candidate.FullName
        }
    }
    return $null
}

try {
    Write-LauncherLog "START pid=$PID scheduler='$SchedulerTaskName' root='$AgentRoot'"
    $codex = Resolve-CodexExe
    if (-not $codex) { throw "Codex CLI mit Code-Mode-Host nicht gefunden." }
    $codexDir = Split-Path $codex -Parent
    $env:Path = "$codexDir;$env:Path"

    $watcher = Join-Path $AgentRoot "runtime\documents-agent-watch.ps1"
    if (-not (Test-Path -LiteralPath $watcher -PathType Leaf)) { throw "Documents-Watcher fehlt: $watcher" }

    $stdoutPath = Join-Path $tempDir "documents-watcher-$PID.out.log"
    $stderrPath = Join-Path $tempDir "documents-watcher-$PID.err.log"
    Remove-Item -LiteralPath $stdoutPath,$stderrPath -Force -ErrorAction SilentlyContinue

    $watcherArgs = @(
        "-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-File",('"' + $watcher + '"'),
        "-RepoUrl",('"' + $RepoUrl + '"'),"-BaseBranch",('"' + $BaseBranch + '"'),
        "-AgentRoot",('"' + $AgentRoot + '"'),"-WorkerDir",('"' + $WorkerDir + '"'),
        "-SchedulerTaskName",('"' + $SchedulerTaskName + '"'),"-LiveStatusBranch",('"' + $LiveStatusBranch + '"'),
        "-PollSeconds",$PollSeconds,"-HeartbeatSeconds",$HeartbeatSeconds,
        "-FetchRetryCount",$FetchRetryCount,"-LogRetentionDays",$LogRetentionDays
    ) -join ' '

    $process = Start-Process -FilePath "powershell.exe" -ArgumentList $watcherArgs -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru -Wait
    foreach ($path in @($stdoutPath,$stderrPath)) {
        if (Test-Path -LiteralPath $path) {
            $content = Get-Content -LiteralPath $path -Raw -ErrorAction SilentlyContinue
            if ($content -and $content.Trim()) { Add-Content -LiteralPath $launcherLog -Value $content.TrimEnd() -Encoding UTF8 }
            Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        }
    }
    Write-LauncherLog "Watcher beendet; ExitCode=$($process.ExitCode)" $(if ($process.ExitCode -eq 0) { "INFO" } else { "ERROR" })
    exit ([int]$process.ExitCode)
}
catch {
    Write-LauncherLog ("LAUNCHER FEHLER: " + $_.Exception.Message) "ERROR"
    Write-LauncherLog ("STACK: " + $_.ScriptStackTrace) "ERROR"
    exit 1
}
