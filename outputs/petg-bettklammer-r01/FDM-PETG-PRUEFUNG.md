# PETG-Bettklammer R01 – FDM-/PETG-Prüfung

Stand: 2026-08-29  
Status: **VORPRÜFUNG; KEINE GEOMETRIEBEZOGENE FREIGABE**

## Prüfergebnis

- Eine belastbare Feder-/Bogenprüfung ist ohne festgelegte Innenweite, Bogenradien und Zahngeometrie nicht möglich.
- Mesh-Prüfung, Wandstärkenprüfung, Maßprüfung und Slicing sind nicht möglich, weil gemäß STOPPREGEL keine STL erzeugt wurde.
- Die lokale Toolchain wurde geprüft. `FreeCADCmd`, `OpenSCAD`, Blender und eine installierte Python-Laufzeit wurden nicht gefunden. Damit wäre auch nach Klärung der Geometrie nur eine durch eine verfügbare CAD-Toolchain reproduzierbare Export-/Validierungsroute zulässig.

## Druckorientierung

Die endgültige Druckorientierung bleibt **OFFEN**, bis die Geometrie feststeht. Technisches Ziel ist, den U-Querschnitt so zur Bauplatte zu orientieren, dass die beim Aufweiten maßgebliche Biegespannung nicht primär die Layerhaftung belastet. Eine konkrete Orientierung wird erst am CAD-Modell festgelegt und anschließend auf Stützbedarf, Zahnabbildung und Layerverlauf geprüft.

## Reale Prüfung

R01 bleibt auch nach später erfolgreichem STL-/Mesh-Check eine Testrevision. Passung, Aufschiebekraft, Haltewirkung, Beschädigungsfreiheit von Filz/Chrom und Dauerverhalten müssen am realen Bett durch den Nutzer geprüft werden. Eine finale Nutzerfreigabe wird hier nicht behauptet.

