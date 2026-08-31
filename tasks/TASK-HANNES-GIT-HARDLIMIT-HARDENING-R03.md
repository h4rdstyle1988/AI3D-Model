# TASK-HANNES-GIT-HARDLIMIT-HARDENING-R03

## Status
Freigegebener rein technischer Workflow-Fix. Keine Produktgeometrie aendern.

## Benennung – verbindlich
Der Watcher/Workflow-Agent heisst ab jetzt **Hannes**.

Bestehende technische Dateinamen, Scheduler-Tasknamen oder Branchnamen duerfen aus Kompatibilitaetsgruenden unveraendert bleiben, wenn eine Umbenennung Risiken erzeugt. Nutzerseitige Statusmeldungen, neue Dokumentation und neue maschinenlesbare Namensfelder sollen jedoch `Hannes` verwenden.

Begruendung fuer die Namenswahl ist keine technische Anforderung und soll nicht in Codekommentare eingebaut werden.

## Nachgewiesenes Problem
R16 konnte trotz fertigem lokalem Ergebnis nicht nach GitHub gepusht werden, weil mehrere PLY-Zwischen-/Masterdateien das GitHub-Einzeldatei-Hardlimit von 100 MB ueberschritten. Der alte Workflow versuchte den Push wiederholt, statt den Hardlimit-Fehler vor dem Push zu erkennen.

## Auftrag
Haerte Hannes so, dass grosse lokale CAD-/Mesh-Artefakte den Workflow nicht erneut blockieren.

## Verbindliche Anforderungen
1. Vor Ergebnis-Commit/Push alle neu hinzukommenden bzw. taskbezogenen Dateien auf GitHub-Einzeldateigroesse pruefen.
2. Sicherheitsgrenze fuer normale Git-Artefakte: 90 MB.
3. Dateien >90 MB duerfen nicht stillschweigend gepusht werden.
4. Temporaere/diagnostische Grossartefakte duerfen automatisiert ausserhalb des Repositories unter `D:\3D-Models\generated\_ruediger-local-large-artifacts\<task>` gesichert und aus dem Git-Ergebnis entfernt werden, **nur wenn** sie nicht als verbindliche finale Nutzerdatei gefordert sind.
5. Fuer ausgelagerte Dateien Manifest erzeugen: Originalpfad, lokaler Pfad, Groesse, SHA-256, Grund der Auslagerung.
6. Ist eine >90-MB-Datei eine verbindliche finale Ausgabe, darf sie nicht stillschweigend entfernt werden. Dann technisch verlustfreie/reproduzierbare kleinere Austauschdarstellung erzeugen, sofern ohne Produktveraenderung moeglich; andernfalls klarer technischer STOPP mit Dateipfad/Groesse.
7. GitHub-Hardlimit vor Push erneut pruefen. Kein Push starten, solange >100-MB-Dateien im zu pushenden Commit enthalten sind.
8. Push-Retries bleiben begrenzt; lokales Ergebnis bleibt erhalten.
9. Keine Aenderung an Produktlogik, Nutzerfreigaben oder CAD-Anforderungen.
10. Hannes-Status soll einen expliziten maschinenlesbaren Agentennamen enthalten, z. B. `agent_name: "Hannes"`.
11. Watcher-Version hochzaehlen.
12. Syntax-/Smoke-Test und gezielter Hardlimit-Selbsttest dokumentieren.
13. GEÄNDERT / UNVERÄNDERT / ENTFERNT / OFFEN dokumentieren.

## Zielverhalten
- Ergebnisdateien <=90 MB -> normal committen/pushen/verifizieren.
- nicht finale Grossartefakte >90 MB -> lokal sichern + Manifest -> nicht in Git pushen.
- verbindliche finale Grossdatei -> reproduzierbare kleinere Austauschdarstellung oder technischer STOPP; niemals stilles Entfernen.
- keine Endlosschleife bei GitHub GH001.

Keine finale Nutzerfreigabe behaupten.
