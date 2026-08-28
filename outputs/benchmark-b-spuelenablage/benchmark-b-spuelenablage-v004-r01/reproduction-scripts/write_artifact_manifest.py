#!/usr/bin/env python3
"""Write and verify a deterministic SHA-256 manifest for one artifact tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()
    manifest = args.root / "artifact-manifest.json"
    rows = []
    for path in sorted(p for p in args.root.rglob("*") if p.is_file() and p != manifest):
        rows.append({"path": path.relative_to(args.root).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)})
    value = {"schema":"ai3d.artifact-manifest.v1","candidate":args.candidate,"file_count":len(rows),"total_bytes":sum(row["bytes"] for row in rows),"files":rows}
    temporary = manifest.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, manifest)
    errors = []
    for row in rows:
        path = args.root / row["path"]
        if path.stat().st_size != row["bytes"] or sha256(path) != row["sha256"]:
            errors.append(row["path"])
    print(json.dumps({"manifest":str(manifest),"files":len(rows),"bytes":value["total_bytes"],"verification_errors":errors}, indent=2))
    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
