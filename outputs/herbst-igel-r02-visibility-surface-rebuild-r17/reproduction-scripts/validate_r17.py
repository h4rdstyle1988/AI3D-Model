"""Independent filesystem and selected-mesh validation for R17."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "outputs" / "herbst-igel-r02-visibility-surface-rebuild-r17"
TASK = "tasks/TASK-HERBST-IGEL-R02-VISIBILITY-SURFACE-REBUILD-R17.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    module_path = OUT / "reproduction-scripts" / "r17_visibility_poisson.py"
    spec = importlib.util.spec_from_file_location("r17_core", module_path)
    core = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(core)
    status = json.loads((OUT / "result-status.json").read_text(encoding="utf-8"))
    topology_report = json.loads((OUT / "reports" / "topology-gate-r17.json").read_text(encoding="utf-8"))
    selected_path = ROOT / status["main_files"][0]
    vertices, faces = core.read_binary_triangle_ply(selected_path)
    measured = core.topology_metrics(vertices, faces)
    manifest = json.loads((OUT / "artifact-manifest.json").read_text(encoding="utf-8"))
    manifest_errors = []
    for item in manifest["artifacts"]:
        path = ROOT / item["path"]
        if not path.is_file():
            manifest_errors.append(f"missing:{item['path']}")
        elif path.stat().st_size != item["bytes"]:
            manifest_errors.append(f"size:{item['path']}")
        elif sha256(path) != item["sha256"]:
            manifest_errors.append(f"sha256:{item['path']}")
    large = [p.relative_to(ROOT).as_posix() for p in OUT.rglob("*") if p.is_file() and p.stat().st_size > 90_000_000]
    forbidden = [p.relative_to(ROOT).as_posix() for p in OUT.rglob("*") if p.suffix.lower() in {".stl", ".3mf", ".glb"}]
    topology_match = all(
        measured[key] == topology_report["mesh_metrics"][key]
        for key in ("vertices", "triangles", "boundary_edges", "nonmanifold_edges", "degenerate_faces", "duplicate_faces")
    )
    checks = {
        "selected_mesh_exists": selected_path.is_file(),
        "selected_mesh_sha256_matches_audit": sha256(selected_path)
        == json.loads((OUT / "audits" / "topology-screened-mls-d-r17.json").read_text(encoding="utf-8"))["master"]["sha256"],
        "independent_topology_matches_report": topology_match,
        "watertight_edge_incidence": measured["all_edges_incidence_two"] and measured["boundary_edges"] == 0,
        "no_nonmanifold_edges": measured["nonmanifold_edges"] == 0,
        "no_degenerate_or_duplicate_faces": measured["degenerate_faces"] == 0 and measured["duplicate_faces"] == 0,
        "manifest_entries_valid_before_this_report": not manifest_errors,
        "no_artifact_over_90MB": not large,
        "no_gate3_stl_3mf_glb": not forbidden,
        "status_is_stopp_gate2_fail": status["status"] == "STOPP" and status["gates"]["gate_2_form_protection"] == "FAIL",
        "no_final_user_approval_claimed": status["final_user_approval_claimed"] is False,
        "nutzerentscheidung_not_required": status["NUTZERENTSCHEIDUNG_ERFORDERLICH"] is False,
    }
    payload = {
        "schema_version": 1,
        "task": TASK,
        "selected_mesh": selected_path.relative_to(ROOT).as_posix(),
        "measured_mesh_metrics": measured,
        "checks": checks,
        "manifest_errors": manifest_errors,
        "files_over_90MB": large,
        "forbidden_gate3_files": forbidden,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    path = OUT / "independent-validation-r17.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if payload["status"] != "PASS":
        raise SystemExit(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
