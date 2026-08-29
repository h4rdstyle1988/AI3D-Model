param([Parameter(Mandatory=$true)][string]$ManifestPath, [string]$RepoRoot=(Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference="Stop"
$manifest=Get-Content -Raw -LiteralPath $ManifestPath | ConvertFrom-Json
if ($manifest.schema_version -ne "1.0" -or -not $manifest.project -or $null -eq $manifest.references) { throw "Ungueltiges Referenzmanifest." }
$errors=@()
foreach($ref in $manifest.references){
    if(-not $ref.repo_path -or $ref.repo_path -notlike "references/$($manifest.project)/*"){$errors += "Ungueltiger repo_path: $($ref.repo_path)"; continue}
    $full=Join-Path $RepoRoot ($ref.repo_path -replace '/', '\')
    if($ref.available -and -not (Test-Path -LiteralPath $full -PathType Leaf)){$errors += "Als verfuegbar markierte Datei fehlt: $($ref.repo_path)"}
    if($ref.kind -eq "ai-generated" -and $ref.real_reference){$errors += "KI-Bild darf keine reale Referenz sein: $($ref.repo_path)"}
}
if($errors.Count){$errors | ForEach-Object {Write-Error $_}; exit 2}
Write-Output "PASS: $ManifestPath"
