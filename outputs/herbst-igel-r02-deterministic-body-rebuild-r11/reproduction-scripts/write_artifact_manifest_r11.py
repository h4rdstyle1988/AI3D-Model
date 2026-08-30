#!/usr/bin/env python3
"""Write SHA-256 manifest for every delivered R11 artifact except itself."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


OUT = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[3]
MANIFEST = OUT / "artifact-manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    artifacts = []
    for path in sorted(OUT.rglob("*")):
        if not path.is_file() or path == MANIFEST or "__pycache__" in path.parts:
            continue
        artifacts.append({
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        })
    payload = {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-DETERMINISTIC-BODY-REBUILD-R11.md",
        "task_blob_sha": "a924b68969a2f82e7e75a924a5e13227b1211d77",
        "status": "STOPP",
        "artifact_count_excluding_manifest": len(artifacts),
        "artifacts": artifacts,
    }
    MANIFEST.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(MANIFEST)


if __name__ == "__main__":
    main()
