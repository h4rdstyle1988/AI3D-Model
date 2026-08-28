#!/usr/bin/env python3
"""Validate outer-candidate-v001 without changing any mesh.

This validator deliberately does not use ``cumesh.cuBVH.ray_trace`` and does
not use edge-connectivity splitting to infer semantic shells.  cuMesh is used
only for unsigned point-to-triangle distance queries, a path independently
validated during Phase 4A.  Triangle intersections are evaluated in float64
with the conservative centroid-sphere broad phase from
``phase4_triangle_intersection_cpu.py``.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import trimesh
from scipy.spatial import cKDTree

import cumesh

from outer_candidate_build_v001 import (
    MOUTH_CENTER,
    MOUTH_RADII,
    load_c01,
    protected_mouth_faces,
    topology_metrics,
)
from phase4_triangle_intersection_cpu import (
    _flatten_query_rows,
    _plane_overlap_mask,
    _query_ball_sorted,
    build_radius_bins,
    prepare_mesh,
    triangle_triangle_intersection,
)


MM_HEIGHT = 190.0
MOUTH_DEPTH_THRESHOLD_Z = 0.05046635086182505
MOUTH_Y = 0.08803552022695714
MOUTH_FLOOR_Y = 0.0628704442297695
MOUTH_BACK_Z = -0.19948527134400784


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def glb_shells(glb_path: Path, build: dict[str, Any]) -> tuple[trimesh.Trimesh, trimesh.Trimesh]:
    scene = trimesh.load(glb_path, force="scene", process=False)
    if len(scene.geometry) != 1:
        raise AssertionError(f"expected one GLB primitive, found {len(scene.geometry)}")
    geometry = next(iter(scene.geometry.values()))
    vertices = np.asarray(geometry.vertices, dtype=np.float64)
    faces = np.asarray(geometry.faces, dtype=np.int64)
    outer_v = int(build["outer_metrics"]["vertices"])
    outer_f = int(build["outer_metrics"]["faces"])
    inner_v = int(build["inner_metrics"]["vertices"])
    inner_f = int(build["inner_metrics"]["faces"])
    if len(vertices) != outer_v + inner_v or len(faces) != outer_f + inner_f:
        raise AssertionError((len(vertices), len(faces), outer_v, outer_f, inner_v, inner_f))
    outer_faces = faces[:outer_f]
    inner_faces = faces[outer_f:] - outer_v
    if outer_faces.min() < 0 or outer_faces.max() >= outer_v:
        raise AssertionError("outer GLB face range invalid")
    if inner_faces.min() < 0 or inner_faces.max() >= inner_v:
        raise AssertionError("inner GLB face range invalid")
    outer = trimesh.Trimesh(vertices=vertices[:outer_v].copy(), faces=outer_faces.copy(), process=False)
    inner = trimesh.Trimesh(vertices=vertices[outer_v:].copy(), faces=inner_faces.copy(), process=False)
    return outer, inner


def exact_self_intersections(
    mesh: trimesh.Trimesh,
    name: str,
    *,
    chunk_size: int,
    workers: int,
    radius_bins: int,
    maximum_examples: int = 100,
) -> dict[str, Any]:
    """Count non-adjacent triangle intersections in one indexed mesh.

    Pairs sharing at least one vertex ID are topological neighbours and are
    excluded.  Faces that only meet through distinct but position-identical
    vertices remain candidates; this exposes geometric contacts hidden by
    index-level fan splitting.
    """

    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    prepared = prepare_mesh(np.asarray(mesh.triangles, dtype=np.float64), {"name": name})
    bins = build_radius_bins(prepared, radius_bins)
    tolerance = max(1e-12, prepared.bbox_diagonal * 1e-10)
    counts: dict[str, int] = {}
    examples: list[dict[str, Any]] = []
    stats = {
        "kdtree_query_hits": 0,
        "ordered_unique_pairs": 0,
        "nonadjacent_pairs": 0,
        "sphere_pass_pairs": 0,
        "aabb_pass_pairs": 0,
        "plane_pass_pairs": 0,
        "narrow_phase_pairs": 0,
    }
    started = time.perf_counter()
    next_progress = 0
    for start in range(0, len(faces), chunk_size):
        end = min(start + chunk_size, len(faces))
        points = prepared.centroids[start:end]
        for radius_bin in bins:
            query_radii = prepared.radii[start:end] + radius_bin.radius_max + tolerance
            rows = _query_ball_sorted(radius_bin.tree, points, query_radii, workers)
            ia, local_b = _flatten_query_rows(rows, start)
            stats["kdtree_query_hits"] += int(len(ia))
            if len(ia) == 0:
                continue
            ib = radius_bin.indices[local_b]
            keep = ib > ia
            ia, ib = ia[keep], ib[keep]
            stats["ordered_unique_pairs"] += int(len(ia))
            if len(ia) == 0:
                continue

            fa = faces[ia]
            fb = faces[ib]
            shared = np.any(fa[:, :, None] == fb[:, None, :], axis=(1, 2))
            ia, ib = ia[~shared], ib[~shared]
            stats["nonadjacent_pairs"] += int(len(ia))
            if len(ia) == 0:
                continue

            delta = prepared.centroids[ia] - prepared.centroids[ib]
            center_sq = np.einsum("ij,ij->i", delta, delta)
            radius_sum = prepared.radii[ia] + prepared.radii[ib] + tolerance
            keep = center_sq <= radius_sum * radius_sum
            ia, ib = ia[keep], ib[keep]
            stats["sphere_pass_pairs"] += int(len(ia))
            if len(ia) == 0:
                continue

            keep = np.all(
                np.maximum(prepared.aabb_min[ia], prepared.aabb_min[ib])
                <= np.minimum(prepared.aabb_max[ia], prepared.aabb_max[ib]) + tolerance,
                axis=1,
            )
            ia, ib = ia[keep], ib[keep]
            stats["aabb_pass_pairs"] += int(len(ia))
            if len(ia) == 0:
                continue

            keep = _plane_overlap_mask(prepared, prepared, ia, ib, tolerance)
            ia, ib = ia[keep], ib[keep]
            stats["plane_pass_pairs"] += int(len(ia))
            if len(ia) == 0:
                continue

            order = np.lexsort((ib, ia))
            for index_a, index_b in zip(ia[order].tolist(), ib[order].tolist()):
                stats["narrow_phase_pairs"] += 1
                hit, kind = triangle_triangle_intersection(
                    prepared.triangles[index_a],
                    prepared.triangles[index_b],
                    tolerance,
                    1e-10,
                    1e-12,
                )
                if not hit:
                    continue
                counts[kind] = counts.get(kind, 0) + 1
                if len(examples) < maximum_examples:
                    examples.append(
                        {"triangle_a": int(index_a), "triangle_b": int(index_b), "kind": kind}
                    )
        percent = int(100 * end / len(faces))
        if percent >= next_progress:
            print(f"{name} self-intersection: {end}/{len(faces)} ({percent}%)", flush=True)
            next_progress = percent + 5

    pair_count = int(sum(counts.values()))
    return {
        "algorithm": "float64 conservative centroid-sphere + AABB + plane + exact triangle narrow phase",
        "adjacency_rule": "pairs sharing any vertex ID excluded; position-identical distinct IDs remain testable",
        "triangle_count": int(len(faces)),
        "degenerate_triangle_count": int(np.count_nonzero(prepared.degenerate)),
        "distance_tolerance_model_units": float(tolerance),
        "self_intersecting_or_contact_pair_count": pair_count,
        "kind_counts": {key: int(value) for key, value in sorted(counts.items())},
        "examples": examples,
        "examples_truncated": pair_count > len(examples),
        "candidate_statistics": stats,
        "seconds": float(time.perf_counter() - started),
        "status": "PASS" if pair_count == 0 else "FAIL",
    }


def run_self_stage(args: argparse.Namespace) -> None:
    build = json.loads(args.build_json.read_text(encoding="utf-8"))
    source_hash_before = sha256(Path(build["source"]["path"]))
    outer, inner = glb_shells(args.glb, build)
    outer_result = exact_self_intersections(
        outer, "outer", chunk_size=args.self_chunk, workers=args.workers, radius_bins=args.radius_bins
    )
    del outer
    gc.collect()
    inner_result = exact_self_intersections(
        inner, "inner", chunk_size=args.self_chunk, workers=args.workers, radius_bins=args.radius_bins
    )
    result = {
        "schema": "ai3d.outer-candidate.self-intersections.v1",
        "candidate": "outer-candidate-v001",
        "analysis_only": True,
        "mesh_mutated": False,
        "invalidated_methods_not_used": [
            "invalidated-cumesh-raytrace-v1",
            "invalidated-edge-connectivity-split-v1",
        ],
        "outer": outer_result,
        "inner": inner_result,
        "source_sha256_before": source_hash_before,
        "source_sha256_after": sha256(Path(build["source"]["path"])),
    }
    atomic_json(args.self_json, result)
    print(json.dumps({"outer": outer_result["status"], "inner": inner_result["status"]}, indent=2))


class UnsignedDistanceOnly:
    def __init__(self, target: trimesh.Trimesh, batch_size: int = 65536):
        self.bvh = cumesh.cuBVH(
            np.asarray(target.vertices, dtype=np.float32), np.asarray(target.faces, dtype=np.int32)
        )
        self.batch_size = int(batch_size)

    def query(self, points: np.ndarray) -> np.ndarray:
        source = np.ascontiguousarray(points, dtype=np.float32)
        result = np.empty(len(source), dtype=np.float32)
        for start in range(0, len(source), self.batch_size):
            end = min(start + self.batch_size, len(source))
            batch = torch.from_numpy(source[start:end]).to("cuda")
            with torch.inference_mode():
                distance, _, _ = self.bvh.unsigned_distance(batch, return_uvw=False)
            result[start:end] = distance.detach().cpu().numpy()
        torch.cuda.synchronize()
        return result


def quadrature(mesh: trimesh.Trimesh, face_mask: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    bary = np.asarray(
        ((2 / 3, 1 / 6, 1 / 6), (1 / 6, 2 / 3, 1 / 6), (1 / 6, 1 / 6, 2 / 3)),
        dtype=np.float32,
    )
    triangles = np.asarray(mesh.triangles, dtype=np.float32)
    areas = np.asarray(mesh.area_faces, dtype=np.float64)
    if face_mask is not None:
        triangles = triangles[face_mask]
        areas = areas[face_mask]
    points = np.einsum("qa,fac->fqc", bary, triangles).reshape((-1, 3))
    weights = np.repeat(areas / 3.0, 3)
    return points, weights


def weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    order = np.argsort(values, kind="mergesort")
    values = np.asarray(values, dtype=np.float64)[order]
    weights = np.asarray(weights, dtype=np.float64)[order]
    cumulative = np.cumsum(weights)
    return float(values[min(int(np.searchsorted(cumulative, q * cumulative[-1])), len(values) - 1)])


def directional_deviation(
    source: trimesh.Trimesh,
    target: trimesh.Trimesh,
    query: UnsignedDistanceOnly,
    mm_per_unit: float,
    face_mask: np.ndarray | None = None,
) -> dict[str, Any]:
    points, weights = quadrature(source, face_mask)
    q_distance = query.query(points)
    if face_mask is None:
        vertex_ids = np.arange(len(source.vertices), dtype=np.int64)
    else:
        vertex_ids = np.unique(np.asarray(source.faces, dtype=np.int64)[face_mask])
    vertex_points = np.asarray(source.vertices, dtype=np.float32)[vertex_ids]
    v_distance = query.query(vertex_points)
    q_max = int(np.argmax(q_distance))
    v_max = int(np.argmax(v_distance))
    if float(q_distance[q_max]) >= float(v_distance[v_max]):
        maximum = float(q_distance[q_max])
        location = points[q_max]
        location_kind = "quadrature"
    else:
        maximum = float(v_distance[v_max])
        location = vertex_points[v_max]
        location_kind = "vertex"
    ids = np.linspace(0, len(points) - 1, min(16, len(points)), dtype=np.int64)
    _, cpu_distance, _ = trimesh.proximity.closest_point_naive(target, points[ids].astype(np.float64))
    cpu_error = np.abs(cpu_distance - q_distance[ids])
    return {
        "quadrature_samples": int(len(points)),
        "vertex_samples": int(len(vertex_points)),
        "sampled_maximum_mm": maximum * mm_per_unit,
        "sampled_maximum_location_model_units": [float(value) for value in location],
        "sampled_maximum_location_mm_from_model_origin": [float(value * mm_per_unit) for value in location],
        "sampled_maximum_location_kind": location_kind,
        "area_weighted_p95_mm": weighted_quantile(q_distance, weights, 0.95) * mm_per_unit,
        "area_weighted_median_mm": weighted_quantile(q_distance, weights, 0.50) * mm_per_unit,
        "sampled_minimum_mm": float(min(q_distance.min(), v_distance.min())) * mm_per_unit,
        "cpu_naive_spotcheck": {
            "samples": int(len(ids)),
            "maximum_abs_error_mm": float(cpu_error.max()) * mm_per_unit,
            "p95_abs_error_mm": float(np.quantile(cpu_error, 0.95)) * mm_per_unit,
            "status": "PASS" if float(cpu_error.max()) * mm_per_unit <= 0.02 else "FAIL",
        },
        "sampling_contract": "all vertices plus three deterministic area-weighted quadrature points per face",
    }


def front_depth(mesh: trimesh.Trimesh, xy_points: np.ndarray) -> np.ndarray:
    triangles = np.asarray(mesh.triangles, dtype=np.float64)
    xy = triangles[:, :, :2]
    a = xy[:, 0]
    e0 = xy[:, 1] - a
    e1 = xy[:, 2] - a
    denominator = e0[:, 0] * e1[:, 1] - e0[:, 1] * e1[:, 0]
    valid_projection = np.abs(denominator) > 1e-16
    aabb_min = xy.min(axis=1)
    aabb_max = xy.max(axis=1)
    result = np.full(len(xy_points), np.nan, dtype=np.float64)
    for index, point in enumerate(np.asarray(xy_points, dtype=np.float64)):
        candidate = np.flatnonzero(
            valid_projection
            & np.all(aabb_min <= point[None] + 1e-12, axis=1)
            & np.all(aabb_max >= point[None] - 1e-12, axis=1)
        )
        if len(candidate) == 0:
            continue
        rel = point[None] - a[candidate]
        den = denominator[candidate]
        u = (rel[:, 0] * e1[candidate, 1] - rel[:, 1] * e1[candidate, 0]) / den
        v = (e0[candidate, 0] * rel[:, 1] - e0[candidate, 1] * rel[:, 0]) / den
        inside = (u >= -1e-10) & (v >= -1e-10) & (u + v <= 1 + 1e-10)
        if not np.any(inside):
            continue
        candidate = candidate[inside]
        u = u[inside]
        v = v[inside]
        z = (
            triangles[candidate, 0, 2]
            + u * (triangles[candidate, 1, 2] - triangles[candidate, 0, 2])
            + v * (triangles[candidate, 2, 2] - triangles[candidate, 0, 2])
        )
        result[index] = float(np.max(z))
    return result


def mouth_first_hit(c01: trimesh.Trimesh, outer: trimesh.Trimesh, mm_per_unit: float) -> dict[str, Any]:
    xs = np.linspace(MOUTH_CENTER[0] - MOUTH_RADII[0], MOUTH_CENTER[0] + MOUTH_RADII[0], 45)
    ys = np.linspace(MOUTH_CENTER[1] - MOUTH_RADII[1], MOUTH_CENTER[1] + MOUTH_RADII[1], 39)
    grid = np.asarray([(x, y) for y in ys for x in xs], dtype=np.float64)
    inside = np.sum(((grid - MOUTH_CENTER[None]) / MOUTH_RADII[None]) ** 2, axis=1) <= 1.0
    grid = grid[inside]
    c01_depth = front_depth(c01, grid)
    cavity = np.isfinite(c01_depth) & (c01_depth <= MOUTH_DEPTH_THRESHOLD_Z)
    points = grid[cavity]
    c01_depth = c01_depth[cavity]
    if len(points) > 512:
        ids = np.linspace(0, len(points) - 1, 512, dtype=np.int64)
        points, c01_depth = points[ids], c01_depth[ids]
    outer_depth = front_depth(outer, points)
    covered = np.isfinite(outer_depth)
    delta = np.abs(outer_depth[covered] - c01_depth[covered]) * mm_per_unit
    max_index = int(np.argmax(delta)) if len(delta) else -1
    covered_points = points[covered]
    return {
        "method": "Float64 all-triangle projected-AABB and exact 2-D barycentric +Z front-hit",
        "sample_definition": "deterministic grid in validated Phase-4A mouth ellipse; C01 front depth <= validated cavity threshold",
        "samples": int(len(points)),
        "candidate_covered_samples": int(np.count_nonzero(covered)),
        "missing_candidate_hits": int(np.count_nonzero(~covered)),
        "absolute_depth_difference_mm": {
            "median": None if not len(delta) else float(np.median(delta)),
            "p95": None if not len(delta) else float(np.quantile(delta, 0.95)),
            "maximum": None if not len(delta) else float(np.max(delta)),
            "maximum_location_model_xy": None if max_index < 0 else [float(v) for v in covered_points[max_index]],
        },
        "status": "PASS" if len(delta) and np.count_nonzero(~covered) == 0 and float(np.quantile(delta, 0.95)) <= 0.05 and float(np.max(delta)) <= 0.20 else "FAIL",
    }


def section_segments(mesh: trimesh.Trimesh, normal: np.ndarray, origin: np.ndarray) -> np.ndarray:
    return np.asarray(
        trimesh.intersections.mesh_plane(mesh, plane_normal=normal, plane_origin=origin),
        dtype=np.float64,
    )


def section_samples(segments: np.ndarray, axes: tuple[int, int]) -> np.ndarray:
    if not len(segments):
        return np.empty((0, 2), dtype=np.float64)
    points = np.concatenate((segments[:, 0], segments[:, 1], segments.mean(axis=1)), axis=0)
    return points[:, axes]


def symmetric_section_distance(before: np.ndarray, after: np.ndarray, axes: tuple[int, int], mm_per_unit: float) -> dict[str, Any]:
    a = section_samples(before, axes)
    b = section_samples(after, axes)
    if not len(a) or not len(b):
        return {"status": "FAIL", "reason": "empty section"}
    da = cKDTree(b).query(a, k=1)[0]
    db = cKDTree(a).query(b, k=1)[0]
    values = np.concatenate((da, db)) * mm_per_unit
    return {
        "samples": int(len(values)),
        "median_mm": float(np.median(values)),
        "p95_mm": float(np.quantile(values, 0.95)),
        "sampled_maximum_mm": float(np.max(values)),
        "warning": "nearest sampled section-point distance; endpoints plus segment midpoints, not exact curve Hausdorff",
        "status": "PASS" if float(np.quantile(values, 0.95)) <= 0.10 else "FAIL",
    }


def render_sections(
    output_dir: Path,
    c01: trimesh.Trimesh,
    outer: trimesh.Trimesh,
    inner: trimesh.Trimesh,
    mm_per_unit: float,
) -> tuple[list[dict[str, Any]], list[Path], Path]:
    definitions = [
        ("mouth-horizontal", f"Mouth horizontal (y={MOUTH_Y * mm_per_unit:.1f} mm plane)", np.array([0.0, 1.0, 0.0]), np.array([0.0, MOUTH_Y, 0.0]), (0, 2), "X", "Z"),
        ("mouth-sagittal", "Mouth/head sagittal (x=0)", np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0, 0.0]), (1, 2), "Y", "Z"),
        ("mouth-floor", f"Mouth-floor horizontal (y={MOUTH_FLOOR_Y * mm_per_unit:.1f} mm plane)", np.array([0.0, 1.0, 0.0]), np.array([0.0, MOUTH_FLOOR_Y, 0.0]), (0, 2), "X", "Z"),
        ("mouth-back", f"Mouth back-wall coronal (z={MOUTH_BACK_Z * mm_per_unit:.1f} mm plane)", np.array([0.0, 0.0, 1.0]), np.array([0.0, 0.0, MOUTH_BACK_Z]), (0, 1), "X", "Y"),
    ]
    reports: list[dict[str, Any]] = []
    paths: list[Path] = []
    for slug, title, normal, origin, axes, x_label, y_label in definitions:
        before = section_segments(c01, normal, origin)
        after_outer = section_segments(outer, normal, origin)
        after_inner = section_segments(inner, normal, origin)
        report = symmetric_section_distance(before, after_outer, axes, mm_per_unit)
        report.update(
            {
                "slug": slug,
                "plane_normal": normal.tolist(),
                "plane_origin_model_units": origin.tolist(),
                "before_segments": int(len(before)),
                "after_outer_segments": int(len(after_outer)),
                "after_inner_segments": int(len(after_inner)),
            }
        )
        reports.append(report)
        figure, axis = plt.subplots(figsize=(8, 7), constrained_layout=True)
        for segments, color, style, label, width in (
            (before, "#1479d1", "-", "C01 before", 1.5),
            (after_outer, "#d6278b", "--", "candidate outer", 1.1),
            (after_inner, "#ed8b00", "-", "new inner wall", 0.8),
        ):
            for index, segment in enumerate(segments):
                projected = segment[:, axes] * mm_per_unit
                axis.plot(projected[:, 0], projected[:, 1], color=color, linestyle=style, linewidth=width, alpha=0.86, label=label if index == 0 else None)
        axis.set_title(title)
        axis.set_xlabel(f"{x_label} (mm at 190 mm model height)")
        axis.set_ylabel(f"{y_label} (mm at 190 mm model height)")
        axis.set_aspect("equal", adjustable="box")
        axis.grid(True, linewidth=0.35, alpha=0.3)
        axis.legend(loc="best")
        path = output_dir / f"outer-candidate-v001-section-{slug}.png"
        figure.savefig(path, dpi=180)
        plt.close(figure)
        paths.append(path)

    figure, axes = plt.subplots(2, 2, figsize=(15, 13), constrained_layout=True)
    for axis, path in zip(axes.ravel(), paths):
        axis.imshow(plt.imread(path))
        axis.set_title(path.stem.replace("outer-candidate-v001-section-", ""))
        axis.axis("off")
    figure.suptitle("outer-candidate-v001 — C01 before vs repaired outer + new inner wall", fontsize=16)
    contact = output_dir / "outer-candidate-v001-before-after-sections.png"
    figure.savefig(contact, dpi=160)
    plt.close(figure)
    return reports, paths, contact


def representative_crossing_point(outer: trimesh.Trimesh, inner: trimesh.Trimesh, cross: dict[str, Any]) -> dict[str, Any]:
    example = cross["intersections"]["examples"][0]
    tri_a = np.asarray(outer.triangles[int(example["triangle_a"])], dtype=np.float64)
    tri_b = np.asarray(inner.triangles[int(example["triangle_b"])], dtype=np.float64)
    points: list[np.ndarray] = []

    def edge_hits_triangle(p0: np.ndarray, p1: np.ndarray, tri: np.ndarray) -> None:
        direction = p1 - p0
        edge1 = tri[1] - tri[0]
        edge2 = tri[2] - tri[0]
        h = np.cross(direction, edge2)
        determinant = float(np.dot(edge1, h))
        if abs(determinant) <= 1e-15:
            return
        inv = 1.0 / determinant
        s = p0 - tri[0]
        u = inv * float(np.dot(s, h))
        q = np.cross(s, edge1)
        v = inv * float(np.dot(direction, q))
        t = inv * float(np.dot(edge2, q))
        if -1e-10 <= u <= 1 + 1e-10 and -1e-10 <= v and u + v <= 1 + 1e-10 and -1e-10 <= t <= 1 + 1e-10:
            points.append(p0 + np.clip(t, 0.0, 1.0) * direction)

    for tri_source, tri_target in ((tri_a, tri_b), (tri_b, tri_a)):
        for edge in ((0, 1), (1, 2), (2, 0)):
            edge_hits_triangle(tri_source[edge[0]], tri_source[edge[1]], tri_target)
    if points:
        point = np.mean(np.asarray(points), axis=0)
    else:
        point = 0.5 * (tri_a.mean(axis=0) + tri_b.mean(axis=0))
    return {
        "outer_triangle": int(example["triangle_a"]),
        "inner_triangle": int(example["triangle_b"]),
        "kind": example["kind"],
        "representative_point_model_units": [float(value) for value in point],
        "point_derivation": "mean of float64 segment-triangle intersection points for first proven pair",
    }


def run_metrics_stage(args: argparse.Namespace) -> None:
    build = json.loads(args.build_json.read_text(encoding="utf-8"))
    self_report = json.loads(args.self_json.read_text(encoding="utf-8"))
    cross = json.loads(args.cross_json.read_text(encoding="utf-8"))
    source_path = Path(build["source"]["path"])
    source_before = sha256(source_path)
    c01 = load_c01(source_path)
    outer, inner = glb_shells(args.glb, build)
    mm_per_unit = MM_HEIGHT / float(np.ptp(c01.bounds[:, 1]))

    print("validating serialized topology", flush=True)
    outer_stl = trimesh.load(args.outer_stl, force="mesh", process=True)
    inner_stl = trimesh.load(args.inner_stl, force="mesh", process=True)
    combined_stl = trimesh.load(args.combined_stl, force="mesh", process=True)
    topology = {
        "glb_indexed_outer": topology_metrics(outer),
        "glb_indexed_inner": topology_metrics(inner),
        "stl_roundtrip_outer": topology_metrics(outer_stl),
        "stl_roundtrip_inner": topology_metrics(inner_stl),
        "stl_roundtrip_combined": topology_metrics(combined_stl),
    }
    del outer_stl, inner_stl, combined_stl
    gc.collect()

    print("measuring bidirectional C01 deviation with cuMesh UDF only", flush=True)
    target_outer = UnsignedDistanceOnly(outer)
    c01_to_outer = directional_deviation(c01, outer, target_outer, mm_per_unit)
    c01_mouth_mask = protected_mouth_faces(c01, 5.0, mm_per_unit)
    c01_mouth_to_outer = directional_deviation(c01, outer, target_outer, mm_per_unit, c01_mouth_mask)
    del target_outer
    torch.cuda.empty_cache()
    gc.collect()

    target_c01 = UnsignedDistanceOnly(c01)
    outer_to_c01 = directional_deviation(outer, c01, target_c01, mm_per_unit)
    outer_mouth_mask = protected_mouth_faces(outer, 5.0, mm_per_unit)
    outer_mouth_to_c01 = directional_deviation(outer, c01, target_c01, mm_per_unit, outer_mouth_mask)
    del target_c01
    torch.cuda.empty_cache()
    gc.collect()

    print("running independent Float64 mouth first-hit comparison", flush=True)
    mouth_depth = mouth_first_hit(c01, outer, mm_per_unit)
    print("rendering before/after sections", flush=True)
    section_report, section_paths, contact_path = render_sections(args.output_dir, c01, outer, inner, mm_per_unit)

    representative = representative_crossing_point(outer, inner, cross)
    representative["representative_point_mm_from_model_origin"] = [
        float(value * mm_per_unit) for value in representative["representative_point_model_units"]
    ]
    representative["minimum_wall_thickness_mm"] = 0.0
    representative["reason"] = "proven noncoplanar outer-inner triangle crossing"

    deviation = {
        "c01_to_candidate_outer": c01_to_outer,
        "candidate_outer_to_c01": outer_to_c01,
        "bidirectional_sampled_maximum_mm": max(c01_to_outer["sampled_maximum_mm"], outer_to_c01["sampled_maximum_mm"]),
        "bidirectional_area_weighted_p95_mm": max(c01_to_outer["area_weighted_p95_mm"], outer_to_c01["area_weighted_p95_mm"]),
        "interpretation": "measured all-vertex + three-point quadrature maximum; not an exact continuous Hausdorff proof",
    }
    mouth = {
        "surface_deviation": {
            "c01_to_candidate_outer": c01_mouth_to_outer,
            "candidate_outer_to_c01": outer_mouth_to_c01,
            "bidirectional_sampled_maximum_mm": max(c01_mouth_to_outer["sampled_maximum_mm"], outer_mouth_to_c01["sampled_maximum_mm"]),
            "bidirectional_area_weighted_p95_mm": max(c01_mouth_to_outer["area_weighted_p95_mm"], outer_mouth_to_c01["area_weighted_p95_mm"]),
        },
        "front_hit_depth": mouth_depth,
        "section_checks": [item for item in section_report if item["slug"].startswith("mouth")],
    }

    gates = {
        "glb_shells_watertight_and_edge_manifold": bool(
            topology["glb_indexed_outer"]["watertight"]
            and topology["glb_indexed_inner"]["watertight"]
            and topology["glb_indexed_outer"]["nonmanifold_edges"] == 0
            and topology["glb_indexed_inner"]["nonmanifold_edges"] == 0
        ),
        "stl_roundtrip_watertight_and_edge_manifold": bool(
            topology["stl_roundtrip_combined"]["watertight"]
            and topology["stl_roundtrip_combined"]["nonmanifold_edges"] == 0
        ),
        "outer_self_intersection_free": self_report["outer"]["status"] == "PASS",
        "inner_self_intersection_free": self_report["inner"]["status"] == "PASS",
        "outer_inner_intersection_and_contact_free": not bool(cross["intersections"]["intersects"]),
        "minimum_wall_thickness_positive": float(cross["global_minimum"]["distance"]) > 0.0,
        "mouth_front_depth_preserved": mouth_depth["status"] == "PASS",
        "mouth_surface_p95_at_most_0_05mm": mouth["surface_deviation"]["bidirectional_area_weighted_p95_mm"] <= 0.05,
        "source_unchanged": source_before == sha256(source_path),
        "c02_not_used": build["guardrails"]["c02_used"] is False,
        "tail_components_not_used": build["guardrails"]["tail_components_used"] == [],
    }
    status = "VALIDATION_PASS_NOT_FINAL" if all(gates.values()) else "REJECTED_VALIDATION_FAILED"

    artifacts = [args.build_json, args.cross_json, args.self_json, args.glb, args.outer_stl, args.inner_stl, args.combined_stl, *section_paths, contact_path]
    result = {
        "schema": "ai3d.outer-candidate.validation.v1",
        "status": status,
        "candidate": "outer-candidate-v001",
        "analysis_only": True,
        "candidate_adopted_as_final": False,
        "mesh_mutated_during_validation": False,
        "invalidated_methods_not_used": [
            "invalidated-cumesh-raytrace-v1",
            "invalidated-edge-connectivity-split-v1",
        ],
        "source": {
            "path": str(source_path),
            "sha256_before": source_before,
            "sha256_after": sha256(source_path),
        },
        "scale": {"model_height_mm": MM_HEIGHT, "millimeters_per_model_unit": mm_per_unit},
        "build_guardrails": build["guardrails"],
        "topology": topology,
        "component_interpretation": "two intentional closed boundary surfaces (outer and inner); tail/detail components were not incorporated",
        "self_intersections": {"path": str(args.self_json), "outer": self_report["outer"], "inner": self_report["inner"]},
        "outer_inner_intersections_and_contacts": {
            "path": str(args.cross_json),
            "intersecting_pair_count": int(cross["intersections"]["intersecting_pair_count"]),
            "kind_counts": cross["intersections"]["kind_counts"],
            "global_minimum": cross["global_minimum"],
            "representative_minimum_wall_location": representative,
        },
        "minimum_wall_thickness": {
            "millimeters": 0.0 if cross["intersections"]["intersects"] else float(cross["global_minimum"]["distance"]) * mm_per_unit,
            "status": "FAIL" if cross["intersections"]["intersects"] else "PASS",
            "location": representative,
            "nominal_requested_mm": float(build["inner_build"]["nominal_wall_mm"]),
            "voxel_pitch_mm": float(build["inner_build"]["pitch_mm"]),
        },
        "outer_surface_deviation_vs_c01": deviation,
        "mouth_validation": mouth,
        "sections": section_report,
        "gates": gates,
        "decision": {
            "status": status,
            "reason": "candidate has proven outer-inner crossings and is not released; no automatic repair attempted" if status != "VALIDATION_PASS_NOT_FINAL" else "all validation gates passed",
            "automatic_followup_repair_performed": False,
        },
        "software": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "hip": torch.version.hip,
            "trimesh": trimesh.__version__,
            "numpy": np.__version__,
        },
        "artifacts": [
            {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in artifacts if path.exists()
        ],
    }
    atomic_json(args.validation_json, result)
    print(json.dumps({"status": status, "gates": gates, "deviation": deviation, "mouth_front": mouth_depth}, indent=2))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("stage", choices=("self", "metrics"))
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--build-json", type=Path, required=True)
    result.add_argument("--glb", type=Path, required=True)
    result.add_argument("--outer-stl", type=Path, required=True)
    result.add_argument("--inner-stl", type=Path, required=True)
    result.add_argument("--combined-stl", type=Path, required=True)
    result.add_argument("--cross-json", type=Path, required=True)
    result.add_argument("--self-json", type=Path, required=True)
    result.add_argument("--validation-json", type=Path, required=True)
    result.add_argument("--self-chunk", type=int, default=512)
    result.add_argument("--radius-bins", type=int, default=8)
    result.add_argument("--workers", type=int, default=4)
    return result


def main() -> None:
    args = parser().parse_args()
    if args.stage == "self":
        run_self_stage(args)
    else:
        run_metrics_stage(args)


if __name__ == "__main__":
    main()
