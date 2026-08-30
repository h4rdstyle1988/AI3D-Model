#!/usr/bin/env python3
"""Perform the approved local REF-SEAM-guided cleanup of R07 Seed 42.

The topology is kept intact.  Only vertices on the body side of REF-SEAM and
within a narrow inward band are relaxed.  Confirmed face features are protected
by reference-space masks.  Taubin passes reduce the foreign leaf/spine relief
without global shrinkage or movement of the protected back.
"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from inspect_seed42_r08 import read_binary_ply
from render_coordinate_diagnostics_r08 import project_xz, reference_masks


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
SOURCE = OUT / "source-r07" / "herbst-igel-r02-trellis-raw-seed-42.ply"
MASTER = OUT / "masterform" / "herbst-igel-r02-masterform-cleanup-attempt-r08-NON-MASTER.ply"
REPORT = OUT / "reports" / "masterform-cleanup-operation-r08.json"
DIAG = OUT / "diagnostics" / "cleanup-selection-r08.png"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


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
    records["indices"] = faces.astype("<i4", copy=False)
    with path.open("wb") as stream:
        stream.write(header)
        np.asarray(vertices, dtype="<f4").tofile(stream)
        records.tofile(stream)


def used_mesh(vertices: np.ndarray, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray, int]:
    used_indices = np.unique(faces)
    remap = np.full(len(vertices), -1, dtype=np.int64)
    remap[used_indices] = np.arange(len(used_indices), dtype=np.int64)
    return vertices[used_indices].copy(), remap[faces], int(len(vertices) - len(used_indices))


def seam_distance(body: np.ndarray, blue: np.ndarray) -> np.ndarray:
    height, width = body.shape
    distance = np.full((height, width), 32767, dtype=np.int16)
    sources = np.asarray(Image.fromarray((blue * 255).astype(np.uint8)).resize((width, height))) > 0
    queue: deque[tuple[int, int]] = deque()
    for y, x in zip(*np.nonzero(sources)):
        distance[y, x] = 0
        queue.append((int(y), int(x)))
    while queue:
        y, x = queue.popleft()
        candidate = int(distance[y, x]) + 1
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < height and 0 <= nx < width and candidate < distance[ny, nx]:
                distance[ny, nx] = candidate
                queue.append((ny, nx))
    distance[~body] = 32767
    return distance


def protected_reference_mask(shape: tuple[int, int]) -> tuple[np.ndarray, list[dict[str, object]]]:
    # Pixel coordinates are direct measurements in the authoritative 384x384
    # REF-SEAM image.  They are protection masks, not replacement geometry.
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
    return np.asarray(image) > 0, features


def directed_adjacency(vertex_count: int, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    edges = np.concatenate((faces[:, (0, 1)], faces[:, (1, 2)], faces[:, (2, 0)]), axis=0)
    edges.sort(axis=1)
    keys = edges[:, 0].astype(np.uint64) * np.uint64(vertex_count) + edges[:, 1].astype(np.uint64)
    keep = np.empty(len(keys), dtype=bool)
    order = np.argsort(keys)
    sorted_edges = edges[order]
    keep[0] = True
    keep[1:] = np.any(sorted_edges[1:] != sorted_edges[:-1], axis=1)
    unique_edges = sorted_edges[keep]
    sources = np.concatenate((unique_edges[:, 0], unique_edges[:, 1]))
    targets = np.concatenate((unique_edges[:, 1], unique_edges[:, 0]))
    order = np.argsort(sources, kind="stable")
    sources, targets = sources[order], targets[order]
    starts = np.flatnonzero(np.r_[True, sources[1:] != sources[:-1]])
    owners = sources[starts]
    degrees = np.diff(np.r_[starts, len(sources)])
    return targets, starts, owners, degrees


def neighbor_mean(vertices: np.ndarray, targets: np.ndarray, starts: np.ndarray, owners: np.ndarray, degrees: np.ndarray) -> np.ndarray:
    sums = np.add.reduceat(vertices[targets], starts, axis=0)
    means = vertices.copy()
    means[owners] = sums / degrees[:, None]
    return means


def filled_filtered_depth(
    u: np.ndarray,
    v: np.ndarray,
    depth: np.ndarray,
    width: int,
    height: int,
    mode: str,
    kernel: int = 35,
) -> tuple[np.ndarray, tuple[float, float]]:
    ui = np.clip(np.rint(u).astype(np.int32), 0, width - 1)
    vi = np.clip(np.rint(v).astype(np.int32), 0, height - 1)
    flat = vi * width + ui
    if mode == "min":
        values = np.full(height * width, np.inf, dtype=np.float64)
        np.minimum.at(values, flat, depth)
    elif mode == "max":
        values = np.full(height * width, -np.inf, dtype=np.float64)
        np.maximum.at(values, flat, depth)
    else:
        raise ValueError(mode)
    finite = np.isfinite(values)
    lo, hi = float(depth.min()), float(depth.max())
    queue: deque[int] = deque(int(x) for x in np.flatnonzero(finite))
    # Nearest occupied-pixel extension prevents the median from seeing a fake
    # background depth at silhouette and sampling holes.
    while queue:
        index = queue.popleft()
        y, x = divmod(index, width)
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < height and 0 <= nx < width:
                other = ny * width + nx
                if not finite[other]:
                    finite[other] = True
                    values[other] = values[index]
                    queue.append(other)
    encoded = np.clip(np.rint((values.reshape(height, width) - lo) / (hi - lo) * 255.0), 0, 255).astype(np.uint8)
    filtered = Image.fromarray(encoded).filter(ImageFilter.MedianFilter(kernel)).filter(ImageFilter.GaussianBlur(3.0))
    decoded = np.asarray(filtered, dtype=np.float64) / 255.0 * (hi - lo) + lo
    return decoded, (lo, hi)


def project_outer_envelopes(
    vertices: np.ndarray,
    selection: np.ndarray,
    u_ref: np.ndarray,
    v_ref: np.ndarray,
    ref_shape: tuple[int, int],
) -> dict[str, object]:
    height, width = ref_shape
    before = vertices.copy()
    tolerance = 0.0045
    operations: list[dict[str, object]] = []

    # Reference and opposite side envelopes, using the seam-aligned X/Z map.
    for label, mode, sign in (("reference_side_y_min", "min", -1), ("opposite_side_y_max", "max", 1)):
        target, depth_range = filled_filtered_depth(u_ref, v_ref, before[:, 1], width, height, mode)
        ui = np.clip(np.rint(u_ref).astype(np.int32), 0, width - 1)
        vi = np.clip(np.rint(v_ref).astype(np.int32), 0, height - 1)
        desired = target[vi, ui]
        delta = (vertices[:, 1] - desired) * sign
        move = selection & (delta > tolerance)
        vertices[move, 1] = desired[move] + sign * tolerance
        operations.append({"name": label, "moved_vertices": int(move.sum()), "source_depth_range": list(depth_range)})

    lo, hi = before.min(axis=0), before.max(axis=0)
    grid = 384
    ypix = (before[:, 1] - lo[1]) / (hi[1] - lo[1]) * (grid - 1)
    zpix = (hi[2] - before[:, 2]) / (hi[2] - lo[2]) * (grid - 1)
    target_x, depth_range = filled_filtered_depth(ypix, zpix, before[:, 0], grid, grid, "min")
    yi = np.clip(np.rint(ypix).astype(np.int32), 0, grid - 1)
    zi = np.clip(np.rint(zpix).astype(np.int32), 0, grid - 1)
    desired_x = target_x[zi, yi]
    move_x = selection & ((desired_x - vertices[:, 0]) > tolerance)
    vertices[move_x, 0] = desired_x[move_x] - tolerance
    operations.append({"name": "front_x_min", "moved_vertices": int(move_x.sum()), "source_depth_range": list(depth_range)})

    xpix = (before[:, 0] - lo[0]) / (hi[0] - lo[0]) * (grid - 1)
    ypix_top = (before[:, 1] - lo[1]) / (hi[1] - lo[1]) * (grid - 1)
    target_z, depth_range = filled_filtered_depth(xpix, ypix_top, before[:, 2], grid, grid, "max")
    xi = np.clip(np.rint(xpix).astype(np.int32), 0, grid - 1)
    yi_top = np.clip(np.rint(ypix_top).astype(np.int32), 0, grid - 1)
    desired_z = target_z[yi_top, xi]
    move_z = selection & ((vertices[:, 2] - desired_z) > tolerance)
    vertices[move_z, 2] = desired_z[move_z] + tolerance
    operations.append({"name": "top_z_max", "moved_vertices": int(move_z.sum()), "source_depth_range": list(depth_range)})

    displacement = np.linalg.norm(vertices - before, axis=1)
    return {
        "method": "35 px robust median plus 3 px Gaussian outer-envelope projection",
        "outward_tolerance_normalized": tolerance,
        "operations": operations,
        "moved_vertices_union": int(np.count_nonzero(displacement > 1e-12)),
        "max_projection_displacement_normalized": float(displacement.max(initial=0.0)),
    }


def main() -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    DIAG.parent.mkdir(parents=True, exist_ok=True)
    original_vertices, original_faces = read_binary_ply(SOURCE)
    vertices, faces, unused_removed = used_mesh(original_vertices, original_faces)
    source_vertices = vertices.copy()
    lo, hi = vertices.min(axis=0), vertices.max(axis=0)
    blue, body, bbox, _rgb = reference_masks()
    distance = seam_distance(body, blue)
    protected, protected_features = protected_reference_mask(body.shape)
    u, v = project_xz(vertices, lo, hi, bbox)
    ui = np.rint(u).astype(np.int32)
    vi = np.rint(v).astype(np.int32)
    valid = (ui >= 0) & (ui < body.shape[1]) & (vi >= 0) & (vi < body.shape[0])
    body_vertex = np.zeros(len(vertices), dtype=bool)
    dist_vertex = np.full(len(vertices), 32767, dtype=np.int16)
    protected_vertex = np.zeros(len(vertices), dtype=bool)
    body_vertex[valid] = body[vi[valid], ui[valid]]
    dist_vertex[valid] = distance[vi[valid], ui[valid]]
    protected_vertex[valid] = protected[vi[valid], ui[valid]]

    band_px = 78
    selection = body_vertex & (dist_vertex >= 4) & (dist_vertex <= band_px) & ~protected_vertex
    # Preserve the entire underside and low body outside the visible overhang zone.
    selection &= vertices[:, 2] > -0.105
    weight = np.zeros(len(vertices), dtype=np.float64)
    d = dist_vertex.astype(np.float64)
    ramp_in = np.clip((d - 4.0) / 16.0, 0.0, 1.0)
    ramp_out = np.clip((band_px - d) / 18.0, 0.0, 1.0)
    weight[selection] = np.minimum(ramp_in[selection], ramp_out[selection])

    envelope_report = project_outer_envelopes(vertices, selection, u, v, body.shape)

    targets, starts, owners, degrees = directed_adjacency(len(vertices), faces)
    iterations = 64
    lambda_step = 0.42
    mu_step = -0.435
    for _ in range(iterations):
        mean = neighbor_mean(vertices, targets, starts, owners, degrees)
        vertices += (lambda_step * weight)[:, None] * (mean - vertices)
        mean = neighbor_mean(vertices, targets, starts, owners, degrees)
        vertices += (mu_step * weight)[:, None] * (mean - vertices)

    displacement = np.linalg.norm(vertices - source_vertices, axis=1)
    write_binary_ply(MASTER, vertices, faces)

    # Visual proof of the exact projected edit/protection mask.
    mask_rgb = np.full((*body.shape, 3), 248, dtype=np.uint8)
    mask_rgb[body] = np.array([232, 219, 196], dtype=np.uint8)
    edit_pixels = body & (distance >= 4) & (distance <= band_px)
    mask_rgb[edit_pixels] = np.array([219, 91, 55], dtype=np.uint8)
    mask_rgb[protected] = np.array([45, 125, 225], dtype=np.uint8)
    mask_rgb[blue] = np.array([0, 70, 255], dtype=np.uint8)
    Image.fromarray(mask_rgb).resize((768, 768), Image.Resampling.NEAREST).save(DIAG)

    moved = displacement > 1e-12
    payload = {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-MASTERFORM-CLEANUP-R08.md",
        "operation": "local_ref_seam_guided_taubin_relaxation",
        "source": {
            "path": SOURCE.relative_to(ROOT).as_posix(),
            "sha256": sha256(SOURCE),
            "vertices": int(len(original_vertices)),
            "triangles": int(len(original_faces)),
            "unused_vertices_removed": unused_removed,
        },
        "seam_transfer": {
            "projection": "reference side -Y; affine X/Z mapping against used Seed-42 bounds",
            "band_px_inward": band_px,
            "lower_z_guard_normalized": -0.105,
            "protected_reference_features": protected_features,
        },
        "relaxation": {
            "envelope_projection": envelope_report,
            "method": "weighted Taubin neighbor relaxation on original connectivity",
            "iterations": iterations,
            "lambda": lambda_step,
            "mu": mu_step,
            "selected_vertices": int(selection.sum()),
            "moved_vertices": int(moved.sum()),
            "unchanged_vertices_exact": int((~moved).sum()),
            "max_displacement_normalized": float(displacement.max(initial=0.0)),
            "mean_displacement_selected_normalized": float(displacement[selection].mean()) if selection.any() else 0.0,
            "p95_displacement_selected_normalized": float(np.percentile(displacement[selection], 95)) if selection.any() else 0.0,
            "faces_and_connectivity_changed": False,
            "vertices_outside_edit_mask_changed": bool(np.any(displacement[~selection] > 1e-12)),
        },
        "output": {
            "path": MASTER.relative_to(ROOT).as_posix(),
            "bytes": MASTER.stat().st_size,
            "sha256": sha256(MASTER),
            "vertices": int(len(vertices)),
            "triangles": int(len(faces)),
        },
        "protected_geometry": {
            "back_outside_ref_seam": "exact vertex preservation",
            "nose_eyes_ears_feet": "reference-space protection masks; exact vertex preservation",
            "maple_leaf": "outside body-side cleanup mask; exact vertex preservation",
        },
    }
    REPORT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
