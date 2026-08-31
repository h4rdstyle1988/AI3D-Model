# Herbst-Igel R02 – technischer Ergebnisstand R18

## Ergebnis

`STOPP`. Keine der drei lokal begrenzten Hybridvarianten erfüllt Gate 1 und
Gate 2 gleichzeitig. Gate 3 wurde deshalb nicht ausgeführt.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

Der Blocker ist weiterhin rein technisch. Es fehlt kein verbindliches Maß,
keine Funktion und kein reales Referenzdatum. Keine finale Nutzerfreigabe wird
behauptet.

## GEÄNDERT

- Die R18-Unterseiten-ROI wurde reproduzierbar aus dem realen R17-Fehlerbild,
  Bottom-Sichtbarkeit, Normalenrichtung und Boundary-/Non-Manifold-Inzidenz
  bestimmt.
- Zwei direkte, kleine/mittlere Quellflächen-Surgeries wurden gerechnet. Sie
  behalten außerhalb ihrer ROI sämtliche Seed-42-Flächen und -Koordinaten
  unverändert und retten das sichtbare Unterseitenrelief direkt.
- Nach demselben Topologiefehler beider Varianten wurde die Methode gewechselt:
  `relief-transfer-c` behält die R17-Manifold-Konnektivität und verschiebt nur
  ROI-Innenpunkte entlang Z; der Rand ist über zwölf Meshringe fest angebunden.
- Reale Front-/Links-/Rechts-/Heck-/Oben-/Unten- und 3/4-Ansichten,
  Unterseiten-Nahvergleich und REF-SEAM-Overlay wurden erzeugt.

## UNVERÄNDERT

- Seed 42, R17-Manifold und REF-CLEAN/REF-SEAM sind byte-identisch per SHA-256
  bestätigt.
- Keine neue Trellis-Generierung, kein neuer Seed, keine globale Skalierung und
  kein Redesign erfolgten.
- Produktidee, ca. 200 mm, zwei Druckteile, Farben/Materialien, nominal 1,6 mm
  Wand, REF-SEAM, Ø10,0 × 20,0-mm-Verbinder und Druckparameter wurden nicht
  geändert.
- Gesicht, Stirn, Augen, Schnauze, Ohren, Rückenblätter und das eine sichtbare
  Ahornblatt wurden nicht kreativ verändert.

## ENTFERNT

- In den beiden direkten Diagnosevarianten wurden ausschließlich innerhalb der
  automatisch bestimmten ROI verdeckte/doppelte Quellflächen entfernt:
  68.338 Flächen bei `direct-source-small-a` und 88.893 bei
  `direct-source-medium-b`.
- Außerhalb der ROI wurde keine Quellfläche entfernt oder verschoben.
- Keine bestätigte Produktionsdatei wurde ersetzt oder gelöscht.

## OFFEN / STOPP-GRUND

- `direct-source-small-a`: 82.623 offene und 4.285 nichtmanifolde Kanten.
- `direct-source-medium-b`: 92.050 offene und 4.095 nichtmanifolde Kanten.
- Diese Varianten schützen das Quellrelief optisch, können aber die bereits
  außerhalb der Unterseiten-ROI vorhandenen Quellfehler nicht lokal beseitigen.
- `relief-transfer-c` hat zwar 0 offene und 0 nichtmanifolde Kanten, aber die
  randgebundene Tiefenübertragung erfordert bis zu rund 160 mm Z-Verschiebung.
  Der Clearance-Audit weist eine negative Stichprobenfreiheit nach; reale
  Selbstschnitte sind damit nicht ausgeschlossen und Gate 1 bleibt FAIL.
- Gate 2 ist ebenfalls FAIL: Das Unterseitenrelief bleibt großflächig glatt,
  Übergangsrippen/-stufen sind sichtbar, und die R17-MLS-Rauheit außerhalb der
  ROI bleibt gegenüber Seed 42 bestehen. Die minimale Sieben-Ansichten-
  Silhouetten-IoU sinkt auf rund 0,953; Bottom-p95 beträgt rund 99,10 mm.
- Das REF-SEAM-Overlay ist erzeugt, kann ohne gate-konformen Master aber keine
  Splitfreigabe begründen.

## Gate 3

Nicht autorisiert und nicht ausgeführt. Es gibt keine Hohlschalen, keinen
REF-SEAM-Split, keinen Klebeverbinder, keine STL-/3MF-/GLB-Datei und keine
Support-, Orientierungs-, Slicer-, Passungs- oder Druckprüfung.

Ein Validator-PASS für die Ergebnisvollständigkeit ist keine Produktfreigabe.
