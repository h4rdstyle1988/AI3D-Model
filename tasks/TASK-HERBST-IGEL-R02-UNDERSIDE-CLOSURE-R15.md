# TASK-HERBST-IGEL-R02-UNDERSIDE-CLOSURE-R15

## Status
Freigegebener technischer Folgeauftrag nach R14 Gate-1-STOPP.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

## Verbindliche Produktbasis
Unverändert aus R14:
- Seed 42 bleibt die sichtbare Formbasis.
- REF-CLEAN und REF-SEAM bleiben autoritativ.
- ca. 200 mm maximale Gesamtausdehnung, proportional.
- exakt zwei Druckteile: Körper vorn PLA Matt Desert Tan, Rücken-/Stachelschale PLA Metal Kupfer.
- beide hohl, nominal 1.6 mm Wand.
- Gesicht frei; keine Blatt-/Stachelflächen über Stirn, Augen oder Schnauze.
- genau ein sichtbares dekoratives Ahornblatt auf Referenzseite.
- zentraler interner Klebeverbinder Ø10.0 mm exakt, 20.0 mm Eingriff exakt.
- 0.4-mm-Düse; Ziel 0.12 mm Layer, adaptiv bis 0.08 mm erlaubt.

## Verifizierter R14-Befund
R14 hat die Nonmanifold-Kanten erfolgreich auf 0 reduziert, ist aber an einem 1.376-Kanten-Boundary-Loop auf der Unterseite gestoppt. Für diesen Loop existiert laut Audit kein benachbarter gleicher Tiefenlage zugehöriger Gegenring. Der R14-Stopp ist technisch, nicht produktbezogen.

Die bisherige R14-Regel war für diesen Sonderfall zu streng: Sie verlangte einerseits eine geschlossene Außenoberfläche, verbot andererseits jede neue Fläche, die nicht innerhalb 0,40 mm zu einer bereits vorhandenen Seed-42-Oberfläche liegt. In einem echten Quellenloch ohne korrespondierende Seed-Fläche ist das logisch nicht erfüllbar.

## Auftrag R15 – technische Schließung eines echten Quellenlochs
Behandle den bestätigten großen Unterseiten-Loop ausdrücklich als fehlende Quellenoberfläche und nicht als Formänderung einer vorhandenen Seed-Fläche.

### 1. Außenhaut unverändert schützen
- Starte von der R14-lokal bereinigten Außenhaut oder reproduziere sie deterministisch aus Seed 42.
- Außerhalb des bestätigten Unterseiten-Lochs und der bekannten Gesichts-ROI gilt weiterhin der R14-Formschutz: bidirektional p95 <= 0.15 mm, max <= 0.40 mm gegenüber der geschützten sichtbaren Seed-42-Außenhaut.
- Keine globale Ersatzhülle, kein Heightfield, keine radiale Hülle, kein Convex Hull, keine globale Poisson-/Voxel-Hülle.

### 2. Unterseiten-Loch schließen – nur innerhalb des fehlenden Gebiets
Für den bestätigten 1.376-Kanten-Unterseitenrand ist eine neue Abschlussfläche zulässig, weil dort keine korrespondierende Seed-42-Fläche existiert.

Die Abschlussfläche MUSS:
- exakt an den vorhandenen Randring anschließen,
- vollständig innerhalb der Projektion/Einspannung dieses Randrings liegen,
- keine Außen-Silhouette in Front/Seite/Heck/Top verändern,
- keine andere Seed-42-Tiefenlage kontaktieren oder überbrücken,
- als glatte, niedrigfrequente Unterseitenfläche entstehen,
- topologisch EIN Bestandteil derselben Außenoberfläche sein,
- keine Doppelhaut erzeugen,
- keine dekorative oder sichtbare Produktform neu erfinden.

Technisch bevorzugt: constrained minimal-surface / biharmonic / harmonic patch oder gleichwertige randgebundene Flächenfüllung. Keine einfache Dreiecks-Fächer-Cap-Endform, wenn diese sichtbare harte Spitzen/Falten erzeugt.

### 3. Geometrische Grenzen der neuen Unterseitenfläche
Da im Loch keine Seed-Sollfläche existiert, gilt dort nicht der 0.40-mm-Punktabstand zu nicht vorhandener Geometrie. Stattdessen harte Ersatzkriterien:
- Randknoten bleiben innerhalb <= 0.05 mm ihrer R14/Seed-Randposition.
- Randnormalen-Übergang organisch; Normalensprung entlang Anschluss möglichst <= 45 Grad, dokumentierte lokale Ausnahmen nur wenn vom vorhandenen Rand erzwungen.
- neue Fläche darf die Bounding-Box der vorhandenen Form nicht erweitern.
- keine neuen Extrempunkte in X/Y; Z darf die bestehende Unterseiten-Minimalhöhe nicht unterschreiten.
- keine Selbstschnitte, keine Überschneidung mit anderer Seed-Geometrie.
- Fläche und Triangulation statistisch plausibel, keine pathologische Flächenaufblähung.

### 4. Danach Gate 1 vollständig erneut
Erst akzeptieren wenn:
- boundary edges = 0
- nonmanifold edges = 0
- degenerate faces = 0
- bestätigte Selbst-/Kreuzschnitte = 0
- genau eine geschlossene orientierbare 2-manifold Außenoberfläche
- keine Doppelhaut

### 5. Gate 2 Formschutz korrekt aufteilen
- Bereich mit vorhandener Seed-42-Korrespondenz: R14-Grenzen p95 <= 0.15 mm, max <= 0.40 mm, Silhouette unverändert.
- bestätigte Quellenloch-Fläche: stattdessen die Ersatzkriterien aus Abschnitt 3 prüfen; sie darf NICHT gegen eine nicht vorhandene Seed-Fläche gemessen und deshalb fälschlich verworfen werden.

### 6. Gesichts-/Body-ROI danach wie R14
Nach Gate 1+2 PASS:
- fusionierte Blatt-/Stachelflächen vor REF-SEAM entfernen,
- fehlende Gesichts-/Körperhaut als EINEN glatten lokalen Patch rekonstruieren,
- Nase, Augen, Ohren, Schnauze, vier Füße und das eine Ahornblatt schützen,
- keine Caps/Fächer/Blockstufen/Doppelhaut.

### 7. Optik-Gate gegen autoritative Referenzen
PASS nur wenn eindeutig:
- Gesicht frei und rundlich wie REF-CLEAN,
- Stirn, beide Augen, beide Ohren, Schnauze und Nase frei,
- vier kurze Füße erhalten,
- Rücken gewölbt, Blatt-/Stachelstruktur plausibel,
- genau ein sichtbares Ahornblatt,
- REF-SEAM plausibel,
- keine sichtbare Reparaturkante, Beule, Delle, Fächer- oder Blockstruktur.

### 8. CAD/FDM nur nach Gate 1+2+3 PASS
Dann unverändert:
- REF-SEAM-Split,
- zwei Hohlschalen nominal 1.6 mm,
- zentraler Klebeverbinder Ø10.0 mm exakt, 20.0 mm Eingriff exakt,
- STL/3MF/GLB,
- vollständige FDM-/Slicer-Validierung.

## Selbstkorrektur
Nicht beim ersten technisch reparierbaren Fehlversuch stoppen. Parameter der randgebundenen Unterseitenfüllung innerhalb dieser Methode selbstständig variieren und erneut prüfen. STOPP nur bei methodisch belegter Unmöglichkeit oder echter Produktentscheidung.

## Pflichtausgaben
- reproduzierbare Skripte
- eindeutige Maske/ID des bestätigten Quellenlochs
- Audit Randpositionen/Normalen und Ausschluss anderer Tiefenlagen
- Topologie-Audit vor/nach
- Formschutz-Report mit getrennten Metriken für vorhandene Seed-Oberfläche vs. Quellenloch-Patch
- sechs reale Renders + SOLL/IST REF-CLEAN/REF-SEAM
- maschinenlesbarer Ergebnisstatus
- bei PASS Fertigungsartefakte + FDM-Validierung

Keine finale Nutzerfreigabe behaupten.
