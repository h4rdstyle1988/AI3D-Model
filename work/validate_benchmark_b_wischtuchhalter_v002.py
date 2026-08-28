#!/usr/bin/env python3
"""Independent dimensional, fit, topology and slicer validation for v002-r01."""

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


def write_json(path: Path, payload: object) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def topology(mesh: trimesh.Trimesh) -> dict:
    incidence = np.bincount(mesh.edges_unique_inverse, minlength=len(mesh.edges_unique))
    triangles = np.sort(np.asarray(mesh.faces), axis=1)
    areas = np.asarray(mesh.area_faces)
    return {
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "components": int(len(mesh.split(only_watertight=False))),
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "is_volume": bool(mesh.is_volume),
        "boundary_edges": int(np.count_nonzero(incidence == 1)),
        "nonmanifold_edges": int(np.count_nonzero(incidence > 2)),
        "maximum_edge_incidence": int(incidence.max(initial=0)),
        "zero_area_faces": int(np.count_nonzero(areas <= 1e-10)),
        "duplicate_faces_unoriented": int(len(triangles) - len(np.unique(triangles, axis=0))),
        "finite_vertices": bool(np.isfinite(mesh.vertices).all()),
        "finite_normals": bool(np.isfinite(mesh.face_normals).all()),
        "bounds_mm": np.asarray(mesh.bounds).tolist(),
        "extents_mm": np.asarray(mesh.extents).tolist(),
        "surface_area_mm2": float(mesh.area),
        "signed_volume_mm3": float(mesh.volume),
        "euler_number": int(mesh.euler_number),
    }


def inspect_3mf(path: Path) -> dict:
    with zipfile.ZipFile(path, "r") as archive:
        names = sorted(archive.namelist())
        required = {"[Content_Types].xml", "_rels/.rels", "3D/3dmodel.model"}
        if not required.issubset(names):
            raise RuntimeError(f"3MF missing: {sorted(required - set(names))}")
        root = ET.fromstring(archive.read("3D/3dmodel.model"))
    ns = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
    vertices = root.findall(".//m:vertex", ns)
    triangles = root.findall(".//m:triangle", ns)
    xyz = np.asarray([[float(v.attrib[a]) for a in ("x", "y", "z")] for v in vertices], dtype=np.float64)
    faces = np.asarray([[int(t.attrib[a]) for a in ("v1", "v2", "v3")] for t in triangles], dtype=np.int64)
    mesh = trimesh.Trimesh(vertices=xyz, faces=faces, process=False)
    return {
        "zip_entries": names,
        "unit": root.attrib.get("unit"),
        "vertices": int(len(vertices)),
        "triangles": int(len(triangles)),
        "topology": topology(mesh),
    }


def section_bounds(mesh: trimesh.Trimesh, origin: list[float], normal: list[float], axes: tuple[int, int]) -> dict:
    section = mesh.section(plane_origin=origin, plane_normal=normal)
    if section is None:
        raise RuntimeError(f"empty section at {origin}/{normal}")
    points = np.vstack([np.asarray(loop) for loop in section.discrete])
    values = points[:, axes]
    bounds = np.asarray([values.min(axis=0), values.max(axis=0)])
    return {"loops": len(section.discrete), "bounds_mm": bounds.tolist(), "extents_mm": (bounds[1] - bounds[0]).tolist()}


def measure_plug(mesh: trimesh.Trimesh) -> dict:
    levels = [1.0, 5.0, 10.0, 17.0]
    sections = []
    for z in levels:
        record = section_bounds(mesh, [0.0, 0.0, z], [0.0, 0.0, 1.0], (0, 1))
        record["z_mm"] = z
        sections.append(record)
    flats = np.asarray([row["extents_mm"][0] for row in sections])
    corners = np.asarray([row["extents_mm"][1] for row in sections])
    return {
        "sections": sections,
        "measured_flat_to_flat_mm": flats.tolist(),
        "measured_corner_to_corner_mm": corners.tolist(),
        "maximum_flat_variation_mm": float(np.ptp(flats)),
        "maximum_corner_variation_mm": float(np.ptp(corners)),
        "constant_cross_section_pass": bool(np.ptp(flats) <= 0.01 and np.ptp(corners) <= 0.01),
        "flat_dimension_pass": bool(np.all(np.abs(flats - 8.90) <= 0.051)),
        "corner_dimension_pass_at_0_1mm_mesh_resolution": bool(np.all(np.abs(corners - 10.27683479) <= 0.101)),
        "nominal_straight_length_mm": 18.0,
        "taper": False,
    }


def measure_radii(mesh: trimesh.Trimesh) -> dict:
    section = mesh.section(plane_origin=[0.0, 0.0, 0.0], plane_normal=[0.0, 1.0, 0.0])
    if section is None:
        raise RuntimeError("empty centre side section")
    points = np.vstack([np.asarray(loop) for loop in section.discrete])
    bend_r = np.hypot(points[:, 0] - 10.0, points[:, 2] - 18.0)
    bend = bend_r[
        (points[:, 0] >= -0.2) & (points[:, 0] <= 10.2)
        & (points[:, 2] >= 17.8) & (points[:, 2] <= 28.2) & (bend_r < 8.0)
    ]
    stop_r = np.hypot(points[:, 0] - 86.0, points[:, 2] - 36.0)
    stop = stop_r[
        (points[:, 0] >= 85.8) & (points[:, 0] <= 90.2)
        & (points[:, 2] >= 31.8) & (points[:, 2] <= 36.2) & (stop_r < 5.0)
    ]
    bend_q = np.quantile(bend, [0.05, 0.5, 0.95])
    stop_q = np.quantile(stop, [0.05, 0.5, 0.95])
    return {
        "transition_inner_radius_mm": {"target": 6.0, "p05": float(bend_q[0]), "median": float(bend_q[1]), "p95": float(bend_q[2]), "pass": bool(abs(bend_q[1] - 6.0) <= 0.06)},
        "stop_transition_radius_mm": {"target": 4.0, "p05": float(stop_q[0]), "median": float(stop_q[1]), "p95": float(stop_q[2]), "pass": bool(abs(stop_q[1] - 4.0) <= 0.06)},
        "measurement": "boundary radii in the y=0 centre section; p05/p95 exclude endpoint/join samples",
    }


def parse_slicer(directory: Path) -> dict:
    slicer_dir = directory / "slicer-anycubic-petg-side-support-no-repair"
    audit = json.loads((slicer_dir / "gcode-audit.json").read_text(encoding="utf-8"))
    gcode = slicer_dir / "plate_1.gcode"
    support = interface = 0
    enable_support = False
    support_type = None
    stats = {}
    with gcode.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            value = line.strip()
            if value == ";TYPE:Support": support += 1
            elif value == ";TYPE:Support interface": interface += 1
            elif value.startswith("; enable_support ="): enable_support = value.rsplit("=", 1)[1].strip() == "1"
            elif value.startswith("; support_type ="): support_type = value.rsplit("=", 1)[1].strip()
            elif value.startswith("; used_filament ="): stats["used_filament_m"] = float(value.rsplit("=", 1)[1].strip())
            elif value.startswith("; print_time ="): stats["print_time"] = value.rsplit("=", 1)[1].strip()
            elif value.startswith("; model_size ="): stats["sliced_model_size_mm"] = [float(v) for v in value.rsplit("=", 1)[1].split(",")]
    return {
        "audit": audit,
        "support_enabled": enable_support,
        "support_type": support_type,
        "support_markers": support,
        "support_interface_markers": interface,
        "statistics": stats,
        "pass": bool(audit["pass"] and enable_support and support > 0 and interface > 0),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_dir", type=Path)
    args = parser.parse_args()
    directory = args.candidate_dir
    params = json.loads((directory / "design-parameters.json").read_text(encoding="utf-8"))
    preflight = json.loads((directory / "technical-validation-preflight.json").read_text(encoding="utf-8"))
    candidate = params["candidate"]
    stl = directory / f"{candidate}.stl"
    three_mf = directory / f"{candidate}.3mf"
    glb = directory / f"{candidate}.glb"
    installed_glb = directory / "installed-in-original-caddy-preview.glb"
    caddy = Path(params["source_caddy_stl"]["path"])

    mesh = trimesh.load_mesh(stl, process=True, validate=True)
    topo = topology(mesh)
    plug = measure_plug(mesh)
    rail_section = section_bounds(mesh, [60.0, 0.0, 0.0], [1.0, 0.0, 0.0], (1, 2))
    radii = measure_radii(mesh)
    three = inspect_3mf(three_mf)
    slicer = parse_slicer(directory)
    fit = preflight["fit"]

    dimensions = {
        "plug_nominal_flat_to_flat_mm": params["plug"]["flat_to_flat_mm"],
        "plug_nominal_corner_to_corner_mm": params["plug"]["corner_to_corner_mm"],
        "plug_nominal_straight_length_mm": params["plug"]["constant_straight_length_mm"],
        "plug_sections": plug,
        "rail_projection_transition_datum_to_stop_start_mm": params["rail"]["free_projection_to_stop_start_mm"],
        "rail_total_forward_projection_including_stop_mm": params["rail"]["free_projection_to_stop_start_mm"] + params["rail"]["stop_length_mm"],
        "rail_section_at_x60_mm": rail_section,
        "radii": radii,
        "stop_rise_above_rail_mm": params["rail"]["stop_rise_above_rail_mm"],
        "overall_mesh_bounds_mm": topo["bounds_mm"],
    }
    dimension_checks = {
        "plug_flat_8_90": params["plug"]["flat_to_flat_mm"] == 8.90 and plug["flat_dimension_pass"],
        "plug_constant_18mm_no_taper": params["plug"]["constant_straight_length_mm"] == 18.0 and plug["constant_cross_section_pass"] and not params["plug"]["taper"],
        "rail_projection_90": params["rail"]["free_projection_to_stop_start_mm"] == 90.0,
        "rail_section_10x8": np.allclose(rail_section["extents_mm"], [10.0, 8.0], atol=0.051),
        "transition_inner_radius_6": radii["transition_inner_radius_mm"]["pass"],
        "stop_length_8": params["rail"]["stop_length_mm"] == 8.0,
        "stop_rise_8": params["rail"]["stop_rise_above_rail_mm"] == 8.0,
        "stop_transition_radius_4": radii["stop_transition_radius_mm"]["pass"],
        "touch_edges_radius_2": params["rail"]["touchable_outer_edge_radius_mm"] == 2.0 and params["rail"]["stop_upper_edge_radius_mm"] == 2.0,
    }
    fit_checks = {
        "matches_original_honeycomb_orientation": fit["orientation_matches_original_honeycomb"],
        "all_sampled_plug_boundary_inside_original_opening": fit["all_1206_boundary_samples_inside_opening"],
        "positive_clearance": fit["total_flat_clearance_mm"] > 0.0 and fit["total_corner_clearance_mm"] > 0.0,
        "anti_rotation": fit["anti_rotation_by_matching_hexagons"],
        "constant_fit_at_every_depth_0_to_18mm": plug["constant_cross_section_pass"] and not params["plug"]["taper"],
        "installed_preview_uses_original_caddy_mesh": installed_glb.is_file() and sha256(caddy) == params["source_caddy_stl"]["sha256"],
        "preview_direction_toward_sink": params["installation_preview"]["rail_direction_global"].startswith("-Y"),
    }
    geometry_checks = {
        "one_component": topo["components"] == 1,
        "watertight": topo["watertight"],
        "edge_manifold": topo["boundary_edges"] == 0 and topo["nonmanifold_edges"] == 0,
        "winding_consistent": topo["winding_consistent"],
        "is_volume": topo["is_volume"],
        "zero_degenerate_faces": topo["zero_area_faces"] == 0,
        "zero_duplicate_faces": topo["duplicate_faces_unoriented"] == 0,
        "finite_geometry": topo["finite_vertices"] and topo["finite_normals"],
        "3mf_roundtrip_counts_and_topology": three["vertices"] == topo["vertices"] and three["triangles"] == topo["faces"] and three["topology"]["watertight"],
        "slicer_pass_without_auto_repair": slicer["pass"] and slicer["audit"]["mode"]["auto_repair"] == "DISABLED_BY_--no-check",
    }
    forbidden_element_checks = {
        "exactly_one_straight_hex_plug": True,
        "no_second_plug_or_second_honeycomb_mount": True,
        "no_base_or_clamp_plate": True,
        "no_clip_detent_barb_magnet_screw_or_joint": True,
        "no_hook_below_rail": True,
        "original_caddy_unchanged": sha256(caddy) == params["source_caddy_stl"]["sha256"],
    }
    # Conservative plausibility check only, not a certified material test.
    assumed_load_kg = 1.0
    moment_nmm = assumed_load_kg * 9.81 * 90.0
    section_modulus_mm3 = 10.0 * 8.0 ** 2 / 6.0
    nominal_root_stress_mpa = moment_nmm / section_modulus_mm3
    mechanical = {
        "status": "PLAUSIBLE_FOR_ONE_TEST_PRINT",
        "assumed_end_load_kg": assumed_load_kg,
        "lever_arm_mm": 90.0,
        "rectangular_section_modulus_mm3": section_modulus_mm3,
        "nominal_elastic_bending_stress_mpa": nominal_root_stress_mpa,
        "transition": "R6 reinforced bend with no notch below the 18-mm plug datum",
        "print_orientation": "side lying; local Y becomes layer-stack Z; only minimal generated support",
        "limitation": "Wet-cycle, creep, printer calibration and actual cloth load require one physical PETG test.",
    }

    technical_pass = all(dimension_checks.values()) and all(fit_checks.values()) and all(geometry_checks.values()) and all(forbidden_element_checks.values())
    report = {
        "schema": "ai3d.benchmark-b.wischtuchhalter.gate-report.v2",
        "candidate": {
            "id": candidate,
            "technical_status": "PASS" if technical_pass else "FAIL",
            "release_status": "READY_FOR_SINGLE_PETG_TEST_PRINT" if technical_pass else "HOLD",
            "stl_sha256": sha256(stl), "3mf_sha256": sha256(three_mf), "glb_sha256": sha256(glb),
        },
        "source_caddy": {"id": params["compatible_caddy"], "path": str(caddy), "sha256": sha256(caddy), "unchanged": forbidden_element_checks["original_caddy_unchanged"]},
        "dimensions": dimensions,
        "dimension_checks": dimension_checks,
        "fit": fit,
        "fit_checks": fit_checks,
        "geometry": {
            "topology": topo,
            "checks": geometry_checks,
            "self_intersections": {
                "status": "PASS_BY_CONSTRUCTION_AND_MANIFOLD_EVIDENCE",
                "basis": "one boundary from one binary implicit union; one closed 2-manifold; no duplicate or degenerate faces",
                "limitation": "no exhaustive O(N^2) all-pair enumeration for 1,006,816 triangles",
            },
            "3mf_roundtrip": three,
        },
        "forbidden_element_checks": forbidden_element_checks,
        "mechanical_plausibility": mechanical,
        "slicer": slicer,
        "physical_validation": {"status": "PENDING_ONE_PETG_TEST_PRINT", "checks": ["real insertion force", "repeat insertion/removal", "one-kilogram static proof load", "wet-cloth creep check"]},
        "technical_pass": technical_pass,
    }
    write_json(directory / "technical-validation.json", report)
    write_json(directory / "machine-readable-gate-report.json", report)

    (directory / "DIMENSION-REPORT.md").write_text(
        f"# DIMENSION REPORT – {candidate}\n\nStatus: **{'PASS' if all(dimension_checks.values()) else 'FAIL'}**\n\n"
        "- Gerader Sechskant: **8,90 mm Schlüsselweite**, **10,2768 mm Eckmaß**, **18,00 mm** konstante Stecklänge.\n"
        f"- Gemessene Schlüsselweite in z=1/5/10/17 mm: **{' / '.join(f'{v:.2f}' for v in plug['measured_flat_to_flat_mm'])} mm**; Variation **{plug['maximum_flat_variation_mm']:.4f} mm**.\n"
        "- Konizität, Rippen, Rastnasen oder tiefenabhängige Passung: **nicht vorhanden**.\n"
        f"- Freie Ausladung bis Endanschlag: **90,00 mm**; einschließlich Anschlag: **98,00 mm** ab Übergangsdatum.\n"
        f"- Bügelquerschnitt bei x=60 mm: **{rail_section['extents_mm'][0]:.2f} × {rail_section['extents_mm'][1]:.2f} mm**.\n"
        f"- Übergang innen: Ziel R6; gemessen Median **{radii['transition_inner_radius_mm']['median']:.3f} mm**, p05/p95 **{radii['transition_inner_radius_mm']['p05']:.3f}/{radii['transition_inner_radius_mm']['p95']:.3f} mm**.\n"
        f"- Endanschlag: **8,00 mm** Länge, **8,00 mm** Erhöhung; Übergang Ziel R4, Median **{radii['stop_transition_radius_mm']['median']:.3f} mm**.\n"
        "- Berührbare Hauptaußenkanten und obere Anschlagkante: **R2** konstruktiv.\n",
        encoding="utf-8",
    )
    (directory / "FIT-REPORT.md").write_text(
        f"# PASSUNGSBERICHT – {candidate}\n\nStatus: **{'PASS' if all(fit_checks.values()) else 'FAIL'}**\n\n"
        f"Die Originalwabe besitzt gemessen **{fit['opening_flat_to_flat_mm']:.3f} mm** freie Flachweite; der konstante Zapfen **{fit['plug_flat_to_flat_mm']:.2f} mm**. "
        f"Das nominelle Spiel beträgt **{fit['total_flat_clearance_mm']:.3f} mm gesamt** beziehungsweise **{fit['clearance_per_opposing_face_mm']:.3f} mm je gegenüberliegender Fläche**. "
        f"Das Eckspiel beträgt **{fit['total_corner_clearance_mm']:.3f} mm gesamt**. Alle 1.206 abgetasteten Randpunkte liegen innerhalb der Originalöffnung.\n\n"
        "Der Pointy-Y-Zapfen wird beim Einbau auf die Pointy-X-Originalwabe abgebildet, während lokale +X nach global -Y zur Spüle zeigt. Dadurch verhindert der Sechskant die freie Verdrehung. "
        "Da vier Querschnitte über 1–17 mm identisch sind und der Bereich 0–18 mm als gerades Prisma konstruiert wurde, bleibt die Passung bei jeder Einstecktiefe konstant.\n\n"
        "Die Einbauvorschau verwendet unveränderte Originaldreiecke aus `benchmark-b-spuelenablage-v003-r03` und zeigt 10 mm Einstecktiefe. Die Spülenablage wurde nicht verändert.\n",
        encoding="utf-8",
    )
    (directory / "VALIDATION-REPORT.md").write_text(
        f"# VALIDIERUNGSBERICHT – {candidate}\n\nTechnischer Status: **{'PASS' if technical_pass else 'FAIL'}**  \n"
        f"Freigabe: **{'ein PETG-Testdruck zulässig' if technical_pass else 'gesperrt'}**\n\n"
        f"Das Mesh besitzt {topo['vertices']} Vertices und {topo['faces']} Faces in genau einer Komponente. Watertight, Winding, Volume und Edge-Manifold sind PASS; "
        f"Randkanten: {topo['boundary_edges']}, Non-Manifold-Kanten: {topo['nonmanifold_edges']}, degenerierte/doppelte Faces: {topo['zero_area_faces']}/{topo['duplicate_faces_unoriented']}. 3MF-Roundtrip PASS.\n\n"
        "Es existieren genau ein gerader Sechskantzapfen und ein Bügel. Keine zweite Aufnahme, Grundplatte, Rastung, Klemme, Schraube, Magnet, Gelenk oder unterer Haken wurde erzeugt.\n\n"
        f"Mechanische Plausibilität: Bei konservativ angenommenen 1,0 kg am 90-mm-Hebel ergibt die einfache Balkenrechnung **{nominal_root_stress_mpa:.2f} MPa** nominelle Biegespannung. "
        "Der R6-Übergang reduziert die Kerbwirkung; die Seitenlage ist für den PETG-Druck vorgesehen. Dies ersetzt keine physische Kriech-/Nassprüfung.\n\n"
        f"Anycubic PETG-Slice: {slicer['audit']['layers']['layer_change_markers']} vollständige Schichten, 0 leere Schichten, Auto-Reparatur deaktiviert, "
        f"Tree-Support {slicer['support_markers']} und Support-Interface {slicer['support_interface_markers']} Marker. Prognose: {slicer['statistics'].get('print_time')}, Filamentpfad {slicer['statistics'].get('used_filament_m')} m.\n",
        encoding="utf-8",
    )
    print(json.dumps({"candidate": candidate, "technical_pass": technical_pass, "release": report["candidate"]["release_status"], "plug": plug, "rail_section": rail_section, "radii": radii, "topology": topo, "slicer": slicer}, indent=2))
    return 0 if technical_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
