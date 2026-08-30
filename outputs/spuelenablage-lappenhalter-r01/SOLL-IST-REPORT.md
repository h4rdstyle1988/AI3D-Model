# SOLL/IST-REPORT – spuelenablage-lappenhalter-r01

Technischer Ergebnisstatus: **PASS**  
Task: `tasks/TASK-SPUELENABLAGE-LAPPENHALTER-R01.md`  
Revision: **R01**

| Merkmal | SOLL | IST | Ergebnis |
|---|---:|---:|---|
| Steckpunkte | genau 1 | 1 | PASS |
| Sechskant-Schlüsselweite | 8,90 mm | 8.900000 mm STL / 8,900000 mm CAD | PASS |
| gerade Stecklänge | 18,0 mm | 18,000000 mm CAD; konstante STL-Schnitte z=1/9/17 | PASS |
| Konizität/Rastung | keine | keine | PASS |
| freie Ausladung bis Anschlagbeginn | 90 mm | 90,000000 mm CAD | PASS |
| Armquerschnitt Hauptsektion | 12 × 10 mm | 12.000000 × 10.000000 mm STL | PASS |
| Anschluss | weich, integriert, keine Kerbe | 12-mm-Quintic-Morph, an beiden Enden tangential | PASS |
| Material / Düse | PETG / 0,4 mm | dokumentiert | PASS |
| zusätzliche Funktionen | keine | keine | PASS |
| STL | watertight / 2-manifold | True, Rand-/Nonmanifold-Kanten 0/0 | PASS |

## Geändert

- Arm-Hauptquerschnitt von 10 × 8 mm auf 12 × 10 mm.
- Anschluss oberhalb z=18 mm als tangentiale, monotone Querschnittsüberleitung statt abruptem Sprung.
- Hauptbogen passend zum höheren Profil mit unverändertem R6-Innenradius; bestätigte Unterseitenhöhe bleibt erhalten.

## Unverändert

- 8,90-mm-Sechskant, 18,0-mm-Stecklänge, gerade/konstante Form.
- Genau ein Steckpunkt, 90-mm-Ausladung, PETG / 0,4-mm-Düse.
- Keine Konizität, Rastung, Zusatzführung, Basis oder Zusatzfunktion.
- Bestehende Höhe bis zum Bogenbeginn, R6-Innenradius sowie Funktion und 8-mm-Hüllmaße des Endanschlags.

## Entfernt

- Nichts.

## Offen

- Reale Steckpassung des unveränderten 8,90-mm-Zapfens.
- Nachweis von mindestens ca. 18,5–19 mm freiem axialem Wabenraum am realen Bauteil.
- PETG-Testdruck, Biegetest mit gut feuchtem Lappen sowie Kriech-/Nasszyklus.
- Finale Produktfreigabe ausschließlich durch den Nutzer.
