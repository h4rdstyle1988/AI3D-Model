#!/usr/bin/env python3
"""Inspect and render deterministic orthographic views of the untouched R06 PLY."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps


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
        records = np.fromfile(
            stream,
            dtype=np.dtype([("count", "u1"), ("indices", "<i4", (3,))]),
            count=face_count,
        )
    if not np.all(records["count"] == 3):
        raise ValueError("Non-triangular face found")
    return vertices.astype(np.float64), records["indices"].astype(np.int64)


def camera_basis(position: tuple[float, float, float]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    camera = np.asarray(position, dtype=np.float64)
    forward = -camera / np.linalg.norm(camera)
    # Trellis exports this object with Z as the vertical axis.
    world_up = np.array([0.0, 0.0, 1.0])
    if abs(float(np.dot(forward, world_up))) > 0.98:
        world_up = np.array([0.0, 1.0, 0.0])
    right = np.cross(forward, world_up)
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    return right, up / np.linalg.norm(up), forward


def render(
    centers: np.ndarray,
    normals: np.ndarray,
    camera: tuple[float, float, float],
    output: Path,
    title: str,
    size: int = 1000,
) -> None:
    right, up, forward = camera_basis(camera)
    u = centers @ right
    v = centers @ up
    depth = centers @ forward
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
    face_light = np.abs(normals[selected] @ light)
    facing = np.abs(normals[selected] @ (-forward))
    shade = np.clip(0.20 + 0.53 * face_light + 0.27 * facing, 0.0, 1.0)
    base = np.array([189.0, 91.0, 41.0])
    colors = np.clip(base[None, :] * (0.43 + 0.70 * shade[:, None]), 0, 255).astype(np.uint8)
    canvas = np.full((size * size, 3), 242, dtype=np.uint8)
    canvas[flat[selected]] = colors
    pixels = canvas.reshape(size, size, 3)
    image = Image.fromarray(pixels, mode="RGB")
    mask = Image.fromarray((np.any(pixels != 242, axis=2) * 255).astype(np.uint8))
    mask = mask.filter(ImageFilter.MaxFilter(3))
    # Brown samples are darker than the background; MinFilter expands them
    # into adjacent uncovered pixels without changing the archived mesh.
    expanded = image.filter(ImageFilter.MinFilter(3))
    result = Image.new("RGB", (size, size), (242, 242, 242))
    result.paste(expanded, mask=mask)
    draw = ImageDraw.Draw(result)
    draw.rectangle((0, 0, size, 42), fill=(255, 255, 255))
    draw.text((14, 14), title, fill=(20, 20, 20))
    result.save(output, optimize=True)


def contact_sheet(paths: list[Path], output: Path) -> None:
    sheet = Image.new("RGB", (1500, 1000), (232, 232, 232))
    for index, path in enumerate(paths):
        image = Image.open(path).convert("RGB")
        image.thumbnail((500, 500), Image.Resampling.LANCZOS)
        x = (index % 3) * 500 + (500 - image.width) // 2
        y = (index // 3) * 500 + (500 - image.height) // 2
        sheet.paste(image, (x, y))
    sheet.save(output, optimize=True)


def comparison(ref: Path, seam: Path, rendered: list[Path], output: Path) -> None:
    sources = [(ref, "SOLL: vollständige Igelreferenz"), (seam, "SOLL: REF-SEAM")]
    sources += [(path, f"IST: {path.stem}") for path in rendered]
    sheet = Image.new("RGB", (1600, 1600), (232, 232, 232))
    for index, (path, label) in enumerate(sources):
        source = Image.open(path).convert("RGB")
        fitted = ImageOps.contain(source, (380, 350), Image.Resampling.LANCZOS)
        panel = Image.new("RGB", (400, 400), (242, 242, 242))
        panel.paste(fitted, ((400 - fitted.width) // 2, 44 + (350 - fitted.height) // 2))
        draw = ImageDraw.Draw(panel)
        draw.rectangle((0, 0, 400, 42), fill=(255, 255, 255))
        draw.text((10, 14), label, fill=(20, 20, 20))
        sheet.paste(panel, ((index % 4) * 400, (index // 4) * 400))
    sheet.save(output, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ply", required=True, type=Path)
    parser.add_argument("--ref", required=True, type=Path)
    parser.add_argument("--seam", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)

    vertices, faces = read_binary_ply(args.ply)
    triangles = vertices[faces]
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(cross, axis=1)
    centers = triangles.mean(axis=1)
    keep = lengths > 1e-12
    normals = cross[keep] / lengths[keep, None]
    centers = centers[keep]
    minimum = vertices.min(axis=0)
    maximum = vertices.max(axis=0)
    centers -= 0.5 * (minimum + maximum)

    views = [
        ("raw-3q-front.png", (-1.0, -1.0, 0.35), "Trellis-Rohmesh: 3/4 vorne"),
        ("raw-left.png", (0.0, -1.0, 0.12), "Trellis-Rohmesh: links"),
        ("raw-right.png", (0.0, 1.0, 0.12), "Trellis-Rohmesh: rechts"),
        ("raw-rear.png", (1.0, 0.0, 0.12), "Trellis-Rohmesh: hinten"),
        ("raw-top.png", (0.0, 0.0, 1.0), "Trellis-Rohmesh: oben"),
        ("raw-bottom.png", (0.0, 0.0, -1.0), "Trellis-Rohmesh: unten"),
    ]
    rendered: list[Path] = []
    view_records = []
    for filename, camera, title in views:
        destination = args.output_dir / filename
        render(centers, normals, camera, destination, title)
        rendered.append(destination)
        view_records.append({"path": destination.as_posix(), "camera_vector": list(camera)})
    contact_sheet(rendered, args.output_dir / "raw-contact-sheet.png")
    comparison(args.ref, args.seam, rendered, args.output_dir / "optic-gate-soll-ist-r06.png")

    report = {
        "schema_version": 1,
        "source_is_untouched_trellis_raw": True,
        "source": args.ply.as_posix(),
        "source_bytes": args.ply.stat().st_size,
        "source_sha256": sha256(args.ply),
        "vertices": int(len(vertices)),
        "triangles": int(len(faces)),
        "all_faces_triangular": True,
        "bounds_min": minimum.tolist(),
        "bounds_max": maximum.tolist(),
        "extents": (maximum - minimum).tolist(),
        "degenerate_triangles": int(np.count_nonzero(~keep)),
        "surface_area_normalized_units2": float((0.5 * lengths).sum()),
        "renders": view_records,
    }
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
