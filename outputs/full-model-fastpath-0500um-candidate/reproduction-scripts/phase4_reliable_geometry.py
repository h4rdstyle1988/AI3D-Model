#!/usr/bin/env python3
"""Reliable read-only geometry diagnostics for AI3D Phase 4.

This module deliberately contains no mesh export, repair, remeshing, Boolean,
or package-management code.  It provides two independent diagnostics:

* an orthographic triangle-ID/depth raster based on the already installed
  nvdiffrast ROCm port, including deterministic CPU barycentric validation;
* a Float64 triangle/triangle intersection test with a SciPy cKDTree bounding-
  sphere broad phase, exact AABB rejection, non-coplanar edge/triangle tests,
  and coplanar convex-polygon clipping.

The cuMesh ``ray_trace`` API is intentionally not used here.  Its point-to-
triangle unsigned-distance API can remain useful elsewhere, but its dense-mesh
ray outputs failed geometric validation on this workstation.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from typing import Any, Iterable, Sequence

import numpy as np
from scipy.spatial import cKDTree
import torch
import nvdiffrast.torch as dr


VIEW_BASES: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {
    # screen-right, screen-up, direction from object towards camera
    "+z": (
        np.array([1.0, 0.0, 0.0]),
        np.array([0.0, 1.0, 0.0]),
        np.array([0.0, 0.0, 1.0]),
    ),
    "-z": (
        np.array([-1.0, 0.0, 0.0]),
        np.array([0.0, 1.0, 0.0]),
        np.array([0.0, 0.0, -1.0]),
    ),
    "+x": (
        np.array([0.0, 0.0, -1.0]),
        np.array([0.0, 1.0, 0.0]),
        np.array([1.0, 0.0, 0.0]),
    ),
    "-x": (
        np.array([0.0, 0.0, 1.0]),
        np.array([0.0, 1.0, 0.0]),
        np.array([-1.0, 0.0, 0.0]),
    ),
    "+y": (
        np.array([1.0, 0.0, 0.0]),
        np.array([0.0, 0.0, 1.0]),
        np.array([0.0, 1.0, 0.0]),
    ),
    "-y": (
        np.array([1.0, 0.0, 0.0]),
        np.array([0.0, 0.0, -1.0]),
        np.array([0.0, -1.0, 0.0]),
    ),
}


def _as_vertices(value: Any) -> np.ndarray:
    result = np.asarray(value, dtype=np.float64)
    if result.ndim != 2 or result.shape[1] != 3:
        raise ValueError(f"vertices must have shape [N,3], got {result.shape}")
    if not np.isfinite(result).all():
        raise ValueError("vertices contain non-finite coordinates")
    return np.ascontiguousarray(result)


def _as_faces(value: Any, vertex_count: int) -> np.ndarray:
    result = np.asarray(value, dtype=np.int64)
    if result.ndim != 2 or result.shape[1] != 3:
        raise ValueError(f"faces must have shape [F,3], got {result.shape}")
    if len(result) and (result.min() < 0 or result.max() >= vertex_count):
        raise ValueError("faces contain out-of-range vertex indices")
    return np.ascontiguousarray(result)


def _resolution_pair(resolution: int | Sequence[int]) -> tuple[int, int]:
    if isinstance(resolution, (int, np.integer)):
        height = width = int(resolution)
    else:
        if len(resolution) != 2:
            raise ValueError("resolution must be an int or [height,width]")
        height, width = int(resolution[0]), int(resolution[1])
    if height < 2 or width < 2:
        raise ValueError("raster resolution must be at least 2x2")
    return height, width


def _barycentric_2d(point: np.ndarray, triangle: np.ndarray) -> np.ndarray:
    """Independent Float64 barycentrics for one 2D triangle."""
    a, b, c = np.asarray(triangle, dtype=np.float64)
    matrix = np.column_stack((a - c, b - c))
    determinant = float(np.linalg.det(matrix))
    scale = max(float(np.linalg.norm(matrix, ord=np.inf)), 1.0)
    if abs(determinant) <= np.finfo(np.float64).eps * scale * scale * 32.0:
        return np.full(3, np.nan, dtype=np.float64)
    first, second = np.linalg.solve(matrix, np.asarray(point, dtype=np.float64) - c)
    return np.array([first, second, 1.0 - first - second], dtype=np.float64)


@dataclass
class OrthographicRaster:
    """In-memory orthographic raster; no image or mesh is written."""

    triangle_id: np.ndarray
    depth_model: np.ndarray
    barycentric: np.ndarray
    model_position: np.ndarray
    group_id: np.ndarray | None
    metadata: dict[str, Any]


def orthographic_id_depth_raster(
    vertices: Any,
    faces: Any,
    *,
    view: str = "+z",
    resolution: int | Sequence[int] = 720,
    padding: float = 0.04,
    face_groups: Any | None = None,
    context: Any | None = None,
    validation_samples: int = 64,
) -> OrthographicRaster:
    """Rasterize stable input-triangle IDs and frontmost model-space depth.

    ``view`` denotes the camera side, e.g. ``+z`` means a camera on the
    positive Z side looking towards negative Z.  nvdiffrast selects the
    smallest clip-space Z, so the model coordinate along the camera direction
    is negated when constructing clip coordinates.

    Returned barycentrics follow input-face vertex order and are
    ``[rast.u, rast.v, 1-rast.u-rast.v]``.  Background triangle/group IDs are
    ``-1`` and background depth/positions are NaN.
    """
    if view not in VIEW_BASES:
        raise ValueError(f"view must be one of {sorted(VIEW_BASES)}, got {view!r}")
    if not (0.0 <= float(padding) < 0.45):
        raise ValueError("padding must be in [0,0.45)")
    height, width = _resolution_pair(resolution)
    points = _as_vertices(vertices)
    triangles = _as_faces(faces, len(points))
    if not len(triangles):
        raise ValueError("at least one triangle is required")

    groups: np.ndarray | None = None
    if face_groups is not None:
        groups = np.asarray(face_groups, dtype=np.int64).reshape(-1)
        if len(groups) != len(triangles):
            raise ValueError("face_groups must have one value per triangle")

    screen_right, screen_up, camera_axis = VIEW_BASES[view]
    screen_u = points @ screen_right
    screen_v = points @ screen_up
    camera_depth = points @ camera_axis
    u_min, u_max = float(screen_u.min()), float(screen_u.max())
    v_min, v_max = float(screen_v.min()), float(screen_v.max())
    d_min, d_max = float(camera_depth.min()), float(camera_depth.max())
    u_span = u_max - u_min
    v_span = v_max - v_min
    screen_span = max(u_span, v_span)
    depth_span = d_max - d_min
    if screen_span <= 0.0:
        raise ValueError("orthographic raster needs non-zero screen extent")
    # Preserve model-space aspect ratio even for a non-square output raster.
    positive_fits = []
    if u_span > 0.0:
        positive_fits.append(float(width) / u_span)
    if v_span > 0.0:
        positive_fits.append(float(height) / v_span)
    pixels_per_model_unit = (1.0 - float(padding)) * min(positive_fits)
    scale_u = 2.0 * pixels_per_model_unit / float(width)
    scale_v = 2.0 * pixels_per_model_unit / float(height)
    u_center = 0.5 * (u_min + u_max)
    v_center = 0.5 * (v_min + v_max)
    d_center = 0.5 * (d_min + d_max)
    clip_depth = (
        -2.0
        * (camera_depth - d_center)
        / depth_span
        * (1.0 - float(padding))
        if depth_span > 0.0
        else np.zeros(len(points), dtype=np.float64)
    )
    clip = np.column_stack(
        (
            (screen_u - u_center) * scale_u,
            (screen_v - v_center) * scale_v,
            clip_depth,
            np.ones(len(points), dtype=np.float64),
        )
    ).astype(np.float32)

    if context is None:
        context = dr.RasterizeCudaContext(device="cuda")
    clip_tensor = torch.from_numpy(clip[None]).to(device="cuda", dtype=torch.float32)
    face_tensor = torch.from_numpy(triangles.astype(np.int32, copy=False)).to(
        device="cuda", dtype=torch.int32
    )
    with torch.inference_mode():
        raster, _ = dr.rasterize(
            context, clip_tensor, face_tensor, resolution=[height, width]
        )
    raw = raster[0].detach().cpu().numpy().astype(np.float64, copy=False)
    triangle_id = np.rint(raw[..., 3]).astype(np.int64) - 1
    valid = (triangle_id >= 0) & (triangle_id < len(triangles))
    triangle_id[~valid] = -1

    barycentric = np.full((height, width, 3), np.nan, dtype=np.float64)
    barycentric[..., 0][valid] = raw[..., 0][valid]
    barycentric[..., 1][valid] = raw[..., 1][valid]
    barycentric[..., 2][valid] = 1.0 - raw[..., 0][valid] - raw[..., 1][valid]
    depth_model = np.full((height, width), np.nan, dtype=np.float64)
    if depth_span > 0.0:
        depth_model[valid] = (
            d_center
            - raw[..., 2][valid]
            * depth_span
            / (2.0 * (1.0 - float(padding)))
        )
    else:
        depth_model[valid] = d_center

    # Pixel position and depth are projection primitives and must not depend
    # on the dense-mesh barycentrics.  The ROCm rasterizer can quantize the
    # latter noticeably for sub-pixel triangles even while its ID/depth
    # buffer is stable.  Reconstruct the orthographic model-space ray sample
    # directly from the pixel centre and raw clip-Z instead.
    columns_ndc = 2.0 * (np.arange(width, dtype=np.float64) + 0.5) / width - 1.0
    rows_ndc = 2.0 * (np.arange(height, dtype=np.float64) + 0.5) / height - 1.0
    screen_u_grid = u_center + columns_ndc[None, :] / scale_u
    screen_v_grid = v_center + rows_ndc[:, None] / scale_v
    model_position = np.full((height, width, 3), np.nan, dtype=np.float64)
    if np.any(valid):
        model_position[valid] = (
            screen_u_grid.repeat(height, axis=0)[valid, None] * screen_right[None]
            + screen_v_grid.repeat(width, axis=1)[valid, None] * screen_up[None]
            + depth_model[valid, None] * camera_axis[None]
        )
    group_id = None
    if groups is not None:
        group_id = np.full((height, width), -1, dtype=np.int64)
        group_id[valid] = groups[triangle_id[valid]]

    valid_pixels = np.argwhere(valid)
    requested = max(0, int(validation_samples))
    chosen = (
        valid_pixels[
            np.linspace(0, len(valid_pixels) - 1, min(requested, len(valid_pixels)), dtype=np.int64)
        ]
        if requested and len(valid_pixels)
        else np.empty((0, 2), dtype=np.int64)
    )
    cpu_bary_errors: list[float] = []
    gpu_bary_errors: list[float] = []
    depth_errors: list[float] = []
    pixel_errors: list[float] = []
    bary_minimum = math.inf
    for row, column in chosen:
        face_id = int(triangle_id[row, column])
        face_clip = clip[triangles[face_id], :3].astype(np.float64)
        pixel_ndc = np.array(
            [
                2.0 * (float(column) + 0.5) / float(width) - 1.0,
                2.0 * (float(row) + 0.5) / float(height) - 1.0,
            ]
        )
        cpu_bary = _barycentric_2d(pixel_ndc, face_clip[:, :2])
        gpu_bary = barycentric[row, column]
        cpu_bary_errors.append(float(np.max(np.abs(cpu_bary - gpu_bary))))
        reconstructed_clip = gpu_bary @ face_clip
        pixel_errors.append(float(np.linalg.norm(reconstructed_clip[:2] - pixel_ndc)))
        depth_errors.append(float(abs(reconstructed_clip[2] - raw[row, column, 2])))
        gpu_bary_errors.append(float(abs(gpu_bary.sum() - 1.0)))
        bary_minimum = min(bary_minimum, float(gpu_bary.min()))

    validation = {
        "sample_count": int(len(chosen)),
        "valid_triangle_ids": bool(
            np.all((triangle_id[valid] >= 0) & (triangle_id[valid] < len(triangles)))
        ),
        "cpu_vs_gpu_barycentric_max_abs_error": (
            max(cpu_bary_errors) if cpu_bary_errors else None
        ),
        "pixel_center_ndc_max_error": max(pixel_errors) if pixel_errors else None,
        "clip_depth_max_abs_error": max(depth_errors) if depth_errors else None,
        "barycentric_sum_max_abs_error": max(gpu_bary_errors) if gpu_bary_errors else None,
        "barycentric_minimum": bary_minimum if math.isfinite(bary_minimum) else None,
    }
    metadata = {
        "view": view,
        "resolution_height_width": [height, width],
        "triangles": int(len(triangles)),
        "hit_pixels": int(np.count_nonzero(valid)),
        "background_pixels": int(np.count_nonzero(~valid)),
        "depth_selection": "smaller clip-z wins; clip-z is negative camera-axis depth",
        "model_position_source": "pixel-center inverse orthographic projection plus raw clip-z; not barycentric reconstruction",
        "screen_right": screen_right.tolist(),
        "screen_up": screen_up.tolist(),
        "camera_axis": camera_axis.tolist(),
        "pixels_per_model_unit": pixels_per_model_unit,
        "screen_u_center": u_center,
        "screen_v_center": v_center,
        "screen_scale_u_ndc_per_model_unit": scale_u,
        "screen_scale_v_ndc_per_model_unit": scale_v,
        "model_depth_min_max": [d_min, d_max],
        "validation": validation,
    }
    return OrthographicRaster(
        triangle_id=triangle_id,
        depth_model=depth_model,
        barycentric=barycentric,
        model_position=model_position,
        group_id=group_id,
        metadata=metadata,
    )


def _triangle_geometry(triangles: np.ndarray) -> dict[str, np.ndarray]:
    minimum = triangles.min(axis=1)
    maximum = triangles.max(axis=1)
    centers = triangles.mean(axis=1)
    radii = np.linalg.norm(triangles - centers[:, None, :], axis=2).max(axis=1)
    raw_normals = np.cross(
        triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
    )
    normal_lengths = np.linalg.norm(raw_normals, axis=1)
    normals = np.zeros_like(raw_normals)
    valid = normal_lengths > 0.0
    normals[valid] = raw_normals[valid] / normal_lengths[valid, None]
    return {
        "minimum": minimum,
        "maximum": maximum,
        "centers": centers,
        "radii": radii,
        "normals": normals,
        "normal_lengths": normal_lengths,
    }


@dataclass
class _RadiusBucket:
    indices: np.ndarray
    tree: cKDTree
    maximum_radius: float


def _radius_buckets(
    centers: np.ndarray, radii: np.ndarray, count: int
) -> list[_RadiusBucket]:
    order = np.argsort(radii, kind="mergesort")
    pieces = [piece for piece in np.array_split(order, max(1, int(count))) if len(piece)]
    return [
        _RadiusBucket(
            indices=piece,
            tree=cKDTree(centers[piece]),
            maximum_radius=float(radii[piece].max(initial=0.0)),
        )
        for piece in pieces
    ]


def _edge_triangle_hits(
    starts: np.ndarray,
    ends: np.ndarray,
    target: np.ndarray,
    target_normals: np.ndarray,
    tolerance: float,
    barycentric_tolerance: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorized Float64 segment/triangle plane-and-barycentric test."""
    signed_start = np.einsum("ij,ij->i", starts - target[:, 0], target_normals)
    signed_end = np.einsum("ij,ij->i", ends - target[:, 0], target_normals)
    denominator = signed_start - signed_end
    crosses_plane = (
        (np.minimum(signed_start, signed_end) <= tolerance)
        & (np.maximum(signed_start, signed_end) >= -tolerance)
        & (np.abs(denominator) > tolerance * 0.25)
    )
    parameter = np.full(len(starts), np.nan, dtype=np.float64)
    parameter[crosses_plane] = (
        signed_start[crosses_plane] / denominator[crosses_plane]
    )
    parameter_ok = crosses_plane & (parameter >= -barycentric_tolerance) & (
        parameter <= 1.0 + barycentric_tolerance
    )
    points = starts + np.nan_to_num(parameter)[:, None] * (ends - starts)

    edge0 = target[:, 1] - target[:, 0]
    edge1 = target[:, 2] - target[:, 0]
    relative = points - target[:, 0]
    dot00 = np.einsum("ij,ij->i", edge0, edge0)
    dot01 = np.einsum("ij,ij->i", edge0, edge1)
    dot11 = np.einsum("ij,ij->i", edge1, edge1)
    dot20 = np.einsum("ij,ij->i", relative, edge0)
    dot21 = np.einsum("ij,ij->i", relative, edge1)
    bary_denominator = dot00 * dot11 - dot01 * dot01
    bary_valid = np.abs(bary_denominator) > np.finfo(np.float64).tiny
    bary1 = np.full(len(starts), np.nan, dtype=np.float64)
    bary2 = np.full(len(starts), np.nan, dtype=np.float64)
    active = parameter_ok & bary_valid
    bary1[active] = (
        dot11[active] * dot20[active] - dot01[active] * dot21[active]
    ) / bary_denominator[active]
    bary2[active] = (
        dot00[active] * dot21[active] - dot01[active] * dot20[active]
    ) / bary_denominator[active]
    bary0 = 1.0 - bary1 - bary2
    inside = (
        active
        & (bary0 >= -barycentric_tolerance)
        & (bary1 >= -barycentric_tolerance)
        & (bary2 >= -barycentric_tolerance)
    )
    strict = (
        inside
        & (parameter > barycentric_tolerance)
        & (parameter < 1.0 - barycentric_tolerance)
        & (bary0 > barycentric_tolerance)
        & (bary1 > barycentric_tolerance)
        & (bary2 > barycentric_tolerance)
        & (np.abs(signed_start) > tolerance)
        & (np.abs(signed_end) > tolerance)
    )
    return inside, points, strict


def _point_triangle_barycentric_3d(
    point: np.ndarray, triangle: np.ndarray
) -> np.ndarray:
    """Float64 barycentrics for a point already known to lie on the plane."""
    edge0 = triangle[1] - triangle[0]
    edge1 = triangle[2] - triangle[0]
    relative = point - triangle[0]
    dot00 = float(np.dot(edge0, edge0))
    dot01 = float(np.dot(edge0, edge1))
    dot11 = float(np.dot(edge1, edge1))
    dot20 = float(np.dot(relative, edge0))
    dot21 = float(np.dot(relative, edge1))
    denominator = dot00 * dot11 - dot01 * dot01
    if abs(denominator) <= np.finfo(np.float64).tiny:
        return np.full(3, np.nan, dtype=np.float64)
    second = (dot11 * dot20 - dot01 * dot21) / denominator
    third = (dot00 * dot21 - dot01 * dot20) / denominator
    return np.array([1.0 - second - third, second, third], dtype=np.float64)


def _signed_polygon_area(polygon: np.ndarray) -> float:
    if len(polygon) < 3:
        return 0.0
    return 0.5 * float(
        np.sum(
            polygon[:, 0] * np.roll(polygon[:, 1], -1)
            - polygon[:, 1] * np.roll(polygon[:, 0], -1)
        )
    )


def _cross2(left: np.ndarray, right: np.ndarray) -> float:
    return float(left[0] * right[1] - left[1] * right[0])


def _clip_convex_polygon(
    subject: np.ndarray, clip: np.ndarray, tolerance: float
) -> np.ndarray:
    """Sutherland-Hodgman clipping for two convex 2D polygons."""
    output = np.asarray(subject, dtype=np.float64)
    clip_polygon = np.asarray(clip, dtype=np.float64)
    if _signed_polygon_area(clip_polygon) < 0.0:
        clip_polygon = clip_polygon[::-1]

    def inside(point: np.ndarray, a: np.ndarray, b: np.ndarray) -> bool:
        edge = b - a
        # Cross-product magnitude is distance times edge length.  Scaling the
        # tolerance here keeps the caller's tolerance in model-space units.
        return _cross2(edge, point - a) >= -tolerance * max(
            float(np.linalg.norm(edge)), np.finfo(np.float64).tiny
        )

    def intersection(
        first: np.ndarray,
        second: np.ndarray,
        clip_a: np.ndarray,
        clip_b: np.ndarray,
    ) -> np.ndarray:
        direction = second - first
        clip_direction = clip_b - clip_a
        denominator = _cross2(direction, clip_direction)
        if abs(denominator) <= np.finfo(np.float64).eps:
            return 0.5 * (first + second)
        parameter = _cross2(clip_a - first, clip_direction) / denominator
        return first + parameter * direction

    for clip_a, clip_b in zip(clip_polygon, np.roll(clip_polygon, -1, axis=0)):
        if not len(output):
            break
        input_polygon = output
        output_points: list[np.ndarray] = []
        previous = input_polygon[-1]
        previous_inside = inside(previous, clip_a, clip_b)
        for current in input_polygon:
            current_inside = inside(current, clip_a, clip_b)
            if current_inside:
                if not previous_inside:
                    output_points.append(
                        intersection(previous, current, clip_a, clip_b)
                    )
                output_points.append(current)
            elif previous_inside:
                output_points.append(intersection(previous, current, clip_a, clip_b))
            previous = current
            previous_inside = current_inside
        output = (
            np.asarray(output_points, dtype=np.float64).reshape((-1, 2))
            if output_points
            else np.empty((0, 2), dtype=np.float64)
        )
    return output


def _lift_from_projection(
    points_2d: np.ndarray,
    drop_axis: int,
    plane_point: np.ndarray,
    plane_normal: np.ndarray,
) -> np.ndarray:
    keep = [axis for axis in range(3) if axis != drop_axis]
    result = np.zeros((len(points_2d), 3), dtype=np.float64)
    result[:, keep] = points_2d
    normal_component = float(plane_normal[drop_axis])
    if abs(normal_component) <= np.finfo(np.float64).eps:
        result[:, drop_axis] = plane_point[drop_axis]
    else:
        other = (
            plane_normal[keep[0]] * (result[:, keep[0]] - plane_point[keep[0]])
            + plane_normal[keep[1]] * (result[:, keep[1]] - plane_point[keep[1]])
        )
        result[:, drop_axis] = plane_point[drop_axis] - other / normal_component
    return result


def _coplanar_pair(
    first: np.ndarray,
    second: np.ndarray,
    normal: np.ndarray,
    tolerance: float,
) -> tuple[str | None, np.ndarray]:
    drop_axis = int(np.argmax(np.abs(normal)))
    keep = [axis for axis in range(3) if axis != drop_axis]
    first_2d = first[:, keep]
    second_2d = second[:, keep]
    polygon = _clip_convex_polygon(first_2d, second_2d, tolerance)
    if not len(polygon):
        return None, np.empty((0, 3), dtype=np.float64)
    # Remove adjacent duplicates introduced by clipping on a shared boundary.
    unique: list[np.ndarray] = []
    for point in polygon:
        if not unique or np.linalg.norm(point - unique[-1]) > tolerance:
            unique.append(point)
    if len(unique) > 1 and np.linalg.norm(unique[0] - unique[-1]) <= tolerance:
        unique.pop()
    polygon = np.asarray(unique, dtype=np.float64).reshape((-1, 2))
    lifted = _lift_from_projection(polygon, drop_axis, first[0], normal)
    area = abs(_signed_polygon_area(polygon))
    area_tolerance = tolerance * tolerance * 4.0
    if len(polygon) >= 3 and area > area_tolerance:
        return "overlap", lifted
    return "touch", lifted


def _narrow_phase(
    first: np.ndarray,
    second: np.ndarray,
    tolerance: float,
    barycentric_tolerance: float,
) -> tuple[np.ndarray, list[np.ndarray]]:
    """Classify candidate pairs: 0 disjoint, 1 proper, 2 touch, 3 overlap."""
    count = len(first)
    classes = np.zeros(count, dtype=np.uint8)
    representative: list[np.ndarray] = [np.empty((0, 3), dtype=np.float64) for _ in range(count)]
    if not count:
        return classes, representative
    raw_first_normal = np.cross(first[:, 1] - first[:, 0], first[:, 2] - first[:, 0])
    raw_second_normal = np.cross(second[:, 1] - second[:, 0], second[:, 2] - second[:, 0])
    first_length = np.linalg.norm(raw_first_normal, axis=1)
    second_length = np.linalg.norm(raw_second_normal, axis=1)
    valid = (first_length > tolerance * tolerance) & (
        second_length > tolerance * tolerance
    )
    first_normal = np.zeros_like(raw_first_normal)
    second_normal = np.zeros_like(raw_second_normal)
    first_normal[valid] = raw_first_normal[valid] / first_length[valid, None]
    second_normal[valid] = raw_second_normal[valid] / second_length[valid, None]
    distance_first_to_second = np.einsum(
        "nij,nj->ni", first - second[:, 0, None, :], second_normal
    )
    distance_second_to_first = np.einsum(
        "nij,nj->ni", second - first[:, 0, None, :], first_normal
    )
    separated = (
        (np.all(distance_first_to_second > tolerance, axis=1))
        | (np.all(distance_first_to_second < -tolerance, axis=1))
        | (np.all(distance_second_to_first > tolerance, axis=1))
        | (np.all(distance_second_to_first < -tolerance, axis=1))
    )
    normal_dot = np.abs(np.einsum("ij,ij->i", first_normal, second_normal))
    coplanar = (
        valid
        & ~separated
        & (normal_dot >= 1.0 - 1.0e-10)
        & (np.max(np.abs(distance_first_to_second), axis=1) <= tolerance)
        & (np.max(np.abs(distance_second_to_first), axis=1) <= tolerance)
    )
    for index in np.flatnonzero(coplanar):
        kind, points = _coplanar_pair(
            first[index], second[index], first_normal[index], tolerance
        )
        if kind == "overlap":
            classes[index] = 3
            representative[index] = points
        elif kind == "touch":
            classes[index] = 2
            representative[index] = points

    active = valid & ~separated & ~coplanar
    active_ids = np.flatnonzero(active)
    if not len(active_ids):
        return classes, representative
    first_active = first[active_ids]
    second_active = second[active_ids]
    first_normals_active = first_normal[active_ids]
    second_normals_active = second_normal[active_ids]
    hit_sets: list[np.ndarray] = []
    point_sets: list[np.ndarray] = []
    strict_sets: list[np.ndarray] = []
    edge_pairs = ((0, 1), (1, 2), (2, 0))
    for start_id, end_id in edge_pairs:
        hit, point, strict = _edge_triangle_hits(
            first_active[:, start_id],
            first_active[:, end_id],
            second_active,
            second_normals_active,
            tolerance,
            barycentric_tolerance,
        )
        hit_sets.append(hit)
        point_sets.append(point)
        strict_sets.append(strict)
    for start_id, end_id in edge_pairs:
        hit, point, strict = _edge_triangle_hits(
            second_active[:, start_id],
            second_active[:, end_id],
            first_active,
            first_normals_active,
            tolerance,
            barycentric_tolerance,
        )
        hit_sets.append(hit)
        point_sets.append(point)
        strict_sets.append(strict)
    hit_matrix = np.column_stack(hit_sets)
    strict_matrix = np.column_stack(strict_sets)
    point_matrix = np.stack(point_sets, axis=1)
    for local_index, global_index in enumerate(active_ids):
        hit_ids = np.flatnonzero(hit_matrix[local_index])
        if not len(hit_ids):
            continue
        points = point_matrix[local_index, hit_ids]
        # Pair-local distance deduplication.  There are at most six candidates,
        # so an explicit deterministic pass is both exact and inexpensive.
        unique_points: list[np.ndarray] = []
        for point in points:
            if not unique_points or all(
                np.linalg.norm(point - previous) > tolerance * 4.0
                for previous in unique_points
            ):
                unique_points.append(point)
        points = np.asarray(unique_points, dtype=np.float64).reshape((-1, 3))

        # A strict edge/triangle hit pierces the relative interiors.  For a
        # positive-length intersection segment, test its midpoint as well;
        # this correctly distinguishes a real crossing from a shared edge or
        # an isolated vertex-to-face tangent.  Plane straddling alone is not
        # sufficient: a triangle can straddle the other plane while touching
        # the finite other triangle at only one boundary point.
        proper = bool(np.any(strict_matrix[local_index]))
        if not proper and len(points) >= 2:
            difference = points[:, None, :] - points[None, :, :]
            squared = np.einsum("ijk,ijk->ij", difference, difference)
            first_id, second_id = np.unravel_index(np.argmax(squared), squared.shape)
            if squared[first_id, second_id] > (tolerance * 4.0) ** 2:
                midpoint = 0.5 * (points[first_id] + points[second_id])
                bary_first = _point_triangle_barycentric_3d(
                    midpoint, first[global_index]
                )
                bary_second = _point_triangle_barycentric_3d(
                    midpoint, second[global_index]
                )
                proper = bool(
                    np.all(bary_first > barycentric_tolerance)
                    and np.all(bary_second > barycentric_tolerance)
                )
        classes[global_index] = 1 if proper else 2
        representative[global_index] = points
    return classes, representative


def _deduplicate_points(points: list[np.ndarray], tolerance: float) -> np.ndarray:
    nonempty = [np.asarray(item, dtype=np.float64).reshape((-1, 3)) for item in points if len(item)]
    if not nonempty:
        return np.empty((0, 3), dtype=np.float64)
    merged = np.vstack(nonempty)
    grid = max(float(tolerance), 1.0e-15)
    keys = np.round(merged / grid).astype(np.int64)
    _, indices = np.unique(keys, axis=0, return_index=True)
    return merged[np.sort(indices)]


@dataclass
class IntersectionResult:
    proper_points: np.ndarray
    touch_points: np.ndarray
    overlap_points: np.ndarray
    proper_pairs: np.ndarray
    touch_pairs: np.ndarray
    overlap_pairs: np.ndarray
    report: dict[str, Any]


def triangle_mesh_intersections(
    vertices_a: Any,
    faces_a: Any,
    vertices_b: Any,
    faces_b: Any,
    *,
    tolerance: float | None = None,
    source_chunk_size: int = 2048,
    narrow_chunk_size: int = 100000,
    radius_bucket_count: int = 12,
    workers: int = -1,
    max_stored_pairs: int = 200000,
) -> IntersectionResult:
    """Find A/B triangle intersections without ray tracing.

    The broad phase is conservative: triangles that intersect must have
    intersecting bounding spheres, and every target radius bucket is queried
    using that bucket's maximum radius before exact sphere and AABB filters.
    Narrow-phase arithmetic is Float64.
    """
    points_a = _as_vertices(vertices_a)
    indices_a = _as_faces(faces_a, len(points_a))
    points_b = _as_vertices(vertices_b)
    indices_b = _as_faces(faces_b, len(points_b))
    triangles_a = points_a[indices_a]
    triangles_b = points_b[indices_b]
    if not len(triangles_a) or not len(triangles_b):
        raise ValueError("both meshes need at least one triangle")
    if int(source_chunk_size) <= 0 or int(narrow_chunk_size) <= 0:
        raise ValueError("source_chunk_size and narrow_chunk_size must be positive")
    if int(radius_bucket_count) <= 0:
        raise ValueError("radius_bucket_count must be positive")
    if int(max_stored_pairs) < 0:
        raise ValueError("max_stored_pairs must be non-negative")
    if int(workers) == 0 or int(workers) < -1:
        raise ValueError("workers must be -1 or a positive integer")
    all_minimum = np.minimum(points_a.min(axis=0), points_b.min(axis=0))
    all_maximum = np.maximum(points_a.max(axis=0), points_b.max(axis=0))
    diagonal = float(np.linalg.norm(all_maximum - all_minimum))
    if tolerance is None:
        tolerance = max(diagonal * 1.0e-7, 1.0e-10)
    tolerance = float(tolerance)
    if not math.isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("tolerance must be finite and positive")
    barycentric_tolerance = max(1.0e-9, tolerance / max(diagonal, 1.0) * 4.0)
    geometry_a = _triangle_geometry(triangles_a)
    geometry_b = _triangle_geometry(triangles_b)
    buckets = _radius_buckets(
        geometry_b["centers"], geometry_b["radii"], radius_bucket_count
    )

    sphere_candidate_count = 0
    aabb_candidate_count = 0
    narrow_tested = 0
    proper_count = 0
    touch_count = 0
    overlap_count = 0
    proper_pairs_parts: list[np.ndarray] = []
    touch_pairs_parts: list[np.ndarray] = []
    overlap_pairs_parts: list[np.ndarray] = []
    proper_point_parts: list[np.ndarray] = []
    touch_point_parts: list[np.ndarray] = []
    overlap_point_parts: list[np.ndarray] = []

    pair_buffer_a: list[np.ndarray] = []
    pair_buffer_b: list[np.ndarray] = []
    buffered = 0

    def store(
        pair_parts: list[np.ndarray],
        point_parts: list[np.ndarray],
        pairs: np.ndarray,
        representatives: list[np.ndarray],
    ) -> None:
        already = sum(len(part) for part in pair_parts)
        remaining = max(0, int(max_stored_pairs) - already)
        if remaining <= 0:
            return
        selected = pairs[:remaining]
        pair_parts.append(selected.copy())
        point_parts.extend(representatives[: len(selected)])

    def process_buffer(force: bool = False) -> None:
        nonlocal buffered, narrow_tested, proper_count, touch_count, overlap_count
        if not buffered or (not force and buffered < int(narrow_chunk_size)):
            return
        source_ids = np.concatenate(pair_buffer_a)
        target_ids = np.concatenate(pair_buffer_b)
        pair_buffer_a.clear()
        pair_buffer_b.clear()
        buffered = 0
        for begin in range(0, len(source_ids), int(narrow_chunk_size)):
            end = min(begin + int(narrow_chunk_size), len(source_ids))
            source_piece = source_ids[begin:end]
            target_piece = target_ids[begin:end]
            classes, representatives = _narrow_phase(
                triangles_a[source_piece],
                triangles_b[target_piece],
                tolerance,
                barycentric_tolerance,
            )
            narrow_tested += len(source_piece)
            pairs = np.column_stack((source_piece, target_piece))
            for code, pair_parts, point_parts in (
                (1, proper_pairs_parts, proper_point_parts),
                (2, touch_pairs_parts, touch_point_parts),
                (3, overlap_pairs_parts, overlap_point_parts),
            ):
                mask = classes == code
                count = int(np.count_nonzero(mask))
                if code == 1:
                    proper_count += count
                elif code == 2:
                    touch_count += count
                else:
                    overlap_count += count
                if count:
                    ids = np.flatnonzero(mask)
                    store(
                        pair_parts,
                        point_parts,
                        pairs[ids],
                        [representatives[index] for index in ids],
                    )

    for source_begin in range(0, len(triangles_a), int(source_chunk_size)):
        source_end = min(source_begin + int(source_chunk_size), len(triangles_a))
        source_local_ids = np.arange(source_begin, source_end, dtype=np.int64)
        source_centers = geometry_a["centers"][source_begin:source_end]
        source_radii = geometry_a["radii"][source_begin:source_end]
        for bucket in buckets:
            query_radii = source_radii + bucket.maximum_radius + tolerance
            neighbors = bucket.tree.query_ball_point(
                source_centers, query_radii, workers=int(workers)
            )
            lengths = np.fromiter((len(item) for item in neighbors), dtype=np.int64)
            if not lengths.sum():
                continue
            local_source = np.repeat(np.arange(len(source_local_ids)), lengths)
            local_target = np.concatenate(neighbors).astype(np.int64, copy=False)
            source_ids = source_local_ids[local_source]
            target_ids = bucket.indices[local_target]
            center_delta = (
                geometry_a["centers"][source_ids] - geometry_b["centers"][target_ids]
            )
            radius_sum = (
                geometry_a["radii"][source_ids]
                + geometry_b["radii"][target_ids]
                + tolerance
            )
            sphere = np.einsum("ij,ij->i", center_delta, center_delta) <= radius_sum * radius_sum
            sphere_candidate_count += int(np.count_nonzero(sphere))
            if not np.any(sphere):
                continue
            source_ids = source_ids[sphere]
            target_ids = target_ids[sphere]
            aabb = np.all(
                geometry_a["minimum"][source_ids]
                <= geometry_b["maximum"][target_ids] + tolerance,
                axis=1,
            ) & np.all(
                geometry_b["minimum"][target_ids]
                <= geometry_a["maximum"][source_ids] + tolerance,
                axis=1,
            )
            aabb_candidate_count += int(np.count_nonzero(aabb))
            if not np.any(aabb):
                continue
            pair_buffer_a.append(source_ids[aabb])
            pair_buffer_b.append(target_ids[aabb])
            buffered += int(np.count_nonzero(aabb))
            process_buffer(force=False)
    process_buffer(force=True)

    def concatenate(parts: list[np.ndarray]) -> np.ndarray:
        return (
            np.vstack(parts).astype(np.int64, copy=False)
            if parts
            else np.empty((0, 2), dtype=np.int64)
        )

    proper_pairs = concatenate(proper_pairs_parts)
    touch_pairs = concatenate(touch_pairs_parts)
    overlap_pairs = concatenate(overlap_pairs_parts)
    proper_points = _deduplicate_points(proper_point_parts, tolerance * 4.0)
    touch_points = _deduplicate_points(touch_point_parts, tolerance * 4.0)
    overlap_points = _deduplicate_points(overlap_point_parts, tolerance * 4.0)
    report = {
        "algorithm": (
            "Float64 cKDTree radius-bucket bounding spheres -> exact sphere -> "
            "AABB -> plane/segment-triangle and coplanar 2D convex clipping"
        ),
        "ray_tracing_used": False,
        "triangles_a": int(len(triangles_a)),
        "triangles_b": int(len(triangles_b)),
        "tolerance": tolerance,
        "barycentric_tolerance": barycentric_tolerance,
        "source_chunk_size": int(source_chunk_size),
        "narrow_chunk_size": int(narrow_chunk_size),
        "radius_bucket_count": int(len(buckets)),
        "sphere_candidates": int(sphere_candidate_count),
        "aabb_candidates": int(aabb_candidate_count),
        "narrow_pairs_tested": int(narrow_tested),
        "degenerate_triangles_a": int(
            np.count_nonzero(geometry_a["normal_lengths"] <= tolerance * tolerance)
        ),
        "degenerate_triangles_b": int(
            np.count_nonzero(geometry_b["normal_lengths"] <= tolerance * tolerance)
        ),
        "classification_scope": (
            "non-degenerate triangles; degenerate faces are reported and do not "
            "produce an intersection class"
        ),
        "proper_intersection_pairs": int(proper_count),
        "touch_pairs": int(touch_count),
        "coplanar_overlap_pairs": int(overlap_count),
        "stored_pair_limit_per_class": int(max_stored_pairs),
        "stored_proper_pairs": int(len(proper_pairs)),
        "stored_touch_pairs": int(len(touch_pairs)),
        "stored_overlap_pairs": int(len(overlap_pairs)),
        "unique_proper_points": int(len(proper_points)),
        "unique_touch_points": int(len(touch_points)),
        "unique_overlap_points": int(len(overlap_points)),
        "representative_points_are": (
            "distance-deduplicated intersection representatives derived from "
            "stored triangle pairs; pair counts include all tested pairs"
        ),
        "proper_pairs_truncated": bool(proper_count > len(proper_pairs)),
        "touch_pairs_truncated": bool(touch_count > len(touch_pairs)),
        "overlap_pairs_truncated": bool(overlap_count > len(overlap_pairs)),
    }
    return IntersectionResult(
        proper_points=proper_points,
        touch_points=touch_points,
        overlap_points=overlap_points,
        proper_pairs=proper_pairs,
        touch_pairs=touch_pairs,
        overlap_pairs=overlap_pairs,
        report=report,
    )


def _raster_self_test() -> dict[str, Any]:
    xy = np.array([[-0.75, -0.65], [0.80, -0.60], [0.05, 0.80]], dtype=np.float64)
    faces = np.array([[0, 1, 2], [3, 4, 5]], dtype=np.int64)
    context = dr.RasterizeCudaContext(device="cuda")
    view_results: dict[str, Any] = {}
    for view, (screen_right, screen_up, camera_axis) in VIEW_BASES.items():
        near = (
            xy[:, 0, None] * screen_right
            + xy[:, 1, None] * screen_up
            + 0.40 * camera_axis
        )
        far = (
            xy[:, 0, None] * screen_right
            + xy[:, 1, None] * screen_up
            - 0.30 * camera_axis
        )
        vertices = np.vstack((near, far))
        result = orthographic_id_depth_raster(
            vertices,
            faces,
            view=view,
            resolution=64,
            padding=0.08,
            face_groups=np.array([10, 20]),
            context=context,
            validation_samples=32,
        )
        hit = result.triangle_id >= 0
        selected = np.unique(result.triangle_id[hit])
        if selected.tolist() != [0]:
            raise AssertionError(
                f"frontmost selection failed for {view}: {selected.tolist()}"
            )
        validation = result.metadata["validation"]
        if validation["cpu_vs_gpu_barycentric_max_abs_error"] > 1.0e-5:
            raise AssertionError(f"barycentric validation failed for {view}: {validation}")
        if validation["pixel_center_ndc_max_error"] > 1.0e-5:
            raise AssertionError(f"pixel reconstruction failed for {view}: {validation}")
        if not np.allclose(result.depth_model[hit], 0.40, atol=1.0e-6):
            raise AssertionError(f"model-space depth failed for {view}")
        view_results[view] = {
            "hit_pixels": int(np.count_nonzero(hit)),
            "selected_input_triangle_ids": selected.tolist(),
            "selected_group_ids": np.unique(result.group_id[hit]).tolist(),
            "model_depth_unique": np.unique(
                np.round(result.depth_model[hit], 7)
            ).tolist(),
            "validation": validation,
        }
    planar = orthographic_id_depth_raster(
        np.column_stack((xy, np.full(3, 0.40))),
        np.array([[0, 1, 2]], dtype=np.int64),
        view="+z",
        resolution=[48, 96],
        padding=0.08,
        context=context,
        validation_samples=16,
    )
    planar_hit = planar.triangle_id >= 0
    if not np.any(planar_hit) or not np.allclose(
        planar.depth_model[planar_hit], 0.40, atol=1.0e-6
    ):
        raise AssertionError("zero-depth-span planar raster failed")
    return {
        "status": "PASS",
        "views": view_results,
        "non_square_planar_zero_depth_span": {
            "status": "PASS",
            "hit_pixels": int(np.count_nonzero(planar_hit)),
            "validation": planar.metadata["validation"],
        },
    }


def _intersection_self_test() -> dict[str, Any]:
    base = np.array(
        [[-1.0, -1.0, 0.0], [1.0, -1.0, 0.0], [0.0, 1.0, 0.0]],
        dtype=np.float64,
    )
    cases = {
        "separated": np.array(
            [[-0.6, -0.5, 0.5], [0.6, -0.5, 0.5], [0.0, 0.6, 0.5]],
            dtype=np.float64,
        ),
        "proper": np.array(
            [[0.0, -0.6, -0.7], [0.0, -0.6, 0.7], [0.0, 0.7, 0.0]],
            dtype=np.float64,
        ),
        "touch": np.array(
            [[0.0, 0.0, 0.0], [-0.25, -0.1, 0.6], [0.25, -0.1, 0.6]],
            dtype=np.float64,
        ),
        "coplanar_overlap": np.array(
            [[-0.4, -0.3, 0.0], [0.7, -0.3, 0.0], [0.1, 0.7, 0.0]],
            dtype=np.float64,
        ),
        "coplanar_edge_touch": np.array(
            [[-1.0, -1.0, 0.0], [1.0, -1.0, 0.0], [0.0, -2.0, 0.0]],
            dtype=np.float64,
        ),
    }
    expected = {
        "separated": (0, 0, 0),
        "proper": (1, 0, 0),
        "touch": (0, 1, 0),
        "coplanar_overlap": (0, 0, 1),
        "coplanar_edge_touch": (0, 1, 0),
    }
    outputs: dict[str, Any] = {}
    face = np.array([[0, 1, 2]], dtype=np.int64)
    for name, other in cases.items():
        result = triangle_mesh_intersections(
            base,
            face,
            other,
            face,
            tolerance=1.0e-9,
            source_chunk_size=1,
            narrow_chunk_size=8,
            radius_bucket_count=1,
        )
        observed = (
            result.report["proper_intersection_pairs"],
            result.report["touch_pairs"],
            result.report["coplanar_overlap_pairs"],
        )
        if observed != expected[name]:
            raise AssertionError(
                f"intersection case {name} expected {expected[name]}, got {observed}"
            )
        reverse = triangle_mesh_intersections(
            other,
            face,
            base,
            face,
            tolerance=1.0e-9,
            source_chunk_size=1,
            narrow_chunk_size=8,
            radius_bucket_count=1,
        )
        reverse_observed = (
            reverse.report["proper_intersection_pairs"],
            reverse.report["touch_pairs"],
            reverse.report["coplanar_overlap_pairs"],
        )
        if reverse_observed != observed:
            raise AssertionError(
                f"intersection symmetry failed for {name}: "
                f"forward={observed}, reverse={reverse_observed}"
            )
        outputs[name] = {
            "proper_touch_overlap_pairs": list(observed),
            "proper_points": int(len(result.proper_points)),
            "touch_points": int(len(result.touch_points)),
            "overlap_points": int(len(result.overlap_points)),
            "broad_phase_aabb_candidates": result.report["aabb_candidates"],
            "reverse_order_same_classification": True,
        }

    # Exercise all chunk boundaries and stored global face IDs with several
    # mutually distant, independently intersecting pairs.
    batch_size = 7
    translations = np.column_stack(
        (np.arange(batch_size, dtype=np.float64) * 5.0, np.zeros(batch_size), np.zeros(batch_size))
    )
    proper_other = cases["proper"]
    batch_a = np.vstack([base + translation for translation in translations])
    batch_b = np.vstack([proper_other + translation for translation in translations])
    batch_faces = np.arange(batch_size * 3, dtype=np.int64).reshape((-1, 3))
    batch = triangle_mesh_intersections(
        batch_a,
        batch_faces,
        batch_b,
        batch_faces,
        tolerance=1.0e-9,
        source_chunk_size=2,
        narrow_chunk_size=3,
        radius_bucket_count=3,
    )
    batch_observed = (
        batch.report["proper_intersection_pairs"],
        batch.report["touch_pairs"],
        batch.report["coplanar_overlap_pairs"],
    )
    expected_pairs = np.column_stack(
        (np.arange(batch_size, dtype=np.int64), np.arange(batch_size, dtype=np.int64))
    )
    if batch_observed != (batch_size, 0, 0) or not np.array_equal(
        batch.proper_pairs, expected_pairs
    ):
        raise AssertionError(
            f"chunked batch expected {(batch_size, 0, 0)} and diagonal IDs; "
            f"got {batch_observed}, pairs={batch.proper_pairs.tolist()}"
        )
    return {
        "status": "PASS",
        "cases": outputs,
        "chunked_batch": {
            "status": "PASS",
            "triangles_per_mesh": batch_size,
            "source_chunk_size": 2,
            "narrow_chunk_size": 3,
            "radius_buckets": 3,
            "proper_touch_overlap_pairs": list(batch_observed),
            "stored_pairs_are_expected_diagonal_ids": True,
        },
    }


def run_self_tests() -> dict[str, Any]:
    return {
        "schema": "ai3d.phase4.reliable-geometry-selftest.v1",
        "torch": torch.__version__,
        "hip": torch.version.hip,
        "gpu": torch.cuda.get_device_name(0),
        "raster": _raster_self_test(),
        "triangle_intersections": _intersection_self_test(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only Phase-4 raster/intersection diagnostics"
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run synthetic in-memory tests; no files are written",
    )
    args = parser.parse_args()
    if not args.self_test:
        parser.error("No implicit mesh operation is provided; use --self-test or import the APIs")
    print(json.dumps(run_self_tests(), indent=2))


if __name__ == "__main__":
    main()
