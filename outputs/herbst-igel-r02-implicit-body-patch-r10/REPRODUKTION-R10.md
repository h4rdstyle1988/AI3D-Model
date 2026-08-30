# Herbst-Igel R02 – Reproduktion R10

## Voraussetzungen

- Python 3.12
- NumPy
- Pillow
- keine externe Poisson-, CAD- oder Meshbibliothek erforderlich

Die Eingabe liegt unter
`source-seed42/herbst-igel-r02-trellis-raw-seed-42.ply` und muss SHA-256
`85ba18eaed15bdbe631fc49dd571e73882c4055e2c247022e90ad15ed99822c6`
haben. Das Skript bricht bei einer Abweichung vor der Rekonstruktion ab.

## Befehle ab Repository-Wurzel

```powershell
python outputs/herbst-igel-r02-implicit-body-patch-r10/reproduction-scripts/reconstruct_implicit_body_r10.py
python outputs/herbst-igel-r02-implicit-body-patch-r10/reproduction-scripts/render_optik_gate_r10.py
python outputs/herbst-igel-r02-implicit-body-patch-r10/reproduction-scripts/validate_r10.py
python outputs/herbst-igel-r02-implicit-body-patch-r10/reproduction-scripts/write_artifact_manifest_r10.py
```

## Verfahren

1. REF-SEAM-Körpermaske, Schutzmasken und die normalisierte Unterkörpergrenze
   `Z = -0,105` werden unverändert aus R08/R09 reproduziert.
2. Die robuste angrenzende Seed-42-Körpertiefe wird erneut gemessen:
   `Y05 = -0,1328873724`, `Y95 = 0,3874041855`, Mittelpunkt
   `0,1272584066`, Halbtiefe `0,2601457790`.
3. Zwei unabhängige glatte Skalarfelder werden erzeugt:
   eine geglättete Signed-Distance-Visual-Hull-Variante und eine Gauß-RBF-
   Interpolation mit 324 Stützstellen.
4. Beide Nullflächen werden ohne planare Caps, Dreiecksfächer, Convex Hull
   oder blockartige Lochfüller per Marching Tetrahedra extrahiert.
5. Tatsächliche äußere Seed-42-Tiefenlagen innerhalb der bestätigten
   Ohren-/Augen-/Nasen-/Fußmasken werden erhalten. Die Diagnosefenster an
   Augen/Nase sind Teil des NON-MASTER-Versuchs und bestehen das Gate nicht.
6. SDF und RBF werden in 3/4-, Referenzseiten- und Gegenseitenansicht
   gescreent. Die numerisch geringere SDF-Abweichung wird in sechs realen
   Geometrieansichten vollständig geprüft.

Die Skripte erzeugen ausschließlich NON-APPROVED-Diagnosegeometrie. Split,
Hohlschalen, Verbinder und Druckdateien werden bei `OPTIK_GATE: FAIL` nicht
ausgeführt.

