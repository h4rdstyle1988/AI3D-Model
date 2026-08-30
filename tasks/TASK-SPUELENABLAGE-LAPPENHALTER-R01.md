# TASK-SPUELENABLAGE-LAPPENHALTER-R01

Status: FREIGEGEBEN
Datum: 2026-08-30

## ZIEL
Robuste Revision des bereits bekannten Lappenhalters fuer die Spuelenablage. Der Halter steckt mit genau einem geraden Sechskantzapfen in eine vorhandene Wabe und traegt einen nassen/gut feuchten Lappen. Der vorherige Entwurf brach bereits bei leichtem Biegetest mit kaum Widerstand. Ursache technisch analysieren und gezielt beheben.

## VERBINDLICH – UNVERAENDERT
- Genau 1 Steckpunkt in eine bestehende Sechskant-Wabe.
- Sechskantzapfen: 8,90 mm Schluesselweite; dieses Mass NICHT aendern.
- Stecklaenge: 18,0 mm.
- Gerade Steckgeometrie; NICHT konisch.
- Keine Rastung, kein Clip, keine Klemmnase, keine zweite Fuehrung, keine Magnete.
- Ausladung des Halters zur Spuele: 90 mm.
- Material: PETG.
- FDM-Druck, 0,4-mm-Duese.
- Keine separate Basis oder Zusatzfunktion.
- Halter soll einen gut feuchten, nicht tropfenden Lappen tragen.

## VERBINDLICH – GEAENDERT
- Der Halter muss deutlich stabiler als der vorherige Entwurf werden.
- Buegel-/Armquerschnitt: 12 x 10 mm statt bisher 10 x 8 mm.
- Uebergang Sechskantzapfen -> Arm lastgerecht, weich und integriert ausformen.
- Keine scharfe Kerbe und kein abrupter Querschnittssprung im hoch belasteten Anschluss.
- Optisch keine aufgesetzten Verstarkungskloetze/Wuelste; Verstarkung soll aus einem Guss wirken.

## BRUCHURSACHE / KONSTRUKTIONSPRUEFUNG
Vor Freigabe bewerten:
1. Liegt der bisherige Bruch plausibel an zu geringem Querschnitt, Kerbwirkung, Layerorientierung oder Kombination daraus?
2. Kraftfluss vom Arm in den Sechskantzapfen konstruktiv nachvollziehen.
3. Kritischen Querschnitt dokumentieren.
4. Keine reine "100-Prozent-Infill-loest-alles"-Loesung verwenden; Geometrie und Druckorientierung zuerst korrekt auslegen.

## DRUCKORIENTIERUNG
Der vorherige Halter wurde seitlich gedruckt, um ohne Support auszukommen. Diese Orientierung ist zu pruefen und beizubehalten, WENN sie zugleich fuer die Biegebelastung mechanisch sinnvoll ist.

Ruediger muss die endgueltige Orientierung dokumentieren und begruenden anhand:
- Layer-Richtung zur erwarteten Biegebelastung,
- Supportbedarf,
- erreichbarer/entfernbarer Support,
- Oberflaeche und Masshaltigkeit des Sechskantzapfens.

Supportfrei bevorzugt, aber nicht auf Kosten der Festigkeit.

## SLICER-EMPFEHLUNG / TECHNISCHER STARTPUNKT
Fuer PETG / 0,4 mm als Startpunkt pruefen und dokumentieren:
- 4 bis 5 Perimeter/Waende,
- 25 bis 35 Prozent Infill,
- Gyroid oder Cubic,
- kleiner hoch belasteter Anschluss darf durch die Wandzahl lokal nahezu Vollmaterial werden.

100 Prozent Infill ist NICHT verbindlich und nur zulaessig, wenn Ruediger technisch begruendet, dass es gegenueber der obigen Loesung einen relevanten Vorteil bringt.

## PASSUNG
Die reale Passung des 8,90-mm-Sechskants wurde noch nicht praktisch getestet, weil der alte Halter schon beim Biegetest brach. Deshalb:
- 8,90 mm unveraendert lassen.
- Keine eigenmaechtige Anpassung Richtung strammer/lockerer.
- Fuer die bestehende Spuelenablage muss die Steckwabe weiterhin mindestens ca. 18,5 bis 19 mm freien axialen Raum fuer den 18-mm-Zapfen besitzen.
- Passungsoptimierung ist erst nach realem Stecktest eine spaetere, getrennte Revision.

## AUSGABEN
1. Reproduzierbare CAD-/Quellgeometrie.
2. STL: `spuelenablage-lappenhalter-r01.stl`
3. Render/Preview aus der tatsaechlichen finalen Geometrie mindestens:
   - 3/4-Ansicht,
   - Seitenansicht,
   - Ansicht auf Steckzapfen und Uebergang.
4. SOLL/IST-Report.
5. Maschinenlesbarer Validierungs-/Revisionsreport.
6. Empfohlene Druckorientierung und Slicer-Startwerte dokumentieren.

## VALIDIERUNG
- STL watertight / 2-manifold.
- Keine Selbstueberschneidungen, offenen Kanten oder doppelten Schalen.
- Sechskant-Schluesselweite CAD-gemessen exakt 8,90 mm.
- Stecklaenge CAD-gemessen exakt 18,0 mm.
- Ausladung CAD-gemessen 90 mm.
- Armquerschnitt 12 x 10 mm an der definierten geraden Hauptsektion.
- Anschluss ohne geometrische Kerbstelle/abrupten Sprung.
- Druckorientierung hinsichtlich Layer-Belastung und Support pruefen.
- Keine unzugaenglichen Supports.
- Keine zusaetzlichen Funktionen oder Befestigungen.

## REVISIONSDOKUMENTATION
GEAENDERT:
- Arm von 10 x 8 mm auf 12 x 10 mm.
- Anschlussbereich gezielt auf Biegefestigkeit optimieren.

UNVERAENDERT:
- 8,90-mm-Sechskant.
- 18,0-mm-Stecklaenge.
- 90-mm-Ausladung.
- 1 Steckpunkt.
- PETG / 0,4 mm.
- keine Konizitaet/Rastung/Zusatzfuehrung.

ENTFERNT:
- Nichts.

OFFEN:
- Reale Steckpassung nach erstem stabilen Testdruck.
- Finale Produktfreigabe durch den Nutzer nach SOLL/IST und physischem Test.
