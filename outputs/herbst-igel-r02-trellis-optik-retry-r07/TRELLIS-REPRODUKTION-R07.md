# Herbst-Igel R02 – Trellis-Reproduktion R07

## Identität

- Task: `tasks/TASK-HERBST-IGEL-R02-TRELLIS-OPTIK-RETRY-R07.md`
- Task-Blob-SHA: `fe7cae0d613379fbd22e00b12320f764ee8818ed`
- Produktrevision: `R02`
- technischer Retry: `R07`
- Eingabe-SHA-256: `c1c9a5a094f1db2fd220f3433f83af8dedca780f56a4bf479eb8883432250859`

## Nativer Lauf

- Tool: Trellis Studio native CLI, Image-to-3D, GGUF/Vulkan
- Executable: `C:\Users\h4rds\AppData\Local\trellis-studio\runtime\trellis-cli.exe`
- Executable-SHA-256: `57f49f7746b88b4468009f626bb6f41fc7b7969d894567cb14553e1893457bfc`
- GPU: Vulkan0, AMD Radeon RX 7800 XT, 16.368 MB
- Geometrieauflösung: 512
- Hintergrundfreistellung: BiRefNet
- Textur: deaktiviert
- Seeds: 42 als bytegenauer R06-PLY-Vergleich sowie 7, 123 und 777 als drei technisch unterschiedliche deterministische RNG-Zustände

Das Preprocessing wurde absichtlich nicht zwischen den Seeds verändert. Damit
ist der Kandidatenvergleich kontrolliert und die bessere oder schlechtere
Geometrie nicht durch eine inhaltliche Bildänderung verfälscht. Alle vier
Cutouts haben den identischen SHA-256
`fc24c21784259dba9641c7093b726147117312d724696a5cb67f38c04c01e22e`.

Der reproduzierbare Aufruf ist in
`reproduction-scripts/run_trellis_candidates_r07.py` hinterlegt. Die exakten
Kommandos, Zeitstempel, Returncodes und Hashes stehen zusätzlich in jeder
Kandidatenmappe in `trellis-run-r07.json`; das unveränderte CLI-Protokoll liegt
daneben.

## Unveränderte Rohkandidaten

| Seed | Laufzeit | PLY-Dreiecke | PLY-Byte | PLY-SHA-256 | Status |
|---:|---:|---:|---:|---|---|
| 42 | 239,285 s | 870.466 | 16.557.141 | `85ba18eaed15bdbe631fc49dd571e73882c4055e2c247022e90ad15ed99822c6` | PASS |
| 7 | 332,916 s | 1.943.650 | 36.960.778 | `020b37f90366be26dfeb812495275136a429b599f2d3a10c1460af75a7c6393c` | PASS |
| 123 | 358,247 s | 2.106.066 | 40.048.975 | `3f0e02bb0a23fb8a9530439047ddf2eab7ad105fbeb1b096a48162fc0cce0613` | PASS |
| 777 | 263,730 s | 1.150.778 | 21.594.770 | `29e71d286e6a7ee3c617c2324c7f07c3b02033fbd0eaae834e10eebbb7652e5c` | PASS |

Alle PLY-Dateien bestehen ausschließlich aus Dreiecken und enthalten null
degenerierte Dreiecke. Seed 42 reproduziert die R06-PLY bytegenau. Die
Rohmeshes wurden nicht skaliert, bereinigt, repariert, getrennt oder sonst
konstruktiv verändert. Die sechs Pflichtansichten je Kandidat wurden direkt
aus diesen hashidentischen PLY-Dateien erzeugt.
