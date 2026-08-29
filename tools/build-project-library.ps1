param(
    [string]$RepoRoot = (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)),
    [string]$OutputDir = (Join-Path $env:LOCALAPPDATA "AI3D-Model\project-library")
)

$ErrorActionPreference = "Stop"

$manifestPath = Join-Path $RepoRoot "library\projects.json"
if (-not (Test-Path $manifestPath)) {
    throw "Projektbibliothek fehlt: $manifestPath"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$assetDir = Join-Path $OutputDir "assets"
New-Item -ItemType Directory -Force -Path $assetDir | Out-Null

$manifest = Get-Content $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$cards = New-Object System.Collections.Generic.List[string]

foreach ($project in @($manifest.projects)) {
    if ([string]::IsNullOrWhiteSpace([string]$project.name)) { continue }

    $name = [System.Net.WebUtility]::HtmlEncode([string]$project.name)
    $description = [System.Net.WebUtility]::HtmlEncode([string]$project.description)
    $status = [System.Net.WebUtility]::HtmlEncode([string]$project.status)
    $github = [string]$project.github
    $image = [string]$project.image

    $imageHtml = '<div class="noimage">Kein Preview</div>'
    if (-not [string]::IsNullOrWhiteSpace($image)) {
        $sourceImage = Join-Path $RepoRoot ($image -replace '/', '\')
        if (Test-Path $sourceImage) {
            $safeName = ([IO.Path]::GetFileName($image) -replace '[^A-Za-z0-9._-]', '_')
            $targetImage = Join-Path $assetDir $safeName
            Copy-Item -Force $sourceImage $targetImage
            $imageHtml = '<img src="assets/' + [System.Net.WebUtility]::HtmlEncode($safeName) + '" alt="' + $name + '">'
        }
    }

    $linkHtml = ''
    if (-not [string]::IsNullOrWhiteSpace($github)) {
        $encodedLink = [System.Net.WebUtility]::HtmlEncode($github)
        $linkHtml = '<a href="' + $encodedLink + '" target="_blank" rel="noopener">Auf GitHub öffnen</a>'
    }

    $cards.Add(@"
<article class="card">
  <div class="preview">$imageHtml</div>
  <div class="body">
    <h2>$name</h2>
    <p class="status">$status</p>
    <p>$description</p>
    $linkHtml
  </div>
</article>
"@)
}

if ($cards.Count -eq 0) {
    $cards.Add('<div class="empty">Noch keine vollständig archivierten Projekte in der Bibliothek.</div>')
}

$html = @"
<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI3D Projektbibliothek</title>
<style>
body{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#111;color:#eee}header{padding:24px 28px;border-bottom:1px solid #333}h1{margin:0;font-size:28px}main{padding:24px;display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:20px}.card{background:#1b1b1b;border:1px solid #333;border-radius:14px;overflow:hidden}.preview{aspect-ratio:16/10;background:#0d0d0d;display:flex;align-items:center;justify-content:center}.preview img{width:100%;height:100%;object-fit:cover}.noimage,.empty{color:#999}.body{padding:16px}.body h2{margin:0 0 8px}.body p{line-height:1.45}.status{font-size:13px;color:#bbb}.body a{color:#9ecbff;text-decoration:none}.body a:hover{text-decoration:underline}.empty{padding:20px;border:1px dashed #444;border-radius:12px}
</style>
</head>
<body>
<header><h1>AI3D Projektbibliothek</h1></header>
<main>
$($cards -join "`n")
</main>
</body>
</html>
"@

$indexPath = Join-Path $OutputDir "index.html"
Set-Content -Path $indexPath -Value $html -Encoding UTF8
Write-Output $indexPath
