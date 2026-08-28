#!/usr/bin/env python3
"""Strict contract validator for Benchmark B – Spülenablage gate reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REVISION = "B-2026-08-25.1"
ZONES = ("dish_brush", "sponge", "detergent_bottle")


def nested(value: dict[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def validate(report: dict[str, Any]) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    checks["schema"] = report.get("schema") == "ai3d.benchmark-b.gate-report.v1"
    checks["requirements_revision"] = report.get("requirements_revision") == REVISION
    checks["candidate_identified"] = bool(nested(report, "candidate", "id")) and bool(nested(report, "candidate", "source_sha256"))

    dimension = nested(report, "dimension_gate") or {}
    outlet = dimension.get("outlet") if isinstance(dimension, dict) else {}
    checks["prior_main_dimensions_pass"] = dimension.get("prior_main_dimensions_pass") is True
    checks["outlet_target_is_50mm"] = outlet.get("functional_length_target_mm") == 50.0
    checks["outlet_measured_is_50mm"] = outlet.get("functional_length_measured_mm") == 50.0
    checks["outlet_measurement_references_present"] = bool(outlet.get("start_reference")) and bool(outlet.get("end_reference"))
    checks["outlet_top_open_full_length"] = outlet.get("top_open_over_full_length") is True
    min_width = outlet.get("minimum_clear_width_mm")
    max_width = outlet.get("maximum_clear_width_mm")
    checks["channel_widths_valid"] = positive_number(min_width) and positive_number(max_width) and max_width >= min_width
    checks["channel_width_positions_reported"] = outlet.get("minimum_width_position_mm") is not None and outlet.get("maximum_width_position_mm") is not None
    grid_present = dimension.get("grid_surfaces_present", {})
    checks["all_grid_surfaces_present"] = all(grid_present.get(zone) is True for zone in ZONES)
    checks["dimension_gate_declared_pass"] = dimension.get("pass") is True

    function = nested(report, "function_gate") or {}
    water = function.get("water", {})
    checks["all_grid_zones_connected_to_outlet"] = all(
        water.get(key) is True
        for key in (
            "brush_grid_to_outlet_connected",
            "sponge_grid_to_outlet_connected",
            "detergent_grid_to_outlet_connected",
        )
    )
    checks["channel_open_free_no_traps"] = all(
        water.get(key) is True
        for key in (
            "channel_open_and_free",
            "no_unintended_pockets",
            "no_dead_ends",
            "no_unconnected_local_minima",
            "sink_rim_rise_verified",
            "free_discharge_after_rim_verified",
        )
    )
    use = function.get("use", {})
    checks["all_objects_stably_supported"] = all(
        use.get(key) is True
        for key in (
            "dish_brush_stably_supported",
            "sponge_stably_supported",
            "detergent_bottle_stably_supported",
            "objects_supported_by_real_grid_geometry",
            "drainage_remains_functional_when_loaded",
        )
    )
    fdm = function.get("fdm", {})
    checks["fdm_profile_identified"] = bool(fdm.get("profile"))
    checks["fdm_and_roundtrip_gates"] = all(
        fdm.get(key) is True
        for key in (
            "grid_struts_robust",
            "grid_openings_not_unnecessarily_fine",
            "bridge_spans_acceptable",
            "slicable_geometry",
            "stl_roundtrip_pass",
            "3mf_roundtrip_pass",
            "slicer_pass",
        )
    )
    checks["function_gate_declared_pass"] = function.get("pass") is True

    measurements = report.get("grid_measurements", {})
    for zone in ZONES:
        row = measurements.get(zone) if isinstance(measurements, dict) else None
        checks[f"{zone}_measurements_complete"] = bool(
            isinstance(row, dict)
            and positive_number(row.get("strut_width_mm"))
            and positive_number(row.get("strut_height_or_thickness_mm"))
            and positive_number(row.get("typical_opening_width_mm"))
            and row.get("reference_object_envelope")
            and row.get("contact_and_stability_result") == "PASS"
            and row.get("drainage_connectivity_result") == "PASS"
        )
    checks["evidence_present"] = isinstance(report.get("evidence"), list) and len(report["evidence"]) > 0
    checks["overall_declared_pass"] = report.get("overall_pass") is True
    failed = [name for name, passed in checks.items() if not passed]
    return {"revision": REVISION, "pass": not failed, "checks": checks, "failed_checks": failed}


def self_test() -> dict[str, Any]:
    base = {
        "schema": "ai3d.benchmark-b.gate-report.v1",
        "requirements_revision": REVISION,
        "candidate": {"id": "synthetic", "source_sha256": "a" * 64, "status": "PASS"},
        "dimension_gate": {
            "prior_main_dimensions_pass": True,
            "outlet": {
                "functional_length_target_mm": 50.0,
                "functional_length_measured_mm": 50.0,
                "start_reference": "exit plane",
                "end_reference": "overhang end",
                "top_open_over_full_length": True,
                "minimum_clear_width_mm": 8.0,
                "maximum_clear_width_mm": 12.0,
                "minimum_width_position_mm": [0, 0, 0],
                "maximum_width_position_mm": [1, 0, 0]
            },
            "grid_surfaces_present": {zone: True for zone in ZONES},
            "pass": True
        },
        "function_gate": {
            "water": {
                "brush_grid_to_outlet_connected": True,
                "sponge_grid_to_outlet_connected": True,
                "detergent_grid_to_outlet_connected": True,
                "channel_open_and_free": True,
                "no_unintended_pockets": True,
                "no_dead_ends": True,
                "no_unconnected_local_minima": True,
                "sink_rim_rise_verified": True,
                "free_discharge_after_rim_verified": True
            },
            "use": {
                "dish_brush_stably_supported": True,
                "sponge_stably_supported": True,
                "detergent_bottle_stably_supported": True,
                "objects_supported_by_real_grid_geometry": True,
                "drainage_remains_functional_when_loaded": True
            },
            "fdm": {
                "profile": "synthetic",
                "grid_struts_robust": True,
                "grid_openings_not_unnecessarily_fine": True,
                "bridge_spans_acceptable": True,
                "slicable_geometry": True,
                "stl_roundtrip_pass": True,
                "3mf_roundtrip_pass": True,
                "slicer_pass": True
            },
            "pass": True
        },
        "grid_measurements": {
            zone: {
                "strut_width_mm": 2.0,
                "strut_height_or_thickness_mm": 2.0,
                "typical_opening_width_mm": 5.0,
                "reference_object_envelope": "synthetic",
                "contact_and_stability_result": "PASS",
                "drainage_connectivity_result": "PASS"
            }
            for zone in ZONES
        },
        "evidence": ["synthetic"],
        "overall_pass": True
    }
    positive = validate(base)
    base["dimension_gate"]["outlet"]["functional_length_measured_mm"] = 49.9
    negative = validate(base)
    return {
        "pass": positive["pass"] is True and negative["pass"] is False and "outlet_measured_is_50mm" in negative["failed_checks"],
        "positive_case": positive,
        "wrong_length_case": negative
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        result = self_test()
    elif args.report:
        result = validate(json.loads(args.report.read_text(encoding="utf-8")))
    else:
        parser.error("report or --self-test required")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not result["pass"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
