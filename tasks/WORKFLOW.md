# Automatischer Übergabe-Workflow

Ziel: Der Nutzer klärt Anforderungen mit ChatGPT. ChatGPT legt die verbindliche Task-Datei im Repository ab und setzt `tasks/CURRENT_TASK.txt`. Rüdiger/Codex liest den Auftrag aus einem separaten Worker-Clone und führt ihn dort aus. Der normale lokale Arbeitsbaum bleibt unberührt.

## Ablauf

1. ChatGPT erstellt/aktualisiert eine Task-Datei unter `tasks/`.
2. ChatGPT setzt `tasks/CURRENT_TASK.txt` auf diese Datei.
3. Der lokale Watcher `tools/ruediger-agent-watch.ps1` erkennt eine neue/geänderte aktive Task.
4. Der Watcher arbeitet ausschließlich in einem separaten Worker-Clone.
5. Codex wird nicht-interaktiv mit der aktiven Task gestartet.
6. Nach erfolgreichem Lauf committet und pusht der Watcher ausschließlich den Worker-Stand auf einen eigenen Branch `ruediger/...`.
7. Der Watcher verifiziert, dass der gepushte Commit tatsächlich als Remote-Branch auf GitHub vorhanden ist.
8. Erst nach dieser Remote-Verifikation darf der lokale Worker auf den kompakten Ruhemodus reduziert werden. Projektordner `outputs/` und `work/` bleiben dann nicht lokal ausgecheckt.
9. Das Ergebnis ist auf GitHub verfügbar und kann von ChatGPT gegen die verbindliche Spezifikation geprüft werden.

## Lokale Speicherregeln

- Watcher-Logs werden tageweise unter `%LOCALAPPDATA%\AI3D-Model\logs` gespeichert.
- Logdateien älter als **7 Tage** werden automatisch gelöscht.
- Alte Projekt-Arbeitsstände sollen **nicht dauerhaft lokal liegen**. GitHub ist die dauerhafte Projektablage.
- Der Worker darf Projektdateien während eines aktiven Auftrags temporär auschecken. Nach verifiziertem Push wird er wieder auf einen kompakten Sparse-Checkout mit nur Steuerdateien (`tasks/`, `tools/`, `library/` und Root-Metadaten) reduziert.
- Der normale Benutzer-Arbeitsbaum wird von dieser Bereinigung nicht verändert.
- Die Git-Objektdatenbank des Worker-Repositories kann weiterhin komprimierte Git-Objekte enthalten; sie ist kein sichtbarer Projekt-Arbeitsordner. Falls später strikte Cache-Limits nötig werden, wird dafür eine separate, ausdrücklich freigegebene Cache-Regel eingeführt.

## Projektbibliothek

- Die dauerhafte Projektübersicht wird aus `library/projects.json` erzeugt.
- Lokal wird daraus eine klickbare HTML-Galerie unter `%LOCALAPPDATA%\AI3D-Model\project-library\index.html` erzeugt.
- Pro freigegebenem/archiviertem Projekt enthält die Bibliothek mindestens:
  - Projektname,
  - kurze Beschreibung,
  - Status,
  - ein reales Projektbild/Preview,
  - GitHub-Ziel (Pfad/Branch/Referenz).
- Keine erfundenen Bilder oder Beschreibungen. Fehlt ein reales Preview, bleibt der Bibliothekseintrag OFFEN und wird nicht als vollständig archiviert bezeichnet.
- Die HTML-Galerie ist nur eine kleine lokale Auswahloberfläche. CAD/STL/Revisionen bleiben auf GitHub.

## Sicherheitsregeln

- Der bestehende Haupt-Arbeitsbaum wird niemals automatisch resettet, bereinigt oder überschrieben.
- Lokale Projektdateien werden erst nach erfolgreichem Push **und Remote-Verifikation** aus dem Worker-Arbeitsbaum entfernt.
- Keine automatische finale Produktfreigabe.
- Wenn die Task selbst einen STOPP wegen fehlender Information fordert, muss Codex den offenen Punkt dokumentieren und darf ihn nicht erraten.
- Ein neuer Nutzerentscheid bleibt dem Nutzer vorbehalten.

## Einmalige lokale Einrichtung

Der Watcher muss einmal auf dem PC gestartet bzw. als Autostart-/Task-Scheduler-Aufgabe eingerichtet werden. Danach überwacht er den aktiven Auftrag selbstständig. Vor der produktiven Konstruktion wird der Scheduler zunächst im Diagnosemodus geprüft.
