# TASK-HANNES-MANFRED-DOCUMENTS-REPAIR-R04

## Ziel
Den lokalen Documents-Ruediger auf GAMECENTER kontrolliert aus dem nachgewiesenen versteckten Post-Validation-/Infrastruktur-Loop holen, den vorhandenen R02.3-Loop-Guard anwenden und den Betriebsflow so haerten, dass kuenftige lokale Agent-Repairs bevorzugt ueber MANFRED/HANNES statt ueber manuelle Nutzer-PowerShell laufen.

## Prioritaet
SOFORTIGE INFRASTRUKTUR-/BETRIEBSREPARATUR. Herbst-Igel bleibt HOLD und darf durch diesen Auftrag nicht bearbeitet werden.

## Verbindliche Ausgangslage
- Documents-Repo: h4rdstyle1988/Documents-Controlling-clear
- Documents-AgentRoot: D:\Documents-Controlling-Agent
- Documents-Scheduler: Documents-Ruediger-Agent
- aktueller Produktauftrag: tasks/R01_GENERIC_VALIDATION_CORE.md
- nach Usage-Limit-Retry neuer Task-Blob: 180b5973f7b5320af090cf9b96fe46e5ec755336
- beobachteter Fehler: Live-Status blieb attempt=1/retry_count=0, waehrend Codex-PIDs wechselten; der aktuelle Watcher zaehlt Fehler nach Codex Exit 0 im allgemeinen Infrastruktur-Catch und kann dadurch unsichtbar erneut starten.
- vorbereiteter, versionierter Hotfix: tools/documents-agent/hotfix-documents-r02.3-hidden-loop-guard.ps1

## Muss 1: Aktuelle Arbeit sichern
Vor jedem Stop/Restart:
1. Pruefe, dass ausschliesslich der dedizierte Documents-Worker unter D:\Documents-Controlling-Agent\worker\Documents-Controlling-clear-worker verwendet wird und origin auf h4rdstyle1988/Documents-Controlling-clear zeigt.
2. Dirty/uncommittete Dateien niemals loeschen oder resetten. Vor Eingriff als eindeutig benannten Stash sichern.
3. Bereits remote verifizierte Checkpoints respektieren.
4. Keine normalen Benutzer-Working-Trees anfassen.

## Muss 2: R02.3 anwenden
Fuehre den vorhandenen Hotfix tools/documents-agent/hotfix-documents-r02.3-hidden-loop-guard.ps1 lokal kontrolliert aus.
Erwartete Wirkung:
- WatcherVersion DOCUMENTS-R02.3
- attempt wird vor jedem Codex-Start persistent gespeichert
- nach drei aufeinanderfolgenden Infrastruktur/Post-Validation-Fehlern stabil BLOCKIERT statt Endlosschleife
- Parsercheck PASS vor Neustart
- Backup von Runtime-Watcher und State bleibt erhalten
- nur Documents-Ruediger-Agent wird neu gestartet

Falls der Hotfix wegen abweichendem Runtime-Text nicht deterministisch angewendet werden kann: STOPP, nichts destruktiv veraendern, konkreten Diff/Blocker dokumentieren.

## Muss 3: Ursache des PID-Wechsels pruefen
Nach Neustart mindestens beobachten:
- gleicher Task-Blob bleibt aktiv
- jeder neue Codex-Prozess fuehrt zu attempt +1
- retry_count bleibt nur fuer echte Codex-Fehler zustaendig
- Post-Validation-/Infrastrukturfehler duerfen nicht mehr endlos neu starten
- kein paralleler zweiter Documents-Watcher
- keine neue Task-Blob-Erzeugung ohne explizite Revision

## Muss 4: MANFRED fuer kuenftigen Flow haerten
MANFRED R01 darf weiterhin KEINE allgemeine Remote-Shell werden. Implementiere eine eng begrenzte Maintenance-Faehigkeit fuer fest definierte Agent-Repairs:
- nur bekannte AgentRoots/Scheduler (AI3D und Documents)
- nur versionierte Maintenance-Skripte aus h4rdstyle1988/AI3D-Model unter explizit erlaubtem Pfad tools/manfred-supervisor/maintenance/ oder tools/documents-agent/
- Whitelist statt beliebiger Kommandos
- vor jeder lokalen Datei-Aenderung Backup/Parsercheck
- Worker-Origin/Pfad pruefen
- laufende ungesicherte Arbeit zuerst sichern
- Ergebnis lokal auditieren
- keine Projekt-/CAD-/Produktaufgaben erzeugen
- keine beliebigen Shell-Kommandos aus GitHub-Inhalten ausfuehren

Wenn eine sichere automatische Selbstaktualisierung von MANFRED ohne Bootstrap-Zirkelschluss nicht belastbar moeglich ist, dokumentiere das klar und implementiere nur den sicheren Teil. Keine Sicherheitsgrenzen aufweichen, nur um Automation zu erzwingen.

## Muss 5: Verifikation
Nach Repair:
1. Scheduled Task Documents-Ruediger-Agent vorhanden und aktiv.
2. Genau ein documents-agent-watch.ps1 Prozess.
3. Live-Status in Documents-Repo wechselt auf START/TASK_GEFUNDEN/ARBEITET/CHECKPOINT/VALIDIERUNG/FERTIG oder einen klaren neuen BLOCKIERT-Grund.
4. Watcher-Version im Live-Status = DOCUMENTS-R02.3.
5. Wenn ein zweiter Codex-Start stattfindet, attempt muss > 1 sein.
6. Keine Herbst-Igel-Arbeit aufnehmen.
7. Keine Produktanforderungen von Documents R01 veraendern.

## Ergebnis
Erzeuge einen knappen Ergebnisbericht unter reports oder tools/manfred-supervisor mit:
- REPAIR_STATUS = PASS/BLOCKED
- vorher/nachher Watcher-Version
- gesicherte Stash-/Backup-Namen
- Scheduler-/Watcher-PIDs
- Live-Status nach Repair
- ob MANFRED-Maintenance-Flow erweitert wurde
- verbleibende manuelle Restschritte nur falls technisch unvermeidbar

## Abschlusskriterium
PASS erst, wenn der lokale Documents-Agent nachweislich unter R02.3 laeuft und der versteckte ungezählte Restart-Loop nicht mehr moeglich ist. Danach den Documents-Produktauftrag selbststaendig weiterlaufen lassen.
