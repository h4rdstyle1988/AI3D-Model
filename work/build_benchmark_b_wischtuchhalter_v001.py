#!/usr/bin/env python3
"""Build a separate PETG twist-lock cloth rail for the v003-r03 honeycomb."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont
from skimage.measure import marching_cubes

import build_benchmark_b_spuelenablage_v003 as common


CANDIDATE = "benchmark-b-wischtuchhalter-v001-r01"
RESOLUTION_MM = 0.25
OPENING_FLAT_MM = 9.32435565
OPENING_CORNER_MM = 10.766752

PARAMETERS = {
    "candidate": CANDIDATE,
    "material": "PETG",
    "compatible_caddy": "benchmark-b-spuelenablage-v003-r03",
    "compatible_honeycomb": {
        "nominal_inner_flat_to_flat_mm": OPENING_FLAT_MM,
        "nominal_inner_corner_to_corner_mm": OPENING_CORNER_MM,
        "grid_thickness_mm": 3.0,
    },
    "twist_lock": {
        "retaining_bar_overall_length_mm": 10.25,
        "retaining_bar_width_mm": 3.0,
        "retaining_bar_thickness_mm": 1.75,
        "shaft_diameter_mm": 4.0,
        "insertion_orientation": "bar aligned vertex-to-vertex with honeycomb",
        "locking_rotation_degrees": 30.0,
        "seating": "45-degree expanding cone contacts honeycomb rim at about z=4.8 mm",
    },
    "cloth_rail": {
        "rail_outer_length_mm": 120.0,
        "installed_height_above_grid_mm": 45.0,
        "rail_section_diameter_mm": 8.0,
        "downturned_end_stop_mm": 12.0,
        "usable_hanging_span_mm": 100.0,
        "direction": "toward sink after the 30-degree locking turn",
        "top_load_spreader_mm": [24.0, 18.0, 2.0],
    },
    "generation": {"resolution_mm": RESOLUTION_MM, "method": "binary solid field plus one Lewiner marching-cubes extraction", "smoothing": False},
    "print": {"nozzle_mm": 0.4, "layer_mm": 0.2, "preferred_orientation": "on its side", "supports_expected": "small support may be required only below the twist-lock base"},
}


def axis_centres(lo: float, hi: float) -> np.ndarray:
    return np.arange(lo - RESOLUTION_MM / 2.0, hi + RESOLUTION_MM / 2.0 + 1e-9, RESOLUTION_MM, dtype=np.float32)


def capsule_distance(x: np.ndarray, y: np.ndarray, z: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    ab = b - a
    denominator = float(ab @ ab)
    t = np.clip(((x - a[0]) * ab[0] + (y - a[1]) * ab[1] + (z - a[2]) * ab[2]) / denominator, 0.0, 1.0)
    dx = x - (a[0] + t * ab[0])
    dy = y - (a[1] + t * ab[1])
    dz = z - (a[2] + t * ab[2])
    return np.sqrt(dx * dx + dy * dy + dz * dz)


def build_volume() -> tuple[np.ndarray, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    xs = axis_centres(-14.0, 120.0)
    ys = axis_centres(-11.0, 11.0)
    zs = axis_centres(-1.0, 52.0)
    zz, yy, xx = np.meshgrid(zs, ys, xs, indexing="ij")
    solid = np.zeros(xx.shape, dtype=bool)

    # Rounded insertion/retaining bar: 10.25 x 3.0 x 1.75 mm.
    half_segment = (10.25 - 3.0) / 2.0
    dx = np.maximum(np.abs(xx) - half_segment, 0.0)
    bar_xy = dx * dx + yy * yy < (1.5 * 1.5)
    solid |= bar_xy & (zz > 0.0) & (zz < 1.75)

    # Circular shaft through the honeycomb.
    radius_xy = np.sqrt(xx * xx + yy * yy)
    solid |= (radius_xy < 2.0) & (zz > 0.75) & (zz < 7.8)

    # Self-centring printable cone.  At the 4.66 mm opening apothem its
    # underside is z~=4.8 mm, leaving the exact 3.0 mm grid gap above the bar.
    cone_radius = 2.0 + np.clip((zz - 3.2) / 3.0, 0.0, 1.0) * 5.0
    solid |= (zz > 3.2) & (zz < 6.2) & (radius_xy < cone_radius)
    solid |= (zz > 6.2) & (zz < 8.2) & (radius_xy < 7.0)

    # A broad top pad distributes cantilever torque over several grid struts;
    # it is not a second foot or anchor.
    qx = np.maximum(np.abs(xx - 8.0) - 9.0, 0.0)
    qy = np.maximum(np.abs(yy) - 6.0, 0.0)
    rounded_pad = (np.abs(xx - 8.0) < 12.0) & (np.abs(yy) < 9.0) & (qx * qx + qy * qy < 9.0)
    solid |= rounded_pad & (zz > 6.2) & (zz < 8.2)

    # Reference-inspired 120 mm rail, 45 mm above the grid, with a 12 mm
    # downturned end that prevents the cloth from sliding off.
    rail_z = 45.8  # top 49.8 minus grid contact 4.8 = 45.0 mm installed
    riser_a = np.asarray([0.0, 0.0, 8.0], dtype=np.float32)
    riser_b = np.asarray([0.0, 0.0, rail_z], dtype=np.float32)
    rail_a = np.asarray([0.0, 0.0, rail_z], dtype=np.float32)
    rail_b = np.asarray([112.0, 0.0, rail_z], dtype=np.float32)
    stop_a = np.asarray([112.0, 0.0, rail_z], dtype=np.float32)
    stop_b = np.asarray([112.0, 0.0, rail_z - 12.0], dtype=np.float32)
    solid |= capsule_distance(xx, yy, zz, riser_a, riser_b) < 4.0
    solid |= capsule_distance(xx, yy, zz, rail_a, rail_b) < 4.0
    solid |= capsule_distance(xx, yy, zz, stop_a, stop_b) < 4.0
    return solid, (xs, ys, zs)


def extract_mesh(volume: np.ndarray, axes: tuple[np.ndarray, np.ndarray, np.ndarray]) -> trimesh.Trimesh:
    xs, ys, zs = axes
    vertices_zyx, faces, _normals, _values = marching_cubes(
        volume.astype(np.float32), level=0.5, spacing=(RESOLUTION_MM,) * 3, allow_degenerate=False
    )
    vertices = np.column_stack(
        [vertices_zyx[:, 2] + float(xs[0]), vertices_zyx[:, 1] + float(ys[0]), vertices_zyx[:, 0] + float(zs[0])]
    )
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=True, validate=True)
    mesh.remove_unreferenced_vertices()
    trimesh.repair.fix_normals(mesh, multibody=True)
    return mesh


def regular_hex_contains(points: np.ndarray, angle_deg: float) -> np.ndarray:
    angle = math.radians(-angle_deg)
    rotation = np.asarray([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
    transformed = points @ rotation.T
    apothem = OPENING_FLAT_MM / 2.0
    return (np.abs(transformed[:, 1]) <= apothem + 1e-9) & (
        math.sqrt(3.0) * np.abs(transformed[:, 0]) + np.abs(transformed[:, 1]) <= 2.0 * apothem + 1e-9
    )


def bar_boundary_samples() -> np.ndarray:
    radius = 1.5
    half_segment = (10.25 - 3.0) / 2.0
    samples = []
    for centre, start, end in ((half_segment, -90.0, 90.0), (-half_segment, 90.0, 270.0)):
        for angle in np.linspace(start, end, 181):
            samples.append([centre + radius * math.cos(math.radians(angle)), radius * math.sin(math.radians(angle))])
    return np.asarray(samples)


def fit_validation() -> dict:
    boundary = bar_boundary_samples()
    inserted = regular_hex_contains(boundary, 0.0)
    locked = regular_hex_contains(boundary, 30.0)
    apothem = OPENING_FLAT_MM / 2.0
    cone_contact_z = 3.2 + (apothem - 2.0) * (3.0 / 5.0)
    return {
        "bar_fits_at_insertion_orientation": bool(inserted.all()),
        "minimum_insertion_margin_to_corner_mm": float((OPENING_CORNER_MM - 10.25) / 2.0),
        "bar_blocked_after_30_degree_rotation": bool(not locked.all()),
        "boundary_samples_outside_after_rotation": int(np.count_nonzero(~locked)),
        "nominal_flatwise_lock_overlap_each_side_mm": float((10.25 - OPENING_FLAT_MM) / 2.0),
        "cone_contact_z_mm": float(cone_contact_z),
        "retaining_bar_top_z_mm": 1.75,
        "effective_grid_capture_gap_mm": float(cone_contact_z - 1.75),
        "target_grid_thickness_mm": 3.0,
        "pass": bool(inserted.all() and not locked.all() and abs((cone_contact_z - 1.75) - 3.0) <= 0.1),
    }


def make_installation_diagram(output: Path, fit: dict) -> Path:
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), dpi=150)
    apothem = OPENING_FLAT_MM / 2.0
    radius = apothem / math.cos(math.radians(30.0))
    hexagon = np.asarray([[radius * math.cos(math.radians(60 * k)), radius * math.sin(math.radians(60 * k))] for k in range(7)])
    bar = bar_boundary_samples()
    for ax, rotation, title in ((axes[0], 0.0, "1  EINSTECKEN"), (axes[1], 30.0, "2  30° DREHEN")):
        angle = math.radians(rotation)
        matrix = np.asarray([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
        rotated = bar @ matrix.T
        ax.plot(hexagon[:, 0], hexagon[:, 1], color="#2e3740", lw=6)
        ax.fill(rotated[:, 0], rotated[:, 1], color="#e39b2e", alpha=0.9)
        ax.set_aspect("equal"); ax.set_xlim(-7, 7); ax.set_ylim(-7, 7); ax.axis("off"); ax.set_title(title, fontweight="bold")
    axes[2].axis("off")
    axes[2].text(0.0, 0.82, "PASSFORM", fontsize=15, fontweight="bold", color="#17345f")
    axes[2].text(0.0, 0.64, f"Wabe innen: {OPENING_FLAT_MM:.2f} / {OPENING_CORNER_MM:.2f} mm")
    axes[2].text(0.0, 0.52, "Riegel: 10,25 × 3,00 × 1,75 mm")
    axes[2].text(0.0, 0.40, f"Einsteckspiel diagonal: {2*fit['minimum_insertion_margin_to_corner_mm']:.2f} mm")
    axes[2].text(0.0, 0.28, f"Verriegelungsübergriff: {fit['nominal_flatwise_lock_overlap_each_side_mm']:.2f} mm je Seite")
    axes[2].text(0.0, 0.16, f"Gitteraufnahme: {fit['effective_grid_capture_gap_mm']:.2f} mm für 3,0-mm-Gitter")
    path = output / "installation-and-fit-diagram.png"
    fig.tight_layout(); fig.savefig(path, bbox_inches="tight"); plt.close(fig)
    return path


def make_contact_sheet(renders: list[Path], diagram: Path, output: Path) -> Path:
    canvas = Image.new("RGB", (1800, 1200), "#f4f2ef")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    items = [(renders[3], "PERSPEKTIVE"), (renders[0], "FRONT"), (renders[1], "OBEN"), (diagram, "EINSTECKEN UND 30° VERRIEGELN")]
    slots = [(20, 35, 860, 540), (920, 35, 860, 540), (20, 620, 860, 540), (920, 620, 860, 540)]
    for (path, label), (x, y, w, h) in zip(items, slots):
        image = Image.open(path).convert("RGB")
        image.thumbnail((w, h - 30), Image.Resampling.LANCZOS)
        canvas.paste(image, (x + (w - image.width) // 2, y + 25 + (h - 30 - image.height) // 2))
        draw.text((x + 8, y + 5), label, fill="#17345f", font=font)
    path = output / "contact-sheet.png"
    canvas.save(path)
    return path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty output: {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    mesh = extract_mesh(*build_volume())
    topo = common.topology(mesh)
    fit = fit_validation()
    if not (topo["components"] == 1 and topo["watertight"] and topo["winding_consistent"] and topo["is_volume"] and fit["pass"]):
        raise RuntimeError({"topology": topo, "fit": fit})
    stl = args.output_dir / f"{CANDIDATE}.stl"
    glb = args.output_dir / f"{CANDIDATE}.glb"
    three_mf = args.output_dir / f"{CANDIDATE}.3mf"
    mesh.export(stl); mesh.export(glb)
    common.CANDIDATE = CANDIDATE
    common.export_3mf(mesh, three_mf)
    views = []
    for name, elev, azim, title in (("front", 4, -90, "FRONT"), ("top", 90, -90, "OBEN"), ("right", 4, 0, "RECHTS"), ("perspective", 24, -58, "PERSPEKTIVE")):
        path = args.output_dir / f"render-{name}.png"
        common._render_mesh(mesh, path, elev, azim, title)
        views.append(path)
    diagram = make_installation_diagram(args.output_dir, fit)
    make_contact_sheet(views, diagram, args.output_dir)
    (args.output_dir / "design-parameters.json").write_text(json.dumps(PARAMETERS, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = {"candidate": CANDIDATE, "status": "PASS", "topology": topo, "fit": fit, "stl_sha256": sha256(stl), "shape_changing_repair": False}
    (args.output_dir / "technical-validation-preflight.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.output_dir / "FIT-AND-USE-REPORT.md").write_text(
        f"# Passform und Verwendung – {CANDIDATE}\n\n"
        "1. Den 10,25-mm-Riegel in Richtung zweier gegenüberliegender Wabenecken ausrichten.\n"
        "2. Bis zum Konus durch die Wabe drücken.\n"
        "3. Den gesamten Bügel um 30° in Richtung Spüle drehen. Der Riegel übergreift dann die Flachweite der Wabe.\n"
        "4. Zum Entfernen 30° zurückdrehen und herausziehen.\n\n"
        f"Einsteckspiel zur Wabendiagonale: {2*fit['minimum_insertion_margin_to_corner_mm']:.2f} mm. "
        f"Übergriff nach Drehung: {fit['nominal_flatwise_lock_overlap_each_side_mm']:.2f} mm je Seite. "
        f"Aufnahmehöhe: {fit['effective_grid_capture_gap_mm']:.2f} mm für das 3,0-mm-Gitter.\n\n"
        "Dies ist eine rechnerische Passform. Vor Dauerbelastung mit einem nassen Lappen wird ein einzelner PETG-Testdruck empfohlen.\n",
        encoding="utf-8",
    )
    print(json.dumps({"candidate": CANDIDATE, "topology": topo, "fit": fit}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
