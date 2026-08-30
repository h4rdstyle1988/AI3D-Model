#!/usr/bin/env python3
"""Render deterministic orthographic audit views from the TRELLIS raw PLY.

The renderer samples every triangle centroid and uses an orthographic z-buffer.
It is intentionally dependency-light (NumPy and Pillow only) and never changes
the source mesh.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def read_binary_ply(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with path.open("rb") as stream:
        header_lines: list[str] = []
        while True:
            line = stream.readline()
            if not line:
                raise ValueError("PLY header ended before end_header")
            decoded = line.decode("ascii").strip()
            header_lines.append(decoded)
            if decoded == "end_header":
                break
        if "format binary_little_endian 1.0" not in header_lines:
            raise ValueError("Only binary_little_endian PLY is supported")
        vertex_count = next(
            int(line.split()[2])
            for line in header_lines
            if line.startswith("element vertex ")
        )
        face_count = next(
            int(line.split()[2])
            for line in header_lines
            if line.startswith("element face ")
        )
        vertices = np.fromfile(stream, dtype="<f4", count=vertex_count * 3).reshape(-1, 3)
        face_records = np.fromfile(
            stream,
            dtype=np.dtype([("count", "u1"), ("indices", "<i4", (3,))]),
            count=face_count,
        )
    if not np.all(face_records["count"] == 3):
        raise ValueError("Non-triangular face encountered")
    return vertices.astype(np.float64), face_records["indices"].astype(np.int64)


def camera_basis(position: tuple[float, float, float]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    camera = np.asarray(position, dtype=np.float64)
    forward = -camera / np.linalg.norm(camera)
    world_up = np.array([0.0, 1.0, 0.0])
    if abs(float(np.dot(forward, world_up))) > 0.98:
        world_up = np.array([0.0, 0.0, 1.0])
    right = np.cross(forward, world_up)
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    up /= np.linalg.norm(up)
    return right, up, forward


def render(
    centers: np.ndarray,
    normals: np.ndarray,
    camera: tuple[float, float, float],
    output: Path,
    title: str,
    size: int = 900,
) -> None:
    right, up, forward = camera_basis(camera)
    u = centers @ right
    v = centers @ up
    depth = centers @ forward

    extent = max(float(np.ptp(u)), float(np.ptp(v))) * 1.12
    center_u = 0.5 * float(np.max(u) + np.min(u))
    center_v = 0.5 * float(np.max(v) + np.min(v))
    scale = (size - 90) / extent
    px = np.rint((u - center_u) * scale + size / 2).astype(np.int64)
    py = np.rint(size / 2 - (v - center_v) * scale).astype(np.int64)
    inside = (px >= 0) & (px < size) & (py >= 0) & (py < size)
    px, py, depth = px[inside], py[inside], depth[inside]
    normals = normals[inside]
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
    shade = np.clip(0.24 + 0.50 * face_light + 0.26 * facing, 0.0, 1.0)
    base = np.array([185.0, 84.0, 37.0])
    colors = np.clip(base[None, :] * (0.42 + 0.72 * shade[:, None]), 0, 255).astype(np.uint8)

    canvas = np.full((size * size, 3), 242, dtype=np.uint8)
    canvas[flat[selected]] = colors
    image = Image.fromarray(canvas.reshape(size, size, 3), mode="RGB")
    mask = Image.fromarray((np.any(canvas.reshape(size, size, 3) != 242, axis=2) * 255).astype(np.uint8))
    mask = mask.filter(ImageFilter.MaxFilter(3))
    expanded = image.filter(ImageFilter.MaxFilter(3))
    background = Image.new("RGB", (size, size), (242, 242, 242))
    background.paste(expanded, mask=mask)
    draw = ImageDraw.Draw(background)
    draw.rectangle((0, 0, size, 34), fill=(255, 255, 255))
    draw.text((12, 10), title, fill=(20, 20, 20))
    output.parent.mkdir(parents=True, exist_ok=True)
    background.save(output, optimize=True)


def make_contact_sheet(images: list[Path], output: Path) -> None:
    opened = [Image.open(path).convert("RGB") for path in images]
    thumb_size = 450
    sheet = Image.new("RGB", (thumb_size * 3, thumb_size * 2), (235, 235, 235))
    for index, image in enumerate(opened):
        image.thumbnail((thumb_size, thumb_size), Image.Resampling.LANCZOS)
        x = (index % 3) * thumb_size + (thumb_size - image.width) // 2
        y = (index // 3) * thumb_size + (thumb_size - image.height) // 2
        sheet.paste(image, (x, y))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ply", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    vertices, faces = read_binary_ply(args.ply)
    triangles = vertices[faces]
    centers = triangles.mean(axis=1)
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    keep = lengths > 1e-12
    centers = centers[keep]
    normals = normals[keep] / lengths[keep, None]
    centers -= 0.5 * (vertices.min(axis=0) + vertices.max(axis=0))

    views = [
        ("raw-3q-front.png", (1.0, 0.45, 1.0), "TRELLIS raw: 3/4 front"),
        ("raw-visible-side.png", (0.0, 0.15, 1.0), "TRELLIS raw: visible side/front"),
        ("raw-opposite-side.png", (0.0, 0.15, -1.0), "TRELLIS raw: opposite side/back"),
        ("raw-rear.png", (-1.0, 0.15, 0.0), "TRELLIS raw: rear"),
        ("raw-top.png", (0.0, 1.0, 0.0), "TRELLIS raw: top"),
        ("raw-bottom.png", (0.0, -1.0, 0.0), "TRELLIS raw: bottom"),
    ]
    rendered: list[Path] = []
    for filename, camera, title in views:
        destination = args.output_dir / filename
        render(centers, normals, camera, destination, title)
        rendered.append(destination)
    make_contact_sheet(rendered, args.output_dir / "raw-contact-sheet.png")


if __name__ == "__main__":
    main()
