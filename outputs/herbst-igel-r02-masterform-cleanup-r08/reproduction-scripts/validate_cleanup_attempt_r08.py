#!/usr/bin/env python3
"""Validate the actual R08 cleanup-attempt mesh without advancing the failed gate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from inspect_seed42_r08 import edge_incidence, read_binary_ply


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
MESH = OUT / "masterform" / "herbst-igel-r02-masterform-cleanup-attempt-r08-NON-MASTER.ply"
REPORT = OUT / "reports" / "cleanup-attempt-mesh-validation-r08.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    vertices, faces = read_binary_ply(MESH)
    triangles = vertices[faces]
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    double_area = np.linalg.norm(cross, axis=1)
    bounds_min, bounds_max = vertices.min(axis=0), vertices.max(axis=0)
    edges = edge_incidence(len(vertices), faces)
    payload = {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-MASTERFORM-CLEANUP-R08.md",
        "mesh": MESH.relative_to(ROOT).as_posix(),
        "sha256": sha256(MESH),
        "bytes": MESH.stat().st_size,
        "vertices": int(len(vertices)),
        "triangles": int(len(faces)),
        "bounds_min_normalized": bounds_min.tolist(),
        "bounds_max_normalized": bounds_max.tolist(),
        "extents_normalized": (bounds_max - bounds_min).tolist(),
        "degenerate_triangles_area_le_1e_12": int(np.count_nonzero(double_area <= 1e-12)),
        "edge_incidence": edges,
        "watertight": edges["boundary_edges_incidence_1"] == 0 and edges["nonmanifold_edges_incidence_gt_2"] == 0,
        "status": "NON_MASTER_OPTIK_GATE_FAIL",
        "cad_fdm_validation_applicable": False,
        "reason": "The task stops before split/CAD/STL when the actual cleanup geometry fails OPTIK_GATE. Raw inherited topology is recorded, not repaired or presented as printable.",
    }
    REPORT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
