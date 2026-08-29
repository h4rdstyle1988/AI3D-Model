# Infrastrukturbericht – CAD-/Rüdiger-Toolchain R01

Revision: R01  
Status: **OFFEN** (Repository-Umsetzung erfolgt; lokale D:-Migration, Scheduler- und Installationsschritte konnten im eingeschränkten Worker nicht ausgeführt werden.)  
Keine Produktgeometrie wurde geändert. Keine finale Produktfreigabe.

## GEÄNDERT

- Watcher-Standardpfade auf `D:\AI3D-Agent` umgestellt: `worker/AI3D-Model`, `outputs`, `logs`, `cache`, `temp`, `state`, `toolchains`.
- Toolchain-Preflight vor Diagnose und Codex-Lauf integriert; JSON unter `D:\AI3D-Agent\state\toolchain-preflight.json`.
- Codex-Lauf mit 90-Sekunden-Heartbeat (`ARBEITET`) versehen; `FERTIG` bleibt explizit.
- Referenzschema unter `references/<projekt>/` und Manifestvalidator ergänzt.
- Maschinenlesbares Ergebnisstatus-Schema ergänzt.
- Reproduzierbarer, standardmäßig nur anzeigender Setup-Weg für OpenSCAD, Python 3.11 und isoliertes CadQuery-venv vorbereitet.

## UNVERÄNDERT

- Bettklammer-/Nubsi- und sonstige Produktgeometrie, Nutzermaße und bestehende Revisionen.
- GitHub-Remote und Branch-/Push-/Remote-Verifikationsablauf.
- Der vorhandene C:-Worker wurde weder verschoben noch gelöscht.

## INSTALLIERT / BEREITS VORHANDEN

- Bereits vorhanden: Git 2.55.0, Codex CLI, Anycubic Slicer Next 1.4.1.2 unter `D:\Program Files\AnycubicSlicerNext\AnycubicSlicerNext.exe`.
- Nicht installiert/auffindbar: OpenSCAD, Python-Laufzeit, CadQuery und winget.
- Keine Installation erzwungen. `tools/setup-cad-toolchains.ps1` nutzt bei ausdrücklichem `-Execute` ausschließlich winget und eine isolierte Umgebung unter D:.

## VALIDIERT

- PowerShell-Parser: Watcher-Syntax PASS.
- Preflight im aktuellen Worker: PASS für erforderliche Werkzeuge Git/Codex; Ergebnis `toolchain-preflight.json`.
- Anycubic-Installation wurde über die Windows-Registrierung bzw. den registrierten Programmpfad nachgewiesen. Eine unterstützte CLI wurde nicht behauptet oder durch Start der GUI erzwungen.
- Git-Remote bleibt `https://github.com/h4rdstyle1988/AI3D-Model.git`.

## OFFEN

- **STOPP lokal:** Schreiben/Anlegen unter `D:\AI3D-Agent` liegt außerhalb der freigegebenen Worker-Sandbox. D:-Worker, Fetch, Task-Erkennung, Codex-Lauf, Commit und Push konnten deshalb hier nicht Ende-zu-Ende ausgeführt werden.
- Scheduler-Konfiguration war im aktuellen Kontext nicht als passende Aufgabe auffindbar; tatsächlichen Startbefehl lokal prüfen.
- OpenSCAD-CLI-Smoke-Test und CadQuery-Import-/STL-Export-Smoke-Test sind mangels Installation offen.
- Anycubic Slicer Next: GUI vorhanden, unterstützte CLI-Schnittstelle offen. Vorhandene ältere Ausgabe-Artefakte belegen frühere Automatisierung, ersetzen aber keine aktuelle Hersteller-CLI-Zusage.
- Heartbeat ist statisch und syntaktisch geprüft, aber noch nicht mit einem echten Langläufer im Scheduler-Kontext validiert.
- Alte C:-Ordner sind erst nach erfolgreichem D:-Ende-zu-Ende-Lauf löschbar. Kandidat: `C:\Users\h4rds\Documents\ChatGPT\AI3D Model-worker`; nicht automatisch löschen.

## NUTZERAKTION ERFORDERLICH

1. Winget/App Installer über den von Microsoft unterstützten lokalen Weg bereitstellen; im aktuellen Kontext ist `winget.exe` nicht auffindbar. Danach aus einem normalen Benutzer-PowerShell-Kontext im Repository ausführen: `powershell -NoProfile -ExecutionPolicy Bypass -File tools/setup-cad-toolchains.ps1 -Execute` (winget kann Rückfragen oder Richtlinien des Systems melden).
2. Danach CadQuery testen: `D:\AI3D-Agent\toolchains\cadquery-venv\Scripts\python.exe tools\cadquery-smoke.py` und OpenSCAD mit `openscad --version` prüfen.
3. Scheduler-Aktion auf dieses Watcher-Skript ohne alten C:-`-WorkerDir` setzen und einmal mit `-DiagnosticOnly` starten.
4. Einen echten Task-Durchlauf einschließlich Remote-Verifikation abwarten. Erst danach den C:-Worker als Altbestand kennzeichnen; Löschung ausschließlich durch den Nutzer.
