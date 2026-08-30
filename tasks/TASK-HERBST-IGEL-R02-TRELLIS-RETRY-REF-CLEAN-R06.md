# TASK-HERBST-IGEL-R02-TRELLIS-RETRY-REF-CLEAN-R06

Status: FREIGEGEBEN
Datum: 2026-08-30

## Zweck
Technischer Retry nach R05-STOPP. Ursache war ausschließlich der beschädigte Referenztransport. R02 bleibt die Produktrevision. Keine Produktanforderung ändern.

## Primärreferenz
Lies `tasks/TASK-HERBST-IGEL-R02-REF-CLEAN-AUTH-R06.md` und rekonstruiere die dort definierte 512×512-JPEG-Datei aus den vier Base64-Teilen. Vor Trellis zwingend prüfen:
- 17.344 Byte
- SHA-256 `c1c9a5a094f1db2fd220f3433f83af8dedca780f56a4bf479eb8883432250859`
- JPEG RGB 512 × 512
- strikter Decode PASS

Bei Transportproblem technisch selbst prüfen und minimal korrigieren. Nur wenn die definierte Datei real nicht rekonstruierbar ist: STOPP.

## REF-SEAM
Unverändert ausschließlich `tasks/TASK-HERBST-IGEL-R01-REF-SEAM.jpg.b64`; dekodierter SHA-256 `b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4`.

## Verbindlicher Workflow
1. Primärreferenz rekonstruieren und verifizieren.
2. Trellis nativ als organische Formbasis verwenden; Tool, GPU, Seed, Auflösung und Rohmesh dokumentieren.
3. Unverändertes Trellis-Rohmesh archivieren.
4. Echte Rohmesh-Renders erzeugen: 3/4 vorne, links, rechts, hinten, oben, unten.
5. Vor CAD/FDM-Aufbereitung OPTIK-GATE gegen die vollständige Igelreferenz und REF-SEAM.
6. Bei OPTIK-FAIL STOPP; keine parametrische Ersatzfigur, kein technisches Schönrechnen.
7. Nur bei eindeutigem OPTIK-PASS technische Aufbereitung fortsetzen.

## Optik-Gate
Erster Gesamteindruck eindeutig Herbst-Igel wie Referenz, nicht Maus/Hamster/Ratte/Bürste/Blüte. Prüfen:
- kompakte bodennahe Silhouette
- rundlicher heller Körper / Gesicht
- kurze weiche Schnauze mit schwarzer Nase
- zwei kleine runde Ohren
- große runde Augen als Geometrie
- vier kurze sichtbare Füße
- gewölbter Rücken mit einzelnen überlappenden Blatt-/Stachelformen
- Blatt-/Stachelrichtung und Dichte wie Referenz
- genau ein sichtbares Ahornblatt auf der gezeigten Seite
- kein zweites erfundenes Ahornblatt
- natürliche Körper/Rücken-Grenze nach REF-SEAM

## Technik nur nach Optik-PASS
- genau 2 druckbare Bauteile
- Körper PLA Matt Desert Tan; Rücken PLA Metal Kupfer
- beide Hohlschalen
- Nenn-Grundwand 1,6 mm
- ca. 200 mm maximale Gesamtausdehnung, proportional
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

## Technische Validierung nur nach Optik-PASS
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

## Pflichtausgabe bei PASS
Trellis-Rohmesh, reproduzierbarer Processing/CAD-Quellstand, `herbst-igel-r02-koerper.stl`, `herbst-igel-r02-ruecken.stl`, Montage-GLB oder 3MF, echte Geometrierender aller Ansichten, SOLL/IST-Optikbericht, technische Validierung, maschinenlesbarer Ergebnisreport sowie GEÄNDERT / UNVERÄNDERT / ENTFERNT / OFFEN.

Technisches PASS ist keine finale Produktfreigabe. Finale optische und Druckfreigabe bleibt beim Nutzer nach unabhängiger ChatGPT-SOLL/IST-Prüfung.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`
