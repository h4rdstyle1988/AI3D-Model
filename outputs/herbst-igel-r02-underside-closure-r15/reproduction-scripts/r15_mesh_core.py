#!/usr/bin/env python3
"""Deterministic mesh primitives used by the Herbst-Igel R15 repair.

Only NumPy and Pillow are used so the audit remains reproducible with the
repository's cached toolchain. Coordinates are Seed-42 normalized units;
MM_PER_UNIT maps the maximum model extent to exactly 200 mm.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict, deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


MM_PER_UNIT = 318.2455727028218


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_binary_ply(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with path.open("rb") as stream:
        header: list[str] = []
        while True:
            line = stream.readline()
            if not line:
                raise ValueError("unexpected EOF in PLY header")
            decoded = line.decode("ascii").strip()
            header.append(decoded)
            if decoded == "end_header":
                break
        vertex_count = int(next(x.split()[2] for x in header if x.startswith("element vertex ")))
        face_count = int(next(x.split()[2] for x in header if x.startswith("element face ")))
        vertices = np.fromfile(stream, dtype="<f4", count=vertex_count * 3).reshape((-1, 3)).astype(np.float64)
        raw = np.fromfile(stream, dtype=np.dtype([("n", "u1"), ("v", "<i4", (3,))]), count=face_count)
        if len(raw) != face_count or not np.all(raw["n"] == 3):
            raise ValueError("all PLY faces must be triangles")
        return vertices, raw["v"].astype(np.int64)


def write_binary_ply(path: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "ply\nformat binary_little_endian 1.0\n"
        f"element vertex {len(vertices)}\nproperty float x\nproperty float y\nproperty float z\n"
        f"element face {len(faces)}\nproperty list uchar int vertex_indices\nend_header\n"
    ).encode("ascii")
    packed = np.empty(len(faces), dtype=np.dtype([("n", "u1"), ("v", "<i4", (3,))]))
    packed["n"] = 3
    packed["v"] = np.asarray(faces, dtype=np.int32)
    with path.open("wb") as stream:
        stream.write(header)
        np.asarray(vertices, dtype="<f4").tofile(stream)
        packed.tofile(stream)


def compact_mesh(vertices: np.ndarray, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    used = np.unique(faces)
    remap = np.full(len(vertices), -1, dtype=np.int64)
    remap[used] = np.arange(len(used), dtype=np.int64)
    return vertices[used], remap[faces], used


def face_geometry(vertices: np.ndarray, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    triangles = vertices[faces]
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    double_area = np.linalg.norm(cross, axis=1)
    normals = np.zeros_like(cross)
    valid = double_area > 1e-15
    normals[valid] = cross[valid] / double_area[valid, None]
    return triangles, double_area, normals


def edge_runs(faces: np.ndarray, face_ids: np.ndarray | None = None):
    if face_ids is None:
        face_ids = np.arange(len(faces), dtype=np.int64)
    selected = faces[face_ids]
    directed = selected[:, [[0, 1], [1, 2], [2, 0]]].reshape((-1, 2))
    owners = np.repeat(face_ids, 3)
    signs = directed[:, 0] < directed[:, 1]
    undirected = np.sort(directed, axis=1)
    order = np.lexsort((undirected[:, 1], undirected[:, 0]))
    edges = undirected[order]
    owners = owners[order]
    signs = signs[order]
    change = np.ones(len(edges), dtype=bool)
    change[1:] = np.any(edges[1:] != edges[:-1], axis=1)
    starts = np.flatnonzero(change)
    ends = np.r_[starts[1:], len(edges)]
    return edges, owners, signs, starts, ends, ends - starts


def connected_components(faces: np.ndarray, active: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    if active is None:
        active = np.arange(len(faces), dtype=np.int64)
    edges, owners, _signs, starts, ends, counts = edge_runs(faces, active)
    parent = np.arange(len(faces), dtype=np.int64)
    rank = np.zeros(len(faces), dtype=np.int8)

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = int(parent[a])
        return a

    def union(a: int, b: int) -> None:
        a, b = find(a), find(b)
        if a == b:
            return
        if rank[a] < rank[b]:
            a, b = b, a
        parent[b] = a
        if rank[a] == rank[b]:
            rank[a] += 1

    for start, end, count in zip(starts, ends, counts):
        if count < 2:
            continue
        first = int(owners[start])
        for owner in owners[start + 1 : end]:
            union(first, int(owner))
    roots = np.asarray([find(int(face)) for face in active], dtype=np.int64)
    unique, inverse, counts_out = np.unique(roots, return_inverse=True, return_counts=True)
    labels = np.full(len(faces), -1, dtype=np.int64)
    labels[active] = inverse
    return labels, counts_out


def boundary_loops(faces: np.ndarray) -> tuple[list[np.ndarray], np.ndarray, dict[tuple[int, int], int], dict[int, list[int]]]:
    edges, owners, _signs, starts, _ends, counts = edge_runs(faces)
    single = starts[counts == 1]
    boundary = edges[single]
    owner_by_edge = {tuple(map(int, edge)): int(owners[start]) for edge, start in zip(boundary, single)}
    adjacency: dict[int, list[int]] = defaultdict(list)
    for a, b in boundary:
        adjacency[int(a)].append(int(b))
        adjacency[int(b)].append(int(a))
    loops: list[np.ndarray] = []
    visited: set[tuple[int, int]] = set()
    for a0, b0 in boundary:
        initial = (int(a0), int(b0))
        if tuple(sorted(initial)) in visited:
            continue
        loop = [initial[0]]
        previous, current = initial
        while True:
            visited.add(tuple(sorted((previous, current))))
            loop.append(current)
            neighbours = adjacency[current]
            if len(neighbours) != 2:
                break
            nxt = neighbours[0] if neighbours[0] != previous else neighbours[1]
            if nxt == loop[0]:
                visited.add(tuple(sorted((current, nxt))))
                break
            if tuple(sorted((current, nxt))) in visited:
                break
            previous, current = current, nxt
        loops.append(np.asarray(loop, dtype=np.int64))
    return loops, boundary, owner_by_edge, adjacency


def orientability_constraints(faces: np.ndarray) -> dict[str, object]:
    edges, owners, signs, starts, _ends, counts = edge_runs(faces)
    graph: list[list[tuple[int, int, int]]] = [[] for _ in range(len(faces))]
    manifold_starts = starts[counts == 2]
    for start in manifold_starts:
        a, b = int(owners[start]), int(owners[start + 1])
        required = int(1 ^ int(signs[start]) ^ int(signs[start + 1]))
        graph[a].append((b, required, int(start)))
        graph[b].append((a, required, int(start)))
    parity = np.full(len(faces), -1, dtype=np.int8)
    conflict_starts: set[int] = set()
    component_count = 0
    for seed in range(len(faces)):
        if parity[seed] >= 0:
            continue
        component_count += 1
        parity[seed] = 0
        queue = deque([seed])
        while queue:
            face = queue.popleft()
            for neighbour, required, start in graph[face]:
                wanted = int(parity[face]) ^ required
                if parity[neighbour] < 0:
                    parity[neighbour] = wanted
                    queue.append(neighbour)
                elif int(parity[neighbour]) != wanted:
                    conflict_starts.add(start)
    conflict_edges = edges[np.fromiter(sorted(conflict_starts), dtype=np.int64)] if conflict_starts else np.empty((0, 2), dtype=np.int64)
    conflict_faces = np.unique(np.concatenate([owners[s : s + 2] for s in sorted(conflict_starts)])) if conflict_starts else np.empty(0, dtype=np.int64)
    return {
        "orientable": not conflict_starts,
        "orientation_constraint_conflicts": len(conflict_starts),
        "component_count": component_count,
        "parity": parity,
        "conflict_edges": conflict_edges,
        "conflict_faces": conflict_faces,
    }


def apply_orientation(faces: np.ndarray, parity: np.ndarray) -> np.ndarray:
    result = faces.copy()
    flip = np.flatnonzero(parity == 1)
    result[flip, 1], result[flip, 2] = result[flip, 2].copy(), result[flip, 1].copy()
    return result


def mesh_metrics(vertices: np.ndarray, faces: np.ndarray) -> dict[str, object]:
    _triangles, double_area, _normals = face_geometry(vertices, faces)
    _edges, _owners, _signs, _starts, _ends, counts = edge_runs(faces)
    labels, components = connected_components(faces)
    used = np.unique(faces)
    return {
        "vertices": int(len(vertices)),
        "used_vertices": int(len(used)),
        "triangles": int(len(faces)),
        "boundary_edges": int(np.count_nonzero(counts == 1)),
        "nonmanifold_edges": int(np.count_nonzero(counts > 2)),
        "max_edge_incidence": int(counts.max(initial=0)),
        "degenerate_faces": int(np.count_nonzero(double_area <= 1e-15)),
        "connected_face_surfaces": int(len(components)),
        "largest_surface_faces": int(components.max(initial=0)),
        "surface_area_normalized2": float(0.5 * double_area.sum()),
        "surface_area_mm2": float(0.5 * double_area.sum() * MM_PER_UNIT * MM_PER_UNIT),
        "bounds_min": vertices[used].min(axis=0).tolist(),
        "bounds_max": vertices[used].max(axis=0).tolist(),
        "bounds_min_mm": (vertices[used].min(axis=0) * MM_PER_UNIT).tolist(),
        "bounds_max_mm": (vertices[used].max(axis=0) * MM_PER_UNIT).tolist(),
    }


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


def render(vertices: np.ndarray, faces: np.ndarray, camera: tuple[float, float, float], output: Path, title: str, size: int = 1000) -> None:
    triangles = vertices[faces]
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(cross, axis=1)
    keep = lengths > 1e-14
    centers = triangles.mean(axis=1)[keep]
    normals = cross[keep] / lengths[keep, None]
    model_center = 0.5 * (vertices.min(axis=0) + vertices.max(axis=0))
    centers = centers - model_center
    right, up, forward = camera_basis(camera)
    u, w, depth = centers @ right, centers @ up, centers @ forward
    extent = max(float(np.ptp(u)), float(np.ptp(w))) * 1.12
    scale = (size - 100) / max(extent, 1e-12)
    px = np.clip(np.rint((u - 0.5 * (u.min() + u.max())) * scale + size / 2), 0, size - 1).astype(np.int64)
    py = np.clip(np.rint(size / 2 - (w - 0.5 * (w.min() + w.max())) * scale), 0, size - 1).astype(np.int64)
    flat = py * size + px
    # The camera looks along ``forward``; the smallest projected depth is the
    # first surface hit. Draw far-to-near so the nearest centroid wins.
    order = np.argsort(depth)[::-1]
    chosen: dict[int, int] = {}
    for index in order:
        chosen[int(flat[index])] = int(index)
    image = np.full((size, size, 3), 246, dtype=np.uint8)
    light = np.array([-0.35, -0.45, 0.82], dtype=np.float64)
    light /= np.linalg.norm(light)
    for pixel, index in chosen.items():
        shade = 0.38 + 0.62 * abs(float(normals[index] @ light))
        color = np.clip(np.array([196, 81, 27]) * shade + np.array([40, 18, 8]), 0, 255).astype(np.uint8)
        image[pixel // size, pixel % size] = color
    canvas = Image.fromarray(image, mode="RGB")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, size, 34), fill=(255, 255, 255))
    draw.text((12, 10), title, fill=(20, 20, 20))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)


def make_sheet(paths: list[Path], labels: list[str], output: Path, columns: int = 3) -> None:
    images = [Image.open(path).convert("RGB") for path in paths]
    width = max(image.width for image in images)
    height = max(image.height for image in images)
    rows = math.ceil(len(images) / columns)
    sheet = Image.new("RGB", (columns * width, rows * (height + 30)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (image, label) in enumerate(zip(images, labels)):
        x = index % columns * width
        y = index // columns * (height + 30)
        draw.text((x + 8, y + 8), label, fill=(20, 20, 20))
        sheet.paste(image, (x, y + 30))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
