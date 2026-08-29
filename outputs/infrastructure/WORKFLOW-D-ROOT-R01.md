# Lokaler D:-Workflow R01

- Stamm: `D:\AI3D-Agent`
- Worker: `worker\AI3D-Model-worker`
- Ergebnisse/Bibliothek: `outputs`
- Watcher-Logs: `logs`
- Zustands- und Preflight-Dateien: `state`
- Reproduzierbare Caches und temporäre Daten: `cache`, `temp`
- Isolierte projektbezogene Toolchain-Umgebungen: `toolchain`

`tools/initialize-ai3d-agent.ps1` richtet diese Struktur ein und löscht keine alten Daten. `-RegisterScheduledTask -SchedulerDiagnosticOnly` registriert zuerst den ungefährlichen Diagnoselauf für `AI3D-Ruediger-Agent`. Nach dessen PASS wird die Aufgabe durch erneuten Aufruf ohne `-SchedulerDiagnosticOnly` auf den normalen Watcher umgestellt. Der Watcher schreibt den Preflight nach `state\toolchain-preflight.json`.

Reale Referenzen folgen `references/README.md`. Jeder Ergebnisbranch führt einen Status nach `result-status.schema.json`. Technische STOPPs stehen in `technical_blockers`, echte Nutzerentscheidungen ausschließlich in `user_decisions`.
