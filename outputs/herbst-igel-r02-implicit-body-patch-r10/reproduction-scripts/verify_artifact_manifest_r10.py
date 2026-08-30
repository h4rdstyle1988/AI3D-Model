#!/usr/bin/env python3
"""Read-only syntax, JSON and manifest verification for the R10 package."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path


OUT = Path(__file__).resolve().parents[1]
MANIFEST = OUT / "artifact-manifest.json"


def main() -> None:
    for path in OUT.rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for path in OUT.rglob("*.json"):
        json.loads(path.read_text(encoding="utf-8-sig"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    errors = []
    for item in manifest["files"]:
        path = Path(item["path"])
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if not path.is_file() or path.stat().st_size != item["bytes"] or actual_hash != item["sha256"]:
            errors.append(item["path"])
    actual = [
        path
        for path in OUT.rglob("*")
        if path.is_file()
        and path != MANIFEST
        and "__pycache__" not in path.parts
        and path.suffix.lower() not in {".pyc", ".pyo"}
    ]
    manufacturing = [
        path.as_posix()
        for path in OUT.rglob("*")
        if path.suffix.lower() in {".stl", ".3mf", ".step", ".stp", ".fcstd"}
    ]
    payload = {
        "python_ast": "PASS",
        "json_parse": "PASS",
        "manifest_entries": len(manifest["files"]),
        "actual_files_excluding_manifest": len(actual),
        "manifest_hash_errors": errors,
        "manufacturing_files": manufacturing,
        "status": "PASS" if not errors and len(actual) == len(manifest["files"]) and not manufacturing else "FAIL",
    }
    print(json.dumps(payload, indent=2))
    if payload["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
