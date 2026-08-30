# TASK-HERBST-IGEL-R02-DETERMINISTIC-BODY-REBUILD-R11

## Status
Freigegebener technischer Folgeauftrag nach wiederholten Optik-Gate-Fehlern R08/R09/R10.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

## ZWECK
Diese Revision beseitigt Interpretationsspielraum. Kein neuer Entwurf, keine Varianten-Lotterie, kein neuer Seed, keine kreative Formänderung. Ziel ist ausschließlich: die bestehende Seed-42-Masterform so lokal zu korrigieren, dass die autoritative Clean-Referenz und REF-SEAM im Gesichts-/Körperbereich eindeutig erfüllt werden.

## VERBINDLICHE PRODUKTBASIS – UNVERÄNDERT
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

## VERBINDLICHE AUSGANGSBASIS
1. Ausgangsgeometrie ist ausschließlich die byte-identische Seed-42-Rohform aus R07/R08.
2. R08-, R09- und ggf. R10-NON-APPROVED-Geometrien dürfen nur als Diagnose dienen, niemals als Formbasis.
3. Es darf kein neuer Trellis-Seed und keine neue Gesamtfigur erzeugt werden.
4. Außerhalb des lokal nachgewiesenen Problemfelds bleiben alle Seed-42-Koordinaten unverändert. Das ist maschinenlesbar nachzuweisen.

## UNMISSVERSTÄNDLICHER SOLLZUSTAND
Die Gesichts-/Körperzone auf der Körperseite von REF-SEAM muss nach der Korrektur wie folgt aussehen:
- Stirn vollständig frei von Blatt-/Stachelgeometrie.
- beide Augen vollständig frei sichtbar.
- Schnauze und Nase vollständig frei sichtbar.
- beide Ohren vollständig frei sichtbar.
- keine kupferne Rücken-/Blattstruktur vor oder auf der Körperseite der REF-SEAM-Grenze.
- Körperoberfläche dort glatt, rundlich und organisch fortlaufend; keine Fächer, Caps, Dreiecks-Sterne, Blöcke, Kanten, Dellen, Beulen oder sichtbare Lochreparatur.
- Rückenstruktur hinter REF-SEAM unverändert erhalten.
- genau das vorhandene sichtbare Ahornblatt erhalten; kein zweites erzeugen.

Wenn einer dieser Punkte nicht erfüllt ist, ist der Stand NICHT PASS.

## DETERMINISTISCHER ARBEITSABLAUF – KEINE ALTERNATIVEN
1. Seed-42 byte-identisch laden und Hash prüfen.
2. REF-CLEAN und REF-SEAM als autoritative Messgrundlage laden und Hash prüfen.
3. Problem-ROI geometrisch bestimmen: ausschließlich die Seed-42-Flächen, die auf der Körperseite von REF-SEAM liegen und dort als Blatt-/Stachelüberdeckung bzw. als dadurch fehlende Körperhaut nachgewiesen sind.
4. Alle gesunden Körperpunkte unmittelbar um diese ROI als feste Randbedingungen sperren: Position + Normalenrichtung.
5. Nase, Augen, Ohren, Schnauze und Füße als Schutzgeometrie sperren; ihre vorhandenen Seed-42-Koordinaten dürfen nicht verändert werden.
6. Störende Blatt-/Stachelflächen in der ROI entfernen.
7. Die dadurch fehlende Körperhaut als EINEN glatten, zusammenhängenden lokalen Körper-Surface-Rebuild erzeugen. Kein patchweises Stückeln. Keine planaren Caps. Keine Dreiecks-Fächer. Keine Convex-Hull-Ersatzfläche.
8. Der Rebuild muss an den gesperrten gesunden Körperrand tangential/normalenstetig anschließen und die vorhandene lokale Körperkrümmung fortführen. Keine neue Gesichtsform erfinden.
9. Danach ausschließlich innerhalb der ROI glätten/reparieren. Außerhalb ROI keinerlei Vertex-Verschiebung.
10. Vor jedem vollständigen Export zuerst 3/4-Front + linke/rechte Frontseite rendern und automatisch/visuell gegen REF-CLEAN + REF-SEAM prüfen.
11. Wenn noch Überdeckung, harte Übergänge oder sichtbare Patch-Artefakte vorhanden sind, lokal innerhalb derselben ROI weiter korrigieren. Nicht sofort nach dem ersten Fehlversuch abbrechen. Der Task endet erst bei eindeutigem PASS oder wenn der gewählte deterministische Surface-Rebuild technisch nachweisbar keinen gültigen zusammenhängenden Körper erzeugen kann.
12. Erst bei eindeutigem Optik-PASS volle 6 Ansichten erzeugen und danach mit Split/CAD/FDM fortfahren.

## VERBOTEN
- neuer Seed / neuer Trellis-Vollaufbau
- neue Figur / Neudesign
- Änderung außerhalb ROI
- Veränderung von Nase, Augen, Ohren, Füßen als kreative Korrektur
- sichtbare Ersatzflächen mit Fächer-/Block-/Cap-Charakter
- mehrere konkurrierende Formvarianten ohne klare deterministische Auswahl
- Fortsetzung zu Split/STL trotz Restüberdeckung im Gesicht
- PASS nur aufgrund Mesh-Validator ohne optische Übereinstimmung

## OPTIK-GATE – BINÄR
PASS nur wenn ALLE Punkte erfüllt sind:
- Gesicht vollständig frei und rundlich wie REF-CLEAN.
- Stirn frei.
- beide Augen frei.
- Schnauze und Nase frei.
- beide Ohren frei.
- keine Blatt-/Stachelgeometrie auf der Körperseite der REF-SEAM.
- Rücken hinter REF-SEAM unverändert.
- genau ein sichtbares Ahornblatt.
- lokaler Übergang glatt/organisch ohne sichtbare Reparatur.
- reale 3D-Geometrie, keine 2D-Retusche.

Bei FAIL: keine STL, keine Hohlschalen, kein Connector. Konkrete geometrische Ursache dokumentieren.
Bei PASS: erst dann unverändert REF-SEAM-Split, 1.6-mm-Hohlschalen, Ø10.0 x 20.0-mm-Klebeverbinder und vollständige technische Validierung.

## PFLICHTNACHWEISE
- Hash-Gate Seed-42 / REF-CLEAN / REF-SEAM
- ROI-Definition und Diagnosebild
- maschinenlesbarer Nachweis: außerhalb ROI keine Vertex-Koordinaten geändert
- reale 3/4-Front-, Links-, Rechts-, Hinten-, Oben-, Unten-Renders
- SOLL/IST-Gegenüberstellung mit REF-CLEAN und REF-SEAM
- Geometrieprüfung auf offene Kanten, Selbstschnitte, degenerierte Dreiecke
- Revisionsbericht: GEÄNDERT / UNVERÄNDERT / ENTFERNT / OFFEN
- maschinenlesbarer Ergebnisstatus

Keine finale Nutzerfreigabe behaupten.
