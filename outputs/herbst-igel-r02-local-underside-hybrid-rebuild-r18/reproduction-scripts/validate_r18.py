"""Independent artifact and topology gate validation for Herbst-Igel R18."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "outputs" / "herbst-igel-r02-local-underside-hybrid-rebuild-r18"
TASK = ROOT / "tasks" / "TASK-HERBST-IGEL-R02-LOCAL-UNDERSIDE-HYBRID-REBUILD-R18.md"
EXPECTED_TASK_BLOB = "0d88869426b14cf2b7da7c05ed328e9d0117cbdc"
EXPECTED_INPUTS = {
    "inputs/seed42-optically-best-source.ply": "85ba18eaed15bdbe631fc49dd571e73882c4055e2c247022e90ad15ed99822c6",
    "inputs/herbst-igel-r02-r17-screened-mls-d-200mm.ply": "d9c63f96e44245c3aebd583457418f3d82afbb6cd1a73163bfe7f70983d3fa29",
    "reference-audit/ref-clean-r18.jpg": "c1c9a5a094f1db2fd220f3433f83af8dedca780f56a4bf479eb8883432250859",
    "reference-audit/ref-seam-r18.jpg": "b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4",
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_ply(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with path.open("rb") as stream:
        header = []
        while True:
            line = stream.readline()
            if not line:
                raise ValueError("missing end_header")
            header.append(line.decode("ascii").strip())
            if line.strip() == b"end_header":
                break
        nv = int(next(x.split()[2] for x in header if x.startswith("element vertex ")))
        nf = int(next(x.split()[2] for x in header if x.startswith("element face ")))
        vertices = np.frombuffer(stream.read(nv * 12), dtype="<f4").reshape((-1, 3)).copy()
        dtype = np.dtype([("count", "u1"), ("index", "<i4", (3,))])
        records = np.frombuffer(stream.read(nf * dtype.itemsize), dtype=dtype, count=nf)
        if not np.all(records["count"] == 3):
            raise ValueError("non-triangle PLY")
        return vertices, records["index"].copy()


def main() -> None:
    checks = []
    task_blob = subprocess.check_output(["git", "hash-object", str(TASK)], cwd=ROOT, text=True).strip()
    checks.append({"name": "task_blob", "pass": task_blob == EXPECTED_TASK_BLOB, "actual": task_blob})
    for name, expected in EXPECTED_INPUTS.items():
        path = OUT / name
        actual = digest(path) if path.is_file() else None
        checks.append({"name": f"hash:{name}", "pass": actual == expected, "actual": actual})

    manifest = json.loads((OUT / "artifact-manifest.json").read_text(encoding="utf-8"))
    for item in manifest["artifacts"]:
        path = ROOT / item["path"]
        checks.append({
            "name": f"manifest:{item['path']}",
            "pass": path.is_file() and path.stat().st_size == item["bytes"] and digest(path) == item["sha256"],
        })

    status = json.loads((OUT / "result-status.json").read_text(encoding="utf-8"))
    checks.extend([
        {"name": "status_is_stopp", "pass": status["status"] == "STOPP"},
        {"name": "no_user_decision_required", "pass": status["NUTZERENTSCHEIDUNG_ERFORDERLICH"] is False},
        {"name": "no_final_user_approval_claimed", "pass": status["final_user_approval_claimed"] is False},
        {"name": "gate3_not_run", "pass": status["gates"]["gate_3_cad_fdm"] == "NOT_RUN_GATE_2_FAIL"},
    ])

    required_renders = [
        *(OUT / "renders-gate-evidence" / f"candidate-r18-{name}.png" for name in ("front", "left", "right", "rear", "top", "bottom", "3q-front")),
        OUT / "renders-gate-evidence" / "underside-source-vs-candidate-closeup-r18.png",
        OUT / "renders-gate-evidence" / "soll-ist-ref-clean-source-candidate-r18.png",
        OUT / "renders-gate-evidence" / "ref-seam-overlay-r18.png",
        OUT / "renders-gate-evidence" / "ref-seam-soll-ist-r18.png",
    ]
    checks.append({"name": "required_renders", "pass": all(p.is_file() and p.stat().st_size > 0 for p in required_renders)})

    forbidden = [p for p in OUT.rglob("*") if p.is_file() and p.suffix.lower() in {".stl", ".3mf", ".glb", ".step", ".stp"}]
    checks.append({"name": "gate3_files_absent", "pass": not forbidden, "files": [str(p) for p in forbidden]})
    oversized = [p for p in OUT.rglob("*") if p.is_file() and p.stat().st_size > 90_000_000]
    checks.append({"name": "no_git_artifact_over_90mb", "pass": not oversized, "files": [str(p) for p in oversized]})

    candidate = OUT / "candidates" / "herbst-igel-r02-r18-relief-transfer-c-200mm.ply"
    vertices, faces = read_ply(candidate)
    edges = np.sort(np.vstack((faces[:, (0, 1)], faces[:, (1, 2)], faces[:, (2, 0)])), axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    tri = vertices[faces]
    area2 = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    checks.extend([
        {"name": "diagnostic_finite", "pass": bool(np.isfinite(vertices).all())},
        {"name": "diagnostic_boundary_edges_zero", "pass": int(np.sum(counts == 1)) == 0},
        {"name": "diagnostic_nonmanifold_edges_zero", "pass": int(np.sum(counts > 2)) == 0},
        {"name": "diagnostic_degenerate_faces_zero", "pass": int(np.sum(area2 <= 1e-12)) == 0},
    ])

    required_reports = [
        OUT / "reports" / "roi-definition-r18.json",
        OUT / "reports" / "topology-gate-r18.json",
        OUT / "reports" / "form-protection-gate-r18.json",
        OUT / "technical-validation-r18.json",
        OUT / "REVISION-R02-R18.md",
        OUT / "REPRODUKTION-R18.md",
        OUT / "CAD-STL-3MF-GLB-FDM-NOT-CREATED.txt",
    ]
    checks.append({"name": "required_reports", "pass": all(p.is_file() for p in required_reports)})
    result = {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-LOCAL-UNDERSIDE-HYBRID-REBUILD-R18.md",
        "validator": "independent file/hash/indexed-edge validation; visual gate remains recorded FAIL",
        "checks": checks,
        "status": "PASS" if all(item["pass"] for item in checks) else "FAIL",
    }
    path = OUT / "independent-validation-r18.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
