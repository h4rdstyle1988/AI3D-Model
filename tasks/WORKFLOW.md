# Automatischer Übergabe-Workflow

Ziel: Der Nutzer beschreibt ChatGPT den gewünschten Druckauftrag. ChatGPT klärt konstruktiv relevante Unklarheiten, hält die Anforderungen fest und aktiviert die Konstruktion erst nach ausdrücklicher Nutzerfreigabe. Rüdiger/Codex arbeitet danach selbstständig im separaten Worker-Clone. Ergebnisse werden auf GitHub zurückgeführt und von ChatGPT gegen die freigegebene Spezifikation geprüft.

## Verbindlicher Ablauf

1. Nutzer übermittelt Idee, Maße, Bilder, Material-/Druckvorgaben und sonstige Anforderungen.
2. ChatGPT prüft, ob Funktion, Maße, Orientierung und Anschlussgeometrie eindeutig genug sind. Fehlende konstruktiv relevante Angaben werden vor der Konstruktion beim Nutzer geklärt; technische Details, die die bestätigte Produktidee nicht verändern, werden nicht unnötig an den Nutzer eskaliert.
3. Vor Nutzerfreigabe darf eine Task als ENTWURF dokumentiert werden, aber weder `tasks/CURRENT_TASK.txt` noch `tasks/TASK_QUEUE.txt` dürfen diesen Entwurf zur Ausführung freigeben.
4. Erst nach ausdrücklicher Nutzerfreigabe wird der Auftrag ausführbar:
   - falls kein Auftrag läuft: als aktiver Task,
   - falls bereits ein Auftrag läuft: FIFO in `tasks/TASK_QUEUE.txt`.
5. Der lokale Watcher erkennt aktive und bereits freigegebene wartende Tasks.
6. Rüdiger/Codex liest `AGENTS.md` und die konkrete Task vollständig und konstruiert ausschließlich die freigegebene Anforderung.
7. Technisch notwendige Details darf Rüdiger selbst lösen, solange keine verbindlichen Nutzermaße, Funktionen oder die Produktidee verändert und keine neue Funktion ergänzt wird.
8. Nach erfolgreichem Lauf committet und pusht der Watcher ausschließlich den Worker-Stand auf einen eigenen Branch `ruediger/...` und verifiziert den Remote-Commit.
9. Erst nach erfolgreicher Remote-Verifikation gilt der Arbeitslauf technisch als abgeschlossen.
10. Wenn weitere freigegebene Tasks in `tasks/TASK_QUEUE.txt` stehen, nimmt der Watcher den nächsten noch nicht verarbeiteten Eintrag selbstständig auf. Ein laufender Task wird niemals durch einen neuen Auftrag überschrieben.
11. ChatGPT prüft das Ergebnis gegen die letzte vom Nutzer freigegebene Spezifikation. Technische Validierung und Übereinstimmung mit der Nutzeridee werden getrennt bewertet.
12. Nur der Nutzer gibt die finale Produktfreigabe. Keine KI, kein Validator und kein erfolgreicher STL-Export ersetzt diese Freigabe.

## Task-Steuerung

- `tasks/CURRENT_TASK.txt`: exakt ein aktiver relativer Task-Pfad oder `NONE`.
- `tasks/TASK_QUEUE.txt`: null oder mehr bereits freigegebene wartende Task-Pfade, ein Pfad pro Zeile, FIFO-Reihenfolge.
- Nicht freigegebene Entwürfe dürfen in `tasks/` liegen, aber weder aktiv noch queued sein.
- Task-Identität wird mindestens aus Task-Pfad + Blob-SHA gebildet. Eine geänderte Task-Version ist ein neuer Arbeitsstand.
- Erfolgreich verarbeitete Queue-Einträge müssen lokal robust nachverfolgt werden; ein einzelner `lastKey` reicht für mehrere Tasks nicht aus.
- Ein Fehler oder STOPP darf einen Queue-Eintrag nicht stillschweigend als erledigt markieren.

## STOPP-/Entscheidungslogik

Rüdiger soll technische Probleme soweit möglich selbst lösen. Ein Ergebnis darf als `NUTZERENTSCHEIDUNG_ERFORDERLICH` nur zurückkommen, wenn mindestens einer dieser Fälle vorliegt:
- ein verbindliches Nutzermaß oder eine verbindliche Funktion müsste geändert werden,
- zwei verbindliche Anforderungen widersprechen sich,
- eine echte Produktentscheidung zwischen unterschiedlichen Funktionen/Formen ist nötig,
- ein erforderliches reales Maß/Referenzdatum fehlt und ist nicht eindeutig aus vorhandenen Dateien/Bildern ableitbar,
- finale Nutzerfreigabe steht an.

Reine Toolchain-, CAD-, Mesh-, Script-, Support-, Druckorientierungs- oder Berechnungsprobleme sind zunächst technische Aufgaben und keine Nutzerentscheidung, solange die freigegebene Produktidee unverändert bleiben kann.

## Ergebnisstatus

Jeder neue Rüdiger-Auftrag soll einen kompakten maschinenlesbaren Status liefern mit mindestens:
- Task und Revision,
- `PASS`, `STOPP` oder `OFFEN`,
- Hauptausgabedateien,
- technische Validierungen,
- offene reale Tests,
- `NUTZERENTSCHEIDUNG_ERFORDERLICH: true/false` samt präzisem Grund.

Keine automatische finale Produktfreigabe und kein automatisches Merge.

Das maschinenlesbare Schema liegt unter `tools/result-status.schema.json`. Technische Fehler erhalten `STOPP` oder `OFFEN`, aber `user_decision_required: false`, solange keine der oben genannten echten Nutzerentscheidungen vorliegt.

## Referenzbilder

- Verbindliches Schema: `references/<projekt>/` mit `manifest.json`.
- Jede freigegebene Task nennt konkrete Referenzpfade; pauschale Hinweise auf bereitgestellte Fotos reichen nicht.
- `kind: original` bezeichnet ausschließlich reale Referenzen, `kind: ai_generated` ausschließlich KI-Bilder.
- Nicht übertragbare Binärdateien werden mit Quelle, geplantem Pfad, Status und `available: false` manifestiert.

## Lokale Speicherregeln

- Produktive Runtime liegt unter `D:\AI3D-Agent`; der laufende Watcher soll außerhalb eines mutablen Worker-Clones unter `D:\AI3D-Agent\runtime` betrieben werden.
- Projektarbeitsdaten des Workers sind temporär. GitHub ist die dauerhafte Projektablage.
- Lokale Projektdateien dürfen erst nach erfolgreichem Push und Remote-Verifikation aus dem sichtbaren Worker-Arbeitsbaum entfernt werden.
- Der normale Benutzer-Arbeitsbaum wird nicht automatisch resettet, bereinigt oder überschrieben.
- Logs werden zeitlich begrenzt aufbewahrt; keine Nutzerdaten breit löschen.

## Projektbibliothek

- Die dauerhafte Projektübersicht wird aus `library/projects.json` erzeugt.
- Nur tatsächlich freigegebene/archivierte Produkte gehören in die Kunden-/Projektbibliothek.
- Reale Produktbilder werden bevorzugt; fehlen sie, bleibt der Eintrag entsprechend OFFEN.
- Interne Testrevisionen, technische STOPPs und Rüdiger-Arbeitsstände bleiben intern.

## Sicherheitsregeln

- Keine breiten Kill/Reset/Clean-Aktionen außerhalb des dedizierten Workers.
- Keine stillen Änderungen an bestätigter Produktgeometrie.
- Keine Konstruktion oder Druckdatei vor Nutzerfreigabe des Auftrags.
- Keine automatische finale Produktfreigabe.
- Ein neuer Nutzerentscheid bleibt dem Nutzer vorbehalten.
