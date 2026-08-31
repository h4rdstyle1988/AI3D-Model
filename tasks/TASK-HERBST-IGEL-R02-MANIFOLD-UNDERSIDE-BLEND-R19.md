# TASK – Herbst-Igel R02 – Manifold Underside Blend R19

Status: freigegebener rein technischer Folgeauftrag nach R18 Gate-1/Gate-2-FAIL.
NUTZERENTSCHEIDUNG_ERFORDERLICH: false

## Verbindliche Produktbasis
Unverändert aus der zuletzt bestätigten R02-Spezifikation: ca. 200 mm Gesamtgröße proportional; genau 2 Druckteile; Front/Körper PLA Matt Desert Tan, Rücken/Stachelschale PLA Metal Kupfer; beide hohl nominal 1,6 mm; REF-SEAM maßgeblich; Gesicht frei; genau ein sichtbares Ahornblatt; zentraler interner Klebeverbinder Ø10,0 mm exakt, 20,0 mm Eingriff exakt; 0,4-mm-Düse, Ziel 0,12 mm Layer, adaptiv bis 0,08 mm zulässig. Keine neuen Funktionen, Sockel, Halter, Führungen oder Anschläge.

## Aktuelle Nutzerpräzisierung Formschutz
Sauberkeit hat Vorrang vor millimetergenauer optischer Kopie. Kleine Abweichungen zur Referenz sind zulässig, wenn Charakter, Grundform und Gesamtwirkung erhalten bleiben. Nicht zulässig sind sichtbare Einschläge, Löcher, Narben, Läufer, Stufen, raue Flickstellen, verschmiertes Relief oder sonstige Rekonstruktionsartefakte.

## Ausgangslage R18
R18 ist STOPP: ausgewählter Diagnosekandidat Gate 1 FAIL und Gate 2 FAIL. Der Blocker ist technisch: lokale Unterseitensurgery erzeugt Übergangsrippen/Topologiefehler bzw. übernimmt MLS-Rauheit. Keine Nutzerangabe fehlt.

## Ziel R19
Eine einzige saubere, orientierte, watertight, 2-manifold Außenhaut erzeugen, wobei optisch gute Seed-42-Außenflächen außerhalb einer streng begrenzten Unterseiten-ROI möglichst exakt erhalten bleiben. Die Unterseite separat neu schließen und den Übergang so konstruieren, dass weder sichtbare Kante/Ridge noch MLS-Rauheit noch tiefe Einschläge entstehen.

## Technische Leitplanken
1. Nicht erneut global rekonstruieren, wenn dadurch gute sichtbare Oberflächen verändert werden.
2. Außerhalb ROI gute Seed-42-Geometrie schützen/übernehmen; Änderungen dort nur technisch zwingend und dokumentiert.
3. Unterseiten-ROI aus realer R18-Fehlerkarte plus Sichtbarkeit/Normalen ableiten; ROI nicht unnötig vergrößern.
4. Für die Unterseite eine manifold Patch-Fläche mit gemeinsamer, eindeutig orientierter Grenzkurve erzeugen. Bevorzugt direkte Boundary-Loft/advancing-front/constrained surface patch oder technisch gleichwertig; keine freie MLS-Rauheit.
5. Übergangsring mit C0 zwingend und möglichst G1/Krümmungs-kontinuierlich; keine sichtbare Stufe. Geometrische Glättung nur im schmalen Übergangsband, nicht global.
6. Kleine saubere Vereinfachung des Unterseitenreliefs ist zulässig, wenn sie artefaktfrei ist und Charakter/Grundform nicht verändert.
7. Nach zwei klar fehlgeschlagenen Varianten Methode wechseln statt weiterzupatchen.
8. Vor Gate-3 keine Split-/Hohl-/Connector-Geometrie.

## Gate 1 – Topologie
PASS nur bei genau einer Außenkomponente, watertight, 2-manifold, 0 open edges, 0 non-manifold edges/vertices, keine eingeschlossenen Schalen, keine doppelten Flächen/Depth-Layer, keine realen Selbstschnitte.

## Gate 2 – Formschutz
Reale Geometrierender: 3/4 front, front, left, right, rear, top, bottom + Kontaktblatt und SOLL/IST. PASS/PASS MIT RESTPUNKTEN/FAIL dokumentieren.
Harte Kriterien: sauberer Gesamteindruck; keine Einschläge/Löcher/Narben/Läufer/Stufen/rauen Flickstellen; Gesicht frei; Augen/Nase/Ohren/Füße lesbar; Rücken-/Blattcharakter erhalten; genau ein sichtbares Ahornblatt; REF-SEAM plausibel. Kleine Formabweichung zur Referenz ist ausdrücklich zulässig, wenn sauber und stimmig.

## Gate 3 – CAD/FDM erst nach Gate 1 + Gate 2 PASS
Dann REF-SEAM-Split, 2 Hohlschalen nominal 1,6 mm, zentraler Klebeverbinder Ø10,0 mm exakt / 20,0 mm Eingriff exakt, Klebespiel dokumentieren, Druckorientierung/Support/Supportentfernbarkeit prüfen, STL + Assembly 3MF/GLB + technische Validierung erzeugen.

## Pflichtausgaben
Reproduzierbare Skripte/Quelle; GEÄNDERT/UNVERÄNDERT/ENTFERNT/OFFEN; Topologiebericht; Formschutz-/Delta-Bericht; reale Renderansichten inkl. Unterseiten-Nahaufnahme; REF-SEAM-Nachweis; machine-readable result-status. Keine finale Nutzerfreigabe behaupten.
