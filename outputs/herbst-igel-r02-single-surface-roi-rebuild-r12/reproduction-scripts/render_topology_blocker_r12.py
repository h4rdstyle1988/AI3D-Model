#!/usr/bin/env python3
"""Render the immutable outside-ROI topology blocker as a diagnostic, not an Optik-Gate render."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from analyze_r11_roi_r12 import OUT, REPORT, SOURCE, edge_table, load_r11


DIAGNOSTICS = OUT / "diagnostics"
RENDER_REPORT = OUT / "reports" / "topology-blocker-renders-r12.json"


def camera_basis(position: tuple[float, float, float]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    camera = np.asarray(position, dtype=np.float64)
    forward = -camera / np.linalg.norm(camera)
    world_up = np.array([0.0, 0.0, 1.0])
    if abs(float(np.dot(forward, world_up))) > 0.98:
        world_up = np.array([0.0, 1.0, 0.0])
    right = np.cross(forward, world_up)
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    return right, up / np.linalg.norm(up), forward


def project(points: np.ndarray, center: np.ndarray, camera: tuple[float, float, float], size: int = 900):
    right, up, forward = camera_basis(camera)
    local = points - center
    return local @ right, local @ up, local @ forward


def render(
    vertices: np.ndarray,
    faces: np.ndarray,
    invalid_edges: np.ndarray,
    camera: tuple[float, float, float],
    output: Path,
    title: str,
    size: int = 900,
) -> None:
    used = np.unique(faces)
    center = 0.5 * (vertices[used].min(axis=0) + vertices[used].max(axis=0))
    tri_centers = vertices[faces].mean(axis=1)
    u, v, depth = project(tri_centers, center, camera, size)
    extent = max(float(np.ptp(u)), float(np.ptp(v))) * 1.12
    center_u = 0.5 * float(np.max(u) + np.min(u))
    center_v = 0.5 * float(np.max(v) + np.min(v))
    scale = (size - 100) / extent
    px = np.rint((u - center_u) * scale + size / 2).astype(np.int64)
    py = np.rint(size / 2 - (v - center_v) * scale).astype(np.int64)
    canvas = np.full((size, size, 3), 245, dtype=np.uint8)
    valid = (px >= 0) & (px < size) & (py >= 48) & (py < size)
    order = np.argsort(depth[valid])
    canvas[py[valid][order], px[valid][order]] = np.array([174, 128, 96], dtype=np.uint8)

    edge_points = vertices[invalid_edges]
    eu, ev, ed = project(edge_points.reshape(-1, 3), center, camera, size)
    ex = np.rint((eu - center_u) * scale + size / 2).astype(np.int64).reshape(-1, 2)
    ey = np.rint(size / 2 - (ev - center_v) * scale).astype(np.int64).reshape(-1, 2)
    ez = ed.reshape(-1, 2).mean(axis=1)
    image = Image.fromarray(canvas)
    draw = ImageDraw.Draw(image)
    for index in np.argsort(ez):
        if np.all((ex[index] >= 0) & (ex[index] < size) & (ey[index] >= 48) & (ey[index] < size)):
            draw.line((int(ex[index, 0]), int(ey[index, 0]), int(ex[index, 1]), int(ey[index, 1])), fill=(225, 24, 24), width=2)
    draw.rectangle((0, 0, size, 46), fill=(255, 255, 255))
    draw.text((14, 15), title, fill=(20, 20, 20))
    image.save(output, optimize=True)


def main() -> None:
    r11 = load_r11()
    vertices, faces = r11["read_binary_ply"](SOURCE)
    used = np.unique(faces)
    bounds_min = vertices[used].min(axis=0).astype(np.float64)
    bounds_max = vertices[used].max(axis=0).astype(np.float64)
    _blue, body, roi, bbox, _rgb = r11["reference_masks"]()
    px, pc, pr, _width = r11["measured_width_profiles"](vertices)
    body_field = r11["signed_distance_field"](body)
    _retained, _remove, problem, _selection = r11["select_source_faces"](
        vertices, faces, roi, body_field, bounds_min, bounds_max, bbox,
        -0.105, px, pc, pr,
    )
    edges, inverse, counts = edge_table(faces)
    problem_incidence = np.bincount(
        inverse, weights=np.tile(problem.astype(np.int8), 3), minlength=len(edges)
    ).astype(np.int32)
    immutable_invalid = edges[(problem_incidence == 0) & ((counts == 1) | (counts > 2))]

    DIAGNOSTICS.mkdir(parents=True, exist_ok=True)
    views = [
        ("3q-front", (-1.0, -1.0, 0.35), "3/4 vorne"),
        ("left", (0.0, -1.0, 0.12), "Referenzseite"),
        ("right", (0.0, 1.0, 0.12), "Gegenseite"),
        ("rear", (1.0, 0.0, 0.12), "hinten"),
        ("top", (0.0, 0.0, 1.0), "oben"),
        ("bottom", (0.0, 0.0, -1.0), "unten"),
    ]
    paths: list[Path] = []
    records: list[dict[str, object]] = []
    for slug, camera, label in views:
        path = DIAGNOSTICS / f"immutable-outside-roi-invalid-edges-{slug}.png"
        render(vertices, faces, immutable_invalid, camera, path, f"R12 Topologieblocker rot: {label}")
        paths.append(path)
        records.append({"view": slug, "camera": list(camera), "path": path.relative_to(OUT.parents[1]).as_posix()})
    panel = (500, 500)
    sheet = Image.new("RGB", (panel[0] * 3, panel[1] * 2), (235, 235, 235))
    for index, path in enumerate(paths):
        image = ImageOps.contain(Image.open(path).convert("RGB"), (480, 480), Image.Resampling.LANCZOS)
        sheet.paste(image, ((index % 3) * 500 + 10, (index // 3) * 500 + 10))
    sheet_path = DIAGNOSTICS / "immutable-outside-roi-topology-blocker-sheet-r12.png"
    sheet.save(sheet_path, optimize=True)
    payload = {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-SINGLE-SURFACE-ROI-REBUILD-R12.md",
        "diagnostic_only_not_optik_gate": True,
        "source": str(SOURCE),
        "immutable_invalid_edges": int(len(immutable_invalid)),
        "views": records,
        "contact_sheet": sheet_path.relative_to(OUT.parents[1]).as_posix(),
        "topology_audit": REPORT.relative_to(OUT.parents[1]).as_posix(),
    }
    RENDER_REPORT.parent.mkdir(parents=True, exist_ok=True)
    RENDER_REPORT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
