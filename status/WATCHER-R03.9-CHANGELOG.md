# WATCHER R03.9 – Push-Recovery-Fix

## GEÄNDERT
- `Invoke-GitSafe` begrenzt jetzt auch Ergebnis-Pushes auf die übergebene Retry-Zahl.
- Nach dem letzten fehlgeschlagenen Push wird die echte letzte Git-Fehlermeldung als Exception weitergegeben.
- Neuer Recovery-Pfad erkennt einen bereits lokal vorhandenen, abgeschlossenen Task-Commit anhand des erwarteten Branch-Namens und Commit-Subjects.
- Ein solches lokales Ergebnis wird nicht neu gerechnet, sondern ausschließlich erneut gepusht und remote verifiziert.
- Neuer Live-Status `PUSH_RETRY` für diesen Recovery-Fall.
- `GIT_TERMINAL_PROMPT=0`, damit ein nicht sichtbarer Credential-Prompt den unbeaufsichtigten Watcher nicht blockiert.
- Watcher-Version auf `R03.9` erhöht.

## UNVERÄNDERT
- FIFO-Task-Selektion.
- CAD-/Produktlogik.
- Nutzerfreigaben und verbindliche Produktanforderungen.
- Preflight-, Codex- und Remote-Verifikationsprinzip.

## ENTFERNT
- Unbegrenzte interne Push-Retry-Schleife.
- Der separat geplante Queue-Hotfix wurde aus der aktiven Queue entfernt, weil der Fix direkt im Watcher umgesetzt wurde. Die historische Task-Datei bleibt erhalten.

## OFFEN
- R03.9 muss auf GAMECENTER durch einen Neustart des laufenden R03.8-Watchers geladen werden, weil R03.8 aktuell innerhalb der alten Push-Schleife blockiert und daher sein Self-Update nicht mehr erreicht.
- Nach dem Neustart ist zu prüfen, ob der lokale R16-Result-Commit erkannt, ohne erneute Codex-Berechnung gepusht und remote verifiziert wird.
