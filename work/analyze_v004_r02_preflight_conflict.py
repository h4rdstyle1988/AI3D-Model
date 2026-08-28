#!/usr/bin/env python3
"""Preflight-only constraint audit for the proposed v004-r02 revision.

This script deliberately creates no mesh.  It records the vertical and
hydraulic contradiction before any geometry is changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


REFERENCE_FILES = (
    "benchmark-b-spuelenablage-v004-r01-wanne.stl",
    "benchmark-b-spuelenablage-v004-r01-wanne.3mf",
    "benchmark-b-spuelenablage-v004-r01-wanne.glb",
    "benchmark-b-spuelenablage-v004-r01-einsatz.stl",
    "benchmark-b-spuelenablage-v004-r01-einsatz.3mf",
    "benchmark-b-spuelenablage-v004-r01-einsatz.glb",
    "benchmark-b-spuelenablage-v004-r01-zusammengesetzt.glb",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def make_figure(output: Path, values: dict) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.5), dpi=180)

    ax = axes[0]
    ax.axhspan(0, 10, color="#cbd5e1", alpha=0.35, label="Höhenzone Fuß")
    ax.axhline(27, color="#2563eb", lw=3, label="Gitterunterseite Z=27")
    ax.axhline(values["existing_floor_top_z_mm"], color="#334155", lw=3, label="Boden v004-r01")
    ax.axhline(10, color="#111827", lw=2, ls="--", label="Unterseite Hauptkörper Z=10")
    ax.axhspan(8.0, 8.5, color="#dc2626", alpha=0.25, label="Bodenziel für 19,0–18,5 mm")
    ax.axhline(12.0, color="#ea580c", lw=2, label="Zapfenende Z=12")
    ax.annotate(
        "striktes Ziel drückt die 2-mm-Schale\nbis Z=6,0–6,5 unter die Wanne",
        xy=(0.65, 8.25), xytext=(1.4, 16.2),
        arrowprops=dict(arrowstyle="->", color="#b91c1c"), color="#991b1b", fontsize=9,
    )
    ax.set_xlim(0, 4); ax.set_ylim(4.5, 29)
    ax.set_xticks([]); ax.set_ylabel("Z [mm]")
    ax.set_title("A – VERTIKALER MASSKONFLIKT")
    ax.legend(loc="upper right", fontsize=7)

    ax = axes[1]
    y = np.linspace(-55.0, -28.0, 300)
    existing = np.where(
        y < -39.3,
        10.0 + np.clip((y + 55.0) / 15.7, 0.0, 1.0) * 2.0,
        12.0 + 3.0 * np.clip((y + 42.5) / 85.0, 0.0, 1.0) + 9.0 / 120.0,
    )
    ax.plot(y, existing, color="#334155", lw=3, label="bestehender Gefälle-/Ablaufboden")
    ax.scatter([values["holder_cell_y_mm"]], [values["target_floor_top_for_18p5_mm"]], color="#dc2626", s=65, zorder=3)
    ax.scatter([values["holder_cell_y_mm"]], [values["target_floor_top_for_19_mm"]], color="#991b1b", s=65, zorder=3)
    ax.axhline(10.0, color="#0f172a", ls="--", lw=1.5, label="Ablaufende Z=10")
    ax.fill_between(y, 8.0, 10.0, color="#dc2626", alpha=0.15)
    ax.annotate(
        "Zielboden 8,0–8,5 liegt\n1,5–2,0 mm unter dem Ablaufende",
        xy=(values["holder_cell_y_mm"], 8.25), xytext=(-51, 15.0),
        arrowprops=dict(arrowstyle="->", color="#b91c1c"), color="#991b1b", fontsize=9,
    )
    ax.text(-50.5, 8.8, "ohne Absenkung des Ablaufs entsteht ein Tiefpunkt", color="#991b1b", fontsize=8)
    ax.set_xlim(-55, -28); ax.set_ylim(6.5, 17)
    ax.set_xlabel("Y [mm] (Frontauslauf links ←)"); ax.set_ylabel("Bodenoberseite Z [mm]")
    ax.set_title("B – HYDRAULISCHER KONFLIKT")
    ax.legend(loc="upper left", fontsize=7)

    fig.suptitle("v004-r02 PREFLIGHT – STOPP VOR GEOMETRIEÄNDERUNG", fontsize=14, fontweight="bold")
    fig.tight_layout()
    target = output / "PREFLIGHT-CONSTRAINT-CROSS-SECTION.png"
    fig.savefig(target, bbox_inches="tight")
    plt.close(fig)
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)

    grid_underside = 27.0
    cell_x = -9.0
    cell_y = -33.93782217350893
    existing_floor_top = 12.0 + 3.0 * ((cell_y + 42.5) / 85.0) + abs(cell_x) / 120.0
    target_18p5 = grid_underside - 18.5
    target_19 = grid_underside - 19.0
    shell_thickness = 2.0
    body_bottom = 10.0
    outlet_end_top = 10.0
    plug_tip = 12.0
    tip_clearance_only_floor = plug_tip - 0.5

    baseline_manifest = json.loads((args.reference_dir / "artifact-manifest.json").read_text(encoding="utf-8"))
    recorded = {entry["path"]: entry["sha256"] for entry in baseline_manifest["files"]}
    reference_hashes = {}
    all_unchanged = True
    for name in REFERENCE_FILES:
        current = sha256(args.reference_dir / name)
        matches = current == recorded[name]
        all_unchanged &= matches
        reference_hashes[name] = {
            "sha256": current,
            "matches_v004_r01_manifest": matches,
        }

    values = {
        "grid_underside_z_mm": grid_underside,
        "holder_cell_x_mm": cell_x,
        "holder_cell_y_mm": cell_y,
        "existing_floor_top_z_mm": existing_floor_top,
        "existing_clearance_below_grid_underside_mm": grid_underside - existing_floor_top,
        "target_floor_top_for_18p5_mm": target_18p5,
        "target_floor_top_for_19_mm": target_19,
        "required_lowering_for_18p5_mm": existing_floor_top - target_18p5,
        "required_lowering_for_19_mm": existing_floor_top - target_19,
        "target_shell_bottom_for_18p5_mm": target_18p5 - shell_thickness,
        "target_shell_bottom_for_19_mm": target_19 - shell_thickness,
        "main_body_bottom_z_mm": body_bottom,
        "protrusion_below_main_body_for_18p5_mm": body_bottom - (target_18p5 - shell_thickness),
        "protrusion_below_main_body_for_19_mm": body_bottom - (target_19 - shell_thickness),
        "existing_outlet_end_floor_top_z_mm": outlet_end_top,
        "target_below_outlet_for_18p5_mm": outlet_end_top - target_18p5,
        "target_below_outlet_for_19_mm": outlet_end_top - target_19,
        "plug_tip_z_mm": plug_tip,
        "floor_top_for_tip_plus_0p5_clearance_mm": tip_clearance_only_floor,
        "resulting_under_grid_clearance_at_tip_plus_0p5_mm": grid_underside - tip_clearance_only_floor,
        "source_resolution_mm": 0.5,
        "rim_relief_target_mm": [0.25, 0.40],
        "rim_relief_representable_in_source_grid": False,
    }
    section = make_figure(args.output_dir, values)
    payload = {
        "schema": "ai3d.benchmark-b.v004-r02.preflight-conflict.v1",
        "status": "STOPPED_BEFORE_GEOMETRY",
        "geometry_created": False,
        "geometry_changed": False,
        "blocking_conflicts": [
            "18.5-19.0 mm below-grid clearance requires floor top Z=8.5-8.0 and a 2 mm shell bottom Z=6.5-6.0, below the unchanged main-body underside Z=10.",
            "The target floor is 1.5-2.0 mm below the existing outlet end Z=10; retaining that outlet creates a hydraulic low point/water trap.",
            "The independently requested 0.25-0.40 mm rim relief is not representable by the unchanged 0.5 mm binary build grid.",
        ],
        "values": values,
        "reference_geometry_hashes": reference_hashes,
        "all_v004_r01_geometry_hashes_unchanged": all_unchanged,
        "proof_section": str(section),
    }
    write_json(args.output_dir / "PREFLIGHT-CONFLICT-AUDIT.json", payload)

    (args.output_dir / "GEOMETRY-NOT-CREATED.txt").write_text(
        "STOPPED BEFORE GEOMETRY: no v004-r02 STL, 3MF or GLB was created.\n",
        encoding="utf-8",
    )
    (args.output_dir / "PREFLIGHT-CONFLICT-REPORT.md").write_text(
        "# v004-r02 – PREFLIGHT-KONFLIKTBERICHT\n\n"
        "Status: **STOPP VOR GEOMETRIEÄNDERUNG**  \n"
        "v004-r01-Geometrie: **unverändert; alle sieben Referenz-Hashes stimmen mit dem Manifest überein**\n\n"
        "## Blocker 1 – verbindliche Halterfreiheit\n\n"
        f"Die Gitterunterseite liegt bei Z={grid_underside:.2f} mm. Für 18,5 mm freie Tiefe darf der "
        f"Boden höchstens Z={target_18p5:.2f} mm erreichen; für 19,0 mm höchstens Z={target_19:.2f} mm. "
        f"Der vorhandene Boden liegt an der Steckwabe bei Z={existing_floor_top:.3f} mm. Er müsste damit "
        f"um {existing_floor_top-target_18p5:.3f} bis {existing_floor_top-target_19:.3f} mm abgesenkt werden.\n\n"
        f"Bei unveränderter 2-mm-Bodenschale läge deren Unterseite auf Z={target_18p5-shell_thickness:.2f} "
        f"bis Z={target_19-shell_thickness:.2f} mm. Am Ort der Steckwabe existiert kein hinterer Fuß; die "
        f"unveränderte Hauptkörper-Unterseite liegt bei Z={body_bottom:.2f} mm. Die neue Schale würde daher "
        f"{body_bottom-(target_18p5-shell_thickness):.2f} bis {body_bottom-(target_19-shell_thickness):.2f} mm "
        "nach unten aus der Wanne herausragen. Das verletzt das unveränderte Hauptkörpermaß und die Druckauflage.\n\n"
        "## Blocker 2 – Wasserweg\n\n"
        f"Das bestehende freie Ablaufende liegt auf Z={outlet_end_top:.2f} mm. Der verlangte lokale Boden "
        f"läge {outlet_end_top-target_18p5:.2f} bis {outlet_end_top-target_19:.2f} mm tiefer. Bei unverändertem "
        "Ablauf entstünde damit zwingend ein lokaler Tiefpunkt. Um ihn zu entwässern, müssten Gefällekanal und "
        "Ablaufende ebenfalls abgesenkt werden; das wäre keine ausschließlich lokale Korrektur unter der Wabe "
        "und widerspricht der Vorgabe, den bestehenden vorderen Ablauf unverändert zu lassen.\n\n"
        "## Widerspruch zur Zapfen-Sicherheitsanforderung\n\n"
        f"Nur der separat genannte Sicherheitsabstand von +0,5 mm zum Zapfenende Z={plug_tip:.2f} mm würde "
        f"einen Boden bei Z={tip_clearance_only_floor:.2f} mm verlangen. Das ergäbe jedoch lediglich "
        f"{grid_underside-tip_clearance_only_floor:.2f} mm freie Tiefe unter der Gitterunterseite und verfehlt "
        "das gleichzeitig verbindliche Ziel von 18,5–19,0 mm deutlich. Beide Sollwerte sind daher nicht gleichzeitig erfüllbar.\n\n"
        "## Behälter-Randentlastung\n\n"
        "Die gewünschte Entlastung von 0,25–0,40 mm ist unabhängig grundsätzlich konstruierbar, aber nicht "
        "im unveränderten 0,5-mm-Voxelraster von v004-r01: darstellbar sind dort nur 0,0 oder 0,5 mm. "
        "Eine lokale höher aufgelöste/parametrische Bearbeitung wäre erforderlich und müsste vollständig "
        "neu validiert werden. Wegen des primären Halterblockers wurde auch diese Geometrie nicht erzeugt.\n\n"
        "## Entscheidung gemäß Änderungsdisziplin\n\n"
        "Die geforderte Korrektur würde entweder Hauptkörper/Druckauflage verändern oder bei bestehendem Ablauf "
        "eine Wasserfalle erzeugen. Deshalb wurde entsprechend der ausdrücklichen STOP-Regel keine v004-r02-Geometrie gebaut.\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
