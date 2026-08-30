# TASK-HERBST-IGEL-R02-TRELLIS-RETRY-REF-CLEAN-R05

Status: FREIGEGEBEN
Datum: 2026-08-30

## Zweck
Minimaler technischer Retry des R04-STOPPs. Der STOPP wurde durch eine gekuerzte Referenzdatei im Transport verursacht, nicht durch eine Produktentscheidung. R02 bleibt die Produktrevision; vorherige STOPP-Staende nicht ueberschreiben.

## Verbindliche Primaerreferenz
1. Lies `tasks/TASK-HERBST-IGEL-R02-REF-CLEAN-AUTH-R05.md`.
2. Konkatenieren exakt in numerischer Reihenfolge, ohne zusaetzliche Zeichen oder Zeilenumbrueche:
   `tasks/TASK-HERBST-IGEL-R02-REF-CLEAN-R05.part01.b64` bis `part08.b64`.
3. Base64 genau einmal dekodieren.
4. Vor jeder weiteren Arbeit zwingend pruefen:
   - 40823 Bytes
   - SHA-256 `2d127f873be82c7247f4c67345821d68edd2a0f8a0c2dab20d24a5e27a3ce8a2`
   - JPEG 512 x 512 RGB
   - strikter Decode PASS
5. Bei Abweichung den Transport/Concat/Decode technisch selbst pruefen und minimal korrigieren. Nur wenn die autorisierte Bildidentitaet real nicht wiederherstellbar ist, STOPP.
6. Alte korrupte R03/R04-Referenzdateien nicht als Formquelle verwenden.
7. Trennlinie weiterhin ausschliesslich aus `tasks/TASK-HERBST-IGEL-R01-REF-SEAM.jpg.b64`, dekodierter SHA-256 `b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4`.

## Verbindlicher Workflow
- Trellis nativ als organische Formbasis nutzen; Tool, GPU, Seed, Aufloesung und Rohmesh dokumentieren.
- Unveraendertes Trellis-Rohmesh archivieren.
- Echte Rohmesh-Renders erzeugen: mindestens 3/4 vorne, links, rechts, hinten, oben, unten.
- Vor CAD/FDM-Aufbereitung zwingend OPTIK-GATE gegen die autorisierte REF-CLEAN und REF-SEAM.
- Bei OPTIK-FAIL STOPP; keine parametrische Ersatzfigur, kein technisches Schoenrechnen.
- Nur bei eindeutigem OPTIK-PASS technische Aufbereitung fortsetzen.

## SOLL fuer das Optik-Gate
Der erste Gesamteindruck muss eindeutig der freigegebenen Igelreferenz entsprechen:
- kompakte, bodennahe Igel-Silhouette
- grosser rundlicher Koerper mit klar erkennbarem hellem Gesicht
- kurze weiche Igelschnauze mit schwarzer Nase
- zwei kleine runde Ohren
- grosse runde Augen als Geometrie
- vier kurze sichtbare Fuesse / bodennahe Haltung
- gewoelbter Ruecken mit deutlich einzelnen ueberlappenden Blatt-/Stachelformen
- Blatt-/Stachelrichtung und Dichte wie Referenz
- genau ein sichtbares dekoratives Ahornblatt auf der gezeigten Seite
- keine zweite erfundene Ahornblatt-Dekoration auf der Gegenseite
- natuerliche Grenze Koerper/Ruecken entsprechend REF-SEAM

## Technik nur nach Optik-PASS
Unveraendert aus R04/R03/R02 uebernehmen:
- genau 2 druckbare Bauteile
- Koerper/Vorderteil PLA Matt Desert Tan; Ruecken/Stachel-/Blaetterschale PLA Metal Kupfer
- beide Hohlschalen
- Nenn-Grundwandstaerke 1,6 mm
- Zielgroesse ca. 200 mm maximale Gesamtausdehnung, proportional
- eine einzelne mittige innenliegende Klebe-Steckverbindung
- Zapfen Durchmesser exakt 10,0 mm
- wirksamer Eingriff exakt 20,0 mm
- Gegenaufnahme fuer 0,4-mm-FDM/Klebespiel technisch bestimmen und dokumentieren
- keine Rastung, Schnappfunktion, Konizitaet, Klemmfunktion, Magnete, Zusatzpins oder aeussere Verstaerkung
- Verbindung aussen unsichtbar
- Augen/Nase als Koerpergeometrie; Nutzer bemalt nach Druck
- 0,4-mm-Duese; Ziel-Layer 0,12 mm, adaptiv bis 0,08 mm erlaubt
- Support nur technisch noetig, vollstaendig erreichbar/entfernbar
- keine Zusatzfunktionen, Sockel, Haken, Oesen oder Halterungen

## Technische Validierung nur nach Optik-PASS
- beide STL separat watertight und 2-manifold
- echte Selbstschnittpruefung
- keine offenen Kanten oder ungewollten Mehrfachschalen
- Grundwandstaerke und Minimum messen
- realen STL-Zapfen 10,0 mm und Eingriff 20,0 mm messen
- Aufnahme, radiales/diametrales Spiel und Axialspiel messen
- vollstaendiger Eingriff kollisionsfrei
- keine sichtbare Beule/Durchzeichnung der Innenverstaerkung
- keine eingeschlossenen Supportbereiche
- Gesamtmass dokumentieren

## Pflichtausgabe bei PASS
Trellis-Rohmesh, reproduzierbarer Processing/CAD-Quellstand, `herbst-igel-r02-koerper.stl`, `herbst-igel-r02-ruecken.stl`, Montage-GLB oder 3MF, echte Geometrierender aller geforderten Ansichten, SOLL/IST-Optikbericht, technische Validierung und maschinenlesbarer Ergebnisreport.

Technisches PASS ist keine finale Produktfreigabe. Finale optische und Druckfreigabe bleibt beim Nutzer nach unabhaengiger ChatGPT-SOLL/IST-Pruefung.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`
