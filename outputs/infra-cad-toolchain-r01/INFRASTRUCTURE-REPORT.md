# Infrastrukturbericht – CAD-Toolchain R01

Revision: R01  
Task: `tasks/TASK-INFRA-CAD-TOOLCHAIN-R01.md`  
Status: PASS mit optionalen Werkzeugen OFFEN; keine Produktfreigabe

## GEÄNDERT

- Reproduzierbarer Preflight `tools/cad-toolchain-preflight.ps1`, maschinenlesbare Ausgabe in `%LOCALAPPDATA%\AI3D-Model\toolchain-preflight.json`.
- Bestehender Watcher gezielt um Preflight und 90-s-Heartbeat (`ARBEITET`/`FERTIG`/`FEHLER`) ergänzt.
- Referenzschema samt Manifestmechanismus unter `references/` ergänzt.
- Ergebnisstatus-Schema und Beispiel unter `tasks/` ergänzt; Workflow dokumentiert.

## UNVERÄNDERT

- Sämtliche Produktgeometrien, Nutzermaße, CAD-, STL- und bestehende Revisionsdateien.
- Separater Worker, Remote-Verifikation, kein automatischer Merge und keine automatische Produktfreigabe.

## INSTALLIERT / BEREITS VORHANDEN

- Bereits vorhanden: Git CLI, Codex CLI, PowerShell.
- Nicht installiert: OpenSCAD CLI, nutzbarer Python-Interpreter/CadQuery, unterstützte Slicer-CLI.
- Es wurde keine Systeminstallation erzwungen. `py.exe` ist vorhanden, meldet jedoch „No installed Pythons found“.

## VALIDIERT

- Siehe `validation.json` und `toolchain-preflight.json` in diesem Ordner.
- PowerShell-Parserprüfung, Preflight-Wiederholung, JSON-Lesbarkeit und DiagnosticOnly-Start wurden lokal geprüft.
- Fehlende optionale Werkzeuge werden OFFEN gemeldet; Git/Codex bleiben die einzigen pauschal blockierenden Preflight-Komponenten.

## OFFEN

- OpenSCAD-Smoke-Test mangels Installation nicht ausführbar.
- CadQuery-Import/-Export-Smoke-Test mangels Python-Interpreter nicht ausführbar.
- Meshprüfung ist ohne OpenSCAD/Python-Modul lokal nicht verfügbar.
- Keine nachweislich unterstützte Anycubic-/Orca-/Prusa-Slicer-CLI gefunden; eine GUI wird nicht als CLI angenommen.
- Ein vollständiger 90-s-Heartbeat mit realem Codex-Arbeitsprozess wurde aus diesem laufenden Codex-Auftrag nicht rekursiv gestartet; Prozesslogik und kurzer Harness-Test sind in `validation.json` dokumentiert.

## NUTZERAKTION ERFORDERLICH

Keine für diesen Infrastrukturauftrag. Für künftige Tasks, die zwingend OpenSCAD oder CadQuery verlangen, ist eine bewusst freigegebene Installation aus offizieller Quelle erforderlich; dieser optionale Ausbau blockiert den aktuellen Workflow nicht.

