# Herbst-Igel R02 – technischer Ergebnisstand R16

## Ergebnis

`STOPP` nach Gate 2. Gate 1 der ausgewählten Envelope-Hülle ist PASS; Gate 2
Formschutz ist FAIL. Gate 3 (Split, Hohlschalen, Verbinder, STL/3MF/GLB und
FDM-Prüfung) wurde deshalb regelkonform nicht ausgeführt.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

Grund: Der verbleibende Blocker ist technisch. Die getestete deterministische
Sechs-Tiefenkarten-/Voxel-Envelope verbindet in den realen Sichtansichten
getrennte sichtbare Tiefenlagen und verschluckt Gesicht und Blattrelief. Es
fehlt kein verbindliches Nutzermaß und keine Produktfunktion muss geändert
werden.

Keine finale Nutzerfreigabe wird behauptet.

## GEÄNDERT

- Eine neue technische Master-Außenhülle wurde aus der byte-identischen,
  optisch besten Seed-42-Quelle rekonstruiert und auf 200 mm maximale
  Gesamtausdehnung skaliert.
- Drei deterministische Varianten wurden geprüft: `coarse-a`, `fine-b` und
  `fine-c-no-close`.
- Reale Geometrie-Renders für 3/4 vorne, links, rechts, hinten, oben und unten
  sowie ein SOLL/IST-Blatt wurden erzeugt.
- Topologie-, Hash-, bidirektionale Sichttiefen-, Silhouetten- und
  Iterationsberichte wurden erzeugt.

## UNVERÄNDERT

- Seed 42 und die autoritativen REF-CLEAN-/REF-SEAM-Dateien sind per SHA-256
  byte-identisch geprüft.
- Verbindliche Nutzermaße, Produktidee, Materialvorgaben, Farben, Teilanzahl,
  REF-SEAM, Wandstärke, Verbindermaße und Druckparameter wurden nicht geändert.
- Es wurde keine neue Figur, kein neuer Seed und kein Trellis-Vollauf erzeugt.

## ENTFERNT

- Interne Seed-42-Flächen, Doppel-/Tiefenlagen und verdeckte Kreuzungsschichten
  sind nicht Bestandteil der ausgewählten Master-Außenhaut. Die Masterhaut ist
  ausschließlich die exponierte Grenze eines einzigen zusammenhängenden
  Volumens.
- Keine bestehende bestätigte Produktionsgeometrie wurde gelöscht oder
  überschrieben.

## OFFEN

- Gate 2 ist nicht erfüllt: Augen, Nase, Ohren, Gesichtskontur, Blatt-/Stachel-
  relief, das einzelne Ahornblatt und REF-SEAM sind in der Envelope-Hülle nicht
  zuverlässig lesbar.
- Eine andere deterministische Außenflächenmethode mit echter
  Sichtflächenbindung ist technisch erforderlich. Reine weitere Pitch- oder
  Closing-Iteration innerhalb der geprüften Projektion ist nach den R16-
  Varianten nicht sinnvoll.
- Reale Druck-, Montage- und Passungstests sind nicht ausführbar, da Gate 3
  gesperrt blieb.

## Gate 1 – PASS für `fine-b`

- genau 1 Oberflächenkomponente
- watertight: ja
- 2-manifold: ja
- offene Kanten: 0
- Non-Manifold-Kanten: 0
- Non-Manifold-Vertices: 0
- degenerierte Flächen: 0
- doppelte Flächen: 0
- bestätigte Selbstschnitte: 0
- interne eingeschlossene Schalen: 0
- überlappende Doppelhaut: nein

Die Selbstschnittprüfung ist für den erzeugten cubical complex vollständig:
Ausgegeben werden nur Hälften eindeutig exponierter Zellflächen; interne
Zellflächen werden verworfen. Zusätzlich wurden alle indizierten
Kanteninzidenzen und doppelten Dreiecke exhaustiv geprüft.

## Gate 2 – FAIL

`fine-b` verbessert die mediane sichtbare Tiefenabweichung gegenüber
`coarse-a`, erreicht aber je nach Ansicht p95-Abweichungen von etwa 1,87 mm bis
47,77 mm. Die Silhouette bleibt mit IoU 0,973 bis 0,991 nahe am Seed, schützt
aber die reale Oberflächenform nicht. Die sechs Renders zeigen die
entscheidenden Merkmale als weitgehend geschlossene Masse statt als lesbares
Gesicht und Blattrelief.

Die gezielte Variante ohne volumetrisches Closing erzeugte 46 Komponenten und
45 eingeschlossene Schalen und scheiterte bereits Gate 1. Damit ist Closing
für die Ein-Komponenten-Topologie nötig, aber nicht die alleinige Ursache des
Gate-2-Formverlusts.

## Gate 3 – nicht ausgeführt

Es wurden keine Split-/Hohl-/Connector-Geometrie, keine STL-Dateien und keine
Assembly-3MF/GLB erzeugt. Das schützt die verbindliche Produktbasis vor einer
Fertigung auf Basis einer optisch verworfenen Außenform.
