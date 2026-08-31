# TASK-WATCHER-LOCAL-RECOVERY-HARDENING-R02

## Status
Freigegebener rein technischer Workflow-Fix. Keine Produktgeometrie aendern.

## Ausgangslage
Watcher R03.9 kann lokale, bereits committete Ergebnisse nach einem Push-Fehler wiederverwenden. Die aktuelle Recovery-Pruefung verwendet jedoch `merge-base --is-ancestor origin/master <result-commit>`. Das kann ein korrektes lokales Ergebnis faelschlich ablehnen, wenn `master` nach Erzeugung des Ergebnis-Commits durch reine Workflow-/Task-Aenderungen weitergelaufen ist.

## Auftrag
Haerte ausschliesslich die lokale Ergebnis-Recovery des Watchers.

## Verbindliche Anforderungen
1. Ein lokales Ergebnis darf nur wiederverwendet werden, wenn Branchname, Commit-Subject und die im Ergebnis-Commit enthaltene freigegebene Task-Datei eindeutig zur aktuell selektierten Task-Revision gehoeren.
2. Pruefe insbesondere den Blob der Task-Datei im Ergebnis-Commit gegen `Task.blob`.
3. Die Recovery darf NICHT davon abhaengen, dass der aktuelle `origin/master` bereits Vorfahr des alten Ergebnis-Commits ist.
4. Dirty Working Tree, falscher Task-Blob, falsches Commit-Subject oder falscher Branch -> keine automatische Wiederverwendung.
5. Push bleibt begrenzt; kein Endlosretry.
6. Nach Push Remote-SHA strikt gegen lokalen Ergebnis-Commit verifizieren, erst dann State `processed` schreiben.
7. Keine Aenderung an CAD-/Produktlogik, Queue-Reihenfolge oder Nutzerfreigaben.
8. Watcher-Version hochzaehlen.
9. PowerShell-Syntax-/Smoke-Test dokumentieren.
10. GEÄNDERT / UNVERÄNDERT / ENTFERNT / OFFEN dokumentieren.

## Ziel
Ein nachweislich zur exakten Task-Revision gehoerendes lokales Ergebnis wird nach Neustart gepusht statt neu berechnet, auch wenn `master` zwischenzeitlich durch reine Workflow-Aenderungen fortgeschritten ist.

Keine finale Nutzerfreigabe behaupten.
