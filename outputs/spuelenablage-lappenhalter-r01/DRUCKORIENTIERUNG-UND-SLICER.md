# DRUCKORIENTIERUNG UND SLICER-STARTWERTE – spuelenablage-lappenhalter-r01

## Empfohlene Orientierung

**Seitlich liegend: lokale Y-Richtung (12-mm-Breite) wird Drucker-Z.** Die lange X-Z-Seitenkontur liegt auf dem Bett.

- Layer-Richtung: Die Gebrauchslast biegt den Arm hauptsächlich in der lokalen X-Z-Ebene. In Seitenlage liegen Zug- und Druckpfad überwiegend innerhalb der Layerflächen; eine Trennebene quer durch den Arm wird vermieden.
- Support: Durch den unveränderten Sechskant (10,277 mm Eckmaß) und den neuen 12-mm-breiten Arm liegt der Zapfen in dieser Orientierung nominell 0,862 mm oberhalb der Arm-Auflageebene. Deshalb ist **kleiner lokaler Support nur unter dem Zapfen** technisch sauberer als eine schwächere Orientierung. Er ist außen vollständig zugänglich und entfernbar. Kein Support im Anschlussbogen oder unter dem 90-mm-Arm.
- Oberfläche/Maßhaltigkeit: Der Support berührt die Sechskantspitze, nicht die beiden für die 8,90-mm-Schlüsselweite maßgebenden x-Flächen. Supportabstand und erste Schicht mit einem Kalibrierteil prüfen; das CAD-Maß bleibt unverändert.
- Supportfrei wurde geprüft, aber wegen des schwebenden Zapfens nicht als Startpunkt gewählt. Die mechanisch sinnvolle Seitenlage bleibt erhalten.

## Slicer-Startwerte für PETG / 0,4 mm

- Schichthöhe: **0,20 mm** (0,24 mm erst nach stabilem Ersttest).
- Wände/Perimeter: **5**; im kleinen Anschluss entsteht dadurch lokal nahezu Vollmaterial.
- Infill: **30 % Gyroid**; alternativ Cubic im Bereich 25–35 %.
- Top/Bottom: mindestens **5 Schichten**.
- Support: nur vom Druckbett, lokal unter dem Sechskantzapfen; keine schwer zugänglichen Supports. Interface und Z-Abstand nach PETG-/Druckerprofil.
- 100 % Infill: **nicht empfohlen**, weil der wesentliche Gewinn aus Querschnitt, tangentialem Anschluss, fünf Wänden und Orientierung kommt.
- Temperatur, Lüfter, Flow und Retract: freigegebenes Profil des konkreten PETG-Herstellers verwenden; diese Werte sind ohne Filament-/Druckerangabe nicht belastbar festgelegt.
