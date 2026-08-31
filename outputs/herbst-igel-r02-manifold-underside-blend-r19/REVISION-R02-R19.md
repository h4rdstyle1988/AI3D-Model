# Herbst-Igel R02 – technischer Ergebnisstand R19

## Ergebnis

`PASS` für den technischen R19-Auftrag. Gate 1 ist PASS; Gate 2 ist
`PASS_WITH_RESTPOINTS`; Gate 3 wurde danach ausgeführt und technisch validiert.
Reale Slicer-, Druck-, Passungs-, Supportentfernungs- und Montageprüfungen sind
weiter offen. Eine finale Nutzer- oder Produktfreigabe wird nicht behauptet.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

## GEÄNDERT

- Die optisch gute Seed-42-Außenfläche wurde als dichtes, eindeutig
  orientiertes Radialmanifold neu indiziert. Das war technisch notwendig, weil
  Seed-42 auch außerhalb der Unterseiten-ROI verteilte offene und
  nichtmanifolde Kanten enthält. 618.385 gültige, geschützte Radialzellen
  außerhalb der ROI blieben unverändert.
- Die R19-ROI umfasst 30.60 % des Winkelrasters und
  folgt R18-Tiefenfehler, realer Unterseitensichtbarkeit und fehlender
  Quellenstützung. Nur dort wurden ein zweifacher 3×3-Median und ein acht Zellen
  breiter kubischer Übergang angewandt.
- Die Unterseite ist sauber vereinfacht; R18-Rippen, extreme Z-Verschiebung und
  MLS-Flickrauheit wurden nicht übernommen.
- Nach Gate-1-/Gate-2-PASS wurden REF-SEAM-Split, zwei Hohlschalen, zentraler
  Klebeverbinder und Fertigungsexporte erzeugt.

## UNVERÄNDERT

- Ca. 200 mm Gesamtgröße; R19-Master-Istmaß 200.094 mm.
- Genau zwei Druckteile: Front/Körper in PLA Matt Desert Tan und
  Rücken/Stachelschale in PLA Metal Kupfer.
- Nominale Wanddicke 1,6 mm; 0,4-mm-Düse; Ziel 0,12 mm, adaptiv bis 0,08 mm.
- Gesicht frei; Augen, Nase, Ohren und Füße lesbar; Rücken-/Blattcharakter und
  genau ein sichtbares Ahornblatt erhalten.
- Verbinder Ø10,0 mm exakt und Eingriff 20,0 mm exakt.

## ENTFERNT

- Der verworfene Diagnoseprototyp mit ungestützter Unterkante bei etwa
  −108,92 mm wurde vollständig entfernt; die reale R19-Unterkante liegt bei
  -80.787 mm.
- Keine bestätigte Produktfunktion, kein Nutzermaß und keine freigegebene
  Produktionsgeometrie wurden entfernt.

## Gate 1 – Topologie

- eine Außenkomponente, watertight und 2-manifold;
- 0 offene Kanten, 0 nichtmanifolde Kanten/Vertices;
- 0 degenerierte oder doppelte Flächen;
- konsistente Außenorientierung, keine eingeschlossene Zusatzschale;
- 0 reale Selbstschnitte über den Radialgraph-/Sphärenkegel-Nachweis.

## Gate 2 – Formschutz

`PASS_WITH_RESTPOINTS`. Minimale Sieben-Ansichten-Silhouetten-IoU:
0.988850. Außerhalb der Bottom-Ansicht beträgt das
schlechteste p95 der sichtbaren Tiefendifferenz
0.388 mm. Der alte orthografische
Bottom-Tiefenwert ist wegen realer Seed-42-Mehrfachlagen nur diagnostisch; die
maßgebliche ROI-Radialänderung beträgt p95
0.074 mm und die reale Nahansicht ist
stufen-, rippen- und flickstellenfrei. Restpunkt ist die ausdrücklich erlaubte
saubere Vereinfachung des verdeckten zentralen Unterseitenreliefs.

## Gate 3 – CAD/FDM

- Frontteil: 791,512 Dreiecke, 0 offene und 0
  nichtmanifolde Kanten.
- Rückenteil: 1,853,416 Dreiecke, 0 offene und 0
  nichtmanifolde Kanten.
- Wand: radial nominal 1,6 mm; Kappen-Referenzabstand an der Verbinderachse
  1,6 mm.
- Pin: Ø10.0 mm exakt; Eingriff X=0,0
  bis X=20.0 mm, also 20,0 mm exakt.
- Aufnahme: Ø10.30 mm; dokumentiertes Klebespiel
  0.30 mm diametral bzw.
  0.15 mm radial.
- 3MF enthält zwei Objekte; GLB enthält zwei Knoten/Netze.

## OFFEN / reale Prüfungen

- Real slicer preview at 0.12 mm / adaptive 0.08 mm.
- Printed wall-thickness coupon or section measurement.
- Real Ø10.0-mm pin / Ø10.30-mm socket glue-fit coupon.
- Support removal check without contact damage to face, leaf or spine relief.
- Dry assembly and user final product approval.

Ein STL-, Manifold- oder Validator-PASS ist keine finale Produktfreigabe.
