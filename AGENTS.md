# AI3D-Model – Agenten-Arbeitsregeln

Dieses Repository steuert die Übergabe zwischen ChatGPT (Spezifikation/Prüfung) und Codex/Rüdiger (Konstruktion/Ausführung).

## Priorität
1. aktuelle Nutzerangabe
2. zuletzt bestätigte Spezifikation / freigegebene Task-Datei
3. reale Datei, Messung oder CAD-Geometrie
4. technische Berechnung
5. frühere KI-Aussage

## Freigabe-Gate
Vor ausdrücklicher Nutzerfreigabe darf keine Konstruktion gestartet und keine Druckdatei erzeugt werden. Entwürfe dürfen unter `tasks/` dokumentiert werden, aber nicht in `tasks/TASK_QUEUE.txt` stehen.

Nach ausdrücklicher Nutzerfreigabe wird der konkrete Task-Pfad in `tasks/TASK_QUEUE.txt` eingereiht. Die Queue ist die einzige ausführbare Steuerquelle und wird FIFO abgearbeitet.

`tasks/CURRENT_TASK.txt` ist ab R03 nur noch eine Migrationsdatei und muss `NONE` enthalten. Der Watcher wertet sie nicht mehr aus.

## Queue und Task-Identität
- `tasks/TASK_QUEUE.txt` enthält null oder mehr freigegebene Task-Pfade, ein Pfad pro Zeile, FIFO-Reihenfolge.
- Ein laufender Auftrag wird nie durch einen neuen Auftrag überschrieben; neue Freigaben werden hinten angefügt.
- Ein verarbeiteter Task wird mindestens über Task-Pfad + Blob-SHA identifiziert. Eine geänderte Task-Version ist ein neuer Arbeitsstand und darf nur nach erneuter Nutzerfreigabe verändert/erneut eingereiht werden.
- Fehler markieren einen Task nicht als erledigt. Technische Fehler werden automatisch erneut versucht, soweit sinnvoll.

Vor jeder Konstruktion:
- konkrete Task vollständig lesen,
- VERBINDLICH / TECHNISCH NOTWENDIG / OFFEN unterscheiden,
- vorhandene Referenzen und Maße prüfen,
- bei fehlenden konstruktiv relevanten realen Angaben nicht raten.

## Technische Eigenständigkeit
Rüdiger löst technische Details selbstständig, wenn sie zur Umsetzung der freigegebenen Funktion notwendig sind und dadurch keine verbindlichen Nutzermaße, Funktionen oder die Produktidee verändert werden.

Keine zusätzlichen Funktionen, Halterungen, Rastungen, Sockel, Anschläge, Führungen oder sonstigen Nutzungsmöglichkeiten erfinden.

Reine CAD-, Mesh-, Script-, Toolchain-, Support-, Druckorientierungs- oder Berechnungsprobleme sind technische Aufgaben und keine Nutzerentscheidung.

`NUTZERENTSCHEIDUNG_ERFORDERLICH` nur wenn:
- ein verbindliches Maß/eine verbindliche Funktion geändert werden müsste,
- verbindliche Anforderungen widersprüchlich sind,
- unterschiedliche Produktfunktionen/Formen zur Wahl stehen,
- ein erforderliches reales Maß/Referenzdatum fehlt und nicht eindeutig ableitbar ist,
- finale Nutzerfreigabe erforderlich ist.

## Schutz bestehender Arbeit
Automatisierte Arbeit erfolgt ausschließlich im dedizierten Worker-Clone unter `D:\AI3D-Agent\worker`. Der normale Benutzer-Arbeitsbaum darf niemals automatisch per `reset`, `clean`, `restore` oder ungezieltem `pull` verändert werden.

## Runtime und Selbstheilung
- Produktive Runtime: `D:\AI3D-Agent\runtime`.
- Der R03-Watcher synchronisiert seine Runtime selbst aus `origin/master` und startet sich bei einer neuen Watcher-Version kontrolliert neu.
- Git-Fetch und Push werden bei temporären Fehlern automatisch wiederholt.
- Ein ungültiger dedizierter Worker darf gesichert und neu geklont werden; vorhandene Sicherungen werden nicht still gelöscht.
- Der vollständige Toolchain-Preflight wird gecacht und nur periodisch bzw. nach Fehler erneut erzwungen.
- `tools/repair-runtime.ps1` ist der manuelle Notfallweg für Scheduler/Worker/Runtime/Preflight.

## Live-Status
Der Watcher publiziert seinen Laufstatus auf dem separaten Branch `ruediger/live-status` in `RUEDIGER_STATUS.json`. Dieser Branch ist reine Telemetrie und wird nicht in `master` gemerged.

Phasen: `START`, `TASK_GEFUNDEN`, `ARBEITET`, `VALIDIERT`, `FERTIG`, `WARTET`, `FEHLER_RETRY`, `RESTARTING`, `DIAGNOSTIC_PASS`.

## Ergebnis
Für jeden Auftrag nur taskbezogene Dateien ändern. Keine stillen Nebenänderungen. Ergebnis mit SOLL/IST-Prüfung, Revisionsangaben, technischen Validierungen und offenen Punkten dokumentieren.

Jeder Ergebnisstand soll maschinenlesbar enthalten:
- Task/Revision,
- PASS/STOPP/OFFEN,
- Hauptdateien,
- Validierungen,
- offene reale Tests,
- `NUTZERENTSCHEIDUNG_ERFORDERLICH: true/false` mit Grund.

Ein erfolgreicher STL-Export, ein watertight Mesh oder ein Validator-PASS ist keine finale Produktfreigabe. Finale Produktfreigabe erfolgt ausschließlich durch den Nutzer.
