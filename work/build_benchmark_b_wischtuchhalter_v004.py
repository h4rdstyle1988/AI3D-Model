#!/usr/bin/env python3
"""Build v004-r01 with continuous constant-section swept rounding transitions."""

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
from matplotlib.collections import PolyCollection
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from PIL import Image, ImageDraw, ImageFont
from skimage.measure import marching_cubes

import build_benchmark_b_spuelenablage_v003 as common


CANDIDATE = "benchmark-b-wischtuchhalter-v004-r02"
SOURCE_CADDY = "benchmark-b-spuelenablage-v003-r03"
RESOLUTION_MM = 0.10
HEX_FLAT_MM = 8.90
HEX_APOTHEM_MM = HEX_FLAT_MM / 2.0
HEX_CORNER_MM = 2.0 * HEX_FLAT_MM / math.sqrt(3.0)
OPENING_FLAT_MM = 9.32435565
OPENING_CORNER_MM = 10.766752
PLUG_LENGTH_MM = 18.0
RAIL_PROJECTION_MM = 90.0
STOP_LENGTH_MM = 8.0
RAIL_WIDTH_MM = 10.0
RAIL_HEIGHT_MM = 8.0
TOUCH_RADIUS_MM = 2.0
TRANSITION_INNER_RADIUS_MM = 6.0
STOP_TRANSITION_RADIUS_MM = 4.0
STOP_RISE_MM = 8.0
VERTICAL_EXTENSION_MM = 50.0

# The original pointy-X honeycomb maps to the accessory's pointy-Y plug when
# local +X is installed toward global -Y (the sink/front direction).
INSTALL_CELL_X_MM = -9.5
INSTALL_CELL_Y_MM = -34.4378221735
VISUAL_INSERTION_DEPTH_MM = 10.0


PARAMETERS = {
    "candidate": CANDIDATE,
    "revision": "B-WISCHTUCH-2026-08-27.4.2",
    "material": "PETG",
    "compatible_caddy": SOURCE_CADDY,
    "honeycomb": {
        "cell_side_on_centreline_mm": 7.0,
        "strut_width_mm": 2.8,
        "grid_thickness_z_mm": 3.0,
        "measured_free_opening_flat_to_flat_mm": OPENING_FLAT_MM,
        "measured_free_opening_corner_to_corner_mm": OPENING_CORNER_MM,
    },
    "plug": {
        "shape": "straight regular hexagonal prism",
        "flat_to_flat_mm": HEX_FLAT_MM,
        "corner_to_corner_mm": HEX_CORNER_MM,
        "constant_straight_length_mm": PLUG_LENGTH_MM,
        "taper": False,
        "ribs_barbs_detents_springs": False,
        "orientation": "pointy-Y locally; maps to original pointy-X honeycomb when rail local +X points to global -Y",
    },
    "rail": {
        "vertical_extension_above_plug_mm": VERTICAL_EXTENSION_MM,
        "full_seated_rail_underside_above_grid_mm": 56.0,
        "full_seated_rail_centre_above_grid_mm": 60.0,
        "free_projection_to_stop_start_mm": RAIL_PROJECTION_MM,
        "section_width_mm": RAIL_WIDTH_MM,
        "section_height_mm": RAIL_HEIGHT_MM,
        "touchable_outer_edge_radius_mm": TOUCH_RADIUS_MM,
        "transition_inner_radius_mm": TRANSITION_INNER_RADIUS_MM,
        "stop_length_mm": STOP_LENGTH_MM,
        "stop_rise_above_rail_mm": STOP_RISE_MM,
        "stop_transition_radius_mm": STOP_TRANSITION_RADIUS_MM,
        "stop_upper_edge_radius_mm": TOUCH_RADIUS_MM,
        "rounding_form": "continuous constant-section swept profile; tangent main R6 bend and tangent R4 end rise",
        "local_rounding_thickening": False,
    },
    "installation_preview": {
        "original_cell_centre_global_xy_mm": [INSTALL_CELL_X_MM, INSTALL_CELL_Y_MM],
        "insertion_depth_mm": VISUAL_INSERTION_DEPTH_MM,
        "rail_direction_global": "-Y, front/toward sink",
    },
    "generation": {
        "method": "one binary implicit solid plus one Lewiner marching-cubes extraction",
        "resolution_mm": RESOLUTION_MM,
        "smoothing": False,
        "shape_changing_repair": False,
    },
    "print": {
        "material": "PETG",
        "nozzle_mm": 0.4,
        "layer_height_mm": [0.20, 0.24],
        "preferred_orientation": "side lying, local Y mapped to printer Z",
        "supports": "disabled; continuous profile is intended to print on its side without support",
        "brim": "disabled; the side orientation provides the long bed-contact contour",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def axis_centres(lo: float, hi: float) -> np.ndarray:
    return np.arange(lo - RESOLUTION_MM / 2.0, hi + RESOLUTION_MM / 2.0 + 1e-9, RESOLUTION_MM, dtype=np.float32)


def rounded_rect_2d(a: np.ndarray, b: np.ndarray, half_a: float, half_b: float, radius: float) -> np.ndarray:
    qa = np.abs(a) - (half_a - radius)
    qb = np.abs(b) - (half_b - radius)
    distance = np.hypot(np.maximum(qa, 0.0), np.maximum(qb, 0.0)) + np.minimum(np.maximum(qa, qb), 0.0) - radius
    return distance <= 0.0


def rounded_box(x: np.ndarray, y: np.ndarray, z: np.ndarray, centre: tuple[float, float, float], size: tuple[float, float, float], radius: float) -> np.ndarray:
    cx, cy, cz = centre
    hx, hy, hz = (value / 2.0 for value in size)
    qx = np.abs(x - cx) - (hx - radius)
    qy = np.abs(y - cy) - (hy - radius)
    qz = np.abs(z - cz) - (hz - radius)
    outside = np.sqrt(np.maximum(qx, 0.0) ** 2 + np.maximum(qy, 0.0) ** 2 + np.maximum(qz, 0.0) ** 2)
    inside = np.minimum(np.maximum(np.maximum(qx, qy), qz), 0.0)
    return outside + inside - radius <= 0.0


def build_volume() -> tuple[np.ndarray, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    xs = axis_centres(-6.0, 99.0)
    ys = axis_centres(-6.0, 6.0)
    zs = axis_centres(-1.0, 91.0)
    x = xs[None, None, :]
    y = ys[None, :, None]
    z = zs[:, None, None]

    # Exact constant pointy-Y regular hexagonal prism, z=0..18 mm.
    plug_xy = (np.abs(x) <= HEX_APOTHEM_MM) & (
        math.sqrt(3.0) * np.abs(y) + np.abs(x) <= 2.0 * HEX_APOTHEM_MM
    )
    solid = plug_xy & (z >= 0.0) & (z <= PLUG_LENGTH_MM)

    # The new revision adds exactly 50 mm of straight vertical structure
    # above the unchanged 18-mm plug.  It has the same robust rounded
    # 10 x 8 mm section as the rail transition.
    vertical_cross = rounded_rect_2d(x, y, RAIL_HEIGHT_MM / 2.0, RAIL_WIDTH_MM / 2.0, TOUCH_RADIUS_MM)
    solid |= vertical_cross & (z >= PLUG_LENGTH_MM) & (z <= PLUG_LENGTH_MM + VERTICAL_EXTENSION_MM)

    # 90-degree transition.  Centreline radius 10 mm minus the 4-mm half
    # beam height gives the prescribed R6 inner radius.  It is clipped at
    # z=68 so the complete plug and the new 50-mm straight remain unmodified.
    bend_cx, bend_cz, centreline_radius = 10.0, PLUG_LENGTH_MM + VERTICAL_EXTENSION_MM, 10.0
    dx = x - bend_cx
    dz = z - bend_cz
    rho = np.sqrt(dx * dx + dz * dz)
    theta = np.arctan2(dz, dx)
    bend_cross = rounded_rect_2d(rho - centreline_radius, y, RAIL_HEIGHT_MM / 2.0, RAIL_WIDTH_MM / 2.0, TOUCH_RADIUS_MM)
    bend = bend_cross & (theta >= math.pi / 2.0) & (theta <= math.pi) & (z >= PLUG_LENGTH_MM + VERTICAL_EXTENSION_MM)
    solid |= bend

    # Main straight rail: the main bend ends tangentially at x=10.  The rail
    # stays a constant 10 x 8 mm profile until the R4 end transition begins
    # four millimetres before the nominal x=90 stop datum.
    rail_cross = rounded_rect_2d(y, z - 78.0, RAIL_WIDTH_MM / 2.0, RAIL_HEIGHT_MM / 2.0, TOUCH_RADIUS_MM)
    solid |= rail_cross & (x >= 10.0) & (x <= 86.0)

    # The end stop is no longer a block plus filler.  It is one constant
    # profile swept through a tangent quarter bend: centreline R8 minus the
    # 4-mm half-height gives the specified R4 inner radius.  The inner face
    # reaches the unchanged x=90 stop datum; the outer face remains at x=98.
    end_cx, end_cz, end_centreline_radius = 86.0, 86.0, 8.0
    end_dx = x - end_cx
    end_dz = z - end_cz
    end_rho = np.sqrt(end_dx * end_dx + end_dz * end_dz)
    end_theta = np.arctan2(end_dz, end_dx)
    end_cross = rounded_rect_2d(end_rho - end_centreline_radius, y, RAIL_HEIGHT_MM / 2.0, RAIL_WIDTH_MM / 2.0, TOUCH_RADIUS_MM)
    solid |= end_cross & (end_theta >= -math.pi / 2.0) & (end_theta <= 0.0)

    # A short, constant-envelope vertical end cap completes the 8-mm rise.
    # The R2 rounded box stays entirely inside the 10 x 8 profile envelope,
    # so it creates no visible local thickening or shoulder.
    solid |= rounded_box(x, y, z, (94.0, 0.0, 87.0), (8.0, 10.0, 6.0), TOUCH_RADIUS_MM)
    return np.asarray(solid, dtype=bool), (xs, ys, zs)


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


def pointy_y_hex(points: np.ndarray, apothem: float) -> np.ndarray:
    return (np.abs(points[:, 0]) <= apothem + 1e-9) & (
        math.sqrt(3.0) * np.abs(points[:, 1]) + np.abs(points[:, 0]) <= 2.0 * apothem + 1e-9
    )


def analytic_fit() -> dict:
    angles = np.linspace(0.0, 2.0 * math.pi, 721)
    # Sample all six plug edges, not only its corners.
    corner_radius = HEX_CORNER_MM / 2.0
    vertices = np.asarray([[corner_radius * math.sin(math.radians(60 * k)), corner_radius * math.cos(math.radians(60 * k))] for k in range(6)])
    samples = []
    for a, b in zip(vertices, np.roll(vertices, -1, axis=0)):
        for t in np.linspace(0.0, 1.0, 201):
            samples.append(a * (1.0 - t) + b * t)
    samples = np.asarray(samples)
    inside = pointy_y_hex(samples, OPENING_FLAT_MM / 2.0)
    return {
        "plug_flat_to_flat_mm": HEX_FLAT_MM,
        "plug_corner_to_corner_mm": HEX_CORNER_MM,
        "opening_flat_to_flat_mm": OPENING_FLAT_MM,
        "opening_corner_to_corner_mm": OPENING_CORNER_MM,
        "total_flat_clearance_mm": OPENING_FLAT_MM - HEX_FLAT_MM,
        "clearance_per_opposing_face_mm": (OPENING_FLAT_MM - HEX_FLAT_MM) / 2.0,
        "total_corner_clearance_mm": OPENING_CORNER_MM - HEX_CORNER_MM,
        "all_1206_boundary_samples_inside_opening": bool(inside.all()),
        "orientation_matches_original_honeycomb": True,
        "anti_rotation_by_matching_hexagons": True,
        "pass": bool(inside.all()),
    }


def installation_transform(insertion_depth: float) -> np.ndarray:
    # global X = cell X + local Y; global Y = cell Y - local X;
    # local plug top z=18 sits insertion_depth above/below global grid top z=30.
    transform = np.eye(4)
    transform[:3, :3] = np.asarray([[0.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    transform[:3, 3] = [INSTALL_CELL_X_MM, INSTALL_CELL_Y_MM, 30.0 - (PLUG_LENGTH_MM - insertion_depth)]
    return transform


def crop_original_caddy(caddy: trimesh.Trimesh) -> trimesh.Trimesh:
    centres = np.asarray(caddy.triangles_center)
    keep = (
        (centres[:, 0] >= -32.0) & (centres[:, 0] <= 18.0)
        & (centres[:, 1] >= -44.0) & (centres[:, 1] <= -10.0)
        & (centres[:, 2] >= 8.0) & (centres[:, 2] <= 31.0)
    )
    return caddy.submesh([keep], append=True, repair=False)


def render_installed(holder: trimesh.Trimesh, caddy_path: Path, output: Path) -> tuple[Path, Path]:
    caddy = trimesh.load_mesh(caddy_path, process=False)
    patch = crop_original_caddy(caddy)
    installed = holder.copy()
    installed.apply_transform(installation_transform(VISUAL_INSERTION_DEPTH_MM))
    scene = trimesh.Scene()
    patch.visual.face_colors = [80, 88, 96, 255]
    installed.visual.face_colors = [230, 151, 45, 255]
    scene.add_geometry(patch, node_name="original-caddy-v003-r03-crop")
    scene.add_geometry(installed, node_name="wischtuchhalter-v004-r02")
    glb_path = output / "installed-in-original-caddy-preview.glb"
    scene.export(glb_path)

    png_path = output / "installed-in-original-caddy-preview.png"
    combined = trimesh.util.concatenate([patch, installed])
    common._render_mesh(combined, png_path, 24.0, -48.0, "IN ORIGINALWABE – 10 mm EINGESTECKT – RICHTUNG SPÜLE")
    return png_path, glb_path


def make_fit_diagram(output: Path, fit: dict) -> Path:
    opening_a = OPENING_FLAT_MM / 2.0
    opening_r = OPENING_CORNER_MM / 2.0
    plug_r = HEX_CORNER_MM / 2.0
    opening = np.asarray([[opening_r * math.sin(math.radians(60 * k)), opening_r * math.cos(math.radians(60 * k))] for k in range(7)])
    plug = np.asarray([[plug_r * math.sin(math.radians(60 * k)), plug_r * math.cos(math.radians(60 * k))] for k in range(7)])
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), dpi=170)
    axes[0].fill(opening[:, 0], opening[:, 1], color="#3e4852", alpha=0.35, label="freie Originalwabe")
    axes[0].plot(opening[:, 0], opening[:, 1], color="#28313a", lw=3)
    axes[0].fill(plug[:, 0], plug[:, 1], color="#e3982e", alpha=0.9, label="8,90-mm-Steckzapfen")
    axes[0].set_aspect("equal"); axes[0].set_xlim(-6, 6); axes[0].set_ylim(-6, 6); axes[0].axis("off")
    axes[0].set_title("ORIENTIERUNG UND PASSUNG", fontweight="bold")
    axes[0].legend(loc="lower center")
    axes[1].axis("off")
    axes[1].text(0.0, 0.85, "RECHNERISCHER NACHWEIS", fontsize=15, fontweight="bold", color="#17345f")
    axes[1].text(0.0, 0.66, f"Wabe Flachweite: {OPENING_FLAT_MM:.3f} mm")
    axes[1].text(0.0, 0.55, f"Zapfen Flachweite: {HEX_FLAT_MM:.2f} mm")
    axes[1].text(0.0, 0.44, f"Spiel gesamt: {fit['total_flat_clearance_mm']:.3f} mm")
    axes[1].text(0.0, 0.33, f"Spiel je Fläche: {fit['clearance_per_opposing_face_mm']:.3f} mm")
    axes[1].text(0.0, 0.22, "Profil über 18,0 mm konstant; keine Konizität")
    path = output / "hex-fit-and-orientation-diagram.png"
    fig.tight_layout(); fig.savefig(path, bbox_inches="tight", facecolor="#f4f2ef"); plt.close(fig)
    return path


def make_contact_sheet(paths: list[tuple[Path, str]], output: Path) -> Path:
    canvas = Image.new("RGB", (1800, 1200), "#f4f2ef")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    slots = [(20, 35, 860, 540), (920, 35, 860, 540), (20, 620, 860, 540), (920, 620, 860, 540)]
    for (path, title), (x, y, w, h) in zip(paths, slots):
        image = Image.open(path).convert("RGB")
        image.thumbnail((w, h - 32), Image.Resampling.LANCZOS)
        canvas.paste(image, (x + (w - image.width) // 2, y + 28 + (h - 32 - image.height) // 2))
        draw.text((x + 8, y + 6), title, fill="#17345f", font=font)
    result = output / "contact-sheet.png"
    canvas.save(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--caddy-stl", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty output: {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if not args.caddy_stl.is_file():
        raise SystemExit(f"Missing source caddy STL: {args.caddy_stl}")

    mesh = extract_mesh(*build_volume())
    topo = common.topology(mesh)
    fit = analytic_fit()
    if not (topo["components"] == 1 and topo["watertight"] and topo["winding_consistent"] and topo["is_volume"] and fit["pass"]):
        raise RuntimeError({"topology": topo, "fit": fit})

    stl = args.output_dir / f"{CANDIDATE}.stl"
    three_mf = args.output_dir / f"{CANDIDATE}.3mf"
    glb = args.output_dir / f"{CANDIDATE}.glb"
    mesh.export(stl); mesh.export(glb)
    common.CANDIDATE = CANDIDATE
    common.export_3mf(mesh, three_mf)

    renders = []
    for name, elev, azim, title in (
        ("front", 4, -90, "FRONT"), ("top", 90, -90, "OBEN"),
        ("side", 4, 0, "SEITE"), ("perspective", 24, -58, "PERSPEKTIVE")
    ):
        path = args.output_dir / f"render-{name}.png"
        common._render_mesh(mesh, path, elev, azim, title)
        renders.append(path)
    profile_side = args.output_dir / "render-seitenansicht-profil.png"
    common._render_mesh(mesh, profile_side, 4, -90, "SEITENANSICHT – DURCHGEHENDE PROFILKONTUR")
    review = Image.new("RGB", (2000, 820), "#f4f2ef")
    review_draw = ImageDraw.Draw(review)
    for index, (source, title) in enumerate(((profile_side, "SEITENANSICHT"), (renders[3], "PERSPEKTIVANSICHT"))):
        picture = Image.open(source).convert("RGB")
        picture.thumbnail((960, 750), Image.Resampling.LANCZOS)
        x0 = 20 + index * 1000
        review.paste(picture, (x0 + (960 - picture.width) // 2, 55 + (750 - picture.height) // 2))
        review_draw.text((x0 + 8, 18), title, fill="#17345f", font=ImageFont.load_default())
    review.save(args.output_dir / "rounding-review-side-and-perspective.png")
    installed_png, installed_glb = render_installed(mesh, args.caddy_stl, args.output_dir)
    fit_diagram = make_fit_diagram(args.output_dir, fit)
    make_contact_sheet(
        [(renders[3], "PERSPEKTIVE"), (renders[2], "SEITENANSICHT"),
         (installed_png, "IN ORIGINALWABE – RICHTUNG SPÜLE"), (fit_diagram, "PASSUNG")],
        args.output_dir,
    )

    PARAMS = dict(PARAMETERS)
    PARAMS["source_caddy_stl"] = {"path": str(args.caddy_stl), "sha256": sha256(args.caddy_stl)}
    (args.output_dir / "design-parameters.json").write_text(json.dumps(PARAMS, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    preflight = {
        "candidate": CANDIDATE,
        "status": "PASS",
        "shape_changing_repair": False,
        "topology": topo,
        "fit": fit,
        "source_caddy_sha256": PARAMS["source_caddy_stl"]["sha256"],
        "artifacts": {"stl_sha256": sha256(stl), "3mf_sha256": sha256(three_mf), "glb_sha256": sha256(glb), "installed_preview_glb_sha256": sha256(installed_glb)},
    }
    (args.output_dir / "technical-validation-preflight.json").write_text(json.dumps(preflight, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"candidate": CANDIDATE, "topology": topo, "fit": fit, "output": str(args.output_dir)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
