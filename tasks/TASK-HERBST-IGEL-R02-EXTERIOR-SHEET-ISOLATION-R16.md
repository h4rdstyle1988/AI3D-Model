# TASK-HERBST-IGEL-R02-EXTERIOR-SHEET-ISOLATION-R16

## Status
Freigegebener technischer Folgeauftrag nach R15 Gate-1-STOPP.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

## Verbindliche Produktbasis
Unverändert aus R15:
- Seed 42 bleibt die sichtbare Formbasis.
- REF-CLEAN und REF-SEAM bleiben autoritativ.
- ca. 200 mm maximale Gesamtausdehnung, proportional.
- exakt zwei Druckteile: Körper vorn PLA Matt Desert Tan, Rücken-/Stachelschale PLA Metal Kupfer.
- beide hohl, nominal 1.6 mm Wand.
- Gesicht frei; keine Blatt-/Stachelflächen über Stirn, Augen oder Schnauze.
- genau ein sichtbares dekoratives Ahornblatt auf Referenzseite.
- zentraler interner Klebeverbinder Ø10.0 mm exakt, 20.0 mm Eingriff exakt.
- 0.4-mm-Düse; Ziel 0.12 mm Layer, adaptiv bis 0.08 mm erlaubt.

## Verifizierter R15-Befund
R15 hat den bestätigten 1.376-Kanten-Unterseitenloop methodisch bearbeitet, aber Gate 1 nicht bestanden. Der Kernbefund ist nun enger: Die R14/R15-Quelle enthält neben der beabsichtigten sichtbaren Außenlage weitere überlagernde/gefaltete Tiefenlagen. Nach reiner Unterseiten-Schließung verbleiben ca. 8.151 weitere Boundary-Edges; die Gesamtfläche ist in dieser Form nicht konsistent orientierbar. Ein erzwungenes Orientieren öffnet zwei globale Schnittloops von jeweils ungefähr 2,6 m und deren pauschales Schließen würde verbotene globale Brücken bzw. pathologische Flächenaufblähung erzeugen.

Das ist ein technischer Quellen-/Topologiefehler, keine Produktentscheidung.

## Auftrag R16 – beabsichtigte Exterior-Sheet-Lage isolieren, dann lokal schließen
Ziel ist NICHT eine neue Hülle zu erzeugen. Ziel ist, aus der vorhandenen Seed-42/R14/R15-Geometrie ausschließlich diejenige zusammenhängende Tiefenlage zu identifizieren und zu behalten, die tatsächlich die sichtbare äußere Produktoberfläche bildet. Spurious innere, rückgefaltete, doppelte oder querende Tiefenlagen dürfen entfernt werden, sofern sie nachweislich nicht zur sichtbaren Außenhaut gehören.

### 1. Keine neue globale Ersatzgeometrie
Verboten bleiben:
- Convex Hull
- globale Poisson-/Voxel-/SDF-Hülle
- Heightfield-/radiale Ersatzhülle
- globale Remesh-Hülle als Formersatz
- Brücken zwischen getrennten Tiefenlagen nur zum Erreichen von Watertightness

### 2. Exterior-Sheet deterministisch identifizieren
Nutze die vorhandene Geometrie selbst und mehrere Außenansichten/Strahltests, um für Front, Heck, links, rechts, oben, unten und schräge Ansichten jeweils die äußerste zuerst getroffene Lage zu bestimmen.

Erzeuge daraus eine konsistente Exterior-Sheet-Maske/Face-ID-Menge mit folgenden Regeln:
- Sichtbar äußerste Faces haben Vorrang.
- Faces, die vollständig hinter einer anderen Seed-42-Lage liegen und aus keiner Außenansicht zur Silhouette/ersten Oberfläche beitragen, gelten als spurious depth layer und dürfen entfernt werden.
- Kreuzende/gefaltete Doppelblätter dürfen nicht durch neue Brücken verbunden werden; stattdessen nur die zur tatsächlichen Außenhaut gehörige Lage behalten.
- Jede Entfernung muss als Face-ID-Liste und mit Begründung dokumentiert sein.
- Vorhandene Koordinaten der behaltenen Faces bleiben exakt unverändert, außer in ausdrücklich zulässigen lokalen Loch-/Gesichts-ROIs.

### 3. Sichtformschutz für die Sheet-Auswahl
Vor jeder Schließung prüfen:
- Front/Seite/Heck/Top-Silhouette gegen die ursprüngliche geschützte Seed-42-Sichtform unverändert innerhalb max. 0.40 mm, Ziel p95 <= 0.15 mm.
- Keine sichtbaren Augen-, Ohren-, Nasen-, Schnauzen-, Fuß-, Rücken-, Stachel-/Blatt- oder Ahornblattflächen entfernen.
- Wenn eine Face-Entfernung aus einer Außenansicht eine sichtbare Lücke erzeugt, war sie nicht als spurious layer zulässig.

### 4. Topologie nach Sheet-Isolation neu analysieren
Nach Entfernung ausschließlich nicht sichtbarer Tiefenlagen:
- Komponenten
- Boundary-Loops einzeln nach Umfang/Position
- nonmanifold edges
- orientation conflicts
- confirmed self/cross intersections
- doppelte/coincident faces

Es ist ausdrücklich zulässig, dass danach echte Quellenlöcher sichtbar werden. Diese dürfen anschließend lokal geschlossen werden; sie sind keine Rechtfertigung für eine globale Ersatzhülle.

### 5. Echte Quellenlöcher lokal schließen
Für jeden nach Exterior-Sheet-Isolation verbleibenden echten Randloop:
- randgebundene harmonic/biharmonic/minimal-surface- oder gleichwertige lokale Füllung,
- keine Verbindung zu anderer Tiefenlage,
- Randposition <= 0.05 mm,
- keine Bounding-Box-Erweiterung,
- keine neuen X/Y-Extrema, Z nicht unter bestehendes Minimum,
- keine Selbst-/Kreuzschnitte,
- keine pathologische Flächenaufblähung.

Der bereits bestätigte Unterseitenloop aus R15 darf auf diese Weise erneut geschlossen werden, nun jedoch erst NACH Entfernung der spurious depth layers.

### 6. Gate 1 vollständig
PASS nur wenn:
- boundary edges = 0
- nonmanifold edges = 0
- degenerate faces = 0
- bestätigte Selbst-/Kreuzschnitte = 0
- genau eine geschlossene orientierbare 2-manifold Außenoberfläche
- keine Doppelhaut/coincident depth layer
- keine pathologische Flächenaufblähung

### 7. Gate 2 Formschutz
- Auf allen ursprünglich vorhandenen, behaltenen Seed-42-Außenflächen: bidirektional p95 <= 0.15 mm, max <= 0.40 mm.
- Für echte Quellenloch-Patches gelten die lokalen Ersatzkriterien statt Abstand zu nicht vorhandener Geometrie.
- Silhouettenabweichung separat dokumentieren.

### 8. Gesichts-/Body-ROI danach unverändert
Erst nach Gate 1+2 PASS:
- fusionierte Blatt-/Stachelflächen vor REF-SEAM entfernen,
- fehlende Gesichts-/Körperhaut als EINEN glatten lokalen Patch rekonstruieren,
- Nase, Augen, Ohren, Schnauze, vier Füße und genau ein Ahornblatt schützen,
- keine Caps/Fächer/Blockstufen/Doppelhaut.

### 9. Optik-Gate gegen REF-CLEAN/REF-SEAM
PASS nur wenn eindeutig:
- Gesicht frei und rundlich wie REF-CLEAN,
- Stirn, beide Augen, beide Ohren, Schnauze und Nase frei,
- vier kurze Füße erhalten,
- Rücken gewölbt, Blatt-/Stachelstruktur plausibel,
- genau ein sichtbares Ahornblatt,
- REF-SEAM plausibel,
- keine sichtbare Reparaturkante, Beule, Delle, Fächer- oder Blockstruktur.

### 10. CAD/FDM nur nach Gate 1+2+3 PASS
Dann unverändert:
- REF-SEAM-Split,
- zwei Hohlschalen nominal 1.6 mm,
- zentraler Klebeverbinder Ø10.0 mm exakt, 20.0 mm Eingriff exakt,
- STL/3MF/GLB,
- vollständige FDM-/Slicer-Validierung.

## Selbstkorrektur
Nicht beim ersten technisch reparierbaren Fehlversuch stoppen. Exterior-Sheet-Klassifizierungsschwellen, Sichtstrahl-Dichte und lokale Randfüllparameter innerhalb dieser Methode selbstständig variieren und erneut prüfen. STOPP nur bei methodisch belegter Unmöglichkeit oder echter Produktentscheidung.

## Pflichtausgaben
- reproduzierbare Skripte
- Face-ID-Maske retained exterior vs. removed spurious depth layers
- Begründung/Visibility-Audit je entfernter Face-Gruppe
- Topologie-Audit vor/nach Exterior-Sheet-Isolation
- Boundary-Loop-Liste nach Isolation
- Intersection-/Orientation-Audit
- Formschutz-Report + Silhouettenmetriken
- sechs reale Renders + SOLL/IST REF-CLEAN/REF-SEAM
- maschinenlesbarer Ergebnisstatus
- bei PASS Fertigungsartefakte + FDM-Validierung

Keine finale Nutzerfreigabe behaupten.
