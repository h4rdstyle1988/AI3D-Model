# PETG-Bettklammer R01 – SOLL/IST, Prüfung und Revision

Status: **TESTREVISION – keine finale Nutzerfreigabe**

## VERBINDLICH

| Merkmal | SOLL | IST CAD/STL | Status |
|---|---:|---:|---|
| Materialvorgabe | PETG | PETG-Auslegung dokumentiert | PASS |
| Klammerbreite | 20,0 mm | 20,0 mm | PASS |
| Gesamthöhe | 40,0 mm | 40,0 mm | PASS |
| Wandstärke | 2,0 mm | 2,0 mm (Bogen radial, Schenkel nominal) | PASS |
| Chromprofil | 20,0 mm | als Aufnahmebedarf berücksichtigt | PASS |
| Filz | 2,0 mm | als Aufnahmebedarf berücksichtigt | PASS |
| Chromüberstand | 2,0 mm, rechteckig, direkt oben | Haltepunkt für gerichtete Verzahnung; realer Eingriff bleibt Testgegenstand | PASS konstruktiv / REALTEST OFFEN |
| Grundform | U-Klammer von oben | U-Klammer | PASS |
| Zusatzfunktionen | keine | keine | PASS |

## TECHNISCH NOTWENDIG / technisch festgelegt

- Lichte Innenweite: **22,4 mm**.
- Aufnahmebedarf: 20,0 mm Profil + 2,0 mm Filz = 22,0 mm.
- Montagespiel: **0,4 mm gesamt**, für R01 technisch festgelegt. Dies ist kein geändertes Nutzermaß.
- Bogen: konzentrischer 180°-Bogen, Außenradius **13,2 mm**, Innenradius **11,2 mm**, konstante radiale Wand 2,0 mm; keine belastete scharfe 90°-Innenecke.
- Verzahnung: **18** direkt aneinandergereihte Zähne, **1,4 mm** Teilung, **0,6 mm** maximaler Eingriff, Beginn 1,2 mm über Schenkelende. Flache Aufschieberampe über 1,15 mm und steile Halteflanke über 0,25 mm. Orientierung: Gleiten beim Aufschieben von unten nach oben entlang der Innenkontur, Greifen gegen die umgekehrte Abziehbewegung.
- Zahnfüße entstehen ohne isolierte scharfe Kerbschlitze als durchgehende Sägezahn-Innenkontur. Die endliche 0,25-mm-Rückflanke vermeidet eine mathematisch überhängende Nullbreitenkante; eine zusätzliche Verrundung unterhalb der FDM-Auflösung wurde nicht erfunden.

## FDM-/PETG-Prüfung

- Empfohlene Druckorientierung: **auf einer 20-mm-breiten Seitenfläche**, sodass der U-Querschnitt in jeder Schicht vollständig aufgebaut wird. Damit liegt die Federbiegung überwiegend in den durchgehenden Extrusionsbahnen und nicht als Ablösebelastung zwischen übereinandergestapelten Schenkellayern.
- Empfohlen: 0,4-mm-Düse, 0,20-mm Schichthöhe, mindestens 4 Perimeter; PETG trocken und mit materialherstellergerechter Temperatur drucken. Keine Supports im offenen U-Querschnitt vorgesehen.
- Indikative Federprüfung: Der 2,0-mm-Bogen mit großen konzentrischen Radien vermeidet die kritische scharfe Innenecke. Die Zahninterferenz beträgt maximal 0,6 mm und wird über beide langen Schenkel/Bogen elastisch aufgenommen. Eine belastbare Spannungsfreigabe ist ohne konkretes PETG-Datenblatt, Druckparameter und reale Einspann-/Reibwerte nicht möglich.
- Lokale Toolchain-Prüfung: STL wird aus dem parametrischen Querschnitt reproduziert; Bounding-Box, Dreieckstopologie und geschlossene Zweifachbelegung aller Meshkanten werden automatisch geprüft. Slicer-/G-Code-Prüfung war lokal mangels CAD-/Slicer-CLI nicht möglich.

## OFFEN / STOPP für finale Bewertung

- Reale Passung, benötigte Aufschiebekraft, Haltekraft, Zahnkontakt am 2,0-mm-Chromüberstand und mögliche Spuren an Chrom/Filz müssen am Bett getestet werden.
- Eine finale Produktfreigabe bleibt ausschließlich dem Nutzer nach Realtest vorbehalten.
- Kein fehlender Punkt verhindert die ausdrücklich verlangte materialarme Testrevision R01; die obigen Punkte verhindern jedoch jede finale Freigabe.

## Revision R01

- **GEÄNDERT:** frühere diskrete Vier-Zacken-Ausführung durch 18-zahnige, regelmäßige Feinverzahnung ersetzt; Innenweite technisch auf 22,4 mm festgelegt; belastungsgerechter Rundbogen ausgeführt.
- **UNVERÄNDERT:** Nutzermaße 20,0 mm Breite, 40,0 mm Gesamthöhe, 2,0 mm Wand, 20,0 mm Profil, 2,0 mm Filz und 2,0 mm Chromüberstand; PETG; U-Grundprinzip.
- **ENTFERNT:** wenige weit auseinanderliegende Einzelzacken; keine Zusatzfunktionen vorhanden.
- **OFFEN:** ausschließlich Realtestpunkte und daraus mögliche Folgerevision; keine finale Nutzerfreigabe.

## Reproduktion

`powershell -ExecutionPolicy Bypass -File .\outputs\petg-bettklammer-r01\build-and-validate-r01.ps1`

Parametrischer CAD-Stand: `petg-bettklammer-r01.scad`. Der PowerShell-Generator verwendet dieselben dokumentierten Parameter und erzeugt `petg-bettklammer-r01.stl` sowie `technical-validation.json` ohne externe CAD-Bibliothek.
