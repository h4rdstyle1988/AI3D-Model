#!/usr/bin/env python3
"""Build outer-candidate-v001 without modifying the Seed-42 source mesh.

The visible C01 triangles are retained at their exact coordinates wherever
possible.  C02 and all tail/detail components are excluded.  A new inner wall
is derived from a voxel distance field only after the repaired C01 exterior is
closed and edge-manifold.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from skimage import measure
import trimesh

EXPECTED_SHA = "58f6a915c53b587e8e796283b1750bd0c060104a90b4616c935c6ccc70771a7d"
EXPECTED_C01_FACES = 232219
MOUTH_CENTER = np.array([1.9982457160949707e-05, 0.05411208200454712])
MOUTH_RADII = np.array([0.2846274420619011, 0.2053562557697296])


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def atomic_export(mesh: trimesh.Trimesh, path: Path, file_type: str) -> None:
    temporary = path.with_name(path.stem + ".tmp" + path.suffix)
    payload = mesh.export(file_type=file_type)
    if isinstance(payload, str):
        temporary.write_text(payload, encoding="utf-8")
    else:
        temporary.write_bytes(payload)
    temporary.replace(path)


def face_component_labels(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    a, b, c = faces.T
    rows = np.concatenate((a, b, a, c)); cols = np.concatenate((b, a, c, a))
    graph = coo_matrix((np.ones(len(rows), np.uint8), (rows, cols)), shape=(len(vertices), len(vertices))).tocsr()
    _, vertex_labels = connected_components(graph, directed=False)
    _, labels = np.unique(vertex_labels[faces[:, 0]], return_inverse=True)
    return labels.astype(np.int32)


def load_c01(path: Path) -> trimesh.Trimesh:
    loaded = trimesh.load(path, force="mesh", process=True)
    vertices = np.asarray(loaded.vertices, dtype=np.float64); faces = np.asarray(loaded.faces, dtype=np.int64)
    labels = face_component_labels(vertices, faces)
    order = sorted(range(int(labels.max()) + 1), key=lambda value: int(np.count_nonzero(labels == value)), reverse=True)
    selected = faces[np.flatnonzero(labels == order[0])]
    used, inverse = np.unique(selected.reshape(-1), return_inverse=True)
    mesh = trimesh.Trimesh(vertices=vertices[used].copy(), faces=inverse.reshape((-1, 3)), process=False)
    if len(mesh.faces) != EXPECTED_C01_FACES:
        raise AssertionError(len(mesh.faces))
    return mesh


def directed_edge_table(faces: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    directed = np.vstack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    face_ids = np.concatenate((np.arange(len(faces)), np.arange(len(faces)), np.arange(len(faces))))
    keys = np.sort(directed, axis=1)
    unique, inverse, counts = np.unique(keys, axis=0, return_inverse=True, return_counts=True)
    return directed, face_ids, unique, inverse, counts


def topology_metrics(mesh: trimesh.Trimesh) -> dict[str, Any]:
    _, _, _, _, counts = directed_edge_table(np.asarray(mesh.faces, dtype=np.int64))
    return {
        "vertices": int(len(mesh.vertices)), "faces": int(len(mesh.faces)),
        "components": int(len(mesh.split(only_watertight=False))),
        "watertight": bool(mesh.is_watertight), "winding_consistent": bool(mesh.is_winding_consistent),
        "boundary_edges": int(np.count_nonzero(counts == 1)), "nonmanifold_edges": int(np.count_nonzero(counts > 2)),
        "maximum_edge_incidence": int(counts.max()), "signed_volume": float(mesh.volume),
    }


def protected_mouth_faces(mesh: trimesh.Trimesh, safety_mm: float, mm_per_unit: float) -> np.ndarray:
    band = safety_mm / mm_per_unit
    radii = MOUTH_RADII + band
    triangle_xy = np.asarray(mesh.triangles, dtype=np.float64)[:, :, :2]
    normalized = np.sum(((triangle_xy - MOUTH_CENTER[None, None]) / radii[None, None]) ** 2, axis=2)
    return np.any(normalized <= 1.0, axis=1)


def select_manifold_subset(mesh: trimesh.Trimesh, protected: np.ndarray) -> tuple[trimesh.Trimesh, dict[str, Any], np.ndarray]:
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    initial_face_count = int(len(faces))
    original_ids = np.arange(len(faces), dtype=np.int64)
    history = []
    for iteration in range(20):
        working = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        normals = np.asarray(working.face_normals, dtype=np.float64)
        directed, face_ids, unique, inverse, counts = directed_edge_table(faces)
        bad = np.flatnonzero(counts > 2)
        if not len(bad):
            break
        order = np.argsort(inverse, kind="mergesort")
        starts = np.r_[0, np.cumsum(counts)[:-1]]
        remove = np.zeros(len(faces), dtype=bool)
        unresolved = []
        for edge_id in bad:
            occurrences = order[starts[edge_id]:starts[edge_id] + counts[edge_id]]
            incident = face_ids[occurrences]
            incident = np.unique(incident)
            protected_incident = protected[incident]
            edge = unique[edge_id]
            candidates = []
            for a_index in range(len(incident)):
                for b_index in range(a_index + 1, len(incident)):
                    a, b = int(incident[a_index]), int(incident[b_index])
                    occ_a = occurrences[face_ids[occurrences] == a][0]
                    occ_b = occurrences[face_ids[occurrences] == b][0]
                    sign_a = 1 if tuple(directed[occ_a]) == tuple(edge) else -1
                    sign_b = 1 if tuple(directed[occ_b]) == tuple(edge) else -1
                    if sign_a == sign_b:
                        continue
                    protect_score = 1000.0 * (int(protected[a]) + int(protected[b]))
                    smooth_score = float(np.dot(normals[a], normals[b]))
                    candidates.append((protect_score + smooth_score, a, b))
            if not candidates:
                unresolved.append({"edge": edge.tolist(), "reason": "no opposite-oriented face pair"})
                continue
            _, keep_a, keep_b = max(candidates, key=lambda row: (row[0], -row[1], -row[2]))
            for face_id in incident:
                if int(face_id) not in (keep_a, keep_b):
                    remove[int(face_id)] = True
        if unresolved:
            raise RuntimeError(f"protected/nonorientable nonmanifold edges: {unresolved[:10]}")
        removed = int(np.count_nonzero(remove))
        if removed == 0:
            raise RuntimeError("nonmanifold selection made no progress")
        history.append({"iteration": iteration + 1, "nonmanifold_edges_before": int(len(bad)), "faces_removed": removed})
        faces = faces[~remove]
        protected = protected[~remove]
        original_ids = original_ids[~remove]
    result = trimesh.Trimesh(vertices=vertices.copy(), faces=faces.copy(), process=False)
    return result, {"iterations": history, "removed_original_face_ids": np.setdiff1d(np.arange(initial_face_count), original_ids).tolist()}, original_ids


def removed_face_deviation(
    original: trimesh.Trimesh,
    repaired: trimesh.Trimesh,
    face_ids: np.ndarray,
    mm_per_unit: float,
) -> dict[str, Any]:
    if not len(face_ids):
        return {"faces": 0, "samples": 0, "maximum_mm": 0.0, "p95_mm": 0.0, "median_mm": 0.0}
    triangles = np.asarray(original.triangles, dtype=np.float64)[face_ids]
    barycentric = np.asarray(((1., 0., 0.), (0., 1., 0.), (0., 0., 1.), (1/3, 1/3, 1/3), (2/3, 1/6, 1/6), (1/6, 2/3, 1/6), (1/6, 1/6, 2/3)))
    points = np.einsum("qa,fac->fqc", barycentric, triangles).reshape((-1, 3))
    distances = np.empty(len(points), dtype=np.float64)
    for start in range(0, len(points), 16):
        stop = min(start + 16, len(points))
        _, values, _ = trimesh.proximity.closest_point_naive(repaired, points[start:stop])
        distances[start:stop] = values
    distances_mm = distances * mm_per_unit
    return {
        "faces": int(len(face_ids)), "samples": int(len(points)),
        "maximum_mm": float(np.max(distances_mm)), "p95_mm": float(np.quantile(distances_mm, 0.95)),
        "median_mm": float(np.median(distances_mm)),
        "sample_rule": "3 vertices + centroid + 3 deterministic quadrature points per removed face; CPU naive point-to-triangle",
    }


def boundary_loops(mesh: trimesh.Trimesh) -> list[np.ndarray]:
    faces = np.asarray(mesh.faces, dtype=np.int64)
    directed, _, _, inverse, counts = directed_edge_table(faces)
    boundary_occ = np.flatnonzero(counts[inverse] == 1)
    boundary = directed[boundary_occ]
    if not len(boundary):
        return []
    outgoing: dict[int, list[int]] = {}; incoming: dict[int, list[int]] = {}
    for start, stop in boundary:
        outgoing.setdefault(int(start), []).append(int(stop)); incoming.setdefault(int(stop), []).append(int(start))
    vertices = set(boundary.reshape(-1).tolist())
    if any(len(outgoing.get(v, [])) != 1 or len(incoming.get(v, [])) != 1 for v in vertices):
        raise RuntimeError("boundary is not a disjoint set of directed loops")
    unused = {(int(a), int(b)) for a, b in boundary}
    loops = []
    while unused:
        first = min(unused); loop = [first[0]]; current = first
        while True:
            if current not in unused:
                raise RuntimeError("boundary loop repeats unexpectedly")
            unused.remove(current); loop.append(current[1])
            if current[1] == loop[0]:
                break
            current = (current[1], outgoing[current[1]][0])
        loops.append(np.asarray(loop[:-1], dtype=np.int64))
    return loops


def split_boundary_vertex_fans(mesh: trimesh.Trimesh) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    """Duplicate only branched boundary vertices, preserving exact positions."""
    vertices = np.asarray(mesh.vertices, dtype=np.float64).tolist()
    faces = np.asarray(mesh.faces, dtype=np.int64).copy()
    iterations = []
    for iteration in range(10):
        directed, face_ids, unique, inverse, counts = directed_edge_table(faces)
        boundary = unique[counts == 1]
        degree = np.bincount(boundary.reshape(-1), minlength=len(vertices)) if len(boundary) else np.zeros(len(vertices), dtype=int)
        problematic = np.flatnonzero((degree != 0) & (degree != 2))
        if not len(problematic):
            break
        duplicates = 0
        for vertex in problematic:
            incident = np.flatnonzero(np.any(faces == vertex, axis=1))
            adjacency = {int(v): set() for v in incident}
            local_edge_faces: dict[int, list[int]] = {}
            for face_id in incident:
                face = faces[int(face_id)]
                for other in face[face != vertex]:
                    local_edge_faces.setdefault(int(other), []).append(int(face_id))
            for linked in local_edge_faces.values():
                if len(linked) == 2:
                    a, b = linked
                    adjacency[a].add(b); adjacency[b].add(a)
            components = []
            unseen = set(adjacency)
            while unseen:
                seed = min(unseen); stack = [seed]; unseen.remove(seed); component = []
                while stack:
                    current = stack.pop(); component.append(current)
                    for neighbor in adjacency[current]:
                        if neighbor in unseen:
                            unseen.remove(neighbor); stack.append(neighbor)
                components.append(sorted(component))
            if len(components) <= 1:
                continue
            components.sort(key=lambda values: (-len(values), values[0]))
            for component in components[1:]:
                new_vertex = len(vertices); vertices.append(vertices[int(vertex)])
                for face_id in component:
                    faces[face_id, faces[face_id] == vertex] = new_vertex
                duplicates += 1
        iterations.append({"iteration": iteration + 1, "problematic_boundary_vertices": int(len(problematic)), "duplicated_vertex_ids": int(duplicates)})
        if duplicates == 0:
            raise RuntimeError(f"could not split branched boundary fans: {problematic[:20].tolist()}")
    result = trimesh.Trimesh(vertices=np.asarray(vertices), faces=faces, process=False)
    return result, {"iterations": iterations, "total_position_identical_vertex_duplicates": int(sum(row["duplicated_vertex_ids"] for row in iterations))}


def close_boundary_loops(mesh: trimesh.Trimesh) -> tuple[trimesh.Trimesh, list[dict[str, Any]]]:
    loops = boundary_loops(mesh)
    if not loops:
        return mesh.copy(), []
    vertices = np.asarray(mesh.vertices, dtype=np.float64).tolist()
    faces = np.asarray(mesh.faces, dtype=np.int64).tolist()
    rows = []
    for loop in loops:
        points = np.asarray(vertices, dtype=np.float64)[loop]
        center = points.mean(axis=0); center_id = len(vertices); vertices.append(center.tolist())
        for index, start in enumerate(loop):
            stop = int(loop[(index + 1) % len(loop)])
            faces.append([stop, int(start), center_id])
        rows.append({"boundary_edges": int(len(loop)), "centroid": center.tolist(), "max_extent": float(np.ptp(points, axis=0).max()), "new_faces": int(len(loop))})
    result = trimesh.Trimesh(vertices=np.asarray(vertices), faces=np.asarray(faces), process=False)
    return result, rows


def retain_largest(mask: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    labels, count = ndimage.label(mask)
    sizes = np.bincount(labels.ravel()); sizes[0] = 0
    winner = int(np.argmax(sizes))
    return labels == winner, {"components_before_selection": int(count), "selected_voxels": int(sizes[winner]), "discarded_voxels": int(np.sum(sizes) - sizes[winner])}


def build_inner(outer: trimesh.Trimesh, target_height_voxels: int, nominal_mm: float, mm_per_unit: float) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    pitch = float(np.ptp(outer.bounds, axis=0)[1] / target_height_voxels)
    voxel = outer.voxelized(pitch=pitch, method="subdivide")
    pad = 4
    surface = np.pad(np.asarray(voxel.matrix, dtype=bool), pad_width=pad)
    solid = ndimage.binary_fill_holes(surface)
    solid, solid_info = retain_largest(solid)
    distance = ndimage.distance_transform_edt(solid) * pitch
    nominal_units = nominal_mm / mm_per_unit
    threshold_units = nominal_units + pitch
    inner_mask = distance >= threshold_units
    inner_mask, inner_info = retain_largest(inner_mask)
    vertices_index, faces, _, _ = measure.marching_cubes(inner_mask.astype(np.uint8), level=0.5, allow_degenerate=False)
    vertices_index -= float(pad)
    vertices_world = trimesh.transform_points(vertices_index, voxel.transform)
    inner_raw = trimesh.Trimesh(vertices=vertices_world, faces=faces, process=True)
    raw_metrics = topology_metrics(inner_raw)
    inner_subset, inner_subset_report, _ = select_manifold_subset(
        inner_raw, np.zeros(len(inner_raw.faces), dtype=bool)
    )
    inner_split, inner_fan_report = split_boundary_vertex_fans(inner_subset)
    inner_closed, inner_loop_report = close_boundary_loops(inner_split)
    inner_closed.remove_unreferenced_vertices()
    inner_closed.fix_normals(multibody=True)
    pieces = list(inner_closed.split(only_watertight=False))
    pieces.sort(key=lambda mesh: (len(mesh.faces), abs(float(mesh.volume))), reverse=True)
    inner = pieces[0]
    discarded = pieces[1:]
    if inner.volume < 0:
        inner.invert()
    return inner, {
        "grid_target_height_voxels": int(target_height_voxels), "pitch_model_units": pitch,
        "pitch_mm": pitch * mm_per_unit, "surface_matrix_shape_padded": list(surface.shape),
        "surface_voxels": int(np.count_nonzero(surface)), "solid_voxels": int(np.count_nonzero(solid)),
        "nominal_wall_mm": nominal_mm, "nominal_wall_model_units": nominal_units,
        "distance_threshold_model_units": threshold_units, "distance_threshold_mm": threshold_units * mm_per_unit,
        "outer_solid_selection": solid_info, "inner_selection": inner_info,
        "marching_cubes_raw_metrics": raw_metrics,
        "generated_inner_topology_selection": inner_subset_report,
        "generated_inner_vertex_fan_split": inner_fan_report,
        "generated_inner_boundary_loop_patches": inner_loop_report,
        "generated_inner_surface_components_before_largest_selection": int(len(pieces)),
        "generated_inner_discarded_components": [
            {"vertices": int(len(mesh.vertices)), "faces": int(len(mesh.faces)), "absolute_volume": abs(float(mesh.volume))}
            for mesh in discarded
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--grid-height", type=int, default=640)
    parser.add_argument("--wall-mm", type=float, default=2.4)
    parser.add_argument("--mouth-safety-mm", type=float, default=5.0)
    args = parser.parse_args()
    source = args.mesh.resolve(); before = sha256(source)
    if before != EXPECTED_SHA:
        raise RuntimeError(before)
    output = args.output_dir.resolve(); output.mkdir(parents=True, exist_ok=True)
    expected_outputs = [output / name for name in ("outer-candidate-v001-outer.stl", "outer-candidate-v001-inner.stl", "outer-candidate-v001.stl", "outer-candidate-v001.glb", "outer-candidate-v001-build.json")]
    if any(path.exists() for path in expected_outputs):
        raise FileExistsError("candidate build output already exists; refusing overwrite")
    original = load_c01(source)
    mm_per_unit = 190.0 / 1.0017378330230713
    protected = protected_mouth_faces(original, args.mouth_safety_mm, mm_per_unit)
    subset, subset_report, retained_original_ids = select_manifold_subset(original, protected.copy())
    removed_ids = np.asarray(subset_report["removed_original_face_ids"], dtype=np.int64)
    removed_protected_ids = removed_ids[protected[removed_ids]] if len(removed_ids) else np.empty(0, dtype=np.int64)
    subset_split, fan_report = split_boundary_vertex_fans(subset)
    outer, loop_report = close_boundary_loops(subset_split)
    outer.remove_unreferenced_vertices()
    outer.fix_normals(multibody=True)
    outer_metrics = topology_metrics(outer)
    protected_redundancy = removed_face_deviation(original, outer, removed_protected_ids, mm_per_unit)
    if protected_redundancy["maximum_mm"] > 0.05:
        failure = {"status": "REJECTED_PROTECTED_MOUTH_DEVIATION", "maximum_allowed_mm": 0.05, "protected_removed_face_deviation": protected_redundancy, "source_sha256": before}
        atomic_json(output / "outer-candidate-v001-build-rejected.json", failure)
        raise RuntimeError(f"protected mouth deviation gate failed: {protected_redundancy}")
    if not outer_metrics["watertight"] or outer_metrics["boundary_edges"] or outer_metrics["nonmanifold_edges"]:
        failure = {"status": "REJECTED_OUTER_TOPOLOGY", "outer_metrics": outer_metrics, "subset": subset_report, "vertex_fan_split": fan_report, "boundary_loops": loop_report, "source_sha256": before}
        atomic_json(output / "outer-candidate-v001-build-rejected.json", failure)
        raise RuntimeError(f"outer topology gate failed: {outer_metrics}")
    inner, inner_build = build_inner(outer, args.grid_height, args.wall_mm, mm_per_unit)
    inner_metrics = topology_metrics(inner)
    if not inner_metrics["watertight"] or inner_metrics["nonmanifold_edges"] or inner_metrics["boundary_edges"]:
        raise RuntimeError(f"inner topology gate failed: {inner_metrics}")
    inner_for_hollow = inner.copy(); inner_for_hollow.invert()
    combined = trimesh.util.concatenate((outer, inner_for_hollow))
    combined_metrics = topology_metrics(combined)
    if not combined_metrics["watertight"] or combined_metrics["nonmanifold_edges"] or combined_metrics["boundary_edges"]:
        raise RuntimeError(f"combined topology gate failed: {combined_metrics}")
    atomic_export(outer, output / "outer-candidate-v001-outer.stl", "stl")
    atomic_export(inner_for_hollow, output / "outer-candidate-v001-inner.stl", "stl")
    atomic_export(combined, output / "outer-candidate-v001.stl", "stl")
    atomic_export(combined, output / "outer-candidate-v001.glb", "glb")
    after = sha256(source)
    if after != before:
        raise RuntimeError("source changed")
    build = {
        "schema": "ai3d.outer-candidate.build.v1", "status": "BUILT_NOT_VALIDATED", "candidate": "outer-candidate-v001",
        "source": {"path": str(source), "sha256_before": before, "sha256_after": after},
        "guardrails": {"c02_used": False, "tail_components_used": [], "original_written": False, "visible_smoothing": False, "global_outer_remesh": False, "mouth_safety_band_mm": args.mouth_safety_mm},
        "protected_mouth_faces": int(np.count_nonzero(protected)), "retained_original_faces": int(len(retained_original_ids)),
        "removed_original_faces": int(len(subset_report["removed_original_face_ids"])),
        "removed_protected_mouth_faces": int(len(removed_protected_ids)), "protected_removed_face_deviation": protected_redundancy,
        "topology_selection": subset_report, "vertex_fan_split": fan_report, "boundary_loop_patches": loop_report,
        "outer_metrics": outer_metrics, "inner_build": inner_build, "inner_metrics": inner_metrics, "combined_metrics": combined_metrics,
        "outputs": {path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)} for path in expected_outputs[:-1]},
    }
    atomic_json(output / "outer-candidate-v001-build.json", build)
    print(json.dumps({"status": build["status"], "protected_faces": build["protected_mouth_faces"], "removed_faces": build["removed_original_faces"], "patch_loops": len(loop_report), "outer": outer_metrics, "inner": inner_metrics, "combined": combined_metrics}, indent=2))


if __name__ == "__main__":
    main()
