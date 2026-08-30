#!/usr/bin/env python3
"""Reconstruct and strictly verify the two authoritative R07 references."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1] / "reference-audit"
PARTS = [
    ROOT / "tasks" / f"TASK-HERBST-IGEL-R02-REF-CLEAN-R04.part{index:02d}.b64"
    for index in range(1, 5)
]
SEAM_SOURCE = ROOT / "tasks" / "TASK-HERBST-IGEL-R01-REF-SEAM.jpg.b64"
EXPECTED_CLEAN = {
    "bytes": 17344,
    "sha256": "c1c9a5a094f1db2fd220f3433f83af8dedca780f56a4bf479eb8883432250859",
    "format": "JPEG",
    "mode": "RGB",
    "size": [512, 512],
}
EXPECTED_SEAM_SHA256 = "b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4"


def normalized_b64(path: Path) -> str:
    return "".join(path.read_text(encoding="utf-8").split())


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inspect_image(path: Path) -> dict[str, object]:
    with Image.open(path) as probe:
        image_format = probe.format
        probe.verify()
    with Image.open(path) as image:
        image.load()
        return {
            "format": image_format,
            "mode": image.mode,
            "size": list(image.size),
            "strict_decode_complete": True,
        }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    chunks = [normalized_b64(part) for part in PARTS]
    clean_encoded = "".join(chunks)
    clean_bytes = base64.b64decode(clean_encoded, validate=True)
    clean_path = OUT / "ref-clean-r07.jpg"
    clean_path.write_bytes(clean_bytes)
    clean_actual = {
        "bytes": len(clean_bytes),
        "sha256": digest(clean_bytes),
        **inspect_image(clean_path),
    }
    clean_checks = {key: clean_actual[key] == value for key, value in EXPECTED_CLEAN.items()}
    clean_checks.update({"strict_base64_decode": True, "strict_image_decode": True})

    seam_encoded = normalized_b64(SEAM_SOURCE)
    seam_bytes = base64.b64decode(seam_encoded, validate=True)
    seam_path = OUT / "ref-seam-r07.jpg"
    seam_path.write_bytes(seam_bytes)
    seam_actual = {
        "bytes": len(seam_bytes),
        "sha256": digest(seam_bytes),
        **inspect_image(seam_path),
    }
    seam_checks = {
        "sha256": seam_actual["sha256"] == EXPECTED_SEAM_SHA256,
        "strict_base64_decode": True,
        "strict_image_decode": True,
    }

    payload = {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-TRELLIS-OPTIK-RETRY-R07.md",
        "task_blob_sha": "fe7cae0d613379fbd22e00b12320f764ee8818ed",
        "clean": {
            "sources": [part.relative_to(ROOT).as_posix() for part in PARTS],
            "part_base64_lengths": [len(chunk) for chunk in chunks],
            "part_base64_sha256": [digest(chunk.encode("ascii")) for chunk in chunks],
            "concatenated_base64_length": len(clean_encoded),
            "output": clean_path.relative_to(ROOT).as_posix(),
            "expected": EXPECTED_CLEAN,
            "actual": clean_actual,
            "checks": clean_checks,
            "status": "PASS" if all(clean_checks.values()) else "STOPP",
        },
        "seam": {
            "source": SEAM_SOURCE.relative_to(ROOT).as_posix(),
            "output": seam_path.relative_to(ROOT).as_posix(),
            "expected_sha256": EXPECTED_SEAM_SHA256,
            "actual": seam_actual,
            "checks": seam_checks,
            "status": "PASS" if all(seam_checks.values()) else "STOPP",
        },
    }
    payload["status"] = (
        "PASS"
        if payload["clean"]["status"] == "PASS" and payload["seam"]["status"] == "PASS"
        else "STOPP"
    )
    report = OUT / "reference-gate-audit-r07.json"
    report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if payload["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
