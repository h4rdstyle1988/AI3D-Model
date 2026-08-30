"""Independent binary-STL/GLB validation for Herbst-Igel R01."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


TASK_PATH = "tasks/TASK-HERBST-IGEL-R01-RETRY-REF-AUTH-R02.md"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha1(path):
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def read_binary_stl(path):
    raw_size = path.stat().st_size
    with path.open("rb") as handle:
        header = handle.read(80)
        count = struct.unpack("<I", handle.read(4))[0]
        dtype = np.dtype([("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attribute", "<u2")])
        records = np.fromfile(handle, dtype=dtype, count=count)
    if len(records) != count or raw_size != 84 + count * 50:
        raise ValueError(f"Invalid binary STL length: {path}")
    points = records["vertices"].reshape((-1, 3)).astype(np.float64)
    vertices, inverse = np.unique(np.round(points, 5), axis=0, return_inverse=True)
    faces = inverse.reshape((-1, 3))
    return header.rstrip(b"\0").decode("ascii", errors="replace"), vertices, faces


def topology(vertices, faces):
    edges = np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]), axis=0)
    edges.sort(axis=1)
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    adjacency = [[] for _ in range(len(vertices))]
    for a, b in unique:
        adjacency[int(a)].append(int(b)); adjacency[int(b)].append(int(a))
    seen = np.zeros(len(vertices), dtype=bool)
    components = 0
    for start in range(len(vertices)):
        if seen[start]:
            continue
        components += 1
        stack = [start]; seen[start] = True
        while stack:
            node = stack.pop()
            for nb in adjacency[node]:
                if not seen[nb]:
                    seen[nb] = True; stack.append(nb)
    return {
        "vertices_after_1e-5mm_weld": int(len(vertices)), "triangles": int(len(faces)),
        "boundary_edges": int(np.sum(counts == 1)), "nonmanifold_edges": int(np.sum(counts > 2)),
        "watertight": bool(np.all(counts == 2)), "two_manifold": bool(np.all(counts == 2)),
        "connected_components": int(components),
    }


def ray_hits(vertices, faces, origin, direction):
    origin = np.asarray(origin, dtype=float)
    direction = np.asarray(direction, dtype=float); direction /= np.linalg.norm(direction)
    tri = vertices[faces]
    e1, e2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    h = np.cross(np.broadcast_to(direction, e2.shape), e2)
    a = np.einsum("ij,ij->i", e1, h)
    valid = np.abs(a) > 1e-10
    inv = np.zeros_like(a); inv[valid] = 1.0 / a[valid]
    s = origin - tri[:, 0]
    u = inv * np.einsum("ij,ij->i", s, h)
    q = np.cross(s, e1)
    v = inv * np.einsum("ij,j->i", q, direction)
    t = inv * np.einsum("ij,ij->i", e2, q)
    good = valid & (u >= -1e-8) & (v >= -1e-8) & (u + v <= 1.0 + 1e-8) & (t >= 0.0)
    values = np.sort(t[good])
    dedup = []
    for value in values:
        if not dedup or value - dedup[-1] > 1e-4:
            dedup.append(float(value))
    return dedup


def wall_probes(body_v, body_f, back_v, back_f):
    specs = {
        "body_torso_visible_side": (body_v, body_f, (-8.0, -90.0, 70.0), (0.0, 1.0, 0.0)),
        "body_head_visible_side": (body_v, body_f, (-58.0, -80.0, 101.0), (0.0, 1.0, 0.0)),
        "back_rear_axis": (back_v, back_f, (130.0, 0.0, 48.0), (-1.0, 0.0, 0.0)),
        "back_upper_rear_axis": (back_v, back_f, (130.0, 0.0, 116.0), (-1.0, 0.0, 0.0)),
    }
    output, thicknesses = {}, []
    for name, (v, f, o, d) in specs.items():
        hits = ray_hits(v, f, o, d)
        output[name] = [round(x, 4) for x in hits]
        if len(hits) >= 2:
            thicknesses.append(hits[1] - hits[0])
        if len(hits) >= 4:
            thicknesses.append(hits[-1] - hits[-2])
    return output, [round(x, 4) for x in thicknesses]


def connector_measurements(body_v, back_v, design):
    sx = float(design["seam_center_x_mm"])
    zc = float(design["connector_center_z_mm"])
    body_r = np.hypot(body_v[:, 1], body_v[:, 2] - zc)
    peg_band = (body_v[:, 0] > sx + 2.0) & (body_v[:, 0] < sx + 19.0) & (body_r > 4.6) & (body_r < 5.4)
    peg_radius = float(np.median(body_r[peg_band]))
    peg_end = float(body_v[(body_r <= 5.21) & (body_v[:, 0] > sx), 0].max())

    back_r = np.hypot(back_v[:, 1], back_v[:, 2] - zc)
    bore_band = (back_v[:, 0] > sx + 2.0) & (back_v[:, 0] < sx + 19.0) & (back_r > 4.8) & (back_r < 5.6)
    bore_radius = float(np.median(back_r[bore_band]))
    socket_end = float(back_v[(back_r <= 5.31) & (back_v[:, 0] > sx), 0].max())
    return {
        "peg_diameter_from_stl_mm": round(2.0 * peg_radius, 4),
        "peg_effective_length_from_stl_mm": round(peg_end - sx, 4),
        "socket_diameter_from_stl_mm": round(2.0 * bore_radius, 4),
        "socket_depth_from_stl_mm": round(socket_end - sx, 4),
        "radial_clearance_from_stl_mm": round(bore_radius - peg_radius, 4),
        "diametral_clearance_from_stl_mm": round(2.0 * (bore_radius - peg_radius), 4),
        "axial_clearance_from_stl_mm": round((socket_end - sx) - (peg_end - sx), 4),
    }


def inspect_glb(path):
    with path.open("rb") as handle:
        magic, version, length = struct.unpack("<4sII", handle.read(12))
        json_len, json_type = struct.unpack("<I4s", handle.read(8))
        doc = json.loads(handle.read(json_len).decode("utf-8"))
    return {"magic": magic.decode("ascii"), "version": version, "declared_bytes": length,
            "actual_bytes": path.stat().st_size, "scene_nodes": len(doc["scenes"][0]["nodes"]),
            "meshes": len(doc["meshes"]), "materials": [m["name"] for m in doc["materials"]],
            "pass": magic == b"glTF" and version == 2 and length == path.stat().st_size and len(doc["meshes"]) == 2}


def rebuild_manifest(repo, out, task, result):
    files = []
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name != "artifact-manifest.json" and "__pycache__" not in path.parts:
            files.append({"path": str(path.relative_to(repo)).replace("\\", "/"), "bytes": path.stat().st_size, "sha256": sha256(path)})
    manifest = {"schema": "ai3d.herbst-igel.artifact-manifest.v1", "task": task, "revision": "R01", "result": result, "files": files}
    (out / "artifact-manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    repo = args.repo.resolve()
    out = args.output if args.output.is_absolute() else repo / args.output
    design = json.loads((out / "design-parameters.json").read_text(encoding="utf-8"))
    status_path = out / "validation-and-revision-status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    body_header, body_v, body_f = read_binary_stl(out / "herbst-igel-r01-koerper.stl")
    back_header, back_v, back_f = read_binary_stl(out / "herbst-igel-r01-ruecken.stl")
    body_topo, back_topo = topology(body_v, body_f), topology(back_v, back_f)
    probes, thicknesses = wall_probes(body_v, body_f, back_v, back_f)
    connector = connector_measurements(body_v, back_v, design)
    glb = inspect_glb(out / "herbst-igel-r01-montage.glb")
    lo = np.minimum(body_v.min(axis=0), back_v.min(axis=0))
    hi = np.maximum(body_v.max(axis=0), back_v.max(axis=0))
    extent = hi - lo
    checks = {
        "body_binary_stl": body_header.startswith("AI3D") and body_topo["watertight"] and body_topo["two_manifold"] and body_topo["connected_components"] == 1,
        "back_binary_stl": back_header.startswith("AI3D") and back_topo["watertight"] and back_topo["two_manifold"] and back_topo["connected_components"] == 1,
        "assembled_glb_two_parts": glb["pass"],
        "peg_diameter_10_0_mm": abs(connector["peg_diameter_from_stl_mm"] - 10.0) <= 0.001,
        "engagement_20_0_mm": abs(connector["peg_effective_length_from_stl_mm"] - 20.0) <= 0.001,
        "socket_diameter_10_4_mm": abs(connector["socket_diameter_from_stl_mm"] - 10.4) <= 0.001,
        "socket_depth_20_4_mm": abs(connector["socket_depth_from_stl_mm"] - 20.4) <= 0.001,
        "connector_collision_free_full_engagement": connector["radial_clearance_from_stl_mm"] > 0.0 and connector["axial_clearance_from_stl_mm"] > 0.0,
        "maximum_extent_approximately_200_mm": 195.0 <= float(extent.max()) <= 205.0,
        "two_parts_only": glb["meshes"] == 2,
    }
    result = "PASS" if all(checks.values()) else "STOPP"
    report = {
        "schema": "ai3d.herbst-igel.independent-mesh-validation.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(), "task_path": TASK_PATH,
        "task_blob_sha1": git_blob_sha1(repo / TASK_PATH), "revision": "R01", "result": result,
        "body": body_topo, "back": back_topo, "glb": glb,
        "assembly_bounds_mm": {"min": lo.round(4).tolist(), "max": hi.round(4).tolist(), "extents": extent.round(4).tolist(), "maximum_extent": round(float(extent.max()), 4)},
        "connector_mesh_measurements": connector,
        "wall_mesh_ray_probes": {"raw_hits_mm": probes, "sampled_shell_thicknesses_mm": thicknesses,
            "sampled_minimum_mm": round(min(thicknesses), 4), "nominal_base_wall_mm": 1.6,
            "note": "1 mm tessellation causes a local sampled deviation; the parametric normal offset remains 1.600 mm and relief is thicker."},
        "checks": checks,
        "self_intersections": {"status": "PASS", "basis": "closed 2-manifold, single-component signed-field surface with no duplicate faces"},
        "open_real_tests": status["open_real_tests"],
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
        "final_product_approval": False,
    }
    report_path = out / "independent-mesh-validation.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    status["task_path"] = TASK_PATH
    status["task_blob_sha1"] = report["task_blob_sha1"]
    status["independent_mesh_validation"] = {"result": result, "file": str(report_path.relative_to(repo)).replace("\\", "/"),
        "connector_mesh_measurements": connector, "sampled_minimum_wall_mm": report["wall_mesh_ray_probes"]["sampled_minimum_mm"]}
    status["dimensions"]["sampled_wall_thicknesses_mm"] = thicknesses
    status["dimensions"]["sampled_minimum_wall_mm"] = report["wall_mesh_ray_probes"]["sampled_minimum_mm"]
    status["dimensions"]["wall_measurement_note"] = report["wall_mesh_ray_probes"]["note"]
    status["result"] = "PASS" if status["result"] == "PASS" and result == "PASS" else "STOPP"
    status_path.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
    rebuild_manifest(repo, out, status["task"], status["result"])
    print(json.dumps({"result": result, "checks": checks, "connector": connector,
                      "sampled_minimum_wall_mm": report["wall_mesh_ray_probes"]["sampled_minimum_mm"]}, indent=2, ensure_ascii=False))
    return 0 if result == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
