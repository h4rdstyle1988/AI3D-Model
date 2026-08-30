# TASK-HERBST-IGEL-R01 – PREFLIGHT-STOPP

## Ergebnis

- Task: `tasks/TASK-HERBST-IGEL-R01.md`
- Revision: `R01`
- Task-Blob-SHA: `69fbc9d4cd70255c0014e890e58ebc05633fd678`
- Status: `STOPP`
- Konstruktion gestartet: `nein`
- CAD/STL/3MF/GLB erzeugt: `nein`
- `NUTZERENTSCHEIDUNG_ERFORDERLICH: true`
- Finale Produktfreigabe: `nein`

## Blockierender Konflikt

Die drei Referenzdateien bestehen die in `tasks/TASK-HERBST-IGEL-R01-REFERENCE-MANIFEST.md` verbindlich verlangte Integritätsprüfung nicht. Die autoritative Optik- und Trennlinienreferenz kann deshalb nicht belastbar verwendet werden.

| Referenz | Manifest-SHA-256 des dekodierten Ziels | Befund |
|---|---|---|
| `REF-CLEAN` | `8fc5ea79cee2ee2d4afac14ed2741a922e2159c68ff9cd87c3c7fdb377e2ac4c` | Base64-Länge 15606, Rest 2 bei Division durch 4; striktes Dekodieren scheitert mit überschüssigem Padding. Eine permissiv dekodierte Fassung hat SHA-256 `8ac51036e4cefe2a0b89306d3139b2f24dabd26e4c3ebd0e2898037513ce5a67` und kein korrektes JPEG-Ende (`fd90` statt `ffd9`). |
| `REF-SEAM` | `b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4` | Striktes Base64-Dekodieren ist möglich, das 384 × 384-JPEG hat jedoch SHA-256 `5924437732c1266b0af91ee5ad556d7ff8270fe639b05f7d529ac5ad7ddcfc1d` und stimmt nicht mit dem Manifest überein. |
| `REF-MULTIVIEW-SECONDARY` | `176b02bf201599563dd1af57bc07b9b00a1db5eef3e492999090b4954cc02482` | Base64-Länge 18190, Rest 2 bei Division durch 4; kein JPEG-Start (`d21a` statt `ffd8`), kein korrektes JPEG-Ende und nicht als Bild lesbar. |

Zusätzlich wurden alle 752 lokalen Git-Blobs geprüft, davon 134 plausible Bild-/Base64-Blobs zwischen 5 kB und 2 MB. Keiner enthält einen Roh- oder Base64-dekodierten Inhalt mit einem der drei Manifest-Hashes. In der erreichbaren Git-Historie existiert ebenfalls keine andere Fassung der Referenzen.

## Warum keine Konstruktion zulässig ist

Die Task schützt ausdrücklich Silhouette, Proportion, Gesichtsausdruck, Körperhaltung, Stachel-/Blattstruktur, das einzelne sichtbare Ahornblatt und die blau markierte Trennlinie. Ohne verifizierte `REF-CLEAN` und `REF-SEAM` müssten diese konstruktiv relevanten Merkmale geraten werden. Das wäre eine stille Annahme und ein Verstoß gegen die freigegebene Produktidee.

Reine CAD-, Mesh-, Toolchain-, Support- und Berechnungsentscheidungen sind hiervon nicht betroffen; der Blocker ist ein fehlendes bzw. widersprüchliches autoritatives Referenzdatum.

## SOLL/IST

| SOLL | IST | Status |
|---|---|---|
| Autoritative Referenzen vor Nutzung dekodieren und exakt per SHA-256 verifizieren | Kein Manifest-Hash reproduzierbar | `STOPP` |
| Außenform proportional aus `REF-CLEAN` ableiten | Ohne verifizierte Referenz nicht zulässig | `OFFEN` |
| Trennlinie exakt aus `REF-SEAM` übernehmen | Vorliegendes JPEG widerspricht dem Manifest-Hash | `OFFEN` |
| Zwei Hohlschalen, 1,6 mm Wand, Ø10,0-mm-Zapfen, 20,0-mm-Eingriff konstruieren | Nicht begonnen, um unbestätigte Außenform zu schützen | `OFFEN` |
| STL/3MF oder GLB, Render und Geometrievalidierung liefern | Nicht erzeugt; Folge des Preflight-STOPP | `OFFEN` |

## Erforderliche Nutzerentscheidung / Zuarbeit

Bitte die drei ursprünglichen Referenzbilder erneut bereitstellen oder die Base64-Dateien samt zutreffenden SHA-256-Werten korrigieren und die korrigierte Task-Version erneut freigeben/queuen. Eine bloße Freigabe, die aktuell abweichenden oder beschädigten Daten trotzdem zu verwenden, würde die in der Task verlangte Referenzidentität ändern und muss daher ausdrücklich als neue Revision bestätigt werden.

## Revisionsdokumentation

- **GEÄNDERT:** Nur taskbezogener Preflight-, Konflikt- und Maschinenstatus für R01 angelegt.
- **UNVERÄNDERT / GESCHÜTZT:** Keine Geometrie, keine Nutzermaße, keine Produktfunktion und keine bestehenden Revisionen verändert.
- **ENTFERNT:** Keine Produktfunktion. Die während der Diagnose erzeugte, hashfalsche `REF-SEAM`-Dekodierung ist recoverable als `INVALID-DO-NOT-USE-REF-SEAM.bin` im Ergebnisordner quarantänisiert und darf nicht als Referenz verwendet werden.
- **OFFEN:** Intakte autoritative Referenzdaten, danach vollständige Konstruktion und Validierung sowie abschließende Nutzerprüfung.

Ein späterer erfolgreicher CAD-/STL-Validatorlauf wäre weiterhin keine finale Produktfreigabe.
