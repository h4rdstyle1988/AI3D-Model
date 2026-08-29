# TASK-KUERBIS-20MM-R01-PRINT-RELEASE

Status: VOM NUTZER ZUM DRUCK FREIGEGEBEN
Datum: 2026-08-29

## VERBINDLICH
- Der Nutzer hat den bestehenden Kürbis-Entwurf R01 ausdrücklich zum Testdruck freigegeben.
- Exakter freigegebener Ergebnisstand: Commit `455914037523924f523f38070c213c34eaaf6fdf` auf Branch `ruediger/task-kuerbis-20mm-r01-6b5f4e28`.
- Geometrie, Maße, Rippen, Oberfläche, Stiel und Verbindung NICHT verändern.
- Keine neue Konstruktion und keine optische Überarbeitung.
- Die bereits erzeugten Druckdateien dieses Ergebnisstands verwenden:
  - `outputs/kuerbis-20mm-r01/kuerbis-20mm-r01-zweifarbig.3mf`
  - `outputs/kuerbis-20mm-r01/kuerbis-20mm-r01-koerper.stl`
  - `outputs/kuerbis-20mm-r01/kuerbis-20mm-r01-stiel.stl`
- Bekannte SHA256 laut freigegebenem Ergebnisstand müssen vor Bereitstellung geprüft werden:
  - Körper STL: `b08f5c257c02d2a7efa1abc6a4cf67f2eca6364f99534f4789df18f0beac7d40`
  - Stiel STL: `94813de8374724ced640ec15b3f879c6fe64f756f91e4c7732b6ed162e4dfe93`
  - Zweifarbig 3MF: `9b220f28e2bd78d722301881288d7a8794b9581e3d6bbed035c0afcaeb814e6c`

## DRUCKZIEL
- Zielgerät: Anycubic Kobra S1 mit ACE Pro.
- Hauptdatei für den Testdruck: zweifarbiges 3MF.
- Körper: PLA Matt Desert Tan.
- Stiel: PLA Metal Kupfer.
- Düse 0,4 mm.
- Layerhöhe 0,12 mm; erste Schicht 0,20 mm.
- 3 Außenwände = 1,2 mm.
- Top/Bottom 4 Schichten.
- 5 % Gyroid.
- Außenwand 30–40 mm/s.
- kleine Perimeter/Stiel 20–30 mm/s.
- Support zunächst AUS.
- Brim zunächst AUS.
- Naht hinten bzw. in Rippenvertiefung.
- Normale Orientierung auf flacher Kürbisunterseite.

## BEREITSTELLUNG
- Freigegebene Dateien unverändert aus dem exakten Ergebniscommit übernehmen; nicht neu meshen oder neu exportieren, sofern kein Dateifehler vorliegt.
- Lokale Druckfreigabe unter `D:\3D-Models\generated\kuerbis-20mm-r01-print-release\` bereitstellen.
- Mindestens 3MF, beide STL und eine kurze `PRINT-RELEASE.txt` mit Commit, Hashes und Slicer-Zielparametern ablegen.
- Zusätzlich im Ergebnisbranch einen maschinenlesbaren Release-Bericht anlegen, der die Hash-Prüfung und den lokalen Zielpfad dokumentiert. Keine Binärdateien unnötig duplizieren, wenn sie bereits exakt aus dem Referenzcommit übernommen werden können.

## VALIDIERUNG
- SHA256 aller drei Binärdateien gegen obige Werte prüfen.
- 3MF-Struktur: zwei getrennt anwählbare Meshobjekte bestätigen.
- Keine Geometrieänderung zwischen Referenzcommit und Druckrelease.
- Lokalen Zielpfad und vorhandene Dateien prüfen.
- Keine finale Druckqualität behaupten; realer Testdruck bleibt reale Prüfung.

## FREIGABE
Dieser Auftrag ist die ausdrückliche Nutzerfreigabe, den bestehenden R01-Entwurf unverändert als Testdruck zu verwenden.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false` – bei reinen Datei-/Kopier-/Hash-/Slicer-Bereitstellungsproblemen technisch selbstständig lösen.