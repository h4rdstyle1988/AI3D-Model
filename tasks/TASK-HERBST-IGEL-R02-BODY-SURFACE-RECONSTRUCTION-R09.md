# TASK-HERBST-IGEL-R02-BODY-SURFACE-RECONSTRUCTION-R09

## Status
Freigegebener technischer Folgeauftrag nach R08-OPTIK_GATE FAIL.

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

## Ausgangslage R08
R08 hat belegt:
- Seed 42 bleibt die beste Trellis-Masterform.
- lokale Entfernung der falschen Blatt-/Stachelflächen allein reicht nicht aus.
- unter den störenden fusionierten Flächen existiert keine ausreichend kontinuierliche versteckte Körperhaut; nur ca. 3.12 % der gesampelten seam-definierten Body-Pixel waren durchgehend als verdeckte Körperoberfläche vorhanden.
- deshalb darf nicht einfach weiter gelöscht werden, weil sonst Löcher/fehlende Körperform entstehen.

## Auftrag R09
Rekonstruiere ausschließlich die technisch fehlende glatte Körper-/Gesichtsoberfläche im durch falsche Blatt-/Stachelflächen verdeckten Bereich der Seed-42-Masterform und entferne danach nur die eindeutig störenden Blatt-/Stachelflächen vor REF-SEAM.

### Rekonstruktionsregeln
1. Keine neue Figur erzeugen und keinen anderen Seed als neue Gesamtform verwenden.
2. Bestehende korrekte Seed-42-Geometrie außerhalb des lokalen Problemfeldes schützen.
3. Rekonstruiere fehlende Körperhaut nur dort, wo REF-CLEAN + REF-SEAM eindeutig Körper/Gesicht verlangen und R08 fehlende Unterhaut nachgewiesen hat.
4. Die rekonstruierte Oberfläche muss als glatte, organische Fortsetzung der angrenzenden vorhandenen Körper-/Gesichtsfläche entstehen. Keine künstlichen Beulen, Wülste, Sockel oder Kanten.
5. Augen, Nase, Ohren, Schnauzenform und Füße nicht neu erfinden; vorhandene korrekte Geometrie erhalten. Falls eine störende Blattfläche diese Geometrie schneidet, nur die Blattfläche entfernen und die lokale Körperhaut geometrisch kontinuierlich ergänzen.
6. Kein dekoratives Rücken-/Blattdetail neu erfinden. Das eine sichtbare Ahornblatt auf der Referenzseite muss erhalten bleiben.
7. Trennbereich muss visuell an REF-SEAM anschließen; keine Kupfer-/Rückenstruktur über die definierte Gesichts-/Körpergrenze ziehen.
8. Keine Bildmanipulation der autoritativen Referenz als Produktänderung. 2D-Masken/Projektionen dürfen ausschließlich als geometrische Mess-/Selektionshilfe aus REF-CLEAN/REF-SEAM abgeleitet werden.

## Technisch bevorzugte Vorgehensweise
- Seed-42-Rohmesh und R08-Diagnostik wiederverwenden; kein neuer Voll-Trellis-Lauf, sofern nicht zwingend technisch erforderlich.
- lokale Problemzone geometrisch bestimmen.
- störende fusionierte Blatt-/Stacheloberflächen selektiv isolieren.
- fehlende Body-Surface als lokale Surface-Reconstruction/Patch auf Basis angrenzender Körperkrümmung, Referenzsilhouette und vorhandener sichtbarer Gesichtsgeometrie erzeugen.
- Übergang mit Krümmungs-/Normalen-Kontinuität glätten, ohne bestätigte Außenform außerhalb der Zone zu verändern.
- anschließend lokale Mesh-Reparatur nur technisch notwendig.

## Optik-Gate vor CAD/FDM
Erzeuge reale Geometrie-Renders mindestens:
- 3/4 vorne
- links
- rechts
- hinten
- oben
- unten
- SOLL/IST-Gegenüberstellung mit REF-CLEAN und REF-SEAM

PASS nur wenn eindeutig:
- Gesicht frei und rundlich wie Referenz
- keine Blatt-/Stachelüberdeckung von Stirn/Augen/Schnauze
- kurze weiche Schnauze/Nase erhalten
- beide runden Ohren erhalten
- Augenform erhalten
- vier kurzen Füße erhalten
- Rücken weiterhin gewölbt mit überlappender Blatt-/Stachelstruktur
- ein sichtbares Ahornblatt erhalten, kein zweites
- REF-SEAM-Grenze visuell plausibel eingehalten
- keine auffällige Patch-Beule, Delle, harte Stufe oder Lochreparatur sichtbar

Bei Optik FAIL: STOPP vor Split/CAD/STL und dokumentieren, warum.
Bei Optik PASS: erst dann unverändert mit Split entlang REF-SEAM, Hohlschalen, Ø10.0 x 20.0 mm Klebeverbinder und vollständiger technischer Validierung fortfahren.

## Pflichtausgaben
- reproduzierbare Skripte/Quelle
- Revisionsbericht GEÄNDERT / UNVERÄNDERT / ENTFERNT / OFFEN
- real-geometry Renders und SOLL/IST
- maschinenlesbarer Ergebnisstatus
- bei PASS danach die bereits verbindlich geforderten Fertigungsartefakte und Validierungen

Keine finale Nutzerfreigabe behaupten.
