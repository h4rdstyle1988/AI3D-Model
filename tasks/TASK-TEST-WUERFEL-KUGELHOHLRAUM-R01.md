# TASK – Testwürfel mit kugelförmigem Hohlraum – R01

Status: **VOM NUTZER FREIGEGEBENER TESTAUFTRAG / WARTESCHLANGE**

## Zweck

Einfacher Test des automatischen CAD-Workflows nach Abschluss des aktuell laufenden Infrastrukturauftrags. Keine zusätzlichen Funktionen erfinden.

## VERBINDLICH

- Außenkörper: Würfel exakt **50.0 × 50.0 × 50.0 mm**.
- Im Würfel befindet sich ein **kugelförmiger Hohlraum Ø55.0 mm**.
- Mittelpunkt der Kugel liegt **exakt im geometrischen Mittelpunkt des Würfels**: X=25.0 mm, Y=25.0 mm, Z=25.0 mm bezogen auf eine Würfelecke bei 0/0/0.
- Geometrie ist die boolesche Differenz Würfel minus Kugel.
- Da Ø55 mm größer als die Würfelkante 50 mm ist, durchdringt der kugelförmige Hohlraum konstruktionsbedingt die sechs Würfelflächen. Das ist ausdrücklich Teil der freigegebenen Geometrie und darf nicht korrigiert werden.
- Keine Rundungen, Füße, Sockel, Halterungen, Verstärkungen, Texte oder sonstigen Zusatzfunktionen.

## AUSGABE

- STL des resultierenden Körpers.
- Parametrische/reproduzierbare Quelldatei mit den oben genannten Maßen.
- Kurzer SOLL/IST-Bericht mit Außenmaßen, Kugeldurchmesser und Kugelzentrum.
- Mesh-/Topologieprüfung soweit lokale Toolchain verfügbar.
- Revision dokumentieren; keine finale Nutzerfreigabe behaupten.

## WICHTIG

Dieser Auftrag ist bereits vom Nutzer geometrisch freigegeben. Technische Umsetzung darf die Maße oder Lage nicht verändern. Nur echte technische Blocker als STOPP dokumentieren.
