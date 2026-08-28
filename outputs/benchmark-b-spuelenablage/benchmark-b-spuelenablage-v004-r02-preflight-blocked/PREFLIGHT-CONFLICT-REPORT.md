# v004-r02 – PREFLIGHT-KONFLIKTBERICHT

Status: **STOPP VOR GEOMETRIEÄNDERUNG**  
v004-r01-Geometrie: **unverändert; alle sieben Referenz-Hashes stimmen mit dem Manifest überein**

## Blocker 1 – verbindliche Halterfreiheit

Die Gitterunterseite liegt bei Z=27.00 mm. Für 18,5 mm freie Tiefe darf der Boden höchstens Z=8.50 mm erreichen; für 19,0 mm höchstens Z=8.00 mm. Der vorhandene Boden liegt an der Steckwabe bei Z=12.377 mm. Er müsste damit um 3.877 bis 4.377 mm abgesenkt werden.

Bei unveränderter 2-mm-Bodenschale läge deren Unterseite auf Z=6.50 bis Z=6.00 mm. Am Ort der Steckwabe existiert kein hinterer Fuß; die unveränderte Hauptkörper-Unterseite liegt bei Z=10.00 mm. Die neue Schale würde daher 3.50 bis 4.00 mm nach unten aus der Wanne herausragen. Das verletzt das unveränderte Hauptkörpermaß und die Druckauflage.

## Blocker 2 – Wasserweg

Das bestehende freie Ablaufende liegt auf Z=10.00 mm. Der verlangte lokale Boden läge 1.50 bis 2.00 mm tiefer. Bei unverändertem Ablauf entstünde damit zwingend ein lokaler Tiefpunkt. Um ihn zu entwässern, müssten Gefällekanal und Ablaufende ebenfalls abgesenkt werden; das wäre keine ausschließlich lokale Korrektur unter der Wabe und widerspricht der Vorgabe, den bestehenden vorderen Ablauf unverändert zu lassen.

## Widerspruch zur Zapfen-Sicherheitsanforderung

Nur der separat genannte Sicherheitsabstand von +0,5 mm zum Zapfenende Z=12.00 mm würde einen Boden bei Z=11.50 mm verlangen. Das ergäbe jedoch lediglich 15.50 mm freie Tiefe unter der Gitterunterseite und verfehlt das gleichzeitig verbindliche Ziel von 18,5–19,0 mm deutlich. Beide Sollwerte sind daher nicht gleichzeitig erfüllbar.

## Behälter-Randentlastung

Die gewünschte Entlastung von 0,25–0,40 mm ist unabhängig grundsätzlich konstruierbar, aber nicht im unveränderten 0,5-mm-Voxelraster von v004-r01: darstellbar sind dort nur 0,0 oder 0,5 mm. Eine lokale höher aufgelöste/parametrische Bearbeitung wäre erforderlich und müsste vollständig neu validiert werden. Wegen des primären Halterblockers wurde auch diese Geometrie nicht erzeugt.

## Entscheidung gemäß Änderungsdisziplin

Die geforderte Korrektur würde entweder Hauptkörper/Druckauflage verändern oder bei bestehendem Ablauf eine Wasserfalle erzeugen. Deshalb wurde entsprechend der ausdrücklichen STOP-Regel keine v004-r02-Geometrie gebaut.
