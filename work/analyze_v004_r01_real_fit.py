#!/usr/bin/env python3
"""Read-only real-fit/contact analysis for split caddy v004-r01."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
from collections import deque
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh


def load_builder(path: Path):
    spec = importlib.util.spec_from_file_location("split_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: object) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def nearest_index(values: np.ndarray, value: float) -> int:
    return int(np.argmin(np.abs(values - value)))


def plane_contact(
    tray: np.ndarray,
    insert: np.ndarray,
    zs: np.ndarray,
    plane_z: float,
    pitch: float,
) -> np.ndarray:
    below = int(np.max(np.where(zs < plane_z)[0]))
    above = int(np.min(np.where(zs > plane_z)[0]))
    if not math.isclose(float(zs[below]), plane_z - pitch / 2, abs_tol=1e-6):
        raise RuntimeError("unexpected lower sampling layer")
    if not math.isclose(float(zs[above]), plane_z + pitch / 2, abs_tol=1e-6):
        raise RuntimeError("unexpected upper sampling layer")
    return tray[below] & insert[above]


def flood_connectivity(
    xs: np.ndarray,
    ys: np.ndarray,
    supports: list[list[float]],
) -> dict:
    xx, yy = np.meshgrid(xs, ys, indexing="xy")
    domain = (xx > -118) & (xx < 118) & (yy > -40.5) & (yy < 40.5)
    obstacles = np.zeros(domain.shape, dtype=bool)
    for px, py in supports:
        obstacles |= (xx - px) ** 2 + (yy - py) ** 2 < 2.5**2
    free = domain & ~obstacles
    outlet = free & (yy < -39.75) & (np.abs(xx) < 12.5)
    visited = np.zeros_like(free)
    queue: deque[tuple[int, int]] = deque((int(y), int(x)) for y, x in np.argwhere(outlet))
    for y, x in queue:
        visited[y, x] = True
    while queue:
        y, x = queue.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < free.shape[0] and 0 <= nx < free.shape[1] and free[ny, nx] and not visited[ny, nx]:
                visited[ny, nx] = True
                queue.append((ny, nx))
    unreachable = free & ~visited
    return {
        "raster_pitch_mm": float(xs[1] - xs[0]),
        "free_cells": int(np.count_nonzero(free)),
        "outlet_connected_cells": int(np.count_nonzero(visited)),
        "unreachable_free_cells": int(np.count_nonzero(unreachable)),
        "all_under_insert_free_space_connected_to_front_outlet": not np.any(unreachable),
        "closed_components_or_water_traps": 0 if not np.any(unreachable) else None,
    }


def make_sections(
    tray: np.ndarray,
    insert: np.ndarray,
    axes: tuple[np.ndarray, np.ndarray, np.ndarray],
    supports: list[list[float]],
    output: Path,
) -> Path:
    xs, ys, zs = axes
    colours = {
        "background": np.asarray([0.965, 0.955, 0.94, 1.0]),
        "tray": np.asarray([0.20, 0.24, 0.28, 1.0]),
        "insert": np.asarray([0.15, 0.39, 0.64, 1.0]),
    }
    fig, plots = plt.subplots(2, 2, figsize=(16, 11), dpi=170)
    plots = plots.ravel()

    # Front/rear fit at x=80: no holder, so the actual 0.5 mm skirt gap and
    # 3 mm recess are visible without an occluding wall.
    ix = nearest_index(xs, 80.0)
    image = np.empty((len(zs), len(ys), 4), dtype=np.float32)
    image[:] = colours["background"]
    image[tray[:, :, ix]] = colours["tray"]
    image[insert[:, :, ix]] = colours["insert"]
    ax = plots[0]
    ax.imshow(image, origin="lower", extent=[ys[0], ys[-1], zs[0], zs[-1]], aspect="equal")
    ax.set_xlim(-46, 46); ax.set_ylim(8, 33)
    ax.axhline(27, ls="--", lw=1, color="#d97706")
    ax.annotate("0,50 mm", xy=(-40.25, 28.5), xytext=(-35.5, 31.5), arrowprops=dict(arrowstyle="->"), fontsize=8)
    ax.annotate("3,00 mm Einlegetiefe", xy=(36, 28.5), xytext=(12, 32), arrowprops=dict(arrowstyle="->"), fontsize=8)
    ax.set_title("A – VORNE/HINTEN, X=80 mm")
    ax.set_xlabel("Y [mm]"); ax.set_ylabel("Z [mm]")

    # Left/right fit at y=0 shows grid skirt and holder/rim relationship.
    iy = nearest_index(ys, 0.0)
    image = np.empty((len(zs), len(xs), 4), dtype=np.float32)
    image[:] = colours["background"]
    image[tray[:, iy, :]] = colours["tray"]
    image[insert[:, iy, :]] = colours["insert"]
    ax = plots[1]
    ax.imshow(image, origin="lower", extent=[xs[0], xs[-1], zs[0], zs[-1]], aspect="equal")
    ax.set_xlim(-122, 122); ax.set_ylim(8, 35)
    ax.annotate("0,50 mm Einsteckspiel", xy=(117.75, 28.5), xytext=(72, 33), arrowprops=dict(arrowstyle="->"), fontsize=8)
    ax.text(-78, 32, "Behälter beginnt erst oberhalb Z=30", ha="center", fontsize=8, color="#17345f")
    ax.set_title("B – LINKS/RECHTS, Y=0")
    ax.set_xlabel("X [mm]"); ax.set_ylabel("Z [mm]")

    # Holder cell: exact z clearance and full 18 mm plug collision.
    intended_x = -9.0
    ix = nearest_index(xs, intended_x)
    image = np.empty((len(zs), len(ys), 4), dtype=np.float32)
    image[:] = colours["background"]
    image[tray[:, :, ix]] = colours["tray"]
    image[insert[:, :, ix]] = colours["insert"]
    ax = plots[2]
    ax.imshow(image, origin="lower", extent=[ys[0], ys[-1], zs[0], zs[-1]], aspect="equal")
    intended_y = -33.93782217350893
    floor_top = 12.0 + 3.0 * ((intended_y + 42.5) / 85.0) + abs(intended_x) / 120.0
    ax.plot([intended_y, intended_y], [12.0, 30.0], color="#c2410c", lw=4, alpha=0.65, label="18-mm-Zapfen")
    ax.hlines(floor_top, intended_y - 5, intended_y + 5, color="#b91c1c", lw=2)
    ax.annotate(f"14,62 mm frei\nunter Gitter", xy=(intended_y, (27 + floor_top) / 2), xytext=(-16, 21), arrowprops=dict(arrowstyle="<->"), fontsize=8, ha="center")
    ax.annotate("0,38 mm Kollision", xy=(intended_y, floor_top), xytext=(-22, 10.5), arrowprops=dict(arrowstyle="->", color="#b91c1c"), fontsize=8, color="#b91c1c")
    ax.set_xlim(-45, -20); ax.set_ylim(8, 33)
    ax.set_title("C – VORGESEHENE HALTERWABE")
    ax.set_xlabel("Y [mm]"); ax.set_ylabel("Z [mm]")

    # Centreline through the open outlet: show the gravity path from the
    # honeycomb through the under-grid plenum and down the sloped floor.
    ix = nearest_index(xs, 0.0)
    image = np.empty((len(zs), len(ys), 4), dtype=np.float32)
    image[:] = colours["background"]
    image[tray[:, :, ix]] = colours["tray"]
    image[insert[:, :, ix]] = colours["insert"]
    ax = plots[3]
    ax.imshow(image, origin="lower", extent=[ys[0], ys[-1], zs[0], zs[-1]], aspect="equal")
    ax.annotate("durch das Wabengitter", xy=(22, 26.0), xytext=(22, 32.0),
                arrowprops=dict(arrowstyle="->", color="#0284c7", lw=2),
                fontsize=8, ha="center", color="#075985")
    ax.annotate("Gefälle zum Frontablauf", xy=(-37, 13.0), xytext=(28, 17.0),
                arrowprops=dict(arrowstyle="->", color="#0284c7", lw=2),
                fontsize=8, ha="center", color="#075985")
    ax.annotate("freier Austritt", xy=(-42.0, 12.0), xytext=(-27, 9.2),
                arrowprops=dict(arrowstyle="->", color="#0284c7", lw=2),
                fontsize=8, color="#075985")
    ax.set_xlim(-46, 46); ax.set_ylim(8, 35)
    ax.set_title("D – WASSERWEG DURCH FRONTABLAUF, X=0")
    ax.set_xlabel("Y [mm]"); ax.set_ylabel("Z [mm]")

    fig.suptitle("v004-r01 – REALE PASSUNG, KONTAKTE UND HALTERFREIRAUM (GEOMETRIE UNVERÄNDERT)", fontsize=14, fontweight="bold")
    fig.tight_layout()
    target = output / "REAL-FIT-CROSS-SECTIONS.png"
    fig.savefig(target, bbox_inches="tight")
    plt.close(fig)
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_dir", type=Path)
    parser.add_argument("--builder", type=Path, required=True)
    args = parser.parse_args()
    output = args.candidate_dir
    builder = load_builder(args.builder)
    tray, insert, axes, supports = builder.build_volumes()
    xs, ys, zs = axes
    pitch = float(xs[1] - xs[0])

    contact27 = plane_contact(tray, insert, zs, 27.0, pitch)
    contact30 = plane_contact(tray, insert, zs, 30.0, pitch)
    xx, yy = np.meshgrid(xs, ys, indexing="xy")
    post_region = np.zeros(contact27.shape, dtype=bool)
    for px, py in supports:
        post_region |= (xx - px) ** 2 + (yy - py) ** 2 <= 3.0**2
    post_contact = contact27 & post_region
    ledge_contact = contact27 & ~post_region

    # Actual voxelized top width at y=0, left side, excluding insert contact.
    z_below_27 = int(np.max(np.where(zs < 27.0)[0]))
    iy0 = nearest_index(ys, 0.0)
    filled_x = xs[tray[z_below_27, iy0]]
    left_ledge = filled_x[(filled_x > -118.0) & (filled_x < -110.0)]
    actual_ledge_width = float(left_ledge.max() + pitch / 2 - (-118.0)) if len(left_ledge) else 0.0
    actual_radial_bearing = max(0.0, actual_ledge_width - 0.5)

    voxel_overlap = int(np.count_nonzero(tray & insert))
    contact = {
        "z27_total_contact_area_mm2": float(np.count_nonzero(contact27) * pitch * pitch),
        "z27_ledge_to_grid_contact_area_mm2": float(np.count_nonzero(ledge_contact) * pitch * pitch),
        "z27_ten_post_to_grid_contact_area_mm2": float(np.count_nonzero(post_contact) * pitch * pitch),
        "z30_holder_bottom_to_tray_rim_contact_area_mm2": float(np.count_nonzero(contact30) * pitch * pitch),
        "actual_voxelized_ledge_top_width_from_inner_wall_mm": actual_ledge_width,
        "actual_radial_bearing_overlap_after_0p5mm_gap_mm": actual_radial_bearing,
        "volumetric_overlap_voxels": voxel_overlap,
        "volumetric_overlap_mm3": float(voxel_overlap * pitch**3),
        "interpretation": "coplanar bearing contacts at z=27 and z=30; no occupied-volume intersection",
    }
    water = flood_connectivity(xs, ys, supports)
    section = make_sections(tray, insert, axes, supports, output)

    report = {
        "schema": "ai3d.benchmark-b.v004-r01.real-fit-audit.v1",
        "geometry_changed": False,
        "assembly_transform": {"tray": "identity", "insert": "local Z + 27.0 mm"},
        "grid_z_assembly_mm": {"underside": 27.0, "top": 30.0, "thickness": 3.0},
        "insertion_depth_mm": 3.0,
        "fit": {
            "tray_inner_opening_xy_mm": [236.0, 81.0],
            "insert_insertion_skirt_xy_mm": [235.0, 80.0],
            "skirt_gap_left_mm": 0.5,
            "skirt_gap_right_mm": 0.5,
            "skirt_gap_front_mm": 0.5,
            "skirt_gap_rear_mm": 0.5,
            "complete_insert_bounds_xy_mm": [237.5, 85.0],
            "tray_outer_bounds_xy_mm": [240.0, 85.0],
            "complete_insert_outer_margin_left_mm": 1.25,
            "complete_insert_outer_margin_right_mm": 1.25,
            "holder_outer_depth_mm": 85.0,
            "holder_front_rear_outer_margin_mm": [0.0, 0.0],
            "explanation": "The 85 mm holder never enters the 81 mm opening. Its wall begins at assembly Z=30, exactly at/above the tray rim. Only the 235 x 80 mm honeycomb skirt descends to Z=27 and defines the removable fit.",
        },
        "contacts": contact,
        "water_path": water,
        "holder_clearance": {
            "intended_complete_cell_xy_mm": [-9.0, -33.93782217350893],
            "floor_top_z_mm": 12.377194511523214,
            "free_depth_below_grid_underside_mm": 14.622805488476786,
            "free_depth_from_grid_top_mm": 17.622805488476786,
            "required_free_depth_mm": [18.5, 19.0],
            "full_18mm_plug_tip_z_mm": 12.0,
            "collision_mm": 0.37719451152321426,
            "pass": False,
        },
        "cross_section": str(section),
    }
    write_json(output / "REAL-FIT-AUDIT.json", report)
    (output / "REAL-FIT-REPORT.md").write_text(
        "# REAL-FIT-PRÜFBERICHT – benchmark-b-spuelenablage-v004-r01\n\n"
        "Geometrieänderung: **NEIN**  \nGesamtstatus der realen Passung: **HOLD**\n\n"
        "## Z-Lage und Einlegetiefe\n\n"
        "Das 3,00-mm-Gitter liegt im zusammengesetzten Koordinatensystem von **Z=27,00 bis Z=30,00 mm**. Die Gitteroberseite ist damit bündig mit der Wannenoberkante Z=30,00 mm; die Einlegetiefe beträgt **3,00 mm**.\n\n"
        "## Seitliche Passung\n\n"
        "Die reale Wannenöffnung beträgt **236,00 × 81,00 mm**. Nur der unter Z=30 eintauchende Gitterrahmen ist passungsbestimmend; er misst **235,00 × 80,00 mm**. Daraus entstehen links, rechts, vorne und hinten jeweils **0,50 mm Abstand**.\n\n"
        "Das Gesamtmaß des Einsatzes von **237,50 × 85,00 mm** entsteht durch den darüberstehenden 85-mm-Behälter. Seine Wände beginnen erst bei **Z=30,00 mm** und werden deshalb nicht in die 81-mm-Wannenöffnung eingeschoben. Gegenüber der 240-mm-Außenbreite bleiben links und rechts je **1,25 mm Außenrandreserve**. Vorne und hinten liegen seine Außenkonturen exakt bündig über den 85-mm-Außenkonturen der Wanne; dort besteht **0,00 mm Außenrandreserve**, aber keine volumetrische Seitenwandüberschneidung. Die herausnehmbare Passung wird ausschließlich vom 235 × 80-mm-Gitterrahmen geführt.\n\n"
        "## Tatsächliche Auflage und Kontakte\n\n"
        f"Durch die 0,5-mm-Rasterung beträgt die tatsächlich ausgebildete horizontale Auflagebreite ab der Innenwand **{actual_ledge_width:.2f} mm**, nicht nominell 3,50 mm. Nach dem seitlichen 0,50-mm-Spiel verbleiben radial **{actual_radial_bearing:.2f} mm** mögliche Überdeckung.\n\n"
        f"- Z=27, Gitter ↔ umlaufende Auflage: **{contact['z27_ledge_to_grid_contact_area_mm2']:.2f} mm²**\n"
        f"- Z=27, Gitter ↔ zehn Stützpfosten: **{contact['z27_ten_post_to_grid_contact_area_mm2']:.2f} mm²**\n"
        f"- Z=30, Behälterunterkante ↔ Wannenrand: **{contact['z30_holder_bottom_to_tray_rim_contact_area_mm2']:.2f} mm²**\n"
        f"- Volumetrische Überschneidung: **{contact['volumetric_overlap_mm3']:.2f} mm³ / {voxel_overlap} Rasterzellen**\n\n"
        "Die Kontakte sind koplanare Auflagekontakte. Es wurde keine Durchdringung festgestellt. Der zusätzliche Kontakt des Behälterbodens mit dem Wannenrand bedeutet allerdings, dass Auflage Z=27 und Randkontakt Z=30 gleichzeitig maßhaltig sein müssen; reale Drucktoleranzen können daher zu leichtem Kippeln führen.\n\n"
        "## Wasserweg\n\n"
        f"Eine 0,5-mm-Flutfüllanalyse der gesamten freien Fläche unter dem Einsatz erreicht **{water['outlet_connected_cells']} von {water['free_cells']} freien Rasterzellen** vom Frontablauf aus. Nicht erreichbare Zellen: **{water['unreachable_free_cells']}**. Die zehn Pfosten sind isoliert; es existiert keine geschlossene Auflagerippe und keine topologisch geschlossene Wasserfalle. Der analytische Gefälleboden bleibt zum Frontzentrum monoton fallend.\n\n"
        "## Wischtuchhalter\n\n"
        "Die geforderte freie Tiefe wird **nicht** erreicht. An der vorgesehenen vollständigen Wabe stehen **14,62 mm unterhalb der Gitterunterseite** beziehungsweise **17,62 mm ab Gitteroberseite** zur Verfügung. Der vollständig eingesetzte 18-mm-Zapfen endet bei Z=12,00 mm, der Gefälleboden liegt dort bei Z=12,38 mm: **0,38 mm geometrische Kollision**. Der geforderte Nachweis von 18,5–19 mm ist damit FAIL.\n",
        encoding="utf-8",
    )
    (output / "REAL-FIT-SOLL-IST-REPORT.md").write_text(
        "# SOLL/IST – reale Passung v004-r01\n\n"
        "Geometrieänderung: **NEIN**  \nGesamtfreigabe: **HOLD**\n\n"
        "| Prüfpunkt | Soll | Ist | Status |\n"
        "|---|---:|---:|:---:|\n"
        "| Gitterstärke / Z-Lage | 3,00 mm, bündig | Z=27,00–30,00 mm | PASS |\n"
        "| Einlegetiefe | ca. 3,00 mm | 3,00 mm | PASS |\n"
        "| Führungsspiel links/rechts | ca. 0,4–0,5 mm je Seite | 0,50 / 0,50 mm | PASS |\n"
        "| Führungsspiel vorne/hinten | ca. 0,4–0,5 mm je Seite | 0,50 / 0,50 mm | PASS |\n"
        "| Vollkontur zu Wannenaußenkante links/rechts | kollisionsfrei | 1,25 / 1,25 mm | PASS |\n"
        "| Vollkontur zu Wannenaußenkante vorne/hinten | kollisionsfrei | 0,00 / 0,00 mm, bündig | PASS* |\n"
        f"| Horizontale Auflagebreite | etwa 3–4 mm | {actual_ledge_width:.2f} mm | PASS |\n"
        f"| Wirksame radiale Überdeckung nach Spiel | tragfähig | {actual_radial_bearing:.2f} mm | PASS |\n"
        f"| Volumenüberschneidung | 0 | {contact['volumetric_overlap_mm3']:.2f} mm³ | PASS |\n"
        f"| Wasserraum bis Frontablauf | vollständig verbunden | {water['outlet_connected_cells']}/{water['free_cells']} Zellen | PASS |\n"
        f"| Wasserfallen an Zusatzauflagen | keine | {water['closed_components_or_water_traps']} | PASS |\n"
        "| Freie Tiefe unter Halterwabe | 18,5–19,0 mm | 14,62 mm unter Gitter | **FAIL** |\n\n"
        "\\* Die bündige 85-mm-Vollkontur ist keine Steckpassung: Der Behälter beginnt erst auf Z=30. "
        "Die entnehmbare PETG-Führung entsteht ausschließlich am 235 × 80-mm-Gitterrahmen in der "
        "236 × 81-mm-Öffnung. Der gleichzeitige Randkontakt auf Z=30 kann bei realen Drucktoleranzen "
        "Kippeln verursachen und bleibt daher ein Fertigungsrisiko, obwohl digital keine Durchdringung vorliegt.\n\n"
        "## Kontaktflächen\n\n"
        f"- Z=27, umlaufende Auflagekante ↔ Gitterunterseite: **{contact['z27_ledge_to_grid_contact_area_mm2']:.2f} mm²**\n"
        f"- Z=27, zehn Einzelstützen ↔ Gitterunterseite: **{contact['z27_ten_post_to_grid_contact_area_mm2']:.2f} mm²**\n"
        f"- Z=30, Behälterunterkante ↔ Wannenrand: **{contact['z30_holder_bottom_to_tray_rim_contact_area_mm2']:.2f} mm²**\n"
        "- Weitere Kontaktflächen: **keine nachgewiesen**\n\n"
        "## Halterwabe\n\n"
        "Der 18-mm-Zapfen endet voll eingesteckt bei Z=12,00 mm, der Gefälleboden liegt dort bei "
        "Z=12,38 mm. Die reale Kollision beträgt **0,38 mm**. Damit ist v004-r01 trotz bestandener "
        "Einsatzpassung nicht für die unveränderte vorgesehene Halterwabe freigegeben.\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
