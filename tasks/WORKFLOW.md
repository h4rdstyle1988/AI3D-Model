# Automatischer Übergabe-Workflow

Ziel: Der Nutzer klärt Anforderungen mit ChatGPT. ChatGPT legt die verbindliche Task-Datei im Repository ab und setzt `tasks/CURRENT_TASK.txt`. Rüdiger/Codex liest den Auftrag aus einem separaten Worker-Clone und führt ihn dort aus. Der normale lokale Arbeitsbaum bleibt unberührt.

## Ablauf

1. ChatGPT erstellt/aktualisiert eine Task-Datei unter `tasks/`.
2. ChatGPT setzt `tasks/CURRENT_TASK.txt` auf diese Datei.
3. Der lokale Watcher `tools/ruediger-agent-watch.ps1` erkennt eine neue/änderte aktive Task.
4. Der Watcher arbeitet ausschließlich in einem separaten Worker-Clone.
5. Codex wird nicht-interaktiv mit der aktiven Task gestartet.
6. Nach erfolgreichem Lauf committet und pusht der Watcher ausschließlich den Worker-Stand auf einen eigenen Branch `ruediger/...`.
7. Das Ergebnis ist damit auf GitHub verfügbar und kann von ChatGPT gegen die verbindliche Spezifikation geprüft werden.

## Sicherheitsregeln

- Der bestehende Haupt-Arbeitsbaum wird niemals automatisch resettet, bereinigt oder überschrieben.
- Keine automatische finale Produktfreigabe.
- Wenn die Task selbst einen STOPP wegen fehlender Information fordert, muss Codex den offenen Punkt dokumentieren und darf ihn nicht erraten.
- Ein neuer Nutzerentscheid bleibt dem Nutzer vorbehalten.

## Einmalige lokale Einrichtung

Der Watcher muss einmal auf dem PC gestartet bzw. als Autostart-/Task-Scheduler-Aufgabe eingerichtet werden. Danach überwacht er den aktiven Auftrag selbstständig.
