#!/usr/bin/env python3
"""Build the 240 x 85 mm sink-tray specification as a separate FDM candidate.

The geometry is generated as a deterministic 0.5 mm cell-centred solid field
and converted once with marching cubes.  This gives a single closed boundary
without relying on Blender booleans or automatic mesh repair.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import moderngl
import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont
from skimage.measure import marching_cubes


CANDIDATE = "benchmark-b-spuelenablage-v003-r03"
REVISION = "B-2026-08-27.3"
RESOLUTION_MM = 0.5

PARAMETERS = {
    "candidate": CANDIDATE,
    "revision": REVISION,
    "reference_image": "Ablage_Spuele.png",
    "main_body_mm": {"width": 240.0, "depth": 85.0, "height": 20.0},
    "rear_foot_mm": {"width": 240.0, "depth": 35.0, "height": 10.0},
    "base_total_height_including_foot_mm": 30.0,
    "brush_holder_mm": {"width": 85.0, "depth": 85.0, "height_above_main": 100.0},
    "brush_holder": {"open_top": True, "open_grid_bottom": True, "wall_mm": 2.0, "front_and_side_walls_closed": True},
    "porcelain_part": {
        "printed_holder_or_guide": False,
        "placement": "free and loose directly on the uninterrupted honeycomb grid",
        "part_of_print_mesh": False,
    },
    "grid": {
        "pattern": "regular hexagonal honeycomb",
        "cell_side_mm": 7.0,
        "strut_width_mm": 2.8,
        "thickness_mm": 3.0,
        "water_openings": True,
    },
    "drain": {
        "location": "front centre",
        "taper_height_mm": 8.0,
        "opening_width_bottom_mm": 25.0,
        "opening_width_top_mm": 12.0,
        "top_open": True,
        "short_chute_projection_mm": 12.5,
        "chute_outer_width_mm": 31.0,
        "catch_floor_top_formula_mm": "12.0 + 3.0*((y+42.5)/85.0) + 1.0*abs(x)/120.0",
        "catch_floor_top_front_centre_mm": 12.0,
        "catch_floor_top_rear_centre_mm": 15.0,
        "catch_floor_top_front_outer_edge_mm": 13.0,
        "catch_floor_top_rear_outer_edge_mm": 16.0,
        "catch_floor_material_thickness_mm": 2.0,
        "chute_floor_start_mm": 12.0,
        "chute_floor_free_end_mm": 10.0,
    },
    "generation": {
        "method": "cell-centred binary CSG followed by one marching-cubes extraction",
        "resolution_mm": RESOLUTION_MM,
        "smoothing": False,
        "shape_changing_repair": False,
    },
    "material": "PETG",
    "normal_wall_thickness_mm": 2.0,
    "documented_functional_exceptions_mm": {"honeycomb_strut_width": 2.8, "honeycomb_thickness": 3.0, "drain_side_walls": "variable tapered functional section"},
    "fdm_assumption": "PETG; 0.4 mm nozzle; 0.20 mm layers",
}


def _axis_centres(lo: float, hi: float, pitch: float) -> np.ndarray:
    return np.arange(lo - pitch / 2.0, hi + pitch / 2.0 + 1e-9, pitch, dtype=np.float32)


def _inside_axis(values: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return (values > lo + 1e-7) & (values < hi - 1e-7)


def _rounded_rect(x: np.ndarray, y: np.ndarray, cx: float, cy: float, width: float, depth: float, radius: float) -> np.ndarray:
    hx, hy = width / 2.0, depth / 2.0
    qx = np.maximum(np.abs(x - cx) - (hx - radius), 0.0)
    qy = np.maximum(np.abs(y - cy) - (hy - radius), 0.0)
    return (np.abs(x - cx) < hx) & (np.abs(y - cy) < hy) & (qx * qx + qy * qy < radius * radius)


def _capsule_mask(x: np.ndarray, y: np.ndarray, a: tuple[float, float], b: tuple[float, float], radius: float) -> np.ndarray:
    ax, ay = a
    bx, by = b
    vx, vy = bx - ax, by - ay
    denom = vx * vx + vy * vy
    t = np.clip(((x - ax) * vx + (y - ay) * vy) / denom, 0.0, 1.0)
    dx = x - (ax + t * vx)
    dy = y - (ay + t * vy)
    return dx * dx + dy * dy <= radius * radius


def _honeycomb_mask(x: np.ndarray, y: np.ndarray, bounds: tuple[float, float, float, float], side: float, width: float) -> np.ndarray:
    x0, x1, y0, y1 = bounds
    result = np.zeros(x.shape, dtype=bool)
    vertical_pitch = math.sqrt(3.0) * side
    col_pitch = 1.5 * side
    col = 0
    cx = x0 - side
    while cx <= x1 + side:
        y_offset = (vertical_pitch / 2.0) if col % 2 else 0.0
        cy = y0 - vertical_pitch + y_offset
        while cy <= y1 + vertical_pitch:
            points = [
                (cx + side * math.cos(math.radians(60 * k)), cy + side * math.sin(math.radians(60 * k)))
                for k in range(6)
            ]
            for k in range(6):
                result |= _capsule_mask(x, y, points[k], points[(k + 1) % 6], width / 2.0)
            cy += vertical_pitch
        col += 1
        cx += col_pitch
    clip = (x > x0) & (x < x1) & (y > y0) & (y < y1)
    return result & clip


def build_volume() -> tuple[np.ndarray, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    pitch = RESOLUTION_MM
    xs = _axis_centres(-121.0, 121.0, pitch)
    ys = _axis_centres(-56.0, 43.5, pitch)
    zs = _axis_centres(-1.0, 131.0, pitch)
    xx, yy = np.meshgrid(xs, ys, indexing="xy")
    volume = np.zeros((len(zs), len(ys), len(xs)), dtype=bool)

    def add_extrusion(mask_xy: np.ndarray, z0: float, z1: float) -> None:
        iz = _inside_axis(zs, z0, z1)
        volume[iz] |= mask_xy[None, :, :]

    def remove_extrusion(mask_xy: np.ndarray, z0: float, z1: float) -> None:
        iz = _inside_axis(zs, z0, z1)
        volume[iz] &= ~mask_xy[None, :, :]

    main = (xx > -120.0) & (xx < 120.0) & (yy > -42.5) & (yy < 42.5)
    rear_foot = (xx > -120.0) & (xx < 120.0) & (yy > 7.5) & (yy < 42.5)
    add_extrusion(rear_foot, 0.0, 10.0)

    # Thin 2.0 mm catch-floor shell.  Its upper surface slopes in both axes
    # toward x=0 / front, including the complete area below the holder.
    y_fraction = np.clip((yy + 42.5) / 85.0, 0.0, 1.0)
    x_fraction = np.clip(np.abs(xx) / 120.0, 0.0, 1.0)
    catch_top = 12.0 + 3.0 * y_fraction + 1.0 * x_fraction
    catch_bottom = catch_top - 2.0
    z3 = zs[:, None, None]
    volume |= main[None, :, :] & (z3 > catch_bottom[None, :, :]) & (z3 < catch_top[None, :, :])

    # Outer tray walls with a large open interior under the honeycomb grid.
    inner = (xx > -118.0) & (xx < 118.0) & (yy > -40.5) & (yy < 40.5)
    add_extrusion(main & ~inner, 10.0, 30.0)

    # Honeycomb grid and a robust perimeter frame.
    grid = _honeycomb_mask(xx, yy, (-118.0, 118.0, -40.5, 40.5), 7.0, 2.8)
    frame = main & ~((xx > -118.0) & (xx < 118.0) & (yy > -40.5) & (yy < 40.5))
    add_extrusion(grid | frame, 27.0, 30.0)

    # Left 85 x 85 x 100 mm open brush holder, fused to the grid only.
    holder_outer = _rounded_rect(xx, yy, -77.5, 0.0, 85.0, 85.0, 5.0)
    holder_inner = _rounded_rect(xx, yy, -77.5, 0.0, 81.0, 81.0, 3.0)
    add_extrusion(holder_outer & ~holder_inner, 27.0, 130.0)

    # Short, open, centred drain chute.  Its hydraulic floor descends toward
    # the sink; side-wall geometry leaves the entire top and free end open.
    chute_xy = (xx > -15.5) & (xx < 15.5) & (yy > -55.0) & (yy < -39.3)
    chute_floor_top = 10.0 + np.clip((yy + 55.0) / 15.7, 0.0, 1.0) * 2.0
    chute_floor_bottom = chute_floor_top - 2.0
    volume |= chute_xy[None, :, :] & (z3 > chute_floor_bottom[None, :, :]) & (z3 < chute_floor_top[None, :, :])
    abs_x = np.abs(xx)
    for zi, z in enumerate(zs):
        if not (8.0 < z < 22.0):
            continue
        local_floor_min = 10.0
        if z <= local_floor_min:
            solid_cross = chute_xy & (z > 8.0)
        else:
            inner_half = max(6.0, 12.5 - (z - 10.0) * (6.5 / 8.0))
            solid_cross = chute_xy & (abs_x >= inner_half) & (z < 18.0)
        volume[zi] |= solid_cross

    # Tapered 25 -> 12 mm opening in the main front wall, then an open slot
    # through the upper two millimetres.  Only the front-wall band is cut.
    front_band = (yy > -42.5) & (yy < -39.0)
    for zi, z in enumerate(zs):
        if z <= 12.0:
            continue
        half = 12.5 - min(max(z - 12.0, 0.0), 8.0) * (6.5 / 8.0)
        half = max(6.0, half)
        volume[zi] &= ~(front_band & (abs_x < half))

    return volume, (xs, ys, zs)


def extract_mesh(volume: np.ndarray, axes: tuple[np.ndarray, np.ndarray, np.ndarray]) -> trimesh.Trimesh:
    xs, ys, zs = axes
    vertices_zyx, faces, _normals, _values = marching_cubes(
        volume.astype(np.float32), level=0.5, spacing=(RESOLUTION_MM, RESOLUTION_MM, RESOLUTION_MM), allow_degenerate=False
    )
    vertices = np.column_stack(
        [vertices_zyx[:, 2] + float(xs[0]), vertices_zyx[:, 1] + float(ys[0]), vertices_zyx[:, 0] + float(zs[0])]
    )
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=True, validate=True)
    mesh.remove_unreferenced_vertices()
    trimesh.repair.fix_normals(mesh, multibody=True)
    return mesh


def topology(mesh: trimesh.Trimesh) -> dict:
    unique_counts = np.bincount(mesh.edges_unique_inverse, minlength=len(mesh.edges_unique))
    components = mesh.split(only_watertight=False)
    area_faces = np.asarray(mesh.area_faces)
    return {
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "components": int(len(components)),
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "is_volume": bool(mesh.is_volume),
        "boundary_edges": int(np.count_nonzero(unique_counts == 1)),
        "nonmanifold_edges": int(np.count_nonzero(unique_counts > 2)),
        "maximum_edge_incidence": int(unique_counts.max(initial=0)),
        "zero_area_faces": int(np.count_nonzero(area_faces <= 1e-10)),
        "bounds_mm": np.asarray(mesh.bounds).tolist(),
        "extents_mm": np.asarray(mesh.extents).tolist(),
        "surface_area_mm2": float(mesh.area),
        "signed_volume_mm3": float(mesh.volume),
        "euler_number": int(mesh.euler_number),
    }


def _render_mesh(mesh: trimesh.Trimesh, target: Path, elev: float, azim: float, title: str) -> None:
    """Render the unchanged indexed mesh through a headless EGL depth buffer."""
    elev_r = math.radians(elev)
    azim_r = math.radians(azim)
    camera = np.asarray([math.cos(elev_r) * math.cos(azim_r), math.cos(elev_r) * math.sin(azim_r), math.sin(elev_r)])
    view = -camera
    world_up = np.asarray([0.0, 0.0, 1.0])
    right = np.cross(view, world_up)
    if np.linalg.norm(right) < 1e-8:
        right = np.asarray([1.0, 0.0, 0.0])
    right /= np.linalg.norm(right)
    up = np.cross(right, view)
    up /= np.linalg.norm(up)
    centre = np.asarray(mesh.bounds).mean(axis=0)
    relative = np.asarray(mesh.vertices, dtype=np.float32) - centre.astype(np.float32)
    horizontal = relative @ right
    vertical = relative @ up
    depth = relative @ view
    width, height = 1000, 760
    aspect = width / height
    half_height = max(float(np.ptp(vertical)) / 2.0, float(np.ptp(horizontal)) / (2.0 * aspect)) * 1.12
    half_width = half_height * aspect
    mid_x = float((horizontal.min() + horizontal.max()) / 2.0)
    mid_y = float((vertical.min() + vertical.max()) / 2.0)
    depth_radius = max(float(np.ptp(depth)) / 2.0, 1.0) * 1.2
    clip = np.column_stack(
        [
            (horizontal - mid_x) / half_width,
            (vertical - mid_y) / half_height,
            (depth - float((depth.min() + depth.max()) / 2.0)) / depth_radius,
        ]
    ).astype(np.float32)
    normals = np.asarray(mesh.vertex_normals, dtype=np.float32)
    camera32 = camera.astype(np.float32)
    light_direction = np.asarray([-0.35, -0.55, 0.76], dtype=np.float32)
    light_direction /= np.linalg.norm(light_direction)
    facing = np.abs(normals @ camera32)
    overhead = np.clip(normals @ light_direction, 0.0, 1.0)
    shade = (0.18 + 0.48 * facing + 0.25 * overhead).clip(0.0, 1.0).astype(np.float32)
    packed = np.column_stack([clip, shade]).astype(np.float32)

    context = moderngl.create_standalone_context(backend="egl")
    program = context.program(
        vertex_shader="""
            #version 330
            in vec3 in_position;
            in float in_shade;
            out float shade;
            void main() {
                gl_Position = vec4(in_position, 1.0);
                shade = in_shade;
            }
        """,
        fragment_shader="""
            #version 330
            in float shade;
            out vec4 color;
            void main() {
                vec3 base = vec3(0.20, 0.225, 0.245);
                color = vec4(base * (0.55 + 0.85 * shade), 1.0);
            }
        """,
    )
    vertex_buffer = context.buffer(packed.tobytes())
    index_buffer = context.buffer(np.asarray(mesh.faces, dtype=np.uint32).tobytes())
    array = context.vertex_array(program, [(vertex_buffer, "3f 1f", "in_position", "in_shade")], index_buffer=index_buffer)
    color = context.texture((width, height), 4)
    depth_buffer = context.depth_renderbuffer((width, height))
    framebuffer = context.framebuffer(color_attachments=[color], depth_attachment=depth_buffer)
    framebuffer.use()
    framebuffer.clear(0.956, 0.949, 0.937, 1.0, depth=1.0)
    context.enable(moderngl.DEPTH_TEST)
    array.render(mode=moderngl.TRIANGLES)
    pixels = framebuffer.read(components=4, alignment=1)
    image = Image.frombytes("RGBA", (width, height), pixels).transpose(Image.Transpose.FLIP_TOP_BOTTOM).convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, 38), fill="#f4f2ef")
    draw.text((18, 13), title, fill="#17345f", font=ImageFont.load_default())
    image.save(target)
    array.release(); vertex_buffer.release(); index_buffer.release(); framebuffer.release(); color.release(); depth_buffer.release(); program.release(); context.release()


def render_views(mesh: trimesh.Trimesh, output: Path) -> list[Path]:
    views = [
        ("front", 8.0, -90.0, "FRONTANSICHT"),
        ("top", 90.0, -90.0, "DRAUFSICHT"),
        ("right", 8.0, 0.0, "SEITENANSICHT"),
        ("perspective", 28.0, -58.0, "PERSPEKTIVE"),
    ]
    paths = []
    for name, elev, azim, title in views:
        path = output / f"render-{name}.png"
        _render_mesh(mesh, path, elev, azim, title)
        paths.append(path)
    return paths


def make_diagram(output: Path) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), dpi=150)
    for ax in axes:
        ax.set_aspect("equal")
        ax.axis("off")
    ax = axes[0]
    ax.add_patch(plt.Rectangle((-120, -42.5), 240, 85, fill=False, lw=3, ec="#30353a"))
    ax.add_patch(plt.Rectangle((-120, -42.5), 85, 85, fill=False, lw=3, ec="#345995"))
    ax.add_patch(plt.Rectangle((-15.5, -55), 31, 12.5, fill=False, lw=3, ec="#2a9d8f"))
    ax.text(-77.5, 0, "BÜRSTE\n85×85", ha="center", va="center", fontweight="bold")
    ax.text(25, 0, "DURCHGEHENDE FREIE\nWABENGITTERFLÄCHE", ha="center", va="center", fontsize=9)
    ax.text(0, -50, "Ablauf\nmittig", ha="center", va="center", fontsize=9)
    ax.annotate("240 mm", (-120, 49), (120, 49), arrowprops=dict(arrowstyle="<->"), ha="center")
    ax.annotate("85 mm", (-128, -42.5), (-128, 42.5), arrowprops=dict(arrowstyle="<->"), va="center", rotation=90)
    ax.set_xlim(-140, 140)
    ax.set_ylim(-65, 58)
    ax.set_title("DRAUFSICHT / FUNKTIONSZONEN", fontweight="bold")

    ax = axes[1]
    ax.add_patch(plt.Rectangle((-120, 10), 240, 20, fc="#4a5056", ec="#222", lw=2))
    ax.add_patch(plt.Rectangle((-120, 0), 240, 10, fc="#34393e", ec="#222", lw=2))
    ax.add_patch(plt.Rectangle((-120, 30), 85, 100, fill=False, ec="#345995", lw=4))
    ax.plot([-15.5, 15.5], [20, 20], color="#2a9d8f", lw=5)
    ax.annotate("20 mm Hauptkörper", (125, 10), (125, 30), arrowprops=dict(arrowstyle="<->"), va="center")
    ax.annotate("10 mm Fuß", (138, 0), (138, 10), arrowprops=dict(arrowstyle="<->"), va="center")
    ax.annotate("100 mm Behälter", (-130, 30), (-130, 130), arrowprops=dict(arrowstyle="<->"), va="center", rotation=90)
    ax.text(0, 16, "geneigte Auffangfläche → mittiger offener Ablauf", ha="center", color="white", fontsize=9)
    ax.set_xlim(-150, 155)
    ax.set_ylim(-5, 142)
    ax.set_title("FRONTANSICHT / HÖHEN", fontweight="bold")
    fig.suptitle("BENCHMARK B – SPÜLENABLAGE v003-r03", fontsize=16, fontweight="bold")
    fig.tight_layout()
    path = output / "dimension-and-function-diagram.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def make_contact_sheet(reference: Path, renders: list[Path], diagram: Path, output: Path) -> Path:
    canvas = Image.new("RGB", (2000, 1440), "#f4f2ef")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    items = [(reference, "REFERENZVORGABE"), (renders[-1], "NEUER KANDIDAT – PERSPEKTIVE"),
             (renders[0], "FRONT"), (renders[1], "OBEN"), (renders[2], "RECHTS"), (diagram, "MASSE UND FUNKTION")]
    slots = [(20, 50, 980, 650), (1020, 50, 980, 650), (20, 750, 620, 600),
             (690, 750, 620, 600), (1360, 750, 620, 600), (690, 750, 620, 600)]
    # The diagram replaces the centre-bottom cell; top and right renders keep
    # the visual sheet compact and legible.
    items = [items[0], items[1], items[2], items[3], items[4], items[5]]
    slots = [(20, 45, 960, 650), (1020, 45, 960, 650), (20, 740, 620, 630),
             (690, 740, 620, 630), (1360, 740, 620, 630), (690, 740, 620, 630)]
    for index, ((path, label), (x, y, w, h)) in enumerate(zip(items, slots)):
        if index == 5:
            continue
        image = Image.open(path).convert("RGB")
        image.thumbnail((w, h - 35), Image.Resampling.LANCZOS)
        px = x + (w - image.width) // 2
        py = y + 28 + (h - 35 - image.height) // 2
        canvas.paste(image, (px, py))
        draw.text((x + 8, y + 7), label, fill="#17345f", font=font)
    path = output / "reference-comparison-contact-sheet.png"
    canvas.save(path, quality=95)
    return path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def export_3mf(mesh: trimesh.Trimesh, path: Path) -> None:
    """Write a minimal standards-compliant 3MF model without optional lxml."""
    model_ns = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
    rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    content_ns = "http://schemas.openxmlformats.org/package/2006/content-types"
    ET.register_namespace("", model_ns)
    model = ET.Element(f"{{{model_ns}}}model", {"unit": "millimeter", "xml:lang": "de-DE"})
    resources = ET.SubElement(model, f"{{{model_ns}}}resources")
    obj = ET.SubElement(resources, f"{{{model_ns}}}object", {"id": "1", "type": "model", "name": CANDIDATE})
    mesh_node = ET.SubElement(obj, f"{{{model_ns}}}mesh")
    vertices_node = ET.SubElement(mesh_node, f"{{{model_ns}}}vertices")
    for vertex in np.asarray(mesh.vertices):
        ET.SubElement(
            vertices_node,
            f"{{{model_ns}}}vertex",
            {"x": f"{vertex[0]:.9g}", "y": f"{vertex[1]:.9g}", "z": f"{vertex[2]:.9g}"},
        )
    triangles_node = ET.SubElement(mesh_node, f"{{{model_ns}}}triangles")
    for face in np.asarray(mesh.faces):
        ET.SubElement(
            triangles_node,
            f"{{{model_ns}}}triangle",
            {"v1": str(int(face[0])), "v2": str(int(face[1])), "v3": str(int(face[2]))},
        )
    build = ET.SubElement(model, f"{{{model_ns}}}build")
    ET.SubElement(build, f"{{{model_ns}}}item", {"objectid": "1"})
    model_xml = ET.tostring(model, encoding="utf-8", xml_declaration=True)

    types = ET.Element(f"{{{content_ns}}}Types")
    ET.SubElement(types, f"{{{content_ns}}}Default", {"Extension": "rels", "ContentType": "application/vnd.openxmlformats-package.relationships+xml"})
    ET.SubElement(types, f"{{{content_ns}}}Default", {"Extension": "model", "ContentType": "application/vnd.ms-package.3dmanufacturing-3dmodel+xml"})
    types_xml = ET.tostring(types, encoding="utf-8", xml_declaration=True)
    relationships = ET.Element(f"{{{rel_ns}}}Relationships")
    ET.SubElement(
        relationships,
        f"{{{rel_ns}}}Relationship",
        {"Target": "/3D/3dmodel.model", "Id": "rel0", "Type": "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"},
    )
    relationships_xml = ET.tostring(relationships, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr("[Content_Types].xml", types_xml)
        archive.writestr("_rels/.rels", relationships_xml)
        archive.writestr("3D/3dmodel.model", model_xml)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reference-image", type=Path)
    parser.add_argument("--render-only-stl", type=Path)
    args = parser.parse_args()
    if args.render_only_stl is not None:
        if args.reference_image is None:
            raise SystemExit("--reference-image is required with --render-only-stl")
        mesh = trimesh.load_mesh(args.render_only_stl, process=False)
        renders = render_views(mesh, args.output_dir)
        diagram = make_diagram(args.output_dir)
        make_contact_sheet(args.reference_image, renders, diagram, args.output_dir)
        print(json.dumps({"render_only": True, "geometry_changed": False, "renders": [str(path) for path in renders]}, indent=2))
        return 0
    if args.reference_image is None:
        raise SystemExit("--reference-image is required")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty output: {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reference_copy = args.output_dir / "reference-image.png"
    shutil.copy2(args.reference_image, reference_copy)

    volume, axes = build_volume()
    mesh = extract_mesh(volume, axes)
    topo = topology(mesh)
    if not (topo["components"] == 1 and topo["watertight"] and topo["winding_consistent"] and topo["is_volume"]):
        raise RuntimeError(f"Generated topology failed: {topo}")

    stl = args.output_dir / f"{CANDIDATE}.stl"
    glb = args.output_dir / f"{CANDIDATE}.glb"
    three_mf = args.output_dir / f"{CANDIDATE}.3mf"
    mesh.export(stl)
    mesh.export(glb)
    export_3mf(mesh, three_mf)

    renders = render_views(mesh, args.output_dir)
    diagram = make_diagram(args.output_dir)
    contact = make_contact_sheet(reference_copy, renders, diagram, args.output_dir)
    (args.output_dir / "design-parameters.json").write_text(json.dumps(PARAMETERS, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.output_dir / "technical-validation-preflight.json").write_text(
        json.dumps({"candidate": CANDIDATE, "topology": topo, "source_sha256": sha256(stl)}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "DIMENSION-REPORT.md").write_text(
        "# DIMENSION REPORT – Spülenablage v003-r03\n\n"
        "- Hauptkörper: **240 × 85 × 20 mm** – umgesetzt.\n"
        "- Hinterer Fuß: **240 × 35 × 10 mm** – umgesetzt.\n"
        "- Basishöhe inklusive Fuß: **30 mm**.\n"
        "- Linker Bürstenbehälter: **85 × 85 × 100 mm über Hauptkörper**; Wandstärke **2,0 mm**; oben offen.\n"
        "- Ablauf: vorne mittig; Öffnung **25 mm unten / 12 mm oben / 8 mm Übergangshöhe**.\n"
        "- Kurzer offener Auslaufüberstand: 12,5 mm konstruktiv ergänzt.\n"
        "- Porzellanteil: keine Führung, Einfassung oder Anschläge; freie Aufstellung auf durchgehendem Gitter.\n",
        encoding="utf-8",
    )
    (args.output_dir / "FUNCTION-REPORT.md").write_text(
        "# FUNCTION REPORT – Spülenablage v003-r03\n\n"
        "- Durchgehendes Wabengitter über der Auffangwanne; Wasser kann nach unten passieren.\n"
        "- Geneigte Auffangfläche führt Wasser zur mittigen Frontöffnung.\n"
        "- Ablauf ist oben und am freien Ende offen; kein Rohr, Tunnel oder Sackgassenkanal.\n"
        "- Bürstenbehälter: Vorder- und Seitenwände geschlossen, 2,0 mm stark, oben offen und mit wasserdurchlässigem Gitterboden.\n"
        "- Rechte Seite bleibt als freie Gitterfläche nutzbar.\n"
        "- Porzellanteil und andere Gegenstände stehen frei; es existiert keine Führung, Halterung oder Positionierhilfe.\n"
        "- Normale Wände und Gefälleboden sind 2,0 mm stark. 2,8-mm-Gitterstege und 3,0-mm-Gitterstärke sind als funktionale PETG-Ausnahme für eine 0,4-mm-Düse ausgelegt.\n"
        "- Keine Glättung und keine formverändernde automatische Reparatur angewendet.\n",
        encoding="utf-8",
    )
    print(json.dumps({"candidate": CANDIDATE, "topology": topo, "outputs": len(list(args.output_dir.iterdir()))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
