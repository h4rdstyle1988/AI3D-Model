#!/usr/bin/env python3
"""Opaque full-face raster QA for C01 single-solid smoke variants.

This does not modify geometry.  It replaces visually misleading face-sampled
Matplotlib previews with full-face nvdiffrast ID/depth images.  The invalidated
cuMesh ray tracer is never used; cuMesh unsigned distance is used only for the
two independently validated surface-distance heatmaps.
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import os
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import colors
import numpy as np
from PIL import Image, ImageDraw
import trimesh

from outer_candidate_validate_v001 import UnsignedDistanceOnly
from phase4_reliable_geometry import orthographic_id_depth_raster
from smoke_single_solid import atomic_json, load_scaled_c01, load_working_npz


VIEWS: dict[str, dict[str, Any]] = {
    "front": {"axis": "+z"},
    "back": {"axis": "-z"},
    "left": {"axis": "-x"},
    "right": {"axis": "+x"},
    "top": {"axis": "+y"},
    "perspective": {"axis": "+z", "oblique": True},
}


def atomic_text(path: Path, value: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def transformed_for_view(mesh: trimesh.Trimesh, spec: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, str]:
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    if not spec.get("oblique"):
        return vertices, faces, str(spec["axis"])
    # Camera at front-right-above; preserve right-handed frame and scale.
    camera = np.asarray([0.78, 0.48, 1.0], dtype=np.float64)
    camera /= np.linalg.norm(camera)
    world_up = np.asarray([0.0, 1.0, 0.0])
    screen_right = np.cross(world_up, camera)
    screen_right /= np.linalg.norm(screen_right)
    screen_up = np.cross(camera, screen_right)
    screen_up /= np.linalg.norm(screen_up)
    transformed = np.column_stack((vertices @ screen_right, vertices @ screen_up, vertices @ camera))
    return transformed, faces, "+z"


def solid_raster(mesh: trimesh.Trimesh, spec: dict[str, Any], resolution: int) -> tuple[np.ndarray, dict[str, Any]]:
    vertices, faces, axis = transformed_for_view(mesh, spec)
    raster = orthographic_id_depth_raster(
        vertices,
        faces,
        view=axis,
        resolution=resolution,
        padding=0.055,
        validation_samples=64,
    )
    ids = raster.triangle_id
    hit = ids >= 0
    normals = np.asarray(trimesh.Trimesh(vertices=vertices, faces=faces, process=False).face_normals)
    # Camera-relative clay shading, with a small depth cue.
    camera_axis = np.asarray(raster.metadata["camera_axis"], dtype=np.float64)
    key = camera_axis + np.asarray([0.35, 0.28, 0.18])
    key /= np.linalg.norm(key)
    shade = np.zeros(ids.shape, dtype=np.float64)
    shade[hit] = np.clip(0.25 + 0.75 * np.abs(normals[ids[hit]] @ key), 0.0, 1.0)
    depth = raster.depth_model
    finite = depth[hit]
    if len(finite):
        lo, hi = np.quantile(finite, [0.01, 0.99])
        if hi > lo:
            shade[hit] *= 0.82 + 0.18 * np.clip((finite - lo) / (hi - lo), 0.0, 1.0)
    image = np.empty((*ids.shape, 3), dtype=np.float64)
    image[:] = np.asarray([0.933, 0.945, 0.957])
    base = np.asarray([0.20, 0.53, 0.80])
    image[hit] = np.clip(base[None] * (0.42 + 0.66 * shade[hit, None]), 0.0, 1.0)
    return (image * 255).astype(np.uint8), raster.metadata


def heatmap_raster(
    mesh: trimesh.Trimesh,
    face_values: np.ndarray,
    spec: dict[str, Any],
    resolution: int,
    cap: float,
) -> tuple[np.ndarray, dict[str, Any]]:
    vertices, faces, axis = transformed_for_view(mesh, spec)
    raster = orthographic_id_depth_raster(
        vertices,
        faces,
        view=axis,
        resolution=resolution,
        padding=0.055,
        validation_samples=64,
    )
    ids = raster.triangle_id
    hit = ids >= 0
    image = np.empty((*ids.shape, 3), dtype=np.uint8)
    image[:] = np.asarray([238, 241, 244], dtype=np.uint8)
    cmap = plt.get_cmap("inferno")
    norm = colors.Normalize(vmin=0.0, vmax=cap, clip=True)
    image[hit] = (cmap(norm(face_values[ids[hit]]))[:, :3] * 255).astype(np.uint8)
    return image, raster.metadata


def save_pair(path: Path, before: np.ndarray, after: np.ndarray, title: str, left: str, right: str) -> None:
    height, width, _ = before.shape
    header = 76
    gutter = 14
    canvas = Image.new("RGB", (2 * width + gutter, height + header), (238, 241, 244))
    canvas.paste(Image.fromarray(np.flipud(before)), (0, header))
    canvas.paste(Image.fromarray(np.flipud(after)), (width + gutter, header))
    draw = ImageDraw.Draw(canvas)
    draw.text((18, 12), title, fill=(17, 24, 39))
    draw.text((18, 44), left, fill=(31, 41, 55))
    draw.text((width + gutter + 18, 44), right, fill=(31, 41, 55))
    canvas.save(path, format="PNG", optimize=True)


def face_centroid_distance(source: trimesh.Trimesh, target: trimesh.Trimesh) -> np.ndarray:
    query = UnsignedDistanceOnly(target, batch_size=65536)
    centroids = np.asarray(source.triangles_center, dtype=np.float32)
    values = query.query(centroids).astype(np.float64)
    del query
    gc.collect()
    return values


def high_deviation_regions(mesh: trimesh.Trimesh, values: np.ndarray) -> dict[str, Any]:
    centers = np.asarray(mesh.triangles_center, dtype=np.float64)
    areas = np.asarray(mesh.area_faces, dtype=np.float64)
    bounds = np.asarray(mesh.bounds, dtype=np.float64)
    extents = np.ptp(bounds, axis=0)
    normalized = (centers - bounds[0]) / extents
    regions = {
        "upper_ear_head_band": normalized[:, 1] >= 0.72,
        "lower_limb_base_band": normalized[:, 1] <= 0.25,
        "front_snout_mouth_band": normalized[:, 2] >= 0.65,
        "rear_body_band": normalized[:, 2] <= 0.20,
        "central_body": (normalized[:, 1] > 0.25) & (normalized[:, 1] < 0.72) & (normalized[:, 2] > 0.20) & (normalized[:, 2] < 0.65),
    }
    rows = {}
    for name, mask in regions.items():
        weights = areas[mask]
        local = values[mask]
        rows[name] = {
            "faces": int(np.count_nonzero(mask)),
            "area_mm2": float(weights.sum()),
            "median_centroid_distance_mm": float(np.median(local)) if len(local) else None,
            "p95_centroid_distance_mm": float(np.quantile(local, 0.95)) if len(local) else None,
            "area_fraction_over_1mm": float(weights[local > 1.0].sum() / weights.sum()) if weights.sum() else None,
            "area_fraction_over_2mm": float(weights[local > 2.0].sum() / weights.sum()) if weights.sum() else None,
        }
    top = np.argsort(values)[-50:][::-1]
    return {
        "regions_are_bbox_normalized_diagnostic_bands_not_semantic_segmentation": True,
        "bands": rows,
        "top_50_source_face_centroids": [
            {"face": int(face), "distance_mm": float(values[face]), "centroid_mm": centers[face].tolist()}
            for face in top.tolist()
        ],
    }


def run(source: Path, variant: Path, resolution: int) -> dict[str, Any]:
    build_path = next(variant.glob("*-build.json"))
    build = json.loads(build_path.read_text(encoding="utf-8"))
    prefix = build_path.name[: -len("-build.json")]
    source_mesh, source_record = load_scaled_c01(source)
    candidate = load_working_npz(Path(build["artifacts"]["working_npz"]["path"]))
    output = variant / "visual-comparison-v2-solid-raster"
    output.mkdir(exist_ok=False)
    view_reports = {}
    pair_paths = []
    for name, spec in VIEWS.items():
        print(f"solid raster {name}: C01", flush=True)
        before, before_meta = solid_raster(source_mesh, spec, resolution)
        print(f"solid raster {name}: candidate", flush=True)
        after, after_meta = solid_raster(candidate, spec, resolution)
        path = output / f"{prefix}-before-after-{name}.png"
        save_pair(path, before, after, f"{prefix} · {name.upper()} · SOLID FULL-FACE RASTER", "C01 BEFORE", "VOXEL SOLID AFTER")
        pair_paths.append(path)
        view_reports[name] = {"C01": before_meta, "candidate": after_meta}
    print("centroid UDF source->candidate", flush=True)
    source_values = face_centroid_distance(source_mesh, candidate)
    print("centroid UDF candidate->source", flush=True)
    candidate_values = face_centroid_distance(candidate, source_mesh)
    for direction, mesh, values in (
        ("C01-to-candidate", source_mesh, source_values),
        ("candidate-to-C01", candidate, candidate_values),
    ):
        cap = max(0.5, float(np.quantile(values, 0.99)))
        for name in ("front", "back", "perspective"):
            rendered, metadata = heatmap_raster(mesh, values, VIEWS[name], resolution, cap)
            path = output / f"{prefix}-{direction}-heatmap-{name}.png"
            Image.fromarray(np.flipud(rendered)).save(path, format="PNG", optimize=True)
            view_reports[f"heatmap_{direction}_{name}"] = metadata
    # Compact contact sheet from the six paired views.
    thumbs = []
    for path in pair_paths:
        with Image.open(path) as image:
            thumb = image.convert("RGB")
            thumb.thumbnail((900, 490), Image.Resampling.LANCZOS)
            thumbs.append((path.stem, thumb.copy()))
    sheet = Image.new("RGB", (1800, 3 * 540 + 70), (238, 241, 244))
    draw = ImageDraw.Draw(sheet)
    draw.text((18, 20), f"{prefix} · C01 BEFORE / VOXEL SOLID AFTER · NON-MASTER", fill=(17, 24, 39))
    for index, (label, image) in enumerate(thumbs):
        row, column = divmod(index, 2)
        x = column * 900
        y = 70 + row * 540
        sheet.paste(image, (x, y))
        draw.text((x + 14, y + 495), label.rsplit("-", 1)[-1].upper(), fill=(31, 41, 55))
    contact_path = output / f"{prefix}-solid-before-after-contact-sheet.png"
    sheet.save(contact_path, format="PNG", optimize=True)
    report = {
        "schema": "ai3d.c01.single-solid-smoke.visual-qa.v2",
        "classification": "SMOKE-TEST / NON-MASTER",
        "geometry_mutated": False,
        "renderer": "nvdiffrast full-face orthographic ID/depth; opaque clay shading; no face subsampling",
        "perspective_note": "perspective panel is an oblique orthographic full-face raster from front-right-above, not a focal-length perspective camera",
        "source": source_record,
        "candidate_prefix": prefix,
        "resolution_px": resolution,
        "view_validation": view_reports,
        "distance_centroid_summary": {
            "C01_to_candidate": {
                "median_mm": float(np.median(source_values)),
                "p95_mm": float(np.quantile(source_values, 0.95)),
                "p99_mm": float(np.quantile(source_values, 0.99)),
                "maximum_mm": float(np.max(source_values)),
            },
            "candidate_to_C01": {
                "median_mm": float(np.median(candidate_values)),
                "p95_mm": float(np.quantile(candidate_values, 0.95)),
                "p99_mm": float(np.quantile(candidate_values, 0.99)),
                "maximum_mm": float(np.max(candidate_values)),
            },
        },
        "C01_high_deviation_regions": high_deviation_regions(source_mesh, source_values),
        "tail_scope_note": "The smoke reference is C01 only. Previously classified separate tail components C05/C07/C08/C09 are outside C01 and are neither reconstructed nor silently modified by this test.",
        "artifacts": [str(path) for path in sorted(output.glob("*.png"))],
    }
    atomic_json(output / f"{prefix}-visual-qa-v2.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--variant", type=Path, required=True)
    parser.add_argument("--resolution", type=int, default=900)
    args = parser.parse_args()
    report = run(args.source, args.variant, args.resolution)
    print(json.dumps({"status": "PASS", "output_count": len(report["artifacts"]), "candidate": report["candidate_prefix"]}, indent=2))


if __name__ == "__main__":
    main()
