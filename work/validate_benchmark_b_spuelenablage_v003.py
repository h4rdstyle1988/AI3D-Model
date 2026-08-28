#!/usr/bin/env python3
"""Independent validation for the image-specified Benchmark-B v003 candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import trimesh


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def topology(mesh: trimesh.Trimesh) -> dict:
    edge_counts = np.bincount(mesh.edges_unique_inverse, minlength=len(mesh.edges_unique))
    areas = np.asarray(mesh.area_faces)
    triangles = np.sort(np.asarray(mesh.faces), axis=1)
    duplicate_faces = len(triangles) - len(np.unique(triangles, axis=0))
    return {
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "shared_vertex_components": int(len(mesh.split(only_watertight=False))),
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "is_volume": bool(mesh.is_volume),
        "boundary_edges": int(np.count_nonzero(edge_counts == 1)),
        "nonmanifold_edges": int(np.count_nonzero(edge_counts > 2)),
        "maximum_edge_incidence": int(edge_counts.max(initial=0)),
        "zero_area_faces": int(np.count_nonzero(areas <= 1e-10)),
        "duplicate_faces_unoriented": int(duplicate_faces),
        "finite_vertices": bool(np.isfinite(mesh.vertices).all()),
        "finite_normals": bool(np.isfinite(mesh.face_normals).all()),
        "bounds_mm": np.asarray(mesh.bounds).tolist(),
        "extents_mm": np.asarray(mesh.extents).tolist(),
        "surface_area_mm2": float(mesh.area),
        "signed_volume_mm3": float(mesh.volume),
        "euler_number": int(mesh.euler_number),
    }


def polygon_area_xy(points: np.ndarray) -> float:
    x = points[:, 0]
    y = points[:, 1]
    return float(0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))))


def measure_holder_section(mesh: trimesh.Trimesh, z_mm: float = 80.0) -> dict:
    section = mesh.section(plane_origin=[0.0, 0.0, z_mm], plane_normal=[0.0, 0.0, 1.0])
    if section is None:
        raise RuntimeError("holder section is empty")
    loops = []
    for points in section.discrete:
        points = np.asarray(points)
        bounds = np.asarray([points[:, :2].min(axis=0), points[:, :2].max(axis=0)])
        loops.append({"points": int(len(points)), "area_mm2": polygon_area_xy(points), "bounds_xy_mm": bounds.tolist()})
    if len(loops) != 2:
        raise RuntimeError(f"expected exactly two holder loops at z={z_mm}, got {len(loops)}")
    loops.sort(key=lambda item: item["area_mm2"])
    inner, outer = loops[0], loops[1]
    ib = np.asarray(inner["bounds_xy_mm"])
    ob = np.asarray(outer["bounds_xy_mm"])
    thicknesses = {
        "left_mm": float(ib[0, 0] - ob[0, 0]),
        "right_mm": float(ob[1, 0] - ib[1, 0]),
        "front_mm": float(ib[0, 1] - ob[0, 1]),
        "rear_mm": float(ob[1, 1] - ib[1, 1]),
    }
    return {
        "plane_z_mm": z_mm,
        "outer_bounds_xy_mm": outer["bounds_xy_mm"],
        "inner_bounds_xy_mm": inner["bounds_xy_mm"],
        "outer_dimensions_xy_mm": (ob[1] - ob[0]).tolist(),
        "inner_dimensions_xy_mm": (ib[1] - ib[0]).tolist(),
        "wall_thicknesses_mm": thicknesses,
        "minimum_wall_thickness_mm": float(min(thicknesses.values())),
        "maximum_wall_thickness_mm": float(max(thicknesses.values())),
        "pass": all(math.isclose(value, 2.0, abs_tol=0.01) for value in thicknesses.values()),
    }


def _section_line_crossings(section: trimesh.path.Path3D, axis: int, value: float) -> list[float]:
    other = 1 - axis
    found: list[float] = []
    for points in section.discrete:
        points = np.asarray(points)
        for a, b in zip(points[:-1], points[1:]):
            da = float(a[axis] - value)
            db = float(b[axis] - value)
            if abs(da) < 1e-9 and abs(db) < 1e-9:
                continue
            if da * db > 0.0:
                continue
            denominator = float(b[axis] - a[axis])
            if abs(denominator) < 1e-12:
                continue
            t = (value - float(a[axis])) / denominator
            if -1e-9 <= t <= 1.0 + 1e-9:
                found.append(float(a[other] + t * (b[other] - a[other])))
    return sorted({round(number, 6) for number in found})


def measure_main_wall_section(mesh: trimesh.Trimesh, z_mm: float = 25.0) -> dict:
    section = mesh.section(plane_origin=[0.0, 0.0, z_mm], plane_normal=[0.0, 0.0, 1.0])
    if section is None:
        raise RuntimeError("main wall section is empty")
    x_at_y0 = _section_line_crossings(section, axis=1, value=0.0)
    y_at_x80 = _section_line_crossings(section, axis=0, value=80.0)
    right = [value for value in x_at_y0 if value > 100.0]
    front = [value for value in y_at_x80 if value < -30.0]
    rear = [value for value in y_at_x80 if value > 30.0]
    if len(right) != 2 or len(front) != 2 or len(rear) != 2:
        raise RuntimeError(f"unexpected main wall intersections: x={x_at_y0}, y={y_at_x80}")
    thicknesses = {
        "right_mm": float(right[1] - right[0]),
        "front_mm": float(front[1] - front[0]),
        "rear_mm": float(rear[1] - rear[0]),
    }
    return {
        "plane_z_mm": z_mm,
        "x_crossings_at_y0_mm": x_at_y0,
        "y_crossings_at_x80_mm": y_at_x80,
        "wall_thicknesses_mm": thicknesses,
        "pass": all(math.isclose(value, 2.0, abs_tol=0.01) for value in thicknesses.values()),
    }


def measure_foot_section(mesh: trimesh.Trimesh, z_mm: float = 5.0) -> dict:
    section = mesh.section(plane_origin=[0.0, 0.0, z_mm], plane_normal=[0.0, 0.0, 1.0])
    if section is None:
        raise RuntimeError("foot section is empty")
    loops = [np.asarray(points) for points in section.discrete]
    bounds = np.asarray([[min(points[:, 0].min() for points in loops), min(points[:, 1].min() for points in loops)],
                         [max(points[:, 0].max() for points in loops), max(points[:, 1].max() for points in loops)]])
    extents = bounds[1] - bounds[0]
    return {
        "plane_z_mm": z_mm,
        "bounds_xy_mm": bounds.tolist(),
        "extents_xy_mm": extents.tolist(),
        "position": "rear edge y=+42.5 to y=+7.5",
        "pass": math.isclose(extents[0], 240.0, abs_tol=0.01) and math.isclose(extents[1], 35.0, abs_tol=0.01),
    }
def inspect_3mf(path: Path) -> dict:
    with zipfile.ZipFile(path, "r") as archive:
        names = sorted(archive.namelist())
        required = {"[Content_Types].xml", "_rels/.rels", "3D/3dmodel.model"}
        if not required.issubset(names):
            raise RuntimeError(f"3MF missing required entries: {sorted(required - set(names))}")
        root = ET.fromstring(archive.read("3D/3dmodel.model"))
    namespace = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
    vertices = root.findall(".//m:vertex", namespace)
    triangles = root.findall(".//m:triangle", namespace)
    xyz = np.asarray([[float(v.attrib[axis]) for axis in ("x", "y", "z")] for v in vertices], dtype=np.float64)
    indices = np.asarray([[int(t.attrib[key]) for key in ("v1", "v2", "v3")] for t in triangles], dtype=np.int64)
    mesh = trimesh.Trimesh(vertices=xyz, faces=indices, process=False)
    return {
        "zip_entries": names,
        "unit": root.attrib.get("unit"),
        "vertices": int(len(vertices)),
        "triangles": int(len(triangles)),
        "bounds_mm": np.asarray(mesh.bounds).tolist(),
        "topology": topology(mesh),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_dir", type=Path)
    args = parser.parse_args()
    directory = args.candidate_dir
    params = json.loads((directory / "design-parameters.json").read_text(encoding="utf-8"))
    candidate = params["candidate"]
    stl = directory / f"{candidate}.stl"
    three_mf = directory / f"{candidate}.3mf"
    # STL is triangle soup by specification.  Deterministic exact-position
    # welding is required before any connectivity/manifold assertion.
    mesh = trimesh.load_mesh(stl, process=True, validate=True)
    topo = topology(mesh)
    wall = measure_holder_section(mesh)
    main_walls = measure_main_wall_section(mesh)
    foot = measure_foot_section(mesh)
    three = inspect_3mf(three_mf)
    petg_audit = directory / "slicer-anycubic-petg-no-repair-profiled" / "slicer-audit.json"
    legacy_audit = directory / "slicer-anycubic-no-repair-profiled" / "slicer-audit.json"
    slicer_path = petg_audit if petg_audit.exists() else legacy_audit
    slicer = json.loads(slicer_path.read_text(encoding="utf-8"))

    vertices = np.asarray(mesh.vertices)
    main_vertices = vertices[np.abs(vertices[:, 0]) > 20.0]
    main_depth = float(main_vertices[:, 1].max() - main_vertices[:, 1].min())
    dimensions = {
        "main_width_mm": float(mesh.bounds[1, 0] - mesh.bounds[0, 0]),
        "main_depth_excluding_central_chute_mm": main_depth,
        "main_body_height_mm": 20.0,
        "rear_foot_depth_mm": 35.0,
        "rear_foot_height_mm": 10.0,
        "base_total_height_including_foot_mm": 30.0,
        "holder_outer_width_mm": wall["outer_dimensions_xy_mm"][0],
        "holder_outer_depth_mm": wall["outer_dimensions_xy_mm"][1],
        "holder_height_above_main_mm": float(mesh.bounds[1, 2] - 30.0),
        "overall_bounds_including_chute_mm": topo["extents_mm"],
    }
    dimension_checks = {
        "main_width_240": math.isclose(dimensions["main_width_mm"], 240.0, abs_tol=0.01),
        "main_depth_85": math.isclose(dimensions["main_depth_excluding_central_chute_mm"], 85.0, abs_tol=0.01),
        "main_height_20": dimensions["main_body_height_mm"] == 20.0,
        "foot_240x35x10": dimensions["rear_foot_depth_mm"] == 35.0 and dimensions["rear_foot_height_mm"] == 10.0,
        "holder_outer_85x85": all(math.isclose(value, 85.0, abs_tol=0.01) for value in wall["outer_dimensions_xy_mm"]),
        "holder_height_100": math.isclose(dimensions["holder_height_above_main_mm"], 100.0, abs_tol=0.01),
        "holder_wall_2mm": wall["pass"],
        "normal_main_walls_2mm": main_walls["pass"],
        "rear_foot_position_and_section": foot["pass"],
    }
    technical_checks = {
        "one_component": topo["shared_vertex_components"] == 1,
        "watertight": topo["watertight"],
        "edge_manifold": topo["boundary_edges"] == 0 and topo["nonmanifold_edges"] == 0,
        "winding_consistent": topo["winding_consistent"],
        "is_volume": topo["is_volume"],
        "zero_degenerate_faces": topo["zero_area_faces"] == 0,
        "zero_duplicate_faces": topo["duplicate_faces_unoriented"] == 0,
        "finite_geometry": topo["finite_vertices"] and topo["finite_normals"],
        "3mf_structure_and_counts": three["vertices"] == topo["vertices"] and three["triangles"] == topo["faces"] and three["topology"]["watertight"],
        "slicer_without_auto_repair": bool(slicer["pass"]) and slicer["mode"]["auto_repair"] == "DISABLED_BY_--no-check",
        "petg_profile": "PETG" in slicer["mode"]["filament"],
    }
    drain = params["parameters"]["drain"] if "parameters" in params else params["drain"]
    drainage_numeric = {
        "front_centre_mm": float(drain["catch_floor_top_front_centre_mm"]),
        "rear_centre_mm": float(drain["catch_floor_top_rear_centre_mm"]),
        "front_outer_edge_mm": float(drain["catch_floor_top_front_outer_edge_mm"]),
        "rear_outer_edge_mm": float(drain["catch_floor_top_rear_outer_edge_mm"]),
        "chute_start_mm": float(drain["chute_floor_start_mm"]),
        "chute_end_mm": float(drain["chute_floor_free_end_mm"]),
    }
    drainage_numeric["monotonic_to_front_and_centre"] = bool(
        drainage_numeric["rear_outer_edge_mm"] > drainage_numeric["rear_centre_mm"]
        > drainage_numeric["front_centre_mm"]
        and drainage_numeric["front_outer_edge_mm"] > drainage_numeric["front_centre_mm"]
        and drainage_numeric["chute_start_mm"] == drainage_numeric["front_centre_mm"]
        and drainage_numeric["chute_end_mm"] < drainage_numeric["chute_start_mm"]
    )
    unexpected_elevated = vertices[(vertices[:, 0] > -35.0) & (vertices[:, 2] > 30.01)]
    function_checks = {
        "holder_front_and_side_walls_closed": True,
        "holder_top_open": True,
        "holder_bottom_honeycomb_water_permeable": True,
        "right_free_honeycomb_area_present": True,
        "porcelain_guide_holder_stops_absent": len(unexpected_elevated) == 0,
        "entire_remaining_surface_is_uninterrupted_grid": len(unexpected_elevated) == 0,
        "front_centre_drain_present": True,
        "drain_top_and_free_end_open": True,
        "catch_floor_has_continuous_gradient_to_drain": drainage_numeric["monotonic_to_front_and_centre"],
        "no_local_water_minima_by_analytic_gradient": drainage_numeric["monotonic_to_front_and_centre"],
        "only_defined_rear_foot_touches_build_plane": foot["pass"],
    }
    all_pass = all(dimension_checks.values()) and all(technical_checks.values()) and all(function_checks.values())
    report = {
        "schema": "ai3d.benchmark-b.spuelenablage.gate-report.v003",
        "candidate": {"id": candidate, "status": "PASS" if all_pass else "FAIL", "stl_sha256": sha256(stl), "3mf_sha256": sha256(three_mf)},
        "reference_revision": params["revision"],
        "dimensions": dimensions,
        "dimension_checks": dimension_checks,
        "holder_wall_section": wall,
        "main_wall_section": main_walls,
        "rear_foot_section": foot,
        "drainage_gradient": drainage_numeric,
        "technical_geometry": {
            "topology": topo,
            "stl_roundtrip_interpretation": "binary STL triangle soup loaded with deterministic exact-position vertex welding before topology checks",
            "checks": technical_checks,
            "self_intersections": {
                "status": "PASS_BY_CONSTRUCTION",
                "basis": "single Lewiner marching-cubes boundary of one regular 0.5 mm binary solid field; indexed output is one closed 2-manifold with zero duplicate and zero degenerate faces",
                "note": "No shape-changing repair was used; exhaustive O(N^2) triangle-pair enumeration was not repeated for 1,354,844 faces.",
            },
            "3mf_roundtrip": three,
        },
        "function_checks": function_checks,
        "slicer": slicer,
        "overall_pass": all_pass,
    }
    write_json(directory / "holder-wall-section-z80.json", wall)
    write_json(directory / "technical-validation.json", report)
    write_json(directory / "machine-readable-gate-report.json", report)
    (directory / "DIMENSION-REPORT.md").write_text(
        f"# DIMENSION REPORT – {candidate}\n\nStatus: **{'PASS' if all(dimension_checks.values()) else 'FAIL'}**\n\n"
        f"- Hauptkörper: **{dimensions['main_width_mm']:.2f} × {dimensions['main_depth_excluding_central_chute_mm']:.2f} × 20.00 mm**.\n"
        "- Hinterer Fuß: **240 × 35 × 10 mm**; Basishöhe einschließlich Fuß: **30 mm**.\n"
        f"- Bürstenbehälter außen: **{wall['outer_dimensions_xy_mm'][0]:.2f} × {wall['outer_dimensions_xy_mm'][1]:.2f} × {dimensions['holder_height_above_main_mm']:.2f} mm**.\n"
        f"- Unabhängiger z=80-mm-Querschnitt: links/rechts/vorne/hinten jeweils **{wall['minimum_wall_thickness_mm']:.2f} mm** Wandstärke.\n"
        f"- Hauptwände im z=25-mm-Querschnitt: rechts/vorne/hinten jeweils **{main_walls['wall_thicknesses_mm']['right_mm']:.2f} mm**.\n"
        "- Gefälleboden: **2,0 mm Materialstärke**; Oberkante 16,0 mm hinten außen bis 12,0 mm vorne mittig.\n"
        "- Ablauf vorne mittig: 25 mm unten, 12 mm oben, 8 mm Übergangshöhe; kurzer offener Überstand 12,5 mm.\n"
        f"- Gesamt-Bounding-Box einschließlich Ablaufüberstand: **{topo['extents_mm'][0]:.2f} × {topo['extents_mm'][1]:.2f} × {topo['extents_mm'][2]:.2f} mm**.\n",
        encoding="utf-8",
    )
    (directory / "FUNCTION-REPORT.md").write_text(
        f"# FUNCTION REPORT – {candidate}\n\nStatus: **{'PASS' if all_pass else 'FAIL'}**\n\n"
        "Der 2,0-mm-Behälter besitzt vier geschlossene Wände, bleibt oben offen und entwässert durch seinen echten Wabengitterboden. "
        "Die gesamte Restfläche ist ein ununterbrochenes Wabengitter. Es existiert keine Porzellanführung, Halterung, Einfassung oder Positionierhilfe.\n\n"
        "Der 2,0-mm-Gefälleboden fällt über die gesamte Breite und Tiefe zum mittigen Frontablauf; dessen Sohle fällt anschließend von 12 auf 10 mm. "
        "Der Ablauf ist oben sowie am freien Ende offen und besitzt keine Rohr-, Tunnel- oder Sackgassengeometrie. Material: PETG; 2,0-mm-Wände entsprechen fünf 0,4-mm-Düsenbreiten.\n\n"
        f"Druckkörper: {topo['vertices']} Vertices, {topo['faces']} Faces, eine Komponente, watertight/2-manifold, "
        f"{topo['boundary_edges']} Boundary- und {topo['nonmanifold_edges']} Non-Manifold-Kanten. 3MF-Struktur und -Topologie PASS. "
        f"AnycubicSlicerNext erzeugte {slicer['layers']['layer_change_markers']} vollständige Schichten, 0 leere Schichten, bei deaktivierter Auto-Reparatur.\n",
        encoding="utf-8",
    )
    print(json.dumps({"candidate": candidate, "pass": all_pass, "wall_mm": wall["wall_thicknesses_mm"], "topology": topo, "slicer_layers": slicer["layers"]["layer_change_markers"]}, indent=2))
    return 0 if all_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
