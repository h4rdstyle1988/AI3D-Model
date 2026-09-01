# TASK-DOCUMENTS-SOFTWARE-WORKFLOW-R02

## Ziel
Den bereits getrennten Documents-Agenten gezielt von einem artefaktorientierten 3D-Workflow zu einem robusten Software-Development-Workflow weiterentwickeln, ohne den laufenden Documents-Auftrag zu unterbrechen und ohne den bestehenden AI3D-Agenten funktional zu veraendern.

## Prioritaet
Infrastruktur-/Workflow-Optimierung fuer `Documents-Controlling-clear`.

## BINDING

1. Der laufende Documents-Auftrag darf durch diese Aufgabe NICHT gestoppt, resettet, bereinigt, repariert oder anderweitig beeinflusst werden.
2. Diese Aufgabe aendert nur die Quell-/Bootstrap-Infrastruktur unter `tools/documents-agent/` im Repository `AI3D-Model` sowie dazugehoerige Tests/Dokumentation.
3. Keine Aenderung an der produktiven AI3D-Watcher-Semantik, CAD-Preflights oder 3D-Tasks.
4. Der Documents-Agent bleibt vollstaendig getrennt:
   - Repo: `h4rdstyle1988/Documents-Controlling-clear`
   - Base: `main`
   - AgentRoot: `D:\Documents-Controlling-Agent`
   - Worker: nur unter diesem AgentRoot
   - Scheduler: `Documents-Ruediger-Agent`
5. Keine Cloud-/AI-Funktion in das Produkt selbst einbauen. Hier geht es nur um den Entwicklungsagenten.
6. Keine GPL-/AGPL-Runtime-Abhaengigkeit hinzufuegen.
7. Keine Arbeitgeberdaten, privaten Quelldateien oder employer-spezifischen Artefakte verwenden.

## Hauptproblem
Der aktuelle Documents-Watcher behandelt einen Software-Task noch weitgehend wie ein geschlossenes 3D-Artefakt. Bei einem Codex-Fehler kann ein kompletter Task erneut von `origin/main` beginnen. Fuer groessere Software-Aufgaben ist das unnoetig teuer und kann bereits geleistete Arbeit verwerfen.

## Muss-Ziele

### A. Checkpoint-/Resume-Modell
Implementiere ein robustes Checkpoint-Modell fuer laufende Software-Aufgaben:

- Ein Task-Branch darf waehrend der Bearbeitung mehrere lokale/remote Zwischen-Commits enthalten.
- Checkpoints muessen eindeutig demselben Task-Pfad + Task-Blob zugeordnet sein.
- Nach einem Codex-/Prozessfehler soll der naechste Versuch am letzten verifizierten Checkpoint fortsetzen, nicht pauschal wieder bei `origin/main` beginnen.
- Ein fremder, inkonsistenter oder nicht eindeutig zuordenbarer Branch darf niemals still als Checkpoint uebernommen werden.
- Remote-Checkpoint bevorzugen, wenn lokal/remote auseinanderlaufen und der lokale Zustand nicht beweisbar sicher ist.
- Kein `reset --hard origin/main` auf einen nachweislich gueltigen Task-Checkpoint.

### B. Begrenzte automatische Zerlegung
Der Codex-Prompt soll Software-Aufgaben anweisen:

- groessere Aufgaben intern in wenige logisch abgeschlossene Schritte zu zerlegen,
- nach einem nachweislich bestandenen Teilabschnitt einen Checkpoint-Commit zu erzeugen,
- keine Mikro-Commits nach jeder Kleinigkeit zu erzeugen,
- vor einem Checkpoint relevante zielgerichtete Tests auszufuehren,
- vor dem finalen Ergebnis einen vollstaendigen relevanten Testlauf auszufuehren.

Keine starre fachliche Zerlegung des konkreten R01 implementieren; das Verhalten muss generisch fuer spaetere Software-Tasks funktionieren.

### C. Retry-Budget / Anti-Endlosschleife
Verhindere Optimierungs- und Retry-Endlosschleifen:

- maximal 3 aufeinanderfolgende Codex-Ausfuehrungsfehler fuer denselben Task-Blob ohne neuen verifizierten Checkpoint,
- danach Status `BLOCKIERT` oder klar aequivalenter STOP-Status publizieren und nicht endlos weiterrechnen,
- sobald ein neuer verifizierter Checkpoint entsteht, darf das Fehlerbudget sinnvoll zurueckgesetzt werden,
- Infrastruktur-/Fetch-Fehler duerfen separat behandelt werden, aber ebenfalls kein unendliches schnelles Retry erzeugen.

### D. Optimierungsbremse
Dokumentiere und implementiere soweit sinnvoll folgende Regel fuer den Entwicklungsagenten:

> Optimieren nur bei messbarem Problem, wiederholtem Fehler oder klarer Zeit-/Robustheitsverbesserung. Keine Refactor-Schleifen ohne konkreten Nutzen. Nach PASS wird der funktionierende Workflow eingefroren; erneute Aenderung nur bei nachgewiesenem Problem, notwendiger Schnittstellenaenderung, Sicherheits-/Lizenzthema oder klar belegtem Nutzen.

Der Agent soll nicht selbststaendig nach jedem erfolgreichen Task seine eigene Infrastruktur refactoren.

### E. Status/Audit
Live-Status um nuetzliche, knappe Angaben erweitern, soweit ohne Bruch moeglich:

- attempt / retry count,
- letzter verifizierter Checkpoint-SHA,
- optional Checkpoint-Nummer,
- Phase klar unterscheidbar: ARBEITET / CHECKPOINT / VALIDIERUNG / FERTIG / FEHLER_RETRY / BLOCKIERT / WARTET.

Keine Status-Flut. Heartbeat weiterhin sinnvoll, aber keine zusaetzlichen Git-Commits nur wegen kosmetischer Details.

### F. Worker-Sicherheit
Beibehalten oder verbessern:

- niemals normalen Benutzer-Working-Tree resetten/cleanen,
- destruktive Git-Befehle nur im dedizierten Documents-Worker nach Pfad- und Origin-Pruefung,
- bei Repair laufende Arbeit nicht vernichten,
- bereits remote gesicherte Checkpoints erkennen und respektieren.

## Soll-Optimierungen, nur wenn klar sinnvoll

1. Sparse-Checkout nur verwenden, wenn er nachweislich einen Vorteil bringt und keinen Resume-/Testpfad verkompliziert. Sonst vereinfachen oder entfernen.
2. Status-Push-Mechanik vereinfachen, falls sie unnoetige Komplexitaet erzeugt, ohne Sichtbarkeit zu verlieren.
3. Tests gezielt zuerst, vollstaendig vor finalem Push; keine unnoetigen Volltests nach jedem kleinen Schritt.
4. Prompt kuerzen/strukturieren, wenn das Verhalten dadurch klarer wird.

## Nicht tun

- laufenden Documents-R01 anfassen,
- den aktuellen lokalen Documents-Scheduler neu starten,
- automatische Installation/Repair auf dem Nutzer-PC aus dieser Task heraus,
- AI3D-Igel wieder aufnehmen,
- GUI bauen,
- Produktfeatures in `Documents-Controlling-clear` implementieren,
- Infrastruktur komplett neu schreiben, wenn eine kleine belastbare Aenderung reicht,
- Perfektionismus-/Refactor-Schleifen.

## Tests
Mindestens synthetisch/statisch pruefen:

1. Erstlauf ohne Checkpoint startet von `origin/main`.
2. Gueltiger Checkpoint desselben Task-Pfad+Blob wird nach simuliertem Codex-Fehler wiederaufgenommen.
3. Fremder Task-Blob wird NICHT wiederaufgenommen.
4. Dirty/unverifizierter Zustand wird nicht still als sicher akzeptiert.
5. Drei Codex-Fehler ohne neuen Checkpoint fuehren zu BLOCKIERT statt Endlos-Retry.
6. Neuer verifizierter Checkpoint setzt/entschaerft Retry-Budget korrekt.
7. Finaler Ergebnis-Push bleibt remote SHA-verifiziert.
8. Existing AI3D defaults/paths/behavior remain unchanged.
9. Documents-Agent defaults bleiben getrennt und ohne CAD-Preflight.
10. PowerShell-Parser fuer alle geaenderten Skripte PASS.

## Ergebnisartefakte
Unter `tools/documents-agent/` aktualisieren/erzeugen:

- geaenderte Runtime-/Watcher-Skripte,
- Tests,
- README/Architekturhinweise,
- `RESULT-R02.md`,
- `result-status-r02.json` oder aequivalenter maschinenlesbarer Status.

## Abschlusskriterien
PASS nur wenn:

- Checkpoint-Resume reproduzierbar getestet,
- Retry-Endlosschleife begrenzt,
- laufender Documents-Auftrag nicht beruehrt wurde,
- AI3D-Workflow unveraendert blieb,
- keine neue unnötige Komplexitaet ohne belegten Nutzen eingefuehrt wurde,
- `NUTZERENTSCHEIDUNG_ERFORDERLICH=false`, sofern keine echte Produktentscheidung auftaucht.

Nach PASS: Workflow R02 als eingefrorenen stabilen Stand behandeln. Weitere Optimierung nur bei messbarem Problem oder klar belegtem Nutzen.
