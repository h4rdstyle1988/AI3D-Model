# TASK-HERBST-IGEL-R02-TRELLIS-REBUILD

Status: FREIGEGEBEN
Datum: 2026-08-30

## AUSGANGSLAGE / FEHLER
Die R01-Konstruktion ist als Formbasis verworfen. Sie ist technisch weitgehend valide, verfehlt aber die verbindliche Nutzeridee deutlich: Der sichtbare Charakter wirkt wie eine dicke Maus statt wie der freigegebene Herbst-Igel.

Dieser Fehler ist ein OPTIK-FAIL. Ein technisches PASS ersetzt keine visuelle Übereinstimmung.

## ZIEL
Den Herbst-Igel neu aufbauen, diesmal mit Trellis als organischer Ausgangsgeometrie. Die Figur muss vor der technischen Aufbereitung optisch eindeutig dem autoritativen Referenz-Igel entsprechen.

## VERBINDLICHE REFERENZEN
1. Optik / Charakter: `tasks/TASK-HERBST-IGEL-R01-REF-CLEAN.jpg.b64`
   - dekodierter SHA-256 exakt `f3017009739284e1bfd6e8502e9d9258eb74dbf52074c425a73ff41fc8bac328`
2. Trennlinie: `tasks/TASK-HERBST-IGEL-R01-REF-SEAM.jpg.b64`
   - dekodierter SHA-256 exakt `b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4`
3. Sekundäre Multiansicht NICHT als primäre Formquelle verwenden.

Vor Konstruktion beide autoritativen Referenzen dekodieren und Hashes prüfen. Bei Mismatch: STOPP.

## VERBINDLICHER WORKFLOW
1. **Trellis MUSS als Formbasis verwendet werden.**
2. Aus REF-CLEAN eine organische 3D-Grundform rekonstruieren.
3. Trellis-Ausgabe bereinigen, ohne den sichtbaren Charakter zu verfälschen.
4. **OPTIK-GATE vor jeder technischen Ausarbeitung:**
   - allgemeine Silhouette
   - Kopf-/Körperproportion
   - Schnauzenform
   - Ohrform und -position
   - Bauch/Füße/Haltung
   - Verlauf des Stachel-/Blätterrückens
   - Dichte/Richtung/Überlappung der Stacheln/Blätter
   - genau ein sichtbares dekoratives Ahornblatt
   - Gesamteindruck eindeutig Igel, nicht Maus/Hamster/Ratte
5. Wenn dieses Optik-Gate nicht eindeutig PASS ist: **STOPP. Keine parametrische Ersatzfigur erzeugen und keinen schlechten Trellis-Entwurf technisch schönrechnen.**
6. Erst nach Optik-PASS technische Aufbereitung für FDM durchführen.

## VERBINDLICH – TECHNIK UNVERÄNDERT
- Insgesamt 2 Bauteile.
- Vorderteil/Körper als Hohlschale in PLA Matt Desert Tan.
- Hinterteil/Stachel- und Blätterrücken als Hohlschale in PLA Metal Kupfer.
- Ziel-Gesamtgröße ca. 200 mm maximale Gesamtausdehnung, proportional skalieren.
- Grundwandstärke 1,6 mm bei beiden Schalen.
- Trennlinie entlang REF-SEAM / blauer Nutzerkontur.
- Nach Montage soll die Trennstelle außen konstruktiv nicht auffallen.
- Eine einzelne mittige, vollständig innenliegende Steckverbindung.
- Zapfen Durchmesser exakt 10,0 mm.
- Wirksame Einstecktiefe exakt 20,0 mm.
- Verbindung wird verklebt.
- Keine Rastung, Schnappfunktion, Konizität, Klemmfunktion, Magnete oder zusätzliche Führungen.
- FDM-Klebespiel der Aufnahme technisch bestimmen und dokumentieren.
- Augen und Nase als Körpergeometrie; nach dem Druck bemalt, keine dritte Filamentfarbe.
- Keine Zusatzfunktionen, Sockel, Halter, Ösen, Haken, Anschläge oder neue Dekoration.
- Kein zweites Ahornblatt erfinden.
- Düse 0,4 mm.
- Ziel-Layerhöhe 0,12 mm; adaptiv bis 0,08 mm auf sichtbaren Rundungen zulässig.
- Support nur technisch notwendig, erreichbar und entfernbar; kein eingeschlossener Support.

## TRELLIS-NACHWEIS PFLICHT
Im Ergebnis dokumentieren:
- welches Trellis-/Hunyuan3D-Tool tatsächlich ausgeführt wurde,
- konkrete Kommandozeile / Reproduktionsweg,
- Eingabereferenz,
- erzeugte Roh-Geometrie als eigenes Zwischenartefakt,
- danach ausgeführte Mesh-/CAD-Aufbereitung.

Ein rein parametrischer Python-Neubau ohne Trellis erfüllt diesen Auftrag NICHT.

## OPTISCHE VALIDIERUNG PFLICHT
Renders aus der tatsächlichen finalen Geometrie erzeugen:
- 3/4 vorne
- sichtbare Seite
- Gegenseite
- hinten
- oben
- unten

SOLL/IST direkt gegen REF-CLEAN und REF-SEAM dokumentieren. Abweichungen klar benennen. Mesh-Gültigkeit ist keine optische Freigabe.

## TECHNISCHE VALIDIERUNG PFLICHT
- beide STL separat watertight
- 2-manifold
- keine offenen Kanten
- keine ungewollten Mehrfachschalen
- echte Selbstschnittprüfung oder belastbarer externer/algorithmischer Nachweis; Manifold/Watertight allein reicht ausdrücklich NICHT
- reale Grundwandstärke und Minimum dokumentieren
- Ø10,0-mm-Zapfen messen
- 20,0-mm-Eingriff messen
- Aufnahme und Spiel messen
- Kollision bei vollständigem Eingriff prüfen
- keine sichtbare Beule/Durchzeichnung innerer Verstärkung
- keine eingeschlossenen Supportbereiche
- maximales Gesamtmaß dokumentieren

## AUSGABE / REVISION
Neue Revision **R02**. R01 nicht überschreiben.

Mindestens liefern:
1. Trellis-Rohmesh / rekonstruierte Ausgangsgeometrie
2. reproduzierbarer Trellis-Aufruf / Reproduktionsbeschreibung
3. reproduzierbarer CAD-/Mesh-Quellstand der technischen Aufbereitung
4. `herbst-igel-r02-koerper.stl`
5. `herbst-igel-r02-ruecken.stl`
6. Montage-/Sichtprüfdatei als GLB oder 3MF
7. Pflicht-Render aus finaler Geometrie
8. SOLL/IST-Bericht mit separatem OPTIK-GATE
9. maschinenlesbarer Validierungs-/Revisionsbericht

## REVISIONSDOKUMENTATION
**GEÄNDERT:** Formbasis R01 verworfen; R02 wird organisch über Trellis rekonstruiert und erst danach technisch aufbereitet.

**UNVERÄNDERT:** Referenzoptik, 2 Hohlschalen, Materialien, ca. 200 mm, 1,6 mm Grundwand, Ø10,0-mm-Zapfen, 20,0-mm-Eingriff, Klebeverbindung, Trennlinie, keine sichtbare Verbindung, keine Zusatzfunktionen.

**ENTFERNT:** Parametrische R01-Form als Ausgangsbasis.

**OFFEN:** finale optische Produktfreigabe durch Nutzer nach ChatGPT-SOLL/IST-Prüfung.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`
