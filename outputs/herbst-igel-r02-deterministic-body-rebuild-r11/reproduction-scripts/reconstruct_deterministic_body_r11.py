#!/usr/bin/env python3
"""Deterministic local body rebuild for Herbst-Igel R02/R11.

The only geometry source is the byte-identical Seed-42 PLY.  The established
REF-SEAM X/Z transfer defines the problem ROI.  No Seed-42 coordinate is ever
modified: source faces in the proven overlap ROI are removed, protected
feature faces keep their original indices/coordinates, and one smooth
low-frequency implicit body surface is added.

R10's deterministic PLY, mask, SDF and marching-tetrahedra primitives are
loaded by immutable Git blob id.  R11 intentionally does not use any R08-R10
candidate geometry as form input.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
TASK = "tasks/TASK-HERBST-IGEL-R02-DETERMINISTIC-BODY-REBUILD-R11.md"
TASK_BLOB = "a924b68969a2f82e7e75a924a5e13227b1211d77"
R10_PRIMITIVES_BLOB = "cbbc1daf11331fae989441968339d21153d9f97b"
SOURCE_EXTERNAL = Path(
    r"D:\3D-Models\generated\herbst-igel-r02-r08-input\outputs\herbst-igel-r02-trellis-optik-retry-r07"
    r"\trellis-raw\seed-00000042\herbst-igel-r02-trellis-raw-seed-42.ply"
)
REF_CLEAN_EXTERNAL = Path(
    r"D:\3D-Models\generated\herbst-igel-r02-r08-input\outputs\herbst-igel-r02-trellis-optik-retry-r07"
    r"\reference-audit\ref-clean-r07.jpg"
)
REF_SEAM_EXTERNAL = Path(
    r"D:\3D-Models\generated\herbst-igel-r02-r08-input\outputs\herbst-igel-r02-trellis-optik-retry-r07"
    r"\reference-audit\ref-seam-r07.jpg"
)
SOURCE = OUT / "source-seed42" / "herbst-igel-r02-trellis-raw-seed-42.ply"
REF_CLEAN = OUT / "reference-audit" / "ref-clean-r11.jpg"
REF_SEAM = OUT / "reference-audit" / "ref-seam-r11.jpg"
MASTER = OUT / "masterform" / "herbst-igel-r02-masterform-deterministic-r11-NON-APPROVED.ply"
REPORT = OUT / "reports" / "deterministic-body-rebuild-r11.json"
ROI_REPORT = OUT / "reports" / "roi-coordinate-preservation-r11.json"
DIAGNOSTIC = OUT / "diagnostics" / "roi-definition-r11.png"

EXPECTED = {
    "seed42": "85ba18eaed15bdbe631fc49dd571e73882c4055e2c247022e90ad15ed99822c6",
    "ref_clean": "c1c9a5a094f1db2fd220f3433f83af8dedca780f56a4bf479eb8883432250859",
    "ref_seam": "b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4",
}


def load_r10_primitives() -> dict[str, object]:
    code = subprocess.check_output(
        ["git", "cat-file", "blob", R10_PRIMITIVES_BLOB], cwd=ROOT
    ).decode("utf-8")
    namespace: dict[str, object] = {
        "__name__": "r10_immutable_primitives",
        "__file__": str(OUT / "reproduction-scripts" / "r10_immutable_primitives.py"),
    }
    exec(compile(code, namespace["__file__"], "exec"), namespace)
    return namespace


P = load_r10_primitives()
read_binary_ply = P["read_binary_ply"]
write_binary_ply = P["write_binary_ply"]
project_xz = P["project_xz"]
bilinear_sample = P["bilinear_sample"]
signed_distance_field = P["signed_distance_field"]
marching_tetrahedra = P["marching_tetrahedra"]
mesh_metrics = P["mesh_metrics"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def stage_and_gate_inputs() -> dict[str, object]:
    for source in (SOURCE_EXTERNAL, REF_CLEAN_EXTERNAL, REF_SEAM_EXTERNAL):
        if not source.is_file():
            raise FileNotFoundError(source)
    actual_external = {
        "seed42": sha256(SOURCE_EXTERNAL),
        "ref_clean": sha256(REF_CLEAN_EXTERNAL),
        "ref_seam": sha256(REF_SEAM_EXTERNAL),
    }
    if actual_external != EXPECTED:
        raise RuntimeError(f"R11 input hash gate failed: {actual_external!r}")
    SOURCE.parent.mkdir(parents=True, exist_ok=True)
    REF_CLEAN.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE_EXTERNAL, SOURCE)
    shutil.copyfile(REF_CLEAN_EXTERNAL, REF_CLEAN)
    shutil.copyfile(REF_SEAM_EXTERNAL, REF_SEAM)
    actual_staged = {
        "seed42": sha256(SOURCE),
        "ref_clean": sha256(REF_CLEAN),
        "ref_seam": sha256(REF_SEAM),
    }
    if actual_staged != EXPECTED:
        raise RuntimeError("Staged R11 input bytes differ from authoritative inputs")
    return {
        key: {
            "expected_sha256": EXPECTED[key],
            "external_sha256": actual_external[key],
            "staged_sha256": actual_staged[key],
            "status": "PASS",
        }
        for key in EXPECTED
    }


def reference_masks() -> tuple[np.ndarray, np.ndarray, np.ndarray, list[int], np.ndarray]:
    """Return blue seam, exact body side, seam-crossing ROI, bbox and RGB."""
    old_seam = P["SEAM_IMAGE"]
    try:
        P["SEAM_IMAGE"] = REF_SEAM
        blue, body, bbox, rgb = P["reference_masks"]()
    finally:
        P["SEAM_IMAGE"] = old_seam
    # Crossing triangles whose centers lie on the thick blue annotation are
    # part of the proven overlap.  This is not a dilation into healthy back.
    seam_band = np.asarray(
        Image.fromarray((blue * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))
    ) > 0
    roi = body | seam_band
    return blue, body, roi, bbox, rgb


FEATURES = [
    {"name": "front_ear", "center_px": [103, 154], "radius_px": 18},
    {"name": "reference_side_ear", "center_px": [226, 174], "radius_px": 23},
    {"name": "front_eye", "center_px": [111, 210], "radius_px": 12, "window_px": 7},
    {"name": "reference_side_eye", "center_px": [205, 207], "radius_px": 13, "window_px": 8},
    {"name": "nose", "center_px": [79, 231], "radius_px": 16, "window_px": 9},
]


def feature_membership(u: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, list[dict[str, object]]]:
    membership = np.zeros(np.broadcast(u, v).shape, dtype=bool)
    definitions: list[dict[str, object]] = []
    for feature in FEATURES:
        x, y = feature["center_px"]
        radius = feature["radius_px"]
        local = ((u - x) / radius) ** 2 + ((v - y) / radius) ** 2 <= 1.0
        membership |= local
        definitions.append(dict(feature))
    return membership, definitions


def measured_width_profiles(vertices: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, object]]:
    """Measure robust Seed-42 face width without deriving a new form."""
    centers = np.linspace(-0.22, 0.10, 9)
    lows: list[float] = []
    highs: list[float] = []
    counts: list[int] = []
    half = 0.0205
    for x in centers:
        select = (
            (vertices[:, 0] >= x - half)
            & (vertices[:, 0] < x + half)
            & (vertices[:, 2] > -0.08)
            & (vertices[:, 2] < 0.12)
        )
        values = vertices[select, 1]
        if len(values) < 500:
            raise RuntimeError(f"Insufficient Seed-42 face width samples at x={x}")
        low, high = np.quantile(values, [0.05, 0.95])
        lows.append(float(low))
        highs.append(float(high))
        counts.append(int(len(values)))
    low_array = np.asarray(lows)
    high_array = np.asarray(highs)
    center_array = 0.5 * (low_array + high_array)
    radius_array = 0.5 * (high_array - low_array)
    return centers, center_array, radius_array, {
        "method": "per-X robust 5/95-percentile envelope in unchanged lower face band",
        "x_centers": centers.tolist(),
        "sample_counts": counts,
        "low_y": low_array.tolist(),
        "high_y": high_array.tolist(),
        "center_y": center_array.tolist(),
        "radius_y": radius_array.tolist(),
    }


def width_at(x: np.ndarray, centers: np.ndarray, values: np.ndarray) -> np.ndarray:
    return np.interp(x, centers, values, left=values[0], right=values[-1])


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


def make_variable_width_surface(
    field2d: np.ndarray,
    bounds_min: np.ndarray,
    bounds_max: np.ndarray,
    bbox: list[int],
    lower_guard: float,
    profile_x: np.ndarray,
    profile_center: np.ndarray,
    profile_radius: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    xs = np.linspace(bounds_min[0] - 0.010, 0.115, 132)
    ys = np.linspace(-0.190, 0.455, 116)
    zs = np.linspace(lower_guard - 0.060, bounds_max[2] + 0.010, 126)
    gx, gz = np.meshgrid(xs, zs, indexing="ij")
    silhouette = sampled_profile(field2d, gx, gz, bounds_min, bounds_max, bbox)
    lower_start = lower_guard - 0.052
    lower_full = lower_guard - 0.012
    t = np.clip((gz - lower_start) / (lower_full - lower_start), 0.0, 1.0)
    taper = t * t * (3.0 - 2.0 * t)
    silhouette = silhouette * taper - (1.0 - taper) * 0.18
    cy = width_at(xs, profile_x, profile_center)
    ry = np.maximum(width_at(xs, profile_x, profile_radius), 0.045)
    scalar = ((ys[None, :, None] - cy[:, None, None]) / ry[:, None, None]) ** 2 - silhouette[:, None, :]
    return xs, ys, zs, scalar


def select_source_faces(
    vertices: np.ndarray,
    faces: np.ndarray,
    roi: np.ndarray,
    body_field: np.ndarray,
    bounds_min: np.ndarray,
    bounds_max: np.ndarray,
    bbox: list[int],
    lower_guard: float,
    profile_x: np.ndarray,
    profile_center: np.ndarray,
    profile_radius: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, object]]:
    triangles = vertices[faces]
    centers3 = triangles.mean(axis=1)
    u, v = project_xz(centers3, bounds_min, bounds_max, bbox)
    ui = np.rint(u).astype(np.int32)
    vi = np.rint(v).astype(np.int32)
    valid = (ui >= 0) & (ui < roi.shape[1]) & (vi >= 0) & (vi < roi.shape[0])
    center_in_roi = np.zeros(len(faces), dtype=bool)
    center_in_roi[valid] = roi[vi[valid], ui[valid]]
    vu, vv = project_xz(triangles.reshape(-1, 3), bounds_min, bounds_max, bbox)
    vui = np.rint(vu).astype(np.int32).reshape(-1, 3)
    vvi = np.rint(vv).astype(np.int32).reshape(-1, 3)
    vvalid = (vui >= 0) & (vui < roi.shape[1]) & (vvi >= 0) & (vvi < roi.shape[0])
    vertex_in_roi = np.zeros(vvalid.shape, dtype=bool)
    vertex_in_roi.ravel()[vvalid.ravel()] = roi[vvi.ravel()[vvalid.ravel()], vui.ravel()[vvalid.ravel()]]
    problem = (center_in_roi | np.any(vertex_in_roi, axis=1)) & (np.max(triangles[:, :, 2], axis=1) > lower_guard)

    in_feature, definitions = feature_membership(u, v)
    flat = triangles.reshape(-1, 3)
    local_profile = sampled_profile(body_field, flat[:, 0], flat[:, 2], bounds_min, bounds_max, bbox)
    cy = width_at(flat[:, 0], profile_x, profile_center)
    ry = np.maximum(width_at(flat[:, 0], profile_x, profile_radius), 0.045)
    implicit = (((flat[:, 1] - cy) / ry) ** 2 - local_profile).reshape(-1, 3)
    # Exact source features are retained only where their geometry reaches the
    # reconstructed exterior.  This rejects leaf sheets merely sharing the 2-D
    # guard while preserving the actual ears, eye relief and nose coordinates.
    exterior = np.max(implicit, axis=1) >= -0.035
    # Each X/Z guard intersects several fused depth layers.  Retain only the
    # two measured exterior clusters; middle layers are the documented false
    # leaf/spine overlap, not protected facial geometry.
    feature_exterior = np.zeros(len(faces), dtype=bool)
    depth_bands: list[dict[str, object]] = []
    for feature in FEATURES:
        fx, fy = feature["center_px"]
        radius = feature["radius_px"]
        local = ((u - fx) / radius) ** 2 + ((v - fy) / radius) ** 2 <= 1.0
        values = centers3[local, 1]
        if len(values) < 100:
            raise RuntimeError(f"Insufficient protected feature samples: {feature['name']}")
        low, high = np.quantile(values, [0.18, 0.82])
        selected = local & ((centers3[:, 1] <= low) | (centers3[:, 1] >= high))
        feature_exterior |= selected
        depth_bands.append({
            "name": feature["name"],
            "low_y": float(low),
            "high_y": float(high),
            "triangles_in_guard": int(local.sum()),
            "triangles_in_exterior_bands": int(selected.sum()),
        })
    protected = problem & in_feature & exterior & feature_exterior
    remove = problem & ~protected
    retained_indices = np.nonzero(~remove)[0]
    outside_indices = np.nonzero(~problem)[0]
    outside_preserved = np.array_equal(faces[retained_indices[np.isin(retained_indices, outside_indices)]], faces[outside_indices])
    return faces[retained_indices], remove, problem, {
        "roi_problem_triangles": int(problem.sum()),
        "removed_source_triangles": int(remove.sum()),
        "protected_exact_feature_triangles": int(protected.sum()),
        "retained_source_triangles": int(len(retained_indices)),
        "outside_roi_source_triangles": int((~problem).sum()),
        "outside_roi_faces_preserved_exact": bool(outside_preserved),
        "source_vertex_coordinates_modified": 0,
        "protected_feature_definitions": definitions,
        "protected_feature_depth_bands": depth_bands,
        "feature_exterior_threshold": -0.035,
    }


def carve_feature_windows(
    vertices: np.ndarray,
    faces: np.ndarray,
    bounds_min: np.ndarray,
    bounds_max: np.ndarray,
    bbox: list[int],
) -> tuple[np.ndarray, dict[str, object]]:
    centers = vertices[faces].mean(axis=1)
    u, v = project_xz(centers, bounds_min, bounds_max, bbox)
    remove = np.zeros(len(faces), dtype=bool)
    windows: list[dict[str, object]] = []
    for feature in FEATURES:
        if "window_px" not in feature:
            continue
        fx, fy = feature["center_px"]
        radius = feature["window_px"]
        local = ((u - fx) / radius) ** 2 + ((v - fy) / radius) ** 2 <= 1.0
        remove |= local
        windows.append({
            "name": feature["name"],
            "center_px": feature["center_px"],
            "radius_px": radius,
            "removed_rebuild_triangles": int(local.sum()),
        })
    return faces[~remove], {
        "method": "small bilateral surface windows covered by exact exterior Seed-42 feature bands",
        "windows": windows,
        "total_removed_rebuild_triangles": int(remove.sum()),
    }


def create_diagnostic(
    rgb: np.ndarray,
    blue: np.ndarray,
    body: np.ndarray,
    roi: np.ndarray,
    bbox: list[int],
) -> None:
    canvas = np.asarray(Image.fromarray(rgb).convert("RGB"), dtype=np.uint8).copy()
    overlay = canvas.copy()
    overlay[body] = np.array([224, 180, 126], dtype=np.uint8)
    overlay[roi & ~body] = np.array([255, 110, 50], dtype=np.uint8)
    overlay[blue] = np.array([0, 70, 255], dtype=np.uint8)
    result = (0.42 * canvas + 0.58 * overlay).astype(np.uint8)
    x0, y0, x1, y1 = bbox
    result[y0 : y0 + 2, x0 : x1 + 1] = 20
    result[y1 - 1 : y1 + 1, x0 : x1 + 1] = 20
    DIAGNOSTIC.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(result).resize((768, 768), Image.Resampling.NEAREST).save(DIAGNOSTIC)


def main() -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    hash_gate = stage_and_gate_inputs()
    vertices, faces = read_binary_ply(SOURCE)
    bounds_min = vertices[np.unique(faces)].min(axis=0).astype(np.float64)
    bounds_max = vertices[np.unique(faces)].max(axis=0).astype(np.float64)
    blue, body, roi, bbox, rgb = reference_masks()
    profile_x, profile_center, profile_radius, width_report = measured_width_profiles(vertices)
    body_field = signed_distance_field(body)
    lower_guard = -0.105
    xs, ys, zs, scalar = make_variable_width_surface(
        body_field, bounds_min, bounds_max, bbox, lower_guard,
        profile_x, profile_center, profile_radius,
    )
    rebuild_vertices, rebuild_faces = marching_tetrahedra(xs, ys, zs, scalar)
    rebuild_faces, window_report = carve_feature_windows(
        rebuild_vertices, rebuild_faces, bounds_min, bounds_max, bbox
    )
    retained_faces, remove, problem, selection = select_source_faces(
        vertices, faces, roi, body_field, bounds_min, bounds_max, bbox,
        lower_guard, profile_x, profile_center, profile_radius,
    )
    combined_vertices = np.vstack((vertices, rebuild_vertices))
    combined_faces = np.vstack((retained_faces, rebuild_faces + len(vertices)))
    write_binary_ply(MASTER, combined_vertices, combined_faces)
    create_diagnostic(rgb, blue, body, roi, bbox)
    metrics = mesh_metrics(rebuild_vertices, rebuild_faces)

    coordinate_report = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "source_vertex_count": int(len(vertices)),
        "result_vertex_count": int(len(combined_vertices)),
        "source_vertex_prefix_exact": bool(np.array_equal(combined_vertices[: len(vertices)], vertices)),
        "source_vertex_coordinates_modified": 0,
        "outside_roi_faces_preserved_exact": selection["outside_roi_faces_preserved_exact"],
        "outside_roi_source_triangle_count": selection["outside_roi_source_triangles"],
        "roi_problem_triangle_count": int(problem.sum()),
        "removed_source_triangle_count": int(remove.sum()),
        "status": "PASS" if selection["outside_roi_faces_preserved_exact"] else "FAIL",
    }
    ROI_REPORT.write_text(json.dumps(coordinate_report, indent=2) + "\n", encoding="utf-8")
    payload = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "technical_revision": "R11",
        "operation": "single_deterministic_variable_width_implicit_body_rebuild",
        "hash_gate": hash_gate,
        "source": {
            "path": SOURCE.relative_to(ROOT).as_posix(),
            "sha256": sha256(SOURCE),
            "vertices": int(len(vertices)),
            "triangles": int(len(faces)),
            "bounds_min": bounds_min.tolist(),
            "bounds_max": bounds_max.tolist(),
        },
        "roi": {
            "authority": "REF-CLEAN and REF-SEAM only; R08-R10 diagnostics not geometry",
            "projection": "established affine Seed-42 X/Z to REF-SEAM foreground bbox",
            "foreground_bbox_px": bbox,
            "body_pixels": int(body.sum()),
            "seam_crossing_band_pixels": int(np.count_nonzero(roi & ~body)),
            "lower_body_guard_normalized": lower_guard,
            **selection,
        },
        "fixed_boundary_measurement": width_report,
        "rebuild": {
            "method": "one smooth variable-width SDF visual body hull, marching tetrahedra",
            "path": MASTER.relative_to(ROOT).as_posix(),
            "sha256": sha256(MASTER),
            "bytes": MASTER.stat().st_size,
            "local_surface": metrics,
            "protected_feature_integration": window_report,
            "combined_vertices": int(len(combined_vertices)),
            "combined_triangles": int(len(combined_faces)),
            "coordinate_preservation_report": ROI_REPORT.relative_to(ROOT).as_posix(),
            "status": "NON_APPROVED_PENDING_OPTIK_GATE",
        },
        "forbidden_methods_used": {
            "new_seed": False,
            "global_rebuild": False,
            "planar_caps": False,
            "triangle_fans": False,
            "convex_hull_visible_surface": False,
            "multiple_competing_variants": False,
        },
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
    }
    REPORT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
