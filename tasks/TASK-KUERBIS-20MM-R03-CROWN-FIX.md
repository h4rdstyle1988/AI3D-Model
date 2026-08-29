# TASK-KUERBIS-20MM-R03-CROWN-FIX

Status: TECHNISCHE KORREKTUR AUS SOLL/IST-PRUEFUNG
Datum: 2026-08-29

## AUSGANGSSTAND
- R02 wurde fuer mehr organische Form und Oberflaechendetail erzeugt.
- Ergebniscommit R02: `6a924eea20881c66c91c9deeb6f8577c1f96d821` auf Branch `ruediger/task-kuerbis-20mm-r02-detail-form-cb2ac484`.
- ChatGPT-Pruefung der tatsaechlichen R02-Geometrieformel hat einen klaren Formfehler ergeben: Die oberste Koerperring-Geometrie bleibt mit ca. Radius 4.2 bis 5.23 mm sehr breit und wird auf gleicher Z-Hoehe flach zum Mittelpunkt gekappt. Der Stiel ist dort deutlich schmaler. Dadurch entsteht sichtbar ein breites horizontales Plateau um den Stiel.
- Das widerspricht der verbindlichen R02-Forderung nach einer typischen organischen Kuerbisoberseite mit Einziehung um den Stiel und natuerlichem Verlauf.
- R01 und R02 bleiben unveraendert erhalten. Neue Revision: R03.

## VERBINDLICH – GEZIELT KORRIGIEREN
1. Nur die obere Kuerbiskrone / Einziehung um den Stiel korrigieren sowie technisch unmittelbar notwendige Folgegeometrie am Koerper-Stiel-Uebergang.
2. Das breite flache Plateau der R02-Krone entfernen.
3. Die acht Hauptlappen muessen bis in die obere Krone organisch auslaufen und sich natuerlich zur Stielbasis hin zusammenziehen.
4. Direkt um den Stiel eine sichtbare, typische leichte Einziehung ausbilden; kein aufgesetzter Deckel, keine horizontale Tellerflaeche, kein harter Absatz.
5. Der Stiel soll optisch aus dieser Einziehung herauswachsen.
6. Die Verbindung Koerper/Stiel muss weiterhin volumetrisch sicher ueberlappen und als ein physisch zusammenhaengendes Druckteil funktionieren.

## VERBINDLICH – UNVERAENDERT AUS R02
- Ziel-Aussendurchmesser ca. 20 mm.
- Acht organisch ungleichmaessige Hauptsegmente.
- R02-Oberflaechenstruktur mit feinen Rillen, Wellen und kontrollierter Unregelmaessigkeit beibehalten.
- R02-Stielcharakter beibehalten: kurz, kraeftig, leicht unregelmaessig; keine Rueckkehr zum langen R01-Stiel.
- Zwei getrennt im Slicer anwählbare Objekte: Koerper und Stiel.
- Nach dem Druck ein zusammenhaengendes physisches Teil.
- Koerper: PLA Matt Desert Tan.
- Stiel: PLA Metal Kupfer.
- Duesse 0,4 mm; Ziel-Layer 0,12 mm; erste Schicht 0,20 mm.
- 3 Aussenwaende = 1,2 mm; Top/Bottom 4; 5 % Gyroid.
- Support zunaechst AUS; Brim zunaechst AUS.
- Normale aufrechte Orientierung auf Kuerbisunterseite.
- Keine neuen Funktionen, Sockel, Halterungen, Haken, Oesen oder sonstige Zusatzgeometrie.

## TECHNISCH NOTWENDIG
- Oberes Profil aus der realen Stielbasis ableiten, sodass die Krone ohne sichtbaren horizontalen Ring in die Stielzone uebergeht.
- Keine willkuerliche neue Stielgroesse erfinden; R02-Stielproportionen soweit moeglich schuetzen.
- Ueberhaenge an der Krone auf supportfreien FDM-Druck mit 0,4-mm-Duese pruefen.
- R03 als eigene Revision ausgeben; R02 nicht ueberschreiben.

## VALIDIERUNG
- SOLL/IST-Bericht gegen diese R03-Spezifikation.
- Render aus der tatsaechlichen R03-Mesh-Geometrie liefern, mit Ansicht, die die obere Krone und den Stiel klar zeigt.
- Quantitativ dokumentieren:
  - Koerper-Aussendurchmesser / Gesamtmass
  - Radius bzw. Durchmesser der obersten sichtbaren Koerperzone direkt an der Stielbasis
  - Stielbasisbreite
  - Koerper/Stiel-Ueberlappung
  - Watertight / manifold
  - 3MF mit 2 getrennt anwählbaren Objekten
  - Supportbedarf
- Zusaetzlich Sichtpruefung: keine breite horizontale Plateau-/Tellerflaeche um den Stiel.
- Keine finale Druckfreigabe behaupten; erst ChatGPT-SOLL/IST, danach Nutzerfreigabe.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false` – es handelt sich um die gezielte Korrektur eines festgestellten Widerspruchs zur bereits verbindlichen R02-Formanforderung.