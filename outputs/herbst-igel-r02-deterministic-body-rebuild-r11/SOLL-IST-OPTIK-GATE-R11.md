# Herbst-Igel R02 – SOLL/IST-Optik-Gate R11

## Ergebnis

`OPTIK_GATE: FAIL`

`STATUS: STOPP`

Die Prüfung beruht auf der realen R11-PLY-Geometrie. Zuerst wurden 3/4-Front,
linke Referenzseite und rechte Seite geprüft. Nach dem ersten Fehlstand wurde
innerhalb derselben ROI die Tiefenselektion der geschützten Seed-42-Merkmale
verschärft und der deterministische Rebuild erneut ausgeführt. Auch dieser
zweite Stand ist kein eindeutiger Optik-PASS.

## Binäre Kriterien

| Verbindliches SOLL | IST R11 | Gate |
|---|---|---|
| Gesicht vollständig frei und rundlich wie REF-CLEAN | Niedrigfrequente Körperhaut vorhanden, aber nicht referenznah frei; harter oberer Übergang bleibt sichtbar | FAIL |
| Stirn frei | Eine harte, regalartige Blatt-/Seam-Kante bleibt über der Stirn | FAIL |
| beide Augen vollständig frei | Quellkoordinaten wurden nicht verschoben, die Augen sind jedoch nicht beidseitig klar und organisch integriert | FAIL |
| Schnauze und Nase frei | Schnauzen-/Nasenbereich bleibt als Quellgeometrie erhalten; die Umgebung ist gegenüber REF-CLEAN zu hart | FAIL |
| beide Ohren vollständig frei | Ohrenkoordinaten sind geschützt, die Übergänge sind nicht beidseitig eindeutig sauber | FAIL |
| keine Blatt-/Stachelgeometrie auf Körperseite von REF-SEAM | Restlicher harter Stirn-/Seam-Überhang ist sichtbar | FAIL |
| Rücken hinter REF-SEAM unverändert | 671.769 Quelltriangles außerhalb der ROI indexgleich erhalten | PASS |
| genau ein vorhandenes Ahornblatt | vorhandenes Blatt erhalten; kein zweites erzeugt | PASS |
| glatter organischer lokaler Übergang | sichtbarer harter Übergang; keine unauffällige Reparatur | FAIL |
| reale 3D-Geometrie | alle Ansichten direkt aus der R11-PLY gerendert | PASS |

## Technischer Zusammenhang

Der einzelne R11-Surface-Rebuild ist für sich niedrigfrequent und ohne
degenerierte Dreiecke, kann aber mit den exakt zu erhaltenden fusionierten
Seed-42-Merkmalsflächen nicht zu einem gültigen Körper verbunden werden:
668 offene Kanten an der lokalen Fläche, im kombinierten Stand 11.125 offene
Kanten, 3.598 nichtmanifolde Kanten und mindestens 253 bestätigte
nichtkoplanare Kreuzungen (Abbruch nach Nachweisgrenze).

Deshalb endet R11 vor REF-SEAM-Split, 1,6-mm-Hohlschalen, Ø10,0 × 20,0-mm-
Klebeverbinder, Skalierung und STL-Export.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

Grund: technischer Optik-/Mesh-Gate-Stopp; kein Nutzermaß und keine
Produktfunktion fehlen.

Eine finale Produkt-, Optik- oder Druckfreigabe wird nicht behauptet.
