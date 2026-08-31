# HANNES WATCHER R03.11 – Git-Hardlimit-Hardening

## GEÄNDERT

- Watcher-Version auf `R03.11` erhöht und maschinenlesbares Statusfeld `agent_name: "Hannes"` ergänzt.
- Vor dem Ergebnis-Commit werden alle neuen beziehungsweise gegenüber `origin/master` geänderten Dateien geprüft. Die normale Sicherheitsgrenze beträgt exakt 90.000.000 Byte.
- Klar temporäre/diagnostische Dateien oberhalb der Sicherheitsgrenze werden lokal unter `D:\3D-Models\generated\_ruediger-local-large-artifacts\<task>-<blob>` gesichert und nicht committet.
- Verbindliche oder nicht eindeutig temporäre Großdateien werden nur durch ein kleineres ZIP ersetzt, wenn Entpacken und SHA-256-Vergleich die verlustfreie Rückgewinnung bestätigen. Andernfalls setzt Hannes einen technischen `STOPP` vor Commit/Push.
- Jede Auslagerung erhält ein Git-seitiges JSON-Manifest mit Originalpfad, lokalem Pfad, Bytegröße, SHA-256, Grund und optionaler Austauschdatei.
- Direkt vor Ergebnis-Push und Recovery-Push wird der Commit-Baum auf das GitHub-Hardlimit von exakt 100.000.000 Byte geprüft. Recovery prüft zusätzlich die 90-MB-Sicherheitsgrenze.
- Hardlimit-STOPPs werden als terminaler technischer Fehler gespeichert. Das lokale Ergebnis bleibt stehen; Codex wird für dieselbe Task-Revision nicht automatisch erneut gestartet.
- Ergebnis- und Live-Status-Commitmeldungen verwenden für neue Stände `Hannes`; bestehende technische Pfade, Branches, Scheduler- und Dateinamen bleiben kompatibel.
- Isolierter Selbsttestmodus `-HardlimitSelfTestOnly` ergänzt.

## UNVERÄNDERT

- Produktlogik, CAD-/Mesh-Geometrie, Nutzermaße und Freigabe-Gates.
- FIFO-Auswahl und Task-Identität aus Task-Pfad plus Blob-SHA.
- Begrenzte Push-Retries, lokaler Ergebniserhalt und Remote-SHA-Verifikation.
- Technische Namen `ruediger/...`, `RUEDIGER_STATUS.json`, Schedulername und bestehende Runtime-/State-Dateinamen.

## ENTFERNT

- Kein produkt- oder geometriebezogener Bestandteil.
- Kein bestehendes Großartefakt wurde durch diesen Infrastrukturauftrag verschoben oder gelöscht.

## OFFEN

- Produktive Runtime muss R03.11 über den bestehenden Self-Update-/Restart-Weg laden.
- Ein realer Ergebnis-Push mit normalen Dateien sowie ein kontrollierter produktiver Großartefaktfall bleiben als Laufzeitprüfungen offen.

Keine finale Nutzer- oder Produktfreigabe.
