# AI3D-Model – Agenten-Arbeitsregeln

Dieses Repository wird für die Übergabe zwischen ChatGPT (Spezifikation/Prüfung) und Codex/Rüdiger (Konstruktion/Ausführung) verwendet.

## Priorität
1. aktuelle Nutzerangabe
2. zuletzt bestätigte Spezifikation / aktive Task-Datei
3. reale Datei, Messung oder CAD-Geometrie
4. technische Berechnung
5. frühere KI-Aussage

## Aktiver Auftrag
Der aktive Auftrag steht in `tasks/CURRENT_TASK.txt`. Diese Datei enthält exakt einen relativen Pfad zu einer Task-Datei unter `tasks/` oder `NONE`.

Vor jeder Konstruktion:
- `tasks/CURRENT_TASK.txt` lesen,
- die referenzierte Task-Datei vollständig lesen,
- VERBINDLICH / TECHNISCH NOTWENDIG / OFFEN unterscheiden,
- bei fehlenden konstruktiv relevanten Angaben nicht raten.

## Schutz bestehender Arbeit
Ein vorhandener Arbeitsbaum darf wegen einer neuen Task niemals pauschal per `reset`, `clean`, `restore` oder ungezieltem `pull` verändert werden. Automatisierte Arbeit erfolgt ausschließlich in einem separaten, dedizierten Worker-Clone.

## Ergebnis
Für jeden Auftrag nur die taskbezogenen Dateien ändern. Keine stillen Nebenänderungen. Ergebnis mit SOLL/IST-Prüfung, Revisionsangaben und offenen Punkten dokumentieren. Finale Produktfreigabe erfolgt ausschließlich durch den Nutzer.
