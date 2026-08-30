#!/usr/bin/env python3
"""Reproduce the mandatory R04 reference transport gate."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import io
import json
import os
import subprocess
from pathlib import Path

from PIL import Image


TASK = Path("tasks/TASK-HERBST-IGEL-R02-TRELLIS-RETRY-REF-CLEAN-R04.md")
QUEUE = Path("tasks/TASK_QUEUE.txt")
CURRENT = Path("tasks/CURRENT_TASK.txt")
CLEAN = Path("tasks/TASK-HERBST-IGEL-R02-REF-CLEAN-R04.jpg.b64")
SEAM = Path("tasks/TASK-HERBST-IGEL-R01-REF-SEAM.jpg.b64")
EXPECTED_CLEAN_SHA256 = "1b039abd4e83ddeff1fe707d07bca5d492b3fbb956857599936b317cf22b4a29"
EXPECTED_SEAM_SHA256 = "b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4"
EXPECTED_CLEAN_BYTES = 31028
TRUNCATION_MARKER = "[...truncated...]"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def strict_image(data: bytes) -> dict:
    result: dict = {
        "jpeg_soi": data[:2] == b"\xff\xd8",
        "jpeg_eoi": data[-2:] == b"\xff\xd9",
        "strict_full_decode": False,
        "format": None,
        "mode": None,
        "dimensions_px": None,
        "error": None,
    }
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            result.update(
                strict_full_decode=True,
                format=image.format,
                mode=image.mode,
                dimensions_px=list(image.size),
            )
    except Exception as exc:  # Exact decoder message is part of the audit.
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def audit_b64(path: Path, expected_sha: str) -> dict:
    stored = path.read_bytes()
    text = stored.decode("utf-8-sig")
    compact = "".join(text.split())
    result: dict = {
        "source": path.as_posix(),
        "repository_bytes": len(stored),
        "repository_sha256": sha256(stored),
        "git_blob_sha1": git("hash-object", "--", str(path)),
        "base64_strict": False,
        "base64_error": None,
        "decoded_bytes": None,
        "decoded_sha256": None,
        "expected_decoded_sha256": expected_sha,
        "hash_match": False,
    }
    try:
        decoded = base64.b64decode(compact, validate=True)
        result.update(
            base64_strict=True,
            decoded_bytes=len(decoded),
            decoded_sha256=sha256(decoded),
            hash_match=sha256(decoded) == expected_sha,
            **strict_image(decoded),
        )
    except (binascii.Error, ValueError) as exc:
        result["base64_error"] = f"{type(exc).__name__}: {exc}"
    return result


def git_object_candidates() -> list[dict]:
    listing = subprocess.check_output(
        [
            "git",
            "cat-file",
            "--batch-all-objects",
            "--batch-check=%(objectname) %(objecttype) %(objectsize)",
        ],
        text=True,
    )
    candidates = []
    for line in listing.splitlines():
        object_id, object_type, object_size = line.split()
        if object_type != "blob" or int(object_size) != EXPECTED_CLEAN_BYTES:
            continue
        data = subprocess.check_output(["git", "cat-file", "blob", object_id])
        candidates.append(
            {
                "object_id": object_id,
                "bytes": len(data),
                "sha256": sha256(data),
                "expected_hash_match": sha256(data) == EXPECTED_CLEAN_SHA256,
            }
        )
    return candidates


def filesystem_candidates() -> list[dict]:
    roots = [Path.cwd(), Path("D:/AI3D-Agent"), Path("D:/3D-Models/generated")]
    candidates = []
    seen: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        for directory, names, files in os.walk(root):
            names[:] = [name for name in names if name != ".git"]
            for name in files:
                path = Path(directory, name)
                try:
                    resolved = str(path.resolve()).casefold()
                    if resolved in seen or path.stat().st_size != EXPECTED_CLEAN_BYTES:
                        continue
                    seen.add(resolved)
                    data = path.read_bytes()
                    candidates.append(
                        {
                            "path": str(path),
                            "bytes": len(data),
                            "sha256": sha256(data),
                            "expected_hash_match": sha256(data)
                            == EXPECTED_CLEAN_SHA256,
                        }
                    )
                except OSError:
                    continue
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    clean = audit_b64(CLEAN, EXPECTED_CLEAN_SHA256)
    compact = "".join(CLEAN.read_text(encoding="utf-8-sig").split())
    marker_index = compact.find(TRUNCATION_MARKER)
    prefix = compact[:marker_index] if marker_index >= 0 else compact
    prefix = prefix[: len(prefix) // 4 * 4]
    prefix_decoded = base64.b64decode(prefix, validate=True) if prefix else b""
    clean.update(
        {
            "expected_decoded_bytes": EXPECTED_CLEAN_BYTES,
            "expected_unwrapped_base64_characters": 41372,
            "literal_truncation_marker_present": marker_index >= 0,
            "truncation_marker_index_compact": marker_index,
            "valid_base64_prefix_characters": len(prefix),
            "valid_prefix_decoded_bytes": len(prefix_decoded),
            "valid_prefix_jpeg_soi": prefix_decoded[:2] == b"\xff\xd8",
            "valid_prefix_jpeg_eoi": prefix_decoded[-2:] == b"\xff\xd9",
            "expected_size_match": clean.get("decoded_bytes") == EXPECTED_CLEAN_BYTES,
            "expected_dimensions_match": clean.get("dimensions_px") == [512, 512],
            "expected_mode_match": clean.get("mode") == "RGB",
            "status": "PASS"
            if clean.get("base64_strict")
            and clean.get("hash_match")
            and clean.get("decoded_bytes") == EXPECTED_CLEAN_BYTES
            and clean.get("dimensions_px") == [512, 512]
            and clean.get("mode") == "RGB"
            and clean.get("strict_full_decode")
            else "FAIL",
        }
    )

    seam = audit_b64(SEAM, EXPECTED_SEAM_SHA256)
    seam["status"] = (
        "PASS"
        if seam.get("base64_strict")
        and seam.get("hash_match")
        and seam.get("strict_full_decode")
        else "FAIL"
    )

    task_path = TASK.as_posix()
    queue_entries = [
        line.strip()
        for line in QUEUE.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    git_candidates = git_object_candidates()
    file_candidates = filesystem_candidates()
    report = {
        "schema": "ai3d-reference-gate-audit-v1",
        "task": {
            "path": task_path,
            "blob_sha1": git("hash-object", "--", str(TASK)),
            "product_revision": "R02",
            "retry_revision": "R04",
        },
        "queue": {
            "entries": queue_entries,
            "task_is_fifo_head": bool(queue_entries and queue_entries[0] == task_path),
            "current_task_migration_value": CURRENT.read_text(encoding="utf-8-sig").strip(),
        },
        "ref_clean": clean,
        "ref_seam": seam,
        "recovery": {
            "searched_filesystem_roots": [
                str(Path.cwd()),
                "D:/AI3D-Agent",
                "D:/3D-Models/generated",
            ],
            "filesystem_files_with_expected_byte_size": file_candidates,
            "all_git_objects_with_expected_decoded_byte_size": git_candidates,
            "matching_filesystem_copy_found": any(
                item["expected_hash_match"] for item in file_candidates
            ),
            "matching_git_object_found": any(
                item["expected_hash_match"] for item in git_candidates
            ),
            "authorized_identity_recoverable_from_repository": False,
        },
        "reference_gate": "PASS" if clean["status"] == "PASS" and seam["status"] == "PASS" else "FAIL",
        "required_action": "STOPP_BEFORE_TRELLIS",
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": True,
        "nutzerentscheidung_grund": (
            "Die autorisierte 31028-Byte-REF-CLEAN mit dem festgelegten SHA-256 "
            "ist im freigegebenen Repository-Blob nicht vorhanden und nicht "
            "eindeutig rekonstruierbar."
        ),
        "final_product_approval": False,
    }

    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if report["reference_gate"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
