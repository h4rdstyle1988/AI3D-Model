# FDM-/PETG-Prüfung – R01

## Druckorientierung

- **Klammer:** auf einer 20 × 40-mm-Seitenfläche liegend. Dadurch verlaufen die Schichten über die 20-mm-Breite, der U-Bogen wird ohne inneren Support aufgebaut und die Federarme werden nicht als zwei nur schwach in Z verbundene Säulen gedruckt.
- **Nubsi:** aufrecht auf der ebenen Schaftunterseite, Schaftachse in Z. Der 3-mm-Radius bietet eine kleine, aber ebene Aufstandsfläche; bei Bedarf ist ein Slicer-Brim zulässig, ohne das CAD zu verändern.
- **Gemeinsamer Stand:** beide Orientierungen sind bereits in der Platten-STL enthalten; Mindestabstand 10,0 mm.

## PETG-/FDM-Bewertung

- Klammerwand 2,0 mm ist bei typischer 0,4-mm-Düse als fünf Linienbreiten grundsätzlich sinnvoll abbildbar; tatsächliche Linienzahl hängt vom Slicerprofil ab.
- Der Innenbogen mit 11,2 mm Radius vermeidet die scharf belastete 90°-Innenecke.
- Die feinen 0,6-mm-Zähne sind druckbar, aber düsen-, Linienbreiten- und Kühlungsabhängig; reale Zahnwirkung und Oberflächenqualität sind R01-Prüfziele.
- Für die Klammerorientierung ist kein geometrisch notwendiger Support erkannt.
- Der Nubsi-Kopf bildet von Ø 6 mm auf Ø 11 mm eine Kopfunterseite mit radial 2,5 mm Ausladung. In aufrechter Orientierung kann diese als Überhang kritisch sein. Support ist slicerabhängig erreichbar und von außen entfernbar; alternativ muss der konkrete Slicer die Brücken-/Überhangfähigkeit bewerten. Die Geometrie wurde nicht zur Supportvermeidung verfälscht.
- Der Schaft wurde trotz möglicher realer Passungskorrektur exakt Ø 6,0 mm belassen. Eine Maßkompensation ist **OFFEN nach realem Passungstest**, nicht Bestandteil R01.

## Lokale Toolchain

- Reproduzierbare ASCII-STL-Erzeugung: ausgeführt.
- Topologieprüfung: ausgeführt; beide Einzelteile ohne degenerierte Dreiecke und ohne Kantenbelegung ungleich zwei.
- Gemeinsamer Stand: topologisch geschlossen, zwei getrennt erzeugte Körper, 10,0 mm Abstand.
- Slicer-/G-Code-Test: **OFFEN / lokal nicht ausführbar**, da weder OpenSCAD/FreeCAD noch ein CLI-Slicer und auch keine lokale Python-Laufzeit verfügbar waren. Dies ist kein Geometrie-STOPP, aber ein realer Slice muss vor dem Druck im vorgesehenen Slicer geprüft werden.

Technischer Mesh-PASS ersetzt weder realen Druck noch Nutzerfreigabe.
