# TASK – CAD-/Rüdiger-Toolchain beschleunigen – R01

Status: **INFRASTRUKTUR-AUFTRAG**
Quelle: Nutzerfreigabe 2026-08-29 nach druckbereiter PETG-Klammer + Nubsi R01

## AKTUELLER NUTZERSTAND

- Nutzer bestätigt: `D:\AI3D-Agent` **existiert bereits**.
- Diesen Punkt nicht erneut als STOPP/NUTZERAKTION behandeln.
- Nächster technischer Schritt ist die kontrollierte Umstellung und Ende-zu-Ende-Validierung des lokalen Workflows auf diesen vorhandenen D:-Pfad.

## Ziel

Den lokalen Rüdiger/Codex-Workflow für künftige 3D-Konstruktionsaufträge schneller, transparenter und robuster machen. Dieser Auftrag darf **keine Produktgeometrie** der Bettklammer oder des Nubsi verändern.

## VERBINDLICHER LOKALER ABLAGEORT

- Der Nutzer hat `D:\AI3D-Agent` als verbindlichen lokalen Stammordner festgelegt; der Ordner ist bereits vorhanden.
- Ziel: große bzw. wachsende Agent-/Worker-/Projekt-Ausgaben sollen nicht weiter unnötig Laufwerk C: füllen.
- Künftiger dedizierter Worker, lokale Ausgaben, Cache-/Arbeitsdaten und sinnvoll verlagerbare projektbezogene Daten sollen unter `D:\AI3D-Agent` organisiert werden.
- Bestehende Daten auf C: **nicht blind löschen oder verschieben**. Zuerst Bestand, aktive Pfade und Abhängigkeiten prüfen; dann kontrolliert migrieren bzw. neue Pfade umstellen.
- Windows-/Codex-Systemdaten, die technisch an `%LOCALAPPDATA%` oder andere Systempfade gebunden sind, nur dann verlagern, wenn dies unterstützt und sicher ist. Keine riskanten Junction-/Symlink-Tricks ohne technische Notwendigkeit.
- Der GitHub-Repository-Workflow bleibt erhalten; `D:\AI3D-Agent` ist die lokale Arbeits-/Ablagestruktur.
- Nach erfolgreicher Migration dokumentieren, welche alten C:-Ordner gefahrlos gelöscht werden können. Nicht eigenmächtig Nutzerdaten löschen.

## VERBINDLICH

1. **OpenSCAD CLI prüfen und bevorzugt verfügbar machen**
   - Zuerst feststellen, ob OpenSCAD bereits installiert, aber im Scheduler-/Watcher-Kontext nicht im PATH ist.
   - Falls vorhanden: Pfad robust erkennen/verwenden, keine unnötige Neuinstallation.
   - Falls nicht vorhanden: eine sichere, reproduzierbare Installationsmöglichkeit vorbereiten bzw. ausführen, soweit ohne Nutzerinteraktion/Admin-Freigabe möglich.
   - Keine dubiosen Downloadquellen. Wenn eine Installation zwingend Admin-/GUI-Freigabe benötigt: sauber als NUTZERAKTION dokumentieren, nicht umgehen.

2. **Python + CadQuery als zweite CAD-Schiene prüfen/einrichten**
   - Vorhandene Python-Installationen/Launcher/venv/Conda prüfen, nicht blind neu installieren.
   - CadQuery in isolierter, projektbezogener Umgebung bevorzugen, damit das System nicht unnötig verändert wird.
   - Funktions-Smoke-Test: einfacher parametrischer Körper muss erzeugbar/exportierbar sein.
   - OpenSCAD bleibt für einfache parametrische Konstruktionen zulässig; CadQuery ist zusätzliche, nicht erzwungene Schiene.

3. **Toolchain-Preflight in den Watcher integrieren**
   - Vor einem Codex-Konstruktionslauf kompakt feststellen und loggen: Git, Codex, OpenSCAD, Python/CadQuery, verfügbarer Mesh-/STL-Prüfweg und CLI-Slicer.
   - Fehlendes optionales Werkzeug darf einen Auftrag nicht pauschal blockieren, wenn ein vorhandener reproduzierbarer Ersatzweg genügt.
   - Ergebnis für Rüdiger maschinenlesbar/leicht auffindbar bereitstellen, damit er nicht bei jedem Auftrag dieselben Tools erneut suchen muss.

4. **Referenzbilder standardisieren**
   - Künftige projektbezogene Referenzen nach einem eindeutigen Schema unter `references/<projekt>/` verwalten.
   - Tasks müssen konkrete Repo-Pfade nennen statt nur „Fotos wurden bereitgestellt“.
   - Originalreferenzen schützen; keine KI-generierten Bilder als reale Referenz umdeuten.
   - Wenn Binärdateien nicht über den aktuellen Remote-Workflow übertragen werden können, einen dokumentierten Ersatzweg/Manifest-Mechanismus schaffen, der Rüdiger die tatsächlich verfügbare Referenzlage eindeutig mitteilt.

5. **Ergebnis-/SOLL-IST-Rückführung verbessern**
   - Jeder Rüdiger-Ergebnisbranch soll einen kompakten maschinenlesbaren Status enthalten: Task, Revision, PASS/STOPP/OFFEN, erzeugte Hauptdateien, Validierungen, offene reale Tests und echte Nutzerentscheidungen.
   - Technische/infrastrukturelle STOPPs nicht fälschlich als Nutzerentscheidung markieren.
   - Keine automatische finale Produktfreigabe und kein automatisches Merge nach master.

6. **Slicer-CLI prüfen**
   - Ermitteln, ob Anycubic Slicer Next oder eine kompatible vorhandene Slicer-CLI lokal automatisierbar erreichbar ist.
   - Keine Annahme, dass eine GUI-Anwendung eine unterstützte CLI besitzt.
   - Falls keine geeignete CLI vorhanden ist: dokumentieren; keine riskante oder fremde Software nur für diesen Punkt installieren.
   - Ziel ist später automatisierbare Prüfung von Bauraum, Orientierung, Supportbedarf und – soweit verlässlich verfügbar – Druckzeit/Material.

7. **Heartbeat/Status für PowerShell-Watcher**
   - Während längerer Codex-Läufe soll der sichtbare Watcher in sinnvollen Abständen einen knappen Status ausgeben, damit klar unterscheidbar ist: ARBEITET / WARTET / FERTIG / FEHLER.
   - Kein Spam im Sekundentakt. Zielbereich für sichtbaren Arbeits-Heartbeat: etwa 60–120 Sekunden.
   - Heartbeat darf den Codex-Prozess nicht unterbrechen oder dessen Ausgabe beschädigen.

8. **Lokale Datenstruktur auf D: umstellen und real validieren**
   - Vorhandenen Stammordner `D:\AI3D-Agent` verwenden; nicht erneut anlegen müssen.
   - Eine klare Unterstruktur für Worker, Outputs, Logs, Cache/Temp und ggf. Toolchain-Umgebungen festlegen, soweit diese Daten tatsächlich zum Agent-Workflow gehören.
   - Watcher/Scheduler so anpassen, dass der dedizierte Worker künftig unter D: arbeitet.
   - Im lokalen Benutzer-/Scheduler-Kontext einen Diagnose- und anschließend echten Ende-zu-Ende-Lauf durchführen: Fetch -> Task-Erkennung -> Codex -> Commit -> Push -> Remote-Verifikation.
   - Heartbeat bei einem ausreichend langen Lauf real beobachten/validieren.
   - Vorhandenen C:-Worker erst nach erfolgreicher Validierung des D:-Workers als Altbestand kennzeichnen.
   - Repository-/Task-Kompatibilität und Git-Push müssen nach der Umstellung unverändert funktionieren.
   - Falls der aktuelle Codex-Worker selbst nicht aus seiner Sandbox nach D: schreiben darf, darf dies nicht erneut als Produkt-/Nutzer-STOPP enden: stattdessen den vorhandenen lokalen Watcher/Scheduler-Weg für die Migration/Validierung nutzen oder präzise nur die tatsächlich nötige einmalige Benutzeraktion ausgeben.

## SICHERHEIT / ÄNDERUNGSSCHUTZ

- Bestehenden funktionierenden Watcher nicht blind ersetzen.
- Vor Änderung aktuellen Stand prüfen und nur gezielt ändern.
- Keine breiten `kill`, `reset`, `clean` oder Änderungen am normalen Benutzer-Arbeitsbaum.
- Der dedizierte Worker bleibt getrennt.
- Keine Produktdateien/Geometrien ändern.
- Keine bestehenden Revisionen überschreiben.
- Keine Installation oder Systemänderung erzwingen, wenn dafür eine echte Nutzer-/Adminfreigabe erforderlich ist.
- Keine Nutzerdaten auf C: eigenmächtig löschen.

## VALIDIERUNG

Nach Umsetzung mindestens prüfen/dokumentieren:

- Watcher startet im Scheduler-Kontext weiterhin erfolgreich.
- Git und Codex weiterhin erreichbar.
- Neuer D:-Worker unter `D:\AI3D-Agent` funktioniert einschließlich Fetch, Task-Erkennung, Codex-Lauf, Commit und Push.
- Neue Toolchain-Erkennung liefert reproduzierbare Ergebnisse.
- Falls OpenSCAD verfügbar/eingerichtet: CLI-Smoke-Test.
- Falls Python/CadQuery verfügbar/eingerichtet: Import- und Export-Smoke-Test.
- Heartbeat funktioniert ohne den Worker-Lauf zu stören.
- Fehlende optionale Tools werden klar gemeldet, ohne unnötigen STOPP.
- Referenzschema und Ergebnisstatus sind dokumentiert.

## AUSGABE

Erzeuge einen Infrastrukturbericht mit:

- **GEÄNDERT**
- **UNVERÄNDERT**
- **INSTALLIERT / BEREITS VORHANDEN**
- **VALIDIERT**
- **OFFEN**
- **NUTZERAKTION ERFORDERLICH** nur wenn wirklich unvermeidbar

Zusätzlich alle erforderlichen Skript-/Dokumentationsänderungen im Ergebnisbranch ablegen.

## ESKALATION

Technische Detailentscheidungen selbstständig treffen, solange keine bestätigte Produktidee verändert und keine riskante Systemänderung vorgenommen wird. Nur echte Admin-/GUI-Freigaben, nicht automatisierbare lokale Benutzeraktionen oder Produktentscheidungen an den Nutzer eskalieren.
