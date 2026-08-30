# Herbst-Igel R02 – Reproduktion R09

Voraussetzungen: Python 3.12, NumPy und Pillow. Aus der Repository-Wurzel in
dieser Reihenfolge ausführen:

```powershell
python outputs/herbst-igel-r02-body-surface-reconstruction-r09/reproduction-scripts/reconstruct_body_surface_r09.py
python outputs/herbst-igel-r02-body-surface-reconstruction-r09/reproduction-scripts/render_optik_gate_r09.py
python outputs/herbst-igel-r02-body-surface-reconstruction-r09/reproduction-scripts/validate_r09.py
python outputs/herbst-igel-r02-body-surface-reconstruction-r09/reproduction-scripts/write_artifact_manifest_r09.py
```

Der Ablauf startet Trellis nicht erneut. Er nutzt ausschließlich den unter
`source-r08/` archivierten, byteidentischen Seed-42-Rohmesh sowie REF-CLEAN und
REF-SEAM unter `reference-audit/`.

Deterministische Hash-Gates:

- Seed-42-Quelle:
  `85ba18eaed15bdbe631fc49dd571e73882c4055e2c247022e90ad15ed99822c6`
- R09-NON-MASTER:
  `cda7fbd40bcaca15c59fcad58981154b6176bca7b59af982dbddd574f7cb78f8`

Wegen `OPTIK_GATE: FAIL` erzeugt der Ablauf keine CAD-, STL-, STEP-, GLB- oder
3MF-Datei.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

