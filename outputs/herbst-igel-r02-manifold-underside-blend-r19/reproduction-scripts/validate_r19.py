"""Independent final artifact and format validation for Herbst-Igel R19."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import struct
import subprocess
import zipfile
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M = load_module("r19_master", HERE / "r19_master.py")
G = load_module("r19_gate3", HERE / "r19_gate3.py")


def count_stream(stream, needles: list[bytes]) -> dict[str, int]:
    overlap = max(map(len, needles)) - 1
    carry = b""
    counts = {needle.decode("ascii"): 0 for needle in needles}
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        data = carry + chunk
        if len(data) <= overlap:
            carry = data
            continue
        body, carry = data[:-overlap], data[-overlap:]
        for needle in needles:
            counts[needle.decode("ascii")] += body.count(needle)
    for needle in needles:
        counts[needle.decode("ascii")] += carry.count(needle)
    return counts


def stl_count(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        header = stream.read(80)
        triangles = struct.unpack("<I", stream.read(4))[0]
    expected = 84 + triangles * 50
    return {
        "header": header.rstrip(b" \x00").decode("ascii", errors="replace"),
        "triangles": int(triangles),
        "bytes": path.stat().st_size,
        "expected_bytes": expected,
        "length_pass": path.stat().st_size == expected,
    }


def validate_3mf(path: Path) -> dict[str, object]:
    with zipfile.ZipFile(path, "r") as archive:
        names = sorted(archive.namelist())
        required = {"[Content_Types].xml", "_rels/.rels", "3D/3dmodel.model"}
        if not required.issubset(names):
            raise RuntimeError(f"3MF entries missing: {required - set(names)}")
        model_info = archive.getinfo("3D/3dmodel.model")
        # The model XML is read once for exact tag counts.  A prior chunked
        # diagnostic counter could lose tags at its artificial carry boundary;
        # this byte count is the authoritative archive-content audit.
        model = archive.read("3D/3dmodel.model")
        counts = {
            needle.decode("ascii"): model.count(needle)
            for needle in (b"<object ", b"<item ", b"<vertex ", b"<triangle ")
        }
    return {
        "entries": names,
        "counts": counts,
        "compressed_model_bytes": model_info.compress_size,
        "uncompressed_model_bytes": model_info.file_size,
        "bytes": path.stat().st_size,
    }


def validate_glb(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        magic, version, total_length = struct.unpack("<4sII", stream.read(12))
        json_length, json_type = struct.unpack("<I4s", stream.read(8))
        document = json.loads(stream.read(json_length).decode("utf-8"))
        bin_length, bin_type = struct.unpack("<I4s", stream.read(8))
        remaining = stream.read()
    return {
        "magic": magic.decode("ascii"),
        "version": version,
        "declared_length": total_length,
        "actual_length": path.stat().st_size,
        "json_chunk_type": json_type.decode("ascii"),
        "bin_chunk_type_hex": bin_type.hex(),
        "bin_declared_bytes": bin_length,
        "bin_actual_bytes": len(remaining),
        "nodes": len(document.get("nodes", [])),
        "meshes": len(document.get("meshes", [])),
        "materials": len(document.get("materials", [])),
        "buffers": document.get("buffers", []),
        "pass": bool(
            magic == b"glTF"
            and version == 2
            and total_length == path.stat().st_size
            and json_type == b"JSON"
            and bin_type == b"BIN\x00"
            and bin_length == len(remaining)
            and len(document.get("nodes", [])) == 2
            and len(document.get("meshes", [])) == 2
            and len(document.get("materials", [])) == 2
        ),
    }


def connector_coordinates(vertices: np.ndarray, radius: float, x0: float, x1: float) -> dict[str, object]:
    yz_radius = np.linalg.norm(vertices[:, 1:3], axis=1)
    selected = (
        (vertices[:, 0] >= x0 - 1e-5)
        & (vertices[:, 0] <= x1 + 1e-5)
        & (np.abs(yz_radius - radius) <= 2e-5)
    )
    values = vertices[selected]
    radial = yz_radius[selected]
    return {
        "matched_vertices": int(len(values)),
        "x_min_mm": float(values[:, 0].min()) if len(values) else None,
        "x_max_mm": float(values[:, 0].max()) if len(values) else None,
        "radius_min_mm": float(radial.min()) if len(values) else None,
        "radius_max_mm": float(radial.max()) if len(values) else None,
        "diameter_nominal_mm": radius * 2.0,
        "pass": bool(
            len(values) > 0
            and abs(float(values[:, 0].min()) - x0) <= 1e-5
            and abs(float(values[:, 0].max()) - x1) <= 1e-5
            and np.max(np.abs(radial - radius)) <= 2e-5
        ),
    }


def wall_sample_check(master_vertices: np.ndarray, part_vertices: np.ndarray, selector: np.ndarray) -> dict[str, object]:
    ids = np.nonzero(selector)[0]
    if len(ids) > 2048:
        ids = ids[np.linspace(0, len(ids) - 1, 2048, dtype=np.int64)]
    outer = master_vertices[ids].astype(np.float64)
    radius = np.linalg.norm(outer, axis=1)
    inner = (outer / radius[:, None] * (radius - G.WALL_MM)[:, None]).astype("<f4")
    part = np.ascontiguousarray(part_vertices.astype("<f4"))
    dtype = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4")])
    part_keys = np.sort(part.view(dtype).reshape(-1))
    expected = np.ascontiguousarray(inner).view(dtype).reshape(-1)
    positions = np.searchsorted(part_keys, expected)
    present = positions < len(part_keys)
    present[present] &= part_keys[positions[present]] == expected[present]
    return {
        "sampled_outer_vertices": int(len(ids)),
        "matching_inner_vertices": int(present.sum()),
        "nominal_radial_offset_mm": G.WALL_MM,
        "pass": bool(np.all(present)),
    }


def main() -> None:
    result_status = json.loads((M.OUT / "result-status.json").read_text(encoding="utf-8"))
    manifest = json.loads((M.OUT / "artifact-manifest.json").read_text(encoding="utf-8"))
    gate3_status = json.loads((M.OUT / "technical-validation-gate3-r19.json").read_text(encoding="utf-8"))
    local_large = json.loads((M.OUT / "LOCAL-LARGE-ARTIFACTS.json").read_text(encoding="utf-8"))
    task_blob = subprocess.check_output(["git", "hash-object", M.TASK], cwd=M.ROOT, text=True).strip()

    front_ply = M.OUT / "cad-mesh-source" / "herbst-igel-r02-r19-front-body-hollow.ply"
    back_ply = M.OUT / "cad-mesh-source" / "herbst-igel-r02-r19-back-spine-shell-hollow.ply"
    front_stl = M.OUT / "stl" / "herbst-igel-r02-r19-front-body-hollow.stl"
    back_stl_record = next(
        item for item in gate3_status["exports"]
        if item["path"].lower().endswith("back-spine-shell-hollow.stl")
    )
    back_stl = Path(back_stl_record["path"])
    if not back_stl.is_absolute():
        back_stl = M.ROOT / back_stl
    assembly_3mf = M.OUT / "assembly" / "herbst-igel-r02-r19-assembly.3mf"
    assembly_glb = M.OUT / "assembly" / "herbst-igel-r02-r19-assembly.glb"
    master_ply = M.OUT / "master" / "herbst-igel-r02-r19-manifold-master-200mm.ply"

    master_vertices, master_faces = M.read_ply(master_ply)
    face_centers = master_vertices[master_faces].mean(axis=1)
    face_direction_x = face_centers[:, 0] / np.linalg.norm(face_centers, axis=1)
    front_master_vertices = np.zeros(len(master_vertices), dtype=bool)
    front_master_vertices[np.unique(master_faces[face_direction_x < G.SEAM_DIRECTION_X_THRESHOLD])] = True
    back_master_vertices = np.zeros(len(master_vertices), dtype=bool)
    back_master_vertices[np.unique(master_faces[face_direction_x >= G.SEAM_DIRECTION_X_THRESHOLD])] = True

    front_vertices, front_faces = M.read_ply(front_ply)
    front_mesh = G.mesh_audit(front_vertices, front_faces)
    front_connector = connector_coordinates(front_vertices, G.PIN_RADIUS_MM, 0.0, G.ENGAGEMENT_MM)
    front_wall = wall_sample_check(master_vertices, front_vertices, front_master_vertices)
    del front_vertices, front_faces

    back_vertices, back_faces = M.read_ply(back_ply)
    back_mesh = G.mesh_audit(back_vertices, back_faces)
    back_connector = connector_coordinates(back_vertices, G.SOCKET_RADIUS_MM, 0.0, G.ENGAGEMENT_MM)
    back_wall = wall_sample_check(master_vertices, back_vertices, back_master_vertices)
    del back_vertices, back_faces

    front_stl_report = stl_count(front_stl)
    back_stl_report = stl_count(back_stl)
    three_mf = validate_3mf(assembly_3mf)
    glb = validate_glb(assembly_glb)

    local_large_failures = []
    for item in local_large["artifacts"]:
        path = Path(item["path"])
        if not path.is_file():
            local_large_failures.append({"path": item["path"], "reason": "missing"})
        elif path.stat().st_size != item["bytes"] or M.sha256(path) != item["sha256"]:
            local_large_failures.append({"path": item["path"], "reason": "size_or_hash"})

    manifest_failures = []
    for item in manifest["artifacts"]:
        path = M.ROOT / item["path"]
        if not path.is_file():
            manifest_failures.append({"path": item["path"], "reason": "missing"})
            continue
        actual_size = path.stat().st_size
        actual_hash = M.sha256(path)
        if actual_size != item["bytes"] or actual_hash != item["sha256"]:
            manifest_failures.append(
                {"path": item["path"], "reason": "size_or_hash", "actual_bytes": actual_size, "actual_sha256": actual_hash}
            )

    three_mf_counts = three_mf["counts"]
    expected_vertices = front_mesh["vertices"] + back_mesh["vertices"]
    expected_triangles = front_mesh["triangles"] + back_mesh["triangles"]
    checks = {
        "task_blob_matches": task_blob == M.TASK_BLOB,
        "result_status_pass": result_status["status"] == "PASS",
        "final_user_approval_not_claimed": result_status["final_user_approval_claimed"] is False,
        "front_mesh_pass": front_mesh["pass"],
        "back_mesh_pass": back_mesh["pass"],
        "front_wall_sample_pass": front_wall["pass"],
        "back_wall_sample_pass": back_wall["pass"],
        "front_pin_coordinates_pass": front_connector["pass"],
        "back_socket_coordinates_pass": back_connector["pass"],
        "front_stl_pass": front_stl_report["length_pass"] and front_stl_report["triangles"] == front_mesh["triangles"],
        "back_stl_pass": back_stl_report["length_pass"] and back_stl_report["triangles"] == back_mesh["triangles"],
        "3mf_two_objects_pass": three_mf_counts["<object "] == 2 and three_mf_counts["<item "] == 2,
        "3mf_geometry_counts_pass": three_mf_counts["<vertex "] == expected_vertices and three_mf_counts["<triangle "] == expected_triangles,
        "glb_pass": glb["pass"],
        "manifest_pass": not manifest_failures,
        "no_file_over_90mb": all(item["bytes"] <= 90_000_000 for item in manifest["artifacts"]),
        "local_large_artifact_pass": bool(local_large["artifacts"]) and not local_large_failures,
    }
    overall = "PASS" if all(checks.values()) else "FAIL"
    report = {
        "schema_version": 1,
        "task": M.TASK,
        "task_blob_sha_expected": M.TASK_BLOB,
        "task_blob_sha_actual": task_blob,
        "revision": "R02/R19",
        "checks": checks,
        "front_mesh": front_mesh,
        "back_mesh": back_mesh,
        "front_wall_sample": front_wall,
        "back_wall_sample": back_wall,
        "front_pin_coordinate_audit": front_connector,
        "back_socket_coordinate_audit": back_connector,
        "front_stl": front_stl_report,
        "back_stl": back_stl_report,
        "assembly_3mf": three_mf,
        "assembly_glb": glb,
        "manifest_failures": manifest_failures,
        "local_large_artifact_failures": local_large_failures,
        "open_real_tests": result_status["open_real_tests"],
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
        "final_user_approval_claimed": False,
        "overall": overall,
    }
    M.write_json(M.OUT / "independent-validation-r19.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)
    if overall != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
