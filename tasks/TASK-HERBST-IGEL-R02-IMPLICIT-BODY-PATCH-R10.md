# TASK-HERBST-IGEL-R02-IMPLICIT-BODY-PATCH-R10

## Status
Freigegebener technischer Folgeauftrag nach R09-OPTIK_GATE FAIL.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

## Verbindliche Produktbasis
Unverändert aus der zuletzt bestätigten Herbst-Igel-Spezifikation:
- Optik so nah wie technisch druckbar an der autoritativen Clean-Referenz.
- ca. 200 mm maximale Gesamtausdehnung, proportional.
- exakt zwei Druckteile: Körper vorn PLA Matt Desert Tan, Rücken-/Stachelschale PLA Metal Kupfer.
- beide hohl, nominal 1.6 mm Wand.
- REF-SEAM ist die autoritative Trennlinie.
- Gesicht frei; keine Blatt-/Stachelflächen über Stirn, Augen oder Schnauze.
- genau ein sichtbares dekoratives Ahornblatt auf der Referenzseite, kein zweites erfundenes.
- ein zentraler interner Klebeverbinder Ø10.0 mm exakt, 20.0 mm Eingriff exakt; keine Rastung, Konizität, Klemmung, Magnete oder Zusatzführungen.
- 0.4-mm-Düse; Ziel 0.12 mm Layer, adaptiv bis 0.08 mm erlaubt.
- keine zusätzlichen Funktionen, Sockel, Halter, Führungen oder Anschläge.

## Ausgangslage R09
R09 hat technisch belegt:
- Seed 42 bleibt die zu schützende Gesamtformbasis.
- lokale Rekonstruktion als triangulierter/patchartiger Oberflächenersatz erzeugte harte fächer-/blockartige Übergänge.
- Restüberdeckung in Stirn/Augen/Schnauzenzone blieb bestehen.
- REF-SEAM war dadurch weiterhin unplausibel.
- vorhandene Quellgeometrie außerhalb des lokalen Feldes wurde korrekt geschützt.

## Auftrag R10
Erzeuge eine neue lokale Körper-/Gesichtsrekonstruktion aus der unveränderten Seed-42-Quelle, diesmal ausdrücklich als glatte implizite/volumetrische Oberfläche mit Krümmungs- und Normalenkontinuität. Der R09-Patch ist nur Diagnose, nicht Formbasis.

### Verbindliche Rekonstruktionsregeln
1. Ausgangsmesh ist wieder die byte-identische Seed-42-Rohform. R09-NON-APPROVED nicht als Master weiterverformen.
2. Außerhalb der eindeutig bestimmten Problemzone keine bestätigte Seed-42-Geometrie verändern.
3. Problemzone ausschließlich aus REF-CLEAN + REF-SEAM + R08/R09-Diagnostik bestimmen.
4. Keine planaren Caps, Dreiecks-Fächer, Convex-Hull-Flächen oder blockartigen Lochfüller als sichtbare Endoberfläche.
5. Verwende eine glatte implizite Rekonstruktion, z. B. SDF/RBF/MLS/Poisson oder technisch gleichwertig, die an den vorhandenen Körperrand mit mindestens C1-artig plausibler Tangenten-/Normalenkontinuität anschließt.
6. Niedrigfrequente Körperform zuerst herstellen; keine dekorativen Details in den rekonstruierten Körper erfinden.
7. Sichtbare Referenzsilhouette und vorhandene freie Körper-/Gesichtsfläche dürfen als Messrandbedingungen dienen. Keine neue Nase, Augen, Ohren, Füße oder Mimik erfinden.
8. Vorhandene Nase, Augen, Ohren, Schnauze und Füße als Schutzgeometrie behandeln. Wenn fusionierte Blatt-/Stachelflächen sie schneiden, nur die störenden Flächen entfernen und die fehlende glatte Haut dazwischen schließen.
9. Das eine sichtbare Ahornblatt auf der Referenzseite und die korrekte Rückenstruktur außerhalb der Problemzone müssen erhalten bleiben.
10. Keine zusätzliche Trenngeometrie oder neue Funktion ergänzen.

## Technisch bevorzugter Weg
- Seed-42-Rohmesh laden und die R08/R09 Problemmaske wiederverwenden/verbessern.
- Randring der gesunden Körperoberfläche um die Problemzone ermitteln.
- Randpositionen, Randnormalen und lokale Krümmung messen.
- Mindestens zwei technisch unterschiedliche glatte lokale Rekonstruktionsvarianten erzeugen, falls mit vertretbarem Aufwand möglich (z. B. RBF/MLS und Poisson/SDF).
- Varianten zunächst schnell mit 3/4-Front + Seitenansicht screenen; nur die beste plausible Variante vollständig in 6 Ansichten rendern.
- Auswahl ausschließlich nach geringster Abweichung zu REF-CLEAN/REF-SEAM und sauberstem organischem Übergang.
- Außerhalb ROI Koordinatenerhalt maschinenlesbar prüfen.
- lokale Selbstschnitte/offene Kanten/degenerierte Dreiecke prüfen; nur technisch notwendige Reparatur.

## Optik-Gate vor CAD/FDM
PASS nur wenn eindeutig:
- Gesicht frei und rundlich wie Referenz.
- keine Blatt-/Stachelüberdeckung von Stirn, Augen oder Schnauze.
- kurze weiche Schnauze/Nase erhalten.
- beide runden Ohren und Augenform erhalten.
- vier kurzen Füße erhalten.
- Rücken gewölbt mit überlappender Blatt-/Stachelstruktur.
- genau ein sichtbares Ahornblatt auf Referenzseite, kein zweites.
- REF-SEAM visuell plausibel.
- keine Patch-Beule, Delle, harte Stufe, Fächerstruktur oder sichtbare Lochreparatur.

Bei FAIL: STOPP vor Split/CAD/STL und dokumentiere die konkrete verbleibende Ursache.
Bei PASS: erst dann unverändert mit REF-SEAM-Split, Hohlschalen, Ø10.0 × 20.0 mm Klebeverbinder und vollständiger technischer Validierung fortfahren.

## Pflichtausgaben
- reproduzierbare Skripte/Quelle
- Revisionsbericht GEÄNDERT / UNVERÄNDERT / ENTFERNT / OFFEN
- real-geometry Renders: 3/4 vorne, links, rechts, hinten, oben, unten
- SOLL/IST mit REF-CLEAN und REF-SEAM
- maschinenlesbarer Ergebnisstatus
- bei PASS anschließend die bereits verbindlich geforderten Fertigungsartefakte und Validierungen

Keine finale Nutzerfreigabe behaupten.
