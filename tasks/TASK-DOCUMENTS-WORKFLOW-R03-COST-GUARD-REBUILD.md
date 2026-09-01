# TASK-DOCUMENTS-WORKFLOW-R03-COST-GUARD-REBUILD

## Ziel
Den Documents-Ruediger-Workflow nach Sicherung des laufenden R01-Zustands sauber neu aufsetzen. Hauptziel ist nicht maximale Autonomie, sondern belastbare Produktentwicklung mit harter Kosten-/Tokenbremse: kein wiederholter Codex-Verbrauch ohne nachweisbaren Fortschritt.

## Ausgangslage
- Repo: h4rdstyle1988/Documents-Controlling-clear
- AgentRoot: D:\Documents-Controlling-Agent
- Scheduler: Documents-Ruediger-Agent
- aktueller Produktauftrag: tasks/R01_GENERIC_VALIDATION_CORE.md
- Task-Blob: 180b5973f7b5320af090cf9b96fe46e5ec755336
- Live-Status meldete wiederholt ARBEITET/attempt=1/retry_count=0 bei wechselnden Codex-PIDs.
- Seit dem Retry-Commit c1fec8699685e79a9d9426fb766eab7a1dd7002e entstand kein neuer Produkt-Commit.
- Der im Live-Status genannte Ergebnisbranch ruediger/r01-generic-validation-core-180b5973 war bei externer GitHub-Pruefung nicht vorhanden.
- Damit ist aktuell kein belastbarer Output trotz wiederholter Codex-Aktivitaet nachgewiesen.

## Prioritaet
HOCH. Nach Abschluss/Sicherung des laufenden Hannes/Manfred-Repairauftrags ausfuehren. Keine Herbst-Igel-Arbeit. Keine neue Produktentwicklung starten, bevor dieser Workflow PASS ist.

## Muss 1: Token-/Kostenverschwendung sofort verhindern
Vor dem Neuaufbau:
1. Documents-Ruediger-Agent kontrolliert stoppen, sobald der aktuelle Worker-Zustand sicher gesichert ist.
2. Dirty/uncommittete Produktarbeit stashen oder als eindeutig gekennzeichneten Recovery-Stand sichern; nichts verwerfen.
3. Keine weiteren Codex-Runs fuer R01 starten, solange R03 nicht validiert ist.
4. Vorhandene Usage-Limit-, Retry- und Loop-Zustaende dokumentieren, aber nicht durch wiederholte Test-Runs reproduzieren, wenn statische/gezielte Tests genuegen.

## Muss 2: Workflow R03 neu aufsetzen
R03 soll einfacher und deterministischer als R02 sein. Bevorzuge Neubau klarer Kernlogik gegen weiteres Patchen historischer Sonderfaelle.

Verbindliches Modell:
- genau ein Watcher
- genau ein aktiver Codex-Run pro Task
- Taskidentitaet = Pfad + Blob-SHA
- Ergebnisbranch MUSS vor Codex-Start remote oder lokal eindeutig angelegt/verifiziert werden; Live-Status darf keinen nicht existierenden Branch als aktiv ausweisen
- Statusdaten muessen reale, extern pruefbare Fakten spiegeln
- Attempts werden VOR jedem Codex-Start persistent inkrementiert
- jede neue Codex-PID = neuer Attempt
- keine versteckten Neustarts

## Muss 3: Harte Fortschrittsbremse
Ein Codex-Run gilt nur dann als produktiv, wenn mindestens eines nachweisbar entsteht:
A) relevanter Working-Tree-Diff gegen Startzustand,
B) neuer verifizierter Checkpoint-Commit,
C) messbarer Test-/Validierungsfortschritt mit gespeichertem Ergebnis,
D) klarer technischer BLOCKER mit reproduzierbarer Evidenz.

Wenn nach einem Run keines von A-D vorliegt:
- Status = NO_PROGRESS_BLOCKED
- KEIN automatischer erneuter Codex-Start fuer denselben Task-Blob
- der Zustand wird persistent gespeichert
- erst neue Task-Revision, expliziter Repair oder nachweislich neuer externer Zustand darf entsperren

Kein Exit-Code-0 darf allein als Fortschritt gelten.

## Muss 4: Begrenztes Arbeitsfenster
Implementiere eine harte Laufzeit-/Inaktivitaetsgrenze, damit ein haengender oder kreisender Codex-Prozess nicht unbegrenzt Budget verbraucht.
- Waehle einen konservativen Standardwert auf Basis bisheriger realer Documents-Aufgaben; dokumentiere ihn.
- Heartbeat allein verlaengert das Budget nicht.
- Wenn waehrend des Fensters kein Dateidiff, Testartefakt, Checkpoint oder klarer Fortschritt sichtbar wird: Prozess kontrolliert beenden, Zustand sichern, NO_PROGRESS_BLOCKED.
- Keine hochfrequenten Polls oder Token-basierte Selbstgespraeche als Ersatz fuer Output.

## Muss 5: Retry-Regeln
Automatische Retries nur fuer klar temporaere Infrastrukturfehler, z. B. Netzwerk/Fetch/Push oder API/Usage-Limit, und nur wenn ein spaeterer Versuch sachlich Sinn ergibt.
- Usage-/Quota-Limit verbraucht kein Software-Fehlerbudget.
- Retry mit langer, begrenzter Wartezeit; keine schnellen Wiederholungen.
- Codex-/Taskfehler: max. 1 automatischer Wiederholungsversuch ohne neuen Checkpoint, nicht 3.
- NO_PROGRESS: 0 automatische Wiederholungen.
- Post-Validation-Fehler ohne neuen Output: 0 automatische Wiederholungen.

## Muss 6: Task kleiner schneiden
R01_GENERIC_VALIDATION_CORE ist vor Wiederaufnahme auf Arbeitsgroesse pruefen. Falls zu breit fuer einen effizienten Codex-Lauf:
- in wenige eigenstaendige, wertliefernde Teilaufgaben schneiden
- jede Teilaufgabe mit eindeutigem Deliverable, Test und Abschlusskriterium
- keine Mikro-Tasks
- keine erneute Markt-/Konzeptanalyse, wenn bereits vorhanden
- vorhandene Artefakte wiederverwenden statt neu erfinden

Ziel: Codex soll konkrete Dateien bauen/testen, nicht lange ueber das Gesamtprojekt nachdenken.

## Muss 7: Prompt-Kosten reduzieren
R03-Prompt minimal halten:
- nur aktuelle Taskdatei
- AGENTS/Produktregeln nur soweit fuer die Aufgabe noetig
- keine komplette Historie in jeden Run injizieren
- keine langen wiederholten Status-/Recovery-Erklaerungen
- keine erneute Analyse bereits verifizierter Grundlagen
- Codex zuerst Repository/Task lesen lassen und dann handeln

Dokumentiere welche Promptteile entfernt/verdichtet wurden.

## Muss 8: MANFRED-Rolle
MANFRED bleibt Betriebs-Supervisor:
- erkennt fehlenden/duplizierten Watcher
- erkennt NO_PROGRESS_BLOCKED und laesst ihn blockiert
- fuehrt nur whitelisted Maintenance/Repair aus
- startet NO_PROGRESS niemals eigenmaechtig neu
- kann nach versioniertem Repair den Scheduler kontrolliert neu starten
- keine allgemeine Remote-Shell

## Muss 9: Tests ohne Tokenverschwendung
R03 zuerst mit deterministischen lokalen Tests pruefen, nicht mit echten langen Codex-Runs.
Mindestens testen:
1. Taskauswahl korrekt.
2. Branch wird real angelegt/verifiziert.
3. Attempt vor Start persistent.
4. Simulierter Exit 0 ohne Diff -> NO_PROGRESS_BLOCKED, kein Restart.
5. Simulierter Diff -> Validierungspfad.
6. Simulierter Usage-Limit -> WAIT_LIMIT, kein Fehlerbudget.
7. Simulierter echter Codex-Fehler -> hoechstens 1 Retry.
8. Post-Validation-Fehler ohne neuen Output -> BLOCKIERT, kein Loop.
9. Doppelte Watcher -> Manfred bereinigt auf genau einen.
10. Statusbranch-Dateiname exakt RUEDIGER_STATUS.json ohne CR/Steuerzeichen.

Erst wenn diese Tests PASS sind, genau EIN kurzer kontrollierter Smoke-Run mit Codex.

## Muss 10: Wiederaufnahme R01
R01 erst wieder aufnehmen wenn:
- R03 statische/deterministische Tests PASS
- genau ein Watcher
- real existierender Taskbranch
- Smoke-Run erzeugt messbaren Output oder klaren Blocker
- keine versteckten Restarts

Falls R01 zu gross ist, zuerst Teilaufgabe 1 starten. Nach deren PASS naechste Teilaufgabe.

## Ergebnisbericht
Erzeuge reports/DOCUMENTS-WORKFLOW-R03-COST-GUARD-REPORT.md mit:
- Ursache des bisherigen Token-/No-Output-Problems
- was aus R02 entfernt/ersetzt wurde
- Fortschrittskriterien
- Retry-/Timeout-Regeln
- Promptreduktion
- Testmatrix + Ergebnisse
- Status von Manfred
- Status des gesicherten R01-Workers
- Freigabe: PASS oder BLOCKED

## Abschlusskriterium
PASS nur wenn nachgewiesen ist: Ein Documents-Task kann nicht mehr automatisch wiederholt Codex starten, ohne messbaren Fortschritt zu erzeugen. Danach R01 kontrolliert weiterfuehren.
