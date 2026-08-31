#!/usr/bin/env python3
"""Audit the immutable R14 input before R15 changes any geometry."""

from pathlib import Path

import numpy as np

from r15_mesh_core import (
    MM_PER_UNIT,
    boundary_loops,
    compact_mesh,
    connected_components,
    face_geometry,
    json_write,
    mesh_metrics,
    orientability_constraints,
    read_binary_ply,
    sha256,
)


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
SOURCE = OUT / "inputs" / "r14-local-surgery-input.ply"
EXPECTED_SHA256 = "f6c82635080a5c97c350ba80e18dbda79424f34542ca3f87e66a7d9d665cb1c2"


def main() -> None:
    if sha256(SOURCE) != EXPECTED_SHA256:
        raise RuntimeError("R14 input hash mismatch")
    vertices, faces = read_binary_ply(SOURCE)
    labels, components = connected_components(faces)
    main_label = int(np.argmax(components))
    main_vertices, main_faces, source_vertex_ids = compact_mesh(vertices, faces[labels == main_label])
    loops, boundary, _owners, adjacency = boundary_loops(main_faces)
    orientation = orientability_constraints(main_faces)
    triangles, _double_area, normals = face_geometry(main_vertices, main_faces)
    conflict_faces = orientation["conflict_faces"]
    conflict_edges = orientation["conflict_edges"]
    loop_records = []
    for loop_id, loop in enumerate(loops):
        points = main_vertices[loop]
        lengths = np.linalg.norm(points - np.roll(points, 1, axis=0), axis=1)
        loop_records.append({
            "loop_id_main_component": loop_id,
            "edge_count": int(len(loop)),
            "perimeter_mm": float(lengths.sum() * MM_PER_UNIT),
            "extent_mm": (np.ptp(points, axis=0) * MM_PER_UNIT).tolist(),
            "centroid_mm": (points.mean(axis=0) * MM_PER_UNIT).tolist(),
            "z_range_mm": [float(points[:, 2].min() * MM_PER_UNIT), float(points[:, 2].max() * MM_PER_UNIT)],
            "source_vertex_ids": source_vertex_ids[loop].tolist(),
        })
    loop_records.sort(key=lambda item: item["edge_count"], reverse=True)
    conflict_payload = {
        "edge_count": int(len(conflict_edges)),
        "face_count": int(len(conflict_faces)),
        "edge_vertex_ids_main_component": conflict_edges.tolist(),
        "face_ids_main_component": conflict_faces.tolist(),
    }
    if len(conflict_faces):
        centers = triangles[conflict_faces].mean(axis=1)
        conflict_payload.update({
            "centroid_bounds_min_mm": (centers.min(axis=0) * MM_PER_UNIT).tolist(),
            "centroid_bounds_max_mm": (centers.max(axis=0) * MM_PER_UNIT).tolist(),
            "centroid_mean_mm": (centers.mean(axis=0) * MM_PER_UNIT).tolist(),
            "normal_abs_z_percentiles": np.percentile(np.abs(normals[conflict_faces, 2]), [5, 50, 95]).tolist(),
        })
    payload = {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-UNDERSIDE-CLOSURE-R15.md",
        "task_blob_sha": "6f36e00693a3f9ad6859b43450a5a77316fa9254",
        "input": {
            "path": SOURCE.relative_to(ROOT).as_posix(),
            "sha256": sha256(SOURCE),
            "metrics_all_r14_components": mesh_metrics(vertices, faces),
        },
        "largest_edge_connected_surface": {
            "component_count_before": int(len(components)),
            "largest_component_faces": int(components[main_label]),
            "discarded_micro_sheet_faces": int(len(faces) - components[main_label]),
            "discarded_micro_sheet_components": int(len(components) - 1),
            "metrics": mesh_metrics(main_vertices, main_faces),
        },
        "boundary": {
            "loop_count": int(len(loops)),
            "non_simple_boundary_vertices": int(sum(len(neighbours) != 2 for neighbours in adjacency.values())),
            "boundary_edges": int(len(boundary)),
            "loops": loop_records,
        },
        "orientation": {
            "orientable": bool(orientation["orientable"]),
            "orientation_constraint_conflicts": int(orientation["orientation_constraint_conflicts"]),
            "constraint_component_count": int(orientation["component_count"]),
            "conflict_distribution": conflict_payload,
        },
        "status": "PASS_INPUT_IDENTIFIED",
    }
    json_write(OUT / "audits" / "r15-input-audit.json", payload)
    print(OUT / "audits" / "r15-input-audit.json")


if __name__ == "__main__":
    main()
