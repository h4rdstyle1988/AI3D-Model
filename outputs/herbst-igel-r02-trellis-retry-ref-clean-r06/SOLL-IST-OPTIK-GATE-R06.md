# Herbst-Igel R02 – SOLL/IST-Optik-Gate R06

## Gate-Ergebnis

`OPTIK-GATE: FAIL`

`STATUS: STOPP`

Der Trellis-Rohmesh ist im ersten Gesamteindruck als stilisierter Igel
erkennbar und nicht als Maus, Hamster, Ratte, Bürste oder Blüte. Für den
verbindlichen Maßstab „wie Referenz“ ist das Ergebnis dennoch nicht eindeutig
ausreichend: Die Blatt-/Stachelformen hängen weit über Stirn, Augenbereich und
Gesicht. Dadurch fehlen die bestätigte natürliche Körper/Rücken-Grenze nach
REF-SEAM und die klare rundliche, überwiegend freie Gesichtsfläche der
Primärreferenz.

Die direkte Gegenüberstellung liegt unter
`renders-optik-gate/optic-gate-soll-ist-r06.png`; die sechs echten
Rohmesh-Renders und das Kontaktblatt liegen im selben Ordner.

## Einzelprüfung

| Kriterium | IST am unveränderten Rohmesh | Ergebnis |
|---|---|---|
| eindeutig Herbst-Igel, keine ausgeschlossene Alternativform | Igel-Silhouette, Gesicht und Stachel-/Blattrücken sind erkennbar | PASS |
| kompakte bodennahe Silhouette | kompakte, niedrige Figur mit kurzen Auflagefüßen | PASS |
| rundlicher heller Körper / Gesicht | rundliche Gesichtsgrundform vorhanden, aber durch zahlreiche herabhängende Rückenformen stark überdeckt; klare freie Gesichtsfläche der Referenz fehlt | FAIL |
| kurze weiche Schnauze mit schwarzer Nase als Geometrie | kurze Schnauze und Nasengeometrie vorhanden; Farbwirkung ist am untexturierten Rohmesh nicht bewertbar | PASS GEOMETRIE |
| zwei kleine runde Ohren | beidseitige runde Ohrgeometrie vorhanden | PASS |
| große runde Augen als Geometrie | beidseitige runde Augengeometrie vorhanden | PASS |
| vier kurze sichtbare Füße | kurze Vorder-/Hinterfußgeometrie ist in Links-/Rechtsansicht vorhanden | PASS |
| gewölbter Rücken mit einzelnen überlappenden Blatt-/Stachelformen | klar vorhanden | PASS |
| Richtung und Dichte wie Referenz | Dichte und Überlappung vorhanden, aber mehrere lange Formen laufen frontal bis an Augen und Schnauze statt hinter der REF-SEAM zu enden | FAIL |
| genau ein sichtbares Ahornblatt auf der gezeigten Seite | ein deutliches Ahornblatt in der linken/Referenzseite sichtbar | PASS |
| kein zweites erfundenes Ahornblatt | auf der Gegenseite kein zweites vollständiges Ahornblatt erkennbar | PASS |
| natürliche Körper/Rücken-Grenze nach REF-SEAM | die Referenzlinie hinter Ohren und seitlich am Körper wird durch eine frontale Blatt-/Stachel-Schürze deutlich überschritten | FAIL |

## Verbindliche Folge

Wegen `OPTIK-GATE: FAIL` endet der Workflow vor jeder CAD-/FDM-Aufbereitung.
Es wurden daher bewusst nicht erzeugt:

- keine parametrische oder anderweitige Ersatzfigur,
- keine Körper- oder Rückenschale,
- keine Körper- oder Rücken-STL,
- keine Montage-GLB/3MF,
- keine Steckverbindung,
- keine Skalierung auf ca. 200 mm,
- keine Wandstärken-, Selbstschnitt-, Kollisions-, Support- oder
  Druckvalidierung.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

Grund: Es fehlt keine konstruktive Nutzerangabe. Der STOPP ist die im Auftrag
vorgegebene technische Folge eines nicht eindeutig bestandenen Optik-Gates.

Eine finale Produkt-, Optik- oder Druckfreigabe wird nicht behauptet.

