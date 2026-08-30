# TASK-HERBST-IGEL-R02-REF-CLEAN-AUTH-R05

Status: FREIGEGEBEN
Datum: 2026-08-30

## Autorisierung und Identitaet
Dies ist ausschliesslich eine transportsichere Wiederherstellung der bereits vom Nutzer freigegebenen primaeren Igelreferenz. Es gibt keine Aenderung der Produktidee oder des Bildinhalts.

Autoritative Nutzerquelle bleibt der am 2026-08-30 erneut hochgeladene vollstaendige Igel (siehe `TASK-HERBST-IGEL-R02-REF-CLEAN-AUTH-R03.md`).

Fuer Trellis ist weiterhin exakt die bereits autorisierte technische R03-Transportkopie zu rekonstruieren:
- 512 x 512 px RGB JPEG
- Dateigroesse exakt 40823 Bytes
- SHA-256 exakt `2d127f873be82c7247f4c67345821d68edd2a0f8a0c2dab20d24a5e27a3ce8a2`
- strikter JPEG-Decode muss PASS sein

Die Base64-Nutzlast wurde wegen wiederholter Transportkuerzung in acht kleine, unveraenderte Teile zerlegt:
`TASK-HERBST-IGEL-R02-REF-CLEAN-R05.part01.b64` bis `part08.b64`.
Sie sind in numerischer Reihenfolge ohne Trennzeichen zu konkatenieren und dann einmal Base64 zu dekodieren.

Die R04-Datei und die korrupte R03-Datei im Repository duerfen nicht als Bildquelle verwendet werden.
Die bestehende REF-SEAM bleibt ausschliesslich fuer die Trennlinie autoritativ.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`
