# Herbst-Igel R02 – Referenz-Gate des R05-Retry

## Ergebnis

`STATUS: STOPP / OFFEN`

`REFERENZ-GATE: FAIL`

Die verbindliche Arbeitsreihenfolge stoppt vor Trellis. Die acht R05-Teile
lassen sich zwar streng als Base64 dekodieren, ergeben aber nicht die
freigegebene Bildidentität. Der Transport enthält vier Base64-Zeichen
beziehungsweise drei dekodierte Bytes zu wenig. Eine byteidentische,
hashgeprüfte Wiederherstellung war aus den vorhandenen Daten nicht möglich.

## Task- und Queue-Identität

- Task: `tasks/TASK-HERBST-IGEL-R02-TRELLIS-RETRY-REF-CLEAN-R05.md`
- Task-Blob-SHA-1: `0ebad9ce7405b87e8d858dd9f89a6de97bb02890`
- Produktrevision: `R02` (unverändert)
- Retry-/Referenztransport: `R05`
- FIFO-Kopf in `tasks/TASK_QUEUE.txt`: identischer Task-Pfad – `PASS`
- `tasks/CURRENT_TASK.txt`: `NONE` – `PASS`

## SOLL/IST – Primäre REF-CLEAN

| Prüfung | SOLL | IST | Ergebnis |
|---|---:|---:|---|
| Teile | `part01` bis `part08`, numerisch | alle acht vorhanden und numerisch gelesen | PASS |
| Base64-Länge | 54.432 Byte für 40.823 Byte Nutzlast | 54.428 Byte | FAIL |
| striktes Base64 | PASS | PASS | PASS |
| dekodierte Größe | 40.823 Byte | 40.820 Byte | FAIL |
| SHA-256 | `2d127f873be82c7247f4c67345821d68edd2a0f8a0c2dab20d24a5e27a3ce8a2` | `6d43cf922b2edc3b049a30b682c16f77be62a369f23ba691551b3a8c9490b586` | FAIL |
| JPEG SOI/EOI | vorhanden | vorhanden | PASS |
| vollständiger strikter Decode | PASS | `UnidentifiedImageError` | FAIL |
| 512 × 512 RGB JPEG | zwingend hashgeprüft | aus dem unveränderten Transport nicht strikt lesbar | FAIL |

## Technische Diagnose und Wiederherstellung

Der zweite DQT-Abschnitt beginnt bei Byte 89 und deklariert eine Länge von 67
Byte. Der folgende SOF0-Marker müsste deshalb bei Byte 158 beginnen, steht im
tatsächlichen Transport aber bereits bei Byte 155. Somit fehlen innerhalb der
zweiten JPEG-Quantisierungstabelle genau drei dekodierte Bytes.

Die strukturell naheliegende Reparatur mit drei wiederholten DQT-Werten
`0x14 0x14 0x14` erzeugt einen vollständig decodierbaren 40.823-Byte-JPEG mit
512 × 512 px und RGB. Dessen SHA-256 ist jedoch
`4d5d46465e2ab1f61636bc8045fa8ed392555f6e3a2fe873d9cc97836b7dd980`
und damit nicht die autorisierte Identität. Dieser Kandidat wurde ausdrücklich
nicht als Referenz verwendet.

Zusätzlich wurden an allen 62 möglichen Einfügegrenzen der betroffenen Tabelle
sämtliche 1.674.000 Kombinationen dreier Quantisierungswerte von 1 bis 30
gegen den Zielhash geprüft. Dieser Bereich enthält den vollständigen im
Transport beobachteten Wertebereich 3 bis 20. Kein Kandidat trifft den
autorisierten SHA-256.

Geprüft wurden außerdem:

- sämtliche vorhandenen Git-Objekte auf eine passende 40.823-Byte-Datei,
- Repository und `D:/AI3D-Agent`,
- `D:/3D-Models/generated`,
- lokale Download-, Desktop-, Bilder-, Temp- und Codex-Übergabebereiche.

Es wurde keine Datei mit der autorisierten Größe und Prüfsumme gefunden. Alte
korrupte R03/R04-Referenzen, REF-SEAM und die sekundäre Multiansicht wurden
nicht als Formquelle eingesetzt.

Der vollständige reproduzierbare Nachweis liegt unter
`reproduction-scripts/verify_reference_gate_r05.py`; sein Ergebnis steht in
`reports/reference-gate-audit-r05.json`.

## SOLL/IST – REF-SEAM

Die ausschließlich für die Trennlinie autorisierte Datei
`tasks/TASK-HERBST-IGEL-R01-REF-SEAM.jpg.b64` ist intakt:

- striktes Base64: `PASS`
- dekodierte Größe: 11.788 Byte
- SHA-256: `b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4` – `PASS`
- Bild: 384 × 384 px, RGB JPEG
- vollständiger strikter Decode: `PASS`
- Verwendung als primäre Formquelle: `NEIN`

## Verbindliche Gate-Folge

Nicht ausgeführt beziehungsweise nicht erzeugt wurden:

- kein Trellis-Aufruf, kein GPU-Lauf, kein Seed und keine Auflösung,
- kein Trellis-Rohmesh und keine Rohmesh-Render,
- kein Optik-Gate an 3D-Geometrie,
- keine CAD-/Mesh-/FDM-Aufbereitung,
- keine Körper- oder Rücken-STL,
- keine Montage-GLB/3MF,
- keine technische Geometrievalidierung.

Dies ist die vorgeschriebene STOPP-Folge des fehlgeschlagenen ersten Gates und
keine Änderung der Produktidee.

## OFFEN / erforderliche Nutzerentscheidung

Erforderlich ist die exakt autorisierte 40.823-Byte-JPEG-Datei mit SHA-256
`2d127f873be82c7247f4c67345821d68edd2a0f8a0c2dab20d24a5e27a3ce8a2`
als vollständiger Transport oder die ausdrückliche Freigabe einer anderen
konkreten primären Formquelle.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: true`

Grund: Die konstruktiv erforderliche reale Primärreferenz fehlt unter der
freigegebenen Dateiidentität und ist nicht eindeutig ableitbar.

Eine finale Produkt- oder Druckfreigabe wird nicht behauptet.

