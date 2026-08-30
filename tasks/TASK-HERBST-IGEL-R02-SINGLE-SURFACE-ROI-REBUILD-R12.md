# TASK-HERBST-IGEL-R02-SINGLE-SURFACE-ROI-REBUILD-R12

## Status
Freigegebener technischer Retry nach R11 OPTIK_GATE + MESH_GATE FAIL.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

## Verbindliche Produktbasis
Unverändert aus der zuletzt freigegebenen Herbst-Igel-Spezifikation:
- Seed 42 bleibt die globale Formbasis.
- REF-CLEAN ist autoritativ für Optik, REF-SEAM autoritativ für Trennlinie.
- ca. 200 mm maximale Gesamtausdehnung, proportional.
- exakt zwei Druckteile: Körper vorn PLA Matt Desert Tan, Rücken-/Stachelschale PLA Metal Kupfer.
- beide hohl, nominal 1.6 mm Wand.
- Gesicht vollständig frei; keine Blatt-/Stachelflächen über Stirn, Augen oder Schnauze.
- genau ein sichtbares dekoratives Ahornblatt auf der Referenzseite, kein zweites.
- zentraler interner Klebeverbinder Ø10.0 mm exakt, 20.0 mm Eingriff exakt; keine Rastung, Konizität, Klemmung, Magnete oder Zusatzführungen.
- 0.4-mm-Düse; Ziel 0.12 mm Layer, adaptiv bis 0.08 mm erlaubt.

## Verifizierter R11-Fehler
R11 hat außerhalb der ROI korrekt geschützt, aber innerhalb der ROI Alt- und Neugeometrie gleichzeitig erzwungen. Dadurch entstanden 11.125 offene Kanten, 3.598 nichtmanifolde Kanten und bestätigte Quell/Rebuild-Kreuzungen. Optisch blieben harter Stirn-/Seam-Überhang sowie nicht sauber integrierte Augen/Ohren.

## Auftrag R12 — unmissverständlich
Erzeuge innerhalb der bereits autoritativ bestimmten Problem-ROI **genau eine einzige zusammenhängende sichtbare Körper-/Gesichtsoberfläche**. In der ROI darf keine alte fusionierte Seed-42-Blatt-/Stachel-/Gesichtsfragment-Geometrie parallel zur neuen Oberfläche verbleiben.

### Harte Regeln
1. Außerhalb der ROI: Seed-42-Geometrie byte-/indexgetreu unverändert lassen.
2. Innerhalb der ROI: alle nachgewiesenen störenden/fusionierten sichtbaren Quelltriangles vollständig aus der sichtbaren Endoberfläche entfernen. Keine überlappenden Altfragmente behalten, nur weil ihre Vertexkoordinaten Gesichtsteile enthalten.
3. Augen, Nase, Schnauze und Ohren innerhalb der ROI müssen als Teil **derselben neu aufgebauten manifold Oberfläche** rekonstruiert werden, geführt durch REF-CLEAN-Silhouette, REF-SEAM, angrenzende gesunde Seed-42-Randgeometrie und die Lage der vorhandenen Merkmalsgeometrie. Sie dürfen nicht als separate schneidende Inseln wieder eingesetzt werden.
4. Der Übergang am ROI-Rand muss topologisch vernäht sein: exakt eine gemeinsame Randkante zwischen erhaltener Quelle und Rebuild, keine doppelten Flächen, keine T-Junctions, keine offenen Nähte.
5. Sichtbarer Endkörper vor Optik-Gate muss bereits ein zusammenhängendes 2-manifold Oberflächenmesh sein. Pflicht: boundary_edges=0 an der Reparaturnaht, nonmanifold_edges=0, confirmed cross_intersections=0.
6. Keine planaren Caps, Triangle-Fans, Convex-Hull-Flicken, Regal-/Stufenkanten oder blockartigen Lochfüller.
7. Keine neue Gesamtfigur, kein anderer Seed, kein neues Ahornblatt, keine Änderung des Rückens außerhalb ROI.
8. REF-SEAM darf nicht überschritten werden: Körperseite glatt; Blatt-/Stachelstruktur beginnt erst hinter der autoritativen Trennlinie.
9. Innerhalb desselben Laufs iterativ technisch nachbessern. Nicht nach einem ersten FAIL abbrechen, solange der Fehler innerhalb der festgelegten ROI ohne Produktentscheidung behebbar ist.

## Verbindliche Ausführungsreihenfolge
A. Referenz- und Seed-Hash-Gates prüfen.
B. R11-ROI und gesunden Randring laden.
C. Sämtliche kollidierenden Alttriangles innerhalb ROI entfernen.
D. Einen einzigen geschlossenen lokalen implicit/SDF/Poisson/MLS-Rebuild erzeugen, inklusive organisch eingebetteter Augen-, Ohr-, Schnauzen- und Nasenreliefs.
E. Rebuild geometrisch mit dem erhaltenen Randring verschweißen/remeshen, bis Naht vollständig manifold ist.
F. ZUERST Mesh-Gate ausführen. Bei boundary/nonmanifold/intersections > 0 innerhalb derselben ROI automatisch korrigieren und erneut prüfen.
G. Erst nach MESH_GATE PASS reale Render aus 3/4 vorne, links, rechts, hinten, oben, unten erzeugen.
H. Optik-Gate gegen REF-CLEAN/REF-SEAM durchführen und innerhalb derselben ROI weiter korrigieren, solange nur technische Form-/Nahtfehler bestehen.
I. Erst nach eindeutigem OPTIK_GATE PASS Split/Hohlschalen/Verbinder/STL/FDM-Validierung ausführen.

## Binäres SOLL/IST-Gate
PASS nur wenn ALLE Punkte erfüllt sind:
- Gesicht rundlich und vollständig frei wie REF-CLEAN.
- Stirn frei, keinerlei Blatt-/Stachel-/Seam-Regalkante davor.
- beide Augen klar sichtbar und organisch in dieselbe Oberfläche integriert.
- beide Ohren klar sichtbar und organisch integriert.
- kurze weiche Schnauze und Nase referenznah.
- vier kurze Füße erhalten.
- Rücken außerhalb ROI unverändert und gewölbt mit Blatt-/Stachelstruktur.
- genau ein sichtbares Ahornblatt erhalten.
- REF-SEAM visuell plausibel und ohne harten Absatz.
- Reparatur optisch nicht als Flicken erkennbar.
- Mesh: 0 offene Reparaturnahtkanten, 0 nonmanifold Kanten, 0 bestätigte Kreuzungen.

Bei echtem technisch unbehebbarem FAIL: STOPP mit exakter Ursache und Nachweis. Keine Nutzerentscheidung behaupten, solange keine Produktvorgabe fehlt.

## Pflichtausgaben
- reproduzierbare Skripte/Quelle
- maschinenlesbarer SOLL/IST-Report mit jedem binären Kriterium
- Mesh-Gate-Metriken vor Optik-Gate
- reale Geometrie-Renders und SOLL/IST-Sheet
- Revisionsbericht GEÄNDERT / UNVERÄNDERT / ENTFERNT / OFFEN
- bei PASS anschließend Fertigungsartefakte und FDM-Validierung

Keine finale Nutzerfreigabe behaupten.
