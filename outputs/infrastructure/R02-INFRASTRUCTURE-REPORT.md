# Infrastrukturbericht R02

Task: `tasks/TASK-INFRA-CAD-TOOLCHAIN-R02.md`  
Revision: R02  
Gesamtstatus: **OFFEN**

Der Repo-Stand ist implementiert und lokal soweit möglich geprüft. Der verbindliche Live-Nachweis „R02 remote verifiziert, danach Queue-Würfel ohne manuelles Umschalten“ kann logisch erst nach Commit/Push dieses Ergebnisbranches durch den außerhalb des Workers laufenden Watcher erfolgen. Er wird nicht vorweggenommen. Das ist ein technischer offener Test, keine Nutzerentscheidung und keine finale Produktfreigabe.

## GEÄNDERT

- Repo-Watcher auf stabilen Stamm `D:\AI3D-Agent`, Runtime außerhalb des mutablen Workers, 90-s-Heartbeat und PowerShell-5.1-kompatible UTF-8-Promptdatei mit `cmd.exe`-stdin-Umleitung gebracht.
- Kein `Start-Job`, keine `StandardInputEncoding`-Eigenschaft.
- Robuster JSON-Zustand Schema 2: mehrere verifizierte `processed`-Einträge plus separate `failures`; Identität Task-Pfad + Blob-SHA.
- Auswahl: unverarbeiteter aktiver Auftrag zuerst, danach erster unverarbeiteter Queue-Eintrag in FIFO-Reihenfolge. Fehler markieren keinen Erfolg und verändern die Queue-Datei nicht.
- Erfolg wird erst nach Push und Gleichheit von lokalem und Remote-Commit gespeichert.
- Maschinenlesbarer Preflight, Referenzmanifest-Schema und Ergebnisstatus-Schema ergänzt.
- Reproduzierbare Runtime-Installation mit Sicherung der vorherigen Skripte ergänzt (`tools/install-runtime-watcher.ps1`).

## UNVERÄNDERT

- `tasks/CURRENT_TASK.txt` bleibt aktiver Auftrag; `tasks/TASK_QUEUE.txt` bleibt die freigegebene FIFO-Queue.
- Produktdateien und bestehende Produktgeometrie wurden nicht geändert.
- Kein automatisches Merge und keine finale Produktfreigabe.
- C:-Altbestand wurde weder verändert noch gelöscht. Mangels vollständigem Abhängigkeitsnachweis wird er nicht als sicher löschbar bezeichnet.

## INSTALLIERT / BEREITS VORHANDEN

- Git und Codex sind vorhanden und erreichbar.
- Reale D:-Struktur mit `runtime`, `worker`, `state`, `logs`, `outputs`, `cache`, `temp`, `toolchain` ist vorhanden.
- Keine globale Installation und kein riskanter Download durchgeführt.
- OpenSCAD CLI wurde in PATH und typischen Installationspfaden nicht gefunden.
- Ein lokaler Python-3.12-Pfad wurde vom außerhalb der Sandbox gelaufenen Runtime-Preflight erkannt; CadQuery war dort nicht importierbar. Der aktuelle eingeschränkte Worker durfte den C:-Interpreter nicht lesen und hat deshalb keine isolierte Umgebung installiert.
- Keine nachgewiesene Slicer-CLI gefunden; eine GUI wird nicht als CLI gewertet.

## VALIDIERT

- Historischer realer D:-E2E-PASS laut Runtime-Log: Fetch → Task → Codex → Commit → Push → Remote-Verifikation, Branch `ruediger/task-infra-e2e-smoke-r01-26960c0e`, Remote-Commit `11a32a0d0edb27658ce10f7544e4c64a9f383e94` am 2026-08-29.
- UTF-8-stdin-Weg war bei diesem realen Lauf erfolgreich; frühere `StandardInputEncoding`-Fehler sind damit überholt.
- Beide PowerShell-Skripte parsen ohne Fehler unter Windows PowerShell.
- Preflight Schema 2 lief mit fehlenden optionalen Tools bis `PASS` durch; Nachweis `R02-toolchain-preflight.json`.
- Auswahltest 1: ohne Erfolgszustand wurde R02 aus `CURRENT_TASK` gewählt.
- Auswahltest 2: nach simuliertem, verifiziertem R02-Schlüssel wurde der Würfel aus `TASK_QUEUE` gewählt, ohne `CURRENT_TASK` zu ändern.
- Heartbeat bleibt mit Standardwert 90 s im geforderten Bereich 60–120 s.
- Freigabe-Gate ist in `AGENTS.md`/`tasks/WORKFLOW.md` verbindlich; der Watcher führt ausschließlich aktive oder queued Tasks aus.

## OFFEN

- OpenSCAD-Smoke-Test: Tool nicht vorhanden.
- CadQuery-Import/Export-Smoke-Test: Modul nicht vorhanden bzw. Interpreter aus aktueller Sandbox nicht zugänglich.
- Slicer-CLI-Test: keine geeignete CLI nachgewiesen.
- Finaler Live-Abnahmetest dieses neuen Repo-Watchers: R02-Push/Remote-Verifikation und anschließend automatischer Würfel-Lauf einschließlich CAD/STL/Validierung/Push/Remote-Verifikation. Bis dahin bleibt Infrastrukturstatus OFFEN.
- Reale Druck-/Passformtests bleiben grundsätzlich Nutzer-/Realwelttests.

## NUTZERAKTION

Einmalig unvermeidbar, weil der aktuelle Codex-Sandboxlauf außerhalb des Worker-Roots nicht nach `D:\AI3D-Agent\runtime` schreiben und den bereits laufenden Scheduler-Prozess nicht kontrolliert ersetzen darf:

1. Nach Übernahme dieses Ergebnisstands aus dem Repo ausführen: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools\install-runtime-watcher.ps1`.
2. Den vorhandenen Watcher über seine bestehende Scheduler-Konfiguration kontrolliert neu starten.
3. Den Live-Nachweis R02-Remote-Verifikation → automatischer Queue-Würfel abwarten und anhand von State/Log/Remote-SHA prüfen.

Optionale OpenSCAD-/CadQuery-/Slicer-Installationen sind keine Voraussetzung für die Repo-Implementierung und werden nicht erzwungen.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false` – alle offenen Punkte sind technische Tool-/Live-Validierungen. Finale Produktfreigaben bleiben ausschließlich beim Nutzer.
