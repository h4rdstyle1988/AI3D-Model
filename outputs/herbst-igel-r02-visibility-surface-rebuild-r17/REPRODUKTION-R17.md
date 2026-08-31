# Reproduktion R17

Voraussetzung: Python 3 mit NumPy und Pillow im Repository-Wurzelverzeichnis.
Die Quelle und Referenzen werden deterministisch aus Commit
`b07a712361ae4561fd29d81755dfe161508dc62d` extrahiert und vor jedem Lauf gegen
die verbindlichen SHA-256-Werte geprüft.

```powershell
python outputs/herbst-igel-r02-visibility-surface-rebuild-r17/reproduction-scripts/r17_visibility_poisson.py --attempt small-a
python outputs/herbst-igel-r02-visibility-surface-rebuild-r17/reproduction-scripts/r17_visibility_poisson.py --attempt medium-b
python outputs/herbst-igel-r02-visibility-surface-rebuild-r17/reproduction-scripts/r17_visibility_poisson.py --attempt fine-c
python outputs/herbst-igel-r02-visibility-surface-rebuild-r17/reproduction-scripts/r17_visibility_poisson.py --attempt screened-mls-d --minimum-visibility-hits 2
python outputs/herbst-igel-r02-visibility-surface-rebuild-r17/reproduction-scripts/finalize_r17.py
```

Die Kandidaten sind ausschließlich technische Vor-Gate-3-Diagnosegeometrien.
`screened-mls-d` ist der ausgewählte, ausdrücklich nicht produktionsfreigegebene
Diagnosekandidat. Der Finalizer dokumentiert Gate 2 als FAIL und erzeugt keine
STL-/3MF-/GLB-, Split-, Hohl- oder Verbindergeometrie.
