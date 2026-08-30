# Herbst-Igel – Revisionsdokumentation R02 / Retry R03

## Ergebnisstand

- Task: `tasks/TASK-HERBST-IGEL-R02-TRELLIS-RETRY-REF-CLEAN-R03.md`
- Task-Blob-SHA-1: `7b68bdd653edadba3d71cc2e4949466490a9ad3a`
- Produktrevision: `R02` (unverändert)
- Retry-/Dokumentationsstand: `R03`
- Status: `STOPP / OFFEN`
- Letzte abgeschlossene Phase: `REFERENZ-PREFLIGHT`
- Finale Produktfreigabe: `NEIN`

## GEÄNDERT

- Für den freigegebenen R03-Retry wurde ein neuer, separater Ergebnisordner
  angelegt.
- Die tatsächliche neue REF-CLEAN-Datei wurde gegen Größe, SHA-256,
  Dateisignatur und zwei strikte Bilddecoder geprüft.
- Der Referenzfehler und die vorgeschriebene Abbruchfolge wurden neu
  dokumentiert.

## UNVERÄNDERT / GESCHÜTZT

- R02 bleibt die Produktrevision.
- Vorherige R01-/R02-Ergebnisse und STOPP-Stände wurden nicht überschrieben.
- Sämtliche bestätigten Geometrieanforderungen und Nutzermaße bleiben
  unangetastet: genau zwei Hohlschalen, 1,6-mm-Grundwand, ca. 200 mm,
  Ø10,0-mm-Zapfen, 20,0-mm-Eingriff, innenliegende Klebeverbindung,
  Nutzer-Trennlinie, Materialien und keine Zusatzfunktionen.
- Die alte beschädigte REF-CLEAN, REF-SEAM und die sekundäre Multiansicht
  wurden nicht als Ersatz-Formquelle verwendet.

## ENTFERNT

- Nichts aus bestätigter Geometrie oder früheren Ergebnissen.
- Keine Ersatzfigur und keine Referenzreparatur wurden erzeugt.

## OFFEN

- Bereitstellung der exakt autorisierten, vollständig decodierbaren primären
  REF-CLEAN oder ausdrückliche Freigabe einer anderen konkreten Formquelle.
- Danach: tatsächlicher Trellis-Lauf, Rohmesh-Archivierung, Rohmesh-Render und
  Optik-Gate.
- Nur nach eindeutigem Optik-PASS: CAD-/FDM-Aufbereitung, STL/Assembly,
  technische Validierung und finale Geometrierender.
- Reale Slicer-, Druck-, Passungs-, Klebe- und Sichtprüfung.
- Finale optische und finale Produktfreigabe ausschließlich durch den Nutzer.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: true`

Grund: Die erforderliche reale Primärreferenz stimmt weder in Dateiidentität
noch Format mit der Freigabe überein und kann nicht eindeutig rekonstruiert
werden.

`FINALE_PRODUKTFREIGABE: false`
