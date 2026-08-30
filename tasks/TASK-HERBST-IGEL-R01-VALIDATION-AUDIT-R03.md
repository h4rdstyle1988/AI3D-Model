# TASK-HERBST-IGEL-R01-VALIDATION-AUDIT-R03

Status: FREIGEGEBEN
Datum: 2026-08-30

## Zweck
Reiner technischer Nachaudit des bereits erzeugten Herbst-Igel-R01-Ergebnisses aus Branch `ruediger/task-herbst-igel-r01-retry-ref-auth-r02-09cb6285`, Ergebniscommit `7b825beac856c0fee120bf080a9b747cb6418313`.

Keine Produktfunktion, kein Nutzermaß und keine sichtbare Geometrie ändern. Dieser Auftrag dient ausschließlich dazu, Lücken der bisherigen Validierung zu schließen und eine belastbare SOLL/IST-Prüfbasis zu erzeugen.

## Autoritative Produktvorgaben
Unverändert gemäß:
- `tasks/TASK-HERBST-IGEL-R01.md`
- `tasks/TASK-HERBST-IGEL-R01-RETRY-REF-AUTH-R02.md`

Autoritative Referenzen unverändert:
- REF-CLEAN SHA-256 `f3017009739284e1bfd6e8502e9d9258eb74dbf52074c425a73ff41fc8bac328`
- REF-SEAM SHA-256 `b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4`
- Sekundäre Multiansicht NICHT verwenden.

## Ausgangsergebnis
Prüfe exakt die beiden STL und die Montage-/Renderdaten aus Ergebniscommit `7b825beac856c0fee120bf080a9b747cb6418313`. Keine Neugenerierung oder Geometrieänderung, solange der Audit nicht einen echten technischen Fehler nachweist.

## Pflichtprüfung 1 – echte Selbstschnittprüfung
Die bisherige Aussage `self_intersections: PASS` darf NICHT nur aus watertight/2-manifold/single-component abgeleitet werden. Diese Eigenschaften beweisen Selbstschnittfreiheit nicht.

Führe eine direkte geometrische Selbstschnittprüfung beider finalen STL aus:
- Broadphase räumlich beschleunigt (BVH/AABB-tree/grid oder vorhandenes geeignetes Tool), keine naive O(n²)-Vollprüfung.
- Narrowphase tatsächlicher Dreieck-Dreieck-Schnitt.
- Topologisch benachbarte Dreiecke mit gemeinsamer Kante/Vertex korrekt von echten Selbstschnitten unterscheiden.
- Anzahl echter Selbstschnittpaare dokumentieren.
- PASS nur bei 0 echten Selbstschnittpaaren.
- Methode, Toleranzen und verwendetes Tool/Script dokumentieren.

## Pflichtprüfung 2 – Außenhaut / Innenverstärkung
Die verbindliche Vorgabe `keine sichtbare Durchzeichnung/Beule der Innenverstärkung auf der Außenhaut` separat prüfen.

Im Bereich von Zapfen/Aufnahme:
- Außenhaut gegen die Basis-Außenform ohne interne Anschlussverstärkung vergleichen oder einen äquivalenten reproduzierbaren geometrischen Differenztest ausführen.
- Maximale nach außen gerichtete Abweichung dokumentieren.
- PASS nur wenn keine durch die Innenverstärkung verursachte äußere Beule/Geometrieänderung vorhanden ist; reine Tessellierungsabweichung separat ausweisen.

## Pflichtprüfung 3 – Trennlinie / optische Prüfbasis
Die bisherige textliche Behauptung zur Trennlinie reicht nicht als Nachweis.

Erzeuge aus der TATSÄCHLICHEN finalen Geometrie eine reproduzierbare Prübdarstellung gegen REF-SEAM:
- Kamera/Projektion so an die autoritative Ansicht ausrichten, dass Silhouette/Orientierung sinnvoll vergleichbar sind.
- Final projizierte Trennlinie und blaue Nutzer-Markierung gemeinsam als Overlay darstellen.
- Datei: `outputs/herbst-igel-r01-audit-r03/seam-overlay.png`.
- Zusätzlich eine Vergleichstafel aus REF-CLEAN und finalem 3/4-Render erzeugen: `outputs/herbst-igel-r01-audit-r03/visual-compare.png`.
- Keine optische Nutzerfreigabe behaupten. Abweichungen sachlich dokumentieren.
- Wenn sinnvoll quantifizierbar: mittlere/maximale 2D-Abweichung der Trennlinie in Pixeln nach dokumentierter Ausrichtung ausgeben. Keine erfundene Präzision.

## Pflichtprüfung 4 – Task-Blob-Nachweis korrigieren
Im bisherigen Validator steht `task_blob_sha1 = 7834e73a...`, während der Git-Blob der freigegebenen Task `09cb6285e81881adb9d3811a118a7b73f706d83b` ist.

Ursache prüfen. Vermutung nur prüfen, nicht voraussetzen: Worktree-CRLF/LF-Konvertierung.

Für den Audit getrennt dokumentieren:
- Git-Repository-Blob-SHA der Task aus dem Commit/Tree.
- optionaler SHA der Worktree-Dateibytes separat und eindeutig benannt.
- Der Repository-Blob-Nachweis muss exakt `09cb6285e81881adb9d3811a118a7b73f706d83b` ergeben.

## Bereits bestätigte technische Werte erneut gegen finales STL querprüfen
Nur lesen/messen, nicht ändern:
- genau 2 Bauteile
- Ø10,0 mm Zapfen exakt
- 20,0 mm wirksamer Eingriff exakt
- Aufnahme Ø10,4 mm / Tiefe 20,4 mm als technisch festgelegtes Klebespiel
- Nenn-Grundwand 1,6 mm
- maximale Gesamtausdehnung ca. 200 mm
- keine zweite Ahornblatt-Dekoration
- keine Rastung/Klemmung/Konizität/Zusatzfunktion

## Ergebnislogik
- `PASS`: alle oben genannten technischen Auditpunkte nachweislich erfüllt.
- `STOPP`: echter technischer Fehler oder nicht nachweisbare verbindliche Geometrieanforderung.
- Keine finale Produkt-/Druckfreigabe behaupten; optische Endfreigabe bleibt beim Nutzer nach ChatGPT-SOLL/IST und Bildvergleich.

## Ausgabe
Neue Revision/Auditdateien anlegen, nichts Bestehendes überschreiben:
- `outputs/herbst-igel-r01-audit-r03/AUDIT-SOLL-IST.md`
- `outputs/herbst-igel-r01-audit-r03/audit-status.json`
- `outputs/herbst-igel-r01-audit-r03/self-intersection-report.json`
- `outputs/herbst-igel-r01-audit-r03/seam-overlay.png`
- `outputs/herbst-igel-r01-audit-r03/visual-compare.png`
- verwendete Audit-Scripts reproduzierbar mitliefern

## Revision
**GEÄNDERT:** nur Validierung/Nachweis.

**UNVERÄNDERT:** komplette R01-Produktgeometrie und alle Nutzeranforderungen.

**ENTFERNT:** nichts.

**OFFEN:** Nutzerfreigabe der Optik und realer Testdruck/Passprobe.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`
