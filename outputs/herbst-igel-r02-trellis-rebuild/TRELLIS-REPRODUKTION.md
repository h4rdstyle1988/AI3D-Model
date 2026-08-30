# Herbst-Igel R02 – Trellis-Reproduktionsnachweis

## Identität

- Task: `tasks/TASK-HERBST-IGEL-R02-TRELLIS-REBUILD.md`
- Revision: `R02`
- Task-Blob-SHA: `d34558dab04d099d04ed9242dd6399038b21e464`
- Status dieses Laufs: `STOPP` am Optik-Gate

## Verwendete Eingabe

Tatsächliche Trellis-Eingabe war ausschließlich die dekodierte Datei
`tasks/TASK-HERBST-IGEL-R01-REF-CLEAN.jpg.b64`.

- SHA-256 dekodiert: `f3017009739284e1bfd6e8502e9d9258eb74dbf52074c425a73ff41fc8bac328`
- Erwarteter SHA-256: `f3017009739284e1bfd6e8502e9d9258eb74dbf52074c425a73ff41fc8bac328`
- Hashprüfung: `PASS`
- Abmessungen: `320 x 320 px`
- Strikter JPEG-Decode: `FAIL`, `OSError: broken data stream when reading image file`
- Letzte nicht uniforme Bildzeile: `y=128`; danach 191 Zeilen ohne verwertbare Bildinformation

Die Trennlinienreferenz wurde separat dekodiert und nur für den SOLL-Vergleich
verwendet. Ihr dekodierter SHA-256
`b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4`
stimmt exakt.

## Tatsächlich ausgeführtes Trellis-Tool

- Tool: native Trellis-Studio CLI, image-to-3D, GGUF/Vulkan
- Executable: `C:\Users\h4rds\AppData\Local\trellis-studio\runtime\trellis-cli.exe`
- Executable SHA-256: `57f49f7746b88b4468009f626bb6f41fc7b7969d894567cb14553e1893457bfc`
- Modelle: `C:\Users\h4rds\AppData\Local\trellis-studio\models`
- Gerät laut Laufprotokoll: Vulkan0, AMD Radeon RX 7800 XT, 16368 MB
- Seed: `42`
- Geometrieauflösung: `512`
- Hintergrundfreistellung: `BiRefNet`
- Ausgabe: Geometrie ohne Textur

## Reproduktionsweg

Aus dem Repository-Stamm in PowerShell:

```powershell
$work = "work\herbst-igel-r02-trellis-rebuild\references"
$raw = "outputs\herbst-igel-r02-trellis-rebuild\trellis-raw"
New-Item -ItemType Directory -Path $work, $raw -Force | Out-Null

$b64 = Get-Content -LiteralPath "tasks\TASK-HERBST-IGEL-R01-REF-CLEAN.jpg.b64" -Raw
$bytes = [Convert]::FromBase64String(($b64 -replace '\s', ''))
[IO.File]::WriteAllBytes("$work\ref-clean.jpg", $bytes)

$exe = "C:\Users\h4rds\AppData\Local\trellis-studio\runtime\trellis-cli.exe"
$models = "C:\Users\h4rds\AppData\Local\trellis-studio\models"

& $exe `
  --image "$work\ref-clean.jpg" `
  --output "$raw\herbst-igel-r02-trellis-raw.glb" `
  --models $models `
  --gpu 0 `
  --seed 42 `
  --res 512 `
  --birefnet `
  --no-texture `
  --require-gpu
```

Die CLI erzeugte zusätzlich zum GLB automatisch die PLY-Rohgeometrie.

Ein erster Lauf mit den optionalen Schaltern `--xatlas --band 1 --voxply
--dump-slat` endete nach der Sparse-Structure-Stufe mit Windows-Status
`0xC0000409`. Der technisch reduzierte Retry ohne diese optionalen Schalter
lief erfolgreich bis zum Rohmesh-Export. Beide Protokolle liegen unverändert
im Ordner `trellis-raw`.

## Erzeugte Rohgeometrie

- `trellis-raw/herbst-igel-r02-trellis-raw.glb`
  - 21.706.780 Bytes
  - SHA-256 `e05453958feac7f828d6b6c25d0a3d409aa9df2d2654966bcd9dcbe971d946be`
- `trellis-raw/herbst-igel-r02-trellis-raw.ply`
  - 22.923.298 Bytes
  - SHA-256 `a9c843d1478d9118971db15a870a35549ecd1cf1dd54cb57fd9cd1344c6ca87e`
  - 591.659 Vertices
  - 1.217.170 Dreiecke
  - keine degenerierten Dreiecke in der Rohmessung
  - normalisierte Extents: `0.999968 x 0.999970 x 0.181586`

Die Rohgeometrie wurde nicht bereinigt, skaliert, geteilt oder konstruktiv
weiterverarbeitet, weil sie das vorgeschaltete Optik-Gate eindeutig verfehlt.

