#!/usr/bin/env python3
"""Stream-validate the Anycubic CLI slice output without modifying it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from smoke_single_solid import atomic_json

EXTRUSION = re.compile(r"(?:^|\s)E([+]?(?:\d+(?:\.\d*)?|\.\d+))(?:\s|$)")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gcode", type=Path, required=True)
    parser.add_argument("--stdout", type=Path, required=True)
    parser.add_argument("--stderr", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    layer = -1
    layer_z = []
    extrusion_moves = []
    layer_markers = 0
    z_markers = 0
    object_definitions = 0
    object_starts = 0
    object_ends = 0
    header: dict[str, str] = {}
    config_started = False
    suspicious_pre_config = []
    with args.gcode.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if stripped == "; CONFIG_BLOCK_START = begin":
                config_started = True
            if layer < 0 and stripped.startswith(";") and ":" in stripped:
                key, value = stripped[1:].split(":", 1)
                if key.strip() in {"total layer number", "max_z_height", "model_instances", "source_info"}:
                    header[key.strip()] = value.strip()
            if stripped == ";LAYER_CHANGE":
                layer += 1
                layer_markers += 1
                layer_z.append(None)
                extrusion_moves.append(0)
                continue
            if stripped.startswith(";Z:") and layer >= 0:
                z_markers += 1
                layer_z[layer] = float(stripped.split(":", 1)[1])
                continue
            if stripped.startswith("EXCLUDE_OBJECT_DEFINE"):
                object_definitions += 1
            elif stripped.startswith("EXCLUDE_OBJECT_START"):
                object_starts += 1
            elif stripped.startswith("EXCLUDE_OBJECT_END"):
                object_ends += 1
            if layer >= 0 and stripped.startswith(("G0", "G1", "G2", "G3")):
                match = EXTRUSION.search(stripped)
                if match and float(match.group(1)) > 0.0:
                    extrusion_moves[layer] += 1
            if not config_started and any(token in stripped.lower() for token in ("error", "warning", "repair", "non-manifold", "empty layer")):
                suspicious_pre_config.append({"line": line_number, "text": stripped[:400]})
    empty_layers = [index for index, moves in enumerate(extrusion_moves) if moves == 0]
    stdout = args.stdout.read_text(encoding="utf-8", errors="replace")
    stderr = args.stderr.read_text(encoding="utf-8", errors="replace")
    known_nonfatal = "calc_exclude_triangles:Unable to create exclude triangles" in stdout
    report = {
        "schema": "ai3d.full-model-fastpath.anycubic-slice-audit.v1",
        "slicer": {"name": "AnycubicSlicerNext", "version": "1.4.1.2"},
        "mode": {
            "auto_repair": "DISABLED_BY_--no-check",
            "machine": "Anycubic Kobra S1 0.4 nozzle",
            "process": "0.20mm High Quality @Anycubic Kobra S1 0.4 nozzle",
            "filament": "Anycubic PLA @Anycubic Kobra S1 0.4 nozzle",
            "orientation": "source +Y mapped to slicer +Z by --rotate-x 90; --ensure-on-bed; --arrange 1",
        },
        "gcode": {"path": str(args.gcode), "bytes": args.gcode.stat().st_size, "sha256": sha256(args.gcode)},
        "header": header,
        "layers": {
            "layer_change_markers": layer_markers,
            "z_markers": z_markers,
            "strictly_increasing_z": all(a is not None and b is not None and b > a for a, b in zip(layer_z, layer_z[1:])),
            "first_z_mm": layer_z[0] if layer_z else None,
            "last_z_mm": layer_z[-1] if layer_z else None,
            "layers_without_positive_extrusion": empty_layers,
            "minimum_positive_extrusion_moves_per_layer": min(extrusion_moves, default=0),
        },
        "objects": {"definitions": object_definitions, "start_markers": object_starts, "end_markers": object_ends},
        "diagnostics": {
            "gcode_pre_config_suspicious_lines": suspicious_pre_config,
            "stdout": stdout,
            "stderr": stderr,
            "known_nonfatal_plate_exclusion_visualization_message": known_nonfatal,
            "fatal_message_after_successful_output": bool(stderr.strip()) or "run found error" in stdout,
        },
    }
    expected = int(header.get("total layer number", "-1"))
    instances = int(header.get("model_instances", "-1"))
    report["pass"] = bool(
        expected == layer_markers == z_markers
        and not empty_layers
        and report["layers"]["strictly_increasing_z"]
        and instances == 1
        and object_definitions == 1
        and not suspicious_pre_config
        and not report["diagnostics"]["fatal_message_after_successful_output"]
    )
    atomic_json(args.output, report)
    print(json.dumps({"pass": report["pass"], "layers": layer_markers, "empty_layers": len(empty_layers), "objects": object_definitions, "output": str(args.output)}, indent=2))
    if not report["pass"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
