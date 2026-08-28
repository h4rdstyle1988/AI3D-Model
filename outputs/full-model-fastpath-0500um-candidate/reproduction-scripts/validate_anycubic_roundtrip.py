#!/usr/bin/env python3
"""Validate a separate AnycubicSlicerNext --no-check STL roundtrip."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh

from full_model_fastpath import PREFIX, manifest_tree, sha256, triangle_geometry_digest
from smoke_layer_slice_audit import audit_mesh
from smoke_single_solid import atomic_json, topology, topology_gate
from v002_prebuild_c01_analysis import self_events


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", required=True, type=Path)
    parser.add_argument("--roundtrip", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    fast_path = args.variant / f"{PREFIX}-fast-gate.json"
    fast = json.loads(fast_path.read_text(encoding="utf-8"))
    original_path = Path(fast["artifacts"]["stl"]["path"])
    original = trimesh.load(original_path, force="mesh", process=True)
    roundtrip = trimesh.load(args.roundtrip, force="mesh", process=True)
    original_digest = triangle_geometry_digest(original)
    roundtrip_digest = triangle_geometry_digest(roundtrip)
    metrics = topology(roundtrip)
    if original_digest == roundtrip_digest:
        events = fast["working"]["events"]
        event_mode = "TRANSFERRED_FROM_IDENTICAL_1E-5MM_TRIANGLE_MULTISET"
    else:
        events = self_events(roundtrip, name=f"{PREFIX}/Anycubic-no-check-roundtrip", workers=args.workers, chunk_size=768, radius_bins=8)
        event_mode = "RECOMPUTED"
    gate = topology_gate(metrics, events)
    layer = audit_mesh(roundtrip, 0.5, 1e-5)
    report = {
        "schema": "ai3d.full-model-fastpath.anycubic-no-check-roundtrip.v1",
        "slicer": {"name": "AnycubicSlicerNext", "version": "1.4.1.2", "mode": "--no-check --export-stl"},
        "auto_repair": "DISABLED_BY_--no-check (CLI help: Do not run any validity checks)",
        "source_stl": {"path": str(original_path), "sha256": sha256(original_path)},
        "roundtrip_stl": {"path": str(args.roundtrip), "sha256": sha256(args.roundtrip)},
        "triangle_multiset": {
            "quantum_mm": 1e-5,
            "source_digest": original_digest,
            "roundtrip_digest": roundtrip_digest,
            "identical": original_digest == roundtrip_digest,
        },
        "bounds_delta_mm": (np.asarray(roundtrip.bounds) - np.asarray(original.bounds)).tolist(),
        "topology": metrics,
        "self_intersections_and_contacts": events,
        "self_event_mode": event_mode,
        "topology_gate": gate,
        "layer_loop_slicability": layer,
        "pass": bool(gate["pass"] and layer["pass"]),
    }
    out = args.roundtrip.parent / "anycubic-no-check-roundtrip-validation.json"
    atomic_json(out, report)
    atomic_json(args.variant / "artifact-manifest.json", manifest_tree(args.variant))
    print(json.dumps({"pass": report["pass"], "triangle_multiset_identical": report["triangle_multiset"]["identical"], "event_mode": event_mode, "output": str(out)}, indent=2))
    if not report["pass"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
