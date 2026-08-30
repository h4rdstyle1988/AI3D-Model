# Herbst-Igel R02 – Referenz-Gate des R03-Retry

## Ergebnis

`STATUS: STOPP`

`REFERENZ-GATE: FAIL`

Die verbindliche Arbeitsreihenfolge stoppt vor Trellis: Die neue primäre
Optik-/Formreferenz liegt im freigegebenen Pfad nicht mit der freigegebenen
Dateiidentität vor und lässt sich nicht als Bild decodieren. Sie darf deshalb
nicht als Trellis-Eingabe verwendet und nicht still ersetzt, repariert oder aus
einer anderen Referenz rekonstruiert werden.

## SOLL/IST – Primäre REF-CLEAN

| Prüfung | SOLL | IST | Ergebnis |
|---|---:|---:|---|
| Pfad | `tasks/TASK-HERBST-IGEL-R02-REF-CLEAN-R03.jpg` | identischer Pfad | PASS |
| Dateigröße | 40.823 Byte | 10.809 Byte | FAIL |
| SHA-256 | `2d127f873be82c7247f4c67345821d68edd2a0f8a0c2dab20d24a5e27a3ce8a2` | `965117ec3a950c33146e0a6c0f6beddbfd4a3f365de9d27ed22389234a13e4f4` | FAIL |
| Bildformat | RGB JPEG | nicht identifizierbare Binärdaten; keine JPEG-SOI-Signatur | FAIL |
| Abmessungen | 512 × 512 px | nicht bestimmbar | FAIL |
| Strikter Decode | vollständig | `PIL.UnidentifiedImageError`; `System.Drawing.ArgumentException` | FAIL |

Der Repository-Blob ist `a2ba8ccfb73f932398c4ab9bdb023b8771266799`.
Die lokale Git-Historie enthält für diesen Pfad ausschließlich denselben Blob;
in den erlaubten Arbeitswurzeln wurde keine Kopie mit dem erwarteten SHA-256
gefunden. Eine verlustfreie technische Wiederherstellung war daher nicht
möglich.

## SOLL/IST – REF-SEAM

Die ausschließlich für die Trennlinie autorisierte Datei
`tasks/TASK-HERBST-IGEL-R01-REF-SEAM.jpg.b64` wurde unabhängig und streng
geprüft:

- Base64-Struktur: PASS
- dekodierte Größe: 11.788 Byte
- SHA-256: `b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4` – PASS
- Bild: 384 × 384 px, 24-bpp RGB – vollständiger Decode PASS
- Verwendung als primäre Formquelle: NEIN, gemäß Auftrag

## Verbindliche Gate-Folge

Nicht ausgeführt beziehungsweise nicht erzeugt wurden:

- kein Trellis-Aufruf, kein GPU-Lauf, kein Seed und keine Auflösung,
- kein Trellis-Rohmesh und keine Rohmesh-Render,
- kein Optik-Gate an 3D-Geometrie,
- keine CAD-/Mesh-Aufbereitung,
- keine Körper- oder Rücken-STL,
- keine Montage-GLB/3MF,
- keine technische Geometrievalidierung.

Diese Auslassungen sind die vorgeschriebene Folge des fehlgeschlagenen ersten
Referenz-Gates und keine stillen Abweichungen vom Auftrag.

## OFFEN / erforderliche Nutzerentscheidung

Für einen regelkonformen Retry wird entweder die in der Autorisierung
beschriebene vollständige 40.823-Byte-Datei mit exakt dem erwarteten SHA-256
benötigt oder eine ausdrückliche Freigabe einer anderen konkreten primären
Formquelle. Die alte beschädigte REF-CLEAN, REF-SEAM und die sekundäre
Multiansicht wurden nicht umgewidmet.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: true`

Grund: Eine konstruktiv erforderliche reale Primärreferenz fehlt in der
freigegebenen Dateiidentität und ist nicht eindeutig ableitbar.

Eine finale Produkt- oder Druckfreigabe wird nicht behauptet.
