# TASK – CAD-/Rüdiger-Toolchain abschließen – R02

Status: **INFRASTRUKTUR-AUFTRAG**

## Ausgangslage

- PETG-Klammer und Nubsi R01 liegen als druckbare Teststände vor. Produktgeometrie nicht verändern.
- `D:\AI3D-Agent` ist aktiv.
- Der reale D:-E2E-Smoke-Test ist erfolgreich: Fetch -> Task-Erkennung -> Codex -> Ergebnisdatei -> Commit -> Push -> Remote-Verifikation.
- Lokaler Runtime-Watcher wurde für stabilen Betrieb außerhalb des mutablen Workers verwendet.
- Codex-stdin musste lokal auf einen UTF-8-sicheren Weg umgestellt werden; diese bewährte Lösung soll sauber ins Repo zurückgeführt werden.
- Alte R01-Berichte, die D:-E2E noch als OFFEN melden, gelten insoweit als überholt.

## Ziel

Die noch fehlenden Toolchain-Punkte technisch abschließen und den nun real validierten lokalen Betrieb reproduzierbar im Repository abbilden. Keine Produktdateien ändern.

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
- Keine Produktgeometrie geändert.

## Sicherheit

- Keine breiten Kill/Reset/Clean-Aktionen außerhalb des dedizierten Workers.
- Keine Nutzerdaten löschen.
- Keine Produktgeometrie ändern.
- Keine riskanten Systemänderungen oder dubiosen Downloads.
- Nur echte unvermeidbare Admin-/GUI-Freigabe an Nutzer eskalieren.
