# TASK-HERBST-IGEL-R02-EXTERIOR-SURFACE-SURGERY-R14

## Status
Freigegebener technischer Folgeauftrag nach R13 FORM_PROTECTION_GATE + OPTIK_GATE FAIL.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

## Verbindliche Produktbasis
Unverändert aus R13 und der autoritativen Herbst-Igel-Spezifikation:
- Seed 42 bleibt die Formbasis.
- REF-CLEAN und REF-SEAM bleiben autoritativ.
- ca. 200 mm maximale Gesamtausdehnung, proportional.
- exakt zwei Druckteile: Körper vorn PLA Matt Desert Tan, Rücken-/Stachelschale PLA Metal Kupfer.
- beide hohl, nominal 1.6 mm Wand.
- Gesicht frei; keine Blatt-/Stachelflächen über Stirn, Augen oder Schnauze.
- genau ein sichtbares dekoratives Ahornblatt auf Referenzseite.
- zentraler interner Klebeverbinder Ø10.0 mm exakt, 20.0 mm Eingriff exakt.
- 0.4-mm-Düse; Ziel 0.12 mm Layer, adaptiv bis 0.08 mm erlaubt.

## Verifizierter R13-Befund
R13 hat zwar ein topologisch geschlossenes Mesh erzeugt, aber die Methode ist als Formbasis verworfen:
- Mesh-Gate formal PASS: 0 boundary, 0 nonmanifold, 0 degeneriert, 0 bestätigte Kreuzungen.
- außerhalb ROI lagen reine Knotenabstände noch innerhalb der Grenzwerte, aber die reale Oberfläche war nicht geschützt.
- Flächeninhalt wurde 60.461x größer, weil ein globales Doppel-Höhenfeld voneinander getrennte Seed-42-Tiefenlagen miteinander verbunden hat.
- reale SOLL/IST-Renders zeigen weiterhin harten Stirn-/Seam-Überhang, nicht klar freie Augen/Ohren und unplausible Rücken-/Ahornblatt-Lesbarkeit.

Dieser STOPP ist rein technisch. Es fehlt keine Produktentscheidung.

## Auftrag R14 – EXTERIOR SURFACE SURGERY
Baue KEINE neue globale Ersatzhülle. Repariere die vorhandene Seed-42-Oberfläche topologisch direkt und lokal, indem die tatsächlich sichtbare Außenhaut erhalten und nur fehlerhafte Kanten-/Doppelhaut-/Lochstellen chirurgisch bereinigt werden. Danach die bekannte Gesichts-/Body-Problemzone als einzige glatte Außenoberfläche rekonstruieren.

## Verbotene Verfahren für R14
Folgende R13-Wege dürfen NICHT erneut als Endform verwendet werden:
1. globales Heightfield / Doppel-Höhenfeld,
2. radiale / sternförmige Hülle oder Icosphere-Projektion,
3. globale Voxel-/Visual-Hull-Hülle,
4. Convex Hull,
5. globale Poisson-Rekonstruktion ohne harte Schutzbindung an die vorhandene sichtbare Seed-42-Außenhaut,
6. irgendein Verfahren, das getrennte Tiefenlagen durch neue lange Brückenflächen verbindet.

## Verbindlicher Reparaturablauf
### A. Seed-42-Außenhaut klassifizieren
1. Byte-identische Seed-42-Quelle laden und Hash prüfen.
2. Dreiecke/Sheets über Kanteninzidenz, Normalenorientierung, räumliche Nähe und Sichtbarkeit aus den sechs kanonischen Außenansichten klassifizieren.
3. Sichtbare Außenhaut ist zu SCHÜTZEN. Verdeckte Doppel-/Innenhäute dürfen nur entfernt werden, wenn ihre Verdeckung geometrisch nachgewiesen ist.
4. Nichtmanifold-Kanten zuerst durch lokale Face-/Vertex-Separation auflösen; NICHT durch globale Neuvernetzung.

### B. Lokale Topologiechirurgie außerhalb Gesichts-ROI
1. Bestehende Seed-42-Dreiecke soweit möglich unverändert übernehmen.
2. Boundary-Loops lokal schließen/stitchen, ausschließlich zwischen direkt benachbarten Randringen derselben lokalen Oberflächenlage.
3. Neue Kanten/Brücken dürfen keine getrennten Tiefenlagen koppeln. Jede neue Stitch-Kante muss lokal plausibel sein: Länge <= 3x lokaler Median der angrenzenden Seed-42-Kanten und Normalensprung <= 60 Grad, außer ein dokumentierter echter scharfer Formrand erfordert mehr.
4. Kein sichtbarer Bereich außerhalb ROI darf durch eine Ersatzhülle geglättet oder kugelig gemacht werden.

### C. Gesichts-/Body-ROI
1. Die aus R11/R12 bestätigte Problemzone verwenden.
2. Fusionierte Blatt-/Stachelflächen vor REF-SEAM vollständig aus der Gesichtszone entfernen.
3. Fehlende Haut als EINEN glatten lokalen Patch aus dem gesunden Randring rekonstruieren; erlaubt sind constrained MLS/RBF/screened-Poisson nur lokal in der ROI.
4. Patch muss positions- und normalenkontinuierlich an den gesunden Rand anschließen; keine Caps, Fächer, Blockstufen oder Doppelhaut.
5. Vorhandene Nase, Augen, Ohren, Schnauze und vier Füße schützen; nichts neu erfinden.

## Harte Gates – Reihenfolge zwingend
### Gate 1: TOPOLOGY
End-Masterkandidat muss genau eine geschlossene orientierbare 2-manifold Außenoberfläche sein:
- boundary edges = 0
- nonmanifold edges = 0
- degenerate faces = 0
- bestätigte Selbst-/Kreuzschnitte = 0
- keine überlappende Doppelhaut

### Gate 2: FORM PROTECTION außerhalb ROI
Nicht nur Vertex-Sampling. Zwingend reale sichtbare Oberfläche prüfen:
- bidirektionaler Punkt-zu-Dreieck-Abstand zwischen geschützter sichtbarer Seed-42-Außenhaut und reparierter Außenhaut: p95 <= 0.15 mm, max <= 0.40 mm.
- Silhouette in allen sechs kanonischen Ansichten außerhalb ROI darf sich sichtbar nicht ändern; pixel-/ray-basierte Abweichung dokumentieren.
- keine neu erzeugte Verbindung zwischen getrennten Seed-42-Tiefenlagen.
- Flächen-/Kantenstatistik auf pathologische Aufblähung prüfen; ein R13-artiger Flächenanstieg ist harter FAIL.

### Gate 3: OPTIK gegen REF-CLEAN + REF-SEAM
PASS nur wenn eindeutig:
- Gesicht frei und rundlich wie Referenz,
- Stirn, beide Augen, beide Ohren, Schnauze und Nase frei von Blatt-/Stachelüberdeckung,
- vier kurze Füße erhalten,
- Rücken gewölbt und Blatt-/Stachelstruktur plausibel,
- genau ein sichtbares Ahornblatt auf Referenzseite,
- REF-SEAM visuell plausibel,
- keine sichtbare Reparaturkante, Beule, Delle, Fächer- oder Blockstruktur.

### Gate 4: CAD/FDM erst nach 1+2+3 PASS
Dann unverändert:
- REF-SEAM Split,
- zwei Hohlschalen nominal 1.6 mm,
- zentraler Klebeverbinder Ø10.0 mm exakt, 20.0 mm Eingriff exakt,
- STL/3MF/GLB,
- vollständige FDM-/Slicer-Validierung für 0.4-mm-Düse und ca. 200 mm Endgröße.

## Selbstkorrektur innerhalb R14
Nicht nach dem ersten reparierbaren technischen Fehlversuch abbrechen. Wenn Gate 1 oder Gate 2 wegen einer eindeutig lokalen Topologie-/Stitching-Ursache fällt, Parameter/Selektion innerhalb derselben Methode korrigieren und erneut prüfen. STOPP erst, wenn der verbleibende Fehler methodisch nicht lokal behebbar ist oder eine echte Produktentscheidung erforderlich wird.

## Pflichtausgaben
- reproduzierbare Skripte/Quelle
- Klassifikation sichtbare Außenhaut vs. verworfene Innen-/Doppelhaut
- Liste/Statistik aller neu erzeugten Stitch-Kanten mit Längen- und Normalenprüfung
- Topologie-Audit vor/nach
- bidirektionaler Surface-Distance-Report außerhalb ROI
- sechs reale Geometrie-Renders + SOLL/IST gegen REF-CLEAN/REF-SEAM
- Revisionsbericht GEÄNDERT / UNVERÄNDERT / ENTFERNT / OFFEN
- maschinenlesbarer Ergebnisstatus
- bei PASS Fertigungsartefakte und vollständige FDM-Validierung

Keine finale Nutzerfreigabe behaupten.
