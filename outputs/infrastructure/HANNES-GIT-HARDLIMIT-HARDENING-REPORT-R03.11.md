# Hannes Git-Hardlimit-Hardening R03.11

Task: `tasks/TASK-HANNES-GIT-HARDLIMIT-HARDENING-R03.md`  
Revision: `R03.11`  
Ergebnisstatus: **PASS**

## SOLL/IST

| SOLL | IST | Status |
|---|---|---|
| Neue/taskbezogene Dateien vor Commit/Push prüfen | Arbeitsbaumprüfung vor `git add`, Indexprüfung nach `git add`, Commit-Baumprüfung vor Push | PASS |
| Normale Sicherheitsgrenze 90 MB | Exakt `90.000.000` Byte; nur Dateien `<=` Grenze bleiben regulär im Ergebnis | PASS |
| Keine stille Mitnahme über 90 MB | Jeder Treffer wird ausgelagert, verlustfrei ausgetauscht oder mit `GIT_HARDLIMIT_STOPP` blockiert | PASS |
| Temporäre/diagnostische Großartefakte lokal sichern | Task-/Blob-spezifischer Pfad unter `D:\3D-Models\generated\_ruediger-local-large-artifacts` | PASS |
| Manifest | Originalpfad, lokaler Pfad, Größe, SHA-256 und Grund; zusätzlich Handling/Austauschdatei | PASS |
| Verbindliche finale Großausgabe schützen | Nur SHA-256-verifizierte ZIP-Austauschdarstellung; andernfalls technischer STOPP bei erhaltenem Original | PASS |
| GitHub-Hardlimit direkt vor Push prüfen | Commit-Baumprüfung mit exakt `100.000.000` Byte in normalem und Recovery-Push-Pfad | PASS |
| Push-Retries begrenzt; lokales Ergebnis erhalten | Bestehende begrenzte Retry-Logik bleibt; Hardlimit-STOPP startet keinen Push und keinen automatischen Codex-Neulauf | PASS |
| Keine Produktänderung | Keine CAD-, Mesh-, STL-, 3MF-, Geometrie- oder Maßdatei geändert | PASS |
| Maschinenlesbarer Agentenname | Live-Status und Schema enthalten `agent_name: "Hannes"` | PASS |
| Watcher-Version erhöhen | `R03.10` → `R03.11` | PASS |
| Syntax-/Smoke-/Hardlimit-Test | Parser PASS; isolierter Hardlimit-Selbsttest PASS | PASS |
| GEÄNDERT / UNVERÄNDERT / ENTFERNT / OFFEN | In diesem Bericht und im Changelog dokumentiert | PASS |

## GEÄNDERT

- `tools/ruediger-agent-watch.ps1`: Größenprüfung, sichere Auslagerung, Manifest, verlustfreie Austauschdarstellung, Push-Gate, terminaler STOPP, Hannes-Status und Selbsttest.
- `status/RUEDIGER_STATUS.schema.json`: `agent_name`, `PUSH_RETRY` und `STOPP`.
- `status/README.md`, `tasks/WORKFLOW.md`, `AGENTS.md`: Hannes-Benennung und Hardlimit-Verhalten dokumentiert.
- `status/WATCHER-R03.11-CHANGELOG.md`: Revisionsänderung.
- `outputs/infrastructure/result-status-r03.11.json`: maschinenlesbarer Ergebnisstatus.

## UNVERÄNDERT

- Bestätigte Produktgeometrie und sämtliche Nutzermaße.
- CAD-, STL-, 3MF-, GLB-, PLY- und Druckdateien.
- Queue-Reihenfolge, Freigabe-Gate, Task-Identität und Remote-Verifikation.
- Kompatibilitätsnamen bestehender Branches, Dateien, Scheduler und lokaler Runtime-/State-Pfade.

## ENTFERNT

- Keine vorhandene Repository-Datei.
- Keine lokale Produkt- oder Großartefaktdatei; der Selbsttest arbeitete ausschließlich in einem isolierten temporären Test-Repository und räumte dessen Testdaten wieder auf.

## VALIDIERUNGEN

- PowerShell-Parser: PASS, keine Syntaxfehler.
- Hardlimit-Selbsttest: PASS.
  - produktive Konstanten `90.000.000` und `100.000.000` Byte geprüft;
  - simulierte temporäre Datei über der Testgrenze lokal ausgelagert;
  - Datei exakt auf der simulierten Sicherheitsgrenze akzeptiert;
  - simulierte finale Datei über der Testgrenze als ZIP erzeugt, entpackt und per SHA-256 gegen das Original geprüft;
  - nicht ausreichend verkleinerbare geschützte Datei mit technischem STOPP blockiert und Originalerhalt geprüft;
  - Manifest mit zwei Artefakten geprüft;
  - zulässiger Commit-Baum akzeptiert;
  - Commit-Baum oberhalb des simulierten 100-MB-Hardlimits vor Push blockiert.
- `git diff --check`: siehe maschinenlesbaren Ergebnisstatus.
- Dateiumfang: keine Produkt-/Geometriedatei geändert.

Selbsttestbefehl:

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File tools/ruediger-agent-watch.ps1 -AgentRoot <isolierter-test-root> -WorkerDir <isolierter-test-worker> -PollSeconds 5 -HeartbeatSeconds 60 -HardlimitSelfTestOnly
```

## OFFEN

- R03.11 in der produktiven Runtime per bestehendem Self-Update/Restart laden.
- Einen realen normalen Ergebnis-Push samt Remote-SHA-Verifikation beobachten.
- Einen kontrollierten produktiven Großartefaktfall beobachten; keine bestehende Nutzerdatei wurde für den Test künstlich verändert.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false` – offene Punkte sind ausschließlich technische Laufzeitprüfungen. Es fehlt keine Produktentscheidung.

Keine finale Nutzer- oder Produktfreigabe erteilt.
