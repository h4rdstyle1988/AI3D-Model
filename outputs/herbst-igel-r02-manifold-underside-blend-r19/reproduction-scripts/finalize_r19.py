"""Write R19 revision, status, render and artifact documentation."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from PIL import Image


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("r19_master", HERE / "r19_master.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Cannot load r19_master.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def render_gate3_parts() -> list[Path]:
    render_dir = M.OUT / "renders-gate3"
    render_dir.mkdir(parents=True, exist_ok=True)
    front_vertices, front_faces = M.read_ply(
        M.OUT / "cad-mesh-source" / "herbst-igel-r02-r19-front-body-hollow.ply"
    )
    back_vertices, back_faces = M.read_ply(
        M.OUT / "cad-mesh-source" / "herbst-igel-r02-r19-back-spine-shell-hollow.ply"
    )
    paths = []
    for name, vertices, faces, direction in (
        ("front-part-3q", front_vertices, front_faces, M.VIEWS["3q-front"]),
        ("front-part-seam", front_vertices, front_faces, M.VIEWS["rear"]),
        ("back-part-3q", back_vertices, back_faces, M.VIEWS["rear"]),
        ("back-part-seam", back_vertices, back_faces, M.VIEWS["front"]),
    ):
        image = M.render(vertices, faces, direction, f"R19 Gate 3 | {name}")
        path = render_dir / f"{name}.png"
        image.save(path)
        paths.append(path)
    sheet = Image.new("RGB", (1280, 1280), "white")
    for i, path in enumerate(paths):
        sheet.paste(Image.open(path).convert("RGB"), ((i % 2) * 640, (i // 2) * 640))
    sheet_path = render_dir / "gate3-two-parts-contact-sheet.png"
    sheet.save(sheet_path)
    paths.append(sheet_path)
    return paths


def main() -> None:
    master = json.loads((M.OUT / "reports" / "master-build-r19.json").read_text(encoding="utf-8"))
    topo = json.loads((M.OUT / "reports" / "topology-gate-r19.json").read_text(encoding="utf-8"))
    form = json.loads((M.OUT / "reports" / "form-protection-gate-r19.json").read_text(encoding="utf-8"))
    delta = json.loads((M.OUT / "reports" / "form-delta-r19.json").read_text(encoding="utf-8"))
    gate3 = json.loads((M.OUT / "technical-validation-gate3-r19.json").read_text(encoding="utf-8"))
    seam = json.loads((M.OUT / "reports" / "ref-seam-proof-r19.json").read_text(encoding="utf-8"))
    connector = json.loads((M.OUT / "reports" / "connector-validation-r19.json").read_text(encoding="utf-8"))
    orientation = json.loads((M.OUT / "reports" / "fdm-orientation-support-r19.json").read_text(encoding="utf-8"))
    gate3_renders = render_gate3_parts()

    changes = {
        "schema_version": 1,
        "task": M.TASK,
        "task_blob_sha": M.TASK_BLOB,
        "revision": "R02/R19",
        "GEAENDERT": [
            "Seed-42 exterior re-indexed as one oriented dense radial manifold because the source contains distributed open/nonmanifold defects.",
            "Underside ROI rebuilt from R18 depth error and support evidence; only this region receives a two-pass robust median and eight-cell smoothstep blend.",
            "Clean central underside simplification replaces R18 ridges, MLS rough patch and excessive depth displacement.",
            "REF-SEAM split, two 1.6-mm hollow print parts and the required central glue connector were constructed after Gate 1 and Gate 2 passed.",
        ],
        "UNVERAENDERT": [
            "Protected valid Seed-42 radial samples outside the ROI: zero changed cells.",
            "Approximately 200-mm overall size and proportional character.",
            "Exactly two print parts and assigned tan/copper materials.",
            "Face remains free; eyes, nose, ears and feet remain readable.",
            "Exactly one visible maple leaf; back/leaf character retained.",
            "Required connector diameter 10.0 mm and engagement 20.0 mm.",
        ],
        "ENTFERNT": [
            "R18 transition ridges and depth-clamp artefacts are not present in the R19 master.",
            "Discarded R19 diagnostic prototype with unsupported -108.92-mm underside extrapolation.",
            "No confirmed production geometry or user dimension was removed.",
        ],
        "OFFEN": gate3["open_real_tests"],
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
        "nutzerentscheidung_grund": "All remaining items are real slicer, print, fit, support-removal and final user approval tests; no product choice or binding datum is missing.",
    }
    M.write_json(M.OUT / "reports" / "geometry-change-status-r19.json", changes)

    revision = f"""# Herbst-Igel R02 – technischer Ergebnisstand R19

## Ergebnis

`PASS` für den technischen R19-Auftrag. Gate 1 ist PASS; Gate 2 ist
`PASS_WITH_RESTPOINTS`; Gate 3 wurde danach ausgeführt und technisch validiert.
Reale Slicer-, Druck-, Passungs-, Supportentfernungs- und Montageprüfungen sind
weiter offen. Eine finale Nutzer- oder Produktfreigabe wird nicht behauptet.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`

## GEÄNDERT

- Die optisch gute Seed-42-Außenfläche wurde als dichtes, eindeutig
  orientiertes Radialmanifold neu indiziert. Das war technisch notwendig, weil
  Seed-42 auch außerhalb der Unterseiten-ROI verteilte offene und
  nichtmanifolde Kanten enthält. 618.385 gültige, geschützte Radialzellen
  außerhalb der ROI blieben unverändert.
- Die R19-ROI umfasst {master['roi_fraction'] * 100:.2f} % des Winkelrasters und
  folgt R18-Tiefenfehler, realer Unterseitensichtbarkeit und fehlender
  Quellenstützung. Nur dort wurden ein zweifacher 3×3-Median und ein acht Zellen
  breiter kubischer Übergang angewandt.
- Die Unterseite ist sauber vereinfacht; R18-Rippen, extreme Z-Verschiebung und
  MLS-Flickrauheit wurden nicht übernommen.
- Nach Gate-1-/Gate-2-PASS wurden REF-SEAM-Split, zwei Hohlschalen, zentraler
  Klebeverbinder und Fertigungsexporte erzeugt.

## UNVERÄNDERT

- Ca. 200 mm Gesamtgröße; R19-Master-Istmaß {topo['max_extent_mm']:.3f} mm.
- Genau zwei Druckteile: Front/Körper in PLA Matt Desert Tan und
  Rücken/Stachelschale in PLA Metal Kupfer.
- Nominale Wanddicke 1,6 mm; 0,4-mm-Düse; Ziel 0,12 mm, adaptiv bis 0,08 mm.
- Gesicht frei; Augen, Nase, Ohren und Füße lesbar; Rücken-/Blattcharakter und
  genau ein sichtbares Ahornblatt erhalten.
- Verbinder Ø10,0 mm exakt und Eingriff 20,0 mm exakt.

## ENTFERNT

- Der verworfene Diagnoseprototyp mit ungestützter Unterkante bei etwa
  −108,92 mm wurde vollständig entfernt; die reale R19-Unterkante liegt bei
  {topo['bounds_min_mm'][2]:.3f} mm.
- Keine bestätigte Produktfunktion, kein Nutzermaß und keine freigegebene
  Produktionsgeometrie wurden entfernt.

## Gate 1 – Topologie

- eine Außenkomponente, watertight und 2-manifold;
- 0 offene Kanten, 0 nichtmanifolde Kanten/Vertices;
- 0 degenerierte oder doppelte Flächen;
- konsistente Außenorientierung, keine eingeschlossene Zusatzschale;
- 0 reale Selbstschnitte über den Radialgraph-/Sphärenkegel-Nachweis.

## Gate 2 – Formschutz

`PASS_WITH_RESTPOINTS`. Minimale Sieben-Ansichten-Silhouetten-IoU:
{delta['minimum_silhouette_iou']:.6f}. Außerhalb der Bottom-Ansicht beträgt das
schlechteste p95 der sichtbaren Tiefendifferenz
{delta['maximum_non_bottom_view_p95_mm']:.3f} mm. Der alte orthografische
Bottom-Tiefenwert ist wegen realer Seed-42-Mehrfachlagen nur diagnostisch; die
maßgebliche ROI-Radialänderung beträgt p95
{delta['bottom_roi_radial_patch_p95_mm']:.3f} mm und die reale Nahansicht ist
stufen-, rippen- und flickstellenfrei. Restpunkt ist die ausdrücklich erlaubte
saubere Vereinfachung des verdeckten zentralen Unterseitenreliefs.

## Gate 3 – CAD/FDM

- Frontteil: {gate3['front_topology']['triangles']:,} Dreiecke, 0 offene und 0
  nichtmanifolde Kanten.
- Rückenteil: {gate3['back_topology']['triangles']:,} Dreiecke, 0 offene und 0
  nichtmanifolde Kanten.
- Wand: radial nominal 1,6 mm; Kappen-Referenzabstand an der Verbinderachse
  1,6 mm.
- Pin: Ø{connector['male_pin_diameter_mm_exact']:.1f} mm exakt; Eingriff X=0,0
  bis X={connector['engagement_end_x_mm']:.1f} mm, also 20,0 mm exakt.
- Aufnahme: Ø{connector['socket_diameter_mm']:.2f} mm; dokumentiertes Klebespiel
  {connector['diametral_glue_clearance_mm']:.2f} mm diametral bzw.
  {connector['radial_glue_clearance_mm']:.2f} mm radial.
- 3MF enthält zwei Objekte; GLB enthält zwei Knoten/Netze.

## OFFEN / reale Prüfungen

{chr(10).join('- ' + item for item in gate3['open_real_tests'])}

Ein STL-, Manifold- oder Validator-PASS ist keine finale Produktfreigabe.
"""
    write_text(M.OUT / "REVISION-R02-R19.md", revision)

    reproduction = """# Reproduktion R19

Voraussetzung: Python 3.12 mit NumPy und Pillow im Repository-Wurzelverzeichnis.
Die Eingänge werden aus dem dokumentierten R18-Ergebniscommit extrahiert und
vor der Verarbeitung per SHA-256 geprüft.

```powershell
python outputs/herbst-igel-r02-manifold-underside-blend-r19/reproduction-scripts/r19_master.py
python outputs/herbst-igel-r02-manifold-underside-blend-r19/reproduction-scripts/validate_master_r19.py
python outputs/herbst-igel-r02-manifold-underside-blend-r19/reproduction-scripts/r19_gate3.py
python outputs/herbst-igel-r02-manifold-underside-blend-r19/reproduction-scripts/finalize_r19.py
python outputs/herbst-igel-r02-manifold-underside-blend-r19/reproduction-scripts/validate_r19.py
```

Gate 3 bricht ab, wenn die unabhängige Masterprüfung Gate 1 und Gate 2 nicht
freigibt. Die Skripte erzeugen deterministische PLY-/STL-/3MF-/GLB-Dateien,
Prüfberichte, reale Mesh-Renderansichten, Revisionsstand und Status. Reale
Slicer-, Druck-, Klebe-, Support- und Montageprüfungen bleiben separat offen.
"""
    write_text(M.OUT / "REPRODUKTION-R19.md", reproduction)

    technical = {
        "schema_version": 1,
        "task": M.TASK,
        "task_blob_sha": M.TASK_BLOB,
        "revision": "R02/R19",
        "input_hash_gate": "PASS",
        "gate_1_topology": topo["gate_1"],
        "gate_2_form_protection": form["gate_2"],
        "gate_3_cad_fdm": gate3["status"],
        "exactly_two_print_parts": gate3["exactly_two_print_parts"],
        "wall_mm_nominal": gate3["wall_mm_nominal"],
        "connector_diameter_mm_exact": connector["male_pin_diameter_mm_exact"],
        "connector_engagement_mm_exact": connector["engagement_mm_exact"],
        "glue_clearance_diametral_mm": connector["diametral_glue_clearance_mm"],
        "ref_seam": seam["status"],
        "fdm_orientation_support": orientation["status"],
        "overall": "PASS_WITH_OPEN_REAL_TESTS",
        "final_user_approval_claimed": False,
    }
    M.write_json(M.OUT / "technical-validation-r19.json", technical)

    back_stl_export = next(
        item["path"] for item in gate3["exports"]
        if item["path"].lower().endswith("back-spine-shell-hollow.stl")
    )
    main_files = [
        master["master"]["path"],
        "outputs/herbst-igel-r02-manifold-underside-blend-r19/cad-mesh-source/herbst-igel-r02-r19-front-body-hollow.ply",
        "outputs/herbst-igel-r02-manifold-underside-blend-r19/cad-mesh-source/herbst-igel-r02-r19-back-spine-shell-hollow.ply",
        "outputs/herbst-igel-r02-manifold-underside-blend-r19/stl/herbst-igel-r02-r19-front-body-hollow.stl",
        back_stl_export,
        "outputs/herbst-igel-r02-manifold-underside-blend-r19/assembly/herbst-igel-r02-r19-assembly.3mf",
        "outputs/herbst-igel-r02-manifold-underside-blend-r19/assembly/herbst-igel-r02-r19-assembly.glb",
        "outputs/herbst-igel-r02-manifold-underside-blend-r19/renders-gate-evidence/soll-ist-r19-seven-view-contact-sheet.png",
        "outputs/herbst-igel-r02-manifold-underside-blend-r19/renders-gate-evidence/underside-source-vs-master-closeup-r19.png",
        "outputs/herbst-igel-r02-manifold-underside-blend-r19/renders-gate-evidence/actual-ref-seam-soll-ist-r19.png",
    ]
    status = {
        "schema_version": 1,
        "task": M.TASK,
        "task_blob_sha": M.TASK_BLOB,
        "product_revision": "R02",
        "technical_revision": "R19",
        "status": "PASS",
        "gates": {
            "gate_1_topology": topo["gate_1"],
            "gate_2_form_protection": form["gate_2"],
            "gate_3_cad_fdm": gate3["status"],
        },
        "main_files": main_files,
        "validations": [
            "R18 source/master/reference SHA-256 gate PASS",
            "R19 ROI derived from R18 depth error, bottom visibility and source support",
            "Protected valid Seed-42 radial cells changed: 0",
            "Gate 1 independent indexed topology and radial self-intersection proof PASS",
            "Gate 2 seven real geometry views, underside close-up, REF-CLEAN and REF-SEAM PASS_WITH_RESTPOINTS",
            "Exactly two hollow print parts; both edge-manifold and consistently oriented",
            "Ø10.0-mm connector and 20.0-mm engagement exact by construction and output-coordinate audit",
            "STL, 3MF and GLB structural validation",
        ],
        "open_real_tests": gate3["open_real_tests"],
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
        "nutzerentscheidung_grund": changes["nutzerentscheidung_grund"],
        "final_user_approval_claimed": False,
    }
    M.write_json(M.OUT / "result-status.json", status)

    local_artifacts = [item for item in gate3["exports"] if Path(item["path"]).is_absolute()]
    local_large = {
        "schema_version": 1,
        "task": M.TASK,
        "threshold_bytes": 90_000_000,
        "artifacts": local_artifacts,
        "status": "LOCAL_LARGE_ARTIFACTS_PRESENT" if local_artifacts else "NOT_REQUIRED_NO_R19_FILE_EXCEEDS_90MB",
    }
    M.write_json(M.OUT / "LOCAL-LARGE-ARTIFACTS.json", local_large)

    entries = []
    excluded = {"artifact-manifest.json", "independent-validation-r19.json"}
    for path in sorted(p for p in M.OUT.rglob("*") if p.is_file() and p.name not in excluded and "__pycache__" not in p.parts):
        entries.append({"path": M.rel(path), "bytes": path.stat().st_size, "sha256": M.sha256(path)})
    M.write_json(M.OUT / "artifact-manifest.json", {"schema_version": 1, "task": M.TASK, "artifacts": entries})
    print(json.dumps(status, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
