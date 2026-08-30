# TASK-HERBST-IGEL-R01

Status: DRAFT – VOLLSTAENDIG VORBEREITET, NOCH NICHT FREIGEGEBEN / NICHT QUEUEN
Datum: 2026-08-30

## FREIGABE-GATE
Diese Task-Datei darf vorbereitet und im Repository gespeichert werden, aber **nicht** in `tasks/TASK_QUEUE.txt` eingereiht werden, bis der Nutzer ausdruecklich sagt: **„gib es weiter an Ruediger“**.
Bis dahin keine Konstruktion und keine Druckdateien erzeugen.

## PROJEKTZIEL
Herbstliche Igel-Dekoration fuer FDM-Druck. Der fertige Igel soll optisch so nah wie technisch druckbar am autoritativen Referenzbild liegen. Die sichtbare Form, Proportion, Gesichtsausdruck, Koerperhaltung, Stacheln/Blattstruktur und die einzelne sichtbare dekorative Ahornblatt-Geometrie sind zu schuetzen.

Das Modell besteht aus zwei separat druckbaren, hohlen Bauteilen:
1. Vorderteil / Koerper in PLA Matt Desert Tan.
2. Hinterteil / kompletter Stachel- und Blaetterruecken in PLA Metal Kupfer.

Beide Teile werden nach dem Druck vom Nutzer zusammengesteckt und verklebt.

## REFERENZEN UND PRIORITAET
Die Referenzdateien liegen als Base64-Textdateien neben dieser Task und muessen vor Nutzung dekodiert werden. SHA-256 und Dekodierhinweise stehen in `tasks/TASK-HERBST-IGEL-R01-REFERENCE-MANIFEST.md`.

Prioritaet bei Widerspruechen:
1. `TASK-HERBST-IGEL-R01-REF-SEAM.jpg` – autoritativ fuer Trennlinie.
2. `TASK-HERBST-IGEL-R01-REF-CLEAN.jpg` – autoritativ fuer sichtbare Optik, Proportion und Details.
3. `TASK-HERBST-IGEL-R01-REF-MULTIVIEW-SECONDARY.jpg` – nur sekundaere Orientierung fuer Silhouette/unsichtbare Seiten; KI-generiert und **nicht** autoritativ fuer Detailplatzierung.

Wenn die Sekundaer-Multiansicht dem autoritativen Referenzbild widerspricht, ist sie zu verwerfen. Insbesondere darf aus der Sekundaeransicht **kein zweites dekoratives Ahornblatt** erfunden oder gespiegelt werden.

## VERBINDLICH – OPTIK UND FORM
- Motiv: niedlicher Herbst-Igel genau im Charakter des Referenzbilds.
- Haltung: stehend/sitzend auf den eigenen Fuessen wie im Referenzbild; kein separater Sockel.
- Ziel-Gesamtgroesse: **ca. 200 mm maximale Gesamtausdehnung**. Das Referenzmodell proportional und gleichmaessig skalieren; keine willkuerlichen Breiten-/Hoehen-/Tiefenmasse erfinden.
- Gesicht, Ohren, Schnauze, Bauch und Fuesse gehoeren zum Desert-Tan-Koerperteil.
- Augen und Nase als druckbare Koerpergeometrie ausbilden, damit sie nachtraeglich bemalt werden koennen.
- Augen und Nase werden vom Nutzer nach dem Druck bemalt; keine dritte Filamentfarbe dafuer vorsehen.
- Stacheln/Blaetter als deutlich einzelne, ueberlappende, organische Blatt-/Stachelformen wie im Referenzbild.
- Sichtbare Oberflaechenstruktur des Koerpers und die feinen Rillen/Adern der Stacheln/Blaetter erhalten, soweit mit 0,4-mm-FDM sinnvoll reproduzierbar.
- Die im autoritativen Bild sichtbare dekorative Ahornblatt-Geometrie auf der gezeigten Seite erhalten.
- Auf der nicht sichtbaren Gegenseite keine neue eigenstaendige Dekoration erfinden; das normale Stachel-/Blattmuster organisch fortsetzen.
- Keine neuen Funktionen, Halterungen, Sockel, Oesen, Haken, Rastungen, Anschlaege oder sonstige Zusatzgeometrie.

## VERBINDLICH – BAUTEILAUFTEILUNG
- Insgesamt **2 Bauteile**.
- Bauteil 1: Vorderteil / Koerper, hohle Schale, PLA Matt Desert Tan.
- Bauteil 2: Hinterteil / Stachel- und Blaetterruecken, hohle Schale, PLA Metal Kupfer.
- Trennlinie exakt nach der vom Nutzer blau markierten Kontur im Referenzbild.
- Die Trennlinie folgt der natuerlichen Grenze zwischen hellem Koerper und kupferfarbenem Stachel-/Blaetterruecken.
- Nach Montage soll die Trennstelle von aussen konstruktiv nicht auffallen.
- Keine sichtbare Steckgeometrie, keine aeusseren Wuelste/Absätze und keine zusaetzliche sichtbare Verstärkung.

## VERBINDLICH – HOHLBAUWEISE / WANDSTAERKE
- Beide Bauteile als **Hohlschalen** ausfuehren; keine massive Vollkoerperkonstruktion.
- Nenn-Grundwandstaerke: **1,6 mm** bei beiden Schalen.
- Der Stachel-/Blaetterruecken darf durch die eigentliche sichtbare Stachel-/Blattgeometrie lokal dicker werden.
- Keine unnoetige massive Materialanhaeufung.
- Innen darf die Steckaufnahme lokal technisch notwendig verstaerkt werden, solange dies von aussen vollstaendig unsichtbar bleibt und die Aussenform nicht veraendert.

## VERBINDLICH – STECKVERBINDUNG
- Eine einzelne **mittige** Steckverbindung zwischen den beiden Schalen.
- Steg/Zapfen: **Durchmesser exakt 10,0 mm**.
- Wirksame Einstecktiefe: **20,0 mm**.
- Verbindung wird vom Nutzer nach dem Zusammenstecken **verklebt**.
- Steckverbindung vollstaendig innenliegend und von aussen nicht sichtbar.
- Keine Rastung, keine Schnappfunktion, keine Konizitaet und keine Klemmfunktion erfinden.
- Welches der beiden Bauteile den Zapfen und welches die Aufnahme traegt, darf Ruediger nach Druckorientierung, Bauraum und Supportzugaenglichkeit technisch festlegen; die Entscheidung dokumentieren.
- Das notwendige FDM-/Klebespiel der Gegenaufnahme technisch aus Material, 0,4-mm-Duese und realer Druckbarkeit bestimmen und dokumentieren. Dieses Spiel ist **kein Nutzer-Mass** und darf nicht als solches ausgegeben werden.
- Die Aufnahme muss den 20-mm-Eingriff sicher ermoeglichen.
- Lokale Innenverstaerkung um Zapfen/Aufnahme nur im technisch notwendigen Umfang.

## MATERIAL / DRUCKZIEL
- Druckverfahren: FDM.
- Duesendurchmesser: **0,4 mm**.
- Koerper: **PLA Matt Desert Tan**.
- Ruecken/Stacheln/Blaetter: **PLA Metal Kupfer**.
- Ziel-Layerhoehe fuer schoene Oberflaeche: **0,12 mm**.
- Variable/adaptive Layerhoehe bis **0,08 mm** ist technisch zulaessig, wenn sie sichtbar runde/gekruemmte Bereiche verbessert und keine Geometrie veraendert.
- Ziel: moeglichst glatte Wirkung mit wenig sichtbarer Stufigkeit bei Erhalt der Oberflaechenstruktur.
- Support: **nur so viel wie technisch notwendig**.
- Support in geschlossenen/unzugaenglichen Hohlraeumen ist unzulaessig.
- Druckorientierung je Bauteil so bestimmen, dass sichtbare Oberflaechen geschuetzt, Support minimiert und vorhandener Support nach dem Druck erreichbar und entfernbar ist.
- Keine Formveraenderung nur zur Supportvermeidung; Konflikte melden.

## TECHNISCH NOTWENDIG – VON RUEDIGER ZU BESTIMMEN
- Exakte CAD-Masse ausser der maximalen Gesamtausdehnung aus der autoritativen Referenz proportional ableiten.
- Exakte Lage/Achse der mittigen Steckverbindung innerhalb der realen finalen Innengeometrie bestimmen.
- Zuordnung Zapfen/Aufnahme zu Vorder- oder Rueckteil anhand FDM-Tauglichkeit entscheiden und begruenden.
- Klebe-/Montagespiel der Ø10-mm-Verbindung bestimmen und messen.
- Innenverstaerkung so klein wie moeglich dimensionieren, aber ausreichend gegen Ausbrechen der 1,6-mm-Schale.
- Druckorientierung und minimalen Support je Bauteil bestimmen.
- Detailstaerke der Stacheln/Blaetter gegen 0,4-mm-Duese pruefen, ohne den sichtbaren Charakter unnoetig zu vereinfachen.

## NICHT ERLAUBT
- Keine Aenderung der Ø10,0-mm-Zapfenvorgabe.
- Keine Aenderung der 20,0-mm-Einstecktiefe.
- Keine Aenderung der 1,6-mm-Grundwandstaerke ohne vorherigen Konfliktbericht.
- Keine sichtbare Verbindungstechnik.
- Keine zusaetzlichen dekorativen Blaetter/Accessoires erfinden.
- Keine dritte Druckfarbe fuer Augen/Nase.
- Keine Rast-, Schnapp- oder Klemmfunktion.
- Keine massive Vollfuellung.
- Keine willkuerlich erfundenen Aussenmasse statt proportionaler Referenzskalierung.

## AUSGABE / DATEIEN
R01 als eigene Revision erzeugen; bestehende Revisionen niemals ueberschreiben.

Mindestens liefern:
1. Reproduzierbarer parametrischer/CAD-Quellstand.
2. `herbst-igel-r01-koerper.stl`
3. `herbst-igel-r01-ruecken.stl`
4. Montage-/Sichtpruefdatei als 3MF oder GLB mit beiden Teilen in korrekter Einbaulage.
5. Render aus der tatsaechlichen finalen Geometrie: mindestens 3/4 vorne, beide Seiten, hinten, oben und unten.
6. SOLL/IST-Bericht.
7. Maschinenlesbarer Validierungs-/Revisionsbericht.

## VALIDIERUNG – GEOMETRIE
- Beide STL separat watertight und 2-manifold.
- Keine Selbstschnitte, offenen Kanten oder ungewollten Mehrfachschalen.
- Je Bauteil die reale Grundwandstaerke pruefen und Minimum dokumentieren.
- Exakten Ø10,0-mm-Zapfendurchmesser messen.
- Effektive Einstecktiefe 20,0 mm messen.
- Reales Aufnahmemass und daraus resultierendes Spiel dokumentieren.
- Steckverbindung im Montagezustand auf Kollision und vollstaendigen 20-mm-Eingriff pruefen.
- Keine sichtbare Durchzeichnung/Beule der Innenverstaerkung auf der Aussenhaut.
- Keine eingeschlossenen Supportbereiche.
- Maximalmass des zusammengesetzten Modells ca. 200 mm dokumentieren.

## VALIDIERUNG – SOLL/IST OPTIK
Gegen `REF-CLEAN` und `REF-SEAM` pruefen:
- allgemeine Silhouette und Proportion,
- Gesichtsausdruck und Schnauzenform,
- Ohrform und -position,
- Bauch/Fuesse/Haltung,
- Verlauf des Stachel-/Blaetterrueckens,
- Dichte, Richtung und Ueberlappung der Stacheln,
- sichtbares dekoratives Ahornblatt,
- Trennlinie entlang der blauen Nutzer-Markierung,
- keine sichtbaren Verbindungsmerkmale.

Abweichungen klar auflisten. Ein formal gueltiges Mesh ist keine optische Freigabe.

## REVISIONSDOKUMENTATION
**GEAENDERT:** neue R01-Konstruktion fuer Herbst-Igel gemaess dieser Task.

**UNVERAENDERT / ZU SCHUETZEN:** autoritative Referenzoptik, zwei Hohlschalen, Farben, Ø10-mm-Stecksteg, 20-mm-Eingriff, 1,6-mm-Grundwand, innenliegende Klebeverbindung, keine sichtbare Verbindung.

**ENTFERNT:** nichts; keine stillen Nebenfunktionen.

**OFFEN:** finale Produkt-/Druckfreigabe nach ChatGPT-SOLL/IST und Nutzerpruefung.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false` fuer die Konstruktion **nach ausdruecklicher Queue-Freigabe**. Technische Detailentscheidungen sind oben begrenzt. Wenn eine verbindliche Vorgabe nicht gleichzeitig erfuellbar ist: STOPP und Konflikt melden.
