#!/usr/bin/env python3
"""Visual/detail QA for the already-built full-model 0.5 mm candidate.

Read-only with respect to all geometry.  It adds reports and PNG previews to
the candidate directory, but never rewrites NPZ/STL/3MF artifacts.
"""

from __future__ import annotations

import argparse
import gc
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import colors
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
import trimesh

from full_model_fastpath import PREFIX, capsule_between, load_scaled_components, manifest_tree
from outer_candidate_validate_v001 import weighted_quantile
from phase4_reliable_geometry import orthographic_id_depth_raster
from smoke_single_solid import (
    _render_mouth_comparison,
    atomic_json,
    deviation_direction,
    load_working_npz,
    mouth_report,
)

VIEWS: dict[str, dict[str, Any]] = {
    "front": {"axis": "+z"},
    "back": {"axis": "-z"},
    "left": {"axis": "-x"},
    "right": {"axis": "+x"},
    "top": {"axis": "+y"},
    "front-oblique": {"camera": [0.78, 0.48, 1.0]},
    "back-oblique": {"camera": [-0.78, 0.48, -1.0]},
}


def view_mesh(mesh: trimesh.Trimesh, spec: dict[str, Any]) -> tuple[trimesh.Trimesh, str]:
    if "camera" not in spec:
        return mesh, str(spec["axis"])
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    camera = np.asarray(spec["camera"], dtype=np.float64)
    camera /= np.linalg.norm(camera)
    world_up = np.asarray([0.0, 1.0, 0.0])
    right = np.cross(world_up, camera)
    right /= np.linalg.norm(right)
    up = np.cross(camera, right)
    up /= np.linalg.norm(up)
    transformed = np.column_stack((vertices @ right, vertices @ up, vertices @ camera))
    return trimesh.Trimesh(vertices=transformed, faces=np.asarray(mesh.faces), process=False), "+z"


def solid_raster(mesh: trimesh.Trimesh, spec: dict[str, Any], resolution: int) -> tuple[np.ndarray, dict[str, Any]]:
    viewed, axis = view_mesh(mesh, spec)
    raster = orthographic_id_depth_raster(
        np.asarray(viewed.vertices), np.asarray(viewed.faces), view=axis,
        resolution=resolution, padding=0.055, validation_samples=64,
    )
    ids = raster.triangle_id
    hit = ids >= 0
    normals = np.asarray(viewed.face_normals)
    camera_axis = np.asarray(raster.metadata["camera_axis"], dtype=np.float64)
    key = camera_axis + np.asarray([0.35, 0.28, 0.18])
    key /= np.linalg.norm(key)
    shade = np.zeros(ids.shape, dtype=np.float64)
    shade[hit] = np.clip(0.25 + 0.75 * np.abs(normals[ids[hit]] @ key), 0.0, 1.0)
    image = np.empty((*ids.shape, 3), dtype=np.float64)
    image[:] = np.asarray([0.933, 0.945, 0.957])
    base = np.asarray([0.20, 0.53, 0.80])
    image[hit] = np.clip(base[None] * (0.42 + 0.66 * shade[hit, None]), 0.0, 1.0)
    return (image * 255).astype(np.uint8), raster.metadata


def save_pair(path: Path, before: np.ndarray, after: np.ndarray, title: str) -> None:
    before = np.flipud(before)
    after = np.flipud(after)
    height, width, _ = before.shape
    header, gutter = 74, 14
    canvas = Image.new("RGB", (2 * width + gutter, height + header), (238, 241, 244))
    canvas.paste(Image.fromarray(before), (0, header))
    canvas.paste(Image.fromarray(after), (width + gutter, header))
    draw = ImageDraw.Draw(canvas)
    draw.text((18, 12), title, fill=(17, 24, 39))
    draw.text((18, 43), "BEFORE · C01+C05+C08 (gaps preserved)", fill=(31, 41, 55))
    draw.text((width + gutter + 18, 43), "AFTER · joint 0.5 mm solid", fill=(31, 41, 55))
    canvas.save(path, format="PNG", optimize=True)


def face_centroid_distance(source: trimesh.Trimesh, target: trimesh.Trimesh) -> np.ndarray:
    from outer_candidate_validate_v001 import UnsignedDistanceOnly
    query = UnsignedDistanceOnly(target, batch_size=65536)
    result = query.query(np.asarray(source.triangles_center, dtype=np.float32)).astype(np.float64)
    del query
    gc.collect()
    return result


def heatmap_raster(mesh: trimesh.Trimesh, face_values: np.ndarray, spec: dict[str, Any], resolution: int, cap: float) -> np.ndarray:
    viewed, axis = view_mesh(mesh, spec)
    raster = orthographic_id_depth_raster(
        np.asarray(viewed.vertices), np.asarray(viewed.faces), view=axis,
        resolution=resolution, padding=0.055, validation_samples=64,
    )
    ids = raster.triangle_id
    hit = ids >= 0
    image = np.empty((*ids.shape, 3), dtype=np.uint8)
    image[:] = np.asarray([238, 241, 244], dtype=np.uint8)
    cmap = plt.get_cmap("inferno")
    norm = colors.Normalize(vmin=0.0, vmax=cap, clip=True)
    image[hit] = (cmap(norm(face_values[ids[hit]]))[:, :3] * 255).astype(np.uint8)
    return np.flipud(image)


def crop_display(image: np.ndarray, metadata: dict[str, Any], point: np.ndarray, radius_mm: float) -> np.ndarray:
    displayed = np.flipud(image)
    h, w = displayed.shape[:2]
    right = np.asarray(metadata["screen_right"], dtype=np.float64)
    up = np.asarray(metadata["screen_up"], dtype=np.float64)
    u = float(np.dot(point, right))
    v = float(np.dot(point, up))
    x = int(round((1.0 + (u - metadata["screen_u_center"]) * metadata["screen_scale_u_ndc_per_model_unit"]) * 0.5 * w))
    raw_y = int(round((1.0 + (v - metadata["screen_v_center"]) * metadata["screen_scale_v_ndc_per_model_unit"]) * 0.5 * h))
    y = h - 1 - raw_y
    radius_px = int(math.ceil(radius_mm * metadata["screen_scale_u_ndc_per_model_unit"] * 0.5 * w))
    x0, x1 = max(0, x - radius_px), min(w, x + radius_px)
    y0, y1 = max(0, y - radius_px), min(h, y + radius_px)
    return displayed[y0:y1, x0:x1]


def save_close_pair(path: Path, before: np.ndarray, after: np.ndarray, title: str) -> None:
    size = 650
    left = Image.fromarray(before).resize((size, size), Image.Resampling.LANCZOS)
    right = Image.fromarray(after).resize((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (2 * size + 14, size + 76), (238, 241, 244))
    canvas.paste(left, (0, 76)); canvas.paste(right, (size + 14, 76))
    draw = ImageDraw.Draw(canvas)
    draw.text((18, 14), title, fill=(17, 24, 39))
    draw.text((18, 45), "BEFORE", fill=(31, 41, 55)); draw.text((size + 32, 45), "AFTER", fill=(31, 41, 55))
    canvas.save(path, format="PNG", optimize=True)


def weighted_region(values: np.ndarray, mesh: trimesh.Trimesh, mask: np.ndarray) -> dict[str, Any]:
    areas = np.asarray(mesh.area_faces)[mask]
    local = values[mask]
    return {
        "faces": int(mask.sum()), "area_mm2": float(areas.sum()),
        "median_mm": weighted_quantile(local, areas, 0.5),
        "p95_mm": weighted_quantile(local, areas, 0.95),
        "maximum_sampled_face_centroid_mm": float(local.max()),
    }


def critical_C01_regions(c01: trimesh.Trimesh, distances: np.ndarray) -> dict[str, Any]:
    centers = np.asarray(c01.triangles_center)
    bounds = np.asarray(c01.bounds)
    norm = (centers - bounds[0]) / np.ptp(bounds, axis=0)
    masks = {
        "ears_upper_head": (norm[:, 1] > 0.76) & (np.abs(norm[:, 0] - 0.5) > 0.18),
        "snout_front_mid": (norm[:, 2] > 0.72) & (norm[:, 1] > 0.38) & (norm[:, 1] < 0.76),
        "fingers_hands_front_lower_mid": (norm[:, 2] > 0.58) & (norm[:, 1] > 0.20) & (norm[:, 1] < 0.48) & (np.abs(norm[:, 0] - 0.5) > 0.16),
        "feet_lower": norm[:, 1] < 0.19,
    }
    return {name: weighted_region(distances, c01, mask) for name, mask in masks.items()}


def centerline_thickness(candidate: trimesh.Trimesh, connections: dict[str, Any]) -> dict[str, Any]:
    grid = candidate.voxelized(0.5, method="subdivide")
    filled = ndimage.binary_fill_holes(np.asarray(grid.matrix, dtype=bool))
    edt = ndimage.distance_transform_edt(filled) * 0.5
    inverse = np.linalg.inv(np.asarray(grid.transform, dtype=np.float64))
    result = {}
    global_min = None
    for name, item in connections.items():
        if not isinstance(item, dict) or "endpoint_C05_mm" not in item:
            continue
        other_key = "endpoint_C01_mm" if "endpoint_C01_mm" in item else "endpoint_C08_mm"
        a = np.asarray(item["endpoint_C05_mm"], dtype=np.float64)
        b = np.asarray(item[other_key], dtype=np.float64)
        t = np.linspace(0.15, 0.85, 101)
        points = a[None] * (1.0 - t[:, None]) + b[None] * t[:, None]
        indices = trimesh.transform_points(points, inverse)
        radius = ndimage.map_coordinates(edt, indices.T, order=1, mode="nearest")
        diameter = 2.0 * radius
        index = int(np.argmin(diameter))
        row = {
            "method": "2x Euclidean distance-transform radius sampled along central 70% of connector centerline",
            "minimum_diameter_mm": float(diameter[index]),
            "minimum_position_mm": points[index].tolist(),
            "median_diameter_mm": float(np.median(diameter)),
            "p05_diameter_mm": float(np.quantile(diameter, 0.05)),
        }
        result[name] = row
        if global_min is None or row["minimum_diameter_mm"] < global_min["minimum_diameter_mm"]:
            global_min = {"connection": name, **row}
    result["thinnest_measured_connection"] = global_min
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--tail-analysis", type=Path, required=True)
    parser.add_argument("--variant", type=Path, required=True)
    parser.add_argument("--resolution", type=int, default=850)
    args = parser.parse_args()
    report_path = args.variant / f"{PREFIX}-fast-gate.json"
    fast = json.loads(report_path.read_text(encoding="utf-8"))
    if fast["status"] != "FAST_GATE_PASS":
        raise RuntimeError("Visual QA requires a successful Fast Gate")
    output = args.variant / "visual-and-detail-qa"
    output.mkdir(exist_ok=False)
    components, _ = load_scaled_components(args.source)
    c01, c05, c08 = components[0], components[4], components[7]
    before = trimesh.util.concatenate([c01, c05, c08])
    candidate = load_working_npz(Path(fast["artifacts"]["working_npz"]["path"]))
    tail = json.loads(args.tail_analysis.read_text(encoding="utf-8"))
    conn = fast["connections"]
    root_bridge = capsule_between(np.asarray(conn["C05_to_C01"]["endpoint_C05_mm"]), np.asarray(conn["C05_to_C01"]["endpoint_C01_mm"]), conn["radius_mm"])
    curl_bridge = capsule_between(np.asarray(conn["C05_to_C08"]["endpoint_C05_mm"]), np.asarray(conn["C05_to_C08"]["endpoint_C08_mm"]), conn["radius_mm"])
    construction_input = trimesh.util.concatenate([before, root_bridge, curl_bridge])

    images: dict[str, tuple[np.ndarray, dict[str, Any], np.ndarray, dict[str, Any]]] = {}
    full_paths = []
    for name, spec in VIEWS.items():
        print(f"raster {name}: before", flush=True)
        b, bm = solid_raster(before, spec, args.resolution)
        print(f"raster {name}: after", flush=True)
        a, am = solid_raster(candidate, spec, args.resolution)
        images[name] = (b, bm, a, am)
        path = output / f"{PREFIX}-before-after-{name}.png"
        save_pair(path, b, a, f"{PREFIX} · {name.upper()}")
        full_paths.append(path)

    close_specs = {
        "tail-root": ("back", 0.5 * (np.asarray(conn["C05_to_C01"]["endpoint_C05_mm"]) + np.asarray(conn["C05_to_C01"]["endpoint_C01_mm"])), 15.0),
        "tail-tip-and-curl-joint": ("back", 0.5 * (np.asarray(c08.bounds[0]) + np.asarray(c08.bounds[1])), 19.0),
        "mouth": ("front", np.asarray([0.0, 17.0, 0.0]), 61.0),
    }
    close_paths = []
    for name, (view, point, radius) in close_specs.items():
        b, bm, a, am = images[view]
        bc = crop_display(b, bm, point, radius)
        ac = crop_display(a, am, point, radius)
        path = output / f"{PREFIX}-closeup-{name}.png"
        save_close_pair(path, bc, ac, f"{PREFIX} · {name.upper()}")
        close_paths.append(path)

    print("UDF C01/C05/C08 -> candidate", flush=True)
    c01_to_candidate, _ = deviation_direction(c01, candidate)
    c05_to_candidate, _ = deviation_direction(c05, candidate)
    c08_to_candidate, _ = deviation_direction(c08, candidate)
    print("UDF candidate -> construction input", flush=True)
    candidate_to_input, candidate_face_values = deviation_direction(candidate, construction_input)
    c01_centroid = face_centroid_distance(c01, candidate)
    cap = max(0.5, float(np.quantile(candidate_face_values, 0.99)))
    heat_paths = []
    for name in ("front", "back", "front-oblique", "back-oblique"):
        image = heatmap_raster(candidate, candidate_face_values, VIEWS[name], args.resolution, cap)
        path = output / f"{PREFIX}-candidate-to-input-heatmap-{name}.png"
        Image.fromarray(image).save(path, format="PNG", optimize=True)
        heat_paths.append(path)

    print("mouth depth QA", flush=True)
    mouth_before, depth_before, mask_before = mouth_report(c01)
    mouth_after, depth_after, mask_after = mouth_report(candidate)
    mouth_ratios = {
        "opening_area": mouth_after["opening_area_mm2_projected"] / mouth_before["opening_area_mm2_projected"],
        "width": mouth_after["opening_width_height_mm"][0] / mouth_before["opening_width_height_mm"][0],
        "height": mouth_after["opening_width_height_mm"][1] / mouth_before["opening_width_height_mm"][1],
        "depth_contrast": mouth_after["rim_transition_minus_interior_median_depth_mm"] / mouth_before["rim_transition_minus_interior_median_depth_mm"],
    }
    mouth_path = output / f"{PREFIX}-mouth-depth-before-after.png"
    _render_mouth_comparison(depth_before, mask_before, depth_after, mask_after, mouth_path, f"{PREFIX} · mouth depth/opening")

    print("local connector thickness", flush=True)
    thickness = centerline_thickness(candidate, conn)
    equivalent_original_tail_diameters = {
        "C05_4V_over_A_mm": float(4.0 * abs(c05.volume) / c05.area),
        "C08_4V_over_A_mm": float(4.0 * abs(c08.volume) / c08.area),
        "interpretation": "Equivalent tubular diameter only; not a certified pointwise minimum wall/thickness.",
    }

    # Contact sheet with the 7 complete comparisons and 3 critical closeups.
    source_paths = full_paths + close_paths
    thumbs = []
    for path in source_paths:
        with Image.open(path) as image:
            item = image.convert("RGB")
            item.thumbnail((900, 490), Image.Resampling.LANCZOS)
            thumbs.append((path.stem, item.copy()))
    rows = math.ceil(len(thumbs) / 2)
    sheet = Image.new("RGB", (1800, rows * 540 + 70), (238, 241, 244))
    draw = ImageDraw.Draw(sheet)
    draw.text((18, 20), f"{PREFIX} · BEFORE / AFTER · CANDIDATE", fill=(17, 24, 39))
    for index, (label, image) in enumerate(thumbs):
        row, column = divmod(index, 2)
        x, y = column * 900, 70 + row * 540
        sheet.paste(image, (x, y))
        draw.text((x + 14, y + 495), label.replace(PREFIX + "-", "").upper(), fill=(31, 41, 55))
    sheet_path = output / f"{PREFIX}-visual-contact-sheet.png"
    sheet.save(sheet_path, format="PNG", optimize=True)

    checks = {
        "mouth_opening_detected": bool(mouth_after["opening_detected"]),
        "mouth_no_front_membrane": mouth_after["membrane_test"] == "PASS",
        "mouth_area_at_least_70_percent": mouth_ratios["opening_area"] >= 0.70,
        "mouth_width_at_least_80_percent": mouth_ratios["width"] >= 0.80,
        "mouth_height_at_least_75_percent": mouth_ratios["height"] >= 0.75,
        "mouth_depth_at_least_70_percent": mouth_ratios["depth_contrast"] >= 0.70,
        "root_connector_minimum_diameter_at_least_3mm": thickness["C05_to_C01"]["minimum_diameter_mm"] >= 3.0,
        "curl_connector_minimum_diameter_at_least_3mm": thickness["C05_to_C08"]["minimum_diameter_mm"] >= 3.0,
    }
    report = {
        "schema": "ai3d.full-model-fastpath.visual-and-detail-qa.v1",
        "classification": "CANDIDATE / NON-MASTER",
        "geometry_mutated": False,
        "renderer": "nvdiffrast full-face opaque ID/depth raster; no face subsampling",
        "deviation_mm": {
            "C01_to_candidate": c01_to_candidate,
            "C05_to_candidate": c05_to_candidate,
            "C08_to_candidate": c08_to_candidate,
            "candidate_to_construction_input": candidate_to_input,
        },
        "critical_C01_regions": critical_C01_regions(c01, c01_centroid),
        "mouth": {"C01": mouth_before, "candidate": mouth_after, "ratios": mouth_ratios},
        "tail": {
            "selection": tail["selection_decision"],
            "connector_centerline_thickness": thickness,
            "original_component_equivalent_diameters": equivalent_original_tail_diameters,
        },
        "checks": checks,
        "pass": all(checks.values()),
        "heatmap_scale_mm": {"minimum": 0.0, "maximum_p99_clipped": cap},
        "artifacts": [str(path) for path in sorted(output.glob("*.png"))],
    }
    atomic_json(output / f"{PREFIX}-visual-and-detail-qa.json", report)
    atomic_json(args.variant / "artifact-manifest.json", manifest_tree(args.variant))
    print(json.dumps({"status": "PASS" if report["pass"] else "FAIL", "checks": checks, "output": str(output)}, indent=2))
    if not report["pass"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
