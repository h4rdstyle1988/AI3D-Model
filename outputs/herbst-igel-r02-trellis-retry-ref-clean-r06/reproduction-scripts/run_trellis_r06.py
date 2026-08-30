#!/usr/bin/env python3
"""Run the native Trellis Studio CLI for the authorized R06 reference."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
IMAGE = OUT / "reference-audit" / "ref-clean-r06.jpg"
RAW = OUT / "trellis-raw"
GLB = RAW / "herbst-igel-r02-trellis-raw-r06.glb"
EXE = Path.home() / "AppData" / "Local" / "trellis-studio" / "runtime" / "trellis-cli.exe"
MODELS = Path.home() / "AppData" / "Local" / "trellis-studio" / "models"
SEED = 42
RESOLUTION = 512


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    if not EXE.is_file():
        raise SystemExit(f"Trellis executable missing: {EXE}")
    if not MODELS.is_dir():
        raise SystemExit(f"Trellis models missing: {MODELS}")
    if not IMAGE.is_file():
        raise SystemExit(f"Verified input missing: {IMAGE}")
    if GLB.exists() or GLB.with_suffix(".ply").exists():
        raise SystemExit("Refusing to overwrite an archived Trellis raw mesh")

    RAW.mkdir(parents=True, exist_ok=True)
    command = [
        str(EXE),
        "--image", str(IMAGE),
        "--output", str(GLB),
        "--models", str(MODELS),
        "--gpu", "0",
        "--seed", str(SEED),
        "--res", str(RESOLUTION),
        "--birefnet",
        "--no-texture",
        "--require-gpu",
    ]
    started = dt.datetime.now(dt.timezone.utc)
    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    finished = dt.datetime.now(dt.timezone.utc)
    log_path = RAW / "trellis-cli-seed42-res512-r06.log"
    log_path.write_bytes(process.stdout)

    run = {
        "schema_version": 1,
        "tool": "Trellis Studio native CLI image-to-3D (GGUF/Vulkan)",
        "executable": str(EXE),
        "executable_sha256": file_sha256(EXE),
        "models": str(MODELS),
        "input": IMAGE.relative_to(ROOT).as_posix(),
        "input_sha256": file_sha256(IMAGE),
        "gpu_argument": 0,
        "seed": SEED,
        "resolution": RESOLUTION,
        "background_removal": "BiRefNet",
        "texture": False,
        "command": command,
        "started_utc": started.isoformat(),
        "finished_utc": finished.isoformat(),
        "elapsed_seconds": (finished - started).total_seconds(),
        "returncode": process.returncode,
        "log": log_path.relative_to(ROOT).as_posix(),
        "outputs": {},
    }
    for output in (GLB, GLB.with_suffix(".ply")):
        if output.is_file():
            run["outputs"][output.suffix.lstrip(".")] = {
                "path": output.relative_to(ROOT).as_posix(),
                "bytes": output.stat().st_size,
                "sha256": file_sha256(output),
            }
    run["status"] = (
        "PASS"
        if process.returncode == 0 and GLB.is_file() and GLB.with_suffix(".ply").is_file()
        else "STOPP"
    )
    report_path = RAW / "trellis-run-r06.json"
    report_path.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(run, indent=2))
    if run["status"] != "PASS":
        sys.exit(process.returncode or 2)


if __name__ == "__main__":
    main()
