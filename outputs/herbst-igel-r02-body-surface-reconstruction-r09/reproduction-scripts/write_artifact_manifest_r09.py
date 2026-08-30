#!/usr/bin/env python3
"""Write a deterministic hash manifest for every R09 artifact except itself."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
MANIFEST = OUT / "artifact-manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def role(path: Path) -> str:
    relative = path.relative_to(OUT)
    first = relative.parts[0]
    if first == "source-r08":
        return "source_geometry"
    if first == "reference-audit":
        return "authoritative_reference_copy"
    if first == "masterform":
        return "non_master_geometry_attempt"
    if first == "renders-optik-gate":
        return "real_geometry_optic_gate_render"
    if first == "diagnostics":
        return "selection_diagnostic"
    if first == "reports":
        return "technical_report"
    if first == "reproduction-scripts":
        return "reproduction_source"
    return "result_document"


def main() -> None:
    records = []
    for path in sorted(OUT.rglob("*")):
        if (
            not path.is_file()
            or path == MANIFEST
            or "__pycache__" in path.parts
            or path.suffix.lower() in {".pyc", ".pyo"}
        ):
            continue
        records.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "role": role(path),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    payload = {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-BODY-SURFACE-RECONSTRUCTION-R09.md",
        "task_blob_sha": "ef3a16cc80c255d0e05c1a5e3773f2c9497c4c73",
        "revision": "R02-R09",
        "status": "STOPP_OPTIK_GATE_FAIL",
        "manifest_self_excluded": True,
        "artifact_count": len(records),
        "artifacts": records,
        "final_user_approval_claimed": False,
    }
    MANIFEST.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"artifact_count": len(records), "path": MANIFEST.relative_to(ROOT).as_posix()}, indent=2))


if __name__ == "__main__":
    main()
