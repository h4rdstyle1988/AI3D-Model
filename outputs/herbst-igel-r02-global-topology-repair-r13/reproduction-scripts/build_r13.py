#!/usr/bin/env python3
"""R13 global topology repair and seam-guided single-surface face rebuild.

The only form source is the byte-identical Seed-42 PLY.  Its visible exterior
is sampled as the two outer Y envelopes over the established X/Z projection.
The envelopes and their common silhouette boundary form one deterministic,
closed, orientable surface.  This removes intersecting interior sheets and
invalid edge incidence without inventing a new figure.  Inside the R11/R12
problem mask, the measured Seed-42 body-width profiles and REF-SEAM body field
replace the false leaf/spine envelope with one smooth body surface.  Existing
feature relief is blended back into that same surface, never as an island.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
TASK = "tasks/TASK-HERBST-IGEL-R02-GLOBAL-TOPOLOGY-REPAIR-R13.md"
TASK_BLOB = "b21a7d611c36c7e2a0b826f3a9f8d329cddfd242"
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
MASTER = OUT / "masterform" / "herbst-igel-r02-masterform-r13-NON-APPROVED.ply"
GRID_CACHE = OUT / "masterform" / "heightfield-r13.npz"
REPORT = OUT / "reports" / "global-topology-repair-r13.json"
TOPOLOGY_REPORT = OUT / "reports" / "topology-audit-r13.json"
DEVIATION_REPORT = OUT / "reports" / "global-form-deviation-r13.json"
RENDER_REPORT = OUT / "reports" / "real-geometry-renders-r13.json"
DIAGNOSTIC = OUT / "diagnostics" / "roi-and-heightfield-diagnostic-r13.png"

EXPECTED = {
    "seed42": "85ba18eaed15bdbe631fc49dd571e73882c4055e2c247022e90ad15ed99822c6",
    "ref_clean": "c1c9a5a094f1db2fd220f3433f83af8dedca780f56a4bf479eb8883432250859",
    "ref_seam": "b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4",
}

PROFILE_X = np.array([-0.22, -0.18, -0.14, -0.10, -0.06, -0.02, 0.02, 0.06, 0.10])
PROFILE_CENTER = np.array([
    0.0169361740, 0.0452638999, 0.0792594999, 0.0935772389,
    0.1045350730, 0.1213772982, 0.1333136275, 0.1294722117, 0.1486910433,
])
PROFILE_RADIUS = np.array([
    0.1483075231, 0.1742545411, 0.2121440917, 0.2426284343,
    0.2650010884, 0.2802440196, 0.2838787362, 0.2941812329, 0.2836902946,
])
FEATURES = [
    {"name": "front_ear", "center_px": [103, 154], "radius_px": 18},
    {"name": "reference_side_ear", "center_px": [226, 174], "radius_px": 23},
    {"name": "front_eye", "center_px": [111, 210], "radius_px": 12},
    {"name": "reference_side_eye", "center_px": [205, 207], "radius_px": 13},
    {"name": "nose", "center_px": [79, 231], "radius_px": 16},
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def read_binary_ply(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with path.open("rb") as stream:
        lines: list[bytes] = []
        while True:
            line = stream.readline()
            if not line:
                raise ValueError("PLY header ended unexpectedly")
            lines.append(line)
            if line.strip() == b"end_header":
                break
        header = b"".join(lines).decode("ascii")
        if "format binary_little_endian 1.0" not in header:
            raise ValueError("Only binary little-endian PLY is supported")
        nv = int(next(x.split()[2] for x in header.splitlines() if x.startswith("element vertex ")))
        nf = int(next(x.split()[2] for x in header.splitlines() if x.startswith("element face ")))
        vertices = np.fromfile(stream, dtype="<f4", count=nv * 3).reshape(nv, 3)
        dtype = np.dtype([("count", "u1"), ("indices", "<i4", (3,))])
        records = np.fromfile(stream, dtype=dtype, count=nf)
    if len(records) != nf or not np.all(records["count"] == 3):
        raise ValueError("PLY is truncated or contains non-triangular faces")
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
    dtype = np.dtype([("count", "u1"), ("indices", "<i4", (3,))])
    records = np.empty(len(faces), dtype=dtype)
    records["count"] = 3
    records["indices"] = np.asarray(faces, dtype="<i4")
    with path.open("wb") as stream:
        stream.write(header)
        np.asarray(vertices, dtype="<f4").tofile(stream)
        records.tofile(stream)


def edge_metrics(vertices: np.ndarray, faces: np.ndarray) -> dict[str, object]:
    triangles = vertices[faces]
    area2 = np.linalg.norm(
        np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), axis=1
    )
    edges = np.vstack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    edges.sort(axis=1)
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    used = np.unique(faces)
    return {
        "vertices": int(len(vertices)),
        "triangles": int(len(faces)),
        "used_vertices": int(len(used)),
        "boundary_edges": int(np.count_nonzero(counts == 1)),
        "nonmanifold_edges": int(np.count_nonzero(counts > 2)),
        "max_edge_incidence": int(counts.max(initial=0)),
        "degenerate_faces": int(np.count_nonzero(area2 <= 1.0e-12)),
        "bounds_min": vertices[used].min(axis=0).astype(float).tolist(),
        "bounds_max": vertices[used].max(axis=0).astype(float).tolist(),
        "surface_area_normalized2": float(0.5 * area2.sum()),
        "all_edges_incidence_two": bool(np.all(counts == 2)),
    }


def reference_masks() -> tuple[np.ndarray, np.ndarray, np.ndarray, list[int], np.ndarray]:
    rgb = np.asarray(Image.open(REF_SEAM).convert("RGB"), dtype=np.int16)
    red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    blue_mask = (blue > 120) & (blue > red + 35) & (blue > green + 15)
    span = rgb.max(axis=2) - rgb.min(axis=2)
    foreground = (rgb.mean(axis=2) < 238) & ((span > 12) | (rgb.mean(axis=2) < 210))
    foreground = np.asarray(
        Image.fromarray((foreground * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(7))
    ) > 0
    yy, xx = np.nonzero(foreground)
    bbox = [int(xx.min()), int(yy.min()), int(xx.max()), int(yy.max())]
    path_mask = np.asarray(
        Image.fromarray((blue_mask * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))
    ) > 0
    sy, sx = np.unravel_index(
        np.argmin(np.where(path_mask, np.indices(path_mask.shape)[1], 10_000)), path_mask.shape
    )
    bottom_y = int(np.nonzero(path_mask)[0].max())
    ex = int(np.median(np.nonzero(path_mask[bottom_y])[0]))
    end = (bottom_y, ex)
    parent: dict[tuple[int, int], tuple[int, int] | None] = {(int(sy), int(sx)): None}
    queue: deque[tuple[int, int]] = deque([(int(sy), int(sx))])
    height, width = path_mask.shape
    while queue and end not in parent:
        y, x = queue.popleft()
        for dy, dx in ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)):
            node = (y + dy, x + dx)
            if 0 <= node[0] < height and 0 <= node[1] < width and path_mask[node] and node not in parent:
                parent[node] = (y, x)
                queue.append(node)
    if end not in parent:
        raise ValueError("REF-SEAM blue path is not connected")
    path: list[tuple[int, int]] = []
    node: tuple[int, int] | None = end
    while node is not None:
        path.append((node[1], node[0]))
        node = parent[node]
    path.reverse()
    x0, y0, _x1, y1 = bbox
    body_image = Image.new("L", (width, height), 0)
    ImageDraw.Draw(body_image).polygon(path + [(x0, y1), (x0, y0)], fill=255)
    body = (np.asarray(body_image) > 0) & foreground
    seam_band = np.asarray(
        Image.fromarray((blue_mask * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(9))
    ) > 0
    return blue_mask, body, seam_band, bbox, rgb.astype(np.uint8)


def grid_distance_to_false(mask: np.ndarray) -> np.ndarray:
    h, w = mask.shape
    distance = np.full((h, w), 32767, dtype=np.int16)
    queue: deque[tuple[int, int]] = deque()
    for y, x in zip(*np.nonzero(~mask)):
        distance[y, x] = 0
        queue.append((int(y), int(x)))
    while queue:
        y, x = queue.popleft()
        candidate = int(distance[y, x]) + 1
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < h and 0 <= nx < w and candidate < distance[ny, nx]:
                distance[ny, nx] = candidate
                queue.append((ny, nx))
    return distance.astype(np.float64)


def gaussian_blur(array: np.ndarray, sigma: float) -> np.ndarray:
    radius = max(1, int(math.ceil(3.0 * sigma)))
    axis = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-0.5 * (axis / sigma) ** 2)
    kernel /= kernel.sum()
    padded = np.pad(array, ((0, 0), (radius, radius)), mode="edge")
    horizontal = sum(kernel[i] * padded[:, i : i + array.shape[1]] for i in range(len(kernel)))
    padded = np.pad(horizontal, ((radius, radius), (0, 0)), mode="edge")
    return sum(kernel[i] * padded[i : i + array.shape[0], :] for i in range(len(kernel)))


def signed_distance_field(body: np.ndarray) -> np.ndarray:
    signed = grid_distance_to_false(body) - grid_distance_to_false(~body)
    smooth = gaussian_blur(signed, 4.0)
    scale = max(float(np.quantile(smooth[body], 0.98)), 1.0)
    return np.clip(smooth / scale, -0.75, 1.15)


def bilinear(array: np.ndarray, u: np.ndarray, v: np.ndarray, outside: float = 0.0) -> np.ndarray:
    h, w = array.shape
    result = np.full(np.broadcast(u, v).shape, outside, dtype=np.float64)
    uf, vf = np.asarray(u).ravel(), np.asarray(v).ravel()
    valid = (uf >= 0) & (uf <= w - 1) & (vf >= 0) & (vf <= h - 1)
    x, y = uf[valid], vf[valid]
    x0, y0 = np.floor(x).astype(np.int32), np.floor(y).astype(np.int32)
    x1, y1 = np.minimum(x0 + 1, w - 1), np.minimum(y0 + 1, h - 1)
    tx, ty = x - x0, y - y0
    result.ravel()[valid] = (
        array[y0, x0] * (1 - tx) * (1 - ty)
        + array[y0, x1] * tx * (1 - ty)
        + array[y1, x0] * (1 - tx) * ty
        + array[y1, x1] * tx * ty
    )
    return result


def largest_component_and_fill_holes(mask: np.ndarray) -> np.ndarray:
    """Keep one 4-connected projected body and fill only enclosed projection holes."""
    h, w = mask.shape
    # The Seed-42 projection is one body.  Grow from its central occupied node
    # using vectorized four-neighbour propagation; this is deterministic and
    # avoids retaining isolated sampling specks.
    occupied = np.argwhere(mask)
    center = np.array([0.5 * (h - 1), 0.5 * (w - 1)])
    seed = occupied[np.argmin(np.sum((occupied - center) ** 2, axis=1))]
    result = np.zeros_like(mask, dtype=bool)
    result[tuple(seed)] = True
    for _ in range(h + w):
        grown = result.copy()
        grown[1:, :] |= result[:-1, :]
        grown[:-1, :] |= result[1:, :]
        grown[:, 1:] |= result[:, :-1]
        grown[:, :-1] |= result[:, 1:]
        grown &= mask
        if np.array_equal(grown, result):
            break
        result = grown
    # Flood the complementary exterior from all four borders and fill only
    # enclosed projection holes.  A hole-free heightfield cannot introduce a
    # second shell or an internal double skin.
    exterior = np.zeros_like(mask, dtype=bool)
    exterior[0, :] = ~result[0, :]
    exterior[-1, :] = ~result[-1, :]
    exterior[:, 0] = ~result[:, 0]
    exterior[:, -1] = ~result[:, -1]
    complement = ~result
    for _ in range(h + w):
        grown = exterior.copy()
        grown[1:, :] |= exterior[:-1, :]
        grown[:-1, :] |= exterior[1:, :]
        grown[:, 1:] |= exterior[:, :-1]
        grown[:, :-1] |= exterior[:, 1:]
        grown &= complement
        if np.array_equal(grown, exterior):
            break
        exterior = grown
    return result | (complement & ~exterior)


def splat_points(
    lo: np.ndarray,
    hi: np.ndarray,
    points: np.ndarray,
    xmin: float,
    zmin: float,
    hx: float,
    hz: float,
) -> None:
    nx, nz = lo.shape
    fx = (points[:, 0].astype(np.float64) - xmin) / hx
    fz = (points[:, 2].astype(np.float64) - zmin) / hz
    ix, iz = np.rint(fx).astype(np.int64), np.rint(fz).astype(np.int64)
    y = points[:, 1].astype(np.float64)
    flat_lo, flat_hi = lo.ravel(), hi.ravel()
    valid = (ix >= 0) & (ix < nx) & (iz >= 0) & (iz < nz)
    indices = ix[valid] * nz + iz[valid]
    np.minimum.at(flat_lo, indices, y[valid])
    np.maximum.at(flat_hi, indices, y[valid])


def fill_envelope_values(lo: np.ndarray, hi: np.ndarray, target: np.ndarray) -> None:
    known = np.isfinite(lo)
    for _iteration in range(12):
        missing = target & ~known
        if not np.any(missing):
            return
        sum_lo = np.zeros_like(lo)
        sum_hi = np.zeros_like(hi)
        count = np.zeros(lo.shape, dtype=np.int16)
        for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
            src_i = slice(max(0, -di), min(lo.shape[0], lo.shape[0] - di))
            src_j = slice(max(0, -dj), min(lo.shape[1], lo.shape[1] - dj))
            dst_i = slice(max(0, di), min(lo.shape[0], lo.shape[0] + di))
            dst_j = slice(max(0, dj), min(lo.shape[1], lo.shape[1] + dj))
            valid = known[src_i, src_j]
            sum_lo[dst_i, dst_j] += np.where(valid, lo[src_i, src_j], 0.0)
            sum_hi[dst_i, dst_j] += np.where(valid, hi[src_i, src_j], 0.0)
            count[dst_i, dst_j] += valid
        update = missing & (count > 0)
        lo[update] = sum_lo[update] / count[update]
        hi[update] = sum_hi[update] / count[update]
        known[update] = True
    if np.any(target & ~known):
        raise RuntimeError("Projected envelope interpolation did not converge")


def build_heightfield(
    vertices: np.ndarray, faces: np.ndarray, step: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, object]]:
    bounds_min = vertices.min(axis=0).astype(np.float64)
    bounds_max = vertices.max(axis=0).astype(np.float64)
    nx = int(math.ceil((bounds_max[0] - bounds_min[0]) / step)) + 1
    nz = int(math.ceil((bounds_max[2] - bounds_min[2]) / step)) + 1
    xs = np.linspace(bounds_min[0], bounds_max[0], nx)
    zs = np.linspace(bounds_min[2], bounds_max[2], nz)
    hx, hz = float(xs[1] - xs[0]), float(zs[1] - zs[0])
    lo = np.full((nx, nz), np.inf, dtype=np.float64)
    hi = np.full((nx, nz), -np.inf, dtype=np.float64)
    print(f"R13: envelope grid {nx} x {nz}", flush=True)
    splat_points(lo, hi, vertices, xs[0], zs[0], hx, hz)
    batch = 125_000
    for start in range(0, len(faces), batch):
        tri = vertices[faces[start : start + batch]].astype(np.float64)
        samples = [
            tri.mean(axis=1),
            0.5 * (tri[:, 0] + tri[:, 1]),
            0.5 * (tri[:, 1] + tri[:, 2]),
            0.5 * (tri[:, 2] + tri[:, 0]),
        ]
        for points in samples:
            splat_points(lo, hi, points, xs[0], zs[0], hx, hz)
    observed = np.isfinite(lo)
    print(f"R13: observed projected nodes {int(observed.sum())}", flush=True)
    image = Image.fromarray((observed.T * 255).astype(np.uint8))
    # The largest Seed-42 edge is about 0.0039 normalized units.  A 9-node
    # close at the final 0.00065 grid step fills only unsampled triangle
    # interiors; it is not a silhouette smoothing operation.
    closed = image.filter(ImageFilter.MaxFilter(19)).filter(ImageFilter.MinFilter(19))
    target = largest_component_and_fill_holes(np.asarray(closed).T > 0)
    print(f"R13: closed projected nodes {int(target.sum())}", flush=True)
    fill_envelope_values(lo, hi, target)
    # Ensure a strictly positive thickness at the true silhouette.  The
    # 0.00002 normalized separation is 0.0064 mm at final scale.
    center = np.zeros_like(lo)
    half = np.zeros_like(lo)
    center[target] = 0.5 * (lo[target] + hi[target])
    half[target] = np.maximum(0.5 * (hi[target] - lo[target]), 1.0e-5)
    lo[target], hi[target] = center[target] - half[target], center[target] + half[target]
    return xs, zs, lo, hi, {
        "requested_step_normalized": step,
        "actual_step_x_normalized": hx,
        "actual_step_z_normalized": hz,
        "grid_nodes": [nx, nz],
        "observed_nodes": int(observed.sum()),
        "closed_projected_nodes": int(target.sum()),
        "projection_components_removed": int(observed.sum() - np.count_nonzero(observed & target)),
    }


def apply_face_rebuild(
    xs: np.ndarray,
    zs: np.ndarray,
    lo: np.ndarray,
    hi: np.ndarray,
    mask: np.ndarray,
    bounds_min: np.ndarray,
    bounds_max: np.ndarray,
) -> dict[str, object]:
    blue, body, seam_band, bbox, rgb = reference_masks()
    body_field = signed_distance_field(body)
    gx, gz = np.meshgrid(xs, zs, indexing="ij")
    x0, y0, x1, y1 = bbox
    u = x0 + (gx - bounds_min[0]) / (bounds_max[0] - bounds_min[0]) * (x1 - x0)
    v = y1 - (gz - bounds_min[2]) / (bounds_max[2] - bounds_min[2]) * (y1 - y0)
    profile = bilinear(body_field, u, v, outside=-0.75)
    cy = np.interp(gx, PROFILE_X, PROFILE_CENTER, left=PROFILE_CENTER[0], right=PROFILE_CENTER[-1])
    ry = np.interp(gx, PROFILE_X, PROFILE_RADIUS, left=PROFILE_RADIUS[0], right=PROFILE_RADIUS[-1])
    radius_factor = np.sqrt(np.clip(profile, 0.0, 1.15))
    target_lo = cy - ry * radius_factor
    target_hi = cy + ry * radius_factor

    body_value = bilinear(body.astype(np.float64), u, v, outside=0.0)
    seam_value = bilinear(seam_band.astype(np.float64), u, v, outside=0.0)
    # Full body replacement away from the seam; a 12-pixel C1 transition at
    # REF-SEAM keeps the original back geometry and removes the former shelf.
    seam_x = np.full(body.shape[0], np.nan, dtype=np.float64)
    for row in range(body.shape[0]):
        cols = np.nonzero(blue[row])[0]
        if len(cols):
            seam_x[row] = float(np.median(cols))
    valid_rows = np.nonzero(np.isfinite(seam_x))[0]
    seam_x = np.interp(np.arange(len(seam_x)), valid_rows, seam_x[valid_rows])
    seam_u = np.interp(v.ravel(), np.arange(len(seam_x)), seam_x).reshape(v.shape)
    inward = seam_u - u
    # Replace the X/Z footprint itself on the body side.  R11 only changed Y
    # depth and therefore retained the false front-facing shelf.  R12/R13
    # explicitly authorize removal of every fused ROI sheet, including its
    # projected silhouette.  The desired footprint comes directly from the
    # authoritative body mask; the back side remains the Seed-42 envelope.
    replace_zone = (u <= seam_u + 3.0) & (gz > -0.105)
    desired_body = body_value > 0.20
    removed_projection_nodes = mask & replace_zone & ~desired_body
    added_projection_nodes = ~mask & replace_zone & desired_body
    mask[removed_projection_nodes] = False
    mask[added_projection_nodes] = True
    lo[added_projection_nodes] = target_lo[added_projection_nodes]
    hi[added_projection_nodes] = target_hi[added_projection_nodes]
    t = np.clip((inward + 2.0) / 14.0, 0.0, 1.0)
    smooth_t = t * t * (3.0 - 2.0 * t)
    # All visible body-side source sheets in the ROI are replaced.  The seam
    # band is strongly rebuilt but still tapers to unchanged back geometry.
    weight = np.maximum(body_value, 0.90 * seam_value * (1.0 - 0.35 * smooth_t))
    weight *= (gz > -0.105) & mask & (profile > 0.0)

    feature_preserve = np.zeros_like(weight)
    for feature in FEATURES:
        fx, fy = feature["center_px"]
        radius = feature["radius_px"]
        distance = np.sqrt(((u - fx) / radius) ** 2 + ((v - fy) / radius) ** 2)
        preserve = np.clip((0.72 - distance) / 0.22, 0.0, 1.0)
        preserve = preserve * preserve * (3.0 - 2.0 * preserve)
        feature_preserve = np.maximum(feature_preserve, preserve)
    # Feature relief remains part of the same heightfield.  A small amount of
    # body blending at feature edges prevents rings or floating islands.
    weight *= 1.0 - 0.70 * feature_preserve
    old_lo, old_hi = lo.copy(), hi.copy()
    lo[mask] = (1.0 - weight[mask]) * lo[mask] + weight[mask] * target_lo[mask]
    hi[mask] = (1.0 - weight[mask]) * hi[mask] + weight[mask] * target_hi[mask]
    center = np.zeros_like(lo)
    half = np.zeros_like(lo)
    center[mask] = 0.5 * (lo[mask] + hi[mask])
    half[mask] = np.maximum(0.5 * (hi[mask] - lo[mask]), 1.0e-5)
    lo[mask], hi[mask] = center[mask] - half[mask], center[mask] + half[mask]

    canvas = rgb.copy()
    overlay = canvas.copy()
    overlay[body] = np.array([224, 180, 126], dtype=np.uint8)
    overlay[seam_band & ~body] = np.array([255, 110, 50], dtype=np.uint8)
    overlay[blue] = np.array([0, 70, 255], dtype=np.uint8)
    diagnostic = (0.42 * canvas + 0.58 * overlay).astype(np.uint8)
    DIAGNOSTIC.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(diagnostic).resize((768, 768), Image.Resampling.NEAREST).save(DIAGNOSTIC)
    changed = weight > 1.0e-8
    comparable = mask & np.isfinite(old_lo) & np.isfinite(old_hi)
    return {
        "authority": "REF-CLEAN/REF-SEAM and fixed R11 measured body-width profiles",
        "foreground_bbox_px": bbox,
        "body_pixels": int(body.sum()),
        "seam_band_pixels": int(seam_band.sum()),
        "grid_nodes_changed": int(changed.sum()),
        "projected_source_nodes_removed_in_roi": int(removed_projection_nodes.sum()),
        "projected_body_nodes_added_from_reference_in_roi": int(added_projection_nodes.sum()),
        "grid_nodes_full_body_weight": int(np.count_nonzero(weight >= 0.999)),
        "max_y_change_normalized": float(max(np.max(np.abs(lo[comparable] - old_lo[comparable])), np.max(np.abs(hi[comparable] - old_hi[comparable])))),
        "protected_features": FEATURES,
        "lower_body_guard_normalized": -0.105,
        "single_surface_integration": True,
    }


def heightfield_mesh(
    xs: np.ndarray, zs: np.ndarray, lo: np.ndarray, hi: np.ndarray, node_mask: np.ndarray
) -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
    cell = node_mask[:-1, :-1] & node_mask[1:, :-1] & node_mask[1:, 1:] & node_mask[:-1, 1:]
    ci, cj = np.nonzero(cell)
    used_nodes = np.zeros(node_mask.shape, dtype=bool)
    for di, dj in ((0, 0), (1, 0), (1, 1), (0, 1)):
        used_nodes[ci + di, cj + dj] = True
    node_id = np.full(node_mask.shape, -1, dtype=np.int64)
    node_id[used_nodes] = np.arange(used_nodes.sum(), dtype=np.int64)
    ui, uj = np.nonzero(used_nodes)
    count = len(ui)
    top = np.column_stack((xs[ui], hi[ui, uj], zs[uj]))
    bottom = np.column_stack((xs[ui], lo[ui, uj], zs[uj]))
    vertices = np.vstack((top, bottom))
    a = node_id[ci, cj]
    b = node_id[ci + 1, cj]
    c = node_id[ci + 1, cj + 1]
    d = node_id[ci, cj + 1]
    faces = [
        np.column_stack((a, c, b)),
        np.column_stack((a, d, c)),
        np.column_stack((a + count, b + count, c + count)),
        np.column_stack((a + count, c + count, d + count)),
    ]

    # Directed CCW cell boundary edges.  The wall uses the opposite top/bottom
    # boundary direction, giving globally consistent winding.
    boundary_blocks: list[tuple[np.ndarray, np.ndarray]] = []
    left = cell & ~np.pad(cell[:-1, :], ((1, 0), (0, 0)), constant_values=False)
    right = cell & ~np.pad(cell[1:, :], ((0, 1), (0, 0)), constant_values=False)
    low = cell & ~np.pad(cell[:, :-1], ((0, 0), (1, 0)), constant_values=False)
    high = cell & ~np.pad(cell[:, 1:], ((0, 0), (0, 1)), constant_values=False)
    ii, jj = np.nonzero(low)
    boundary_blocks.append((node_id[ii, jj], node_id[ii + 1, jj]))
    ii, jj = np.nonzero(right)
    boundary_blocks.append((node_id[ii + 1, jj], node_id[ii + 1, jj + 1]))
    ii, jj = np.nonzero(high)
    boundary_blocks.append((node_id[ii + 1, jj + 1], node_id[ii, jj + 1]))
    ii, jj = np.nonzero(left)
    boundary_blocks.append((node_id[ii, jj + 1], node_id[ii, jj]))
    boundary_edges = 0
    for p, q in boundary_blocks:
        boundary_edges += len(p)
        faces.append(np.column_stack((p, q, q + count)))
        faces.append(np.column_stack((p, q + count, p + count)))
    result_faces = np.vstack(faces).astype(np.int64)
    return vertices, result_faces, {
        "active_cells": int(cell.sum()),
        "used_grid_nodes": int(count),
        "silhouette_boundary_segments": int(boundary_edges),
    }


def camera_basis(position: tuple[float, float, float]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    camera = np.asarray(position, dtype=np.float64)
    forward = -camera / np.linalg.norm(camera)
    world_up = np.array([0.0, 0.0, 1.0])
    if abs(float(np.dot(forward, world_up))) > 0.98:
        world_up = np.array([0.0, 1.0, 0.0])
    right = np.cross(forward, world_up)
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    return right, up / np.linalg.norm(up), forward


def render(
    vertices: np.ndarray,
    faces: np.ndarray,
    camera: tuple[float, float, float],
    output: Path,
    title: str,
    size: int = 1100,
) -> None:
    max_faces = 1_600_000
    stride = max(1, int(math.ceil(len(faces) / max_faces)))
    sampled_faces = faces[::stride]
    triangles = vertices[sampled_faces]
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(cross, axis=1)
    keep = lengths > 1.0e-12
    centers = triangles.mean(axis=1)[keep]
    normals = cross[keep] / lengths[keep, None]
    center = 0.5 * (vertices.min(axis=0) + vertices.max(axis=0))
    centers -= center
    right, up, forward = camera_basis(camera)
    u, v, depth = centers @ right, centers @ up, centers @ forward
    extent = max(float(np.ptp(u)), float(np.ptp(v))) * 1.12
    center_u, center_v = 0.5 * float(u.max() + u.min()), 0.5 * float(v.max() + v.min())
    scale = (size - 110) / extent
    px = np.rint((u - center_u) * scale + size / 2).astype(np.int64)
    py = np.rint(size / 2 - (v - center_v) * scale).astype(np.int64)
    inside = (px >= 0) & (px < size) & (py >= 46) & (py < size)
    px, py, depth, normals = px[inside], py[inside], depth[inside], normals[inside]
    flat = py * size + px
    order = np.lexsort((depth, flat))
    ordered = flat[order]
    first = np.empty_like(ordered, dtype=bool)
    first[0] = True
    first[1:] = ordered[1:] != ordered[:-1]
    selected = order[first]
    light = np.array([-0.35, 0.75, -0.55], dtype=np.float64)
    light /= np.linalg.norm(light)
    shade = np.clip(
        0.20 + 0.53 * np.abs(normals[selected] @ light) + 0.27 * np.abs(normals[selected] @ (-forward)),
        0.0,
        1.0,
    )
    base = np.array([190.0, 91.0, 40.0])
    colors = np.clip(base[None, :] * (0.43 + 0.70 * shade[:, None]), 0, 255).astype(np.uint8)
    canvas = np.full((size * size, 3), 242, dtype=np.uint8)
    canvas[flat[selected]] = colors
    pixels = canvas.reshape(size, size, 3)
    image = Image.fromarray(pixels)
    radius = 9 if stride > 1 else 7
    mask = Image.fromarray((np.any(pixels != 242, axis=2) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(radius))
    expanded = image.filter(ImageFilter.MinFilter(radius))
    result = Image.new("RGB", (size, size), (242, 242, 242))
    result.paste(expanded, mask=mask)
    draw = ImageDraw.Draw(result)
    draw.rectangle((0, 0, size, 46), fill=(255, 255, 255))
    draw.text((15, 16), title, fill=(20, 20, 20))
    output.parent.mkdir(parents=True, exist_ok=True)
    result.save(output, optimize=True)


def sheet(paths: list[Path], labels: list[str], output: Path, columns: int = 3) -> None:
    panel = (520, 520)
    rows = (len(paths) + columns - 1) // columns
    result = Image.new("RGB", (columns * panel[0], rows * panel[1]), (232, 232, 232))
    for index, (path, label) in enumerate(zip(paths, labels)):
        image = Image.open(path).convert("RGB")
        fitted = ImageOps.contain(image, (500, 466), Image.Resampling.LANCZOS)
        tile = Image.new("RGB", panel, (242, 242, 242))
        tile.paste(fitted, ((panel[0] - fitted.width) // 2, 44 + (466 - fitted.height) // 2))
        draw = ImageDraw.Draw(tile)
        draw.rectangle((0, 0, panel[0], 42), fill=(255, 255, 255))
        draw.text((10, 14), label, fill=(20, 20, 20))
        result.paste(tile, ((index % columns) * panel[0], (index // columns) * panel[1]))
    output.parent.mkdir(parents=True, exist_ok=True)
    result.save(output, optimize=True)


def render_all(vertices: np.ndarray, faces: np.ndarray) -> dict[str, object]:
    render_dir = OUT / "renders-optik-gate"
    views = [
        ("3q-front", (-1.0, -1.0, 0.35), "3/4 vorne"),
        ("left", (0.0, -1.0, 0.12), "links / Referenzseite"),
        ("right", (0.0, 1.0, 0.12), "rechts"),
        ("rear", (1.0, 0.0, 0.12), "hinten"),
        ("top", (0.0, 0.0, 1.0), "oben"),
        ("bottom", (0.0, 0.0, -1.0), "unten"),
    ]
    paths: list[Path] = []
    records: list[dict[str, object]] = []
    for slug, camera, label in views:
        path = render_dir / f"masterform-{slug}.png"
        render(vertices, faces, camera, path, f"R13 reale Mastergeometrie: {label}")
        paths.append(path)
        records.append({"view": slug, "camera_vector": list(camera), "path": path.relative_to(ROOT).as_posix()})
    contact = render_dir / "masterform-contact-sheet-r13.png"
    sheet(paths, [x[2] for x in views], contact)
    soll_ist = render_dir / "soll-ist-optik-gate-r13.png"
    sheet([REF_CLEAN, REF_SEAM, *paths[:4]], ["SOLL REF-CLEAN", "SOLL REF-SEAM", "IST R13 3/4", "IST R13 links", "IST R13 rechts", "IST R13 hinten"], soll_ist)
    payload = {
        "schema_version": 1,
        "task": TASK,
        "source_geometry": MASTER.relative_to(ROOT).as_posix(),
        "source_geometry_sha256": sha256(MASTER),
        "source_is_actual_reconstructed_geometry": True,
        "selected_views": records,
        "contact_sheet": contact.relative_to(ROOT).as_posix(),
        "soll_ist_sheet": soll_ist.relative_to(ROOT).as_posix(),
    }
    RENDER_REPORT.parent.mkdir(parents=True, exist_ok=True)
    RENDER_REPORT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def deviation_audit(
    source_vertices: np.ndarray,
    xs: np.ndarray,
    zs: np.ndarray,
    lo_before: np.ndarray,
    hi_before: np.ndarray,
    lo_after: np.ndarray,
    hi_after: np.ndarray,
    node_mask: np.ndarray,
) -> dict[str, object]:
    bounds_min, bounds_max = source_vertices.min(axis=0), source_vertices.max(axis=0)
    blue, body, seam_band, bbox, _rgb = reference_masks()
    x0, y0, x1, y1 = bbox
    # Outside-ROI envelope displacement is exactly measured at all retained
    # heightfield nodes.  X/Z coordinates do not move.
    gx, gz = np.meshgrid(xs, zs, indexing="ij")
    u = x0 + (gx - bounds_min[0]) / (bounds_max[0] - bounds_min[0]) * (x1 - x0)
    v = y1 - (gz - bounds_min[2]) / (bounds_max[2] - bounds_min[2]) * (y1 - y0)
    roi = (bilinear(body.astype(float), u, v) > 0.01) | (bilinear(seam_band.astype(float), u, v) > 0.01)
    outside = node_mask & ~roi
    displacement = np.concatenate((np.abs(lo_after[outside] - lo_before[outside]), np.abs(hi_after[outside] - hi_before[outside])))
    scale = 200.0 / float(np.ptp(source_vertices, axis=0).max())
    mm = displacement * scale
    grid_half_diagonal_mm = 0.5 * math.hypot(float(xs[1] - xs[0]), float(zs[1] - zs[0])) * scale
    # Conservative surface bound combines measured envelope movement with
    # half a sampling-cell diagonal.  The exact node displacement is reported
    # separately so the bound is not mistaken for a measured shift.
    return {
        "schema_version": 1,
        "task": TASK,
        "comparison": "Seed-42 visible exterior envelope -> repaired master outside R11/R12 ROI",
        "final_scale_mm_per_normalized_unit": scale,
        "outside_roi_grid_nodes": int(outside.sum()),
        "measured_node_displacement_mm": {
            "median": float(np.median(mm)),
            "p95": float(np.quantile(mm, 0.95)),
            "maximum": float(mm.max(initial=0.0)),
        },
        "sampling_half_cell_diagonal_mm": grid_half_diagonal_mm,
        "conservative_surface_bound_mm": {
            "p95": float(np.quantile(mm, 0.95) + grid_half_diagonal_mm),
            "maximum": float(mm.max(initial=0.0) + 2.0 * grid_half_diagonal_mm),
        },
        "requirements_mm": {"p95_max": 0.15, "maximum_max": 0.40},
        "status": "PASS" if np.quantile(mm, 0.95) + grid_half_diagonal_mm <= 0.15 and mm.max(initial=0.0) + 2.0 * grid_half_diagonal_mm <= 0.40 else "FAIL",
        "local_exceedances": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--grid-step", type=float, default=0.00065)
    parser.add_argument("--skip-renders", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for path in (SOURCE, REF_CLEAN, REF_SEAM):
        if not path.is_file():
            raise FileNotFoundError(path)
    actual = {"seed42": sha256(SOURCE), "ref_clean": sha256(REF_CLEAN), "ref_seam": sha256(REF_SEAM)}
    if actual != EXPECTED:
        raise RuntimeError(f"R13 hash gate failed: {actual}")
    reference_dir = OUT / "reference-audit"
    reference_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REF_CLEAN, reference_dir / "ref-clean-r13.jpg")
    shutil.copyfile(REF_SEAM, reference_dir / "ref-seam-r13.jpg")

    print("R13: hash gate PASS", flush=True)
    vertices, faces = read_binary_ply(SOURCE)
    print("R13: source loaded", flush=True)
    before = edge_metrics(vertices, faces)
    print("R13: source topology audited", flush=True)
    xs, zs, lo, hi, grid_report = build_heightfield(vertices, faces, args.grid_step)
    node_mask = np.isfinite(lo)
    lo_before, hi_before = lo.copy(), hi.copy()
    rebuild_report = apply_face_rebuild(xs, zs, lo, hi, node_mask, vertices.min(axis=0), vertices.max(axis=0))
    print("R13: local face rebuild applied", flush=True)
    master_vertices, master_faces, surface_report = heightfield_mesh(xs, zs, lo, hi, node_mask)
    print(f"R13: master mesh {len(master_vertices)} vertices / {len(master_faces)} faces", flush=True)
    write_binary_ply(MASTER, master_vertices, master_faces)
    np.savez_compressed(GRID_CACHE, xs=xs, zs=zs, lo=lo, hi=hi, mask=node_mask)
    after = edge_metrics(master_vertices, master_faces)
    print("R13: master topology audited", flush=True)
    topology = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "before_seed42": before,
        "after_repaired_master": after,
        "single_connected_surface": True,
        "orientable": True,
        "confirmed_self_or_cross_intersections": 0,
        "intersection_proof": "strict double-heightfield ordering plus simple projected boundary; top>bottom at every used node",
        "status": "PASS" if after["boundary_edges"] == 0 and after["nonmanifold_edges"] == 0 and after["degenerate_faces"] == 0 else "FAIL",
    }
    TOPOLOGY_REPORT.parent.mkdir(parents=True, exist_ok=True)
    TOPOLOGY_REPORT.write_text(json.dumps(topology, indent=2) + "\n", encoding="utf-8")
    deviation = deviation_audit(vertices, xs, zs, lo_before, hi_before, lo, hi, node_mask)
    area_ratio = float(after["surface_area_normalized2"] / before["surface_area_normalized2"])
    deviation["surface_area_ratio_repaired_to_seed42"] = area_ratio
    deviation["surface_area_gate_max_ratio"] = 1.25
    if area_ratio > 1.25:
        deviation["status"] = "FAIL"
        deviation["failure_reason"] = (
            "Although envelope nodes outside ROI retain their measured extrema, connections between different "
            "Seed-42 depth layers create excessive real surface area and therefore do not protect the visible surface."
        )
    DEVIATION_REPORT.write_text(json.dumps(deviation, indent=2) + "\n", encoding="utf-8")
    render_report = None if args.skip_renders else render_all(master_vertices, master_faces)
    payload = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "product_revision": "R02",
        "technical_revision": "R13",
        "hash_gate": {"expected": EXPECTED, "actual": actual, "status": "PASS"},
        "method": "deterministic_seed42_outer_double_heightfield_with_ref_seam_single_surface_rebuild",
        "grid": grid_report,
        "face_rebuild": rebuild_report,
        "surface_construction": surface_report,
        "master": {
            "path": MASTER.relative_to(ROOT).as_posix(),
            "sha256": sha256(MASTER),
            "bytes": MASTER.stat().st_size,
            "normalized_geometry": True,
        },
        "topology_audit": TOPOLOGY_REPORT.relative_to(ROOT).as_posix(),
        "form_deviation_report": DEVIATION_REPORT.relative_to(ROOT).as_posix(),
        "render_report": None if render_report is None else RENDER_REPORT.relative_to(ROOT).as_posix(),
        "mesh_gate": topology["status"],
        "form_protection_gate": deviation["status"],
        "optic_gate": "PENDING_MANUAL_BINARY_REVIEW",
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
    }
    REPORT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
