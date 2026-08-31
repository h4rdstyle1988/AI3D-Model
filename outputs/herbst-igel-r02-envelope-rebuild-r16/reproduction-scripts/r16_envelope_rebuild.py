"""Deterministic six-depth-map voxel-envelope rebuild for Herbst-Igel R16.

Standalone readable source using only NumPy and Pillow. It validates the
authorized hashes, intersects three pairs of exterior depth intervals, closes
and repairs the voxel volume, and emits exposed cell faces only. Hidden source
sheets are never copied. Split/hollow/connector/STL work is intentionally not
part of this pre-Gate-2 script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "outputs" / "herbst-igel-r02-envelope-rebuild-r16"
SOURCE = OUT / "inputs" / "seed42-optically-best-source.ply"
REF_CLEAN = OUT / "reference-audit" / "ref-clean-r16.jpg"
REF_SEAM = OUT / "reference-audit" / "ref-seam-r16.jpg"
TASK = "tasks/TASK-HERBST-IGEL-R02-ENVELOPE-REBUILD-R16.md"
TASK_BLOB = "5d2d6ab9d3d2cb522e65e8a1de57dddc3e872e62"
EXPECTED = {
    "seed42": "85ba18eaed15bdbe631fc49dd571e73882c4055e2c247022e90ad15ed99822c6",
    "ref_clean": "c1c9a5a094f1db2fd220f3433f83af8dedca780f56a4bf479eb8883432250859",
    "ref_seam": "b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def hash_gate() -> dict[str, object]:
    actual = {"seed42": sha256(SOURCE), "ref_clean": sha256(REF_CLEAN), "ref_seam": sha256(REF_SEAM)}
    report = {"schema_version": 1, "task": TASK, "task_blob_sha": TASK_BLOB,
              "expected": EXPECTED, "actual": actual,
              "status": "PASS" if actual == EXPECTED else "FAIL"}
    write_json(OUT / "reference-audit" / "hash-gate-r16-source.json", report)
    if report["status"] != "PASS":
        raise RuntimeError(f"R16 hash gate failed: {actual}")
    return report


def read_binary_triangle_ply(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with path.open("rb") as stream:
        header = []
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
        vertices = np.frombuffer(stream.read(nv * 12), dtype="<f4", count=nv * 3).reshape((-1, 3)).astype(np.float64)
        dtype = np.dtype([("count", "u1"), ("index", "<i4", (3,))])
        records = np.frombuffer(stream.read(nf * dtype.itemsize), dtype=dtype, count=nf)
        if not np.all(records["count"] == 3):
            raise ValueError("R16 requires triangular faces")
        return vertices, records["index"].astype(np.int32, copy=True)


def write_binary_triangle_ply(path: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = ("ply\nformat binary_little_endian 1.0\n"
              f"comment {TASK} {TASK_BLOB}\n"
              "comment units millimetres; maximum extent exactly 200.0 mm\n"
              f"element vertex {len(vertices)}\nproperty float x\nproperty float y\nproperty float z\n"
              f"element face {len(faces)}\nproperty list uchar int vertex_indices\nend_header\n").encode("ascii")
    dtype = np.dtype([("count", "u1"), ("index", "<i4", (3,))])
    records = np.empty(len(faces), dtype=dtype)
    records["count"] = 3
    records["index"] = faces.astype("<i4", copy=False)
    with path.open("wb") as stream:
        stream.write(header)
        stream.write(vertices.astype("<f4", copy=False).tobytes())
        stream.write(records.tobytes())


def make_edges(vertices: np.ndarray, pitch: float):
    low, high = vertices.min(axis=0), vertices.max(axis=0)
    counts = np.ceil((high - low) / pitch).astype(int) + 1
    edges = [np.linspace(low[a] - pitch / 2, high[a] + pitch / 2, counts[a] + 1) for a in range(3)]
    actual = [float(x[1] - x[0]) for x in edges]
    scale = 200.0 / float((high - low).max())
    return edges, {"requested_pitch_normalized": pitch,
                   "shape_cells": counts.astype(int).tolist(),
                   "actual_pitch_normalized": actual,
                   "actual_pitch_mm": [x * scale for x in actual],
                   "source_to_200mm_scale": scale}


def flood_outside(background: np.ndarray) -> np.ndarray:
    outside = np.zeros_like(background, dtype=bool)
    queue: deque[tuple[int, int]] = deque()
    h, w = background.shape
    for y in range(h):
        for x in (0, w - 1):
            if background[y, x] and not outside[y, x]: outside[y, x] = True; queue.append((y, x))
    for x in range(w):
        for y in (0, h - 1):
            if background[y, x] and not outside[y, x]: outside[y, x] = True; queue.append((y, x))
    while queue:
        y, x = queue.popleft()
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < h and 0 <= nx < w and background[ny, nx] and not outside[ny, nx]:
                outside[ny, nx] = True; queue.append((ny, nx))
    return outside


def projection_interval(points, a_edges, b_edges, a_axis, b_axis, depth_axis):
    shape = (len(a_edges) - 1, len(b_edges) - 1)
    lo, hi = np.full(shape, np.inf), np.full(shape, -np.inf)
    ia = np.clip(np.searchsorted(a_edges, points[:, a_axis]) - 1, 0, shape[0] - 1)
    ib = np.clip(np.searchsorted(b_edges, points[:, b_axis]) - 1, 0, shape[1] - 1)
    flat = ia * shape[1] + ib
    np.minimum.at(lo.ravel(), flat, points[:, depth_axis]); np.maximum.at(hi.ravel(), flat, points[:, depth_axis])
    observed = np.isfinite(lo)
    image = Image.fromarray((observed * 255).astype(np.uint8))
    closed = np.asarray(image.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))) > 0
    target, known = closed | (~flood_outside(~closed)), observed.copy()
    before = int(known.sum())
    while np.any(target & ~known):
        count = np.zeros(shape, np.uint8); lo_sum = np.zeros(shape); hi_sum = np.zeros(shape)
        pairs = (((slice(None, -1), slice(None)), (slice(1, None), slice(None))),
                 ((slice(1, None), slice(None)), (slice(None, -1), slice(None))),
                 ((slice(None), slice(None, -1)), (slice(None), slice(1, None))),
                 ((slice(None), slice(1, None)), (slice(None), slice(None, -1))))
        for source, dest in pairs:
            valid = known[source]; count[dest] += valid
            lo_sum[dest] += np.where(valid, lo[source], 0.0); hi_sum[dest] += np.where(valid, hi[source], 0.0)
        update = target & ~known & (count > 0)
        if not np.any(update): raise RuntimeError("Projection depth propagation did not converge")
        lo[update] = lo_sum[update] / count[update]; hi[update] = hi_sum[update] / count[update]; known[update] = True
    return lo, hi, target, {"observed_nodes": before, "closed_and_hole_filled_nodes": int(target.sum()),
                            "interpolated_nodes": int((target & ~observed).sum())}


def build_intervals(vertices, faces, edges):
    points = np.vstack((vertices, vertices[faces].mean(axis=1)))
    x, y, z = edges
    return {"yz_to_x": projection_interval(points, y, z, 1, 2, 0),
            "xz_to_y": projection_interval(points, x, z, 0, 2, 1),
            "xy_to_z": projection_interval(points, x, y, 0, 1, 2)}


def shift_or(v):
    r = v.copy(); r[1:] |= v[:-1]; r[:-1] |= v[1:]; r[:, 1:] |= v[:, :-1]; r[:, :-1] |= v[:, 1:]
    r[:, :, 1:] |= v[:, :, :-1]; r[:, :, :-1] |= v[:, :, 1:]; return r


def shift_and(v):
    r = v.copy(); r[1:] &= v[:-1]; r[:-1] &= v[1:]; r[:, 1:] &= v[:, :-1]; r[:, :-1] &= v[:, 1:]
    r[:, :, 1:] &= v[:, :, :-1]; r[:, :, :-1] &= v[:, :, 1:]
    r[[0, -1]] = False; r[:, [0, -1]] = False; r[:, :, [0, -1]] = False; return r


def component_count(bits: int) -> int:
    unseen = {i for i in range(8) if bits & (1 << i)}; count = 0
    while unseen:
        count += 1; stack = [unseen.pop()]
        while stack:
            n = stack.pop(); xyz = ((n >> 2) & 1, (n >> 1) & 1, n & 1)
            for other in list(unseen):
                oxyz = ((other >> 2) & 1, (other >> 1) & 1, other & 1)
                if sum(abs(a - b) for a, b in zip(xyz, oxyz)) == 1: unseen.remove(other); stack.append(other)
    return count


REPAIR_LUT = np.array([255 if component_count(code) > 1 else code for code in range(256)], np.uint8)


def repair_blocks(volume, limit=6):
    total = repaired = 0
    for iteration in range(1, limit + 1):
        code = np.zeros(np.array(volume.shape) - 1, np.uint8); bit = 0
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    code |= volume[dx:volume.shape[0]-1+dx, dy:volume.shape[1]-1+dy, dz:volume.shape[2]-1+dz].astype(np.uint8) << bit; bit += 1
        target, changed = REPAIR_LUT[code], REPAIR_LUT[code] != code
        if not np.any(changed): break
        repaired += int(changed.sum()); before = int(volume.sum()); bit = 0
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    volume[dx:volume.shape[0]-1+dx, dy:volume.shape[1]-1+dy, dz:volume.shape[2]-1+dz] |= changed & ((target & (1 << bit)) != 0); bit += 1
        total += int(volume.sum()) - before
    return volume, {"well_composed_blocks_repaired": repaired,
                    "voxels_added_as_topology_microcorrection": total, "repair_iterations": iteration}


def build_solid(edges, intervals, close_radius):
    xc, yc, zc = [(x[:-1] + x[1:]) / 2 for x in edges]
    solid = np.zeros((len(xc), len(yc), len(zc)), bool)
    xlo, xhi, xm, _ = intervals["yz_to_x"]; ylo, yhi, ym, _ = intervals["xz_to_y"]; zlo, zhi, zm, _ = intervals["xy_to_z"]
    for k, zv in enumerate(zc):
        ix = xm[:, k][None, :] & (xc[:, None] >= xlo[:, k][None, :]) & (xc[:, None] <= xhi[:, k][None, :])
        iy = ym[:, k][:, None] & (yc[None, :] >= ylo[:, k][:, None]) & (yc[None, :] <= yhi[:, k][:, None])
        solid[:, :, k] = ix & iy & zm & (zv >= zlo) & (zv <= zhi)
    initial = int(solid.sum()); before = initial
    dilated = solid
    for _ in range(close_radius): dilated = shift_or(dilated)
    after_dilate = int(dilated.sum()); solid = dilated
    for _ in range(close_radius): solid = shift_and(solid)
    closing = {"closing_radius_voxels": close_radius, "voxels_added": after_dilate - before,
               "voxels_removed": after_dilate - int(solid.sum()), "net_voxel_change": int(solid.sum()) - before}
    solid, repair = repair_blocks(solid)
    return solid, {"initial_occupied_voxels": initial, "volumetric_micro_closing": closing,
                   "final_occupied_voxels": int(solid.sum()), **repair}


def cubical_boundary(edges, solid):
    nx, ny, nz = solid.shape; ny1, nz1 = ny + 1, nz + 1; chunks = []; exposed = {x: 0 for x in ("-x", "+x", "-y", "+y", "-z", "+z")}
    def corner(i, j, k): return ((i * ny1 + j) * nz1 + k).astype(np.int64)
    def add(mask, d):
        i, j, k = np.nonzero(mask)
        if not len(i): return
        if d == "-x": q = [corner(i,j,k),corner(i,j,k+1),corner(i,j+1,k+1),corner(i,j+1,k)]
        elif d == "+x": q = [corner(i+1,j,k),corner(i+1,j+1,k),corner(i+1,j+1,k+1),corner(i+1,j,k+1)]
        elif d == "-y": q = [corner(i,j,k),corner(i+1,j,k),corner(i+1,j,k+1),corner(i,j,k+1)]
        elif d == "+y": q = [corner(i,j+1,k),corner(i,j+1,k+1),corner(i+1,j+1,k+1),corner(i+1,j+1,k)]
        elif d == "-z": q = [corner(i,j,k),corner(i,j+1,k),corner(i+1,j+1,k),corner(i+1,j,k)]
        else: q = [corner(i,j,k+1),corner(i+1,j,k+1),corner(i+1,j+1,k+1),corner(i,j+1,k+1)]
        q = np.stack(q, axis=1); chunks.extend((q[:, (0,1,2)], q[:, (0,2,3)])); exposed[d] += len(i)
    n = np.zeros_like(solid); n[1:] = solid[:-1]; add(solid & ~n, "-x")
    n.fill(False); n[:-1] = solid[1:]; add(solid & ~n, "+x")
    n.fill(False); n[:,1:] = solid[:,:-1]; add(solid & ~n, "-y")
    n.fill(False); n[:,:-1] = solid[:,1:]; add(solid & ~n, "+y")
    n.fill(False); n[:,:,1:] = solid[:,:,:-1]; add(solid & ~n, "-z")
    n.fill(False); n[:,:,:-1] = solid[:,:,1:]; add(solid & ~n, "+z")
    gf = np.concatenate(chunks); used, inverse = np.unique(gf, return_inverse=True); faces = inverse.reshape((-1,3)).astype(np.int32)
    k = used % nz1; tmp = used // nz1; j = tmp % ny1; i = tmp // ny1
    vertices = np.column_stack((edges[0][i], edges[1][j], edges[2][k]))
    return vertices, faces, {"occupied_voxels": int(solid.sum()), "exposed_quads": exposed}


def mesh_metrics(vertices, faces):
    tri = vertices[faces]; area2 = np.linalg.norm(np.cross(tri[:,1]-tri[:,0], tri[:,2]-tri[:,0]), axis=1)
    edges = np.sort(np.vstack((faces[:,(0,1)],faces[:,(1,2)],faces[:,(2,0)])), axis=1); _, counts = np.unique(edges, axis=0, return_counts=True)
    canonical = np.sort(faces, axis=1); duplicates = len(canonical) - len(np.unique(canonical, axis=0))
    volume6 = np.einsum("ij,ij->i", tri[:,0], np.cross(tri[:,1],tri[:,2])).sum()
    return {"vertices": len(vertices), "triangles": len(faces), "boundary_edges": int((counts==1).sum()),
            "nonmanifold_edges": int((counts>2).sum()), "max_edge_incidence": int(counts.max(initial=0)),
            "all_edges_incidence_two": bool(np.all(counts==2)), "degenerate_faces": int((area2<=1e-18).sum()),
            "duplicate_faces": int(duplicates), "surface_area_normalized2": float(area2.sum()/2),
            "signed_volume_normalized3": float(volume6/6), "orientable_outward": bool(volume6>0),
            "bounds_min": vertices.min(axis=0).tolist(), "bounds_max": vertices.max(axis=0).tolist()}


def build_attempt(slug, pitch, close_radius, vertices, faces):
    edges, grid = make_edges(vertices, pitch); print(f"R16 {slug}: grid {grid['shape_cells']}", flush=True)
    intervals = build_intervals(vertices, faces, edges); projection = {k: v[3] for k, v in intervals.items()}
    solid, repair = build_solid(edges, intervals, close_radius); mv, mf, construction = cubical_boundary(edges, solid); metrics = mesh_metrics(mv, mf)
    master = OUT / "masterform-source-rebuild" / f"herbst-igel-r02-r16-{slug}-200mm.ply"
    write_binary_triangle_ply(master, mv * grid["source_to_200mm_scale"], mf)
    passed = metrics["all_edges_incidence_two"] and metrics["degenerate_faces"] == 0 and metrics["duplicate_faces"] == 0 and metrics["orientable_outward"]
    report = {"schema_version":1,"task":TASK,"task_blob_sha":TASK_BLOB,"attempt":slug,
              "method":"six-depth-map three-axis Boolean visual envelope; exposed cubical boundary only",
              "grid":grid,"projection_fill":projection,"well_composed_repair":repair,"construction":construction,"topology":metrics,
              "actual_self_intersection_check":{"method":"cubical-complex construction plus exhaustive edge/duplicate-face checks",
              "tested_exposed_quads":int(sum(construction["exposed_quads"].values())),"confirmed_self_intersections":0 if passed else None,"status":"PASS" if passed else "FAIL"},
              "status":"PASS" if passed else "FAIL","master":{"path":master.relative_to(ROOT).as_posix(),"sha256":sha256(master),"bytes":master.stat().st_size}}
    write_json(OUT / "audits-source-rebuild" / f"topology-{slug}.json", report); return report


def verify_existing():
    hash_gate()
    required = [OUT/"masterform"/"herbst-igel-r02-r16-envelope-master-200mm.ply", OUT/"audits"/"topology-envelope-fine-b-r16.json",
                OUT/"reports"/"form-protection-gate-r16.json", OUT/"renders-gate-evidence"/"envelope-r16-contact-sheet.png",
                OUT/"renders-gate-evidence"/"soll-ist-r16.png", OUT/"result-status.json"]
    missing = [str(x) for x in required if not x.is_file()]
    if missing: raise FileNotFoundError("Missing R16 evidence: " + ", ".join(missing))
    topology = json.loads(required[1].read_text(encoding="utf-8")); status = json.loads(required[-1].read_text(encoding="utf-8"))
    if topology["status"] != "PASS" or status["status"] != "STOPP": raise RuntimeError("Existing R16 gate state mismatch")
    print("R16 existing artifact/hash/status verification: PASS")


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--coarse-pitch",type=float,default=.0014); parser.add_argument("--fine-pitch",type=float,default=.001)
    parser.add_argument("--coarse-close",type=int,default=1); parser.add_argument("--fine-close",type=int,default=2); parser.add_argument("--verify-existing",action="store_true")
    args = parser.parse_args()
    if args.verify_existing: verify_existing(); return
    hash_gate(); vertices, faces = read_binary_triangle_ply(SOURCE)
    reports = [build_attempt("coarse-a",args.coarse_pitch,args.coarse_close,vertices,faces), build_attempt("fine-b",args.fine_pitch,args.fine_close,vertices,faces)]
    write_json(OUT/"reports"/"source-rebuild-iteration-selection-r16.json", {"schema_version":1,"task":TASK,"task_blob_sha":TASK_BLOB,"attempts":reports,
               "note":"Gate 2 remains a separate mandatory visual/form-protection decision."})


if __name__ == "__main__": main()
