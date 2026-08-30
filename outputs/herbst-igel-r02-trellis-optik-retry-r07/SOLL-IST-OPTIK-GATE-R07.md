# Herbst-Igel R02 – SOLL/IST-Optik-Gate R07

## Gate-Ergebnis

`OPTIK-GATE: FAIL`

`STATUS: STOPP`

Keiner der vier unveränderten nativen Trellis-Rohkandidaten besteht sämtliche
verbindlichen Optikkriterien eindeutig. Seed 42 bleibt der beste Kandidat,
weil er den Gesamtcharakter und als einziger Kandidat das eine sichtbare
Ahornblatt klar erhält. Er reproduziert jedoch bytegenau den bereits in R06
festgestellten Fehler: Blatt-/Stachelformen hängen über Stirn, Augenbereich und
Gesicht und überschreiten die autoritative Körper/Rücken-Grenze.

Die gemeinsame visuelle Gegenüberstellung liegt in
`renders-optik-gate/candidate-comparison-r07.png`. Für jeden Seed liegen
zusätzlich sechs Renders direkt aus dem unveränderten Rohmesh vor: 3/4 vorne,
links, rechts, hinten, oben und unten.

## Vergleich der Varianten

| Seed | Stärke gegenüber Referenz | Verbindliche Abweichung | Ahornblatt | REF-SEAM / Gesichtsfreiraum | Gate |
|---:|---|---|---|---|---|
| 42 | beste Gesamtähnlichkeit; kompakte bodennahe Silhouette; Nase, zwei Ohren, Augen und kurze Füße klar; gewölbter überlappender Rücken | zahlreiche lange Blatt-/Stachelformen reichen bis Stirn, Augen und Schnauze | genau eines auf Referenzseite, kein zweites | natürliche Grenzlinie deutlich überschritten; Gesicht nicht frei | FAIL – bester Kandidat |
| 7 | klarer Igel; kurze Schnauze, Nase, runde Augen und Ohren; vier kurze Füße über die Ansichten erkennbar | stärker frontalisierte, radial kronenartige Stachelanordnung; mehrere Formen hängen zentral bis zwischen Augen/Nase | kein eindeutig einzelnes Ahornblatt | Grenze hinter Ohren und seitlich am Körper nicht referenzgetreu | FAIL |
| 123 | klarer Igel; relativ runde Gesichtsgrundform; Nase, Augen, Ohren und kurze Füße vorhanden | ebenfalls frontalisierte Stachelkrone; Blatt-/Stacheldichte und Richtung weichen ab; Stirn wird überdeckt | kein eindeutig einzelnes Ahornblatt | natürliche REF-SEAM-Grenze wird nicht eingehalten | FAIL |
| 777 | Igelgrundform und einzelne Rückenformen erkennbar | großflächige unerwünschte Boden-/Hintergrundgeometrie ist Bestandteil des Rohmeshs; Proportion/Gesamteindruck dadurch nicht referenzgetreu | kein eindeutig einzelnes Ahornblatt | Grenzlinie und bodennahe Produktsilhouette nicht belastbar bewertbar | FAIL |

## Kriterienmatrix

| Verbindliches Kriterium | Seed 42 | Seed 7 | Seed 123 | Seed 777 |
|---|---|---|---|---|
| kompakte bodennahe Silhouette | PASS | PASS | PASS | FAIL |
| rundlicher heller Körper / freie Gesichtsfläche | FAIL | FAIL | FAIL | FAIL |
| kurze weiche Schnauze mit Nase | PASS Geometrie | PASS Geometrie | PASS Geometrie | PASS Geometrie |
| zwei kleine runde Ohren | PASS | PASS | PASS | PASS |
| große runde Augen als Geometrie | PASS | PASS | PASS | PASS |
| vier kurze sichtbare Füße über die Ansichten | PASS | PASS | PASS | FAIL |
| gewölbter Rücken mit überlappenden Formen | PASS | PASS | PASS | PASS |
| Blatt-/Stachelrichtung und Dichte wie Referenz | FAIL | FAIL | FAIL | FAIL |
| keine unnatürliche Überdeckung von Stirn/Augen/Schnauze | FAIL | FAIL | FAIL | PASS, aber Gesamtkandidat unbrauchbar |
| genau ein sichtbares Ahornblatt auf Referenzseite | PASS | FAIL | FAIL | FAIL |
| kein zweites erfundenes Ahornblatt | PASS | PASS | PASS | PASS |
| natürliche Körper/Rücken-Grenze nach REF-SEAM | FAIL | FAIL | FAIL | FAIL / nicht belastbar |

## Verbindliche Folge

Wegen `OPTIK-GATE: FAIL` endet der Workflow vor jeder CAD-/FDM-Aufbereitung.
Es wurden daher bewusst keine Körper-/Rückenschalen, keine STL-Dateien, keine
Montagedatei und keine Steckverbindung erzeugt. Wandstärken-, Maß-,
Selbstschnitt-, Kollisions-, Support- und Druckvalidierungen sind am
Trellis-Rohmesh nicht anwendbar und wurden nicht schöngerechnet.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

Grund: Es fehlt keine reale Nutzerangabe und kein verbindliches Maß. Der STOPP
ist die im Auftrag vorgeschriebene technische Folge, wenn kein Kandidat das
Optik-Gate eindeutig besteht.

Eine finale Produkt-, Optik- oder Druckfreigabe wird nicht behauptet.
