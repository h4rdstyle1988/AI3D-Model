# MANFRED Supervisor R01.1

MANFRED ist die lokale Supervisor- und Betriebsueberwachung fuer die bestehenden
Agentenstapel auf GAMECENTER.

Ziele:

- AI3D-Ruediger-Agent und Documents-Ruediger-Agent ueberwachen
- genau einen Watcher pro Agent sicherstellen
- abgestuerzte Watcher ueber den bestehenden Scheduled Task neu starten
- doppelte Watcher erkennen und nur ueberzaehlige Instanzen beenden
- laufende Codex-Worker nicht grundlos beenden
- Usage-Limit/Retry-Zustaende als zulaessige Wartezustaende behandeln
- Logs und lokalen Status schreiben
- Herbst-Igel nach R19 auf HOLD belassen; MANFRED erzeugt niemals Projektaufgaben
- keine beliebigen Remote-Shell-Kommandos ausfuehren
- lokale, fest allowlistete Agent-Repairs ausschliesslich fuer AI3D und Documents
  ausfuehren

Lokale Installation:

- Root: `D:\Manfred-Supervisor`
- Scheduled Task: `MANFRED-Supervisor`
- Intervall: 60 Sekunden

MANFRED veraendert keinen Projektcode und keine CAD-Ergebnisse. Er ueberwacht
ausschliesslich den Betrieb und fuehrt nur fest definierte Recovery-Aktionen aus.

## Eng begrenzte Maintenance

Der lokal installierte Runner akzeptiert keine Kommandos und keine freien
Skriptpfade. Ein Request enthaelt nur eine bekannte Repair-ID und einen vollen
Commit-SHA. Der Runner prueft vor der Ausfuehrung:

- lokales Request-Schema und begrenzte Request-ID
- bekannte AgentRoots, Worker und Scheduler fuer AI3D oder Documents
- erwartete Git-Origins und dedizierte Worker-Pfade
- erlaubten Repository-Pfad unter `tools/manfred-supervisor/maintenance/` oder
  `tools/documents-agent/`
- den im lokal installierten Runner fest allowlisteten Git-Blob
- PowerShell-Parser fuer Repair-Skript und vorhandenen Ziel-Watcher
- Stash fuer dirty/uncommittete Worker-Arbeit sowie Runtime-/State-Backups

Ein GitHub-Inhalt allein kann weder eine Repair-ID noch einen neuen
ausfuehrbaren Blob freischalten. MANFRED R01.1 aktualisiert deshalb seine eigene
Allowlist absichtlich nicht automatisch. Neue Allowlist-Eintraege erfordern den
kontrollierten lokalen Installer-Bootstrap; damit wird der Bootstrap-Zirkelschluss
nicht durch eine allgemeine Remote-Shell aufgeloest.

Nach dem einmaligen R01.1-Bootstrap kann HANNES einen bekannten lokalen Repair so
anfordern:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\Manfred-Supervisor\runtime\request-known-agent-repair.ps1" -RepairId documents-r02.3-hidden-loop-guard -SourceCommit <voller-origin-master-SHA>
```

MANFRED verarbeitet `D:\Manfred-Supervisor\maintenance\REQUEST.json` genau
einmal, archiviert den Request und schreibt ein Audit-JSON unter
`maintenance\results`. Projekt-, CAD- und Produkt-Tasks werden dadurch nicht
erzeugt.
