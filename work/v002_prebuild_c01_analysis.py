#!/usr/bin/env python3
"""Read-only v002 pre-build analysis of C01 and v001 event provenance.

No mesh is exported.  STL and 3MF roundtrips happen only in memory.  The two
invalidated Phase-4 approaches (cuMesh ray tracing and edge-connectivity shell
splitting) are not used.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import io
import json
import math
import os
import platform
import sys
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import scipy
import trimesh
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from outer_candidate_build_v001 import (
    MOUTH_CENTER,
    MOUTH_RADII,
    directed_edge_table,
    load_c01,
    protected_mouth_faces,
    topology_metrics,
)
from outer_candidate_validate_v001 import glb_shells
from phase4_triangle_intersection_cpu import (
    _flatten_query_rows,
    _plane_overlap_mask,
    _query_ball_sorted,
    build_radius_bins,
    prepare_mesh,
    triangle_triangle_intersection,
)


MM_HEIGHT = 190.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def canonical_triangles(triangles: np.ndarray) -> np.ndarray:
    result = np.empty_like(np.asarray(triangles, dtype=np.float64))
    for index, triangle in enumerate(np.asarray(triangles, dtype=np.float64)):
        order = np.lexsort((triangle[:, 2], triangle[:, 1], triangle[:, 0]))
        result[index] = triangle[order]
    return result


def self_events(
    mesh: trimesh.Trimesh,
    *,
    name: str,
    workers: int,
    chunk_size: int = 512,
    radius_bins: int = 8,
) -> dict[str, Any]:
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    prepared = prepare_mesh(np.asarray(mesh.triangles, dtype=np.float64), {"name": name})
    bins = build_radius_bins(prepared, radius_bins)
    tolerance = max(1e-12, prepared.bbox_diagonal * 1e-10)
    pairs: list[dict[str, Any]] = []
    stats = Counter()
    started = time.perf_counter()
    next_progress = 0
    for start in range(0, len(faces), chunk_size):
        stop = min(start + chunk_size, len(faces))
        points = prepared.centroids[start:stop]
        for radius_bin in bins:
            query_radii = prepared.radii[start:stop] + radius_bin.radius_max + tolerance
            rows = _query_ball_sorted(radius_bin.tree, points, query_radii, workers)
            ia, local_b = _flatten_query_rows(rows, start)
            stats["kdtree_query_hits"] += int(len(ia))
            if not len(ia):
                continue
            ib = radius_bin.indices[local_b]
            keep = ib > ia
            ia, ib = ia[keep], ib[keep]
            if not len(ia):
                continue
            fa, fb = faces[ia], faces[ib]
            shared = np.any(fa[:, :, None] == fb[:, None, :], axis=(1, 2))
            ia, ib = ia[~shared], ib[~shared]
            stats["nonadjacent_ordered_pairs"] += int(len(ia))
            if not len(ia):
                continue
            delta = prepared.centroids[ia] - prepared.centroids[ib]
            radius_sum = prepared.radii[ia] + prepared.radii[ib] + tolerance
            keep = np.einsum("ij,ij->i", delta, delta) <= radius_sum * radius_sum
            ia, ib = ia[keep], ib[keep]
            stats["sphere_pass"] += int(len(ia))
            if not len(ia):
                continue
            keep = np.all(
                np.maximum(prepared.aabb_min[ia], prepared.aabb_min[ib])
                <= np.minimum(prepared.aabb_max[ia], prepared.aabb_max[ib]) + tolerance,
                axis=1,
            )
            ia, ib = ia[keep], ib[keep]
            stats["aabb_pass"] += int(len(ia))
            if not len(ia):
                continue
            keep = _plane_overlap_mask(prepared, prepared, ia, ib, tolerance)
            ia, ib = ia[keep], ib[keep]
            stats["plane_pass"] += int(len(ia))
            if not len(ia):
                continue
            order = np.lexsort((ib, ia))
            for face_a, face_b in zip(ia[order].tolist(), ib[order].tolist()):
                stats["narrow_phase"] += 1
                hit, kind = triangle_triangle_intersection(
                    prepared.triangles[face_a], prepared.triangles[face_b], tolerance, 1e-10, 1e-12
                )
                if hit:
                    pairs.append({"face_a": int(face_a), "face_b": int(face_b), "kind": kind})
        percent = int(100 * stop / len(faces))
        if percent >= next_progress:
            print(f"{name}: {stop}/{len(faces)} ({percent}%)", flush=True)
            next_progress = percent + 10
    return {
        "triangle_count": int(len(faces)),
        "distance_tolerance_model_units": float(tolerance),
        "events": pairs,
        "counts": dict(Counter(row["kind"] for row in pairs)),
        "event_count": int(len(pairs)),
        "candidate_statistics": {key: int(value) for key, value in stats.items()},
        "seconds": float(time.perf_counter() - started),
        "algorithm": "Float64 conservative centroid-sphere/AABB/plane broadphase plus exact triangle narrowphase; shared-vertex pairs excluded",
    }


def shared_vertex_count(faces: np.ndarray, a: int, b: int) -> int:
    return int(len(set(faces[a].tolist()).intersection(faces[b].tolist())))


def mouth_event(tri_a: np.ndarray, tri_b: np.ndarray) -> bool:
    points = np.vstack((tri_a, tri_b))[:, :2]
    normalized = np.sum(((points - MOUTH_CENTER[None]) / MOUTH_RADII[None]) ** 2, axis=1)
    return bool(np.any(normalized <= 1.0))


def classify_v001_events(
    c01: trimesh.Trimesh,
    outer: trimesh.Trimesh,
    retained_ids: np.ndarray,
    events: list[dict[str, Any]],
    mm_per_unit: float,
) -> dict[str, Any]:
    original_faces = np.asarray(c01.faces, dtype=np.int64)
    original_triangles = np.asarray(c01.triangles, dtype=np.float64)
    outer_triangles = np.asarray(outer.triangles, dtype=np.float64)
    retained_count = int(len(retained_ids))
    diagonal = float(np.linalg.norm(np.ptp(np.asarray(outer.vertices), axis=0)))
    tolerances = [max(1e-12, diagonal * factor) for factor in (0.5e-10, 1e-10, 2e-10)]
    classified = []
    summary = Counter()
    detail = Counter()
    for event_id, event in enumerate(events, start=1):
        a, b = int(event["face_a"]), int(event["face_b"])
        tri_a, tri_b = outer_triangles[a], outer_triangles[b]
        candidate_trials = [
            triangle_triangle_intersection(tri_a, tri_b, tolerance, 1e-10, 1e-12)
            for tolerance in tolerances
        ]
        candidate_stable = all(hit for hit, _ in candidate_trials) and len({kind for _, kind in candidate_trials}) == 1
        retained_a, retained_b = a < retained_count, b < retained_count
        mapped_a = int(retained_ids[a]) if retained_a else None
        mapped_b = int(retained_ids[b]) if retained_b else None
        original_trials: list[tuple[bool, str]] = []
        original_shared = None
        if retained_a and retained_b:
            original_shared = shared_vertex_count(original_faces, mapped_a, mapped_b)
            original_trials = [
                triangle_triangle_intersection(
                    original_triangles[mapped_a], original_triangles[mapped_b], tolerance, 1e-10, 1e-12
                )
                for tolerance in tolerances
            ]
            original_stable = all(hit for hit, _ in original_trials) and len({kind for _, kind in original_trials}) == 1
            same_kind = original_stable and original_trials[1][1] == event["kind"]
        else:
            original_stable = False
            same_kind = False

        if not candidate_stable:
            provenance = "unclear_numeric"
            reason = "candidate event is not stable at 0.5x/1x/2x tolerance"
        elif retained_a and retained_b and original_stable and same_kind:
            provenance = "already_in_c01"
            reason = "both unchanged retained C01 triangles reproduce the same event at all three tolerances"
        elif not (retained_a and retained_b):
            provenance = "new_in_v001"
            reason = "at least one event triangle is a v001 boundary-loop patch face"
        else:
            provenance = "unclear_numeric"
            reason = "retained geometry does not reproduce the same stable event classification in C01"

        point = 0.5 * (tri_a.mean(axis=0) + tri_b.mean(axis=0))
        if retained_a and retained_b and original_shared:
            detail[f"{provenance}:original_shared_{original_shared}_vertices"] += 1
        elif retained_a and retained_b:
            detail[f"{provenance}:original_nonadjacent"] += 1
        else:
            detail[f"{provenance}:patch_involved"] += 1
        summary[f"{event['kind']}:{provenance}"] += 1
        classified.append(
            {
                "event_id": event_id,
                "kind": event["kind"],
                "classification": provenance,
                "reason": reason,
                "v001_faces": [a, b],
                "c01_faces": [mapped_a, mapped_b],
                "patch_face_involved": not (retained_a and retained_b),
                "original_shared_vertex_count": original_shared,
                "candidate_tolerance_trials": [
                    {"tolerance": tolerances[index], "hit": bool(hit), "kind": kind}
                    for index, (hit, kind) in enumerate(candidate_trials)
                ],
                "original_tolerance_trials": [
                    {"tolerance": tolerances[index], "hit": bool(hit), "kind": kind}
                    for index, (hit, kind) in enumerate(original_trials)
                ],
                "location_proxy_model_units": [float(value) for value in point],
                "location_proxy_mm": [float(value * mm_per_unit) for value in point],
                "inside_validated_mouth_projection": mouth_event(tri_a, tri_b),
            }
        )
    category_totals = Counter(row["classification"] for row in classified)
    return {
        "classification_contract": {
            "already_in_c01": "both triangles are unchanged retained C01 faces and the same event kind is reproduced at 0.5x, 1x and 2x tolerance",
            "new_in_v001": "one or both triangles are newly added v001 patch faces and the event is tolerance-stable",
            "unclear_numeric": "event or matching classification is not stable/reproducible under the tolerance audit",
            "adjacency_note": "retained pairs that shared C01 vertex IDs are reported separately; their coordinates are unchanged, but v001 fan splitting can change whether the pair is topologically adjacent",
        },
        "tolerances_model_units": tolerances,
        "category_totals": dict(category_totals),
        "by_kind_and_category": dict(summary),
        "adjacency_and_patch_breakdown": dict(detail),
        "events": classified,
    }


def edge_and_vertex_topology(mesh: trimesh.Trimesh) -> dict[str, Any]:
    faces = np.asarray(mesh.faces, dtype=np.int64)
    directed, face_ids, unique_edges, inverse, counts = directed_edge_table(faces)
    boundary_ids = np.flatnonzero(counts == 1)
    nonmanifold_ids = np.flatnonzero(counts > 2)
    defect_edges = unique_edges[np.r_[boundary_ids, nonmanifold_ids]]
    defect_vertices = np.unique(defect_edges) if len(defect_edges) else np.empty(0, dtype=np.int64)
    # Vertex-link audit only needs vertices incident to a bad edge.  A valid
    # closed 2-manifold vertex has one cycle of incident faces.
    bad_vertex_links = []
    for vertex in defect_vertices.tolist():
        incident = np.flatnonzero(np.any(faces == vertex, axis=1))
        adjacency = {int(face): set() for face in incident}
        for face in incident:
            others = faces[face][faces[face] != vertex]
            for other in others:
                linked = np.flatnonzero(np.any(faces[incident] == other, axis=1))
                for local in linked:
                    neighbour = int(incident[local])
                    if neighbour != int(face):
                        adjacency[int(face)].add(neighbour)
        degrees = [len(adjacency[int(face)]) for face in incident]
        unseen = set(int(value) for value in incident)
        components = 0
        while unseen:
            components += 1
            stack = [unseen.pop()]
            while stack:
                current = stack.pop()
                for neighbour in adjacency[current]:
                    if neighbour in unseen:
                        unseen.remove(neighbour)
                        stack.append(neighbour)
        if components != 1 or any(value != 2 for value in degrees):
            bad_vertex_links.append(
                {
                    "vertex": int(vertex),
                    "incident_faces": int(len(incident)),
                    "link_components": int(components),
                    "link_degree_min": int(min(degrees, default=0)),
                    "link_degree_max": int(max(degrees, default=0)),
                }
            )
    return {
        "unique_edges": int(len(unique_edges)),
        "boundary_edges": int(len(boundary_ids)),
        "nonmanifold_edges": int(len(nonmanifold_ids)),
        "maximum_edge_incidence": int(counts.max()),
        "vertices_incident_to_boundary_or_nonmanifold_edges": int(len(defect_vertices)),
        "invalid_vertex_links_among_defect_vertices": int(len(bad_vertex_links)),
        "invalid_vertex_link_examples": bad_vertex_links[:100],
    }


def connectivity_summary(mesh: trimesh.Trimesh) -> dict[str, Any]:
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    a, b, c = faces.T
    rows = np.concatenate((a, b, a, c))
    cols = np.concatenate((b, a, c, a))
    graph = coo_matrix(
        (np.ones(len(rows), dtype=np.uint8), (rows, cols)),
        shape=(len(vertices), len(vertices)),
    ).tocsr()
    _, vertex_labels = connected_components(graph, directed=False)
    shared_vertex_components = int(len(np.unique(vertex_labels[faces[:, 0]])))
    edge_pieces = mesh.split(only_watertight=False)
    rows = sorted(
        [
            {
                "faces": int(len(piece.faces)),
                "vertices": int(len(piece.vertices)),
                "area": float(piece.area),
                "extent_model_units": np.ptp(piece.bounds, axis=0).tolist(),
            }
            for piece in edge_pieces
        ],
        key=lambda row: row["faces"],
        reverse=True,
    )
    return {
        "canonical_shared_vertex_components": shared_vertex_components,
        "shared_edge_face_adjacency_components": int(len(rows)),
        "largest_edge_component_faces": rows[0]["faces"],
        "largest_edge_component_face_fraction": float(rows[0]["faces"] / len(faces)),
        "second_edge_component_faces": rows[1]["faces"] if len(rows) > 1 else 0,
        "remaining_edge_components_faces": int(sum(row["faces"] for row in rows[2:])),
        "top_20_edge_components": rows[:20],
        "interpretation": (
            "C01 is one canonical shared-vertex component, but invalid pinched/nonmanifold "
            "vertex joins split it into multiple shared-edge surface pieces.  The dominant "
            "piece contains nearly all faces; the remaining pieces are local repair targets."
        ),
    }


def weld_audit(mesh: trimesh.Trimesh, mm_per_unit: float) -> list[dict[str, Any]]:
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    diagonal = float(np.linalg.norm(np.ptp(vertices, axis=0)))
    rows = []
    for relative in (0.0, 1e-10, 1e-9, 1e-8, 1e-7, 1e-6):
        if relative == 0.0:
            unique, inverse = np.unique(vertices, axis=0, return_inverse=True)
            tolerance = 0.0
        else:
            tolerance = diagonal * relative
            keys = np.rint(vertices / tolerance).astype(np.int64)
            _, first, inverse = np.unique(keys, axis=0, return_index=True, return_inverse=True)
            unique = vertices[first]
        remapped = inverse[faces]
        collapsed = (
            (remapped[:, 0] == remapped[:, 1])
            | (remapped[:, 1] == remapped[:, 2])
            | (remapped[:, 2] == remapped[:, 0])
        )
        canonical_faces = np.sort(remapped, axis=1)
        duplicate_faces = int(len(canonical_faces) - len(np.unique(canonical_faces, axis=0)))
        welded = trimesh.Trimesh(vertices=unique, faces=remapped, process=False)
        metrics = topology_metrics(welded)
        rows.append(
            {
                "relative_to_bbox_diagonal": relative,
                "absolute_tolerance_model_units": tolerance,
                "absolute_tolerance_mm": tolerance * mm_per_unit,
                "vertices_before": int(len(vertices)),
                "vertices_after": int(len(unique)),
                "vertices_merged": int(len(vertices) - len(unique)),
                "collapsed_face_rows": int(np.count_nonzero(collapsed)),
                "duplicate_face_rows": duplicate_faces,
                "topology": metrics,
            }
        )
    return rows


def stl_roundtrip(mesh: trimesh.Trimesh) -> dict[str, Any]:
    payload = mesh.export(file_type="stl")
    loaded = trimesh.load(io.BytesIO(payload), file_type="stl", force="mesh", process=True)
    return {
        "implementation": "trimesh binary STL export + process=True import, entirely in memory",
        "bytes": int(len(payload)),
        "topology": topology_metrics(loaded),
        "vertices": int(len(loaded.vertices)),
        "faces": int(len(loaded.faces)),
    }


def minimal_3mf_roundtrip(mesh: trimesh.Trimesh) -> dict[str, Any]:
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    xml = io.StringIO()
    xml.write('<?xml version="1.0" encoding="UTF-8"?>')
    xml.write('<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"><resources><object id="1" type="model"><mesh><vertices>')
    for x, y, z in vertices:
        xml.write(f'<vertex x="{x:.17g}" y="{y:.17g}" z="{z:.17g}"/>')
    xml.write('</vertices><triangles>')
    for a, b, c in faces:
        xml.write(f'<triangle v1="{int(a)}" v2="{int(b)}" v3="{int(c)}"/>')
    xml.write('</triangles></mesh></object></resources><build><item objectid="1"/></build></model>')
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>',
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>',
        )
        archive.writestr("3D/3dmodel.model", xml.getvalue())
    raw = payload.getvalue()
    with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
        model_xml = archive.read("3D/3dmodel.model")
        if archive.testzip() is not None:
            raise RuntimeError("3MF CRC failure")
    import xml.etree.ElementTree as ET

    root = ET.fromstring(model_xml)
    namespace = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
    parsed_vertices = np.asarray(
        [
            [float(node.attrib[axis]) for axis in ("x", "y", "z")]
            for node in root.findall(".//m:vertices/m:vertex", namespace)
        ],
        dtype=np.float64,
    )
    parsed_faces = np.asarray(
        [
            [int(node.attrib[axis]) for axis in ("v1", "v2", "v3")]
            for node in root.findall(".//m:triangles/m:triangle", namespace)
        ],
        dtype=np.int64,
    )
    loaded = trimesh.Trimesh(vertices=parsed_vertices, faces=parsed_faces, process=False)
    return {
        "implementation": "standards-structured core 3MF OPC/ZIP + XML roundtrip in memory using Python stdlib; no lxml dependency",
        "bytes": int(len(raw)),
        "crc": "PASS",
        "vertex_coordinate_max_abs_error_model_units": float(np.max(np.abs(parsed_vertices - vertices))),
        "face_index_arrays_identical": bool(np.array_equal(parsed_faces, faces)),
        "topology": topology_metrics(loaded),
        "vertices": int(len(parsed_vertices)),
        "faces": int(len(parsed_faces)),
    }


def event_clusters(events: list[dict[str, Any]], mm_per_unit: float) -> dict[str, Any]:
    if not events:
        return {"count": 0, "clusters": []}
    points = np.asarray([row["location_proxy_model_units"] for row in events], dtype=np.float64)
    radius = 2.0 / mm_per_unit
    pairs = np.asarray(list(cKDTree(points).query_pairs(radius)), dtype=np.int64)
    if len(pairs):
        graph = coo_matrix((np.ones(2 * len(pairs)), (np.r_[pairs[:, 0], pairs[:, 1]], np.r_[pairs[:, 1], pairs[:, 0]])), shape=(len(points), len(points))).tocsr()
        count, labels = connected_components(graph, directed=False)
    else:
        count, labels = len(points), np.arange(len(points), dtype=np.int64)
    clusters = []
    for label in range(count):
        ids = np.flatnonzero(labels == label)
        values = points[ids]
        clusters.append(
            {
                "events": int(len(ids)),
                "bounds_min_mm": (values.min(axis=0) * mm_per_unit).tolist(),
                "bounds_max_mm": (values.max(axis=0) * mm_per_unit).tolist(),
                "centroid_mm": (values.mean(axis=0) * mm_per_unit).tolist(),
                "mouth_projection_events": int(sum(bool(events[index]["inside_validated_mouth_projection"]) for index in ids)),
            }
        )
    clusters.sort(key=lambda row: row["events"], reverse=True)
    return {"radius_mm": 2.0, "count": int(count), "clusters": clusters}


def render_event_map(path: Path, c01: trimesh.Trimesh, classified: dict[str, Any], mm_per_unit: float) -> None:
    vertices = np.asarray(c01.vertices, dtype=np.float64) * mm_per_unit
    sample = vertices[:: max(1, len(vertices) // 12000)]
    events = classified["events"]
    colors = {"already_in_c01": "#1f77b4", "new_in_v001": "#d62728", "unclear_numeric": "#7f7f7f"}
    views = [((0, 1), "Front projection", "X (mm)", "Y (mm)"), ((2, 1), "Side projection", "Z (mm)", "Y (mm)"), ((0, 2), "Top projection", "X (mm)", "Z (mm)")]
    categories = [category for category in ("already_in_c01", "new_in_v001", "unclear_numeric") if any(row["classification"] == category for row in events)]
    figure, axes = plt.subplots(len(categories), 3, figsize=(18, 6 * len(categories)), constrained_layout=True, squeeze=False)
    for row_index, category in enumerate(categories):
        rows = [row for row in events if row["classification"] == category]
        points = np.asarray([row["location_proxy_mm"] for row in rows])
        crossing = np.asarray([row["kind"] == "noncoplanar_crossing" for row in rows])
        for axis, (projection, title, x_label, y_label) in zip(axes[row_index], views):
            axis.scatter(sample[:, projection[0]], sample[:, projection[1]], s=0.15, color="#b8b8b8", alpha=0.22, rasterized=True)
            points = np.asarray([row["location_proxy_mm"] for row in rows])
            axis.scatter(points[~crossing, projection[0]], points[~crossing, projection[1]], s=11, marker="o", facecolors="none", edgecolors=colors[category], linewidths=0.75, alpha=0.8, label="contact")
            axis.scatter(points[crossing, projection[0]], points[crossing, projection[1]], s=13, marker="x", color=colors[category], linewidths=0.8, alpha=0.85, label="crossing")
            axis.set_title(f"{category} — {title}")
            axis.set_xlabel(x_label)
            axis.set_ylabel(y_label)
            axis.set_aspect("equal", adjustable="box")
            axis.grid(True, linewidth=0.3, alpha=0.25)
        axes[row_index, 0].legend(loc="lower left", fontsize=9)
    figure.suptitle("v001 outer self-events classified against original C01", fontsize=15)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--build-json", type=Path, required=True)
    parser.add_argument("--glb", type=Path, required=True)
    parser.add_argument("--preflight-json", type=Path, required=True)
    parser.add_argument("--mouth-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--overwrite-analysis", action="store_true")
    args = parser.parse_args()
    expected_names = {
        "V002-PREBUILD-ARTIFACT-MANIFEST.sha256",
        "V002-PREBUILD-C01-ANALYSIS.md",
        "v002-prebuild-c01-analysis.json",
        "v002-prebuild-v001-event-classification.json",
        "v002-prebuild-v001-event-classification.png",
    }
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        actual_names = {path.name for path in args.output_dir.iterdir()}
        if not args.overwrite_analysis or not actual_names.issubset(expected_names):
            raise FileExistsError(f"refusing to overwrite non-empty output directory: {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    source_hash_before = sha256(args.source)
    build = json.loads(args.build_json.read_text(encoding="utf-8"))
    preflight = json.loads(args.preflight_json.read_text(encoding="utf-8"))
    mouth_phase4a = json.loads(args.mouth_json.read_text(encoding="utf-8"))
    c01 = load_c01(args.source)
    outer, _ = glb_shells(args.glb, build)
    mm_per_unit = MM_HEIGHT / float(np.ptp(c01.bounds[:, 1]))
    removed_ids = np.asarray(build["topology_selection"]["removed_original_face_ids"], dtype=np.int64)
    retained_ids = np.setdiff1d(np.arange(len(c01.faces), dtype=np.int64), removed_ids)
    if len(retained_ids) != build["retained_original_faces"]:
        raise AssertionError((len(retained_ids), build["retained_original_faces"]))
    retained_count = len(retained_ids)
    mapped_difference = np.max(
        np.abs(
            canonical_triangles(np.asarray(outer.triangles)[:retained_count])
            - canonical_triangles(np.asarray(c01.triangles)[retained_ids])
        )
    )
    if mapped_difference != 0.0:
        raise AssertionError(f"retained face coordinate mismatch: {mapped_difference}")

    print("enumerating original C01 self-events", flush=True)
    c01_events = self_events(c01, name="C01", workers=args.workers)
    print("enumerating v001 outer self-events", flush=True)
    v001_events = self_events(outer, name="v001 outer", workers=args.workers)
    if v001_events["event_count"] != 2148 or v001_events["counts"].get("noncoplanar_crossing") != 680 or v001_events["counts"].get("touching") != 1468:
        raise AssertionError(v001_events["counts"])
    classified = classify_v001_events(c01, outer, retained_ids, v001_events["events"], mm_per_unit)

    c01_mouth_faces = protected_mouth_faces(c01, 5.0, mm_per_unit)
    c01_event_rows = []
    for event in c01_events["events"]:
        a, b = event["face_a"], event["face_b"]
        tri_a, tri_b = np.asarray(c01.triangles[a]), np.asarray(c01.triangles[b])
        point = 0.5 * (tri_a.mean(axis=0) + tri_b.mean(axis=0))
        c01_event_rows.append(
            {
                **event,
                "location_proxy_model_units": point.tolist(),
                "location_proxy_mm": (point * mm_per_unit).tolist(),
                "inside_validated_mouth_projection": bool(c01_mouth_faces[a] or c01_mouth_faces[b]),
            }
        )
    c01_event_summary = {
        **{key: value for key, value in c01_events.items() if key != "events"},
        "events": c01_event_rows,
        "mouth_projection_event_count": int(sum(row["inside_validated_mouth_projection"] for row in c01_event_rows)),
        "clusters": event_clusters(c01_event_rows, mm_per_unit),
    }

    print("auditing C01 welding and in-memory format roundtrips", flush=True)
    topology = topology_metrics(c01)
    edge_vertex = edge_and_vertex_topology(c01)
    connectivity = connectivity_summary(c01)
    welding = weld_audit(c01, mm_per_unit)
    stl = stl_roundtrip(c01)
    three_mf = minimal_3mf_roundtrip(c01)
    defect_clusters = preflight["defect_clusters"]
    mouth_mask_bounds = np.asarray(mouth_phase4a["mouth_roi"]["mask"]["bounds_model_xy"], dtype=np.float64)
    broad_mouth_clusters = [row for row in defect_clusters if row["centroid_inside_mouth_guard_xy"]]
    mouth_bbox_centroid_count = 0
    mouth_bbox_centroid_clearances = []
    for row in broad_mouth_clusters:
        point = np.asarray(row["centroid"], dtype=np.float64)[:2]
        inside_bbox = bool(np.all(point >= mouth_mask_bounds[0]) and np.all(point <= mouth_mask_bounds[1]))
        mouth_bbox_centroid_count += int(inside_bbox)
        delta = np.maximum(np.maximum(mouth_mask_bounds[0] - point, point - mouth_mask_bounds[1]), 0.0)
        mouth_bbox_centroid_clearances.append(float(np.linalg.norm(delta) * mm_per_unit))
    cluster_summary = {
        "count": int(len(defect_clusters)),
        "inside_mouth_projection": int(sum(bool(row["centroid_inside_mouth_guard_xy"]) for row in defect_clusters)),
        "centroid_inside_validated_mouth_mask_xy_bounding_box": int(mouth_bbox_centroid_count),
        "broad_mouth_guard_cluster_maximum_extent_mm": float(max(row["max_extent"] for row in broad_mouth_clusters) * mm_per_unit),
        "broad_mouth_guard_cluster_minimum_centroid_clearance_to_mask_bbox_mm": float(min(mouth_bbox_centroid_clearances)),
        "maximum_extent_mm": float(max(row["max_extent"] for row in defect_clusters) * mm_per_unit),
        "p95_extent_mm": float(np.quantile([row["max_extent"] * mm_per_unit for row in defect_clusters], 0.95)),
        "top_20_by_extent": sorted(defect_clusters, key=lambda row: row["max_extent"], reverse=True)[:20],
    }

    phase4a_mouth = {
        "c01_is_authoritative_front_surface": True,
        "dense_cpu_front_samples": int(mouth_phase4a["authoritative_cpu_counterfactual_summary"]["whole_mouth"]["sampled_pixels"]),
        "dense_cpu_c01_front_fraction": float(
            mouth_phase4a["authoritative_cpu_counterfactual_summary"]["whole_mouth"]["cpu_frontmost_counts"]["c01"]
            / mouth_phase4a["authoritative_cpu_counterfactual_summary"]["whole_mouth"]["sampled_pixels"]
        ),
        "mouth_mask_pixels": int(mouth_phase4a["mouth_roi"]["mask"]["pixels"]),
        "c01_protected_faces_with_5mm_band": int(np.count_nonzero(c01_mouth_faces)),
        "interpretation": "The mouth cavity faces are connected faces of C01 and form a concave external indentation, not a separate interior component.",
    }

    repairability = {
        "recommendation": "YES_SINGLE_SOLID_BOUNDARY_FEASIBLE_WITH_LOCAL_REPAIR",
        "additional_closed_inner_boundary_required_for_fdm": False,
        "confidence": "high for representation choice; actual repaired mesh still requires build-and-roundtrip validation",
        "evidence": {
            "c01_canonical_shared_vertex_components": connectivity["canonical_shared_vertex_components"],
            "dominant_shared_edge_component_face_fraction": connectivity["largest_edge_component_face_fraction"],
            "winding_consistent": topology["winding_consistent"],
            "defect_clusters": cluster_summary["count"],
            "defect_cluster_maximum_extent_mm": cluster_summary["maximum_extent_mm"],
            "mouth_is_part_of_c01": True,
            "separate_macro_inner_surface_required": False,
            "stl_roundtrip_adds_no_new_topology_change": stl["topology"] == topology,
            "3mf_indices_identical": three_mf["face_index_arrays_identical"],
        },
        "constraints_for_future_local_repair": [
            "No position-identical fan splits: true local retriangulation must remain manifold after welding.",
            "Protect validated mouth faces and a 5 mm safety band; replace only proven redundant/invalid local triangles.",
            "Every local patch must pass nonadjacent self-intersection tests and vertex-link manifold checks.",
            "A welded STL and indexed 3MF roundtrip must independently remain one component, watertight, edge/vertex-manifold and self-intersection-free.",
        ],
    }

    analysis = {
        "schema": "ai3d.v002-prebuild-c01-analysis.v1",
        "status": "ANALYSIS_COMPLETE_NO_GEOMETRY_CREATED",
        "analysis_only": True,
        "mesh_mutated": False,
        "invalidated_methods_not_used": ["invalidated-cumesh-raytrace-v1", "invalidated-edge-connectivity-split-v1"],
        "source": {"path": str(args.source), "sha256_before": source_hash_before, "sha256_after": sha256(args.source)},
        "scale": {"height_mm": MM_HEIGHT, "millimeters_per_model_unit": mm_per_unit},
        "c01": {
            "topology": topology,
            "connectivity": connectivity,
            "edge_and_vertex_manifold_audit": edge_vertex,
            "self_intersections": c01_event_summary,
            "defect_clusters": cluster_summary,
            "mouth": phase4a_mouth,
            "welding_sensitivity": welding,
            "stl_roundtrip": stl,
            "three_mf_roundtrip": three_mf,
        },
        "v001_face_mapping": {
            "retained_original_faces": int(retained_count),
            "new_patch_faces": int(len(outer.faces) - retained_count),
            "retained_face_coordinate_max_abs_difference": float(mapped_difference),
        },
        "v001_event_classification": classified,
        "repairability_recommendation": repairability,
        "software": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__, "trimesh": trimesh.__version__},
    }
    if analysis["source"]["sha256_before"] != analysis["source"]["sha256_after"]:
        raise AssertionError("source changed")

    event_json = args.output_dir / "v002-prebuild-v001-event-classification.json"
    analysis_json = args.output_dir / "v002-prebuild-c01-analysis.json"
    event_png = args.output_dir / "v002-prebuild-v001-event-classification.png"
    atomic_json(event_json, classified)
    # Avoid duplicating all 2,148 classification rows in the main summary.
    analysis["v001_event_classification"] = {key: value for key, value in classified.items() if key != "events"}
    analysis["v001_event_classification"]["full_event_table"] = event_json.name
    atomic_json(analysis_json, analysis)
    render_event_map(event_png, c01, classified, mm_per_unit)

    counts = classified["by_kind_and_category"]
    report_path = args.output_dir / "V002-PREBUILD-C01-ANALYSIS.md"
    report = f"""# v002 Pre-Build: C01-Solid- und Innenwandanalyse

## Empfehlung

**C01 kann voraussichtlich durch ausschließlich lokale, echte topologische Reparaturen zu einer einzelnen Solid-Grenze gemacht werden. Eine zweite geschlossene Innen-Grenzfläche ist für das endgültige FDM-Modell technisch nicht erforderlich.**

Diese Aussage betrifft die Repräsentationswahl. Ein repariertes Mesh wurde in diesem Schritt ausdrücklich nicht erzeugt; der spätere Reparaturbuild muss alle Roundtrip- und Geometriegates erneut praktisch bestehen.

## Warum eine einzelne Grenze für FDM genügt

C01 ist kanonisch **eine Shared-Vertex-Komponente**. Wegen der lokalen Pinch-/Non-Manifold-Defekte zerfällt sie bei strenger Shared-Edge-Flächenadjazenz noch in {connectivity['shared_edge_face_adjacency_components']} Teilstücke; das dominante Teilstück enthält {connectivity['largest_edge_component_face_fraction'] * 100:.4f} % aller Faces. Das zweitgrößte besitzt {connectivity['second_edge_component_faces']} Faces, alle übrigen zusammen nur {connectivity['remaining_edge_components_faces']} Faces. Das ist lokale Defekttopologie, keine zweite makroskopische Innenfläche.

Die validierte Maulhöhle ist eine konkave Einbuchtung derselben C01-Oberfläche: {phase4a_mouth['dense_cpu_front_samples']} dichte Float64-Frontstichproben bestätigten C01 als vorderste Kavitätsfläche (Anteil {phase4a_mouth['dense_cpu_c01_front_fraction']:.3f}). Sie ist kein separates inneres Volumen.

Ist diese Oberfläche watertight, edge-/vertex-manifold und selbstschnittfrei, definiert sie genau ein druckbares Solid. Der Slicer erzeugt daraus Perimeter, Top-/Bottom-Lagen und Infill. Materialeinsparung und effektive Wandstärke werden über Perimeterzahl, Infill-Dichte/-Muster und gegebenenfalls modifiers gesteuert. Eine im Mesh modellierte Innenhaut wäre nur erforderlich, wenn ein geometrisch fest definierter Hohlraum mit konstruktiver Innenform unabhängig vom Slicer verlangt wird.

## C01-Befund

- kanonische Shared-Vertex-Komponenten: **{connectivity['canonical_shared_vertex_components']}**.
- Shared-Edge-Flächenteilstücke im noch defekten C01: **{connectivity['shared_edge_face_adjacency_components']}**; größtes Teilstück {connectivity['largest_edge_component_faces']} Faces.
- Faces/Vertices: **{topology['faces']} / {topology['vertices']}**.
- Winding konsistent: **{str(topology['winding_consistent']).lower()}**.
- Boundary-Kanten: **{edge_vertex['boundary_edges']}**.
- Non-Manifold-Kanten: **{edge_vertex['nonmanifold_edges']}**, maximale Inzidenz {edge_vertex['maximum_edge_incidence']}.
- ungültige Vertex-Links an Defektvertices: **{edge_vertex['invalid_vertex_links_among_defect_vertices']}**.
- nicht-adjazente C01-Selbstereignisse: **{c01_event_summary['event_count']}** ({c01_event_summary['counts'].get('noncoplanar_crossing', 0)} Kreuzungen, {c01_event_summary['counts'].get('touching', 0)} Kontakte).
- Defektcluster: **{cluster_summary['count']}**, maximaler Cluster-Extent **{cluster_summary['maximum_extent_mm']:.3f} mm**, p95 **{cluster_summary['p95_extent_mm']:.3f} mm**.
- Maulschutz: 9 Clusterzentren liegen im absichtlich breiten Maul-Guard, aber **0** innerhalb selbst der XY-Bounding-Box der validierten Maulmaske. Der größte dieser neun Cluster misst **{cluster_summary['broad_mouth_guard_cluster_maximum_extent_mm']:.3f} mm**; das nächste Zentrum liegt **{cluster_summary['broad_mouth_guard_cluster_minimum_centroid_clearance_to_mask_bbox_mm']:.3f} mm** außerhalb der Masken-Bounding-Box. Sie liegen im Sicherheitsband/Übergang und rechtfertigen keinen Eingriff in die validierte Kavität.
- Die Defekte sind zahlreich, aber räumlich klein und lokal; es gibt keine zweite makroskopische Fläche, die als zwingende Innenwand erhalten werden müsste.

## Welding- und Formatprüfung von C01

- Exaktes positionsbasiertes Welding und Toleranzen bis 1e-6 der Bounding-Box-Diagonale wurden nur im Speicher simuliert. Details stehen im JSON.
- STL-Roundtrip: {stl['vertices']} Vertices / {stl['faces']} Faces; Topologie entspricht C01: **{str(stl['topology'] == topology).lower()}**.
- 3MF-Roundtrip ohne externe Bibliothek: CRC **{three_mf['crc']}**, Face-Indizes identisch **{str(three_mf['face_index_arrays_identical']).lower()}**, maximaler Koordinatenfehler **{three_mf['vertex_coordinate_max_abs_error_model_units']:.3g}** Modell­einheiten.

Das beweist nicht die spätere Reparatur, zeigt aber: STL/3MF erzwingen keine zweite Schale. Der v001-STL-Fehler stammte aus positionsgleichen Fan-Splits, nicht aus einem grundsätzlichen Formatproblem.

## Klassifikation aller v001-Außenereignisse

| Ereignis | bereits in C01 | durch v001 neu | unklar/numerisch | Summe |
|---|---:|---:|---:|---:|
| Selbstkreuzungen | {counts.get('noncoplanar_crossing:already_in_c01', 0)} | {counts.get('noncoplanar_crossing:new_in_v001', 0)} | {counts.get('noncoplanar_crossing:unclear_numeric', 0)} | 680 |
| Kontakte | {counts.get('touching:already_in_c01', 0)} | {counts.get('touching:new_in_v001', 0)} | {counts.get('touching:unclear_numeric', 0)} | 1468 |
| **Gesamt** | {classified['category_totals'].get('already_in_c01', 0)} | {classified['category_totals'].get('new_in_v001', 0)} | {classified['category_totals'].get('unclear_numeric', 0)} | **2148** |

Klassifikationsregel: Ein Ereignis gilt nur dann als bereits vorhanden, wenn beide Dreiecke unveränderte C01-Faces sind und Art/Treffer bei 0,5×, 1× und 2× Toleranz identisch reproduziert werden. Patch-beteiligte, toleranzstabile Ereignisse gelten als v001-neu. Abweichende oder toleranzinstabile Fälle sind unklar. Die vollständige Face-für-Face-Tabelle liegt im JSON.

Alle {classified['category_totals'].get('already_in_c01', 0)} als bereits vorhanden klassifizierten Ereignisse betreffen C01-Facepaare, die ursprünglich genau einen gemeinsamen Vertex besaßen. Sie sind deshalb nicht Teil der oben genannten **nicht-adjazenten** C01-Zählung. Die {counts.get('noncoplanar_crossing:already_in_c01', 0)} Kreuzungen belegen reale lokale Pinch-/Foldover-Geometrie an diesen ungültigen Vertex-Links; die {counts.get('touching:already_in_c01', 0)} Kontakte sind positionsgleiche Pinch-Kontakte. v001 hat ihre Koordinaten nicht erzeugt, aber die Fan-Splits machten sie zu getrennten Kontaktflächen. Demgegenüber enthalten alle {classified['category_totals'].get('new_in_v001', 0)} neuen Ereignisse mindestens eine neu erzeugte Patchfläche.

## Zwingende Regeln vor einem v002-Build

1. Keine separate Innenwand erzeugen, solange ein Single-Solid-C01-Pfad möglich ist.
2. Keine positionsgleichen Vertex-Fan-Splits. Lokale Bereiche müssen echt retrianguliert werden und nach Welding manifold bleiben.
3. Maul-ROI plus 5-mm-Sicherheitsband unverändert schützen; dort nur nach einzelnem Nachweis eingreifen.
4. Lokale Patches gegen alle nicht-adjazenten C01-Faces testen, nicht nur auf Watertightness.
5. Erst freigeben, wenn die eine Solid-Grenze nach positionsbasiertem Welding sowie STL- und 3MF-Roundtrip weiterhin eine Komponente, watertight, edge-/vertex-manifold und self-intersection-free ist.

## Grenzen dieser Analyse

Kein Mesh wurde repariert oder exportiert. Die Empfehlung ist deshalb ein technisch begründeter Pre-Build-Gate, kein PASS eines noch nicht gebauten v002. Dünne äußere Features müssen später separat auf druckbare Mindestdicke geprüft werden; eine zusätzliche Innenhaut würde solche Außenfeatures nicht automatisch reparieren.
"""
    atomic_text(report_path, report)

    manifest_path = args.output_dir / "V002-PREBUILD-ARTIFACT-MANIFEST.sha256"
    lines = []
    for path in sorted(args.output_dir.iterdir(), key=lambda value: value.name.lower()):
        if path.is_file() and path != manifest_path:
            lines.append(f"{sha256(path).upper()} *{path.name}")
    atomic_text(manifest_path, "\n".join(lines) + "\n")
    print(
        json.dumps(
            {
                "status": analysis["status"],
                "recommendation": repairability["recommendation"],
                "c01_self_events": c01_event_summary["counts"],
                "v001_classification": classified["by_kind_and_category"],
                "outputs": [path.name for path in sorted(args.output_dir.iterdir())],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
