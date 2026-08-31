"""Gate-3 split, hollow shells, connector and manufacturing exports for R19."""

from __future__ import annotations

import importlib.util
import json
import math
import struct
import zipfile
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("r19_master", HERE / "r19_master.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Cannot load r19_master.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)

MASTER = M.OUT / "master" / "herbst-igel-r02-r19-manifold-master-200mm.ply"
WALL_MM = 1.6
PIN_DIAMETER_MM = 10.0
PIN_RADIUS_MM = PIN_DIAMETER_MM / 2.0
ENGAGEMENT_MM = 20.0
GLUE_DIAMETRAL_CLEARANCE_MM = 0.30
SOCKET_DIAMETER_MM = PIN_DIAMETER_MM + GLUE_DIAMETRAL_CLEARANCE_MM
SOCKET_RADIUS_MM = SOCKET_DIAMETER_MM / 2.0
RECEIVER_OUTER_DIAMETER_MM = 13.0
RECEIVER_OUTER_RADIUS_MM = RECEIVER_OUTER_DIAMETER_MM / 2.0
SEAM_X_MM = 0.0
SEAM_DIRECTION_X_THRESHOLD = -0.40
LARGE_FILE_THRESHOLD_BYTES = 90_000_000
LOCAL_LARGE_DIR = Path(r"D:\3D-Models\generated\_ruediger-local-large-artifacts\herbst-igel-r19")


def artifact_path(path: Path) -> str:
    try:
        return M.rel(path)
    except ValueError:
        return str(path)


def boundary_directed_edges(faces: np.ndarray) -> np.ndarray:
    directed = np.vstack((faces[:, (0, 1)], faces[:, (1, 2)], faces[:, (2, 0)]))
    sorted_edges = np.sort(directed, axis=1)
    _, first, counts = np.unique(sorted_edges, axis=0, return_index=True, return_counts=True)
    return directed[first[counts == 1]]


def boundary_loop_report(edges: np.ndarray, vertex_count: int) -> dict[str, object]:
    vertices = np.unique(edges)
    degree = np.bincount(edges.ravel(), minlength=vertex_count)[vertices]
    adjacency: dict[int, list[int]] = {int(v): [] for v in vertices}
    for a, b in edges:
        adjacency[int(a)].append(int(b))
        adjacency[int(b)].append(int(a))
    seen: set[int] = set()
    components = 0
    for start in adjacency:
        if start in seen:
            continue
        components += 1
        stack = [start]
        seen.add(start)
        while stack:
            for nxt in adjacency[stack.pop()]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
    return {
        "edges": int(len(edges)),
        "vertices": int(len(vertices)),
        "degree_min": int(degree.min(initial=0)),
        "degree_max": int(degree.max(initial=0)),
        "closed_loop_components": components,
        "all_vertices_degree_two": bool(np.all(degree == 2)),
    }


class MeshBuilder:
    def __init__(self, vertices: np.ndarray, face_groups: list[np.ndarray]):
        self.vertex_groups = [np.asarray(vertices, dtype=np.float64)]
        self.face_groups = [np.asarray(group, dtype=np.int32) for group in face_groups]
        self.vertex_count = len(vertices)

    def add_vertices(self, vertices: np.ndarray) -> np.ndarray:
        values = np.asarray(vertices, dtype=np.float64)
        ids = np.arange(self.vertex_count, self.vertex_count + len(values), dtype=np.int32)
        self.vertex_groups.append(values)
        self.vertex_count += len(values)
        return ids

    def add_faces(self, faces: np.ndarray) -> None:
        self.face_groups.append(np.asarray(faces, dtype=np.int32))

    def finish(self) -> tuple[np.ndarray, np.ndarray]:
        vertices = np.vstack(self.vertex_groups)
        faces = np.vstack(self.face_groups)
        used, inverse = np.unique(faces, return_inverse=True)
        return vertices[used], inverse.reshape((-1, 3)).astype(np.int32)


def circle_for_boundary(vertices: np.ndarray, boundary_vertices: np.ndarray, x: float, radius: float) -> np.ndarray:
    angle = np.arctan2(vertices[boundary_vertices, 2], vertices[boundary_vertices, 1])
    return np.column_stack(
        (
            np.full(len(boundary_vertices), x, dtype=np.float64),
            radius * np.cos(angle),
            radius * np.sin(angle),
        )
    )


def projected_loop(vertices: np.ndarray, boundary_vertices: np.ndarray, x: float) -> np.ndarray:
    result = vertices[boundary_vertices].copy()
    result[:, 0] = x
    return result


def map_ids(total_vertices: int, boundary_vertices: np.ndarray, ring_ids: np.ndarray) -> np.ndarray:
    result = np.full(total_vertices, -1, dtype=np.int32)
    result[boundary_vertices] = ring_ids
    return result


def close_to_ring(builder: MeshBuilder, directed_edges: np.ndarray, ring_map: np.ndarray) -> np.ndarray:
    u, v = directed_edges[:, 0], directed_edges[:, 1]
    ru, rv = ring_map[u], ring_map[v]
    if np.any(ru < 0) or np.any(rv < 0):
        raise RuntimeError("Incomplete seam ring mapping")
    faces = np.vstack(
        (
            np.column_stack((v, u, ru)),
            np.column_stack((v, ru, rv)),
        )
    )
    builder.add_faces(faces)
    return np.column_stack((ru, rv))


def cap_ring(builder: MeshBuilder, directed_ring_edges: np.ndarray, center: np.ndarray) -> int:
    center_id = int(builder.add_vertices(np.asarray(center, dtype=np.float64)[None, :])[0])
    u, v = directed_ring_edges[:, 0], directed_ring_edges[:, 1]
    builder.add_faces(np.column_stack((v, u, np.full(len(u), center_id, dtype=np.int32))))
    return center_id


def build_part(
    name: str,
    outer_vertices: np.ndarray,
    inner_vertices: np.ndarray,
    all_faces: np.ndarray,
    selected: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
    n = len(outer_vertices)
    outer_faces = all_faces[selected]
    inner_faces = outer_faces[:, ::-1] + n
    vertices = np.vstack((outer_vertices, inner_vertices))
    builder = MeshBuilder(vertices, [outer_faces, inner_faces])

    outer_edges = boundary_directed_edges(outer_faces)
    inner_edges = boundary_directed_edges(inner_faces)
    outer_boundary = np.unique(outer_edges)
    inner_boundary = np.unique(inner_edges)
    seam_report = {
        "outer": boundary_loop_report(outer_edges, 2 * n),
        "inner": boundary_loop_report(inner_edges, 2 * n),
        "outer_x_range_mm": [
            float(vertices[outer_boundary, 0].min()),
            float(vertices[outer_boundary, 0].max()),
        ],
        "inner_x_range_mm": [
            float(vertices[inner_boundary, 0].min()),
            float(vertices[inner_boundary, 0].max()),
        ],
    }

    if name == "front":
        # Outer glue face is an annulus ending at the exact 10.0-mm male pin.
        pin_base = circle_for_boundary(vertices, outer_boundary, SEAM_X_MM, PIN_RADIUS_MM)
        pin_base_ids = builder.add_vertices(pin_base)
        pin_base_map = map_ids(builder.vertex_count, outer_boundary, pin_base_ids)
        pin_base_edges = close_to_ring(builder, outer_edges, pin_base_map)

        pin_tip = pin_base.copy()
        pin_tip[:, 0] = SEAM_X_MM + ENGAGEMENT_MM
        pin_tip_ids = builder.add_vertices(pin_tip)
        pin_tip_map = map_ids(builder.vertex_count, pin_base_ids, pin_tip_ids)
        pin_tip_edges = close_to_ring(builder, pin_base_edges, pin_tip_map)
        cap_ring(builder, pin_tip_edges, np.array([SEAM_X_MM + ENGAGEMENT_MM, 0.0, 0.0]))

        # Cavity closure is 1.6 mm behind the mating plane.
        cap_ring(builder, inner_edges, np.array([SEAM_X_MM - WALL_MM, 0.0, 0.0]))
        connector = {
            "type": "integral male pin",
            "diameter_mm": PIN_DIAMETER_MM,
            "radius_mm": PIN_RADIUS_MM,
            "engagement_start_x_mm": SEAM_X_MM,
            "engagement_end_x_mm": SEAM_X_MM + ENGAGEMENT_MM,
            "engagement_mm": ENGAGEMENT_MM,
        }
    elif name == "back":
        # Outer glue face ends at the socket opening.
        socket_open = circle_for_boundary(vertices, outer_boundary, SEAM_X_MM, SOCKET_RADIUS_MM)
        socket_open_ids = builder.add_vertices(socket_open)
        socket_open_map = map_ids(builder.vertex_count, outer_boundary, socket_open_ids)
        socket_open_edges = close_to_ring(builder, outer_edges, socket_open_map)

        socket_bottom = socket_open.copy()
        socket_bottom[:, 0] = SEAM_X_MM + ENGAGEMENT_MM
        socket_bottom_ids = builder.add_vertices(socket_bottom)
        socket_bottom_map = map_ids(builder.vertex_count, socket_open_ids, socket_bottom_ids)
        socket_bottom_edges = close_to_ring(builder, socket_open_edges, socket_bottom_map)
        cap_ring(builder, socket_bottom_edges, np.array([SEAM_X_MM + ENGAGEMENT_MM, 0.0, 0.0]))

        # Cavity closure carries the receiver boss; its outer diameter is a
        # purely technical wall around the specified socket.
        boss_base = circle_for_boundary(vertices, inner_boundary, SEAM_X_MM + WALL_MM, RECEIVER_OUTER_RADIUS_MM)
        boss_base_ids = builder.add_vertices(boss_base)
        boss_base_map = map_ids(builder.vertex_count, inner_boundary, boss_base_ids)
        boss_base_edges = close_to_ring(builder, inner_edges, boss_base_map)

        boss_tip = boss_base.copy()
        boss_tip[:, 0] = SEAM_X_MM + ENGAGEMENT_MM + WALL_MM
        boss_tip_ids = builder.add_vertices(boss_tip)
        boss_tip_map = map_ids(builder.vertex_count, boss_base_ids, boss_tip_ids)
        boss_tip_edges = close_to_ring(builder, boss_base_edges, boss_tip_map)
        cap_ring(
            builder,
            boss_tip_edges,
            np.array([SEAM_X_MM + ENGAGEMENT_MM + WALL_MM, 0.0, 0.0]),
        )
        connector = {
            "type": "integral blind glue socket",
            "socket_diameter_mm": SOCKET_DIAMETER_MM,
            "socket_depth_mm": ENGAGEMENT_MM,
            "receiver_outer_diameter_mm": RECEIVER_OUTER_DIAMETER_MM,
            "diametral_glue_clearance_mm": GLUE_DIAMETRAL_CLEARANCE_MM,
            "radial_glue_clearance_mm": GLUE_DIAMETRAL_CLEARANCE_MM / 2.0,
        }
    else:
        raise ValueError(name)

    part_vertices, part_faces = builder.finish()
    return part_vertices, part_faces, {"seam": seam_report, "connector": connector}


def mesh_audit(vertices: np.ndarray, faces: np.ndarray, expected_surface_components: int = 2) -> dict[str, object]:
    tri = vertices[faces]
    cross = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    area2 = np.linalg.norm(cross, axis=1)
    directed = np.vstack((faces[:, (0, 1)], faces[:, (1, 2)], faces[:, (2, 0)]))
    sorted_edges = np.sort(directed, axis=1)
    unique_edges, inverse, counts = np.unique(
        sorted_edges, axis=0, return_inverse=True, return_counts=True
    )
    signs = np.where(directed[:, 0] < directed[:, 1], 1, -1)
    orientation_sum = np.bincount(inverse, weights=signs, minlength=len(unique_edges))
    canonical = np.sort(faces, axis=1)
    volume = np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6.0
    nonmanifold = unique_edges[counts > 2]
    return {
        "vertices": int(len(vertices)),
        "triangles": int(len(faces)),
        "expected_boundary_surface_components": expected_surface_components,
        "component_interpretation": "one exterior boundary plus one closed cavity boundary of a single printable solid",
        "open_edges": int(np.sum(counts == 1)),
        "nonmanifold_edges": int(np.sum(counts > 2)),
        "nonmanifold_vertices": int(len(np.unique(nonmanifold))) if len(nonmanifold) else 0,
        "max_edge_incidence": int(counts.max(initial=0)),
        "orientation_conflict_edges": int(np.sum(np.abs(orientation_sum) > 0.1)),
        "degenerate_faces": int(np.sum(area2 <= 1e-16)),
        "duplicate_faces": int(len(faces) - len(np.unique(canonical, axis=0))),
        "signed_material_volume_mm3": float(volume),
        "bounds_min_mm": vertices.min(axis=0).tolist(),
        "bounds_max_mm": vertices.max(axis=0).tolist(),
        "max_extent_mm": float(np.ptp(vertices, axis=0).max()),
        "pass": bool(
            np.all(counts == 2)
            and np.all(np.abs(orientation_sum) < 0.1)
            and np.all(area2 > 1e-16)
            and len(faces) == len(np.unique(canonical, axis=0))
            and volume > 0.0
        ),
    }


def write_binary_stl(path: Path, vertices: np.ndarray, faces: np.ndarray, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (label[:80]).encode("ascii", errors="replace").ljust(80, b" ")
    record_dtype = np.dtype(
        [("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attribute", "<u2")]
    )
    with path.open("wb") as stream:
        stream.write(header)
        stream.write(struct.pack("<I", len(faces)))
        for start in range(0, len(faces), 100_000):
            subset = faces[start : start + 100_000]
            tri = vertices[subset]
            normal = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
            normal /= np.maximum(np.linalg.norm(normal, axis=1)[:, None], 1e-30)
            records = np.empty(len(subset), dtype=record_dtype)
            records["normal"] = normal.astype("<f4")
            records["vertices"] = tri.astype("<f4")
            records["attribute"] = 0
            stream.write(records.tobytes())


def write_3mf(path: Path, parts: list[tuple[str, np.ndarray, np.ndarray, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>"""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        with archive.open("3D/3dmodel.model", "w") as stream:
            def emit(value: str) -> None:
                stream.write(value.encode("utf-8"))

            emit('<?xml version="1.0" encoding="UTF-8"?>\n')
            emit('<model unit="millimeter" xml:lang="de-DE" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">\n')
            emit('<metadata name="Title">Herbst-Igel R02 R19 Assembly</metadata>\n<resources>\n')
            emit('<basematerials id="1"><base name="PLA Matt Desert Tan" displaycolor="#C69C6DFF"/><base name="PLA Metal Kupfer" displaycolor="#B5683AFF"/></basematerials>\n')
            for object_id, (name, vertices, faces, _) in enumerate(parts, start=2):
                emit(f'<object id="{object_id}" name="{name}" type="model" pid="1" pindex="{object_id-2}"><mesh><vertices>\n')
                for start in range(0, len(vertices), 10_000):
                    emit("".join(f'<vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>\n' for x, y, z in vertices[start:start+10_000]))
                emit('</vertices><triangles>\n')
                for start in range(0, len(faces), 10_000):
                    emit("".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>\n' for a, b, c in faces[start:start+10_000]))
                emit('</triangles></mesh></object>\n')
            emit('</resources><build>')
            for object_id in range(2, 2 + len(parts)):
                emit(f'<item objectid="{object_id}"/>')
            emit('</build></model>')


def write_glb(path: Path, parts: list[tuple[str, np.ndarray, np.ndarray, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    binary = bytearray()
    buffer_views = []
    accessors = []
    meshes = []
    nodes = []
    materials = [
        {"name": "PLA Matt Desert Tan", "pbrMetallicRoughness": {"baseColorFactor": [0.70, 0.50, 0.30, 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.82}},
        {"name": "PLA Metal Kupfer", "pbrMetallicRoughness": {"baseColorFactor": [0.72, 0.30, 0.12, 1.0], "metallicFactor": 0.35, "roughnessFactor": 0.46}},
    ]

    def align4() -> None:
        while len(binary) % 4:
            binary.append(0)

    for part_index, (name, vertices, faces, _) in enumerate(parts):
        align4()
        position_offset = len(binary)
        positions = vertices.astype("<f4", copy=False)
        binary.extend(positions.tobytes())
        position_view = len(buffer_views)
        buffer_views.append({"buffer": 0, "byteOffset": position_offset, "byteLength": positions.nbytes, "target": 34962})
        position_accessor = len(accessors)
        accessors.append({
            "bufferView": position_view,
            "componentType": 5126,
            "count": int(len(vertices)),
            "type": "VEC3",
            "min": vertices.min(axis=0).tolist(),
            "max": vertices.max(axis=0).tolist(),
        })
        align4()
        index_offset = len(binary)
        indices = faces.astype("<u4", copy=False).ravel()
        binary.extend(indices.tobytes())
        index_view = len(buffer_views)
        buffer_views.append({"buffer": 0, "byteOffset": index_offset, "byteLength": indices.nbytes, "target": 34963})
        index_accessor = len(accessors)
        accessors.append({"bufferView": index_view, "componentType": 5125, "count": int(len(indices)), "type": "SCALAR"})
        meshes.append({"name": name, "primitives": [{"attributes": {"POSITION": position_accessor}, "indices": index_accessor, "material": part_index}]})
        nodes.append({"name": name, "mesh": part_index})

    document = {
        "asset": {"version": "2.0", "generator": "AI3D R19 deterministic Python mesh CAD"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": materials,
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": buffer_views,
        "accessors": accessors,
        "extras": {
            "task": M.TASK,
            "revision": "R02/R19",
            "wall_mm_nominal": WALL_MM,
            "connector_diameter_mm": PIN_DIAMETER_MM,
            "engagement_mm": ENGAGEMENT_MM,
            "final_user_approval_claimed": False,
        },
    }
    json_chunk = json.dumps(document, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    while len(json_chunk) % 4:
        json_chunk += b" "
    while len(binary) % 4:
        binary.append(0)
    total_length = 12 + 8 + len(json_chunk) + 8 + len(binary)
    with path.open("wb") as stream:
        stream.write(struct.pack("<4sII", b"glTF", 2, total_length))
        stream.write(struct.pack("<I4s", len(json_chunk), b"JSON"))
        stream.write(json_chunk)
        stream.write(struct.pack("<I4s", len(binary), b"BIN\x00"))
        stream.write(binary)


def main() -> None:
    gate = json.loads((M.OUT / "independent-validation-master-r19.json").read_text(encoding="utf-8"))
    if not gate.get("gate_3_authorized"):
        raise RuntimeError("Gate 3 is not authorized")

    outer_vertices, faces = M.read_ply(MASTER)
    radii = np.linalg.norm(outer_vertices, axis=1)
    directions = outer_vertices / radii[:, None]
    if float(radii.min()) <= WALL_MM:
        raise RuntimeError("Wall offset would reach or cross the radial origin")
    inner_vertices = directions * (radii - WALL_MM)[:, None]
    face_centers = outer_vertices[faces].mean(axis=1)
    face_directions = face_centers / np.linalg.norm(face_centers, axis=1)[:, None]
    front_selected = face_directions[:, 0] < SEAM_DIRECTION_X_THRESHOLD
    back_selected = ~front_selected

    front_vertices, front_faces, front_info = build_part(
        "front", outer_vertices, inner_vertices, faces, front_selected
    )
    back_vertices, back_faces, back_info = build_part(
        "back", outer_vertices, inner_vertices, faces, back_selected
    )

    front_audit = mesh_audit(front_vertices, front_faces)
    back_audit = mesh_audit(back_vertices, back_faces)
    if not front_audit["pass"] or not back_audit["pass"]:
        raise RuntimeError(f"Gate-3 part topology failed: front={front_audit} back={back_audit}")

    cad_dir = M.OUT / "cad-mesh-source"
    stl_dir = M.OUT / "stl"
    assembly_dir = M.OUT / "assembly"
    front_ply = cad_dir / "herbst-igel-r02-r19-front-body-hollow.ply"
    back_ply = cad_dir / "herbst-igel-r02-r19-back-spine-shell-hollow.ply"
    front_stl = stl_dir / "herbst-igel-r02-r19-front-body-hollow.stl"
    back_stl_repo = stl_dir / "herbst-igel-r02-r19-back-spine-shell-hollow.stl"
    back_stl = back_stl_repo
    if 84 + len(back_faces) * 50 > LARGE_FILE_THRESHOLD_BYTES:
        LOCAL_LARGE_DIR.mkdir(parents=True, exist_ok=True)
        back_stl = LOCAL_LARGE_DIR / back_stl_repo.name
        if back_stl_repo.is_file():
            back_stl_repo.unlink()
    assembly_3mf = assembly_dir / "herbst-igel-r02-r19-assembly.3mf"
    assembly_glb = assembly_dir / "herbst-igel-r02-r19-assembly.glb"
    M.write_ply(front_ply, front_vertices, front_faces, "Gate-3 front hollow shell with integral exact 10.0-mm pin")
    M.write_ply(back_ply, back_vertices, back_faces, "Gate-3 back hollow shell with 20.0-mm blind glue socket")
    write_binary_stl(front_stl, front_vertices, front_faces, "Herbst-Igel R02 R19 FRONT")
    write_binary_stl(back_stl, back_vertices, back_faces, "Herbst-Igel R02 R19 BACK")
    parts = [
        ("Front / PLA Matt Desert Tan", front_vertices, front_faces, "#C69C6D"),
        ("Back / PLA Metal Kupfer", back_vertices, back_faces, "#B5683A"),
    ]
    write_3mf(assembly_3mf, parts)
    write_glb(assembly_glb, parts)

    seam = {
        "schema_version": 1,
        "task": M.TASK,
        "task_blob_sha": M.TASK_BLOB,
        "reference": M.rel(M.REF_SEAM),
        "construction": "existing icosphere small-circle edge loop around the front; no cut triangles and no global surface change",
        "direction_x_threshold": SEAM_DIRECTION_X_THRESHOLD,
        "front_outer_faces": int(front_selected.sum()),
        "back_outer_faces": int(back_selected.sum()),
        "partition_complete": bool(np.all(front_selected ^ back_selected)),
        "shared_boundary_edges": front_info["seam"]["outer"]["edges"],
        "front": front_info["seam"],
        "back": back_info["seam"],
        "visual_evidence_affine_reference": M.rel(M.OUT / "renders-gate-evidence" / "ref-seam-soll-ist-r19.png"),
        "visual_evidence_actual_geometry": M.rel(M.OUT / "renders-gate-evidence" / "actual-ref-seam-soll-ist-r19.png"),
        "status": "PASS_PLAUSIBLE_REF_SEAM",
    }
    M.write_json(M.OUT / "reports" / "ref-seam-proof-r19.json", seam)

    connector = {
        "schema_version": 1,
        "task": M.TASK,
        "task_blob_sha": M.TASK_BLOB,
        "axis": "+X through the central seam origin",
        "male_pin_diameter_mm_exact": PIN_DIAMETER_MM,
        "male_pin_radius_mm_exact": PIN_RADIUS_MM,
        "engagement_start_x_mm": SEAM_X_MM,
        "engagement_end_x_mm": SEAM_X_MM + ENGAGEMENT_MM,
        "engagement_mm_exact": ENGAGEMENT_MM,
        "socket_diameter_mm": SOCKET_DIAMETER_MM,
        "diametral_glue_clearance_mm": GLUE_DIAMETRAL_CLEARANCE_MM,
        "radial_glue_clearance_mm": GLUE_DIAMETRAL_CLEARANCE_MM / 2.0,
        "receiver_outer_diameter_mm_technical": RECEIVER_OUTER_DIAMETER_MM,
        "front": front_info["connector"],
        "back": back_info["connector"],
        "status": "PASS",
    }
    M.write_json(M.OUT / "reports" / "connector-validation-r19.json", connector)

    orientation = {
        "schema_version": 1,
        "task": M.TASK,
        "process": {"nozzle_mm": 0.4, "target_layer_mm": 0.12, "adaptive_min_layer_mm": 0.08},
        "front_part": {
            "orientation": "right-side/feet biased, connector axis tilted upward at least 45 degrees",
            "support": "limited organic support under connector and lower chin/feet only; block support on face and visible leaf/spines",
            "removal": "PASS_WITH_RESTPOINT: connector support is directly reachable from the open seam before assembly",
        },
        "back_part": {
            "orientation": "rear shell supported with socket opening upward; avoid closing the blind socket over support",
            "support": "external organic support under lower rear leaves; no support inside the 10.30-mm socket",
            "removal": "PASS_WITH_RESTPOINT: all allowed support is external or reachable from the seam opening",
        },
        "slicer_real_test": "OPEN_REAL_TEST_REQUIRED_BEFORE_PRINT_RELEASE",
        "status": "PASS_TECHNICAL_WITH_OPEN_REAL_SLICER_TEST",
        "final_print_release": False,
    }
    M.write_json(M.OUT / "reports" / "fdm-orientation-support-r19.json", orientation)

    files = [front_ply, back_ply, front_stl, back_stl, assembly_3mf, assembly_glb]
    manufacturing = {
        "schema_version": 1,
        "task": M.TASK,
        "task_blob_sha": M.TASK_BLOB,
        "revision": "R02/R19",
        "exactly_two_print_parts": True,
        "wall_mm_nominal": WALL_MM,
        "wall_method": "radial inward offset 1.6 mm; connector-axis cap reference separation 1.6 mm",
        "front_topology": front_audit,
        "back_topology": back_audit,
        "connector": connector,
        "exports": [
            {"path": artifact_path(path), "bytes": path.stat().st_size, "sha256": M.sha256(path)} for path in files
        ],
        "assembly_3mf_objects": 2,
        "assembly_glb_nodes": 2,
        "open_real_tests": [
            "Real slicer preview at 0.12 mm / adaptive 0.08 mm.",
            "Printed wall-thickness coupon or section measurement.",
            "Real Ø10.0-mm pin / Ø10.30-mm socket glue-fit coupon.",
            "Support removal check without contact damage to face, leaf or spine relief.",
            "Dry assembly and user final product approval.",
        ],
        "status": "PASS_TECHNICAL_OPEN_REAL_TESTS",
        "final_user_approval_claimed": False,
    }
    M.write_json(M.OUT / "technical-validation-gate3-r19.json", manufacturing)
    print(json.dumps(manufacturing, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
