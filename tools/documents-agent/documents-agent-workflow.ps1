Set-StrictMode -Version 2.0

function Invoke-DocumentsGit {
    param(
        [Parameter(Mandatory=$true)][string]$Repository,
        [Parameter(Mandatory=$true)][string[]]$Arguments,
        [switch]$AllowFailure
    )
    $oldPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = @(& git.exe -C $Repository @Arguments 2>&1)
        $exitCode = [int]$LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $oldPreference
    }
    $text = (($output | ForEach-Object { $_.ToString() }) -join "`n").Trim()
    if ($exitCode -ne 0 -and -not $AllowFailure) {
        throw "git $($Arguments -join ' ') failed ($exitCode): $text"
    }
    return [pscustomobject]@{ ExitCode=$exitCode; Output=$text }
}

function Get-CommitTrailerValue {
    param([string]$Message,[string]$Name)
    $match = [regex]::Match($Message,"(?im)^$([regex]::Escape($Name)):\s*(.+?)\s*$")
    if (-not $match.Success) { return "" }
    return $match.Groups[1].Value.Trim()
}

function Get-VerifiedTaskCommit {
    param(
        [Parameter(Mandatory=$true)][string]$Repository,
        [Parameter(Mandatory=$true)][string]$Commit,
        [Parameter(Mandatory=$true)][string]$TaskPath,
        [Parameter(Mandatory=$true)][string]$TaskBlob,
        [ValidateSet("checkpoint","final")][string]$Kind = "checkpoint"
    )
    $resolved = Invoke-DocumentsGit -Repository $Repository -Arguments @("rev-parse","--verify","${Commit}^{commit}") -AllowFailure
    if ($resolved.ExitCode -ne 0 -or -not $resolved.Output) { return $null }
    $sha = ($resolved.Output -split "`n")[0].Trim()
    $messageResult = Invoke-DocumentsGit -Repository $Repository -Arguments @("show","-s","--format=%B",$sha) -AllowFailure
    if ($messageResult.ExitCode -ne 0) { return $null }
    $message = $messageResult.Output
    $trailerPath = Get-CommitTrailerValue -Message $message -Name "Ruediger-Task-Path"
    $trailerBlob = Get-CommitTrailerValue -Message $message -Name "Ruediger-Task-Blob"
    $baseSha = Get-CommitTrailerValue -Message $message -Name "Ruediger-Base-SHA"
    if ($trailerPath -cne $TaskPath -or $trailerBlob -cne $TaskBlob -or $baseSha -notmatch '^[0-9a-fA-F]{40}$') { return $null }

    $baseCommit = Invoke-DocumentsGit -Repository $Repository -Arguments @("cat-file","-e","${baseSha}^{commit}") -AllowFailure
    if ($baseCommit.ExitCode -ne 0) { return $null }
    $ancestor = Invoke-DocumentsGit -Repository $Repository -Arguments @("merge-base","--is-ancestor",$baseSha,$sha) -AllowFailure
    if ($ancestor.ExitCode -ne 0) { return $null }
    $commitTaskBlob = Invoke-DocumentsGit -Repository $Repository -Arguments @("rev-parse","${sha}:$TaskPath") -AllowFailure
    if ($commitTaskBlob.ExitCode -ne 0 -or $commitTaskBlob.Output.Trim() -cne $TaskBlob) { return $null }

    if ($Kind -eq "checkpoint") {
        $numberText = Get-CommitTrailerValue -Message $message -Name "Ruediger-Checkpoint"
        $verified = Get-CommitTrailerValue -Message $message -Name "Ruediger-Checkpoint-Verified"
        $number = 0
        if (-not [int]::TryParse($numberText,[ref]$number) -or $number -lt 1 -or $verified -cne "true") { return $null }
        return [pscustomobject]@{ sha=$sha;kind="checkpoint";number=$number;base_sha=$baseSha;task_path=$TaskPath;task_blob=$TaskBlob }
    }

    $final = Get-CommitTrailerValue -Message $message -Name "Ruediger-Final"
    if ($final -cne "true") { return $null }
    return [pscustomobject]@{ sha=$sha;kind="final";number=$null;base_sha=$baseSha;task_path=$TaskPath;task_blob=$TaskBlob }
}

function Find-VerifiedTaskCommit {
    param(
        [Parameter(Mandatory=$true)][string]$Repository,
        [Parameter(Mandatory=$true)][string]$Ref,
        [Parameter(Mandatory=$true)][string]$TaskPath,
        [Parameter(Mandatory=$true)][string]$TaskBlob,
        [ValidateSet("checkpoint","final")][string]$Kind = "checkpoint"
    )
    $commits = Invoke-DocumentsGit -Repository $Repository -Arguments @("rev-list","--first-parent",$Ref) -AllowFailure
    if ($commits.ExitCode -ne 0) { return $null }
    foreach ($commit in @($commits.Output -split "`n")) {
        if (-not $commit.Trim()) { continue }
        $candidate = Get-VerifiedTaskCommit -Repository $Repository -Commit $commit.Trim() -TaskPath $TaskPath -TaskBlob $TaskBlob -Kind $Kind
        if ($candidate) { return $candidate }
        if ($Kind -eq "final") { break }
    }
    return $null
}

function Resolve-TaskCheckpoint {
    param(
        [Parameter(Mandatory=$true)][string]$Repository,
        [Parameter(Mandatory=$true)][string]$Branch,
        [Parameter(Mandatory=$true)][string]$TaskPath,
        [Parameter(Mandatory=$true)][string]$TaskBlob
    )
    $localRef = "refs/heads/$Branch"
    $remoteRef = "refs/remotes/origin/$Branch"
    $localExists = (Invoke-DocumentsGit -Repository $Repository -Arguments @("show-ref","--verify","--quiet",$localRef) -AllowFailure).ExitCode -eq 0
    $remoteExists = (Invoke-DocumentsGit -Repository $Repository -Arguments @("show-ref","--verify","--quiet",$remoteRef) -AllowFailure).ExitCode -eq 0
    $local = $(if ($localExists) { Find-VerifiedTaskCommit -Repository $Repository -Ref $localRef -TaskPath $TaskPath -TaskBlob $TaskBlob } else { $null })
    $remote = $(if ($remoteExists) { Find-VerifiedTaskCommit -Repository $Repository -Ref $remoteRef -TaskPath $TaskPath -TaskBlob $TaskBlob } else { $null })
    $localHead = $(if ($localExists) { (Invoke-DocumentsGit -Repository $Repository -Arguments @("rev-parse",$localRef) -AllowFailure).Output } else { "" })
    $remoteHead = $(if ($remoteExists) { (Invoke-DocumentsGit -Repository $Repository -Arguments @("rev-parse",$remoteRef) -AllowFailure).Output } else { "" })
    if ($local -and $local.sha -ne $localHead) { $local = $null }
    if ($remote -and $remote.sha -ne $remoteHead) { $remote = $null }
    $dirty = [bool](Invoke-DocumentsGit -Repository $Repository -Arguments @("status","--porcelain") -AllowFailure).Output

    if ($remoteExists -and -not $remote) {
        return [pscustomobject]@{status="REJECTED";source="remote";checkpoint=$null;local_dirty=$dirty;reason="Remote-Branch existiert, enthaelt aber keinen eindeutig zuordenbaren verifizierten Checkpoint."}
    }
    if ($remote) {
        return [pscustomobject]@{status="FOUND";source="remote";checkpoint=$remote;local_dirty=$dirty;reason=$(if ($local -and $local.sha -ne $remote.sha) { "Lokaler und Remote-Checkpoint divergieren; Remote wird bevorzugt." } else { "Verifizierter Remote-Checkpoint." })}
    }
    if ($local) {
        return [pscustomobject]@{status="FOUND";source="local";checkpoint=$local;local_dirty=$dirty;reason="Verifizierter lokaler Checkpoint; vor Resume remote zu sichern."}
    }
    return [pscustomobject]@{status="START_BASE";source="base";checkpoint=$null;local_dirty=$dirty;reason=$(if ($dirty) { "Dirty/unverifizierter Zustand wird nicht als Checkpoint akzeptiert." } else { "Kein Checkpoint vorhanden." })}
}

function Get-CodexRetryDecision {
    param(
        [int]$PreviousFailures,
        [string]$PreviousCheckpointSha = "",
        [string]$CurrentCheckpointSha = "",
        [int]$MaximumFailures = 3
    )
    if ($MaximumFailures -lt 1) { throw "MaximumFailures muss mindestens 1 sein." }
    $newCheckpoint = [bool]$CurrentCheckpointSha -and $CurrentCheckpointSha -ne $PreviousCheckpointSha
    $failures = $(if ($newCheckpoint) { 1 } else { $PreviousFailures + 1 })
    return [pscustomobject]@{
        failures_without_checkpoint=$failures
        new_checkpoint=$newCheckpoint
        blocked=($failures -ge $MaximumFailures)
        checkpoint_sha=$(if ($CurrentCheckpointSha) { $CurrentCheckpointSha } else { $PreviousCheckpointSha })
    }
}

function Test-RemoteBranchSha {
    param(
        [Parameter(Mandatory=$true)][string]$Repository,
        [Parameter(Mandatory=$true)][string]$Branch,
        [Parameter(Mandatory=$true)][string]$ExpectedSha
    )
    $line = Invoke-DocumentsGit -Repository $Repository -Arguments @("ls-remote","--heads","origin","refs/heads/$Branch") -AllowFailure
    if ($line.ExitCode -ne 0 -or -not $line.Output) { return $false }
    return (($line.Output -split '\s+')[0] -ceq $ExpectedSha)
}
