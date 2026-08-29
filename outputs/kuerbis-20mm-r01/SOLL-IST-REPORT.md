# SOLL/IST – TASK-KUERBIS-20MM-R01, Revision R01

Status: **PASS** (technische Dateiprüfung), keine finale Produktfreigabe.

| Anforderung | IST | Bewertung |
|---|---|---|
| Außendurchmesser ca. 20 mm | 19,83 mm achsenbezogene Außenweite; radialer Maximalradius 10,00 mm | PASS |
| Deutliche Kürbisrippen | Acht Rippen, ca. 9,2 % radiale Modulation | PASS, Sichtprüfung am Druck offen |
| Organische/strukturierte Haut | Zwei überlagerte, deterministische Reliefwellen, nominal 0,18 mm Spitzenamplitude | PASS, Sichtprüfung am Druck offen |
| Kurzer, leicht unregelmäßiger Stiel | 6,00 mm hoch, leicht gekrümmt, unregelmäßiger 5-/11-facher Querschnitt | PASS |
| Ein zusammenhängender Druck | Körper/Stiel überlappen axial 0,83 mm und radial volumetrisch | PASS |
| Getrennte Materialzuweisung | 3MF enthält zwei benannte Meshobjekte und zwei Build-Items | PASS, Slicer-UI-Prüfung offen |
| Körperwand 1,2 mm | 3 × 0,4 mm Außenwand im verbindlichen Slicerprofil; kein CAD-Hohlraum | PASS gemäß Task |
| 5 % Gyroid | Im Slicerprofil dokumentiert | OFFEN bis realer Slice |
| FDM, normale Unterseite, möglichst supportfrei | Ebene Unterseite; kein freier Brückenbereich; kurzer, sich verjüngender Stiel | PASS analytisch, realer Slice offen |
| Keine Zusatzfunktionen | Keine ergänzt | PASS |

## Validierung

- Körper: 31.104 Dreiecke, 0 Randkanten, 0 nichtmanifold Kanten, watertight.
- Stiel: 3.200 Dreiecke, 0 Randkanten, 0 nichtmanifold Kanten, watertight.
- 3MF: Core-2015-Namespace, Millimeter, zwei getrennte Objekte in gemeinsamer Lage.
- Druckparameter sind dokumentiert, aber nicht als endgültiger Druckcode erzeugt.

## Offene reale Prüfungen

1. 3MF im Ziel-Slicer öffnen, getrennte Anwahl und Filamentzuordnung bestätigen.
2. Vorschau auf Naht, kleine Perimeter, Überhänge und tatsächliche 5-%-Gyroid-Füllung prüfen.
3. Testdruck: Sichtbarkeit von Rippen/Haut und Festigkeit der Stielverbindung beurteilen.
4. Finale Produktfreigabe ausschließlich durch den Nutzer.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false` – keine widersprüchliche oder fehlende konstruktiv relevante Vorgabe; nur reale Prüfungen und finale Nutzerfreigabe sind offen.

