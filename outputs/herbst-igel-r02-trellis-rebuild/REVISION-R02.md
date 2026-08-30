# Herbst-Igel – Revisionsdokumentation R02

## Ergebnisstand

- Revision: `R02`
- Status: `STOPP`
- Letzte abgeschlossene Phase: `TRELLIS-ROHMESH / OPTIK-GATE`
- Optik-Gate: `FAIL`
- Finale Produktfreigabe: `NEIN`

## GEÄNDERT

- R01 wurde nicht als Formbasis weiterverwendet.
- Die hashverifizierte R02-`REF-CLEAN` wurde mit Trellis Studio nativ über
  Vulkan rekonstruiert.
- Ein eigener Trellis-Rohmesh wurde als GLB und PLY erzeugt.
- Direkte SOLL/IST- und Sechs-Ansichten-Prüfrenders wurden aus diesem Rohmesh
  erzeugt.

## UNVERÄNDERT / GESCHÜTZT

Die bestätigte Produktidee und sämtliche Nutzermaße wurden nicht verändert:
zwei Hohlschalen, Materialzuordnung, ca. 200 mm, 1,6 mm Grundwand,
Ø10,0-mm-Zapfen, 20,0-mm-Eingriff, Klebeverbindung, Nutzer-Trennlinie, keine
sichtbare Verbindung und keine Zusatzfunktionen.

Keines dieser Merkmale wurde konstruktiv umgesetzt oder neu interpretiert,
weil das vorgelagerte Optik-Gate scheiterte.

## ENTFERNT

- Keine R01-Geometrie wurde übernommen.
- Keine parametrische Ersatzfigur wurde erzeugt.

## HAUPTDATEIEN DIESES STOPP-STANDS

- `trellis-raw/herbst-igel-r02-trellis-raw.glb`
- `trellis-raw/herbst-igel-r02-trellis-raw.ply`
- `renders-optik-gate/optic-gate-soll-ist.png`
- `renders-optik-gate/raw-contact-sheet.png`
- `SOLL-IST-OPTIK-GATE.md`
- `TRELLIS-REPRODUKTION.md`
- `reports/raw-gate-inspection.json`
- `VALIDIERUNG-R02.json`

## OFFEN

- Vollständige autoritative Optikreferenz oder Freigabe einer konkreten
  Ersatzquelle.
- Neuer Trellis-Lauf und erneutes Optik-Gate nach neuer Freigabe.
- Sämtliche CAD-, STL-, Montage- und technische Validierungsschritte.
- Reale Druck-, Passungs-, Klebe- und Sichtprüfung.
- Finale optische und finale Produktfreigabe ausschließlich durch den Nutzer.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: true`

