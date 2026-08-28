# Benchmark B – Spülenablage: verbindliche Anforderungen

Revision: **B-2026-08-25.1**  
Status: **BINDING / BUILD NOT YET PRESENT / NOT YET EVALUATED**

Diese Revision ist für alle weiteren Benchmark‑B-Konstruktionen, Builds und Berichte verbindlich. Bei Konflikten überschreibt sie ältere Annahmen zu Auslauflänge, Auslauftopologie und den Auflageflächen. Andere bereits definierte Hauptmaße bleiben bestehen, wurden im aktuellen Arbeitsbestand jedoch nicht gefunden und werden hier nicht erfunden.

## 1. Auslauf

### 1.1 Verbindliches Konstruktionsmaß

Die funktionale Auslaufstrecke beträgt **exakt 50 mm**.

Gemessen wird entlang der funktionalen Kanal-/Rinnenmittellinie:

- Start: Austritt der Entwässerungsrinne aus dem Hauptkörper;
- Ende: äußerstes funktionales Ende des Überstands in Richtung Spülbecken;
- nicht einzubeziehen: Kanalstrecke innerhalb des Hauptkörpers;
- bei einer gekrümmten Rinne gilt die Mittellinien-Bogenlänge, nicht die direkte Sehne.

Der `DIMENSION REPORT` muss Ziel, Messmethode, Start-/Endreferenz und gemessene Länge separat ausweisen.

### 1.2 Oben offene Rinne

Der gesamte Auslauf wird als **oben offene Rinne / offener Kanal** konstruiert.

Verboten sind:

- geschlossenes Rohr;
- Tunnel oder überdeckte Ablaufstrecke;
- unbeabsichtigte Tasche oder Sackgasse;
- lokale Abdeckung, die den freien Zugang von oben unterbricht.

Erforderlich sind:

- durchgehend sichtbarer und von oben zugänglicher Wasserweg;
- leichter Anstieg über den Spülenrand entsprechend der bisherigen Grunddefinition;
- anschließend freier Auslauf in die Spüle;
- keine unentwässerte lokale Senke entlang des funktionalen Wasserpfads.

Der Bericht weist zusätzlich minimale und maximale lichte Kanalbreite aus. Für diese Breiten wird mit dieser Revision kein neuer Zielwert erfunden; sie müssen aus dem konkreten CAD-Modell gemessen und funktional begründet werden.

## 2. Gitterauflagen

Spülbürste, Schwamm und Spülmittelflasche müssen auf **echten gitterartigen, wasserdurchlässigen Auflagen** stehen. Eine lediglich texturierte oder optisch angedeutete Vollfläche gilt nicht.

Zulässige Muster sind beispielsweise Raster, Steg-/Schlitzgitter oder wiederholte offene Drainagefelder. Das Muster ist frei, sofern alle Funktionsgates erfüllt werden.

Für jede der drei Nutzungszonen ist nachzuweisen:

1. offene Durchbrüche führen Wasser nach unten in die Auffang-/Drainagegeometrie;
2. Gegenstand steht oder liegt stabil und wird konstruktiv unterstützt;
3. Stege sind mit dem verwendeten FDM-Profil robust druckbar;
4. Öffnungen sind nicht unnötig fein und unterstützen den Wasserabfluss;
5. es existiert ein verbundener Wasserpfad von der Zone zur offenen Auslaufrinne.

Der Bericht nennt pro Zone mindestens Stegbreite, Steghöhe/-dicke, typische Öffnungsweite, freie Öffnungsfläche soweit berechenbar und die verwendete Gegenstands-/Hüllgeometrie für den Stabilitätsnachweis. Diese Revision setzt absichtlich keine unbelegten Universalmaße für Stege oder Öffnungen; sie müssen zum später angegebenen Düse-/Material-/Layer-Profil passen.

## 3. Verbindlicher Dimension Gate

Der Dimension Gate darf nur `PASS` sein, wenn alle bisherigen Hauptmaße und zusätzlich folgende Punkte erfüllt sind:

| ID | Prüfung | Soll |
|---|---|---|
| B-DIM-OUTLET-LENGTH | funktionale Auslauflänge | **50,000 mm** |
| B-DIM-OUTLET-OPEN | Auslauf über die gesamte funktionale Länge oben offen | **ja** |
| B-DIM-GRID-PRESENT | Gitterauflagen vorhanden | **ja – Bürste, Schwamm und Flasche** |
| B-DIM-CHANNEL-WIDTH | minimale/maximale lichte Kanalbreite gemessen | Wert + Position dokumentiert |
| B-DIM-GRID-GEOMETRY | Steg-/Öffnungsmaße pro Nutzungszone gemessen | vollständig dokumentiert |

`50 mm` ist ein Konstruktionsmaß, keine ungefähre Designabsicht. Eine spätere Fertigungstoleranz darf separat behandelt werden, ändert aber nicht das CAD-Sollmaß.

## 4. Verbindlicher Function Gate

### 4.1 Wasserablauf

`PASS` erfordert:

- Wasser kann von jeder Gitterzone nach unten in die Auffang-/Drainagegeometrie gelangen;
- von dort besteht ein zusammenhängender Wasserpfad bis zum Auslaufende;
- die Rinne ist über ihre gesamte funktionale Länge oben offen und frei;
- keine Tasche, Sackgasse oder unentwässerte lokale Senke;
- der vorgesehene Spülenrand-Anstieg und der anschließende freie Auslauf sind geometrisch nachgewiesen.

### 4.2 Nutzung

`PASS` erfordert:

- Bürste, Schwamm und Spülmittelflasche nutzen jeweils eine gitterartige Auflage;
- die Gegenstände werden durch reale Stege/Flächen unterstützt, nicht nur in Renderings angedeutet;
- Stabilität, Kippneigung und Kontaktfläche werden mit dokumentierten Referenzhüllen geprüft;
- Drainageöffnungen bleiben bei aufgelegtem Gegenstand funktional ausreichend verbunden.

### 4.3 Fertigbarkeit

`PASS` erfordert außerdem:

- technisch sauberer, slicbarer Solid;
- FDM-taugliche Gitterstege und Brückenspannen bezogen auf das dokumentierte Druckprofil;
- keine geschlossenen Restvolumen oder eingeschlossenen Wasserfallen;
- STL-/3MF-Roundtrip ohne Verlust der offenen Rinne oder Gitterdurchbrüche.

## 5. Verbindliche Berichtsartefakte

Jeder Benchmark‑B-Kandidat liefert mindestens:

- `DIMENSION-REPORT.md` und maschinenlesbare Messwerte;
- `FUNCTION-REPORT.md` mit Drainage- und Stabilitätsnachweisen;
- Draufsicht und Längsschnitt der offenen Auslaufrinne;
- Querschnitte an minimaler und maximaler Kanalbreite;
- Detailansicht jeder Gitterzone;
- visualisierten zusammenhängenden Wasserpfad von allen drei Zonen bis zum Auslaufende;
- STL-/3MF-/Slicer-Gate;
- SHA-256-Artefaktmanifest.

Der aktuelle Status bleibt `NOT EVALUATED`, bis ein reales Benchmark‑B-CAD/Mesh gegen diese Gates geprüft wurde.
