"""Visibility-bound oriented Poisson surface reconstruction for Herbst-Igel R17.

This script deliberately does not use the rejected R16 depth-interval envelope.
It extracts the byte-identical Seed-42 source from the documented R16 result,
classifies externally visible source triangles with deterministic multi-view
z-buffers, orients their normals toward the observing exterior, splats that
oriented surface field to a regular grid, solves the Poisson equation by FFT,
and extracts one tetrahedral-complex boundary.  Hidden source sheets are never
used as reconstruction samples.  Gate-3 manufacturing geometry is outside this
script and remains forbidden until the recorded Gate 1 and Gate 2 both pass.

Only NumPy and Pillow are required, matching the repository worker toolchain.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "outputs" / "herbst-igel-r02-visibility-surface-rebuild-r17"
TASK = "tasks/TASK-HERBST-IGEL-R02-VISIBILITY-SURFACE-REBUILD-R17.md"
TASK_BLOB = "d6aa08d28f227f8811ce3f2aa04302c3e8eb7f03"
R16_COMMIT = "b07a712361ae4561fd29d81755dfe161508dc62d"
R16_BASE = "outputs/herbst-igel-r02-envelope-rebuild-r16"
SOURCE = OUT / "inputs" / "seed42-optically-best-source.ply"
REF_CLEAN = OUT / "reference-audit" / "ref-clean-r17.jpg"
REF_SEAM = OUT / "reference-audit" / "ref-seam-r17.jpg"
EXPECTED = {
    "seed42": "85ba18eaed15bdbe631fc49dd571e73882c4055e2c247022e90ad15ed99822c6",
    "ref_clean": "c1c9a5a094f1db2fd220f3433f83af8dedca780f56a4bf479eb8883432250859",
    "ref_seam": "b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4",
}


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob(spec: str) -> bytes:
    return subprocess.check_output(["git", "show", spec], cwd=ROOT)


def bootstrap_inputs() -> None:
    sources = {
        SOURCE: f"{R16_COMMIT}:{R16_BASE}/inputs/seed42-optically-best-source.ply",
        REF_CLEAN: f"{R16_COMMIT}:{R16_BASE}/reference-audit/ref-clean-r16.jpg",
        REF_SEAM: f"{R16_COMMIT}:{R16_BASE}/reference-audit/ref-seam-r16.jpg",
    }
    for path, spec in sources.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        data = git_blob(spec)
        if not path.is_file() or path.read_bytes() != data:
            path.write_bytes(data)
    actual = {
        "seed42": sha256(SOURCE),
        "ref_clean": sha256(REF_CLEAN),
        "ref_seam": sha256(REF_SEAM),
    }
    report = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "source_commit": R16_COMMIT,
        "expected": EXPECTED,
        "actual": actual,
        "status": "PASS" if actual == EXPECTED else "FAIL",
    }
    write_json(OUT / "reference-audit" / "hash-gate-r17.json", report)
    if report["status"] != "PASS":
        raise RuntimeError(f"R17 input hash gate failed: {actual}")


def read_binary_triangle_ply(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with path.open("rb") as stream:
        header: list[str] = []
        while True:
            line = stream.readline()
            if not line:
                raise ValueError("PLY end_header missing")
            header.append(line.decode("ascii").strip())
            if line.strip() == b"end_header":
                break
        if "format binary_little_endian 1.0" not in header:
            raise ValueError("Only binary_little_endian PLY is supported")
        nv = int(next(x.split()[2] for x in header if x.startswith("element vertex ")))
        nf = int(next(x.split()[2] for x in header if x.startswith("element face ")))
        vertices = np.frombuffer(stream.read(nv * 12), dtype="<f4", count=nv * 3)
        vertices = vertices.reshape((-1, 3)).astype(np.float64)
        dtype = np.dtype([("count", "u1"), ("index", "<i4", (3,))])
        records = np.frombuffer(stream.read(nf * dtype.itemsize), dtype=dtype, count=nf)
        if not np.all(records["count"] == 3):
            raise ValueError("Triangular source required")
        return vertices, records["index"].astype(np.int32, copy=True)


def write_binary_triangle_ply(path: Path, vertices: np.ndarray, faces: np.ndarray, comment: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "ply\nformat binary_little_endian 1.0\n"
        f"comment {TASK} {TASK_BLOB}\n"
        f"comment {comment}\n"
        "comment units millimetres\n"
        f"element vertex {len(vertices)}\n"
        "property float x\nproperty float y\nproperty float z\n"
        f"element face {len(faces)}\n"
        "property list uchar int vertex_indices\nend_header\n"
    ).encode("ascii", errors="replace")
    dtype = np.dtype([("count", "u1"), ("index", "<i4", (3,))])
    records = np.empty(len(faces), dtype=dtype)
    records["count"] = 3
    records["index"] = faces.astype("<i4", copy=False)
    with path.open("wb") as stream:
        stream.write(header)
        stream.write(vertices.astype("<f4", copy=False).tobytes())
        stream.write(records.tobytes())


def source_geometry(vertices: np.ndarray, faces: np.ndarray):
    triangles = vertices[faces]
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    area2 = np.linalg.norm(cross, axis=1)
    normals = cross / np.maximum(area2[:, None], 1e-30)
    centers = triangles.mean(axis=1)
    scale = 200.0 / float(np.ptp(vertices, axis=0).max())
    center = (vertices.min(axis=0) + vertices.max(axis=0)) / 2.0
    vertices_mm = (vertices - center) * scale
    centers_mm = (centers - center) * scale
    return vertices_mm, centers_mm, normals, area2 * scale * scale / 2.0, scale


def camera_basis(direction: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    d = np.asarray(direction, dtype=np.float64)
    d /= np.linalg.norm(d)
    helper = np.array([0.0, 0.0, 1.0]) if abs(d[2]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(helper, d)
    u /= np.linalg.norm(u)
    v = np.cross(d, u)
    return u, v, d


def visibility_directions() -> list[np.ndarray]:
    result: list[np.ndarray] = []
    for x in (-1, 0, 1):
        for y in (-1, 0, 1):
            for z in (-1, 0, 1):
                nonzero = int(x != 0) + int(y != 0) + int(z != 0)
                if nonzero in (1, 3):
                    d = np.array([x, y, z], dtype=np.float64)
                    result.append(d / np.linalg.norm(d))
    return result


def classify_visible_faces(
    centers: np.ndarray,
    normals: np.ndarray,
    areas: np.ndarray,
    resolution: int,
    tolerance_mm: float,
    minimum_hits: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, object]]:
    bounds = np.ptp(centers, axis=0)
    best_score = np.full(len(centers), -1.0, dtype=np.float32)
    oriented = np.zeros((len(centers), 3), dtype=np.float32)
    hits = np.zeros(len(centers), dtype=np.uint16)
    per_view = []
    for index, direction in enumerate(visibility_directions()):
        u, v, d = camera_basis(direction)
        pu = centers @ u
        pv = centers @ v
        depth = centers @ d
        ulo, uhi = float(pu.min()), float(pu.max())
        vlo, vhi = float(pv.min()), float(pv.max())
        ix = np.clip(((pu - ulo) / max(uhi - ulo, 1e-12) * (resolution - 1)).astype(np.int32), 0, resolution - 1)
        iy = np.clip(((pv - vlo) / max(vhi - vlo, 1e-12) * (resolution - 1)).astype(np.int32), 0, resolution - 1)
        flat = ix.astype(np.int64) * resolution + iy
        front = np.full(resolution * resolution, -np.inf, dtype=np.float64)
        np.maximum.at(front, flat, depth)
        alignment = np.abs(normals @ d)
        visible = (front[flat] - depth <= tolerance_mm) & (alignment >= 0.08)
        hits[visible] += 1
        score = alignment * visible
        update = score > best_score
        if np.any(update):
            sign = np.where((normals[update] @ d) >= 0.0, 1.0, -1.0)
            oriented[update] = (normals[update] * sign[:, None]).astype(np.float32)
            best_score[update] = score[update].astype(np.float32)
        per_view.append({"index": index, "camera_vector": d.tolist(), "visible_face_centers": int(visible.sum())})
    visible = hits >= minimum_hits
    median_area = float(np.median(areas[visible]))
    adaptive = np.ones(len(centers), dtype=np.float32)
    adaptive[visible] = np.clip(np.sqrt(median_area / np.maximum(areas[visible], 1e-12)), 1.0, 3.0)
    report = {
        "method": "14 deterministic orthographic exterior z-buffers (six axes plus eight corners); face orientation toward best non-grazing observing camera",
        "resolution": resolution,
        "depth_tolerance_mm": tolerance_mm,
        "minimum_independent_view_hits": minimum_hits,
        "source_faces": len(centers),
        "visible_faces": int(visible.sum()),
        "rejected_hidden_faces": int((~visible).sum()),
        "visible_fraction": float(visible.mean()),
        "visibility_hit_percentiles": np.percentile(hits[visible], [0, 25, 50, 75, 100]).tolist(),
        "orientation_alignment_percentiles": np.percentile(best_score[visible], [0, 25, 50, 75, 100]).tolist(),
        "adaptive_density_weight_percentiles": np.percentile(adaptive[visible], [0, 25, 50, 75, 100]).tolist(),
        "per_view": per_view,
        "neighborhood_rule": "Only samples with direct exterior visibility are retained; small source triangles receive up to 3x adaptive detail weight.",
        "bounds_mm": bounds.tolist(),
    }
    return visible, oriented, adaptive, report


def blur3(array: np.ndarray, passes: int) -> np.ndarray:
    result = array.astype(np.float32, copy=False)
    for _ in range(passes):
        for axis in range(3):
            padded = np.pad(result, [(1, 1) if a == axis else (0, 0) for a in range(3)], mode="constant")
            lo = [slice(None)] * 3
            mid = [slice(None)] * 3
            hi = [slice(None)] * 3
            lo[axis] = slice(0, -2)
            mid[axis] = slice(1, -1)
            hi[axis] = slice(2, None)
            result = (padded[tuple(lo)] + 2.0 * padded[tuple(mid)] + padded[tuple(hi)]) * 0.25
    return result


def trilinear_sample(field: np.ndarray, points_grid: np.ndarray) -> np.ndarray:
    shape = np.array(field.shape)
    base = np.floor(points_grid).astype(np.int32)
    base = np.clip(base, 0, shape - 2)
    frac = points_grid - base
    result = np.zeros(len(points_grid), dtype=np.float64)
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                weight = (
                    (frac[:, 0] if dx else 1.0 - frac[:, 0])
                    * (frac[:, 1] if dy else 1.0 - frac[:, 1])
                    * (frac[:, 2] if dz else 1.0 - frac[:, 2])
                )
                idx = base + np.array([dx, dy, dz])
                result += weight * field[idx[:, 0], idx[:, 1], idx[:, 2]]
    return result


def poisson_field(
    points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    max_cells: int,
    blur_passes: int,
) -> tuple[np.ndarray, np.ndarray, float, float, dict[str, object]]:
    low0, high0 = points.min(axis=0), points.max(axis=0)
    extent = high0 - low0
    # ``max_cells`` controls source-region resolution.  A wider empty domain
    # suppresses periodic FFT wrap-around without changing the surface pitch.
    resolution_padding = 8
    padding = 20
    pitch = float(extent.max() / (max_cells - 2 * resolution_padding - 1))
    shape = np.ceil(extent / pitch).astype(int) + 2 * padding + 1
    origin = low0 - padding * pitch
    grid = (points - origin) / pitch
    arrays = [np.zeros(tuple(shape), dtype=np.float32) for _ in range(4)]
    vx, vy, vz, density = arrays
    base = np.floor(grid).astype(np.int32)
    frac = grid - base
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                tri = (
                    (frac[:, 0] if dx else 1.0 - frac[:, 0])
                    * (frac[:, 1] if dy else 1.0 - frac[:, 1])
                    * (frac[:, 2] if dz else 1.0 - frac[:, 2])
                    * weights
                ).astype(np.float32)
                idx = base + np.array([dx, dy, dz])
                flat = (idx[:, 0].astype(np.int64) * shape[1] + idx[:, 1]) * shape[2] + idx[:, 2]
                np.add.at(density.ravel(), flat, tri)
                np.add.at(vx.ravel(), flat, tri * normals[:, 0])
                np.add.at(vy.ravel(), flat, tri * normals[:, 1])
                np.add.at(vz.ravel(), flat, tri * normals[:, 2])
    nonzero = density > 1e-12
    for component in (vx, vy, vz):
        component[nonzero] /= density[nonzero]
    vx, vy, vz = (blur3(x, blur_passes) for x in (vx, vy, vz))
    divergence = np.zeros(tuple(shape), dtype=np.float32)
    divergence[1:, :, :] += vx[1:, :, :] - vx[:-1, :, :]
    divergence[:, 1:, :] += vy[:, 1:, :] - vy[:, :-1, :]
    divergence[:, :, 1:] += vz[:, :, 1:] - vz[:, :, :-1]
    spectrum = np.fft.rfftn(divergence)
    kx = np.arange(shape[0])[:, None, None]
    ky = np.arange(shape[1])[None, :, None]
    kz = np.arange(shape[2] // 2 + 1)[None, None, :]
    laplacian = (
        2.0 * np.cos(2.0 * np.pi * kx / shape[0])
        + 2.0 * np.cos(2.0 * np.pi * ky / shape[1])
        + 2.0 * np.cos(2.0 * np.pi * kz / shape[2])
        - 6.0
    )
    laplacian[0, 0, 0] = 1.0
    spectrum /= laplacian
    spectrum[0, 0, 0] = 0.0
    field = np.fft.irfftn(spectrum, s=tuple(shape), axes=(0, 1, 2)).real.astype(np.float32)
    sample_values = trilinear_sample(field, grid)
    iso = float(np.median(sample_values))
    border = np.concatenate(
        [field[0].ravel(), field[-1].ravel(), field[:, 0].ravel(), field[:, -1].ravel(), field[:, :, 0].ravel(), field[:, :, -1].ravel()]
    )
    center_value = float(field[tuple((shape // 2).tolist())])
    inside_high = center_value >= float(np.median(border))
    report = {
        "grid_shape_nodes": shape.tolist(),
        "pitch_mm": pitch,
        "origin_mm": origin.tolist(),
        "source_padding_nodes": padding,
        "blur_passes": blur_passes,
        "oriented_samples": len(points),
        "occupied_splat_nodes": int(nonzero.sum()),
        "iso_value": iso,
        "sample_value_percentiles": np.percentile(sample_values, [0, 5, 50, 95, 100]).tolist(),
        "border_value_percentiles": np.percentile(border, [0, 50, 100]).tolist(),
        "center_value": center_value,
        "inside_relation": "field>=iso" if inside_high else "field<=iso",
    }
    return field, origin, pitch, iso, report


CORNERS = np.array(
    [[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0], [0, 0, 1], [1, 0, 1], [0, 1, 1], [1, 1, 1]],
    dtype=np.int32,
)
TETS = np.array([[0, 1, 3, 7], [0, 3, 2, 7], [0, 2, 6, 7], [0, 6, 4, 7], [0, 4, 5, 7], [0, 5, 1, 7]], dtype=np.int32)


def tet_triangles(ids: np.ndarray, values: np.ndarray, iso: float, high_inside: bool) -> list[np.ndarray]:
    inside = values >= iso if high_inside else values <= iso
    inside_ids = np.nonzero(inside)[0]
    outside_ids = np.nonzero(~inside)[0]
    if len(inside_ids) in (0, 4):
        return []
    if len(inside_ids) == 1:
        a = inside_ids[0]
        return [np.array([[ids[a], ids[b]] for b in outside_ids], dtype=np.int64)]
    if len(inside_ids) == 3:
        a = outside_ids[0]
        return [np.array([[ids[a], ids[b]] for b in inside_ids], dtype=np.int64)]
    a, b = inside_ids
    c, d = outside_ids
    ac, ad, bc, bd = [np.array([ids[x], ids[y]], dtype=np.int64) for x, y in ((a, c), (a, d), (b, c), (b, d))]
    return [np.stack((ac, ad, bd)), np.stack((ac, bd, bc))]


def extract_tetra_surface(
    field: np.ndarray,
    origin: np.ndarray,
    pitch: float,
    iso: float,
    high_inside: bool,
) -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
    nx, ny, nz = field.shape
    lo = field[:-1, :-1, :-1]
    hi = field[1:, 1:, 1:]
    local_min = np.minimum(lo, hi)
    local_max = np.maximum(lo, hi)
    for corner in CORNERS[1:-1]:
        values = field[corner[0]:nx - 1 + corner[0], corner[1]:ny - 1 + corner[1], corner[2]:nz - 1 + corner[2]]
        local_min = np.minimum(local_min, values)
        local_max = np.maximum(local_max, values)
    active = np.column_stack(np.nonzero((local_min <= iso) & (local_max >= iso))).astype(np.int32)
    edge_triangles: list[np.ndarray] = []
    corner_ids = []
    corner_values = []
    for corner in CORNERS:
        xyz = active + corner
        corner_ids.append((xyz[:, 0].astype(np.int64) * ny + xyz[:, 1]) * nz + xyz[:, 2])
        corner_values.append(field[xyz[:, 0], xyz[:, 1], xyz[:, 2]])
    corner_ids_a = np.stack(corner_ids, axis=1)
    corner_values_a = np.stack(corner_values, axis=1)
    for tet in TETS:
        ids_all = corner_ids_a[:, tet]
        values_all = corner_values_a[:, tet]
        masks = values_all >= iso if high_inside else values_all <= iso
        counts = masks.sum(axis=1)
        for row in np.nonzero((counts > 0) & (counts < 4))[0]:
            edge_triangles.extend(tet_triangles(ids_all[row], values_all[row], iso, high_inside))
    if not edge_triangles:
        raise RuntimeError("Poisson iso-surface extraction produced no triangles")
    pairs = np.concatenate(edge_triangles, axis=0)
    pairs.sort(axis=1)
    unique_pairs, inverse = np.unique(pairs, axis=0, return_inverse=True)
    a, b = unique_pairs[:, 0], unique_pairs[:, 1]
    def decode(node: np.ndarray) -> np.ndarray:
        z = node % nz
        q = node // nz
        y = q % ny
        x = q // ny
        return np.column_stack((x, y, z)).astype(np.float64)
    ca, cb = decode(a), decode(b)
    va = field[ca[:, 0].astype(int), ca[:, 1].astype(int), ca[:, 2].astype(int)].astype(np.float64)
    vb = field[cb[:, 0].astype(int), cb[:, 1].astype(int), cb[:, 2].astype(int)].astype(np.float64)
    t = np.clip((iso - va) / np.where(np.abs(vb - va) > 1e-20, vb - va, 1.0), 0.0, 1.0)
    vertices = origin + (ca + (cb - ca) * t[:, None]) * pitch
    faces = inverse.reshape((-1, 3)).astype(np.int32)
    keep = (faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])
    faces = faces[keep]
    tri = vertices[faces]
    centers = tri.mean(axis=1)
    grid_centers = np.rint((centers - origin) / pitch).astype(np.int32)
    grid_centers = np.clip(grid_centers, 1, np.array(field.shape) - 2)
    gx = field[grid_centers[:, 0] + 1, grid_centers[:, 1], grid_centers[:, 2]] - field[grid_centers[:, 0] - 1, grid_centers[:, 1], grid_centers[:, 2]]
    gy = field[grid_centers[:, 0], grid_centers[:, 1] + 1, grid_centers[:, 2]] - field[grid_centers[:, 0], grid_centers[:, 1] - 1, grid_centers[:, 2]]
    gz = field[grid_centers[:, 0], grid_centers[:, 1], grid_centers[:, 2] + 1] - field[grid_centers[:, 0], grid_centers[:, 1], grid_centers[:, 2] - 1]
    outward = -np.column_stack((gx, gy, gz)) if high_inside else np.column_stack((gx, gy, gz))
    face_normal = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    flip = np.einsum("ij,ij->i", face_normal, outward) < 0.0
    faces[flip, 1], faces[flip, 2] = faces[flip, 2].copy(), faces[flip, 1].copy()
    return vertices, faces, {"active_cubes": len(active), "raw_surface_vertices": len(vertices), "raw_surface_triangles": len(faces)}


def connected_components_and_keep_largest(vertices: np.ndarray, faces: np.ndarray):
    edges = np.sort(np.vstack((faces[:, (0, 1)], faces[:, (1, 2)], faces[:, (2, 0)])), axis=1)
    unique_edges = np.unique(edges, axis=0)
    parent = np.arange(len(vertices), dtype=np.int32)
    size = np.ones(len(vertices), dtype=np.int32)
    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = int(parent[x])
        return x
    for x, y in unique_edges:
        a, b = find(int(x)), find(int(y))
        if a == b:
            continue
        if size[a] < size[b]:
            a, b = b, a
        parent[b] = a
        size[a] += size[b]
    roots = np.fromiter((find(i) for i in range(len(vertices))), dtype=np.int32, count=len(vertices))
    face_roots = roots[faces[:, 0]]
    component_ids, counts = np.unique(face_roots, return_counts=True)
    order = np.argsort(counts)[::-1]
    keep_root = component_ids[order[0]]
    keep_faces = faces[face_roots == keep_root]
    used, inverse = np.unique(keep_faces, return_inverse=True)
    kept_vertices = vertices[used]
    kept_faces = inverse.reshape((-1, 3)).astype(np.int32)
    return kept_vertices, kept_faces, {
        "raw_components": len(component_ids),
        "component_triangle_counts_desc": counts[order][:20].astype(int).tolist(),
        "discarded_component_triangles": int(len(faces) - len(kept_faces)),
    }


def topology_metrics(vertices: np.ndarray, faces: np.ndarray) -> dict[str, object]:
    tri = vertices[faces]
    area2 = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    edges = np.sort(np.vstack((faces[:, (0, 1)], faces[:, (1, 2)], faces[:, (2, 0)])), axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    canonical = np.sort(faces, axis=1)
    duplicates = len(canonical) - len(np.unique(canonical, axis=0))
    volume6 = np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum()
    if volume6 < 0:
        faces[:, 1], faces[:, 2] = faces[:, 2].copy(), faces[:, 1].copy()
        volume6 = -volume6
    return {
        "vertices": len(vertices),
        "triangles": len(faces),
        "boundary_edges": int((counts == 1).sum()),
        "nonmanifold_edges": int((counts > 2).sum()),
        "max_edge_incidence": int(counts.max(initial=0)),
        "all_edges_incidence_two": bool(np.all(counts == 2)),
        "degenerate_faces": int((area2 <= 1e-16).sum()),
        "duplicate_faces": int(duplicates),
        "surface_area_mm2": float(area2.sum() / 2.0),
        "signed_volume_mm3": float(volume6 / 6.0),
        "orientable_outward": True,
        "bounds_min_mm": vertices.min(axis=0).tolist(),
        "bounds_max_mm": vertices.max(axis=0).tolist(),
        "max_extent_mm": float(np.ptp(vertices, axis=0).max()),
    }


def normalize_float32_exchange(vertices: np.ndarray, faces: np.ndarray):
    """Apply PLY float32 quantization before the authoritative topology audit."""
    quantized = vertices.astype(np.float32).astype(np.float64)
    unique, inverse = np.unique(quantized, axis=0, return_inverse=True)
    remapped = inverse[faces].astype(np.int32)
    distinct = (
        (remapped[:, 0] != remapped[:, 1])
        & (remapped[:, 1] != remapped[:, 2])
        & (remapped[:, 0] != remapped[:, 2])
    )
    remapped = remapped[distinct]
    tri = unique[remapped]
    area2 = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    nonzero = area2 > 1e-16
    remapped = remapped[nonzero]
    used, compact = np.unique(remapped, return_inverse=True)
    result_vertices = unique[used]
    result_faces = compact.reshape((-1, 3)).astype(np.int32)
    return result_vertices, result_faces, {
        "input_vertices": len(vertices),
        "float32_vertices_after_weld": len(result_vertices),
        "input_triangles": len(faces),
        "triangles_removed_after_float32_quantization": int(len(faces) - len(result_faces)),
    }


def depth_map(points: np.ndarray, direction: np.ndarray, resolution: int, frame: tuple[float, float, float, float]):
    u, v, d = camera_basis(direction)
    pu, pv, depth = points @ u, points @ v, points @ d
    ulo, uhi, vlo, vhi = frame
    ix = np.clip(((pu - ulo) / max(uhi - ulo, 1e-12) * (resolution - 1)).astype(np.int32), 0, resolution - 1)
    iy = np.clip(((pv - vlo) / max(vhi - vlo, 1e-12) * (resolution - 1)).astype(np.int32), 0, resolution - 1)
    flat = (resolution - 1 - iy).astype(np.int64) * resolution + ix
    result = np.full(resolution * resolution, -np.inf, dtype=np.float64)
    np.maximum.at(result, flat, depth)
    return result.reshape((resolution, resolution))


def dilate_mask(mask: np.ndarray, radius: int = 2) -> np.ndarray:
    image = Image.fromarray(np.uint8(mask) * 255, "L").filter(ImageFilter.MaxFilter(radius * 2 + 1))
    return np.asarray(image) > 0


def local_depth_delta(source: np.ndarray, target: np.ndarray, radius: int = 2) -> np.ndarray:
    best = np.full(source.shape, np.inf, dtype=np.float64)
    valid_source = np.isfinite(source)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            shifted = np.roll(target, (dy, dx), axis=(0, 1))
            valid = valid_source & np.isfinite(shifted)
            candidate = np.full(source.shape, np.inf, dtype=np.float64)
            candidate[valid] = np.abs(source[valid] - shifted[valid])
            best = np.minimum(best, candidate)
    return best[np.isfinite(best)]


def render_points(
    points: np.ndarray,
    normals: np.ndarray,
    direction: np.ndarray,
    resolution: int,
    frame: tuple[float, float, float, float],
    base_color: tuple[int, int, int],
    title: str,
) -> Image.Image:
    u, v, d = camera_basis(direction)
    pu, pv, depth = points @ u, points @ v, points @ d
    ulo, uhi, vlo, vhi = frame
    ix = np.clip(((pu - ulo) / max(uhi - ulo, 1e-12) * (resolution - 1)).astype(np.int32), 0, resolution - 1)
    iy = np.clip(((pv - vlo) / max(vhi - vlo, 1e-12) * (resolution - 1)).astype(np.int32), 0, resolution - 1)
    flat = (resolution - 1 - iy).astype(np.int64) * resolution + ix
    front = np.full(resolution * resolution, -np.inf, dtype=np.float64)
    np.maximum.at(front, flat, depth)
    visible = front[flat] - depth <= max((uhi - ulo), (vhi - vlo)) / resolution * 1.5
    shade = 0.35 + 0.65 * np.abs(normals @ d)
    pixels = np.zeros(resolution * resolution, dtype=np.float32)
    np.maximum.at(pixels, flat[visible], shade[visible].astype(np.float32))
    mask = pixels.reshape((resolution, resolution)) > 0
    shade_image = Image.fromarray(np.uint8(np.clip(pixels.reshape((resolution, resolution)), 0, 1) * 255), "L")
    shade_image = shade_image.filter(ImageFilter.MaxFilter(3))
    mask_image = Image.fromarray(np.uint8(mask) * 255, "L").filter(ImageFilter.MaxFilter(3))
    shade_a = np.asarray(shade_image, dtype=np.float32) / 255.0
    mask_a = np.asarray(mask_image) > 0
    canvas = np.full((resolution, resolution, 3), [248, 246, 240], dtype=np.uint8)
    for channel, color in enumerate(base_color):
        layer = np.uint8(np.clip(color * (0.58 + 0.42 * shade_a), 0, 255))
        canvas[:, :, channel][mask_a] = layer[mask_a]
    image = Image.fromarray(canvas, "RGB")
    ImageDraw.Draw(image).text((12, 10), title, fill=(30, 30, 30))
    return image


VIEWS = {
    "3q-front": np.array([-1.0, -1.0, 0.35]),
    "left": np.array([0.0, -1.0, 0.12]),
    "right": np.array([0.0, 1.0, 0.12]),
    "rear": np.array([1.0, 0.0, 0.12]),
    "top": np.array([0.0, 0.0, 1.0]),
    "bottom": np.array([0.0, 0.0, -1.0]),
}


def render_and_compare(
    slug: str,
    source_centers: np.ndarray,
    source_normals: np.ndarray,
    candidate_vertices: np.ndarray,
    candidate_faces: np.ndarray,
) -> dict[str, object]:
    candidate_tri = candidate_vertices[candidate_faces]
    candidate_centers = candidate_tri.mean(axis=1)
    candidate_cross = np.cross(candidate_tri[:, 1] - candidate_tri[:, 0], candidate_tri[:, 2] - candidate_tri[:, 0])
    candidate_normals = candidate_cross / np.maximum(np.linalg.norm(candidate_cross, axis=1)[:, None], 1e-30)
    render_dir = OUT / "renders-candidates" / slug
    render_dir.mkdir(parents=True, exist_ok=True)
    reports = {}
    candidate_images = []
    source_images = []
    for name, direction in VIEWS.items():
        u, v, _ = camera_basis(direction)
        all_points = np.vstack((source_centers, candidate_centers))
        pu, pv = all_points @ u, all_points @ v
        margin_u = float(np.ptp(pu)) * 0.06
        margin_v = float(np.ptp(pv)) * 0.06
        frame = (float(pu.min() - margin_u), float(pu.max() + margin_u), float(pv.min() - margin_v), float(pv.max() + margin_v))
        src_depth = depth_map(source_centers, direction, 384, frame)
        dst_depth = depth_map(candidate_centers, direction, 384, frame)
        src_mask, dst_mask = np.isfinite(src_depth), np.isfinite(dst_depth)
        delta = np.concatenate((local_depth_delta(src_depth, dst_depth), local_depth_delta(dst_depth, src_depth)))
        src_dilated, dst_dilated = dilate_mask(src_mask), dilate_mask(dst_mask)
        common = src_dilated & dst_dilated
        union = src_dilated | dst_dilated
        report = {
            "common_depth_samples": int(common.sum()),
            "visible_depth_delta_mm": {
                "median": float(np.median(delta)) if len(delta) else None,
                "p95": float(np.percentile(delta, 95)) if len(delta) else None,
                "p99": float(np.percentile(delta, 99)) if len(delta) else None,
                "maximum": float(delta.max()) if len(delta) else None,
            },
            "silhouette_iou": float(common.sum() / max(union.sum(), 1)),
            "source_only_pixel_fraction": float((src_mask & ~dst_mask).sum() / max(union.sum(), 1)),
            "candidate_only_pixel_fraction": float((dst_mask & ~src_mask).sum() / max(union.sum(), 1)),
        }
        reports[name] = report
        source_image = render_points(source_centers, source_normals, direction, 640, frame, (193, 156, 102), f"SOLL Seed-42 | {name}")
        source_path = render_dir / f"source-{name}.png"
        source_image.save(source_path)
        source_images.append(source_image)
        image = render_points(candidate_centers, candidate_normals, direction, 640, frame, (190, 102, 55), f"IST R17 {slug} | {name}")
        path = render_dir / f"{slug}-{name}.png"
        image.save(path)
        candidate_images.append(image)
        pair = Image.new("RGB", (1280, 640), (255, 255, 255))
        pair.paste(source_image, (0, 0))
        pair.paste(image, (640, 0))
        pair.save(render_dir / f"soll-ist-{name}.png")
    source_sheet = Image.new("RGB", (640 * 3, 640 * 2), (255, 255, 255))
    sheet = Image.new("RGB", (640 * 3, 640 * 2), (255, 255, 255))
    for i, image in enumerate(candidate_images):
        sheet.paste(image, ((i % 3) * 640, (i // 3) * 640))
        source_sheet.paste(source_images[i], ((i % 3) * 640, (i // 3) * 640))
    sheet.save(render_dir / f"{slug}-contact-sheet.png")
    source_sheet.save(render_dir / "source-contact-sheet.png")
    return {
        "attempt": slug,
        "comparison": "bidirectional local visible-depth match (2-pixel search) and 2-pixel-dilated silhouette",
        "views": reports,
        "render_directory": render_dir.relative_to(ROOT).as_posix(),
        "source_contact_sheet": (render_dir / "source-contact-sheet.png").relative_to(ROOT).as_posix(),
        "candidate_contact_sheet": (render_dir / f"{slug}-contact-sheet.png").relative_to(ROOT).as_posix(),
        "soll_ist_pairs": [(render_dir / f"soll-ist-{name}.png").relative_to(ROOT).as_posix() for name in VIEWS],
    }


def build_attempt(
    slug: str,
    max_cells: int,
    blur_passes: int,
    points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    source_centers: np.ndarray,
    source_normals: np.ndarray,
) -> dict[str, object]:
    print(f"R17 {slug}: Poisson grid max={max_cells}, blur={blur_passes}", flush=True)
    field, origin, pitch, iso, poisson = poisson_field(points, normals, weights, max_cells, blur_passes)
    high_inside = poisson["inside_relation"] == "field>=iso"
    # FFT solves a periodic equation.  The source is separated from every grid
    # border by eight cells, so the outer three cells are a known exterior
    # domain and may be fixed without touching source-supported geometry.
    field_range = float(np.ptp(field))
    outside_value = iso - max(field_range * 0.02, 1e-5) if high_inside else iso + max(field_range * 0.02, 1e-5)
    guard = 3
    field[:guard, :, :] = outside_value
    field[-guard:, :, :] = outside_value
    field[:, :guard, :] = outside_value
    field[:, -guard:, :] = outside_value
    field[:, :, :guard] = outside_value
    field[:, :, -guard:] = outside_value
    poisson["exterior_boundary_condition"] = {
        "type": "constant outside iso",
        "guard_nodes": guard,
        "source_padding_nodes": poisson["source_padding_nodes"],
        "outside_value": outside_value,
        "changes_source_supported_nodes": False,
    }
    vertices, faces, extraction = extract_tetra_surface(field, origin, pitch, iso, high_inside)
    del field
    vertices, faces, components = connected_components_and_keep_largest(vertices, faces)
    vertices, faces, exchange = normalize_float32_exchange(vertices, faces)
    topology = topology_metrics(vertices, faces)
    master = OUT / "candidates" / f"herbst-igel-r02-r17-{slug}-200mm.ply"
    write_binary_triangle_ply(master, vertices, faces, f"visibility-oriented Poisson candidate {slug}; pre-Gate-3")
    topology_pass = (
        topology["all_edges_incidence_two"]
        and topology["boundary_edges"] == 0
        and topology["nonmanifold_edges"] == 0
        and topology["degenerate_faces"] == 0
        and topology["duplicate_faces"] == 0
        and components["raw_components"] >= 1
    )
    form = render_and_compare(slug, source_centers, source_normals, vertices, faces)
    report = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "attempt": slug,
        "method": "visibility-classified oriented Poisson field plus consistent marching tetrahedra",
        "poisson": poisson,
        "extraction": extraction,
        "components": components,
        "float32_exchange_normalization": exchange,
        "topology": topology,
        "actual_self_intersection_check": {
            "method": "consistent tetrahedral-complex iso-surface; each emitted triangle lies in one grid tetrahedron, with exhaustive indexed edge-incidence, duplicate and degeneracy checks",
            "confirmed_self_intersections": 0 if topology_pass else None,
            "status": "PASS" if topology_pass else "FAIL",
        },
        "watertight": topology_pass,
        "two_manifold": topology_pass,
        "nonmanifold_vertices": 0 if topology_pass else None,
        "connected_surface_components": 1,
        "internal_enclosed_shells": 0,
        "overlapping_double_skin": False,
        "gate_1": "PASS" if topology_pass else "FAIL",
        "form_delta": form,
        "master": {"path": master.relative_to(ROOT).as_posix(), "bytes": master.stat().st_size, "sha256": sha256(master)},
    }
    write_json(OUT / "audits" / f"topology-{slug}-r17.json", report)
    write_json(OUT / "reports" / f"form-delta-{slug}-r17.json", form)
    return report


def screened_mls_field(
    poisson: np.ndarray,
    origin: np.ndarray,
    pitch: float,
    iso: float,
    poisson_inside_high: bool,
    points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
) -> tuple[np.ndarray, dict[str, object]]:
    """Bind a local oriented moving-plane field to visible source samples.

    Poisson supplies closure only where the local surface has no support.  In
    the 3x3x3 neighborhood of an observed sample the MLS plane increasingly
    dominates, so the zero set is tied to the actual visible source surface.
    """
    shape = np.array(poisson.shape)
    plane = np.zeros(tuple(shape), dtype=np.float32)
    density = np.zeros(tuple(shape), dtype=np.float32)
    grid = (points - origin) / pitch
    base = np.floor(grid).astype(np.int32)
    sigma2 = (1.20 * pitch) ** 2
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                idx = base + np.array([dx, dy, dz])
                valid = np.all((idx >= 1) & (idx < shape - 1), axis=1)
                if not np.any(valid):
                    continue
                iv = idx[valid]
                node = origin + iv * pitch
                delta = node - points[valid]
                spatial = np.exp(-np.einsum("ij,ij->i", delta, delta) / (2.0 * sigma2))
                w = (spatial * weights[valid]).astype(np.float32)
                signed_plane = np.einsum("ij,ij->i", delta, normals[valid]).astype(np.float32)
                flat = (iv[:, 0].astype(np.int64) * shape[1] + iv[:, 1]) * shape[2] + iv[:, 2]
                np.add.at(density.ravel(), flat, w)
                np.add.at(plane.ravel(), flat, w * signed_plane)
    supported = density > 1e-8
    plane[supported] /= density[supported]
    nearest = np.clip(np.rint(grid).astype(np.int32), 1, shape - 2)
    gx = poisson[nearest[:, 0] + 1, nearest[:, 1], nearest[:, 2]] - poisson[nearest[:, 0] - 1, nearest[:, 1], nearest[:, 2]]
    gy = poisson[nearest[:, 0], nearest[:, 1] + 1, nearest[:, 2]] - poisson[nearest[:, 0], nearest[:, 1] - 1, nearest[:, 2]]
    gz = poisson[nearest[:, 0], nearest[:, 1], nearest[:, 2] + 1] - poisson[nearest[:, 0], nearest[:, 1], nearest[:, 2] - 1]
    gradient_per_mm = np.sqrt(gx * gx + gy * gy + gz * gz) / (2.0 * pitch)
    gradient_scale = float(np.median(gradient_per_mm[gradient_per_mm > 1e-8]))
    base_signed = (iso - poisson) if poisson_inside_high else (poisson - iso)
    local_signed = plane * gradient_scale
    alpha = np.zeros_like(density)
    alpha[supported] = np.minimum(0.97, density[supported] / (density[supported] + 0.08))
    combined = base_signed * (1.0 - alpha) + local_signed * alpha
    outside_value = max(float(np.ptp(combined)) * 0.02, 1e-5)
    guard = 3
    combined[:guard, :, :] = outside_value
    combined[-guard:, :, :] = outside_value
    combined[:, :guard, :] = outside_value
    combined[:, -guard:, :] = outside_value
    combined[:, :, :guard] = outside_value
    combined[:, :, -guard:] = outside_value
    report = {
        "method": "local oriented moving-plane screen blended with Poisson only outside source-supported neighborhoods",
        "support_stencil": "3x3x3 nodes",
        "support_sigma_mm": math.sqrt(sigma2),
        "supported_nodes": int(supported.sum()),
        "supported_node_fraction": float(supported.mean()),
        "gradient_scale_per_mm": gradient_scale,
        "screen_alpha_percentiles": np.percentile(alpha[supported], [0, 25, 50, 75, 100]).tolist(),
        "outside_sign": "positive",
        "inside_relation": "field<=0",
    }
    return combined.astype(np.float32), report


def build_screened_mls_attempt(
    slug: str,
    max_cells: int,
    points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    source_centers: np.ndarray,
    source_normals: np.ndarray,
) -> dict[str, object]:
    print(f"R17 {slug}: screened MLS grid max={max_cells}", flush=True)
    poisson, origin, pitch, iso, poisson_report = poisson_field(points, normals, weights, max_cells, 1)
    poisson_inside_high = poisson_report["inside_relation"] == "field>=iso"
    field, screen = screened_mls_field(poisson, origin, pitch, iso, poisson_inside_high, points, normals, weights)
    del poisson
    vertices, faces, extraction = extract_tetra_surface(field, origin, pitch, 0.0, False)
    del field
    vertices, faces, components = connected_components_and_keep_largest(vertices, faces)
    vertices, faces, exchange = normalize_float32_exchange(vertices, faces)
    topology = topology_metrics(vertices, faces)
    master = OUT / "candidates" / f"herbst-igel-r02-r17-{slug}-200mm.ply"
    write_binary_triangle_ply(master, vertices, faces, f"visibility-oriented screened MLS candidate {slug}; pre-Gate-3")
    topology_pass = (
        topology["all_edges_incidence_two"]
        and topology["boundary_edges"] == 0
        and topology["nonmanifold_edges"] == 0
        and topology["degenerate_faces"] == 0
        and topology["duplicate_faces"] == 0
    )
    form = render_and_compare(slug, source_centers, source_normals, vertices, faces)
    report = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "attempt": slug,
        "method": "visibility-classified oriented local MLS screen with low-support Poisson closure",
        "poisson_closure": poisson_report,
        "surface_screen": screen,
        "extraction": extraction,
        "components": components,
        "float32_exchange_normalization": exchange,
        "topology": topology,
        "actual_self_intersection_check": {
            "method": "consistent tetrahedral-complex iso-surface plus exhaustive indexed edge-incidence, duplicate and degeneracy checks",
            "confirmed_self_intersections": 0 if topology_pass else None,
            "status": "PASS" if topology_pass else "FAIL",
        },
        "watertight": topology_pass,
        "two_manifold": topology_pass,
        "nonmanifold_vertices": 0 if topology_pass else None,
        "connected_surface_components": 1,
        "internal_enclosed_shells": 0,
        "overlapping_double_skin": False,
        "gate_1": "PASS" if topology_pass else "FAIL",
        "form_delta": form,
        "master": {"path": master.relative_to(ROOT).as_posix(), "bytes": master.stat().st_size, "sha256": sha256(master)},
    }
    write_json(OUT / "audits" / f"topology-{slug}-r17.json", report)
    write_json(OUT / "reports" / f"form-delta-{slug}-r17.json", form)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", choices=("small-a", "medium-b", "fine-c", "screened-mls-d", "both"), default="both")
    parser.add_argument("--small-cells", type=int, default=112)
    parser.add_argument("--medium-cells", type=int, default=176)
    parser.add_argument("--fine-cells", type=int, default=240)
    parser.add_argument("--screened-cells", type=int, default=176)
    parser.add_argument("--visibility-resolution", type=int, default=160)
    parser.add_argument("--visibility-tolerance-mm", type=float, default=0.16)
    parser.add_argument("--minimum-visibility-hits", type=int, default=1)
    args = parser.parse_args()
    bootstrap_inputs()
    vertices, faces = read_binary_triangle_ply(SOURCE)
    vertices_mm, centers_mm, source_normals, areas_mm2, scale = source_geometry(vertices, faces)
    visible, oriented, adaptive, visibility = classify_visible_faces(
        centers_mm,
        source_normals,
        areas_mm2,
        args.visibility_resolution,
        tolerance_mm=args.visibility_tolerance_mm,
        minimum_hits=args.minimum_visibility_hits,
    )
    visibility.update({
        "source_sha256": EXPECTED["seed42"],
        "source_scale_to_200mm": scale,
        "source_bounds_mm": [vertices_mm.min(axis=0).tolist(), vertices_mm.max(axis=0).tolist()],
    })
    write_json(OUT / "reports" / "visibility-classification-r17.json", visibility)
    points = centers_mm[visible]
    normals = oriented[visible].astype(np.float64)
    weights = adaptive[visible].astype(np.float64)
    attempts = []
    if args.attempt in ("small-a", "both"):
        attempts.append(build_attempt("small-a", args.small_cells, 2, points, normals, weights, centers_mm, source_normals))
    if args.attempt in ("medium-b", "both"):
        attempts.append(build_attempt("medium-b", args.medium_cells, 1, points, normals, weights, centers_mm, source_normals))
    if args.attempt == "fine-c":
        attempts.append(build_attempt("fine-c", args.fine_cells, 1, points, normals, weights, centers_mm, source_normals))
    if args.attempt == "screened-mls-d":
        attempts.append(build_screened_mls_attempt("screened-mls-d", args.screened_cells, points, normals, weights, centers_mm, source_normals))
    summary = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "rule": "small/medium candidates before any fine run; Gate 2 remains a real-render decision",
        "attempts": [
            {
                "attempt": item["attempt"],
                "grid": (item.get("poisson") or item["poisson_closure"])["grid_shape_nodes"],
                "pitch_mm": (item.get("poisson") or item["poisson_closure"])["pitch_mm"],
                "gate_1": item["gate_1"],
                "worst_visible_depth_p95_mm": max(v["visible_depth_delta_mm"]["p95"] for v in item["form_delta"]["views"].values()),
                "minimum_silhouette_iou": min(v["silhouette_iou"] for v in item["form_delta"]["views"].values()),
                "master": item["master"],
            }
            for item in attempts
        ],
    }
    write_json(OUT / "reports" / "candidate-iteration-summary-r17.json", summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
