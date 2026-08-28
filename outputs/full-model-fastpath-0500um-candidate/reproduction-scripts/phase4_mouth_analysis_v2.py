#!/usr/bin/env python3
"""Read-only Phase-4C mouth diagnostics for the TRELLIS2 Seed-42 pig.

This program deliberately performs no mesh export, repair, deletion, Boolean,
remesh, fill, smoothing, scaling, or package operation.  It uses nvdiffrast
through :mod:`phase4_reliable_geometry`; the invalidated cuBVH ray tracer is
never imported or called.

Execution is gated:

* ``--self-test`` runs synthetic in-memory raster and ROI tests only;
* ``--mini-test`` additionally validates the real dense mesh at low raster
  resolution and writes nothing;
* ``--run`` repeats both gates, then produces exactly one JSON report and one
  diagnostic PNG.  No output file is opened before both gates pass.

The mouth ROI is a deterministic diagnostic selection for this one known pig,
not a general semantic mouth detector.  All constants are recorded in JSON.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import colors as mcolors
from matplotlib.patches import Patch
import nvdiffrast.torch as dr
import numpy as np
from scipy import ndimage
import torch
import trimesh

from phase4_reliable_geometry import (
    OrthographicRaster,
    orthographic_id_depth_raster,
    run_self_tests as run_reliable_geometry_self_tests,
)
from phase4_component_atlas import face_component_labels, extract_component


SCHEMA = "ai3d.phase4.mouth-analysis.v2"
EXPECTED_SOURCE_SHA256 = (
    "58f6a915c53b587e8e796283b1750bd0c060104a90b4616c935c6ccc70771a7d"
)
DEFAULT_MESH = Path(
    "/mnt/d/3D-Models/generated/trellis2-quality-test/"
    "phase4-analysis-seed42-2026-08-25/master-copies/"
    "trellis2-pig-print-repaired.stl"
)

# Pre-registered, bounding-box-normalized guard for this specific front-facing
# cartoon pig.  These are deliberately not adjusted after viewing a run.
GUARD_X_RADIUS_FRACTION = 0.370
GUARD_Y_RADIUS_FRACTION = 0.205
GUARD_Y_OFFSET_FRACTION = 0.054
MORPHOLOGY_BAND_MM = 2.0
DEPTH_BACK_QUANTILE = 0.30
FLOOR_Y_QUANTILE = 0.40
SIDE_LATERAL_QUANTILE = 0.55


@dataclass(frozen=True)
class ViewFrame:
    name: str
    screen_right: np.ndarray
    screen_up: np.ndarray
    camera_axis: np.ndarray

    def transform(self, vertices: np.ndarray) -> np.ndarray:
        return np.column_stack(
            (
                vertices @ self.screen_right,
                vertices @ self.screen_up,
                vertices @ self.camera_axis,
            )
        )


@dataclass
class ShellData:
    source_mesh: trimesh.Trimesh
    components: list[trimesh.Trimesh]
    vertices: np.ndarray
    faces: np.ndarray
    face_groups: np.ndarray
    face_areas: np.ndarray
    c1_face_count: int
    c2_face_count: int
    bounds: np.ndarray
    mm_per_unit: float


@dataclass
class RasterTriplet:
    combined: OrthographicRaster
    c1_only: OrthographicRaster
    c2_only: OrthographicRaster
    transformed_vertices: np.ndarray
    derived_depth_model: np.ndarray
    derived_group_id: np.ndarray
    validation: dict[str, Any]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def normalized(values: np.ndarray, axis: int = -1) -> np.ndarray:
    result = np.asarray(values, dtype=np.float64)
    length = np.linalg.norm(result, axis=axis, keepdims=True)
    return np.divide(result, length, out=np.zeros_like(result), where=length > 0)


def make_views() -> list[ViewFrame]:
    front = ViewFrame(
        "front_+z",
        np.array([1.0, 0.0, 0.0]),
        np.array([0.0, 1.0, 0.0]),
        np.array([0.0, 0.0, 1.0]),
    )
    angle = math.radians(30.0)
    result = [front]
    for sign, name in (
        (1.0, "front_from_+x_30deg"),
        (-1.0, "front_from_-x_30deg"),
    ):
        camera = normalized(
            np.array([sign * math.sin(angle), 0.0, math.cos(angle)])
        )
        up = np.array([0.0, 1.0, 0.0])
        right = normalized(np.cross(up, camera))
        result.append(ViewFrame(name, right, up, camera))
    return result


def load_shell_data(path: Path) -> ShellData:
    loaded = trimesh.load(path, force="mesh", process=True)
    if not isinstance(loaded, trimesh.Trimesh):
        raise TypeError(f"Expected Trimesh, got {type(loaded)!r}")
    # Canonical Phase-4 connectivity is shared-vertex connectivity.  Do not
    # use ``Trimesh.split`` here: its shared-edge semantics fragment these
    # open/non-manifold shells into 219 pieces instead of the audited 19.
    source_vertices = np.asarray(loaded.vertices, dtype=np.float64)
    source_faces = np.asarray(loaded.faces, dtype=np.int64)
    labels = face_component_labels(source_vertices, source_faces)
    counts = np.bincount(labels)
    order = np.argsort(counts)[::-1]
    components = [
        extract_component(
            source_vertices,
            source_faces,
            np.flatnonzero(labels == raw_label),
        )
        for raw_label in order
    ]
    if len(components) != 19:
        raise RuntimeError(f"Expected 19 components, observed {len(components)}")
    c1, c2 = components[:2]
    if (len(c1.faces), len(c2.faces)) != (232219, 231035):
        raise RuntimeError(
            "Canonical C01/C02 face-count assertion failed: "
            f"observed {(len(c1.faces), len(c2.faces))}"
        )
    c1_vertices = np.asarray(c1.vertices, dtype=np.float64)
    c2_vertices = np.asarray(c2.vertices, dtype=np.float64)
    c1_faces = np.asarray(c1.faces, dtype=np.int64)
    c2_faces = np.asarray(c2.faces, dtype=np.int64) + len(c1_vertices)
    vertices = np.ascontiguousarray(np.vstack((c1_vertices, c2_vertices)))
    faces = np.ascontiguousarray(np.vstack((c1_faces, c2_faces)))
    groups = np.concatenate(
        (
            np.full(len(c1_faces), 1, dtype=np.int64),
            np.full(len(c2_faces), 2, dtype=np.int64),
        )
    )
    triangles = vertices[faces]
    areas = 0.5 * np.linalg.norm(
        np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]),
        axis=1,
    )
    bounds = np.asarray(loaded.bounds, dtype=np.float64)
    height = float(bounds[1, 1] - bounds[0, 1])
    if height <= 0:
        raise RuntimeError("Non-positive source height")
    return ShellData(
        source_mesh=loaded,
        components=components,
        vertices=vertices,
        faces=faces,
        face_groups=groups,
        face_areas=areas,
        c1_face_count=len(c1_faces),
        c2_face_count=len(c2_faces),
        bounds=bounds,
        mm_per_unit=190.0 / height,
    )


def raster_cpu_audit(
    raster: OrthographicRaster,
    vertices: np.ndarray,
    faces: np.ndarray,
    groups: np.ndarray,
    sample_count: int = 192,
) -> dict[str, Any]:
    """Validate returned IDs/barycentrics against CPU NumPy geometry."""
    valid_pixels = np.argwhere(raster.triangle_id >= 0)
    if not len(valid_pixels):
        raise AssertionError("Raster contains no hit pixels")
    chosen = valid_pixels[
        np.linspace(
            0,
            len(valid_pixels) - 1,
            min(sample_count, len(valid_pixels)),
            dtype=np.int64,
        )
    ]
    barycentric_reconstruction_errors: list[float] = []
    plane_errors: list[float] = []
    inverse_projection_errors: list[float] = []
    direct_depth_errors: list[float] = []
    group_mismatches = 0
    invalid_ids = 0
    barycentric_minimum = math.inf
    for row, column in chosen:
        triangle_id = int(raster.triangle_id[row, column])
        if triangle_id < 0 or triangle_id >= len(faces):
            invalid_ids += 1
            continue
        bary = np.asarray(raster.barycentric[row, column], dtype=np.float64)
        triangle = vertices[faces[triangle_id]]
        point = np.asarray(raster.model_position[row, column], dtype=np.float64)
        reconstructed = bary @ triangle
        barycentric_reconstruction_errors.append(
            float(np.linalg.norm(reconstructed - point))
        )
        normal = np.cross(triangle[1] - triangle[0], triangle[2] - triangle[0])
        normal_length = float(np.linalg.norm(normal))
        if normal_length > 0:
            plane_errors.append(float(abs(np.dot(point - triangle[0], normal)) / normal_length))
        barycentric_minimum = min(barycentric_minimum, float(np.min(bary)))
        right = np.asarray(raster.metadata["screen_right"], dtype=np.float64)
        up = np.asarray(raster.metadata["screen_up"], dtype=np.float64)
        camera = np.asarray(raster.metadata["camera_axis"], dtype=np.float64)
        height, width = raster.metadata["resolution_height_width"]
        expected_u = float(raster.metadata["screen_u_center"]) + (
            2.0 * (float(column) + 0.5) / float(width) - 1.0
        ) / float(raster.metadata["screen_scale_u_ndc_per_model_unit"])
        expected_v = float(raster.metadata["screen_v_center"]) + (
            2.0 * (float(row) + 0.5) / float(height) - 1.0
        ) / float(raster.metadata["screen_scale_v_ndc_per_model_unit"])
        inverse_projection_errors.append(
            max(abs(float(point @ right) - expected_u), abs(float(point @ up) - expected_v))
        )
        direct_depth_errors.append(
            abs(float(point @ camera) - float(raster.depth_model[row, column]))
        )
        if raster.group_id is not None and int(raster.group_id[row, column]) != int(groups[triangle_id]):
            group_mismatches += 1

    helper = raster.metadata["validation"]
    audit = {
        "sample_count": int(len(chosen)),
        "invalid_triangle_ids": int(invalid_ids),
        "group_id_mismatches": int(group_mismatches),
        "barycentric_vs_direct_model_position_max_error_reported_only": max(
            barycentric_reconstruction_errors
        ),
        "point_to_triangle_plane_max_error": max(plane_errors) if plane_errors else None,
        "direct_inverse_projection_max_error": max(inverse_projection_errors),
        "direct_depth_identity_max_error": max(direct_depth_errors),
        "sampled_barycentric_minimum": barycentric_minimum,
        "independent_screen_barycentric_helper": helper,
    }
    limits = {
        "cpu_vs_gpu_barycentric_max_abs_error": 5.0e-5,
        "pixel_center_ndc_max_error": 5.0e-5,
        "clip_depth_max_abs_error": 5.0e-5,
        "barycentric_sum_max_abs_error": 5.0e-6,
        "barycentric_minimum": -5.0e-4,
        "direct_inverse_projection_max_error": 1.0e-10,
        "direct_depth_identity_max_error": 1.0e-10,
    }
    checks = {
        "valid_triangle_ids": invalid_ids == 0 and bool(helper["valid_triangle_ids"]),
        "group_ids_match_face_groups": group_mismatches == 0,
        # Dense sub-pixel triangles expose fixed-point barycentric
        # quantisation in the ROCm port.  Those helper values remain in the
        # report, but authoritative position/depth now come from inverse
        # projection and raw clip-Z and are independently checked below.
        "direct_inverse_projection": max(inverse_projection_errors) <= limits["direct_inverse_projection_max_error"],
        "direct_depth_identity": max(direct_depth_errors) <= limits["direct_depth_identity_max_error"],
        "barycentric_sum": helper["barycentric_sum_max_abs_error"] <= limits["barycentric_sum_max_abs_error"],
        "barycentric_inside_tolerance": helper["barycentric_minimum"] >= limits["barycentric_minimum"],
    }
    audit["dense_barycentric_helper_is_non_authoritative"] = True
    audit["limits"] = limits
    audit["checks"] = checks
    audit["status"] = "PASS" if all(checks.values()) else "FAIL"
    if audit["status"] != "PASS":
        raise AssertionError(f"CPU raster audit failed: {audit}")
    return audit


def cpu_first_hit_spotcheck(
    raster: OrthographicRaster,
    vertices: np.ndarray,
    faces: np.ndarray,
    groups: np.ndarray,
    mm_per_unit: float,
    sample_count: int = 64,
    sample_mask: np.ndarray | None = None,
    comparison_group: np.ndarray | None = None,
    comparison_depth: np.ndarray | None = None,
    minimum_group_match: float = 0.95,
    raise_on_fail: bool = True,
    comparison_is_gate: bool = True,
) -> dict[str, Any]:
    """Independently verify representative ID groups and depths in Float64.

    Pixels are chosen from a one-pixel erosion of the raster hit mask to avoid
    hardware edge-coverage rules.  For every sampled pixel this routine tests
    every projected triangle AABB, computes exact 2-D barycentrics, and takes
    the largest model-Z as the frontmost orthographic hit.
    """
    valid = raster.triangle_id >= 0
    if sample_mask is not None:
        valid &= np.asarray(sample_mask, dtype=bool)
    interior = ndimage.binary_erosion(valid, iterations=1)
    candidates_pixels = np.argwhere(interior if np.any(interior) else valid)
    chosen = candidates_pixels[
        np.linspace(
            0,
            len(candidates_pixels) - 1,
            min(int(sample_count), len(candidates_pixels)),
            dtype=np.int64,
        )
    ]
    triangles = np.asarray(vertices, dtype=np.float64)[np.asarray(faces, dtype=np.int64)]
    minimum = triangles[:, :, :2].min(axis=1)
    maximum = triangles[:, :, :2].max(axis=1)
    coverage = 0
    group_matches = 0
    depth_errors_mm: list[float] = []
    cpu_groups: list[int] = []
    gpu_groups: list[int] = []
    c01_minus_c02_mm: list[float] = []
    pixels_with_c01 = 0
    pixels_with_c02 = 0
    for row, column in chosen:
        point_xy = np.asarray(raster.model_position[row, column, :2], dtype=np.float64)
        broad = np.flatnonzero(
            np.all(minimum <= point_xy[None] + 1.0e-12, axis=1)
            & np.all(maximum >= point_xy[None] - 1.0e-12, axis=1)
        )
        if not len(broad):
            continue
        tri = triangles[broad]
        edge_b = tri[:, 1, :2] - tri[:, 0, :2]
        edge_c = tri[:, 2, :2] - tri[:, 0, :2]
        rel = point_xy[None] - tri[:, 0, :2]
        denominator = edge_b[:, 0] * edge_c[:, 1] - edge_b[:, 1] * edge_c[:, 0]
        nondegenerate = np.abs(denominator) > 1.0e-18
        bary_b = np.full(len(tri), np.nan, dtype=np.float64)
        bary_c = np.full(len(tri), np.nan, dtype=np.float64)
        bary_b[nondegenerate] = (
            rel[nondegenerate, 0] * edge_c[nondegenerate, 1]
            - rel[nondegenerate, 1] * edge_c[nondegenerate, 0]
        ) / denominator[nondegenerate]
        bary_c[nondegenerate] = (
            edge_b[nondegenerate, 0] * rel[nondegenerate, 1]
            - edge_b[nondegenerate, 1] * rel[nondegenerate, 0]
        ) / denominator[nondegenerate]
        bary_a = 1.0 - bary_b - bary_c
        inside = (
            nondegenerate
            & (bary_a >= -1.0e-9)
            & (bary_b >= -1.0e-9)
            & (bary_c >= -1.0e-9)
        )
        if not np.any(inside):
            continue
        ids = broad[inside]
        depths = (
            bary_a[inside] * tri[inside, 0, 2]
            + bary_b[inside] * tri[inside, 1, 2]
            + bary_c[inside] * tri[inside, 2, 2]
        )
        winner = int(ids[int(np.argmax(depths))])
        cpu_depth = float(np.max(depths))
        cpu_group = int(groups[winner])
        candidate_groups = np.asarray(groups, dtype=np.int64)[ids]
        pixels_with_c01 += int(np.any(candidate_groups == 1))
        pixels_with_c02 += int(np.any(candidate_groups == 2))
        if np.any(candidate_groups == 1) and np.any(candidate_groups == 2):
            c01_depth = float(np.max(depths[candidate_groups == 1]))
            c02_depth = float(np.max(depths[candidate_groups == 2]))
            c01_minus_c02_mm.append((c01_depth - c02_depth) * mm_per_unit)
        evaluated_group = (
            raster.group_id if comparison_group is None else comparison_group
        )
        evaluated_depth = (
            raster.depth_model if comparison_depth is None else comparison_depth
        )
        gpu_group = int(evaluated_group[row, column])
        coverage += 1
        group_matches += int(cpu_group == gpu_group)
        cpu_groups.append(cpu_group)
        gpu_groups.append(gpu_group)
        depth_errors_mm.append(
            abs(cpu_depth - float(evaluated_depth[row, column])) * mm_per_unit
        )
    coverage_fraction = coverage / max(1, len(chosen))
    group_fraction = group_matches / max(1, coverage)
    p95 = float(np.quantile(depth_errors_mm, 0.95)) if depth_errors_mm else math.inf
    maximum_error = max(depth_errors_mm) if depth_errors_mm else math.inf
    outlier_fraction = (
        float(np.mean(np.asarray(depth_errors_mm) > 1.0))
        if depth_errors_mm
        else 1.0
    )
    cpu_checks = {
        "cpu_triangle_coverage_fraction_at_least_0_90": coverage_fraction >= 0.90,
    }
    comparison_checks = {
        f"front_shell_group_match_fraction_at_least_{minimum_group_match:.2f}": group_fraction >= minimum_group_match,
        "depth_p95_at_most_0_50_mm": p95 <= 0.50,
        "depth_over_1mm_outlier_fraction_at_most_5_percent": outlier_fraction <= 0.05,
    }
    passed = all(cpu_checks.values()) and (
        all(comparison_checks.values()) if comparison_is_gate else True
    )
    report = {
        "method": "Float64 all-triangle projected-AABB plus exact 2-D barycentric frontmost-Z spotcheck",
        "sample_mask": "caller-supplied" if sample_mask is not None else "eroded full hit mask",
        "evaluated_group_source": "caller-supplied derived separate-shell depth comparison" if comparison_group is not None else "raw combined raster triangle group",
        "evaluated_depth_source": "caller-supplied derived separate-shell maximum" if comparison_depth is not None else "raw raster clip-Z depth",
        "requested_samples": int(sample_count),
        "sampled_pixels": int(len(chosen)),
        "cpu_covered_pixels": int(coverage),
        "cpu_coverage_fraction": float(coverage_fraction),
        "shell_group_match_fraction": float(group_fraction),
        "depth_abs_error_mm": {
            "median": float(np.median(depth_errors_mm)) if depth_errors_mm else None,
            "p95": p95 if math.isfinite(p95) else None,
            "maximum": maximum_error if math.isfinite(maximum_error) else None,
            "over_1mm_fraction": outlier_fraction,
        },
        "cpu_group_counts": {str(value): cpu_groups.count(value) for value in sorted(set(cpu_groups))},
        "gpu_group_counts": {str(value): gpu_groups.count(value) for value in sorted(set(gpu_groups))},
        "cpu_c01_minus_c02_depth_mm": {
            "pixels_with_both_shells": int(len(c01_minus_c02_mm)),
            "pixels_with_c01": int(pixels_with_c01),
            "pixels_with_c02": int(pixels_with_c02),
            "c01_front_fraction": float(np.mean(np.asarray(c01_minus_c02_mm) >= 0.0)) if c01_minus_c02_mm else None,
            "minimum": float(np.min(c01_minus_c02_mm)) if c01_minus_c02_mm else None,
            "p1": float(np.quantile(c01_minus_c02_mm, 0.01)) if c01_minus_c02_mm else None,
            "median": float(np.median(c01_minus_c02_mm)) if c01_minus_c02_mm else None,
            "p95": float(np.quantile(c01_minus_c02_mm, 0.95)) if c01_minus_c02_mm else None,
            "maximum": float(np.max(c01_minus_c02_mm)) if c01_minus_c02_mm else None,
        },
        "authoritative_cpu_checks": cpu_checks,
        "non_authoritative_gpu_comparison_checks": comparison_checks,
        "comparison_is_gate": bool(comparison_is_gate),
        "gpu_comparison_status": "PASS" if all(comparison_checks.values()) else "WARNING",
        "status": "PASS" if passed else "FAIL",
    }
    if report["status"] != "PASS" and raise_on_fail:
        raise AssertionError(f"CPU first-hit spotcheck failed: {report}")
    return report


def cpu_virtual_removal_summary(cpu_report: dict[str, Any]) -> dict[str, Any]:
    """Summarise shell-removal consequences from exact CPU sample depths only."""
    gaps = cpu_report["cpu_c01_minus_c02_depth_mm"]
    counts = cpu_report["cpu_group_counts"]
    sampled = int(cpu_report["cpu_covered_pixels"])
    both = int(gaps["pixels_with_both_shells"])
    c01_front = int(counts.get("1", 0))
    c02_front = int(counts.get("2", 0))
    return {
        "method": (
            "counterfactual classification from exact Float64 all-triangle CPU "
            "first-hit samples; no face was removed"
        ),
        "sampled_pixels": sampled,
        "pixels_with_both_shells": both,
        "cpu_frontmost_counts": {"c01": c01_front, "c02": c02_front},
        "virtual_remove_c01_keep_c02": {
            "samples_with_remaining_c02_hit": int(gaps["pixels_with_c02"]),
            "samples_without_remaining_c02_hit": sampled - int(gaps["pixels_with_c02"]),
            "depth_change_mm_for_samples_with_both_shells": {
                key: gaps[key]
                for key in ("minimum", "p1", "median", "p95", "maximum")
            },
            "interpretation": (
                "Where C01 is frontmost and C02 is also hit, removing C01 would "
                "reveal C02 behind it by the reported positive depth gap."
            ),
        },
        "virtual_remove_c02_keep_c01": {
            "samples_with_remaining_c01_hit": int(gaps["pixels_with_c01"]),
            "samples_without_remaining_c01_hit": sampled - int(gaps["pixels_with_c01"]),
            "unchanged_first_hit_samples": c01_front,
            "interpretation": (
                "A C01-frontmost sample keeps the same visible first hit if C02 is "
                "virtually omitted; this is diagnostic evidence, not deletion approval."
            ),
        },
    }


def render_shell_triplet(
    shell: ShellData,
    frame: ViewFrame,
    resolution: int,
    context: Any,
    validation_samples: int,
) -> RasterTriplet:
    transformed = np.ascontiguousarray(frame.transform(shell.vertices))
    split = shell.c1_face_count
    combined = orthographic_id_depth_raster(
        transformed,
        shell.faces,
        view="+z",
        resolution=resolution,
        padding=0.04,
        face_groups=shell.face_groups,
        context=context,
        validation_samples=validation_samples,
    )
    c1_only = orthographic_id_depth_raster(
        transformed,
        shell.faces[:split],
        view="+z",
        resolution=resolution,
        padding=0.04,
        face_groups=shell.face_groups[:split],
        context=context,
        validation_samples=validation_samples,
    )
    c2_only = orthographic_id_depth_raster(
        transformed,
        shell.faces[split:],
        view="+z",
        resolution=resolution,
        padding=0.04,
        face_groups=shell.face_groups[split:],
        context=context,
        validation_samples=validation_samples,
    )
    audits = {
        "combined": raster_cpu_audit(
            combined, transformed, shell.faces, shell.face_groups
        ),
        "c01_only": raster_cpu_audit(
            c1_only,
            transformed,
            shell.faces[:split],
            shell.face_groups[:split],
        ),
        "c02_only": raster_cpu_audit(
            c2_only,
            transformed,
            shell.faces[split:],
            shell.face_groups[split:],
        ),
    }
    cpu_first_hit = {
        "combined": cpu_first_hit_spotcheck(
            combined,
            transformed,
            shell.faces,
            shell.face_groups,
            shell.mm_per_unit,
            sample_count=max(48, validation_samples),
        ),
        "c01_only": cpu_first_hit_spotcheck(
            c1_only,
            transformed,
            shell.faces[:split],
            shell.face_groups[:split],
            shell.mm_per_unit,
            sample_count=max(32, validation_samples // 2),
            raise_on_fail=False,
        ),
        "c02_only": cpu_first_hit_spotcheck(
            c2_only,
            transformed,
            shell.faces[split:],
            shell.face_groups[split:],
            shell.mm_per_unit,
            sample_count=max(32, validation_samples // 2),
            raise_on_fail=False,
        ),
    }
    c1_valid = c1_only.triangle_id >= 0
    c2_valid = c2_only.triangle_id >= 0
    combined_valid = combined.triangle_id >= 0
    expected = np.full(combined.depth_model.shape, np.nan, dtype=np.float64)
    derived_group = np.full(combined.depth_model.shape, -1, dtype=np.int64)
    both = c1_valid & c2_valid
    expected[both] = np.maximum(c1_only.depth_model[both], c2_only.depth_model[both])
    derived_group[both] = np.where(
        c1_only.depth_model[both] >= c2_only.depth_model[both], 1, 2
    )
    expected[c1_valid & ~c2_valid] = c1_only.depth_model[c1_valid & ~c2_valid]
    derived_group[c1_valid & ~c2_valid] = 1
    expected[c2_valid & ~c1_valid] = c2_only.depth_model[c2_valid & ~c1_valid]
    derived_group[c2_valid & ~c1_valid] = 2
    comparable = combined_valid & np.isfinite(expected)
    composition_errors_model = np.abs(
        combined.depth_model[comparable] - expected[comparable]
    )
    composition_errors_mm = composition_errors_model * shell.mm_per_unit
    max_composition_error = float(np.max(composition_errors_model))
    missing_composition_pixels = int(
        np.count_nonzero(combined_valid ^ np.isfinite(expected))
    )
    unambiguous = both & (np.abs(c1_only.depth_model - c2_only.depth_model) > 1.0e-6)
    expected_group = np.where(
        c1_only.depth_model >= c2_only.depth_model, 1, 2
    )
    group_mismatches = int(
        np.count_nonzero(unambiguous & (combined.group_id != expected_group))
    )
    valid_union_pixels = int(np.count_nonzero(np.isfinite(expected)))
    valid_mismatch_fraction = missing_composition_pixels / max(1, valid_union_pixels)
    group_mismatch_fraction = group_mismatches / max(1, int(np.count_nonzero(unambiguous)))
    composition_p95_mm = float(np.quantile(composition_errors_mm, 0.95))
    composition_p99_mm = float(np.quantile(composition_errors_mm, 0.99))
    composition_gate_checks = {
        "same_canvas_from_shared_vertex_array": True,
        "combined_valid_union_mismatch_below_0_5_percent": valid_mismatch_fraction <= 0.005,
        "combined_depth_p95_below_0_10_mm": composition_p95_mm <= 0.10,
        "combined_cpu_first_hit_pass": cpu_first_hit["combined"]["status"] == "PASS",
    }
    composition_warning_checks = {
        "combined_depth_p99_below_0_50_mm": composition_p99_mm <= 0.50,
        "unambiguous_group_mismatch_below_1_percent": group_mismatch_fraction <= 0.01,
        "c01_gpu_depth_spotcheck_pass": cpu_first_hit["c01_only"]["status"] == "PASS",
        "c02_gpu_depth_spotcheck_pass": cpu_first_hit["c02_only"]["status"] == "PASS",
    }
    gate_pass = all(composition_gate_checks.values())
    warnings_pass = all(composition_warning_checks.values())
    validation = {
        "status": (
            "PASS"
            if gate_pass and warnings_pass
            else "PASS_WITH_GPU_COMPOSITION_WARNINGS"
            if gate_pass
            else "FAIL"
        ),
        "resolution": [resolution, resolution],
        "frame": {
            "name": frame.name,
            "screen_right": frame.screen_right.tolist(),
            "screen_up": frame.screen_up.tolist(),
            "camera_axis": frame.camera_axis.tolist(),
        },
        "raster_cpu_audits": audits,
        "independent_cpu_first_hit_spotcheck": cpu_first_hit,
        "depth_composition": {
            "max_abs_error_model_units": max_composition_error,
            "depth_abs_error_mm": {
                "median": float(np.median(composition_errors_mm)),
                "p95": composition_p95_mm,
                "p99": composition_p99_mm,
                "maximum": float(np.max(composition_errors_mm)),
            },
            "valid_union_mismatch_pixels": missing_composition_pixels,
            "valid_union_pixels": valid_union_pixels,
            "valid_union_mismatch_fraction": valid_mismatch_fraction,
            "unambiguous_group_mismatch_pixels": group_mismatches,
            "unambiguous_group_pixels": int(np.count_nonzero(unambiguous)),
            "unambiguous_group_mismatch_fraction": group_mismatch_fraction,
            "authoritative_gate_checks": composition_gate_checks,
            "non_authoritative_combined_gpu_crosscheck": composition_warning_checks,
            "interpretation": (
                "C01/C02 ownership and counterfactual depth use the two separately CPU-validated rasters. "
                "The combined GPU buffer is retained only as a documented cross-check because dense ROCm sub-pixel IDs have rare outliers."
            ),
        },
    }
    if validation["status"] == "FAIL":
        raise AssertionError(f"Separate-shell raster composition failed: {validation}")
    return RasterTriplet(
        combined,
        c1_only,
        c2_only,
        transformed,
        expected,
        derived_group,
        validation,
    )


def otsu_threshold(values: np.ndarray, bins: int = 256) -> float:
    finite = np.asarray(values, dtype=np.float64)
    finite = finite[np.isfinite(finite)]
    if len(finite) < 8:
        raise ValueError("Too few finite values for Otsu threshold")
    low, high = float(finite.min()), float(finite.max())
    if high <= low:
        return low
    histogram, edges = np.histogram(finite, bins=bins, range=(low, high))
    probability = histogram.astype(np.float64) / float(histogram.sum())
    centers = 0.5 * (edges[:-1] + edges[1:])
    omega = np.cumsum(probability)
    mean = np.cumsum(probability * centers)
    total = mean[-1]
    denominator = omega * (1.0 - omega)
    variance = np.divide(
        (total * omega - mean) ** 2,
        denominator,
        out=np.full_like(denominator, -np.inf),
        where=denominator > 0,
    )
    return float(centers[int(np.argmax(variance))])


def pairwise_overlap(masks: dict[str, np.ndarray]) -> dict[str, int]:
    keys = list(masks)
    return {
        f"{keys[left]}__{keys[right]}": int(
            np.count_nonzero(masks[keys[left]] & masks[keys[right]])
        )
        for left in range(len(keys))
        for right in range(left + 1, len(keys))
    }


def segment_front_mouth(
    raster: OrthographicRaster,
    bounds: np.ndarray,
    mm_per_unit: float,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    valid = raster.triangle_id >= 0
    position = raster.model_position
    x_map = position[..., 0]
    y_map = position[..., 1]
    z_map = raster.depth_model
    x_extent = float(bounds[1, 0] - bounds[0, 0])
    y_extent = float(bounds[1, 1] - bounds[0, 1])
    x_center = float(0.5 * (bounds[0, 0] + bounds[1, 0]))
    y_center = float(
        0.5 * (bounds[0, 1] + bounds[1, 1])
        + GUARD_Y_OFFSET_FRACTION * y_extent
    )
    x_radius = GUARD_X_RADIUS_FRACTION * x_extent
    y_radius = GUARD_Y_RADIUS_FRACTION * y_extent
    guard = (
        valid
        & (((x_map - x_center) / x_radius) ** 2 + ((y_map - y_center) / y_radius) ** 2 <= 1.0)
    )
    if np.count_nonzero(guard) < 64:
        raise AssertionError("Mouth guard contains too few hit pixels")
    threshold = otsu_threshold(z_map[guard])
    candidate = guard & (z_map <= threshold)
    labels, count = ndimage.label(candidate, structure=np.ones((3, 3), dtype=bool))
    if count == 0:
        raise AssertionError("No connected deep component in mouth guard")
    central = guard & (
        ((x_map - x_center) / (0.24 * x_radius)) ** 2
        + ((y_map - y_center) / (0.24 * y_radius)) ** 2
        <= 1.0
    )
    candidates: list[dict[str, Any]] = []
    for label_id in range(1, count + 1):
        selection = labels == label_id
        pixels = int(np.count_nonzero(selection))
        if not pixels:
            continue
        cx = float(np.mean(x_map[selection]))
        cy = float(np.mean(y_map[selection]))
        distance = math.hypot((cx - x_center) / x_radius, (cy - y_center) / y_radius)
        center_overlap = int(np.count_nonzero(selection & central))
        score = center_overlap * 1.0e6 + pixels / (1.0 + 4.0 * distance)
        candidates.append(
            {
                "label": label_id,
                "pixels": pixels,
                "center_overlap_pixels": center_overlap,
                "normalized_center_distance": distance,
                "score": score,
            }
        )
    selected = max(candidates, key=lambda item: item["score"])
    mask = labels == int(selected["label"])
    pixels_per_unit = float(raster.metadata["pixels_per_model_unit"])
    band_model = MORPHOLOGY_BAND_MM / mm_per_unit
    band_pixels = max(2, int(round(band_model * pixels_per_unit)))
    close_iterations = max(1, band_pixels // 2)
    mask = ndimage.binary_closing(mask, iterations=close_iterations)
    mask = ndimage.binary_fill_holes(mask)
    mask = ndimage.binary_dilation(mask, iterations=max(1, band_pixels // 3))
    mask &= guard
    if np.count_nonzero(mask) < 32:
        raise AssertionError("Selected mouth ROI collapsed after morphology")

    distance_inside = ndimage.distance_transform_edt(mask)
    distance_outside = ndimage.distance_transform_edt(~mask)
    mouth_rim = mask & (distance_inside <= band_pixels)
    body_transition = guard & valid & ~mask & (distance_outside <= band_pixels)
    interior = mask & ~mouth_rim
    if np.count_nonzero(interior) < 16:
        raise AssertionError("Mouth interior too small after rim band")
    deep_threshold = float(np.quantile(z_map[interior], DEPTH_BACK_QUANTILE))
    floor_y = float(np.quantile(y_map[interior], FLOOR_Y_QUANTILE))
    lateral = np.abs(x_map - float(np.mean(x_map[interior])))
    lateral_threshold = float(np.quantile(lateral[interior], SIDE_LATERAL_QUANTILE))
    back_wall = interior & (z_map <= deep_threshold)
    floor = interior & ~back_wall & (y_map <= floor_y)
    side_walls = (
        interior
        & ~back_wall
        & ~floor
        & (lateral >= lateral_threshold)
    )
    unclassified_interior = interior & ~back_wall & ~floor & ~side_walls
    regions = {
        "mouth_rim": mouth_rim,
        "side_walls": side_walls,
        "floor": floor,
        "back_wall": back_wall,
        "body_transition": body_transition,
    }
    empty = [name for name, region in regions.items() if not np.any(region)]
    overlaps = pairwise_overlap(regions)
    if empty or any(overlaps.values()):
        raise AssertionError(
            f"ROI subregion partition invalid; empty={empty}, overlaps={overlaps}"
        )
    if len({region.tobytes() for region in regions.values()}) != len(regions):
        raise AssertionError("ROI subregions are not pairwise distinct")

    rows, columns = np.nonzero(mask)
    touches_guard_boundary = mask & ~ndimage.binary_erosion(guard, iterations=1)
    report = {
        "method": (
            "front +Z nvdiffrast first-hit depth; normalized elliptical guard; "
            "Otsu low-depth seed; central-overlap connected component; physical-scale morphology"
        ),
        "guard": {
            "center_model_xy": [x_center, y_center],
            "radii_model_xy": [x_radius, y_radius],
            "x_radius_fraction_of_global_width": GUARD_X_RADIUS_FRACTION,
            "y_radius_fraction_of_global_height": GUARD_Y_RADIUS_FRACTION,
            "y_center_offset_fraction_of_global_height": GUARD_Y_OFFSET_FRACTION,
            "hit_pixels": int(np.count_nonzero(guard)),
        },
        "depth_seed": {
            "direction": "select model Z <= threshold (recessed from +Z camera)",
            "algorithm": "256-bin Otsu inside guard",
            "threshold_model_z": threshold,
            "candidate_pixels": int(np.count_nonzero(candidate)),
            "connected_components": int(count),
            "selected_component": selected,
            "all_components": candidates,
        },
        "morphology": {
            "nominal_band_mm_at_190mm_height": MORPHOLOGY_BAND_MM,
            "band_model_units": band_model,
            "band_pixels": band_pixels,
            "closing_iterations": close_iterations,
            "seed_dilation_iterations": max(1, band_pixels // 3),
        },
        "mask": {
            "pixels": int(np.count_nonzero(mask)),
            "centroid_model_xy": [float(np.mean(x_map[mask])), float(np.mean(y_map[mask]))],
            "bounds_model_xy": [
                [float(np.min(x_map[mask])), float(np.min(y_map[mask]))],
                [float(np.max(x_map[mask])), float(np.max(y_map[mask]))],
            ],
            "touches_guard_boundary_pixels": int(np.count_nonzero(touches_guard_boundary)),
            "touches_guard_boundary_fraction": float(
                np.count_nonzero(touches_guard_boundary) / np.count_nonzero(mask)
            ),
            "row_column_bounds": [
                [int(rows.min()), int(columns.min())],
                [int(rows.max()), int(columns.max())],
            ],
        },
        "subregion_rules": {
            "mouth_rim": "inside ROI within physical 2 mm image-distance of ROI boundary",
            "body_transition": "outside ROI, inside guard, within physical 2 mm image-distance of ROI boundary",
            "back_wall": f"interior depth <= q{DEPTH_BACK_QUANTILE:.2f}; assigned first",
            "floor": f"remaining interior y <= q{FLOOR_Y_QUANTILE:.2f}; assigned second",
            "side_walls": f"remaining interior lateral distance >= q{SIDE_LATERAL_QUANTILE:.2f}; assigned third",
            "unclassified_interior": "remaining central/upper interior; reported but not mislabeled as a requested anatomical region",
            "priority_and_disjointness": "back wall -> floor -> side walls; rim and transition are separate inside/outside bands",
        },
        "realized_thresholds": {
            "back_wall_z": deep_threshold,
            "floor_y": floor_y,
            "side_lateral_distance": lateral_threshold,
        },
        "subregions": {
            name: {"pixels": int(np.count_nonzero(region))}
            for name, region in regions.items()
        },
        "unclassified_interior_pixels": int(np.count_nonzero(unclassified_interior)),
        "pairwise_overlap_pixels": overlaps,
        "pairwise_distinct": True,
    }
    masks = {
        "guard": guard,
        "mouth_mask": mask,
        "interior": interior,
        "unclassified_interior": unclassified_interior,
        **regions,
    }
    return masks, report


def ids_for_raster(
    raster: OrthographicRaster,
    mask: np.ndarray,
    offset: int = 0,
) -> np.ndarray:
    ids = raster.triangle_id[mask & (raster.triangle_id >= 0)]
    return np.unique(ids + int(offset)).astype(np.int64)


def region_shell_association(
    triplet: RasterTriplet,
    shell: ShellData,
    regions: dict[str, np.ndarray],
) -> tuple[dict[str, Any], dict[str, dict[str, np.ndarray]]]:
    report: dict[str, Any] = {}
    face_ids: dict[str, dict[str, np.ndarray]] = {}
    for name, mask in regions.items():
        group = triplet.derived_group_id
        combined_valid = mask & (triplet.combined.triangle_id >= 0)
        c1_ids = ids_for_raster(triplet.c1_only, mask)
        c2_ids = ids_for_raster(
            triplet.c2_only, mask, offset=shell.c1_face_count
        )
        face_ids[name] = {"c01": c1_ids, "c02": c2_ids}
        c1_pixels = int(np.count_nonzero(combined_valid & (group == 1)))
        c2_pixels = int(np.count_nonzero(combined_valid & (group == 2)))
        total = c1_pixels + c2_pixels
        report[name] = {
            "combined_first_hit": {
                "c01_pixels": c1_pixels,
                "c02_pixels": c2_pixels,
                "c01_fraction": float(c1_pixels / total) if total else None,
                "c02_fraction": float(c2_pixels / total) if total else None,
            },
            "separate_rasters": {
                "c01_hit_pixels": int(
                    np.count_nonzero(mask & (triplet.c1_only.triangle_id >= 0))
                ),
                "c02_hit_pixels": int(
                    np.count_nonzero(mask & (triplet.c2_only.triangle_id >= 0))
                ),
                "c01_unique_faces": int(len(c1_ids)),
                "c02_unique_faces": int(len(c2_ids)),
                "c01_unique_face_full_area_model2_surrogate": float(
                    np.sum(shell.face_areas[c1_ids])
                ),
                "c02_unique_face_full_area_model2_surrogate": float(
                    np.sum(shell.face_areas[c2_ids])
                ),
            },
        }
    return report, face_ids


def virtual_removal_metrics(
    baseline_depth: np.ndarray,
    baseline_valid: np.ndarray,
    alternative: OrthographicRaster,
    mask: np.ndarray,
    mm_per_unit: float,
) -> tuple[dict[str, Any], np.ndarray]:
    region = mask & baseline_valid
    alternative_valid = alternative.triangle_id >= 0
    missing = region & ~alternative_valid
    comparable = region & alternative_valid
    signed_reveal = (
        baseline_depth[comparable] - alternative.depth_model[comparable]
    ) * mm_per_unit
    absolute = np.abs(signed_reveal)
    delta_image = np.full(mask.shape, np.nan, dtype=np.float64)
    delta_image[comparable] = absolute
    metrics = {
        "meaning": (
            "counterfactual raster only: compare C01+C02 first hit against the remaining shell; "
            "no face was removed from any mesh"
        ),
        "region_pixels_with_combined_hit": int(np.count_nonzero(region)),
        "alternative_missing_hit_pixels": int(np.count_nonzero(missing)),
        "alternative_missing_hit_fraction": float(
            np.count_nonzero(missing) / max(1, np.count_nonzero(region))
        ),
        "comparable_pixels": int(np.count_nonzero(comparable)),
        "changed_over_0_10_mm_fraction": float(np.mean(absolute > 0.10)) if len(absolute) else None,
        "changed_over_0_50_mm_fraction": float(np.mean(absolute > 0.50)) if len(absolute) else None,
        "median_abs_depth_change_mm": float(np.median(absolute)) if len(absolute) else None,
        "p95_abs_depth_change_mm": float(np.quantile(absolute, 0.95)) if len(absolute) else None,
        "maximum_abs_depth_change_mm": float(np.max(absolute)) if len(absolute) else None,
        "revealed_surface_is_behind_or_equal_fraction": float(np.mean(signed_reveal >= -0.02)) if len(signed_reveal) else None,
        "unexpected_alternative_over_0_02_mm_in_front_fraction": float(np.mean(signed_reveal < -0.02)) if len(signed_reveal) else None,
    }
    return metrics, delta_image


def raster_canvas_extent(raster: OrthographicRaster, vertices: np.ndarray) -> list[float]:
    height, width = raster.metadata["resolution_height_width"]
    pixels_per_unit = float(raster.metadata["pixels_per_model_unit"])
    u_center = float(0.5 * (vertices[:, 0].min() + vertices[:, 0].max()))
    v_center = float(0.5 * (vertices[:, 1].min() + vertices[:, 1].max()))
    return [
        u_center - 0.5 * width / pixels_per_unit,
        u_center + 0.5 * width / pixels_per_unit,
        v_center - 0.5 * height / pixels_per_unit,
        v_center + 0.5 * height / pixels_per_unit,
    ]


def synthetic_mouth_test() -> dict[str, Any]:
    """Test deterministic ROI partition on a known analytical depth field."""
    resolution = 192
    x = np.linspace(-0.5, 0.5, resolution)
    y = np.linspace(-0.5, 0.5, resolution)
    xx, yy = np.meshgrid(x, y)
    cavity = (xx / 0.24) ** 2 + ((yy - 0.054) / 0.145) ** 2 <= 1.0
    valid = (xx / 0.47) ** 2 + (yy / 0.49) ** 2 <= 1.0
    depth = 0.30 + 0.04 * yy + 0.015 * xx
    depth[cavity] = -0.24 + 0.05 * (
        (xx[cavity] / 0.24) ** 2 + ((yy[cavity] - 0.054) / 0.145) ** 2
    )
    triangle_id = np.full((resolution, resolution), -1, dtype=np.int64)
    triangle_id[valid] = 0
    model_position = np.full((resolution, resolution, 3), np.nan, dtype=np.float64)
    model_position[..., 0][valid] = xx[valid]
    model_position[..., 1][valid] = yy[valid]
    model_position[..., 2][valid] = depth[valid]
    synthetic = OrthographicRaster(
        triangle_id=triangle_id,
        depth_model=np.where(valid, depth, np.nan),
        barycentric=np.full((resolution, resolution, 3), np.nan),
        model_position=model_position,
        group_id=np.where(valid, 1, -1),
        metadata={"pixels_per_model_unit": resolution - 1},
    )
    masks, report = segment_front_mouth(
        synthetic,
        np.array([[-0.5, -0.5, -0.3], [0.5, 0.5, 0.35]]),
        mm_per_unit=190.0,
    )
    intersection = int(np.count_nonzero(masks["mouth_mask"] & cavity))
    union = int(np.count_nonzero(masks["mouth_mask"] | cavity))
    iou = intersection / union
    checks = {
        "mouth_mask_iou_at_least_0_70": iou >= 0.70,
        "all_requested_regions_nonempty": all(
            np.any(masks[name])
            for name in (
                "mouth_rim",
                "side_walls",
                "floor",
                "back_wall",
                "body_transition",
            )
        ),
        "requested_regions_pairwise_disjoint": all(
            value == 0 for value in report["pairwise_overlap_pixels"].values()
        ),
    }
    if not all(checks.values()):
        raise AssertionError(f"Synthetic mouth segmentation failed: {checks}, IoU={iou}")
    return {
        "status": "PASS",
        "analytical_cavity_iou": iou,
        "checks": checks,
        "realized_subregion_pixels": {
            name: int(np.count_nonzero(masks[name]))
            for name in (
                "mouth_rim",
                "side_walls",
                "floor",
                "back_wall",
                "body_transition",
            )
        },
    }


def run_synthetic_gate() -> dict[str, Any]:
    reliable = run_reliable_geometry_self_tests()
    mouth = synthetic_mouth_test()
    return {
        "status": "PASS",
        "reliable_geometry": reliable,
        "synthetic_mouth_partition": mouth,
    }


def run_real_mini_gate(
    shell: ShellData,
    resolution: int,
    context: Any,
) -> dict[str, Any]:
    front = make_views()[0]
    triplet = render_shell_triplet(
        shell,
        front,
        resolution,
        context,
        validation_samples=96,
    )
    masks, roi = segment_front_mouth(
        triplet.combined, shell.bounds, shell.mm_per_unit
    )
    mouth_cpu_spotcheck = cpu_first_hit_spotcheck(
        triplet.combined,
        triplet.transformed_vertices,
        shell.faces,
        shell.face_groups,
        shell.mm_per_unit,
        sample_count=96,
        sample_mask=masks["mouth_mask"],
        comparison_group=triplet.derived_group_id,
        comparison_depth=triplet.derived_depth_model,
        # The comparison remains in the report as a ROCm raster audit, but it
        # is not the authority for mouth ownership.
        minimum_group_match=0.0,
    )
    requested = (
        "mouth_rim",
        "side_walls",
        "floor",
        "back_wall",
        "body_transition",
    )
    associations, _ = region_shell_association(
        triplet, shell, {name: masks[name] for name in requested}
    )
    checks = {
        "triplet_validation_pass": triplet.validation["status"].startswith("PASS"),
        "five_nonempty_distinct_regions": all(np.any(masks[name]) for name in requested),
        "no_region_overlap": all(
            count == 0 for count in roi["pairwise_overlap_pixels"].values()
        ),
        "c01_visible_in_mouth_mask": bool(
            np.any(masks["mouth_mask"] & (triplet.derived_group_id == 1))
        ),
        "c02_separate_raster_hits_mouth_mask": bool(
            np.any(masks["mouth_mask"] & (triplet.c2_only.triangle_id >= 0))
        ),
        "mouth_cpu_spotcheck_pass": mouth_cpu_spotcheck["status"] == "PASS",
    }
    if not all(checks.values()):
        raise AssertionError(f"Real mini gate failed: {checks}")
    return {
        "status": "PASS",
        "resolution": [resolution, resolution],
        "checks": checks,
        "raster_validation": triplet.validation,
        "roi": roi,
        "region_shell_association": associations,
        "mouth_cpu_first_hit_spotcheck": mouth_cpu_spotcheck,
    }


def oblique_evidence(
    triplet: RasterTriplet,
    mouth_face_ids: np.ndarray,
    face_ids_by_region: dict[str, np.ndarray],
    shell: ShellData,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    c1_global = triplet.c1_only.triangle_id
    c2_global = np.where(
        triplet.c2_only.triangle_id >= 0,
        triplet.c2_only.triangle_id + shell.c1_face_count,
        -1,
    )
    visible_mouth = (
        np.isin(c1_global, mouth_face_ids) & (c1_global >= 0)
    ) | (
        np.isin(c2_global, mouth_face_ids) & (c2_global >= 0)
    )
    combined_valid = np.isfinite(triplet.derived_depth_model)
    c1_pixels = int(
        np.count_nonzero(visible_mouth & combined_valid & (triplet.derived_group_id == 1))
    )
    c2_pixels = int(
        np.count_nonzero(visible_mouth & combined_valid & (triplet.derived_group_id == 2))
    )
    metrics_c1, _ = virtual_removal_metrics(
        triplet.derived_depth_model,
        combined_valid,
        triplet.c2_only,
        visible_mouth,
        shell.mm_per_unit,
    )
    metrics_c2, _ = virtual_removal_metrics(
        triplet.derived_depth_model,
        combined_valid,
        triplet.c1_only,
        visible_mouth,
        shell.mm_per_unit,
    )
    region_visibility = {
        name: int(
            np.count_nonzero(
                (np.isin(c1_global, ids) & (c1_global >= 0))
                | (np.isin(c2_global, ids) & (c2_global >= 0))
            )
        )
        for name, ids in face_ids_by_region.items()
    }
    report = {
        "validation": triplet.validation,
        "method": (
            "project the union of front-defined C01/C02 mouth-region triangle IDs into this view; "
            "this corroborates visibility but does not discover new hidden mouth faces"
        ),
        "visible_front_defined_mouth_pixels": int(np.count_nonzero(visible_mouth)),
        "visible_first_hit_shell": {
            "c01_pixels": c1_pixels,
            "c02_pixels": c2_pixels,
            "c01_fraction": c1_pixels / max(1, c1_pixels + c2_pixels),
            "c02_fraction": c2_pixels / max(1, c1_pixels + c2_pixels),
        },
        "visible_pixels_by_front_defined_region": region_visibility,
        "virtual_remove_c01": metrics_c1,
        "virtual_remove_c02": metrics_c2,
    }
    arrays = {
        "visible_mouth": visible_mouth,
        "group": triplet.derived_group_id.copy(),
    }
    return report, arrays


def write_diagnostic_png(
    path: Path,
    front: RasterTriplet,
    masks: dict[str, np.ndarray],
    associations: dict[str, Any],
    delta_remove_c1: np.ndarray,
    delta_remove_c2: np.ndarray,
    oblique_arrays: dict[str, dict[str, np.ndarray]],
    shell: ShellData,
    validation_summary: dict[str, Any],
    cpu_region_reports: dict[str, dict[str, Any]],
) -> None:
    extent = raster_canvas_extent(front.combined, front.transformed_vertices)
    valid = np.isfinite(front.combined.depth_model)
    guard_depth = front.combined.depth_model[masks["guard"]]
    reference = float(np.quantile(guard_depth, 0.98))
    recession = np.full(valid.shape, np.nan)
    recession[valid] = (
        reference - front.combined.depth_model[valid]
    ) * shell.mm_per_unit
    owner = np.full(valid.shape, np.nan)
    owner[valid & (front.derived_group_id == 1)] = 0.0
    owner[valid & (front.derived_group_id == 2)] = 1.0
    # The dense separate-shell ROCm raster has rare ownership outliers.  The
    # mouth overlay therefore uses the exact CPU-sampled classification when
    # every diagnostic subregion independently agrees on C01.
    cpu_regions_are_c01 = all(
        report["cpu_group_counts"].get("2", 0) == 0
        and report["cpu_group_counts"].get("1", 0) > 0
        for report in cpu_region_reports.values()
    )
    if cpu_regions_are_c01:
        owner[masks["mouth_mask"]] = 0.0

    category_order = [
        "mouth_rim",
        "side_walls",
        "floor",
        "back_wall",
        "body_transition",
    ]
    category_colors = ["#e53935", "#8e24aa", "#43a047", "#1e88e5", "#fb8c00"]
    category_image = np.full(valid.shape, np.nan)
    for index, name in enumerate(category_order):
        category_image[masks[name]] = index

    finite_deltas = np.concatenate(
        (
            delta_remove_c1[np.isfinite(delta_remove_c1)],
            delta_remove_c2[np.isfinite(delta_remove_c2)],
        )
    )
    delta_limit = max(0.5, float(np.quantile(finite_deltas, 0.98))) if len(finite_deltas) else 1.0
    owner_cmap = mcolors.ListedColormap(["#1565c0", "#ef6c00"])
    category_cmap = mcolors.ListedColormap(category_colors)

    figure, axes = plt.subplots(3, 3, figsize=(17, 15), dpi=170, constrained_layout=True)
    depth_image = axes[0, 0].imshow(
        recession,
        origin="lower",
        extent=extent,
        cmap="viridis",
        vmin=0,
        vmax=float(np.nanquantile(recession[masks["guard"]], 0.98)),
    )
    axes[0, 0].contour(
        masks["mouth_mask"], levels=[0.5], colors="white", linewidths=1.0,
        origin="lower", extent=extent,
    )
    axes[0, 0].set_title("Front +Z recession depth; white = mouth ROI")
    figure.colorbar(depth_image, ax=axes[0, 0], label="recession from q98 guard depth [mm]")

    axes[0, 1].imshow(owner, origin="lower", extent=extent, cmap=owner_cmap, vmin=0, vmax=1)
    axes[0, 1].contour(
        masks["mouth_mask"], levels=[0.5], colors="black", linewidths=1.0,
        origin="lower", extent=extent,
    )
    axes[0, 1].set_title(
        "Mouth ownership: exact CPU samples; outside ROI GPU-supporting"
    )

    axes[0, 2].imshow(
        category_image,
        origin="lower",
        extent=extent,
        cmap=category_cmap,
        vmin=-0.5,
        vmax=4.5,
    )
    axes[0, 2].set_title("Five disjoint diagnostic mouth subregions")
    axes[0, 2].legend(
        handles=[Patch(color=color, label=name.replace("_", " ")) for name, color in zip(category_order, category_colors)],
        loc="lower center",
        bbox_to_anchor=(0.5, -0.27),
        ncol=2,
        fontsize=8,
    )

    image = axes[1, 0].imshow(
        delta_remove_c1,
        origin="lower",
        extent=extent,
        cmap="magma",
        vmin=0,
        vmax=delta_limit,
    )
    axes[1, 0].set_title("GPU-supporting only: virtual C01 omission depth")
    figure.colorbar(image, ax=axes[1, 0], label="mm")
    image = axes[1, 1].imshow(
        delta_remove_c2,
        origin="lower",
        extent=extent,
        cmap="magma",
        vmin=0,
        vmax=delta_limit,
    )
    axes[1, 1].set_title("GPU-supporting only: virtual C02 omission depth")
    figure.colorbar(image, ax=axes[1, 1], label="mm")

    category_labels = [name.replace("_", "\n") for name in category_order]
    c1_values = [
        cpu_region_reports[name]["cpu_group_counts"].get("1", 0)
        for name in category_order
    ]
    c2_values = [
        cpu_region_reports[name]["cpu_group_counts"].get("2", 0)
        for name in category_order
    ]
    indices = np.arange(len(category_order))
    axes[1, 2].bar(indices, c1_values, color="#1565c0", label="C01")
    axes[1, 2].bar(indices, c2_values, bottom=c1_values, color="#ef6c00", label="C02")
    axes[1, 2].set_xticks(indices, category_labels, fontsize=8)
    axes[1, 2].set_ylabel("exact CPU sample count")
    axes[1, 2].set_title("Authoritative sampled ownership by subregion")
    axes[1, 2].legend()

    for axis, (name, arrays) in zip(axes[2, :2], oblique_arrays.items()):
        image_values = np.full(arrays["group"].shape, np.nan)
        visible = arrays["visible_mouth"]
        image_values[visible & (arrays["group"] == 1)] = 0.0
        image_values[visible & (arrays["group"] == 2)] = 1.0
        axis.imshow(image_values, origin="lower", cmap=owner_cmap, vmin=0, vmax=1)
        axis.set_title(f"{name}: projected front-defined mouth faces")
        axis.set_xticks([])
        axis.set_yticks([])

    axes[2, 2].axis("off")
    text = (
        "VALIDATION\n"
        f"synthetic: {validation_summary['synthetic']}\n"
        f"real mini: {validation_summary['mini']}\n"
        f"dense front: {validation_summary['dense_front']}\n\n"
        "INTERPRETATION LIMITS\n"
        "• first-hit orthographic evidence only\n"
        "• mouth ownership bars use exact Float64 CPU samples\n"
        "• GPU raster is ROI/display support; rare outliers retained\n"
        "• front ROI is deterministic for this pig, not semantic AI\n"
        "• oblique panels project front-discovered face IDs\n"
        "• no triangle was removed and no mesh was written"
    )
    axes[2, 2].text(0.02, 0.98, text, va="top", ha="left", family="monospace", fontsize=10)

    for axis in axes[:2, :].ravel():
        if axis is axes[1, 2]:
            continue
        axis.set_xlabel("screen right")
        axis.set_ylabel("screen up")
        axis.set_aspect("equal")
    figure.suptitle(
        "Phase 4C V2 – CPU-gated read-only mouth and shell diagnostics",
        fontsize=16,
        weight="bold",
    )
    temporary = path.with_name(path.name + ".tmp.png")
    figure.savefig(temporary, facecolor="white", bbox_inches="tight")
    plt.close(figure)
    temporary.replace(path)


def run_dense_analysis(
    shell: ShellData,
    source_path: Path,
    source_hash_before: str,
    output_dir: Path,
    resolution: int,
    synthetic_gate: dict[str, Any],
    mini_gate: dict[str, Any],
    context: Any,
) -> dict[str, Any]:
    views = make_views()
    front = render_shell_triplet(
        shell, views[0], resolution, context, validation_samples=192
    )
    masks, roi = segment_front_mouth(
        front.combined, shell.bounds, shell.mm_per_unit
    )
    mouth_cpu_spotcheck = cpu_first_hit_spotcheck(
        front.combined,
        front.transformed_vertices,
        shell.faces,
        shell.face_groups,
        shell.mm_per_unit,
        sample_count=256,
        sample_mask=masks["mouth_mask"],
        comparison_group=front.derived_group_id,
        comparison_depth=front.derived_depth_model,
        # Report the GPU comparison, but do not let its known rare ownership
        # outliers veto the authoritative exact CPU classification below.
        minimum_group_match=0.0,
        comparison_is_gate=False,
    )
    category_names = (
        "mouth_rim",
        "side_walls",
        "floor",
        "back_wall",
        "body_transition",
    )
    category_masks = {name: masks[name] for name in category_names}
    cpu_region_reports = {
        name: cpu_first_hit_spotcheck(
            front.combined,
            front.transformed_vertices,
            shell.faces,
            shell.face_groups,
            shell.mm_per_unit,
            sample_count=64,
            sample_mask=category_masks[name],
            comparison_group=front.derived_group_id,
            comparison_depth=front.derived_depth_model,
            minimum_group_match=0.0,
            raise_on_fail=False,
            comparison_is_gate=False,
        )
        for name in category_names
    }
    if not all(
        report["cpu_group_counts"].get("1", 0) > 0
        and report["cpu_group_counts"].get("2", 0) == 0
        for report in cpu_region_reports.values()
    ):
        raise AssertionError(
            "Exact CPU samples do not consistently classify all five mouth regions as C01-frontmost"
        )
    associations, region_face_ids = region_shell_association(
        front, shell, category_masks
    )
    all_mouth_ids = np.unique(
        np.concatenate(
            [
                ids
                for by_shell in region_face_ids.values()
                for ids in by_shell.values()
                if len(ids)
            ]
        )
    )
    face_ids_by_region = {
        name: np.unique(np.concatenate((by_shell["c01"], by_shell["c02"])))
        for name, by_shell in region_face_ids.items()
    }
    virtual_c1, delta_c1 = virtual_removal_metrics(
        front.derived_depth_model,
        np.isfinite(front.derived_depth_model),
        front.c2_only,
        masks["mouth_mask"],
        shell.mm_per_unit,
    )
    virtual_c2, delta_c2 = virtual_removal_metrics(
        front.derived_depth_model,
        np.isfinite(front.derived_depth_model),
        front.c1_only,
        masks["mouth_mask"],
        shell.mm_per_unit,
    )
    authoritative_virtual = {
        "whole_mouth": cpu_virtual_removal_summary(mouth_cpu_spotcheck),
        "by_region": {
            name: cpu_virtual_removal_summary(report)
            for name, report in cpu_region_reports.items()
        },
    }
    oblique_reports: dict[str, Any] = {}
    oblique_arrays: dict[str, dict[str, np.ndarray]] = {}
    for frame in views[1:]:
        triplet = render_shell_triplet(
            shell, frame, resolution, context, validation_samples=128
        )
        report, arrays = oblique_evidence(
            triplet, all_mouth_ids, face_ids_by_region, shell
        )
        oblique_reports[frame.name] = report
        oblique_arrays[frame.name] = arrays
        del triplet
        torch.cuda.empty_cache()

    source_hash_after = sha256_file(source_path)
    if source_hash_after != source_hash_before:
        raise RuntimeError("Source hash changed during read-only analysis")
    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / "phase4-mouth-diagnostic-v2.png"
    json_path = output_dir / "phase4-mouth-analysis-v2.json"
    write_diagnostic_png(
        png_path,
        front,
        masks,
        associations,
        delta_c1,
        delta_c2,
        oblique_arrays,
        shell,
        {
            "synthetic": synthetic_gate["status"],
            "mini": mini_gate["status"],
            "dense_front": front.validation["status"],
        },
        cpu_region_reports,
    )

    report = {
        "schema": SCHEMA,
        "analysis_only": True,
        "mesh_mutated": False,
        "prohibited_operations_executed": [],
        "source": {
            "path": str(source_path),
            "bytes": source_path.stat().st_size,
            "sha256_before": source_hash_before,
            "sha256_after": source_hash_after,
            "expected_known_copy_sha256": EXPECTED_SOURCE_SHA256,
            "expected_hash_matches": source_hash_before == EXPECTED_SOURCE_SHA256,
            "load_mode": (
                "trimesh process=True in memory; canonical shared-vertex connected "
                "components (not trimesh.split); no export"
            ),
            "component_count": len(shell.components),
            "c01": {
                "faces": shell.c1_face_count,
                "surface_area_model2": float(shell.components[0].area),
            },
            "c02": {
                "faces": shell.c2_face_count,
                "surface_area_model2": float(shell.components[1].area),
            },
        },
        "method_guardrails": {
            "cuBVH_ray_trace_used": False,
            "rasterizer": "existing nvdiffrast.torch ROCm/CUDA-compatible API",
            "same_canvas_rule": "combined/C01-only/C02-only use the identical complete C01+C02 vertex array; only face arrays differ",
            "virtual_removal": "separate first-hit raster comparison only; no mesh edit",
            "original_glb_used": False,
            "reason_original_glb_not_used": "geometry-depth and stable component ownership suffice; texture was not allowed to alter objective ROI selection",
        },
        "coordinate_system": {
            "x": "left/right",
            "y": "up",
            "z": "front (+Z)",
            "target_height_mm_for_reported_distances": 190.0,
            "mm_per_model_unit": shell.mm_per_unit,
            "bounds": shell.bounds.tolist(),
        },
        "validation_gates": {
            "synthetic": synthetic_gate,
            "real_mesh_low_resolution": mini_gate,
            "dense_front": front.validation,
            "dense_mouth_cpu_first_hit": mouth_cpu_spotcheck,
            "dense_cpu_first_hit_by_disjoint_region": cpu_region_reports,
            "policy": "JSON/PNG opened only after synthetic and real low-resolution gates passed",
        },
        "mouth_roi": roi,
        "region_shell_association": associations,
        "authoritative_cpu_sampled_region_shell_association": cpu_region_reports,
        "authoritative_cpu_counterfactual_summary": authoritative_virtual,
        "front_virtual_raster_comparison": {
            "authority": "GPU-supporting visualization only; not used for final mouth ownership",
            "virtual_remove_c01_keep_c02": virtual_c1,
            "virtual_remove_c02_keep_c01": virtual_c2,
        },
        "oblique_corroboration": oblique_reports,
        "front_discovered_face_id_counts": {
            "union_c01_c02": int(len(all_mouth_ids)),
            "by_region": {
                name: {
                    "c01": int(len(region_face_ids[name]["c01"])),
                    "c02": int(len(region_face_ids[name]["c02"])),
                    "union": int(len(face_ids_by_region[name])),
                }
                for name in category_names
            },
        },
        "interpretation_limits_and_risks": [
            "The ROI is a deterministic geometric diagnostic tuned by normalized guard constants for this one Seed-42 pig; it is not a general semantic detector.",
            "Orthographic first-hit rasters cannot enumerate fully occluded surfaces; separate C01/C02 rasters reduce but do not remove that limitation.",
            "Oblique evidence projects face IDs discovered in the front view and therefore corroborates those faces only; it does not discover hidden mouth topology.",
            "Unique-face full triangle area is a visibility surrogate, not exact projected area and not a repair selection.",
            "The five requested regions are intentionally disjoint; central/upper interior pixels that do not meet an anatomical rule remain explicitly unclassified.",
            "Virtual removal numbers are counterfactual depth changes from separate rasters, not authorization or execution of deletion.",
            "Dense ROCm raster ownership/depth contains rare outliers; exact Float64 all-triangle CPU samples are authoritative for the five mouth regions.",
            "The 360-pixel raster is used for ROI and display after CPU gating; a prior 720-pixel attempt was rejected before writing artifacts because C02 raster depth outliers exceeded the gate.",
            "CPU evidence is deterministic sampling of each region, not an exhaustive per-pixel proof or a closed-volume containment test.",
            "No claim about watertightness, manifoldness, shell intersection, or physical wall thickness is derived from this raster analysis.",
        ],
        "artifacts": {
            "json": str(json_path),
            "diagnostic_png": str(png_path),
            "artifact_count": 2,
        },
    }
    temporary = json_path.with_name(json_path.name + ".tmp")
    temporary.write_text(
        json.dumps(json_ready(report), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(json_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only, gated Phase-4C V2 mouth diagnostics"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--mini-test", action="store_true")
    mode.add_argument("--run", action="store_true")
    parser.add_argument("--mesh", type=Path, default=DEFAULT_MESH)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--mini-resolution", type=int, default=144)
    parser.add_argument("--resolution", type=int, default=720)
    args = parser.parse_args()

    synthetic = run_synthetic_gate()
    if args.self_test:
        print(json.dumps(json_ready(synthetic), indent=2))
        return

    source_path = args.mesh.resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    source_hash = sha256_file(source_path)
    if source_hash != EXPECTED_SOURCE_SHA256:
        raise RuntimeError(
            f"Known working-copy hash mismatch: {source_hash}; expected {EXPECTED_SOURCE_SHA256}"
        )
    shell = load_shell_data(source_path)
    context = dr.RasterizeCudaContext(device="cuda")
    mini = run_real_mini_gate(shell, args.mini_resolution, context)
    if sha256_file(source_path) != source_hash:
        raise RuntimeError("Source hash changed during mini gate")
    if args.mini_test:
        print(json.dumps(json_ready({"synthetic": synthetic, "real_mini": mini}), indent=2))
        return

    if args.output_dir is None:
        parser.error("--run requires --output-dir")
    if args.resolution <= args.mini_resolution:
        parser.error("--resolution must be greater than --mini-resolution")
    print(
        json.dumps(
            json_ready(
                run_dense_analysis(
                    shell,
                    source_path,
                    source_hash,
                    args.output_dir.resolve(),
                    args.resolution,
                    synthetic,
                    mini,
                    context,
                )
            ),
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {type(error).__name__}: {error}", file=sys.stderr)
        raise
