# Reproduktion R11

Aus dem Repository-Wurzelverzeichnis mit Python 3.12, NumPy und Pillow:

```powershell
python outputs/herbst-igel-r02-deterministic-body-rebuild-r11/reproduction-scripts/reconstruct_deterministic_body_r11.py
python outputs/herbst-igel-r02-deterministic-body-rebuild-r11/reproduction-scripts/render_optik_gate_r11.py
python outputs/herbst-igel-r02-deterministic-body-rebuild-r11/reproduction-scripts/validate_r11.py
python outputs/herbst-igel-r02-deterministic-body-rebuild-r11/reproduction-scripts/write_artifact_manifest_r11.py
```

Das Rebuild-Skript erzwingt vor jeder Geometrieerzeugung die drei autoritativen
SHA-256-Gates. Es lädt ausschließlich die Seed-42-Rohform als Formquelle.
Numerische PLY-, Masken-, SDF- und Marching-Tetrahedra-Grundfunktionen werden
reproduzierbar über die unveränderliche Git-Blob-ID
`cbbc1daf11331fae989441968339d21153d9f97b` geladen; R10-Kandidatengeometrie
wird nicht gelesen.

Der Ergebnisstand ist `NON-APPROVED` und endet zwingend vor CAD/FDM/STL.
