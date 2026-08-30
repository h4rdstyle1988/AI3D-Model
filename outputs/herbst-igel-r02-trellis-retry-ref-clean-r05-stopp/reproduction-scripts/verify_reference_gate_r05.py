from __future__ import annotations

import base64
import binascii
import hashlib
import io
import itertools
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageFile


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "tasks"
EXPECTED_CLEAN_BYTES = 40823
EXPECTED_CLEAN_SHA256 = "2d127f873be82c7247f4c67345821d68edd2a0f8a0c2dab20d24a5e27a3ce8a2"
EXPECTED_SEAM_SHA256 = "b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strict_image(data: bytes) -> dict[str, object]:
    ImageFile.LOAD_TRUNCATED_IMAGES = False
    if not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
        raise ValueError("JPEG SOI/EOI marker missing")
    with Image.open(io.BytesIO(data)) as image:
        image.verify()
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        return {
            "format": image.format,
            "dimensions_px": [image.width, image.height],
            "mode": image.mode,
        }


def git_blob_sha1(path: Path) -> str:
    return subprocess.check_output(
        ["git", "hash-object", str(path)], cwd=ROOT, text=True
    ).strip()


def matching_git_blobs() -> list[str]:
    listing = subprocess.check_output(
        [
            "git",
            "cat-file",
            "--batch-check=%(objectname) %(objecttype) %(objectsize)",
            "--batch-all-objects",
        ],
        cwd=ROOT,
        text=True,
    )
    matches: list[str] = []
    for line in listing.splitlines():
        oid, kind, size_text = line.split()
        if kind != "blob" or int(size_text) != EXPECTED_CLEAN_BYTES:
            continue
        data = subprocess.check_output(["git", "cat-file", "blob", oid], cwd=ROOT)
        if sha256(data) == EXPECTED_CLEAN_SHA256:
            matches.append(oid)
    return matches


def local_exact_matches() -> tuple[list[str], list[str]]:
    roots = [
        ROOT,
        Path("D:/AI3D-Agent"),
        Path("D:/3D-Models/generated"),
        Path("C:/Users/h4rds/Downloads"),
        Path("C:/Users/h4rds/Desktop"),
        Path("C:/Users/h4rds/Pictures"),
        Path("C:/Users/h4rds/AppData/Local/Temp"),
        Path("C:/Users/h4rds/.codex"),
    ]
    checked: list[str] = []
    matches: list[str] = []
    seen: set[Path] = set()
    for search_root in roots:
        if not search_root.exists():
            continue
        checked.append(search_root.as_posix())
        try:
            candidates = search_root.rglob("*")
            for path in candidates:
                try:
                    resolved = path.resolve()
                    if resolved in seen or not path.is_file() or path.stat().st_size != EXPECTED_CLEAN_BYTES:
                        continue
                    seen.add(resolved)
                    if sha256(path.read_bytes()) == EXPECTED_CLEAN_SHA256:
                        matches.append(path.as_posix())
                except (OSError, PermissionError):
                    continue
        except (OSError, PermissionError):
            continue
    return checked, matches


def constrained_dqt_recovery(raw: bytes) -> dict[str, object]:
    # The missing 3 decoded bytes are confined to DQT table 1: the DQT starts
    # at 89, declares 67 bytes, but SOF0 occurs at 155 instead of 158.
    # Exhaust values 1..30 at every one of the 62 insertion boundaries. This
    # strictly contains the observed table's range 3..20 and all normal values
    # consistent with that high-quality quantization table.
    target = bytes.fromhex(EXPECTED_CLEAN_SHA256)
    attempts = 0
    found: dict[str, object] | None = None
    triples = [bytes(values) for values in itertools.product(range(1, 31), repeat=3)]
    for position in range(94, 156):
        prefix_hash = hashlib.sha256(raw[:position])
        suffix = raw[position:]
        for candidate in triples:
            check = prefix_hash.copy()
            check.update(candidate)
            check.update(suffix)
            attempts += 1
            if check.digest() == target:
                found = {"decoded_offset": position, "inserted_hex": candidate.hex()}
                break
        if found:
            break
    return {
        "search_space": "three quantization values 1..30 at all 62 DQT insertion boundaries",
        "attempts": attempts,
        "target_match": found,
        "status": "PASS" if found else "FAIL",
    }


def main() -> None:
    part_paths = [
        TASKS / f"TASK-HERBST-IGEL-R02-REF-CLEAN-R05.part{index:02d}.b64"
        for index in range(1, 9)
    ]
    encoded = b"".join(path.read_bytes() for path in part_paths)
    raw: bytes | None = None
    base64_error: str | None = None
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        base64_error = f"{type(exc).__name__}: {exc}"

    raw_image_info: dict[str, object] | None = None
    raw_decode_error: str | None = None
    if raw is not None:
        try:
            raw_image_info = strict_image(raw)
        except Exception as exc:  # explicit audit capture
            raw_decode_error = f"{type(exc).__name__}: {exc}"

    candidate = None
    constrained = None
    if raw is not None and len(raw) == 40820:
        standard_repair = raw[:155] + b"\x14\x14\x14" + raw[155:]
        candidate_info = None
        candidate_error = None
        try:
            candidate_info = strict_image(standard_repair)
        except Exception as exc:  # explicit audit capture
            candidate_error = f"{type(exc).__name__}: {exc}"
        candidate = {
            "method": "insert standard repeated DQT tail 0x14 0x14 0x14 at decoded offset 155",
            "bytes": len(standard_repair),
            "sha256": sha256(standard_repair),
            "hash_match": sha256(standard_repair) == EXPECTED_CLEAN_SHA256,
            "strict_decode_complete": candidate_info is not None,
            "image": candidate_info,
            "decode_error": candidate_error,
            "accepted_as_reference": False,
        }
        constrained = constrained_dqt_recovery(raw)

    seam_source = TASKS / "TASK-HERBST-IGEL-R01-REF-SEAM.jpg.b64"
    seam = base64.b64decode(seam_source.read_bytes(), validate=True)
    checked_roots, local_matches = local_exact_matches()
    task_path = TASKS / "TASK-HERBST-IGEL-R02-TRELLIS-RETRY-REF-CLEAN-R05.md"

    report = {
        "schema": "ai3d-reference-gate-audit-v1",
        "task": str(task_path.relative_to(ROOT)).replace("\\", "/"),
        "task_blob_sha1": git_blob_sha1(task_path),
        "queue_head": (TASKS / "TASK_QUEUE.txt").read_text(encoding="utf-8").splitlines()[0],
        "current_task_migration_file": (TASKS / "CURRENT_TASK.txt").read_text(encoding="utf-8").strip(),
        "ref_clean": {
            "source_parts": [str(path.relative_to(ROOT)).replace("\\", "/") for path in part_paths],
            "part_bytes": [path.stat().st_size for path in part_paths],
            "part_git_blob_sha1": [git_blob_sha1(path) for path in part_paths],
            "concatenated_base64_bytes": len(encoded),
            "expected_base64_bytes_for_40823_byte_payload": 54432,
            "base64_byte_deficit": 54432 - len(encoded),
            "strict_base64_decode": raw is not None,
            "base64_error": base64_error,
            "decoded_bytes": None if raw is None else len(raw),
            "expected_decoded_bytes": EXPECTED_CLEAN_BYTES,
            "decoded_byte_deficit": None if raw is None else EXPECTED_CLEAN_BYTES - len(raw),
            "decoded_sha256": None if raw is None else sha256(raw),
            "expected_sha256": EXPECTED_CLEAN_SHA256,
            "hash_match": raw is not None and sha256(raw) == EXPECTED_CLEAN_SHA256,
            "jpeg_soi": raw is not None and raw.startswith(b"\xff\xd8"),
            "jpeg_eoi": raw is not None and raw.endswith(b"\xff\xd9"),
            "strict_decode_complete": raw_image_info is not None,
            "strict_decode_error": raw_decode_error,
            "image": raw_image_info,
            "transport_diagnosis": {
                "second_dqt_marker_offset": 89,
                "second_dqt_declared_length": 67,
                "expected_next_marker_offset": 158,
                "actual_sof0_marker_offset": None if raw is None else raw.find(b"\xff\xc0", 89, 200),
                "missing_decoded_bytes_within_second_dqt": 3,
            },
            "standard_dqt_repair_candidate": candidate,
            "constrained_dqt_recovery": constrained,
            "matching_historical_git_blobs": matching_git_blobs(),
            "checked_local_roots": checked_roots,
            "matching_local_files": local_matches,
            "authorized_identity_recoverable": False,
            "status": "FAIL",
        },
        "ref_seam": {
            "source": str(seam_source.relative_to(ROOT)).replace("\\", "/"),
            "decoded_bytes": len(seam),
            "sha256": sha256(seam),
            "expected_sha256": EXPECTED_SEAM_SHA256,
            "hash_match": sha256(seam) == EXPECTED_SEAM_SHA256,
            "strict_decode_complete": True,
            "image": strict_image(seam),
            "role": "SEAM_ONLY_NOT_PRIMARY_FORM_SOURCE",
            "status": "PASS" if sha256(seam) == EXPECTED_SEAM_SHA256 else "FAIL",
        },
        "gate": "FAIL",
        "decision": "STOPP_BEFORE_TRELLIS",
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": True,
        "nutzerentscheidung_grund": (
            "Die exakt autorisierte 40823-Byte-REF-CLEAN ist aus dem freigegebenen "
            "Transport und den vorhandenen lokalen Quellen nicht byteidentisch wiederherstellbar."
        ),
    }
    report_path = OUTPUT / "reports" / "reference-gate-audit-r05.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["gate"] == "PASS" else 2)


if __name__ == "__main__":
    main()
