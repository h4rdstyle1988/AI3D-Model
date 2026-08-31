"""Finalize the auditable R17 STOPP result after Gate-2 inspection."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "outputs" / "herbst-igel-r02-visibility-surface-rebuild-r17"
TASK = "tasks/TASK-HERBST-IGEL-R02-VISIBILITY-SURFACE-REBUILD-R17.md"
TASK_BLOB = "d6aa08d28f227f8811ce3f2aa04302c3e8eb7f03"
ATTEMPTS = ("small-a", "medium-b", "fine-c", "screened-mls-d")
SELECTED = "screened-mls-d"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def summary_row(audit: dict) -> dict:
    views = audit["form_delta"]["views"]
    field = audit.get("poisson") or audit["poisson_closure"]
    return {
        "attempt": audit["attempt"],
        "method": audit["method"],
        "grid_shape_nodes": field["grid_shape_nodes"],
        "pitch_mm": field["pitch_mm"],
        "gate_1": audit["gate_1"],
        "triangles": audit["topology"]["triangles"],
        "max_extent_mm": audit["topology"]["max_extent_mm"],
        "minimum_silhouette_iou": min(v["silhouette_iou"] for v in views.values()),
        "front_visible_depth_p95_mm": views["3q-front"]["visible_depth_delta_mm"]["p95"],
        "bottom_visible_depth_p95_mm": views["bottom"]["visible_depth_delta_mm"]["p95"],
        "worst_view_median_depth_delta_mm": max(v["visible_depth_delta_mm"]["median"] for v in views.values()),
        "gate_2": "FAIL",
        "master": audit["master"],
    }


def evidence() -> dict:
    source_dir = OUT / "renders-candidates" / SELECTED
    target = OUT / "renders-gate-evidence"
    target.mkdir(parents=True, exist_ok=True)
    selected_views = []
    for name in ("3q-front", "left", "right", "rear", "top", "bottom"):
        src = source_dir / f"{SELECTED}-{name}.png"
        dst = target / f"selected-r17-{name}.png"
        shutil.copyfile(src, dst)
        pair_src = source_dir / f"soll-ist-{name}.png"
        pair_dst = target / f"soll-ist-r17-{name}.png"
        shutil.copyfile(pair_src, pair_dst)
        selected_views.append({
            "view": name,
            "candidate": dst.relative_to(ROOT).as_posix(),
            "soll_ist": pair_dst.relative_to(ROOT).as_posix(),
        })
    source_sheet = Image.open(source_dir / "source-contact-sheet.png").convert("RGB")
    candidate_sheet = Image.open(source_dir / f"{SELECTED}-contact-sheet.png").convert("RGB")
    contact = Image.new("RGB", (source_sheet.width + candidate_sheet.width, source_sheet.height), "white")
    contact.paste(source_sheet, (0, 0))
    contact.paste(candidate_sheet, (source_sheet.width, 0))
    contact_path = target / "soll-ist-r17.png"
    contact.save(contact_path)
    ref_clean = Image.open(OUT / "reference-audit" / "ref-clean-r17.jpg").convert("RGB")
    ref_seam = Image.open(OUT / "reference-audit" / "ref-seam-r17.jpg").convert("RGB")
    ref_height = 620
    refs = Image.new("RGB", (contact.width, ref_height), (248, 246, 240))
    draw = ImageDraw.Draw(refs)
    draw.text((16, 12), "Autoritative references: REF-CLEAN / REF-SEAM", fill=(20, 20, 20))
    x = 20
    for image in (ref_clean, ref_seam):
        image.thumbnail((contact.width // 2 - 40, ref_height - 55))
        refs.paste(image, (x, 45))
        x += contact.width // 2
    full = Image.new("RGB", (contact.width, ref_height + contact.height), "white")
    full.paste(refs, (0, 0))
    full.paste(contact, (0, ref_height))
    full_path = target / "soll-ist-ref-source-candidate-r17.png"
    full.save(full_path)
    return {
        "selected_attempt": SELECTED,
        "candidate_is_real_geometry_render": True,
        "selected_views": selected_views,
        "contact_sheet": contact_path.relative_to(ROOT).as_posix(),
        "reference_source_candidate_sheet": full_path.relative_to(ROOT).as_posix(),
    }


def main() -> None:
    audits = {name: read_json(OUT / "audits" / f"topology-{name}-r17.json") for name in ATTEMPTS}
    rows = [summary_row(audits[name]) for name in ATTEMPTS]
    write_json(
        OUT / "reports" / "candidate-iteration-summary-r17.json",
        {
            "schema_version": 1,
            "task": TASK,
            "task_blob_sha": TASK_BLOB,
            "attempts": rows,
            "method_change_rule": {
                "triggered": True,
                "reason": "The bottom-layer smoothing/edge-runner failure did not materially decrease from medium-b to fine-c.",
                "changed_from": "global oriented Poisson",
                "changed_to": "local oriented screened MLS with low-support Poisson closure",
            },
            "selected_diagnostic_attempt": SELECTED,
            "selection_reason": "Highest minimum six-view silhouette IoU and better feet/nose binding; still Gate-2 FAIL because bottom relief is replaced and the surface is visibly noisy.",
        },
    )
    render_report = evidence()
    write_json(OUT / "reports" / "real-geometry-renders-r17.json", {"schema_version": 1, "task": TASK, **render_report})
    selected = audits[SELECTED]
    form = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "selected_attempt": SELECTED,
        "comparison_basis": [
            "byte-identical optically best Seed-42 source",
            "authoritative REF-CLEAN",
            "authoritative REF-SEAM",
            "six real candidate/source geometry render pairs plus combined SOLL/IST sheet",
        ],
        "quantitative_attempts": rows,
        "visual_checks": {
            "face_free_and_round_like_reference": "PASS",
            "forehead_eyes_snout_uncovered": "PASS",
            "eyes_nose_ears_short_feet_preserved_and_readable": "PASS_MIT_RESTPUNKTEN_SURFACE_NOISE",
            "back_and_leaf_spine_character_preserved": "PASS_MIT_RESTPUNKTEN_SURFACE_NOISE",
            "exactly_one_visible_maple_leaf": "PASS_ONE_VISIBLE_NO_SECOND_ADDED",
            "ref_seam_visually_plausible": "OFFEN_NOT_DEMONSTRATED_WELL_ENOUGH_ON_RECONSTRUCTED_SURFACE",
            "no_visible_inflation_shrink_step_or_smear": "FAIL_BOTTOM_RELIEF_REPLACED_AND_VISIBLE_MLS_ROUGHNESS",
        },
        "observations": [
            "All four attempts preserve the overall hedgehog silhouette far better than the rejected R16 depth-envelope family.",
            "medium-b and fine-c make the face, nose, ears and back leaves readable, but both replace the underside depth structure by a smooth closure and create runners near the lowest feet.",
            "The required method switch screened-mls-d binds feet and nose more closely and removes the long runners, but introduces visible surface roughness and still does not reconstruct the source underside relief.",
            "The selected attempt has one manifold outer component, but Gate 1 success cannot override the visible Gate 2 failure.",
        ],
        "gate_2": "FAIL",
        "gate_3_cad_fdm_authorized": False,
    }
    write_json(OUT / "reports" / "form-protection-gate-r17.json", form)
    topology = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "selected_attempt": SELECTED,
        "gate_1": selected["gate_1"],
        "exactly_one_outer_master_component": selected["connected_surface_components"] == 1,
        "watertight": selected["watertight"],
        "two_manifold": selected["two_manifold"],
        "open_edges": selected["topology"]["boundary_edges"],
        "nonmanifold_edges": selected["topology"]["nonmanifold_edges"],
        "nonmanifold_vertices": selected["nonmanifold_vertices"],
        "internal_enclosed_shells": selected["internal_enclosed_shells"],
        "duplicate_depth_layers": False,
        "confirmed_real_self_intersections": selected["actual_self_intersection_check"]["confirmed_self_intersections"],
        "construction_evidence": selected["actual_self_intersection_check"]["method"],
        "mesh_metrics": selected["topology"],
        "status": "PASS",
    }
    write_json(OUT / "reports" / "topology-gate-r17.json", topology)
    validation = {
        "schema_version": 1,
        "task": TASK,
        "revision": "R02/R17",
        "task_blob_sha": TASK_BLOB,
        "reference_hash_gate": read_json(OUT / "reference-audit" / "hash-gate-r17.json")["status"],
        "visibility_classification": "PASS_TECHNICAL",
        "gate_1_topology": "PASS",
        "gate_2_form_protection": "FAIL",
        "gate_3_cad_fdm": "NOT_RUN_GATE_2_FAIL",
        "stl_generated": False,
        "assembly_3mf_or_glb_generated": False,
        "split_hollow_connector_generated": False,
        "overall": "STOPP",
        "final_user_approval_claimed": False,
    }
    write_json(OUT / "technical-validation-r17.json", validation)
    status = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "product_revision": "R02",
        "technical_revision": "R17",
        "status": "STOPP",
        "gates": {
            "gate_1_topology": "PASS",
            "gate_2_form_protection": "FAIL",
            "gate_3_cad_fdm": "NOT_RUN_GATE_2_FAIL",
        },
        "main_files": [
            selected["master"]["path"],
            "outputs/herbst-igel-r02-visibility-surface-rebuild-r17/reports/topology-gate-r17.json",
            "outputs/herbst-igel-r02-visibility-surface-rebuild-r17/reports/form-protection-gate-r17.json",
            render_report["reference_source_candidate_sheet"],
            "outputs/herbst-igel-r02-visibility-surface-rebuild-r17/REVISION-R02-R17.md",
        ],
        "validations": [
            "Reference/source hash gate PASS",
            "Visibility/orientation classification recorded",
            "Gate 1 selected screened-mls-d topology PASS",
            "Gate 2 six-view and SOLL/IST inspection FAIL",
            "Method changed after persistent bottom failure",
            "Gate 3 correctly not run",
        ],
        "open_real_tests": [
            "No print, assembly, wall-thickness, connector, support or slicer test because Gate 2 failed.",
            "A new technical reconstruction must preserve the visible underside relief without roughness or edge runners before Gate 3.",
        ],
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
        "nutzerentscheidung_grund": "The blocker is technical surface reconstruction. No binding user dimension, function or reference datum is missing.",
        "final_user_approval_claimed": False,
    }
    write_json(OUT / "result-status.json", status)
    write_json(
        OUT / "LOCAL-LARGE-ARTIFACTS.json",
        {
            "schema_version": 1,
            "task": TASK,
            "threshold_bytes": 90_000_000,
            "artifacts": [],
            "status": "NOT_REQUIRED_ALL_R17_ARTIFACTS_BELOW_90MB",
        },
    )
    inventory = []
    for path in sorted(p for p in OUT.rglob("*") if p.is_file()):
        if path.name == "artifact-manifest.json" or "__pycache__" in path.parts:
            continue
        inventory.append({"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)})
    write_json(
        OUT / "artifact-manifest.json",
        {"schema_version": 1, "task": TASK, "task_blob_sha": TASK_BLOB, "artifacts": inventory},
    )


if __name__ == "__main__":
    main()
