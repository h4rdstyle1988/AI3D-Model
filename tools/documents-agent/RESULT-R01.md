# Ergebnis – Documents Agent Bootstrap R01

## Status

`PASS` – die getrennte Documents-Agent-Infrastruktur ist als gepruefter,
nicht automatisch aktivierter Bootstrap erstellt.

- Task: `tasks/TASK-DOCUMENTS-AGENT-BOOTSTRAP-R01.md`
- Revision: `R01`
- Task-Blob: `f9590d7504d32dad0314c3d0a4fefee2c6b658e8`
- Gewaehlte Variante: B, separater Documents-spezifischer Watcher
- `NUTZERENTSCHEIDUNG_ERFORDERLICH: false`
- Finale Nutzerfreigabe: nicht behauptet

## SOLL/IST

| SOLL | IST |
|---|---|
| Bestehenden 3D-Agenten nicht umkonfigurieren | PASS – keine bestehende AI3D-Runtime-Datei geaendert |
| Eigenes Repo und `main` | PASS – explizites Documents-Repo und `main` im Profil und Watcher |
| Eigene Root-/Worker-/Runtime-/Lock-/State-/Log-Pfade | PASS – alles unter `D:\Documents-Controlling-Agent` |
| Eigener Scheduler | PASS – `Documents-Ruediger-Agent` |
| FIFO und Task-Pfad + Blob-SHA | PASS – implementiert und statisch/unit-getestet |
| Codex, Ergebnisbranch, Remote-Verifikation, Retry/Recovery | PASS – implementiert |
| Separater Live-Status | PASS – parametrisierter Branch `ruediger/live-status` im Documents-Remote |
| Kein CAD-Preflight | PASS – nur generischer Entwicklungs-Preflight |
| Kein normaler Benutzer-Arbeitsbaum | PASS – destruktive Git-Befehle sind auf den geprueften dedizierten Worker begrenzt |
| Nicht automatisch installieren/starten | PASS – Installer und Scheduler wurden in diesem Task nicht ausgefuehrt |

CAD-, STL-, Mesh- und Druckdateien sind fuer diesen reinen Infrastrukturauftrag
nicht anwendbar und wurden nicht erzeugt oder veraendert.

## Validierungen

- PowerShell-Parser: PASS fuer 6 von 6 neuen Skripten.
- Generischer Entwicklungs-Preflight: PASS fuer PowerShell, Git, Codex,
  Code-Mode-Host und Git-Identitaet; Python vorhanden, aber nicht erforderlich.
- Statische Documents-Isolation: PASS; keine AI3D-, CAD-, Slicer- oder
  3D-Ausgabepfade in Profil und operativen Documents-Skripten.
- Statische AI3D-Rueckwaertskompatibilitaet: PASS; bestehende Defaults bleiben
  `D:\AI3D-Agent`, `AI3D-Ruediger-Agent`, AI3D-Repo/`master` und CAD-Preflight.
- FIFO-/Pfad+Blob-Unit-Test: PASS.
- `git diff --check`: PASS.
- Zielrepo-Queue-Auswahl: OFFEN. Der read-only Versuch gegen GitHub scheiterte
  am gesperrten Sandbox-Netzwerkproxy. Es wurde kein Queue-Task ausgefuehrt.

Details stehen in `development-preflight-report.json`, `validation-report.json`
und `result-status.json`.

## Einmalige Aktivierung

Aus dem Repository-Root in einer als Administrator gestarteten PowerShell auf
der interaktiven Windows-Maschine:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\tools\documents-agent\install-documents-agent.ps1" -StartAfterInstall
```

Danach bleiben als reale Tests die reine Queue-Auswahl mit `-SelectionTestOnly`,
der Scheduler-Status und die Status-Branch-Publikation im Documents-Repository
offen. Diese Betriebspruefungen sind keine offene Produkt- oder Designentscheidung.
