# Documents-Agent Bootstrap R01

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

## Betriebsmodell

- FIFO-Steuerquelle: `tasks/TASK_QUEUE.txt`; `CURRENT_TASK.txt` wird nicht gelesen.
- Task-Identitaet: Task-Pfad plus Blob-SHA aus `origin/main`.
- Ergebnisbranch: `ruediger/<task>-<blob8>` mit Remote-SHA-Verifikation.
- Fehlgeschlagene Tasks gelten nicht als verarbeitet und werden erneut versucht.
- Ein bereits lokal abgeschlossenes Ergebnis derselben Task-Revision wird beim
  Push-Fehler wiederverwendet, nicht erneut erzeugt.
- Live-Status liegt ausschliesslich auf `ruediger/live-status` im Documents-Repo.
- Lock, State, Logs, Runtime, Temp und Worker liegen unter dem getrennten
  Documents-AgentRoot.
- Vor `reset --hard` oder `clean -fd` wird geprueft, dass der Worker unter dem
  dedizierten `AgentRoot\worker` liegt. Normale Benutzer-Arbeitsbaeume werden
  nicht veraendert.
- Der Preflight prueft PowerShell, Git, Git-Identitaet und Codex. Python ist nur
  informativ; CAD-, Slicer- und 3D-Ausgabe-Pfade sind nicht Bestandteil des
  Documents-Agenten.

Installation, Parser-/Statik-PASS und ein erfolgreicher Agentenlauf sind keine
finale Freigabe von Dokumentinhalten. Diese bleibt ausschliesslich beim Nutzer.
