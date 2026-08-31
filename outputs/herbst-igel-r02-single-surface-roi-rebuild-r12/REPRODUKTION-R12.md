# Reproduktion R12

Aus dem Repository-Wurzelverzeichnis mit Python 3.12, NumPy und Pillow:

```powershell
python outputs/herbst-igel-r02-single-surface-roi-rebuild-r12/reproduction-scripts/analyze_r11_roi_r12.py
python outputs/herbst-igel-r02-single-surface-roi-rebuild-r12/reproduction-scripts/render_topology_blocker_r12.py
python outputs/herbst-igel-r02-single-surface-roi-rebuild-r12/reproduction-scripts/validate_r12.py
python outputs/herbst-igel-r02-single-surface-roi-rebuild-r12/reproduction-scripts/write_artifact_manifest_r12.py
```

Der erste Lauf rekonstruiert die freigegebene R11-ROI aus dem unveränderlichen R11-Code-Blob, zählt die Kanteninzidenzen der Seed-42-Quelle und trennt Defekte, die von der ROI berührt werden, von Defekten, deren sämtliche inzidenten Flächen außerhalb der ROI liegen.

Die Diagnosebilder markieren ausschließlich die unveränderlichen Außen-ROI-Defektkanten rot. Sie sind keine Optik-Gate-Renders. Die verbindliche Reihenfolge untersagt das Optik-Gate nach dem fehlgeschlagenen Mesh-Gate.
