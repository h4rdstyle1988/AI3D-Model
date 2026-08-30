#!/usr/bin/env python3
"""Run the native Trellis CLI for the four approved R07 seed candidates."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
IMAGE = OUT / "reference-audit" / "ref-clean-r07.jpg"
RAW = OUT / "trellis-raw"
EXE = Path.home() / "AppData" / "Local" / "trellis-studio" / "runtime" / "trellis-cli.exe"
MODELS = Path.home() / "AppData" / "Local" / "trellis-studio" / "models"
SEEDS = (42, 7, 123, 777)
RESOLUTION = 512
EXPECTED_INPUT_SHA256 = "c1c9a5a094f1db2fd220f3433f83af8dedca780f56a4bf479eb8883432250859"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def run_seed(seed: int) -> dict[str, object]:
    candidate = RAW / f"seed-{seed:08d}"
    candidate.mkdir(parents=True, exist_ok=True)
    glb = candidate / f"herbst-igel-r02-trellis-raw-seed-{seed}.glb"
    ply = glb.with_suffix(".ply")
    log_path = candidate / f"trellis-cli-seed-{seed}-res512-r07.log"
    report_path = candidate / "trellis-run-r07.json"
    if glb.exists() or ply.exists():
        raise SystemExit(f"Refusing to overwrite archived raw candidate: {candidate}")

    command = [
        str(EXE),
        "--image", str(IMAGE),
        "--output", str(glb),
        "--models", str(MODELS),
        "--gpu", "0",
        "--seed", str(seed),
        "--res", str(RESOLUTION),
        "--bg-removal", "birefnet",
        "--dump-bg",
        "--no-texture",
        "--require-gpu",
    ]
    started = dt.datetime.now(dt.timezone.utc)
    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    finished = dt.datetime.now(dt.timezone.utc)
    log_path.write_bytes(process.stdout)
    run: dict[str, object] = {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-TRELLIS-OPTIK-RETRY-R07.md",
        "task_blob_sha": "fe7cae0d613379fbd22e00b12320f764ee8818ed",
        "tool": "Trellis Studio native CLI image-to-3D (GGUF/Vulkan)",
        "executable": str(EXE),
        "executable_sha256": file_sha256(EXE),
        "models": str(MODELS),
        "input": rel(IMAGE),
        "input_sha256": file_sha256(IMAGE),
        "gpu_argument": 0,
        "seed": seed,
        "seed_selection_reason": "Distinct deterministic latent RNG state; seed 42 retained as the R06 comparison baseline.",
        "resolution": RESOLUTION,
        "background_removal": "BiRefNet",
        "background_variation": "none; controlled seed comparison with identical authorized preprocessing",
        "texture": False,
        "command": command,
        "started_utc": started.isoformat(),
        "finished_utc": finished.isoformat(),
        "elapsed_seconds": (finished - started).total_seconds(),
        "returncode": process.returncode,
        "log": rel(log_path),
        "outputs": {},
    }
    for output in (glb, ply, glb.with_name(glb.stem + "_cutout.png")):
        if output.is_file():
            run["outputs"][output.suffix.lstrip(".") + ("_cutout" if "cutout" in output.stem else "")] = {
                "path": rel(output),
                "bytes": output.stat().st_size,
                "sha256": file_sha256(output),
            }
    run["status"] = (
        "PASS" if process.returncode == 0 and glb.is_file() and ply.is_file() else "STOPP"
    )
    report_path.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"seed": seed, "status": run["status"], "elapsed_seconds": run["elapsed_seconds"], "outputs": run["outputs"]}, indent=2), flush=True)
    return run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, choices=SEEDS, help="Run only one configured seed")
    args = parser.parse_args()
    if not EXE.is_file():
        raise SystemExit(f"Trellis executable missing: {EXE}")
    if not MODELS.is_dir():
        raise SystemExit(f"Trellis models missing: {MODELS}")
    if not IMAGE.is_file() or file_sha256(IMAGE) != EXPECTED_INPUT_SHA256:
        raise SystemExit("Verified R07 input is missing or has the wrong SHA-256")

    requested = (args.seed,) if args.seed is not None else SEEDS
    runs = [run_seed(seed) for seed in requested]
    if any(run["status"] != "PASS" for run in runs):
        sys.exit(2)


if __name__ == "__main__":
    main()
