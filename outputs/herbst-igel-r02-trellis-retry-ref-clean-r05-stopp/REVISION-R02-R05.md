# Herbst-Igel – Revisionsdokumentation R02 / Retry R05

## Ergebnisstand

- Task: `tasks/TASK-HERBST-IGEL-R02-TRELLIS-RETRY-REF-CLEAN-R05.md`
- Task-Blob-SHA-1: `0ebad9ce7405b87e8d858dd9f89a6de97bb02890`
- Produktrevision: `R02` (unverändert)
- Retry-/Referenztransportstand: `R05`
- Status: `STOPP / OFFEN`
- Letzte abgeschlossene Phase: `REFERENZ-PREFLIGHT`
- Finale Produktfreigabe: `NEIN`

## GEÄNDERT

- Neuer, isolierter R05-STOPP-Ergebnisstand angelegt; frühere STOPP-Stände
  wurden nicht überschrieben.
- Die acht R05-Transportteile exakt numerisch konkateniert und einmal streng
  Base64-dekodiert.
- Bytezahl, SHA-256, JPEG-Struktur, Abmessungen, Farbraum und strikter Decode
  geprüft.
- Die Drei-Byte-Lücke in der zweiten DQT-Tabelle technisch lokalisiert.
- Standardreparatur, 1.674.000 plausible DQT-Kombinationen, vorhandene
  Git-Objekte und lokale Übergabe-/Arbeitsbereiche gegen die autorisierte
  Bildidentität geprüft.
- Reproduzierbarer Auditor sowie maschinenlesbare Berichte erzeugt.

## UNVERÄNDERT / GESCHÜTZT

- R02 bleibt die Produktrevision.
- Es wurde keine bestätigte Geometrie verändert oder ersetzt.
- Alle Nutzermaße und Funktionen bleiben unangetastet: genau zwei Hohlschalen,
  1,6-mm-Grundwand, ca. 200 mm maximale Ausdehnung, Ø10,0-mm-Zapfen,
  20,0-mm-Eingriff, eine mittige innenliegende Klebeverbindung, Nutzer-
  Trennlinie, Materialzuordnung und keine Zusatzfunktionen.
- Alte korrupte R03/R04-Referenzen, REF-SEAM und die sekundäre Multiansicht
  wurden nicht als primäre Formquelle verwendet.
- Keine parametrische Ersatzfigur wurde erzeugt.

## ENTFERNT

- Nichts.
- Keine frühere Ausgabe oder bestätigte Geometrie wurde überschrieben.

## OFFEN

- Vollständige autorisierte REF-CLEAN mit 40.823 Byte und dem festgelegten
  SHA-256 oder ausdrückliche Freigabe einer anderen konkreten Primärquelle.
- Danach tatsächlicher Trellis-Lauf, unveränderte Rohmesh-Archivierung,
  Rohmesh-Render und Optik-Gate.
- Nur nach eindeutigem Optik-PASS: CAD-/FDM-Aufbereitung, STL/Assembly und
  technische Validierung.
- Reale Slicer-, Druck-, Passungs-, Klebe-, Support- und Sichtprüfung.
- Finale optische sowie Produkt-/Druckfreigabe ausschließlich durch den Nutzer.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: true`

Grund: Die erforderliche reale Primärreferenz fehlt unter der freigegebenen
Dateiidentität und kann nicht eindeutig rekonstruiert werden.

`FINALE_PRODUKTFREIGABE: false`

