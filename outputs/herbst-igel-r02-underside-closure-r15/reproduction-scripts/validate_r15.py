#!/usr/bin/env python3
"""Validate the completeness and internal consistency of the R15 STOPP result."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

from PIL import Image

from r15_mesh_core import json_write, sha256


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
EXPECTED_TASK_BLOB = "6f36e00693a3f9ad6859b43450a5a77316fa9254"
EXPECTED = {
    "r14-local-surgery-input.ply": "f6c82635080a5c97c350ba80e18dbda79424f34542ca3f87e66a7d9d665cb1c2",
    "ref-clean-r15.jpg": "c1c9a5a094f1db2fd220f3433f83af8dedca780f56a4bf479eb8883432250859",
    "ref-seam-r15.jpg": "b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4",
}


def git_blob_sha(path: Path) -> str:
    # Repository text attributes normalize CRLF worktree bytes to LF in Git.
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def main() -> None:
    checks = []

    def check(name: str, condition: bool, detail: object = None) -> None:
        checks.append({"check": name, "pass": bool(condition), "detail": detail})

    task_path = ROOT / "tasks" / "TASK-HERBST-IGEL-R02-UNDERSIDE-CLOSURE-R15.md"
    check("task_blob_sha", git_blob_sha(task_path) == EXPECTED_TASK_BLOB, git_blob_sha(task_path))
    for name, expected in EXPECTED.items():
        actual = sha256(OUT / "inputs" / name)
        check(f"input_hash_{name}", actual == expected, actual)

    required = [
        "VALIDIERUNG-R02-R15.json", "result-status.json", "REVISION-R02-R15.md", "REPRODUKTION-R15.md",
        "CAD-STL-3MF-GLB-FDM-NOT-CREATED.txt", "audits/confirmed-source-hole-mask-r15.json",
        "audits/r15-input-audit.json", "audits/gate1-harmonic-closure-r15.json",
        "audits/topology-before-after-r15.json", "audits/underside-boundary-normal-depth-audit-r15.json",
        "audits/underside-d4-intersection-audit-r15.json", "reports/form-protection-split-r15.json",
        "reports/real-geometry-renders-r15.json", "reports/soll-ist-binary-r15.json",
        "masterform/r15-underside-d4-PARTIAL-NON-APPROVED.ply", "renders-gate-evidence/partial-r15-contact-sheet.png",
        "renders-gate-evidence/soll-ist-r15.png", "toolchain-preflight.json",
    ]
    for relative in required:
        path = OUT / relative
        check(f"required_{relative}", path.is_file() and path.stat().st_size > 0, path.stat().st_size if path.exists() else None)

    validation = json.loads((OUT / "VALIDIERUNG-R02-R15.json").read_text(encoding="utf-8"))
    status = json.loads((OUT / "result-status.json").read_text(encoding="utf-8"))
    topology = json.loads((OUT / "audits" / "topology-before-after-r15.json").read_text(encoding="utf-8"))
    patch = json.loads((OUT / "audits" / "underside-boundary-normal-depth-audit-r15.json").read_text(encoding="utf-8"))
    check("status_stopp", validation["status"] == status["status"] == "STOPP")
    check("gate1_fail", validation["validations"]["gate_1_topology"] == topology["gate_1"] == "FAIL")
    check("confirmed_crossings", patch["other_depth_layers"]["confirmed_strict_crossings"] == 45)
    check("boundary_fixed", patch["boundary"]["maximum_position_displacement_mm"] == 0.0)
    check("manufacturing_all_false", not any(validation["manufacturing_outputs"].values()), validation["manufacturing_outputs"])
    check("no_user_decision", validation["NUTZERENTSCHEIDUNG_ERFORDERLICH"] is False)
    check("no_final_approval", validation["final_user_approval_claimed"] is False and status["final_user_approval_claimed"] is False)

    manufacturing_extensions = {".stl", ".3mf", ".glb", ".step", ".stp", ".fcstd", ".gcode"}
    manufacturing = [path.relative_to(OUT).as_posix() for path in OUT.rglob("*") if path.is_file() and path.suffix.lower() in manufacturing_extensions]
    check("manufacturing_artifacts_absent", not manufacturing, manufacturing)

    render_paths = [OUT / "renders-gate-evidence" / f"partial-r15-{slug}.png" for slug in ("3q-front", "left", "right", "rear", "top", "bottom")]
    render_valid = []
    for path in render_paths:
        try:
            with Image.open(path) as image:
                image.verify()
            render_valid.append(True)
        except Exception:
            render_valid.append(False)
    check("six_real_renders", len(render_paths) == 6 and all(render_valid), render_valid)

    syntax = []
    for script in sorted((OUT / "reproduction-scripts").glob("*.py")):
        try:
            ast.parse(script.read_text(encoding="utf-8"))
            syntax.append({"script": script.name, "pass": True})
        except SyntaxError as error:
            syntax.append({"script": script.name, "pass": False, "error": str(error)})
    check("reproduction_script_syntax", all(item["pass"] for item in syntax), syntax)

    evidence = {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-UNDERSIDE-CLOSURE-R15.md",
        "task_blob_sha": EXPECTED_TASK_BLOB,
        "evidence_status": "PASS" if all(item["pass"] for item in checks) else "FAIL",
        "product_status": "STOPP",
        "checks": checks,
        "note": "Evidence PASS verifies the STOPP package; it is not a product, mesh, print or user approval.",
    }
    json_write(OUT / "reports" / "evidence-validation-r15.json", evidence)

    files = []
    for path in sorted(OUT.rglob("*")):
        if not path.is_file() or path.name == "artifact-manifest.json":
            continue
        files.append({
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        })
    json_write(OUT / "artifact-manifest.json", {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-UNDERSIDE-CLOSURE-R15.md",
        "task_blob_sha": EXPECTED_TASK_BLOB,
        "revision": "R02/R15",
        "status": "STOPP",
        "files": files,
        "manifest_excludes_self": True,
    })
    print(json.dumps({"evidence_status": evidence["evidence_status"], "checks": len(checks), "files": len(files)}, indent=2))
    if evidence["evidence_status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
