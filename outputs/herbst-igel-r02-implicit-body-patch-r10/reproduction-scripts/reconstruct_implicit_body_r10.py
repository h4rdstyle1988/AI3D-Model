#!/usr/bin/env python3
"""Build two local smooth implicit body reconstructions for Herbst-Igel R10.

The byte-identical Seed-42 PLY is the only geometry source.  Source vertex
coordinates are never modified.  Source triangles are removed only in the
R08/R09 REF-SEAM body problem mask above the unchanged lower-body guard.

Two independent scalar fields are evaluated and iso-surfaced with marching
tetrahedra:

* ``sdf``: a Gaussian-smoothed signed-distance visual hull;
* ``rbf``: a Gaussian radial-basis interpolation of that measured field.

Both fields use the unchanged R09 robust depth measurement.  The generated
surface is low-frequency body skin only; no feature geometry is invented.
Existing Seed-42 ears, eyes, nose/snout cores and feet are retained as source
triangles near the implicit exterior.  The result remains an optical-gate
candidate until the real-geometry renders have been inspected.
"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
SOURCE = OUT / "source-seed42" / "herbst-igel-r02-trellis-raw-seed-42.ply"
SEAM_IMAGE = OUT / "reference-audit" / "ref-seam-r10.jpg"
REPORT = OUT / "reports" / "implicit-reconstruction-r10.json"
DIAGNOSTIC = OUT / "diagnostics" / "problem-mask-and-controls-r10.png"
TASK = "tasks/TASK-HERBST-IGEL-R02-IMPLICIT-BODY-PATCH-R10.md"
TASK_BLOB = "18406bd6fc9d50ad033ed7cc41d1d5a8fe257383"
EXPECTED_SOURCE_SHA256 = "85ba18eaed15bdbe631fc49dd571e73882c4055e2c247022e90ad15ed99822c6"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def read_binary_ply(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with path.open("rb") as stream:
        header_lines: list[bytes] = []
        while True:
            line = stream.readline()
            if not line:
                raise ValueError("PLY header ended unexpectedly")
            header_lines.append(line)
            if line.strip() == b"end_header":
                break
        header = b"".join(header_lines).decode("ascii")
        if "format binary_little_endian 1.0" not in header:
            raise ValueError("Only binary little-endian PLY is supported")
        vertex_count = int(next(x.split()[2] for x in header.splitlines() if x.startswith("element vertex ")))
        face_count = int(next(x.split()[2] for x in header.splitlines() if x.startswith("element face ")))
        vertices = np.fromfile(stream, dtype="<f4", count=vertex_count * 3).reshape(vertex_count, 3)
        face_dtype = np.dtype([("count", "u1"), ("indices", "<i4", (3,))])
        records = np.fromfile(stream, dtype=face_dtype, count=face_count)
    if not np.all(records["count"] == 3):
        raise ValueError("Source contains non-triangular faces")
    return vertices, records["indices"].astype(np.int64)


def write_binary_ply(path: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "ply\nformat binary_little_endian 1.0\n"
        f"element vertex {len(vertices)}\n"
        "property float x\nproperty float y\nproperty float z\n"
        f"element face {len(faces)}\n"
        "property list uchar int vertex_indices\nend_header\n"
    ).encode("ascii")
    records = np.empty(len(faces), dtype=np.dtype([("count", "u1"), ("indices", "<i4", (3,))]))
    records["count"] = 3
    records["indices"] = np.asarray(faces, dtype="<i4")
    with path.open("wb") as stream:
        stream.write(header)
        np.asarray(vertices, dtype="<f4").tofile(stream)
        records.tofile(stream)


def reference_masks() -> tuple[np.ndarray, np.ndarray, list[int], np.ndarray]:
    """Reproduce the unchanged R08/R09 REF-SEAM body-mask transfer."""
    rgb = np.asarray(Image.open(SEAM_IMAGE).convert("RGB"), dtype=np.int16)
    red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    blue_mask = (blue > 120) & (blue > red + 35) & (blue > green + 15)
    channel_span = rgb.max(axis=2) - rgb.min(axis=2)
    foreground = (rgb.mean(axis=2) < 238) & ((channel_span > 12) | (rgb.mean(axis=2) < 210))
    foreground = np.asarray(Image.fromarray((foreground * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(7))) > 0
    yy, xx = np.nonzero(foreground)
    bbox = [int(xx.min()), int(yy.min()), int(xx.max()), int(yy.max())]

    path_mask = np.asarray(Image.fromarray((blue_mask * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))) > 0
    sy, sx = np.unravel_index(
        np.argmin(np.where(path_mask, np.indices(path_mask.shape)[1], 10_000)), path_mask.shape
    )
    bottom_y = int(np.nonzero(path_mask)[0].max())
    bottom_xs = np.nonzero(path_mask[bottom_y])[0]
    ey, ex = bottom_y, int(np.median(bottom_xs))
    parent: dict[tuple[int, int], tuple[int, int] | None] = {(int(sy), int(sx)): None}
    queue: deque[tuple[int, int]] = deque([(int(sy), int(sx))])
    height, width = path_mask.shape
    while queue and (ey, ex) not in parent:
        y, x = queue.popleft()
        for dy, dx in ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)):
            node = (y + dy, x + dx)
            if 0 <= node[0] < height and 0 <= node[1] < width and path_mask[node] and node not in parent:
                parent[node] = (y, x)
                queue.append(node)
    if (ey, ex) not in parent:
        raise ValueError("Blue REF-SEAM is not a connected top-to-bottom path")
    seam_path: list[tuple[int, int]] = []
    node: tuple[int, int] | None = (ey, ex)
    while node is not None:
        seam_path.append((node[1], node[0]))
        node = parent[node]
    seam_path.reverse()
    x0, y0, _x1, y1 = bbox
    polygon = seam_path + [(x0, y1), (x0, y0)]
    body_image = Image.new("L", (width, height), 0)
    ImageDraw.Draw(body_image).polygon(polygon, fill=255)
    body = (np.asarray(body_image) > 0) & foreground
    return blue_mask, body, bbox, rgb.astype(np.uint8)


def feature_masks(shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[dict[str, object]]]:
    """Use only the measured R08/R09 feature guards; do not add semantics."""
    height, width = shape
    image = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(image)
    features = [
        {"name": "front_ear", "center_px": [103, 154], "radius_px": 24},
        {"name": "reference_side_ear", "center_px": [226, 174], "radius_px": 30},
        {"name": "front_eye", "center_px": [111, 210], "radius_px": 18},
        {"name": "reference_side_eye", "center_px": [205, 207], "radius_px": 19},
        {"name": "nose", "center_px": [79, 231], "radius_px": 23},
        {"name": "front_foot", "center_px": [124, 300], "radius_px": 30},
        {"name": "reference_side_foot", "center_px": [212, 306], "radius_px": 34},
    ]
    for feature in features:
        x, y = feature["center_px"]
        radius = feature["radius_px"]
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)
    full = np.asarray(image) > 0
    core = np.asarray(image.filter(ImageFilter.MinFilter(9))) > 0
    # Only the eyes and nose need a viewing window through the low-frequency
    # implicit skin.  Ears project outside the skin and feet remain below the
    # lower guard, so carving those would create unnecessary openings.
    window_image = Image.new("L", (width, height), 0)
    window_draw = ImageDraw.Draw(window_image)
    for feature in features:
        if feature["name"] not in {"front_eye", "reference_side_eye", "nose"}:
            continue
        x, y = feature["center_px"]
        radius = feature["radius_px"]
        window_draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)
    windows = np.asarray(window_image.filter(ImageFilter.MinFilter(9))) > 0
    return full, core, windows, features


def project_xz(points: np.ndarray, bounds_min: np.ndarray, bounds_max: np.ndarray, bbox: list[int]) -> tuple[np.ndarray, np.ndarray]:
    x0, y0, x1, y1 = bbox
    u = x0 + (points[:, 0] - bounds_min[0]) / (bounds_max[0] - bounds_min[0]) * (x1 - x0)
    v = y1 - (points[:, 2] - bounds_min[2]) / (bounds_max[2] - bounds_min[2]) * (y1 - y0)
    return u, v


def grid_distance_to_false(mask: np.ndarray) -> np.ndarray:
    """Exact 4-neighbour distance transform; deterministic NumPy/Python fallback."""
    height, width = mask.shape
    distance = np.full((height, width), 32767, dtype=np.int16)
    queue: deque[tuple[int, int]] = deque()
    for y, x in zip(*np.nonzero(~mask)):
        distance[y, x] = 0
        queue.append((int(y), int(x)))
    while queue:
        y, x = queue.popleft()
        candidate = int(distance[y, x]) + 1
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < height and 0 <= nx < width and candidate < distance[ny, nx]:
                distance[ny, nx] = candidate
                queue.append((ny, nx))
    return distance.astype(np.float64)


def gaussian_blur(array: np.ndarray, sigma: float) -> np.ndarray:
    radius = max(1, int(np.ceil(3.0 * sigma)))
    axis = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-0.5 * (axis / sigma) ** 2)
    kernel /= kernel.sum()
    padded = np.pad(array, ((0, 0), (radius, radius)), mode="edge")
    horizontal = sum(kernel[index] * padded[:, index : index + array.shape[1]] for index in range(len(kernel)))
    padded = np.pad(horizontal, ((radius, radius), (0, 0)), mode="edge")
    return sum(kernel[index] * padded[index : index + array.shape[0], :] for index in range(len(kernel)))


def signed_distance_field(body: np.ndarray) -> np.ndarray:
    inside = grid_distance_to_false(body)
    outside = grid_distance_to_false(~body)
    signed = inside - outside
    smooth = gaussian_blur(signed, 4.0)
    scale = max(float(np.quantile(smooth[body], 0.98)), 1.0)
    return np.clip(smooth / scale, -0.75, 1.15)


def rbf_field(signed: np.ndarray, bbox: list[int]) -> tuple[np.ndarray, dict[str, object]]:
    """Interpolate the measured signed field with Gaussian radial bases."""
    height, width = signed.shape
    x0, y0, x1, y1 = bbox
    xs = np.linspace(max(0, x0 - 12), min(width - 1, x1 + 12), 18)
    ys = np.linspace(max(0, y0 - 12), min(height - 1, y1 + 12), 18)
    cx, cy = np.meshgrid(xs, ys)
    controls_px = np.column_stack((cx.ravel(), cy.ravel()))
    controls = np.column_stack((controls_px[:, 0] / (width - 1), controls_px[:, 1] / (height - 1)))
    targets = bilinear_sample(signed, controls_px[:, 0], controls_px[:, 1], outside=-0.75)
    epsilon = 0.085
    delta = controls[:, None, :] - controls[None, :, :]
    kernel = np.exp(-np.sum(delta * delta, axis=2) / (2.0 * epsilon * epsilon))
    regularization = 2.5e-4
    weights = np.linalg.solve(kernel + regularization * np.eye(len(kernel)), targets)

    gx, gy = np.meshgrid(np.arange(width, dtype=np.float64), np.arange(height, dtype=np.float64))
    queries = np.column_stack((gx.ravel() / (width - 1), gy.ravel() / (height - 1)))
    result = np.empty(len(queries), dtype=np.float64)
    chunk = 4096
    for start in range(0, len(queries), chunk):
        q = queries[start : start + chunk]
        d = q[:, None, :] - controls[None, :, :]
        result[start : start + chunk] = np.exp(-np.sum(d * d, axis=2) / (2.0 * epsilon * epsilon)) @ weights
    result = gaussian_blur(result.reshape(height, width), 1.2)
    result = np.clip(result, -0.75, 1.15)
    residual = result - signed
    report = {
        "control_points": int(len(controls)),
        "gaussian_epsilon_normalized": epsilon,
        "tikhonov_regularization": regularization,
        "field_rmse_in_body_bbox": float(np.sqrt(np.mean(residual[y0 : y1 + 1, x0 : x1 + 1] ** 2))),
        "field_p95_abs_error_in_body_bbox": float(np.quantile(np.abs(residual[y0 : y1 + 1, x0 : x1 + 1]), 0.95)),
    }
    return result, report


def bilinear_sample(array: np.ndarray, u: np.ndarray, v: np.ndarray, outside: float) -> np.ndarray:
    height, width = array.shape
    result = np.full(np.broadcast(u, v).shape, outside, dtype=np.float64)
    uf = np.asarray(u, dtype=np.float64).ravel()
    vf = np.asarray(v, dtype=np.float64).ravel()
    valid = (uf >= 0.0) & (uf <= width - 1) & (vf >= 0.0) & (vf <= height - 1)
    if np.any(valid):
        x = uf[valid]
        y = vf[valid]
        x0 = np.floor(x).astype(np.int32)
        y0 = np.floor(y).astype(np.int32)
        x1 = np.minimum(x0 + 1, width - 1)
        y1 = np.minimum(y0 + 1, height - 1)
        tx = x - x0
        ty = y - y0
        values = (
            array[y0, x0] * (1.0 - tx) * (1.0 - ty)
            + array[y0, x1] * tx * (1.0 - ty)
            + array[y1, x0] * (1.0 - tx) * ty
            + array[y1, x1] * tx * ty
        )
        result.ravel()[valid] = values
    return result


def sampled_profile(
    field2d: np.ndarray,
    x: np.ndarray,
    z: np.ndarray,
    bounds_min: np.ndarray,
    bounds_max: np.ndarray,
    bbox: list[int],
) -> np.ndarray:
    points = np.column_stack((np.asarray(x).ravel(), np.zeros(np.asarray(x).size), np.asarray(z).ravel()))
    u, v = project_xz(points, bounds_min, bounds_max, bbox)
    return bilinear_sample(field2d, u, v, outside=-0.75).reshape(np.broadcast(x, z).shape)


def make_scalar_grid(
    field2d: np.ndarray,
    bounds_min: np.ndarray,
    bounds_max: np.ndarray,
    bbox: list[int],
    center_y: float,
    radius_y: float,
    lower_guard: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    xs = np.linspace(bounds_min[0] - 0.018, bounds_max[0] + 0.018, 118)
    ys = np.linspace(center_y - radius_y * 1.08, center_y + radius_y * 1.08, 92)
    zs = np.linspace(lower_guard - 0.070, bounds_max[2] + 0.018, 110)
    gx, gz = np.meshgrid(xs, zs, indexing="ij")
    profile = sampled_profile(field2d, gx, gz, bounds_min, bounds_max, bbox)

    # Close the local volume smoothly below the unchanged lower-body guard so
    # the generated surface overlaps the protected source skin without a cap.
    lower_start = lower_guard - 0.062
    lower_full = lower_guard - 0.018
    t = np.clip((gz - lower_start) / (lower_full - lower_start), 0.0, 1.0)
    taper = t * t * (3.0 - 2.0 * t)
    profile = profile * taper - (1.0 - taper) * 0.20
    dy2 = ((ys - center_y) / radius_y) ** 2
    scalar = dy2[None, :, None] - profile[:, None, :] + 1.0e-8
    return xs, ys, zs, scalar


def tetra_patterns(case: int) -> list[list[tuple[int, int]]]:
    inside = [index for index in range(4) if case & (1 << index)]
    outside = [index for index in range(4) if not case & (1 << index)]
    if len(inside) == 1:
        i = inside[0]
        return [[(i, outside[0]), (i, outside[1]), (i, outside[2])]]
    if len(inside) == 3:
        o = outside[0]
        return [[(o, inside[2]), (o, inside[1]), (o, inside[0])]]
    if len(inside) == 2:
        i0, i1 = inside
        o0, o1 = outside
        return [
            [(i0, o0), (i0, o1), (i1, o1)],
            [(i0, o0), (i1, o1), (i1, o0)],
        ]
    return []


def marching_tetrahedra(xs: np.ndarray, ys: np.ndarray, zs: np.ndarray, scalar: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Extract a welded zero-isosurface without planar caps or triangle fans."""
    corners = np.array(
        [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]],
        dtype=np.int32,
    )
    tetrahedra = np.array(
        [[0, 5, 1, 6], [0, 1, 2, 6], [0, 2, 3, 6], [0, 3, 7, 6], [0, 7, 4, 6], [0, 4, 5, 6]],
        dtype=np.int32,
    )
    cube_min = scalar[:-1, :-1, :-1].copy()
    cube_max = cube_min.copy()
    for dx, dy, dz in corners[1:]:
        values = scalar[dx : dx + len(xs) - 1, dy : dy + len(ys) - 1, dz : dz + len(zs) - 1]
        cube_min = np.minimum(cube_min, values)
        cube_max = np.maximum(cube_max, values)
    active = np.argwhere((cube_min <= 0.0) & (cube_max >= 0.0))
    if len(active) == 0:
        raise RuntimeError("Implicit field has no zero crossing")

    corner_values = np.empty((len(active), 8), dtype=np.float64)
    corner_points = np.empty((len(active), 8, 3), dtype=np.float64)
    for index, (dx, dy, dz) in enumerate(corners):
        ix = active[:, 0] + dx
        iy = active[:, 1] + dy
        iz = active[:, 2] + dz
        corner_values[:, index] = scalar[ix, iy, iz]
        corner_points[:, index, 0] = xs[ix]
        corner_points[:, index, 1] = ys[iy]
        corner_points[:, index, 2] = zs[iz]

    triangle_blocks: list[np.ndarray] = []
    for tet in tetrahedra:
        values = corner_values[:, tet]
        points = corner_points[:, tet]
        cases = np.sum((values < 0.0).astype(np.uint8) * np.array([1, 2, 4, 8], dtype=np.uint8), axis=1)
        for case in range(1, 15):
            select = np.nonzero(cases == case)[0]
            if len(select) == 0:
                continue
            selected_values = values[select]
            selected_points = points[select]
            for pattern in tetra_patterns(case):
                tri = np.empty((len(select), 3, 3), dtype=np.float64)
                for slot, (a, b) in enumerate(pattern):
                    va = selected_values[:, a]
                    vb = selected_values[:, b]
                    denominator = va - vb
                    fraction = np.divide(va, denominator, out=np.full_like(va, 0.5), where=np.abs(denominator) > 1e-15)
                    tri[:, slot, :] = selected_points[:, a, :] + fraction[:, None] * (
                        selected_points[:, b, :] - selected_points[:, a, :]
                    )
                triangle_blocks.append(tri)
    triangles = np.concatenate(triangle_blocks, axis=0)
    flat = triangles.reshape(-1, 3)
    quantized = np.rint(flat * 1.0e7).astype(np.int64)
    _unique, first, inverse = np.unique(quantized, axis=0, return_index=True, return_inverse=True)
    vertices = flat[first]
    faces = inverse.reshape(-1, 3)
    nondegenerate = (faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 2] != faces[:, 0])
    faces = faces[nondegenerate]
    triangles = vertices[faces]
    area2 = np.linalg.norm(np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), axis=1)
    return vertices, faces[area2 > 1.0e-12]


def mesh_metrics(vertices: np.ndarray, faces: np.ndarray) -> dict[str, object]:
    triangles = vertices[faces]
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    area2 = np.linalg.norm(cross, axis=1)
    edges = np.vstack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    edges.sort(axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    return {
        "vertices": int(len(vertices)),
        "triangles": int(len(faces)),
        "degenerate_triangles": int(np.count_nonzero(area2 <= 1.0e-12)),
        "boundary_edges": int(np.count_nonzero(counts == 1)),
        "nonmanifold_edges": int(np.count_nonzero(counts > 2)),
        "watertight_edge_incidence": bool(np.all(counts == 2)),
        "bounds_min": vertices.min(axis=0).tolist(),
        "bounds_max": vertices.max(axis=0).tolist(),
    }


def source_selection(
    vertices: np.ndarray,
    faces: np.ndarray,
    body: np.ndarray,
    feature_full: np.ndarray,
    feature_core: np.ndarray,
    bounds_min: np.ndarray,
    bounds_max: np.ndarray,
    bbox: list[int],
    lower_guard: float,
    field2d: np.ndarray,
    center_y: float,
    radius_y: float,
) -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
    triangles = vertices[faces]
    centers = triangles.mean(axis=1)
    u, v = project_xz(centers, bounds_min, bounds_max, bbox)
    ui = np.rint(u).astype(np.int32)
    vi = np.rint(v).astype(np.int32)
    valid = (ui >= 0) & (ui < body.shape[1]) & (vi >= 0) & (vi < body.shape[0])
    in_body = np.zeros(len(faces), dtype=bool)
    in_feature = np.zeros(len(faces), dtype=bool)
    in_core = np.zeros(len(faces), dtype=bool)
    in_body[valid] = body[vi[valid], ui[valid]]
    in_feature[valid] = feature_full[vi[valid], ui[valid]]
    in_core[valid] = feature_core[vi[valid], ui[valid]]

    vu, vv = project_xz(triangles.reshape(-1, 3), bounds_min, bounds_max, bbox)
    vui = np.rint(vu).astype(np.int32).reshape(-1, 3)
    vvi = np.rint(vv).astype(np.int32).reshape(-1, 3)
    vertex_valid = (vui >= 0) & (vui < body.shape[1]) & (vvi >= 0) & (vvi < body.shape[0])
    vertex_body = np.zeros(vertex_valid.shape, dtype=bool)
    flat_valid = vertex_valid.ravel()
    vertex_body.ravel()[flat_valid] = body[vvi.ravel()[flat_valid], vui.ravel()[flat_valid]]
    intersects_body = in_body | np.any(vertex_body, axis=1)

    flat_points = triangles.reshape(-1, 3)
    profile = sampled_profile(field2d, flat_points[:, 0], flat_points[:, 2], bounds_min, bounds_max, bbox)
    implicit_value = ((flat_points[:, 1] - center_y) / radius_y) ** 2 - profile
    implicit_value = implicit_value.reshape(-1, 3)

    # Retain actual Seed-42 feature shells by measured exterior depth, not by
    # assuming that an eye indentation must sit outside the new implicit skin.
    # This is the R10 correction to the insufficient R08/R09 2-D-only guard.
    measured_feature_surface = np.zeros(len(faces), dtype=bool)
    feature_depth_measurements: list[dict[str, object]] = []
    for feature in [
        {"name": "front_ear", "center_px": [103, 154], "radius_px": 24},
        {"name": "reference_side_ear", "center_px": [226, 174], "radius_px": 30},
        {"name": "front_eye", "center_px": [111, 210], "radius_px": 18},
        {"name": "reference_side_eye", "center_px": [205, 207], "radius_px": 19},
        {"name": "nose", "center_px": [79, 231], "radius_px": 23},
        {"name": "front_foot", "center_px": [124, 300], "radius_px": 30},
        {"name": "reference_side_foot", "center_px": [212, 306], "radius_px": 34},
    ]:
        fx, fy = feature["center_px"]
        radius = feature["radius_px"]
        ellipse = ((u - fx) / radius) ** 2 + ((v - fy) / radius) ** 2 <= 1.0
        if np.count_nonzero(ellipse) < 20:
            continue
        low, high = np.quantile(centers[ellipse, 1], [0.12, 0.88])
        surface = ellipse & ((centers[:, 1] <= low) | (centers[:, 1] >= high))
        measured_feature_surface |= surface
        feature_depth_measurements.append(
            {
                "name": feature["name"],
                "triangles_in_projected_guard": int(np.count_nonzero(ellipse)),
                "exterior_depth_quantiles_y": [float(low), float(high)],
                "retained_exterior_depth_triangles": int(np.count_nonzero(surface)),
            }
        )
    exterior_feature = (in_feature | in_core) & measured_feature_surface
    problem = intersects_body & (np.max(triangles[:, :, 2], axis=1) > lower_guard)
    remove = problem & ~exterior_feature
    retained = faces[~remove]
    outside_roi = ~problem
    outside_roi_preserved = np.array_equal(retained[np.isin(np.nonzero(~remove)[0], np.nonzero(outside_roi)[0])], faces[outside_roi])
    report = {
        "problem_triangles": int(problem.sum()),
        "removed_source_triangles": int(remove.sum()),
        "retained_source_triangles": int((~remove).sum()),
        "retained_exterior_feature_triangles_in_problem": int(np.count_nonzero(problem & exterior_feature)),
        "outside_roi_source_triangles": int(outside_roi.sum()),
        "outside_roi_faces_preserved_exact": bool(outside_roi_preserved),
        "source_vertex_coordinates_modified": 0,
        "feature_depth_measurements": feature_depth_measurements,
    }
    return retained, remove, report


def carve_implicit_feature_windows(
    vertices: np.ndarray,
    faces: np.ndarray,
    windows: np.ndarray,
    bounds_min: np.ndarray,
    bounds_max: np.ndarray,
    bbox: list[int],
    lower_guard: float,
) -> tuple[np.ndarray, int]:
    centers = vertices[faces].mean(axis=1)
    u, v = project_xz(centers, bounds_min, bounds_max, bbox)
    ui = np.rint(u).astype(np.int32)
    vi = np.rint(v).astype(np.int32)
    valid = (ui >= 0) & (ui < windows.shape[1]) & (vi >= 0) & (vi < windows.shape[0])
    in_window = np.zeros(len(faces), dtype=bool)
    in_window[valid] = windows[vi[valid], ui[valid]]
    remove = in_window & (centers[:, 2] > lower_guard)
    return faces[~remove], int(np.count_nonzero(remove))


def create_diagnostic(
    body: np.ndarray,
    blue: np.ndarray,
    feature_core: np.ndarray,
    rbf_report: dict[str, object],
    bbox: list[int],
) -> None:
    image = np.full((*body.shape, 3), 246, dtype=np.uint8)
    image[body] = np.array([224, 180, 126], dtype=np.uint8)
    image[feature_core] = np.array([56, 135, 224], dtype=np.uint8)
    image[blue] = np.array([0, 70, 255], dtype=np.uint8)
    x0, y0, x1, y1 = bbox
    controls = int(round(np.sqrt(int(rbf_report["control_points"]))))
    for y in np.linspace(y0, y1, controls).astype(int):
        for x in np.linspace(x0, x1, controls).astype(int):
            image[max(0, y - 1) : y + 2, max(0, x - 1) : x + 2] = np.array([42, 42, 42], dtype=np.uint8)
    Image.fromarray(image).resize((768, 768), Image.Resampling.NEAREST).save(DIAGNOSTIC)


def main() -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC.parent.mkdir(parents=True, exist_ok=True)
    if sha256(SOURCE) != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("Seed-42 source hash gate failed")
    vertices, faces = read_binary_ply(SOURCE)
    used = np.unique(faces)
    bounds_min = vertices[used].min(axis=0).astype(np.float64)
    bounds_max = vertices[used].max(axis=0).astype(np.float64)
    blue, body, bbox, _rgb = reference_masks()
    feature_full, feature_core, feature_windows, features = feature_masks(body.shape)

    lower_guard = -0.105
    triangles = vertices[faces]
    centers = triangles.mean(axis=1)
    u, v = project_xz(centers, bounds_min, bounds_max, bbox)
    ui = np.rint(u).astype(np.int32)
    vi = np.rint(v).astype(np.int32)
    valid = (ui >= 0) & (ui < body.shape[1]) & (vi >= 0) & (vi < body.shape[0])
    in_body = np.zeros(len(faces), dtype=bool)
    in_feature = np.zeros(len(faces), dtype=bool)
    in_body[valid] = body[vi[valid], ui[valid]]
    in_feature[valid] = feature_full[vi[valid], ui[valid]]
    anchor = in_body & ~in_feature & (centers[:, 2] >= lower_guard - 0.055) & (centers[:, 2] <= lower_guard - 0.008)
    if np.count_nonzero(anchor) < 100:
        raise RuntimeError("Insufficient unchanged adjacent body geometry")
    y_low, y_high = np.quantile(centers[anchor, 1], [0.05, 0.95])
    center_y = float((y_low + y_high) * 0.5)
    radius_y = float((y_high - y_low) * 0.5)

    sdf = signed_distance_field(body)
    rbf, rbf_report = rbf_field(sdf, bbox)
    variants: dict[str, dict[str, object]] = {}
    scores: dict[str, float] = {}
    for name, field2d, method in (
        ("sdf", sdf, "Gaussian-smoothed signed-distance visual hull"),
        ("rbf", rbf, "Gaussian radial-basis implicit visual hull"),
    ):
        xs, ys, zs, scalar = make_scalar_grid(field2d, bounds_min, bounds_max, bbox, center_y, radius_y, lower_guard)
        implicit_vertices, implicit_faces = marching_tetrahedra(xs, ys, zs, scalar)
        implicit_faces, carved_faces = carve_implicit_feature_windows(
            implicit_vertices, implicit_faces, feature_windows, bounds_min, bounds_max, bbox, lower_guard
        )
        implicit_metrics = mesh_metrics(implicit_vertices, implicit_faces)
        implicit_metrics["faces_removed_for_measured_eye_nose_windows"] = carved_faces
        retained_faces, remove, selection_report = source_selection(
            vertices,
            faces,
            body,
            feature_full,
            feature_core,
            bounds_min,
            bounds_max,
            bbox,
            lower_guard,
            field2d,
            center_y,
            radius_y,
        )
        combined_vertices = np.vstack((vertices, implicit_vertices))
        combined_faces = np.vstack((retained_faces, implicit_faces + len(vertices)))
        variant_path = OUT / "variants" / f"herbst-igel-r02-implicit-{name}-r10-NON-APPROVED.ply"
        write_binary_ply(variant_path, combined_vertices, combined_faces)
        profile_error = float(np.sqrt(np.mean((field2d[body] - sdf[body]) ** 2)))
        score = profile_error + 0.001 * implicit_metrics["boundary_edges"] + 0.002 * implicit_metrics["nonmanifold_edges"]
        scores[name] = score
        variants[name] = {
            "method": method,
            "path": variant_path.relative_to(ROOT).as_posix(),
            "sha256": sha256(variant_path),
            "bytes": variant_path.stat().st_size,
            "implicit_surface": implicit_metrics,
            "selection": selection_report,
            "combined_vertices": int(len(combined_vertices)),
            "combined_triangles": int(len(combined_faces)),
            "field_rmse_vs_smoothed_sdf_inside_roi": profile_error,
            "preliminary_numeric_score_lower_is_better": score,
        }

    selected = min(scores, key=scores.get)
    selected_source = OUT / "variants" / f"herbst-igel-r02-implicit-{selected}-r10-NON-APPROVED.ply"
    master = OUT / "masterform" / "herbst-igel-r02-masterform-implicit-r10-NON-APPROVED.ply"
    master.write_bytes(selected_source.read_bytes())
    create_diagnostic(body, blue, feature_core, rbf_report, bbox)

    payload = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "operation": "local_smooth_implicit_body_reconstruction",
        "source": {
            "path": SOURCE.relative_to(ROOT).as_posix(),
            "sha256": sha256(SOURCE),
            "expected_sha256": EXPECTED_SOURCE_SHA256,
            "byte_identical_seed42_gate": True,
            "vertices": int(len(vertices)),
            "triangles": int(len(faces)),
            "bounds_min": bounds_min.tolist(),
            "bounds_max": bounds_max.tolist(),
        },
        "problem_zone": {
            "authority": "REF-CLEAN + REF-SEAM + copied R08/R09 diagnostics",
            "projection": "unchanged R08/R09 affine X/Z transfer",
            "lower_body_guard_normalized": lower_guard,
            "body_mask_pixels": int(body.sum()),
            "protected_features": features,
        },
        "adjacent_body_depth_measurement": {
            "anchor_triangles": int(anchor.sum()),
            "robust_y_percentiles": [float(y_low), float(y_high)],
            "center_y": center_y,
            "radius_y": radius_y,
        },
        "methods": {
            "sdf": {"description": "Gaussian-smoothed signed-distance field; closed marching-tetrahedra zero set"},
            "rbf": {"description": "Gaussian RBF interpolation; closed marching-tetrahedra zero set", **rbf_report},
        },
        "variants": variants,
        "preliminary_numeric_selection": selected,
        "selected_master": {
            "path": master.relative_to(ROOT).as_posix(),
            "sha256": sha256(master),
            "bytes": master.stat().st_size,
            "status": "NON_APPROVED_PENDING_OPTIK_GATE",
        },
        "protected_geometry": {
            "all_seed42_vertex_coordinates": "unchanged",
            "outside_roi_source_faces": "retained exactly",
            "back_and_maple_leaf_outside_problem_mask": "retained source geometry",
            "feet_below_guard": "retained source geometry",
            "feature_cores": "actual outer Seed-42 depth layers retained inside unchanged measured guards",
        },
        "forbidden_methods_used": {
            "planar_caps": False,
            "triangle_fans": False,
            "convex_hull_visible_surface": False,
            "block_hole_filler": False,
        },
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
    }
    REPORT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
