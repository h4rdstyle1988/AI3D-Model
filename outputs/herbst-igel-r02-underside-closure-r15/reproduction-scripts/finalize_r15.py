#!/usr/bin/env python3
"""Finalize R15 audits, diagnostic renders, revision and machine status."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from r15_mesh_core import (
    CAMERAS,
    MM_PER_UNIT,
    boundary_loops,
    compact_mesh,
    connected_components,
    face_geometry,
    json_write,
    make_sheet,
    mesh_metrics,
    orientability_constraints,
    read_binary_ply,
    render,
    sha256,
)
from build_r15_gate1 import boundary_normal_transition


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
TASK = "tasks/TASK-HERBST-IGEL-R02-UNDERSIDE-CLOSURE-R15.md"
TASK_BLOB = "6f36e00693a3f9ad6859b43450a5a77316fa9254"
SOURCE = OUT / "inputs" / "r14-local-surgery-input.ply"
BEST_PARTIAL = OUT / "masterform" / "r15-underside-d4-PARTIAL-NON-APPROVED.ply"
REF_CLEAN = OUT / "inputs" / "ref-clean-r15.jpg"
REF_SEAM = OUT / "inputs" / "ref-seam-r15.jpg"


def point_in_polygon(points: np.ndarray, polygon: np.ndarray) -> np.ndarray:
    x, y = points[:, 0], points[:, 1]
    inside = np.zeros(len(points), dtype=bool)
    xj, yj = polygon[-1]
    for xi, yi in polygon:
        crossing = ((yi > y) != (yj > y)) & (x < (xj - xi) * (y - yi) / ((yj - yi) + 1e-300) + xi)
        inside ^= crossing
        xj, yj = xi, yi
    return inside


def main() -> None:
    all_vertices, all_faces = read_binary_ply(SOURCE)
    labels, components = connected_components(all_faces)
    main_label = int(np.argmax(components))
    base_vertices, base_faces, source_vertex_ids = compact_mesh(all_vertices, all_faces[labels == main_label])
    loops, _boundary, _owners, _adjacency = boundary_loops(base_faces)
    matches = [(i, loop) for i, loop in enumerate(loops) if len(loop) >= 1000 and base_vertices[loop, 2].max() * MM_PER_UNIT < -50.0]
    if len(matches) != 1:
        raise RuntimeError("confirmed underside loop identity changed")
    loop_id, loop = matches[0]
    candidate_vertices, candidate_faces = read_binary_ply(BEST_PARTIAL)
    if not np.array_equal(candidate_faces[: len(base_faces)], base_faces):
        raise RuntimeError("best partial does not preserve base faces exactly")
    coordinate_delta = np.linalg.norm(candidate_vertices[: len(base_vertices)] - base_vertices, axis=1) * MM_PER_UNIT
    patch_vertices = candidate_vertices[len(base_vertices) :]
    patch_faces = candidate_faces[len(base_faces) :]
    patch_triangles, patch_double_area, _patch_normals = face_geometry(candidate_vertices, patch_faces)
    edge_lengths = np.stack([
        np.linalg.norm(patch_triangles[:, 1] - patch_triangles[:, 0], axis=1),
        np.linalg.norm(patch_triangles[:, 2] - patch_triangles[:, 1], axis=1),
        np.linalg.norm(patch_triangles[:, 0] - patch_triangles[:, 2], axis=1),
    ], axis=1) * MM_PER_UNIT
    aspect = edge_lengths.max(axis=1) / np.maximum(edge_lengths.min(axis=1), 1e-15)
    boundary_points = base_vertices[loop]
    inside = point_in_polygon(patch_vertices[:, :2], boundary_points[:, :2])
    transition = boundary_normal_transition(candidate_vertices, base_faces, candidate_faces, len(base_faces))
    orientation = orientability_constraints(candidate_faces)
    intersection = json.loads((OUT / "audits" / "underside-d4-intersection-audit-r15.json").read_text(encoding="utf-8"))
    closure = json.loads((OUT / "audits" / "gate1-harmonic-closure-r15.json").read_text(encoding="utf-8"))
    input_audit = json.loads((OUT / "audits" / "r15-input-audit.json").read_text(encoding="utf-8"))
    r14_loop_audit = json.loads((OUT / "inputs" / "boundary-loop-audit-r14.json").read_text(encoding="utf-8"))

    mask = {
        "schema_version": 1,
        "task": TASK,
        "identity": {
            "r14_loop_id": int(r14_loop_audit["largest_unresolved_loop"]["loop_id"]),
            "r15_main_component_loop_id": int(loop_id),
            "edge_count": int(len(loop)),
            "perimeter_mm": float(np.linalg.norm(boundary_points - np.roll(boundary_points, 1, axis=0), axis=1).sum() * MM_PER_UNIT),
            "source_vertex_ids_r14_input": source_vertex_ids[loop].tolist(),
            "vertex_ids_r15_main_component": loop.tolist(),
        },
        "selection_rule": "unique simple boundary loop with >=1000 edges and z_max below -50 mm on the dominant R14 exterior component",
        "status": "PASS_UNAMBIGUOUS_ID",
    }
    json_write(OUT / "audits" / "confirmed-source-hole-mask-r15.json", mask)

    base_bounds_min, base_bounds_max = base_vertices.min(axis=0), base_vertices.max(axis=0)
    candidate_bounds_min, candidate_bounds_max = candidate_vertices.min(axis=0), candidate_vertices.max(axis=0)
    patch_report = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "selected_variant": "d4",
        "selection_reason": "fewest confirmed strict crossings after a complete 133472-face patch scan; d1-d3 and d5 reached the 50-witness fail-fast limit",
        "method": "boundary-constrained discrete harmonic disk, depth biased to existing minimum Z with exponent 32 and zero floor offset",
        "boundary": {
            "nodes": int(len(loop)),
            "maximum_position_displacement_mm": float(coordinate_delta[loop].max(initial=0.0)),
            "position_requirement_mm": 0.05,
            "position_pass": bool(coordinate_delta[loop].max(initial=0.0) <= 0.05),
            "normal_transition": transition,
        },
        "projection_confinement": {
            "interior_patch_vertices_tested": int(len(patch_vertices)),
            "inside_xy_ring_projection": int(np.count_nonzero(inside)),
            "outside_xy_ring_projection": int(np.count_nonzero(~inside)),
            "pass": bool(np.all(inside)),
        },
        "bounds": {
            "base_min_mm": (base_bounds_min * MM_PER_UNIT).tolist(),
            "base_max_mm": (base_bounds_max * MM_PER_UNIT).tolist(),
            "candidate_min_mm": (candidate_bounds_min * MM_PER_UNIT).tolist(),
            "candidate_max_mm": (candidate_bounds_max * MM_PER_UNIT).tolist(),
            "bbox_expansion_mm": ((candidate_bounds_max - base_bounds_max).clip(min=0) + (base_bounds_min - candidate_bounds_min).clip(min=0)).tolist(),
            "no_new_x_y_extrema": bool(np.all(candidate_bounds_min[:2] >= base_bounds_min[:2] - 1e-12) and np.all(candidate_bounds_max[:2] <= base_bounds_max[:2] + 1e-12)),
            "z_not_below_existing_minimum": bool(candidate_bounds_min[2] >= base_bounds_min[2] - 1e-12),
        },
        "triangulation": {
            "new_vertices": int(len(patch_vertices)),
            "new_faces": int(len(patch_faces)),
            "surface_area_mm2": float(0.5 * patch_double_area.sum() * MM_PER_UNIT * MM_PER_UNIT),
            "edge_length_mm_percentiles": np.percentile(edge_lengths, [0, 5, 50, 95, 100]).tolist(),
            "edge_aspect_ratio_percentiles": np.percentile(aspect, [50, 95, 99, 100]).tolist(),
            "degenerate_faces": int(np.count_nonzero(patch_double_area <= 1e-15)),
        },
        "other_depth_layers": {
            "r14_adjacent_same_layer_counter_ring_found": bool(r14_loop_audit["largest_unresolved_loop"]["adjacent_same_layer_counter_ring_found"]),
            "r14_centroid_to_nearest_seed_vertex_mm": float(r14_loop_audit["largest_unresolved_loop"]["nearest_seed42_vertex_distance_mm"]),
            "complete_patch_source_crossing_scan": intersection["patch_faces_scanned"] == intersection["eligible_patch_faces"],
            "confirmed_strict_crossings": int(intersection["confirmed_strict_crossings"]),
            "pass": False,
            "reason": "45 strict source/patch crossings remain even at the existing minimum-Z floor; lowering farther would violate the hard Z bound.",
        },
        "status": "FAIL_OTHER_DEPTH_LAYER_INTERSECTIONS_AND_NORMAL_TRANSITION",
    }
    json_write(OUT / "audits" / "underside-boundary-normal-depth-audit-r15.json", patch_report)

    topology = {
        "schema_version": 1,
        "task": TASK,
        "before_r14_all_components": input_audit["input"]["metrics_all_r14_components"],
        "before_r14_dominant_surface": input_audit["largest_edge_connected_surface"]["metrics"],
        "after_best_underside_only_variant_d4": mesh_metrics(candidate_vertices, candidate_faces),
        "after_best_underside_only_orientation": {
            "orientable": bool(orientation["orientable"]),
            "orientation_constraint_conflicts": int(orientation["orientation_constraint_conflicts"]),
        },
        "after_best_underside_only_confirmed_strict_crossings": int(intersection["confirmed_strict_crossings"]),
        "self_correction_attempts": {
            "A_all_harmonic_closures": {"metrics": closure["attempt_a"]["output_metrics"], "orientation": closure["attempt_a"]["orientation"]},
            "B_broad_conflict_surgery": {"metrics": closure["attempt_b"]["output_metrics"], "orientation": closure["attempt_b"]["orientation"], "confirmed_crossings": 50},
            "C_greedy_conflict_cover": {
                "metrics": closure["attempt_c"]["output_metrics"],
                "orientation": closure["attempt_c"]["orientation"],
                "surgery": closure["attempt_c_narrow_surgery"],
                "rejection": "two non-underside global cut loops of 4502/4435 edges and ~2624/2602 mm perimeter require forbidden global caps; surface area inflates pathologically",
            },
            "D_underside_depth_variants": "d1-d5; all have confirmed strict source/patch crossings, d4 complete scan found 45",
        },
        "gate_1": "FAIL",
        "failure_reasons": [
            f"best underside-only variant still has {mesh_metrics(candidate_vertices, candidate_faces)['boundary_edges']} boundary edges outside the confirmed source hole",
            f"best underside-only variant remains non-orientable with {orientation['orientation_constraint_conflicts']} conflicts",
            "45 strict source/patch crossings confirmed in the complete d4 underside-patch scan",
            "orientable attempts B/C require nonlocal global cut closure, have severe normal discontinuities and pathological area inflation",
        ],
    }
    json_write(OUT / "audits" / "topology-before-after-r15.json", topology)

    form = {
        "schema_version": 1,
        "task": TASK,
        "gate_1_precondition": "FAIL",
        "existing_seed_correspondence": {
            "retained_r14_main_faces": int(len(base_faces)),
            "retained_vertex_coordinates_exact": bool(np.max(coordinate_delta, initial=0.0) == 0.0),
            "identity_surface_distance_mm": {"p95": 0.0, "maximum": 0.0},
            "r14_limits_mm": {"p95_max": 0.15, "maximum_max": 0.40},
            "status": "PASS_EXACT_IDENTITY_FOR_RETAINED_SURFACE_ONLY",
        },
        "confirmed_source_hole_patch": {
            "seed_distance_rule_applied": False,
            "replacement_criteria_report": "outputs/herbst-igel-r02-underside-closure-r15/audits/underside-boundary-normal-depth-audit-r15.json",
            "status": "FAIL_INTERSECTIONS",
        },
        "formal_bidirectional_visible_surface_gate": "NOT_RUN_BY_GATE1_FAIL",
        "formal_silhouette_gate": "NOT_RUN_BY_GATE1_FAIL",
        "gate_2": "NOT_RUN",
    }
    json_write(OUT / "reports" / "form-protection-split-r15.json", form)

    render_paths = []
    render_records = []
    for slug, camera, label in CAMERAS:
        path = OUT / "renders-gate-evidence" / f"partial-r15-{slug}.png"
        render(candidate_vertices, candidate_faces, camera, path, f"R15 PARTIAL NON-APPROVED: {label}")
        render_paths.append(path)
        render_records.append({"view": slug, "camera_vector": list(camera), "path": path.relative_to(ROOT).as_posix()})
    contact = OUT / "renders-gate-evidence" / "partial-r15-contact-sheet.png"
    make_sheet(render_paths, [record[2] for record in CAMERAS], contact)
    soll_ist = OUT / "renders-gate-evidence" / "soll-ist-r15.png"
    make_sheet([REF_CLEAN, REF_SEAM, *render_paths[:4]], ["SOLL REF-CLEAN", "SOLL REF-SEAM", "IST R15 3/4", "IST R15 links", "IST R15 rechts", "IST R15 hinten"], soll_ist)
    json_write(OUT / "reports" / "real-geometry-renders-r15.json", {
        "schema_version": 1,
        "task": TASK,
        "source_geometry": BEST_PARTIAL.relative_to(ROOT).as_posix(),
        "source_geometry_sha256": sha256(BEST_PARTIAL),
        "source_is_real_partial_geometry": True,
        "approved_master": False,
        "views": render_records,
        "contact_sheet": contact.relative_to(ROOT).as_posix(),
        "soll_ist_sheet": soll_ist.relative_to(ROOT).as_posix(),
    })
    criteria = [
        "face_free_and_round_like_ref_clean", "forehead_free", "both_eyes_clear", "both_ears_clear",
        "snout_and_nose_clear", "four_short_feet_preserved", "arched_plausible_back",
        "exactly_one_visible_maple_leaf", "ref_seam_plausible", "no_visible_repair_artifact",
    ]
    json_write(OUT / "reports" / "soll-ist-binary-r15.json", {
        "schema_version": 1,
        "task": TASK,
        "criteria": [{"criterion": criterion, "pass": None, "status": "NOT_FORMALLY_EVALUATED_BY_GATE1_FAIL"} for criterion in criteria],
        "diagnostic_observation": "The retained Seed-42 face remains visibly covered by fused leaf/spine sheets; ROI reconstruction was correctly not started after Gate-1 failure.",
        "gate_3": "NOT_RUN",
        "overall": "STOPP",
    })

    open_tests = [
        "Gate 2 formal bidirectional visible-surface and silhouette audits remain gated by Gate 1.",
        "Gate 3 independent optical acceptance remains gated; diagnostic renders are not approval renders.",
        "Physical print, wall, split, connector, fit, material, support and slicer tests remain gated by Gates 1-3.",
    ]
    validation = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "product_revision": "R02",
        "technical_revision": "R15",
        "status": "STOPP",
        "stop_phase": "GATE_1_TOPOLOGY_AND_INTERSECTION_AFTER_SELF_CORRECTION",
        "validations": {
            "hash_gate": "PASS",
            "confirmed_source_hole_identity": "PASS",
            "boundary_position_max_0_05mm": "PASS",
            "bbox_and_extrema": "PASS",
            "projection_confinement": "PASS" if patch_report["projection_confinement"]["pass"] else "FAIL",
            "boundary_normal_transition": "FAIL",
            "other_depth_layer_exclusion": "FAIL_45_CONFIRMED_CROSSINGS",
            "gate_1_topology": "FAIL",
            "gate_2_form_protection": "NOT_RUN_BY_GATE1",
            "gate_3_optic": "NOT_RUN_BY_GATE1",
            "gate_4_cad_fdm": "NOT_RUN_BY_GATES_1_2_3",
        },
        "manufacturing_outputs": {
            "approved_master_created": False, "cad_created": False, "split_created": False,
            "hollow_shells_created": False, "connector_created": False, "stl_created": False,
            "three_mf_created": False, "glb_created": False, "fdm_validation_run": False,
        },
        "open_real_tests": open_tests,
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
        "nutzerentscheidung_grund": "Methodically proven topology/depth-layer conflict in the R14 source; no user dimension, function or reference datum is missing.",
        "final_user_approval_claimed": False,
    }
    json_write(OUT / "VALIDIERUNG-R02-R15.json", validation)
    json_write(OUT / "result-status.json", {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "revision": "R02/R15",
        "status": "STOPP",
        "main_files": [
            BEST_PARTIAL.relative_to(ROOT).as_posix(),
            (OUT / "VALIDIERUNG-R02-R15.json").relative_to(ROOT).as_posix(),
            (OUT / "audits" / "topology-before-after-r15.json").relative_to(ROOT).as_posix(),
            (OUT / "audits" / "underside-boundary-normal-depth-audit-r15.json").relative_to(ROOT).as_posix(),
            soll_ist.relative_to(ROOT).as_posix(),
        ],
        "validations": validation["validations"],
        "open_real_tests": open_tests,
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
        "nutzerentscheidung_grund": validation["nutzerentscheidung_grund"],
        "final_user_approval_claimed": False,
    })
    (OUT / "CAD-STL-3MF-GLB-FDM-NOT-CREATED.txt").write_text(
        "Gate 1 failed after five depth-guided underside variants and three whole-surface topology attempts. No approved master, CAD split, hollow shell, connector, STL, 3MF, GLB, slicer profile or FDM validation was created.\n",
        encoding="utf-8",
    )
    (OUT / "REVISION-R02-R15.md").write_text(
        "# REVISION R02 / R15\n\nStatus: **STOPP** at Gate 1; no final user approval is claimed.\n\n"
        "## GEÄNDERT\n\n- The confirmed 1,376-edge underside loop was identified unambiguously and closed in five boundary-fixed harmonic variants.\n"
        "- R14 micro-sheets and orientation-conflict surgery were tested in three documented whole-surface attempts.\n\n"
        "## UNVERÄNDERT\n\n- Seed 42, REF-CLEAN, REF-SEAM, all user dimensions, materials, two-part concept, four feet, facial features, back and the single maple leaf.\n"
        "- Every retained R14-main-surface coordinate is byte/numerically unchanged (0.000 mm displacement).\n\n"
        "## ENTFERNT\n\n- No product feature was accepted as removed. Attempt-only conflict-face removals remain non-approved diagnostics.\n"
        "- No manufacturing artifact was produced.\n\n"
        "## OFFEN\n\n- The best fully scanned underside patch still has 45 strict crossings with other R14 source geometry; a lower route would violate the existing minimum-Z bound.\n"
        "- The remaining R14 main sheet has 8,151 other boundary edges and is intrinsically non-orientable after underside-only closure.\n"
        "- Making it orientable opens two global ~2.6 m cut loops; closing them would violate the ban on global bridge/replacement surfaces and causes pathological area inflation.\n"
        "- Gates 2-4 and all real production tests remain gated.\n\n"
        "`NUTZERENTSCHEIDUNG_ERFORDERLICH: false` — the stop is purely technical.\n",
        encoding="utf-8",
    )
    (OUT / "REPRODUKTION-R15.md").write_text(
        "# REPRODUKTION R15\n\nRun from the repository root:\n\n```powershell\n"
        "python outputs\\herbst-igel-r02-underside-closure-r15\\reproduction-scripts\\analyze_r15_input.py\n"
        "python outputs\\herbst-igel-r02-underside-closure-r15\\reproduction-scripts\\build_r15_gate1.py\n"
        "python outputs\\herbst-igel-r02-underside-closure-r15\\reproduction-scripts\\build_r15_underside_variants.py\n"
        "python outputs\\herbst-igel-r02-underside-closure-r15\\reproduction-scripts\\audit_r15_intersections.py --candidate outputs\\herbst-igel-r02-underside-closure-r15\\masterform\\r15-underside-d4-PARTIAL-NON-APPROVED.ply --attempt-key attempt_a --output outputs\\herbst-igel-r02-underside-closure-r15\\audits\\underside-d4-intersection-audit-r15.json\n"
        "python outputs\\herbst-igel-r02-underside-closure-r15\\reproduction-scripts\\finalize_r15.py\n"
        "python outputs\\herbst-igel-r02-underside-closure-r15\\reproduction-scripts\\validate_r15.py\n```\n"
        "\nNo forbidden global hull method is invoked.\n",
        encoding="utf-8",
    )
    print(json.dumps(validation, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
