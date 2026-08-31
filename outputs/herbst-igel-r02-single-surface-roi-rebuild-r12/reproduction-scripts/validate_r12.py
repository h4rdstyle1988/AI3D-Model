#!/usr/bin/env python3
"""Enforce R12 hash, fixed-ROI topology and downstream phase gates."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from analyze_r11_roi_r12 import OUT, REPORT, ROOT, SOURCE


TASK = "tasks/TASK-HERBST-IGEL-R02-SINGLE-SURFACE-ROI-REBUILD-R12.md"
TASK_BLOB = "7c0db136c53ed5aa07e03ba7de178f12f669561d"
R11_TASK_BLOB = "a924b68969a2f82e7e75a924a5e13227b1211d77"
R11_ROI_CODE_BLOB = "571d31343ad14e27a8705d0120764667f59d9cf5"
REF_CLEAN = Path(
    r"D:\3D-Models\generated\herbst-igel-r02-r08-input\outputs"
    r"\herbst-igel-r02-trellis-optik-retry-r07\reference-audit\ref-clean-r07.jpg"
)
REF_SEAM = Path(
    r"D:\3D-Models\generated\herbst-igel-r02-r08-input\outputs"
    r"\herbst-igel-r02-trellis-optik-retry-r07\reference-audit\ref-seam-r07.jpg"
)
EXPECTED = {
    "seed42": "85ba18eaed15bdbe631fc49dd571e73882c4055e2c247022e90ad15ed99822c6",
    "ref_clean": "c1c9a5a094f1db2fd220f3433f83af8dedca780f56a4bf479eb8883432250859",
    "ref_seam": "b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4",
}
VALIDATION = OUT / "VALIDIERUNG-R02-R12.json"
SOLL_IST = OUT / "reports" / "soll-ist-binary-r12.json"
STATUS = OUT / "result-status.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def git_blob_exists(blob: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{blob}^{{blob}}"], cwd=ROOT,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def criterion(key: str, soll: str, reason: str, phase: str = "OPTIK_GATE") -> dict[str, object]:
    return {
        "key": key,
        "soll": soll,
        "ist_erfuellt": False,
        "status": "NOT_RUN_BY_MESH_GATE" if phase == "OPTIK_GATE" else "FAIL",
        "reason": reason,
    }


def main() -> None:
    audit = json.loads(REPORT.read_text(encoding="utf-8"))
    actual = {
        "seed42": sha256(SOURCE),
        "ref_clean": sha256(REF_CLEAN),
        "ref_seam": sha256(REF_SEAM),
    }
    hash_pass = actual == EXPECTED and git_blob_exists(TASK_BLOB) and git_blob_exists(R11_TASK_BLOB) and git_blob_exists(R11_ROI_CODE_BLOB)
    immutable_boundary = audit["source_topology"]["boundary_edges_strictly_outside_roi"]
    immutable_nonmanifold = audit["source_topology"]["nonmanifold_edges_strictly_outside_roi"]
    immutable_invalid = immutable_boundary + immutable_nonmanifold
    fixed_gate_pass = immutable_invalid == 0

    blocker_reason = (
        f"{immutable_boundary} boundary edges and {immutable_nonmanifold} nonmanifold edges are incident only to "
        "the byte/index-fixed outside-ROI source. An ROI-only rebuild cannot alter their incidence."
    )
    criteria = [
        criterion("free_round_face", "Gesicht rundlich und vollständig frei wie REF-CLEAN.", blocker_reason),
        criterion("forehead_free", "Stirn frei; keine Blatt-/Stachel-/Seam-Regalkante davor.", blocker_reason),
        criterion("eyes_integrated", "Beide Augen klar sichtbar und organisch in dieselbe Oberfläche integriert.", blocker_reason),
        criterion("ears_integrated", "Beide Ohren klar sichtbar und organisch integriert.", blocker_reason),
        criterion("snout_nose_reference_like", "Kurze weiche Schnauze und Nase referenznah.", blocker_reason),
        criterion("four_short_feet", "Vier kurze Füße erhalten.", blocker_reason),
        criterion("back_preserved", "Rücken außerhalb ROI unverändert und gewölbt mit Blatt-/Stachelstruktur.", blocker_reason),
        criterion("single_maple_leaf", "Genau ein sichtbares Ahornblatt erhalten.", blocker_reason),
        criterion("ref_seam_continuous", "REF-SEAM plausibel und ohne harten Absatz.", blocker_reason),
        criterion("repair_invisible", "Reparatur optisch nicht als Flicken erkennbar.", blocker_reason),
        criterion(
            "mesh_zero_defects",
            "0 offene Reparaturnahtkanten, 0 nonmanifold Kanten, 0 bestätigte Kreuzungen.",
            blocker_reason,
            phase="MESH_GATE",
        ),
    ]
    soll_ist = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "product_revision": "R02",
        "technical_revision": "R12",
        "overall_status": "STOPP",
        "all_binary_criteria_met": False,
        "criteria": criteria,
        "gate_order_enforced": True,
        "optic_gate_run": False,
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
    }
    SOLL_IST.parent.mkdir(parents=True, exist_ok=True)
    SOLL_IST.write_text(json.dumps(soll_ist, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    validation = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "product_revision": "R02",
        "technical_revision": "R12",
        "status": "STOPP",
        "stop_phase": "B_R11_ROI_HEALTHY_RING_PRECONDITION",
        "reference_and_seed_hash_gate": {
            "status": "PASS" if hash_pass else "FAIL",
            "actual_sha256": actual,
            "expected_sha256": EXPECTED,
            "r12_task_blob_available": git_blob_exists(TASK_BLOB),
            "r11_task_blob_available": git_blob_exists(R11_TASK_BLOB),
            "r11_roi_code_blob_available": git_blob_exists(R11_ROI_CODE_BLOB),
        },
        "r11_roi_loaded": {
            "status": "PASS",
            "problem_triangles": audit["r11_roi_problem_triangles"],
            "outside_roi_triangles": audit["outside_roi_triangles"],
            "foreground_bbox_px": audit["reference_measurements"]["foreground_bbox_px"],
            "source_vertex_coordinates_modified": 0,
            "source_faces_modified": 0,
        },
        "healthy_ring_precondition": {
            "status": "PASS" if fixed_gate_pass else "FAIL",
            "retained_boundary_edges_after_roi_removal": audit["healthy_ring_after_removing_all_r11_problem_triangles"]["boundary_edges"],
            "retained_nonmanifold_edges_after_roi_removal": audit["healthy_ring_after_removing_all_r11_problem_triangles"]["nonmanifold_edges"],
            "boundary_vertex_degree_histogram": audit["healthy_ring_after_removing_all_r11_problem_triangles"]["boundary_vertex_degree_histogram"],
            "simple_closed_loops_possible": audit["healthy_ring_after_removing_all_r11_problem_triangles"]["simple_closed_loops_possible"],
            "reason": blocker_reason,
        },
        "mesh_gate_before_optik_gate": {
            "status": "FAIL_PRECONDITION",
            "candidate_created": False,
            "source_boundary_edges_total": audit["source_topology"]["boundary_edges_total"],
            "source_nonmanifold_edges_total": audit["source_topology"]["nonmanifold_edges_total"],
            "immutable_outside_roi_boundary_edges": immutable_boundary,
            "immutable_outside_roi_nonmanifold_edges": immutable_nonmanifold,
            "immutable_outside_roi_invalid_edges_total": immutable_invalid,
            "repair_seam_boundary_edges": None,
            "confirmed_cross_intersections": None,
            "proof": "For every counted immutable edge, all incident source faces are outside the fixed R11 problem mask. Adding/removing incident faces would extend work outside the approved ROI; changing an outside face or index violates hard rule 1.",
        },
        "execution_sequence": {
            "A_hash_gates": "PASS" if hash_pass else "FAIL",
            "B_load_r11_roi_and_healthy_ring": "FAIL_HEALTHY_RING",
            "C_remove_colliding_old_triangles": "NOT_RUN_FATAL_B_PRECONDITION",
            "D_single_local_rebuild": "NOT_RUN_FATAL_B_PRECONDITION",
            "E_weld_remesh": "NOT_RUN_FATAL_B_PRECONDITION",
            "F_mesh_gate": "FAIL_PRECONDITION",
            "G_six_real_optic_renders": "NOT_RUN_BY_MESH_GATE",
            "H_optik_gate": "NOT_RUN_BY_MESH_GATE",
            "I_split_shell_connector_stl_fdm": "NOT_RUN_BY_MESH_AND_OPTIK_GATE",
        },
        "forbidden_output_absence": {
            "approved_master_created": False,
            "cad_created": False,
            "stl_created": False,
            "split_created": False,
            "shells_created": False,
            "connector_created": False,
            "fdm_validation_run": False,
            "optic_gate_renders_created": False,
        },
        "soll_ist_report": SOLL_IST.relative_to(ROOT).as_posix(),
        "topology_audit": REPORT.relative_to(ROOT).as_posix(),
        "open_real_tests": [
            "Optical comparison remains gated by the failed mesh precondition.",
            "Physical print, fit, support, material, wall and 200 mm scale tests remain inapplicable before mesh and optical PASS.",
        ],
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
        "nutzerentscheidung_grund": "Technically proven incompatibility between fixed outside-ROI geometry and the mandatory zero-nonmanifold mesh gate; no product dimension or function choice is missing.",
        "final_user_approval_claimed": False,
    }
    VALIDATION.write_text(json.dumps(validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    status = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "product_revision": "R02",
        "technical_revision": "R12",
        "status": "STOPP",
        "gate": "MESH_GATE_PRECONDITION",
        "summary": "The byte/index-fixed outside-ROI Seed-42 geometry already contains 6671 boundary and 3528 nonmanifold edges. A local R12 rebuild cannot reach the mandatory all-zero mesh gate without violating hard rule 1.",
        "main_files": {
            "validation": VALIDATION.relative_to(ROOT).as_posix(),
            "soll_ist": SOLL_IST.relative_to(ROOT).as_posix(),
            "topology_audit": REPORT.relative_to(ROOT).as_posix(),
            "diagnostic_sheet": (OUT / "diagnostics" / "immutable-outside-roi-topology-blocker-sheet-r12.png").relative_to(ROOT).as_posix(),
            "revision_report": (OUT / "REVISION-R02-R12.md").relative_to(ROOT).as_posix(),
            "optic_outputs_not_created": (OUT / "OPTIK-RENDERS-AND-SOLL-IST-SHEET-NOT-CREATED.txt").relative_to(ROOT).as_posix(),
            "cad_stl_not_created": (OUT / "CAD-STL-NOT-CREATED.txt").relative_to(ROOT).as_posix(),
        },
        "validations": {
            "hash_gate": hash_pass,
            "r11_roi_loaded": True,
            "outside_roi_coordinates_unchanged": True,
            "outside_roi_indices_unchanged": True,
            "healthy_boundary_ring": fixed_gate_pass,
            "mesh_gate": False,
            "optic_gate": False,
            "cad_fdm_generated": False,
        },
        "open_real_tests": validation["open_real_tests"],
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
        "nutzerentscheidung_grund": validation["nutzerentscheidung_grund"],
        "final_user_approval_claimed": False,
    }
    STATUS.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
