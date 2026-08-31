#!/usr/bin/env python3
"""R15 constrained harmonic closure and Gate-1 self-correction.

The large underside source hole and every remaining local boundary of the
selected R14 exterior sheet are filled with boundary-constrained harmonic disk
patches. No hull, voxelization, Poisson reconstruction, heightfield or radial
replacement surface is used. If the closed source sheet remains topologically
non-orientable, the second attempt removes only faces participating in proven
orientation-conflict cycles, regularizes the new local boundaries, and repeats
the same constrained patch operation.
"""

from __future__ import annotations

import json
import heapq
import math
from pathlib import Path

import numpy as np

from r15_mesh_core import (
    MM_PER_UNIT,
    apply_orientation,
    boundary_loops,
    compact_mesh,
    connected_components,
    edge_runs,
    face_geometry,
    json_write,
    mesh_metrics,
    orientability_constraints,
    read_binary_ply,
    sha256,
    write_binary_ply,
)


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
SOURCE = OUT / "inputs" / "r14-local-surgery-input.ply"
EXPECTED_SHA256 = "f6c82635080a5c97c350ba80e18dbda79424f34542ca3f87e66a7d9d665cb1c2"
ATTEMPT_A = OUT / "masterform" / "r15-attempt-a-harmonic-closure-NON-APPROVED.ply"
ATTEMPT_B = OUT / "masterform" / "herbst-igel-r02-r15-gate1-candidate.ply"
ATTEMPT_C = OUT / "masterform" / "herbst-igel-r02-r15-gate1-candidate-c.ply"


def resample_closed(points: np.ndarray, count: int) -> np.ndarray:
    lengths = np.linalg.norm(np.roll(points, -1, axis=0) - points, axis=1)
    perimeter = float(lengths.sum())
    if perimeter <= 1e-15:
        raise ValueError("zero-perimeter boundary")
    cumulative = np.r_[0.0, np.cumsum(lengths)] / perimeter
    extended = np.vstack((points, points[0]))
    targets = np.arange(count, dtype=np.float64) / count
    result = np.empty((count, 3), dtype=np.float64)
    for axis in range(3):
        result[:, axis] = np.interp(targets, cumulative, extended[:, axis])
    return result


def harmonic_samples(boundary_uniform: np.ndarray, radius: float, count: int) -> np.ndarray:
    n = len(boundary_uniform)
    spectrum = np.fft.fft(boundary_uniform, axis=0)
    frequencies = np.minimum(np.arange(n), n - np.arange(n)).astype(np.float64)
    attenuated = spectrum * np.power(radius, frequencies)[:, None]
    ring_full = np.fft.ifft(attenuated, axis=0).real
    if count == n:
        return ring_full
    positions = np.arange(count, dtype=np.float64) * n / count
    low = np.floor(positions).astype(np.int64) % n
    high = (low + 1) % n
    alpha = (positions - np.floor(positions))[:, None]
    return ring_full[low] * (1.0 - alpha) + ring_full[high] * alpha


def ring_parameters(points: np.ndarray) -> np.ndarray:
    lengths = np.linalg.norm(np.roll(points, -1, axis=0) - points, axis=1)
    perimeter = float(lengths.sum())
    return np.r_[0.0, np.cumsum(lengths[:-1])] / max(perimeter, 1e-15)


def connect_annulus(
    outer_ids: np.ndarray,
    outer_t: np.ndarray,
    inner_ids: np.ndarray,
    inner_t: np.ndarray,
) -> np.ndarray:
    na, nb = len(outer_ids), len(inner_ids)
    faces: list[tuple[int, int, int]] = []
    i = j = 0
    while i < na or j < nb:
        next_a = float(outer_t[(i + 1) % na] + (1.0 if i + 1 >= na else 0.0)) if i < na else math.inf
        next_b = float(inner_t[(j + 1) % nb] + (1.0 if j + 1 >= nb else 0.0)) if j < nb else math.inf
        a0 = int(outer_ids[i % na])
        b0 = int(inner_ids[j % nb])
        if next_a <= next_b:
            a1 = int(outer_ids[(i + 1) % na])
            faces.append((a0, a1, b0))
            i += 1
        else:
            b1 = int(inner_ids[(j + 1) % nb])
            faces.append((a0, b1, b0))
            j += 1
    return np.asarray(faces, dtype=np.int64)


def harmonic_disk_patch(vertices: np.ndarray, loop: np.ndarray, next_vertex: int) -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
    boundary = vertices[loop]
    edge_lengths = np.linalg.norm(np.roll(boundary, -1, axis=0) - boundary, axis=1)
    perimeter_mm = float(edge_lengths.sum() * MM_PER_UNIT)
    extent_mm = np.ptp(boundary, axis=0) * MM_PER_UNIT
    max_extent_mm = float(extent_mm.max())
    underside = len(loop) >= 1000 and float(boundary[:, 2].max() * MM_PER_UNIT) < -50.0
    radial_layers = int(np.clip(math.ceil(max_extent_mm / (0.9 if underside else 0.65)), 3, 96))
    boundary_uniform = resample_closed(boundary, len(loop))
    rings: list[tuple[np.ndarray, np.ndarray]] = [(loop.copy(), ring_parameters(boundary))]
    new_vertices: list[np.ndarray] = []
    current = next_vertex
    for layer in range(1, radial_layers + 1):
        radius = 1.0 - layer / (radial_layers + 1)
        count = max(6, int(round(len(loop) * radius)))
        points = harmonic_samples(boundary_uniform, radius, count)
        ids = np.arange(current, current + count, dtype=np.int64)
        current += count
        new_vertices.append(points)
        rings.append((ids, np.arange(count, dtype=np.float64) / count))
    center = boundary_uniform.mean(axis=0, keepdims=True)
    center_id = current
    new_vertices.append(center)
    faces: list[np.ndarray] = []
    for (outer_ids, outer_t), (inner_ids, inner_t) in zip(rings[:-1], rings[1:]):
        faces.append(connect_annulus(outer_ids, outer_t, inner_ids, inner_t))
    last_ids = rings[-1][0]
    faces.append(np.asarray([(int(last_ids[i]), int(last_ids[(i + 1) % len(last_ids)]), center_id) for i in range(len(last_ids))], dtype=np.int64))
    patch_vertices = np.vstack(new_vertices)
    patch_faces = np.vstack(faces)
    meta = {
        "edge_count": int(len(loop)),
        "perimeter_mm": perimeter_mm,
        "extent_mm": extent_mm.tolist(),
        "centroid_mm": (boundary.mean(axis=0) * MM_PER_UNIT).tolist(),
        "z_range_mm": [float(boundary[:, 2].min() * MM_PER_UNIT), float(boundary[:, 2].max() * MM_PER_UNIT)],
        "radial_layers": radial_layers,
        "new_vertices": int(len(patch_vertices)),
        "new_triangles": int(len(patch_faces)),
        "method": "boundary-constrained discrete harmonic disk (Fourier attenuation, progressive annular triangulation)",
        "confirmed_underside_source_hole": underside,
    }
    return patch_vertices, patch_faces, meta


def fill_all_boundaries(vertices: np.ndarray, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray, list[dict[str, object]]]:
    loops, boundary, owner_by_edge, adjacency = boundary_loops(faces)
    non_simple = [vertex for vertex, neighbours in adjacency.items() if len(neighbours) != 2]
    if non_simple:
        raise RuntimeError(f"boundary is not a union of simple rings: {len(non_simple)} exceptional vertices")
    patch_vertices: list[np.ndarray] = []
    patch_faces: list[np.ndarray] = []
    records: list[dict[str, object]] = []
    next_vertex = len(vertices)
    for loop_id, loop in enumerate(loops):
        vertices_new, faces_new, record = harmonic_disk_patch(vertices, loop, next_vertex)
        record["loop_id"] = loop_id
        record["boundary_vertex_ids"] = loop.tolist()
        records.append(record)
        patch_vertices.append(vertices_new)
        patch_faces.append(faces_new)
        next_vertex += len(vertices_new)
    result_vertices = np.vstack((vertices, *patch_vertices)) if patch_vertices else vertices.copy()
    result_faces = np.vstack((faces, *patch_faces)) if patch_faces else faces.copy()
    return result_vertices, result_faces, records


def boundary_normal_transition(vertices: np.ndarray, source_faces: np.ndarray, candidate_faces: np.ndarray, source_face_count: int) -> dict[str, object]:
    edges, owners, _signs, starts, _ends, counts = edge_runs(candidate_faces)
    _triangles, _areas, normals = face_geometry(vertices, candidate_faces)
    jumps: list[float] = []
    records = []
    for start in starts[counts == 2]:
        a, b = int(owners[start]), int(owners[start + 1])
        if (a < source_face_count) == (b < source_face_count):
            continue
        source_face = a if a < source_face_count else b
        patch_face = b if a < source_face_count else a
        dot = float(np.clip(abs(normals[source_face] @ normals[patch_face]), 0.0, 1.0))
        jump = math.degrees(math.acos(dot))
        jumps.append(jump)
        if jump > 45.0:
            records.append({
                "edge_vertex_ids": edges[start].tolist(),
                "source_face": source_face,
                "patch_face": patch_face,
                "normal_jump_deg_unsigned": jump,
            })
    values = np.asarray(jumps, dtype=np.float64)
    return {
        "connection_edges": int(len(values)),
        "normal_jump_deg_unsigned": {
            "minimum": float(values.min(initial=0.0)),
            "median": float(np.median(values)) if len(values) else None,
            "p95": float(np.percentile(values, 95)) if len(values) else None,
            "maximum": float(values.max(initial=0.0)),
        },
        "within_45deg": int(np.count_nonzero(values <= 45.0)),
        "over_45deg": int(np.count_nonzero(values > 45.0)),
        "local_exceptions": records,
    }


def keep_largest_component(vertices: np.ndarray, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict[str, int]]:
    labels, components = connected_components(faces)
    main = int(np.argmax(components))
    selected = faces[labels == main]
    compact_vertices, compact_faces, _used = compact_mesh(vertices, selected)
    return compact_vertices, compact_faces, {
        "components_before": int(len(components)),
        "kept_faces": int(len(selected)),
        "discarded_faces": int(len(faces) - len(selected)),
    }


def remove_orientation_conflicts(vertices: np.ndarray, faces: np.ndarray, max_rounds: int = 5):
    active = np.ones(len(faces), dtype=bool)
    records = []
    for round_id in range(max_rounds):
        current_ids = np.flatnonzero(active)
        current = faces[current_ids]
        orientation = orientability_constraints(current)
        record = {
            "round": round_id,
            "active_faces_before": int(len(current)),
            "conflict_edges": int(orientation["orientation_constraint_conflicts"]),
            "conflict_faces": int(len(orientation["conflict_faces"])),
        }
        if orientation["orientable"]:
            record["status"] = "ORIENTABLE"
            records.append(record)
            break
        remove_global = current_ids[orientation["conflict_faces"]]
        active[remove_global] = False
        record["removed_faces"] = int(len(remove_global))
        record["status"] = "REMOVED_CONFLICT_FACES"
        records.append(record)
    selected = faces[active]
    # Keep the exterior majority sheet after conflict removal.
    labels, components = connected_components(selected)
    main = int(np.argmax(components))
    selected = selected[labels == main]
    # Erode only faces incident to non-simple boundary vertices until every
    # remaining boundary is a simple closed ring, allowing deterministic disks.
    regularization = []
    for iteration in range(20):
        loops, boundary, _owners, adjacency = boundary_loops(selected)
        exceptional = np.asarray([vertex for vertex, neighbours in adjacency.items() if len(neighbours) != 2], dtype=np.int64)
        regularization.append({"iteration": iteration, "exceptional_boundary_vertices": int(len(exceptional)), "faces": int(len(selected))})
        if not len(exceptional):
            break
        touch = np.any(np.isin(selected, exceptional), axis=1)
        selected = selected[~touch]
        labels, components = connected_components(selected)
        selected = selected[labels == int(np.argmax(components))]
    compact_vertices, compact_faces, used = compact_mesh(vertices, selected)
    return compact_vertices, compact_faces, {
        "rounds": records,
        "boundary_regularization": regularization,
        "source_faces_before": int(len(faces)),
        "source_faces_after": int(len(compact_faces)),
        "source_faces_removed_total": int(len(faces) - len(compact_faces)),
        "source_vertices_retained": int(len(used)),
    }


def split_bowtie_vertices_all(vertices: np.ndarray, faces: np.ndarray):
    faces_out = faces.copy()
    extra_vertices: list[np.ndarray] = []
    records = []
    for iteration in range(12):
        edges, owners, _signs, starts, _ends, counts = edge_runs(faces_out)
        boundary_edges = edges[starts[counts == 1]]
        boundary_vertices, degree = np.unique(boundary_edges.ravel(), return_counts=True)
        bad_vertices = boundary_vertices[degree > 2]
        if not len(bad_vertices):
            break
        bad_set = set(map(int, bad_vertices))
        flat_vertices = faces_out.ravel()
        flat_faces = np.repeat(np.arange(len(faces_out), dtype=np.int64), 3)
        mask = np.isin(flat_vertices, bad_vertices)
        selected_vertices = flat_vertices[mask]
        selected_faces = flat_faces[mask]
        incident_by_vertex: dict[int, list[int]] = {int(vertex): [] for vertex in bad_vertices}
        for vertex, face in zip(selected_vertices, selected_faces):
            incident_by_vertex[int(vertex)].append(int(face))
        connections_by_vertex: dict[int, list[tuple[int, int]]] = {int(vertex): [] for vertex in bad_vertices}
        manifold_starts = starts[counts == 2]
        touching_mask = np.isin(edges[manifold_starts, 0], bad_vertices) | np.isin(edges[manifold_starts, 1], bad_vertices)
        for start in manifold_starts[touching_mask]:
            a, b = int(edges[start, 0]), int(edges[start, 1])
            pair = (int(owners[start]), int(owners[start + 1]))
            if a in bad_set:
                connections_by_vertex[a].append(pair)
            if b in bad_set:
                connections_by_vertex[b].append(pair)
        for vertex in bad_vertices:
            incident = np.asarray(sorted(set(incident_by_vertex[int(vertex)])), dtype=np.int64)
            local = {int(face): index for index, face in enumerate(incident)}
            parent = np.arange(len(incident), dtype=np.int64)

            def find(a: int) -> int:
                while parent[a] != a:
                    parent[a] = parent[parent[a]]
                    a = int(parent[a])
                return a

            def union(a: int, b: int) -> None:
                a, b = find(a), find(b)
                if a != b:
                    parent[b] = a

            for face_a, face_b in connections_by_vertex[int(vertex)]:
                union(local[face_a], local[face_b])
            for index in range(len(parent)):
                parent[index] = find(index)
            roots = np.unique(parent)
            for component in roots[1:]:
                new_vertex = len(vertices) + len(extra_vertices)
                coordinate = vertices[int(vertex)] if int(vertex) < len(vertices) else extra_vertices[int(vertex) - len(vertices)]
                extra_vertices.append(coordinate.copy())
                selected_faces = incident[parent == component]
                replacement = faces_out[selected_faces].copy()
                replacement[replacement == vertex] = new_vertex
                faces_out[selected_faces] = replacement
                records.append({
                    "iteration": iteration,
                    "source_vertex": int(vertex),
                    "new_vertex": int(new_vertex),
                    "coordinate_displacement_mm": 0.0,
                    "separated_face_count": int(len(selected_faces)),
                })
    vertices_out = np.vstack((vertices, np.asarray(extra_vertices))) if extra_vertices else vertices.copy()
    return vertices_out, faces_out, records


def remove_orientation_conflicts_greedy(vertices: np.ndarray, faces: np.ndarray):
    orientation = orientability_constraints(faces)
    parity = orientation["parity"]
    edges, owners, signs, starts, _ends, counts = edge_runs(faces)
    conflict_pairs = []
    for start in starts[counts == 2]:
        a, b = int(owners[start]), int(owners[start + 1])
        required = int(1 ^ int(signs[start]) ^ int(signs[start + 1]))
        if (int(parity[a]) ^ int(parity[b])) != required:
            conflict_pairs.append((a, b))
    incident: dict[int, set[int]] = {}
    for edge_id, (a, b) in enumerate(conflict_pairs):
        incident.setdefault(a, set()).add(edge_id)
        incident.setdefault(b, set()).add(edge_id)
    heap = [(-len(edge_ids), face) for face, edge_ids in incident.items()]
    heapq.heapify(heap)
    uncovered = np.ones(len(conflict_pairs), dtype=bool)
    selected: set[int] = set()
    while np.any(uncovered):
        negative_degree, face = heapq.heappop(heap)
        current_edges = {edge_id for edge_id in incident.get(face, set()) if uncovered[edge_id]}
        if -negative_degree != len(current_edges):
            heapq.heappush(heap, (-len(current_edges), face))
            continue
        if not current_edges:
            continue
        selected.add(face)
        for edge_id in current_edges:
            uncovered[edge_id] = False
            a, b = conflict_pairs[edge_id]
            other = b if a == face else a
            remaining = sum(bool(uncovered[x]) for x in incident.get(other, set()))
            heapq.heappush(heap, (-remaining, other))
    keep = np.ones(len(faces), dtype=bool)
    keep[np.fromiter(sorted(selected), dtype=np.int64)] = False
    selected_faces = faces[keep]
    labels, components = connected_components(selected_faces)
    main = int(np.argmax(components))
    selected_faces = selected_faces[labels == main]
    split_vertices, split_faces, splits = split_bowtie_vertices_all(vertices, selected_faces)
    compact_vertices, compact_faces, used = compact_mesh(split_vertices, split_faces)
    after_orientation = orientability_constraints(compact_faces)
    loops, boundary, _owners, adjacency = boundary_loops(compact_faces)
    return compact_vertices, compact_faces, {
        "conflict_edges_before": int(len(conflict_pairs)),
        "greedy_vertex_cover_faces_removed": int(len(selected)),
        "faces_after_component_selection": int(len(selected_faces)),
        "discarded_faces_total": int(len(faces) - len(selected_faces)),
        "zero_displacement_bowtie_splits": int(len(splits)),
        "boundary_edges_after": int(len(boundary)),
        "boundary_loops_after": int(len(loops)),
        "non_simple_boundary_vertices_after": int(sum(len(neighbours) != 2 for neighbours in adjacency.values())),
        "orientable_after": bool(after_orientation["orientable"]),
        "orientation_conflicts_after": int(after_orientation["orientation_constraint_conflicts"]),
        "vertices_retained_after_compaction": int(len(used)),
    }


def run_attempt(name: str, vertices: np.ndarray, faces: np.ndarray, output: Path):
    before = mesh_metrics(vertices, faces)
    closed_vertices, closed_faces, patches = fill_all_boundaries(vertices, faces)
    transition = boundary_normal_transition(closed_vertices, faces, closed_faces, len(faces))
    orientation = orientability_constraints(closed_faces)
    if orientation["orientable"]:
        closed_faces = apply_orientation(closed_faces, orientation["parity"])
        # Select outward global winding by signed volume.
        triangles = closed_vertices[closed_faces]
        volume6 = float(np.einsum("ij,ij->i", triangles[:, 0], np.cross(triangles[:, 1], triangles[:, 2])).sum())
        if volume6 < 0:
            closed_faces[:, [1, 2]] = closed_faces[:, [2, 1]]
    after = mesh_metrics(closed_vertices, closed_faces)
    write_binary_ply(output, closed_vertices, closed_faces)
    underside = next((record for record in patches if record["confirmed_underside_source_hole"]), None)
    return closed_vertices, closed_faces, {
        "attempt": name,
        "input_metrics": before,
        "patch_count": int(len(patches)),
        "patch_triangles": int(sum(record["new_triangles"] for record in patches)),
        "patch_vertices": int(sum(record["new_vertices"] for record in patches)),
        "confirmed_underside_patch": underside,
        "all_patch_records": patches,
        "boundary_normal_transition": transition,
        "orientation": {
            "orientable": bool(orientation["orientable"]),
            "orientation_constraint_conflicts": int(orientation["orientation_constraint_conflicts"]),
            "conflict_faces": int(len(orientation["conflict_faces"])),
        },
        "output_metrics": after,
        "output_path": output.relative_to(ROOT).as_posix(),
        "output_sha256": sha256(output),
    }


def main() -> None:
    if sha256(SOURCE) != EXPECTED_SHA256:
        raise RuntimeError("R14 input hash mismatch")
    all_vertices, all_faces = read_binary_ply(SOURCE)
    base_vertices, base_faces, component_selection = keep_largest_component(all_vertices, all_faces)
    _va, _fa, attempt_a = run_attempt("A_KEEP_R14_MAIN_AND_CLOSE", base_vertices, base_faces, ATTEMPT_A)
    corrected_vertices, corrected_faces, conflict_surgery = remove_orientation_conflicts(base_vertices, base_faces)
    _vb, _fb, attempt_b = run_attempt("B_LOCAL_CONFLICT_SURGERY_AND_CLOSE", corrected_vertices, corrected_faces, ATTEMPT_B)
    narrow_vertices, narrow_faces, narrow_surgery = remove_orientation_conflicts_greedy(base_vertices, base_faces)
    _vc, _fc, attempt_c = run_attempt("C_GREEDY_MINIMAL_CONFLICT_COVER_AND_CLOSE", narrow_vertices, narrow_faces, ATTEMPT_C)
    gate1_pass = (
        attempt_c["output_metrics"]["boundary_edges"] == 0
        and attempt_c["output_metrics"]["nonmanifold_edges"] == 0
        and attempt_c["output_metrics"]["degenerate_faces"] == 0
        and attempt_c["output_metrics"]["connected_face_surfaces"] == 1
        and attempt_c["orientation"]["orientable"]
    )
    report = {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-UNDERSIDE-CLOSURE-R15.md",
        "task_blob_sha": "6f36e00693a3f9ad6859b43450a5a77316fa9254",
        "method": "R14 exterior main-sheet selection + boundary-constrained harmonic disk patches; local orientation-conflict face surgery only on retry",
        "forbidden_global_methods_used": False,
        "r14_component_selection": component_selection,
        "attempt_a": attempt_a,
        "attempt_b_conflict_surgery": conflict_surgery,
        "attempt_b": attempt_b,
        "attempt_c_narrow_surgery": narrow_surgery,
        "attempt_c": attempt_c,
        "confirmed_self_or_cross_intersections": None,
        "intersection_test_status": "PENDING_SEPARATE_GATE1_INTERSECTION_AUDIT" if gate1_pass else "NOT_RUN_OTHER_GATE1_PRECONDITION_FAIL",
        "gate_1_preliminary": "PASS_PENDING_INTERSECTION_AUDIT" if gate1_pass else "FAIL",
    }
    json_write(OUT / "audits" / "gate1-harmonic-closure-r15.json", report)
    print(json.dumps({
        "attempt_a": attempt_a["orientation"],
        "attempt_a_metrics": attempt_a["output_metrics"],
        "attempt_b": attempt_b["orientation"],
        "attempt_b_metrics": attempt_b["output_metrics"],
        "attempt_c": attempt_c["orientation"],
        "attempt_c_metrics": attempt_c["output_metrics"],
        "gate_1_preliminary": report["gate_1_preliminary"],
    }, indent=2))


if __name__ == "__main__":
    main()
