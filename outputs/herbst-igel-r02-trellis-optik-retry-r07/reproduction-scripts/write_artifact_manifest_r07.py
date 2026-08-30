#!/usr/bin/env python3
"""Write and verify the deterministic R07 artifact manifest."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "artifact-manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    files = sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path != MANIFEST
        and "__pycache__" not in path.parts
        and path.suffix.lower() not in {".pyc", ".pyo"}
    )
    rows = [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in files
    ]
    payload = {
        "schema": "ai3d.artifact-manifest.v1",
        "task": "tasks/TASK-HERBST-IGEL-R02-TRELLIS-OPTIK-RETRY-R07.md",
        "task_blob_sha": "fe7cae0d613379fbd22e00b12320f764ee8818ed",
        "candidate": "herbst-igel-r02-trellis-optik-retry-r07-stopp",
        "file_count": len(rows),
        "total_bytes": sum(row["bytes"] for row in rows),
        "files": rows,
    }
    temporary = MANIFEST.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, MANIFEST)
    errors = [
        row["path"]
        for row in rows
        if (ROOT / row["path"]).stat().st_size != row["bytes"]
        or sha256(ROOT / row["path"]) != row["sha256"]
    ]
    print(json.dumps({"manifest": str(MANIFEST), "files": len(rows), "bytes": payload["total_bytes"], "verification_errors": errors}, indent=2))
    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
