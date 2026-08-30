# TASK-HERBST-IGEL-R02-TRELLIS-OPTIK-RETRY-R07

Status: FREIGEGEBEN
Datum: 2026-08-30

## Zweck
Technischer Retry nach R06-STOPP am Optik-Gate. Keine Produktanforderung ändern. R02 bleibt die Produktrevision.

R06 hat Referenztransport und Trellis-Toolchain erfolgreich validiert, aber das einzelne Rohmesh mit Seed 42 hat die autoritative Optik nicht ausreichend getroffen: zu viele Blatt-/Stachelformen hängen über Stirn/Augen/Gesicht und überschreiten die natürliche Körper/Rücken-Grenze.

## Verbindliche Referenzen
- Primärreferenz unverändert aus `tasks/TASK-HERBST-IGEL-R02-REF-CLEAN-AUTH-R06.md` rekonstruieren und verifizieren.
- REF-SEAM unverändert ausschließlich `tasks/TASK-HERBST-IGEL-R01-REF-SEAM.jpg.b64`.
- Keine alte beschädigte REF-CLEAN und keine sekundäre Multiansicht als primäre Formquelle verwenden.

## Technischer Auftrag
1. Referenz-Gate erneut PASS nachweisen.
2. Trellis nativ verwenden.
3. Mehrere technisch unterschiedliche Trellis-Rohmesh-Kandidaten erzeugen, ohne die Produktidee oder Referenz zu ändern. Mindestens 4 Seeds testen, darunter Seed 42 als Vergleich. Weitere Seeds technisch wählen und dokumentieren.
4. Soweit die installierte Trellis-CLI dies unterstützt, darf die Hintergrundfreistellung/Preprocessing technisch variiert werden, jedoch nur zur besseren Rekonstruktion derselben Referenz. Kein inhaltliches Redesign, keine Bildmanipulation, kein Hinzufügen/Entfernen von Produktmerkmalen.
5. Jeden Kandidaten unverändert archivieren und aus echtem Rohmesh in 3/4 vorne, links, rechts, hinten, oben, unten rendern.
6. Kandidaten systematisch gegen REF-CLEAN und REF-SEAM vergleichen. Auswahlkriterium ist ausschließlich die beste Übereinstimmung mit der autoritativen Referenz.
7. Nur den besten Kandidaten für das verbindliche Optik-Gate verwenden.
8. Wenn mindestens ein Kandidat das Optik-Gate eindeutig besteht, technische CAD/FDM-Aufbereitung fortsetzen.
9. Wenn keiner besteht, STOPP mit Vergleichstabelle der getesteten Varianten. Keine parametrische Ersatzfigur und kein Schönrechnen.

## Optik-Gate – verbindlich
Erster Gesamteindruck eindeutig der freigegebene Herbst-Igel. Prüfen:
- kompakte bodennahe Silhouette
- rundlicher heller Körper / freie Gesichtsfläche
- kurze weiche Schnauze mit Nase
- zwei kleine runde Ohren
- große runde Augen als Geometrie
- vier kurze sichtbare Füße
- gewölbter Rücken mit einzelnen überlappenden Blatt-/Stachelformen
- Blatt-/Stachelrichtung und Dichte wie Referenz
- Blatt-/Stachelformen dürfen Stirn, Augen und Schnauze nicht unnatürlich überdecken
- genau ein sichtbares Ahornblatt auf der Referenzseite
- kein zweites erfundenes Ahornblatt
- natürliche Körper/Rücken-Grenze nach REF-SEAM

## Technik nur nach Optik-PASS
Unverändert aus R02/R06 übernehmen:
- genau 2 druckbare Hohlschalen
- Körper PLA Matt Desert Tan, Rücken PLA Metal Kupfer
- Nenn-Grundwand 1,6 mm
- ca. 200 mm maximale Gesamtausdehnung proportional
- eine mittige innenliegende Klebe-Steckverbindung
- Zapfen Ø10,0 mm exakt
- wirksamer Eingriff 20,0 mm exakt
- Gegenaufnahme technisch für 0,4-mm-FDM/Klebespiel bestimmen und dokumentieren
- keine Rastung, Schnappfunktion, Konizität, Klemmung, Magnete, Zusatzpins oder äußere Verstärkung
- Verbindung außen unsichtbar
- Augen/Nase als Körpergeometrie; Nutzer bemalt nach Druck
- 0,4-mm-Düse; Ziel-Layer 0,12 mm, adaptiv bis 0,08 mm erlaubt
- Support nur technisch nötig, vollständig erreichbar und entfernbar
- keine Zusatzfunktionen, Sockel, Haken, Ösen oder Halterungen

## Validierung nur nach Optik-PASS
- beide STL separat watertight und 2-manifold
- echte Selbstschnittprüfung
- keine offenen Kanten / ungewollten Mehrfachschalen
- Grundwandstärke und Minimum messen
- Ø10,0-mm-Zapfen und 20,0-mm-Eingriff aus realem STL messen
- Aufnahme, radiales/diametrales Spiel und Axialspiel messen
- vollständiger Eingriff kollisionsfrei
- keine sichtbare Durchzeichnung der Innenverstärkung
- keine eingeschlossenen Supportbereiche
- Gesamtmaß dokumentieren

## Revision
GEÄNDERT: nur technischer Trellis-Kandidatenvergleich zur Verbesserung der Referenztreue.
UNVERÄNDERT: sämtliche Nutzeranforderungen, Maße, Materialien, Trennlinie und Produktidee.
ENTFERNT: nichts.
OFFEN: finale Produkt-/Druckfreigabe ausschließlich nach unabhängiger ChatGPT-SOLL/IST-Prüfung und Nutzerfreigabe.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`
