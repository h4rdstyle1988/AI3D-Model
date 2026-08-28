# Benchmark B – Spülenablage v004-r01 (zweiteilig)

Neue, getrennte Revision auf Basis von `C:\Users\h4rds\Documents\spuelenablage.3mf`. Keine frühere Revision wurde überschrieben.

## Bauteile

1. `benchmark-b-spuelenablage-v004-r01-einsatz`: vollständiges 3-mm-Wabengitter plus direkt verbundener 85 × 85 × 100-mm-Behälter mit vier geschlossenen 2-mm-Wänden, offenem Deckel und wasserdurchlässigem Wabenboden.
2. `benchmark-b-spuelenablage-v004-r01-wanne`: unveränderte 240 × 85 × 20-mm-Grundfunktion mit 240 × 35 × 10-mm-Fuß, Gefälleboden und offenem Frontablauf; ergänzt um eine 3,5-mm-Auflage mit 45°-Unterseite sowie zehn isolierte Stützpfosten.

Der Einsatz misst am einzulegenden Rahmen 235 × 80 mm und sitzt in der gemessenen 236 × 81-mm-Wannenöffnung mit 0,50 mm Spiel pro Seite. Er ist gerade, nur durch Schwerkraft gehalten und von Hand herausnehmbar.

## Druck

- Einsatz: natürliche Lage mit Wabengitter auf dem Druckbett, PETG 0,24 mm, **ohne Support**.
- Wanne: natürliche Lage, PETG 0,24 mm, zugänglicher Tree-Support ausschließlich von der Druckplatte unter der offenen Unterseite.
- Beide G-Codes wurden ohne automatische Formreparatur erzeugt und besitzen keine leeren Schichten.

## Freigabestatus

Geometrie, Passung, Wasserweg, Topologie, 3MF und beide Slices: **PASS**.

Gesamtspezifikation: **HOLD**. Unter der besten vollständigen vorhandenen Wabe stehen nur 14,62 mm unterhalb der Gitterunterseite zur Verfügung; gefordert sind 18,5–19 mm. Von der Gitteroberseite bis zum Boden sind es maximal 17,62 mm. Der unveränderte 18-mm-Zapfen kollidiert bei vollständigem Einsetzen um rund 0,38 mm. Es existiert innerhalb der geschützten Maße keine geeignete alternative vollständige Wabe.

Halter und Gefälleboden wurden deshalb nicht stillschweigend verändert. Details stehen in `WISCHTUCHHALTER-COMPATIBILITY-REPORT.md`.
