# TASK-KUERBIS-20MM-R02-DETAIL-FORM

Status: VOM NUTZER ZUR ÜBERARBEITUNG FREIGEGEBEN
Datum: 2026-08-29

## AUSGANGSSTAND
- R01 ist technisch druckbereit und wurde vom Nutzer im Slicer angesehen.
- Nutzerfeedback zum sichtbaren Modell: **"er braucht mehr details und Form"**.
- R01 bleibt unverändert als Referenz/Teststand erhalten und darf nicht überschrieben werden.
- Neue Revision: R02.

## VERBINDLICH – ÄNDERN
1. **Kürbisform organischer und ausgeprägter machen**
   - Der Körper darf nicht wie eine regelmäßig gerippte Kugel wirken.
   - Die einzelnen Kürbislappen müssen deutlicher als echte, gewachsene Segmente lesbar sein.
   - Ober- und Unterseite sollen stärker die typische Kürbisform zeigen: leichte Einziehung um den Stiel, organischer Verlauf zu den Seiten und zur Unterseite.
   - Keine perfekte Rotationssymmetrie; kontrollierte natürliche Unregelmäßigkeit ist gewünscht.

2. **Rippen/Lappen natürlicher gestalten**
   - Vorhandene acht Hauptsegmente als Grundcharakter beibehalten, sofern dies der organischen Form nicht widerspricht.
   - Rippen nicht mathematisch identisch ausführen.
   - Leichte Unterschiede in Breite, Tiefe und Verlauf der Segmente zulassen, damit die Form gewachsen statt parametrisch wirkt.
   - Vertiefungen zwischen den Segmenten klarer ausformen, ohne unentfernbare Supportbereiche zu erzeugen.

3. **Oberflächendetails deutlich erhöhen**
   - Sichtbare, organische Hautstruktur ergänzen bzw. verstärken: feine Rillen, kleine Wellen/Unebenheiten und unregelmäßige Oberflächenvariation.
   - Keine gleichmäßige mathematische Textur und kein reines Noise-Muster ohne Bezug zur Kürbisform.
   - Details müssen bei ca. 20 mm Außendurchmesser mit 0,4-mm-Düse noch als echte Forminformation druckbar und sichtbar sein.
   - Details dürfen die Silhouette und Hauptsegmente unterstützen, nicht überdecken.

4. **Stiel formgerechter machen**
   - Stiel im Vergleich zu R01 kürzer und kräftiger ausführen.
   - Leicht unregelmäßig/organisch, nicht als schlanker gerader Zapfen.
   - Verbindung zum Kürbiskörper muss optisch natürlich aus der oberen Einziehung wachsen.
   - Zweifarbige Materialtrennung zwischen Körper und Stiel beibehalten.

## VERBINDLICH – UNVERÄNDERT
- Zielgröße weiterhin ca. 20 mm Außendurchmesser.
- Zwei getrennt im Slicer anwählbare Objekte: Körper und Stiel.
- Nach dem Druck ein zusammenhängendes physisches Teil.
- Körper: PLA Matt Desert Tan.
- Stiel: PLA Metal Kupfer.
- Düse: 0,4 mm.
- Ziel-Layerhöhe: 0,12 mm; erste Schicht 0,20 mm.
- 3 Außenwände = 1,2 mm.
- Top/Bottom 4 Schichten.
- 5 % Gyroid.
- Support zunächst AUS; Brim zunächst AUS.
- Normale aufrechte Orientierung auf Kürbisunterseite.
- Keine neuen Funktionen, Sockel, Halterungen, Haken, Ösen oder sonstige Zusatzgeometrie.

## TECHNISCH NOTWENDIG
- Für sichtbare Oberflächendetails Mindestgröße/Relieftiefe anhand 0,4-mm-Düse und 0,12-mm-Layer technisch bestimmen und dokumentieren.
- Übergänge zwischen Segmenten so auslegen, dass sie druckbar bleiben und keine unzugänglichen Supports benötigen.
- Stiel/Körper-Verbindung ausreichend volumetrisch überlappen, ohne die sichtbare Form unnötig zu verändern.
- R02 als eigene Dateien/Revision ausgeben; R01 nicht überschreiben.

## VALIDIERUNG
- SOLL/IST-Bericht gegen diese R02-Spezifikation.
- Sichtprüfung/Render aus tatsächlicher R02-Geometrie bereitstellen.
- Prüfen und dokumentieren:
  - Außendurchmesser / Gesamtmaße
  - Anzahl und Charakter der Hauptsegmente
  - Asymmetrie/organische Form
  - Oberflächendetailgrößen und Druckbarkeit bei 0,4-mm-Düse
  - Stielhöhe/-breite und Verbindung
  - Watertight / manifold
  - 3MF mit zwei getrennt anwählbaren Objekten
  - Supportbedarf und Supportentfernbarkeit
- Keine finale Druckfreigabe behaupten. Erst technische Prüfung durch ChatGPT und anschließend Nutzerfreigabe.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false` – die Richtung ist durch das aktuelle Nutzerfeedback und die bereits etablierte Referenz klar; fehlende technische Detailwerte sind konstruktiv zu bestimmen und zu dokumentieren, ohne die Produktidee zu erweitern.