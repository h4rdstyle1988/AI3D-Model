#!/usr/bin/env python3
"""Audit the fixed R11 ROI boundary before the R12 single-surface rebuild."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
R11_REBUILD_BLOB = "571d31343ad14e27a8705d0120764667f59d9cf5"
SOURCE = Path(
    r"D:\3D-Models\generated\herbst-igel-r02-r08-input\outputs"
    r"\herbst-igel-r02-trellis-optik-retry-r07\trellis-raw\seed-00000042"
    r"\herbst-igel-r02-trellis-raw-seed-42.ply"
)
REF_SEAM = Path(
    r"D:\3D-Models\generated\herbst-igel-r02-r08-input\outputs"
    r"\herbst-igel-r02-trellis-optik-retry-r07\reference-audit\ref-seam-r07.jpg"
)
REPORT = OUT / "reports" / "r11-roi-boundary-audit-r12.json"


def load_r11() -> dict[str, object]:
    code = subprocess.check_output(
        ["git", "cat-file", "blob", R11_REBUILD_BLOB], cwd=ROOT
    ).decode("utf-8")
    namespace: dict[str, object] = {
        "__name__": "r11_fixed_roi",
        "__file__": str(OUT / "reproduction-scripts" / "r11_fixed_roi.py"),
    }
    exec(compile(code, namespace["__file__"], "exec"), namespace)
    namespace["REF_SEAM"] = REF_SEAM
    return namespace


def edge_table(faces: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    edges = np.vstack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    edges.sort(axis=1)
    unique, inverse, counts = np.unique(
        edges, axis=0, return_inverse=True, return_counts=True
    )
    return unique, inverse, counts


def main() -> None:
    r11 = load_r11()
    vertices, faces = r11["read_binary_ply"](SOURCE)
    used = np.unique(faces)
    bounds_min = vertices[used].min(axis=0).astype(np.float64)
    bounds_max = vertices[used].max(axis=0).astype(np.float64)
    blue, body, roi, bbox, _rgb = r11["reference_masks"]()
    profile_x, profile_center, profile_radius, _width = r11["measured_width_profiles"](vertices)
    body_field = r11["signed_distance_field"](body)
    _retained, _remove, problem, selection = r11["select_source_faces"](
        vertices,
        faces,
        roi,
        body_field,
        bounds_min,
        bounds_max,
        bbox,
        -0.105,
        profile_x,
        profile_center,
        profile_radius,
    )

    source_edges, source_inverse, source_counts = edge_table(faces)
    edge_problem_incidence = np.bincount(
        source_inverse,
        weights=np.tile(problem.astype(np.int8), 3),
        minlength=len(source_edges),
    ).astype(np.int32)
    source_boundary = source_counts == 1
    source_nonmanifold = source_counts > 2
    outside_only = edge_problem_incidence == 0
    immutable_bad_edges = source_edges[outside_only & (source_boundary | source_nonmanifold)]
    immutable_bad_points = vertices[immutable_bad_edges]

    retained_faces = faces[~problem]
    retained_edges, _retained_inverse, retained_counts = edge_table(retained_faces)
    retained_boundary_edges = retained_edges[retained_counts == 1]
    boundary_vertices, boundary_degree = np.unique(
        retained_boundary_edges.ravel(), return_counts=True
    )

    report = {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-SINGLE-SURFACE-ROI-REBUILD-R12.md",
        "source_vertices": int(len(vertices)),
        "source_triangles": int(len(faces)),
        "r11_roi_problem_triangles": int(problem.sum()),
        "outside_roi_triangles": int((~problem).sum()),
        "r11_selection_crosscheck": selection,
        "source_topology": {
            "boundary_edges_total": int(source_boundary.sum()),
            "nonmanifold_edges_total": int(source_nonmanifold.sum()),
            "boundary_edges_strictly_outside_roi": int(np.count_nonzero(source_boundary & outside_only)),
            "nonmanifold_edges_strictly_outside_roi": int(np.count_nonzero(source_nonmanifold & outside_only)),
            "boundary_edges_touched_by_roi": int(np.count_nonzero(source_boundary & ~outside_only)),
            "nonmanifold_edges_touched_by_roi": int(np.count_nonzero(source_nonmanifold & ~outside_only)),
        },
        "healthy_ring_after_removing_all_r11_problem_triangles": {
            "retained_triangles": int(len(retained_faces)),
            "boundary_edges": int(np.count_nonzero(retained_counts == 1)),
            "nonmanifold_edges": int(np.count_nonzero(retained_counts > 2)),
            "boundary_vertices": int(len(boundary_vertices)),
            "boundary_vertex_degree_histogram": {
                str(int(value)): int(np.count_nonzero(boundary_degree == value))
                for value in np.unique(boundary_degree)
            },
            "simple_closed_loops_possible": bool(np.all(boundary_degree == 2)),
        },
        "fixed_outside_roi_gate_feasibility": {
            "status": "PASS" if not np.any(source_boundary & outside_only) and not np.any(source_nonmanifold & outside_only) else "FAIL",
            "reason": (
                "All pre-existing open/nonmanifold source edges touch the R11 ROI and can be replaced locally."
                if not np.any(source_boundary & outside_only) and not np.any(source_nonmanifold & outside_only)
                else "The byte/index-fixed outside-ROI source already contains open or nonmanifold edges; an all-zero full-mesh gate cannot be reached by an ROI-only rebuild."
            ),
            "immutable_invalid_edges": int(len(immutable_bad_edges)),
            "immutable_invalid_edge_bounds_min": immutable_bad_points.min(axis=(0, 1)).tolist(),
            "immutable_invalid_edge_bounds_max": immutable_bad_points.max(axis=(0, 1)).tolist(),
        },
        "reference_measurements": {
            "foreground_bbox_px": bbox,
            "body_pixels": int(body.sum()),
            "seam_band_pixels": int(np.count_nonzero(roi & ~body)),
            "blue_pixels": int(blue.sum()),
        },
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
