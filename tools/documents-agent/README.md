# Documents-Agent Software-Workflow R02.3

Diese Infrastruktur ist eine getrennte zweite Ruediger-Instanz fuer
`Documents-Controlling-clear`. Sie aendert weder Konfiguration noch Queue-Semantik
des bestehenden 3D-Agenten. Die produktiven Standardpfade stehen in
`documents-agent-profile.json`.

## Einmalige Installation und Aktivierung

Aus einer **als Administrator gestarteten PowerShell** im Root dieses
Repositories:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\tools\documents-agent\install-documents-agent.ps1" -StartAfterInstall
```

Dieser ausdrueckliche Benutzerbefehl legt ausschliesslich die getrennten Pfade
unter `D:\Documents-Controlling-Agent` an, klont das Zielrepository in den
dedizierten Worker, registriert `Documents-Ruediger-Agent` und startet ihn. Durch
diesen Task selbst wird der Installer weder ausgefuehrt noch der Scheduler
gestartet.

## Kontrolliertes Update oder Repair

Nach Aktualisierung dieses Repository-Standes:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\tools\documents-agent\repair-documents-agent.ps1" -StartAfterRepair
```

Repair wartet bei einem laufenden Auftrag, bis kein zugehoeriger Codex-Prozess
mehr aktiv und der dedizierte Worker sauber beziehungsweise remote gesichert ist.
Ein Worker mit unerwartetem `origin` wird nicht automatisch umkonfiguriert.

## Diagnose und gefahrlose Queue-Auswahl

Generischer Preflight ohne CAD-Abhaengigkeiten:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\Documents-Controlling-Agent\runtime\documents-agent-preflight.ps1"
```

Queue-Auswahl gegen `origin/main`, ohne den gefundenen Task auszufuehren und ohne
einen Live-Status zu publizieren:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\Documents-Controlling-Agent\runtime\documents-agent-watch.ps1" -SelectionTestOnly
```

Statische Infrastrukturpruefung; der optionale Schalter versucht zusaetzlich den
reinen Queue-Auswahltest gegen das Zielrepository:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\tools\documents-agent\test-documents-agent-infrastructure.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\tools\documents-agent\test-documents-agent-infrastructure.ps1" -LiveQueueSelectionTest
```

## Checkpoint- und Resume-Modell

- FIFO-Steuerquelle: `tasks/TASK_QUEUE.txt`; `CURRENT_TASK.txt` wird nicht gelesen.
- Task-Identitaet: Task-Pfad plus Blob-SHA aus `origin/main`.
- Ergebnisbranch: `ruediger/<task>-<blob8>` mit Remote-SHA-Verifikation.
- Groessere Software-Aufgaben werden in wenige logisch abgeschlossene Abschnitte
  zerlegt. Nach zielgerichteten Tests darf Codex einen Zwischen-Commit erzeugen
  und auf denselben Task-Branch pushen. Mikro-Commits sind nicht vorgesehen.
- Ein Checkpoint ist nur gueltig, wenn seine Commit-Trailer Task-Pfad, Task-Blob,
  Basis-SHA, positive Checkpoint-Nummer und
  `Ruediger-Checkpoint-Verified: true` eindeutig ausweisen. Zusaetzlich prueft
  der Watcher Basis-Ancestry und den unveraenderten Task-Blob im Commit.
- Bei lokal/remote abweichenden Checkpoints wird der verifizierte Remote-Stand
  verwendet. Ein lokaler Checkpoint wird nur bei eindeutiger Identitaet
  akzeptiert und vor dem Resume remote gesichert. Ein fremder oder
  inkonsistenter Remote-Branch fuehrt zu `BLOCKIERT`.
- Dirty oder nicht verifizierte Arbeitsbaum-Aenderungen gelten nie als
  Checkpoint. Vor einer technischen Wiederherstellung sichert der Watcher sie
  explizit als Stash und setzt nur innerhalb des geprueften dedizierten Workers
  auf den verifizierten Checkpoint beziehungsweise beim Erstlauf auf
  `origin/main` zurueck.
- Ein gueltiger Checkpoint wird niemals pauschal auf `origin/main` gesetzt.

## Retry, Validierung und Audit

- Maximal drei aufeinanderfolgende Codex-Ausfuehrungsfehler ohne neuen
  verifizierten Checkpoint sind erlaubt. Danach bleibt die FIFO-Task in
  `BLOCKIERT` und wird nicht erneut ausgefuehrt. Ein neuer verifizierter
  Checkpoint beginnt ein frisches begrenztes Fehlerbudget.
- Fetch-, Push- und sonstige Infrastrukturfehler zaehlen getrennt und erhalten
  einen bis auf fuenf Minuten begrenzten exponentiellen Backoff.
- R02.3 speichert `attempt` vor jedem Codex-Start. Drei aufeinanderfolgende
  Infrastruktur- oder Post-Validation-Fehler fuehren stabil zu `BLOCKIERT`,
  sodass ein erfolgreicher Codex-Exit ohne Ergebnisdateien keinen versteckten
  PID-Restart-Loop mehr erzeugen kann. Echte Codex-Fehler bleiben ausschliesslich
  im separaten `retry_count`-Budget.
- Vor Checkpoints laufen zielgerichtete Tests; vor dem finalen Ergebnis fordert
  der Prompt den vollstaendigen relevanten Testlauf. Der finale Commit wird vom
  Watcher mit Task-Trailern erzeugt und erst nach exakter Remote-SHA-Pruefung als
  verarbeitet gespeichert.
- Der Live-Status fuehrt knapp Phase, Attempt, Retry-Zahl, letzten verifizierten
  Checkpoint-SHA und Checkpoint-Nummer. Betriebsphasen sind `ARBEITET`,
  `CHECKPOINT`, `VALIDIERUNG`, `FERTIG`, `FEHLER_RETRY`, `BLOCKIERT` und
  `WARTET`; Heartbeats erzeugen keine Aenderungen im Produktbranch.

## Betriebsmodell und Abgrenzung

- Live-Status liegt ausschliesslich auf `ruediger/live-status` im Documents-Repo.
- Lock, State, Logs, Runtime, Temp und Worker liegen unter dem getrennten
  Documents-AgentRoot.
- Vor `reset --hard`, `clean -fd` oder einer Sicherung wird geprueft, dass der Worker unter dem
  dedizierten `AgentRoot\worker` liegt. Normale Benutzer-Arbeitsbaeume werden
  nicht veraendert.
- Der Preflight prueft PowerShell, Git, Git-Identitaet und Codex. Python ist nur
  informativ; CAD-, Slicer- und 3D-Ausgabe-Pfade sind nicht Bestandteil des
  Documents-Agenten.

Sparse-Checkout wird nicht mehr aktiviert: Fuer allgemeine Software-Tests und
Resume-Pfade ist ein vollstaendiger Worker belastbarer; ein messbarer Vorteil
des bisherigen `tasks`/`tools`-Ausschnitts war nicht belegt.

## Optimierungsbremse

Optimieren nur bei messbarem Problem, wiederholtem Fehler oder klarer
Zeit-/Robustheitsverbesserung. Keine Refactor-Schleifen ohne konkreten Nutzen.
Nach PASS ist R02 ein eingefrorener stabiler Workflow. Erneute Aenderungen sind
nur bei nachgewiesenem Problem, notwendiger Schnittstellenaenderung,
Sicherheits-/Lizenzthema oder klar belegtem Nutzen vorgesehen. Der Agent
refactort seine Infrastruktur nicht selbststaendig nach erfolgreichen Tasks.

Installation, Parser-/Statik-PASS und ein erfolgreicher Agentenlauf sind keine
finale Freigabe von Dokumentinhalten. Diese bleibt ausschliesslich beim Nutzer.
