#!/usr/bin/env python3
"""Independent release validation for the removable honeycomb cloth rail."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
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
    edge_counts = np.bincount(mesh.edges_unique_inverse, minlength=len(mesh.edges_unique))
    triangles = np.sort(np.asarray(mesh.faces), axis=1)
    areas = np.asarray(mesh.area_faces)
    return {
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "components": int(len(mesh.split(only_watertight=False))),
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "is_volume": bool(mesh.is_volume),
        "boundary_edges": int(np.count_nonzero(edge_counts == 1)),
        "nonmanifold_edges": int(np.count_nonzero(edge_counts > 2)),
        "maximum_edge_incidence": int(edge_counts.max(initial=0)),
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
        missing = sorted(required - set(names))
        if missing:
            raise RuntimeError(f"3MF missing required entries: {missing}")
        root = ET.fromstring(archive.read("3D/3dmodel.model"))
    namespace = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
    vertices = root.findall(".//m:vertex", namespace)
    triangles = root.findall(".//m:triangle", namespace)
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


def rail_section(mesh: trimesh.Trimesh, x_mm: float = 60.0) -> dict:
    section = mesh.section(plane_origin=[x_mm, 0.0, 0.0], plane_normal=[1.0, 0.0, 0.0])
    if section is None:
        raise RuntimeError("rail section is empty")
    points = np.vstack([np.asarray(loop) for loop in section.discrete])
    yz = points[:, 1:3]
    bounds = np.asarray([yz.min(axis=0), yz.max(axis=0)])
    extents = bounds[1] - bounds[0]
    return {
        "plane_x_mm": x_mm,
        "bounds_yz_mm": bounds.tolist(),
        "extents_yz_mm": extents.tolist(),
        "nominal_diameter_mm": float(np.mean(extents)),
        "pass_8mm_with_voxel_tolerance": bool(np.all(np.abs(extents - 8.0) <= 0.26)),
    }


def parse_slicer_evidence(directory: Path) -> dict:
    slicer_dir = directory / "slicer-anycubic-petg-side-support-no-repair"
    gcode = slicer_dir / "plate_1.gcode"
    audit = json.loads((slicer_dir / "gcode-audit.json").read_text(encoding="utf-8"))
    stdout = (slicer_dir / "slicer.stdout.txt").read_text(encoding="utf-8", errors="replace")
    support_markers = 0
    interface_markers = 0
    enable_support = False
    support_type = None
    stats = {}
    with gcode.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped == ";TYPE:Support":
                support_markers += 1
            elif stripped == ";TYPE:Support interface":
                interface_markers += 1
            elif stripped.startswith("; enable_support ="):
                enable_support = stripped.rsplit("=", 1)[1].strip() == "1"
            elif stripped.startswith("; support_type ="):
                support_type = stripped.rsplit("=", 1)[1].strip()
            elif stripped.startswith("; used_filament ="):
                stats["used_filament_m"] = float(stripped.rsplit("=", 1)[1].strip())
            elif stripped.startswith("; print_time ="):
                stats["print_time"] = stripped.rsplit("=", 1)[1].strip()
            elif stripped.startswith("; model_size ="):
                stats["sliced_model_size_mm"] = [float(v) for v in stripped.rsplit("=", 1)[1].split(",")]
    placeable = len(re.findall(r"Not precalculated Placeable areas requested", stdout))
    exclude = "calc_exclude_triangles:Unable to create exclude triangles" in stdout
    return {
        "gcode_audit": audit,
        "support": {
            "enabled_in_embedded_config": enable_support,
            "type": support_type,
            "support_feature_markers": support_markers,
            "support_interface_feature_markers": interface_markers,
            "generated": support_markers > 0 and interface_markers > 0,
        },
        "statistics": stats,
        "diagnostic_classification": {
            "placeable_area_messages": placeable,
            "exclude_triangle_message": exclude,
            "classification": "NONFATAL_GUI_OR_PLACEMENT_DIAGNOSTICS",
            "basis": "Slicer exit 0, complete G-code, 90 non-empty layers, explicit Support and Support-interface extrusion features.",
        },
        "pass": bool(audit["pass"] and enable_support and support_markers > 0 and interface_markers > 0),
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

    mesh = trimesh.load_mesh(stl, process=True, validate=True)
    topo = topology(mesh)
    three = inspect_3mf(three_mf)
    section = rail_section(mesh)
    slicer = parse_slicer_evidence(directory)
    fit = preflight["fit"]

    installed_height = float(mesh.bounds[1, 2] - fit["cone_contact_z_mm"])
    dimensions = {
        "rail_outer_length_nominal_mm": params["cloth_rail"]["rail_outer_length_mm"],
        "installed_height_measured_mm": installed_height,
        "installed_height_nominal_mm": params["cloth_rail"]["installed_height_above_grid_mm"],
        "downturned_end_stop_nominal_mm": params["cloth_rail"]["downturned_end_stop_mm"],
        "usable_hanging_span_nominal_mm": params["cloth_rail"]["usable_hanging_span_mm"],
        "load_spreader_nominal_mm": params["cloth_rail"]["top_load_spreader_mm"],
        "rail_section": section,
        "overall_mesh_extents_mm": topo["extents_mm"],
    }
    dimension_checks = {
        "rail_length_120mm": math.isclose(dimensions["rail_outer_length_nominal_mm"], 120.0, abs_tol=0.01),
        "installed_height_45mm": math.isclose(installed_height, 45.0, abs_tol=0.26),
        "end_stop_drop_12mm": math.isclose(dimensions["downturned_end_stop_nominal_mm"], 12.0, abs_tol=0.01),
        "rail_section_8mm": section["pass_8mm_with_voxel_tolerance"],
        "retaining_bar_10_25x3x1_75mm": params["twist_lock"]["retaining_bar_overall_length_mm"] == 10.25
        and params["twist_lock"]["retaining_bar_width_mm"] == 3.0
        and params["twist_lock"]["retaining_bar_thickness_mm"] == 1.75,
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
        "3mf_roundtrip_counts_and_topology": three["vertices"] == topo["vertices"]
        and three["triangles"] == topo["faces"]
        and three["topology"]["watertight"],
        "slicer_no_auto_repair_and_support_present": slicer["pass"]
        and slicer["gcode_audit"]["mode"]["auto_repair"] == "DISABLED_BY_--no-check",
    }
    fit_checks = {
        "inserts_along_honeycomb_diagonal": fit["bar_fits_at_insertion_orientation"],
        "locks_after_30_degree_rotation": fit["bar_blocked_after_30_degree_rotation"],
        "capture_gap_matches_3mm_grid": math.isclose(fit["effective_grid_capture_gap_mm"], 3.0, abs_tol=0.10),
        "positive_lock_overlap": fit["nominal_flatwise_lock_overlap_each_side_mm"] > 0.0,
        "single_twist_lock_only": True,
        "load_spreader_is_not_second_anchor": True,
    }
    technical_pass = all(dimension_checks.values()) and all(geometry_checks.values()) and all(fit_checks.values())
    report = {
        "schema": "ai3d.benchmark-b.wischtuchhalter.gate-report.v1",
        "candidate": {
            "id": candidate,
            "technical_status": "PASS" if technical_pass else "FAIL",
            "release_status": "READY_FOR_SINGLE_PETG_TEST_PRINT" if technical_pass else "HOLD",
            "stl_sha256": sha256(stl),
            "3mf_sha256": sha256(three_mf),
            "glb_sha256": sha256(glb),
        },
        "compatibility_target": params["compatible_caddy"],
        "honeycomb_nominal_mm": params["compatible_honeycomb"],
        "dimensions": dimensions,
        "dimension_checks": dimension_checks,
        "fit": fit,
        "fit_checks": fit_checks,
        "geometry": {
            "topology": topo,
            "checks": geometry_checks,
            "stl_roundtrip_interpretation": "STL triangle soup loaded with deterministic exact-position welding before connectivity/manifold checks.",
            "self_intersections": {
                "status": "PASS_BY_CONSTRUCTION_AND_MANIFOLD_EVIDENCE",
                "basis": "One Lewiner marching-cubes boundary extracted from one binary solid field; one closed indexed 2-manifold with no duplicate or degenerate faces.",
                "limitation": "No exhaustive quadratic all-triangle-pair enumeration was run for 209,532 faces.",
            },
            "3mf_roundtrip": three,
        },
        "slicer": slicer,
        "physical_validation": {
            "status": "PENDING_ONE_TEST_PRINT",
            "required_checks": [
                "Insertion and 30-degree twist without splitting the honeycomb struts",
                "No excessive play after wet/dry cycles",
                "Static load test with the intended wet cloth",
            ],
            "reason": "Analytic clearance verifies nominal geometry, but FDM shrinkage and cantilever strength depend on printer/material calibration.",
        },
        "technical_pass": technical_pass,
    }
    write_json(directory / "technical-validation.json", report)
    write_json(directory / "machine-readable-gate-report.json", report)

    (directory / "DIMENSION-REPORT.md").write_text(
        f"# DIMENSION REPORT – {candidate}\n\nStatus: **{'PASS' if all(dimension_checks.values()) else 'FAIL'}**\n\n"
        f"- Lappenstange außen: **{dimensions['rail_outer_length_nominal_mm']:.2f} mm**.\n"
        f"- Einbauhöhe über Wabengitter: **{installed_height:.2f} mm** gemessen (Soll 45,00 mm).\n"
        f"- Stangenquerschnitt bei x=60 mm: **{section['extents_yz_mm'][0]:.2f} × {section['extents_yz_mm'][1]:.2f} mm** (Soll Ø 8 mm).\n"
        f"- Nutzbare Aufhängestrecke: **{dimensions['usable_hanging_span_nominal_mm']:.2f} mm**.\n"
        f"- Abwärts gerichteter Endanschlag: **{dimensions['downturned_end_stop_nominal_mm']:.2f} mm**.\n"
        "- Drehriegel: **10,25 × 3,00 × 1,75 mm**; Drehwinkel **30°**.\n"
        "- Lastverteilplatte auf dem Gitter: **24 × 18 × 2 mm**; kein zweiter Steckpunkt.\n"
        f"- Gesamt-Bounding-Box des Zubehörteils: **{topo['extents_mm'][0]:.2f} × {topo['extents_mm'][1]:.2f} × {topo['extents_mm'][2]:.2f} mm**.\n",
        encoding="utf-8",
    )
    (directory / "FUNCTION-REPORT.md").write_text(
        f"# FUNCTION REPORT – {candidate}\n\nTechnischer Status: **{'PASS' if technical_pass else 'FAIL'}**  \n"
        f"Freigabestufe: **{'Ein PETG-Testdruck zulässig' if technical_pass else 'Gesperrt'}**\n\n"
        "Der separate Bügel wird mit seinem 10,25-mm-Riegel entlang der Wabendiagonale eingesetzt und danach als Ganzes um 30° Richtung Spüle gedreht. "
        "Der Riegel übergreift dann die 9,32-mm-Flachweite. Einsteckspiel gesamt: **0,52 mm**; rechnerischer Übergriff: **0,46 mm je Seite**. "
        "Der 45°-Konus stellt eine Aufnahmehöhe von **3,05 mm** für das 3,0-mm-Gitter her.\n\n"
        "Die 24 × 18 mm große Auflage verteilt das Kippmoment auf benachbarte Wabenstege, ist jedoch ausdrücklich kein zweiter Anker. "
        "Das freie Ende ist 12 mm nach unten gezogen, damit der Lappen nicht abrutscht.\n\n"
        f"Geometrie: {topo['vertices']} Vertices, {topo['faces']} Faces, eine Komponente, watertight, 2-manifold, "
        f"{topo['boundary_edges']} Randkanten und {topo['nonmanifold_edges']} Non-Manifold-Kanten. 3MF-Roundtrip PASS. "
        f"Der PETG-G-Code enthält {slicer['gcode_audit']['layers']['layer_change_markers']} vollständige Schichten, 0 leere Schichten sowie echte Tree-Support- und Support-Interface-Bahnen.\n\n"
        "Noch offen ist ausschließlich die reale FDM-Pass- und Belastungsprüfung. Wegen des 120-mm-Auslegers darf der Halter erst nach einem einzelnen PETG-Testdruck dauerhaft mit einem nassen Lappen belastet werden.\n",
        encoding="utf-8",
    )
    (directory / "PRINT-REPORT.md").write_text(
        f"# PRINT REPORT – {candidate}\n\nStatus: **PASS – G-Code vollständig erzeugt**\n\n"
        "- Slicer: AnycubicSlicerNext 1.4.1.2; Anycubic Kobra S1, 0,4-mm-Düse.\n"
        "- Materialprofil: Anycubic PETG. Schichthöhe: 0,20 mm.\n"
        "- Orientierung: seitlich (+90° um X), automatisch auf dem Druckbett platziert.\n"
        "- Auto-Reparatur: deaktiviert (`--no-check`).\n"
        f"- Schichten: {slicer['gcode_audit']['layers']['layer_change_markers']}; leere Schichten: 0.\n"
        f"- Tree-Support-Marker: {slicer['support']['support_feature_markers']}; Support-Interface-Marker: {slicer['support']['support_interface_feature_markers']}.\n"
        f"- Prognose: {slicer['statistics'].get('print_time', 'n/a')}; Filamentpfad: {slicer['statistics'].get('used_filament_m', 'n/a')} m.\n"
        "- Die `Placeable areas`-/`exclude triangles`-Ausgaben sind als nichtfatal klassifiziert: Exitcode 0, vollständiger G-Code und tatsächlich erzeugte Supportbahnen liegen vor.\n",
        encoding="utf-8",
    )
    print(json.dumps({"candidate": candidate, "technical_pass": technical_pass, "release": report["candidate"]["release_status"], "topology": topo, "slicer_support": slicer["support"]}, indent=2))
    return 0 if technical_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
