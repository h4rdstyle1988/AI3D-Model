#!/usr/bin/env python3
"""Deterministic CPU triangle/triangle analysis without rtree or FCL.

The tool is intended for the two large, nested TRELLIS pig shells.  It keeps
the source meshes read-only and provides two independent guarantees:

1. Intersection broad phase
   A triangle is enclosed by the sphere centred at its vertex centroid with
   radius ``max(||vertex-centroid||)``.  Intersecting triangles therefore
   satisfy ``||c_a-c_b|| <= r_a+r_b``.  Radius-binned scipy cKDTree queries,
   followed by the exact sphere predicate and an AABB predicate, are a
   guaranteed superset of all intersecting pairs (up to the declared numeric
   tolerance).

2. Exact global minimum distance
   ``max(0, ||c_a-c_b||-r_a-r_b)`` is a valid lower bound for triangle
   distance.  Starting from a real triangle-pair upper bound, the same KD
   trees enumerate every pair whose lower bound can improve that upper bound.
   Exact triangle distance is then evaluated from all vertex/triangle and all
   edge/edge feature pairs.  If an intersection was found, the exact minimum
   is zero immediately.

Narrow phase intersection uses float64 plane-sidedness rejection,
Moller-Trumbore segment/triangle tests in both directions, explicit
vertex-on-triangle handling for boundary contact, and coplanar 2-D SAT.

No mesh is edited or exported.  JSON output contains only analysis results.
Use ``--self-test`` for deterministic mini-tests and ``--performance-test``
for an in-memory triangulated-grid workload.  A 340x340 grid has 231,200
triangles per mesh and is representative of the two pig shell sizes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

import numpy as np
import scipy
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree


ALGORITHM_NAME = "centroid-sphere-kdtree-triangle-narrowphase"
ALGORITHM_VERSION = "1.0.0"


@dataclass(frozen=True)
class PreparedMesh:
    triangles: np.ndarray
    centroids: np.ndarray
    radii: np.ndarray
    aabb_min: np.ndarray
    aabb_max: np.ndarray
    unit_normals: np.ndarray
    plane_offsets: np.ndarray
    degenerate: np.ndarray
    bbox_min: np.ndarray
    bbox_max: np.ndarray
    bbox_diagonal: float
    metadata: dict[str, Any]


@dataclass(frozen=True)
class RadiusBin:
    indices: np.ndarray
    tree: cKDTree
    radius_min: float
    radius_max: float


def _as_float64_triangles(triangles: np.ndarray) -> np.ndarray:
    arr = np.ascontiguousarray(np.asarray(triangles, dtype=np.float64))
    if arr.ndim != 3 or arr.shape[1:] != (3, 3):
        raise ValueError(f"triangles must have shape (N, 3, 3), got {arr.shape}")
    if len(arr) == 0:
        raise ValueError("mesh has no triangles")
    if not np.isfinite(arr).all():
        bad = int(np.size(arr) - np.count_nonzero(np.isfinite(arr)))
        raise ValueError(f"mesh contains {bad} non-finite coordinate values")
    return arr


def prepare_mesh(
    triangles: np.ndarray,
    metadata: Optional[dict[str, Any]] = None,
) -> PreparedMesh:
    tri = _as_float64_triangles(triangles)
    centroids = tri.mean(axis=1)
    radii = np.linalg.norm(tri - centroids[:, None, :], axis=2).max(axis=1)
    aabb_min = tri.min(axis=1)
    aabb_max = tri.max(axis=1)
    bbox_min = aabb_min.min(axis=0)
    bbox_max = aabb_max.max(axis=0)
    bbox_diagonal = float(np.linalg.norm(bbox_max - bbox_min))

    edge_1 = tri[:, 1] - tri[:, 0]
    edge_2 = tri[:, 2] - tri[:, 0]
    raw_normals = np.cross(edge_1, edge_2)
    normal_length = np.linalg.norm(raw_normals, axis=1)
    # Cross-product magnitude has length^2 units.  The threshold is only used
    # to route pathological triangles away from plane tests; source metrics
    # should separately report whether such faces exist.
    area_scale = np.linalg.norm(edge_1, axis=1) * np.linalg.norm(edge_2, axis=1)
    degenerate_threshold = (
        np.finfo(np.float64).eps
        * np.maximum(area_scale, np.finfo(np.float64).tiny)
        * 128.0
    )
    degenerate = normal_length <= degenerate_threshold
    unit_normals = np.zeros_like(raw_normals)
    good = ~degenerate
    unit_normals[good] = raw_normals[good] / normal_length[good, None]
    plane_offsets = -np.einsum("ij,ij->i", unit_normals, tri[:, 0])

    return PreparedMesh(
        triangles=tri,
        centroids=centroids,
        radii=radii,
        aabb_min=aabb_min,
        aabb_max=aabb_max,
        unit_normals=unit_normals,
        plane_offsets=plane_offsets,
        degenerate=degenerate,
        bbox_min=bbox_min,
        bbox_max=bbox_max,
        bbox_diagonal=bbox_diagonal,
        metadata=dict(metadata or {}),
    )


def build_radius_bins(mesh: PreparedMesh, requested_bins: int) -> list[RadiusBin]:
    count = min(max(1, int(requested_bins)), len(mesh.triangles))
    order = np.argsort(mesh.radii, kind="mergesort")
    bins: list[RadiusBin] = []
    for idx in np.array_split(order, count):
        if len(idx) == 0:
            continue
        idx = np.asarray(idx, dtype=np.int64)
        bins.append(
            RadiusBin(
                indices=idx,
                tree=cKDTree(mesh.centroids[idx], compact_nodes=True, balanced_tree=True),
                radius_min=float(mesh.radii[idx].min()),
                radius_max=float(mesh.radii[idx].max()),
            )
        )
    return bins


def _query_ball_sorted(
    tree: cKDTree,
    points: np.ndarray,
    radii: np.ndarray,
    workers: int,
) -> Sequence[Sequence[int]]:
    kwargs: dict[str, Any] = {"workers": workers}
    try:
        return tree.query_ball_point(points, radii, return_sorted=True, **kwargs)
    except TypeError:  # scipy versions before return_sorted
        result = tree.query_ball_point(points, radii, **kwargs)
        return [sorted(row) for row in result]


def _flatten_query_rows(
    rows: Sequence[Sequence[int]],
    a_start: int,
) -> tuple[np.ndarray, np.ndarray]:
    lengths = np.fromiter((len(row) for row in rows), dtype=np.int64, count=len(rows))
    total = int(lengths.sum())
    if total == 0:
        empty = np.empty(0, dtype=np.int64)
        return empty, empty
    ia = np.repeat(np.arange(a_start, a_start + len(rows), dtype=np.int64), lengths)
    jb = np.fromiter(
        (int(value) for row in rows for value in row),
        dtype=np.int64,
        count=total,
    )
    return ia, jb


def _point_on_triangle(
    point: np.ndarray,
    tri: np.ndarray,
    unit_normal: np.ndarray,
    plane_offset: float,
    distance_tolerance: float,
    barycentric_tolerance: float,
) -> bool:
    if abs(float(np.dot(unit_normal, point) + plane_offset)) > distance_tolerance:
        return False
    a, b, c = tri
    v0 = b - a
    v1 = c - a
    v2 = point - a
    d00 = float(np.dot(v0, v0))
    d01 = float(np.dot(v0, v1))
    d11 = float(np.dot(v1, v1))
    d20 = float(np.dot(v2, v0))
    d21 = float(np.dot(v2, v1))
    denominator = d00 * d11 - d01 * d01
    if denominator <= np.finfo(np.float64).eps * max(
        d00 * d11, np.finfo(np.float64).tiny
    ) * 128.0:
        return False
    v = (d11 * d20 - d01 * d21) / denominator
    w = (d00 * d21 - d01 * d20) / denominator
    u = 1.0 - v - w
    eps = barycentric_tolerance
    return u >= -eps and v >= -eps and w >= -eps


def _segment_triangle_moller(
    p0: np.ndarray,
    p1: np.ndarray,
    tri: np.ndarray,
    barycentric_tolerance: float,
    angular_tolerance: float,
) -> bool:
    """Moller-Trumbore ray test restricted to the finite segment [p0,p1]."""
    a, b, c = tri
    direction = p1 - p0
    edge1 = b - a
    edge2 = c - a
    h = np.cross(direction, edge2)
    determinant = float(np.dot(edge1, h))
    determinant_scale = (
        float(np.linalg.norm(edge1))
        * float(np.linalg.norm(edge2))
        * float(np.linalg.norm(direction))
    )
    if abs(determinant) <= angular_tolerance * max(determinant_scale, np.finfo(float).tiny):
        return False
    inv_det = 1.0 / determinant
    s = p0 - a
    u = inv_det * float(np.dot(s, h))
    eps = barycentric_tolerance
    if u < -eps or u > 1.0 + eps:
        return False
    q = np.cross(s, edge1)
    v = inv_det * float(np.dot(direction, q))
    if v < -eps or u + v > 1.0 + eps:
        return False
    segment_parameter = inv_det * float(np.dot(edge2, q))
    return -eps <= segment_parameter <= 1.0 + eps


def _coplanar_triangle_sat(
    tri_a: np.ndarray,
    tri_b: np.ndarray,
    normal: np.ndarray,
    distance_tolerance: float,
) -> tuple[bool, str]:
    """2-D separating-axis test; reports overlap versus boundary-only touch."""
    drop_axis = int(np.argmax(np.abs(normal)))
    keep = [axis for axis in range(3) if axis != drop_axis]
    a2 = tri_a[:, keep]
    b2 = tri_b[:, keep]
    axes: list[np.ndarray] = []
    for poly in (a2, b2):
        for edge_index in range(3):
            edge = poly[(edge_index + 1) % 3] - poly[edge_index]
            axis = np.array([-edge[1], edge[0]], dtype=np.float64)
            length = float(np.linalg.norm(axis))
            if length > np.finfo(float).tiny:
                axes.append(axis / length)
    minimum_overlap = math.inf
    for axis in axes:
        pa = a2 @ axis
        pb = b2 @ axis
        overlap = min(float(pa.max()), float(pb.max())) - max(
            float(pa.min()), float(pb.min())
        )
        if overlap < -distance_tolerance:
            return False, "separated"
        minimum_overlap = min(minimum_overlap, overlap)
    kind = "coplanar_touching" if minimum_overlap <= distance_tolerance else "coplanar_overlap"
    return True, kind


def triangle_triangle_intersection(
    tri_a: np.ndarray,
    tri_b: np.ndarray,
    distance_tolerance: float,
    barycentric_tolerance: float,
    angular_tolerance: float,
) -> tuple[bool, str]:
    """Robust float64 triangle intersection including coplanar contact."""
    a = np.asarray(tri_a, dtype=np.float64)
    b = np.asarray(tri_b, dtype=np.float64)
    raw_na = np.cross(a[1] - a[0], a[2] - a[0])
    raw_nb = np.cross(b[1] - b[0], b[2] - b[0])
    len_na = float(np.linalg.norm(raw_na))
    len_nb = float(np.linalg.norm(raw_nb))
    scale_a = float(np.linalg.norm(a[1] - a[0]) * np.linalg.norm(a[2] - a[0]))
    scale_b = float(np.linalg.norm(b[1] - b[0]) * np.linalg.norm(b[2] - b[0]))
    relative_degenerate_a = len_na <= np.finfo(float).eps * max(
        scale_a, np.finfo(float).tiny
    ) * 128.0
    relative_degenerate_b = len_nb <= np.finfo(float).eps * max(
        scale_b, np.finfo(float).tiny
    ) * 128.0
    if relative_degenerate_a or relative_degenerate_b:
        # Degenerate input is outside the authoritative triangle contract.
        # Treat zero-distance feature contact as touching for diagnostics.
        d2 = float(triangle_triangle_distance_sq_batch(a[None], b[None])[0])
        return d2 <= distance_tolerance * distance_tolerance, "degenerate_touching"
    na = raw_na / len_na
    nb = raw_nb / len_nb
    da = -float(np.dot(na, a[0]))
    db = -float(np.dot(nb, b[0]))
    b_to_a = b @ na + da
    a_to_b = a @ nb + db
    eps = distance_tolerance
    if (np.all(b_to_a > eps) or np.all(b_to_a < -eps)) or (
        np.all(a_to_b > eps) or np.all(a_to_b < -eps)
    ):
        return False, "separated"

    cross_normals = np.cross(na, nb)
    parallel = float(np.linalg.norm(cross_normals)) <= angular_tolerance
    if parallel:
        coplanar = bool(np.max(np.abs(b_to_a)) <= eps and np.max(np.abs(a_to_b)) <= eps)
        if not coplanar:
            return False, "parallel_separated"
        return _coplanar_triangle_sat(a, b, na, eps)

    for edge_index in range(3):
        if _segment_triangle_moller(
            a[edge_index],
            a[(edge_index + 1) % 3],
            b,
            barycentric_tolerance,
            angular_tolerance,
        ):
            strict = bool(np.min(b_to_a) < -eps and np.max(b_to_a) > eps)
            return True, "noncoplanar_crossing" if strict else "touching"
        if _segment_triangle_moller(
            b[edge_index],
            b[(edge_index + 1) % 3],
            a,
            barycentric_tolerance,
            angular_tolerance,
        ):
            strict = bool(np.min(a_to_b) < -eps and np.max(a_to_b) > eps)
            return True, "noncoplanar_crossing" if strict else "touching"

    # Explicit boundary fallback catches a vertex exactly on an edge/face when
    # the segment determinant is numerically parallel.
    for point in a:
        if _point_on_triangle(point, b, nb, db, eps, barycentric_tolerance):
            return True, "touching"
    for point in b:
        if _point_on_triangle(point, a, na, da, eps, barycentric_tolerance):
            return True, "touching"
    return False, "separated"


def _plane_overlap_mask(
    mesh_a: PreparedMesh,
    mesh_b: PreparedMesh,
    ia: np.ndarray,
    ib: np.ndarray,
    distance_tolerance: float,
) -> np.ndarray:
    if len(ia) == 0:
        return np.empty(0, dtype=bool)
    tri_a = mesh_a.triangles[ia]
    tri_b = mesh_b.triangles[ib]
    na = mesh_a.unit_normals[ia]
    nb = mesh_b.unit_normals[ib]
    db_to_a = np.einsum("ij,ikj->ik", na, tri_b) + mesh_a.plane_offsets[ia, None]
    da_to_b = np.einsum("ij,ikj->ik", nb, tri_a) + mesh_b.plane_offsets[ib, None]
    eps = distance_tolerance
    separated_a = np.all(db_to_a > eps, axis=1) | np.all(db_to_a < -eps, axis=1)
    separated_b = np.all(da_to_b > eps, axis=1) | np.all(da_to_b < -eps, axis=1)
    degenerate = mesh_a.degenerate[ia] | mesh_b.degenerate[ib]
    return ~(separated_a | separated_b) | degenerate


def _point_segment_sq_batch(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    ab = b - a
    denominator = np.einsum("ij,ij->i", ab, ab)
    t = np.zeros(len(p), dtype=np.float64)
    good = denominator > np.finfo(float).tiny
    t[good] = np.einsum("ij,ij->i", p[good] - a[good], ab[good]) / denominator[good]
    np.clip(t, 0.0, 1.0, out=t)
    closest = a + t[:, None] * ab
    delta = p - closest
    return np.einsum("ij,ij->i", delta, delta)


def _point_triangle_sq_batch(p: np.ndarray, tri: np.ndarray) -> np.ndarray:
    a = tri[:, 0]
    b = tri[:, 1]
    c = tri[:, 2]
    ab = b - a
    ac = c - a
    normal = np.cross(ab, ac)
    normal_sq = np.einsum("ij,ij->i", normal, normal)
    ap = p - a

    edge_min = np.minimum.reduce(
        [
            _point_segment_sq_batch(p, a, b),
            _point_segment_sq_batch(p, b, c),
            _point_segment_sq_batch(p, c, a),
        ]
    )
    result = edge_min.copy()
    good = normal_sq > np.finfo(float).tiny
    if not np.any(good):
        return result

    # Project the point onto the triangle plane, then test barycentric inclusion.
    signed_numerator = np.einsum("ij,ij->i", ap, normal)
    projection = p.copy()
    projection[good] -= (
        signed_numerator[good] / normal_sq[good]
    )[:, None] * normal[good]
    v2 = projection - a
    d00 = np.einsum("ij,ij->i", ab, ab)
    d01 = np.einsum("ij,ij->i", ab, ac)
    d11 = np.einsum("ij,ij->i", ac, ac)
    d20 = np.einsum("ij,ij->i", v2, ab)
    d21 = np.einsum("ij,ij->i", v2, ac)
    denominator = d00 * d11 - d01 * d01
    valid = good & (np.abs(denominator) > np.finfo(float).tiny)
    v = np.zeros(len(p), dtype=np.float64)
    w = np.zeros(len(p), dtype=np.float64)
    v[valid] = (d11[valid] * d20[valid] - d01[valid] * d21[valid]) / denominator[valid]
    w[valid] = (d00[valid] * d21[valid] - d01[valid] * d20[valid]) / denominator[valid]
    u = 1.0 - v - w
    bary_eps = 1e-12
    inside = valid & (u >= -bary_eps) & (v >= -bary_eps) & (w >= -bary_eps)
    plane_sq = np.zeros(len(p), dtype=np.float64)
    plane_sq[good] = signed_numerator[good] ** 2 / normal_sq[good]
    result[inside] = plane_sq[inside]
    return np.maximum(result, 0.0)


def _segment_segment_sq_batch(
    p0: np.ndarray,
    p1: np.ndarray,
    q0: np.ndarray,
    q1: np.ndarray,
) -> np.ndarray:
    u = p1 - p0
    v = q1 - q0
    w = p0 - q0
    a = np.einsum("ij,ij->i", u, u)
    b = np.einsum("ij,ij->i", u, v)
    c = np.einsum("ij,ij->i", v, v)
    d = np.einsum("ij,ij->i", u, w)
    e = np.einsum("ij,ij->i", v, w)
    denominator = a * c - b * b

    endpoint_min = np.minimum.reduce(
        [
            _point_segment_sq_batch(p0, q0, q1),
            _point_segment_sq_batch(p1, q0, q1),
            _point_segment_sq_batch(q0, p0, p1),
            _point_segment_sq_batch(q1, p0, p1),
        ]
    )
    result = endpoint_min.copy()
    scale = np.maximum(a * c, np.finfo(float).tiny)
    nonparallel = np.abs(denominator) > np.finfo(float).eps * scale * 32.0
    if np.any(nonparallel):
        s = np.zeros(len(p0), dtype=np.float64)
        t = np.zeros(len(p0), dtype=np.float64)
        s[nonparallel] = (
            b[nonparallel] * e[nonparallel] - c[nonparallel] * d[nonparallel]
        ) / denominator[nonparallel]
        t[nonparallel] = (
            a[nonparallel] * e[nonparallel] - b[nonparallel] * d[nonparallel]
        ) / denominator[nonparallel]
        interior = nonparallel & (s >= 0.0) & (s <= 1.0) & (t >= 0.0) & (t <= 1.0)
        if np.any(interior):
            delta = w[interior] + s[interior, None] * u[interior] - t[interior, None] * v[interior]
            result[interior] = np.einsum("ij,ij->i", delta, delta)
    return np.maximum(result, 0.0)


def triangle_triangle_distance_sq_batch(tri_a: np.ndarray, tri_b: np.ndarray) -> np.ndarray:
    """Exact feature-pair distance for non-intersecting triangle pairs."""
    ta = np.asarray(tri_a, dtype=np.float64)
    tb = np.asarray(tri_b, dtype=np.float64)
    if ta.shape != tb.shape or ta.ndim != 3 or ta.shape[1:] != (3, 3):
        raise ValueError("paired triangle arrays must both have shape (N, 3, 3)")
    distances: list[np.ndarray] = []
    for vertex in range(3):
        distances.append(_point_triangle_sq_batch(ta[:, vertex], tb))
        distances.append(_point_triangle_sq_batch(tb[:, vertex], ta))
    for edge_a in range(3):
        for edge_b in range(3):
            distances.append(
                _segment_segment_sq_batch(
                    ta[:, edge_a],
                    ta[:, (edge_a + 1) % 3],
                    tb[:, edge_b],
                    tb[:, (edge_b + 1) % 3],
                )
            )
    return np.minimum.reduce(distances)


def _closest_point_triangle_scalar(point: np.ndarray, tri: np.ndarray) -> np.ndarray:
    # Candidate projections to the face and its three edges; choose the nearest.
    a, b, c = tri
    normal = np.cross(b - a, c - a)
    candidates: list[np.ndarray] = []
    normal_sq = float(np.dot(normal, normal))
    if normal_sq > np.finfo(float).tiny:
        q = point - (float(np.dot(point - a, normal)) / normal_sq) * normal
        if _point_on_triangle(
            q,
            tri,
            normal / math.sqrt(normal_sq),
            -float(np.dot(normal / math.sqrt(normal_sq), a)),
            1e-12,
            1e-12,
        ):
            candidates.append(q)
    for p0, p1 in ((a, b), (b, c), (c, a)):
        edge = p1 - p0
        denominator = float(np.dot(edge, edge))
        t = 0.0 if denominator <= np.finfo(float).tiny else float(np.dot(point - p0, edge) / denominator)
        t = min(1.0, max(0.0, t))
        candidates.append(p0 + t * edge)
    return min(candidates, key=lambda q: float(np.dot(point - q, point - q)))


def _closest_segment_points_scalar(
    p0: np.ndarray,
    p1: np.ndarray,
    q0: np.ndarray,
    q1: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    candidates: list[tuple[np.ndarray, np.ndarray]] = []
    for p in (p0, p1):
        edge = q1 - q0
        den = float(np.dot(edge, edge))
        t = 0.0 if den <= np.finfo(float).tiny else float(np.dot(p - q0, edge) / den)
        t = min(1.0, max(0.0, t))
        candidates.append((p, q0 + t * edge))
    for q in (q0, q1):
        edge = p1 - p0
        den = float(np.dot(edge, edge))
        s = 0.0 if den <= np.finfo(float).tiny else float(np.dot(q - p0, edge) / den)
        s = min(1.0, max(0.0, s))
        candidates.append((p0 + s * edge, q))
    u = p1 - p0
    v = q1 - q0
    w = p0 - q0
    aa = float(np.dot(u, u))
    bb = float(np.dot(u, v))
    cc = float(np.dot(v, v))
    dd = float(np.dot(u, w))
    ee = float(np.dot(v, w))
    den = aa * cc - bb * bb
    if abs(den) > np.finfo(float).eps * max(
        aa * cc, np.finfo(float).tiny
    ) * 32.0:
        s = (bb * ee - cc * dd) / den
        t = (aa * ee - bb * dd) / den
        if 0.0 <= s <= 1.0 and 0.0 <= t <= 1.0:
            candidates.append((p0 + s * u, q0 + t * v))
    return min(candidates, key=lambda pair: float(np.dot(pair[0] - pair[1], pair[0] - pair[1])))


def closest_triangle_witness(
    tri_a: np.ndarray,
    tri_b: np.ndarray,
) -> tuple[float, np.ndarray, np.ndarray, str]:
    candidates: list[tuple[np.ndarray, np.ndarray, str]] = []
    for vertex in range(3):
        pa = tri_a[vertex]
        pb = _closest_point_triangle_scalar(pa, tri_b)
        candidates.append((pa, pb, f"a_vertex_{vertex}_to_b_face"))
        pb2 = tri_b[vertex]
        pa2 = _closest_point_triangle_scalar(pb2, tri_a)
        candidates.append((pa2, pb2, f"b_vertex_{vertex}_to_a_face"))
    for edge_a in range(3):
        for edge_b in range(3):
            pa, pb = _closest_segment_points_scalar(
                tri_a[edge_a],
                tri_a[(edge_a + 1) % 3],
                tri_b[edge_b],
                tri_b[(edge_b + 1) % 3],
            )
            candidates.append((pa, pb, f"edge_{edge_a}_to_edge_{edge_b}"))
    pa, pb, feature = min(
        candidates,
        key=lambda item: float(np.dot(item[0] - item[1], item[0] - item[1])),
    )
    return float(np.linalg.norm(pa - pb)), pa, pb, feature


def _update_best(
    distances_sq: np.ndarray,
    ia: np.ndarray,
    ib: np.ndarray,
    best_sq: float,
    best_pair: Optional[tuple[int, int]],
) -> tuple[float, Optional[tuple[int, int]]]:
    if len(distances_sq) == 0:
        return best_sq, best_pair
    local_min = float(np.min(distances_sq))
    if not np.isfinite(best_sq):
        tolerance = np.finfo(float).eps * max(
            abs(local_min), np.finfo(float).tiny
        ) * 256.0
        candidates = np.flatnonzero(distances_sq <= local_min + tolerance)
        pairs = sorted((int(ia[k]), int(ib[k])) for k in candidates)
        return local_min, pairs[0]
    tolerance = np.finfo(float).eps * max(
        abs(best_sq), abs(local_min), np.finfo(float).tiny
    ) * 256.0
    if local_min < best_sq - tolerance:
        candidates = np.flatnonzero(distances_sq <= local_min + tolerance)
        pairs = sorted((int(ia[k]), int(ib[k])) for k in candidates)
        return local_min, pairs[0]
    if abs(local_min - best_sq) <= tolerance:
        candidates = np.flatnonzero(distances_sq <= local_min + tolerance)
        pairs = sorted((int(ia[k]), int(ib[k])) for k in candidates)
        candidate = pairs[0]
        if best_pair is None or candidate < best_pair:
            return min(best_sq, local_min), candidate
    return best_sq, best_pair


def initial_distance_upper_bound(
    mesh_a: PreparedMesh,
    mesh_b: PreparedMesh,
    pair_batch_size: int,
    workers: int,
) -> tuple[float, tuple[int, int], int]:
    tree_b = cKDTree(mesh_b.centroids, compact_nodes=True, balanced_tree=True)
    tree_a = cKDTree(mesh_a.centroids, compact_nodes=True, balanced_tree=True)
    best_sq = math.inf
    best_pair: Optional[tuple[int, int]] = None
    evaluated = 0

    for direction in ("a_to_b", "b_to_a"):
        source = mesh_a if direction == "a_to_b" else mesh_b
        target_tree = tree_b if direction == "a_to_b" else tree_a
        for start in range(0, len(source.triangles), pair_batch_size):
            end = min(start + pair_batch_size, len(source.triangles))
            _, nearest = target_tree.query(source.centroids[start:end], k=1, workers=workers)
            nearest = np.atleast_1d(nearest).astype(np.int64, copy=False)
            source_indices = np.arange(start, end, dtype=np.int64)
            if direction == "a_to_b":
                ia, ib = source_indices, nearest
            else:
                ia, ib = nearest, source_indices
            distances_sq = triangle_triangle_distance_sq_batch(
                mesh_a.triangles[ia], mesh_b.triangles[ib]
            )
            best_sq, best_pair = _update_best(distances_sq, ia, ib, best_sq, best_pair)
            evaluated += len(ia)
    if best_pair is None or not np.isfinite(best_sq):
        raise RuntimeError("could not establish a finite global-distance upper bound")
    return math.sqrt(max(0.0, best_sq)), best_pair, evaluated


def find_intersections(
    mesh_a: PreparedMesh,
    mesh_b: PreparedMesh,
    radius_bins: list[RadiusBin],
    chunk_size: int,
    workers: int,
    distance_tolerance: float,
    barycentric_tolerance: float,
    angular_tolerance: float,
    maximum_examples: int,
    progress: bool,
) -> tuple[dict[str, Any], dict[str, int]]:
    stats = {
        "kdtree_query_hits": 0,
        "sphere_pass_pairs": 0,
        "aabb_pass_pairs": 0,
        "plane_pass_pairs": 0,
        "narrow_phase_pairs": 0,
    }
    count = 0
    kind_counts: dict[str, int] = {}
    examples: list[dict[str, Any]] = []

    for start in range(0, len(mesh_a.triangles), chunk_size):
        end = min(start + chunk_size, len(mesh_a.triangles))
        points = mesh_a.centroids[start:end]
        for radius_bin in radius_bins:
            query_radii = mesh_a.radii[start:end] + radius_bin.radius_max + distance_tolerance
            rows = _query_ball_sorted(radius_bin.tree, points, query_radii, workers)
            ia, jb_local = _flatten_query_rows(rows, start)
            stats["kdtree_query_hits"] += len(ia)
            if len(ia) == 0:
                continue
            ib = radius_bin.indices[jb_local]

            delta = mesh_a.centroids[ia] - mesh_b.centroids[ib]
            center_sq = np.einsum("ij,ij->i", delta, delta)
            radius_sum = mesh_a.radii[ia] + mesh_b.radii[ib] + distance_tolerance
            keep = center_sq <= radius_sum * radius_sum
            ia, ib = ia[keep], ib[keep]
            stats["sphere_pass_pairs"] += len(ia)
            if len(ia) == 0:
                continue

            keep = np.all(
                np.maximum(mesh_a.aabb_min[ia], mesh_b.aabb_min[ib])
                <= np.minimum(mesh_a.aabb_max[ia], mesh_b.aabb_max[ib]) + distance_tolerance,
                axis=1,
            )
            ia, ib = ia[keep], ib[keep]
            stats["aabb_pass_pairs"] += len(ia)
            if len(ia) == 0:
                continue

            keep = _plane_overlap_mask(mesh_a, mesh_b, ia, ib, distance_tolerance)
            ia, ib = ia[keep], ib[keep]
            stats["plane_pass_pairs"] += len(ia)
            if len(ia) == 0:
                continue

            order = np.lexsort((ib, ia))
            ia, ib = ia[order], ib[order]
            for index_a, index_b in zip(ia.tolist(), ib.tolist()):
                stats["narrow_phase_pairs"] += 1
                hit, kind = triangle_triangle_intersection(
                    mesh_a.triangles[index_a],
                    mesh_b.triangles[index_b],
                    distance_tolerance,
                    barycentric_tolerance,
                    angular_tolerance,
                )
                if not hit:
                    continue
                count += 1
                kind_counts[kind] = kind_counts.get(kind, 0) + 1
                if len(examples) < maximum_examples:
                    examples.append(
                        {
                            "triangle_a": int(index_a),
                            "triangle_b": int(index_b),
                            "kind": kind,
                        }
                    )
        if progress:
            print(
                f"intersection broad/narrow phase: {end}/{len(mesh_a.triangles)} A triangles",
                file=sys.stderr,
                flush=True,
            )

    examples.sort(key=lambda item: (item["triangle_a"], item["triangle_b"], item["kind"]))
    result = {
        "intersects": bool(count),
        "intersecting_pair_count": int(count),
        "kind_counts": {key: int(kind_counts[key]) for key in sorted(kind_counts)},
        "examples": examples,
        "examples_truncated": bool(count > len(examples)),
    }
    return result, stats


def exact_global_minimum_distance(
    mesh_a: PreparedMesh,
    mesh_b: PreparedMesh,
    radius_bins: list[RadiusBin],
    chunk_size: int,
    pair_batch_size: int,
    workers: int,
    distance_tolerance: float,
    progress: bool,
) -> tuple[dict[str, Any], dict[str, int]]:
    upper_bound, best_pair, initial_pairs = initial_distance_upper_bound(
        mesh_a, mesh_b, pair_batch_size, workers
    )
    best_sq = upper_bound * upper_bound
    stats = {
        "initial_upper_bound_pairs": int(initial_pairs),
        "kdtree_query_hits": 0,
        "lower_bound_pass_pairs": 0,
        "exact_distance_pairs": 0,
    }

    for start in range(0, len(mesh_a.triangles), chunk_size):
        end = min(start + chunk_size, len(mesh_a.triangles))
        points = mesh_a.centroids[start:end]
        current_upper_bound = math.sqrt(max(0.0, best_sq))
        for radius_bin in radius_bins:
            query_radii = (
                mesh_a.radii[start:end]
                + radius_bin.radius_max
                + current_upper_bound
                + distance_tolerance
            )
            rows = _query_ball_sorted(radius_bin.tree, points, query_radii, workers)
            ia, jb_local = _flatten_query_rows(rows, start)
            stats["kdtree_query_hits"] += len(ia)
            if len(ia) == 0:
                continue
            ib = radius_bin.indices[jb_local]
            delta = mesh_a.centroids[ia] - mesh_b.centroids[ib]
            center_distance = np.linalg.norm(delta, axis=1)
            lower_bound = np.maximum(
                0.0,
                center_distance - mesh_a.radii[ia] - mesh_b.radii[ib],
            )
            current_upper_bound = math.sqrt(max(0.0, best_sq))
            keep = lower_bound <= current_upper_bound + distance_tolerance
            ia, ib = ia[keep], ib[keep]
            stats["lower_bound_pass_pairs"] += len(ia)
            if len(ia) == 0:
                continue
            order = np.lexsort((ib, ia))
            ia, ib = ia[order], ib[order]
            for pair_start in range(0, len(ia), pair_batch_size):
                pair_end = min(pair_start + pair_batch_size, len(ia))
                batch_a = ia[pair_start:pair_end]
                batch_b = ib[pair_start:pair_end]
                distances_sq = triangle_triangle_distance_sq_batch(
                    mesh_a.triangles[batch_a], mesh_b.triangles[batch_b]
                )
                best_sq, maybe_pair = _update_best(
                    distances_sq, batch_a, batch_b, best_sq, best_pair
                )
                if maybe_pair is not None:
                    best_pair = maybe_pair
                stats["exact_distance_pairs"] += len(batch_a)
        if progress:
            print(
                f"exact distance branch-and-bound: {end}/{len(mesh_a.triangles)} A triangles; "
                f"upper_bound={math.sqrt(max(0.0, best_sq)):.12g}",
                file=sys.stderr,
                flush=True,
            )

    distance, witness_a, witness_b, feature = closest_triangle_witness(
        mesh_a.triangles[best_pair[0]], mesh_b.triangles[best_pair[1]]
    )
    # Vectorized and scalar paths should agree; use the smaller roundoff-safe value.
    distance = min(distance, math.sqrt(max(0.0, best_sq)))
    result = {
        "status": "exact",
        "distance": float(distance),
        "squared_distance": float(distance * distance),
        "triangle_a": int(best_pair[0]),
        "triangle_b": int(best_pair[1]),
        "witness_point_a": [float(value) for value in witness_a],
        "witness_point_b": [float(value) for value in witness_b],
        "witness_feature": feature,
        "proof": (
            "All pairs capable of improving the current real-pair upper bound were "
            "enumerated using lower bound max(0, centroid_distance-radius_a-radius_b); "
            "each surviving pair used all vertex-triangle and edge-edge features."
        ),
    }
    return result, stats


def analyze_prepared_meshes(
    mesh_a: PreparedMesh,
    mesh_b: PreparedMesh,
    *,
    chunk_size: int = 256,
    pair_batch_size: int = 32768,
    radius_bin_count: int = 8,
    workers: int = 1,
    distance_tolerance: Optional[float] = None,
    barycentric_tolerance: float = 1e-10,
    angular_tolerance: float = 1e-12,
    maximum_examples: int = 100,
    compute_global_minimum: bool = True,
    progress: bool = False,
    include_timings: bool = True,
) -> dict[str, Any]:
    if chunk_size <= 0 or pair_batch_size <= 0:
        raise ValueError("chunk sizes must be positive")
    combined_diagonal = float(
        np.linalg.norm(
            np.maximum(mesh_a.bbox_max, mesh_b.bbox_max)
            - np.minimum(mesh_a.bbox_min, mesh_b.bbox_min)
        )
    )
    if distance_tolerance is None:
        distance_tolerance = max(1e-12, combined_diagonal * 1e-10)
    if distance_tolerance < 0:
        raise ValueError("distance tolerance must be non-negative")

    timings: dict[str, float] = {}
    started = time.perf_counter()
    stage = time.perf_counter()
    bins = build_radius_bins(mesh_b, radius_bin_count)
    timings["build_radius_bins"] = time.perf_counter() - stage

    stage = time.perf_counter()
    intersections, intersection_stats = find_intersections(
        mesh_a,
        mesh_b,
        bins,
        chunk_size,
        workers,
        distance_tolerance,
        barycentric_tolerance,
        angular_tolerance,
        maximum_examples,
        progress,
    )
    timings["intersection_search"] = time.perf_counter() - stage

    distance_stats: dict[str, int] = {}
    if intersections["intersects"]:
        first = intersections["examples"][0] if intersections["examples"] else None
        global_minimum = {
            "status": "exact_zero_due_to_intersection",
            "distance": 0.0,
            "squared_distance": 0.0,
            "triangle_a": None if first is None else first["triangle_a"],
            "triangle_b": None if first is None else first["triangle_b"],
            "witness_point_a": None,
            "witness_point_b": None,
            "witness_feature": None if first is None else first["kind"],
            "proof": "At least one narrow-phase triangle intersection was proven.",
        }
        timings["global_minimum"] = 0.0
    elif compute_global_minimum:
        stage = time.perf_counter()
        global_minimum, distance_stats = exact_global_minimum_distance(
            mesh_a,
            mesh_b,
            bins,
            chunk_size,
            pair_batch_size,
            workers,
            distance_tolerance,
            progress,
        )
        timings["global_minimum"] = time.perf_counter() - stage
    else:
        global_minimum = {
            "status": "not_computed",
            "distance": None,
            "proof": None,
        }
        timings["global_minimum"] = 0.0
    timings["total"] = time.perf_counter() - started

    result: dict[str, Any] = {
        "schema_version": 1,
        "algorithm": {
            "name": ALGORITHM_NAME,
            "version": ALGORITHM_VERSION,
            "intersection_candidate_guarantee": (
                "If two closed triangles intersect, their centroid spheres overlap; "
                "the radius-binned KD queries enumerate that pair before exact sphere, "
                "AABB, plane, Moller segment and coplanar SAT tests."
            ),
            "global_minimum_guarantee": (
                "For non-intersecting meshes, every pair with a centroid-sphere lower "
                "bound no greater than the current real-pair upper bound is evaluated."
            ),
            "numeric_contract": (
                "float64 predicates under the declared absolute distance, barycentric "
                "and angular tolerances; degenerate faces are reported separately."
            ),
        },
        "mesh_a": {
            **mesh_a.metadata,
            "triangle_count": int(len(mesh_a.triangles)),
            "degenerate_triangle_count": int(np.count_nonzero(mesh_a.degenerate)),
            "bbox_min": [float(value) for value in mesh_a.bbox_min],
            "bbox_max": [float(value) for value in mesh_a.bbox_max],
            "maximum_centroid_sphere_radius": float(mesh_a.radii.max()),
        },
        "mesh_b": {
            **mesh_b.metadata,
            "triangle_count": int(len(mesh_b.triangles)),
            "degenerate_triangle_count": int(np.count_nonzero(mesh_b.degenerate)),
            "bbox_min": [float(value) for value in mesh_b.bbox_min],
            "bbox_max": [float(value) for value in mesh_b.bbox_max],
            "maximum_centroid_sphere_radius": float(mesh_b.radii.max()),
        },
        "settings": {
            "chunk_size": int(chunk_size),
            "pair_batch_size": int(pair_batch_size),
            "radius_bin_count_requested": int(radius_bin_count),
            "radius_bin_count_actual": int(len(bins)),
            "workers": int(workers),
            "distance_tolerance": float(distance_tolerance),
            "barycentric_tolerance": float(barycentric_tolerance),
            "angular_tolerance": float(angular_tolerance),
            "compute_global_minimum": bool(compute_global_minimum),
        },
        "intersections": intersections,
        "global_minimum": global_minimum,
        "candidate_statistics": {
            "intersection": intersection_stats,
            "global_minimum": distance_stats,
        },
        "software": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "platform": platform.platform(),
        },
        "reproducibility": {
            "deterministic_pair_order": True,
            "random_sampling": False,
            "mesh_mutation": False,
            "timings_are_nondeterministic": bool(include_timings),
        },
    }
    if include_timings:
        result["timings_seconds"] = {key: float(value) for key, value in timings.items()}
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


_LOAD_CACHE: dict[tuple[str, bool], Any] = {}
_CANONICAL_COMPONENT_CACHE: dict[
    str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]
] = {}


def _load_trimesh(path: Path, process: bool) -> Any:
    key = (str(path.resolve()), bool(process))
    if key in _LOAD_CACHE:
        return _LOAD_CACHE[key].copy()
    try:
        import trimesh
    except ImportError as exc:  # pragma: no cover - environment-specific
        raise RuntimeError("trimesh is required to load non-NPZ mesh files") from exc
    loaded = trimesh.load(str(path), force="mesh", process=process)
    if not isinstance(loaded, trimesh.Trimesh):
        raise TypeError(f"could not flatten {path} to a Trimesh")
    _LOAD_CACHE[key] = loaded.copy()
    return loaded


def face_component_labels(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """Canonical shared-vertex face connectivity used by Phase-4 atlases.

    Deliberately do not use ``Trimesh.split``: its edge-adjacency semantics
    fragment the non-manifold TRELLIS shells even though their faces belong to
    one shared-vertex component.
    """
    vertices_array = np.asarray(vertices)
    faces_array = np.asarray(faces, dtype=np.int64)
    if faces_array.ndim != 2 or faces_array.shape[1] != 3:
        raise ValueError(f"faces must have shape (N, 3), got {faces_array.shape}")
    a, b, c = faces_array.T
    rows = np.concatenate((a, b, a, c))
    columns = np.concatenate((b, a, c, a))
    graph = coo_matrix(
        (np.ones(len(rows), dtype=np.uint8), (rows, columns)),
        shape=(len(vertices_array), len(vertices_array)),
    ).tocsr()
    _, vertex_labels = connected_components(graph, directed=False)
    raw_face_labels = vertex_labels[faces_array[:, 0]]
    _, compact = np.unique(raw_face_labels, return_inverse=True)
    return compact.astype(np.int32, copy=False)


def extract_component_triangles(
    vertices: np.ndarray,
    faces: np.ndarray,
    face_ids: np.ndarray,
) -> np.ndarray:
    """Extract exact triangle coordinates without topology processing."""
    selected_faces = np.asarray(faces, dtype=np.int64)[np.asarray(face_ids, dtype=np.int64)]
    return np.ascontiguousarray(
        np.asarray(vertices, dtype=np.float64)[selected_faces], dtype=np.float64
    )


def _canonical_components_for_path(
    path: Path,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    key = str(path.resolve())
    cached = _CANONICAL_COMPONENT_CACHE.get(key)
    if cached is not None:
        return cached
    mesh = _load_trimesh(path, process=True)
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    labels = face_component_labels(vertices, faces)
    counts = np.bincount(labels)
    # Match phase4_component_atlas.py exactly, including its deterministic
    # descending face-count ranking.
    order = np.argsort(counts)[::-1]
    cached = (vertices, faces, labels, order)
    _CANONICAL_COMPONENT_CACHE[key] = cached
    return cached


def load_triangle_source(
    path_text: str,
    component_rank: Optional[int],
    expected_component_count: Optional[int] = None,
) -> PreparedMesh:
    path = Path(path_text).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    metadata: dict[str, Any] = {
        "path": str(path),
        "size_bytes": int(path.stat().st_size),
        "sha256": _sha256(path),
        "component_rank_by_faces": component_rank,
    }
    if path.suffix.lower() == ".npz":
        with np.load(path, allow_pickle=False) as data:
            if "triangles" in data:
                triangles = data["triangles"]
            elif "vertices" in data and "faces" in data:
                triangles = data["vertices"][data["faces"]]
            else:
                raise ValueError("NPZ must contain triangles or vertices+faces")
        if component_rank is not None:
            raise ValueError("component selection is only supported for mesh files")
        metadata["loader"] = "numpy.npz"
        return prepare_mesh(triangles, metadata)

    metadata["loader"] = "trimesh"
    metadata["trimesh_process"] = bool(component_rank is not None)
    if component_rank is not None:
        if component_rank <= 0:
            raise ValueError("component rank is one-based and must be positive")
        vertices, faces, labels, order = _canonical_components_for_path(path)
        component_count = int(len(order))
        if expected_component_count is not None and component_count != expected_component_count:
            raise RuntimeError(
                "Canonical shared-vertex component assertion failed: "
                f"expected {expected_component_count}, found {component_count}"
            )
        if component_rank > component_count:
            raise ValueError(
                f"component rank {component_rank} requested, but mesh has {component_count} components"
            )
        raw_label = int(order[component_rank - 1])
        face_ids = np.flatnonzero(labels == raw_label)
        triangles = extract_component_triangles(vertices, faces, face_ids)
        metadata["component_connectivity"] = "canonical shared-vertex"
        metadata["component_count_after_processing"] = component_count
        metadata["component_face_count"] = int(len(face_ids))
        metadata["expected_component_count"] = expected_component_count
        return prepare_mesh(triangles, metadata)

    mesh = _load_trimesh(path, process=False)
    return prepare_mesh(np.asarray(mesh.triangles, dtype=np.float64), metadata)


def _run_case(
    name: str,
    tri_a: np.ndarray,
    tri_b: np.ndarray,
    expected_intersection: bool,
    expected_distance: float,
    expected_kind_prefix: Optional[str] = None,
) -> dict[str, Any]:
    a = prepare_mesh(np.asarray(tri_a, dtype=np.float64), {"synthetic": name + "_a"})
    b = prepare_mesh(np.asarray(tri_b, dtype=np.float64), {"synthetic": name + "_b"})
    result = analyze_prepared_meshes(
        a,
        b,
        chunk_size=4,
        pair_batch_size=32,
        radius_bin_count=2,
        workers=1,
        maximum_examples=10,
        include_timings=False,
    )
    actual_intersection = bool(result["intersections"]["intersects"])
    actual_distance = float(result["global_minimum"]["distance"])
    passed = actual_intersection == expected_intersection and math.isclose(
        actual_distance, expected_distance, rel_tol=1e-9, abs_tol=1e-9
    )
    if expected_kind_prefix is not None and actual_intersection:
        kinds = list(result["intersections"]["kind_counts"])
        passed = passed and any(kind.startswith(expected_kind_prefix) for kind in kinds)
    return {
        "name": name,
        "passed": bool(passed),
        "expected_intersection": expected_intersection,
        "actual_intersection": actual_intersection,
        "expected_distance": expected_distance,
        "actual_distance": actual_distance,
        "kind_counts": result["intersections"]["kind_counts"],
    }


def run_self_tests() -> dict[str, Any]:
    base = np.array([[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]])
    separated = np.array([[[0.0, 0.0, 1.0], [1.0, 0.0, 1.0], [0.0, 1.0, 1.0]]])
    crossing = np.array(
        [[[0.25, 0.25, -1.0], [0.25, 0.25, 1.0], [0.75, 0.25, 0.25]]]
    )
    point_contact = np.array(
        [[[1.0, 0.0, 0.0], [1.0, -1.0, 1.0], [1.0, 0.0, 1.0]]]
    )
    common_edge = np.array(
        [[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.5, 0.0, -1.0]]]
    )
    coplanar_common_edge = np.array(
        [[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, -1.0, 0.0]]]
    )
    coplanar = np.array([[[0.2, 0.2, 0.0], [1.2, 0.2, 0.0], [0.2, 1.2, 0.0]]])
    cases = [
        _run_case("separated", base, separated, False, 1.0),
        _run_case("proper_noncoplanar_intersection", base, crossing, True, 0.0, "noncoplanar"),
        _run_case("point_contact", base, point_contact, True, 0.0, "touching"),
        _run_case("common_edge", base, common_edge, True, 0.0, "touching"),
        _run_case(
            "coplanar_common_edge",
            base,
            coplanar_common_edge,
            True,
            0.0,
            "coplanar_touching",
        ),
        _run_case("coplanar_overlap", base, coplanar, True, 0.0, "coplanar"),
    ]

    # Multi-triangle guarantee test: the only intersecting pair is deliberately
    # not a nearest-centroid pair for every triangle.
    many_a = np.concatenate([base + np.array([[[3.0 * i, 0.0, 0.0]]]) for i in range(6)])
    many_b = np.concatenate(
        [separated + np.array([[[3.0 * i, 0.0, 0.0]]]) for i in range(5)]
        + [crossing + np.array([[[15.0, 0.0, 0.0]]])]
    )
    multi_result = analyze_prepared_meshes(
        prepare_mesh(many_a, {"synthetic": "multi_a"}),
        prepare_mesh(many_b, {"synthetic": "multi_b"}),
        chunk_size=2,
        pair_batch_size=16,
        radius_bin_count=3,
        workers=1,
        include_timings=False,
    )
    cases.append(
        {
            "name": "multi_triangle_candidate_guarantee",
            "passed": bool(
                multi_result["intersections"]["intersects"]
                and multi_result["global_minimum"]["distance"] == 0.0
            ),
            "intersecting_pair_count": multi_result["intersections"]["intersecting_pair_count"],
        }
    )

    # Canonical loader topology test: faces 0 and 1 share exactly one vertex,
    # not an edge.  Edge-adjacency splitters incorrectly produce three pieces;
    # Phase-4 shared-vertex connectivity must produce two components of sizes 2
    # and 1 and rank the two-face component first.
    loader_vertices = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [-1.0, 0.0, 0.0],
            [0.0, -1.0, 0.0],
            [10.0, 0.0, 0.0],
            [11.0, 0.0, 0.0],
            [10.0, 1.0, 0.0],
        ],
        dtype=np.float64,
    )
    loader_faces = np.array(
        [[0, 1, 2], [0, 3, 4], [5, 6, 7]], dtype=np.int64
    )
    loader_labels = face_component_labels(loader_vertices, loader_faces)
    loader_counts = np.bincount(loader_labels)
    loader_order = np.argsort(loader_counts)[::-1]
    extracted = extract_component_triangles(
        loader_vertices,
        loader_faces,
        np.flatnonzero(loader_labels == loader_order[0]),
    )
    cases.append(
        {
            "name": "canonical_shared_vertex_component_loader",
            "passed": bool(
                len(loader_order) == 2
                and sorted(loader_counts.tolist(), reverse=True) == [2, 1]
                and len(extracted) == 2
            ),
            "component_count": int(len(loader_order)),
            "face_counts_descending": sorted(
                (int(value) for value in loader_counts), reverse=True
            ),
            "rank_1_faces": int(len(extracted)),
        }
    )
    return {
        "self_test": "PASS" if all(case["passed"] for case in cases) else "FAIL",
        "cases": cases,
    }


def make_grid_triangles(grid_size: int, z: float) -> np.ndarray:
    n = int(grid_size)
    if n <= 0:
        raise ValueError("grid size must be positive")
    x, y = np.meshgrid(
        np.linspace(0.0, 1.0, n + 1, dtype=np.float64),
        np.linspace(0.0, 1.0, n + 1, dtype=np.float64),
        indexing="xy",
    )
    vertices = np.column_stack((x.ravel(), y.ravel(), np.full(x.size, z)))
    row = n + 1
    i = np.arange(n * n, dtype=np.int64)
    iy = i // n
    ix = i % n
    v00 = iy * row + ix
    v10 = v00 + 1
    v01 = v00 + row
    v11 = v01 + 1
    faces = np.empty((2 * n * n, 3), dtype=np.int64)
    faces[0::2] = np.column_stack((v00, v10, v11))
    faces[1::2] = np.column_stack((v00, v11, v01))
    return vertices[faces]


def run_performance_test(
    grid_size: int,
    separation: float,
    chunk_size: int,
    pair_batch_size: int,
    radius_bins: int,
    workers: int,
    progress: bool,
) -> dict[str, Any]:
    tri_a = make_grid_triangles(grid_size, 0.0)
    tri_b = make_grid_triangles(grid_size, separation)
    prepared_a = prepare_mesh(tri_a, {"synthetic": "grid_a", "grid_size": grid_size})
    prepared_b = prepare_mesh(tri_b, {"synthetic": "grid_b", "grid_size": grid_size})
    result = analyze_prepared_meshes(
        prepared_a,
        prepared_b,
        chunk_size=chunk_size,
        pair_batch_size=pair_batch_size,
        radius_bin_count=radius_bins,
        workers=workers,
        progress=progress,
        include_timings=True,
    )
    expected = abs(float(separation))
    actual = float(result["global_minimum"]["distance"])
    result["performance_test"] = {
        "grid_size": int(grid_size),
        "triangles_per_mesh": int(len(tri_a)),
        "expected_distance": expected,
        "actual_distance": actual,
        "passed": bool(
            not result["intersections"]["intersects"]
            and math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9)
        ),
        "representative_230k_grid_size": 340,
    }
    return result


def _json_dump(data: dict[str, Any], output: Optional[str]) -> None:
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if output:
        target = Path(output).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".tmp")
        temporary.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temporary, target)
    else:
        sys.stdout.write(text)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mesh_a", nargs="?", help="first mesh or NPZ")
    parser.add_argument("mesh_b", nargs="?", help="second mesh or NPZ")
    parser.add_argument("--component-a", type=int, help="one-based component rank by face count")
    parser.add_argument("--component-b", type=int, help="one-based component rank by face count")
    parser.add_argument(
        "--expected-components",
        type=int,
        default=19,
        help=(
            "hard assertion for canonical shared-vertex decomposition when a "
            "component rank is selected (default: 19; use 0 to disable)"
        ),
    )
    parser.add_argument("--output", help="atomic JSON output path; default stdout")
    parser.add_argument("--chunk-size", type=int, default=256)
    parser.add_argument("--pair-batch-size", type=int, default=32768)
    parser.add_argument("--radius-bins", type=int, default=8)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--distance-tolerance", type=float)
    parser.add_argument("--barycentric-tolerance", type=float, default=1e-10)
    parser.add_argument("--angular-tolerance", type=float, default=1e-12)
    parser.add_argument("--maximum-examples", type=int, default=100)
    parser.add_argument("--skip-global-minimum", action="store_true")
    parser.add_argument("--omit-timings", action="store_true")
    parser.add_argument("--progress", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--performance-test", action="store_true")
    parser.add_argument("--performance-grid", type=int, default=80)
    parser.add_argument("--performance-separation", type=float, default=0.01)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_argument_parser().parse_args(argv)
    if args.self_test:
        result = run_self_tests()
        _json_dump(result, args.output)
        return 0 if result["self_test"] == "PASS" else 1
    if args.performance_test:
        result = run_performance_test(
            args.performance_grid,
            args.performance_separation,
            args.chunk_size,
            args.pair_batch_size,
            args.radius_bins,
            args.workers,
            args.progress,
        )
        _json_dump(result, args.output)
        return 0 if result["performance_test"]["passed"] else 1
    if not args.mesh_a or not args.mesh_b:
        raise SystemExit("mesh_a and mesh_b are required unless a test mode is selected")

    expected_components = None if args.expected_components == 0 else args.expected_components
    if expected_components is not None and expected_components <= 0:
        raise SystemExit("--expected-components must be positive, or 0 to disable")
    mesh_a = load_triangle_source(args.mesh_a, args.component_a, expected_components)
    mesh_b = load_triangle_source(args.mesh_b, args.component_b, expected_components)
    result = analyze_prepared_meshes(
        mesh_a,
        mesh_b,
        chunk_size=args.chunk_size,
        pair_batch_size=args.pair_batch_size,
        radius_bin_count=args.radius_bins,
        workers=args.workers,
        distance_tolerance=args.distance_tolerance,
        barycentric_tolerance=args.barycentric_tolerance,
        angular_tolerance=args.angular_tolerance,
        maximum_examples=args.maximum_examples,
        compute_global_minimum=not args.skip_global_minimum,
        progress=args.progress,
        include_timings=not args.omit_timings,
    )
    _json_dump(result, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
