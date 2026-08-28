# Laufzeitreport – Full-Model Fast-Path 0,5 mm

Status: **PASS / CANDIDATE / NON-MASTER**  
Messdatum: 2026-08-25  
Hardware: Ryzen/Windows-WSL-System mit 32 GB Host-RAM; WSL 24 GB; RX 7800 XT. Der Produktionspfad selbst ist CPU-basiert.

## Gemessener Kandidatenlauf

| Phase | Zeit |
|---|---:|
| Quelle laden und 19 Komponenten klassifizieren | 0,840 s |
| Zwei lokale Schwanzverbindungen erzeugen | 0,012 s |
| Oberflächen-Voxelisierung, 0,5 mm | 21,055 s |
| Binäre Solid-Rekonstruktion | 0,841 s |
| Mesh-Extraktion und Orientierung | 1,997 s |
| **Rekonstruktion gesamt** | **24,745 s** |
| Schnelle Topologie Arbeitsmesh | 13,468 s |
| Exakte Prüfung nichtbenachbarter Selbstschnitte/Kontakte | 215,548 s |
| STL-Roundtrip + Topologie | 16,084 s |
| 3MF-Roundtrip + Topologie | 19,006 s |
| 3 × 381 Layer-Loop-Prüfungen | 28,116 s |
| NPZ + STL + 3MF schreiben | 4,522 s |
| **Vollständiger Build + strenger Gate** | **323,238 s = 5:23 min** |

Peak-RAM: **6.986 GB dezimal / 6,507 GiB**. Die CPU-Zeit entsprach in den langen Phasen ungefähr einem voll ausgelasteten logischen Kern. GPU-Auslastung wurde nicht belastbar gemessen; Voxelisierung, Marching Cubes und CPU-Schnittprüfung sind CPU-Pfade. Die GPU wurde nur bei der späteren UDF-/Raster-QA verwendet.

Der exakte Selbstschnittvalidator beanspruchte **215,548 s bzw. 66,7 %** der Gesamtzeit. Ohne diesen Deep-Schritt hätte derselbe Build samt Export, Roundtrips, Topologie und Layer-Loops **107,690 s = 1:48 min** benötigt.

## Anycubic-Test

AnycubicSlicerNext 1.4.1.2 importierte das STL mit `--no-check` als manifold, ein Teil und 1.443.070 Facetten. Der erfolgreiche, profilgebundene Slice benötigte anhand der Dateizeitstempel **17,744 s**.

- Profil: Anycubic Kobra S1, 0,4-mm-Düse, 0,20-mm-High-Quality, Anycubic PLA
- 953 Layer, 0 Layer ohne positive Extrusion
- 1 Modellinstanz
- Max-Z: 190,60 mm
- G-code: 170.709.743 Bytes
- geschätzte Druckzeit: 22 h 37 min 10 s
- geschätzter Materialeinsatz: 348,57 g

Die G-code-Werte sind ein Slicer-Funktionstest, keine fertige Druckempfehlung; Support war im verwendeten Profil deaktiviert.

## Produktionsregel

Der derzeitige **Strict Fast Gate** liegt mit 5:23 min unter dem 10-Minuten-Limit. Für den späteren Normalmodus wird ein zweistufiges Gate empfohlen:

1. **Normal/Fast:** deterministische 0,5-mm-Rekonstruktion, vollständige Topologie, Format-Roundtrip, Dreiecksdigest und Layer-Loops. Zielwert mit diesem Modell: ca. **1:48 min**, plus optional ca. 18 s echter Slice.
2. **Deep:** exakte globale Nichtnachbarschaftsprüfung nur bei Fast-Gate-Fehler, Digest-Abweichung, ungewöhnlicher Geometrie, sichtbarem Fehler oder ausdrücklicher Maximalprüfung. Gemessener Aufpreis hier: ca. **3:36 min**.

Der vorliegende Kandidat wurde zur Freigabe trotzdem einmal vollständig mit dem exakten Deep-Schritt geprüft.
