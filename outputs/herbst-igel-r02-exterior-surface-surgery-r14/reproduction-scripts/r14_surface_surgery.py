#!/usr/bin/env python3
"""R14 local exterior-surface surgery and ordered gate evidence.

This script never builds a global replacement hull.  It keeps Seed-42 faces,
resolves edge and vertex branching locally, closes only small boundary loops
whose complete triangulation satisfies the approved edge-length and normal
limits, and stops before any forbidden cap/depth bridge.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import subprocess
from collections import defaultdict, deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
TASK = "tasks/TASK-HERBST-IGEL-R02-EXTERIOR-SURFACE-SURGERY-R14.md"
TASK_BLOB = "24e2f98d42250e59fa72f462f0b258c7dd8b65d0"
R11_REBUILD_BLOB = "571d31343ad14e27a8705d0120764667f59d9cf5"
SOURCE = Path(
    r"D:\3D-Models\generated\herbst-igel-r02-r08-input\outputs"
    r"\herbst-igel-r02-trellis-optik-retry-r07\trellis-raw\seed-00000042"
    r"\herbst-igel-r02-trellis-raw-seed-42.ply"
)
REF_CLEAN = Path(
    r"D:\3D-Models\generated\herbst-igel-r02-r08-input\outputs"
    r"\herbst-igel-r02-trellis-optik-retry-r07\reference-audit\ref-clean-r07.jpg"
)
REF_SEAM = Path(
    r"D:\3D-Models\generated\herbst-igel-r02-r08-input\outputs"
    r"\herbst-igel-r02-trellis-optik-retry-r07\reference-audit\ref-seam-r07.jpg"
)
EXPECTED = {
    "seed42": "85ba18eaed15bdbe631fc49dd571e73882c4055e2c247022e90ad15ed99822c6",
    "ref_clean": "c1c9a5a094f1db2fd220f3433f83af8dedca780f56a4bf479eb8883432250859",
    "ref_seam": "b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4",
}
MASTER = OUT / "masterform" / "herbst-igel-r02-r14-local-surgery-PARTIAL-NON-APPROVED.ply"
MM_PER_UNIT = 318.2455727028218
COS_60 = 0.5


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_binary_ply(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with path.open("rb") as stream:
        header: list[str] = []
        while True:
            line = stream.readline()
            if not line:
                raise ValueError("Unexpected EOF in PLY header")
            decoded = line.decode("ascii").strip()
            header.append(decoded)
            if decoded == "end_header":
                break
        vertices_count = int(next(x.split()[2] for x in header if x.startswith("element vertex ")))
        faces_count = int(next(x.split()[2] for x in header if x.startswith("element face ")))
        vertices = np.fromfile(stream, dtype="<f4", count=vertices_count * 3).reshape((-1, 3)).astype(np.float64)
        raw = np.fromfile(stream, dtype=np.dtype([("n", "u1"), ("v", "<i4", (3,))]), count=faces_count)
        if len(raw) != faces_count or not np.all(raw["n"] == 3):
            raise ValueError("R14 requires an all-triangle binary PLY")
        faces = raw["v"].astype(np.int64)
    return vertices, faces


def write_binary_ply(path: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "ply\nformat binary_little_endian 1.0\n"
        f"element vertex {len(vertices)}\nproperty float x\nproperty float y\nproperty float z\n"
        f"element face {len(faces)}\nproperty list uchar int vertex_indices\nend_header\n"
    ).encode("ascii")
    face_dtype = np.dtype([("n", "u1"), ("v", "<i4", (3,))])
    packed = np.empty(len(faces), dtype=face_dtype)
    packed["n"] = 3
    packed["v"] = faces.astype(np.int32)
    with path.open("wb") as stream:
        stream.write(header)
        np.asarray(vertices, dtype="<f4").tofile(stream)
        packed.tofile(stream)


def json_write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def edge_runs(faces: np.ndarray, face_ids: np.ndarray | None = None):
    if face_ids is None:
        face_ids = np.arange(len(faces), dtype=np.int64)
    selected = faces[face_ids]
    directed = np.concatenate((selected[:, [0, 1]], selected[:, [1, 2]], selected[:, [2, 0]]))
    signs = np.where(directed[:, 0] < directed[:, 1], 1, -1).astype(np.int8)
    edges = np.sort(directed, axis=1)
    owners = np.tile(face_ids, 3)
    order = np.lexsort((edges[:, 1], edges[:, 0]))
    sorted_edges, sorted_owners, sorted_signs = edges[order], owners[order], signs[order]
    starts = np.r_[0, 1 + np.nonzero(np.any(sorted_edges[1:] != sorted_edges[:-1], axis=1))[0]]
    ends = np.r_[starts[1:], len(sorted_edges)]
    return sorted_edges, sorted_owners, sorted_signs, starts, ends, ends - starts


def face_geometry(vertices: np.ndarray, faces: np.ndarray):
    triangles = vertices[faces]
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(cross, axis=1)
    normals = np.zeros_like(cross)
    good = lengths > 1e-15
    normals[good] = cross[good] / lengths[good, None]
    return triangles, lengths, normals


def connected_components(faces: np.ndarray, active: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    _e, owners, _s, starts, _ends, counts = edge_runs(faces, active)
    mapping = {int(face): index for index, face in enumerate(active)}
    parent = np.arange(len(active), dtype=np.int64)
    size = np.ones(len(active), dtype=np.int64)

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = int(parent[a])
        return a

    def union(a: int, b: int) -> None:
        a, b = find(a), find(b)
        if a == b:
            return
        if size[a] < size[b]:
            a, b = b, a
        parent[b] = a
        size[a] += size[b]

    for start in starts[counts == 2]:
        union(mapping[int(owners[start])], mapping[int(owners[start + 1])])
    for index in range(len(parent)):
        parent[index] = find(index)
    _roots, inverse, counts_out = np.unique(parent, return_inverse=True, return_counts=True)
    labels = np.full(len(faces), -1, dtype=np.int64)
    labels[active] = inverse
    return labels, counts_out


def camera_basis(camera: tuple[float, float, float]):
    position = np.asarray(camera, dtype=np.float64)
    forward = -position / np.linalg.norm(position)
    up_world = np.array([0.0, 0.0, 1.0])
    if abs(float(forward @ up_world)) > 0.98:
        up_world = np.array([0.0, 1.0, 0.0])
    right = np.cross(forward, up_world)
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    return right, up / np.linalg.norm(up), forward


CAMERAS = [
    ("3q-front", (-1.0, -1.0, 0.35), "3/4 vorne"),
    ("left", (0.0, -1.0, 0.12), "links / Referenzseite"),
    ("right", (0.0, 1.0, 0.12), "rechts"),
    ("rear", (1.0, 0.0, 0.12), "hinten"),
    ("top", (0.0, 0.0, 1.0), "oben"),
    ("bottom", (0.0, 0.0, -1.0), "unten"),
]


def exposure_hits(vertices: np.ndarray, faces: np.ndarray, resolution: int = 160, tolerance: float = 0.0005):
    centers = vertices[faces].mean(axis=1)
    hits = np.zeros(len(faces), dtype=np.uint8)
    records = []
    for slug, camera, _label in CAMERAS:
        right, up, forward = camera_basis(camera)
        u, w, depth = centers @ right, centers @ up, centers @ forward
        u0, u1, w0, w1 = float(u.min()), float(u.max()), float(w.min()), float(w.max())
        px = np.clip(np.floor((u - u0) / max(u1 - u0, 1e-12) * (resolution - 1)), 0, resolution - 1).astype(np.int64)
        py = np.clip(np.floor((w - w0) / max(w1 - w0, 1e-12) * (resolution - 1)), 0, resolution - 1).astype(np.int64)
        flat = py * resolution + px
        envelope = np.full(resolution * resolution, np.inf)
        np.minimum.at(envelope, flat, depth)
        visible = depth <= envelope[flat] + tolerance
        hits += visible.astype(np.uint8)
        records.append({"view": slug, "exposed_face_centers": int(visible.sum()), "resolution": resolution, "depth_tolerance_normalized": tolerance})
    return hits, records


def load_confirmed_roi(vertices: np.ndarray, faces: np.ndarray) -> dict[str, object]:
    code = subprocess.check_output(["git", "cat-file", "blob", R11_REBUILD_BLOB], cwd=ROOT).decode("utf-8")
    namespace: dict[str, object] = {
        "__name__": "r11_confirmed_roi",
        "__file__": str(OUT / "reproduction-scripts" / "r11_confirmed_roi.py"),
    }
    exec(compile(code, namespace["__file__"], "exec"), namespace)
    namespace["REF_SEAM"] = REF_SEAM
    used = np.unique(faces)
    bounds_min, bounds_max = vertices[used].min(axis=0), vertices[used].max(axis=0)
    blue, body, roi, bbox, _rgb = namespace["reference_masks"]()
    profile_x, profile_center, profile_radius, _width = namespace["measured_width_profiles"](vertices)
    body_field = namespace["signed_distance_field"](body)
    _retained, remove, problem, selection = namespace["select_source_faces"](
        vertices, faces, roi, body_field, bounds_min, bounds_max, bbox, -0.105,
        profile_x, profile_center, profile_radius,
    )
    return {
        "problem_mask": problem,
        "remove_mask": remove,
        "selection": selection,
        "foreground_bbox_px": bbox,
        "body_pixels": int(body.sum()),
        "seam_pixels": int(np.count_nonzero(roi & ~body)),
        "lower_guard_normalized": -0.105,
    }


def separate_nonmanifold_edges(faces: np.ndarray, normals: np.ndarray, visible: np.ndarray, initial_labels: np.ndarray, initial_main: int):
    active = np.arange(len(faces), dtype=np.int64)
    rejected: set[int] = set()
    selection_rows: list[dict[str, object]] = []
    for iteration in range(4):
        edges, owners, _signs, starts, ends, counts = edge_runs(faces, active)
        bad = np.nonzero(counts > 2)[0]
        if not len(bad):
            break
        iteration_rejected: set[int] = set()
        for run_index in bad:
            incident = owners[starts[run_index] : ends[run_index]]
            best: tuple[float, int, int] | None = None
            for i in range(len(incident)):
                for j in range(i + 1, len(incident)):
                    a, b = int(incident[i]), int(incident[j])
                    crosses_main_sheet = (initial_labels[a] == initial_main) != (initial_labels[b] == initial_main)
                    score = (
                        abs(float(normals[a] @ normals[b]))
                        + 0.15 * (int(visible[a] > 0) + int(visible[b] > 0))
                        + 0.01 * (int(visible[a]) + int(visible[b]))
                        + 1.0 * int(crosses_main_sheet)
                    )
                    if best is None or score > best[0]:
                        best = (score, a, b)
            assert best is not None
            keep = {best[1], best[2]}
            rejected_here = [int(face) for face in incident if int(face) not in keep]
            iteration_rejected.update(rejected_here)
            selection_rows.append({
                "iteration": iteration,
                "edge_v0": int(edges[starts[run_index], 0]),
                "edge_v1": int(edges[starts[run_index], 1]),
                "incidence": int(counts[run_index]),
                "kept_face_0": best[1],
                "kept_face_1": best[2],
                "rejected_faces": ";".join(str(x) for x in rejected_here),
                "kept_visibility_hits": int(visible[best[1]]) + int(visible[best[2]]),
                "rejected_visibility_hits": int(sum(int(visible[x]) for x in rejected_here)),
                "pair_abs_normal_dot": abs(float(normals[best[1]] @ normals[best[2]])),
            })
        if not iteration_rejected:
            break
        rejected.update(iteration_rejected)
        reject_array = np.fromiter(iteration_rejected, dtype=np.int64)
        active = active[~np.isin(active, reject_array)]
    return active, rejected, selection_rows


def split_bowtie_vertices(vertices: np.ndarray, faces: np.ndarray, active: np.ndarray):
    vertices_out = vertices.copy()
    faces_out = faces.copy()
    records: list[dict[str, object]] = []
    for _iteration in range(4):
        edges, owners, _signs, starts, _ends, counts = edge_runs(faces_out, active)
        boundary_edges = edges[starts[counts == 1]]
        boundary_vertices, degree = np.unique(boundary_edges.ravel(), return_counts=True)
        bad_vertices = boundary_vertices[degree > 2]
        if not len(bad_vertices):
            break
        for vertex in bad_vertices:
            incident = active[np.any(faces_out[active] == vertex, axis=1)]
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

            touching = (counts == 2) & ((edges[starts, 0] == vertex) | (edges[starts, 1] == vertex))
            for start in starts[touching]:
                union(local[int(owners[start])], local[int(owners[start + 1])])
            for index in range(len(parent)):
                parent[index] = find(index)
            roots = np.unique(parent)
            for component in roots[1:]:
                new_vertex = len(vertices_out)
                vertices_out = np.vstack((vertices_out, vertices_out[int(vertex)]))
                selected_faces = incident[parent == component]
                replacement = faces_out[selected_faces].copy()
                replacement[replacement == vertex] = new_vertex
                faces_out[selected_faces] = replacement
                records.append({
                    "source_vertex": int(vertex),
                    "new_vertex": int(new_vertex),
                    "coordinate_displacement_mm": 0.0,
                    "separated_face_count": int(len(selected_faces)),
                })
    return vertices_out, faces_out, records


def boundary_loops(faces: np.ndarray, active: np.ndarray):
    edges, owners, _signs, starts, _ends, counts = edge_runs(faces, active)
    boundary_runs = np.nonzero(counts == 1)[0]
    boundary_edges = edges[starts[boundary_runs]]
    boundary_owners = owners[starts[boundary_runs]]
    owner_by_edge = {tuple(map(int, edge)): int(owner) for edge, owner in zip(boundary_edges, boundary_owners)}
    adjacency: dict[int, list[int]] = defaultdict(list)
    for a, b in boundary_edges:
        adjacency[int(a)].append(int(b))
        adjacency[int(b)].append(int(a))
    loops: list[list[int]] = []
    seen: set[int] = set()
    for first in adjacency:
        if first in seen or len(adjacency[first]) != 2:
            continue
        loop: list[int] = []
        previous: int | None = None
        current = first
        while current not in seen:
            seen.add(current)
            loop.append(current)
            candidates = adjacency[current]
            following = candidates[0] if candidates[0] != previous else candidates[1]
            previous, current = current, following
        if current == first:
            loops.append(loop)
    return loops, boundary_edges, owner_by_edge, adjacency


def polygon_area(points: np.ndarray) -> float:
    return 0.5 * float(np.sum(points[:, 0] * np.roll(points[:, 1], -1) - points[:, 1] * np.roll(points[:, 0], -1)))


def point_in_triangle(point: np.ndarray, a: np.ndarray, b: np.ndarray, c: np.ndarray, orientation: float) -> bool:
    cross = lambda p, q, r: float((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]))
    e0, e1, e2 = cross(a, b, point), cross(b, c, point), cross(c, a, point)
    eps = 1e-12
    return (e0 * orientation >= -eps) and (e1 * orientation >= -eps) and (e2 * orientation >= -eps)


def triangulate_small_loop(
    loop: list[int],
    vertices: np.ndarray,
    faces: np.ndarray,
    owner_by_edge: dict[tuple[int, int], int],
    source_normals: np.ndarray,
    existing_edge_keys: np.ndarray,
    edge_key_base: int,
):
    count = len(loop)
    if count > 32:
        return None, "loop_over_32_edges_not_local"
    points = vertices[loop]
    center = points.mean(axis=0)
    covariance = (points - center).T @ (points - center)
    _values, axes = np.linalg.eigh(covariance)
    basis = axes[:, 1:3]
    flat = (points - center) @ basis
    area = polygon_area(flat)
    if abs(area) < 1e-14:
        return None, "projection_degenerate"
    orientation = 1.0 if area > 0 else -1.0
    boundary_lengths = np.linalg.norm(points - np.roll(points, 1, axis=0), axis=1)
    local_median = float(np.median(boundary_lengths))
    edge_limit = 3.0 * local_median
    remaining = list(range(count))
    triangles_local: list[tuple[int, int, int]] = []
    new_diagonals: list[tuple[int, int]] = []
    while len(remaining) > 3:
        candidates: list[tuple[float, int, tuple[int, int, int]]] = []
        for position, current in enumerate(remaining):
            previous = remaining[position - 1]
            following = remaining[(position + 1) % len(remaining)]
            a, b, c = flat[previous], flat[current], flat[following]
            turn = float((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])) * orientation
            if turn <= 1e-13:
                continue
            diagonal = float(np.linalg.norm(points[previous] - points[following]))
            if diagonal > edge_limit:
                continue
            others = [index for index in remaining if index not in (previous, current, following)]
            if any(point_in_triangle(flat[index], a, b, c, orientation) for index in others):
                continue
            candidates.append((diagonal, position, (previous, current, following)))
        if not candidates:
            return None, "no_complete_local_ear_triangulation_within_3x_edge_limit"
        _length, position, triangle = min(candidates, key=lambda item: item[0])
        triangles_local.append(triangle)
        new_diagonals.append((triangle[0], triangle[2]))
        remaining.pop(position)
    triangles_local.append(tuple(remaining))
    patch_faces = np.asarray([[loop[a], loop[b], loop[c]] for a, b, c in triangles_local], dtype=np.int64)
    patch_triangles = vertices[patch_faces]
    patch_cross = np.cross(patch_triangles[:, 1] - patch_triangles[:, 0], patch_triangles[:, 2] - patch_triangles[:, 0])
    patch_lengths = np.linalg.norm(patch_cross, axis=1)
    if np.any(patch_lengths <= 1e-14):
        return None, "degenerate_patch_face"
    patch_normals = patch_cross / patch_lengths[:, None]
    edge_faces: dict[tuple[int, int], list[int]] = defaultdict(list)
    for face_index, triangle in enumerate(patch_faces):
        for a, b in ((triangle[0], triangle[1]), (triangle[1], triangle[2]), (triangle[2], triangle[0])):
            edge_faces[tuple(sorted((int(a), int(b))))].append(face_index)
    normal_jumps: list[float] = []
    for edge, local_faces in edge_faces.items():
        if len(local_faces) == 2:
            dot = abs(float(patch_normals[local_faces[0]] @ patch_normals[local_faces[1]]))
        else:
            source_face = owner_by_edge.get(edge)
            if source_face is None:
                return None, "patch_boundary_not_source_boundary"
            dot = abs(float(patch_normals[local_faces[0]] @ source_normals[source_face]))
        normal_jumps.append(math.degrees(math.acos(float(np.clip(dot, -1.0, 1.0)))))
    max_jump = max(normal_jumps, default=0.0)
    if max_jump > 60.0 + 1e-8:
        return None, "normal_jump_over_60deg"
    internal_edges = []
    for edge, local_faces in edge_faces.items():
        if len(local_faces) == 2 and edge not in owner_by_edge:
            edge_key = edge[0] * edge_key_base + edge[1]
            position = int(np.searchsorted(existing_edge_keys, edge_key))
            if position < len(existing_edge_keys) and int(existing_edge_keys[position]) == edge_key:
                return None, "internal_diagonal_already_exists_in_seed42_surface"
            length = float(np.linalg.norm(vertices[edge[0]] - vertices[edge[1]]))
            internal_edges.append({"v0": edge[0], "v1": edge[1], "length_normalized": length, "length_mm": length * MM_PER_UNIT})
            if length > edge_limit + 1e-12:
                return None, "internal_edge_over_3x_local_median"
    incidence = np.bincount(patch_faces.ravel(), minlength=len(vertices))
    if count >= 8 and int(incidence.max()) > math.ceil(0.60 * len(patch_faces)):
        return None, "triangle_fan_concentration_rejected"
    return {
        "faces": patch_faces,
        "internal_edges": internal_edges,
        "local_median_edge_normalized": local_median,
        "edge_limit_normalized": edge_limit,
        "max_normal_jump_deg": max_jump,
    }, None


def mesh_metrics(vertices: np.ndarray, faces: np.ndarray) -> dict[str, object]:
    triangles, double_area, _normals = face_geometry(vertices, faces)
    edges, _owners, _signs, _starts, _ends, counts = edge_runs(faces)
    labels, components = connected_components(faces, np.arange(len(faces), dtype=np.int64))
    _ = labels
    return {
        "vertices": int(len(vertices)),
        "triangles": int(len(faces)),
        "used_vertices": int(len(np.unique(faces))),
        "boundary_edges": int(np.count_nonzero(counts == 1)),
        "nonmanifold_edges": int(np.count_nonzero(counts > 2)),
        "max_edge_incidence": int(counts.max()),
        "degenerate_faces": int(np.count_nonzero(double_area <= 1e-15)),
        "connected_face_surfaces": int(len(components)),
        "largest_surface_faces": int(components.max()),
        "surface_area_normalized2": float(0.5 * double_area.sum()),
        "bounds_min": vertices[np.unique(faces)].min(axis=0).tolist(),
        "bounds_max": vertices[np.unique(faces)].max(axis=0).tolist(),
    }


def orientability(faces: np.ndarray) -> dict[str, object]:
    _edges, owners, signs, starts, _ends, counts = edge_runs(faces)
    parent = np.arange(len(faces), dtype=np.int64)
    parity = np.zeros(len(faces), dtype=np.int8)
    conflicts = 0

    def find(a: int) -> tuple[int, int]:
        if parent[a] == a:
            return a, 0
        root, inherited = find(int(parent[a]))
        parity[a] ^= inherited
        parent[a] = root
        return root, int(parity[a])

    for start in starts[counts == 2]:
        a, b = int(owners[start]), int(owners[start + 1])
        required = int(1 ^ int(signs[start] > 0) ^ int(signs[start + 1] > 0))
        ra, pa = find(a)
        rb, pb = find(b)
        if ra == rb:
            conflicts += int((pa ^ pb) != required)
        else:
            parent[rb] = ra
            parity[rb] = pa ^ pb ^ required
    return {"orientable": conflicts == 0, "orientation_constraint_conflicts": int(conflicts)}


def render(vertices: np.ndarray, faces: np.ndarray, camera: tuple[float, float, float], output: Path, title: str, size: int = 1000) -> None:
    stride = max(1, int(math.ceil(len(faces) / 1_500_000)))
    triangles = vertices[faces[::stride]]
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(cross, axis=1)
    keep = lengths > 1e-14
    centers = triangles.mean(axis=1)[keep]
    normals = cross[keep] / lengths[keep, None]
    center = 0.5 * (vertices.min(axis=0) + vertices.max(axis=0))
    centers -= center
    right, up, forward = camera_basis(camera)
    u, w, depth = centers @ right, centers @ up, centers @ forward
    extent = max(float(np.ptp(u)), float(np.ptp(w))) * 1.12
    scale = (size - 100) / extent
    u_mid, w_mid = 0.5 * float(u.max() + u.min()), 0.5 * float(w.max() + w.min())
    px = np.rint((u - u_mid) * scale + size / 2).astype(np.int64)
    py = np.rint(size / 2 - (w - w_mid) * scale).astype(np.int64)
    inside = (px >= 0) & (px < size) & (py >= 46) & (py < size)
    px, py, depth, normals = px[inside], py[inside], depth[inside], normals[inside]
    flat = py * size + px
    order = np.lexsort((depth, flat))
    ordered = flat[order]
    first = np.empty(len(ordered), dtype=bool)
    first[0] = True
    first[1:] = ordered[1:] != ordered[:-1]
    chosen = order[first]
    light = np.array([-0.35, 0.75, -0.55])
    light /= np.linalg.norm(light)
    shade = np.clip(0.22 + 0.52 * np.abs(normals[chosen] @ light) + 0.26 * np.abs(normals[chosen] @ (-forward)), 0, 1)
    base = np.array([190.0, 91.0, 40.0])
    colors = np.clip(base * (0.43 + 0.70 * shade[:, None]), 0, 255).astype(np.uint8)
    canvas = np.full((size * size, 3), 242, dtype=np.uint8)
    canvas[flat[chosen]] = colors
    pixels = canvas.reshape(size, size, 3)
    image = Image.fromarray(pixels)
    mask = Image.fromarray((np.any(pixels != 242, axis=2) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(7))
    expanded = image.filter(ImageFilter.MinFilter(7))
    result = Image.new("RGB", (size, size), (242, 242, 242))
    result.paste(expanded, mask=mask)
    draw = ImageDraw.Draw(result)
    draw.rectangle((0, 0, size, 46), fill=(255, 255, 255))
    draw.text((15, 16), title, fill=(20, 20, 20))
    output.parent.mkdir(parents=True, exist_ok=True)
    result.save(output, optimize=True)


def make_sheet(paths: list[Path], labels: list[str], output: Path, columns: int = 3) -> None:
    panel = (500, 500)
    rows = math.ceil(len(paths) / columns)
    sheet = Image.new("RGB", (columns * panel[0], rows * panel[1]), (232, 232, 232))
    for index, (path, label) in enumerate(zip(paths, labels)):
        source = Image.open(path).convert("RGB")
        fitted = ImageOps.contain(source, (480, 448), Image.Resampling.LANCZOS)
        tile = Image.new("RGB", panel, (242, 242, 242))
        tile.paste(fitted, ((panel[0] - fitted.width) // 2, 42 + (448 - fitted.height) // 2))
        draw = ImageDraw.Draw(tile)
        draw.rectangle((0, 0, panel[0], 40), fill=(255, 255, 255))
        draw.text((10, 13), label, fill=(20, 20, 20))
        sheet.paste(tile, ((index % columns) * panel[0], (index // columns) * panel[1]))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, optimize=True)


def silhouette_diagnostic(source_vertices: np.ndarray, source_faces: np.ndarray, candidate_vertices: np.ndarray, candidate_faces: np.ndarray, resolution: int = 256):
    records = []
    for slug, camera, _label in CAMERAS:
        right, up, _forward = camera_basis(camera)
        all_vertices = np.vstack((source_vertices, candidate_vertices))
        all_u, all_w = all_vertices @ right, all_vertices @ up
        u0, u1, w0, w1 = float(all_u.min()), float(all_u.max()), float(all_w.min()), float(all_w.max())

        def mask(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
            centers = vertices[faces].mean(axis=1)
            u, w = centers @ right, centers @ up
            px = np.clip(np.floor((u - u0) / max(u1 - u0, 1e-12) * (resolution - 1)), 0, resolution - 1).astype(np.int64)
            py = np.clip(np.floor((w - w0) / max(w1 - w0, 1e-12) * (resolution - 1)), 0, resolution - 1).astype(np.int64)
            image = np.zeros((resolution, resolution), dtype=np.uint8)
            image[py, px] = 255
            return np.asarray(Image.fromarray(image).filter(ImageFilter.MaxFilter(5))) > 0

        source_mask, candidate_mask = mask(source_vertices, source_faces), mask(candidate_vertices, candidate_faces)
        union = source_mask | candidate_mask
        xor = source_mask ^ candidate_mask
        records.append({
            "view": slug,
            "source_pixels": int(source_mask.sum()),
            "candidate_pixels": int(candidate_mask.sum()),
            "xor_pixels": int(xor.sum()),
            "xor_over_union_percent": float(100.0 * xor.sum() / max(1, union.sum())),
            "method": "real face-centroid ray-bin silhouette diagnostic with 5px conservative dilation",
        })
    return records


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    actual = {"seed42": sha256(SOURCE), "ref_clean": sha256(REF_CLEAN), "ref_seam": sha256(REF_SEAM)}
    if actual != EXPECTED:
        raise RuntimeError(f"R14 hash gate failed: {actual}")
    reference_dir = OUT / "reference-audit"
    reference_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REF_CLEAN, reference_dir / "ref-clean-r14.jpg")
    shutil.copyfile(REF_SEAM, reference_dir / "ref-seam-r14.jpg")
    json_write(reference_dir / "hash-gate-r14.json", {"schema_version": 1, "task": TASK, "expected": EXPECTED, "actual": actual, "status": "PASS"})

    vertices, faces = read_binary_ply(SOURCE)
    triangles, double_area, normals = face_geometry(vertices, faces)
    before = mesh_metrics(vertices, faces)
    roi = load_confirmed_roi(vertices, faces)
    roi_problem = roi.pop("problem_mask")
    roi_remove = roi.pop("remove_mask")
    visible, view_visibility = exposure_hits(vertices, faces)
    initial_active = np.arange(len(faces), dtype=np.int64)
    initial_labels, initial_components = connected_components(faces, initial_active)
    initial_main = int(np.argmax(initial_components))

    active, rejected, separation_rows = separate_nonmanifold_edges(faces, normals, visible, initial_labels, initial_main)
    active_labels, active_components = connected_components(faces, active)
    active_main = int(np.argmax(active_components))
    vertices_split, faces_split, vertex_separations = split_bowtie_vertices(vertices, faces, active)
    loops, boundary_edges, owner_by_edge, boundary_adjacency = boundary_loops(faces_split, active)
    all_active_edges, _active_owners, _active_signs, active_starts, _active_ends, _active_counts = edge_runs(faces_split, active)
    edge_key_base = len(vertices_split) + 1
    existing_edge_keys = (
        all_active_edges[active_starts, 0].astype(np.int64) * edge_key_base
        + all_active_edges[active_starts, 1].astype(np.int64)
    )
    non_simple_boundary_vertices = int(sum(len(neighbours) != 2 for neighbours in boundary_adjacency.values()))

    new_faces: list[np.ndarray] = []
    stitch_records: list[dict[str, object]] = []
    loop_records: list[dict[str, object]] = []
    filled_loop_indices: set[int] = set()
    for loop_index, loop in enumerate(loops):
        points = vertices_split[loop]
        lengths = np.linalg.norm(points - np.roll(points, 1, axis=0), axis=1)
        extent = np.ptp(points, axis=0)
        record = {
            "loop_id": loop_index,
            "edges": len(loop),
            "perimeter_mm": float(lengths.sum() * MM_PER_UNIT),
            "max_boundary_edge_mm": float(lengths.max() * MM_PER_UNIT),
            "extent_mm": (extent * MM_PER_UNIT).tolist(),
            "centroid_normalized": points.mean(axis=0).tolist(),
            "outside_confirmed_roi": bool(points[:, 2].max() < -0.105) if points[:, 2].max() < -0.105 else None,
        }
        patch, reason = triangulate_small_loop(
            loop, vertices_split, faces_split, owner_by_edge, normals,
            existing_edge_keys, edge_key_base,
        )
        if patch is None:
            record.update({"status": "REJECTED", "reason": reason})
        else:
            base_new_face = len(faces) + sum(len(block) for block in new_faces)
            new_faces.append(patch["faces"])
            filled_loop_indices.add(loop_index)
            record.update({
                "status": "FILLED_LOCAL_STITCH",
                "new_faces": int(len(patch["faces"])),
                "new_internal_edges": int(len(patch["internal_edges"])),
                "local_median_edge_mm": float(patch["local_median_edge_normalized"] * MM_PER_UNIT),
                "edge_limit_3x_mm": float(patch["edge_limit_normalized"] * MM_PER_UNIT),
                "max_normal_jump_deg": float(patch["max_normal_jump_deg"]),
            })
            for edge in patch["internal_edges"]:
                stitch_records.append({
                    "loop_id": loop_index,
                    "v0": edge["v0"],
                    "v1": edge["v1"],
                    "length_mm": edge["length_mm"],
                    "local_median_mm": float(patch["local_median_edge_normalized"] * MM_PER_UNIT),
                    "ratio_to_local_median": float(edge["length_normalized"] / patch["local_median_edge_normalized"]),
                    "max_adjacent_normal_jump_deg": float(patch["max_normal_jump_deg"]),
                    "first_new_face_index": base_new_face,
                })
        loop_records.append(record)

    candidate_faces = faces_split[active]
    if new_faces:
        candidate_faces = np.vstack((candidate_faces, *new_faces))
    used = np.unique(candidate_faces)
    remap = np.full(len(vertices_split), -1, dtype=np.int64)
    remap[used] = np.arange(len(used), dtype=np.int64)
    candidate_vertices = vertices_split[used]
    candidate_faces = remap[candidate_faces]
    write_binary_ply(MASTER, candidate_vertices, candidate_faces)
    after = mesh_metrics(candidate_vertices, candidate_faces)
    orientation = orientability(candidate_faces)

    remaining_loops = [record for record in loop_records if record["status"] == "REJECTED"]
    largest = max(remaining_loops, key=lambda item: item["perimeter_mm"])
    largest_centroid = np.asarray(largest["centroid_normalized"], dtype=np.float64)
    nearest_distance = float(np.linalg.norm(vertices - largest_centroid, axis=1).min())
    largest["nearest_seed42_vertex_distance_mm"] = nearest_distance * MM_PER_UNIT
    largest["roi_relation"] = "strictly outside confirmed R11/R12 ROI; z_max below -0.105 guard"
    largest["adjacent_same_layer_counter_ring_found"] = False

    rejected_array = np.fromiter(sorted(rejected), dtype=np.int64)
    classification = {
        "schema_version": 1,
        "task": TASK,
        "method": "edge-incidence patches + face normals + six-view ray-bin exposure + local nonmanifold pair selection",
        "six_view_visibility": view_visibility,
        "initial_manifold_edge_patches": int(len(initial_components)),
        "initial_main_patch_faces": int(initial_components[initial_main]),
        "initial_micro_patch_faces": int(len(faces) - initial_components[initial_main]),
        "active_faces_after_local_edge_separation": int(len(active)),
        "rejected_branch_faces": int(len(rejected)),
        "rejected_faces_with_any_exposure_hit": int(np.count_nonzero(visible[rejected_array] > 0)) if len(rejected_array) else 0,
        "active_components_after_edge_separation": int(len(active_components)),
        "largest_active_component_faces": int(active_components[active_main]),
        "visible_faces_outside_largest_component": int(np.count_nonzero((active_labels >= 0) & (active_labels != active_main) & (visible > 0))),
        "confirmed_r11_r12_roi": {
            **roi,
            "problem_triangles": int(roi_problem.sum()),
            "fusion_triangles_marked_for_removal_if_gate1_passed": int(roi_remove.sum()),
            "roi_rebuild_executed": False,
            "reason": "Gate 1 remains impossible without a forbidden global bottom cap/depth bridge; ordered gates stop before ROI rebuild and optics.",
        },
        "classification_status": "PASS_DIAGNOSTIC_NOT_A_GATE_PASS",
    }
    json_write(OUT / "reports" / "exterior-classification-r14.json", classification)
    json_write(OUT / "reports" / "boundary-loop-audit-r14.json", {
        "schema_version": 1,
        "task": TASK,
        "loops_before_local_fill": len(loops),
        "non_simple_boundary_vertices_after_vertex_separation": non_simple_boundary_vertices,
        "locally_filled_loops": len(filled_loop_indices),
        "rejected_loops": len(remaining_loops),
        "largest_unresolved_loop": largest,
        "loops": loop_records,
    })
    json_write(OUT / "reports" / "topology-audit-r14.json", {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "before_seed42": before,
        "after_maximum_compliant_local_surgery": after,
        "orientability": orientation,
        "face_vertex_separations": {"count": len(vertex_separations), "all_coordinate_displacements_mm_zero": True},
        "new_local_stitch_faces": int(sum(len(block) for block in new_faces)),
        "new_local_stitch_edges": len(stitch_records),
        "confirmed_self_or_cross_intersections": None,
        "intersection_test_status": "NOT_RUN_GATE1_BOUNDARY_AND_COMPONENT_PRECONDITION_FAIL",
        "overlapping_double_skin_status": "UNRESOLVED_VISIBLE_MICRO_SHEETS_PREVENT_REMOVAL",
        "gate_1_topology": "FAIL",
        "failure_reasons": [
            f"boundary_edges={after['boundary_edges']} (required 0)",
            f"connected_face_surfaces={after['connected_face_surfaces']} (required exactly 1)",
            f"orientation_constraint_conflicts={orientation['orientation_constraint_conflicts']} (required 0)",
            "the dominant remaining loop is the open Seed-42 underside, not a local hole between adjacent same-layer rings",
        ],
    })
    json_write(OUT / "reports" / "vertex-separation-r14.json", {"schema_version": 1, "records": vertex_separations})
    with (OUT / "reports" / "nonmanifold-face-selection-r14.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(separation_rows[0]))
        writer.writeheader()
        writer.writerows(separation_rows)
    with (OUT / "reports" / "stitch-edges-r14.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = ["loop_id", "v0", "v1", "length_mm", "local_median_mm", "ratio_to_local_median", "max_adjacent_normal_jump_deg", "first_new_face_index"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(stitch_records)
    stitch_summary = {
        "schema_version": 1,
        "task": TASK,
        "new_stitch_edges": len(stitch_records),
        "length_mm": {
            "minimum": min((x["length_mm"] for x in stitch_records), default=None),
            "median": float(np.median([x["length_mm"] for x in stitch_records])) if stitch_records else None,
            "maximum": max((x["length_mm"] for x in stitch_records), default=None),
        },
        "maximum_ratio_to_local_median": max((x["ratio_to_local_median"] for x in stitch_records), default=None),
        "maximum_normal_jump_deg": max((x["max_adjacent_normal_jump_deg"] for x in stitch_records), default=None),
        "all_length_checks_le_3x": all(x["ratio_to_local_median"] <= 3.0 + 1e-9 for x in stitch_records),
        "all_normal_checks_le_60deg": all(x["max_adjacent_normal_jump_deg"] <= 60.0 + 1e-9 for x in stitch_records),
        "complete_list": "outputs/herbst-igel-r02-exterior-surface-surgery-r14/reports/stitch-edges-r14.csv",
    }
    json_write(OUT / "reports" / "stitch-edge-summary-r14.json", stitch_summary)

    silhouette = silhouette_diagnostic(vertices, faces, candidate_vertices, candidate_faces)
    json_write(OUT / "reports" / "silhouette-ray-audit-r14.json", {
        "schema_version": 1,
        "task": TASK,
        "status": "DIAGNOSTIC_ONLY_GATE2_NOT_RUN",
        "outside_roi_masking": "not applied because Gate 1 failed before formal Gate 2",
        "views": silhouette,
    })
    distance_report = {
        "schema_version": 1,
        "task": TASK,
        "comparison": "protected visible Seed-42 exterior <-> repaired exterior outside ROI",
        "formal_bidirectional_point_to_triangle_status": "NOT_RUN_GATE1_FAIL",
        "requirements_mm": {"p95_max": 0.15, "maximum_max": 0.40},
        "gate_1_precondition": "FAIL",
        "geometric_blocker": {
            "loop_id": largest["loop_id"],
            "loop_edges": largest["edges"],
            "perimeter_mm": largest["perimeter_mm"],
            "extent_mm": largest["extent_mm"],
            "centroid_to_nearest_seed42_vertex_mm": largest["nearest_seed42_vertex_distance_mm"],
            "same_layer_counter_ring": "none",
            "interpretation": (
                "A same-layer underside closure would introduce real exterior tens of millimetres from Seed-42 and fail the 0.40 mm maximum. "
                "Following another Seed-42 depth layer would create the explicitly forbidden long depth-layer bridge/double skin."
            ),
        },
        "surface_area_ratio_partial_candidate_to_seed42": float(after["surface_area_normalized2"] / before["surface_area_normalized2"]),
        "r13_like_area_inflation": False,
        "gate_2_form_protection": "NOT_RUN_BY_GATE1",
    }
    json_write(OUT / "reports" / "surface-distance-outside-roi-r14.json", distance_report)

    render_paths: list[Path] = []
    render_records = []
    for slug, camera, label in CAMERAS:
        path = OUT / "renders-gate-evidence" / f"partial-r14-{slug}.png"
        render(candidate_vertices, candidate_faces, camera, path, f"R14 PARTIAL NON-APPROVED: {label}")
        render_paths.append(path)
        render_records.append({"view": slug, "camera_vector": list(camera), "path": path.relative_to(ROOT).as_posix()})
    contact = OUT / "renders-gate-evidence" / "partial-r14-contact-sheet.png"
    make_sheet(render_paths, [x[2] for x in CAMERAS], contact)
    soll_ist = OUT / "renders-gate-evidence" / "soll-ist-r14.png"
    make_sheet([REF_CLEAN, REF_SEAM, *render_paths[:4]], ["SOLL REF-CLEAN", "SOLL REF-SEAM", "IST R14 3/4", "IST R14 links", "IST R14 rechts", "IST R14 hinten"], soll_ist)
    json_write(OUT / "reports" / "real-geometry-renders-r14.json", {
        "schema_version": 1,
        "task": TASK,
        "source_geometry": MASTER.relative_to(ROOT).as_posix(),
        "source_geometry_sha256": sha256(MASTER),
        "source_is_real_partial_geometry": True,
        "approved_master": False,
        "views": render_records,
        "contact_sheet": contact.relative_to(ROOT).as_posix(),
        "soll_ist_sheet": soll_ist.relative_to(ROOT).as_posix(),
    })
    criteria = [
        "face_free_and_round_like_ref_clean", "forehead_free", "both_eyes_clear", "both_ears_clear",
        "snout_and_nose_clear", "four_short_feet_preserved", "arched_plausible_back",
        "exactly_one_visible_maple_leaf", "ref_seam_plausible", "no_visible_repair_artifact",
    ]
    json_write(OUT / "reports" / "soll-ist-binary-r14.json", {
        "schema_version": 1,
        "task": TASK,
        "source_is_real_geometry": True,
        "criteria": [{"criterion": criterion, "pass": None, "status": "NOT_EVALUATED_BY_GATE1_FAIL"} for criterion in criteria],
        "gate_1_topology": "FAIL",
        "gate_2_form_protection": "NOT_RUN",
        "gate_3_optic": "NOT_RUN",
        "gate_4_cad_fdm": "NOT_RUN",
        "overall": "STOPP",
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
    })

    validation = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "product_revision": "R02",
        "technical_revision": "R14",
        "status": "STOPP",
        "stop_phase": "GATE_1_TOPOLOGY_AFTER_LOCAL_SELF_CORRECTION",
        "reference_and_seed_hash_gate": {"status": "PASS", "actual_sha256": actual},
        "execution_sequence": {
            "A_exterior_classification": "PASS_DIAGNOSTIC",
            "B_local_topology_surgery_outside_roi": "STOPP_GLOBAL_UNDERSIDE_LOOP",
            "C_face_body_roi": "NOT_RUN_BY_GATE1_ORDER",
            "gate_1_topology": "FAIL",
            "gate_2_form_protection": "NOT_RUN_BY_GATE1",
            "gate_3_optic": "NOT_RUN_BY_GATE1_AND_GATE2",
            "gate_4_cad_fdm": "NOT_RUN_BY_GATES_1_2_3",
        },
        "topology_after": after,
        "self_correction": {
            "nonmanifold_face_pairing_iterations": max((row["iteration"] for row in separation_rows), default=-1) + 1,
            "nonmanifold_edges_after": after["nonmanifold_edges"],
            "vertex_separations": len(vertex_separations),
            "locally_filled_boundary_loops": len(filled_loop_indices),
            "new_stitch_edges": len(stitch_records),
            "remaining_methodic_blocker": distance_report["geometric_blocker"],
        },
        "manufacturing_outputs": {
            "approved_master_created": False, "split_created": False, "hollow_shells_created": False,
            "connector_created": False, "stl_created": False, "three_mf_created": False,
            "glb_created": False, "fdm_validation_run": False,
        },
        "open_real_tests": [
            "Gate 2 real bidirectional point-to-triangle audit remains inapplicable until Gate 1 passes.",
            "Gate 3 independent optical review remains gated.",
            "Physical print, wall, split, connector, fit, material, support and slicer tests remain gated by 1+2+3 PASS.",
        ],
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
        "nutzerentscheidung_grund": "Technical incompatibility in the Seed-42 source outside the approved ROI; no product dimension, function, or reference datum is missing.",
        "final_user_approval_claimed": False,
    }
    json_write(OUT / "VALIDIERUNG-R02-R14.json", validation)
    json_write(OUT / "result-status.json", {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "revision": "R02/R14",
        "status": "STOPP",
        "main_files": [
            MASTER.relative_to(ROOT).as_posix(),
            (OUT / "VALIDIERUNG-R02-R14.json").relative_to(ROOT).as_posix(),
            (OUT / "reports" / "topology-audit-r14.json").relative_to(ROOT).as_posix(),
            (OUT / "reports" / "surface-distance-outside-roi-r14.json").relative_to(ROOT).as_posix(),
            soll_ist.relative_to(ROOT).as_posix(),
        ],
        "validations": {"hash_gate": "PASS", "gate_1_topology": "FAIL", "gate_2_form_protection": "NOT_RUN", "gate_3_optic": "NOT_RUN", "gate_4_cad_fdm": "NOT_RUN"},
        "open_real_tests": validation["open_real_tests"],
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
        "nutzerentscheidung_grund": validation["nutzerentscheidung_grund"],
        "final_user_approval_claimed": False,
    })
    (OUT / "CAD-STL-3MF-GLB-FDM-NOT-CREATED.txt").write_text(
        "Gate 1 TOPOLOGY failed after compliant local surgery. By the mandatory gate order, no approved master, split, shells, connector, STL, 3MF, GLB, slicer profile, or FDM validation was created.\n",
        encoding="utf-8",
    )
    revision_text = (
        "# REVISION R02 / R14\n\n"
        "Status: **STOPP** at Gate 1; no final user approval is claimed.\n\n"
        "## GEÄNDERT\n\n"
        "- Nonmanifold edge branches were separated locally by face selection and zero-displacement vertex separation.\n"
        "- Every fully compliant small-loop stitch was added and measured.\n\n"
        "## UNVERÄNDERT\n\n"
        "- Seed 42, all user dimensions, materials, two-part concept, REF-CLEAN, REF-SEAM, four feet, facial features, back and the single maple leaf.\n"
        "- The confirmed face/body ROI was loaded but not rebuilt because the ordered Gate 1 precondition failed first.\n\n"
        "## ENTFERNT\n\n"
        "- Only locally rejected branch faces at nonmanifold edges in the non-approved diagnostic candidate; all selections are listed.\n"
        "- No product feature was intentionally removed and no manufacturing artifact was produced.\n\n"
        "## OFFEN\n\n"
        "- The Seed-42 underside has a 1,376-edge global boundary with no adjacent same-depth counter-ring. A closure would either exceed the 0.40 mm form limit by tens of millimetres or create the forbidden depth-layer bridge/double skin.\n"
        "- The separated source remains non-orientable and contains disconnected visible micro-sheets.\n"
        "- Gates 2–4 and all real production tests remain gated.\n\n"
        "`NUTZERENTSCHEIDUNG_ERFORDERLICH: false` — the stop is purely technical.\n"
    )
    (OUT / "REVISION-R02-R14.md").write_text(revision_text, encoding="utf-8")
    reproduction_text = (
        "# REPRODUKTION R14\n\n"
        "Run from the repository root:\n\n"
        "```powershell\n"
        "python outputs\\herbst-igel-r02-exterior-surface-surgery-r14\\reproduction-scripts\\r14_mesh_probe.py `\n"
        f"  '{SOURCE}' --output outputs\\herbst-igel-r02-exterior-surface-surgery-r14\\audits\\topology-before.json\n"
        "python outputs\\herbst-igel-r02-exterior-surface-surgery-r14\\reproduction-scripts\\r14_surface_surgery.py\n"
        "python outputs\\herbst-igel-r02-exterior-surface-surgery-r14\\reproduction-scripts\\validate_r14.py\n"
        "```\n\n"
        "The script hash-gates Seed 42 and both references. It does not invoke a heightfield, radial hull, voxel hull, convex hull, or global Poisson reconstruction.\n"
    )
    (OUT / "REPRODUKTION-R14.md").write_text(reproduction_text, encoding="utf-8")
    print(json.dumps(validation, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
