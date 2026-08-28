#!/usr/bin/env python3
"""Exact read-only analysis of the four TRELLIS pig tail components.

No geometry is exported or modified.  The validated cuMesh unsigned-distance
query is used only for distribution statistics; exact inter-mesh minima and
triangle intersections use the independent Float64 CPU implementation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np
import trimesh

from phase4_component_atlas import extract_component, face_component_labels
from phase4_triangle_intersection_cpu import analyze_prepared_meshes, prepare_mesh
from outer_candidate_validate_v001 import UnsignedDistanceOnly, quadrature, weighted_quantile
from smoke_single_solid import atomic_json, bounds_record, topology
from v002_prebuild_c01_analysis import self_events


EXPECTED_SHA = "58f6a915c53b587e8e796283b1750bd0c060104a90b4616c935c6ccc70771a7d"
TAIL_IDS = (5, 7, 8, 9)
TARGET_HEIGHT_MM = 190.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_ranked(source: Path) -> tuple[dict[int, trimesh.Trimesh], float]:
    if sha256(source).lower() != EXPECTED_SHA:
        raise RuntimeError("Source hash mismatch")
    loaded = trimesh.load(source, force="mesh", process=True)
    vertices = np.asarray(loaded.vertices, dtype=np.float64)
    faces = np.asarray(loaded.faces, dtype=np.int64)
    labels = face_component_labels(vertices, faces)
    order = sorted(
        range(int(labels.max()) + 1),
        key=lambda value: int(np.count_nonzero(labels == value)),
        reverse=True,
    )
    components = {
        rank: extract_component(vertices, faces, np.flatnonzero(labels == raw_label))
        for rank, raw_label in enumerate(order, start=1)
    }
    scale = TARGET_HEIGHT_MM / float(np.ptp(np.asarray(components[1].bounds), axis=0)[1])
    for mesh in components.values():
        mesh.vertices = np.asarray(mesh.vertices, dtype=np.float64) * scale
    return components, scale


def directional_udf(source: trimesh.Trimesh, target: trimesh.Trimesh) -> dict[str, Any]:
    query = UnsignedDistanceOnly(target, batch_size=65536)
    points, weights = quadrature(source)
    quadrature_distance = query.query(points).astype(np.float64)
    vertices = np.asarray(source.vertices, dtype=np.float32)
    vertex_distance = query.query(vertices).astype(np.float64)
    combined = np.r_[quadrature_distance, vertex_distance]
    index = int(np.argmin(combined))
    if index < len(points):
        source_witness = np.asarray(points[index], dtype=np.float64)
        witness_kind = "quadrature"
    else:
        source_witness = np.asarray(vertices[index - len(points)], dtype=np.float64)
        witness_kind = "vertex"
    closest, cpu_distance, face_id = trimesh.proximity.closest_point_naive(
        target, source_witness.reshape((1, 3))
    )
    return {
        "sampling": "all vertices plus three deterministic area-weighted quadrature points per face",
        "quadrature_samples": int(len(points)),
        "vertex_samples": int(len(vertices)),
        "sampled_minimum_mm": float(combined[index]),
        "area_weighted_p01_mm": weighted_quantile(quadrature_distance, weights, 0.01),
        "area_weighted_p05_mm": weighted_quantile(quadrature_distance, weights, 0.05),
        "area_weighted_median_mm": weighted_quantile(quadrature_distance, weights, 0.50),
        "area_weighted_p95_mm": weighted_quantile(quadrature_distance, weights, 0.95),
        "sampled_maximum_mm": float(combined.max()),
        "sampled_source_witness_mm": source_witness.tolist(),
        "sampled_source_witness_kind": witness_kind,
        "CPU_exact_target_point_for_sampled_witness_mm": closest[0].tolist(),
        "CPU_exact_distance_for_sampled_witness_mm": float(cpu_distance[0]),
        "CPU_target_face_for_sampled_witness": int(face_id[0]),
        "backend": "cuMesh unsigned_distance only; invalidated ray_trace is never called",
    }


def pair_analysis(a_id: int, a: trimesh.Trimesh, b_id: int, b: trimesh.Trimesh, workers: int) -> dict[str, Any]:
    prepared_a = prepare_mesh(np.asarray(a.triangles, dtype=np.float64), {"component": a_id})
    prepared_b = prepare_mesh(np.asarray(b.triangles, dtype=np.float64), {"component": b_id})
    exact = analyze_prepared_meshes(
        prepared_a,
        prepared_b,
        chunk_size=256,
        pair_batch_size=32768,
        radius_bin_count=8,
        workers=workers,
        maximum_examples=30,
        compute_global_minimum=True,
        progress=False,
        include_timings=True,
    )
    bounds_a = np.asarray(a.bounds, dtype=np.float64)
    bounds_b = np.asarray(b.bounds, dtype=np.float64)
    intersection_extents = np.maximum(
        0.0, np.minimum(bounds_a[1], bounds_b[1]) - np.maximum(bounds_a[0], bounds_b[0])
    )
    union_extents = np.maximum(bounds_a[1], bounds_b[1]) - np.minimum(bounds_a[0], bounds_b[0])
    return {
        "components": [a_id, b_id],
        "AABB_intersection_extents_mm": intersection_extents.tolist(),
        "AABB_intersection_volume_mm3": float(np.prod(intersection_extents)),
        "AABB_IoU": float(np.prod(intersection_extents) / max(np.prod(union_extents), 1e-30)),
        "exact_CPU": exact,
        "A_to_B_unsigned_distance": directional_udf(a, b),
        "B_to_A_unsigned_distance": directional_udf(b, a),
    }


def render_tail(path: Path, components: dict[int, trimesh.Trimesh]) -> None:
    colors = {1: "#9ca3af", 5: "#16a34a", 7: "#dc2626", 8: "#ec4899", 9: "#7c3aed"}
    views = [("Back (-Z)", 0, -90), ("Left (-X)", 0, 180), ("Top (+Y)", 90, -90), ("Oblique", 22, 135)]
    figure = plt.figure(figsize=(18, 15), dpi=150, facecolor="#eef1f4")
    all_bounds = np.vstack([components[index].bounds for index in (1, 5, 7, 8, 9)])
    center = 0.5 * (all_bounds.min(axis=0) + all_bounds.max(axis=0))
    radius = 0.56 * float(np.max(all_bounds.max(axis=0) - all_bounds.min(axis=0)))
    for panel, (title, elev, azim) in enumerate(views, start=1):
        ax = figure.add_subplot(2, 2, panel, projection="3d", facecolor="#eef1f4")
        for component_id in (1, 5, 7, 8, 9):
            mesh = components[component_id]
            faces = np.asarray(mesh.faces, dtype=np.int64)
            if component_id == 1:
                ids = np.linspace(0, len(faces) - 1, min(50000, len(faces)), dtype=np.int64)
                alpha = 0.18
            else:
                ids = np.arange(len(faces), dtype=np.int64)
                alpha = 0.94
            triangles = np.asarray(mesh.triangles, dtype=np.float64)[ids]
            ax.add_collection3d(
                Poly3DCollection(triangles, facecolors=colors[component_id], edgecolors="none", alpha=alpha, rasterized=True)
            )
        ax.set_xlim(center[0] - radius, center[0] + radius)
        ax.set_ylim(center[1] - radius, center[1] + radius)
        ax.set_zlim(center[2] - radius, center[2] + radius)
        ax.set_box_aspect((1, 1, 1))
        ax.view_init(elev=elev, azim=azim)
        ax.set_axis_off()
        ax.set_title(title)
    figure.suptitle("Tail analysis · C05 green / C07 red / C08 pink / C09 purple · C01 gray", fontsize=15)
    figure.tight_layout()
    figure.savefig(path, facecolor="#eef1f4")
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    started = time.perf_counter()
    components, scale = load_ranked(args.source)
    selected = {index: components[index] for index in (1, 5, 7, 8, 9)}
    inventory = {}
    for component_id, mesh in selected.items():
        metrics = topology(mesh)
        events = self_events(mesh, name=f"C{component_id:02d}", workers=args.workers, chunk_size=512, radius_bins=8)
        inventory[str(component_id)] = {
            "stable_role": "C01 body" if component_id == 1 else "tail-related",
            "topology": metrics,
            "bounds_mm": bounds_record(mesh),
            "self_intersections_and_contacts": events,
        }
    pairs = {}
    for a_id, b_id in ((5, 1), (7, 1), (8, 1), (9, 1), (5, 7), (8, 9), (5, 8), (5, 9), (7, 8), (7, 9)):
        print(f"pair C{a_id:02d} vs C{b_id:02d}", flush=True)
        pairs[f"C{a_id:02d}_C{b_id:02d}"] = pair_analysis(a_id, selected[a_id], b_id, selected[b_id], args.workers)
    decision = {
        "visible_tail_components_to_keep": [5, 8],
        "double_skin_components_to_exclude": [7, 9],
        "basis": [
            "C05 and C08 are the larger outer members of two near-coincident pairs and match the visible long strand plus curled/end fragment.",
            "C07 and C09 add no independently visible feature and would reintroduce duplicate/inner boundaries.",
            "The reference image shows one connected curled tail, so C05 must connect to C01 and C08 must connect to C05 before the joint voxel rebuild.",
        ],
        "geometry_not_yet_created": True,
    }
    render_path = args.output / "tail-components-analysis.png"
    render_tail(render_path, selected)
    report = {
        "schema": "ai3d.full-model-fastpath.tail-analysis.v1",
        "analysis_only": True,
        "mesh_mutated": False,
        "source": {"path": str(args.source), "sha256": sha256(args.source), "millimeters_per_source_unit": scale},
        "tail_component_count": 4,
        "inventory": inventory,
        "pairwise": pairs,
        "selection_decision": decision,
        "visual": str(render_path),
        "total_seconds": time.perf_counter() - started,
        "invalidated_methods_not_used": ["invalidated-cumesh-raytrace-v1", "invalidated-edge-connectivity-split-v1"],
    }
    atomic_json(args.output / "tail-analysis.json", report)
    print(json.dumps({"status": "PASS", "output": str(args.output), "selection": decision}, indent=2))


if __name__ == "__main__":
    main()
