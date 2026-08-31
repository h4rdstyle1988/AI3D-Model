# TASK-WATCHER-PUSH-RETRY-FIX-R01

## Status
Freigegebener rein technischer Workflow-Fix. Keine Produktgeometrie aendern.

## Problem
Der Watcher R03.8 setzt nach erfolgreichem Codex-Lauf den Status auf `VALIDIERT` und ruft danach `Invoke-GitSafe` fuer den Ergebnis-Push auf. In `Invoke-GitSafe` werden Push-Fehler derzeit innerhalb einer unbeschraenkten Schleife immer wiederholt. Dadurch kann der Watcher dauerhaft in `VALIDIERT` haengen, ohne den echten Git-Fehler als `FEHLER_RETRY` zu publizieren. Genau dieses Verhalten wurde bei Herbst-Igel R16 beobachtet: lokales Ergebnis fertig, Remote-Branch fehlt, Live-Status bleibt auf `VALIDIERT`.

## Auftrag
Aendere ausschliesslich den Watcher-/Workflow-Code so, dass Push-Fehler begrenzt und transparent behandelt werden.

### Verbindliche Anforderungen
1. `Invoke-GitSafe` darf bei Pushes NICHT endlos intern wiederholen.
2. Fuer Pushes gilt die bereits uebergebene Retry-Grenze `Retries` verbindlich. Nach Erreichen dieser Anzahl muss `Invoke-GitSafe` mit einer aussagekraeftigen Exception abbrechen.
3. Die Exception muss die letzte echte Git-Fehlermeldung enthalten.
4. Der vorhandene aeussere Watcher-`catch` muss dadurch `FEHLER_RETRY` publizieren koennen.
5. Das lokale CAD-/Ergebnis-Commit darf bei Push-Fehlern nicht geloescht oder neu erzeugt werden.
6. `stale info`/`--force-with-lease` darf weiterhin technisch sinnvoll behandelt werden, aber auch diese Behandlung darf nicht zu einer Endlosschleife fuehren.
7. Keine Aenderung an Task-Selektion, Produktlogik, CAD-Auftraegen oder Nutzerfreigaben.
8. Watcher-Version hochzaehlen und Aenderung kurz dokumentieren.
9. Syntax-/Smoke-Test fuer den geaenderten PowerShell-Watcher durchfuehren.
10. Ergebnisstatus mit GEÄNDERT / UNVERÄNDERT / ENTFERNT / OFFEN dokumentieren.

## Zielverhalten
- Push PASS -> Remote verifizieren -> `FERTIG`.
- Push FAIL -> begrenzte interne Versuche -> Exception mit echtem Git-Fehler -> `FEHLER_RETRY` -> Hauptloop uebernimmt spaeteren Retry.
- Kein minuten-/stundenlanges scheinbares `VALIDIERT` ohne Fehlerursache.

Keine finale Nutzerfreigabe behaupten.
