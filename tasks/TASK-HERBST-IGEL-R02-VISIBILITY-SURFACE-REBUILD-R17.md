# TASK-HERBST-IGEL-R02-VISIBILITY-SURFACE-REBUILD-R17

## Status
Freigegebener rein technischer Folgeauftrag nach R16 Gate-2-FAIL.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

## Verbindliche Produktbasis
Unveraendert aus der zuletzt bestaetigten Herbst-Igel-Spezifikation und R16:
- Optik so nah wie technisch druckbar an REF-CLEAN.
- ca. 200 mm maximale Gesamtausdehnung, proportional.
- exakt zwei Druckteile: Koerper vorn PLA Matt Desert Tan, Ruecken-/Stachelschale PLA Metal Kupfer.
- beide hohl, nominal 1.6 mm Wand.
- REF-SEAM ist die autoritative Trennlinie.
- Gesicht frei; keine Blatt-/Stachelflaechen ueber Stirn, Augen oder Schnauze.
- genau ein sichtbares dekoratives Ahornblatt auf der Referenzseite, kein zweites erfundenes.
- ein zentraler interner Klebeverbinder Ø10.0 mm exakt, 20.0 mm Eingriff exakt.
- 0.4-mm-Duese; Ziel 0.12 mm Layer, adaptiv bis 0.08 mm erlaubt.
- keine zusaetzlichen Funktionen, Sockel, Halter, Fuehrungen oder Anschlaege.

## Nachgewiesene Ausgangslage
R16 hat Gate 1 erreicht, ist aber an Gate 2 gescheitert:
- Topologie der ausgewaehlten Envelope-Huelle PASS.
- Sichtbare Form FAIL, weil die projektions-/depth-map-basierte Volumenhuelle verschiedene sichtbare Tiefenlagen miteinander verbindet.
- Gesicht, Augen/Nase/Ohren, Blatt-/Stachelrelief und das einzelne Ahornblatt wurden dadurch unlesbar.
- Reine Aufloesungserhoehung dieser Methode ist nach R16 nicht zielfuehrend.

Die R16-Envelope-Methode darf daher NICHT erneut mit nur anderer Aufloesung wiederholt werden.

## Auftrag R17
Rekonstruiere eine einzige saubere aeussere Masterflaeche mit einer **sichtbarkeits- und oberflaechenorientierten Methode**, die nur nachweislich aeussere Quelloberflaechen als Formdaten benutzt und keine getrennten Tiefenlagen durch Volumenbelegung miteinander verbindet.

Technisch bevorzugter Weg:
1. Ausgangspunkt ist die optisch beste unveraenderte Quellform, nicht die optisch schlechte R16-Envelope-Huelle.
2. Klassifiziere Quellflaechen/-samples nach externer Sichtbarkeit, Orientierung und Nachbarschaft. Verdeckte interne/Doppel-/Tiefenlagen verwerfen.
3. Erzeuge daraus eine konsistente orientierte aeussere Punkt-/Flaechenmenge.
4. Rekonstruiere daraus deterministisch eine einzige manifold Aussenhaut, z. B. mit screened/oriented Poisson, winding-/outside-klassifizierter Surface-Reconstruction, Alpha-Wrap oder technisch gleichwertiger Methode.
5. Charakterpraegende Bereiche adaptiv dichter sampeln: Gesicht, Augen-/Nasenbereich, Ohren, Fuesse, Blattkanten, sichtbares Ahornblatt und Silhouette. Keine kreative Formkorrektur.
6. Keine globale Glattung, die Relief oder Silhouette sichtbar veraendert.

## Verbindliche Arbeitsweise
- Vor einem sehr grossen Feinlauf zuerst kleine/medium technische Kandidaten erzeugen und Gate-2-Eignung pruefen.
- Wenn dieselbe Fehlerart nach zwei gezielten Parametervarianten nicht deutlich sinkt, Methode wechseln statt weiter patchen.
- Gute Bereiche gegen die optisch beste Quellform schuetzen.
- Keine neue Trellis-Generierung, kein neuer Seed, kein Redesign.
- Keine Split-/Hohl-/Connector-Geometrie vor Gate 1 + Gate 2 PASS.

## Gate 1 – Topologie
PASS nur bei:
- genau einer aeusseren Master-Komponente
- watertight
- 2-manifold
- 0 offenen Kanten
- 0 Non-Manifold-Kanten/-Vertices
- keine eingeschlossenen Schalen
- keine doppelten Tiefenlagen
- keine realen Selbstschnitte

## Gate 2 – Formschutz
Reale Geometrie-Renders: 3/4 vorne, links, rechts, hinten, oben, unten sowie SOLL/IST.

PASS / PASS MIT RESTPUNKTEN / FAIL verwenden.

Harte charakterrelevante Anforderungen:
- Gesicht frei und rundlich wie Referenz
- Augen, Nase, Ohren und kurze Fuesse klar lesbar
- keine Blatt-/Stachelflaeche ueber Stirn/Augen/Schnauze
- Ruecken-/Blattcharakter erhalten
- genau ein sichtbares Ahornblatt lesbar
- REF-SEAM visuell plausibel
- keine sichtbare Aufblaehung, Schrumpfung, Stufe oder verschmiertes Relief

Kleine technisch harmlose, eindeutig slicer-reparierbare Restfehler duerfen als PASS MIT RESTPUNKTEN dokumentiert werden, sofern die sichtbare Form korrekt bleibt und keine unzugaengliche/problematische Geometrie entsteht.

## Gate 3 – CAD/FDM erst nach Gate 1 + Gate 2
Dann erst:
- REF-SEAM-Split
- zwei Hohlschalen nominal 1.6 mm
- zentraler Klebeverbinder Ø10.0 mm exakt, 20.0 mm Eingriff exakt
- Klebespiel dokumentieren
- Support-/Orientierungspruefung
- STL + Assembly 3MF/GLB + technische Validierung

## Git-/Artefaktregel – verbindlich
GitHub blockiert Einzeldateien >100 MB. Dieser Fehler darf nicht erneut den Hannes-Workflow blockieren.
- Temporaere/diagnostische Meshes >90 MB NICHT in Git committen.
- Solche Dateien unter `D:\3D-Models\generated\_ruediger-local-large-artifacts\herbst-igel-r17` lokal sichern.
- Im Ergebnis ein Manifest mit Originalpfad, lokalem Pfad, Dateigroesse und SHA-256 erzeugen.
- Reproduzierbare Skripte, Reports, Render und maschinenlesbare Statusdateien bleiben im Git-Ergebnis.
- Falls eine notwendige finale Masterdatei >90 MB waere, vor Push eine technisch verlustfreie bzw. reproduzierbare kleinere Austauschdarstellung erzeugen; Produktgeometrie nicht veraendern.

## Pflichtausgaben
- reproduzierbare Skripte/Quelle
- GEÄNDERT / UNVERÄNDERT / ENTFERNT / OFFEN
- Topologiebericht
- Formschutz-/Form-Delta-Bericht
- reale 6-Ansichten + SOLL/IST
- maschinenlesbarer Ergebnisstatus
- Manifest fuer lokal ausgelagerte grosse Artefakte, falls vorhanden

Keine finale Nutzerfreigabe behaupten.
