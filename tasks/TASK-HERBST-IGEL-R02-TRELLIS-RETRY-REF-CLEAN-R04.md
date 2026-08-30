# TASK-HERBST-IGEL-R02-TRELLIS-RETRY-REF-CLEAN-R04

Status: FREIGEGEBEN
Datum: 2026-08-30

## Zweck
Technisch notwendiger Retry von `TASK-HERBST-IGEL-R02-TRELLIS-REBUILD.md` nach dem ausschließlich technischen Transportfehler der R03-Primärreferenz. R02 bleibt die Produktrevision; R04 bezeichnet nur den Retry/Referenztransport.

## Verbindliche Referenzen
1. Primäre Optik/Formquelle für Trellis: `tasks/TASK-HERBST-IGEL-R02-REF-CLEAN-R04.jpg.b64`
   - Repository-Inhalt ist Base64-Text.
   - Vor Verwendung Base64 dekodieren.
   - dekodiert exakt 512 × 512 px, RGB JPEG.
   - erwartete dekodierte Größe exakt `31028` Byte.
   - erwarteter SHA-256 exakt `1b039abd4e83ddeff1fe707d07bca5d492b3fbb956857599936b317cf22b4a29`.
   - strikter vollständiger JPEG-Decode muss PASS sein.
   - Autorisierung: `tasks/TASK-HERBST-IGEL-R02-REF-CLEAN-AUTH-R04.md`.
2. Trennlinie weiterhin ausschließlich: `tasks/TASK-HERBST-IGEL-R01-REF-SEAM.jpg.b64`
   - dekodierter SHA-256 exakt `b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4`.
3. Alte beschädigte R01-REF-CLEAN und rohe R03-JPG NICHT als Formquelle verwenden.
4. Sekundäre Multiansicht weiterhin NICHT als primäre Formquelle verwenden.

## Arbeitsreihenfolge – verbindlich
1. R04-REF-CLEAN Base64 dekodieren, Dateigröße, SHA-256, JPEG-Signatur, 512×512-Abmessungen und vollständigen strikten Decode prüfen.
2. Wenn dieser reine Transportcheck fehlschlägt, Fehler technisch untersuchen und – sofern ohne Änderung der Nutzerreferenz möglich – selbst beheben. Nur wenn die autorisierte Bildidentität real nicht herstellbar ist, STOPP.
3. Trellis nativ als organische Formbasis verwenden; tatsächlichen Trellis-Aufruf, GPU, Seed, Auflösung und Rohmesh dokumentieren.
4. Rohmesh aus tatsächlicher Trellis-Ausgabe rendern: mindestens 3/4 vorne, beide Seiten, hinten, oben, unten.
5. OPTIK-GATE gegen R04-REF-CLEAN durchführen, bevor CAD/FDM-Technik ergänzt wird.
6. Nur bei eindeutigem OPTIK-PASS technische Aufbereitung fortsetzen.
7. Bei OPTIK-FAIL STOPP; keine parametrische Ersatzfigur und keine technische Schönrechnung.

## Optik-Gate
Der erste Gesamteindruck muss eindeutig dem freigegebenen Herbst-Igel entsprechen, nicht Maus/Hamster/Ratte/Bürste/Blüte.
Prüfen und dokumentieren:
- kompakte, bodennahe Igel-Silhouette
- großer rundlicher Körper mit klar erkennbarem hellem Gesicht
- kurze weiche Igelschnauze mit schwarzer Nase
- zwei kleine runde Ohren
- große runde Augen als Geometrie
- vier kurze sichtbare Füße / bodennahe Haltung
- gewölbter Rücken mit deutlich einzelnen überlappenden Blatt-/Stachelformen
- Blatt-/Stachelrichtung und Dichte wie Referenz
- genau ein sichtbares dekoratives Ahornblatt auf der gezeigten Seite
- keine zweite erfundene Ahornblatt-Dekoration auf der Gegenseite
- natürliche Grenze Körper/Rücken entsprechend REF-SEAM

## Technik – bei Optik-PASS unverändert
- insgesamt genau 2 druckbare Bauteile
- Körper/Vorderteil: PLA Matt Desert Tan
- Rücken/Stachel-/Blätterschale: PLA Metal Kupfer
- beide als Hohlschalen
- Nenn-Grundwandstärke 1,6 mm
- Zielgröße ca. 200 mm maximale Gesamtausdehnung, proportional skalieren
- eine einzelne mittige innenliegende Klebe-Steckverbindung
- Zapfen Ø10,0 mm exakt
- wirksamer Eingriff 20,0 mm exakt
- Gegenaufnahme technisch für 0,4-mm-FDM/Klebespiel bestimmen und dokumentieren
- keine Rastung, Schnappfunktion, Konizität, Klemmfunktion, Magnete, Zusatzpins oder äußere Verstärkung
- Verbindung außen unsichtbar
- Augen/Nase als Körpergeometrie; Nutzer bemalt sie nach Druck
- 0,4-mm-Düse
- Ziel-Layerhöhe 0,12 mm; adaptiv bis 0,08 mm erlaubt
- Support nur technisch nötig, vollständig erreichbar und entfernbar
- keine Zusatzfunktionen, Sockel, Haken, Ösen oder Halterungen

## Technische Validierung – erst nach Optik-PASS
- beide STL separat watertight und 2-manifold
- echte Selbstschnittprüfung, nicht nur aus Watertight/Manifold ableiten
- keine offenen Kanten oder ungewollten Mehrfachschalen
- Grundwandstärke und Minimum messen
- Ø10,0-mm-Zapfen aus realem STL messen
- 20,0-mm-Eingriff aus realem STL messen
- Aufnahme, radiales/diametrales Spiel und Axialspiel messen
- vollständiger Eingriff kollisionsfrei
- keine sichtbare Beule/Durchzeichnung der Innenverstärkung
- keine eingeschlossenen Supportbereiche
- Gesamtmaß dokumentieren

## Pflichtausgabe bei PASS
- Trellis-Rohmesh unverändert archivieren
- reproduzierbarer CAD/Processing-Quellstand
- `herbst-igel-r02-koerper.stl`
- `herbst-igel-r02-ruecken.stl`
- Montage-GLB oder 3MF
- echte Geometrierender: 3/4 vorne, beide Seiten, hinten, oben, unten
- SOLL/IST Optikbericht
- technische Validierung
- maschinenlesbarer Revisions-/Validierungsreport
- GEÄNDERT / UNVERÄNDERT / ENTFERNT / OFFEN dokumentieren

## Freigabe
Ein technisches PASS ist keine Produktfreigabe. Finale optische und Druckfreigabe bleibt beim Nutzer nach unabhängiger ChatGPT-SOLL/IST-Prüfung.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`
