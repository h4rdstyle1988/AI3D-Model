# Herbst-Igel R02 – Trellis-Reproduktion R06

## Identität

- Task: `tasks/TASK-HERBST-IGEL-R02-TRELLIS-RETRY-REF-CLEAN-R06.md`
- Task-Blob-SHA: `4816056a56ebb7dd24e4150c260a11cc93257c9a`
- Produktrevision: `R02`
- technischer Retry: `R06`
- Trellis-Eingabe-SHA-256:
  `c1c9a5a094f1db2fd220f3433f83af8dedca780f56a4bf479eb8883432250859`

## Nativer Lauf

- Tool: Trellis Studio native CLI, Image-to-3D, GGUF/Vulkan
- Executable:
  `C:\Users\h4rds\AppData\Local\trellis-studio\runtime\trellis-cli.exe`
- Executable SHA-256:
  `57f49f7746b88b4468009f626bb6f41fc7b7969d894567cb14553e1893457bfc`
- Modelle: `C:\Users\h4rds\AppData\Local\trellis-studio\models`
- GPU-Argument: `0`
- tatsächlich protokolliertes Gerät: AMD Radeon RX 7800 XT, Vulkan0,
  16.368 MB
- Seed: `42`
- Geometrieauflösung: `512`
- Hintergrundfreistellung: BiRefNet
- Textur: deaktiviert
- Laufzeit: 245,499 s
- Returncode: `0`

Der vollständige Aufruf, Zeitstempel, Hashes und das unveränderte CLI-Protokoll
liegen in `trellis-raw/trellis-run-r06.json` und
`trellis-raw/trellis-cli-seed42-res512-r06.log`.

## Unverändertes Rohmesh

| Datei | Byte | SHA-256 |
|---|---:|---|
| `trellis-raw/herbst-igel-r02-trellis-raw-r06.glb` | 15.687.328 | `81d5bea62c13cd2c4d85b9a803a1dd7aa9c951262f35a8ea3a421baecb38a13d` |
| `trellis-raw/herbst-igel-r02-trellis-raw-r06.ply` | 16.557.141 | `85ba18eaed15bdbe631fc49dd571e73882c4055e2c247022e90ad15ed99822c6` |

Rohmessung der PLY-Datei:

- 436.742 Vertices
- 870.466 Dreiecke
- alle Flächen dreieckig
- 0 degenerierte Dreiecke
- normalisierte Extents:
  `0,628445506 × 0,620399445 × 0,500158638`

Das Rohmesh wurde weder skaliert noch bereinigt, getrennt, repariert oder
konstruktiv verändert. Die sechs geforderten Ansichten wurden direkt aus
dieser hashidentischen PLY-Datei erzeugt. Der Renderer ändert nur die
Darstellung, nicht die Geometrie.

