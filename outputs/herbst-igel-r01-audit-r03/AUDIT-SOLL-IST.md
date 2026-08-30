# Herbst-Igel R01 – Validierungs-Nachaudit R03

Task: `TASK-HERBST-IGEL-R01-VALIDATION-AUDIT-R03`  
Quellergebnis: R01, Commit `7b825beac856c0fee120bf080a9b747cb6418313`  
Ergebnis: **STOPP**  
Finale Produkt-/Druckfreigabe: **NEIN – ausschließlich durch den Nutzer**

## Revisionsumfang

**GEÄNDERT:** ausschließlich Validierung und Nachweis in diesem neuen Auditordner.  
**UNVERÄNDERT:** beide R01-STL, Montage-GLB, parametrische Produktquelle, sichtbare Geometrie und alle Nutzermaße.  
**ENTFERNT:** nichts.  
**OFFEN:** optische Nutzerfreigabe, realer Testdruck, Pass-/Klebeprobe und slicerspezifische Supportprüfung.

## SOLL/IST

| Prüfpunkt | SOLL | IST | Status |
|---|---|---|---|
| Ausgangsgeometrie | exakt Commit `7b825beac856c0fee120bf080a9b747cb6418313` | Körper-LFS `ecab728a7a194bf6ded12d03163b0ef31c02456e06a2ff77c124f4571b99e7a8`, Rücken-LFS `5f3085a7b498c2003e0c6a3cfb694f2f48f52ea74774f0c92f310eca53973df9`; beide Hashes verifiziert; nicht neu generiert | PASS |
| Selbstschnitt Körper | direkte Prüfung, 0 echte Paare | 21 echte Paare; 7,057,051 AABB-Kandidaten, 1,118,780 Narrowphase-Paare | STOPP |
| Selbstschnitt Rücken | direkte Prüfung, 0 echte Paare | 22772 echte Paare; 4,300,232 AABB-Kandidaten, 747,169 Narrowphase-Paare | STOPP |
| Innenverstärkung/Außenhaut Körper | keine verursachte Außenbeule | STL max. 0.038009 mm bei Tessellierungsbasis 0.552556 mm; analytischer Verstärkungsüberstand 0.000000000 mm | PASS |
| Innenverstärkung/Außenhaut Rücken | keine verursachte Außenbeule | STL max. 0.474501 mm bei Tessellierungsbasis 0.478020 mm; analytischer Verstärkungsüberstand 0.009059259 mm am Punkt [33.3912, -46.0, 73.0] | STOPP |
| Repository-Task-Blob | `09cb6285e81881adb9d3811a118a7b73f706d83b` | `09cb6285e81881adb9d3811a118a7b73f706d83b` | PASS |
| Bauteile | genau 2 | 2 STL; GLB mit 2 Nodes und 2 Meshes | PASS |
| Zapfen | Ø10,0 mm, 20,0 mm wirksam | Median Ø9.999999 mm; Länge 19.999998 mm aus finalem STL | PASS |
| Aufnahme | Ø10,4 mm, Tiefe 20,4 mm | Median Ø10.399998 mm; Tiefe 20.400000 mm; diametrales Spiel 0.399999 mm | PASS |
| Grundwand | Nennmaß 1,6 mm | gefrorener Normaloffset 1,600 mm; kleinste STL-Strahlprobe 1.5758 mm (1-mm-Tessellierung separat) | PASS |
| Gesamtmaß | ca. 200 mm | 199.5295 mm | PASS |
| Dekoration/Funktion | ein Ahornblatt; keine Rastung/Klemmung/Konizität/Zusatzfunktion | Quellenparameter: ein Ahornblatt; eine gerade geklebte Zapfen-/Aufnahmeverbindung; keine genannten Zusatzprimitive/-pfade | PASS |

## Direkte Selbstschnittmethode

Broadphase: Morton-sortierter binärer AABB-BVH mit 8 Dreiecken pro Blatt; dadurch keine naive O(n²)-Vollprüfung. Narrowphase: tatsächlicher 3D-Dreieck/Dreieck-SAT mit beiden Flächennormalen, neun Kante/Kante-Achsen und sechs zusätzlichen In-Plane-Achsen für koplanare Fälle. AABB- und Schnitt-Toleranz: `1e-06` mm. Topologische Nachbarn werden über koordinatenverschweißte gemeinsame Vertices bei `1e-05` mm ausgeschlossen; damit sind auch gemeinsame Kanten ausgeschlossen. Nicht benachbarte Punkt-/Kantenkontakte zählen als echte Schnitte. Vollständige Zähler stehen in `self-intersection-report.json`.

## Außenhaut / Innenverstärkung

Für jedes finale STL wurden alle Vertices und Dreieckszentren im Anschlussbereich gegen die gefrorene R01-`outer_sdf`-Basis ohne Anschlussverstärkung ausgewertet. Die separat ausgewiesene Tessellierungsbasis stammt aus demselben finalen STL außerhalb des Anschlussbereichs. Zusätzlich wurde das vollständige analytische Verstärkungsvolumen auf 0,25-mm-Rasterpunkten und an allen exakten Brückenquader-Ecken gegen dieselbe Basis geprüft. Der Rücken-Brückenpunkt `[33.3912, -46.0, 73.0]` liegt um 0.009059259 mm außerhalb der unverstärkten Außenform. Das ist trotz seiner sehr kleinen Größe keine reine Tessellierungsabweichung und daher `STOPP`. Es wurde keine Vergleichs- oder Produktgeometrie exportiert.

## Trennlinie / optische Prüfbasis

`seam-overlay.png` legt die aus tatsächlichen finalen Körper-STL-Vertices extrahierte und projizierte Außenkante rot über die blaue Markierung in REF-SEAM. Perspektivkamera: `(-250, -260, 175) mm`, Ziel `(0, 0, 78) mm`, Brennparameter 1,75. Die Ausrichtung verwendet eine einheitliche, seitenverhältnistreue 2D-Skalierung plus Translation der Vordergrund-Bounding-Boxes; es gibt keine nichtlineare oder nichtuniforme Verzerrung.

Diagnostische symmetrische 2D-Nächstlinienabweichung bei nativer REF-SEAM-Auflösung: Mittel `88.9` px, Maximum `156.1` px. Die Werte sind auf 0,1 px gerundet und keine Maßhaltigkeitsfreigabe, da keine kalibrierte Referenzkamera vorliegt und Referenz- und Modell-Silhouetten nicht identisch sind.

`visual-compare.png` zeigt die unveränderten autoritativen REF-CLEAN-Bytes neben dem tatsächlichen finalen R01-3/4-Render. REF-CLEAN enthält im freigegebenen Hashstand eine graue untere Bildhälfte; diese Transport-/Bildgrenze wird nicht retuschiert oder durch eine andere Referenz ersetzt. Der Vergleich zeigt sachlich eine deutlich aufrechtere, rundere Modellproportion, vereinfachte Gesicht-/Fußdetails und gröbere Rückenblätter gegenüber der Referenz. Das ist keine optische Freigabe; die Endentscheidung bleibt offen beim Nutzer.

## Task-Blob-Ursache

Repository-Blob aus dem Ergebniscommit: `09cb6285e81881adb9d3811a118a7b73f706d83b`. Der frühere Wert `7834e73a9dc494ed9a96f0daefbfeecfd99a374f` ist der Blobstil-SHA der rohen CRLF-Worktree-Bytes. `git hash-object` mit Repository-Filter ergibt `09cb6285e81881adb9d3811a118a7b73f706d83b`. Der Worktree enthält 22 CRLF-Zeilenenden; nach CRLF→LF-Normalisierung stimmen seine Bytes exakt mit dem Commit-Blob überein. Ursache damit bestätigt: Worktree-Zeilenenden wurden statt des Repository-Blobs gehasht.

## Reproduktion

Vollständiger Lauf aus der Repository-Wurzel (Python 3.12.10, NumPy 2.4.2, Pillow 12.1.1):

```powershell
python outputs/herbst-igel-r01-audit-r03/audit_herbst_igel_r03.py --repo . --output outputs/herbst-igel-r01-audit-r03
```

Der Script-Exitcode ist bei diesem nachgewiesenen `STOPP` ungleich null. `--reuse-self-report` ist ausschließlich für die reproduzierbare Neuerzeugung nachgelagerter Berichte/Bilder aus einem bereits vollständig abgeschlossenen, commitgleichen Direkttest vorgesehen.

## Offene reale Prüfungen

1. Optischer Nutzervergleich und finale Produktfreigabe anhand der beiden Prüfbilder.
2. FDM-Testdruck mit 0,4-mm-Düse und 0,12-mm-Layer, optional adaptiv bis 0,08 mm.
3. Reale Ø10,0/Ø10,4-Pass- und Klebeprobe in den gewählten PLA-Chargen.
4. Slicer-spezifische Prüfung von Supportzugänglichkeit und Oberflächenwirkung.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false` – der Audit ändert keine verbindliche Funktion, kein Nutzermaß und keine Produktgeometrie; optische und reale Endprüfungen bleiben ausdrücklich offen.
