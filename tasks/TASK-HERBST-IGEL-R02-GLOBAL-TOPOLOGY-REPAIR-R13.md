# TASK-HERBST-IGEL-R02-GLOBAL-TOPOLOGY-REPAIR-R13

## Status
Freigegebener technischer Folgeauftrag nach R12-MESH_GATE_PRECONDITION FAIL.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

## Verbindliche Produktbasis
Unverändert aus der zuletzt bestätigten Herbst-Igel-Spezifikation:
- Seed 42 bleibt die Formbasis.
- REF-CLEAN und REF-SEAM bleiben autoritativ.
- ca. 200 mm maximale Gesamtausdehnung, proportional.
- exakt zwei Druckteile: Körper vorn PLA Matt Desert Tan, Rücken-/Stachelschale PLA Metal Kupfer.
- beide hohl, nominal 1.6 mm Wand.
- Gesicht frei; keine Blatt-/Stachelflächen über Stirn, Augen oder Schnauze.
- genau ein sichtbares dekoratives Ahornblatt auf Referenzseite.
- zentraler interner Klebeverbinder Ø10.0 mm exakt, 20.0 mm Eingriff exakt.
- 0.4-mm-Düse; Ziel 0.12 mm Layer, adaptiv bis 0.08 mm erlaubt.

## Technischer Befund aus R12
R12 hat reproduzierbar nachgewiesen, dass die unveränderte Seed-42-Quelle bereits außerhalb der R11-ROI 6.671 Boundary-Edges und 3.528 Nonmanifold-Edges enthält. Damit war die R12-Regel "außerhalb ROI byte/index-identisch" mit dem zugleich geforderten Null-Fehler-Mesh-Gate logisch unvereinbar.

Dieser Widerspruch ist rein technisch und keine Produktentscheidung. R13 hebt daher ausschließlich die zu strenge Topologie-Sperre außerhalb der ROI auf. Die sichtbare Form bleibt geschützt.

## Auftrag R13
Erzeuge aus Seed 42 eine topologisch saubere, geschlossene Single-Surface-Masterform und führe danach den bereits definierten lokalen Gesichts-/Body-Rebuild aus R12 aus.

### Harte Regeln
1. Keine neue Figur, kein anderer Seed, kein Re-Design.
2. Sichtbare Außenform außerhalb der Gesichts-/Problemzone geometrisch erhalten. Topologische Änderungen außerhalb ROI sind erlaubt, wenn sie ausschließlich zum Schließen/Welden/Remeshen nötig sind und die sichtbare Oberfläche innerhalb enger Toleranz bleibt.
3. Außerhalb ROI gilt Formschutz statt Indexschutz: Zielabweichung zur Seed-42-Oberfläche p95 <= 0.15 mm, max <= 0.40 mm; lokale Überschreitung nur mit dokumentiertem zwingendem Topologiegrund und ohne sichtbare Silhouettenänderung.
4. In der R11/R12-Problemzone weiterhin die falschen fusionierten Blatt-/Stachelflächen entfernen und eine einzige glatte organische Körper-/Gesichtsoberfläche rekonstruieren.
5. Keine sichtbaren Caps, Fächer, Blockflächen, harten Stufen oder überlappenden Doppelhäute.
6. Nase, Augen, Ohren, Schnauze, vier Füße, Rückenstruktur und das eine Ahornblatt erhalten; nichts neu erfinden.
7. Vor Optik-Gate muss die sichtbare End-Masterform bestehen aus genau einer geschlossenen, orientierbaren 2-manifold Oberfläche mit:
   - boundary edges = 0
   - nonmanifold edges = 0
   - degenerierte Faces = 0
   - bestätigte Selbst-/Kreuzschnittfehler = 0
8. Erst nach Mesh-Gate Optik-Gate gegen REF-CLEAN + REF-SEAM.
9. Optik PASS nur wenn Gesicht frei/rundlich, Augen/Ohren/Nase/Schnauze klar, vier Füße erhalten, Rücken/Blattstruktur plausibel und REF-SEAM visuell stimmt.
10. Bei Optik PASS erst dann Split, Hohlschalen, Ø10.0 x 20.0 mm Klebeverbinder, STL/3MF/GLB und FDM-Validierung erzeugen.

## Technisch bevorzugter Weg
- Seed-42-Mesh global topologisch sanieren (weld + manifold repair + gezieltes remesh), dabei Formabweichung quantitativ gegen die ursprüngliche Seed-42-Oberfläche messen.
- Keine pauschale starke Glättung; Silhouette und Details schützen.
- Danach die bekannte lokale Gesichtszone als Single-Surface-Rebuild sauber ersetzen und mit der reparierten Masteroberfläche verschweißen.
- Mesh-Gate vollständig ausführen.
- Reale Geometrie-Renders in 3/4 vorne, links, rechts, hinten, oben, unten sowie SOLL/IST erzeugen.

## Pflichtausgaben
- reproduzierbare Skripte/Quelle
- globaler Formabweichungsreport Seed42 -> repaired master
- Topologie-Audit vor/nach
- Revisionsbericht GEÄNDERT / UNVERÄNDERT / ENTFERNT / OFFEN
- sechs real-geometry Renders + SOLL/IST
- maschinenlesbarer Ergebnisstatus
- bei PASS Fertigungsartefakte und vollständige FDM-Validierung

Keine finale Nutzerfreigabe behaupten.
