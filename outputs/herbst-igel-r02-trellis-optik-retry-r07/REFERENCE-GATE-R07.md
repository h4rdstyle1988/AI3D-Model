# Herbst-Igel R02 – Referenz-Gate R07

`REFERENZ-GATE: PASS`

Die Primärreferenz wurde entsprechend
`tasks/TASK-HERBST-IGEL-R02-REF-CLEAN-AUTH-R06.md` aus den vier numerisch
geordneten Base64-Teilen rekonstruiert und streng geprüft.

| Prüfung | SOLL | IST | Ergebnis |
|---|---:|---:|---|
| Dateigröße REF-CLEAN | 17.344 Byte | 17.344 Byte | PASS |
| SHA-256 REF-CLEAN | `c1c9a5a094f1db2fd220f3433f83af8dedca780f56a4bf479eb8883432250859` | identisch | PASS |
| Bildformat | JPEG RGB | JPEG RGB | PASS |
| Bildgröße | 512 × 512 px | 512 × 512 px | PASS |
| strikter Base64-/Bilddecode | vollständig | vollständig | PASS |
| SHA-256 REF-SEAM | `b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4` | identisch | PASS |

Die alte beschädigte REF-CLEAN und die sekundäre Multiansicht wurden nicht als
Formquelle verwendet. Der vollständige maschinenlesbare Nachweis liegt in
`reference-audit/reference-gate-audit-r07.json`.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`
