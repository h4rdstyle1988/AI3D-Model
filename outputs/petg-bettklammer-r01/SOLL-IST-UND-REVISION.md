# PETG-Bettklammer R01 – SOLL/IST, Prüfung und Revision

Status: **TESTREVISION – keine finale Nutzerfreigabe**  
Task: `tasks/TASK-PETG-BETTKLAMMER-R01.md`

## VERBINDLICH

| Merkmal | SOLL | IST CAD/STL | Bewertung |
|---|---:|---:|---|
| Materialvorgabe | PETG | PETG für Druck festgelegt | erfüllt; nicht im STL codierbar |
| Klammerbreite | 20,0 mm | 20,0 mm | erfüllt |
| Gesamthöhe ganz oben bis ganz unten | 40,0 mm | 40,0 mm | erfüllt |
| Wandstärke | 2,0 mm | 2,0 mm am Bogen und an beiden Schenkeln | erfüllt |
| Chromprofil-Tiefe | 20,0 mm | 20,0 mm Auslegungsmaß | geschützt |
| Filzdicke | 2,0 mm | 2,0 mm Auslegungsmaß | geschützt |
| Chromüberstand | 2,0 mm, rechteckig, direkt oben | als realer Haltepunkt der Zähne berücksichtigt | real zu prüfen |
| Grundprinzip | U-Klammer, von oben aufgeschoben | offenes U-Profil | erfüllt |
| Zähne | mehrere, keine Zusatzfunktion | 4 | erfüllt |

## TECHNISCH NOTWENDIG / für R01 festgelegt

- Lichte Innenweite: **22,4 mm**.
- Zusammensetzung: 20,0 mm Chromprofil + 2,0 mm Filz + **0,4 mm Montagespiel**. Das Montagespiel ist technisch festgelegt, nicht nutzerverbindlich.
- Außenmaß in Aufnahmerichtung: 26,4 mm; kein nutzerbestätigtes Zielmaß, sondern Ergebnis aus Innenweite plus zweimal 2,0 mm Wand.
- Bogen: innerer Radius 3,0 mm, äußerer Radius 5,0 mm; konstante 2,0-mm-Wand und keine belastete scharfe 90°-Innenecke.
- Zähne: vier Stück, je 1,0 mm nomineller Eingriff. Anordnung an der Bett-/Chromseite bei z = 32/27/22/17 mm.
- Orientierung: Zahnspitzen zeigen in die lichte Aufnahme. Die lange untere Flanke bildet beim Aufschieben von oben die Rampe; die kurze obere Flanke greift gegen Abziehen nach oben. Zahnfüße sind mit nominell 0,35 mm verrundet.

## PETG-/FDM-Prüfung

Empfohlene Druckorientierung: Klammer auf eine 20-mm-breite Seitenfläche legen (STL um 90° drehen), sodass der komplette U-Querschnitt in der Schichtebene liegt. Dadurch laufen die Konturen durch Bogen und Schenkel; die Federwirkung muss nicht primär zwischen Layern übertragen werden. Diese Lage ist ohne konstruktive Zusatzhalterung druckbar. Brim nur bei lokaler Haftungsnotwendigkeit im Slicer, nicht als Bauteilgeometrie.

Konservative Überschlagsprüfung eines 35-mm-langen, 2-mm-starken Schenkels bei 1,0 mm lokaler Auslenkung: Oberflächendehnung näherungsweise `6*t*delta/L² = 0,98 %`. Das liegt für einen ersten PETG-Funktionstest in einer plausiblen elastischen Größenordnung, ersetzt aber weder konkrete Filamentdaten noch den realen Steck-/Dauertest. Die 0,4-mm Grundluft reduziert Dauer-Vorspannung; die Zähne verursachen lokal bis zu 1,0 mm Auslenkung. Bogen- und Zahnfußradien reduzieren Kerbwirkung.

## Technische Validierung

`build_and_validate_r01.ps1` erzeugt die ASCII-STL reproduzierbar und prüft Dreieckszahl, Grenzen und watertight-Kanteninzidenz. Ergebnis steht in `technical-validation.json`. Die lokale Toolchain enthält keinen OpenSCAD-/FreeCAD-Kernel und keinen Slicer; deshalb konnten SCAD-Boolean-Render und G-Code-Slicing nicht ausgeführt werden. Die erzeugte STL stammt direkt aus der identischen parametrischen Querschnittsdefinition.

Ein Validator-PASS bestätigt nur formale Mesh-/Maßeigenschaften und ist ausdrücklich **keine finale Produktfreigabe**.

## Revision R01

### GEÄNDERT

- Erstkonstruktion des parametrischen U-Profils angelegt.
- Technisch festgelegtes Montagespiel 0,4 mm ergänzt.
- Vier 1,0-mm-Widerhaken mit Einführrampe, Haltekante und verrundetem Fuß ergänzt.
- Belastungsgerechter Bogen mit 3,0/5,0-mm Innen-/Außenradius angelegt.

### UNVERÄNDERT

- Alle bestätigten Nutzermaße: 20,0 mm Breite, 40,0 mm Höhe, 2,0 mm Wand, 20,0 mm Chromtiefe, 2,0 mm Filz, 2,0 mm rechteckiger Chromüberstand direkt oben.
- Reines Klammerprinzip ohne zusätzliche Funktion.

### ENTFERNT

- Nichts; Erstkonstruktion.

### OFFEN

- Reale Passung, Aufschiebekraft, Haltekraft, Kriechverhalten und Oberflächenschutz am konkreten Bett sind nur durch den Nutzer-Test prüfbar.
- Falls R01 zu stramm/locker ist oder die 1,0-mm-Zähne den Chromüberstand nicht passend greifen, sind Messwerte aus dem realen Test für eine Folgerevision erforderlich.
- Keine konstruktiv relevante Angabe fehlt, die die Erstellung dieser R01-Testgeometrie verhindert; daher kein STOPP vor der Testrevision.

