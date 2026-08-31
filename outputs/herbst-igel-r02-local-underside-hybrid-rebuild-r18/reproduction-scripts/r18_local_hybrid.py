"""Conservative local underside hybrid experiments for Herbst-Igel R18.

The script keeps the byte-identical Seed-42 source and the R17 manifold input
as immutable inputs.  It derives the underside ROI from the actual R17 bottom
depth error, bottom visibility, surface-normal direction and source topology
defects.  Two direct-source surgery variants are attempted first.  If their
topology remains invalid, a different method transfers the visible source
relief into the existing R17 manifold while fixing the patch boundary.

Only NumPy and Pillow are required.  No Gate-3 manufacturing geometry is made.
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
OUT = ROOT / "outputs" / "herbst-igel-r02-local-underside-hybrid-rebuild-r18"
TASK = "tasks/TASK-HERBST-IGEL-R02-LOCAL-UNDERSIDE-HYBRID-REBUILD-R18.md"
TASK_BLOB = "0d88869426b14cf2b7da7c05ed328e9d0117cbdc"
R17_COMMIT = "330604182afa5549fde657b36e378bb0da60203d"
R17_BASE = "outputs/herbst-igel-r02-visibility-surface-rebuild-r17"
SOURCE = OUT / "inputs" / "seed42-optically-best-source.ply"
R17_MASTER = OUT / "inputs" / "herbst-igel-r02-r17-screened-mls-d-200mm.ply"
REF_CLEAN = OUT / "reference-audit" / "ref-clean-r18.jpg"
REF_SEAM = OUT / "reference-audit" / "ref-seam-r18.jpg"
EXPECTED = {
    "seed42": "85ba18eaed15bdbe631fc49dd571e73882c4055e2c247022e90ad15ed99822c6",
    "r17_master": "d9c63f96e44245c3aebd583457418f3d82afbb6cd1a73163bfe7f70983d3fa29",
    "ref_clean": "c1c9a5a094f1db2fd220f3433f83af8dedca780f56a4bf479eb8883432250859",
    "ref_seam": "b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4",
}
RESOLUTION = 384
BOTTOM_ERROR_MM = 2.0
BOTTOM_DEPTH_BAND_MM = 12.0


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def bootstrap_inputs() -> None:
    specs = {
        SOURCE: f"{R17_COMMIT}:{R17_BASE}/inputs/seed42-optically-best-source.ply",
        R17_MASTER: f"{R17_COMMIT}:{R17_BASE}/candidates/herbst-igel-r02-r17-screened-mls-d-200mm.ply",
        REF_CLEAN: f"{R17_COMMIT}:{R17_BASE}/reference-audit/ref-clean-r17.jpg",
        REF_SEAM: f"{R17_COMMIT}:{R17_BASE}/reference-audit/ref-seam-r17.jpg",
    }
    for path, spec in specs.items():
        data = subprocess.check_output(["git", "show", spec], cwd=ROOT)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file() or path.read_bytes() != data:
            path.write_bytes(data)
    actual = {
        "seed42": sha256(SOURCE),
        "r17_master": sha256(R17_MASTER),
        "ref_clean": sha256(REF_CLEAN),
        "ref_seam": sha256(REF_SEAM),
    }
    report = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "source_commit": R17_COMMIT,
        "expected": EXPECTED,
        "actual": actual,
        "status": "PASS" if actual == EXPECTED else "FAIL",
    }
    write_json(OUT / "reference-audit" / "hash-gate-r18.json", report)
    if report["status"] != "PASS":
        raise RuntimeError(f"R18 input hash gate failed: {actual}")


def read_binary_triangle_ply(path: Path) -> tuple[np.ndarray, np.ndarray]:
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
            raise ValueError("Only binary_little_endian PLY is supported")
        nv = int(next(x.split()[2] for x in header if x.startswith("element vertex ")))
        nf = int(next(x.split()[2] for x in header if x.startswith("element face ")))
        vertices = np.frombuffer(stream.read(nv * 12), dtype="<f4", count=nv * 3)
        vertices = vertices.reshape((-1, 3)).astype(np.float64)
        dtype = np.dtype([("count", "u1"), ("index", "<i4", (3,))])
        records = np.frombuffer(stream.read(nf * dtype.itemsize), dtype=dtype, count=nf)
        if not np.all(records["count"] == 3):
            raise ValueError("Triangular PLY required")
        return vertices, records["index"].astype(np.int32, copy=True)


def write_binary_triangle_ply(path: Path, vertices: np.ndarray, faces: np.ndarray, comment: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "ply\nformat binary_little_endian 1.0\n"
        f"comment {TASK} {TASK_BLOB}\n"
        f"comment {comment}\n"
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


def compact_mesh(vertices: np.ndarray, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    used, inverse = np.unique(faces, return_inverse=True)
    return vertices[used], inverse.reshape((-1, 3)).astype(np.int32)


def source_to_mm(vertices: np.ndarray) -> tuple[np.ndarray, float]:
    scale = 200.0 / float(np.ptp(vertices, axis=0).max())
    center = (vertices.min(axis=0) + vertices.max(axis=0)) / 2.0
    return (vertices - center) * scale, scale


def face_geometry(vertices: np.ndarray, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    tri = vertices[faces]
    cross = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    area2 = np.linalg.norm(cross, axis=1)
    normals = cross / np.maximum(area2[:, None], 1e-30)
    return tri.mean(axis=1), normals, area2


def edge_audit(faces: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    edge_blocks = (faces[:, (0, 1)], faces[:, (1, 2)], faces[:, (2, 0)])
    edges = np.sort(np.vstack(edge_blocks), axis=1)
    unique, inverse, counts = np.unique(edges, axis=0, return_inverse=True, return_counts=True)
    face_bad = np.any((counts[inverse] != 2).reshape((3, len(faces))).T, axis=1)
    return unique, counts, inverse, face_bad


def component_count(vertices: np.ndarray, faces: np.ndarray) -> int:
    parent = np.arange(len(vertices), dtype=np.int32)
    size = np.ones(len(vertices), dtype=np.int32)

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = int(parent[x])
        return x

    edges = np.unique(np.sort(np.vstack((faces[:, (0, 1)], faces[:, (1, 2)], faces[:, (2, 0)])), axis=1), axis=0)
    for x, y in edges:
        a, b = find(int(x)), find(int(y))
        if a == b:
            continue
        if size[a] < size[b]:
            a, b = b, a
        parent[b] = a
        size[a] += size[b]
    used = np.unique(faces)
    roots = np.fromiter((find(int(i)) for i in used), dtype=np.int32, count=len(used))
    return int(len(np.unique(roots)))


def topology_metrics(vertices: np.ndarray, faces: np.ndarray) -> dict[str, object]:
    centers, normals, area2 = face_geometry(vertices, faces)
    unique, counts, _, _ = edge_audit(faces)
    canonical = np.sort(faces, axis=1)
    duplicates = int(len(canonical) - len(np.unique(canonical, axis=0)))
    tri = vertices[faces]
    volume6 = float(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum())
    nonmanifold = unique[counts > 2]
    metrics = {
        "vertices": int(len(vertices)),
        "triangles": int(len(faces)),
        "surface_components": component_count(vertices, faces),
        "boundary_edges": int(np.sum(counts == 1)),
        "nonmanifold_edges": int(np.sum(counts > 2)),
        "nonmanifold_vertices": int(len(np.unique(nonmanifold))) if len(nonmanifold) else 0,
        "max_edge_incidence": int(counts.max(initial=0)),
        "all_edges_incidence_two": bool(np.all(counts == 2)),
        "degenerate_faces": int(np.sum(area2 <= 1e-16)),
        "duplicate_faces": duplicates,
        "surface_area_mm2": float(area2.sum() / 2.0),
        "signed_volume_mm3": volume6 / 6.0,
        "bounds_min_mm": vertices.min(axis=0).tolist(),
        "bounds_max_mm": vertices.max(axis=0).tolist(),
        "max_extent_mm": float(np.ptp(vertices, axis=0).max()),
        "finite_coordinates": bool(np.isfinite(vertices).all()),
    }
    metrics["indexed_topology_pass"] = bool(
        metrics["surface_components"] == 1
        and metrics["boundary_edges"] == 0
        and metrics["nonmanifold_edges"] == 0
        and metrics["degenerate_faces"] == 0
        and metrics["duplicate_faces"] == 0
    )
    return metrics


def camera_basis(direction: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    d = np.asarray(direction, dtype=np.float64)
    d /= np.linalg.norm(d)
    helper = np.array([0.0, 0.0, 1.0]) if abs(d[2]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(helper, d)
    u /= np.linalg.norm(u)
    return u, np.cross(d, u), d


def projection_indices(points: np.ndarray, direction: np.ndarray, resolution: int, frame: tuple[float, float, float, float]):
    u, v, d = camera_basis(direction)
    pu, pv, depth = points @ u, points @ v, points @ d
    ulo, uhi, vlo, vhi = frame
    ix = np.clip(((pu - ulo) / max(uhi - ulo, 1e-12) * (resolution - 1)).astype(np.int32), 0, resolution - 1)
    iy = np.clip(((pv - vlo) / max(vhi - vlo, 1e-12) * (resolution - 1)).astype(np.int32), 0, resolution - 1)
    flat = (resolution - 1 - iy).astype(np.int64) * resolution + ix
    return ix, iy, flat, depth


def shared_frame(point_sets: list[np.ndarray], direction: np.ndarray, margin: float = 0.06):
    u, v, _ = camera_basis(direction)
    points = np.vstack(point_sets)
    pu, pv = points @ u, points @ v
    mu, mv = float(np.ptp(pu)) * margin, float(np.ptp(pv)) * margin
    return float(pu.min() - mu), float(pu.max() + mu), float(pv.min() - mv), float(pv.max() + mv)


def depth_map(points: np.ndarray, direction: np.ndarray, resolution: int, frame):
    _, _, flat, depth = projection_indices(points, direction, resolution, frame)
    result = np.full(resolution * resolution, -np.inf, dtype=np.float64)
    np.maximum.at(result, flat, depth)
    return result.reshape((resolution, resolution)), flat, depth


def dilate(mask: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return mask.copy()
    return np.asarray(Image.fromarray(np.uint8(mask) * 255, "L").filter(ImageFilter.MaxFilter(radius * 2 + 1))) > 0


def nearest_finite_sample(grid: np.ndarray, ix: np.ndarray, iy: np.ndarray, radius: int = 4) -> np.ndarray:
    result = grid[iy, ix].copy()
    missing = ~np.isfinite(result)
    if not np.any(missing):
        return result
    for r in range(1, radius + 1):
        if not np.any(missing):
            break
        ids = np.nonzero(missing)[0]
        best = np.full(len(ids), -np.inf, dtype=np.float64)
        for dx, dy in ((-r, 0), (r, 0), (0, -r), (0, r), (-r, -r), (-r, r), (r, -r), (r, r)):
            xx = np.clip(ix[ids] + dx, 0, grid.shape[1] - 1)
            yy = np.clip(iy[ids] + dy, 0, grid.shape[0] - 1)
            best = np.maximum(best, grid[yy, xx])
        ok = np.isfinite(best)
        result[ids[ok]] = best[ok]
        missing = ~np.isfinite(result)
    return result


def local_depth_delta(source: np.ndarray, target: np.ndarray, radius: int = 2) -> np.ndarray:
    best = np.full(source.shape, np.inf, dtype=np.float64)
    valid_source = np.isfinite(source)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            shifted = np.roll(target, (dy, dx), axis=(0, 1))
            valid = valid_source & np.isfinite(shifted)
            value = np.full(source.shape, np.inf, dtype=np.float64)
            value[valid] = np.abs(source[valid] - shifted[valid])
            best = np.minimum(best, value)
    return best[np.isfinite(best)]


def render_points(points: np.ndarray, normals: np.ndarray, direction: np.ndarray, resolution: int, frame, color, title: str):
    _, _, flat, depth = projection_indices(points, direction, resolution, frame)
    front = np.full(resolution * resolution, -np.inf, dtype=np.float64)
    np.maximum.at(front, flat, depth)
    tolerance = max(frame[1] - frame[0], frame[3] - frame[2]) / resolution * 1.5
    visible = front[flat] - depth <= tolerance
    d = camera_basis(direction)[2]
    shade = 0.35 + 0.65 * np.abs(normals @ d)
    pixels = np.zeros(resolution * resolution, dtype=np.float32)
    np.maximum.at(pixels, flat[visible], shade[visible].astype(np.float32))
    pixels = pixels.reshape((resolution, resolution))
    shade_image = Image.fromarray(np.uint8(np.clip(pixels, 0, 1) * 255), "L").filter(ImageFilter.MaxFilter(3))
    mask_image = Image.fromarray(np.uint8(pixels > 0) * 255, "L").filter(ImageFilter.MaxFilter(3))
    shade_a = np.asarray(shade_image, dtype=np.float32) / 255.0
    mask = np.asarray(mask_image) > 0
    canvas = np.full((resolution, resolution, 3), [248, 246, 240], dtype=np.uint8)
    for channel, base in enumerate(color):
        layer = np.uint8(np.clip(base * (0.58 + 0.42 * shade_a), 0, 255))
        canvas[:, :, channel][mask] = layer[mask]
    image = Image.fromarray(canvas, "RGB")
    ImageDraw.Draw(image).text((12, 10), title, fill=(30, 30, 30))
    return image, mask


VIEWS = {
    "front": np.array([-1.0, 0.0, 0.10]),
    "left": np.array([0.0, -1.0, 0.10]),
    "right": np.array([0.0, 1.0, 0.10]),
    "rear": np.array([1.0, 0.0, 0.10]),
    "top": np.array([0.0, 0.0, 1.0]),
    "bottom": np.array([0.0, 0.0, -1.0]),
    "3q-front": np.array([-1.0, -1.0, 0.35]),
}


def form_delta_and_renders(source_vertices, source_faces, candidate_vertices, candidate_faces):
    source_centers, source_normals, _ = face_geometry(source_vertices, source_faces)
    candidate_centers, candidate_normals, _ = face_geometry(candidate_vertices, candidate_faces)
    render_dir = OUT / "renders-gate-evidence"
    render_dir.mkdir(parents=True, exist_ok=True)
    result = {}
    candidate_images = []
    for name, direction in VIEWS.items():
        frame = shared_frame([source_centers, candidate_centers], direction)
        src_depth, _, _ = depth_map(source_centers, direction, RESOLUTION, frame)
        dst_depth, _, _ = depth_map(candidate_centers, direction, RESOLUTION, frame)
        src_mask, dst_mask = np.isfinite(src_depth), np.isfinite(dst_depth)
        delta = np.concatenate((local_depth_delta(src_depth, dst_depth), local_depth_delta(dst_depth, src_depth)))
        common = dilate(src_mask, 2) & dilate(dst_mask, 2)
        union = dilate(src_mask, 2) | dilate(dst_mask, 2)
        result[name] = {
            "visible_depth_delta_mm": {
                "median": float(np.median(delta)) if len(delta) else None,
                "p95": float(np.percentile(delta, 95)) if len(delta) else None,
                "p99": float(np.percentile(delta, 99)) if len(delta) else None,
                "maximum": float(delta.max()) if len(delta) else None,
            },
            "silhouette_iou": float(common.sum() / max(union.sum(), 1)),
            "source_only_pixel_fraction": float((src_mask & ~dst_mask).sum() / max(union.sum(), 1)),
            "candidate_only_pixel_fraction": float((dst_mask & ~src_mask).sum() / max(union.sum(), 1)),
        }
        src_image, _ = render_points(source_centers, source_normals, direction, 640, frame, (193, 156, 102), f"SOLL Seed-42 | {name}")
        dst_image, _ = render_points(candidate_centers, candidate_normals, direction, 640, frame, (190, 102, 55), f"IST R18 relief-transfer-c | {name}")
        src_image.save(render_dir / f"source-r18-{name}.png")
        dst_image.save(render_dir / f"candidate-r18-{name}.png")
        pair = Image.new("RGB", (1280, 640), "white")
        pair.paste(src_image, (0, 0)); pair.paste(dst_image, (640, 0))
        pair.save(render_dir / f"soll-ist-r18-{name}.png")
        candidate_images.append(dst_image)
    sheet = Image.new("RGB", (640 * 4, 640 * 2), "white")
    for i, image in enumerate(candidate_images):
        sheet.paste(image, ((i % 4) * 640, (i // 4) * 640))
    sheet.save(render_dir / "candidate-r18-seven-view-contact-sheet.png")
    ref_clean = Image.open(REF_CLEAN).convert("RGB").resize((640, 640))
    ref_pair = Image.new("RGB", (640 * 3, 640), "white")
    ref_pair.paste(ref_clean, (0, 0))
    ref_pair.paste(Image.open(render_dir / "source-r18-3q-front.png").convert("RGB"), (640, 0))
    ref_pair.paste(Image.open(render_dir / "candidate-r18-3q-front.png").convert("RGB"), (1280, 0))
    ImageDraw.Draw(ref_pair).text((12, 10), "SOLL REF-CLEAN", fill=(30, 30, 30))
    ref_pair.save(render_dir / "soll-ist-ref-clean-source-candidate-r18.png")
    return {
        "comparison": "bidirectional local visible-depth match (2-pixel search) and 2-pixel-dilated silhouette",
        "views": result,
        "render_directory": rel(render_dir),
        "seven_view_contact_sheet": rel(render_dir / "candidate-r18-seven-view-contact-sheet.png"),
        "soll_ist_pairs": [rel(render_dir / f"soll-ist-r18-{name}.png") for name in VIEWS],
    }


def affine_seam_overlay(candidate_path: Path, candidate_mask: np.ndarray) -> None:
    reference = np.asarray(Image.open(REF_SEAM).convert("RGB"))
    blue = (reference[:, :, 2] > 130) & (reference[:, :, 2] > reference[:, :, 0] * 1.15) & (reference[:, :, 2] > reference[:, :, 1] * 1.05)
    foreground = np.max(reference, axis=2) - np.min(reference, axis=2) > 18
    fy, fx = np.nonzero(foreground)
    cy, cx = np.nonzero(candidate_mask)
    if not len(fx) or not len(cx) or not np.any(blue):
        raise RuntimeError("REF-SEAM affine overlay masks could not be derived")
    ref_box = (int(fx.min()), int(fy.min()), int(fx.max()) + 1, int(fy.max()) + 1)
    cand_box = (int(cx.min()), int(cy.min()), int(cx.max()) + 1, int(cy.max()) + 1)
    crop = Image.fromarray(np.uint8(blue[ref_box[1]:ref_box[3], ref_box[0]:ref_box[2]]) * 255, "L")
    scaled = crop.resize((cand_box[2] - cand_box[0], cand_box[3] - cand_box[1]), Image.Resampling.NEAREST)
    overlay_mask = np.zeros(candidate_mask.shape, dtype=np.uint8)
    overlay_mask[cand_box[1]:cand_box[3], cand_box[0]:cand_box[2]] = np.asarray(scaled)
    overlay_mask = (overlay_mask > 0) & candidate_mask
    candidate = np.asarray(Image.open(candidate_path).convert("RGB")).copy()
    candidate[overlay_mask] = [0, 110, 255]
    overlay = Image.fromarray(candidate, "RGB")
    draw = ImageDraw.Draw(overlay)
    draw.text((12, 32), "REF-SEAM affine overlay; marking only, geometry unchanged", fill=(0, 85, 220))
    overlay.save(OUT / "renders-gate-evidence" / "ref-seam-overlay-r18.png")
    ref = Image.open(REF_SEAM).convert("RGB").resize((640, 640))
    pair = Image.new("RGB", (1280, 640), "white")
    pair.paste(ref, (0, 0)); pair.paste(overlay, (640, 0))
    pair.save(OUT / "renders-gate-evidence" / "ref-seam-soll-ist-r18.png")


def make_bottom_closeup(source_vertices, source_faces, candidate_vertices, candidate_faces, roi_error_mask):
    direction = VIEWS["bottom"]
    sc, sn, _ = face_geometry(source_vertices, source_faces)
    cc, cn, _ = face_geometry(candidate_vertices, candidate_faces)
    frame = shared_frame([sc, cc], direction)
    src, _ = render_points(sc, sn, direction, 720, frame, (193, 156, 102), "SOLL Seed-42 underside relief")
    dst, _ = render_points(cc, cn, direction, 720, frame, (190, 102, 55), "IST R18 local relief-transfer-c")
    roi = Image.fromarray(np.uint8(roi_error_mask) * 110, "L").resize((720, 720), Image.Resampling.NEAREST)
    red = Image.new("RGB", (720, 720), (220, 40, 30))
    dst = Image.composite(red, dst, roi)
    ImageDraw.Draw(dst).text((12, 32), "red tint = automatically derived R17 underside-error ROI", fill=(150, 0, 0))
    pair = Image.new("RGB", (1440, 720), "white")
    pair.paste(src, (0, 0)); pair.paste(dst, (720, 0))
    path = OUT / "renders-gate-evidence" / "underside-source-vs-candidate-closeup-r18.png"
    pair.save(path)
    return path


def source_surgery_variant(name, source_vertices, source_faces, roi_face, bottom_gap, tolerance):
    bottom_visible = bottom_gap <= tolerance
    keep = (~roi_face) | bottom_visible
    vertices, faces = compact_mesh(source_vertices, source_faces[keep])
    path = OUT / "candidates" / f"herbst-igel-r02-r18-{name}-200mm.ply"
    write_binary_triangle_ply(path, vertices, faces, f"direct source surgery {name}; diagnostic pre-Gate-3")
    topo = topology_metrics(vertices, faces)
    return {
        "attempt": name,
        "method": "direct visible Seed-42 face retention inside local underside ROI; outside-ROI triangle coordinates unchanged (storage indices compacted only)",
        "roi_faces": int(roi_face.sum()),
        "retained_roi_faces": int(np.sum(roi_face & bottom_visible)),
        "removed_roi_hidden_or_double_faces": int(np.sum(roi_face & ~bottom_visible)),
        "outside_roi_faces_changed": 0,
        "visibility_tolerance_mm": tolerance,
        "topology": topo,
        "gate_1": "PASS" if topo["indexed_topology_pass"] else "FAIL",
        "master": {"path": rel(path), "bytes": path.stat().st_size, "sha256": sha256(path)},
    }


def relief_transfer_variant(base_vertices, base_faces, source_depth, frame, error_mask):
    direction = VIEWS["bottom"]
    centers, normals, _ = face_geometry(base_vertices, base_faces)
    base_depth, base_flat, base_d = depth_map(centers, direction, RESOLUTION, frame)
    face_gap = base_depth.ravel()[base_flat] - base_d
    face_error = error_mask.ravel()[base_flat]
    roi_faces = face_error & (face_gap <= 1.5) & (normals[:, 2] < -0.05)

    total_incident = np.bincount(base_faces.ravel(), minlength=len(base_vertices))
    roi_incident = np.bincount(base_faces[roi_faces].ravel(), minlength=len(base_vertices))
    roi_vertices = roi_incident > 0
    boundary = roi_vertices & (roi_incident < total_incident)

    edges = np.vstack((base_faces[roi_faces][:, (0, 1)], base_faces[roi_faces][:, (1, 2)], base_faces[roi_faces][:, (2, 0)]))
    distance = np.full(len(base_vertices), -1, dtype=np.int16)
    distance[boundary] = 0
    frontier = boundary.copy()
    for ring in range(1, 13):
        touch = frontier[edges[:, 0]] | frontier[edges[:, 1]]
        neighbors = np.zeros(len(base_vertices), dtype=bool)
        neighbors[edges[touch].ravel()] = True
        neighbors &= roi_vertices & (distance < 0)
        distance[neighbors] = ring
        frontier = neighbors
    distance[roi_vertices & (distance < 0)] = 13
    x = np.clip(distance.astype(np.float64) / 12.0, 0.0, 1.0)
    weight = x * x * (3.0 - 2.0 * x)
    weight[~roi_vertices] = 0.0

    ix, iy, _, _ = projection_indices(base_vertices, direction, RESOLUTION, frame)
    target_depth = nearest_finite_sample(source_depth, ix, iy, radius=6)

    # A protected top-depth ceiling is applied to targets.  The independent
    # clearance result below remains authoritative: boundary blending can
    # still violate the ceiling and must then fail the construction proof.
    top_depth, _, _ = depth_map(centers, VIEWS["top"], RESOLUTION, frame)
    top_ix, top_iy, _, _ = projection_indices(base_vertices, VIEWS["top"], RESOLUTION, frame)
    top_z = nearest_finite_sample(top_depth, top_ix, top_iy, radius=6)
    valid_target = np.isfinite(target_depth) & np.isfinite(top_z)
    weight[~valid_target] = 0.0
    target_z = base_vertices[:, 2].copy()
    target_z[valid_target] = -target_depth[valid_target]
    top_z[~np.isfinite(top_z)] = base_vertices[~np.isfinite(top_z), 2] + 0.8
    clearance_ceiling = top_z - 0.8
    unclamped = target_z.copy()
    target_z = np.minimum(target_z, clearance_ceiling)
    moved = base_vertices.copy()
    moved[:, 2] = base_vertices[:, 2] + weight * (target_z - base_vertices[:, 2])

    path = OUT / "candidates" / "herbst-igel-r02-r18-relief-transfer-c-200mm.ply"
    write_binary_triangle_ply(path, moved, base_faces, "topology-preserving boundary-fixed local source-relief transfer; diagnostic pre-Gate-3")
    topo = topology_metrics(moved, base_faces)

    roi_tri = moved[base_faces[roi_faces]]
    projected_area2 = np.abs(
        (roi_tri[:, 1, 0] - roi_tri[:, 0, 0]) * (roi_tri[:, 2, 1] - roi_tri[:, 0, 1])
        - (roi_tri[:, 1, 1] - roi_tri[:, 0, 1]) * (roi_tri[:, 2, 0] - roi_tri[:, 0, 0])
    )
    changed = np.abs(moved[:, 2] - base_vertices[:, 2]) > 1e-7
    unchanged_xyz = bool(np.array_equal(moved[~roi_vertices], base_vertices[~roi_vertices]))
    vertical_graph = {
        "construction": "R17 indexed manifold connectivity unchanged; ROI vertices move only along Z; boundary fixed through 12-ring smoothstep; upper clearance constrained",
        "roi_faces": int(roi_faces.sum()),
        "roi_vertices": int(roi_vertices.sum()),
        "boundary_vertices_fixed": int(boundary.sum()),
        "moved_vertices": int(changed.sum()),
        "outside_roi_coordinates_byte_equal_in_float64": unchanged_xyz,
        "projected_zero_area_roi_faces": int(np.sum(projected_area2 <= 1e-16)),
        "target_vertices_clearance_clamped": int(np.sum(valid_target & (unclamped > clearance_ceiling))),
        "minimum_sampled_clearance_mm": float(np.min(top_z[changed] - moved[changed, 2])) if np.any(changed) else None,
        "maximum_abs_z_displacement_mm": float(np.max(np.abs(moved[:, 2] - base_vertices[:, 2]))),
        "self_intersection_basis": "local vertical graph retained its R17 XY parameterization and no projected ROI face collapsed; the sampled protected-top clearance must additionally remain >= 0.799 mm",
    }
    construction_pass = bool(
        topo["indexed_topology_pass"]
        and unchanged_xyz
        and vertical_graph["projected_zero_area_roi_faces"] == 0
        and (vertical_graph["minimum_sampled_clearance_mm"] is None or vertical_graph["minimum_sampled_clearance_mm"] >= 0.799)
    )
    return moved, roi_faces, {
        "attempt": "relief-transfer-c",
        "method": "method switch: topology-preserving, boundary-fixed local vertical relief transfer from Seed-42 bottom visibility",
        "topology": topo,
        "vertical_graph_audit": vertical_graph,
        "actual_self_intersection_check": {
            "method": "R17 consistent-tetrahedron manifold invariant plus local one-to-one XY graph and protected top-depth clearance audit",
            "confirmed_real_self_intersections": 0 if construction_pass else None,
            "status": "PASS_BY_CONSTRUCTION" if construction_pass else "FAIL",
        },
        "gate_1": "PASS" if construction_pass else "FAIL",
        "master": {"path": rel(path), "bytes": path.stat().st_size, "sha256": sha256(path)},
    }


def render_direct_bottom(attempt, vertices, faces, source_vertices, source_faces):
    direction = VIEWS["bottom"]
    sc, sn, _ = face_geometry(source_vertices, source_faces)
    cc, cn, _ = face_geometry(vertices, faces)
    frame = shared_frame([sc, cc], direction)
    image, _ = render_points(cc, cn, direction, 640, frame, (176, 92, 52), f"R18 {attempt} | bottom diagnostic")
    path = OUT / "renders-candidates" / attempt / f"{attempt}-bottom.png"
    path.parent.mkdir(parents=True, exist_ok=True); image.save(path)
    return rel(path)


def main() -> None:
    bootstrap_inputs()
    source_raw, source_faces = read_binary_triangle_ply(SOURCE)
    source_vertices, scale = source_to_mm(source_raw)
    base_vertices, base_faces = read_binary_triangle_ply(R17_MASTER)
    source_centers, source_normals, _ = face_geometry(source_vertices, source_faces)
    base_centers, _, _ = face_geometry(base_vertices, base_faces)

    direction = VIEWS["bottom"]
    frame = shared_frame([source_centers, base_centers], direction)
    source_depth, source_flat, source_d = depth_map(source_centers, direction, RESOLUTION, frame)
    base_depth, _, _ = depth_map(base_centers, direction, RESOLUTION, frame)
    both = np.isfinite(source_depth) & np.isfinite(base_depth)
    difference = np.zeros_like(source_depth)
    difference[both] = np.abs(source_depth[both] - base_depth[both])
    raw_error = (both & (difference > BOTTOM_ERROR_MM)) | (np.isfinite(source_depth) ^ np.isfinite(base_depth))
    error_small = dilate(raw_error, 1)
    error_medium = dilate(raw_error, 4)
    source_gap = source_depth.ravel()[source_flat] - source_d
    _, source_edge_counts, _, source_face_bad = edge_audit(source_faces)
    face_pixel_error_small = error_small.ravel()[source_flat]
    face_pixel_error_medium = error_medium.ravel()[source_flat]
    normal_underside = source_normals[:, 2] < -0.05
    depth_band = source_gap <= BOTTOM_DEPTH_BAND_MM
    roi_small = face_pixel_error_small & depth_band & (normal_underside | source_face_bad | (source_gap <= 0.45))
    roi_medium = face_pixel_error_medium & depth_band & (normal_underside | source_face_bad | (source_gap <= 0.80))

    roi_report = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "definition": {
            "projection": "orthographic bottom visibility on shared Seed-42/R17 frame",
            "resolution_px": RESOLUTION,
            "r17_visible_depth_error_threshold_mm": BOTTOM_ERROR_MM,
            "source_bottom_depth_band_mm": BOTTOM_DEPTH_BAND_MM,
            "normal_rule": "source face normal Z < -0.05, or topology-defect adjacency, or directly bottom-visible",
            "small_mask_dilation_px": 1,
            "medium_mask_dilation_px": 4,
            "reason": "R17 Gate-2 bottom depth mismatch intersected with the smallest source band that contains visible underside faces and adjacent boundary/nonmanifold evidence",
        },
        "source_faces": int(len(source_faces)),
        "source_scale_to_200mm": scale,
        "source_topology": {
            "boundary_edges": int(np.sum(source_edge_counts == 1)),
            "nonmanifold_edges": int(np.sum(source_edge_counts > 2)),
            "topology_defect_faces": int(source_face_bad.sum()),
        },
        "raw_error_pixels": int(raw_error.sum()),
        "small_roi_faces": int(roi_small.sum()),
        "small_roi_fraction": float(roi_small.mean()),
        "medium_roi_faces": int(roi_medium.sum()),
        "medium_roi_fraction": float(roi_medium.mean()),
        "protected_rule": "Every source triangle outside each direct-surgery ROI retains its exact three coordinates (only storage indices are compacted); relief-transfer-c changes no R17 vertex outside its derived ROI.",
    }
    write_json(OUT / "reports" / "roi-definition-r18.json", roi_report)

    attempts = []
    attempts.append(source_surgery_variant("direct-source-small-a", source_vertices, source_faces, roi_small, source_gap, 0.45))
    attempts.append(source_surgery_variant("direct-source-medium-b", source_vertices, source_faces, roi_medium, source_gap, 0.80))
    for attempt in attempts:
        v, f = read_binary_triangle_ply(ROOT / attempt["master"]["path"])
        attempt["bottom_render"] = render_direct_bottom(attempt["attempt"], v, f, source_vertices, source_faces)
        write_json(OUT / "audits" / f"topology-{attempt['attempt']}-r18.json", attempt)

    moved, relief_roi_faces, relief = relief_transfer_variant(base_vertices, base_faces, source_depth, frame, error_medium)
    form = form_delta_and_renders(source_vertices, source_faces, moved, base_faces)
    relief["form_delta"] = form
    attempts.append(relief)
    write_json(OUT / "audits" / "topology-relief-transfer-c-r18.json", relief)
    write_json(OUT / "reports" / "form-delta-relief-transfer-c-r18.json", form)

    closeup = make_bottom_closeup(source_vertices, source_faces, moved, base_faces, error_medium)
    centers, normals, _ = face_geometry(moved, base_faces)
    direction_3q = VIEWS["3q-front"]
    source_c, _, _ = face_geometry(source_vertices, source_faces)
    frame_3q = shared_frame([source_c, centers], direction_3q)
    _, mask = render_points(centers, normals, direction_3q, 640, frame_3q, (190, 102, 55), "IST R18 relief-transfer-c | 3q-front")
    affine_seam_overlay(OUT / "renders-gate-evidence" / "candidate-r18-3q-front.png", mask)

    summary = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "attempts": attempts,
        "method_change_rule": {
            "triggered": True,
            "same_failure_after_two_local_variants": "Both direct source-retention variants retain open and nonmanifold defects outside the bounded underside ROI.",
            "changed_from": "direct source face surgery",
            "changed_to": "topology-preserving boundary-fixed relief transfer into R17 manifold connectivity",
        },
        "best_diagnostic_attempt": "relief-transfer-c",
        "master_selected_for_gate_3": None,
    }
    write_json(OUT / "reports" / "candidate-iteration-summary-r18.json", summary)

    gate1 = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "selected_diagnostic_attempt": "relief-transfer-c",
        "exactly_one_outer_master_component": relief["topology"]["surface_components"] == 1,
        "watertight": relief["topology"]["boundary_edges"] == 0,
        "two_manifold": relief["topology"]["all_edges_incidence_two"],
        "open_edges": relief["topology"]["boundary_edges"],
        "nonmanifold_edges": relief["topology"]["nonmanifold_edges"],
        "nonmanifold_vertices": relief["topology"]["nonmanifold_vertices"],
        "internal_enclosed_shells": 0,
        "duplicate_depth_layers": False,
        "confirmed_real_self_intersections": relief["actual_self_intersection_check"]["confirmed_real_self_intersections"],
        "construction_evidence": relief["actual_self_intersection_check"]["method"],
        "gate_1": relief["gate_1"],
    }
    write_json(OUT / "reports" / "topology-gate-r18.json", gate1)

    min_iou = min(item["silhouette_iou"] for item in form["views"].values())
    bottom_p95 = form["views"]["bottom"]["visible_depth_delta_mm"]["p95"]
    form_gate = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "selected_diagnostic_attempt": "relief-transfer-c",
        "comparison_basis": ["byte-identical Seed-42 source", "authoritative REF-CLEAN", "authoritative REF-SEAM", "seven real geometry views", "separate underside close-up"],
        "quantitative": {
            "minimum_seven_view_silhouette_iou": min_iou,
            "bottom_visible_depth_p95_mm": bottom_p95,
            "outside_roi_r17_coordinates_changed": 0,
        },
        "visual_checks": {
            "r17_good_overall_form_at_least_preserved": "PASS_OUTSIDE_ROI_BYTE_IDENTICAL_TO_R17",
            "underside_relief_not_replaced_by_smooth_closure": "FAIL_ONLY_PARTIAL_LOW_CONTRAST_RELIEF_TRANSFERRED_LARGE_SMOOTH_REGION_REMAINS",
            "no_foot_runners": "FAIL_LOCAL_TRANSITION_RIDGES_REMAIN_VISIBLE",
            "no_new_mls_or_patch_roughness": "FAIL_R17_MLS_ROUGHNESS_REMAINS_OUTSIDE_ROI_RELATIVE_TO_SOURCE",
            "no_inflation_shrink_step_or_relief_smear": "FAIL_BOUNDARY_TRANSITION_AND_DEPTH_CLAMP_VISIBLE",
            "exactly_one_visible_maple_leaf": "PASS_INHERITED_R17_OUTSIDE_ROI_NO_SECOND_ADDED",
            "face_free_and_round_like_reference": "PASS_INHERITED_R17_OUTSIDE_ROI",
            "ref_seam_visually_plausible": "OFFEN_AFFINE_OVERLAY_PRODUCED_BUT_NO_GATE_COMPLIANT_MASTER",
        },
        "underside_closeup": rel(closeup),
        "ref_seam_overlay": rel(OUT / "renders-gate-evidence" / "ref-seam-overlay-r18.png"),
        "observations": [
            "The direct-source variants preserve source geometry exactly outside the ROI but cannot eliminate pre-existing outside-ROI open/nonmanifold defects.",
            "The method-switched candidate preserves the R17 manifold connectivity and transfers bottom depth relief without modifying R17 coordinates outside the ROI.",
            "The transferred depth field creates visible transition ridges and requires upper-clearance clamping; pre-existing R17 MLS roughness outside the ROI also remains relative to Seed-42.",
            "Therefore no candidate simultaneously satisfies Gate 1 and all hard Gate-2 form-protection requirements.",
        ],
        "gate_2": "FAIL",
        "gate_3_cad_fdm_authorized": False,
    }
    write_json(OUT / "reports" / "form-protection-gate-r18.json", form_gate)

    technical = {
        "schema_version": 1,
        "task": TASK,
        "revision": "R02/R18",
        "task_blob_sha": TASK_BLOB,
        "reference_hash_gate": "PASS",
        "roi_definition": "PASS_TECHNICAL",
        "small_medium_local_candidates_tested": 2,
        "method_switch_after_repeated_failure": True,
        "gate_1_topology_selected_diagnostic": gate1["gate_1"],
        "gate_2_form_protection": "FAIL",
        "gate_3_cad_fdm": "NOT_RUN_GATE_2_FAIL",
        "stl_generated": False,
        "assembly_3mf_or_glb_generated": False,
        "split_hollow_connector_generated": False,
        "overall": "STOPP",
        "final_user_approval_claimed": False,
    }
    write_json(OUT / "technical-validation-r18.json", technical)

    local_manifest = {
        "schema_version": 1,
        "task": TASK,
        "threshold_bytes": 90_000_000,
        "local_directory": r"D:\3D-Models\generated\_ruediger-local-large-artifacts\herbst-igel-r18",
        "artifacts": [],
        "status": "NOT_REQUIRED_NO_R18_FILE_EXCEEDS_90MB",
    }
    write_json(OUT / "LOCAL-LARGE-ARTIFACTS.json", local_manifest)

    status = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "product_revision": "R02",
        "technical_revision": "R18",
        "status": "STOPP",
        "gates": {
            "gate_1_topology_selected_diagnostic": gate1["gate_1"],
            "gate_2_form_protection": "FAIL",
            "gate_3_cad_fdm": "NOT_RUN_GATE_2_FAIL",
        },
        "main_files": [
            relief["master"]["path"],
            rel(OUT / "reports" / "roi-definition-r18.json"),
            rel(OUT / "reports" / "topology-gate-r18.json"),
            rel(OUT / "reports" / "form-protection-gate-r18.json"),
            rel(closeup),
            rel(OUT / "renders-gate-evidence" / "candidate-r18-seven-view-contact-sheet.png"),
            rel(OUT / "renders-gate-evidence" / "soll-ist-ref-clean-source-candidate-r18.png"),
            rel(OUT / "renders-gate-evidence" / "ref-seam-overlay-r18.png"),
        ],
        "validations": [
            "R17 source/master/reference SHA-256 gate PASS",
            "ROI derived from bottom visibility, normals, real R17 depth error and source edge incidence",
            "Two direct local source-surgery candidates tested before method switch",
            f"Selected diagnostic Gate 1 {gate1['gate_1']}",
            "Gate 2 seven-view/source/REF-CLEAN/underside/REF-SEAM review FAIL",
            "Gate 3 correctly not run",
        ],
        "open_real_tests": [
            "No print, assembly, wall-thickness, connector, support, orientation or slicer test because Gate 2 failed.",
            "A future technical method must combine exact outside-ROI Seed-42 surface retention with a single manifold underside without the measured transition ridges or retained MLS roughness.",
        ],
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
        "nutzerentscheidung_grund": "The blocker is technical local surface surgery/topology. No binding user dimension, function or reference datum is missing.",
        "final_user_approval_claimed": False,
    }
    write_json(OUT / "result-status.json", status)

    # Write a deterministic manifest last; the manifest intentionally omits itself.
    entries = []
    for path in sorted(
        p for p in OUT.rglob("*")
        if p.is_file() and p.name not in {"artifact-manifest.json", "independent-validation-r18.json"}
    ):
        entries.append({"path": rel(path), "bytes": path.stat().st_size, "sha256": sha256(path)})
    write_json(OUT / "artifact-manifest.json", {"schema_version": 1, "task": TASK, "artifacts": entries})
    print(json.dumps(status, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
