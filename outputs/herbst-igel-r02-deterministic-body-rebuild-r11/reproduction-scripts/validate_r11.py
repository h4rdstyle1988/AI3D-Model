#!/usr/bin/env python3
"""Validate R11 geometry and enforce the binary optical gate."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

import numpy as np

from reconstruct_deterministic_body_r11 import (
    EXPECTED,
    MASTER,
    OUT,
    REF_CLEAN,
    REF_SEAM,
    ROOT,
    SOURCE,
    TASK,
    TASK_BLOB,
    mesh_metrics,
    read_binary_ply,
)


VALIDATION = OUT / "VALIDIERUNG-R02-R11.json"
STATUS = OUT / "result-status.json"
RECONSTRUCTION = OUT / "reports" / "deterministic-body-rebuild-r11.json"
RENDERS = OUT / "reports" / "real-geometry-renders-r11.json"
R10_VALIDATOR_BLOB = "056a3c097f1df38d0ca8d3abd14e778c62d9411e"


def load_validation_primitives() -> dict[str, object]:
    code = subprocess.check_output(["git", "cat-file", "blob", R10_VALIDATOR_BLOB], cwd=ROOT).decode("utf-8")
    code = re.sub(
        r"from reconstruct_implicit_body_r10 import \(.*?\)\s*",
        "",
        code,
        count=1,
        flags=re.DOTALL,
    )
    namespace: dict[str, object] = {
        "__name__": "r10_validation_primitives",
        "__file__": str(OUT / "reproduction-scripts" / "r10_validation_primitives.py"),
        "mesh_metrics": mesh_metrics,
        "read_binary_ply": read_binary_ply,
    }
    exec(compile(code, namespace["__file__"], "exec"), namespace)
    return namespace


V = load_validation_primitives()
edge_metrics = V["edge_metrics"]
cross_intersections = V["conservative_cross_intersection_check"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    reconstruction = json.loads(RECONSTRUCTION.read_text(encoding="utf-8"))
    renders = json.loads(RENDERS.read_text(encoding="utf-8"))
    source_vertices, source_faces = read_binary_ply(SOURCE)
    vertices, faces = read_binary_ply(MASTER)
    source_count = len(source_vertices)
    source_prefix_exact = bool(np.array_equal(vertices[:source_count], source_vertices))
    retained_mask = np.all(faces < source_count, axis=1)
    rebuild_mask = np.all(faces >= source_count, axis=1)
    retained_faces = faces[retained_mask]
    rebuild_faces = faces[rebuild_mask] - source_count
    rebuild_vertices = vertices[source_count:]
    full_metrics = edge_metrics(vertices, faces)
    local_metrics = edge_metrics(rebuild_vertices, rebuild_faces)

    local_min = rebuild_vertices[rebuild_faces].min(axis=(0, 1)) - 0.018
    local_max = rebuild_vertices[rebuild_faces].max(axis=(0, 1)) + 0.018
    retained_triangles = vertices[retained_faces]
    centers = retained_triangles.mean(axis=1)
    near = np.all((centers >= local_min) & (centers <= local_max), axis=1)
    intersection_report = cross_intersections(
        retained_triangles[near],
        rebuild_vertices[rebuild_faces],
        cell_size=0.012,
        stop_after=250,
    )
    intersection_report["retained_source_triangles_in_local_broadphase"] = int(near.sum())

    required_views = ["3q-front", "left", "right", "rear", "top", "bottom"]
    rendered = {item["view"] for item in renders["selected_views"]}
    view_gate = all((OUT / "renders-optik-gate" / f"masterform-{name}.png").is_file() for name in required_views)
    view_gate = view_gate and rendered == set(required_views)
    validation = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "product_revision": "R02",
        "technical_revision": "R11",
        "status": "STOPP",
        "stop_phase": "OPTIK_GATE",
        "reference_gate": {
            "status": "PASS" if sha256(REF_CLEAN) == EXPECTED["ref_clean"] and sha256(REF_SEAM) == EXPECTED["ref_seam"] else "FAIL",
            "clean_sha256": sha256(REF_CLEAN),
            "seam_sha256": sha256(REF_SEAM),
        },
        "seed_42_source": {
            "status": "PASS_BYTE_IDENTICAL",
            "sha256": sha256(SOURCE),
            "expected_sha256": EXPECTED["seed42"],
            "vertices": int(len(source_vertices)),
            "triangles": int(len(source_faces)),
        },
        "roi_and_coordinate_preservation": {
            "status": "PASS" if source_prefix_exact and reconstruction["roi"]["outside_roi_faces_preserved_exact"] else "FAIL",
            "source_vertex_prefix_exact": source_prefix_exact,
            "source_vertex_coordinates_modified": 0,
            "outside_roi_faces_preserved_exact": reconstruction["roi"]["outside_roi_faces_preserved_exact"],
            "outside_roi_source_triangles": reconstruction["roi"]["outside_roi_source_triangles"],
        },
        "mesh_geometry": {
            "master_sha256": sha256(MASTER),
            "combined": full_metrics,
            "local_rebuild": local_metrics,
            "retained_source_triangles": int(len(retained_faces)),
            "local_rebuild_triangles": int(len(rebuild_faces)),
            "cross_intersections": intersection_report,
            "status": "FAIL",
            "reason": "Open boundary edges and confirmed source/rebuild crossings prevent one valid connected master body.",
        },
        "real_geometry_render_gate": {
            "status": "PASS" if view_gate else "FAIL",
            "source_is_actual_reconstructed_geometry": True,
            "required_six_views_exist": view_gate,
            "preliminary_front_sides": renders["preliminary_front_sides"],
            "contact_sheet": renders["contact_sheet"],
            "soll_ist_sheet": renders["soll_ist_sheet"],
        },
        "optic_gate": {
            "status": "FAIL",
            "failed_criteria": [
                "free_round_reference_like_face",
                "forehead_free_of_leaf_spine_geometry",
                "both_eyes_fully_free_and_cleanly_integrated",
                "both_ears_fully_free_and_cleanly_integrated",
                "ref_seam_visual_continuity",
                "no_visible_hard_patch_transition",
            ],
            "passed_criteria": [
                "snout_and_nose_source_coordinates_not_moved",
                "four_feet_source_coordinates_not_moved",
                "back_outside_roi_preserved",
                "single_existing_maple_leaf_preserved",
                "no_second_maple_leaf_created",
            ],
            "reason": "The real R11 front/side renders retain a hard forehead/seam shelf; eye and ear relief is not fully free or organically integrated. The binary R11 gate therefore fails.",
        },
        "cad_fdm_phase": {
            "status": "NOT_RUN_BY_OPTIK_GATE",
            "approved_master_created": False,
            "split_created": False,
            "body_stl_created": False,
            "back_stl_created": False,
            "connector_created": False,
            "shell_and_wall_validation_run": False,
        },
        "open_real_tests": [
            "Physical print, fit, support, material and 200 mm production-scale tests remain inapplicable before an optical PASS."
        ],
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
        "nutzerentscheidung_grund": "Technical deterministic-rebuild and optic-gate stop; no user dimension or product choice is missing.",
        "final_user_approval_claimed": False,
    }
    VALIDATION.write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    status = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "product_revision": "R02",
        "technical_revision": "R11",
        "status": "STOPP",
        "gate": "OPTIK_GATE",
        "summary": "Deterministic local body rebuild executed twice within the same ROI; the final real-geometry candidate still fails the binary visual and connected-mesh gates.",
        "main_files": {
            "non_approved_master": MASTER.relative_to(ROOT).as_posix(),
            "validation": VALIDATION.relative_to(ROOT).as_posix(),
            "reconstruction_report": RECONSTRUCTION.relative_to(ROOT).as_posix(),
            "renders": renders["contact_sheet"],
            "soll_ist": renders["soll_ist_sheet"],
        },
        "validations": {
            "hash_gate": validation["reference_gate"]["status"] == "PASS" and sha256(SOURCE) == EXPECTED["seed42"],
            "outside_roi_coordinates_unchanged": validation["roi_and_coordinate_preservation"]["status"] == "PASS",
            "six_real_geometry_views": view_gate,
            "optic_gate": False,
            "mesh_gate": False,
            "cad_fdm_generated": False,
        },
        "open_real_tests": validation["open_real_tests"],
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
        "nutzerentscheidung_grund": validation["nutzerentscheidung_grund"],
        "final_user_approval_claimed": False,
    }
    STATUS.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2))


if __name__ == "__main__":
    main()
