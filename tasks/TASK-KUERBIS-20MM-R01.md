# TASK-KUERBIS-20MM-R01

Status: VOM NUTZER FREIGEGEBEN
Datum: 2026-08-29

## VERBINDLICH
- Kleiner Kürbis, Außendurchmesser ca. 20 mm.
- Äußere Form entsprechend der im Chat vom Nutzer freigegebenen Darstellung: deutlich ausgeprägte Kürbisrippen und organische/strukturierte Außenhaut; ausdrücklich nicht nur glatt.
- Kurzer, leicht unregelmäßiger Stiel entsprechend der freigegebenen Darstellung.
- Kürbiskörper und Stiel werden in einem Druckvorgang gefertigt und bilden nach dem Druck ein zusammenhängendes Teil.
- Kürbiskörper und Stiel müssen im Slicer getrennt anwählbar sein, damit ihnen unterschiedliche Filamente/Farben zugewiesen werden können.
- Kürbiskörper: PLA Matt Desert Tan.
- Stiel: PLA Metal Kupfer.
- Düse: 0,4 mm.
- Feiner Druck.
- Kürbiskörper Wandstärke: 1,2 mm.
- Infill: 5 % Gyroid. Der Kürbis soll damit weitgehend hohl/nur wenig gefüllt sein; kein separat konstruierter CAD-Hohlraum erforderlich.
- Keine zusätzlichen Funktionen, Sockel, Halterungen, Ösen, Befestigungen, Führungen oder Anschläge ergänzen.

## DRUCKPARAMETER / SLICER-ZIEL
- Layerhöhe: 0,12 mm.
- Erste Schicht: 0,20 mm.
- Außenwände: 3.
- Top/Bottom: 4 Schichten.
- Außenwand-Geschwindigkeit: 30–40 mm/s.
- Kleine Perimeter/Stiel: 20–30 mm/s.
- Support möglichst aus. Geometrie so auslegen, dass normale Druckorientierung auf der Kürbisunterseite ohne kritischen Support funktioniert.
- Brim zunächst aus.
- Naht möglichst hinten bzw. in einer Rippenvertiefung.
- Variable Layerhöhe ist im oberen Kürbisbereich und am Stiel sinnvoll.
- Der kleine Stiel muss nicht künstlich hohl sein und darf slicerbedingt weitgehend oder vollständig massiv werden, damit er stabil bleibt.

## TECHNISCH NOTWENDIG
- Sichere, druckbare Verbindung zwischen Kürbiskörper und Stiel herstellen, ohne die freigegebene äußere Gestaltung unnötig zu verändern.
- Körper und Stiel so strukturieren/exportieren, dass getrennte Materialzuweisung im Slicer möglich bleibt, während das Druckergebnis ein zusammenhängendes Teil ist.
- FDM-Tauglichkeit mit 0,4-mm-Düse prüfen.
- Außenstruktur muss bei nur ca. 20 mm Gesamtgröße tatsächlich druckbar und sichtbar bleiben.

## VALIDIERUNG VOR ERGEBNISRÜCKGABE
- tatsächlichen Außendurchmesser dokumentieren;
- Wandstärke 1,2 mm prüfen;
- Verbindung Körper/Stiel prüfen;
- getrennte Materialzuweisbarkeit prüfen;
- Mesh/Geometrie auf Manifold/Watertight bzw. für den vorgesehenen Mehrkörper-Export korrekte Slicer-Verarbeitung prüfen;
- Überhänge, Brücken und Supportbedarf prüfen;
- SOLL/IST-Bericht erstellen;
- keine stillen Nebenänderungen.

## FREIGABE-GATE
Die Konstruktion ist vom Nutzer freigegeben. Rüdiger darf Konstruktion und technische Validierung selbstständig durchführen. Eine technisch valide Datei ist noch keine finale Produktfreigabe. Vor Erstellung/Verwendung endgültiger Druckdateien gilt der etablierte Nutzer-Freigabeprozess.

NUTZERENTSCHEIDUNG_ERFORDERLICH nur bei einem echten Konflikt gemäß AGENTS.md; technische CAD-/Mesh-/Toolchain-Probleme selbstständig lösen.