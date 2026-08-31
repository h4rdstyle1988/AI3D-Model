#!/usr/bin/env python3
"""Write SHA-256 metadata for every R12 result artifact except the manifest itself."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


OUT = Path(__file__).resolve().parents[1]
ROOT = OUT.parents[1]
MANIFEST = OUT / "artifact-manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    files = sorted(path for path in OUT.rglob("*") if path.is_file() and path != MANIFEST)
    payload = {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-SINGLE-SURFACE-ROI-REBUILD-R12.md",
        "technical_revision": "R12",
        "status": "STOPP",
        "artifacts": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in files
        ],
        "final_user_approval_claimed": False,
    }
    MANIFEST.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
