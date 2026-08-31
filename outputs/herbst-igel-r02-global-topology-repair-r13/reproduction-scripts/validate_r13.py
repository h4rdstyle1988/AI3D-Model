#!/usr/bin/env python3
"""Validate the stopped R13 evidence set and write its artifact manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
MASTER = OUT / "masterform" / "herbst-igel-r02-masterform-r13-NON-APPROVED.ply"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    required = [
        MASTER,
        OUT / "reports" / "topology-audit-r13.json",
        OUT / "reports" / "global-form-deviation-r13.json",
        OUT / "reports" / "soll-ist-binary-r13.json",
        OUT / "reports" / "real-geometry-renders-r13.json",
        OUT / "VALIDIERUNG-R02-R13.json",
        OUT / "result-status.json",
        OUT / "REVISION-R02-R13.md",
        OUT / "REPRODUKTION-R13.md",
        OUT / "CAD-STL-3MF-GLB-FDM-NOT-CREATED.txt",
        OUT / "renders-optik-gate" / "masterform-contact-sheet-r13.png",
        OUT / "renders-optik-gate" / "soll-ist-optik-gate-r13.png",
    ]
    views = ["3q-front", "left", "right", "rear", "top", "bottom"]
    required += [OUT / "renders-optik-gate" / f"masterform-{view}.png" for view in views]
    missing = [path.relative_to(ROOT).as_posix() for path in required if not path.is_file()]
    topology = load(OUT / "reports" / "topology-audit-r13.json")
    deviation = load(OUT / "reports" / "global-form-deviation-r13.json")
    soll = load(OUT / "reports" / "soll-ist-binary-r13.json")
    status = load(OUT / "result-status.json")
    image_checks = {}
    for path in required:
        if path.suffix.lower() == ".png" and path.is_file():
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                image_checks[path.relative_to(ROOT).as_posix()] = {"size": list(image.size), "format": image.format, "valid": True}
    forbidden = []
    for suffix in ("*.stl", "*.3mf", "*.glb", "*.gcode"):
        forbidden.extend(path.relative_to(ROOT).as_posix() for path in OUT.rglob(suffix))
    checks = {
        "required_files_present": not missing,
        "master_sha256_matches_build_report": sha256(MASTER) == load(OUT / "reports" / "global-topology-repair-r13.json")["master"]["sha256"],
        "mesh_boundary_edges_zero": topology["after_repaired_master"]["boundary_edges"] == 0,
        "mesh_nonmanifold_edges_zero": topology["after_repaired_master"]["nonmanifold_edges"] == 0,
        "mesh_degenerate_faces_zero": topology["after_repaired_master"]["degenerate_faces"] == 0,
        "mesh_single_connected_orientable": topology["single_connected_surface"] and topology["orientable"],
        "confirmed_cross_intersections_zero": topology["confirmed_self_or_cross_intersections"] == 0,
        "form_gate_fails": deviation["status"] == "FAIL",
        "optic_gate_fails": soll["optic_gate"] == "FAIL",
        "overall_status_stopp": status["status"] == "STOPP",
        "manufacturing_outputs_absent": not forbidden,
        "final_user_approval_not_claimed": not status["final_user_approval_claimed"],
        "nutzerentscheidung_false": not status["NUTZERENTSCHEIDUNG_ERFORDERLICH"],
    }
    audit = {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-GLOBAL-TOPOLOGY-REPAIR-R13.md",
        "status": "PASS_EVIDENCE_SET_FOR_STOPP" if all(checks.values()) else "FAIL_EVIDENCE_SET",
        "checks": checks,
        "missing": missing,
        "forbidden_manufacturing_outputs": forbidden,
        "image_checks": image_checks,
    }
    (OUT / "reports" / "evidence-validation-r13.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    if not all(checks.values()):
        raise SystemExit(json.dumps(audit, indent=2))

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
        "task": "tasks/TASK-HERBST-IGEL-R02-GLOBAL-TOPOLOGY-REPAIR-R13.md",
        "task_blob_sha": "b21a7d611c36c7e2a0b826f3a9f8d329cddfd242",
        "product_revision": "R02",
        "technical_revision": "R13",
        "status": "STOPP",
        "files": files,
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
        "final_user_approval_claimed": False,
    }
    (OUT / "artifact-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
