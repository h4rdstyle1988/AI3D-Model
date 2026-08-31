#!/usr/bin/env python3
"""Build three depth-guided harmonic variants for the confirmed underside loop only."""

from pathlib import Path

import numpy as np

from r15_mesh_core import boundary_loops, compact_mesh, connected_components, json_write, mesh_metrics, read_binary_ply, sha256, write_binary_ply
from build_r15_gate1 import MM_PER_UNIT, connect_annulus, harmonic_samples, resample_closed, ring_parameters


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
SOURCE = OUT / "inputs" / "r14-local-surgery-input.ply"


def patch_variant(vertices, loop, exponent: float, floor_offset_mm: float):
    boundary = vertices[loop]
    uniform = resample_closed(boundary, len(loop))
    max_extent_mm = float(np.ptp(boundary, axis=0).max() * MM_PER_UNIT)
    layers = int(np.clip(np.ceil(max_extent_mm / 0.9), 3, 96))
    safe_z = float(boundary[:, 2].min() + floor_offset_mm / MM_PER_UNIT)
    rings = [(loop.copy(), ring_parameters(boundary))]
    blocks = []
    faces = []
    current = len(vertices)
    for layer in range(1, layers + 1):
        radius = 1.0 - layer / (layers + 1)
        count = max(6, int(round(len(loop) * radius)))
        points = harmonic_samples(uniform, radius, count)
        points[:, 2] = safe_z + (points[:, 2] - safe_z) * radius**exponent
        ids = np.arange(current, current + count, dtype=np.int64)
        current += count
        blocks.append(points)
        rings.append((ids, np.arange(count, dtype=np.float64) / count))
    center = uniform.mean(axis=0, keepdims=True)
    center[:, 2] = safe_z
    center_id = current
    blocks.append(center)
    for outer, inner in zip(rings[:-1], rings[1:]):
        faces.append(connect_annulus(*outer, *inner))
    last = rings[-1][0]
    faces.append(np.asarray([(int(last[i]), int(last[(i + 1) % len(last)]), center_id) for i in range(len(last))], dtype=np.int64))
    return np.vstack(blocks), np.vstack(faces), {"exponent": exponent, "floor_offset_mm": floor_offset_mm, "safe_z_mm": safe_z * MM_PER_UNIT, "layers": layers}


def main() -> None:
    vertices_all, faces_all = read_binary_ply(SOURCE)
    labels, components = connected_components(faces_all)
    main = int(np.argmax(components))
    vertices, faces, _used = compact_mesh(vertices_all, faces_all[labels == main])
    loops, _boundary, _owners, _adjacency = boundary_loops(faces)
    matches = [(i, loop) for i, loop in enumerate(loops) if len(loop) >= 1000 and vertices[loop, 2].max() * MM_PER_UNIT < -50.0]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one confirmed underside loop, got {len(matches)}")
    loop_id, loop = matches[0]
    variants = [(2.0, 0.40), (4.0, 0.20), (8.0, 0.05), (32.0, 0.0), (128.0, 0.0)]
    records = []
    for label, (exponent, offset) in zip(("d1", "d2", "d3", "d4", "d5"), variants):
        new_vertices, new_faces, parameters = patch_variant(vertices, loop, exponent, offset)
        candidate_vertices = np.vstack((vertices, new_vertices))
        candidate_faces = np.vstack((faces, new_faces))
        path = OUT / "masterform" / f"r15-underside-{label}-PARTIAL-NON-APPROVED.ply"
        write_binary_ply(path, candidate_vertices, candidate_faces)
        records.append({
            "variant": label,
            "parameters": parameters,
            "loop_id_main_component": loop_id,
            "loop_edges": int(len(loop)),
            "boundary_positions_modified": 0,
            "new_vertices": int(len(new_vertices)),
            "new_faces": int(len(new_faces)),
            "metrics_partial_open_mesh": mesh_metrics(candidate_vertices, candidate_faces),
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": sha256(path),
        })
    json_write(OUT / "audits" / "underside-depth-variant-build-r15.json", {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-UNDERSIDE-CLOSURE-R15.md",
        "method": "boundary-constrained harmonic disk with low-frequency depth bias toward the existing minimum Z",
        "confirmed_loop_id_main_component": loop_id,
        "variants": records,
    })
    print(OUT / "audits" / "underside-depth-variant-build-r15.json")


if __name__ == "__main__":
    main()
