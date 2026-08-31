# Automatischer Übergabe-Workflow R03

Ziel: Der Nutzer beschreibt ChatGPT den Druckauftrag. ChatGPT klärt nur konstruktiv relevante Unklarheiten, dokumentiert die freigegebene Spezifikation und reiht sie nach ausdrücklicher Nutzerfreigabe in eine einzige FIFO-Queue ein. Hannes/Codex arbeitet danach selbstständig im separaten Worker-Clone. Ergebnisse werden auf GitHub zurückgeführt und von ChatGPT gegen die letzte freigegebene Spezifikation geprüft.

## Verbindlicher Ablauf

1. Nutzer übermittelt Idee, Maße, Bilder, Material-/Druckvorgaben und sonstige Anforderungen.
2. ChatGPT prüft Funktion, Maße, Orientierung, Anschlussgeometrie und Referenzen. Fehlende konstruktiv relevante Angaben werden vor der Konstruktion geklärt; rein technische Details werden nicht unnötig eskaliert.
3. Vor Nutzerfreigabe darf eine Task als ENTWURF unter `tasks/` liegen, aber nicht in `tasks/TASK_QUEUE.txt` stehen.
4. Erst nach ausdrücklicher Nutzerfreigabe wird der Task-Pfad hinten an `tasks/TASK_QUEUE.txt` angefügt.
5. Der lokale Watcher liest ausschließlich die Queue und nimmt den ersten noch nicht verarbeiteten Eintrag.
6. Hannes/Codex liest `AGENTS.md` und die konkrete Task vollständig und konstruiert ausschließlich die freigegebene Anforderung.
7. Technisch notwendige Details darf Hannes selbst lösen, solange keine verbindlichen Nutzermaße, Funktionen oder die Produktidee verändert und keine neue Funktion ergänzt wird.
8. Nach erfolgreichem Lauf committet und pusht der Watcher den Worker-Stand auf einen eigenen Branch `ruediger/...` und verifiziert den Remote-SHA.
9. Erst nach erfolgreicher Remote-Verifikation wird der Task im lokalen Zustand als verarbeitet markiert.
10. Danach wird ohne manuelles Umschalten sofort der nächste unverarbeitete Queue-Eintrag bewertet.
11. ChatGPT prüft das Ergebnis gegen die letzte vom Nutzer freigegebene Spezifikation. Technische Validierung und Übereinstimmung mit der Nutzeridee werden getrennt bewertet.
12. Nur der Nutzer gibt die finale Produktfreigabe.

## Eine Queue statt zwei Steuerdateien

- `tasks/TASK_QUEUE.txt` ist die einzige ausführbare Steuerquelle.
- `tasks/CURRENT_TASK.txt` ist ab R03 nur noch eine Migrationsdatei und enthält dauerhaft `NONE`.
- Neue Aufträge werden niemals in einen aktiven Slot geschrieben, sondern immer hinten an die Queue angefügt.
- Bereits verarbeitete Einträge dürfen zur Nachvollziehbarkeit in der Queue stehen bleiben; der lokale State überspringt sie über Task-Pfad + Blob-SHA.
- Eine geänderte Task-Datei ist ein neuer Arbeitsstand und darf nur nach erneuter Nutzerfreigabe als ausführbar gelten.

## Laufzeit und Geschwindigkeit

- Standard-Polling: 30 Sekunden.
- Heartbeat bei längerem Codex-Lauf: 90 Sekunden.
- Nach erfolgreichem Task kein zusätzlicher Polling-Wartezyklus; die nächste Queue-Task wird sofort bewertet.
- Vollständiger Toolchain-Preflight wird bis zu 6 Stunden gecacht, solange der letzte Status PASS ist.
- Nach Codex-/Toolchain-Fehler wird ein vollständiger Preflight erzwungen.

## Selbstupdate

Der R03-Watcher vergleicht nach jedem erfolgreichen `fetch origin master` die produktiven Runtime-Skripte mit `origin/master`:

- `tools/ruediger-agent-watch.ps1`
- `tools/cad-toolchain-preflight.ps1`
- `tools/repair-runtime.ps1`
- `tools/restart-runtime-watcher.ps1`

Geänderte Runtime-Dateien werden nach `D:\AI3D-Agent\runtime` übernommen. Wenn der Watcher selbst geändert wurde, startet `restart-runtime-watcher.ps1` nach dem Ende der alten Instanz den bestehenden Scheduler `AI3D-Ruediger-Agent` erneut. Falls das nicht möglich ist, startet der Helper die Runtime direkt.

Ein exklusives Lockfile unter `D:\AI3D-Agent\state` verhindert parallele Doppelinstanzen.

## Automatische Fehlerbehandlung

- Git-Fetch/Push: mehrere Versuche mit kurzer Wartezeit.
- Vor dem Ergebnis-Commit prüft Hannes alle neuen und taskbezogenen Dateien gegen die Sicherheitsgrenze von 90.000.000 Byte.
- Klar temporäre/diagnostische Großartefakte werden unter `D:\3D-Models\generated\_ruediger-local-large-artifacts\<task>` gesichert, aus dem Git-Ergebnis entfernt und mit Originalpfad, lokalem Pfad, Größe, SHA-256 und Grund manifestiert.
- Verbindliche oder nicht eindeutig temporäre Großdateien werden nur nach verifizierter verlustfreier ZIP-Austauschdarstellung ersetzt. Ist keine Darstellung bis 90.000.000 Byte möglich, folgt ein technischer `STOPP`; Original und lokales Ergebnis bleiben erhalten.
- Unmittelbar vor jedem Ergebnis-Push, auch beim lokalen Recovery, prüft Hannes den Commit-Baum erneut. Bei einer Datei über 100.000.000 Byte wird kein Push gestartet.
- Fehlt ein gültiger dedizierter Worker, wird ein vorhandener ungültiger Ordner mit Zeitstempel gesichert und der Worker neu geklont.
- State-Datei wird vor Änderungen gesichert; eine unlesbare State-Datei wird nicht still überschrieben.
- Technische Fehler bleiben unverarbeitet und werden nach dem Poll-Intervall erneut versucht.
- Kein Fehler darf einen Task still als erledigt markieren.

## Live-Status

Der Watcher publiziert auf dem separaten Branch `ruediger/live-status` die Datei `RUEDIGER_STATUS.json`. Der Statusbranch ist reine Telemetrie und wird nicht in `master` gemerged.

Mögliche Phasen:
- `START`
- `TASK_GEFUNDEN`
- `ARBEITET`
- `VALIDIERT`
- `FERTIG`
- `WARTET`
- `FEHLER_RETRY`
- `PUSH_RETRY`
- `STOPP`
- `RESTARTING`
- `DIAGNOSTIC_PASS`

Damit kann ChatGPT den echten Hannes-Status direkt über GitHub prüfen, ohne aus indirekten Branch-/Commit-Signalen raten zu müssen.

## STOPP-/Entscheidungslogik

`NUTZERENTSCHEIDUNG_ERFORDERLICH` nur wenn mindestens einer dieser Fälle vorliegt:
- ein verbindliches Nutzermaß oder eine verbindliche Funktion müsste geändert werden,
- zwei verbindliche Anforderungen widersprechen sich,
- eine echte Produktentscheidung zwischen unterschiedlichen Funktionen/Formen ist nötig,
- ein erforderliches reales Maß/Referenzdatum fehlt und ist nicht eindeutig aus vorhandenen Dateien/Bildern ableitbar,
- finale Nutzerfreigabe steht an.

Reine Toolchain-, CAD-, Mesh-, Script-, Support-, Druckorientierungs- oder Berechnungsprobleme sind zunächst technische Aufgaben.

## Ergebnisstatus

Jeder neue Hannes-Auftrag soll einen kompakten maschinenlesbaren Status liefern mit mindestens:
- Task und Revision,
- `PASS`, `STOPP` oder `OFFEN`,
- Hauptausgabedateien,
- technische Validierungen,
- offene reale Tests,
- `NUTZERENTSCHEIDUNG_ERFORDERLICH: true/false` samt präzisem Grund.

Keine automatische finale Produktfreigabe und kein automatisches Merge der Produkt-Branches.

## Standard-Taskformat

Neue Tasks sollen `tasks/TASK-TEMPLATE.md` als Struktur verwenden. Verbindliche Nutzerangaben, technisch notwendige Umsetzung, Referenzen, Validierung, Freigabe-Gate und offene Nutzerentscheidungen bleiben klar getrennt.

## Notfall-Reparatur

Der manuelle Notfallweg ist ein einziger Befehl aus dem aktuellen Worker-Clone:

`powershell.exe -NoProfile -ExecutionPolicy Bypass -File D:\AI3D-Agent\worker\AI3D-Model-worker\tools\repair-runtime.ps1`

Das Skript stoppt den vorhandenen Scheduler kontrolliert, prüft/rekonstruiert bei Bedarf den dedizierten Worker, synchronisiert die Runtime, führt den Preflight aus und startet den Scheduler wieder. Es verändert keinen normalen Benutzer-Arbeitsbaum.

## Sicherheitsregeln

- Keine breiten Kill/Reset/Clean-Aktionen außerhalb des dedizierten Workers.
- Keine stillen Änderungen an bestätigter Produktgeometrie.
- Keine Konstruktion oder Druckdatei vor Nutzerfreigabe des Auftrags.
- Keine automatische finale Produktfreigabe.
- Ein neuer Nutzerentscheid bleibt dem Nutzer vorbehalten.
