#!/usr/bin/env python3
"""Write a deterministic SHA-256 manifest for all material R08 artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


OUT = Path(__file__).resolve().parents[1]
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
        if not path.is_file() or path == MANIFEST or "__pycache__" in path.parts or path.suffix.lower() in {".pyc", ".pyo"}:
            continue
        artifacts.append({
            "path": path.relative_to(OUT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        })
    payload = {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-MASTERFORM-CLEANUP-R08.md",
        "manifest_self_excluded": True,
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }
    MANIFEST.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"artifact_count": len(artifacts), "manifest": str(MANIFEST)}, indent=2))


if __name__ == "__main__":
    main()
