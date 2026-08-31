"""Create the R16 gate summary, revision record, and artifact manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "outputs" / "herbst-igel-r02-envelope-rebuild-r16"
TASK = "tasks/TASK-HERBST-IGEL-R02-ENVELOPE-REBUILD-R16.md"
TASK_BLOB = "5d2d6ab9d3d2cb522e65e8a1de57dddc3e872e62"


def read_json(relative: str):
    return json.loads((OUT / relative).read_text(encoding="utf-8"))


def write_json(relative: str, payload) -> None:
    path = OUT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def form_attempt(slug: str):
    report = read_json(f"reports/bidirectional-form-protection-{slug}-r16.json")
    worst_p95 = max(
        item["bidirectional_visible_depth_delta_mm"]["p95"]
        for item in report["views"].values()
    )
    minimum_iou = min(
        item["silhouette_iou"] for item in report["views"].values()
    )
    return {
        "attempt": slug,
        "worst_visible_depth_p95_mm": worst_p95,
        "minimum_silhouette_iou": minimum_iou,
        "gate_2": "FAIL",
    }


def main() -> None:
    coarse = read_json("audits/topology-envelope-coarse-a-r16.json")
    fine = read_json("audits/topology-envelope-fine-b-r16.json")
    no_close = read_json(
        "audits/topology-envelope-fine-c-no-close-r16.json"
    )
    hash_gate = read_json("reference-audit/hash-gate-r16.json")
    render_report = read_json("reports/real-geometry-renders-r16.json")

    form = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "selected_attempt": "fine-b",
        "comparison_basis": [
            "byte-identical optically best Seed-42 source",
            "authoritative REF-CLEAN",
            "authoritative REF-SEAM",
            "six real geometry renders plus SOLL/IST sheet",
        ],
        "quantitative_attempts": [
            form_attempt("coarse-a"),
            form_attempt("fine-b"),
        ],
        "visual_checks": {
            "face_free_and_round_like_reference": "FAIL",
            "forehead_eyes_snout_uncovered": "FAIL",
            "eyes_nose_ears_short_feet_preserved_and_readable": "FAIL",
            "back_and_leaf_spine_character_preserved": "FAIL",
            "exactly_one_visible_maple_leaf": "FAIL_NOT_READABLE",
            "ref_seam_visually_plausible": "FAIL_NOT_READABLE",
            "no_visible_remesh_inflation_shrink_step_or_smear": "FAIL",
        },
        "observations": [
            "The outer silhouette remains close, but the envelope fills visible face and leaf relief into a largely opaque mass.",
            "Fine-b improves median depth error over coarse-a but retains multi-millimetre to centimetre p95 errors in every oblique/side view.",
            "The selected render does not show readable eyes, nose, ears, face boundary, or the single maple leaf.",
            "Resolution iteration therefore cannot cure the projection-envelope method's depth-layer bridging.",
        ],
        "gate_2": "FAIL",
        "gate_3_cad_fdm_authorized": False,
    }
    write_json("reports/form-protection-gate-r16.json", form)

    iteration = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "attempts": [
            {
                "attempt": "coarse-a",
                "pitch_mm": coarse["grid"]["actual_pitch_mm"],
                "closing_radius_voxels": 1,
                "gate_1": coarse["status"],
                "gate_2": "FAIL",
            },
            {
                "attempt": "fine-b",
                "pitch_mm": fine["grid"]["actual_pitch_mm"],
                "closing_radius_voxels": 2,
                "gate_1": fine["status"],
                "gate_2": "FAIL",
            },
            {
                "attempt": "fine-c-no-close",
                "pitch_mm": no_close["grid"]["actual_pitch_mm"],
                "closing_radius_voxels": 0,
                "gate_1": no_close["status"],
                "gate_1_failure": {
                    "connected_surface_components": no_close[
                        "connected_surface_components"
                    ],
                    "internal_enclosed_shells": no_close[
                        "internal_enclosed_shells"
                    ],
                },
                "gate_2": "NOT_RUN_GATE_1_FAIL",
            },
        ],
        "technical_conclusion": (
            "Closing is required to obtain one component, but the large Gate-2 "
            "depth and visual failures persist across the two closed resolutions. "
            "Further pitch-only iteration is not technically meaningful."
        ),
    }
    write_json("reports/envelope-iteration-summary-r16.json", iteration)

    validation = {
        "schema_version": 1,
        "task": TASK,
        "revision": "R16",
        "task_blob_sha": TASK_BLOB,
        "reference_hash_gate": hash_gate["status"],
        "gate_1_topology": {
            "status": fine["status"],
            "selected_attempt": "fine-b",
            "connected_components": fine["connected_surface_components"],
            "watertight": fine["watertight"],
            "two_manifold": fine["two_manifold"],
            "boundary_edges": fine["topology"]["boundary_edges"],
            "nonmanifold_edges": fine["topology"]["nonmanifold_edges"],
            "nonmanifold_vertices": fine["nonmanifold_vertices"],
            "degenerate_faces": fine["topology"]["degenerate_faces"],
            "duplicate_faces": fine["topology"]["duplicate_faces"],
            "confirmed_self_intersections": fine[
                "actual_self_intersection_check"
            ]["confirmed_self_intersections"],
            "internal_enclosed_shells": fine["internal_enclosed_shells"],
            "overlapping_double_skin": fine["overlapping_double_skin"],
        },
        "gate_2_form_protection": {
            "status": "FAIL",
            "report": "outputs/herbst-igel-r02-envelope-rebuild-r16/reports/form-protection-gate-r16.json",
            "real_views": len(render_report["selected_views"]),
            "soll_ist_present": (OUT / render_report["soll_ist_sheet"]).is_file()
            if not Path(render_report["soll_ist_sheet"]).is_absolute()
            else Path(render_report["soll_ist_sheet"]).is_file(),
        },
        "gate_3_cad_fdm": {
            "status": "NOT_RUN_GATE_2_FAIL",
            "stl_generated": False,
            "assembly_3mf_or_glb_generated": False,
            "split_hollow_connector_generated": False,
        },
        "overall": "STOPP",
        "final_user_approval_claimed": False,
    }
    # The manifest path in the render report is repository-relative.
    validation["gate_2_form_protection"]["soll_ist_present"] = (
        ROOT / render_report["soll_ist_sheet"]
    ).is_file()
    write_json("technical-validation-r16.json", validation)

    status = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "product_revision": "R02",
        "technical_revision": "R16",
        "status": "STOPP",
        "gates": {
            "gate_1_topology": "PASS",
            "gate_2_form_protection": "FAIL",
            "gate_3_cad_fdm": "NOT_RUN_GATE_2_FAIL",
        },
        "main_files": [
            "outputs/herbst-igel-r02-envelope-rebuild-r16/masterform/herbst-igel-r02-r16-envelope-master-200mm.ply",
            "outputs/herbst-igel-r02-envelope-rebuild-r16/audits/topology-envelope-fine-b-r16.json",
            "outputs/herbst-igel-r02-envelope-rebuild-r16/reports/form-protection-gate-r16.json",
            "outputs/herbst-igel-r02-envelope-rebuild-r16/renders-gate-evidence/envelope-r16-contact-sheet.png",
            "outputs/herbst-igel-r02-envelope-rebuild-r16/renders-gate-evidence/soll-ist-r16.png",
            "outputs/herbst-igel-r02-envelope-rebuild-r16/REVISION-R16.md",
        ],
        "validations": [
            "Reference and source hash gate PASS",
            "Gate 1 selected fine-b topology PASS",
            "Gate 2 quantitative bidirectional visible-depth audit FAIL",
            "Gate 2 real six-view and SOLL/IST inspection FAIL",
            "No-close targeted iteration Gate 1 FAIL with 45 enclosed shells",
            "Gate 3 correctly not run",
        ],
        "open_real_tests": [
            "No print or physical fit test: manufacturing geometry was correctly not generated after Gate 2 FAIL.",
            "A different deterministic exterior-surface reconstruction method must pass Gate 2 before split/hollow/connector work.",
        ],
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
        "nutzerentscheidung_grund": (
            "The blocker is technical: the tested six-depth-map voxel envelope "
            "bridges visible depth layers and destroys readable exterior detail. "
            "No binding product dimension or function needs a user choice."
        ),
        "final_user_approval_claimed": False,
    }
    write_json("result-status.json", status)

    inventory = []
    for path in sorted(p for p in OUT.rglob("*") if p.is_file()):
        if path.name == "artifact-manifest.json" or "__pycache__" in path.parts:
            continue
        inventory.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    write_json(
        "artifact-manifest.json",
        {
            "schema_version": 1,
            "task": TASK,
            "task_blob_sha": TASK_BLOB,
            "artifacts": inventory,
        },
    )


if __name__ == "__main__":
    main()
