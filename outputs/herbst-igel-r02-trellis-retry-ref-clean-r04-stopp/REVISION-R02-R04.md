# Herbst-Igel – Revisionsdokumentation R02 / Retry R04

## Ergebnisstand

- Task: `tasks/TASK-HERBST-IGEL-R02-TRELLIS-RETRY-REF-CLEAN-R04.md`
- Task-Blob-SHA-1: `68df6b5ca7759d63a6b25a686db4278d27a07a10`
- Produktrevision: `R02` (unverändert)
- Retry-/Referenztransportstand: `R04`
- Status: `STOPP / OFFEN`
- Letzte abgeschlossene Phase: `REFERENZ-PREFLIGHT`
- Finale Produktfreigabe: `NEIN`

## GEÄNDERT

- Neuer, isolierter R04-STOPP-Ergebnisstand angelegt.
- Tatsächlicher R04-Base64-Blob gegen Transportstruktur, Größe, SHA-256,
  JPEG-Signatur, Abmessungen und strikten Decode geprüft.
- Technische Wiederherstellbarkeit über alle vorhandenen Git-Objekte und die
  lokalen Worker-/Ausgabewurzeln geprüft.
- Reproduzierbarer Referenz-Auditor und maschinenlesbare Berichte erzeugt.

## UNVERÄNDERT / GESCHÜTZT

- R02 bleibt die Produktrevision.
- Frühere R01-/R02-/R03-Artefakte wurden nicht überschrieben.
- Alle bestätigten Anforderungen und Nutzermaße bleiben unangetastet: genau
  zwei Hohlschalen, 1,6-mm-Grundwand, ca. 200 mm Gesamtausdehnung,
  Ø10,0-mm-Zapfen, 20,0-mm-Eingriff, innenliegende Klebeverbindung,
  Nutzer-Trennlinie, Materialzuordnung und keine Zusatzfunktionen.
- Alte beschädigte REF-CLEAN, R03-Rohdatei, REF-SEAM und sekundäre Multiansicht
  wurden nicht als Ersatz-Formquelle verwendet.

## ENTFERNT

- Nichts.
- Keine bestätigte Geometrie und keine bestehende Ausgabe wurden verändert.

## OFFEN

- Vollständige autorisierte REF-CLEAN mit 31.028 Byte und dem festgelegten
  SHA-256 oder Freigabe einer anderen konkreten primären Formquelle.
- Danach tatsächlicher Trellis-Lauf, Rohmesh-Archivierung, Rohmesh-Render und
  Optik-Gate.
- Nur nach eindeutigem Optik-PASS: CAD-/FDM-Aufbereitung, STL/Assembly und
  technische Validierung.
- Reale Slicer-, Druck-, Passungs-, Klebe-, Support- und Sichtprüfung.
- Finale optische sowie Produkt-/Druckfreigabe ausschließlich durch den Nutzer.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: true`

Grund: Die erforderliche reale Primärreferenz fehlt unter der freigegebenen
Dateiidentität und kann nicht eindeutig rekonstruiert werden.

`FINALE_PRODUKTFREIGABE: false`

