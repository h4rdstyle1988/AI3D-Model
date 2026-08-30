# Herbst-Igel – Revision R02 / technische Rekonstruktion R09

## GEÄNDERT

- Byteidentischer Seed-42-Rohstand aus R08 als einzige Masterformbasis verwendet.
- Lokales Problemfeld mit der unveränderten R08-Projektion von REF-SEAM, der
  Unterkörpergrenze `Z = -0,105` und den bereits vermessenen Merkmalmasken
  bestimmt.
- 137.183 Quelldreiecke, die das seam-definierte lokale Körperfeld schneiden,
  aus dem NON-MASTER-Versuch entfernt.
- Eine glatte, zweiseitige Körperflächen-Rekonstruktion mit 46.016 Punkten und
  90.336 Dreiecken aus REF-SEAM-Körpersilhouette und der robust gemessenen Tiefe
  angrenzender unveränderter Seed-42-Geometrie erzeugt.
- Reale Geometrie in sechs Pflichtansichten sowie als SOLL/IST-Blatt gerendert.

## UNVERÄNDERT

- Alle 436.742 Seed-42-Quellpunktkoordinaten; kein bestehender Punkt wurde
  verschoben.
- Normalisierte Gesamtgrenzen und Gesamtausdehnungen des Seed-42-Stands.
- Quellgeometrie außerhalb der lokalen Körperseiten-Selektion, einschließlich
  gewölbtem Rücken und vorhandenem Ahornblatt.
- Unterkörper/Füße unterhalb der Schutzgrenze.
- Produktidee, ca. 200 mm Zielausdehnung, zwei Teile, Materialien, nominal
  1,6 mm Wand und Ø10,0 × 20,0 mm Klebeverbinderanforderung.

## ENTFERNT

- Ausschließlich Quelldreiecke im technisch definierten lokalen Problemfeld des
  NON-MASTER-Versuchs; keine neue Funktion, Halterung, Rastung, Führung oder
  Produktnutzung ergänzt.
- Keine Fertigungsdatei gelöscht oder ersetzt; R09 erzeugte aufgrund des Gates
  keine Fertigungsdatei.

## OFFEN

- `OPTIK_GATE: FAIL`: Gesicht, Merkmale und REF-SEAM-Übergang sind nicht
  eindeutig referenznah; der Patch zeigt harte fächer-/blockartige Artefakte.
- Der NON-MASTER ist nicht watertight (12.296 Randkanten, 3.875 Kanten mit
  Inzidenz größer zwei) und ausdrücklich nicht druckbar.
- Split, zwei 1,6-mm-Hohlschalen, Verbinder, Produktionsskalierung, STL und
  Montageformat wurden durch das Gate nicht autorisiert.
- Physischer Druck-, Passungs-, Support- und Materialtest bleibt offen und vor
  einem Optik-PASS nicht anwendbar.
- Finale Produkt- und Druckfreigabe bleibt ausschließlich beim Nutzer.

`STATUS: STOPP`

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

Grund: technischer Gate-Stopp; keine fehlende Nutzerentscheidung.

