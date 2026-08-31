# TASK-HERBST-IGEL-R02-LOCAL-UNDERSIDE-HYBRID-REBUILD-R18

## Status
Freigegebener technischer Folgeauftrag nach R17 Gate-2-FAIL.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

## Verbindliche Produktbasis
Unveraendert aus der zuletzt bestaetigten Herbst-Igel-Spezifikation und R17:
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

## Nachgewiesene Ausgangslage R17
R17 verbessert die sichtbare Gesamtfigur deutlich gegenueber R16 und erreicht fuer `screened-mls-d`:
- Gate 1 PASS
- minimale Silhouetten-IoU ca. 0.983
- Gesicht, Nase, Ohren, kurze Fuesse, Ruecken-/Blattcharakter und das einzelne Ahornblatt grundsaetzlich lesbar

Gate 2 bleibt FAIL, weil:
- sichtbares Unterseitenrelief durch glatte Schliessflaeche ersetzt wird
- globale/implizite Rekonstruktionen Laeufer an tiefen Fussbereichen erzeugen
- MLS zwar Laeufer reduziert, aber sichtbare Oberflaechenrauheit erzeugt
- REF-SEAM noch nicht ausreichend klar demonstriert ist

## Auftrag R18
Kein weiterer globaler Neuaufbau der bereits guten sichtbaren Gesamtform.

Erzeuge eine konservative Hybrid-Aussenhaut, die die optisch guten, extern sichtbaren Quellflaechen maximal direkt erhaelt und nur die nachweislich problematische Unterseiten-/Topologiezone lokal ersetzt bzw. verbindet.

Technisch bevorzugter Weg:
1. Ausgangspunkt ist die byte-identische optisch beste Seed-42-Quellform bzw. deren extern sichtbare, orientierte Oberflaechenmenge aus R17.
2. Gute sichtbare Regionen ausserhalb einer automatisch aus dem R17-Fehlerbild bestimmten Unterseiten-ROI werden GEOMETRISCH GESCHUETZT: keine globale Glattung, kein globales Poisson/MLS-Resampling, keine Silhouettenveraenderung.
3. Unterseiten-ROI aus Sichtbarkeit, Normalenrichtung, Boundary-/Doppelhaut-/Intersections-Audit und R17-SOLL/IST-Fehlern bestimmen. ROI nicht groesser machen als technisch notwendig.
4. Innerhalb der ROI zuerst versuchen, die vorhandene sichtbare Quellunterseite direkt als orientierte Flaeche zu retten: externe Dreiecke klassifizieren, interne/doppelte Tiefenlagen entfernen, lokale Loecher/Naehte topologisch sauber schliessen.
5. Nur verbleibende Luecken lokal mit randbedingter Patch-Rekonstruktion schliessen. Patch-Rand muss positionell und normalenseitig an unveraenderte Quellflaeche anschliessen. Keine grossflaechige glatte Deckelflaeche.
6. Geeignete lokale Verfahren: constrained triangulation + tangential fairing nur im Patchinneren, local screened Poisson mit Dirichlet/Boundary constraints, winding-classified local surface surgery oder technisch gleichwertig.
7. Das sichtbare Unterseitenrelief aus der Quellform muss als harte Forminformation einfließen. Keine Methode verwenden, die getrennte Tiefenlagen volumetrisch zusammenzieht oder das Relief durch eine plan/glatte Schliessflaeche ersetzt.
8. Oberflaechenrauheit ausserhalb der ROI darf gegenueber der Quellform nicht zunehmen. Innerhalb der ROI nur so viel lokale Glattung wie fuer manifold Kontinuitaet zwingend noetig.
9. REF-SEAM explizit auf dem Kandidaten rendern/markieren und gegen REF-SEAM pruefen, ohne Geometrie kreativ zu verschieben.
10. Zuerst kleine/medium lokale Patch-Kandidaten pruefen. Wenn zwei gezielte lokale Varianten dieselbe sichtbare Fehlerart zeigen, lokale Methode wechseln statt globale Rekonstruktion zu wiederholen.

## Formschutz – harte Regeln
- Gesicht, Stirn, Augen, Schnauze, Ohren, Rueckenblaetter, sichtbares Ahornblatt und Silhouette ausserhalb der Unterseiten-ROI duerfen nicht sichtbar veraendert werden.
- Keine globale Skalierung ausser der bereits dokumentierten proportionalen Zielgroesse.
- Keine neue Trellis-Generierung, kein neuer Seed, kein Redesign.
- Keine neuen dekorativen Details oder Funktionen.

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
Pflicht:
- reale 6-Ansichten plus 3/4 vorne
- SOLL/IST gegen optisch beste Seed-42-Quelle und REF-CLEAN
- separate Unterseiten-Nahansicht mit Quellrelief vs Kandidat
- REF-SEAM-Overlay/Markierung

PASS nur wenn:
- bisher gute sichtbare Gesamtform von R17 mindestens erhalten bleibt
- Unterseitenrelief nicht durch glatte Schliessflaeche ersetzt wird
- keine Fuss-Laeufer
- keine neue sichtbare MLS-/Patch-Rauheit
- keine sichtbare Aufblaehung, Schrumpfung, Stufe oder Reliefverschmierung
- genau ein sichtbares Ahornblatt erhalten
- Gesicht frei und rundlich wie Referenz
- REF-SEAM visuell plausibel nachgewiesen

## Gate 3 – CAD/FDM erst nach Gate 1 + Gate 2 PASS
Dann erst:
- REF-SEAM-Split
- zwei Hohlschalen nominal 1.6 mm
- zentraler Klebeverbinder Ø10.0 mm exakt, 20.0 mm Eingriff exakt
- Klebespiel dokumentieren
- Support-/Orientierungspruefung
- STL + Assembly 3MF/GLB + technische Validierung

## Git-/Artefaktregel
- Temporaere/diagnostische Meshes >90 MB nicht in Git committen.
- lokal unter `D:\3D-Models\generated\_ruediger-local-large-artifacts\herbst-igel-r18` sichern.
- Manifest mit Originalpfad, lokalem Pfad, Dateigroesse, SHA-256 und Grund erzeugen.
- verbindliche finale Ausgabe >90 MB nicht still entfernen; reproduzierbare kleinere Austauschdarstellung oder klarer technischer STOPP.

## Pflichtausgaben
- reproduzierbare Skripte/Quelle
- GEÄNDERT / UNVERÄNDERT / ENTFERNT / OFFEN
- ROI-Definition und Begruendung
- Topologiebericht
- Formschutz-/Form-Delta-Bericht
- Unterseiten-SOLL/IST-Nahansicht
- reale 6-Ansichten + 3/4 vorne
- REF-SEAM-Overlay
- maschinenlesbarer Ergebnisstatus
- Manifest fuer lokal ausgelagerte Grossartefakte, falls vorhanden

Keine finale Nutzerfreigabe behaupten.
