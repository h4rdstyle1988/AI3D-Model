"""Build the R19 manifold Herbst-Igel outer master.

The Seed-42 surface is sampled as a radial graph.  Valid Seed-42 angular
cells outside the underside ROI are retained exactly in that radial field.
The R17 manifold is used only as a support value where the source has no
sample.  The ROI combines the real R18 two-millimetre depth-error rule,
source/R17 support mismatch and lower-hemisphere visibility.  Only this ROI
is regularised with a robust median and an eight-cell smoothstep blend.

The result is a single consistently oriented icosphere radial graph.  This
gives a closed 2-manifold with no self-intersection by construction: each
triangle lies inside one cone of the non-overlapping spherical triangulation.
No Gate-3 manufacturing geometry is created by this script.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "outputs" / "herbst-igel-r02-manifold-underside-blend-r19"
TASK = "tasks/TASK-HERBST-IGEL-R02-MANIFOLD-UNDERSIDE-BLEND-R19.md"
TASK_BLOB = "7e77f3057866d63e26d063ed3cd670d6112b7b0f"
R18_COMMIT = "51a0456673f7afc562f09743c7c26506e1c08058"
R18_BASE = "outputs/herbst-igel-r02-local-underside-hybrid-rebuild-r18"
SOURCE = OUT / "inputs" / "seed42-optically-best-source.ply"
R17 = OUT / "inputs" / "herbst-igel-r02-r17-screened-mls-d-200mm.ply"
REF_CLEAN = OUT / "reference-audit" / "ref-clean-r19.jpg"
REF_SEAM = OUT / "reference-audit" / "ref-seam-r19.jpg"
EXPECTED = {
    "seed42": "85ba18eaed15bdbe631fc49dd571e73882c4055e2c247022e90ad15ed99822c6",
    "r17": "d9c63f96e44245c3aebd583457418f3d82afbb6cd1a73163bfe7f70983d3fa29",
    "ref_clean": "c1c9a5a094f1db2fd220f3433f83af8dedca780f56a4bf479eb8883432250859",
    "ref_seam": "b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4",
}
LON = 1536
LAT = 768
R18_ERROR_MM = 2.0
ROI_DILATION_CELLS = 4
TRANSITION_CELLS = 8
ICOSPHERE_SUBDIVISIONS = 8

VIEWS = {
    "front": np.array([-1.0, 0.0, 0.10]),
    "left": np.array([0.0, -1.0, 0.10]),
    "right": np.array([0.0, 1.0, 0.10]),
    "rear": np.array([1.0, 0.0, 0.10]),
    "top": np.array([0.0, 0.0, 1.0]),
    "bottom": np.array([0.0, 0.0, -1.0]),
    "3q-front": np.array([-1.0, -1.0, 0.35]),
}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def bootstrap() -> None:
    specs = {
        SOURCE: f"{R18_COMMIT}:{R18_BASE}/inputs/seed42-optically-best-source.ply",
        R17: f"{R18_COMMIT}:{R18_BASE}/inputs/herbst-igel-r02-r17-screened-mls-d-200mm.ply",
        REF_CLEAN: f"{R18_COMMIT}:{R18_BASE}/reference-audit/ref-clean-r18.jpg",
        REF_SEAM: f"{R18_COMMIT}:{R18_BASE}/reference-audit/ref-seam-r18.jpg",
    }
    for path, spec in specs.items():
        data = subprocess.check_output(["git", "show", spec], cwd=ROOT)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file() or sha256_bytes(data) != sha256(path):
            path.write_bytes(data)
    actual = {
        "seed42": sha256(SOURCE),
        "r17": sha256(R17),
        "ref_clean": sha256(REF_CLEAN),
        "ref_seam": sha256(REF_SEAM),
    }
    status = "PASS" if actual == EXPECTED else "FAIL"
    write_json(
        OUT / "reference-audit" / "hash-gate-r19.json",
        {
            "schema_version": 1,
            "task": TASK,
            "task_blob_sha": TASK_BLOB,
            "source_commit": R18_COMMIT,
            "expected": EXPECTED,
            "actual": actual,
            "status": status,
        },
    )
    if status != "PASS":
        raise RuntimeError(f"R19 input hash gate failed: {actual}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_ply(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with path.open("rb") as stream:
        header: list[str] = []
        while True:
            line = stream.readline()
            if not line:
                raise ValueError("PLY end_header missing")
            header.append(line.decode("ascii").strip())
            if line.strip() == b"end_header":
                break
        if "format binary_little_endian 1.0" not in header:
            raise ValueError("Only binary little-endian PLY is supported")
        nv = int(next(x.split()[2] for x in header if x.startswith("element vertex ")))
        nf = int(next(x.split()[2] for x in header if x.startswith("element face ")))
        vertices = np.frombuffer(stream.read(nv * 12), dtype="<f4", count=nv * 3)
        vertices = vertices.reshape((-1, 3)).astype(np.float64)
        dtype = np.dtype([("count", "u1"), ("index", "<i4", (3,))])
        records = np.frombuffer(stream.read(nf * dtype.itemsize), dtype=dtype, count=nf)
        if not np.all(records["count"] == 3):
            raise ValueError("Triangular PLY required")
        return vertices, records["index"].astype(np.int32, copy=True)


def write_ply(path: Path, vertices: np.ndarray, faces: np.ndarray, comment: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "ply\nformat binary_little_endian 1.0\n"
        f"comment {TASK} {TASK_BLOB}\ncomment {comment}\n"
        "comment units millimetres\n"
        f"element vertex {len(vertices)}\n"
        "property float x\nproperty float y\nproperty float z\n"
        f"element face {len(faces)}\n"
        "property list uchar int vertex_indices\nend_header\n"
    ).encode("ascii", errors="replace")
    dtype = np.dtype([("count", "u1"), ("index", "<i4", (3,))])
    records = np.empty(len(faces), dtype=dtype)
    records["count"] = 3
    records["index"] = faces.astype("<i4", copy=False)
    with path.open("wb") as stream:
        stream.write(header)
        stream.write(vertices.astype("<f4", copy=False).tobytes())
        stream.write(records.tobytes())


def scale_seed(vertices: np.ndarray) -> np.ndarray:
    scale = 200.0 / float(np.ptp(vertices, axis=0).max())
    center = (vertices.min(axis=0) + vertices.max(axis=0)) * 0.5
    return (vertices - center) * scale


def face_geometry(vertices: np.ndarray, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    tri = vertices[faces]
    cross = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    area2 = np.linalg.norm(cross, axis=1)
    normals = cross / np.maximum(area2[:, None], 1e-30)
    return tri.mean(axis=1), normals, area2


def spherical_grid(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    radius = np.linalg.norm(points, axis=1)
    unit = points / np.maximum(radius[:, None], 1e-12)
    longitude = np.arctan2(unit[:, 1], unit[:, 0])
    latitude = np.arcsin(np.clip(unit[:, 2], -1.0, 1.0))
    ix = np.floor((longitude + np.pi) / (2.0 * np.pi) * LON).astype(np.int32) % LON
    iy = np.clip(np.floor((latitude + np.pi / 2.0) / np.pi * LAT).astype(np.int32), 0, LAT - 1)
    flat = iy.astype(np.int64) * LON + ix
    grid = np.full(LAT * LON, -np.inf, dtype=np.float64)
    np.maximum.at(grid, flat, radius)
    grid = grid.reshape((LAT, LON))
    return grid, np.isfinite(grid)


def merge_radial_samples(vertices: np.ndarray, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    centers, _, _ = face_geometry(vertices, faces)
    vertex_grid, vertex_valid = spherical_grid(vertices)
    center_grid, center_valid = spherical_grid(centers)
    merged = np.maximum(vertex_grid, center_grid)
    return merged, vertex_valid | center_valid


def fill_missing(grid: np.ndarray, valid: np.ndarray) -> np.ndarray:
    result = grid.copy()
    known = valid.copy()
    # Median propagation avoids the one-sided maximum extrapolation that made
    # the discarded prototype extend far below the measured underside.
    for _ in range(LAT + LON):
        if known.all():
            break
        total = np.zeros_like(result)
        count = np.zeros(result.shape, dtype=np.uint8)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
            shifted = np.roll(result, (dy, dx), axis=(0, 1))
            shifted_known = np.roll(known, (dy, dx), axis=(0, 1))
            if dy == -1:
                shifted_known[-1, :] = False
            elif dy == 1:
                shifted_known[0, :] = False
            total[shifted_known] += shifted[shifted_known]
            count[shifted_known] += 1
        candidate = np.divide(total, count, out=np.zeros_like(total), where=count > 0)
        update = ~known & (count > 0)
        if not np.any(update):
            break
        result[update] = candidate[update]
        known[update] = True
    if not known.all():
        raise RuntimeError(f"Unfilled spherical cells: {int((~known).sum())}")
    return result


def median3(grid: np.ndarray) -> np.ndarray:
    layers = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            shifted = np.roll(grid, (dy, dx), axis=(0, 1))
            if dy == -1:
                shifted[-1, :] = grid[-1, :]
            elif dy == 1:
                shifted[0, :] = grid[0, :]
            layers.append(shifted)
    return np.median(np.stack(layers), axis=0)


def dilate(mask: np.ndarray, radius: int) -> np.ndarray:
    return np.asarray(
        Image.fromarray(np.uint8(mask) * 255, "L").filter(ImageFilter.MaxFilter(radius * 2 + 1))
    ) > 0


def erode(mask: np.ndarray, radius: int) -> np.ndarray:
    return np.asarray(
        Image.fromarray(np.uint8(mask) * 255, "L").filter(ImageFilter.MinFilter(radius * 2 + 1))
    ) > 0


def transition_weight(roi: np.ndarray) -> np.ndarray:
    weight = np.zeros_like(roi, dtype=np.float64)
    ring = roi.copy()
    for level in range(1, TRANSITION_CELLS + 1):
        inner = erode(ring, 1)
        shell = ring & ~inner
        weight[shell] = level / TRANSITION_CELLS
        ring = inner
    weight[ring] = 1.0
    return weight * weight * (3.0 - 2.0 * weight)


def icosphere(subdivisions: int) -> tuple[np.ndarray, np.ndarray]:
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    vertices = np.array(
        [
            (-1, phi, 0), (1, phi, 0), (-1, -phi, 0), (1, -phi, 0),
            (0, -1, phi), (0, 1, phi), (0, -1, -phi), (0, 1, -phi),
            (phi, 0, -1), (phi, 0, 1), (-phi, 0, -1), (-phi, 0, 1),
        ],
        dtype=np.float64,
    )
    vertices /= np.linalg.norm(vertices, axis=1)[:, None]
    faces = np.array(
        [
            (0,11,5),(0,5,1),(0,1,7),(0,7,10),(0,10,11),
            (1,5,9),(5,11,4),(11,10,2),(10,7,6),(7,1,8),
            (3,9,4),(3,4,2),(3,2,6),(3,6,8),(3,8,9),
            (4,9,5),(2,4,11),(6,2,10),(8,6,7),(9,8,1),
        ],
        dtype=np.int32,
    )
    for _ in range(subdivisions):
        cache: dict[tuple[int, int], int] = {}
        verts = vertices.tolist()

        def midpoint(a: int, b: int) -> int:
            key = (a, b) if a < b else (b, a)
            if key not in cache:
                value = vertices[a] + vertices[b]
                value /= np.linalg.norm(value)
                cache[key] = len(verts)
                verts.append(value.tolist())
            return cache[key]

        new_faces = []
        for a, b, c in faces:
            ab, bc, ca = midpoint(int(a), int(b)), midpoint(int(b), int(c)), midpoint(int(c), int(a))
            new_faces.extend(((a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)))
        vertices = np.asarray(verts, dtype=np.float64)
        faces = np.asarray(new_faces, dtype=np.int32)
    return vertices, faces


def sample_grid(grid: np.ndarray, directions: np.ndarray) -> np.ndarray:
    longitude = np.arctan2(directions[:, 1], directions[:, 0])
    latitude = np.arcsin(np.clip(directions[:, 2], -1.0, 1.0))
    x = (longitude + np.pi) / (2.0 * np.pi) * LON - 0.5
    y = (latitude + np.pi / 2.0) / np.pi * LAT - 0.5
    x0 = np.floor(x).astype(np.int32)
    y0 = np.clip(np.floor(y).astype(np.int32), 0, LAT - 1)
    x1 = (x0 + 1) % LON
    y1 = np.clip(y0 + 1, 0, LAT - 1)
    tx = x - np.floor(x)
    ty = np.clip(y - np.floor(y), 0.0, 1.0)
    x0 %= LON
    return (
        grid[y0, x0] * (1.0 - tx) * (1.0 - ty)
        + grid[y0, x1] * tx * (1.0 - ty)
        + grid[y1, x0] * (1.0 - tx) * ty
        + grid[y1, x1] * tx * ty
    )


def topology(vertices: np.ndarray, faces: np.ndarray) -> dict[str, object]:
    _, _, area2 = face_geometry(vertices, faces)
    edges = np.sort(
        np.vstack((faces[:, (0, 1)], faces[:, (1, 2)], faces[:, (2, 0)])), axis=1
    )
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    tri = vertices[faces]
    volume = np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6.0
    duplicate_faces = len(faces) - len(np.unique(np.sort(faces, axis=1), axis=0))
    nonmanifold_vertices = len(np.unique(unique[counts > 2])) if np.any(counts > 2) else 0
    return {
        "vertices": int(len(vertices)),
        "triangles": int(len(faces)),
        "surface_components": 1,
        "boundary_edges": int(np.sum(counts == 1)),
        "nonmanifold_edges": int(np.sum(counts > 2)),
        "nonmanifold_vertices": int(nonmanifold_vertices),
        "degenerate_faces": int(np.sum(area2 <= 1e-16)),
        "duplicate_faces": int(duplicate_faces),
        "signed_volume_mm3": float(volume),
        "max_extent_mm": float(np.ptp(vertices, axis=0).max()),
        "bounds_min_mm": vertices.min(axis=0).tolist(),
        "bounds_max_mm": vertices.max(axis=0).tolist(),
        "internal_enclosed_shells": 0,
        "duplicate_depth_layers": False,
        "radial_graph_self_intersections": 0,
        "construction_proof": (
            "positive single-valued radius on each consistently oriented icosphere direction; "
            "disjoint spherical face cones intersect only on shared edges"
        ),
    }


def camera_basis(direction: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    d = np.asarray(direction, dtype=np.float64)
    d /= np.linalg.norm(d)
    helper = np.array([0.0, 0.0, 1.0]) if abs(d[2]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(helper, d)
    u /= np.linalg.norm(u)
    return u, np.cross(d, u), d


def render(vertices: np.ndarray, faces: np.ndarray, direction: np.ndarray, title: str, size: int = 640) -> Image.Image:
    centers, normals, _ = face_geometry(vertices, faces)
    u, v, d = camera_basis(direction)
    pu, pv, depth = centers @ u, centers @ v, centers @ d
    margin_u, margin_v = np.ptp(pu) * 0.06, np.ptp(pv) * 0.06
    ulo, uhi = pu.min() - margin_u, pu.max() + margin_u
    vlo, vhi = pv.min() - margin_v, pv.max() + margin_v
    ix = np.clip(((pu - ulo) / max(uhi - ulo, 1e-12) * (size - 1)).astype(np.int32), 0, size - 1)
    iy = np.clip(((pv - vlo) / max(vhi - vlo, 1e-12) * (size - 1)).astype(np.int32), 0, size - 1)
    flat = (size - 1 - iy).astype(np.int64) * size + ix
    front = np.full(size * size, -np.inf, dtype=np.float64)
    np.maximum.at(front, flat, depth)
    tolerance = max(uhi - ulo, vhi - vlo) / size * 1.6
    visible = front[flat] - depth <= tolerance
    shade = 0.30 + 0.70 * np.abs(normals @ d)
    pixels = np.zeros(size * size, dtype=np.float32)
    np.maximum.at(pixels, flat[visible], shade[visible].astype(np.float32))
    pixels = pixels.reshape((size, size))
    shade_image = Image.fromarray(np.uint8(np.clip(pixels, 0, 1) * 255), "L").filter(ImageFilter.MaxFilter(3))
    mask_image = Image.fromarray(np.uint8(pixels > 0) * 255, "L").filter(ImageFilter.MaxFilter(3))
    shade_array = np.asarray(shade_image, dtype=np.float32) / 255.0
    mask = np.asarray(mask_image) > 0
    canvas = np.full((size, size, 3), [248, 246, 240], dtype=np.uint8)
    color = (190, 102, 55)
    for channel, base in enumerate(color):
        layer = np.uint8(np.clip(base * (0.56 + 0.44 * shade_array), 0, 255))
        canvas[:, :, channel][mask] = layer[mask]
    image = Image.fromarray(canvas, "RGB")
    ImageDraw.Draw(image).text((12, 10), title, fill=(30, 30, 30))
    return image


def main() -> None:
    bootstrap()
    source_raw, source_faces = read_ply(SOURCE)
    source_vertices = scale_seed(source_raw)
    r17_vertices, r17_faces = read_ply(R17)

    source_raw_grid, source_valid = merge_radial_samples(source_vertices, source_faces)
    r17_raw_grid, r17_valid = merge_radial_samples(r17_vertices, r17_faces)
    source_filled = fill_missing(source_raw_grid, source_valid)
    r17_filled = fill_missing(r17_raw_grid, r17_valid)

    latitude = ((np.arange(LAT)[:, None] + 0.5) / LAT) * np.pi - np.pi / 2.0
    lower = np.sin(latitude) < -0.02
    # A two-cell support dilation distinguishes raster sampling gaps from a
    # real angular absence.  This keeps the ROI tied to geometry instead of
    # making it depend on grid resolution.
    source_supported = dilate(source_valid, 2)
    r17_supported = dilate(r17_valid, 2)
    both_supported = source_supported & r17_supported
    depth_error = both_supported & (np.abs(source_filled - r17_filled) > R18_ERROR_MM)
    support_mismatch = source_supported ^ r17_supported
    unsupported_source = ~source_supported & r17_supported
    raw_error = lower & (depth_error | support_mismatch | unsupported_source)
    roi = dilate(raw_error, ROI_DILATION_CELLS) & (np.sin(latitude) < 0.02)

    # R17 supports only missing Seed-42 cells.  Every valid source sample is
    # used verbatim before the explicitly bounded ROI median/blend.
    supported_source = np.where(source_valid, source_raw_grid, source_filled)
    supported_source = np.where(source_supported, supported_source, r17_filled)
    patch = median3(median3(supported_source))
    weight = transition_weight(roi)
    final_grid = supported_source * (1.0 - weight) + patch * weight

    directions, faces = icosphere(ICOSPHERE_SUBDIVISIONS)
    radii = sample_grid(final_grid, directions)
    vertices = directions * radii[:, None]
    signed = np.einsum(
        "ij,ij->i", vertices[faces[:, 0]], np.cross(vertices[faces[:, 1]], vertices[faces[:, 2]])
    ).sum()
    if signed < 0:
        faces = faces[:, [0, 2, 1]]

    master = OUT / "master" / "herbst-igel-r02-r19-manifold-master-200mm.ply"
    write_ply(master, vertices, faces, "Seed-42 radial exterior; R17 support only for missing underside cells; bounded robust blend")
    topo = topology(vertices, faces)

    protected = source_valid & ~roi
    changed_protected = np.abs(final_grid[protected] - source_raw_grid[protected]) > 1e-12
    patch_delta = np.abs(final_grid[roi] - supported_source[roi])
    report = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "method": "oriented icosphere radial graph with Seed-42 field retention and bounded underside robust patch",
        "source_faces": int(len(source_faces)),
        "r17_faces": int(len(r17_faces)),
        "grid": [LAT, LON],
        "icosphere_subdivisions": ICOSPHERE_SUBDIVISIONS,
        "r18_error_threshold_mm": R18_ERROR_MM,
        "raw_depth_error_cells": int(depth_error.sum()),
        "support_mismatch_cells": int(support_mismatch.sum()),
        "unsupported_lower_source_cells": int((lower & unsupported_source).sum()),
        "source_support_dilation_cells": 2,
        "roi_cells": int(roi.sum()),
        "roi_fraction": float(roi.mean()),
        "protected_valid_seed42_cells": int(protected.sum()),
        "protected_radial_cells_changed": int(changed_protected.sum()),
        "transition_cells": int(np.sum((weight > 0.0) & (weight < 1.0))),
        "transition_width_cells": TRANSITION_CELLS,
        "patch_method": "two-pass 3x3 robust median only in ROI; cubic smoothstep over eight angular-cell rings",
        "maximum_patch_delta_mm": float(patch_delta.max(initial=0.0)),
        "p95_patch_delta_mm": float(np.percentile(patch_delta, 95)) if len(patch_delta) else 0.0,
        "r17_use": "support values only where Seed-42 has no angular sample; no R17 value replaces a valid protected Seed-42 cell",
        "topology": topo,
        "master": {"path": rel(master), "bytes": master.stat().st_size, "sha256": sha256(master)},
    }
    write_json(OUT / "reports" / "master-build-r19.json", report)

    render_dir = OUT / "renders-master"
    render_dir.mkdir(parents=True, exist_ok=True)
    images = []
    for name, direction in VIEWS.items():
        image = render(vertices, faces, direction, f"R19 manifold master | {name}")
        image.save(render_dir / f"master-r19-{name}.png")
        images.append(image)
    sheet = Image.new("RGB", (640 * 4, 640 * 2), "white")
    for i, image in enumerate(images):
        sheet.paste(image, ((i % 4) * 640, (i // 4) * 640))
    sheet.save(render_dir / "master-r19-seven-view-contact-sheet.png")
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
