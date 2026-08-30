# TASK – HERBST-IGEL R02 MASTERFORM-CLEANUP R08

## Zweck
Technischer Folgeversuch nach R07 OPTIK_GATE FAIL. Keine Produktänderung.

R07 hat bestätigt: Seed 42 besitzt die beste Gesamtähnlichkeit und als einziger Kandidat das korrekte einzelne sichtbare Ahornblatt. Der wiederkehrende Hauptfehler ist lokal: Blatt-/Stachelformen überschreiten die autoritative Körper/Rücken-Grenze und hängen über Stirn, Augen und Schnauze.

Statt weitere Voll-Trellis-Läufe blind zu wiederholen, ist R08 als effizientere Masterform-Bereinigung auszuführen.

## Autoritative Quellen
- unverändert dieselbe saubere Herbst-Igel-Referenz wie R06/R07
- unverändert dieselbe REF-SEAM-Referenz mit blauer Trennlinie
- R07 Seed 42 als technisch bester Rohkandidat

Keine neue Interpretation, kein Redesign, keine zusätzlichen Produktmerkmale.

## Verbindlicher Arbeitsweg
1. R07 Seed 42 als Masterform-Ausgangsbasis laden und reproduzierbar referenzieren.
2. Zuerst prüfen, ob die eigentliche Körper-/Gesichtsoberfläche hinter den überhängenden Blatt-/Stachelformen bereits als Geometrie vorhanden ist.
3. Die autoritative REF-SEAM-Grenze auf die 3D-Masterform übertragen.
4. Ausschließlich die Trellis-erzeugten Blatt-/Stachelanteile entfernen bzw. beschneiden, die sichtbar in den Körper-/Gesichtsbereich vor der REF-SEAM-Grenze hineinragen.
5. Falls dadurch lokale offene Bereiche entstehen:
   - nur technisch notwendige lokale Flächenrekonstruktion,
   - tangential und glatt aus angrenzender Körperform ableiten,
   - gegen die saubere Referenz prüfen,
   - keine neue Gesichtsform erfinden,
   - keine globale Glättung oder Neuformung des Igelkörpers.
6. Rücken-/Blattstruktur hinter der REF-SEAM-Grenze möglichst unverändert schützen, insbesondere genau ein sichtbares Ahornblatt auf Referenzseite und kein zweites erfundenes Ahornblatt.
7. Neue bereinigte MASTERFORM rendern: 3/4 vorne, links, rechts, hinten, oben, unten sowie Soll/Ist-Gegenüberstellung zur sauberen Referenz und REF-SEAM.
8. OPTIK_GATE erneut ausführen. Bewertet wird die tatsächliche Geometrie, nicht ein Bericht.
9. Nur bei eindeutigem OPTIK PASS mit der bereits freigegebenen technischen Kette fortfahren:
   - Gesamtform als Master schützen,
   - Split entlang REF-SEAM,
   - zwei Hohlschalen,
   - nominell 1,6 mm Wandstärke,
   - zentraler versteckter geklebter Verbinder,
   - Zapfen Ø10,0 mm exakt,
   - effektiver Eingriff 20,0 mm exakt,
   - kein Snap/Clips/Taper/Key/Magnete/zusätzliche Führungen,
   - PLA Matt Desert Tan Körper, PLA Metal Kupfer Rücken,
   - 0,4-mm-Düse,
   - ca. 200 mm max. Gesamtausdehnung proportional,
   - FDM-/Mesh-/Support-/Passungsvalidierung.
10. Wenn eine saubere Masterform durch lokales seam-geführtes Cleanup nicht belastbar erreichbar ist: STOPP vor Split/CAD und exakt dokumentieren, warum. Nicht auf eine parametrische Ersatzfigur wechseln.

## Effizienzvorgabe
- Keine weiteren 4×512-Trellis-Vollserien, solange nicht nachgewiesen ist, dass Cleanup unmöglich ist.
- Vorhandene R07-Artefakte wiederverwenden.
- Nur lokal neu rechnen/bearbeiten, was für das Optik-Gate notwendig ist.

## Schutzregeln
- Nutzeridee unverändert.
- Keine Änderung der Silhouette außerhalb technisch notwendiger lokaler Korrektur.
- Keine Änderung von Ohren, Augen, Nase, Füßen oder Ahornblatt, sofern nicht unmittelbar durch das Entfernen einer falschen Überdeckung notwendig.
- Keine zusätzlichen Blätter, Stacheln, Sockel, Halter, Führungen oder Funktionen.
- Außenoptik hat vor Split/Schalen/CAD Vorrang.

## Ergebnis / Bericht
Dokumentieren:
- GEÄNDERT
- UNVERÄNDERT
- ENTFERNT
- OFFEN
- Soll/Ist Optik
- verwendete Seed-42-Ausgangsdateien und Hashes
- ob verdeckte Körperoberfläche vorhanden war
- welche Geometrie lokal entfernt / rekonstruiert wurde
- alle tatsächlichen Renderansichten

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

Dies ist eine rein technische Korrektur im bereits freigegebenen Produktkonzept. Nur wenn ein echter Produktkonflikt entsteht, Nutzerentscheidung anfordern.
