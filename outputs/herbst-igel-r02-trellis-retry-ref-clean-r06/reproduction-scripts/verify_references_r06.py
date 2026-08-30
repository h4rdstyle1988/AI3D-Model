#!/usr/bin/env python3
"""Reconstruct and strictly verify the two authorized R06 references."""

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
    text = path.read_text(encoding="utf-8")
    return "".join(text.split())


def decode_strict(encoded: str) -> bytes:
    return base64.b64decode(encoded, validate=True)


def sha256(data: bytes) -> str:
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

    clean_part_lengths = []
    clean_part_sha256 = []
    clean_chunks = []
    for part in PARTS:
        chunk = normalized_b64(part)
        clean_chunks.append(chunk)
        clean_part_lengths.append(len(chunk))
        clean_part_sha256.append(hashlib.sha256(chunk.encode("ascii")).hexdigest())
    clean_encoded = "".join(clean_chunks)
    clean_bytes = decode_strict(clean_encoded)
    clean_path = OUT / "ref-clean-r06.jpg"
    clean_path.write_bytes(clean_bytes)
    clean_image = inspect_image(clean_path)
    clean_actual = {
        "bytes": len(clean_bytes),
        "sha256": sha256(clean_bytes),
        **clean_image,
    }
    clean_checks = {
        key: clean_actual[key] == value for key, value in EXPECTED_CLEAN.items()
    }
    clean_checks["strict_base64_decode"] = True
    clean_checks["strict_image_decode"] = bool(clean_image["strict_decode_complete"])

    seam_encoded = normalized_b64(SEAM_SOURCE)
    seam_bytes = decode_strict(seam_encoded)
    seam_path = OUT / "ref-seam-r06.jpg"
    seam_path.write_bytes(seam_bytes)
    seam_image = inspect_image(seam_path)
    seam_actual = {
        "bytes": len(seam_bytes),
        "sha256": sha256(seam_bytes),
        **seam_image,
    }
    seam_checks = {
        "sha256": seam_actual["sha256"] == EXPECTED_SEAM_SHA256,
        "strict_base64_decode": True,
        "strict_image_decode": bool(seam_image["strict_decode_complete"]),
    }

    payload = {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-TRELLIS-RETRY-REF-CLEAN-R06.md",
        "clean": {
            "sources": [part.relative_to(ROOT).as_posix() for part in PARTS],
            "part_base64_lengths": clean_part_lengths,
            "part_base64_sha256": clean_part_sha256,
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
    report = OUT / "reference-gate-audit-r06.json"
    report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if payload["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
