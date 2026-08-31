# TASK – DOCUMENTS AGENT BOOTSTRAP R01

## STATUS
APPROVED BY USER

## PURPOSE
Der bestehende Hannes/Rüdiger-Workflow soll für ein zweites, vollständig getrenntes Repository nutzbar gemacht werden:
`https://github.com/h4rdstyle1988/Documents-Controlling-clear.git`

Das bestehende produktive 3D-Agentensystem unter `D:\AI3D-Agent` darf dabei funktional NICHT verändert oder gefährdet werden.

## BINDING
1. Bestehenden 3D-Watcher/Scheduler/Worker nicht umkonfigurieren.
2. Keine Änderung der bestehenden AI3D-Task-Auswahl oder Queue-Semantik.
3. Zweite Instanz muss eigene Pfade, Locks, State, Logs, Runtime, Worker und Scheduler-Namen besitzen.
4. Zielrepo verwendet `main`, nicht `master`.
5. Documents-Agent benötigt KEINEN CAD-Preflight.
6. Documents-Agent soll denselben bewährten Grundworkflow nutzen: FIFO `tasks/TASK_QUEUE.txt`, Task-Identität aus Pfad + Blob-SHA, dedizierter Worker, Codex-Ausführung, Branch-Ergebnis, Remote-Verifikation, Retry/Recovery, Live-Status auf separatem Status-Branch.
7. Keine automatische Änderung am normalen Benutzer-Arbeitsbaum.
8. Keine Arbeitgeberdaten oder Inhalte aus dem Documents-Projekt anfassen; diese Aufgabe betrifft nur die Agent-Infrastruktur.
9. Bestehende AI3D-Runtime darf nicht automatisch durch die neue Documents-Runtime ersetzt werden.

## TARGET CONFIGURATION
Suggested independent defaults:
- Repo: `https://github.com/h4rdstyle1988/Documents-Controlling-clear.git`
- Base branch: `main`
- AgentRoot: `D:\Documents-Controlling-Agent`
- WorkerDir: `D:\Documents-Controlling-Agent\worker\Documents-Controlling-clear-worker`
- Scheduler: `Documents-Ruediger-Agent`
- Live status branch: `ruediger/live-status`
- Poll interval: 30 s
- Log retention: 7 days

## DESIGN GOAL
Do not create a fragile one-off copy if a small, well-tested parameterization of the proven watcher infrastructure is safer. However, preserving the existing AI3D behavior is the highest priority.

A good result may be either:
A) a generic reusable watcher/runtime with explicit project profile while keeping AI3D defaults backward-compatible, or
B) a separate Documents-specific watcher derived from the proven design.
Choose whichever has lower regression risk.

## REQUIRED VALIDATION
- PowerShell parser PASS for every new/changed script.
- Static validation proving AI3D defaults still point to `D:\AI3D-Agent`, `AI3D-Ruediger-Agent`, AI3D repo/master and CAD preflight where applicable.
- Static validation proving Documents profile points only to its independent root/scheduler/repo/main branch and no CAD paths.
- Selection test against the Documents repo queue if technically possible without executing the queued implementation task.
- Lock/state/log paths must be independent.
- No destructive commands against user's normal working trees.

## DELIVERABLES
Create task-related infrastructure files under an isolated path such as:
`tools/documents-agent/`

At minimum provide:
- watcher/runtime script or profile
- installer/bootstrap script
- restart/repair path
- diagnostic/preflight for generic development prerequisites only (Git, Codex, Python as needed), not CAD
- README with one-command installation/update instructions
- machine-readable validation report

Do NOT install or start the second scheduler automatically from this task unless the task environment can do so without touching the user's interactive machine state unexpectedly. Prefer producing a reviewed one-command installer for the user.

## RESULT
Report PASS/STOP/OPEN and explicitly state:
- whether existing AI3D workflow was left behaviorally unchanged
- files created/changed
- parser/tests run
- exact one-time command required from user to activate Documents agent, if any
- NUTZERENTSCHEIDUNG_ERFORDERLICH true/false
