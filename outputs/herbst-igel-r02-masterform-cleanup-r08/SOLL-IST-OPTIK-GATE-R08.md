# Herbst-Igel R02 – SOLL/IST-Optik-Gate R08

## Gate-Ergebnis

`OPTIK_GATE: FAIL`

`STATUS: STOPP`

Der reale lokale Cleanup-Versuch ist in `renders-masterform/soll-ist-masterform-r08.png` gegen REF-CLEAN und REF-SEAM dargestellt. Die sechs Einzelansichten und das Kontaktblatt stammen direkt aus `masterform/herbst-igel-r02-masterform-cleanup-attempt-r08-NON-MASTER.ply`.

Die Blatt-/Stachelüberhänge vor der autoritativen REF-SEAM wurden durch eine ausschließlich lokale, maskierte Hüllkurvenprojektion und Taubin-Relaxation reduziert. Sie wurden jedoch nicht belastbar entfernt: In 3/4-Front-, linker und rechter Ansicht bleiben verschmolzene beziehungsweise gefaltete Blattkörper und Blattkonturen auf Stirn und im Augen-/Gesichtsbereich sichtbar. Zugleich sind an der lokal stärker projizierten Oberfläche erste Artefakte sichtbar. Der Versuch ist deshalb ausdrücklich `NON-MASTER`.

## Prüfung der verbindlichen Kriterien

| Kriterium | IST R08 | Gate |
|---|---|---|
| kompakte bodennahe Silhouette | erhalten | PASS |
| rundlicher heller Körper / freie Gesichtsfläche | Gesichtsgrundform erkennbar, aber Blattlagen und Konturen liegen weiter im Gesicht | FAIL |
| kurze weiche Schnauze mit Nase | Geometrie erhalten | PASS |
| zwei kleine runde Ohren | Geometrie erhalten | PASS |
| große runde Augen als Geometrie | Geometrie erhalten | PASS |
| vier kurze sichtbare Füße | über die Ansichten erhalten | PASS |
| gewölbter Rücken mit einzelnen überlappenden Formen | außerhalb der Cleanup-Maske exakt geschützt | PASS |
| Blatt-/Stachelrichtung und Dichte wie Referenz | im Gesichtsübergang weiterhin zu dicht und zu weit nach vorn/unten reichend | FAIL |
| keine unnatürliche Überdeckung von Stirn, Augen und Schnauze | weiterhin nicht erfüllt | FAIL |
| genau ein sichtbares Ahornblatt auf der Referenzseite | erhalten | PASS |
| kein zweites erfundenes Ahornblatt | erfüllt | PASS |
| natürliche Körper/Rücken-Grenze nach REF-SEAM | durch verbliebene Falt-/Blattflächen weiterhin überschritten | FAIL |

## Warum lokales Entfernen nicht belastbar fortgesetzt wurde

Die Vorprüfung des unveränderten Seed-42-Netzes ergab 436.742 Punkte, 870.466 Dreiecke, 8.608 offene Randkanten und 5.079 Kanten mit Inzidenz größer zwei. Eine durchgehende verdeckte Körperhaut hinter den Überhängen ist nicht vorhanden. Die konservative Tiefenlagenprüfung bestätigte eine zusätzliche Körperlage nur in 759 von 24.326 abgetasteten Körperpixeln, also 3,12 % der tatsächlich abgetasteten seam-definierten Fläche.

Der zulässige lokale Rekonstruktionsversuch bewegte 39.045 von 436.374 verwendeten Punkten; 397.329 Punkte blieben exakt unverändert. Rücken, Ahornblatt und die referenzbasierten Schutzbereiche für Ohren, Augen, Nase und Füße wurden nicht verändert. Trotz maximal 0,08708 normalisierter lokaler Verschiebung bleibt der Gate-Fehler sichtbar. Eine weitere Bereinigung müsste großflächig neue Gesichtsflächen beziehungsweise eine neue semantische Retopologie erzeugen; sie wäre nicht mehr belastbar tangential aus einer vorhandenen Körperhaut ableitbar und würde die Schutzgrenze des Auftrags überschreiten.

## Verbindliche Folge

Gemäß Schritt 10 des R08-Auftrags endet die Ausführung vor Split, Schalen, Verbinder, STL und Montagedatei. Es wurden keine Druckdateien erzeugt und keine parametrische Ersatzfigur gebaut.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

Grund: Es fehlt keine reale Nutzerangabe. Der STOPP folgt technisch aus dem nicht bestandenen Optik-Gate und der nachgewiesenen Grenze eines lokalen seam-geführten Cleanups.

Eine finale Produkt-, Optik- oder Druckfreigabe wird nicht behauptet.
