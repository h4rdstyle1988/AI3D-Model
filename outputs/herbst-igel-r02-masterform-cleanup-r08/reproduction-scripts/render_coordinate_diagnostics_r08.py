#!/usr/bin/env python3
"""Render deterministic coordinate/seam diagnostics for the untouched Seed-42 mesh."""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from inspect_seed42_r08 import read_binary_ply


OUT = Path(__file__).resolve().parents[1]
SOURCE = OUT / "source-r07" / "herbst-igel-r02-trellis-raw-seed-42.ply"
SEAM_IMAGE = OUT / "reference-audit" / "ref-seam-r08.jpg"
DIAG = OUT / "diagnostics"
REPORT = OUT / "reports" / "coordinate-diagnostics-r08.json"


def reference_masks() -> tuple[np.ndarray, np.ndarray, list[int], np.ndarray]:
    rgb = np.asarray(Image.open(SEAM_IMAGE).convert("RGB"), dtype=np.int16)
    red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    blue_mask = (blue > 120) & (blue > red + 35) & (blue > green + 15)
    channel_span = rgb.max(axis=2) - rgb.min(axis=2)
    foreground = (rgb.mean(axis=2) < 238) & ((channel_span > 12) | (rgb.mean(axis=2) < 210))
    foreground = np.asarray(
        Image.fromarray((foreground * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(7))
    ) > 0
    yy, xx = np.nonzero(foreground)
    bbox = [int(xx.min()), int(yy.min()), int(xx.max()), int(yy.max())]

    # Convert the thick JPEG annotation into one deterministic connected path.
    path_mask = np.asarray(
        Image.fromarray((blue_mask * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))
    ) > 0
    sy, sx = np.unravel_index(np.argmin(np.where(path_mask, np.indices(path_mask.shape)[1], 10_000)), path_mask.shape)
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
        raise ValueError("Blue REF-SEAM does not form a connected top-to-bottom path")
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


def project_xz(points: np.ndarray, bounds_min: np.ndarray, bounds_max: np.ndarray, bbox: list[int]) -> tuple[np.ndarray, np.ndarray]:
    x0, y0, x1, y1 = bbox
    u = x0 + (points[:, 0] - bounds_min[0]) / (bounds_max[0] - bounds_min[0]) * (x1 - x0)
    v = y1 - (points[:, 2] - bounds_min[2]) / (bounds_max[2] - bounds_min[2]) * (y1 - y0)
    return u, v


def render_side_mapping(centers: np.ndarray, bounds_min: np.ndarray, bounds_max: np.ndarray, blue_mask: np.ndarray, body: np.ndarray, bbox: list[int], rgb: np.ndarray) -> dict[str, int]:
    height, width = body.shape
    u, v = project_xz(centers, bounds_min, bounds_max, bbox)
    ui = np.rint(u).astype(np.int32)
    vi = np.rint(v).astype(np.int32)
    valid = (ui >= 0) & (ui < width) & (vi >= 0) & (vi < height)
    is_body = np.zeros(len(centers), dtype=bool)
    is_body[valid] = body[vi[valid], ui[valid]]
    canvas = np.full((height, width, 3), 245, dtype=np.uint8)
    flat = vi[valid] * width + ui[valid]
    # Rear-to-front order for visible reference side (-Y camera): lower Y is nearer.
    order = np.argsort(centers[valid, 1])[::-1]
    colors = np.where(is_body[valid, None], np.array([229, 191, 139]), np.array([177, 78, 34])).astype(np.uint8)
    canvas.reshape(-1, 3)[flat[order]] = colors[order]
    canvas[blue_mask] = np.array([0, 100, 255], dtype=np.uint8)
    mapped = Image.fromarray(canvas).resize((768, 768), Image.Resampling.NEAREST)
    mapped.save(DIAG / "seed42-side-ref-seam-mapping-r08.png")

    overlay = Image.blend(Image.fromarray(rgb), Image.fromarray(canvas), 0.48).resize((768, 768), Image.Resampling.LANCZOS)
    overlay.save(DIAG / "ref-seam-mesh-overlay-r08.png")

    mask_rgb = np.full((height, width, 3), 250, dtype=np.uint8)
    mask_rgb[body] = np.array([229, 191, 139], dtype=np.uint8)
    mask_rgb[blue_mask] = np.array([0, 100, 255], dtype=np.uint8)
    Image.fromarray(mask_rgb).resize((768, 768), Image.Resampling.NEAREST).save(DIAG / "ref-seam-body-mask-r08.png")
    return {
        "triangle_centers_in_mapped_body_region": int(np.count_nonzero(is_body)),
        "triangle_centers_outside_mapped_body_region": int(len(is_body) - np.count_nonzero(is_body)),
    }


def cross_sections(vertices: np.ndarray, bounds_min: np.ndarray, bounds_max: np.ndarray) -> list[dict[str, float]]:
    records = []
    width, height = 900, 700
    span_y = bounds_max[1] - bounds_min[1]
    levels = [-0.15, -0.10, -0.05, 0.00, 0.05, 0.10, 0.20]
    for level in levels:
        half_band = span_y * 0.004
        section = vertices[np.abs(vertices[:, 1] - level) <= half_band]
        canvas = Image.new("RGB", (width, height), (248, 248, 248))
        draw = ImageDraw.Draw(canvas)
        draw.text((18, 15), f"Seed 42 cross-section: Y={level:+.3f} +/- {half_band:.4f}", fill=(20, 20, 20))
        if len(section):
            px = 45 + (section[:, 0] - bounds_min[0]) / (bounds_max[0] - bounds_min[0]) * (width - 90)
            py = height - 45 - (section[:, 2] - bounds_min[2]) / (bounds_max[2] - bounds_min[2]) * (height - 90)
            for x, y in zip(px.astype(int), py.astype(int)):
                if 0 <= x < width and 0 <= y < height:
                    draw.point((x, y), fill=(153, 65, 29))
        path = DIAG / f"cross-section-y-{level:+.2f}.png"
        canvas.save(path)
        records.append({"y": level, "half_band": float(half_band), "vertex_samples": int(len(section))})
    return records


def coordinate_render(points: np.ndarray, horizontal_axis: int, vertical_axis: int, depth_axis: int, near_is_low: bool, name: str) -> None:
    size = 1000
    lo, hi = points.min(axis=0), points.max(axis=0)
    u = (points[:, horizontal_axis] - lo[horizontal_axis]) / (hi[horizontal_axis] - lo[horizontal_axis])
    v = (points[:, vertical_axis] - lo[vertical_axis]) / (hi[vertical_axis] - lo[vertical_axis])
    px = np.clip(np.rint(50 + u * 900).astype(np.int32), 0, size - 1)
    py = np.clip(np.rint(950 - v * 900).astype(np.int32), 0, size - 1)
    depth = points[:, depth_axis]
    flat = py * size + px
    order = np.lexsort((depth if near_is_low else -depth, flat))
    ordered_flat = flat[order]
    first = np.empty(len(order), dtype=bool)
    first[0] = True
    first[1:] = ordered_flat[1:] != ordered_flat[:-1]
    selected = order[first]
    norm = np.clip((depth[selected] - lo[depth_axis]) / (hi[depth_axis] - lo[depth_axis]), 0.0, 1.0)
    colors = np.column_stack((40 + 205 * norm, 75 + 110 * (1.0 - np.abs(norm - 0.5) * 2.0), 245 - 205 * norm)).astype(np.uint8)
    canvas = np.full((size * size, 3), 246, dtype=np.uint8)
    canvas[flat[selected]] = colors
    image = Image.fromarray(canvas.reshape(size, size, 3))
    mask = Image.fromarray((np.any(np.asarray(image) != 246, axis=2) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))
    expanded = image.filter(ImageFilter.MinFilter(3))
    result = Image.new("RGB", (size, size), (246, 246, 246))
    result.paste(expanded, mask=mask)
    draw = ImageDraw.Draw(result)
    axis_names = "XYZ"
    draw.rectangle((0, 0, size, 45), fill=(255, 255, 255))
    draw.text((15, 15), f"{name}: horizontal {axis_names[horizontal_axis]}, vertical {axis_names[vertical_axis]}, color/depth {axis_names[depth_axis]} ({lo[depth_axis]:+.3f} blue -> {hi[depth_axis]:+.3f} red)", fill=(15, 15, 15))
    result.save(DIAG / f"coordinate-{name}.png")


def main() -> None:
    DIAG.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    vertices, faces = read_binary_ply(SOURCE)
    used = np.zeros(len(vertices), dtype=bool)
    used[np.unique(faces)] = True
    vertices = vertices[used]
    # Faces are used only to form representative surface samples; original indexing is retained above.
    original_vertices, original_faces = read_binary_ply(SOURCE)
    centers = original_vertices[original_faces].mean(axis=1)
    bounds_min, bounds_max = vertices.min(axis=0), vertices.max(axis=0)
    blue_mask, body, bbox, rgb = reference_masks()
    mapping = render_side_mapping(centers, bounds_min, bounds_max, blue_mask, body, bbox, rgb)
    sections = cross_sections(vertices, bounds_min, bounds_max)
    coordinate_render(centers, 1, 2, 0, True, "front-yz-depth-x")
    coordinate_render(centers, 0, 2, 1, True, "left-xz-depth-y")
    coordinate_render(centers, 0, 1, 2, False, "top-xy-depth-z")
    payload = {
        "schema_version": 1,
        "operation": "read_only_coordinate_and_seam_diagnostics",
        "mesh_projection": {
            "reference_side_camera": "-Y",
            "screen_horizontal": "+X (front to rear)",
            "screen_vertical": "+Z",
            "mapping": "REF-SEAM foreground bbox mapped affinely to the used-vertex X/Z bounds",
            "reference_foreground_bbox_px": bbox,
        },
        "body_region_extraction": {
            "method": "shortest 8-connected center path through the blue REF-SEAM annotation, closed against the left/bottom foreground bounds",
            "body_mask_pixels": int(body.sum()),
            "blue_seam_pixels": int(blue_mask.sum()),
        },
        "mapping_counts": mapping,
        "cross_sections": sections,
        "outputs": [
            "diagnostics/seed42-side-ref-seam-mapping-r08.png",
            "diagnostics/ref-seam-mesh-overlay-r08.png",
            "diagnostics/ref-seam-body-mask-r08.png",
            "diagnostics/coordinate-front-yz-depth-x.png",
            "diagnostics/coordinate-left-xz-depth-y.png",
            "diagnostics/coordinate-top-xy-depth-z.png",
        ] + [f"diagnostics/cross-section-y-{x['y']:+.2f}.png" for x in sections],
    }
    REPORT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
