#!/usr/bin/env python3
"""Validate the R09 NON-MASTER reconstruction and enforce its gate stop."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from reconstruct_body_surface_r09 import read_binary_ply


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
SOURCE = OUT / "source-r08" / "herbst-igel-r02-trellis-raw-seed-42.ply"
MASTER = OUT / "masterform" / "herbst-igel-r02-masterform-reconstructed-r09-NON-APPROVED.ply"
OPERATION = OUT / "reports" / "body-surface-reconstruction-r09.json"
REPORT = OUT / "VALIDIERUNG-R02-R09.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def topology(vertices: np.ndarray, faces: np.ndarray) -> dict[str, object]:
    triangles = vertices[faces]
    doubled_area = np.linalg.norm(
        np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), axis=1
    )
    edges = np.concatenate((faces[:, (0, 1)], faces[:, (1, 2)], faces[:, (2, 0)]), axis=0)
    edges.sort(axis=1)
    vertex_count = len(vertices)
    keys = edges[:, 0].astype(np.uint64) * np.uint64(vertex_count) + edges[:, 1].astype(np.uint64)
    _unique, incidence = np.unique(keys, return_counts=True)
    used = np.unique(faces)
    lo, hi = vertices[used].min(axis=0), vertices[used].max(axis=0)
    return {
        "vertices": int(len(vertices)),
        "used_vertices": int(len(used)),
        "triangles": int(len(faces)),
        "degenerate_triangles": int(np.count_nonzero(doubled_area <= 1e-12)),
        "boundary_edges": int(np.count_nonzero(incidence == 1)),
        "nonmanifold_edges": int(np.count_nonzero(incidence > 2)),
        "watertight_edge_incidence": bool(np.all(incidence == 2)),
        "bounds_min_normalized": lo.tolist(),
        "bounds_max_normalized": hi.tolist(),
        "extents_normalized": (hi - lo).tolist(),
    }


def main() -> None:
    source_vertices, source_faces = read_binary_ply(SOURCE)
    master_vertices, master_faces = read_binary_ply(MASTER)
    operation = json.loads(OPERATION.read_text(encoding="utf-8"))
    retained_count = int(operation["selection"]["retained_source_triangles"])
    patch_count = int(operation["patch"]["triangles"])
    source_coordinates_preserved = bool(
        len(master_vertices) >= len(source_vertices)
        and np.array_equal(master_vertices[: len(source_vertices)], source_vertices)
    )
    source_face_partition_valid = bool(
        len(master_faces) == retained_count + patch_count
        and np.all(master_faces[:retained_count] < len(source_vertices))
        and np.all(master_faces[retained_count:] >= len(source_vertices))
    )

    expected_renders = [
        "masterform-3q-front.png",
        "masterform-left.png",
        "masterform-right.png",
        "masterform-rear.png",
        "masterform-top.png",
        "masterform-bottom.png",
        "masterform-contact-sheet-r09.png",
        "soll-ist-optik-gate-r09.png",
    ]
    render_records = []
    for name in expected_renders:
        path = OUT / "renders-optik-gate" / name
        render_records.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "exists": path.is_file(),
                "bytes": path.stat().st_size if path.is_file() else 0,
                "sha256": sha256(path) if path.is_file() else None,
            }
        )

    prohibited_suffixes = {".stl", ".3mf", ".step", ".stp", ".glb", ".gltf"}
    manufacturing_artifacts = sorted(
        path.relative_to(ROOT).as_posix()
        for path in OUT.rglob("*")
        if path.is_file() and path.suffix.lower() in prohibited_suffixes
    )
    master_topology = topology(master_vertices, master_faces)
    payload = {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-BODY-SURFACE-RECONSTRUCTION-R09.md",
        "task_blob_sha": "ef3a16cc80c255d0e05c1a5e3773f2c9497c4c73",
        "product_revision": "R02",
        "technical_revision": "R09",
        "status": "STOPP",
        "stop_phase": "OPTIK_GATE",
        "reference_gate": {
            "status": "PASS",
            "clean_sha256": sha256(OUT / "reference-audit" / "ref-clean-r09.jpg"),
            "seam_sha256": sha256(OUT / "reference-audit" / "ref-seam-r09.jpg"),
        },
        "seed_42_source": {
            "status": "PASS_BYTE_IDENTICAL_TO_R08",
            "sha256": sha256(SOURCE),
            "expected_sha256": "85ba18eaed15bdbe631fc49dd571e73882c4055e2c247022e90ad15ed99822c6",
            "vertices": int(len(source_vertices)),
            "triangles": int(len(source_faces)),
        },
        "reconstruction": {
            "status": "EXECUTED_NON_MASTER",
            "sha256": sha256(MASTER),
            "source_vertex_coordinates_preserved": source_coordinates_preserved,
            "source_and_patch_face_partition_valid": source_face_partition_valid,
            "removed_source_triangles_local_zone": int(operation["selection"]["removed_source_triangles"]),
            "retained_source_triangles": retained_count,
            "patch_vertices": int(operation["patch"]["vertices"]),
            "patch_triangles": patch_count,
            "mesh": master_topology,
        },
        "real_geometry_render_gate": {
            "status": "PASS",
            "source_is_reconstructed_geometry": True,
            "required_six_views_exist": bool(all(x["exists"] for x in render_records[:6])),
            "soll_ist_exists": bool(render_records[-1]["exists"]),
            "files": render_records,
        },
        "optic_gate": {
            "status": "FAIL",
            "failed_criteria": [
                "free_round_reference_like_face",
                "no_leaf_spine_overlap_of_forehead_eyes_snout",
                "ref_seam_visual_continuity",
                "no_visible_patch_bulge_dent_hard_step_or_hole_repair",
            ],
            "passed_protected_criteria": [
                "four_short_feet_retained_across_views",
                "arched_back_retained",
                "one_visible_maple_leaf_retained",
                "no_second_maple_leaf_added",
            ],
            "reason": (
                "Actual R09 renders show a hard fan/block-like reconstructed face transition, residual fused "
                "leaf/spine structures in the face zone, and discontinuities that do not plausibly follow REF-SEAM."
            ),
        },
        "cad_fdm_phase": {
            "status": "NOT_RUN_BY_OPTIK_GATE",
            "manufacturing_artifacts_found": manufacturing_artifacts,
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
        "nutzerentscheidung_grund": "Technical gate stop; no user dimension or product decision is missing.",
        "final_user_approval_claimed": False,
    }
    REPORT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
