# Herbst-Igel R02 – technischer Ergebnisstand R17

## Ergebnis

`STOPP` nach Gate 2. Die ausgewählte sichtbarkeitsorientierte Außenhaut
`screened-mls-d` besteht Gate 1, Gate 2 Formschutz ist jedoch `FAIL`. Gate 3
(REF-SEAM-Split, Hohlschalen, Klebeverbinder, STL, 3MF/GLB und FDM-Prüfung)
wurde deshalb nicht ausgeführt.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

Der Blocker ist rein technisch: Keine verbindliche Funktion und kein
Nutzermaß fehlt. Die getesteten Oberflächenrekonstruktionen erhalten die
Gesamtfigur wesentlich besser als R16, können die sichtbare Unterseitenstruktur
aber noch nicht ohne Glättung, Randläufer oder sichtbare Oberflächenrauheit in
eine einzige saubere Außenhaut überführen.

Keine finale Nutzerfreigabe wird behauptet.

## GEÄNDERT

- Die byte-identische optisch beste Seed-42-Quelle wurde aus dem dokumentierten
  R16-Ergebnis übernommen und per SHA-256 geprüft.
- Quellflächen wurden mit 14 deterministischen Außenansichten nach Sichtbarkeit,
  Orientierung und Quellauflösung klassifiziert; verdeckte Samples wurden nicht
  als Formdaten verwendet.
- Drei orientierte Poisson-Varianten (`small-a`, `medium-b`, `fine-c`) wurden in
  abgestufter Auflösung geprüft.
- Nach fortbestehendem Unterseitenfehler wurde regelkonform auf die unabhängige
  lokale, orientierte Screening-Methode `screened-mls-d` gewechselt.
- Für alle Kandidaten wurden reale Geometrieansichten und Form-Delta-Daten
  erzeugt; für den ausgewählten Diagnosekandidaten liegen sechs Ansichten,
  sechs SOLL/IST-Paare und ein Referenz-/Quell-/Kandidatenblatt vor.

## UNVERÄNDERT

- Produktidee, ca. 200 mm Gesamtgröße, Proportionen, Materialien, Farben,
  Zweiteiligkeit, nominal 1,6 mm Wand, REF-SEAM, Verbinder Ø10,0 mm / 20,0 mm
  Eingriff und Druckparameter wurden nicht geändert.
- Gesicht, Augen, Nase, Ohren, kurze Füße, Rücken-/Blattcharakter und das eine
  sichtbare Ahornblatt wurden nicht kreativ umgestaltet.
- Kein neuer Seed, keine Trellis-Neugenerierung und kein Redesign erfolgten.

## ENTFERNT

- Nicht außen sichtbar klassifizierte Quellsamples werden nicht als
  Rekonstruktionsdaten verwendet.
- Kleine, vom impliziten Feld getrennte Nebenschalen werden deterministisch vor
  der Gate-1-Ausgabe verworfen und im jeweiligen Audit gezählt.
- Keine bestätigte Produktgeometrie wurde überschrieben oder gelöscht.

## OFFEN

- Gate 2 FAIL: In der Unteransicht wird sichtbares Quellrelief durch eine glatte
  Schließfläche ersetzt. Poisson-Varianten erzeugen zusätzlich kleine Läufer an
  den tiefsten Fußbereichen; die MLS-Variante entfernt die langen Läufer, zeigt
  aber sichtbare Oberflächenrauheit.
- REF-SEAM ist auf der rekonstruierten Außenhaut noch nicht ausreichend klar
  demonstriert.
- Reale Druck-, Montage-, Passungs-, Wand-, Verbinder-, Support- und Slicertests
  bleiben gesperrt, weil Gate 2 nicht bestanden ist.

## Gate 1 – PASS für `screened-mls-d`

- genau eine ausgewählte Außenkomponente
- watertight und 2-manifold
- 0 offene Kanten
- 0 Non-Manifold-Kanten/-Vertices
- 0 degenerierte oder doppelte Flächen
- 0 eingeschlossene Schalen in der ausgewählten Komponente
- 0 bestätigte reale Selbstschnitte durch konsistente Tetraederkomplex-
  Konstruktion und exhaustive Kanten-/Duplikatprüfung

## Gate 2 – FAIL

Die Gesamtfigur, Silhouette, freie runde Gesichtsfläche, Nase, Ohren, kurze
Füße, Rückenblätter und genau ein sichtbares Ahornblatt bleiben grundsätzlich
lesbar. Der ausgewählte Kandidat erreicht über die sechs Ansichten eine minimale
Silhouetten-IoU von rund 0,983 zur besten Quelle. Dieser Wert reicht nicht zur
Freigabe: Der visuell harte Unterseitenfehler bleibt bestehen, und die lokale
Screening-Variante zeigt eine sichtbare Rauheit. Das erfüllt die Forderung
„keine Aufblähung, Schrumpfung, Stufe oder verschmiertes Relief“ nicht.

## Gate 3 – nicht ausgeführt

Es wurden keine Split-/Hohl-/Connector-Geometrie, keine STL-Dateien und keine
Assembly-3MF/GLB erzeugt. Ein erfolgreicher Topologiecheck ist keine finale
Produktfreigabe.
