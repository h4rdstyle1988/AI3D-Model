# AI3D-Model – Agenten-Arbeitsregeln

Dieses Repository wird für die Übergabe zwischen ChatGPT (Spezifikation/Prüfung) und Codex/Rüdiger (Konstruktion/Ausführung) verwendet.

## Priorität
1. aktuelle Nutzerangabe
2. zuletzt bestätigte Spezifikation / freigegebene Task-Datei
3. reale Datei, Messung oder CAD-Geometrie
4. technische Berechnung
5. frühere KI-Aussage

## Freigabe-Gate
Vor ausdrücklicher Nutzerfreigabe darf keine Konstruktion gestartet und keine Druckdatei erzeugt werden. Entwürfe dürfen dokumentiert werden, aber nicht über `tasks/CURRENT_TASK.txt` oder `tasks/TASK_QUEUE.txt` ausführbar gemacht werden.

Nach ausdrücklicher Nutzerfreigabe darf der Auftrag aktiviert oder in die Queue eingereiht werden.

## Aktiver Auftrag und Queue
- `tasks/CURRENT_TASK.txt` enthält exakt einen relativen Pfad zu einer aktiven Task unter `tasks/` oder `NONE`.
- `tasks/TASK_QUEUE.txt` enthält null oder mehr bereits freigegebene wartende Tasks, ein relativer Pfad pro Zeile, FIFO-Reihenfolge.
- Ein laufender Auftrag darf durch einen neuen Auftrag niemals überschrieben werden.
- Ein verarbeiteter Task wird mindestens über Task-Pfad + Blob-SHA identifiziert. Eine geänderte Task-Version ist ein neuer Arbeitsstand.

Vor jeder Konstruktion:
- Steuerdateien lesen,
- konkrete Task vollständig lesen,
- VERBINDLICH / TECHNISCH NOTWENDIG / OFFEN unterscheiden,
- vorhandene Referenzen und Maße prüfen,
- bei fehlenden konstruktiv relevanten realen Angaben nicht raten.

## Technische Eigenständigkeit
Rüdiger soll technische Details selbstständig lösen, wenn sie notwendig sind, um die freigegebene Funktion umzusetzen und dadurch keine verbindlichen Nutzermaße, Funktionen oder die Produktidee verändert werden.

Keine zusätzlichen Funktionen, Halterungen, Rastungen, Sockel, Anschläge, Führungen oder sonstige Nutzungsmöglichkeiten erfinden.

Reine CAD-, Mesh-, Script-, Toolchain-, Support-, Druckorientierungs- oder Berechnungsprobleme sind technische Aufgaben. Sie sind nicht automatisch Nutzerentscheidungen.

`NUTZERENTSCHEIDUNG_ERFORDERLICH` nur wenn:
- ein verbindliches Maß/eine verbindliche Funktion geändert werden müsste,
- verbindliche Anforderungen widersprüchlich sind,
- unterschiedliche Produktfunktionen/Formen zur Wahl stehen,
- ein erforderliches reales Maß/Referenzdatum fehlt und nicht eindeutig ableitbar ist,
- finale Nutzerfreigabe erforderlich ist.

## Schutz bestehender Arbeit
Ein vorhandener Arbeitsbaum darf wegen einer neuen Task niemals pauschal per `reset`, `clean`, `restore` oder ungezieltem `pull` verändert werden. Automatisierte Arbeit erfolgt ausschließlich in einem separaten, dedizierten Worker-Clone.

## Ergebnis
Für jeden Auftrag nur taskbezogene Dateien ändern. Keine stillen Nebenänderungen. Ergebnis mit SOLL/IST-Prüfung, Revisionsangaben, technischen Validierungen und offenen Punkten dokumentieren.

Jeder neue Ergebnisstand soll zusätzlich maschinenlesbar kenntlich machen:
- Task/Revision,
- PASS/STOPP/OFFEN,
- Hauptdateien,
- Validierungen,
- offene reale Tests,
- `NUTZERENTSCHEIDUNG_ERFORDERLICH: true/false` mit Grund.

Ein erfolgreicher STL-Export, ein watertight Mesh oder ein Validator-PASS ist keine finale Produktfreigabe. Finale Produktfreigabe erfolgt ausschließlich durch den Nutzer.
