#!/usr/bin/env python3
"""Read-only topology and REF-SEAM inspection of the untouched R07 Seed-42 PLY."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
SOURCE = OUT / "source-r07" / "herbst-igel-r02-trellis-raw-seed-42.ply"
SEAM_IMAGE = OUT / "reference-audit" / "ref-seam-r08.jpg"
REPORT = OUT / "reports" / "seed42-precleanup-inspection-r08.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def read_binary_ply(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with path.open("rb") as stream:
        header: list[str] = []
        while True:
            line = stream.readline()
            if not line:
                raise ValueError("PLY header ended before end_header")
            decoded = line.decode("ascii").strip()
            header.append(decoded)
            if decoded == "end_header":
                break
        if "format binary_little_endian 1.0" not in header:
            raise ValueError("Only binary little-endian PLY is supported")
        vertex_count = int(next(x.split()[2] for x in header if x.startswith("element vertex ")))
        face_count = int(next(x.split()[2] for x in header if x.startswith("element face ")))
        vertices = np.fromfile(stream, dtype="<f4", count=vertex_count * 3).reshape(-1, 3)
        record_dtype = np.dtype([("count", "u1"), ("indices", "<i4", (3,))])
        records = np.fromfile(stream, dtype=record_dtype, count=face_count)
    if not np.all(records["count"] == 3):
        raise ValueError("Non-triangular face found")
    return vertices.astype(np.float64), records["indices"].astype(np.int64)


def connected_labels(vertex_count: int, faces: np.ndarray) -> tuple[np.ndarray, list[int]]:
    parent = np.arange(vertex_count, dtype=np.int64)
    rank = np.zeros(vertex_count, dtype=np.uint8)

    def find(value: int) -> int:
        root = value
        while parent[root] != root:
            root = int(parent[root])
        while parent[value] != value:
            next_value = int(parent[value])
            parent[value] = root
            value = next_value
        return root

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if rank[ra] < rank[rb]:
            ra, rb = rb, ra
        parent[rb] = ra
        if rank[ra] == rank[rb]:
            rank[ra] += 1

    for a, b, c in faces:
        union(int(a), int(b))
        union(int(a), int(c))
    labels = np.fromiter((find(i) for i in range(vertex_count)), dtype=np.int64, count=vertex_count)
    _, inverse, counts = np.unique(labels, return_inverse=True, return_counts=True)
    return inverse, sorted((int(x) for x in counts), reverse=True)


def edge_incidence(vertex_count: int, faces: np.ndarray) -> dict[str, int]:
    edges = np.concatenate((faces[:, (0, 1)], faces[:, (1, 2)], faces[:, (2, 0)]), axis=0)
    edges.sort(axis=1)
    keys = edges[:, 0].astype(np.uint64) * np.uint64(vertex_count) + edges[:, 1].astype(np.uint64)
    _, counts = np.unique(keys, return_counts=True)
    return {
        "unique_edges": int(len(counts)),
        "boundary_edges_incidence_1": int(np.count_nonzero(counts == 1)),
        "manifold_edges_incidence_2": int(np.count_nonzero(counts == 2)),
        "nonmanifold_edges_incidence_gt_2": int(np.count_nonzero(counts > 2)),
        "maximum_edge_incidence": int(counts.max(initial=0)),
    }


def extract_reference_seam(image_path: Path) -> dict[str, object]:
    rgb = np.asarray(Image.open(image_path).convert("RGB"), dtype=np.int16)
    red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    blue_mask = (blue > 120) & (blue > red + 35) & (blue > green + 15)
    yy, xx = np.nonzero(blue_mask)
    if not len(xx):
        raise ValueError("No blue REF-SEAM pixels detected")

    # Foreground bbox excludes the near-white studio background and blue annotation.
    channel_span = rgb.max(axis=2) - rgb.min(axis=2)
    foreground = (rgb.mean(axis=2) < 238) & ((channel_span > 12) | (rgb.mean(axis=2) < 210))
    fy, fx = np.nonzero(foreground)
    bbox = [int(fx.min()), int(fy.min()), int(fx.max()), int(fy.max())]

    rows = []
    for y in sorted(set(int(v) for v in yy)):
        xs = xx[yy == y]
        rows.append([y, float(np.median(xs)), int(xs.min()), int(xs.max()), int(len(xs))])
    x0, y0, x1, y1 = bbox
    normalized = [
        [(row[1] - x0) / (x1 - x0), 1.0 - (row[0] - y0) / (y1 - y0)]
        for row in rows
    ]
    return {
        "blue_pixel_count": int(len(xx)),
        "blue_bbox_px": [int(xx.min()), int(yy.min()), int(xx.max()), int(yy.max())],
        "reference_foreground_bbox_px": bbox,
        "row_samples_px": rows,
        "normalized_seam_xz_samples": normalized,
        "normalization": "x=(pixel_x-object_bbox_xmin)/object_bbox_width; z=1-(pixel_y-object_bbox_ymin)/object_bbox_height",
    }


def projected_depth_layers(vertices: np.ndarray, faces: np.ndarray) -> dict[str, object]:
    """Test whether separate front-side sheets cover the face, without editing it.

    Triangle centers are binned in the front-view Y/Z plane.  A closed ordinary
    body produces two broad X layers (front/back).  More than two separated
    occupied X clusters in a bin is evidence for a distinct covering sheet.
    """
    triangles = vertices[faces]
    centers = triangles.mean(axis=1)
    lo, hi = vertices.min(axis=0), vertices.max(axis=0)
    grid = 192
    yi = np.clip(((centers[:, 1] - lo[1]) / (hi[1] - lo[1]) * grid).astype(np.int32), 0, grid - 1)
    zi = np.clip(((centers[:, 2] - lo[2]) / (hi[2] - lo[2]) * grid).astype(np.int32), 0, grid - 1)
    xi = np.clip(((centers[:, 0] - lo[0]) / (hi[0] - lo[0]) * 255).astype(np.int16), 0, 255)
    occupied = np.zeros((grid * grid, 256), dtype=np.bool_)
    occupied[zi * grid + yi, xi] = True
    # Close one-bin sampling gaps, then count contiguous depth clusters.
    closed = occupied | np.roll(occupied, 1, axis=1) | np.roll(occupied, -1, axis=1)
    starts = closed & ~np.roll(closed, 1, axis=1)
    starts[:, 0] = closed[:, 0]
    cluster_count = starts.sum(axis=1)
    active = occupied.sum(axis=1) >= 3
    counts = cluster_count[active]
    return {
        "projection": "front rays parallel to +X; triangle-center occupancy binned in Y/Z",
        "grid_yz": [grid, grid],
        "depth_bins_x": 256,
        "active_ray_bins": int(active.sum()),
        "bins_with_1_depth_cluster": int(np.count_nonzero(counts == 1)),
        "bins_with_2_depth_clusters": int(np.count_nonzero(counts == 2)),
        "bins_with_gt_2_depth_clusters": int(np.count_nonzero(counts > 2)),
        "max_depth_clusters": int(counts.max(initial=0)),
        "interpretation_limit": "Cluster count is a conservative projection diagnostic, not semantic identification of a body surface.",
    }


def main() -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    vertices, faces = read_binary_ply(SOURCE)
    triangle_vertices = vertices[faces]
    cross = np.cross(triangle_vertices[:, 1] - triangle_vertices[:, 0], triangle_vertices[:, 2] - triangle_vertices[:, 0])
    double_area = np.linalg.norm(cross, axis=1)
    labels, component_vertex_counts = connected_labels(len(vertices), faces)
    component_face_counts = np.bincount(labels[faces[:, 0]], minlength=len(component_vertex_counts))
    bounds_min, bounds_max = vertices.min(axis=0), vertices.max(axis=0)
    payload = {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-MASTERFORM-CLEANUP-R08.md",
        "operation": "read_only_precleanup_inspection",
        "source": {
            "path": SOURCE.relative_to(ROOT).as_posix(),
            "bytes": SOURCE.stat().st_size,
            "sha256": sha256(SOURCE),
            "vertices": int(len(vertices)),
            "triangles": int(len(faces)),
            "bounds_min_normalized": bounds_min.tolist(),
            "bounds_max_normalized": bounds_max.tolist(),
            "extents_normalized": (bounds_max - bounds_min).tolist(),
            "degenerate_triangles": int(np.count_nonzero(double_area <= 1e-12)),
            "connected_vertex_components": int(len(component_vertex_counts)),
            "component_vertex_counts_desc": component_vertex_counts,
            "component_face_counts": [int(x) for x in component_face_counts],
            "edge_incidence": edge_incidence(len(vertices), faces),
        },
        "reference_seam": extract_reference_seam(SEAM_IMAGE),
        "front_projection_depth_layers": projected_depth_layers(vertices, faces),
        "hidden_body_surface_conclusion": {
            "status": "NOT_YET_SEMANTICALLY_CONFIRMED",
            "reason": "Topology and ray-layer diagnostics establish whether separate shells/sheets exist; final classification is made together with coordinate renders.",
        },
    }
    REPORT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
