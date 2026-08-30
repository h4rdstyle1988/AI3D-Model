# Herbst-Igel R02 – Reproduktion R08

Aus Repository-Wurzel mit Python 3.12, NumPy und Pillow in dieser Reihenfolge ausführen:

```powershell
python outputs/herbst-igel-r02-masterform-cleanup-r08/reproduction-scripts/inspect_seed42_r08.py
python outputs/herbst-igel-r02-masterform-cleanup-r08/reproduction-scripts/render_coordinate_diagnostics_r08.py
python outputs/herbst-igel-r02-masterform-cleanup-r08/reproduction-scripts/analyze_hidden_body_r08.py
python outputs/herbst-igel-r02-masterform-cleanup-r08/reproduction-scripts/cleanup_masterform_r08.py
python outputs/herbst-igel-r02-masterform-cleanup-r08/reproduction-scripts/render_masterform_r08.py
python outputs/herbst-igel-r02-masterform-cleanup-r08/reproduction-scripts/validate_cleanup_attempt_r08.py
python outputs/herbst-igel-r02-masterform-cleanup-r08/reproduction-scripts/write_artifact_manifest_r08.py
```

Der Ablauf verwendet ausschließlich das unter `source-r07/` archivierte byteidentische Seed-42-PLY sowie die beiden Dateien unter `reference-audit/`. Er startet Trellis nicht erneut und erzeugt wegen des dokumentierten Optik-FAIL keine CAD-, STL-, GLB- oder 3MF-Datei.

Der Cleanup ist deterministisch: Der PLY-Versuch muss SHA-256 `0bd6c4f7362caf5a37e8fd11c835eb3147de432fb5db4bc6af9996f449784ba4` ergeben.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`
