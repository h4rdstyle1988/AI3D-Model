# TASK-HERBST-IGEL-R02-ENVELOPE-REBUILD-R16

## Status
Freigegebener technischer Folgeauftrag nach R15-GATE1-FAIL.

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

## Ausgangslage R15
R15 hat methodisch nachgewiesen, dass die bisherige lokale Loch-/Unterseitenreparatur am R14-Quellmesh nicht zuverlässig fortsetzbar ist:
- Projektionsbegrenzung FAIL
- Normalenübergang FAIL
- 45 bestätigte Kreuzungen mit anderen Tiefenlagen
- Topologie-Gate FAIL
- Optik- und CAD/FDM-Gates dadurch nicht ausführbar

Damit ist die lokale Patch-Strategie für diese Quelle beendet. Nicht noch einen weiteren lokalen Lochfüller erzeugen.

## Auftrag R16
Erzeuge aus der zuletzt optisch besten, unveränderten sichtbaren Außenform eine **einzige saubere äußere Hüllfläche** als neue technische Masterbasis. Ziel ist ausschließlich, die intern/mehrlagig problematische Topologie zu entfernen, ohne die sichtbare Produktform neu zu entwerfen.

### Unmissverständliche Regeln
1. Keine neue Figur, kein neuer Seed, kein erneuter Trellis-Vollauf.
2. Keine lokale Patch-Kette R09–R15 als neue Form erfinden. Verwende deren Daten nur zur Diagnose und zum Erkennen gültiger äußerer Sichtflächen.
3. Die neue Masterfläche muss aus dem äußersten sichtbaren Envelope der optisch besten vorhandenen Form abgeleitet werden. Interne Doppel-/Tiefenlagen, eingeschlossene Flächen und verdeckte Kreuzungsschichten dürfen NICHT übernommen werden.
4. Sichtbare Außenform schützen: Silhouette, Gesicht, Augen, Nase, Ohren, Füße, Rückenwölbung, Blatt-/Stachelstruktur und genau ein sichtbares Ahornblatt dürfen nicht absichtlich umgestaltet werden.
5. Kein Glätten, das charakteristische Blattkanten, Augen/Nase oder Silhouette sichtbar verändert. Nur technisch notwendige Mikrokorrektur zur Herstellung einer einzigen manifold Außenhaut.
6. Rekonstruktion als deterministische watertight/2-manifold Envelope-Fläche, z. B. robustes SDF/TSDF/Poisson/voxel-envelope oder gleichwertig. Methode frei, Ergebnis nicht.
7. Vor Freigabe muss die neue Envelope-Geometrie gegen die optisch beste Ausgangsform bidirektional geprüft werden. Sichtbare Abweichung darf nicht nur statistisch klein, sondern muss in den realen Renderansichten unauffällig sein.
8. Keine Split-/Hohl-/Connector-Geometrie, bevor Gate 1 und Gate 2 bestanden sind.

## Gates
### Gate 1 – Topologie zwingend PASS
- genau eine äußere Komponente für die Master-Außenhaut
- watertight
- 2-manifold
- 0 offene Kanten
- 0 Non-Manifold-Kanten/-Vertices
- keine internen eingeschlossenen Schalen
- keine doppelten Tiefenlagen
- keine tatsächlichen Selbstschnitte

Wenn Gate 1 FAIL: innerhalb desselben Auftrags Parameter/Envelope-Auflösung iterieren. Nicht beim ersten Versuch STOPP, solange technisch sinnvoll weitere deterministische Varianten möglich sind.

### Gate 2 – Formschutz zwingend PASS
Erzeuge reale Geometrie-Renders 3/4 vorne, links, rechts, hinten, oben, unten sowie SOLL/IST gegen REF-CLEAN/REF-SEAM und beste Ausgangsform.
PASS nur wenn:
- Gesicht frei und rundlich wie Referenz
- keine Stachel-/Blattüberdeckung von Stirn/Augen/Schnauze
- Augen, Nase, Ohren und kurze Füße erhalten
- Rücken-/Blattcharakter erhalten
- genau ein sichtbares Ahornblatt
- REF-SEAM visuell plausibel
- keine sichtbare Remesh-Aufblähung, Schrumpfung, Stufe oder verschmierte Details

Wenn Gate 2 FAIL: Envelope-Parameter gezielt nachstellen und erneut prüfen. Kein neues Design.

### Gate 3 – danach erst CAD/FDM
Nur nach Gate 1 + Gate 2 PASS:
- REF-SEAM-Split
- zwei Hohlschalen nominal 1.6 mm
- zentraler Klebeverbinder Ø10.0 mm exakt, 20.0 mm Eingriff exakt
- Material-/Düsen-/Supportprüfung wie verbindlich spezifiziert
- STL + Assembly 3MF/GLB + vollständige technische Validierung

## Pflichtausgaben
- reproduzierbare Skripte/Quelle
- GEÄNDERT / UNVERÄNDERT / ENTFERNT / OFFEN
- Topologiebericht mit tatsächlichen Selbstschnitt-/Manifold-Checks
- bidirektionaler Formschutzbericht
- reale 6-Ansichten + SOLL/IST
- maschinenlesbarer Ergebnisstatus

Keine finale Nutzerfreigabe behaupten.
