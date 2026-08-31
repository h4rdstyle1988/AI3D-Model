# Herbst-Igel R02 – Revisionsbericht R12

## Status

`STOPP – MESH_GATE_PRECONDITION FAIL`

## GEÄNDERT

- Keine Produkt-, Seed-42-, CAD- oder Mesh-Geometrie geändert.
- Ausschließlich taskbezogene Prüfskripte, Topologieberichte und Diagnosebilder für R12 erzeugt.
- Die R11-ROI wurde unverändert aus dem R11-Code-Blob `571d31343ad14e27a8705d0120764667f59d9cf5` reproduziert.

## UNVERÄNDERT

- Seed 42 byte-identisch: `85ba18eaed15bdbe631fc49dd571e73882c4055e2c247022e90ad15ed99822c6`.
- REF-CLEAN: `c1c9a5a094f1db2fd220f3433f83af8dedca780f56a4bf479eb8883432250859`.
- REF-SEAM: `b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4`.
- Alle 436.742 Seed-42-Vertexkoordinaten und alle 870.466 Quelltriangles; es wurde keine Kandidatengeometrie geschrieben.
- Verbindliche Produktidee, Maße, Materialien, vier Füße, Rücken und vorhandenes einzelnes Ahornblatt.

## ENTFERNT

- Keine reale Geometrie entfernt. Schritt C wurde wegen der fatalen, bereits in Schritt B nachgewiesenen Randring-Vorbedingung nicht ausgeführt.

## OFFEN

- 6.671 Quellkanten mit nur einer inzidenten Fläche liegen vollständig außerhalb der R11-ROI.
- 3.528 Quellkanten mit mehr als zwei inzidenten Flächen liegen vollständig außerhalb der R11-ROI.
- Nach Entfernen aller 198.697 R11-Problemtriangles hätte der unveränderliche Rest noch 8.940 Randkanten, 3.528 nichtmanifolde Kanten und keinen einfachen geschlossenen Randring.
- Ein ROI-lokaler Rebuild kann diese unveränderlichen Außen-ROI-Defekte nicht auf null setzen. Ihre Reparatur würde zwingend Regel 1 verletzen.
- Daher kein Optik-Gate, keine CAD-/Split-/Hohlschalen-/Verbinder-/STL-/FDM-Artefakte und keine realen Drucktests.
- Keine finale Produkt- oder Druckfreigabe behauptet.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

Grund: Der STOPP ist ein reproduzierbar nachgewiesener technischer Widerspruch zwischen unveränderlicher Außen-ROI-Geometrie und dem verpflichtenden Null-Fehler-Mesh-Gate. Es fehlt keine Nutzerangabe.
