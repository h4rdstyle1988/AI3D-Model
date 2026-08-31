# Reproduktion R19

Voraussetzung: Python 3.12 mit NumPy und Pillow im Repository-Wurzelverzeichnis.
Die Eingänge werden aus dem dokumentierten R18-Ergebniscommit extrahiert und
vor der Verarbeitung per SHA-256 geprüft.

```powershell
python outputs/herbst-igel-r02-manifold-underside-blend-r19/reproduction-scripts/r19_master.py
python outputs/herbst-igel-r02-manifold-underside-blend-r19/reproduction-scripts/validate_master_r19.py
python outputs/herbst-igel-r02-manifold-underside-blend-r19/reproduction-scripts/r19_gate3.py
python outputs/herbst-igel-r02-manifold-underside-blend-r19/reproduction-scripts/finalize_r19.py
python outputs/herbst-igel-r02-manifold-underside-blend-r19/reproduction-scripts/validate_r19.py
```

Gate 3 bricht ab, wenn die unabhängige Masterprüfung Gate 1 und Gate 2 nicht
freigibt. Die Skripte erzeugen deterministische PLY-/STL-/3MF-/GLB-Dateien,
Prüfberichte, reale Mesh-Renderansichten, Revisionsstand und Status. Reale
Slicer-, Druck-, Klebe-, Support- und Montageprüfungen bleiben separat offen.
