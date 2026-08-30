#!/usr/bin/env python3
"""Render the actual R09 reconstruction in all required optical-gate views."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from reconstruct_body_surface_r09 import read_binary_ply


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
MASTER = OUT / "masterform" / "herbst-igel-r02-masterform-reconstructed-r09-NON-APPROVED.ply"
RAW = OUT / "source-r08" / "herbst-igel-r02-trellis-raw-seed-42.ply"
REF = OUT / "reference-audit" / "ref-clean-r09.jpg"
SEAM = OUT / "reference-audit" / "ref-seam-r09.jpg"
RENDERS = OUT / "renders-optik-gate"
REPORT = OUT / "reports" / "real-geometry-renders-r09.json"


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


def render(
    vertices: np.ndarray,
    faces: np.ndarray,
    camera: tuple[float, float, float],
    output: Path,
    title: str,
    size: int = 1100,
) -> None:
    triangles = vertices[faces]
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(cross, axis=1)
    keep = lengths > 1e-12
    centers = triangles.mean(axis=1)[keep]
    normals = cross[keep] / lengths[keep, None]
    used = np.unique(faces)
    center = 0.5 * (vertices[used].min(axis=0) + vertices[used].max(axis=0))
    centers -= center
    right, up, forward = camera_basis(camera)
    u, v, depth = centers @ right, centers @ up, centers @ forward
    extent = max(float(np.ptp(u)), float(np.ptp(v))) * 1.12
    center_u = 0.5 * float(np.max(u) + np.min(u))
    center_v = 0.5 * float(np.max(v) + np.min(v))
    scale = (size - 110) / extent
    px = np.rint((u - center_u) * scale + size / 2).astype(np.int64)
    py = np.rint(size / 2 - (v - center_v) * scale).astype(np.int64)
    inside = (px >= 0) & (px < size) & (py >= 46) & (py < size)
    px, py, depth, normals = px[inside], py[inside], depth[inside], normals[inside]
    flat = py * size + px
    order = np.lexsort((depth, flat))
    ordered_flat = flat[order]
    first = np.empty_like(ordered_flat, dtype=bool)
    first[0] = True
    first[1:] = ordered_flat[1:] != ordered_flat[:-1]
    selected = order[first]
    light = np.array([-0.35, 0.75, -0.55], dtype=np.float64)
    light /= np.linalg.norm(light)
    shade = np.clip(
        0.20 + 0.53 * np.abs(normals[selected] @ light) + 0.27 * np.abs(normals[selected] @ (-forward)),
        0.0,
        1.0,
    )
    base = np.array([190.0, 91.0, 40.0])
    colors = np.clip(base[None, :] * (0.43 + 0.70 * shade[:, None]), 0, 255).astype(np.uint8)
    canvas = np.full((size * size, 3), 242, dtype=np.uint8)
    canvas[flat[selected]] = colors
    pixels = canvas.reshape(size, size, 3)
    image = Image.fromarray(pixels)
    # Triangle-center splats are a deterministic software raster fallback.
    # Seven pixels cover the largest projected R09 patch edge at 1100 px and
    # remove sampling gaps without changing or retouching the geometry.
    mask = Image.fromarray((np.any(pixels != 242, axis=2) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(7))
    expanded = image.filter(ImageFilter.MinFilter(7))
    result = Image.new("RGB", (size, size), (242, 242, 242))
    result.paste(expanded, mask=mask)
    draw = ImageDraw.Draw(result)
    draw.rectangle((0, 0, size, 46), fill=(255, 255, 255))
    draw.text((15, 16), title, fill=(20, 20, 20))
    result.save(output, optimize=True)


def sheet(paths: list[Path], labels: list[str], output: Path, columns: int, panel: tuple[int, int]) -> None:
    rows = (len(paths) + columns - 1) // columns
    pw, ph = panel
    result = Image.new("RGB", (columns * pw, rows * ph), (232, 232, 232))
    for index, (path, label) in enumerate(zip(paths, labels)):
        image = Image.open(path).convert("RGB")
        fitted = ImageOps.contain(image, (pw - 20, ph - 54), Image.Resampling.LANCZOS)
        panel_image = Image.new("RGB", panel, (242, 242, 242))
        panel_image.paste(fitted, ((pw - fitted.width) // 2, 44 + (ph - 54 - fitted.height) // 2))
        draw = ImageDraw.Draw(panel_image)
        draw.rectangle((0, 0, pw, 42), fill=(255, 255, 255))
        draw.text((10, 14), label, fill=(20, 20, 20))
        result.paste(panel_image, ((index % columns) * pw, (index // columns) * ph))
    result.save(output, optimize=True)


def main() -> None:
    RENDERS.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    vertices, faces = read_binary_ply(MASTER)
    raw_vertices, raw_faces = read_binary_ply(RAW)
    views = [
        ("3q-front", (-1.0, -1.0, 0.35), "3/4 vorne"),
        ("left", (0.0, -1.0, 0.12), "links / Referenzseite"),
        ("right", (0.0, 1.0, 0.12), "rechts"),
        ("rear", (1.0, 0.0, 0.12), "hinten"),
        ("top", (0.0, 0.0, 1.0), "oben"),
        ("bottom", (0.0, 0.0, -1.0), "unten"),
    ]
    paths: list[Path] = []
    records: list[dict[str, object]] = []
    for slug, camera, label in views:
        path = RENDERS / f"masterform-{slug}.png"
        render(vertices, faces, camera, path, f"R09 REKONSTRUKTION (NICHT FREIGEGEBEN): {label}")
        paths.append(path)
        records.append({"view": slug, "camera_vector": list(camera), "path": path.relative_to(ROOT).as_posix()})
    contact = RENDERS / "masterform-contact-sheet-r09.png"
    sheet(paths, [x[2] for x in views], contact, 3, (520, 520))

    raw_cmp = RENDERS / "raw-seed42-3q-front-comparison.png"
    render(raw_vertices, raw_faces, views[0][1], raw_cmp, "R07/R08 Seed 42 roh: 3/4 vorne")
    compare_paths = [REF, SEAM, raw_cmp, paths[0], paths[1], paths[2]]
    compare_labels = ["SOLL REF-CLEAN", "SOLL REF-SEAM", "IST Seed 42 roh", "IST R09 3/4", "IST R09 links", "IST R09 rechts"]
    soll_ist = RENDERS / "soll-ist-optik-gate-r09.png"
    sheet(compare_paths, compare_labels, soll_ist, 3, (520, 520))
    payload = {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-BODY-SURFACE-RECONSTRUCTION-R09.md",
        "source_geometry": MASTER.relative_to(ROOT).as_posix(),
        "source_is_actual_reconstructed_geometry": True,
        "approval_status": "NON_APPROVED_PENDING_OPTIK_GATE",
        "views": records,
        "contact_sheet": contact.relative_to(ROOT).as_posix(),
        "soll_ist_sheet": soll_ist.relative_to(ROOT).as_posix(),
    }
    REPORT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
