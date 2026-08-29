# TASK-INFRA-R03-8-LOCAL-GENERATED-WRITE

Status: TECHNISCH FREIGEGEBEN
Datum: 2026-08-29

## ZIEL
Rüdigers Codex-Lauf soll zusätzlich zum Worker-Verzeichnis den lokalen Ausgabeordner `D:\3D-Models\generated` im `workspace-write`-Sandbox beschreiben dürfen, damit freigegebene Druckdateien ohne manuellen PowerShell-Schritt lokal bereitgestellt werden können.

## VERBINDLICH
- Nur Infrastruktur ändern, keine Produktgeometrie oder Produkt-Tasks verändern.
- Watcher-Version von R03.7 auf R03.8 erhöhen.
- Bestehenden Sandbox-Modus `workspace-write`, `--ask-for-approval never`, `--skip-git-repo-check` und `-C "$WorkerDir"` beibehalten.
- Für Codex-Läufe zusätzlich `--add-dir "D:\3D-Models\generated"` setzen.
- Vor Start eines Codex-Laufs sicherstellen, dass `D:\3D-Models\generated` als Verzeichnis existiert. Nur dieses Verzeichnis anlegen; keine weiteren Ordner/Funktionen erfinden.
- Keine Lockerung auf `danger-full-access`, kein `--dangerously-bypass-approvals-and-sandbox`.
- Bestehende R03.7 Push-Retry-Logik unverändert erhalten.
- Bestehende Queue-, Live-Status-, Self-Update-, Lock- und Preflight-Logik schützen.

## VALIDIERUNG
- PowerShell-Syntaxprüfung PASS.
- Im Diff nur technisch notwendige Watcher-Änderungen.
- Nachweis im Bericht, dass `--add-dir "D:\3D-Models\generated"` im Codex-Aufruf enthalten ist.
- Kein Produktfile ändern.
- Ergebnisbranch normal remote verifizieren.

## HINWEIS
Der bestehende Kürbis-R01-Print-Release ist bereits byte-identisch validiert. Dieses Task behebt ausschließlich den Sandbox-Zugriff auf den lokalen Ausgabeordner.

NUTZERENTSCHEIDUNG_ERFORDERLICH: false
