# Kürbis 20 mm – R01

Freigegebener Auftrag: `tasks/TASK-KUERBIS-20MM-R01.md`

## Hauptdateien

- `kuerbis-20mm-r01-zweifarbig.3mf`: zwei getrennt anwählbare, überlappende Objekte für einen zusammenhängenden Zweifarb-Druck.
- `kuerbis-20mm-r01-koerper.stl`: Kürbiskörper.
- `kuerbis-20mm-r01-stiel.stl`: Stiel in identischen Weltkoordinaten; nicht separat auf das Druckbett absenken.
- `../../work/build_kuerbis_20mm_r01.py`: parametrische CAD-/Exportquelle.
- `machine-readable-result.json`: maschinenlesbarer Ergebnis- und Prüfstatus.

## Slicer-Ziel

3MF als ein Mehrkörpermodell importieren. Körper auf PLA Matt Desert Tan und Stiel auf PLA Metal Kupfer legen. 0,4-mm-Düse, 0,12-mm-Layer (erste Schicht 0,20 mm), drei Außenwände = 1,2 mm, vier Top-/Bottom-Schichten, 5 % Gyroid. Support und Brim zunächst aus. Naht hinten oder in eine Rippenvertiefung legen.

Die Datei ist technisch erzeugt und geprüft, aber nicht final vom Nutzer freigegeben.

