# TASK – PETG-Bettklammer für Filztasche – R01

Status: **KONSTRUKTIONSAUFTRAG / TESTREVISION**
Quelle: Nutzerfreigabe vom 2026-08-29
GitHub Issue: #1

## Auftrag

Konstruiere eine erste druckbare Testrevision **R01** einer PETG-Klammer, die eine Filztasche über der oberen Chromkante eines Bett-Kopfteils hält.

## VERBINDLICH – vom Nutzer vorgegeben / bestätigt

- Material: **PETG**
- Klammerbreite: **20 mm**
- Schenkellänge / Gesamthöhe: **40 mm von ganz oben nach ganz unten** der Klammer
- Material-/Wandstärke: **2,0 mm**
- Bettprofil / Chromleiste: **20,0 mm tief** – vom Nutzer gemessen/bestätigt
- Filzdicke an der Klemmstelle: **2,0 mm** – vom Nutzer gemessen/bestätigt
- Vorhandener Chromüberstand gegenüber der angrenzenden Bettfläche: **2,0 mm** – vom Nutzer gemessen/bestätigt
- Der 2,0-mm-Chromüberstand sitzt **direkt oben an der Chromleiste** und läuft dort als **rechteckige Kante** entlang; Ansicht von vorne rechteckig – vom Nutzer bestätigt
- Grundprinzip: federnde, von oben aufgeschobene **U-Klammer** über Chromprofil + Filz
- Der vorhandene 2,0-mm-Chromüberstand dient als Haltepunkt für die Widerhaken/Zacken.
- Die Zacken sitzen auf der **langen Innenseite des betreffenden Klammerschenkels**.
- Ausführung der Zacken: **viele kleine, direkt aneinandergereihte Zacken / eine feine Verzahnung**, nicht wenige weit auseinanderliegende Einzelzacken.
- Keine zusätzlichen Funktionen, Halterungen, Führungen oder Befestigungsprinzipien ergänzen.

## TECHNISCH NOTWENDIG

- Die lichte Aufnahme muss **20,0 mm Chromprofil + 2,0 mm Filz** aufnehmen.
- Die ursprünglich genannten 20 mm Tiefe dürfen deshalb NICHT als fertige lichte Innenweite oder zwingendes Außenmaß interpretiert werden.
- Nur das technisch notwendige Montagespiel für PETG/FDM ergänzen. Den tatsächlich gewählten Wert dokumentieren und ausdrücklich als technisch festgelegt kennzeichnen.
- Übergang über den Klammerbogen mit belastungsgerechten Radien ausführen; keine scharf belastete 90°-Innenecke.
- Die feine Verzahnung auf der langen Innenseite so ausrichten, dass sie beim Aufschieben über den vorhandenen **2,0-mm-Chromüberstand** gleiten kann und gegen Abziehen nach oben greift.
- Zahnfüße verrunden bzw. konstruktiv so auslegen, dass keine unnötige Kerbwirkung entsteht.
- PETG-Federwirkung und Belastung des Klammerbogens prüfen.
- Druckorientierung so festlegen, dass die Federwirkung nicht unnötig durch ungünstige Layerorientierung geschwächt wird.

## TECHNISCHE FESTLEGUNG DURCH CHATGPT – IM RAHMEN DER NUTZERVORGABE

- Die bisherige Ausführung mit nur vier Einzelzacken auf diskreten Höhen ist **nicht mehr zulässig**.
- R01 soll eine **kleine, regelmäßig aneinandergereihte Verzahnung entlang der langen Innenseite** erhalten.
- Exakte Zahnsteigung, Zahnhöhe und Anzahl dürfen technisch so gewählt werden, dass die Verzahnung mit PETG/FDM zuverlässig druckbar bleibt und die bestätigten Produktmaße/Funktionen unverändert bleiben.
- Diese Detailwerte sind im SOLL/IST-Bericht als **technisch festgelegt** zu dokumentieren.

## GEOMETRISCHE KLÄRUNG VOM 2026-08-29

Die zuvor offenen Geometriepunkte sind durch den Nutzer geklärt:

- Gesamthöhe der Klammer: **40 mm von ganz oben bis ganz unten**.
- Horizontaler Chromüberstand: **2,0 mm**.
- Lage: Überstand **direkt oben an der Chromleiste**.
- Form: **rechteckige, gerade Kante**; keine schräge oder gerundete Sonderkontur vorgegeben.
- Verzahnung: **auf der langen Innenseite, klein und direkt aneinandergereiht**.

Für diese Punkte besteht kein STOPP-Grund mehr. Sollte bei der tatsächlichen CAD-Konstruktion eine **andere, bisher nicht benannte** konstruktiv relevante Information fehlen, gilt weiterhin die STOPPREGEL; nicht raten.

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
5. Zahnanzahl, Zahnsteigung, Zahnhöhe/Eingriff und Orientierung der feinen Verzahnung,
6. kurze FDM-/PETG-Prüfung inklusive empfohlener Druckorientierung,
7. Revisionseintrag mit **GEÄNDERT / UNVERÄNDERT / ENTFERNT / OFFEN**,
8. klare Trennung von **VERBINDLICH / TECHNISCH NOTWENDIG / OFFEN**.

## STOPPREGEL

Wenn eine konstruktiv relevante Information nicht aus diesen bestätigten Angaben oder der realen Geometrie eindeutig ableitbar ist: **nicht raten**. Punkt als OFFEN markieren und beim Nutzer nachfragen.

Keine stillen Nebenänderungen und keine zusätzlichen Features.