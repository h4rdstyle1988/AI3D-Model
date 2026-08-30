# Konfliktbericht – Herbst-Igel R01 Retry Ref Fix

## Ergebnis

**STOPP vor Konstruktion.** Die autoritative Optikreferenz `REF-CLEAN` besteht die im freigegebenen Auftrag zwingend vorgeschriebene SHA-256-Prüfung nicht.

## Geprüfter freigegebener Stand

- Auftrag: `tasks/TASK-HERBST-IGEL-R01-RETRY-REF-FIX.md`
- Task/Revision: `TASK-HERBST-IGEL-R01-RETRY-REF-FIX` / `R01-RETRY-REF-FIX`
- Task-Blob: `8552dc925239ee6197ba05f087e5914902aacc50`
- Hauptauftrag-Blob: `69fbc9d4cd70255c0014e890e58ebc05633fd678`
- Referenzmanifest-Blob: `ef44f5b7af24980db3ea5b2af85f2f99fa57130e`

## Referenzprüfung

| Referenz | Manifest-SHA-256 | Dekodierte SHA-256 | Ergebnis |
|---|---|---|---|
| REF-CLEAN | `d3e7465d9f2d5164836cf5b4d238e04e37778eac995d35123edd6cee04ad9836` | `f3017009739284e1bfd6e8502e9d9258eb74dbf52074c425a73ff41fc8bac328` | **FAIL** |
| REF-SEAM | `b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4` | `b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4` | PASS |

REF-CLEAN dekodiert formal als gültiges JPEG mit 320 × 320 Pixeln, RGB und 11.536 Byte. Der abweichende Hash wurde unabhängig mit PowerShell/.NET und Python bestätigt. Base64-Leerraum oder Zeilenenden erklären die Abweichung nicht.

Die sekundäre Multiansicht wurde gemäß Auftrag weder dekodiert noch verwendet.

## Warum keine Konstruktion erzeugt wurde

Der freigegebene Retry-Auftrag verlangt, beide autoritativen Referenzen vor Nutzung exakt gegen das aktive Manifest zu prüfen. REF-CLEAN ist allein autoritativ für sichtbare Optik, Proportion, Gesicht, Körperhaltung und Oberflächendetails. Die vorhandenen Bytes trotz Hashkonflikt zu verwenden, den Manifest-Hash still zu ändern oder REF-SEAM ersatzweise als Optikreferenz umzudeuten wäre jeweils eine nicht freigegebene Annahme.

Deshalb wurden keine CAD-, STL-, GLB-/3MF-, Montage-, Render- oder Druckdateien erzeugt. Bestätigte Maße und Produktgeometrie wurden nicht verändert.

## Erforderliche Auflösung

Es wird entweder eine `REF-CLEAN`-Base64-Datei benötigt, deren dekodierte Bytes exakt den manifestierten SHA-256 `d3e746…9836` besitzen, oder ein korrigiertes Manifest, das den tatsächlich beabsichtigten Referenzstand eindeutig benennt. Jede Änderung an Referenzdatei oder Manifest ist ein neuer Task-Arbeitsstand und muss gemäß Repository-Regeln erneut ausdrücklich freigegeben werden.

## Status

- PASS/STOPP/OFFEN: **STOPP**
- NUTZERENTSCHEIDUNG_ERFORDERLICH: **true**
- Grund: Die erforderliche autoritative Optikreferenz ist unter dem freigegebenen SHA-256 nicht vorhanden; welcher Byte-Stand autoritativ sein soll, ist nicht technisch eindeutig ableitbar.
- FINALE_PRODUKTFREIGABE: **false**

