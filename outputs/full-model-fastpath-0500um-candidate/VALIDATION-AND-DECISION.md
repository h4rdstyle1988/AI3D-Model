# Full-Model Fast-Path – Validierung und Entscheidung

## Entscheidung

# A – PRODUCTION FAST-PATH PASS

Der vollständige Körper einschließlich ausgewähltem und verbundenem Schwanz ist technisch sauber, visuell akzeptabel, formatstabil und in sinnvoller Laufzeit entstanden.

Gemessene Gesamtzeit für Build + strengen technischen Gate: **323,238 s = 5:23 min**.  
Davon reine Rekonstruktion: **24,745 s**.  
Normalpfad ohne einmalige exakte Deep-Prüfung: **107,690 s = 1:48 min**.  
Zusätzlicher echter Anycubic-Slice: **17,744 s**.

Der Kandidat ersetzt keinen Master und bleibt ausdrücklich **CANDIDATE / NON-MASTER**.

## Geometriegate

| Kriterium | Ergebnis |
|---|---:|
| Vertices / Faces | 721.371 / 1.443.070 |
| gemeinsame Vertex-/Edge-Komponenten | 1 / 1 |
| watertight / is_volume | PASS / PASS |
| edge-manifold / vertex-manifold | PASS / PASS |
| Boundary / Non-Manifold Edges | 0 / 0 |
| ungültige Vertex-Links | 0 |
| Zero-Area / wiederholte Indizes | 0 / 0 |
| Duplicate Faces | 0 |
| Winding / Normalen | konsistent / endlich |
| exakte nichtbenachbarte Selbstschnitte/Kontakte | 0 |
| Bounding Box | 146,5 × 190,5 × 146,0 mm |
| Volumen | 1.245.106,047 mm³ |

Keine separate Innenhaut wurde erzeugt. Der Slicer übernimmt Wandlinien und Infill für den einen geschlossenen Solid.

## Format-Roundtrips

- Arbeitsmesh: PASS
- STL: PASS; identischer quantisierter Dreieckssatz; 381/381 Layer-Loops; 0 Fehler
- 3MF: PASS; identischer quantisierter Dreieckssatz; 381/381 Layer-Loops; 0 Fehler
- Anycubic `--no-check` STL-Roundtrip: PASS; identischer quantisierter Dreieckssatz; Topologie und Layer-Loops PASS

Kandidatenhashes:

- STL: `9E2A2367AF8BD34720B11DFA6A4149E720371C6F9F6D646E9ADEC239EBEA1158`
- 3MF: `5CF6001018A3B97CE8AEE6D8255252FAE4BD313D293BB2F2D702BF9CD3C53CAD`
- Working NPZ: `1ABE583E8070366AA013CE07ADF18DCA62A7BA2020C6572EAB12898300D292C7`

## Echter Slicer

AnycubicSlicerNext 1.4.1.2 wurde mit `--no-check` verwendet; automatische Validitätsprüfung/Repair war damit deaktiviert.

- Import: `manifold = yes`, `number_of_parts = 1`, 1.443.070 Facetten
- Kobra-S1-Slice: 953 Layer, 953 Z-Marker, 0 Layer ohne positive Extrusion
- 1 Objektdefinition / 1 Modellinstanz
- G-code SHA-256: `879BB3AA9583A26E5C0A5D5A3B1AAD6239666FD4C91B4EFBC8B3CCA247D12EFD`
- keine Repair-, Non-Manifold- oder Empty-Layer-Meldung

Die Meldung `calc_exclude_triangles: Unable to create exclude triangles` betrifft die optionale Platten-/Objektausschlussvisualisierung und war nicht fatal; der Slice und die 953 Layer wurden vollständig erzeugt.

## Abgrenzung

- Der G-code ist ein Testartefakt, keine finale Druckfreigabe für Material-, Support- oder Qualitätsparameter.
- Es wurde keine 0,25-mm-Variante, keine v003-Mikrochirurgie, keine Glättung, keine Decimation und kein alternativer Remesher gestartet.
- Der eingefrorene erfolgreiche 0,5-mm-C01-Smoke-Kandidat und sämtliche Original-/Phase-4-Artefakte blieben unverändert.

Weiterführende Details:

- [Laufzeitreport](RUNTIME-REPORT.md)
- [Formerhalt und Schwanz](FORM-AND-TAIL-REPORT.md)
- [Generalisierte Pipeline](PIPELINE-SPEC.md)
- [Maschinenlesbare Fast-Gate-Daten](full-model-fastpath-0500um-CANDIDATE-fast-gate.json)
- [Maschinenlesbare Form-QA](visual-and-detail-qa/full-model-fastpath-0500um-CANDIDATE-visual-and-detail-qa.json)
- [Anycubic Slice-Audit](anycubic-no-check-slice-attempt03/anycubic-slice-audit.json)
