# Herbst-Igel – Revision R02 / technische Rekonstruktion R10

## GEÄNDERT

- Byteidentische Seed-42-Rohform erneut als einzige Geometriebasis geladen;
  R09-NON-APPROVED wurde nicht weiterverformt.
- Die bestätigte REF-SEAM-Problemzone oberhalb `Z = -0,105` als glatte
  implizite Volumenrekonstruktion neu aufgebaut.
- Zwei technisch unterschiedliche Varianten erzeugt: geglättete SDF-
  Visual Hull und Gauß-RBF mit 324 Stützstellen.
- Äußere Seed-42-Tiefenlagen in den unveränderten Schutzmasken vermessen, um
  vorhandene Ohren, Augen, Nase/Schnauze und Füße nicht neu zu modellieren.
- Beide Varianten in drei Ansichten gescreent; die SDF-Variante hatte die
  geringere Feldabweichung und wurde in sechs Ansichten gerendert.
- Lokale Topologie und Übergänge geprüft: 0 degenerierte Dreiecke,
  940 offene Randkanten, 0 nichtmannigfaltige Kanten innerhalb der
  impliziten Teilfläche und 209 bestätigte nichtkoplanare Kreuzungen zwischen
  lokaler Quell- und Rekonstruktionsgeometrie.

## UNVERÄNDERT

- Alle 436.742 Seed-42-Quellpunktkoordinaten; der Quellpunktpräfix im
  ausgewählten NON-MASTER ist bitgleich.
- Sämtliche 681.744 Quellflächen außerhalb der bestimmten Problemzone.
- Bestätigte Rücken-/Stachelstruktur und das eine sichtbare Ahornblatt
  außerhalb der ROI; kein zweites Blatt ergänzt.
- Unterkörper und Füße unterhalb der Schutzgrenze.
- Produktidee, ca. 200 mm Zielausdehnung, exakt zwei Teile, Materialien,
  nominal 1,6 mm Wand und Ø10,0 × 20,0 mm Klebeverbinderanforderung.

## ENTFERNT

- Im ausgewählten SDF-NON-MASTER 169.923 Seed-42-Quelldreiecke ausschließlich
  im seam-definierten Problemfeld; 18.799 vermessene äußere Merkmalflächen im
  Problemfeld blieben erhalten.
- Keine bestätigte Quellgeometrie außerhalb der ROI entfernt.
- Keine vorhandene Fertigungsdatei ersetzt oder gelöscht.

## OFFEN

- `OPTIK_GATE: FAIL`: Augen/Nase/Ohren sind nicht sauber in die glatte Haut
  integriert; an den Diagnosefenstern bleiben sichtbare Öffnungen und harte
  Übergänge.
- Fusionierte Blatt-/Stachelflächen reichen weiterhin in Stirn/Gesichtsübergang.
- REF-SEAM ist visuell nicht plausibel kontinuierlich.
- Die lokale Rekonstruktion ist wegen 940 Randkanten und 209 bestätigten
  Kreuzungen nicht als Master- oder Druckgeometrie geeignet.
- Split, 1,6-mm-Hohlschalen, Ø10,0 × 20,0-mm-Klebeverbinder, Skalierung,
  CAD/STL und Montageformat sind durch das Gate nicht autorisiert.
- Physischer Druck-, Passungs-, Support-, Material- und 200-mm-Test bleibt
  offen und vor einem Optik-PASS nicht anwendbar.
- Finale Produkt- und Druckfreigabe bleibt ausschließlich beim Nutzer.

`STATUS: STOPP`

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

Grund: technischer Gate-Stopp; keine fehlende Nutzerentscheidung.

