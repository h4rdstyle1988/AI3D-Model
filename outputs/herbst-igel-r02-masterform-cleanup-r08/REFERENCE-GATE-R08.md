# Herbst-Igel R02 – Referenz- und Ausgangs-Gate R08

`STATUS: PASS`

Verwendet wurden ausschließlich die im Auftrag autorisierten Quellen:

- REF-CLEAN R06/R07: `reference-audit/ref-clean-r08.jpg`, 17.344 Byte, SHA-256 `c1c9a5a094f1db2fd220f3433f83af8dedca780f56a4bf479eb8883432250859`.
- REF-SEAM: `reference-audit/ref-seam-r08.jpg`, 11.788 Byte, SHA-256 `b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4`.
- R07 Seed 42: `source-r07/herbst-igel-r02-trellis-raw-seed-42.ply`, 16.557.141 Byte, SHA-256 `85ba18eaed15bdbe631fc49dd571e73882c4055e2c247022e90ad15ed99822c6`.

Der Seed-42-Hash stimmt bytegenau mit `c8b2b86` und dem R07-Prüfbericht überein. Es wurde keine neue Trellis-Serie gerechnet und keine andere Formquelle verwendet.

Die blaue REF-SEAM wurde als zusammenhängender Pixelpfad extrahiert und über die X/Z-Projektion der Referenzseite auf die reale Seed-42-Geometrie übertragen. Der verwendete Körperbereich und die Schutzmasken sind in `diagnostics/ref-seam-body-mask-r08.png`, `diagnostics/seed42-side-ref-seam-mapping-r08.png` und `diagnostics/cleanup-selection-r08.png` sichtbar.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`
