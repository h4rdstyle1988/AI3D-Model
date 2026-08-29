# TASK-KUERBIS-20MM-R01-PRINT-RELEASE-R03-8

Status: VOM NUTZER ZUM DRUCK FREIGEGEBEN
Datum: 2026-08-29

## VERBINDLICH
- Den bereits freigegebenen Kürbis R01 unverändert als Testdruck bereitstellen.
- Referenzstand bleibt exakt Commit `455914037523924f523f38070c213c34eaaf6fdf` auf Branch `ruediger/task-kuerbis-20mm-r01-6b5f4e28`.
- Keine Geometrie-, Maß-, Rippen-, Oberflächen-, Stiel-, Verbindungs- oder Exportänderung.
- Keine Neukonstruktion, kein Remesh, kein Re-Export, sofern die vorhandenen Binärdateien fehlerfrei sind.
- Vor Bereitstellung SHA256 exakt prüfen:
  - Körper STL: `b08f5c257c02d2a7efa1abc6a4cf67f2eca6364f99534f4789df18f0beac7d40`
  - Stiel STL: `94813de8374724ced640ec15b3f879c6fe64f756f91e4c7732b6ed162e4dfe93`
  - Zweifarbig 3MF: `9b220f28e2bd78d722301881288d7a8794b9581e3d6bbed035c0afcaeb814e6c`

## DRUCKZIEL
- Hauptdatei: `kuerbis-20mm-r01-zweifarbig.3mf`
- Anycubic Kobra S1 mit ACE Pro.
- Körper: PLA Matt Desert Tan.
- Stiel: PLA Metal Kupfer.
- Düse 0,4 mm; Layerhöhe 0,12 mm; erste Schicht 0,20 mm.
- 3 Außenwände = 1,2 mm; Top/Bottom 4; 5 % Gyroid.
- Support zunächst AUS; Brim zunächst AUS.
- Normale Orientierung auf flacher Kürbisunterseite.

## R03.8-BEREITSTELLUNGSTEST
- Dieser Auftrag wird ausdrücklich nach Aktivierung von Watcher R03.8 erneut ausgeführt.
- Lokalen Zielpfad `D:\3D-Models\generated\kuerbis-20mm-r01-print-release\` anlegen/verwenden.
- Dort exakt die geprüften 3 Dateien und `PRINT-RELEASE.txt` bereitstellen.
- Danach lokal tatsächlich prüfen, dass Zielordner und alle vier Dateien existieren.
- SHA256 der drei Binärdateien auch am lokalen Ziel erneut gegen die oben genannten Werte prüfen.
- Ergebnisbericht muss lokalen Zielpfad mit PASS/FAIL und den drei lokalen Hash-Prüfungen dokumentieren.

## VALIDIERUNG
- 3MF enthält weiterhin zwei getrennt anwählbare Meshobjekte.
- Geometrie bleibt per identischer SHA256 unverändert.
- Keine finale Druckqualität behaupten; realer Testdruck bleibt reale Prüfung.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false` – reine technische Bereitstellung, selbstständig lösen.
