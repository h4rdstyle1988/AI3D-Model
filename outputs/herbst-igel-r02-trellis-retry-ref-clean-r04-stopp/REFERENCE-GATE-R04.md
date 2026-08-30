# Herbst-Igel R02 – Referenz-Gate des R04-Retry

## Ergebnis

`STATUS: STOPP / OFFEN`

`REFERENZ-GATE: FAIL`

Die verbindliche Arbeitsreihenfolge stoppt vor Trellis. Die primäre
Optik-/Formreferenz liegt im freigegebenen Pfad nicht mit der freigegebenen
Dateiidentität vor. Der Repository-Inhalt ist ein abgeschnittener Base64-Text
und endet wörtlich mit `[...truncated...]`. Eine vollständige, byteidentische
Wiederherstellung ist weder aus dem Blob noch aus den vorhandenen Git-Objekten
oder den geprüften lokalen Arbeitswurzeln möglich.

## Task- und Queue-Identität

- Task: `tasks/TASK-HERBST-IGEL-R02-TRELLIS-RETRY-REF-CLEAN-R04.md`
- Task-Blob-SHA-1: `68df6b5ca7759d63a6b25a686db4278d27a07a10`
- Produktrevision: `R02`
- Retry-/Referenztransport: `R04`
- FIFO-Kopf in `tasks/TASK_QUEUE.txt`: identischer Task-Pfad – `PASS`
- `tasks/CURRENT_TASK.txt`: `NONE` – `PASS`

## SOLL/IST – Primäre REF-CLEAN

| Prüfung | SOLL | IST | Ergebnis |
|---|---:|---:|---|
| Pfad | `tasks/TASK-HERBST-IGEL-R02-REF-CLEAN-R04.jpg.b64` | identischer Pfad | PASS |
| Repository-Transport | vollständiger Base64-Text | 10.013 Byte mit literalem Kürzungsmarker ab Zeichen 9.996 | FAIL |
| ungebrochene Base64-Zeichen | 41.372 | 9.996 vor dem Marker | FAIL |
| striktes Base64 | vollständig decodierbar | `Error: Only base64 data is allowed` | FAIL |
| dekodierte Dateigröße | 31.028 Byte | nicht herstellbar; gültiger Präfix nur 7.497 Byte | FAIL |
| dekodierter SHA-256 | `1b039abd4e83ddeff1fe707d07bca5d492b3fbb956857599936b317cf22b4a29` | nicht prüfbar/herstellbar | FAIL |
| JPEG-Signatur | SOI und EOI | Präfix hat SOI, aber kein EOI | FAIL |
| Bildformat | 512 × 512 px, RGB JPEG | wegen unvollständigem Datenstrom nicht bestimmbar | FAIL |
| vollständiger strikter Decode | PASS | nicht möglich | FAIL |

Der tatsächliche Repository-Blob ist
`a1123c4910a3c524658873031eca255dd902f91a`; sein SHA-256 ist
`d7a7bc276318dea54458311c844d5f7532e8be038687f50064bad28fe6304b85`.
Die Prüfung sämtlicher lokaler Git-Objekte ergab keinen Blob mit 31.028 Byte.
Auch in Repository, `D:/AI3D-Agent` und `D:/3D-Models/generated` wurde keine
31.028-Byte-Datei mit der autorisierten Identität gefunden.

## SOLL/IST – REF-SEAM

Die ausschließlich für die Trennlinie autorisierte Datei
`tasks/TASK-HERBST-IGEL-R01-REF-SEAM.jpg.b64` ist intakt:

- Base64-Struktur: `PASS`
- dekodierte Größe: 11.788 Byte
- dekodierter SHA-256:
  `b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4`
  – `PASS`
- JPEG-SOI/EOI: `PASS`
- Bild: 384 × 384 px, RGB JPEG
- vollständiger strikter Decode: `PASS`
- Verwendung als primäre Formquelle: `NEIN`, gemäß Auftrag

## Technische Untersuchung und Wiederherstellung

Der Kürzungsmarker ist kein Base64-Zeichen und kein Bestandteil eines JPEG.
Hinter dem Marker fehlen die nicht übergebenen Bytes; sie lassen sich aus dem
7.497-Byte-Präfix und einem SHA-256-Zielwert nicht verlustfrei rekonstruieren.
Eine Neuencodierung der alten beschädigten R01-Referenz, der R03-Rohdatei, von
REF-SEAM oder der sekundären Multiansicht würde die verbindliche Formquelle
ändern und wurde daher nicht vorgenommen.

Der reproduzierbare Auditor liegt unter
`reproduction-scripts/verify_reference_gate_r04.py`; sein maschinenlesbares
Ergebnis liegt unter `reports/reference-gate-audit-r04.json`.

## Verbindliche Gate-Folge

Nicht ausgeführt beziehungsweise nicht erzeugt wurden:

- kein Trellis-Aufruf, kein GPU-Lauf, kein Seed und keine Auflösung,
- kein Trellis-Rohmesh und keine Rohmesh-Render,
- kein Optik-Gate an 3D-Geometrie,
- keine CAD-/Mesh-Aufbereitung,
- keine Körper- oder Rücken-STL,
- keine Montage-GLB/3MF,
- keine technische Geometrievalidierung.

Das sind die vorgeschriebenen Folgen des fehlgeschlagenen ersten
Referenz-Gates, keine stillen Abweichungen.

## OFFEN / erforderliche Nutzerentscheidung

Erforderlich ist die exakt autorisierte 31.028-Byte-JPEG-Datei mit SHA-256
`1b039abd4e83ddeff1fe707d07bca5d492b3fbb956857599936b317cf22b4a29`
als vollständiger Base64-Transport oder die ausdrückliche Freigabe einer
anderen konkreten primären Formquelle.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: true`

Grund: Eine konstruktiv erforderliche reale Primärreferenz fehlt unter der
freigegebenen Dateiidentität und ist nicht eindeutig ableitbar.

Eine finale Produkt- oder Druckfreigabe wird nicht behauptet.

