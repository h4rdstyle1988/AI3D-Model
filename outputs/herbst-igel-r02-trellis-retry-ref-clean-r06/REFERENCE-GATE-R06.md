# Herbst-Igel R02 – Referenz-Gate R06

## Ergebnis

`REFERENCE-GATE: PASS`

Die vier in `tasks/TASK-HERBST-IGEL-R02-REF-CLEAN-AUTH-R06.md`
autorisierten Base64-Teile wurden numerisch konkateniniert und genau einmal
streng Base64-dekodiert. Eine Transportkorrektur war nicht erforderlich.

## Primärreferenz – SOLL/IST

| Prüfung | SOLL | IST | Ergebnis |
|---|---:|---:|---|
| Bytezahl | 17.344 | 17.344 | PASS |
| SHA-256 | `c1c9a5a094f1db2fd220f3433f83af8dedca780f56a4bf479eb8883432250859` | identisch | PASS |
| Format | JPEG | JPEG | PASS |
| Farbmodus | RGB | RGB | PASS |
| Abmessung | 512 × 512 px | 512 × 512 px | PASS |
| strikter Base64-Decode | PASS | PASS | PASS |
| strikter JPEG-Decode | PASS | PASS | PASS |

Die rekonstruierte Datei liegt unter
`reference-audit/ref-clean-r06.jpg`. Der vollständige maschinenlesbare Nachweis
liegt unter `reference-audit/reference-gate-audit-r06.json`.

## REF-SEAM

Als einzige Trennlinienreferenz wurde
`tasks/TASK-HERBST-IGEL-R01-REF-SEAM.jpg.b64` dekodiert.

- SHA-256 SOLL/IST:
  `b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4`
- strikter Base64- und JPEG-Decode: `PASS`
- Ausgabe: `reference-audit/ref-seam-r06.jpg`

Keine alte R03/R04/R05-Referenz wurde als Formquelle verwendet.

