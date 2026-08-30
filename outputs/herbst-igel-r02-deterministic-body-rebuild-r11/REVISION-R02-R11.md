# Herbst-Igel R02 – Revisionsbericht R11

## Status

`STOPP – OPTIK_GATE FAIL`

## GEÄNDERT

- Ausschließlich die aus REF-CLEAN/REF-SEAM bestimmte lokale Gesichts-/Körper-ROI wurde als ein deterministischer, variabel breiter SDF-Körperrebuild neu berechnet.
- 181.949 nachgewiesene Quelltriangles der störenden ROI wurden aus der sichtbaren Kandidatenfläche entfernt.
- 16.748 tiefenselektierte Quelltriangles von Ohren, Augen und Nase wurden mit unveränderten Seed-42-Koordinaten geschützt.
- Nach dem ersten Front-/Seitenscreening wurde nur die Tiefenselektion innerhalb derselben ROI verschärft; es wurde kein zweiter Formkandidat und kein neuer Seed erzeugt.

## UNVERÄNDERT

- Seed-42-Quelldatei byte-identisch: `85ba18eaed15bdbe631fc49dd571e73882c4055e2c247022e90ad15ed99822c6`.
- REF-CLEAN: `c1c9a5a094f1db2fd220f3433f83af8dedca780f56a4bf479eb8883432250859`.
- REF-SEAM: `b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4`.
- Sämtliche 436.742 Seed-42-Vertexkoordinaten; kein Quellvertex wurde verschoben.
- 671.769 Quelltriangles außerhalb der ROI indexgleich.
- Rückenstruktur außerhalb ROI, vier Füße und vorhandenes einzelnes Ahornblatt.
- Produktidee, ca. 200 mm Zielgröße, zwei Materialien, 1,6 mm Nennwand und Verbindermaße.

## ENTFERNT

- Ausschließlich störende/fusionierte Blatt-/Stachelflächen innerhalb der autoritativ bestimmten ROI.
- Keine bestätigte Rückenstruktur außerhalb der ROI.

## OFFEN

- Gesicht, Stirn, beide Augen und beide Ohren bestehen das binäre Optik-Gate nicht eindeutig.
- Der lokale Übergang besitzt offene Kanten und Kreuzungen mit geschützten Quellflächen; kein gültiger zusammenhängender Masterkörper.
- Daher keine CAD-Splitdatei, keine Hohlschalen, kein Connector und keine STL.
- Reale Druck-, Passungs-, Support-, Material- und 200-mm-Tests sind vor Optik-PASS nicht anwendbar.
- Finale Produkt-/Druckfreigabe bleibt ausschließlich beim Nutzer.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

Grund: Der Stopp ist technisch nachgewiesen; es fehlt keine Nutzerentscheidung.
