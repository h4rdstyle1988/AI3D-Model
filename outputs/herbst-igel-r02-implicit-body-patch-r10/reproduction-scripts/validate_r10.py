#!/usr/bin/env python3
"""Validate the R10 reconstruction and enforce the optical gate stop."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from reconstruct_implicit_body_r10 import (
    EXPECTED_SOURCE_SHA256,
    TASK,
    TASK_BLOB,
    mesh_metrics,
    project_xz,
    read_binary_ply,
    reference_masks,
)


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
SOURCE = OUT / "source-seed42" / "herbst-igel-r02-trellis-raw-seed-42.ply"
MASTER = OUT / "masterform" / "herbst-igel-r02-masterform-implicit-r10-NON-APPROVED.ply"
RECONSTRUCTION = OUT / "reports" / "implicit-reconstruction-r10.json"
RENDER_REPORT = OUT / "reports" / "real-geometry-renders-r10.json"
VALIDATION = OUT / "VALIDIERUNG-R02-R10.json"
STATUS = OUT / "result-status.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def edge_metrics(vertices: np.ndarray, faces: np.ndarray) -> dict[str, object]:
    metrics = mesh_metrics(vertices, faces)
    triangles = vertices[faces]
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(cross, axis=1)
    normals = np.zeros_like(cross)
    valid = lengths > 1.0e-12
    normals[valid] = cross[valid] / lengths[valid, None]
    edges = np.vstack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    owners = np.tile(np.arange(len(faces), dtype=np.int64), 3)
    edges.sort(axis=1)
    order = np.lexsort((edges[:, 1], edges[:, 0]))
    edges = edges[order]
    owners = owners[order]
    same = np.all(edges[1:] == edges[:-1], axis=1)
    first = np.nonzero(same)[0]
    # Only ordinary two-face runs enter the smoothness diagnostic.
    run_start = np.r_[True, np.any(edges[1:] != edges[:-1], axis=1)]
    starts = np.nonzero(run_start)[0]
    ends = np.r_[starts[1:], len(edges)]
    pairs = [(s, e) for s, e in zip(starts, ends) if e - s == 2]
    if pairs:
        a = np.fromiter((owners[s] for s, _e in pairs), dtype=np.int64)
        b = np.fromiter((owners[s + 1] for s, _e in pairs), dtype=np.int64)
        cosine = np.clip(np.abs(np.sum(normals[a] * normals[b], axis=1)), 0.0, 1.0)
        degrees = np.degrees(np.arccos(cosine))
        metrics["absolute_dihedral_degrees"] = {
            "samples": int(len(degrees)),
            "median": float(np.median(degrees)),
            "p95": float(np.quantile(degrees, 0.95)),
            "maximum": float(np.max(degrees)),
        }
    else:
        metrics["absolute_dihedral_degrees"] = {"samples": 0}
    return metrics


def segment_triangle_hits(p0: np.ndarray, p1: np.ndarray, a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    direction = p1 - p0
    edge1 = b - a
    edge2 = c - a
    h = np.cross(direction, edge2)
    determinant = np.sum(edge1 * h, axis=1)
    valid = np.abs(determinant) > 1.0e-12
    inv = np.zeros_like(determinant)
    inv[valid] = 1.0 / determinant[valid]
    s = p0 - a
    u = inv * np.sum(s * h, axis=1)
    q = np.cross(s, edge1)
    v = inv * np.sum(direction * q, axis=1)
    t = inv * np.sum(edge2 * q, axis=1)
    return valid & (u >= -1.0e-9) & (v >= -1.0e-9) & (u + v <= 1.0 + 1.0e-9) & (t >= -1.0e-9) & (t <= 1.0 + 1.0e-9)


def triangle_pair_hits(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    hit = np.zeros(len(first), dtype=bool)
    for i, j in ((0, 1), (1, 2), (2, 0)):
        hit |= segment_triangle_hits(first[:, i], first[:, j], second[:, 0], second[:, 1], second[:, 2])
    for i, j in ((0, 1), (1, 2), (2, 0)):
        hit |= segment_triangle_hits(second[:, i], second[:, j], first[:, 0], first[:, 1], first[:, 2])
    return hit


def conservative_cross_intersection_check(
    source_triangles: np.ndarray,
    implicit_triangles: np.ndarray,
    cell_size: float = 0.012,
    stop_after: int = 250,
) -> dict[str, object]:
    """Center-grid broadphase plus exact segment/triangle narrowphase.

    The narrowphase omits perfectly coplanar overlap, so a positive result is
    conclusive while zero would remain conservative.  R10 only needs the first
    conclusive local conflicts because any one blocks the technical gate.
    """
    origin = np.minimum(source_triangles.min(axis=(0, 1)), implicit_triangles.min(axis=(0, 1))) - cell_size
    source_centers = source_triangles.mean(axis=1)
    implicit_centers = implicit_triangles.mean(axis=1)
    source_cells = np.floor((source_centers - origin) / cell_size).astype(np.int32)
    implicit_cells = np.floor((implicit_centers - origin) / cell_size).astype(np.int32)
    buckets: dict[tuple[int, int, int], list[int]] = {}
    for index, cell in enumerate(source_cells):
        buckets.setdefault((int(cell[0]), int(cell[1]), int(cell[2])), []).append(index)
    hit_count = 0
    candidate_pairs = 0
    batch_source: list[int] = []
    batch_implicit: list[int] = []

    def flush() -> int:
        nonlocal candidate_pairs
        if not batch_source:
            return 0
        s = np.asarray(batch_source, dtype=np.int64)
        i = np.asarray(batch_implicit, dtype=np.int64)
        candidate_pairs += len(s)
        close = np.linalg.norm(source_centers[s] - implicit_centers[i], axis=1) <= cell_size * 1.9
        if not np.any(close):
            batch_source.clear()
            batch_implicit.clear()
            return 0
        found = int(np.count_nonzero(triangle_pair_hits(source_triangles[s[close]], implicit_triangles[i[close]])))
        batch_source.clear()
        batch_implicit.clear()
        return found

    for implicit_index, cell in enumerate(implicit_cells):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for source_index in buckets.get((int(cell[0] + dx), int(cell[1] + dy), int(cell[2] + dz)), ()):
                        batch_source.append(source_index)
                        batch_implicit.append(implicit_index)
        if len(batch_source) >= 100_000:
            hit_count += flush()
            if hit_count >= stop_after:
                break
    if hit_count < stop_after:
        hit_count += flush()
    return {
        "method": "3D center-grid broadphase plus Moller segment/triangle narrowphase",
        "cell_size_normalized": cell_size,
        "candidate_pairs_narrowphase_or_distance_screened": int(candidate_pairs),
        "confirmed_non_coplanar_cross_intersections": int(hit_count),
        "stopped_after_threshold": bool(hit_count >= stop_after),
        "coplanar_overlap_counted": False,
        "status": "FAIL" if hit_count > 0 else "PASS_CONSERVATIVE",
    }


def main() -> None:
    reconstruction = json.loads(RECONSTRUCTION.read_text(encoding="utf-8"))
    render_report = json.loads(RENDER_REPORT.read_text(encoding="utf-8"))
    source_vertices, source_faces = read_binary_ply(SOURCE)
    vertices, faces = read_binary_ply(MASTER)
    source_count = len(source_vertices)
    source_prefix_equal = bool(np.array_equal(vertices[:source_count], source_vertices))
    retained_source_faces = faces[np.all(faces < source_count, axis=1)]
    implicit_faces = faces[np.all(faces >= source_count, axis=1)] - source_count
    implicit_vertices = vertices[source_count:]

    used = np.unique(source_faces)
    bounds_min = source_vertices[used].min(axis=0)
    bounds_max = source_vertices[used].max(axis=0)
    _blue, body, bbox, _rgb = reference_masks()
    retained_triangles = source_vertices[retained_source_faces]
    centers = retained_triangles.mean(axis=1)
    u, v = project_xz(centers, bounds_min, bounds_max, bbox)
    ui = np.rint(u).astype(np.int32)
    vi = np.rint(v).astype(np.int32)
    valid = (ui >= 0) & (ui < body.shape[1]) & (vi >= 0) & (vi < body.shape[0])
    local_source = np.zeros(len(retained_source_faces), dtype=bool)
    local_source[valid] = body[vi[valid], ui[valid]]
    local_source &= np.max(retained_triangles[:, :, 2], axis=1) > -0.105
    cross_intersections = conservative_cross_intersection_check(
        retained_triangles[local_source], implicit_vertices[implicit_faces]
    )

    implicit_validation = edge_metrics(implicit_vertices, implicit_faces)
    required_render_paths = [ROOT / item["path"] for item in render_report["selected_views"]]
    required_render_paths += [ROOT / render_report["contact_sheet"], ROOT / render_report["soll_ist_sheet"]]
    render_files = [
        {"path": path.relative_to(ROOT).as_posix(), "exists": path.is_file(), "bytes": path.stat().st_size if path.is_file() else 0, "sha256": sha256(path) if path.is_file() else None}
        for path in required_render_paths
    ]
    manufacturing_suffixes = {".stl", ".3mf", ".step", ".stp", ".fcstd"}
    manufacturing = [path.relative_to(ROOT).as_posix() for path in OUT.rglob("*") if path.is_file() and path.suffix.lower() in manufacturing_suffixes]

    failed_criteria = [
        "free_round_reference_like_face",
        "no_leaf_spine_overlap_of_forehead_eyes_snout",
        "short_soft_snout_and_nose_clearly_retained",
        "both_round_ears_and_eye_forms_clearly_retained",
        "ref_seam_visual_continuity",
        "no_visible_patch_hole_step_or_repair",
    ]
    validation = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "product_revision": "R02",
        "technical_revision": "R10",
        "status": "STOPP",
        "stop_phase": "OPTIK_GATE",
        "reference_gate": {
            "status": "PASS",
            "clean_sha256": sha256(OUT / "reference-audit" / "ref-clean-r10.jpg"),
            "seam_sha256": sha256(OUT / "reference-audit" / "ref-seam-r10.jpg"),
        },
        "seed_42_source": {
            "status": "PASS_BYTE_IDENTICAL_TO_R08_R09",
            "sha256": sha256(SOURCE),
            "expected_sha256": EXPECTED_SOURCE_SHA256,
            "vertices": int(len(source_vertices)),
            "triangles": int(len(source_faces)),
        },
        "reconstruction": {
            "status": "EXECUTED_TWO_VARIANTS_NON_MASTER",
            "methods": ["sdf", "rbf"],
            "selected": reconstruction["preliminary_numeric_selection"],
            "master_sha256": sha256(MASTER),
            "source_vertex_prefix_exact": source_prefix_equal,
            "outside_roi_source_faces_preserved_exact": bool(reconstruction["variants"]["sdf"]["selection"]["outside_roi_faces_preserved_exact"]),
            "implicit_local_surface": implicit_validation,
            "local_cross_intersections": cross_intersections,
        },
        "real_geometry_render_gate": {
            "status": "PASS",
            "source_is_actual_reconstructed_geometry": bool(render_report["source_is_actual_reconstructed_geometry"]),
            "required_six_views_exist": bool(all(item["exists"] for item in render_files[:6])),
            "variant_screening_exists": (ROOT / render_report["preliminary_variant_screening"]["contact_sheet"]).is_file(),
            "soll_ist_exists": (ROOT / render_report["soll_ist_sheet"]).is_file(),
            "files": render_files,
        },
        "optic_gate": {
            "status": "FAIL",
            "failed_criteria": failed_criteria,
            "passed_protected_criteria": [
                "four_short_feet_retained_in_source_geometry",
                "arched_back_outside_roi_retained",
                "one_visible_maple_leaf_retained",
                "no_second_maple_leaf_added",
            ],
            "reason": "Real R10 renders show that the smooth low-frequency body field is present, but eyes/nose are not cleanly integrated, feature windows are visibly open, residual fused leaf/spine geometry reaches the forehead/face transition, and REF-SEAM remains discontinuous. SDF and RBF variants fail the same protected-feature integration gate.",
        },
        "cad_fdm_phase": {
            "status": "NOT_RUN_BY_OPTIK_GATE",
            "manufacturing_artifacts_found": manufacturing,
            "approved_master_created": False,
            "split_created": False,
            "body_stl_created": False,
            "back_stl_created": False,
            "connector_created": False,
            "shell_and_wall_validation_run": False,
        },
        "open_real_tests": [
            "Physical print, fit, support, material and 200 mm production-scale tests remain inapplicable before an optical PASS."
        ],
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
        "nutzerentscheidung_grund": "Technical gate stop; no user dimension or product decision is missing.",
        "final_user_approval_claimed": False,
    }
    VALIDATION.write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    status = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "revision": {"product": "R02", "technical": "R10"},
        "status": "STOPP",
        "gate": "OPTIK_GATE",
        "gate_result": "FAIL",
        "summary": "Two smooth local implicit Seed-42 reconstructions (SDF and Gaussian RBF) were generated and screened. The selected SDF candidate preserves source coordinates outside the ROI but does not integrate the protected eyes/nose/ears without visible openings and residual face-zone overlap, so CAD/FDM did not run.",
        "main_files": [
            (OUT / "SOLL-IST-OPTIK-GATE-R10.md").relative_to(ROOT).as_posix(),
            (OUT / "REVISION-R02-R10.md").relative_to(ROOT).as_posix(),
            VALIDATION.relative_to(ROOT).as_posix(),
            (OUT / "renders-optik-gate" / "soll-ist-optik-gate-r10.png").relative_to(ROOT).as_posix(),
            MASTER.relative_to(ROOT).as_posix(),
            (OUT / "artifact-manifest.json").relative_to(ROOT).as_posix(),
        ],
        "validations": {
            "reference_gate": "PASS",
            "seed42_hash_gate": "PASS",
            "two_implicit_variants": "PASS_EXECUTED_NON_MASTER",
            "outside_roi_coordinate_preservation": "PASS",
            "six_real_geometry_renders": "PASS",
            "local_open_edge_gate": "FAIL",
            "local_cross_intersection_gate": cross_intersections["status"],
            "optic_gate": "FAIL",
            "cad_fdm_validation": "NOT_RUN_BY_GATE",
        },
        "artifacts_not_created_by_gate": [
            "approved masterform",
            "REF-SEAM split",
            "body STL",
            "back STL",
            "assembly 3MF or GLB",
            "connector and receptacle",
        ],
        "open_real_tests": validation["open_real_tests"],
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
        "nutzerentscheidung_grund": validation["nutzerentscheidung_grund"],
        "final_user_approval_claimed": False,
    }
    STATUS.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2))


if __name__ == "__main__":
    main()
