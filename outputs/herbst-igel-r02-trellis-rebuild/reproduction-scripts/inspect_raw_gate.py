#!/usr/bin/env python3
"""Generate objective reference and raw-mesh measurements for the R02 gate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFile


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def inspect_reference(path: Path) -> dict[str, object]:
    strict_error: str | None = None
    try:
        Image.open(path).convert("RGB").load()
        strict_decode = True
    except Exception as exc:  # decoder evidence is part of the report
        strict_decode = False
        strict_error = f"{type(exc).__name__}: {exc}"
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    pixels = np.asarray(Image.open(path).convert("RGB"))
    row_std = pixels.std(axis=(1, 2))
    nonuniform = np.flatnonzero(row_std > 2.0)
    last_nonuniform = int(nonuniform.max()) if nonuniform.size else None
    return {
        "path": path.as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "width_px": int(pixels.shape[1]),
        "height_px": int(pixels.shape[0]),
        "strict_decode_complete": strict_decode,
        "strict_decode_error": strict_error,
        "last_nonuniform_row_y": last_nonuniform,
        "rows_after_last_nonuniform": (
            int(pixels.shape[0] - 1 - last_nonuniform)
            if last_nonuniform is not None
            else int(pixels.shape[0])
        ),
    }


def read_raw_ply(path: Path) -> tuple[np.ndarray, np.ndarray, int, int]:
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
        vertex_count = int(next(x.split()[2] for x in header if x.startswith("element vertex ")))
        face_count = int(next(x.split()[2] for x in header if x.startswith("element face ")))
        vertices = np.fromfile(stream, dtype="<f4", count=vertex_count * 3).reshape(-1, 3)
        records = np.fromfile(
            stream,
            dtype=np.dtype([("count", "u1"), ("indices", "<i4", (3,))]),
            count=face_count,
        )
    if not np.all(records["count"] == 3):
        raise ValueError("Non-triangular face encountered")
    return vertices, records["indices"], vertex_count, face_count


def inspect_ply(path: Path) -> dict[str, object]:
    vertices, faces, vertex_count, face_count = read_raw_ply(path)
    triangles = vertices[faces]
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    areas = 0.5 * np.linalg.norm(cross, axis=1)
    minimum = vertices.min(axis=0)
    maximum = vertices.max(axis=0)
    return {
        "path": path.as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "vertices": vertex_count,
        "triangles": face_count,
        "all_faces_triangular": True,
        "bounds_min": minimum.astype(float).tolist(),
        "bounds_max": maximum.astype(float).tolist(),
        "extents": (maximum - minimum).astype(float).tolist(),
        "degenerate_triangles": int(np.count_nonzero(areas <= 1e-12)),
        "surface_area_normalized_units2": float(areas.sum()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ref-clean", required=True, type=Path)
    parser.add_argument("--ref-seam", required=True, type=Path)
    parser.add_argument("--raw-ply", required=True, type=Path)
    parser.add_argument("--raw-glb", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = {
        "reference_clean": inspect_reference(args.ref_clean),
        "reference_seam": inspect_reference(args.ref_seam),
        "raw_ply": inspect_ply(args.raw_ply),
        "raw_glb": {
            "path": args.raw_glb.as_posix(),
            "bytes": args.raw_glb.stat().st_size,
            "sha256": sha256(args.raw_glb),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
