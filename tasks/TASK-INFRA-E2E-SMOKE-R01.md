# TASK – Infrastruktur Ende-zu-Ende Smoke-Test – R01

Status: **INFRASTRUKTUR-TEST**

## Ziel

Den neuen lokalen D:-Watcher einmal real Ende-zu-Ende validieren: Fetch -> Task-Erkennung -> Codex -> Dateiänderung -> Commit -> Push -> Remote-Verifikation.

## VERBINDLICH

- Keine Produktgeometrie ändern.
- Keine bestehenden Produktdateien ändern.
- Keine Systeminstallation durchführen.
- Keine Daten auf C: löschen, verschieben oder verändern.
- Nur einen kleinen Infrastruktur-Testnachweis erzeugen.

## AUSFÜHRUNG

1. Lies `AGENTS.md`.
2. Prüfe, dass der Lauf im dedizierten Worker erfolgt.
3. Erzeuge ausschließlich die Datei `outputs/infrastructure/E2E-SMOKE-R01.md` mit:
   - Zeitstempel
   - erkannter Task-Pfad
   - kurzer Aussage, dass der Codex-Lauf im Worker erfolgreich gestartet wurde
   - Status `PASS` für den Codex-Arbeitsschritt
4. Keine weiteren Dateien ändern, außer wenn technisch zwingend für diesen Test.
5. Keine finale Freigabe behaupten.

## ERWARTETES ERGEBNIS

Der Watcher soll anschließend selbst committen, den Ergebnisbranch pushen und den Remote-Commit verifizieren.
