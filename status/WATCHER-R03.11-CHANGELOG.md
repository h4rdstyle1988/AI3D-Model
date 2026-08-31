# WATCHER R03.11 – Local-Recovery-Hardening

Task: `tasks/TASK-WATCHER-LOCAL-RECOVERY-HARDENING-R02.md`  
Task-Blob: `76d7b38f14a579efed372e22fab621ad2a9846ad`

## GEÄNDERT

- Die lokale Ergebnis-Recovery akzeptiert ausschließlich den aus aktuellem Task-Pfad und aktuellem `Task.blob` abgeleiteten Branchnamen.
- Ein bereits dirty Working Tree wird vor Branchwechsel oder Push abgewiesen.
- Der lokale Branch wird explizit als Commit aufgelöst; nach dem Checkout muss `HEAD` exakt diesem zuvor geprüften Ergebnis-Commit entsprechen.
- Commit-Subject und Blob der Task-Datei im Ergebnis-Commit müssen exakt zur selektierten Task-Revision passen.
- Nach dem begrenzten Push muss der Remote-SHA exakt dem lokalen Ergebnis-Commit entsprechen. Erst danach wird der Task als `processed` gespeichert.
- Watcher-Version auf `R03.11` erhöht.
- Ein isolierter Windows-PowerShell-Smoke-Test deckt Positiv- und Negativfälle der Recovery ab.

## UNVERÄNDERT

- FIFO-Reihenfolge und Task-Selektion aus `tasks/TASK_QUEUE.txt`.
- Retry-Grenze des Pushs: Recovery verwendet weiterhin `FetchRetryCount`; es gibt keinen internen Endlosretry.
- CAD-, Mesh-, Produkt- und Nutzermaßlogik.
- Nutzerfreigaben und Task-Identität aus Task-Pfad plus Blob-SHA.
- Normale Ergebnisberechnung, Preflight, Self-Update und Live-Status außerhalb der Recovery.

## ENTFERNT

- Die Abhängigkeit der Recovery von `merge-base --is-ancestor origin/master <result-commit>`.
- Automatische Wiederverwendung bei dirty Working Tree, abweichendem Branch, abweichendem Commit-Subject oder abweichendem Task-Blob.

## OFFEN

- Nach Installation der Runtime ist der Neustart-/Push-Fall einmal gegen den echten Remote-Branch zu beobachten. Dies ist ein technischer Betriebstest und keine Nutzerentscheidung.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false` — keine verbindliche Produktanforderung oder Nutzerangabe muss geändert werden.

Keine finale Nutzer- oder Produktfreigabe erteilt.
