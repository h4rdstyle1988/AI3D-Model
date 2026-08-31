#!/usr/bin/env python3
"""Deterministic Seed-42 topology probe for approved R14 surface surgery."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

import numpy as np


EXPECTED_SEED_SHA256 = "85ba18eaed15bdbe631fc49dd571e73882c4055e2c247022e90ad15ed99822c6"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_binary_ply(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with path.open("rb") as stream:
        header = []
        while True:
            line = stream.readline()
            if not line:
                raise ValueError("Unexpected EOF in PLY header")
            decoded = line.decode("ascii").strip()
            header.append(decoded)
            if decoded == "end_header":
                break
        if "format binary_little_endian 1.0" not in header:
            raise ValueError("Only binary little-endian PLY is supported")
        vertex_count = int(next(x.split()[2] for x in header if x.startswith("element vertex ")))
        face_count = int(next(x.split()[2] for x in header if x.startswith("element face ")))
        vertices = np.fromfile(stream, dtype="<f4", count=vertex_count * 3).reshape((-1, 3)).astype(np.float64)
        raw = np.fromfile(stream, dtype=np.dtype([("n", "u1"), ("v", "<i4", (3,))]), count=face_count)
        if len(raw) != face_count or not np.all(raw["n"] == 3):
            raise ValueError("PLY must contain triangles only")
        faces = raw["v"].astype(np.int64)
    return vertices, faces


def edge_table(faces: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    directed = np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]), axis=0)
    edges = np.sort(directed, axis=1)
    unique, first, counts = np.unique(edges, axis=0, return_index=True, return_counts=True)
    return unique, first, counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("seed", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    actual_hash = sha256(args.seed)
    vertices, faces = read_binary_ply(args.seed)
    tri = vertices[faces]
    cross = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    double_area = np.linalg.norm(cross, axis=1)
    area = float(0.5 * double_area.sum())
    signed_volume = float(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6.0)

    edges, _, counts = edge_table(faces)
    lengths = np.linalg.norm(vertices[edges[:, 1]] - vertices[edges[:, 0]], axis=1)
    max_extent = float(np.ptp(vertices, axis=0).max())
    mm_per_unit = 200.0 / max_extent

    canonical_faces = np.sort(faces, axis=1)
    _, face_multiplicity = np.unique(canonical_faces, axis=0, return_counts=True)
    report = {
        "schema_version": 1,
        "source": str(args.seed),
        "source_sha256": actual_hash,
        "expected_sha256": EXPECTED_SEED_SHA256,
        "hash_gate": "PASS" if actual_hash == EXPECTED_SEED_SHA256 else "FAIL",
        "vertices": int(len(vertices)),
        "triangles": int(len(faces)),
        "bounds_min": vertices.min(axis=0).tolist(),
        "bounds_max": vertices.max(axis=0).tolist(),
        "extents_normalized": np.ptp(vertices, axis=0).tolist(),
        "scale_for_200mm_max_extent": mm_per_unit,
        "surface_area_normalized2": area,
        "surface_area_at_200mm_mm2": area * mm_per_unit * mm_per_unit,
        "signed_volume_normalized3": signed_volume,
        "degenerate_faces": int(np.count_nonzero(double_area <= 1e-15)),
        "boundary_edges": int(np.count_nonzero(counts == 1)),
        "manifold_edges": int(np.count_nonzero(counts == 2)),
        "nonmanifold_edges": int(np.count_nonzero(counts > 2)),
        "max_edge_incidence": int(counts.max()),
        "duplicate_face_groups": int(np.count_nonzero(face_multiplicity > 1)),
        "duplicate_faces_excess": int(np.maximum(face_multiplicity - 1, 0).sum()),
        "edge_length_mm": {
            "min": float(lengths.min() * mm_per_unit),
            "median": float(np.median(lengths) * mm_per_unit),
            "p95": float(np.percentile(lengths, 95) * mm_per_unit),
            "p99": float(np.percentile(lengths, 99) * mm_per_unit),
            "max": float(lengths.max() * mm_per_unit),
        },
    }
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
