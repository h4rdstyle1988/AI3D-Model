param(
    [int]$ParentPid = 0,
    [string]$AgentRoot = "D:\AI3D-Agent",
    [string]$WorkerDir = "",
    [string]$SchedulerTaskName = "AI3D-Ruediger-Agent"
)

$ErrorActionPreference = "Stop"
if (-not $WorkerDir) { $WorkerDir = Join-Path $AgentRoot "worker\AI3D-Model-worker" }

$logDir = Join-Path $AgentRoot "logs"
$tempDir = Join-Path $AgentRoot "temp"
New-Item -ItemType Directory -Force -Path $logDir,$tempDir | Out-Null
$launcherLog = Join-Path $logDir "ruediger-launcher.log"

function Write-LauncherLog {
    param([string]$Message,[string]$Level="INFO")
    $line = "{0} [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff zzz"),$Level,$Message
    Add-Content -LiteralPath $launcherLog -Value $line -Encoding UTF8
}

function Resolve-CodexExe {
    $cmd = Get-Command codex -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd -and $cmd.Source -and (Test-Path -LiteralPath $cmd.Source -PathType Leaf)) {
        return $cmd.Source
    }

    $localBase = $env:LOCALAPPDATA
    if (-not $localBase -and $env:USERPROFILE) {
        $localBase = Join-Path $env:USERPROFILE "AppData\Local"
    }
    if (-not $localBase) { return $null }

    $root = Join-Path $localBase "OpenAI\Codex\bin"
    Write-LauncherLog "Codex-Suchroot: '$root'"
    if (-not (Test-Path -LiteralPath $root -PathType Container)) { return $null }

    $candidates = @(Get-ChildItem -LiteralPath $root -Filter "codex.exe" -File -Recurse -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending)

    foreach ($candidate in $candidates) {
        $codeModeHost = Join-Path $candidate.DirectoryName "codex-code-mode-host.exe"
        if (Test-Path -LiteralPath $codeModeHost -PathType Leaf) {
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
    $launchArgs = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$self`" -AgentRoot `"$AgentRoot`" -WorkerDir `"$WorkerDir`" -SchedulerTaskName `"$SchedulerTaskName`""
    Start-Process -FilePath "powershell.exe" -ArgumentList $launchArgs -WindowStyle Hidden
    exit 0
}

try {
    Write-LauncherLog "START pid=$PID user=$env:USERNAME machine=$env:COMPUTERNAME USERPROFILE='$env:USERPROFILE' LOCALAPPDATA='$env:LOCALAPPDATA'"

    $codex = Resolve-CodexExe
    if (-not $codex) {
        throw "Codex CLI nicht gefunden. Erwartet unter PATH oder AppData\Local\OpenAI\Codex\bin\*\codex.exe."
    }

    $codexDir = Split-Path $codex -Parent
    $codeModeHost = Join-Path $codexDir "codex-code-mode-host.exe"
    Write-LauncherLog "Codex='$codex'; CodeModeHostExists=$(Test-Path -LiteralPath $codeModeHost -PathType Leaf)"

    $env:Path = "$codexDir;$env:Path"
    if (-not $env:HOME -and $env:USERPROFILE) { $env:HOME = $env:USERPROFILE }

    $watcher = Join-Path $AgentRoot "runtime\ruediger-agent-watch.ps1"
    if (-not (Test-Path -LiteralPath $watcher -PathType Leaf)) {
        throw "Ruediger-Watcher fehlt: $watcher"
    }

    Write-LauncherLog "Starte Watcher: '$watcher'"
    $stdoutPath = Join-Path $tempDir "ruediger-watcher-$PID.out.log"
    $stderrPath = Join-Path $tempDir "ruediger-watcher-$PID.err.log"
    Remove-Item -LiteralPath $stdoutPath,$stderrPath -Force -ErrorAction SilentlyContinue

    $watcherArgs = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$watcher`" -AgentRoot `"$AgentRoot`" -WorkerDir `"$WorkerDir`" -SchedulerTaskName `"$SchedulerTaskName`""
    $proc = Start-Process -FilePath "powershell.exe" -ArgumentList $watcherArgs -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru -Wait
    $exitCode = [int]$proc.ExitCode

    foreach ($path in @($stdoutPath,$stderrPath)) {
        if (Test-Path -LiteralPath $path) {
            $text = Get-Content -LiteralPath $path -Raw -ErrorAction SilentlyContinue
            if ($text -and $text.Trim()) {
                Add-Content -LiteralPath $launcherLog -Value $text.TrimEnd() -Encoding UTF8
            }
            Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        }
    }

    Write-LauncherLog "Watcher beendet; ExitCode=$exitCode" $(if($exitCode -eq 0){"INFO"}else{"ERROR"})
    exit $exitCode
}
catch {
    Write-LauncherLog ("LAUNCHER FEHLER: " + $_.Exception.Message) "ERROR"
    Write-LauncherLog ("STACK: " + $_.ScriptStackTrace) "ERROR"
    exit 1
}
