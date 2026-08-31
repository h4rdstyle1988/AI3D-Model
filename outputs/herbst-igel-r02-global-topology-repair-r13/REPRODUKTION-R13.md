# Reproduktion R13

Aus dem Repository-Wurzelverzeichnis mit Python 3.12, NumPy und Pillow:

```powershell
python outputs/herbst-igel-r02-global-topology-repair-r13/reproduction-scripts/build_r13.py
python outputs/herbst-igel-r02-global-topology-repair-r13/reproduction-scripts/validate_r13.py
```

`build_r13.py` prüft die autoritativen Hashes, erzeugt den topologisch geschlossenen NON-APPROVED-Prüfstand in Endauflösung, schreibt Vorher-/Nachher-Topologie, Formabweichung und sechs reale Geometrieansichten samt SOLL/IST.

Die zusätzlichen Skripte `build_spherical_r13.py` und `build_voxel_r13.py` dokumentieren die verworfenen technischen Alternativen. Sie sind nicht die Quelle der finalen R13-Prüfdatei.

`validate_r13.py` prüft die vorhandenen Pflichtausgaben und erzeugt das Artefaktmanifest. Der Form-/Optik-FAIL sperrt Fertigungsdateien absichtlich.
