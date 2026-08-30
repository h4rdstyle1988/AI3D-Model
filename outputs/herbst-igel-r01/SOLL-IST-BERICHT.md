# Herbst-Igel R01 – SOLL/IST-Bericht

Task: `TASK-HERBST-IGEL-R01-RETRY-REF-AUTH-R02`  
Revision: `R01`  
Ergebnis: **PASS**  
Finale Produktfreigabe: **NEIN – ausschließlich durch den Nutzer**

## Referenzen

- REF-CLEAN dekodiert und SHA-256 PASS: `f3017009739284e1bfd6e8502e9d9258eb74dbf52074c425a73ff41fc8bac328`.
- REF-SEAM dekodiert und SHA-256 PASS: `b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4`.
- Sekundäre Multiansicht wurde nicht dekodiert und nicht verwendet.

## SOLL/IST

| Merkmal | SOLL | IST |
|---|---|---|
| Bauteile | 2 Hohlschalen | 2 separate, offene Hohlschalen: Körper und Rücken |
| Gesamtmaß | ca. 200 mm | 199.529 mm maximale Ausdehnung |
| Grundwand | Nennmaß 1,6 mm | parametrischer Normaloffset 1,600 mm; kleinste unabhängige STL-Strahlprobe 1,5758 mm (Abweichung durch 1,0-mm-Tessellierung) |
| Stecksteg | Ø10,0 × 20,0 mm | Ø10.0 × 20.0 mm, analytisch gesnappt |
| Aufnahme | technisch bestimmtes Klebespiel | Ø10.4 mm, radial 0.2 mm, Tiefe 20.4 mm |
| Verbindung | eine, mittig, unsichtbar | eine interne Körper-Zapfen/Rücken-Aufnahme-Verbindung; keine Rastung/Klemmung/Konizität |
| Optik | niedlicher Referenz-Igel | sitzende Haltung auf vier integrierten Füßen, runde Schnauze, Ohren, erhabene Augen/Nase |
| Rücken | einzelne überlappende Blattstacheln | 54 organisch überlappende Blattkörper mit druckbaren Mittelrippen |
| Ahornblatt | genau ein sichtbares | genau ein zusammenhängendes fünf-lappiges Ahornblatt auf der sichtbaren Seite |
| Trennlinie | blaue natürliche Kontur | komplementäre Kurve `x=42−0,15z−0,0018(z−30)²+0,0018y²` |
| Zusatzfunktionen | keine | keine; nur technisch nötige innere Anschlussrippen |

## Optische Abweichungen / Grenzen

- Die Konstruktion ist eine parametrische 3D-Ableitung aus der einzigen autoritativen 3/4-Ansicht; unsichtbare Seiten wurden ausschließlich als organische Fortsetzung ohne zweite Dekoration ausgeführt.
- Feine Material-/Fellwirkung ist als 0,28-mm-Relief angelegt; die reale Wiedergabe hängt von PLA, Kalibrierung und 0,08–0,12-mm-Schichthöhe ab.
- Augen und Nase sind Körpergeometrie und werden erst nach dem Druck bemalt; die Renderfarbe trennt nur die beiden Filamentbauteile.

## Druckorientierung und Support

- Körper: sichtbare Gesichtsseite schräg nach oben; große Nahtöffnung zugänglich. Der interne Zapfen wird möglichst annähernd vertikal orientiert. Nur erreichbarer äußerer/tree Support unter Schnauze/Ohren/Füßen nach Slicer-Vorschau.
- Rücken: Nahtöffnung nach oben oder schräg oben; Blattspitzen nicht als Auflagefläche. Nur äußerer, entfernbarer Support unter stark negativen Blattwinkeln.
- Kein Support ist in einem geschlossenen Hohlraum eingeschlossen; beide Hohlschalen bleiben über die Montageöffnung zugänglich.

## Offene reale Prüfungen

1. FDM-Testdruck mit 0,4-mm-Düse und 0,12-mm-Layer (optional adaptiv bis 0,08 mm).
2. Reale Ø10,0/Ø10,4-Passung und Klebeprobe mit den gewählten PLA-Chargen.
3. Slicer-spezifische Prüfung der Supportzugänglichkeit und sichtbaren Oberflächen.
4. Optischer Nutzervergleich und ausschließlich danach finale Produktfreigabe.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false` – keine verbindliche Funktion und kein Nutzermaß wurde geändert.
