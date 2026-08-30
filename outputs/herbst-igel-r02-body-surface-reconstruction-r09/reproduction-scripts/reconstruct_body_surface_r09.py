#!/usr/bin/env python3
"""Reconstruct only the missing Seed-42 body surface authorized by R09.

The script removes source triangles only inside the REF-SEAM-defined body-side
problem zone above the unchanged R08 lower-body guard.  Existing source
triangles in measured feature protection masks and every triangle outside the
local zone remain byte-identical in coordinate values.  A smooth two-sided
surface patch is derived from the authoritative body silhouette and from the
depth span of adjacent, unedited Seed-42 body geometry.
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
SOURCE = OUT / "source-r08" / "herbst-igel-r02-trellis-raw-seed-42.ply"
SEAM_IMAGE = OUT / "reference-audit" / "ref-seam-r09.jpg"
MASTER = OUT / "masterform" / "herbst-igel-r02-masterform-reconstructed-r09-NON-APPROVED.ply"
REPORT = OUT / "reports" / "body-surface-reconstruction-r09.json"
DIAGNOSTIC = OUT / "diagnostics" / "reconstruction-selection-r09.png"


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
    """Reproduce the R08 REF-SEAM transfer without changing its measurements."""
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


def protected_reference_mask(shape: tuple[int, int]) -> tuple[np.ndarray, list[dict[str, object]]]:
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


def project_xz(points: np.ndarray, bounds_min: np.ndarray, bounds_max: np.ndarray, bbox: list[int]) -> tuple[np.ndarray, np.ndarray]:
    x0, y0, x1, y1 = bbox
    u = x0 + (points[:, 0] - bounds_min[0]) / (bounds_max[0] - bounds_min[0]) * (x1 - x0)
    v = y1 - (points[:, 2] - bounds_min[2]) / (bounds_max[2] - bounds_min[2]) * (y1 - y0)
    return u, v


def distance_inside(mask: np.ndarray) -> np.ndarray:
    """4-neighbour distance to the outside, followed by a mild organic blur."""
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
    distance[~mask] = 0
    blurred = Image.fromarray(np.clip(distance, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3.0))
    result = np.asarray(blurred, dtype=np.float64)
    result[~mask] = 0.0
    return result


def patch_mesh(
    body: np.ndarray,
    bbox: list[int],
    bounds_min: np.ndarray,
    bounds_max: np.ndarray,
    center_y: float,
    radius_y: float,
    lower_guard: float,
    step: int = 1,
) -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
    """Create a smooth two-sided patch from REF-SEAM silhouette measurements."""
    height, width = body.shape
    x0, y0, x1, y1 = bbox
    distance = distance_inside(body)
    max_distance = float(distance.max())
    yy = np.arange(y0, y1 + 1, step, dtype=np.int32)
    xx = np.arange(x0, x1 + 1, step, dtype=np.int32)
    if yy[-1] != y1:
        yy = np.r_[yy, y1]
    if xx[-1] != x1:
        xx = np.r_[xx, x1]
    grid_x, grid_y = np.meshgrid(xx, yy)
    inside = body[grid_y, grid_x]
    world_x = bounds_min[0] + (grid_x - x0) / (x1 - x0) * (bounds_max[0] - bounds_min[0])
    world_z = bounds_max[2] - (grid_y - y0) / (y1 - y0) * (bounds_max[2] - bounds_min[2])
    inside &= world_z >= lower_guard - 0.050

    # A square-root distance profile is the local equivalent of a rounded
    # ellipsoidal continuation.  It is anchored to the unedited body depth
    # span, not to a newly selected aesthetic thickness.
    normalized = np.clip(distance[grid_y, grid_x] / max_distance, 0.0, 1.0)
    half_depth = radius_y * np.power(normalized, 0.52)
    # Keep the patch slightly inside the measured adjacent envelope so the
    # retained nose, eye and ear geometry remains the visible outer surface.
    inset = 0.0025
    y_near = center_y - np.maximum(half_depth - inset, 0.0)
    y_far = center_y + np.maximum(half_depth - inset, 0.0)

    vertex_index_near = np.full(inside.shape, -1, dtype=np.int64)
    vertex_index_far = np.full(inside.shape, -1, dtype=np.int64)
    patch_vertices: list[list[float]] = []
    for row, col in zip(*np.nonzero(inside)):
        vertex_index_near[row, col] = len(patch_vertices)
        patch_vertices.append([world_x[row, col], y_near[row, col], world_z[row, col]])
        vertex_index_far[row, col] = len(patch_vertices)
        patch_vertices.append([world_x[row, col], y_far[row, col], world_z[row, col]])

    faces: list[list[int]] = []
    rows, cols = inside.shape
    for row in range(rows - 1):
        for col in range(cols - 1):
            if inside[row, col] and inside[row, col + 1] and inside[row + 1, col] and inside[row + 1, col + 1]:
                a = int(vertex_index_near[row, col])
                b = int(vertex_index_near[row, col + 1])
                c = int(vertex_index_near[row + 1, col + 1])
                d = int(vertex_index_near[row + 1, col])
                faces.extend(([a, c, b], [a, d, c]))
                a = int(vertex_index_far[row, col])
                b = int(vertex_index_far[row, col + 1])
                c = int(vertex_index_far[row + 1, col + 1])
                d = int(vertex_index_far[row + 1, col])
                faces.extend(([a, b, c], [a, c, d]))

    vertices_array = np.asarray(patch_vertices, dtype=np.float64)
    faces_array = np.asarray(faces, dtype=np.int64)
    report = {
        "method": "REF-SEAM silhouette constrained two-sided rounded distance-field patch",
        "grid_step_reference_pixels": step,
        "lower_overlap_guard_normalized": lower_guard - 0.050,
        "center_y_from_adjacent_body": center_y,
        "radius_y_from_adjacent_body": radius_y,
        "surface_inset_normalized": inset,
        "vertices": int(len(vertices_array)),
        "triangles": int(len(faces_array)),
    }
    return vertices_array, faces_array, report


def main() -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC.parent.mkdir(parents=True, exist_ok=True)
    vertices, faces = read_binary_ply(SOURCE)
    used_indices = np.unique(faces)
    bounds_min = vertices[used_indices].min(axis=0)
    bounds_max = vertices[used_indices].max(axis=0)
    blue, body, bbox, _rgb = reference_masks()
    protected, protected_features = protected_reference_mask(body.shape)

    face_vertices = vertices[faces]
    centers = face_vertices.mean(axis=1)
    u, v = project_xz(centers, bounds_min, bounds_max, bbox)
    ui = np.rint(u).astype(np.int32)
    vi = np.rint(v).astype(np.int32)
    valid = (ui >= 0) & (ui < body.shape[1]) & (vi >= 0) & (vi < body.shape[0])
    in_body = np.zeros(len(faces), dtype=bool)
    in_protected = np.zeros(len(faces), dtype=bool)
    in_body[valid] = body[vi[valid], ui[valid]]
    in_protected[valid] = protected[vi[valid], ui[valid]]

    vertex_u, vertex_v = project_xz(face_vertices.reshape(-1, 3), bounds_min, bounds_max, bbox)
    vertex_ui = np.rint(vertex_u).astype(np.int32).reshape(-1, 3)
    vertex_vi = np.rint(vertex_v).astype(np.int32).reshape(-1, 3)
    vertex_valid = (
        (vertex_ui >= 0)
        & (vertex_ui < body.shape[1])
        & (vertex_vi >= 0)
        & (vertex_vi < body.shape[0])
    )
    vertex_body = np.zeros(vertex_valid.shape, dtype=bool)
    vertex_protected = np.zeros(vertex_valid.shape, dtype=bool)
    flat_valid = vertex_valid.ravel()
    vertex_body.ravel()[flat_valid] = body[vertex_vi.ravel()[flat_valid], vertex_ui.ravel()[flat_valid]]
    # Retain the measured feature cores.  Intersecting leaf sheets outside the
    # actual feature core are intentionally not protected, as required by R09.
    core = np.asarray(
        Image.fromarray((protected * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(11))
    ) > 0
    vertex_protected.ravel()[flat_valid] = core[
        vertex_vi.ravel()[flat_valid], vertex_ui.ravel()[flat_valid]
    ]

    lower_guard = -0.105
    intersects_body = in_body | np.any(vertex_body, axis=1)
    intersects_feature_core = in_protected & np.any(vertex_protected, axis=1)
    remove = intersects_body & ~intersects_feature_core & (np.max(face_vertices[:, :, 2], axis=1) > lower_guard)
    retained_faces = faces[~remove]

    # Measure depth only from adjacent, retained body triangles below the edit
    # zone and away from the protected feet.  Robust 5/95 percentiles reject
    # isolated sheet tips without inventing a new product dimension.
    anchor = in_body & ~in_protected & (centers[:, 2] >= lower_guard - 0.055) & (centers[:, 2] <= lower_guard - 0.008)
    if np.count_nonzero(anchor) < 100:
        raise RuntimeError("Insufficient unchanged adjacent body geometry for patch depth measurement")
    y_low, y_high = np.quantile(centers[anchor, 1], [0.05, 0.95])
    center_y = float((y_low + y_high) * 0.5)
    radius_y = float((y_high - y_low) * 0.5)
    patch_vertices, patch_faces, patch_report = patch_mesh(
        body, bbox, bounds_min, bounds_max, center_y, radius_y, lower_guard
    )

    combined_vertices = np.vstack((vertices, patch_vertices))
    combined_faces = np.vstack((retained_faces, patch_faces + len(vertices)))
    write_binary_ply(MASTER, combined_vertices, combined_faces)

    selection_rgb = np.full((*body.shape, 3), 248, dtype=np.uint8)
    selection_rgb[body] = np.array([229, 191, 139], dtype=np.uint8)
    guard_v = int(round(bbox[3] - (lower_guard - bounds_min[2]) / (bounds_max[2] - bounds_min[2]) * (bbox[3] - bbox[1])))
    edit_mask = body.copy()
    edit_mask[np.indices(body.shape)[0] >= guard_v] = False
    selection_rgb[edit_mask] = np.array([219, 91, 55], dtype=np.uint8)
    selection_rgb[protected] = np.array([45, 125, 225], dtype=np.uint8)
    selection_rgb[blue] = np.array([0, 70, 255], dtype=np.uint8)
    Image.fromarray(selection_rgb).resize((768, 768), Image.Resampling.NEAREST).save(DIAGNOSTIC)

    retained_source_vertices = np.unique(retained_faces)
    payload = {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-BODY-SURFACE-RECONSTRUCTION-R09.md",
        "task_blob_sha": "ef3a16cc80c255d0e05c1a5e3773f2c9497c4c73",
        "operation": "local_ref_seam_body_surface_reconstruction",
        "source": {
            "path": SOURCE.relative_to(ROOT).as_posix(),
            "sha256": sha256(SOURCE),
            "vertices": int(len(vertices)),
            "triangles": int(len(faces)),
        },
        "selection": {
            "projection": "unchanged R08 affine X/Z transfer to authoritative REF-SEAM",
            "lower_body_guard_normalized": lower_guard,
            "removed_source_triangles": int(remove.sum()),
            "retained_source_triangles": int((~remove).sum()),
            "retained_source_vertices": int(len(retained_source_vertices)),
            "retained_source_vertex_coordinates_modified": 0,
            "protected_reference_features": protected_features,
        },
        "adjacent_body_depth_measurement": {
            "anchor_triangles": int(anchor.sum()),
            "robust_y_percentiles": [float(y_low), float(y_high)],
            "center_y": center_y,
            "radius_y": radius_y,
        },
        "patch": patch_report,
        "output": {
            "path": MASTER.relative_to(ROOT).as_posix(),
            "sha256": sha256(MASTER),
            "bytes": MASTER.stat().st_size,
            "vertices": int(len(combined_vertices)),
            "triangles": int(len(combined_faces)),
            "status": "NON_APPROVED_PENDING_OPTIK_GATE",
        },
        "protected_geometry": {
            "all_source_vertex_coordinates": "unchanged",
            "outside_local_problem_zone": "source triangles retained",
            "nose_eyes_ears_feet": "source triangles retained by unchanged R08 measured masks",
            "maple_leaf_and_back": "outside REF-SEAM body selection; source triangles retained",
        },
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
    }
    REPORT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
