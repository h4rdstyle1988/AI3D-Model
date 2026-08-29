param(
 [string]$RepoUrl="https://github.com/h4rdstyle1988/AI3D-Model.git",[string]$AgentRoot="D:\AI3D-Agent",
 [string]$WorkerDir="",[int]$PollSeconds=60,[int]$HeartbeatSeconds=90,[int]$LogRetentionDays=7,
 [switch]$DiagnosticOnly,[switch]$SelectionTestOnly)
$ErrorActionPreference="Stop"
if($PollSeconds-lt 1){throw "PollSeconds muss mindestens 1 sein."}
if($HeartbeatSeconds-lt 60-or$HeartbeatSeconds-gt 120){throw "HeartbeatSeconds muss zwischen 60 und 120 liegen."}
if(-not $WorkerDir){$WorkerDir=Join-Path $AgentRoot "worker\AI3D-Model-worker"}
if(-not(Test-Path -LiteralPath $AgentRoot -PathType Container)){throw "AgentRoot fehlt: $AgentRoot"}
$stateDir=Join-Path $AgentRoot "state";$stateFile=Join-Path $stateDir "ruediger-task-state.json"
$logDir=Join-Path $AgentRoot "logs";$runtimeDir=Join-Path $AgentRoot "runtime";$tempDir=Join-Path $AgentRoot "temp"
New-Item -ItemType Directory -Force -Path $stateDir,$logDir,$runtimeDir,$tempDir,(Join-Path $AgentRoot "toolchain")|Out-Null
$logFile=Join-Path $logDir ("ruediger-agent-watch-{0}.log"-f(Get-Date -Format "yyyy-MM-dd"))
function Write-Log([string]$Message,[string]$Level="INFO"){$line="{0} [{1}] {2}"-f(Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff zzz"),$Level,$Message;Add-Content -LiteralPath $script:logFile -Value $line -Encoding UTF8;Write-Host $line}
function Remove-ExpiredLogs{$cutoff=(Get-Date).AddDays(-$LogRetentionDays);Get-ChildItem -LiteralPath $logDir -File -Filter "ruediger-agent-watch-*.log" -ErrorAction SilentlyContinue|Where-Object{$_.LastWriteTime-lt$cutoff}|Remove-Item -Force -ErrorAction SilentlyContinue}
function Invoke-GitSafe{param([Parameter(ValueFromRemainingArguments=$true)][string[]]$GitArgs);& git.exe @GitArgs;if($LASTEXITCODE-ne 0){throw "git failed: git $($GitArgs-join ' ')"}}
function Read-State{
 if(-not(Test-Path -LiteralPath $stateFile)){return [pscustomobject]@{schema_version=2;processed=@();failures=@()}}
 try{$s=Get-Content -LiteralPath $stateFile -Raw|ConvertFrom-Json;if($s.schema_version-ne 2){throw "Schema-Version"};$s.processed=@($s.processed);$s.failures=@($s.failures);return $s}
 catch{throw "Task-Zustand unlesbar; kein Ueberschreiben: $($_.Exception.Message)"}
}
function Write-State($State){$tmp="$stateFile.tmp";$State|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $tmp -Encoding UTF8;Move-Item -LiteralPath $tmp -Destination $stateFile -Force}
function Remote-Text([string]$Path){$v=(& git -C $WorkerDir show "origin/master:$Path" 2>$null|Out-String);if($LASTEXITCODE-ne 0){throw "Remote-Datei fehlt: $Path"};$v}
function Select-Task($State){
 $done=@($State.processed|ForEach-Object{$_.key});$active=(Remote-Text "tasks/CURRENT_TASK.txt").Trim();$items=@()
 if($active-and$active-ne"NONE"){$items+=[pscustomobject]@{path=$active;source="CURRENT_TASK"}}
 foreach($line in((Remote-Text "tasks/TASK_QUEUE.txt")-split"`r?`n")){$p=$line.Trim();if($p-and-not$p.StartsWith("#")){$items+=[pscustomobject]@{path=$p;source="TASK_QUEUE"}}}
 foreach($i in $items){
  if(-not$i.path.StartsWith("tasks/")-or$i.path.Contains("..")){throw "Ungueltiger Task-Pfad: $($i.path)"}
  $blob=(& git -C $WorkerDir rev-parse "origin/master:$($i.path)" 2>$null|Out-String).Trim();if($LASTEXITCODE-ne 0-or-not$blob){throw "Task fehlt: $($i.path)"}
  $key="$($i.path)|$blob";if($done-notcontains$key){return [pscustomobject]@{path=$i.path;blob=$blob;key=$key;source=$i.source}}
 }
 return $null
}
function Preflight{$p=Join-Path $WorkerDir "tools\cad-toolchain-preflight.ps1";if(-not(Test-Path $p)){throw "Preflight fehlt"};& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $p -AgentRoot $AgentRoot;if($LASTEXITCODE-ne 0){throw "Preflight STOPP"}}
function Run-Codex([string]$Exe,[string]$Prompt){
 $pf=Join-Path $tempDir "codex-prompt-$PID.txt";[IO.File]::WriteAllText($pf,$Prompt,(New-Object Text.UTF8Encoding($false)))
 try{$psi=New-Object Diagnostics.ProcessStartInfo;$psi.FileName="cmd.exe";$psi.Arguments="/d /s /c `"`"$Exe`" --sandbox workspace-write --ask-for-approval never exec < `"$pf`"`"";$psi.UseShellExecute=$false;$psi.CreateNoWindow=$true
  $proc=New-Object Diagnostics.Process;$proc.StartInfo=$psi;if(-not$proc.Start()){throw "Codex-Start fehlgeschlagen"};$heartbeat=(Get-Date).AddSeconds($HeartbeatSeconds)
  while(-not$proc.HasExited){if((Get-Date)-ge$heartbeat){Write-Log "ARBEITET: Codex pid=$($proc.Id)";$heartbeat=(Get-Date).AddSeconds($HeartbeatSeconds)};Start-Sleep 5};$proc.WaitForExit();return [int]$proc.ExitCode
 }finally{Remove-Item -LiteralPath $pf -Force -ErrorAction SilentlyContinue}
}
function Verify-Remote([string]$Branch){$local=(& git -C $WorkerDir rev-parse HEAD|Out-String).Trim();$line=(& git -C $WorkerDir ls-remote --heads origin "refs/heads/$Branch"|Out-String).Trim();if($LASTEXITCODE-ne 0-or-not$line){throw "Remote-Branch fehlt"};$remote=($line-split'\s+')[0];if($remote-ne$local){throw "Remote-SHA ungleich"};Write-Log "Remote-Verifikation PASS: $Branch @ $local";return $local}
function Compact{Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"checkout","--detach","origin/master");Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"sparse-checkout","init","--cone");Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"sparse-checkout","set","tasks","tools","library")}
if(-not(Get-Command git -ErrorAction SilentlyContinue)){throw "Git fehlt"};$cc=Get-Command codex -ErrorAction SilentlyContinue;if(-not$cc){throw "Codex fehlt"};$CodexExe=$cc.Source
if(-not(Test-Path (Join-Path(Split-Path $CodexExe -Parent)"codex-code-mode-host.exe"))){throw "Codex Code-Mode-Host fehlt"}
if(-not(Test-Path(Join-Path $WorkerDir ".git"))){Invoke-GitSafe -GitArgs @("clone",$RepoUrl,$WorkerDir)}
if($DiagnosticOnly){Preflight;Write-Log "DIAGNOSTIC PASS";exit 0}
Remove-ExpiredLogs
Write-Log "START AgentRoot='$AgentRoot' WorkerDir='$WorkerDir' Heartbeat=$HeartbeatSeconds"
while($true){$task=$null;try{
 if(-not$SelectionTestOnly){Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"fetch","origin","master")};$state=Read-State;$task=Select-Task $state
 if($SelectionTestOnly){if($task){$task|ConvertTo-Json -Compress}else{'{"selection":null}'};exit 0}
 if(-not$task){Compact;Write-Log "WARTET: kein unverarbeiteter freigegebener Auftrag";Start-Sleep $PollSeconds;continue}
 & git.exe -C $WorkerDir sparse-checkout disable 2>$null;Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"checkout","--detach","origin/master");Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"reset","--hard","origin/master");Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"clean","-fd")
 $stem=[IO.Path]::GetFileNameWithoutExtension($task.path).ToLowerInvariant()-replace'[^a-z0-9-]+','-';$branch="ruediger/$stem-$($task.blob.Substring(0,8))";& git.exe -C $WorkerDir branch -D $branch 2>$null;Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"checkout","-b",$branch,"origin/master");Preflight
 $prompt="Lies zuerst AGENTS.md und danach die aktive Auftragsdatei '$($task.path)' vollstaendig.`r`nFuehre genau diesen Auftrag aus. Keine neuen Funktionen oder stillen Annahmen. Schuetze bestaetigte Geometrie und Nutzermasse. Bei offenen konstruktiven Punkten STOPP/OFFEN dokumentieren. Erzeuge geforderte CAD-/STL-/Pruef-/Revisionsdateien. Keine finale Nutzerfreigabe. Nur taskbezogene Dateien aendern."
 Push-Location $WorkerDir;try{$code=Run-Codex $CodexExe $prompt}finally{Pop-Location};if($code-ne 0){throw "Codex Exit $code"};if(-not((& git -C $WorkerDir status --porcelain|Out-String).Trim())){throw "Keine Ergebnisdateien"}
 Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"add","-A");Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"commit","-m","Ruediger result for $($task.path)");Invoke-GitSafe -GitArgs @("-C",$WorkerDir,"push","-u","origin",$branch,"--force-with-lease");$sha=Verify-Remote $branch
 $state.processed+= [pscustomobject]@{key=$task.key;task=$task.path;blob=$task.blob;source=$task.source;branch=$branch;remote_commit=$sha;verified_at=(Get-Date).ToString("o")};$state.failures=@($state.failures|Where-Object{$_.key-ne$task.key});Write-State $state;Write-Log "FERTIG: naechste Queue-Task wird automatisch bewertet";Compact
 }catch{try{$fs=Read-State;if($task){$fs.failures=@($fs.failures|Where-Object{$_.key-ne$task.key});$fs.failures+=[pscustomobject]@{key=$task.key;task=$task.path;occurred_at=(Get-Date).ToString("o");reason=$_.Exception.Message};Write-State $fs}}catch{Write-Log "Fehlerstatus nicht schreibbar: $($_.Exception.Message)" "ERROR"};Write-Log "FEHLER: $($_.Exception.Message)" "WARN"};Start-Sleep $PollSeconds
}
