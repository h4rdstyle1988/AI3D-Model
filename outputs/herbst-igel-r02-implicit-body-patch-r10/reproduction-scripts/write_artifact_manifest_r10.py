#!/usr/bin/env python3
"""Write the deterministic R10 artifact inventory after validation."""

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


def main() -> None:
    files = []
    for path in sorted(OUT.rglob("*")):
        if not path.is_file() or path == MANIFEST or "__pycache__" in path.parts or path.suffix.lower() in {".pyc", ".pyo"}:
            continue
        files.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    payload = {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-IMPLICIT-BODY-PATCH-R10.md",
        "task_blob_sha": "18406bd6fc9d50ad033ed7cc41d1d5a8fe257383",
        "revision": {"product": "R02", "technical": "R10"},
        "status": "STOPP",
        "file_count_excluding_manifest": len(files),
        "files": files,
    }
    MANIFEST.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": MANIFEST.relative_to(ROOT).as_posix(), "files": len(files)}, indent=2))


if __name__ == "__main__":
    main()
