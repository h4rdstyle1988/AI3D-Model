# Herbst-Igel R02 – SOLL/IST und Optik-Gate

## Ergebnis

`OPTIK-GATE: FAIL`

`STATUS: STOPP`

Die direkte Bildgegenüberstellung liegt unter
`renders-optik-gate/optic-gate-soll-ist.png`. Die sechs orthografischen
Rohmesh-Ansichten liegen im selben Ordner. Es handelt sich ausdrücklich um
Renders des tatsächlichen Trellis-Rohmeshes, nicht um eine parametrische
Ersatzfigur.

## Referenzbefund

Beide vorgeschriebenen SHA-256-Werte stimmen exakt. Die konkrete
`REF-CLEAN`-Datei ist dennoch ein unvollständiger JPEG-Datenstrom. Ein strikter
Decoder meldet `broken data stream`; verwertbare Bildvariation endet bei Zeile
128 von 319. Trellis akzeptiert den Stream tolerant, die eigene
BiRefNet-Freistellung enthält aber nur den Stachelrücken sowie kleine
Ohr-/Kopfreste. Körper, Gesicht, Füße und dekoratives Blatt fehlen bereits in
der Trellis-Eingabeaufbereitung.

`REF-SEAM` ist vollständig decodierbar, ist laut freigegebenem Auftrag jedoch
nur für die Trennlinie autoritativ und darf nicht still zur primären
Formquelle umgewidmet werden.

## Verbindliches Optik-Gate

| Kriterium | SOLL laut Referenz | IST Trellis-Rohmesh | Ergebnis |
|---|---|---|---|
| Allgemeine Silhouette | niedriger, kompakter, horizontaler Igel | hohe blatt-/bürstenartige Form mit Schaft und großer Hintergrundfläche | FAIL |
| Kopf-/Körperproportion | klarer heller Kopf vor rundem Körper | kein identifizierbarer Igelkopf oder Igelkörper | FAIL |
| Schnauzenform | kurze, weiche, nach vorn zulaufende Igelschnauze | fehlt | FAIL |
| Ohrform und -position | zwei kleine runde Ohren am Kopf | fehlen als eindeutige Körpermerkmale | FAIL |
| Bauch/Füße/Haltung | sitzender, bodennaher Körper mit vier sichtbaren Füßen | kein Bauch und keine Igelhaltung; schmaler vertikaler Schaft | FAIL |
| Verlauf Stachel-/Blätterrücken | gewölbter Rücken entlang des Igelkörpers | isolierte hochformatige Blatt-/Stachelkrone | FAIL |
| Dichte/Richtung/Überlappung | gerichtete, überlappende Kupferstacheln über rundem Rücken | lokale Blattstruktur vorhanden, aber auf falscher Gesamtform | FAIL |
| Genau ein sichtbares Ahornblatt | ein Blatt seitlich am Rücken | kein erkennbares Ahornblatt | FAIL |
| Trennlinie | blaue Nutzerkontur zwischen Körper und Rücken | mangels Körper nicht anwendbar | FAIL |
| Gesamteindruck | eindeutig Igel, nicht Maus/Hamster/Ratte | weder Igel noch Nagetier; eher Bürste/Blüte auf Schaft | FAIL |

## Gate-Folge

Der freigegebene Workflow verbietet nach diesem Ergebnis eine technische
Aufbereitung. Deshalb wurden insbesondere **nicht** erzeugt:

- keine parametrische oder anderweitige Ersatzfigur,
- kein CAD-Schalenmodell,
- keine Körper-STL,
- keine Rücken-STL,
- keine Montage-GLB/3MF,
- keine Steckverbindung,
- keine Skalierung auf 200 mm,
- keine Wandstärken-, Selbstschnitt-, Kollisions- oder Supportvalidierung.

Diese fehlenden technischen Dateien sind keine übersehenen Liefergegenstände,
sondern die vorgeschriebene Folge des nicht bestandenen Optik-Gates.

## Offener Punkt

Zum regelkonformen Fortsetzen wird entweder eine vollständige, decodierbare
`REF-CLEAN` mit neu freigegebenem Hash benötigt oder eine ausdrückliche
Nutzerfreigabe, eine andere konkrete Datei als primäre Trellis-Formquelle zu
verwenden. Die vorhandene `REF-SEAM` wird nicht ohne diese Freigabe umgedeutet.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: true`

Grund: Die erforderliche primäre Optikreferenz enthält real keine vollständige
Figur; eine Ersatzquelle oder Rekonstruktion wäre eine Änderung der
verbindlichen Formquelle.

Eine finale Produktfreigabe wird nicht behauptet.

