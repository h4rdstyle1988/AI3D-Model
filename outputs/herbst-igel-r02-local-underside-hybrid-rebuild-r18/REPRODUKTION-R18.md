# Reproduktion R18

Voraussetzung: Python 3 mit NumPy und Pillow im Repository-Wurzelverzeichnis.
Die Eingangsdaten werden aus dem dokumentierten R17-Ergebniscommit extrahiert
und vor der Verarbeitung per SHA-256 geprüft.

```powershell
python outputs/herbst-igel-r02-local-underside-hybrid-rebuild-r18/reproduction-scripts/r18_local_hybrid.py
python outputs/herbst-igel-r02-local-underside-hybrid-rebuild-r18/reproduction-scripts/validate_r18.py
```

Der erste Lauf erzeugt die drei Diagnosekandidaten, ROI-/Topologie-/Formberichte,
sieben Ansichten, Unterseiten-Nahansicht, REF-SEAM-Overlay und Statusdateien.
Der zweite Lauf prüft Eingangs-/Artefakthashes, Pflichtdateien, Gate-3-Sperre,
Dateigrößen und die indizierte Topologie des ausgewählten Diagnosekandidaten.

Alle Kandidaten sind ausdrücklich `pre-Gate-3` und nicht produktionsfreigegeben.
