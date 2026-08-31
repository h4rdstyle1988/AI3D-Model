# Herbst-Igel R02 – Revisionsbericht R13

## Status

`STOPP – FORM_PROTECTION_GATE FAIL + OPTIK_GATE FAIL`

`MESH_GATE: PASS`

## GEÄNDERT

- Seed 42 wurde global als geschlossene, zusammenhängende und orientierbare Doppel-Höhenfeld-Oberfläche neu vernetzt.
- Innerhalb der autoritativen R11/R12-Problemzone wurden 9.982 projizierte Quellknoten entfernt und 6.596 referenzgeführte Body-Knoten ergänzt.
- Der lokale Körperbereich wurde mit den unveränderten R11-Breitenprofilen und REF-SEAM als eine einzige Oberfläche aufgebaut.
- Drei technisch verschiedene Reparaturwege wurden geprüft: Doppel-Höhenfeld, Radialhülle und dreiachsige Volumenhülle.

## UNVERÄNDERT

- Seed-42-Quelle und Hash: `85ba18eaed15bdbe631fc49dd571e73882c4055e2c247022e90ad15ed99822c6`.
- REF-CLEAN und REF-SEAM samt Hashes.
- Produktidee, ca. 200 mm Zielgröße, zwei Druckteile, 1,6-mm-Nennwand, Materialien, Ø10,0 × 20,0-mm-Klebeverbinder und Druckparameter.
- Keine neue Funktion, kein anderer Seed, kein zweites Ahornblatt und kein parametrischer Ersatzigel.

## ENTFERNT

- Überlappende Innen-/Doppelhäute und fehlerhafte Kanteninzidenzen sind im topologischen Prüfstand entfernt.
- Keine verbindliche Nutzerfunktion oder kein Nutzermaß wurde entfernt.

## OFFEN / STOPP-GRUND

- Die Prüfmasterform besitzt 0 offene, 0 nichtmanifolde und 0 degenerierte Kanten/Flächen und keine bestätigten Selbst-/Kreuzschnitte.
- Der reale Flächeninhalt beträgt jedoch das 60,461-Fache der Seed-42-Oberfläche. Ursache sind Verbindungen zwischen unterschiedlichen Seed-42-Tiefenlagen; die sichtbare Oberfläche außerhalb der ROI ist daher trotz identischer Hüllknoten nicht geschützt.
- Reale Render zeigen weiterhin einen harten Stirn-/Seam-Überhang. Beide Augen und Ohren sind nicht eindeutig frei und organisch integriert; Rückenstruktur und einzelnes Ahornblatt sind nicht eindeutig referenznah lesbar.
- Die Radialhülle machte die nicht sternförmige Figur kugelig; die dreiachsige Volumenhülle verlor Gesichtsrelief und blieb an diskreten Punktkontakten nichtmanifold. Beide wurden verworfen.
- Deshalb kein freigegebener Master, kein Split, keine Hohlschalen, kein Verbinder, keine STL/3MF/GLB und keine FDM-Validierung.
- Keine finale Produkt-, Optik- oder Druckfreigabe behauptet.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

Grund: rein technischer Rekonstruktionsstopp; es fehlt keine Nutzerangabe.
