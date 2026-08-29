# Infrastrukturbericht R01

Task: `tasks/TASK-INFRA-CAD-TOOLCHAIN-R01.md`  
Revision: R01  
Gesamtstatus: **OFFEN**

## GEÄNDERT

- Watcher-Standardpfade auf `D:\AI3D-Agent` umgestellt: Worker, Outputs/Bibliothek, Logs, Cache, Temp, Toolchain und State.
- Maschinenlesbarer Toolchain-Preflight vor Diagnose- und Konstruktionsläufen integriert.
- Sichtbarer Codex-Heartbeat im Abstand von standardmäßig 90 Sekunden ergänzt (`ARBEITET`), ohne den Codex-Job zu beenden.
- Kontrolliertes Initialisierungsskript für D:-Unterstruktur, Worker-Clone und optional explizite Scheduler-Registrierung ergänzt.
- Repo-Schema für reale Referenzen und maschinenlesbares Ergebnisstatus-Schema ergänzt.

## UNVERÄNDERT

- Keine Produktgeometrie, CAD-, STL-, 3MF- oder Nutzermaßdatei geändert.
- GitHub-Branch-/Commit-/Push- und Remote-Verifikationslogik bleibt erhalten.
- Kein automatisches Merge nach `master`; keine finale Produktfreigabe.
- Bestehende C:-Daten wurden weder gelöscht noch verschoben oder als löschbar markiert.
- `%LOCALAPPDATA%`-gebundene Codex-Systemdaten wurden nicht verlagert.

## INSTALLIERT / BEREITS VORHANDEN

- Bereits vorhanden: `D:\AI3D-Agent`, Git CLI, Codex CLI und PowerShell.
- Nicht installiert/gefunden: OpenSCAD CLI, echte Python-Installation, CadQuery, Python-Mesh-Prüfmodule, unterstützte Slicer-CLI.
- Keine Software aus Fremdquellen installiert. Der vorhandene `py.exe` ist nur ein Launcher ohne Interpreter.

## VALIDIERT

- PowerShell-Syntaxprüfung aller drei Infrastruktur-Skripte: PASS.
- Watcher-Diagnoselauf mit isoliertem temporärem Stamm: Exit 0; Log-, State- und Preflight-Erzeugung sowie Git-/Codex-Erkennung: PASS. Dies ersetzt nicht den Scheduler-Kontext oder den D:-Test.
- Toolchain-Erkennung: PASS für erforderliche Werkzeuge Git und Codex; Details in `toolchain-preflight.json`.
- `D:\AI3D-Agent` als existierender Ordner gelesen: PASS.
- Optionale fehlende Werkzeuge führen nicht zum pauschalen STOPP: PASS.
- Status und Referenzlage sind maschinenlesbar spezifiziert.

## OFFEN

- **TECHNISCH OFFEN:** Die aktuelle Codex-Sandbox erlaubt Schreibzugriff nur im C:-Repository, nicht unter `D:\AI3D-Agent`. D:-Unterstruktur und D:-Worker konnten nicht real erzeugt werden.
- **TECHNISCH OFFEN:** Im sichtbaren Benutzerkontext wurde keine AI3D-/Rüdiger-Scheduler-Aufgabe gefunden. Scheduler-Start im tatsächlichen Scheduler-Kontext ist nicht nachgewiesen.
- **TECHNISCH OFFEN:** Fetch → Task-Erkennung → Codex → Commit → Push → Remote-Verifikation wurde nicht real ausgeführt und wird nicht vorgetäuscht.
- **TECHNISCH OFFEN:** Der 90-Sekunden-Heartbeat ist implementiert, aber noch nicht während eines ausreichend langen realen Scheduler-Laufs beobachtet.
- **OPTIONAL OFFEN:** OpenSCAD- und CadQuery-Smoke-Tests sind mangels Installation nicht ausführbar.
- **OPTIONAL OFFEN:** Keine unterstützte Anycubic-/kompatible Slicer-CLI wurde an PATH oder bekannten Standardpfaden gefunden. Eine GUI wird nicht als CLI angenommen.
- C:-Altbestand darf erst nach vollständigem D:-E2E-PASS als löschbar bewertet werden.

## NUTZERAKTION ERFORDERLICH

Einmalig außerhalb der Codex-Sandbox im normalen lokalen Benutzerkontext aus diesem Ergebnisbranch ausführen:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\initialize-ai3d-agent.ps1 -RegisterScheduledTask -SchedulerDiagnosticOnly
```

Nach PASS des Scheduler-Diagnoselaufs denselben Befehl ohne `-SchedulerDiagnosticOnly` ausführen und anschließend den geforderten echten Tasklauf beobachten. Erst wenn Commit, Push und Remote-HEAD übereinstimmen sowie mindestens ein Heartbeat sichtbar war, darf der Status auf PASS und der C:-Worker auf Altbestand gesetzt werden. Das Skript löscht keine C:-Daten.

## SOLL/IST

| SOLL | IST | Status |
|---|---|---|
| D:-Stammordner vorhanden | gelesen vorhanden | PASS |
| D:-Unterstruktur und Worker aktiv | Skript vorbereitet, Sandbox verhindert reale Anlage | OFFEN |
| Git/Codex erreichbar | beide erkannt | PASS |
| OpenSCAD CLI | nicht gefunden | OFFEN (optional) |
| Python/CadQuery | kein Interpreter gefunden | OFFEN (optional) |
| Mesh-/STL-Prüfweg | kein Preflight-Modul gefunden | OFFEN (optional) |
| Slicer-CLI | nicht gefunden | OFFEN (optional) |
| Maschinenlesbarer Preflight | erzeugt | PASS |
| Referenzschema | dokumentiert und Schema erzeugt | PASS |
| Ergebnisstatus | Schema und R01-Status erzeugt | PASS |
| Scheduler-Diagnose | Scheduler-Aufgabe nicht sichtbar | OFFEN |
| E2E inkl. Push/Remote | nicht ausgeführt | OFFEN |
| Heartbeat real beobachtet | implementiert, nicht real beobachtet | OFFEN |

Keine finale Nutzer- oder Produktfreigabe erteilt.
