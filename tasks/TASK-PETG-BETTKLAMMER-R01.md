# TASK – PETG-Bettklammer für Filztasche – R01

Status: **KONSTRUKTIONSAUFTRAG / TESTREVISION**
Quelle: Nutzerfreigabe vom 2026-08-29
GitHub Issue: #1

## Auftrag

Konstruiere eine erste druckbare Testrevision **R01** einer PETG-Klammer, die eine Filztasche über der oberen Chromkante eines Bett-Kopfteils hält.

## VERBINDLICH – vom Nutzer vorgegeben / bestätigt

- Material: **PETG**
- Klammerbreite: **20 mm**
- Schenkellänge: **40 mm**
- Material-/Wandstärke: **2,0 mm**
- Bettprofil / Chromleiste: **20,0 mm tief** – vom Nutzer gemessen/bestätigt
- Filzdicke an der Klemmstelle: **2,0 mm** – vom Nutzer gemessen/bestätigt
- Grundprinzip: federnde, von oben aufgeschobene **U-Klammer** über Chromprofil + Filz
- Die Chromleiste steht auf der Bettseite leicht über. Dieser vorhandene Überstand dient als Haltepunkt für die Widerhaken/Zacken.
- **Mehrere Zacken/Widerhaken** vorsehen, damit die Haltewirkung verteilt wird und die Klammer nicht unnötig stark überdehnt werden muss.
- Keine zusätzlichen Funktionen, Halterungen, Führungen oder Befestigungsprinzipien ergänzen.

## TECHNISCH NOTWENDIG

- Die lichte Aufnahme muss **20,0 mm Chromprofil + 2,0 mm Filz** aufnehmen.
- Die ursprünglich genannten 20 mm Tiefe dürfen deshalb NICHT als fertige lichte Innenweite oder zwingendes Außenmaß interpretiert werden.
- Nur das technisch notwendige Montagespiel für PETG/FDM ergänzen. Den tatsächlich gewählten Wert dokumentieren und ausdrücklich als technisch festgelegt kennzeichnen.
- Übergang über den Klammerbogen mit belastungsgerechten Radien ausführen; keine scharf belastete 90°-Innenecke.
- Zacken auf der Bettseite so ausrichten, dass sie beim Aufschieben über den vorhandenen Chromüberstand gleiten können und gegen Abziehen nach oben greifen.
- Zahnfüße verrunden, um Kerbwirkung zu reduzieren.
- PETG-Federwirkung und Belastung des Klammerbogens prüfen.
- Druckorientierung so festlegen, dass die Federwirkung nicht unnötig durch ungünstige Layerorientierung geschwächt wird.

## TECHNISCHER STARTVORSCHLAG – NICHT NUTZERVERBINDLICH

Für R01 als Ausgangspunkt:

- **3–4 kleine Zacken/Widerhaken**
- Eingriff ungefähr **0,8–1,2 mm**
- verrundeter Zahnfuß

Diese Werte sind technische Vorschläge. Falls die CAD-/FDM-Prüfung eine Abweichung erforderlich macht, begründen und dokumentieren; keine stillen Änderungen.

## ZIEL VON R01

R01 ist ausdrücklich ein **kleiner, materialarmer Passungs- und Funktionstest am realen Bett**.

R01 darf NICHT als final freigegeben bezeichnet werden, nur weil:
- STL erzeugt wurde,
- Mesh watertight ist,
- Maße formal stimmen oder
- ein Validator PASS meldet.

Die finale Freigabe erfolgt ausschließlich durch den Nutzer nach realem Test.

## AUSGABE

Erzeuge und dokumentiere:

1. parametrische Quelldatei / reproduzierbaren CAD-Konstruktionsstand,
2. STL der Testrevision R01,
3. SOLL/IST-Maßbericht,
4. tatsächlich gewählte lichte Innenweite und Montagespiel,
5. Zahnanzahl, Zahnhöhe/Eingriff und Orientierung,
6. kurze FDM-/PETG-Prüfung inklusive empfohlener Druckorientierung,
7. Revisionseintrag mit **GEÄNDERT / UNVERÄNDERT / ENTFERNT / OFFEN**,
8. klare Trennung von **VERBINDLICH / TECHNISCH NOTWENDIG / OFFEN**.

## STOPPREGEL

Wenn eine konstruktiv relevante Information nicht aus diesen bestätigten Angaben oder der realen Geometrie eindeutig ableitbar ist: **nicht raten**. Punkt als OFFEN markieren und beim Nutzer nachfragen.

Keine stillen Nebenänderungen und keine zusätzlichen Features.