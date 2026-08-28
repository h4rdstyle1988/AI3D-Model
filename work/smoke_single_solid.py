#!/usr/bin/env python3
"""Pragmatic NON-MASTER C01 single-solid voxel smoke test.

This intentionally performs a global volumetric rebuild.  It never writes to
the C01 source, v001, v002, or v003 trees.  The invalidated cuMesh ray tracer
and edge-connectivity shell splitting are not used.  cuMesh is used only for
its separately validated unsigned-distance query during deviation analysis.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import io
import json
import math
import os
import shutil
import sys
import time
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import colors
from matplotlib.patches import Patch
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from trimesh.voxel import ops as voxel_ops
import trimesh

from outer_candidate_build_v001 import EXPECTED_SHA, load_c01
from outer_candidate_validate_v001 import UnsignedDistanceOnly, quadrature, weighted_quantile
from phase4_mouth_analysis_v2 import segment_front_mouth
from phase4_reliable_geometry import orthographic_id_depth_raster
from v002_prebuild_c01_analysis import self_events


SCHEMA = "ai3d.c01.single-solid-smoke.v1"
TARGET_HEIGHT_MM = 190.0
DEFAULT_SOURCE = Path(
    "/mnt/d/3D-Models/generated/trellis2-quality-test/"
    "phase4-analysis-seed42-2026-08-25/master-copies/"
    "trellis2-pig-print-repaired.stl"
)
VIEW_SPECS = {
    "front": (10.0, -90.0),
    "back": (10.0, 90.0),
    "left": (10.0, 180.0),
    "right": (10.0, 0.0),
    "top": (90.0, -90.0),
    "perspective": (24.0, -52.0),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def atomic_text(path: Path, payload: str) -> None:
    atomic_bytes(path, payload.encode("utf-8"))


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def atomic_npz(path: Path, *, vertices: np.ndarray, faces: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp.npz")
    np.savez_compressed(temporary, vertices=vertices, faces=faces)
    os.replace(temporary, path)


def bounds_record(mesh: trimesh.Trimesh) -> dict[str, Any]:
    bounds = np.asarray(mesh.bounds, dtype=np.float64)
    return {
        "minimum_mm": bounds[0].tolist(),
        "maximum_mm": bounds[1].tolist(),
        "extents_mm": np.ptp(bounds, axis=0).tolist(),
        "center_mm": np.mean(bounds, axis=0).tolist(),
        "diagonal_mm": float(np.linalg.norm(np.ptp(bounds, axis=0))),
    }


def expected_grid(extents: np.ndarray, pitch: float, padding: int = 2) -> dict[str, Any]:
    shape = np.ceil(np.asarray(extents, dtype=np.float64) / pitch).astype(np.int64) + 1 + 2 * padding
    voxels = int(np.prod(shape, dtype=np.int64))
    return {
        "pitch_mm": float(pitch),
        "estimated_shape_with_two_voxel_padding": shape.tolist(),
        "estimated_voxels": voxels,
        "bool_mib": voxels / (1024.0**2),
        "float32_mib": 4.0 * voxels / (1024.0**2),
    }


def load_scaled_c01(source: Path) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    source_hash = sha256(source)
    if source_hash.lower() != EXPECTED_SHA.lower():
        raise RuntimeError(f"C01 source hash mismatch: {source_hash}")
    mesh = load_c01(source)
    raw_bounds = np.asarray(mesh.bounds, dtype=np.float64)
    source_height = float(np.ptp(raw_bounds, axis=0)[1])
    scale = TARGET_HEIGHT_MM / source_height
    mesh.vertices = np.asarray(mesh.vertices, dtype=np.float64) * scale
    return mesh, {
        "source_path": str(source),
        "source_sha256": source_hash,
        "source_full_stl_contains_19_components": True,
        "selected_geometry": "C01 largest canonical shared-vertex component only",
        "c01_vertices": int(len(mesh.vertices)),
        "c01_faces": int(len(mesh.faces)),
        "original_normalized_bounds": raw_bounds.tolist(),
        "explicit_unit_conversion": "normalized TRELLIS source units to intended millimeters",
        "target_height_mm": TARGET_HEIGHT_MM,
        "millimeters_per_source_unit": scale,
        "orientation": "unchanged; X/Y/Z retained; no mirroring or axis swap",
        "position": "scaled about source origin only; no recentering",
        "bounds_mm": bounds_record(mesh),
    }


def _face_components(faces: np.ndarray, edge_inverse: np.ndarray, edge_counts: np.ndarray) -> int:
    face_ids = np.tile(np.arange(len(faces), dtype=np.int64), 3)
    order = np.argsort(edge_inverse, kind="mergesort")
    starts = np.r_[0, np.cumsum(edge_counts)[:-1]]
    manifold = np.flatnonzero(edge_counts == 2)
    left = face_ids[order[starts[manifold]]]
    right = face_ids[order[starts[manifold] + 1]]
    rows = np.r_[left, right]
    cols = np.r_[right, left]
    graph = coo_matrix(
        (np.ones(len(rows), dtype=np.uint8), (rows, cols)),
        shape=(len(faces), len(faces)),
    ).tocsr()
    count, _ = connected_components(graph, directed=False)
    return int(count)


def _shared_vertex_components(vertex_count: int, faces: np.ndarray) -> int:
    a, b, c = faces.T
    rows = np.r_[a, b, b, c, c, a]
    cols = np.r_[b, a, c, b, a, c]
    graph = coo_matrix(
        (np.ones(len(rows), dtype=np.uint8), (rows, cols)),
        shape=(vertex_count, vertex_count),
    ).tocsr()
    count, labels = connected_components(graph, directed=False)
    used = np.unique(faces)
    return int(len(np.unique(labels[used]))) if len(used) else int(count)


def _invalid_vertex_links(vertex_count: int, faces: np.ndarray) -> tuple[int, list[dict[str, Any]]]:
    # Each triangle contributes one opposite link edge at each corner.
    centers = np.concatenate((faces[:, 0], faces[:, 1], faces[:, 2]))
    links = np.vstack((faces[:, [1, 2]], faces[:, [2, 0]], faces[:, [0, 1]]))
    order = np.argsort(centers, kind="mergesort")
    centers = centers[order]
    links = links[order]
    starts = np.r_[0, np.flatnonzero(np.diff(centers)) + 1]
    stops = np.r_[starts[1:], len(centers)]
    invalid = 0
    examples: list[dict[str, Any]] = []
    for start, stop in zip(starts.tolist(), stops.tolist()):
        vertex = int(centers[start])
        local = links[start:stop]
        neighbors, inverse = np.unique(local, return_inverse=True)
        local_edges = inverse.reshape((-1, 2))
        degree = np.bincount(local_edges.reshape(-1), minlength=len(neighbors))
        parent = np.arange(len(neighbors), dtype=np.int64)

        def find(value: int) -> int:
            while parent[value] != value:
                parent[value] = parent[parent[value]]
                value = int(parent[value])
            return value

        for left, right in local_edges.tolist():
            root_left, root_right = find(int(left)), find(int(right))
            if root_left != root_right:
                parent[root_right] = root_left
        components = len({find(index) for index in range(len(neighbors))})
        okay = components == 1 and bool(np.all(degree == 2))
        if not okay:
            invalid += 1
            if len(examples) < 100:
                examples.append(
                    {
                        "vertex": vertex,
                        "incident_faces": int(stop - start),
                        "link_vertices": int(len(neighbors)),
                        "link_components": int(components),
                        "link_degree_min": int(degree.min(initial=0)),
                        "link_degree_max": int(degree.max(initial=0)),
                    }
                )
    unused = vertex_count - len(starts)
    return invalid + max(0, unused), examples


def topology(mesh: trimesh.Trimesh) -> dict[str, Any]:
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    directed = np.vstack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    edge_keys = np.sort(directed, axis=1)
    unique_edges, edge_inverse, edge_counts = np.unique(
        edge_keys, axis=0, return_inverse=True, return_counts=True
    )
    repeated_indices = (
        (faces[:, 0] == faces[:, 1])
        | (faces[:, 1] == faces[:, 2])
        | (faces[:, 2] == faces[:, 0])
    )
    triangles = vertices[faces]
    double_area = np.linalg.norm(
        np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), axis=1
    )
    diagonal = float(np.linalg.norm(np.ptp(vertices, axis=0)))
    area_tolerance = max(np.finfo(np.float64).eps, diagonal * diagonal * 1e-24)
    canonical = np.sort(faces, axis=1)
    duplicate_faces = int(len(canonical) - len(np.unique(canonical, axis=0)))
    invalid_links, invalid_examples = _invalid_vertex_links(len(vertices), faces)
    boundary = int(np.count_nonzero(edge_counts == 1))
    nonmanifold = int(np.count_nonzero(edge_counts > 2))
    edge_components = _face_components(faces, edge_inverse, edge_counts)
    vertex_components = _shared_vertex_components(len(vertices), faces)
    normals = np.asarray(mesh.face_normals, dtype=np.float64)
    return {
        "vertices": int(len(vertices)),
        "faces": int(len(faces)),
        "shared_vertex_components": vertex_components,
        "shared_edge_components": edge_components,
        "boundary_edges": boundary,
        "nonmanifold_edges": nonmanifold,
        "maximum_edge_incidence": int(edge_counts.max(initial=0)),
        "edge_manifold_closed": boundary == 0 and nonmanifold == 0,
        "invalid_vertex_links": int(invalid_links),
        "vertex_manifold": int(invalid_links) == 0,
        "invalid_vertex_link_examples": invalid_examples,
        "duplicate_faces_unoriented": duplicate_faces,
        "repeated_index_faces": int(np.count_nonzero(repeated_indices)),
        "zero_area_faces": int(np.count_nonzero(double_area <= area_tolerance)),
        "finite_vertices": bool(np.all(np.isfinite(vertices))),
        "finite_face_normals": bool(np.all(np.isfinite(normals))),
        "zero_length_face_normals": int(np.count_nonzero(np.linalg.norm(normals, axis=1) <= 1e-12)),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "watertight": bool(mesh.is_watertight),
        "is_volume": bool(mesh.is_volume),
        "euler_number": int(mesh.euler_number),
        "signed_volume_mm3": float(mesh.volume),
        "surface_area_mm2": float(mesh.area),
        "bounds": bounds_record(mesh),
    }


def topology_gate(metrics: dict[str, Any], events: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "one_shared_vertex_component": metrics["shared_vertex_components"] == 1,
        "one_shared_edge_component": metrics["shared_edge_components"] == 1,
        "zero_boundary_edges": metrics["boundary_edges"] == 0,
        "zero_nonmanifold_edges": metrics["nonmanifold_edges"] == 0,
        "zero_invalid_vertex_links": metrics["invalid_vertex_links"] == 0,
        "zero_duplicate_faces": metrics["duplicate_faces_unoriented"] == 0,
        "zero_degenerate_or_zero_area_faces": metrics["repeated_index_faces"] == 0 and metrics["zero_area_faces"] == 0,
        "finite_geometry_and_normals": metrics["finite_vertices"] and metrics["finite_face_normals"] and metrics["zero_length_face_normals"] == 0,
        "winding_consistent": metrics["winding_consistent"],
        "watertight": metrics["watertight"],
        "is_volume": metrics["is_volume"],
        "zero_nonadjacent_self_intersections_or_contacts": events["event_count"] == 0,
    }
    return {"checks": checks, "pass": all(checks.values())}


def write_3mf(mesh: trimesh.Trimesh, path: Path) -> None:
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
    atomic_bytes(path, payload.getvalue())


def load_3mf(path: Path) -> trimesh.Trimesh:
    import xml.etree.ElementTree as ET

    with zipfile.ZipFile(path, "r") as archive:
        if archive.testzip() is not None:
            raise RuntimeError(f"3MF CRC failure: {path}")
        root = ET.fromstring(archive.read("3D/3dmodel.model"))
    ns = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
    vertices = np.asarray(
        [[float(node.attrib[axis]) for axis in ("x", "y", "z")] for node in root.findall(".//m:vertices/m:vertex", ns)],
        dtype=np.float64,
    )
    faces = np.asarray(
        [[int(node.attrib[axis]) for axis in ("v1", "v2", "v3")] for node in root.findall(".//m:triangles/m:triangle", ns)],
        dtype=np.int64,
    )
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def build_variant(source: Path, output: Path, pitch: float) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    c01, source_record = load_scaled_c01(source)
    started = time.perf_counter()
    voxel_started = time.perf_counter()
    grid = c01.voxelized(pitch, method="subdivide")
    surface = np.asarray(grid.matrix, dtype=bool)
    surface_seconds = time.perf_counter() - voxel_started
    surface_labels, surface_components = ndimage.label(surface, structure=ndimage.generate_binary_structure(3, 1))
    del surface_labels
    fill_started = time.perf_counter()
    filled = ndimage.binary_fill_holes(surface)
    fill_seconds = time.perf_counter() - fill_started
    occupied_labels, occupied_components = ndimage.label(filled, structure=ndimage.generate_binary_structure(3, 1))
    if occupied_components != 1:
        counts = np.bincount(occupied_labels.ravel())
        keep = int(np.argmax(counts[1:]) + 1)
        filled = occupied_labels == keep
    del occupied_labels
    mesh_started = time.perf_counter()
    candidate = voxel_ops.matrix_to_marching_cubes(filled, pitch=pitch)
    candidate.apply_translation(np.asarray(grid.transform[:3, 3], dtype=np.float64))
    candidate.remove_unreferenced_vertices()
    if not candidate.is_winding_consistent or candidate.volume < 0:
        candidate.fix_normals(multibody=True)
    mesh_seconds = time.perf_counter() - mesh_started
    metrics = topology(candidate)
    prefix = f"C01-smoke-{int(round(pitch * 1000)):04d}um-NON-MASTER"
    npz_path = output / f"{prefix}-working-mesh.npz"
    stl_path = output / f"{prefix}.stl"
    three_mf_path = output / f"{prefix}.3mf"
    atomic_npz(npz_path, vertices=np.asarray(candidate.vertices, dtype=np.float64), faces=np.asarray(candidate.faces, dtype=np.int64))
    atomic_bytes(stl_path, candidate.export(file_type="stl"))
    write_3mf(candidate, three_mf_path)
    report = {
        "schema": SCHEMA,
        "status": "BUILT_NOT_YET_VALIDATED",
        "classification": "SMOKE-TEST / NON-MASTER",
        "backend": {
            "surface_voxelization": "trimesh.voxelized(method='subdivide')",
            "inside_outside": "scipy.ndimage.binary_fill_holes on a connected rasterized surface barrier",
            "surface_extraction": "trimesh.voxel.ops.matrix_to_marching_cubes (skimage marching cubes), no smoothing",
            "morphological_closing_or_dilation": False,
            "separate_inner_shell": False,
            "invalidated_methods_not_used": ["invalidated-cumesh-raytrace-v1", "invalidated-edge-connectivity-split-v1"],
        },
        "source": source_record,
        "parameters": {
            "pitch_mm": float(pitch),
            "target_height_mm": TARGET_HEIGHT_MM,
            "smoothing": "none",
            "simplification": "none",
            "surface_connectivity": 6,
            "occupancy_connectivity": 6,
        },
        "voxel_grid": {
            "shape": list(surface.shape),
            "total_voxels": int(surface.size),
            "surface_voxels": int(surface.sum()),
            "surface_components_before_fill": int(surface_components),
            "filled_voxels": int(filled.sum()),
            "new_interior_voxels": int(filled.sum() - surface.sum()),
            "occupied_components_before_largest_filter": int(occupied_components),
            "largest_component_filter_used": bool(occupied_components != 1),
            "transform": np.asarray(grid.transform, dtype=np.float64).tolist(),
        },
        "working_mesh_topology_before_export": metrics,
        "timings_seconds": {
            "surface_voxelization": surface_seconds,
            "binary_fill": fill_seconds,
            "marching_cubes_and_normal_orientation": mesh_seconds,
            "total_build_and_export": time.perf_counter() - started,
        },
        "artifacts": {
            "working_npz": {"path": str(npz_path), "sha256": sha256(npz_path), "bytes": npz_path.stat().st_size},
            "stl": {"path": str(stl_path), "sha256": sha256(stl_path), "bytes": stl_path.stat().st_size},
            "3mf": {"path": str(three_mf_path), "sha256": sha256(three_mf_path), "bytes": three_mf_path.stat().st_size},
        },
    }
    atomic_json(output / f"{prefix}-build.json", report)
    return report


def load_working_npz(path: Path) -> trimesh.Trimesh:
    with np.load(path) as payload:
        vertices = np.asarray(payload["vertices"], dtype=np.float64)
        faces = np.asarray(payload["faces"], dtype=np.int64)
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def deviation_direction(source: trimesh.Trimesh, target: trimesh.Trimesh) -> tuple[dict[str, Any], np.ndarray]:
    query = UnsignedDistanceOnly(target, batch_size=65536)
    points, weights = quadrature(source)
    distances = query.query(points).astype(np.float64)
    vertices = np.asarray(source.vertices, dtype=np.float32)
    vertex_distances = query.query(vertices).astype(np.float64)
    maximum_values = np.r_[distances, vertex_distances]
    maximum_index = int(np.argmax(maximum_values))
    if maximum_index < len(points):
        maximum_location = points[maximum_index]
        maximum_kind = "face quadrature"
    else:
        maximum_location = vertices[maximum_index - len(points)]
        maximum_kind = "vertex"
    sample_ids = np.linspace(0, len(points) - 1, min(8, len(points)), dtype=np.int64)
    cpu_errors = []
    for sample_id in sample_ids.tolist():
        _, cpu_distance, _ = trimesh.proximity.closest_point_naive(target, points[sample_id : sample_id + 1].astype(np.float64))
        cpu_errors.append(abs(float(cpu_distance[0]) - float(distances[sample_id])))
    result = {
        "sampling": "all vertices plus three deterministic area-weighted quadrature points per face",
        "quadrature_samples": int(len(points)),
        "vertex_samples": int(len(vertices)),
        "area_weighted_median_mm": weighted_quantile(distances, weights, 0.50),
        "area_weighted_p95_mm": weighted_quantile(distances, weights, 0.95),
        "area_weighted_p99_mm": weighted_quantile(distances, weights, 0.99),
        "sampled_maximum_mm": float(maximum_values[maximum_index]),
        "sampled_maximum_location_mm": np.asarray(maximum_location, dtype=np.float64).tolist(),
        "sampled_maximum_location_kind": maximum_kind,
        "area_fraction_above_mm": {
            str(threshold): float(np.sum(weights[distances > threshold]) / np.sum(weights))
            for threshold in (0.25, 0.5, 1.0, 2.0)
        },
        "cpu_naive_spotcheck": {
            "samples": int(len(cpu_errors)),
            "maximum_abs_error_mm": max(cpu_errors, default=0.0),
            "status": "PASS" if max(cpu_errors, default=0.0) <= 0.02 else "FAIL",
        },
        "backend": "cuMesh unsigned_distance only; ray_trace is not called",
    }
    # One face scalar for visual heatmaps: maximum of its 3 quadrature points.
    face_values = distances.reshape((-1, 3)).max(axis=1)
    del query
    gc.collect()
    return result, face_values


def mouth_report(mesh: trimesh.Trimesh, resolution: int = 1024) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    raster = orthographic_id_depth_raster(
        np.asarray(mesh.vertices, dtype=np.float64),
        np.asarray(mesh.faces, dtype=np.int64),
        view="+z",
        resolution=resolution,
        padding=0.04,
        validation_samples=64,
    )
    masks, segmentation = segment_front_mouth(raster, np.asarray(mesh.bounds), mm_per_unit=1.0)
    mask = masks["mouth_mask"]
    interior = masks["interior"]
    transition = masks["body_transition"]
    depth = raster.depth_model
    pixels_per_mm = float(raster.metadata["pixels_per_model_unit"])
    mouth_depth = depth[interior]
    transition_depth = depth[transition]
    report = {
        "segmentation": segmentation,
        "raster_metadata": raster.metadata,
        "opening_area_mm2_projected": float(np.count_nonzero(mask) / (pixels_per_mm**2)),
        "opening_bounds_xy_mm": segmentation["mask"]["bounds_model_xy"],
        "opening_width_height_mm": (
            np.ptp(np.asarray(segmentation["mask"]["bounds_model_xy"], dtype=np.float64), axis=0).tolist()
        ),
        "interior_depth_z_mm": {
            "minimum": float(np.min(mouth_depth)),
            "median": float(np.median(mouth_depth)),
            "maximum": float(np.max(mouth_depth)),
            "range": float(np.ptp(mouth_depth)),
        },
        "rim_transition_minus_interior_median_depth_mm": float(np.median(transition_depth) - np.median(mouth_depth)),
        "subregions_nonempty": all(segmentation["subregions"][name]["pixels"] > 0 for name in ("mouth_rim", "side_walls", "floor", "back_wall", "body_transition")),
        "opening_detected": bool(np.count_nonzero(mask) > 100 and np.ptp(mouth_depth) > 2.0),
        "membrane_test": "PASS" if np.median(transition_depth) - np.median(mouth_depth) > 3.0 else "FAIL",
    }
    return report, depth, mask


def _render_mesh(mesh: trimesh.Trimesh, path: Path, view: str, title: str, max_faces: int = 130000) -> None:
    faces = np.asarray(mesh.faces, dtype=np.int64)
    if len(faces) > max_faces:
        ids = np.linspace(0, len(faces) - 1, max_faces, dtype=np.int64)
        triangles = np.asarray(mesh.triangles, dtype=np.float64)[ids]
        normals = np.asarray(mesh.face_normals, dtype=np.float64)[ids]
    else:
        triangles = np.asarray(mesh.triangles, dtype=np.float64)
        normals = np.asarray(mesh.face_normals, dtype=np.float64)
    light = np.array([0.35, -0.45, 0.82], dtype=np.float64)
    light /= np.linalg.norm(light)
    shade = np.clip(0.30 + 0.70 * np.abs(normals @ light), 0.0, 1.0)
    face_colors = plt.get_cmap("Blues")(0.30 + 0.55 * shade)
    fig = plt.figure(figsize=(7.2, 7.2), dpi=150, facecolor="#eef1f4")
    ax = fig.add_subplot(111, projection="3d", facecolor="#eef1f4")
    ax.add_collection3d(Poly3DCollection(triangles, facecolors=face_colors, edgecolors="none", rasterized=True))
    bounds = np.asarray(mesh.bounds, dtype=np.float64)
    center = np.mean(bounds, axis=0)
    radius = float(np.max(np.ptp(bounds, axis=0))) * 0.58
    ax.set_xlim(center[0] - radius, center[0] + radius)
    ax.set_ylim(center[1] - radius, center[1] + radius)
    ax.set_zlim(center[2] - radius, center[2] + radius)
    ax.set_box_aspect((1, 1, 1))
    elev, azim = VIEW_SPECS[view]
    ax.view_init(elev=elev, azim=azim)
    ax.set_proj_type("ortho" if view != "perspective" else "persp")
    ax.set_axis_off()
    fig.subplots_adjust(0, 0, 1, 1)
    fig.text(0.025, 0.97, title, ha="left", va="top", fontsize=10, color="#111827", bbox={"facecolor": (1, 1, 1, 0.78), "edgecolor": "none", "pad": 4})
    fig.savefig(path, facecolor="#eef1f4")
    plt.close(fig)


def _render_heatmap(mesh: trimesh.Trimesh, face_values: np.ndarray, path: Path, title: str, max_faces: int = 180000) -> None:
    faces = np.asarray(mesh.faces, dtype=np.int64)
    if len(faces) > max_faces:
        ids = np.linspace(0, len(faces) - 1, max_faces, dtype=np.int64)
    else:
        ids = np.arange(len(faces), dtype=np.int64)
    triangles = np.asarray(mesh.triangles, dtype=np.float64)[ids]
    values = np.asarray(face_values, dtype=np.float64)[ids]
    cap = max(0.5, float(np.quantile(face_values, 0.99)))
    norm = colors.Normalize(vmin=0.0, vmax=cap, clip=True)
    cmap = plt.get_cmap("inferno")
    fig = plt.figure(figsize=(8.0, 7.2), dpi=150, facecolor="#eef1f4")
    ax = fig.add_subplot(111, projection="3d", facecolor="#eef1f4")
    ax.add_collection3d(Poly3DCollection(triangles, facecolors=cmap(norm(values)), edgecolors="none", rasterized=True))
    bounds = np.asarray(mesh.bounds)
    center = np.mean(bounds, axis=0)
    radius = float(np.max(np.ptp(bounds, axis=0))) * 0.58
    ax.set_xlim(center[0] - radius, center[0] + radius)
    ax.set_ylim(center[1] - radius, center[1] + radius)
    ax.set_zlim(center[2] - radius, center[2] + radius)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=24, azim=-52)
    ax.set_axis_off()
    fig.subplots_adjust(0, 0, 0.90, 1)
    fig.text(0.025, 0.97, title, ha="left", va="top", fontsize=10, color="#111827", bbox={"facecolor": (1, 1, 1, 0.78), "edgecolor": "none", "pad": 4})
    scalar = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    cbar = fig.colorbar(scalar, ax=ax, fraction=0.04, pad=0.02)
    cbar.set_label(f"unsigned distance to C01 (mm), clipped at p99={cap:.3f}")
    fig.savefig(path, facecolor="#eef1f4")
    plt.close(fig)


def _render_mouth_comparison(source_depth: np.ndarray, source_mask: np.ndarray, candidate_depth: np.ndarray, candidate_mask: np.ndarray, path: Path, title: str) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2), dpi=150, facecolor="#eef1f4")
    finite = np.r_[source_depth[np.isfinite(source_depth)], candidate_depth[np.isfinite(candidate_depth)]]
    vmin, vmax = np.quantile(finite, [0.02, 0.98])
    for axis, depth, mask, label in zip(axes, (source_depth, candidate_depth), (source_mask, candidate_mask), ("C01 BEFORE", "VOXEL SOLID AFTER")):
        image = axis.imshow(depth, origin="lower", cmap="viridis", vmin=vmin, vmax=vmax)
        axis.contour(mask.astype(float), levels=[0.5], colors=["#ff3b30"], linewidths=1.1)
        rows, columns = np.nonzero(mask)
        if len(rows):
            pad = 28
            axis.set_xlim(max(0, columns.min() - pad), min(depth.shape[1], columns.max() + pad))
            axis.set_ylim(max(0, rows.min() - pad), min(depth.shape[0], rows.max() + pad))
        axis.set_title(label)
        axis.set_axis_off()
    cbar = fig.colorbar(image, ax=axes.ravel().tolist(), fraction=0.025, pad=0.02)
    cbar.set_label("front +Z surface depth (mm)")
    fig.suptitle(title)
    fig.savefig(path, facecolor="#eef1f4", bbox_inches="tight")
    plt.close(fig)


def validate_variant(source: Path, variant: Path, workers: int) -> dict[str, Any]:
    build_json = next(variant.glob("*-build.json"))
    build = json.loads(build_json.read_text(encoding="utf-8"))
    prefix = build_json.name[: -len("-build.json")]
    working_path = Path(build["artifacts"]["working_npz"]["path"])
    stl_path = Path(build["artifacts"]["stl"]["path"])
    three_mf_path = Path(build["artifacts"]["3mf"]["path"])
    for artifact_name, artifact_path in (("working NPZ", working_path), ("STL", stl_path), ("3MF", three_mf_path)):
        if not artifact_path.is_file():
            raise FileNotFoundError(f"{artifact_name}: {artifact_path}")
    source_mesh, source_record = load_scaled_c01(source)
    meshes = {
        "working": load_working_npz(working_path),
        "stl_roundtrip": trimesh.load(stl_path, force="mesh", process=True),
        "3mf_roundtrip": load_3mf(three_mf_path),
    }
    validations: dict[str, Any] = {}
    for name, mesh in meshes.items():
        print(f"[{prefix}] topology: {name}", flush=True)
        metrics = topology(mesh)
        print(f"[{prefix}] exact nonadjacent events: {name}", flush=True)
        events = self_events(mesh, name=f"{prefix}/{name}", workers=workers, chunk_size=768, radius_bins=8)
        validations[name] = {
            "topology": metrics,
            "self_intersections_and_contacts": events,
            "gate": topology_gate(metrics, events),
            "bounds_delta_vs_working_mm": {
                "minimum": (np.asarray(mesh.bounds)[0] - np.asarray(meshes["working"].bounds)[0]).tolist(),
                "maximum": (np.asarray(mesh.bounds)[1] - np.asarray(meshes["working"].bounds)[1]).tolist(),
                "extents": (np.ptp(np.asarray(mesh.bounds), axis=0) - np.ptp(np.asarray(meshes["working"].bounds), axis=0)).tolist(),
            },
        }
    print(f"[{prefix}] bidirectional unsigned surface distance", flush=True)
    source_to_candidate, source_face_values = deviation_direction(source_mesh, meshes["working"])
    candidate_to_source, candidate_face_values = deviation_direction(meshes["working"], source_mesh)
    pooled = {
        "approximate_hausdorff_sampled_mm": max(source_to_candidate["sampled_maximum_mm"], candidate_to_source["sampled_maximum_mm"]),
        "note": "Maximum over all vertices and deterministic three-point face quadrature in both directions; sampled, not a certified continuous Hausdorff bound.",
    }
    print(f"[{prefix}] mouth rasters and segmentation", flush=True)
    source_mouth, source_depth, source_mask = mouth_report(source_mesh)
    candidate_mouth, candidate_depth, candidate_mask = mouth_report(meshes["working"])
    mouth_ratios = {
        "opening_area_ratio_candidate_to_c01": candidate_mouth["opening_area_mm2_projected"] / source_mouth["opening_area_mm2_projected"],
        "width_ratio_candidate_to_c01": candidate_mouth["opening_width_height_mm"][0] / source_mouth["opening_width_height_mm"][0],
        "height_ratio_candidate_to_c01": candidate_mouth["opening_width_height_mm"][1] / source_mouth["opening_width_height_mm"][1],
        "depth_contrast_ratio_candidate_to_c01": candidate_mouth["rim_transition_minus_interior_median_depth_mm"] / source_mouth["rim_transition_minus_interior_median_depth_mm"],
    }
    mouth_checks = {
        "opening_detected": candidate_mouth["opening_detected"],
        "no_front_membrane": candidate_mouth["membrane_test"] == "PASS",
        "all_cavity_subregions_detected": candidate_mouth["subregions_nonempty"],
        "projected_opening_area_at_least_70_percent_of_c01": mouth_ratios["opening_area_ratio_candidate_to_c01"] >= 0.70,
        "mouth_width_at_least_80_percent_of_c01": mouth_ratios["width_ratio_candidate_to_c01"] >= 0.80,
        "mouth_height_at_least_75_percent_of_c01": mouth_ratios["height_ratio_candidate_to_c01"] >= 0.75,
        "depth_contrast_at_least_70_percent_of_c01": mouth_ratios["depth_contrast_ratio_candidate_to_c01"] >= 0.70,
    }
    visual_dir = variant / "visual-comparison"
    visual_dir.mkdir(exist_ok=False)
    for name in VIEW_SPECS:
        _render_mesh(source_mesh, visual_dir / f"before-C01-{name}.png", name, f"C01 BEFORE · {name.upper()}")
        _render_mesh(meshes["working"], visual_dir / f"after-{prefix}-{name}.png", name, f"{prefix} · {name.upper()}")
    _render_heatmap(meshes["working"], candidate_face_values, visual_dir / f"{prefix}-candidate-to-C01-distance-heatmap.png", f"{prefix} · distance to C01")
    _render_mouth_comparison(source_depth, source_mask, candidate_depth, candidate_mask, visual_dir / f"{prefix}-mouth-before-after.png", f"{prefix} · mouth depth and opening")
    report = {
        "schema": SCHEMA,
        "classification": "SMOKE-TEST / NON-MASTER",
        "source": source_record,
        "build": build,
        "roundtrip_validation": validations,
        "deviation_mm": {
            "C01_to_candidate": source_to_candidate,
            "candidate_to_C01": candidate_to_source,
            "combined": pooled,
            "bounding_box_delta_candidate_minus_C01_mm": {
                "minimum": (np.asarray(meshes["working"].bounds)[0] - np.asarray(source_mesh.bounds)[0]).tolist(),
                "maximum": (np.asarray(meshes["working"].bounds)[1] - np.asarray(source_mesh.bounds)[1]).tolist(),
                "extents": (np.ptp(np.asarray(meshes["working"].bounds), axis=0) - np.ptp(np.asarray(source_mesh.bounds), axis=0)).tolist(),
                "center": (np.mean(np.asarray(meshes["working"].bounds), axis=0) - np.mean(np.asarray(source_mesh.bounds), axis=0)).tolist(),
            },
        },
        "mouth": {
            "C01": source_mouth,
            "candidate": candidate_mouth,
            "ratios": mouth_ratios,
            "checks": mouth_checks,
            "pass": all(mouth_checks.values()),
        },
        "visuals": sorted(str(path) for path in visual_dir.glob("*.png")),
        "slicer": {
            "status": "NOT_AVAILABLE",
            "audit": "No Blender, MeshLab, PrusaSlicer, OrcaSlicer, Bambu Studio, CuraEngine or other local slicer CLI was found in Windows standard paths/PATH or WSL PATH.",
            "geometric_slicability_proxy": "Internal + STL + 3MF topology gates and one positive-volume single closed solid.",
        },
    }
    report["overall_technical_pass"] = all(value["gate"]["pass"] for value in validations.values())
    report["overall_visual_mouth_pass"] = report["mouth"]["pass"]
    report["status"] = "PASS" if report["overall_technical_pass"] and report["overall_visual_mouth_pass"] else "FAIL"
    atomic_json(variant / f"{prefix}-validation.json", report)
    return report


def manifest_tree(root: Path) -> dict[str, Any]:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name not in {"ARTIFACT-MANIFEST.json", "ARTIFACT-MANIFEST.sha256"}:
            files.append({"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)})
    return {
        "schema": "ai3d.artifact-manifest.v1",
        "classification": "SMOKE-TEST / NON-MASTER",
        "root": str(root),
        "files": files,
        "file_count": len(files),
        "total_bytes": int(sum(row["bytes"] for row in files)),
    }


def finalize(root: Path) -> None:
    reports = []
    for path in sorted(root.glob("C01-smoke-*um-NON-MASTER/*-validation.json")):
        reports.append(json.loads(path.read_text(encoding="utf-8")))
    if not reports:
        raise RuntimeError("No validation reports found")
    rows = []
    for report in reports:
        pitch = report["build"]["parameters"]["pitch_mm"]
        working = report["roundtrip_validation"]["working"]
        stl = report["roundtrip_validation"]["stl_roundtrip"]
        three = report["roundtrip_validation"]["3mf_roundtrip"]
        dev = report["deviation_mm"]["candidate_to_C01"]
        rows.append(
            {
                "variant": f"{int(round(pitch * 1000))} um",
                "resolution_mm": pitch,
                "topology": "PASS" if working["gate"]["pass"] else "FAIL",
                "stl": "PASS" if stl["gate"]["pass"] else "FAIL",
                "3mf": "PASS" if three["gate"]["pass"] else "FAIL",
                "slicer": report["slicer"]["status"],
                "mouth": "PASS" if report["mouth"]["pass"] else "FAIL",
                "candidate_to_C01_median_mm": dev["area_weighted_median_mm"],
                "candidate_to_C01_p95_mm": dev["area_weighted_p95_mm"],
                "candidate_to_C01_p99_mm": dev["area_weighted_p99_mm"],
                "sampled_hausdorff_mm": report["deviation_mm"]["combined"]["approximate_hausdorff_sampled_mm"],
                "status": report["status"],
            }
        )
    final = {
        "schema": SCHEMA,
        "classification": "SMOKE-TEST / NON-MASTER",
        "variants": rows,
        "backend": reports[0]["build"]["backend"],
        "source": reports[0]["source"],
        "decision": "PENDING_VISUAL_REVIEW",
    }
    atomic_json(root / "smoke-test-summary.json", final)
    lines = [
        "# C01 Single-Solid Smoke-Test — NON-MASTER",
        "",
        "> **SMOKE-TEST / NON-MASTER.** Kein Ergebnis in diesem Verzeichnis ist ein finaler Master.",
        "",
        "## Methode",
        "",
        "Globaler Neuaufbau aus einer C01-Kopie: `trimesh.voxelized(subdivide)` → verbundenes Oberflächenraster → `scipy.ndimage.binary_fill_holes` → ungeglättetes skimage-Marching-Cubes. Keine Innenhaut, kein morphologisches Closing, keine Glättung, keine Simplification.",
        "",
        "## Vergleich",
        "",
        "| Variante | Auflösung | Topologie | STL | 3MF | Slicer | Maul | Median | p95 | p99 | sampled Hausdorff |",
        "|---|---:|---|---|---|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['variant']} | {row['resolution_mm']:.3f} mm | {row['topology']} | {row['stl']} | {row['3mf']} | {row['slicer']} | {row['mouth']} | {row['candidate_to_C01_median_mm']:.3f} mm | {row['candidate_to_C01_p95_mm']:.3f} mm | {row['candidate_to_C01_p99_mm']:.3f} mm | {row['sampled_hausdorff_mm']:.3f} mm |"
        )
    lines.extend(
        [
            "",
            "## Slicer",
            "",
            "Kein lokaler Slicer wurde gefunden. Die Slicbarkeit ist daher geometrisch, aber nicht durch einen G-Code-Lauf belegt: genau ein positiver, watertighter, edge-/vertex-manifolder Solid sowie identische Gates nach STL- und 3MF-Neuimport.",
            "",
            "## Entscheidungsstatus",
            "",
            "Die automatische Entscheidung wird erst nach Sichtprüfung der gespeicherten Before/After-Ansichten, des Maul-Depth-Vergleichs und der Distanz-Heatmap finalisiert.",
            "",
        ]
    )
    atomic_text(root / "SMOKE-TEST-REPORT.md", "\n".join(lines))
    manifest = manifest_tree(root)
    atomic_json(root / "ARTIFACT-MANIFEST.json", manifest)
    atomic_text(root / "ARTIFACT-MANIFEST.sha256", "".join(f"{row['sha256']}  {row['path']}\n" for row in manifest["files"]))


def preflight(source: Path, root: Path) -> dict[str, Any]:
    c01, source_record = load_scaled_c01(source)
    record = {
        "schema": SCHEMA,
        "classification": "SMOKE-TEST / NON-MASTER",
        "source": source_record,
        "tool_audit": {
            "selected": ["trimesh", "scipy.ndimage", "skimage marching cubes"],
            "available": ["trimesh", "scipy", "skimage", "numpy", "matplotlib"],
            "not_available": ["OpenVDB", "VTK/PyVista", "libigl", "PyMeshLab/MeshLab", "Blender", "manifold3d", "local FDM slicer CLI"],
            "installation_performed": False,
        },
        "grid_estimates": [expected_grid(np.ptp(np.asarray(c01.bounds), axis=0), pitch) for pitch in (1.0, 0.5, 0.3, 0.25)],
        "guard": {
            "root_must_not_preexist": str(root),
            "source_is_never_opened_for_writing": True,
            "previous_artifact_trees_are_not_arguments": True,
        },
    }
    return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    prepare.add_argument("--output", type=Path, required=True)
    build = sub.add_parser("build")
    build.add_argument("--source", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--pitch-mm", type=float, required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--source", type=Path, required=True)
    validate.add_argument("--variant", type=Path, required=True)
    validate.add_argument("--workers", type=int, default=4)
    finish = sub.add_parser("finalize")
    finish.add_argument("--root", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "prepare":
        if args.output.exists():
            raise FileExistsError(f"Refusing to overwrite existing smoke-test root: {args.output}")
        record = preflight(args.source, args.output)
        args.output.mkdir(parents=True)
        copy_path = args.output / "C01-source-reference-copy-58F6A915-NON-MASTER.stl"
        shutil.copy2(args.source, copy_path)
        if sha256(copy_path).lower() != EXPECTED_SHA.lower():
            raise RuntimeError("C01 working reference copy hash mismatch")
        record["source_copy"] = {"path": str(copy_path), "sha256": sha256(copy_path), "bytes": copy_path.stat().st_size}
        atomic_json(args.output / "preflight.json", record)
        print(json.dumps(record, indent=2))
    elif args.command == "build":
        report = build_variant(args.source, args.output, args.pitch_mm)
        print(json.dumps({"status": report["status"], "output": str(args.output), "topology": report["working_mesh_topology_before_export"]}, indent=2))
    elif args.command == "validate":
        report = validate_variant(args.source, args.variant, args.workers)
        print(json.dumps({"status": report["status"], "technical": report["overall_technical_pass"], "mouth": report["overall_visual_mouth_pass"]}, indent=2))
    elif args.command == "finalize":
        finalize(args.root)
        print(json.dumps({"status": "FINALIZED", "root": str(args.root)}, indent=2))


if __name__ == "__main__":
    main()
