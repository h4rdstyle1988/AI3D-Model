# SOLL/IST-Maßbericht – R01

## Klammer

| Merkmal | SOLL | IST CAD/STL | Status |
|---|---:|---:|---|
| Materialvorgabe | PETG | PETG dokumentiert | PASS |
| Breite | 20,0 mm | 20,0 mm | PASS |
| Gesamthöhe | 40,0 mm | 40,0 mm | PASS |
| Wandstärke | 2,0 mm | 2,0 mm | PASS |
| aufzunehmendes Chromprofil | 20,0 mm | berücksichtigt | PASS |
| Filz an Klemmstelle | 2,0 mm | berücksichtigt | PASS |
| lichte Aufnahme | mindestens 22,0 mm plus technisches Spiel | 22,4 mm | PASS |
| technisches Montagespiel | nur notwendiges PETG/FDM-Spiel | 0,4 mm diametral, technisch festgelegt | PASS |
| Chromüberstand | 2,0 mm, rechteckig/oben | Zahnrichtung darauf ausgelegt; Nutzermaß nicht verändert | PASS konstruktiv, real zu testen |
| Verzahnung | fein, direkt aneinandergereiht | 18 Zähne, 1,4 mm Teilung, 0,6 mm Eingriff | PASS |
| Klammerbogen | keine scharf belastete 90°-Innenecke | konzentrischer Halbring, Innenradius 11,2 mm | PASS |
| Außenabmessung STL | abgeleitet | 26,4 × 20,0 × 40,0 mm | INFO |

Die Zahnflanke besitzt über 1,05 mm Höhe den flachen Aufschieberampenanteil und über 0,35 mm den steileren Halteanteil. Die Zahnfüße gehen ohne zusätzliche Nut oder Hinterschneidung in den langen Innenschenkel über. Dies ist eine technische R01-Festlegung, keine Änderung eines Nutzermaßes.

## Nubsi

| Merkmal | SOLL | IST CAD/STL | Status |
|---|---:|---:|---|
| Materialvorgabe | PETG | PETG dokumentiert | PASS |
| Schaftdurchmesser | 6,0 mm | 6,0 mm | PASS |
| Schaftlänge | 4,0 mm | 4,0 mm | PASS |
| Schaftform | gerader Zylinder ohne Stufe | gerader Zylinder ohne Stufe | PASS |
| maximaler Kopfdurchmesser | 11,0 mm | 11,0 mm | PASS |
| Kopfhöhe | fotoabgeleitet ca. 3,5–4,5 mm | 4,0 mm | PASS, FOTOABGELEITET / TECHNISCH FESTGELEGT |
| Gesamthöhe | fotoabgeleitet ca. 7,5–8,5 mm | 8,0 mm | PASS, FOTOABGELEITET |
| Kopfcharakter | glatt gewölbt/kuppelförmig | gerundete Rotationskontur, integrierte dünne Randkante | PASS |
| verbotene Zusatzfeatures | keine | keine Stufe, Nut, Rastung, Bohrung oder Hohlraum | PASS |
| STL-Abmessung | abgeleitet | 11,0 × 11,0 × 8,0 mm | PASS |

Die exakte Kuppelkontur und ihr 4,0-mm-Höhenwert sind **FOTOABGELEITET / TECHNISCH FESTGELEGT**. Es wird keine Messgenauigkeit des Originals behauptet.

## Gemeinsame Druckplatte

- Zwei separate STL-Bauteile sind vorhanden.
- Im gemeinsamen STL bleiben zwei Körper geometrisch unverbunden.
- Klammer: X = 0,0–26,4 mm, Y = 0,0–20,0 mm.
- Nubsi: X = 36,4–47,4 mm, Y = 0,0–11,0 mm.
- Kleinster Kantenabstand in X: **10,0 mm**, technisch festgelegt.
- Keine geometrische Verbindung: **PASS** aufgrund getrennter Erzeugungspfade; gemeinsames Mesh zusätzlich geschlossen/topologisch gültig.
