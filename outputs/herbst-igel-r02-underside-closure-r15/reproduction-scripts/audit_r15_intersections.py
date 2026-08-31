#!/usr/bin/env python3
"""Deterministic broad/narrow-phase self-intersection audit for R15.

The audit targets source-versus-new-patch pairs in the preliminary Gate-1
candidate. A centroid/radius uniform-grid query is a conservative broad phase;
the narrow phase is an exact float64 triangle/triangle predicate. Finding one
strict crossing is sufficient to fail Gate 1, so the scan stops after a fixed
number of reproducible witnesses.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from r15_mesh_core import json_write, read_binary_ply, sha256


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
CANDIDATE = OUT / "masterform" / "herbst-igel-r02-r15-gate1-candidate.ply"
CLOSURE_REPORT = OUT / "audits" / "gate1-harmonic-closure-r15.json"


def point_on_triangle(point, tri, unit_normal, plane_offset, distance_tolerance, barycentric_tolerance):
    if abs(float(np.dot(unit_normal, point) + plane_offset)) > distance_tolerance:
        return False
    a, b, c = tri
    v0, v1, v2 = b - a, c - a, point - a
    d00, d01, d11 = float(v0 @ v0), float(v0 @ v1), float(v1 @ v1)
    d20, d21 = float(v2 @ v0), float(v2 @ v1)
    denominator = d00 * d11 - d01 * d01
    if denominator <= np.finfo(float).eps * max(d00 * d11, np.finfo(float).tiny) * 128.0:
        return False
    v = (d11 * d20 - d01 * d21) / denominator
    w = (d00 * d21 - d01 * d20) / denominator
    u = 1.0 - v - w
    eps = barycentric_tolerance
    return u >= -eps and v >= -eps and w >= -eps


def segment_triangle(p0, p1, tri, barycentric_tolerance, angular_tolerance):
    a, b, c = tri
    direction, edge1, edge2 = p1 - p0, b - a, c - a
    h = np.cross(direction, edge2)
    determinant = float(edge1 @ h)
    scale = float(np.linalg.norm(edge1) * np.linalg.norm(edge2) * np.linalg.norm(direction))
    if abs(determinant) <= angular_tolerance * max(scale, np.finfo(float).tiny):
        return False
    inv_det = 1.0 / determinant
    s = p0 - a
    u = inv_det * float(s @ h)
    eps = barycentric_tolerance
    if u < -eps or u > 1.0 + eps:
        return False
    q = np.cross(s, edge1)
    v = inv_det * float(direction @ q)
    if v < -eps or u + v > 1.0 + eps:
        return False
    t = inv_det * float(edge2 @ q)
    return -eps <= t <= 1.0 + eps


def coplanar_sat(a, b, normal, tolerance):
    drop_axis = int(np.argmax(np.abs(normal)))
    keep = [axis for axis in range(3) if axis != drop_axis]
    a2, b2 = a[:, keep], b[:, keep]
    minimum_overlap = math.inf
    for polygon in (a2, b2):
        for edge_index in range(3):
            edge = polygon[(edge_index + 1) % 3] - polygon[edge_index]
            axis = np.array([-edge[1], edge[0]], dtype=np.float64)
            length = float(np.linalg.norm(axis))
            if length <= np.finfo(float).tiny:
                continue
            axis /= length
            pa, pb = a2 @ axis, b2 @ axis
            overlap = min(float(pa.max()), float(pb.max())) - max(float(pa.min()), float(pb.min()))
            if overlap < -tolerance:
                return False, "separated"
            minimum_overlap = min(minimum_overlap, overlap)
    return True, "coplanar_overlap" if minimum_overlap > tolerance else "coplanar_touching"


def triangle_intersection(a, b, distance_tolerance=1e-10, barycentric_tolerance=1e-10, angular_tolerance=1e-12):
    raw_na = np.cross(a[1] - a[0], a[2] - a[0])
    raw_nb = np.cross(b[1] - b[0], b[2] - b[0])
    len_na, len_nb = float(np.linalg.norm(raw_na)), float(np.linalg.norm(raw_nb))
    if len_na <= 1e-15 or len_nb <= 1e-15:
        return False, "degenerate"
    na, nb = raw_na / len_na, raw_nb / len_nb
    da, db = -float(na @ a[0]), -float(nb @ b[0])
    b_to_a, a_to_b = b @ na + da, a @ nb + db
    eps = distance_tolerance
    if (np.all(b_to_a > eps) or np.all(b_to_a < -eps)) or (np.all(a_to_b > eps) or np.all(a_to_b < -eps)):
        return False, "separated"
    if float(np.linalg.norm(np.cross(na, nb))) <= angular_tolerance:
        if np.max(np.abs(b_to_a)) > eps or np.max(np.abs(a_to_b)) > eps:
            return False, "parallel_separated"
        return coplanar_sat(a, b, na, eps)
    for edge_index in range(3):
        if segment_triangle(a[edge_index], a[(edge_index + 1) % 3], b, barycentric_tolerance, angular_tolerance):
            strict = bool(np.min(b_to_a) < -eps and np.max(b_to_a) > eps)
            return True, "noncoplanar_crossing" if strict else "touching"
        if segment_triangle(b[edge_index], b[(edge_index + 1) % 3], a, barycentric_tolerance, angular_tolerance):
            strict = bool(np.min(a_to_b) < -eps and np.max(a_to_b) > eps)
            return True, "noncoplanar_crossing" if strict else "touching"
    for point in a:
        if point_on_triangle(point, b, nb, db, eps, barycentric_tolerance):
            return True, "touching"
    for point in b:
        if point_on_triangle(point, a, na, da, eps, barycentric_tolerance):
            return True, "touching"
    return False, "separated"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", default=str(CANDIDATE))
    parser.add_argument("--attempt-key", default="attempt_b", choices=["attempt_a", "attempt_b", "attempt_c"])
    parser.add_argument("--loop-id", type=int, help="scan only one recorded harmonic patch loop")
    parser.add_argument("--output", default=str(OUT / "audits" / "self-intersection-audit-r15.json"))
    args = parser.parse_args()
    candidate = Path(args.candidate).resolve()
    closure = json.loads(CLOSURE_REPORT.read_text(encoding="utf-8"))
    source_face_count = int(closure[args.attempt_key]["input_metrics"]["triangles"])
    vertices, faces = read_binary_ply(candidate)
    triangles = vertices[faces]
    source = triangles[:source_face_count]
    patch = triangles[source_face_count:]
    source_centers = source.mean(axis=1)
    source_radii = np.linalg.norm(source - source_centers[:, None, :], axis=2).max(axis=1)
    source_min, source_max = source.min(axis=1), source.max(axis=1)
    patch_centers = patch.mean(axis=1)
    patch_radii = np.linalg.norm(patch - patch_centers[:, None, :], axis=2).max(axis=1)
    patch_min, patch_max = patch.min(axis=1), patch.max(axis=1)
    scan_pool = np.arange(len(patch), dtype=np.int64)
    if args.loop_id is not None:
        offset = 0
        selected_range = None
        for record in closure[args.attempt_key]["all_patch_records"]:
            end = offset + int(record["new_triangles"])
            if int(record["loop_id"]) == args.loop_id:
                selected_range = (offset, end)
                break
            offset = end
        if selected_range is None:
            raise ValueError(f"loop {args.loop_id} not present")
        scan_pool = np.arange(selected_range[0], selected_range[1], dtype=np.int64)
    cell_size = 2.0 / 318.2455727028218
    origin = np.minimum(source_centers.min(axis=0), patch_centers.min(axis=0)) - cell_size
    q = np.floor((source_centers - origin) / cell_size).astype(np.int64)
    dimensions = np.maximum(q.max(axis=0) + 3, 3)
    keys = q[:, 0] + dimensions[0] * (q[:, 1] + dimensions[1] * q[:, 2])
    order = np.argsort(keys)
    sorted_keys = keys[order]
    unique_keys, starts, counts = np.unique(sorted_keys, return_index=True, return_counts=True)
    max_source_radius = float(source_radii.max())
    witnesses = []
    tested_exact = 0
    broad_pairs = 0
    scanned_patch_faces = 0
    maximum_witnesses = 50
    maximum_patch_scan = min(len(scan_pool), 300000)
    # A prime stride distributes the finite fail-fast scan over every patch.
    stride = 104729
    patch_indices = scan_pool[(np.arange(maximum_patch_scan, dtype=np.int64) * stride) % len(scan_pool)]
    for local_patch in patch_indices:
        scanned_patch_faces += 1
        center = patch_centers[local_patch]
        radius = float(patch_radii[local_patch])
        qp = np.floor((center - origin) / cell_size).astype(np.int64)
        span = int(math.ceil((radius + max_source_radius) / cell_size))
        candidate_blocks = []
        for dz in range(-span, span + 1):
            for dy in range(-span, span + 1):
                for dx in range(-span, span + 1):
                    cell = qp + np.array([dx, dy, dz])
                    if np.any(cell < 0) or np.any(cell >= dimensions):
                        continue
                    key = int(cell[0] + dimensions[0] * (cell[1] + dimensions[1] * cell[2]))
                    where = int(np.searchsorted(unique_keys, key))
                    if where < len(unique_keys) and int(unique_keys[where]) == key:
                        candidate_blocks.append(order[starts[where] : starts[where] + counts[where]])
        if not candidate_blocks:
            continue
        candidates = np.concatenate(candidate_blocks)
        sphere = np.linalg.norm(source_centers[candidates] - center, axis=1) <= source_radii[candidates] + radius + 1e-10
        candidates = candidates[sphere]
        aabb = np.all(source_max[candidates] >= patch_min[local_patch] - 1e-10, axis=1) & np.all(source_min[candidates] <= patch_max[local_patch] + 1e-10, axis=1)
        candidates = candidates[aabb]
        broad_pairs += int(len(candidates))
        patch_face_id = source_face_count + int(local_patch)
        patch_vertex_ids = set(map(int, faces[patch_face_id]))
        for source_face_id in candidates:
            if patch_vertex_ids.intersection(map(int, faces[source_face_id])):
                continue
            tested_exact += 1
            hit, kind = triangle_intersection(source[int(source_face_id)], patch[int(local_patch)])
            if hit and kind in ("noncoplanar_crossing", "coplanar_overlap"):
                witnesses.append({
                    "source_face": int(source_face_id),
                    "patch_face": patch_face_id,
                    "kind": kind,
                    "source_vertices": faces[int(source_face_id)].tolist(),
                    "patch_vertices": faces[patch_face_id].tolist(),
                    "source_triangle_mm": (source[int(source_face_id)] * 318.2455727028218).tolist(),
                    "patch_triangle_mm": (patch[int(local_patch)] * 318.2455727028218).tolist(),
                })
                if len(witnesses) >= maximum_witnesses:
                    break
        if len(witnesses) >= maximum_witnesses:
            break
    payload = {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-UNDERSIDE-CLOSURE-R15.md",
        "attempt_key": args.attempt_key,
        "candidate": candidate.relative_to(ROOT).as_posix(),
        "candidate_sha256": sha256(candidate),
        "algorithm": "conservative centroid-sphere uniform-grid broad phase + float64 triangle narrow phase",
        "source_faces": source_face_count,
        "patch_faces": int(len(patch)),
        "restricted_loop_id": args.loop_id,
        "eligible_patch_faces": int(len(scan_pool)),
        "patch_faces_scanned": scanned_patch_faces,
        "broad_phase_pairs": broad_pairs,
        "exact_pairs_tested": tested_exact,
        "confirmed_strict_crossings": len(witnesses),
        "witnesses": witnesses,
        "audit_scope": "Fail-fast source-versus-patch scan; a positive result proves Gate-1 failure, but a zero result would not certify the unscanned pairs.",
        "status": "FAIL_CONFIRMED_INTERSECTIONS" if witnesses else "INCONCLUSIVE_NO_WITNESS_IN_FINITE_SCAN",
    }
    json_write(Path(args.output), payload)
    print(json.dumps({key: payload[key] for key in ("patch_faces_scanned", "broad_phase_pairs", "exact_pairs_tested", "confirmed_strict_crossings", "status")}, indent=2))


if __name__ == "__main__":
    main()
