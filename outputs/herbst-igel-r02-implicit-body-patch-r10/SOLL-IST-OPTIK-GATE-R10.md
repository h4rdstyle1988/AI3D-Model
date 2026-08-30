# Herbst-Igel R02 – SOLL/IST-Optik-Gate R10

## Gate-Ergebnis

`OPTIK_GATE: FAIL`

`STATUS: STOPP`

Die beiden Varianten wurden zunächst aus ihrer realen PLY-Geometrie in
`renders-optik-gate/variant-screening-r10.png` verglichen. Die vollständigen
sechs Einzelansichten, das Kontaktblatt und
`renders-optik-gate/soll-ist-optik-gate-r10.png` stammen direkt aus dem
ausgewählten SDF-NON-MASTER. Referenzen wurden nicht retuschiert oder in
Produktgeometrie umgewandelt.

## Prüfung der verbindlichen Kriterien

| Kriterium | IST R10 | Gate |
|---|---|---|
| Gesicht frei und rundlich wie REF-CLEAN | Niedrigfrequente Haut ist glatt, aber Merkmalsübergänge und Stirn bleiben nicht referenznah frei | FAIL |
| keine Blatt-/Stachelüberdeckung von Stirn, Augen oder Schnauze | Restliche fusionierte Strukturen reichen in Stirn und Gesichtsübergang | FAIL |
| kurze weiche Schnauze/Nase erhalten | Quellgeometrie wurde geschützt, erscheint aber getrennt/angeschnitten statt sauber eingebettet | FAIL |
| beide runden Ohren erhalten | Quellflächen vorhanden, Form und Übergang jedoch nicht in beiden maßgeblichen Seitenansichten eindeutig sauber | FAIL |
| Augenform erhalten | Schutzflächen vorhanden, aber sichtbare Öffnungen und unvollständige Integration | FAIL |
| vier kurze Füße erhalten | Quellgeometrie unter Schutzgrenze unverändert erhalten | PASS |
| Rücken gewölbt mit überlappender Blatt-/Stachelstruktur | außerhalb der ROI unverändert erhalten | PASS |
| genau ein sichtbares Ahornblatt, kein zweites | vorhandenes Blatt erhalten; kein Blatt ergänzt | PASS |
| REF-SEAM visuell plausibel | harte beziehungsweise offene Übergänge und Restüberdeckung | FAIL |
| keine Patch-Beule, Delle, harte Stufe oder sichtbare Reparatur | sichtbare Fenster/Öffnungen; 940 lokale Randkanten und 209 bestätigte Kreuzungen | FAIL |

## Technische Auswahl

- SDF: ausgewählt; identische REF-SEAM-Messbasis, geringste Feldabweichung.
- RBF: 324 Gauß-Stützstellen, RMSE `0,0150493` im Körper-Bounding-Box-Feld;
  visuell derselbe Merkmalsintegrationsfehler.
- Glattheit der ausgewählten impliziten Teilfläche: medianer absoluter
  Dihedralwinkel `0,028°`, P95 `7,848°`; der niedrige Frequenzkörper selbst
  ist glatt, die offenen Übergänge bestehen das Endoberflächen-Gate dennoch
  nicht.

## Verbindliche Folge

Gemäß R10 endet die Ausführung vor REF-SEAM-Split, Hohlschalen,
Ø10,0 × 20,0 mm Klebeverbinder, Produktionsskalierung, STL und Montagedatei.
Die PLY-Dateien sind reproduzierbare `NON-APPROVED`-Versuche, keine
freigegebene Masterform.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

Grund: technischer Optik-Gate-Stopp; Nutzermaß und Produktfunktion sind
vollständig, müssen aber nicht geändert werden.

Eine finale Produkt-, Optik- oder Druckfreigabe wird nicht behauptet.

