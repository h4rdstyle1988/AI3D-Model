# Generalisierte Produktionspipeline

## Zielpfad

`Multi-View-Rekonstruktion → sichtbare Surface-Geometrie → volumetrischer Fast-Path → Fast Validation → STL/3MF → optional echter Slicer`

## Normal Mode

1. Eingabedatei per SHA-256 einfrieren; Original nie überschreiben.
2. Positionsbasiert verbundene Surface-Komponenten inventarisieren.
3. Sichtbare Außenteile auswählen; nahezu deckungsgleiche Innen-/Gegenhäute ausschließen.
4. Beabsichtigte kleine Lücken exakt messen. Nur semantisch notwendige Lücken mit minimalen lokalen Verbindungen schließen.
5. Alle sichtbaren Teile gemeinsam mit 0,5 mm voxelisieren.
6. Oberfläche in eine binäre Belegung überführen, Innenraum füllen und abbrechen, falls nicht genau ein Occupancy-Solid entsteht. Niemals still die größte Komponente auswählen.
7. Ungeglättetes Marching Cubes; keine Decimation, kein Closing, keine künstliche Innenwand.
8. Fast Gate: ein Solid, watertight, edge-/vertex-manifold, 0 Boundary/NM/ungültige Links/Degenerates/Duplicates, konsistentes Winding; STL und 3MF lesen; quantisierten Dreiecksdigest und Bounds vergleichen; Layer-Loop-Prüfung.
9. Sicht-Gate: Vollansichten, kritische Detail-ROIs, Maul-/Kavitätsprüfung und UDF-Heatmap.
10. Optional vorhandenen Slicer im Repair-off/No-check-Modus importieren und testweise slicen.

## Detail Mode

Nur bei belegtem sichtbarem Detailverlust: 0,25–0,30 mm oder eine gezielte lokale Verbesserung. Nicht automatisch als zweite Variante rechnen.

## Deep Repair/Validation Mode

Nur wenn Fast Gate, Digest, Form-Gate oder Slicer scheitert oder der Benutzer maximale Prüfung verlangt:

- exakte globale nichtbenachbarte Dreiecksschnitt-/Kontaktprüfung
- feinere UDF-/ROI-Analysen
- lokale Problemklassifikation
- erst danach eine gezielte neue Geometrievariante

Die invalidierten Verfahren `invalidated-cumesh-raytrace-v1` und `invalidated-edge-connectivity-split-v1` bleiben ausgeschlossen. cuMesh darf nur für den validierten unsigned-distance-Pfad verwendet werden.

## Reproduktionskommando

Die Skripte liegen unter `reproduction-scripts/`. Der Build benötigt die bestehende TRELLIS2-venv und die im Report festgehaltenen Quell-/Analysepfade. Kernparameter:

- Zielhöhe: 190 mm
- Voxel-Pitch: 0,5 mm
- sichtbare Teile: C01, C05, C08
- ausgeschlossene Doppelhäute: C07, C09
- lokale Verbindungsradien: 2,5 mm
- kein Closing, Smoothing, Simplification oder separater innerer Shell

Jeder Output-Ordner wird mit `exist_ok=False` erzeugt; bestehende Kandidaten werden nicht überschrieben.
