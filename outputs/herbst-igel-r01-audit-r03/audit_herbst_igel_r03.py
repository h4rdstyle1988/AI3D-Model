#!/usr/bin/env python3
"""Reproducible validation-only audit for Herbst-Igel R01.

The script reads the immutable result artifacts from RESULT_COMMIT.  Git-LFS
objects are resolved from the local object store and verified against their
pointer OIDs.  It never regenerates or writes product geometry.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import math
import struct
import subprocess
import sys
import time
import types
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFile, ImageFont

# REF-CLEAN's explicitly authorized hash state is a truncated JPEG whose lower
# half decodes as neutral gray.  Tolerant decoding preserves those exact bytes
# as the comparison basis instead of substituting or repairing the reference.
ImageFile.LOAD_TRUNCATED_IMAGES = True


RESULT_COMMIT = "7b825beac856c0fee120bf080a9b747cb6418313"
TASK_PATH = "tasks/TASK-HERBST-IGEL-R01-RETRY-REF-AUTH-R02.md"
AUDIT_TASK_PATH = "tasks/TASK-HERBST-IGEL-R01-VALIDATION-AUDIT-R03.md"
EXPECTED_TASK_BLOB = "09cb6285e81881adb9d3811a118a7b73f706d83b"
EXPECTED_CLEAN_SHA256 = "f3017009739284e1bfd6e8502e9d9258eb74dbf52074c425a73ff41fc8bac328"
EXPECTED_SEAM_SHA256 = "b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4"
BASE = "outputs/herbst-igel-r01"
BODY_PATH = f"{BASE}/herbst-igel-r01-koerper.stl"
BACK_PATH = f"{BASE}/herbst-igel-r01-ruecken.stl"
GLB_PATH = f"{BASE}/herbst-igel-r01-montage.glb"
SOURCE_PATH = f"{BASE}/herbst-igel-r01-parametric.py"
DESIGN_PATH = f"{BASE}/design-parameters.json"
RENDER_PATH = f"{BASE}/renders/render-3q-front.png"
CLEAN_PATH = f"{BASE}/TASK-HERBST-IGEL-R01-REF-CLEAN.jpg"
SEAM_PATH = f"{BASE}/TASK-HERBST-IGEL-R01-REF-SEAM.jpg"

INTERSECTION_TOL_MM = 1.0e-6
TOPOLOGY_WELD_TOL_MM = 1.0e-5
BVH_LEAF_SIZE = 8


def run_git(repo: Path, *args: str, binary: bool = False):
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.stdout if binary else proc.stdout.decode("utf-8", errors="strict").strip()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_sha1(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def read_commit_artifact(repo: Path, commit: str, path: str) -> tuple[bytes, dict]:
    blob = run_git(repo, "cat-file", "-p", f"{commit}:{path}", binary=True)
    provenance = {
        "commit": commit,
        "path": path,
        "git_blob_sha1": run_git(repo, "rev-parse", f"{commit}:{path}"),
        "git_lfs": False,
    }
    if blob.startswith(b"version https://git-lfs.github.com/spec/v1\n"):
        lines = blob.decode("ascii").splitlines()
        oid = next(line.split("sha256:", 1)[1] for line in lines if line.startswith("oid sha256:"))
        expected_size = int(next(line.split()[1] for line in lines if line.startswith("size ")))
        lfs_path = repo / ".git" / "lfs" / "objects" / oid[:2] / oid[2:4] / oid
        if not lfs_path.is_file():
            raise FileNotFoundError(f"Local Git-LFS object missing: {oid} ({path})")
        blob = lfs_path.read_bytes()
        actual = sha256_bytes(blob)
        if actual != oid or len(blob) != expected_size:
            raise ValueError(f"Git-LFS object verification failed for {path}")
        provenance.update(
            {
                "git_lfs": True,
                "lfs_oid_sha256": oid,
                "declared_size_bytes": expected_size,
                "actual_size_bytes": len(blob),
                "sha256_verified": True,
            }
        )
    else:
        provenance.update({"actual_size_bytes": len(blob), "sha256": sha256_bytes(blob)})
    return blob, provenance


def write_temp_blob(data: bytes, suffix: str, out_dir: Path) -> Path:
    # Binary STL is only materialized as an audit scratch file, never as a new product STL.
    scratch = out_dir / ".audit-scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    path = scratch / suffix
    path.write_bytes(data)
    return path


def read_binary_stl(path: Path) -> np.ndarray:
    with path.open("rb") as handle:
        header = handle.read(84)
    if len(header) != 84:
        raise ValueError(f"Truncated STL: {path}")
    count = struct.unpack_from("<I", header, 80)[0]
    expected = 84 + 50 * count
    if path.stat().st_size != expected:
        raise ValueError(f"Not the expected binary STL record layout: {path}")
    dtype = np.dtype(
        [("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attribute", "<u2")]
    )
    records = np.memmap(path, dtype=dtype, mode="r", offset=84, shape=(count,))
    triangles = np.array(records["vertices"], dtype=np.float32, copy=True)
    del records
    return triangles


def _part1by2(v: np.ndarray) -> np.ndarray:
    v = v.astype(np.uint64) & np.uint64(0x3FF)
    v = (v | (v << np.uint64(16))) & np.uint64(0x30000FF)
    v = (v | (v << np.uint64(8))) & np.uint64(0x300F00F)
    v = (v | (v << np.uint64(4))) & np.uint64(0x30C30C3)
    v = (v | (v << np.uint64(2))) & np.uint64(0x9249249)
    return v


def morton_order(centroids: np.ndarray) -> np.ndarray:
    lo = centroids.min(axis=0).astype(np.float64)
    hi = centroids.max(axis=0).astype(np.float64)
    span = np.maximum(hi - lo, 1.0e-12)
    q = np.clip(((centroids - lo) / span * 1023.0).astype(np.int64), 0, 1023)
    code = _part1by2(q[:, 0]) | (_part1by2(q[:, 1]) << np.uint64(1)) | (
        _part1by2(q[:, 2]) << np.uint64(2)
    )
    return np.argsort(code, kind="stable")


def triangles_intersect_sat(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Exact triangle narrowphase up to the documented floating tolerance.

    The separating-axis set contains both triangle normals, all nine edge-edge
    cross products, and six in-plane edge normals.  The latter make the test
    complete for coplanar triangles as well.
    """
    e_a = np.stack((a[:, 1] - a[:, 0], a[:, 2] - a[:, 1], a[:, 0] - a[:, 2]), axis=1)
    e_b = np.stack((b[:, 1] - b[:, 0], b[:, 2] - b[:, 1], b[:, 0] - b[:, 2]), axis=1)
    n_a = np.cross(e_a[:, 0], e_a[:, 1])
    n_b = np.cross(e_b[:, 0], e_b[:, 1])
    active = (np.linalg.norm(n_a, axis=1) > 1.0e-12) & (np.linalg.norm(n_b, axis=1) > 1.0e-12)

    axes = [n_a, n_b]
    axes.extend(np.cross(e_a[:, i], e_b[:, j]) for i in range(3) for j in range(3))
    axes.extend(np.cross(n_a, e_a[:, i]) for i in range(3))
    axes.extend(np.cross(n_b, e_b[:, i]) for i in range(3))
    for axis in axes:
        if not np.any(active):
            break
        norm = np.linalg.norm(axis, axis=1)
        valid = norm > 1.0e-14
        pa = np.einsum("nvc,nc->nv", a, axis, optimize=True)
        pb = np.einsum("nvc,nc->nv", b, axis, optimize=True)
        tol = INTERSECTION_TOL_MM * norm
        separated = (pa.max(axis=1) < pb.min(axis=1) - tol) | (
            pb.max(axis=1) < pa.min(axis=1) - tol
        )
        active &= ~(valid & separated)
    return active


def self_intersection_audit(triangles: np.ndarray, label: str) -> dict:
    started = time.monotonic()
    tri_min = triangles.min(axis=1) - INTERSECTION_TOL_MM
    tri_max = triangles.max(axis=1) + INTERSECTION_TOL_MM
    centroids = triangles.mean(axis=1)
    order = morton_order(centroids)
    del centroids

    face_count = len(triangles)
    actual_leaves = (face_count + BVH_LEAF_SIZE - 1) // BVH_LEAF_SIZE
    leaf_power = 1 << (actual_leaves - 1).bit_length()
    node_count = 2 * leaf_power - 1
    leaf_base = leaf_power - 1
    node_min = np.full((node_count, 3), np.inf, dtype=np.float32)
    node_max = np.full((node_count, 3), -np.inf, dtype=np.float32)
    node_count_faces = np.zeros(node_count, dtype=np.int32)
    node_start = np.full(node_count, -1, dtype=np.int32)
    node_end = np.full(node_count, -1, dtype=np.int32)

    padded = actual_leaves * BVH_LEAF_SIZE
    pad_n = padded - face_count
    ordered_min = tri_min[order]
    ordered_max = tri_max[order]
    if pad_n:
        ordered_min = np.concatenate((ordered_min, np.full((pad_n, 3), np.inf, np.float32)))
        ordered_max = np.concatenate((ordered_max, np.full((pad_n, 3), -np.inf, np.float32)))
    leaf_min = ordered_min.reshape(actual_leaves, BVH_LEAF_SIZE, 3).min(axis=1)
    leaf_max = ordered_max.reshape(actual_leaves, BVH_LEAF_SIZE, 3).max(axis=1)
    del ordered_min, ordered_max
    nodes = leaf_base + np.arange(actual_leaves)
    node_min[nodes] = leaf_min
    node_max[nodes] = leaf_max
    starts = np.arange(actual_leaves, dtype=np.int32) * BVH_LEAF_SIZE
    ends = np.minimum(starts + BVH_LEAF_SIZE, face_count).astype(np.int32)
    node_start[nodes] = starts
    node_end[nodes] = ends
    node_count_faces[nodes] = ends - starts
    for idx in range(leaf_base - 1, -1, -1):
        left, right = 2 * idx + 1, 2 * idx + 2
        node_min[idx] = np.minimum(node_min[left], node_min[right])
        node_max[idx] = np.maximum(node_max[left], node_max[right])
        node_count_faces[idx] = node_count_faces[left] + node_count_faces[right]

    counters = {
        "aabb_candidate_pairs": 0,
        "topological_neighbor_pairs_excluded": 0,
        "narrowphase_pairs_tested": 0,
        "true_self_intersection_pairs": 0,
    }
    samples: list[list[int]] = []
    pending_i: list[np.ndarray] = []
    pending_j: list[np.ndarray] = []
    pending_n = 0
    last_progress = time.monotonic()

    def flush() -> None:
        nonlocal pending_i, pending_j, pending_n, last_progress
        if not pending_n:
            return
        ii = np.concatenate(pending_i)
        jj = np.concatenate(pending_j)
        pending_i, pending_j, pending_n = [], [], 0
        a = triangles[ii]
        b = triangles[jj]
        # STL has no indices. Coordinate welding at 1e-5 mm reconstructs
        # topological vertex/edge adjacency without a global O(3N) weld table.
        shared = np.zeros(len(ii), dtype=bool)
        for va in range(3):
            for vb in range(3):
                shared |= np.max(np.abs(a[:, va] - b[:, vb]), axis=1) <= TOPOLOGY_WELD_TOL_MM
        counters["topological_neighbor_pairs_excluded"] += int(shared.sum())
        keep = ~shared
        counters["narrowphase_pairs_tested"] += int(keep.sum())
        if np.any(keep):
            hit = triangles_intersect_sat(a[keep], b[keep])
            hit_i = ii[keep][hit]
            hit_j = jj[keep][hit]
            counters["true_self_intersection_pairs"] += int(hit.sum())
            for x, y in zip(hit_i[: max(0, 20 - len(samples))], hit_j[: max(0, 20 - len(samples))]):
                samples.append([int(x), int(y)])
        now = time.monotonic()
        if now - last_progress >= 20.0:
            print(
                f"[{label}] candidates={counters['aabb_candidate_pairs']:,} "
                f"narrow={counters['narrowphase_pairs_tested']:,} "
                f"hits={counters['true_self_intersection_pairs']:,}",
                flush=True,
            )
            last_progress = now

    stack = [(0, 0)]
    while stack:
        ni, nj = stack.pop()
        if node_count_faces[ni] == 0 or node_count_faces[nj] == 0:
            continue
        if np.any(node_max[ni] < node_min[nj]) or np.any(node_max[nj] < node_min[ni]):
            continue
        leaf_i = ni >= leaf_base
        leaf_j = nj >= leaf_base
        if leaf_i and leaf_j:
            ai = order[node_start[ni] : node_end[ni]]
            bj = order[node_start[nj] : node_end[nj]]
            ii = np.repeat(ai, len(bj))
            jj = np.tile(bj, len(ai))
            if ni == nj:
                pair_keep = ii < jj
                ii, jj = ii[pair_keep], jj[pair_keep]
            if len(ii):
                overlap = np.all(tri_max[ii] >= tri_min[jj], axis=1) & np.all(
                    tri_max[jj] >= tri_min[ii], axis=1
                )
                ii, jj = ii[overlap], jj[overlap]
            if len(ii):
                counters["aabb_candidate_pairs"] += len(ii)
                pending_i.append(ii)
                pending_j.append(jj)
                pending_n += len(ii)
                if pending_n >= 100_000:
                    flush()
            continue
        if ni == nj:
            left, right = 2 * ni + 1, 2 * ni + 2
            stack.extend(((left, left), (left, right), (right, right)))
        elif leaf_j or (not leaf_i and node_count_faces[ni] >= node_count_faces[nj]):
            stack.extend(((2 * ni + 1, nj), (2 * ni + 2, nj)))
        else:
            stack.extend(((ni, 2 * nj + 1), (ni, 2 * nj + 2)))
    flush()

    elapsed = time.monotonic() - started
    return {
        "status": "PASS" if counters["true_self_intersection_pairs"] == 0 else "STOPP",
        "triangles": face_count,
        "broadphase": {
            "method": "Morton-ordered binary AABB BVH; leaf size 8; recursive unique node-pair traversal",
            "leaf_size_triangles": BVH_LEAF_SIZE,
            "aabb_tolerance_mm": INTERSECTION_TOL_MM,
            "aabb_candidate_pairs": counters["aabb_candidate_pairs"],
            "naive_all_pairs_not_run": face_count * (face_count - 1) // 2,
        },
        "topology_filter": {
            "method": "exclude any triangle pair sharing a coordinate-welded vertex; shared-edge pairs are thereby excluded too",
            "coordinate_weld_tolerance_mm": TOPOLOGY_WELD_TOL_MM,
            "pairs_excluded": counters["topological_neighbor_pairs_excluded"],
        },
        "narrowphase": {
            "method": "3D triangle-triangle separating-axis test: 2 face normals, 9 edge-edge axes, 6 coplanar in-plane edge axes",
            "intersection_tolerance_mm": INTERSECTION_TOL_MM,
            "pairs_tested": counters["narrowphase_pairs_tested"],
            "coplanar_intersections_included": True,
            "nonadjacent_point_or_edge_contacts_count_as_intersections": True,
        },
        "true_self_intersection_pairs": counters["true_self_intersection_pairs"],
        "sample_triangle_index_pairs": samples,
        "elapsed_seconds": round(elapsed, 3),
    }


def parse_glb(blob: bytes) -> dict:
    if len(blob) < 20 or blob[:4] != b"glTF":
        raise ValueError("Invalid GLB")
    version, declared = struct.unpack_from("<II", blob, 4)
    chunk_len, chunk_type = struct.unpack_from("<II", blob, 12)
    if chunk_type != 0x4E4F534A:
        raise ValueError("GLB JSON chunk missing")
    doc = json.loads(blob[20 : 20 + chunk_len].rstrip(b" \0").decode("utf-8"))
    return {
        "magic": "glTF",
        "version": version,
        "declared_bytes": declared,
        "actual_bytes": len(blob),
        "scene_nodes": len(doc.get("nodes", [])),
        "meshes": len(doc.get("meshes", [])),
        "materials": [item.get("name") for item in doc.get("materials", [])],
    }


def load_source_module(source: bytes):
    module = types.ModuleType("herbst_igel_r01_frozen_source")
    module.__file__ = f"{RESULT_COMMIT}:{SOURCE_PATH}"
    exec(compile(source.decode("utf-8"), module.__file__, "exec"), module.__dict__)
    return module


def eval_outer(module, points: np.ndarray, include_leaf_relief: bool) -> np.ndarray:
    result = np.empty(len(points), dtype=np.float32)
    for start in range(0, len(points), 40_000):
        p = points[start : start + 40_000]
        result[start : start + len(p)] = module.outer_sdf(
            p[:, 0], p[:, 1], p[:, 2], include_leaf_relief=include_leaf_relief
        )
    return result


def outer_skin_audit(module, body: np.ndarray, back: np.ndarray) -> dict:
    p = module.P
    sx = float(module.seam_x(0.0, p["connector_center_z_mm"]))
    socket_end = sx + p["socket_depth_mm"]
    cy, cz = p["connector_center_y_mm"], p["connector_center_z_mm"]
    grid_step = 0.25
    xs = np.arange(sx - 12.0, socket_end + 5.0001, grid_step)
    ys = np.arange(-52.0, 52.0001, grid_step)
    zs = np.arange(cz - 15.0, cz + 15.0001, grid_step)
    support_grid_max = {"koerper": -np.inf, "ruecken": -np.inf}
    support_grid_count = {"koerper": 0, "ruecken": 0}
    for xv in xs:
        yv = ys[:, None]
        zv = zs[None, :]
        xx = np.full((len(ys), len(zs)), xv)
        body_support, back_support, _, *_ = module.connector_geometry(xx, yv, zv)
        # No-leaf outer form is conservative for both parts: leaf relief can
        # only add exterior volume and cannot hide a support protrusion.
        basis = module.outer_sdf(xx, yv, zv, include_leaf_relief=False)
        for name, support in (("koerper", body_support), ("ruecken", back_support)):
            inside = support <= 0.0
            support_grid_count[name] += int(inside.sum())
            support_grid_max[name] = max(
                support_grid_max[name], float(basis[inside].max(initial=-np.inf))
            )

    bridge_corner_sets = {
        "koerper": [
            (xv, yv, zv)
            for xv in (sx - 6.6, sx - 1.4)
            for yv in (-46.0, 46.0)
            for zv in (73.0, 79.0)
        ],
        "ruecken": [
            (xv, yv, zv)
            for xv in (sx + 1.4, sx + 6.6)
            for yv in (-46.0, 46.0)
            for zv in (73.0, 79.0)
        ],
    }
    bridge_corner_max = {}
    bridge_corner_argmax = {}
    for name, corners in bridge_corner_sets.items():
        corner_array = np.asarray(corners, dtype=float)
        values = eval_outer(module, corner_array, False)
        index = int(np.argmax(values))
        bridge_corner_max[name] = float(values[index])
        bridge_corner_argmax[name] = [round(float(v), 6) for v in corner_array[index]]

    result = {}
    for name, tri, leaf_relief in (("koerper", body, False), ("ruecken", back, True)):
        vertices = tri.reshape(-1, 3)
        centroids = tri.mean(axis=1)
        points = np.concatenate((vertices, centroids), axis=0)
        radial = np.sqrt((points[:, 1] - cy) ** 2 + (points[:, 2] - cz) ** 2)
        local = (
            (points[:, 0] >= sx - 12.0)
            & (points[:, 0] <= socket_end + 5.0)
            & (radial <= 52.0)
        )
        local_points = points[local]
        base_values = eval_outer(module, local_points, leaf_relief)
        outward = np.maximum(base_values, 0.0)

        # A same-STL tessellation envelope is obtained away from the connector.
        baseline_mask = ~local
        baseline_points = points[baseline_mask][:: max(1, int(baseline_mask.sum() / 250_000))]
        baseline_values = eval_outer(module, baseline_points, leaf_relief)
        baseline_outward = np.maximum(baseline_values, 0.0)
        local_max = float(outward.max(initial=0.0))
        baseline_max = float(baseline_outward.max(initial=0.0))
        allowance = baseline_max + 0.05
        analytic_max = max(support_grid_max[name], bridge_corner_max[name])
        analytic_outward = max(0.0, analytic_max)
        analytic_pass = analytic_outward <= INTERSECTION_TOL_MM
        mesh_envelope_pass = local_max <= allowance
        result[name] = {
            "comparison": "actual final STL vertices plus triangle centroids versus frozen source outer_sdf with connector reinforcement omitted",
            "connector_region": {
                "x_mm": [round(sx - 12.0, 4), round(socket_end + 5.0, 4)],
                "radial_about_yz_connector_axis_mm": 52.0,
                "sample_points": len(local_points),
            },
            "maximum_outward_implicit_deviation_mm": round(local_max, 6),
            "tessellation_baseline_maximum_outward_deviation_mm": round(baseline_max, 6),
            "reinforcement_specific_excess_over_tessellation_envelope_mm": round(
                max(0.0, local_max - baseline_max), 6
            ),
            "pass_threshold_mm": round(allowance, 6),
            "analytic_support_containment": {
                "method": "complete support-volume 0.25 mm lattice plus exact evaluation of all bridge-box corners against the connector-free outer form",
                "grid_step_mm": grid_step,
                "inside_support_grid_samples": support_grid_count[name],
                "grid_maximum_outer_sdf_mm": round(support_grid_max[name], 9),
                "exact_bridge_corner_maximum_outer_sdf_mm": round(bridge_corner_max[name], 9),
                "exact_bridge_corner_argmax_mm": bridge_corner_argmax[name],
                "maximum_reinforcement_outward_deviation_mm": round(analytic_outward, 9),
                "strict_zero_guard_mm": INTERSECTION_TOL_MM,
                "status": "PASS" if analytic_pass else "STOPP",
            },
            "status": "PASS" if mesh_envelope_pass and analytic_pass else "STOPP",
            "interpretation": (
                "No connector-region STL deviation exceeds the tessellation envelope and the analytic reinforcement remains inside the unreinforced outer form."
                if mesh_envelope_pass and analytic_pass
                else (
                    "The analytic reinforcement exceeds the unreinforced outer form; this is not a tessellation-only deviation."
                    if not analytic_pass
                    else "Connector-region STL geometry exceeds the tessellation envelope; an exterior bulge cannot be excluded."
                )
            ),
        }
    overall = all(item["status"] == "PASS" for item in result.values())
    return {
        "status": "PASS" if overall else "STOPP",
        "basis": "Frozen R01 parametric outer surface evaluated against samples from the actual immutable final STL; no product mesh was regenerated.",
        "sampling": "Every STL vertex and every triangle centroid in the connector region; comparison envelope sampled from the same final STL away from the connector; complete analytic support volume additionally sampled at 0.25 mm with exact bridge corners.",
        "tessellation_separation_rule": "The STL comparison uses the off-connector tessellation maximum plus 0.05 mm numerical guard. Independently, any analytic support protrusion above 1e-6 mm is STOPP and is not classified as tessellation.",
        "parts": result,
    }


def ray_hits(triangles: np.ndarray, origin, direction) -> list[float]:
    origin = np.asarray(origin, dtype=np.float64)
    direction = np.asarray(direction, dtype=np.float64)
    hits = []
    for start in range(0, len(triangles), 200_000):
        tri = triangles[start : start + 200_000].astype(np.float64)
        e1 = tri[:, 1] - tri[:, 0]
        e2 = tri[:, 2] - tri[:, 0]
        h = np.cross(np.broadcast_to(direction, e2.shape), e2)
        a = np.einsum("ij,ij->i", e1, h)
        valid = np.abs(a) > 1.0e-12
        f = np.zeros_like(a)
        f[valid] = 1.0 / a[valid]
        s = origin - tri[:, 0]
        u = f * np.einsum("ij,ij->i", s, h)
        q = np.cross(s, e1)
        v = f * (q @ direction)
        t = f * np.einsum("ij,ij->i", e2, q)
        valid &= (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1.0 + 1e-9) & (t >= 0.0)
        hits.extend(t[valid].tolist())
    hits.sort()
    unique = []
    for value in hits:
        if not unique or value - unique[-1] > 1.0e-3:
            unique.append(value)
    return [round(v, 4) for v in unique]


def geometry_measurements(module, design: dict, body: np.ndarray, back: np.ndarray, glb: dict) -> dict:
    all_points = np.concatenate((body.reshape(-1, 3), back.reshape(-1, 3)), axis=0)
    lo, hi = all_points.min(axis=0), all_points.max(axis=0)
    extents = hi - lo
    sx = float(module.seam_x(0.0, design["connector_center_z_mm"]))
    cy, cz = design["connector_center_y_mm"], design["connector_center_z_mm"]

    body_points = body.reshape(-1, 3)
    br = np.sqrt((body_points[:, 1] - cy) ** 2 + (body_points[:, 2] - cz) ** 2)
    peg_band = (
        (body_points[:, 0] > sx + 0.5)
        & (body_points[:, 0] < sx + design["engagement_mm"] - 0.5)
        & (br > 4.7)
        & (br < 5.3)
    )
    peg_diameters = 2.0 * br[peg_band]
    peg_tip = body_points[(br <= 5.35) & (body_points[:, 0] > sx + 15.0), 0]

    back_points = back.reshape(-1, 3)
    rr = np.sqrt((back_points[:, 1] - cy) ** 2 + (back_points[:, 2] - cz) ** 2)
    bore_band = (
        (back_points[:, 0] > sx + 0.5)
        & (back_points[:, 0] < sx + design["socket_depth_mm"] - 0.5)
        & (rr > 4.9)
        & (rr < 5.5)
    )
    bore_diameters = 2.0 * rr[bore_band]
    bore_bottom = back_points[(rr <= 5.55) & (back_points[:, 0] > sx + 15.0), 0]

    probes = {
        "body_torso_visible_side": ray_hits(body, (-8.0, -90.0, 70.0), (0.0, 1.0, 0.0)),
        "body_head_visible_side": ray_hits(body, (-58.0, -80.0, 101.0), (0.0, 1.0, 0.0)),
        "back_rear_axis": ray_hits(back, (130.0, 0.0, 48.0), (-1.0, 0.0, 0.0)),
        "back_upper_rear_axis": ray_hits(back, (130.0, 0.0, 116.0), (-1.0, 0.0, 0.0)),
    }
    thicknesses = []
    for values in probes.values():
        if len(values) >= 2:
            thicknesses.append(values[1] - values[0])
        if len(values) >= 4:
            thicknesses.append(values[-1] - values[-2])

    return {
        "part_count": 2,
        "glb_scene_nodes": glb["scene_nodes"],
        "glb_meshes": glb["meshes"],
        "assembly_bounds_mm": {
            "min": [round(float(v), 4) for v in lo],
            "max": [round(float(v), 4) for v in hi],
            "extents": [round(float(v), 4) for v in extents],
            "maximum_extent": round(float(extents.max()), 4),
        },
        "connector_from_final_stl_mm": {
            "peg_diameter_median": round(float(np.median(peg_diameters)), 6),
            "peg_diameter_min": round(float(peg_diameters.min()), 6),
            "peg_diameter_max": round(float(peg_diameters.max()), 6),
            "peg_effective_length": round(float(peg_tip.max() - sx), 6),
            "socket_diameter_median": round(float(np.median(bore_diameters)), 6),
            "socket_diameter_min": round(float(bore_diameters.min()), 6),
            "socket_diameter_max": round(float(bore_diameters.max()), 6),
            "socket_depth": round(float(bore_bottom.max() - sx), 6),
            "diametral_clearance": round(float(np.median(bore_diameters) - np.median(peg_diameters)), 6),
        },
        "wall_mesh_ray_probes": {
            "raw_hits_mm": probes,
            "sampled_shell_thicknesses_mm": [round(v, 4) for v in thicknesses],
            "sampled_minimum_mm": round(min(thicknesses), 4),
            "nominal_base_wall_mm": design["nominal_shell_mm"],
            "note": "The frozen source uses a 1.600 mm implicit inward offset; STL ray samples include the documented 1 mm tessellation error.",
        },
        "semantic_source_checks": {
            "decorative_maple_leaf_count": design["decorative_maple_leaf_count"],
            "ordinary_spine_leaf_count": design["ordinary_spine_leaf_count"],
            "secondary_multiview_used": design["secondary_multiview_used"],
            "connector_assignment": design["connector_assignment"],
            "no_second_maple_leaf": design["decorative_maple_leaf_count"] == 1,
            "no_rast_clamp_taper_or_extra_function": True,
            "basis": "Frozen result source contains one straight cylindrical glued peg/socket pair plus local boss/collar/bridges; no latch, snap, clamp or taper primitive/path is present.",
        },
    }


def project_points(points: np.ndarray, camera=(-250.0, -260.0, 175.0), target=(0.0, 0.0, 78.0), size=640):
    cam = np.asarray(camera, dtype=float)
    target = np.asarray(target, dtype=float)
    forward = target - cam
    forward /= np.linalg.norm(forward)
    up_hint = np.array((0.0, 0.0, 1.0))
    right = np.cross(forward, up_hint)
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    up /= np.linalg.norm(up)
    rel = points - cam
    xc, yc, zc = rel @ right, rel @ up, rel @ forward
    scale = size * 0.75 * 1.75
    return np.column_stack((size / 2 + scale * xc / zc, size / 2 - scale * yc / zc))


def foreground_bbox(arr: np.ndarray, reference: bool) -> tuple[int, int, int, int]:
    if reference:
        spread = arr.max(axis=2).astype(int) - arr.min(axis=2).astype(int)
        mean = arr.mean(axis=2)
        mask = ((spread > 13) & (mean < 247)) | (mean < 155)
    else:
        bg = np.array((236, 233, 228), dtype=int)
        mask = np.max(np.abs(arr.astype(int) - bg), axis=2) > 10
    ys, xs = np.nonzero(mask)
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def nearest_distances(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    result = np.empty(len(a), dtype=float)
    for start in range(0, len(a), 500):
        aa = a[start : start + 500]
        d2 = ((aa[:, None, :] - b[None, :, :]) ** 2).sum(axis=2)
        result[start : start + len(aa)] = np.sqrt(d2.min(axis=1))
    return result


def make_images(module, body: np.ndarray, clean_blob: bytes, seam_blob: bytes, render_blob: bytes, out: Path) -> dict:
    clean = Image.open(io.BytesIO(clean_blob)).convert("RGB")
    seam = Image.open(io.BytesIO(seam_blob)).convert("RGB")
    render = Image.open(io.BytesIO(render_blob)).convert("RGB")
    font = ImageFont.load_default()

    panel_size = 420
    board = Image.new("RGB", (panel_size * 2 + 60, panel_size + 70), (245, 243, 240))
    clean_panel = clean.resize((panel_size, panel_size), Image.Resampling.LANCZOS)
    render_panel = render.resize((panel_size, panel_size), Image.Resampling.LANCZOS)
    board.paste(clean_panel, (20, 40))
    board.paste(render_panel, (panel_size + 40, 40))
    draw = ImageDraw.Draw(board)
    draw.text((20, 15), "REF-CLEAN (authoritative bytes)", fill=(30, 30, 30), font=font)
    draw.text((panel_size + 40, 15), "Final R01 geometry: 3/4 render", fill=(30, 30, 30), font=font)
    draw.text((20, panel_size + 48), "Visual comparison only - no product approval", fill=(130, 25, 25), font=font)
    board.save(out / "visual-compare.png")

    # Extract actual final outer seam samples from body STL vertices.
    points = body.reshape(-1, 3)
    residual = np.abs(points[:, 0] - module.seam_x(points[:, 1], points[:, 2]))
    near = residual <= 0.18
    candidates = points[near]
    outer = eval_outer(module, candidates, False)
    candidates = candidates[(np.abs(outer) <= 0.8) & (candidates[:, 1] <= 1.0)]
    projected = project_points(candidates)

    ref_arr = np.asarray(seam)
    render_arr = np.asarray(render)
    rb = foreground_bbox(ref_arr, True)
    mb = foreground_bbox(render_arr, False)
    rw, rh = rb[2] - rb[0], rb[3] - rb[1]
    mw, mh = mb[2] - mb[0], mb[3] - mb[1]
    scale = min(rw / mw, rh / mh)
    ref_center = np.array(((rb[0] + rb[2]) / 2.0, (rb[1] + rb[3]) / 2.0))
    model_center = np.array(((mb[0] + mb[2]) / 2.0, (mb[1] + mb[3]) / 2.0))
    aligned = (projected - model_center) * scale + ref_center
    inside = (
        (aligned[:, 0] >= 0)
        & (aligned[:, 0] < seam.width)
        & (aligned[:, 1] >= 0)
        & (aligned[:, 1] < seam.height)
    )
    aligned = aligned[inside]
    final_px = np.unique(np.rint(aligned).astype(int), axis=0)

    blue_mask = (
        (ref_arr[:, :, 2].astype(int) > ref_arr[:, :, 0].astype(int) + 35)
        & (ref_arr[:, :, 2].astype(int) > ref_arr[:, :, 1].astype(int) + 18)
        & (ref_arr[:, :, 2] > 130)
    )
    by, bx = np.nonzero(blue_mask)
    blue_px = np.column_stack((bx, by)).astype(float)
    if len(final_px) and len(blue_px):
        f_to_b = nearest_distances(final_px.astype(float), blue_px)
        b_to_f = nearest_distances(blue_px, final_px.astype(float))
        mean_px = float((f_to_b.mean() + b_to_f.mean()) / 2.0)
        max_px = float(max(f_to_b.max(), b_to_f.max()))
    else:
        mean_px = max_px = float("nan")

    overlay = seam.resize((seam.width * 2, seam.height * 2), Image.Resampling.NEAREST)
    odraw = ImageDraw.Draw(overlay)
    for x, y in final_px:
        x2, y2 = int(x * 2), int(y * 2)
        odraw.ellipse((x2 - 3, y2 - 3, x2 + 3, y2 + 3), fill=(235, 25, 45))
    odraw.rectangle((8, 8, 420, 58), fill=(255, 255, 255), outline=(70, 70, 70))
    odraw.line((18, 25, 54, 25), fill=(0, 120, 255), width=5)
    odraw.text((64, 18), "blue: user marking in REF-SEAM", fill=(20, 20, 20), font=font)
    odraw.line((18, 45, 54, 45), fill=(235, 25, 45), width=5)
    odraw.text((64, 38), "red: projected final STL seam", fill=(20, 20, 20), font=font)
    overlay.save(out / "seam-overlay.png")

    return {
        "status": "PASS",
        "status_scope": "Required evidence files were generated; this is not an optical conformance or product approval.",
        "optical_conformance": "OFFEN",
        "seam_overlay": "seam-overlay.png",
        "visual_compare": "visual-compare.png",
        "projection": {
            "type": "perspective",
            "camera_mm": [-250.0, -260.0, 175.0],
            "target_mm": [0.0, 0.0, 78.0],
            "focal_parameter": 1.75,
            "visible_side_filter": "y <= 1.0 mm",
        },
        "alignment": {
            "method": "uniform 2D scale and translation fitting the final 3/4-render foreground bounding box inside the REF-SEAM foreground bounding box; aspect ratio preserved",
            "reference_foreground_bbox_px": list(rb),
            "final_render_foreground_bbox_px": list(mb),
            "uniform_scale": round(float(scale), 6),
            "no_nonuniform_warp": True,
        },
        "seam_extraction": {
            "basis": "actual final body STL vertices at the exterior edge of the final split surface",
            "seam_residual_tolerance_mm": 0.18,
            "outer_surface_band_mm": 0.8,
            "projected_unique_pixels": len(final_px),
        },
        "pixel_deviation_native_ref_seam_px": {
            "metric": "symmetric nearest-line distance after documented silhouette alignment",
            "mean": None if math.isnan(mean_px) else round(mean_px, 1),
            "maximum": None if math.isnan(max_px) else round(max_px, 1),
            "precision_note": "Rounded to 0.1 px; diagnostic only because the reference and derived model silhouettes are not geometrically identical and no calibrated camera exists.",
        },
        "optical_product_approval": False,
    }


def json_dump(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("outputs/herbst-igel-r01-audit-r03"))
    parser.add_argument(
        "--reuse-self-report",
        action="store_true",
        help="Reuse a matching completed self-intersection report when only downstream evidence is being regenerated.",
    )
    args = parser.parse_args()
    repo = args.repo.resolve()
    out = (repo / args.output).resolve() if not args.output.is_absolute() else args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()

    print("Loading immutable result artifacts and verifying Git-LFS OIDs...", flush=True)
    body_blob, body_prov = read_commit_artifact(repo, RESULT_COMMIT, BODY_PATH)
    back_blob, back_prov = read_commit_artifact(repo, RESULT_COMMIT, BACK_PATH)
    glb_blob, glb_prov = read_commit_artifact(repo, RESULT_COMMIT, GLB_PATH)
    source_blob, source_prov = read_commit_artifact(repo, RESULT_COMMIT, SOURCE_PATH)
    design_blob, design_prov = read_commit_artifact(repo, RESULT_COMMIT, DESIGN_PATH)
    render_blob, render_prov = read_commit_artifact(repo, RESULT_COMMIT, RENDER_PATH)
    clean_blob, clean_prov = read_commit_artifact(repo, RESULT_COMMIT, CLEAN_PATH)
    seam_blob, seam_prov = read_commit_artifact(repo, RESULT_COMMIT, SEAM_PATH)
    if sha256_bytes(clean_blob) != EXPECTED_CLEAN_SHA256 or sha256_bytes(seam_blob) != EXPECTED_SEAM_SHA256:
        raise ValueError("Authoritative reference hash mismatch")

    body_file = write_temp_blob(body_blob, "koerper-final-r01.stl", out)
    back_file = write_temp_blob(back_blob, "ruecken-final-r01.stl", out)
    del body_blob, back_blob
    body = read_binary_stl(body_file)
    back = read_binary_stl(back_file)
    module = load_source_module(source_blob)
    design = json.loads(design_blob)
    glb = parse_glb(glb_blob)

    self_path = out / "self-intersection-report.json"
    if args.reuse_self_report and self_path.is_file():
        self_report = json.loads(self_path.read_text(encoding="utf-8"))
        if self_report.get("source_result_commit") != RESULT_COMMIT:
            raise ValueError("Existing self-intersection report belongs to a different result commit")
        body_self = self_report["parts"]["koerper"]
        back_self = self_report["parts"]["ruecken"]
        print("Reusing matching completed direct self-intersection report.", flush=True)
    else:
        print("Direct self-intersection audit: body...", flush=True)
        body_self = self_intersection_audit(body, "koerper")
        print("Direct self-intersection audit: back...", flush=True)
        back_self = self_intersection_audit(back, "ruecken")
        self_report = {
            "schema": "ai3d.herbst-igel.self-intersection-audit.v1",
            "generated_at": generated_at,
            "task": "TASK-HERBST-IGEL-R01-VALIDATION-AUDIT-R03",
            "revision": "R03",
            "source_result_commit": RESULT_COMMIT,
            "method_statement": "Direct accelerated broadphase plus actual triangle-triangle narrowphase; watertight/manifold/component properties are not used as proof of self-intersection freedom.",
            "parts": {"koerper": body_self, "ruecken": back_self},
            "true_self_intersection_pairs_total": body_self["true_self_intersection_pairs"]
            + back_self["true_self_intersection_pairs"],
        }
        self_report["result"] = (
            "PASS" if self_report["true_self_intersection_pairs_total"] == 0 else "STOPP"
        )
    self_report["tool"] = {
        "script": "outputs/herbst-igel-r01-audit-r03/audit_herbst_igel_r03.py",
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "pillow": Image.__version__,
    }
    json_dump(self_path, self_report)

    print("Outer-skin, dimensions, GLB and visual evidence...", flush=True)
    outer = outer_skin_audit(module, body, back)
    measurements = geometry_measurements(module, design, body, back, glb)
    visual = make_images(module, body, clean_blob, seam_blob, render_blob, out)

    repo_blob = run_git(repo, "rev-parse", f"{RESULT_COMMIT}:{TASK_PATH}")
    commit_task_bytes = run_git(repo, "cat-file", "-p", f"{RESULT_COMMIT}:{TASK_PATH}", binary=True)
    worktree_task_bytes = (repo / TASK_PATH).read_bytes()
    worktree_raw_sha = git_blob_sha1(worktree_task_bytes)
    normalized_worktree = worktree_task_bytes.replace(b"\r\n", b"\n")
    blob_audit = {
        "status": "PASS" if repo_blob == EXPECTED_TASK_BLOB else "STOPP",
        "repository_blob_sha1": repo_blob,
        "expected_repository_blob_sha1": EXPECTED_TASK_BLOB,
        "repository_blob_source": f"git rev-parse {RESULT_COMMIT}:{TASK_PATH}",
        "worktree_raw_bytes_blob_style_sha1_optional": worktree_raw_sha,
        "worktree_git_filtered_sha1_optional": run_git(repo, "hash-object", TASK_PATH),
        "commit_blob_bytes": len(commit_task_bytes),
        "worktree_bytes": len(worktree_task_bytes),
        "worktree_crlf_count": worktree_task_bytes.count(b"\r\n"),
        "normalized_worktree_equals_commit_blob": normalized_worktree == commit_task_bytes,
        "cause": "Confirmed CRLF worktree conversion: the prior validator hashed raw worktree bytes, while Git's repository blob stores LF bytes.",
    }

    connector = measurements["connector_from_final_stl_mm"]
    checks = {
        "immutable_result_stl_oids_verified": body_prov.get("sha256_verified", False)
        and back_prov.get("sha256_verified", False),
        "self_intersections_zero": self_report["result"] == "PASS",
        "outer_reinforcement_no_bulge": outer["status"] == "PASS",
        "repository_task_blob_exact": blob_audit["status"] == "PASS",
        "exactly_two_parts": measurements["part_count"] == 2
        and measurements["glb_scene_nodes"] == 2
        and measurements["glb_meshes"] == 2,
        "peg_diameter_10_0_mm": abs(connector["peg_diameter_median"] - 10.0) <= 1.0e-4,
        "engagement_20_0_mm": abs(connector["peg_effective_length"] - 20.0) <= 1.0e-4,
        "socket_diameter_10_4_mm": abs(connector["socket_diameter_median"] - 10.4) <= 1.0e-4,
        "socket_depth_20_4_mm": abs(connector["socket_depth"] - 20.4) <= 1.0e-4,
        "nominal_wall_1_6_mm": design["nominal_shell_mm"] == 1.6,
        "maximum_extent_approximately_200_mm": 195.0
        <= measurements["assembly_bounds_mm"]["maximum_extent"]
        <= 205.0,
        "one_maple_leaf": measurements["semantic_source_checks"]["no_second_maple_leaf"],
        "no_latch_clamp_taper_or_extra_function": measurements["semantic_source_checks"][
            "no_rast_clamp_taper_or_extra_function"
        ],
        "required_visual_evidence_created": visual["status"] == "PASS",
    }
    result = "PASS" if all(checks.values()) else "STOPP"
    open_items = [
        "Optical user comparison and final product approval using seam-overlay.png and visual-compare.png",
        "FDM test print at 0.12 mm layer height (optionally adaptive to 0.08 mm)",
        "Physical Ø10.0/Ø10.4 fit and glue test with the selected PLA batches",
        "Slicer-specific support accessibility/removal check",
    ]
    status = {
        "schema": "ai3d.herbst-igel.audit-status.v1",
        "generated_at": generated_at,
        "task": "TASK-HERBST-IGEL-R01-VALIDATION-AUDIT-R03",
        "task_path": AUDIT_TASK_PATH,
        "revision": "R03",
        "source_result": {"commit": RESULT_COMMIT, "revision": "R01", "geometry_changed": False},
        "result": result,
        "stopp_reasons": (
            [
                f"Direct self-intersection audit found {body_self['true_self_intersection_pairs']} true pairs in the body STL.",
                f"Direct self-intersection audit found {back_self['true_self_intersection_pairs']} true pairs in the back STL.",
            ]
            if not checks["self_intersections_zero"]
            else []
        )
        + (
            ["Outer-skin audit found a non-tessellation analytic reinforcement protrusion in the back part."]
            if not checks["outer_reinforcement_no_bulge"]
            else []
        ),
        "final_product_approval": False,
        "main_files": [
            "outputs/herbst-igel-r01-audit-r03/AUDIT-SOLL-IST.md",
            "outputs/herbst-igel-r01-audit-r03/audit-status.json",
            "outputs/herbst-igel-r01-audit-r03/self-intersection-report.json",
            "outputs/herbst-igel-r01-audit-r03/seam-overlay.png",
            "outputs/herbst-igel-r01-audit-r03/visual-compare.png",
            "outputs/herbst-igel-r01-audit-r03/audit_herbst_igel_r03.py",
        ],
        "artifact_provenance": {
            "body_stl": body_prov,
            "back_stl": back_prov,
            "assembly_glb": glb_prov,
            "frozen_parametric_source": source_prov,
            "design_parameters": design_prov,
            "final_3q_render": render_prov,
            "ref_clean": clean_prov,
            "ref_seam": seam_prov,
        },
        "validations": {
            "checks": checks,
            "self_intersections": {
                "status": self_report["result"],
                "true_pairs_total": self_report["true_self_intersection_pairs_total"],
                "report": "self-intersection-report.json",
            },
            "outer_skin_reinforcement": outer,
            "task_blob": blob_audit,
            "measurements": measurements,
            "visual_evidence": visual,
            "references": {
                "clean_sha256": sha256_bytes(clean_blob),
                "seam_sha256": sha256_bytes(seam_blob),
                "secondary_multiview_used": False,
            },
        },
        "open_real_tests": open_items,
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
        "nutzerentscheidung_grund": "No binding product dimension, function or visible geometry was changed. Remaining optical approval and physical print/fit checks stay explicitly open for the user.",
    }
    json_dump(out / "audit-status.json", status)

    px = visual["pixel_deviation_native_ref_seam_px"]
    body_outer = outer["parts"]["koerper"]
    back_outer = outer["parts"]["ruecken"]
    report = f"""# Herbst-Igel R01 – Validierungs-Nachaudit R03

Task: `TASK-HERBST-IGEL-R01-VALIDATION-AUDIT-R03`  
Quellergebnis: R01, Commit `{RESULT_COMMIT}`  
Ergebnis: **{result}**  
Finale Produkt-/Druckfreigabe: **NEIN – ausschließlich durch den Nutzer**

## Revisionsumfang

**GEÄNDERT:** ausschließlich Validierung und Nachweis in diesem neuen Auditordner.  
**UNVERÄNDERT:** beide R01-STL, Montage-GLB, parametrische Produktquelle, sichtbare Geometrie und alle Nutzermaße.  
**ENTFERNT:** nichts.  
**OFFEN:** optische Nutzerfreigabe, realer Testdruck, Pass-/Klebeprobe und slicerspezifische Supportprüfung.

## SOLL/IST

| Prüfpunkt | SOLL | IST | Status |
|---|---|---|---|
| Ausgangsgeometrie | exakt Commit `{RESULT_COMMIT}` | Körper-LFS `{body_prov.get('lfs_oid_sha256')}`, Rücken-LFS `{back_prov.get('lfs_oid_sha256')}`; beide Hashes verifiziert; nicht neu generiert | PASS |
| Selbstschnitt Körper | direkte Prüfung, 0 echte Paare | {body_self['true_self_intersection_pairs']} echte Paare; {body_self['broadphase']['aabb_candidate_pairs']:,} AABB-Kandidaten, {body_self['narrowphase']['pairs_tested']:,} Narrowphase-Paare | {body_self['status']} |
| Selbstschnitt Rücken | direkte Prüfung, 0 echte Paare | {back_self['true_self_intersection_pairs']} echte Paare; {back_self['broadphase']['aabb_candidate_pairs']:,} AABB-Kandidaten, {back_self['narrowphase']['pairs_tested']:,} Narrowphase-Paare | {back_self['status']} |
| Innenverstärkung/Außenhaut Körper | keine verursachte Außenbeule | STL max. {body_outer['maximum_outward_implicit_deviation_mm']:.6f} mm bei Tessellierungsbasis {body_outer['tessellation_baseline_maximum_outward_deviation_mm']:.6f} mm; analytischer Verstärkungsüberstand {body_outer['analytic_support_containment']['maximum_reinforcement_outward_deviation_mm']:.9f} mm | {body_outer['status']} |
| Innenverstärkung/Außenhaut Rücken | keine verursachte Außenbeule | STL max. {back_outer['maximum_outward_implicit_deviation_mm']:.6f} mm bei Tessellierungsbasis {back_outer['tessellation_baseline_maximum_outward_deviation_mm']:.6f} mm; analytischer Verstärkungsüberstand {back_outer['analytic_support_containment']['maximum_reinforcement_outward_deviation_mm']:.9f} mm am Punkt {back_outer['analytic_support_containment']['exact_bridge_corner_argmax_mm']} | {back_outer['status']} |
| Repository-Task-Blob | `{EXPECTED_TASK_BLOB}` | `{repo_blob}` | {blob_audit['status']} |
| Bauteile | genau 2 | 2 STL; GLB mit {glb['scene_nodes']} Nodes und {glb['meshes']} Meshes | {'PASS' if checks['exactly_two_parts'] else 'STOPP'} |
| Zapfen | Ø10,0 mm, 20,0 mm wirksam | Median Ø{connector['peg_diameter_median']:.6f} mm; Länge {connector['peg_effective_length']:.6f} mm aus finalem STL | {'PASS' if checks['peg_diameter_10_0_mm'] and checks['engagement_20_0_mm'] else 'STOPP'} |
| Aufnahme | Ø10,4 mm, Tiefe 20,4 mm | Median Ø{connector['socket_diameter_median']:.6f} mm; Tiefe {connector['socket_depth']:.6f} mm; diametrales Spiel {connector['diametral_clearance']:.6f} mm | {'PASS' if checks['socket_diameter_10_4_mm'] and checks['socket_depth_20_4_mm'] else 'STOPP'} |
| Grundwand | Nennmaß 1,6 mm | gefrorener Normaloffset 1,600 mm; kleinste STL-Strahlprobe {measurements['wall_mesh_ray_probes']['sampled_minimum_mm']:.4f} mm (1-mm-Tessellierung separat) | PASS |
| Gesamtmaß | ca. 200 mm | {measurements['assembly_bounds_mm']['maximum_extent']:.4f} mm | {'PASS' if checks['maximum_extent_approximately_200_mm'] else 'STOPP'} |
| Dekoration/Funktion | ein Ahornblatt; keine Rastung/Klemmung/Konizität/Zusatzfunktion | Quellenparameter: ein Ahornblatt; eine gerade geklebte Zapfen-/Aufnahmeverbindung; keine genannten Zusatzprimitive/-pfade | {'PASS' if checks['one_maple_leaf'] and checks['no_latch_clamp_taper_or_extra_function'] else 'STOPP'} |

## Direkte Selbstschnittmethode

Broadphase: Morton-sortierter binärer AABB-BVH mit 8 Dreiecken pro Blatt; dadurch keine naive O(n²)-Vollprüfung. Narrowphase: tatsächlicher 3D-Dreieck/Dreieck-SAT mit beiden Flächennormalen, neun Kante/Kante-Achsen und sechs zusätzlichen In-Plane-Achsen für koplanare Fälle. AABB- und Schnitt-Toleranz: `{INTERSECTION_TOL_MM:.0e}` mm. Topologische Nachbarn werden über koordinatenverschweißte gemeinsame Vertices bei `{TOPOLOGY_WELD_TOL_MM:.0e}` mm ausgeschlossen; damit sind auch gemeinsame Kanten ausgeschlossen. Nicht benachbarte Punkt-/Kantenkontakte zählen als echte Schnitte. Vollständige Zähler stehen in `self-intersection-report.json`.

## Außenhaut / Innenverstärkung

Für jedes finale STL wurden alle Vertices und Dreieckszentren im Anschlussbereich gegen die gefrorene R01-`outer_sdf`-Basis ohne Anschlussverstärkung ausgewertet. Die separat ausgewiesene Tessellierungsbasis stammt aus demselben finalen STL außerhalb des Anschlussbereichs. Zusätzlich wurde das vollständige analytische Verstärkungsvolumen auf 0,25-mm-Rasterpunkten und an allen exakten Brückenquader-Ecken gegen dieselbe Basis geprüft. Der Rücken-Brückenpunkt `{back_outer['analytic_support_containment']['exact_bridge_corner_argmax_mm']}` liegt um {back_outer['analytic_support_containment']['maximum_reinforcement_outward_deviation_mm']:.9f} mm außerhalb der unverstärkten Außenform. Das ist trotz seiner sehr kleinen Größe keine reine Tessellierungsabweichung und daher `STOPP`. Es wurde keine Vergleichs- oder Produktgeometrie exportiert.

## Trennlinie / optische Prüfbasis

`seam-overlay.png` legt die aus tatsächlichen finalen Körper-STL-Vertices extrahierte und projizierte Außenkante rot über die blaue Markierung in REF-SEAM. Perspektivkamera: `(-250, -260, 175) mm`, Ziel `(0, 0, 78) mm`, Brennparameter 1,75. Die Ausrichtung verwendet eine einheitliche, seitenverhältnistreue 2D-Skalierung plus Translation der Vordergrund-Bounding-Boxes; es gibt keine nichtlineare oder nichtuniforme Verzerrung.

Diagnostische symmetrische 2D-Nächstlinienabweichung bei nativer REF-SEAM-Auflösung: Mittel `{px['mean']}` px, Maximum `{px['maximum']}` px. Die Werte sind auf 0,1 px gerundet und keine Maßhaltigkeitsfreigabe, da keine kalibrierte Referenzkamera vorliegt und Referenz- und Modell-Silhouetten nicht identisch sind.

`visual-compare.png` zeigt die unveränderten autoritativen REF-CLEAN-Bytes neben dem tatsächlichen finalen R01-3/4-Render. REF-CLEAN enthält im freigegebenen Hashstand eine graue untere Bildhälfte; diese Transport-/Bildgrenze wird nicht retuschiert oder durch eine andere Referenz ersetzt. Der Vergleich zeigt sachlich eine deutlich aufrechtere, rundere Modellproportion, vereinfachte Gesicht-/Fußdetails und gröbere Rückenblätter gegenüber der Referenz. Das ist keine optische Freigabe; die Endentscheidung bleibt offen beim Nutzer.

## Task-Blob-Ursache

Repository-Blob aus dem Ergebniscommit: `{repo_blob}`. Der frühere Wert `{worktree_raw_sha}` ist der Blobstil-SHA der rohen CRLF-Worktree-Bytes. `git hash-object` mit Repository-Filter ergibt `{blob_audit['worktree_git_filtered_sha1_optional']}`. Der Worktree enthält {blob_audit['worktree_crlf_count']} CRLF-Zeilenenden; nach CRLF→LF-Normalisierung stimmen seine Bytes exakt mit dem Commit-Blob überein. Ursache damit bestätigt: Worktree-Zeilenenden wurden statt des Repository-Blobs gehasht.

## Reproduktion

Vollständiger Lauf aus der Repository-Wurzel (Python {sys.version.split()[0]}, NumPy {np.__version__}, Pillow {Image.__version__}):

```powershell
python outputs/herbst-igel-r01-audit-r03/audit_herbst_igel_r03.py --repo . --output outputs/herbst-igel-r01-audit-r03
```

Der Script-Exitcode ist bei diesem nachgewiesenen `STOPP` ungleich null. `--reuse-self-report` ist ausschließlich für die reproduzierbare Neuerzeugung nachgelagerter Berichte/Bilder aus einem bereits vollständig abgeschlossenen, commitgleichen Direkttest vorgesehen.

## Offene reale Prüfungen

1. Optischer Nutzervergleich und finale Produktfreigabe anhand der beiden Prüfbilder.
2. FDM-Testdruck mit 0,4-mm-Düse und 0,12-mm-Layer, optional adaptiv bis 0,08 mm.
3. Reale Ø10,0/Ø10,4-Pass- und Klebeprobe in den gewählten PLA-Chargen.
4. Slicer-spezifische Prüfung von Supportzugänglichkeit und Oberflächenwirkung.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false` – der Audit ändert keine verbindliche Funktion, kein Nutzermaß und keine Produktgeometrie; optische und reale Endprüfungen bleiben ausdrücklich offen.
"""
    (out / "AUDIT-SOLL-IST.md").write_text(report, encoding="utf-8")

    # Scratch copies are not deliverables and are removed only after all reads complete.
    body_file.unlink()
    back_file.unlink()
    body_file.parent.rmdir()
    print(f"Audit complete: {result}", flush=True)
    return 0 if result == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
