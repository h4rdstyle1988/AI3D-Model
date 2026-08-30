#!/usr/bin/env python3
"""Render six deterministic views directly from every untouched R07 raw PLY."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
RAW = OUT / "trellis-raw"
RENDERS = OUT / "renders-optik-gate"
REPORTS = OUT / "reports"
REF = OUT / "reference-audit" / "ref-clean-r07.jpg"
SEAM = OUT / "reference-audit" / "ref-seam-r07.jpg"
SEEDS = (42, 7, 123, 777)


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
        records = np.fromfile(stream, dtype=np.dtype([("count", "u1"), ("indices", "<i4", (3,))]), count=face_count)
    if not np.all(records["count"] == 3):
        raise ValueError("Non-triangular face found")
    return vertices.astype(np.float64), records["indices"].astype(np.int64)


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


def render(centers: np.ndarray, normals: np.ndarray, camera: tuple[float, float, float], output: Path, title: str, size: int = 1000) -> None:
    right, up, forward = camera_basis(camera)
    u, v, depth = centers @ right, centers @ up, centers @ forward
    extent = max(float(np.ptp(u)), float(np.ptp(v))) * 1.12
    center_u = 0.5 * float(np.max(u) + np.min(u))
    center_v = 0.5 * float(np.max(v) + np.min(v))
    scale = (size - 100) / extent
    px = np.rint((u - center_u) * scale + size / 2).astype(np.int64)
    py = np.rint(size / 2 - (v - center_v) * scale).astype(np.int64)
    inside = (px >= 0) & (px < size) & (py >= 42) & (py < size)
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
    shade = np.clip(0.20 + 0.53 * np.abs(normals[selected] @ light) + 0.27 * np.abs(normals[selected] @ (-forward)), 0.0, 1.0)
    base = np.array([189.0, 91.0, 41.0])
    colors = np.clip(base[None, :] * (0.43 + 0.70 * shade[:, None]), 0, 255).astype(np.uint8)
    canvas = np.full((size * size, 3), 242, dtype=np.uint8)
    canvas[flat[selected]] = colors
    pixels = canvas.reshape(size, size, 3)
    image = Image.fromarray(pixels, mode="RGB")
    mask = Image.fromarray((np.any(pixels != 242, axis=2) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))
    expanded = image.filter(ImageFilter.MinFilter(3))
    result = Image.new("RGB", (size, size), (242, 242, 242))
    result.paste(expanded, mask=mask)
    draw = ImageDraw.Draw(result)
    draw.rectangle((0, 0, size, 42), fill=(255, 255, 255))
    draw.text((14, 14), title, fill=(20, 20, 20))
    result.save(output, optimize=True)


def sheet(paths: list[Path], labels: list[str], output: Path, columns: int, panel_size: tuple[int, int]) -> None:
    rows = (len(paths) + columns - 1) // columns
    width, height = panel_size
    result = Image.new("RGB", (columns * width, rows * height), (232, 232, 232))
    for index, (path, label) in enumerate(zip(paths, labels)):
        image = Image.open(path).convert("RGB")
        fitted = ImageOps.contain(image, (width - 20, height - 54), Image.Resampling.LANCZOS)
        panel = Image.new("RGB", panel_size, (242, 242, 242))
        panel.paste(fitted, ((width - fitted.width) // 2, 44 + (height - 54 - fitted.height) // 2))
        draw = ImageDraw.Draw(panel)
        draw.rectangle((0, 0, width, 42), fill=(255, 255, 255))
        draw.text((10, 14), label, fill=(20, 20, 20))
        result.paste(panel, ((index % columns) * width, (index // columns) * height))
    result.save(output, optimize=True)


def main() -> None:
    RENDERS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    views = [
        ("3q-front", (-1.0, -1.0, 0.35), "3/4 vorne"),
        ("left", (0.0, -1.0, 0.12), "links / Referenzseite"),
        ("right", (0.0, 1.0, 0.12), "rechts"),
        ("rear", (1.0, 0.0, 0.12), "hinten"),
        ("top", (0.0, 0.0, 1.0), "oben"),
        ("bottom", (0.0, 0.0, -1.0), "unten"),
    ]
    reports = []
    compare_paths = [REF, SEAM]
    compare_labels = ["SOLL: REF-CLEAN", "SOLL: REF-SEAM"]
    for seed in SEEDS:
        ply = RAW / f"seed-{seed:08d}" / f"herbst-igel-r02-trellis-raw-seed-{seed}.ply"
        vertices, faces = read_binary_ply(ply)
        triangles = vertices[faces]
        cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
        lengths = np.linalg.norm(cross, axis=1)
        keep = lengths > 1e-12
        centers = triangles.mean(axis=1)[keep]
        normals = cross[keep] / lengths[keep, None]
        minimum, maximum = vertices.min(axis=0), vertices.max(axis=0)
        centers -= 0.5 * (minimum + maximum)
        seed_dir = RENDERS / f"seed-{seed:08d}"
        seed_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        view_records = []
        for slug, camera, label in views:
            path = seed_dir / f"raw-{slug}.png"
            render(centers, normals, camera, path, f"Seed {seed}: {label}")
            paths.append(path)
            view_records.append({"path": path.relative_to(ROOT).as_posix(), "camera_vector": list(camera)})
        sheet(paths, [f"Seed {seed}: {label}" for _, _, label in views], seed_dir / "raw-contact-sheet.png", 3, (500, 500))
        compare_paths.extend(paths[:3])
        compare_labels.extend([f"Seed {seed}: {views[i][2]}" for i in range(3)])
        reports.append({
            "seed": seed,
            "source_is_untouched_trellis_raw": True,
            "source": ply.relative_to(ROOT).as_posix(),
            "source_bytes": ply.stat().st_size,
            "source_sha256": sha256(ply),
            "vertices": int(len(vertices)),
            "triangles": int(len(faces)),
            "all_faces_triangular": True,
            "bounds_min": minimum.tolist(),
            "bounds_max": maximum.tolist(),
            "extents": (maximum - minimum).tolist(),
            "degenerate_triangles": int(np.count_nonzero(~keep)),
            "surface_area_normalized_units2": float((0.5 * lengths).sum()),
            "renders": view_records,
        })
    sheet(compare_paths, compare_labels, RENDERS / "candidate-comparison-r07.png", 4, (400, 400))
    payload = {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-TRELLIS-OPTIK-RETRY-R07.md",
        "source_geometry_modified_for_rendering": False,
        "candidates": reports,
    }
    (REPORTS / "raw-mesh-inspection-r07.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
