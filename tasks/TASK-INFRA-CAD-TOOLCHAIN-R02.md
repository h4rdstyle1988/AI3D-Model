# TASK – CAD-/Rüdiger-Toolchain abschließen – R02

Status: **INFRASTRUKTUR-AUFTRAG**

## Ausgangslage

- PETG-Klammer und Nubsi R01 liegen als druckbare Teststände vor. Produktgeometrie nicht verändern.
- `D:\AI3D-Agent` ist aktiv.
- Der reale D:-E2E-Smoke-Test ist erfolgreich: Fetch -> Task-Erkennung -> Codex -> Ergebnisdatei -> Commit -> Push -> Remote-Verifikation.
- Lokaler Runtime-Watcher wurde für stabilen Betrieb außerhalb des mutablen Workers verwendet.
- Codex-stdin musste lokal auf einen UTF-8-sicheren Weg umgestellt werden; diese bewährte Lösung soll sauber ins Repo zurückgeführt werden.
- Alte R01-Berichte, die D:-E2E noch als OFFEN melden, gelten insoweit als überholt.
- `tasks/TASK_QUEUE.txt` existiert als FIFO-Warteschlange. Der bereits vom Nutzer freigegebene Testwürfel steht dort und darf den laufenden R02-Auftrag nicht verdrängen.

## Ziel

Die noch fehlenden Toolchain-Punkte technisch abschließen und den nun real validierten lokalen Betrieb reproduzierbar im Repository abbilden. Zusätzlich den Übergabeprozess so absichern, dass ein freigegebener Auftrag weder verloren gehen noch einen laufenden Auftrag überschreiben kann. Keine Produktdateien ändern.

## VERBINDLICH

1. **Watcher auf validierten Runtime-Stand bringen**
   - Repo-Watcher mit der lokal bewährten D:-Architektur abgleichen.
   - Kein `Start-Job` für Codex-stdin verwenden, wenn dies den bekannten stdin-Loop auslösen kann.
   - Prompt-Übergabe muss unter Windows PowerShell 5.1 UTF-8-sicher funktionieren; keine Nutzung einer dort nicht vorhandenen `StandardInputEncoding`-Eigenschaft voraussetzen.
   - Stabilen Runtime-Pfad unter `D:\AI3D-Agent\runtime` berücksichtigen, sodass ein Worker-Reset den laufenden Watcher nicht überschreibt.
   - Heartbeat 60–120 s beibehalten.

2. **OpenSCAD CLI prüfen/einrichten**
   - Vorhandene Installation und typische Pfade prüfen.
   - Falls vorhanden: robust erkennen und Smoke-Test durchführen.
   - Falls nicht vorhanden: nur sichere/reproduzierbare Installationswege verwenden; ohne nötige Admin-/GUI-Freigabe selbstständig einrichten, andernfalls präzise NUTZERAKTION dokumentieren.

3. **Python + CadQuery als isolierte zweite CAD-Schiene**
   - Vorhandenes Python prüfen.
   - Falls kein brauchbarer Interpreter vorhanden und ohne riskante Systemänderung möglich: projektbezogene Umgebung unter `D:\AI3D-Agent\toolchain` einrichten.
   - CadQuery-Import + einfacher parametrischer Export-Smoke-Test.
   - Keine globale Paketinstallation erzwingen.

4. **CAD-Toolchain-Preflight**
   - Vor Konstruktionsläufen maschinenlesbar prüfen/loggen: Git, Codex, OpenSCAD, Python, CadQuery, Mesh/STL-Prüfweg, Slicer-CLI.
   - Fehlende optionale Tools dürfen nicht pauschal blockieren, wenn ein reproduzierbarer Ersatzweg vorhanden ist.
   - Ergebnis unter D:-State/Toolchain-Struktur leicht auffindbar halten.

5. **Referenzbilder standardisieren**
   - Schema `references/<projekt>/` verbindlich dokumentieren/implementieren.
   - Tasks müssen konkrete Referenzpfade nennen.
   - Originale und KI-generierte Bilder eindeutig unterscheiden.
   - Falls Binärübertragung nicht möglich: Manifest mit Quelle, Dateiname, Status und Verfügbarkeit.

6. **Ergebnis-/SOLL-IST-Rückführung verbessern**
   - Für neue Rüdiger-Branches kompakten maschinenlesbaren Status festlegen/erzeugen: Task, Revision, PASS/STOPP/OFFEN, Hauptdateien, Validierungen, offene reale Tests, echte Nutzerentscheidungen.
   - Technische STOPPs nicht als Nutzerentscheidung markieren.
   - Keine automatische finale Produktfreigabe und kein automatisches Merge.

7. **Slicer-CLI prüfen**
   - Anycubic Slicer Next und kompatible lokal vorhandene CLIs prüfen.
   - GUI nicht als CLI behandeln.
   - Falls keine geeignete CLI vorhanden: klar dokumentieren, keine riskante Fremdinstallation nur dafür.

8. **R01-Status aktualisieren**
   - Neuen Infrastrukturbericht R02 erzeugen, der den realen D:-E2E-PASS korrekt berücksichtigt.
   - Klar trennen: GEÄNDERT / UNVERÄNDERT / INSTALLIERT / VALIDIERT / OFFEN / NUTZERAKTION.
   - C:-Altbestand nicht löschen. Nur als potenziell entfernbar markieren, wenn technisch sicher belegt.

9. **Selbstständigen Auftrags-Workflow mit FIFO-Queue absichern**
   - `tasks/CURRENT_TASK.txt` bleibt der explizit aktive Auftrag.
   - `tasks/TASK_QUEUE.txt` enthält null oder mehr bereits freigegebene, wartende Tasks; ein relativer Task-Pfad pro Zeile, Reihenfolge = FIFO.
   - Ein laufender Auftrag darf niemals durch einen neuen Nutzerauftrag überschrieben werden.
   - Wenn der aktive Task bereits erfolgreich verarbeitet und remote verifiziert wurde, muss der Watcher selbstständig den ersten noch nicht verarbeiteten Queue-Eintrag auswählen und ausführen, ohne dass der Nutzer oder ChatGPT `CURRENT_TASK` manuell umschalten muss.
   - Dafür robuste lokale Zustandsführung verwenden (mehr als nur ein einzelner `lastKey`), sodass mehrere Queue-Aufträge nacheinander genau einmal verarbeitet werden können.
   - Task-Identität mindestens aus Task-Pfad + Blob-SHA bilden. Eine geänderte Task-Revision muss als neuer Arbeitsstand erkannt werden.
   - Queue-Einträge dürfen bei Fehlern/STOPP nicht stillschweigend als erfolgreich erledigt markiert werden.
   - Nach erfolgreichem Push muss der Remote-Branch verifiziert sein, bevor ein Auftrag als verarbeitet gilt.
   - Ein technischer Fehler darf die Queue nicht zerstören. Zustand und Ursache protokollieren.
   - Der bereits in `tasks/TASK_QUEUE.txt` eingetragene Testwürfel ist nach R02 der erste reale Queue-Test.

10. **Freigabe-Gate zwischen Nutzer/ChatGPT und Rüdiger verbindlich machen**
   - Anforderungen dürfen vor Nutzerfreigabe als Entwurf/Spezifikation dokumentiert werden, aber nicht zur Konstruktion aktiviert oder in die ausführbare Queue eingestellt werden.
   - Erst nach ausdrücklicher Nutzerfreigabe darf ChatGPT den Konstruktionsauftrag aktivieren/einreihen.
   - Rüdiger erzeugt CAD/STL/Druckdateien erst aus einem freigegebenen aktiven/queued Task.
   - Rüdiger darf technisch notwendige Details selbst lösen, solange dadurch keine verbindliche Nutzeranforderung verändert oder neue Funktion erfunden wird.
   - Bei technischen STOPPs zuerst technisch sauber dokumentieren; nur echte Änderungen an Funktion, verbindlichen Maßen, Produktidee, fehlende reale Referenzdaten oder widersprüchliche Anforderungen als `NUTZERENTSCHEIDUNG_ERFORDERLICH` kennzeichnen.
   - Keine Rückfrage an den Nutzer wegen rein technischer Umsetzungsdetails, die innerhalb der freigegebenen Spezifikation lösbar sind.

11. **Ende-zu-Ende-Abnahmetest des endgültigen Workflows**
   - Nach Implementierung R02 selbst erfolgreich remote verifizieren.
   - Danach ohne manuelle Änderung von `CURRENT_TASK` den freigegebenen Würfel aus `TASK_QUEUE.txt` automatisch aufnehmen.
   - Für den Würfel muss der Ablauf nachweisbar sein: Queue-Erkennung -> Codex -> reproduzierbare CAD-Quelle -> STL -> SOLL/IST/Validierung -> Commit -> Push -> Remote-Verifikation.
   - Keine zusätzliche Geometrie erfinden.
   - Wenn dieser Queue-Test nicht vollständig PASS ist, Infrastrukturstatus bleibt OFFEN und die konkrete Ursache wird dokumentiert.

## Validierung

Mindestens dokumentieren:
- D:-Worker und Scheduler-Kontext weiterhin funktionsfähig.
- Git/Codex erreichbar.
- UTF-8-sichere Codex-Promptübergabe reproduzierbar.
- Toolchain-Preflight läuft auch bei fehlenden optionalen Modulen durch.
- OpenSCAD-Smoke-Test falls verfügbar.
- Python/CadQuery-Smoke-Test falls verfügbar/eingerichtet.
- Slicer-CLI-Inventar.
- Referenzschema und Ergebnisstatusschema.
- Queue verarbeitet mehrere freigegebene Aufträge genau einmal und ohne Überschreiben.
- Freigabe-Gate verhindert Konstruktion vor Nutzerfreigabe.
- R02 -> queued Testwürfel läuft ohne manuelle Task-Umschaltung.
- Keine Produktgeometrie außerhalb des ausdrücklich freigegebenen Würfeltests geändert.

## Sicherheit

- Keine breiten Kill/Reset/Clean-Aktionen außerhalb des dedizierten Workers.
- Keine Nutzerdaten löschen.
- Keine bestehende Produktgeometrie ändern.
- Keine riskanten Systemänderungen oder dubiosen Downloads.
- Nur echte unvermeidbare Admin-/GUI-Freigabe an Nutzer eskalieren.
