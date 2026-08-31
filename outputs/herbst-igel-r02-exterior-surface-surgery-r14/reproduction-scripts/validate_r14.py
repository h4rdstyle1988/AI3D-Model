#!/usr/bin/env python3
"""Validate the complete R14 STOPP evidence set and write its manifest."""

from __future__ import annotations

import ast
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

import r14_surface_surgery as r14


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
TASK = "tasks/TASK-HERBST-IGEL-R02-EXTERIOR-SURFACE-SURGERY-R14.md"
TASK_BLOB = "24e2f98d42250e59fa72f462f0b258c7dd8b65d0"
MASTER = OUT / "masterform" / "herbst-igel-r02-r14-local-surgery-PARTIAL-NON-APPROVED.ply"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    required = [
        MASTER,
        OUT / "reference-audit" / "hash-gate-r14.json",
        OUT / "reference-audit" / "ref-clean-r14.jpg",
        OUT / "reference-audit" / "ref-seam-r14.jpg",
        OUT / "reports" / "exterior-classification-r14.json",
        OUT / "reports" / "boundary-loop-audit-r14.json",
        OUT / "reports" / "topology-audit-r14.json",
        OUT / "reports" / "surface-distance-outside-roi-r14.json",
        OUT / "reports" / "silhouette-ray-audit-r14.json",
        OUT / "reports" / "stitch-edge-summary-r14.json",
        OUT / "reports" / "stitch-edges-r14.csv",
        OUT / "reports" / "nonmanifold-face-selection-r14.csv",
        OUT / "reports" / "real-geometry-renders-r14.json",
        OUT / "reports" / "soll-ist-binary-r14.json",
        OUT / "VALIDIERUNG-R02-R14.json",
        OUT / "result-status.json",
        OUT / "REVISION-R02-R14.md",
        OUT / "REPRODUKTION-R14.md",
        OUT / "CAD-STL-3MF-GLB-FDM-NOT-CREATED.txt",
        OUT / "renders-gate-evidence" / "partial-r14-contact-sheet.png",
        OUT / "renders-gate-evidence" / "soll-ist-r14.png",
    ]
    required.extend(OUT / "renders-gate-evidence" / f"partial-r14-{slug}.png" for slug, _camera, _label in r14.CAMERAS)
    missing = [path.relative_to(ROOT).as_posix() for path in required if not path.is_file()]

    topology = load(OUT / "reports" / "topology-audit-r14.json")
    distance = load(OUT / "reports" / "surface-distance-outside-roi-r14.json")
    stitch = load(OUT / "reports" / "stitch-edge-summary-r14.json")
    validation = load(OUT / "VALIDIERUNG-R02-R14.json")
    status = load(OUT / "result-status.json")
    hash_gate = load(OUT / "reference-audit" / "hash-gate-r14.json")

    vertices, faces = r14.read_binary_ply(MASTER)
    recomputed = r14.mesh_metrics(vertices, faces)
    after = topology["after_maximum_compliant_local_surgery"]
    with (OUT / "reports" / "stitch-edges-r14.csv").open("r", encoding="utf-8", newline="") as stream:
        stitch_rows = list(csv.DictReader(stream))

    image_checks = {}
    for path in required:
        if path.suffix.lower() not in (".png", ".jpg", ".jpeg") or not path.is_file():
            continue
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            image_checks[path.relative_to(ROOT).as_posix()] = {"valid": True, "format": image.format, "size": list(image.size)}

    forbidden = []
    for pattern in ("*.stl", "*.3mf", "*.glb", "*.gltf", "*.gcode"):
        forbidden.extend(path.relative_to(ROOT).as_posix() for path in OUT.rglob(pattern))
    source_syntax = {}
    for path in sorted((OUT / "reproduction-scripts").glob("*.py")):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        source_syntax[path.relative_to(ROOT).as_posix()] = "PASS"

    revision_text = (OUT / "REVISION-R02-R14.md").read_text(encoding="utf-8")
    checks = {
        "required_files_present": not missing,
        "task_blob_matches_approved": validation["task_blob_sha"] == TASK_BLOB and status["task_blob_sha"] == TASK_BLOB,
        "hash_gate_pass": hash_gate["status"] == "PASS" and hash_gate["actual"] == r14.EXPECTED,
        "candidate_hash_matches_render_report": sha256(MASTER) == load(OUT / "reports" / "real-geometry-renders-r14.json")["source_geometry_sha256"],
        "recomputed_vertices_match": recomputed["vertices"] == after["vertices"],
        "recomputed_triangles_match": recomputed["triangles"] == after["triangles"],
        "recomputed_boundary_edges_match": recomputed["boundary_edges"] == after["boundary_edges"],
        "recomputed_nonmanifold_edges_match": recomputed["nonmanifold_edges"] == after["nonmanifold_edges"],
        "recomputed_degenerate_faces_match": recomputed["degenerate_faces"] == after["degenerate_faces"],
        "local_nonmanifold_self_correction_pass": after["nonmanifold_edges"] == 0,
        "local_stitch_lengths_pass": stitch["all_length_checks_le_3x"],
        "local_stitch_normals_pass": stitch["all_normal_checks_le_60deg"],
        "stitch_csv_count_matches": len(stitch_rows) == stitch["new_stitch_edges"],
        "gate1_fails_open_nonorientable_disconnected": (
            topology["gate_1_topology"] == "FAIL"
            and after["boundary_edges"] > 0
            and not topology["orientability"]["orientable"]
            and after["connected_face_surfaces"] > 1
        ),
        "gate2_not_run_after_gate1": distance["formal_bidirectional_point_to_triangle_status"] == "NOT_RUN_GATE1_FAIL",
        "gate3_and_gate4_not_run": validation["execution_sequence"]["gate_3_optic"].startswith("NOT_RUN") and validation["execution_sequence"]["gate_4_cad_fdm"].startswith("NOT_RUN"),
        "overall_status_stopp": validation["status"] == "STOPP" and status["status"] == "STOPP",
        "manufacturing_outputs_absent": not forbidden,
        "nutzerentscheidung_false": not validation["NUTZERENTSCHEIDUNG_ERFORDERLICH"] and not status["NUTZERENTSCHEIDUNG_ERFORDERLICH"],
        "final_user_approval_not_claimed": not validation["final_user_approval_claimed"] and not status["final_user_approval_claimed"],
        "revision_has_required_sections": all(section in revision_text for section in ("GEÄNDERT", "UNVERÄNDERT", "ENTFERNT", "OFFEN")),
    }
    evidence = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "status": "PASS_EVIDENCE_SET_FOR_STOPP" if all(checks.values()) else "FAIL_EVIDENCE_SET",
        "checks": checks,
        "missing": missing,
        "forbidden_manufacturing_outputs": forbidden,
        "source_syntax": source_syntax,
        "image_checks": image_checks,
        "candidate_recomputed_metrics": recomputed,
    }
    json_write = r14.json_write
    json_write(OUT / "reports" / "evidence-validation-r14.json", evidence)
    if not all(checks.values()):
        raise SystemExit(json.dumps(evidence, indent=2, ensure_ascii=False))

    files = []
    for path in sorted(OUT.rglob("*")):
        if not path.is_file() or path.name == "artifact-manifest.json" or "__pycache__" in path.parts:
            continue
        files.append({
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        })
    manifest = {
        "schema_version": 1,
        "task": TASK,
        "task_blob_sha": TASK_BLOB,
        "product_revision": "R02",
        "technical_revision": "R14",
        "status": "STOPP",
        "files": files,
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
        "final_user_approval_claimed": False,
    }
    json_write(OUT / "artifact-manifest.json", manifest)
    print(json.dumps(evidence, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
