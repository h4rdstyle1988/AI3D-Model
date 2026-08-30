#!/usr/bin/env python3
"""Quantify whether Seed 42 contains a continuous body sheet behind overhangs."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from inspect_seed42_r08 import read_binary_ply
from render_coordinate_diagnostics_r08 import project_xz, reference_masks


OUT = Path(__file__).resolve().parents[1]
SOURCE = OUT / "source-r07" / "herbst-igel-r02-trellis-raw-seed-42.ply"
DIAG = OUT / "diagnostics"
REPORT = OUT / "reports" / "hidden-body-surface-analysis-r08.json"


def cluster_count(occupied: np.ndarray) -> np.ndarray:
    closed = occupied | np.roll(occupied, 1, axis=1) | np.roll(occupied, -1, axis=1)
    closed[:, 0] = occupied[:, 0] | occupied[:, 1]
    closed[:, -1] = occupied[:, -1] | occupied[:, -2]
    starts = closed & ~np.roll(closed, 1, axis=1)
    starts[:, 0] = closed[:, 0]
    return starts.sum(axis=1)


def save_cluster_map(counts: np.ndarray, body: np.ndarray, path: Path, title: str) -> None:
    palette = np.array([
        [246, 246, 246],
        [220, 220, 220],
        [233, 195, 137],
        [255, 190, 70],
        [210, 65, 50],
        [120, 35, 130],
    ], dtype=np.uint8)
    clipped = np.clip(counts, 0, 5)
    rgb = palette[clipped]
    rgb[~body] = np.array([246, 246, 246], dtype=np.uint8)
    image = Image.fromarray(rgb).resize((768, 768), Image.Resampling.NEAREST)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 768, 34), fill=(255, 255, 255))
    draw.text((10, 11), title + " | gray=1, tan=2, yellow=3, red=4, purple>=5", fill=(15, 15, 15))
    image.save(path)


def main() -> None:
    DIAG.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    vertices, faces = read_binary_ply(SOURCE)
    centers = vertices[faces].mean(axis=1)
    used = vertices[np.unique(faces)]
    lo, hi = used.min(axis=0), used.max(axis=0)
    _blue, body, bbox, _rgb = reference_masks()
    height, width = body.shape

    # Reference-side (-Y camera): X/Z pixels with occupied Y depth bands.
    u, v = project_xz(centers, lo, hi, bbox)
    ui = np.rint(u).astype(np.int32)
    vi = np.rint(v).astype(np.int32)
    valid = (ui >= 0) & (ui < width) & (vi >= 0) & (vi < height)
    body_center = np.zeros(len(centers), dtype=bool)
    body_center[valid] = body[vi[valid], ui[valid]]
    valid &= body_center
    depth_bins = 160
    yi = np.clip(((centers[:, 1] - lo[1]) / (hi[1] - lo[1]) * (depth_bins - 1)).astype(np.int16), 0, depth_bins - 1)
    occ_y = np.zeros((height * width, depth_bins), dtype=np.bool_)
    occ_y[vi[valid] * width + ui[valid], yi[valid]] = True
    count_y = cluster_count(occ_y).reshape(height, width)
    save_cluster_map(count_y, body, DIAG / "hidden-layers-reference-side-r08.png", "Reference-side Y-depth clusters inside mapped body")

    active = body & (count_y > 0)
    # Four separated bands are the conservative signature of covering sheet
    # front/back plus underlying body front/back. Three is ambiguous at contacts.
    confirmed_hidden = body & (count_y >= 4)
    ambiguous_extra = body & (count_y == 3)
    ordinary_two = body & (count_y == 2)
    insufficient = body & (count_y <= 1)

    # Front (-X camera): Y/Z pixels, but accept only samples whose own X/Z
    # position lies in the mapped body polygon.
    grid = 320
    yi2 = np.clip(((centers[:, 1] - lo[1]) / (hi[1] - lo[1]) * (grid - 1)).astype(np.int32), 0, grid - 1)
    zi2 = np.clip(((centers[:, 2] - lo[2]) / (hi[2] - lo[2]) * (grid - 1)).astype(np.int32), 0, grid - 1)
    xi2 = np.clip(((centers[:, 0] - lo[0]) / (hi[0] - lo[0]) * (depth_bins - 1)).astype(np.int16), 0, depth_bins - 1)
    occ_x = np.zeros((grid * grid, depth_bins), dtype=np.bool_)
    occ_x[zi2[body_center] * grid + yi2[body_center], xi2[body_center]] = True
    count_x = cluster_count(occ_x).reshape(grid, grid)
    palette = np.array([[246, 246, 246], [220, 220, 220], [233, 195, 137], [255, 190, 70], [210, 65, 50], [120, 35, 130]], dtype=np.uint8)
    Image.fromarray(palette[np.clip(count_x, 0, 5)]).resize((768, 768), Image.Resampling.NEAREST).save(DIAG / "hidden-layers-front-r08.png")

    body_pixels = int(body.sum())
    payload = {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-MASTERFORM-CLEANUP-R08.md",
        "method": {
            "surface_samples": "all triangle centers of untouched R07 Seed-42 PLY",
            "reference_side_projection": "X/Z mapped to REF-SEAM body polygon; Y quantized to 160 depth bins",
            "cluster_rule": "one-bin gaps closed; contiguous occupied depth bands counted",
            "confirmed_hidden_body_signature": ">=4 separated depth bands (covering sheet front/back plus body front/back)",
            "limitations": "Three bands are ambiguous at fused contacts; triangle-center sampling may undercount very thin layers.",
        },
        "reference_side_body_region": {
            "body_polygon_pixels": body_pixels,
            "pixels_with_any_surface_sample": int(active.sum()),
            "pixels_two_layers_ordinary_closed_body": int(ordinary_two.sum()),
            "pixels_three_layers_ambiguous": int(ambiguous_extra.sum()),
            "pixels_ge_four_layers_confirmed_hidden_body": int(confirmed_hidden.sum()),
            "pixels_le_one_layer_insufficient": int(insufficient.sum()),
            "confirmed_hidden_body_coverage_of_body_polygon_percent": round(100.0 * confirmed_hidden.sum() / body_pixels, 3),
            "confirmed_hidden_body_coverage_of_sampled_body_percent": round(100.0 * confirmed_hidden.sum() / max(1, active.sum()), 3),
        },
        "front_projection": {
            "grid_yz": [grid, grid],
            "active_bins": int(np.count_nonzero(count_x)),
            "bins_ge_four_depth_layers": int(np.count_nonzero(count_x >= 4)),
            "max_depth_layers": int(count_x.max(initial=0)),
        },
        "conclusion": {
            "hidden_body_surface_fully_available": False,
            "reason": "Confirmed underlying four-layer geometry is sparse rather than continuous across the seam-defined face; removing all overhangs would therefore leave gaps requiring reconstruction.",
            "local_reconstruction_required": True,
        },
        "outputs": [
            "diagnostics/hidden-layers-reference-side-r08.png",
            "diagnostics/hidden-layers-front-r08.png",
        ],
    }
    REPORT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
