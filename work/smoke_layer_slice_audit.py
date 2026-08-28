#!/usr/bin/env python3
"""Planar layer-loop slicability proxy for a closed smoke-test mesh.

No G-code is generated.  Every sampled horizontal layer must consist entirely
of closed, non-branching segment loops after a strict positional endpoint weld.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import trimesh
from trimesh.intersections import mesh_multiplane

from smoke_single_solid import atomic_json, load_3mf, load_working_npz, topology


def audit_mesh(mesh: trimesh.Trimesh, layer_height_mm: float, endpoint_tolerance_mm: float) -> dict[str, Any]:
    bounds = np.asarray(mesh.bounds, dtype=np.float64)
    y_min, y_max = float(bounds[0, 1]), float(bounds[1, 1])
    # Irrational-looking fixed phase avoids the Marching-Cubes quarter/half-grid
    # vertex levels while remaining reproducible.
    first = y_min + 0.17320508075688773 * layer_height_mm
    heights = np.arange(first, y_max, layer_height_mm, dtype=np.float64) - y_min
    sections, _, face_ids = mesh_multiplane(
        mesh,
        plane_origin=np.asarray([0.0, y_min, 0.0]),
        plane_normal=np.asarray([0.0, 1.0, 0.0]),
        heights=heights,
    )
    rows = []
    invalid = []
    total_segments = 0
    for layer_index, (height, segments, faces) in enumerate(zip(heights, sections, face_ids)):
        segments = np.asarray(segments, dtype=np.float64)
        if not len(segments):
            row = {"layer": layer_index, "y_mm": y_min + float(height), "segments": 0, "loops": 0, "status": "EMPTY"}
            rows.append(row)
            continue
        endpoints = segments.reshape((-1, 2))
        keys = np.rint(endpoints / endpoint_tolerance_mm).astype(np.int64)
        unique, inverse = np.unique(keys, axis=0, return_inverse=True)
        edges = inverse.reshape((-1, 2))
        nonzero = edges[:, 0] != edges[:, 1]
        edges = edges[nonzero]
        degree = np.bincount(edges.reshape(-1), minlength=len(unique))
        used = np.flatnonzero(degree)
        degree_bad = used[degree[used] != 2]
        # Union-find for the number of closed loops/components.
        parent = np.arange(len(unique), dtype=np.int64)

        def find(value: int) -> int:
            while parent[value] != value:
                parent[value] = parent[parent[value]]
                value = int(parent[value])
            return value

        for left, right in edges.tolist():
            a, b = find(int(left)), find(int(right))
            if a != b:
                parent[b] = a
        loops = len({find(int(node)) for node in used.tolist()}) if len(used) else 0
        status = "PASS" if len(degree_bad) == 0 and int(np.count_nonzero(~nonzero)) == 0 else "FAIL"
        row = {
            "layer": layer_index,
            "y_mm": y_min + float(height),
            "segments": int(len(segments)),
            "nonzero_segments": int(len(edges)),
            "collapsed_segments_after_endpoint_weld": int(np.count_nonzero(~nonzero)),
            "unique_endpoint_nodes": int(len(used)),
            "nodes_not_degree_two": int(len(degree_bad)),
            "loops": int(loops),
            "intersected_faces": int(len(faces)),
            "status": status,
        }
        rows.append(row)
        total_segments += int(len(segments))
        if status == "FAIL":
            invalid.append(row)
    nonempty = [row for row in rows if row["status"] != "EMPTY"]
    return {
        "method": "trimesh.intersections.mesh_multiplane with cached vertex-plane dots; 2D endpoint graph after strict positional weld",
        "interpretation": "geometric slicability proxy only; no extrusion widths, printer profile, supports, G-code, or toolpaths",
        "layer_axis": "+Y",
        "layer_height_mm": float(layer_height_mm),
        "first_layer_phase_fraction": 0.17320508075688773,
        "endpoint_weld_tolerance_mm": float(endpoint_tolerance_mm),
        "layers_tested": int(len(rows)),
        "nonempty_layers": int(len(nonempty)),
        "empty_layers": int(len(rows) - len(nonempty)),
        "failed_layers": int(len(invalid)),
        "total_segments": total_segments,
        "loops_min_max_nonempty": [
            int(min((row["loops"] for row in nonempty), default=0)),
            int(max((row["loops"] for row in nonempty), default=0)),
        ],
        "pass": len(invalid) == 0 and len(nonempty) > 0,
        "invalid_layers": invalid[:100],
        "layers": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", type=Path, required=True)
    parser.add_argument("--layer-height-mm", type=float, default=0.5)
    parser.add_argument("--endpoint-tolerance-mm", type=float, default=1e-5)
    args = parser.parse_args()
    build_path = next(args.variant.glob("*-build.json"))
    build = json.loads(build_path.read_text(encoding="utf-8"))
    prefix = build_path.name[: -len("-build.json")]
    meshes = {
        "working": load_working_npz(Path(build["artifacts"]["working_npz"]["path"])),
        "stl_roundtrip": trimesh.load(Path(build["artifacts"]["stl"]["path"]), force="mesh", process=True),
        "3mf_roundtrip": load_3mf(Path(build["artifacts"]["3mf"]["path"])),
    }
    results = {}
    for name, mesh in meshes.items():
        print(f"layer slicing proxy: {name}", flush=True)
        results[name] = {
            "topology_before_slice": topology(mesh),
            "layer_loop_audit": audit_mesh(mesh, args.layer_height_mm, args.endpoint_tolerance_mm),
        }
    report = {
        "schema": "ai3d.c01.single-solid-smoke.layer-slice-audit.v1",
        "classification": "SMOKE-TEST / NON-MASTER",
        "candidate": prefix,
        "geometry_mutated": False,
        "results": results,
        "overall_pass": all(value["layer_loop_audit"]["pass"] for value in results.values()),
        "local_slicer_status": "NOT_AVAILABLE",
    }
    output = args.variant / f"{prefix}-layer-slice-audit.json"
    atomic_json(output, report)
    print(json.dumps({"overall_pass": report["overall_pass"], "output": str(output), "failed_layers": {name: value["layer_loop_audit"]["failed_layers"] for name, value in results.items()}}, indent=2))


if __name__ == "__main__":
    main()
