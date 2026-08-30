# Herbst-Igel – REF-CLEAN Autorisierung R04

Status: FREIGEGEBEN
Datum: 2026-08-30

## Anlass
Der Nutzer hat das vollständige gewünschte Igelbild im Chat erneut hochgeladen und zuvor ausdrücklich `Go` für die saubere Neuübergabe als primäre Trellis-Formquelle gegeben. Der R03-Transport als rohe `.jpg`-Datei war technisch fehlerhaft, weil der verwendete GitHub-Connector nur UTF-8-Textdateien zuverlässig schreibt. Das ist ein reiner Transportfehler und keine neue Produktentscheidung.

## Autoritative Nutzerreferenz
- vollständiger aktueller Chat-Upload, 1254 × 1254 px, RGB JPEG
- lokal strikt decodierbar: PASS
- inhaltlich unverändert als Nutzeridee autorisiert

## Transport-sichere Repository-Referenz
- Pfad: `tasks/TASK-HERBST-IGEL-R02-REF-CLEAN-R04.jpg.b64`
- Format im Repository: reiner Base64-Text
- nach Base64-Dekodierung: 512 × 512 px, RGB JPEG
- keine Beschneidung, keine Retusche, keine inhaltliche Änderung
- einzige Bildtransformation: proportionale Skalierung 1254 → 512 px und JPEG-Neukodierung für Trellis
- erwartete dekodierte Dateigröße: exakt `31028` Byte
- erwarteter SHA-256 der dekodierten JPEG-Datei: exakt `1b039abd4e83ddeff1fe707d07bca5d492b3fbb956857599936b317cf22b4a29`
- JPEG muss strikt vollständig decodieren.

Die alte beschädigte R01-REF-CLEAN und die fehlerhafte rohe R03-JPG-Datei sind ab jetzt ausdrücklich **keine** primäre Formquelle mehr.

`REF-SEAM` bleibt ausschließlich für die Trennlinie autoritativ und wird nicht zur Formquelle umgewidmet.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`
