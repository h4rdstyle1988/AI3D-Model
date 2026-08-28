#!/usr/bin/env python3
"""Build Benchmark B sink organizer concept v001 in Blender 5.2.

This is a new, deterministic concept geometry.  It does not read or modify any
AI-generated model.  All dimensions are millimetres and Z is up.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy


REVISION = "B-2026-08-25.1"
OUTLET_ARC_MM = 50.0
OUTLET_VERTICAL_DROP_MM = 2.5
OUTLET_HORIZONTAL_PROJECTION_MM = math.sqrt(OUTLET_ARC_MM**2 - OUTLET_VERTICAL_DROP_MM**2)
CANDIDATE = "benchmark-b-parametric-v001-r04"

P = {
    "design_status": "CONCEPT_ASSUMPTIONS_PENDING_PRIOR_MAIN_DIMENSIONS",
    "main_body_width_mm": 240.0,
    "main_body_depth_mm": 110.0,
    "main_body_max_height_mm": 30.0,
    "body_wall_mm": 3.2,
    "body_floor_front_top_z_mm": 5.0,
    "body_floor_rear_top_z_mm": 8.0,
    "body_floor_bottom_z_mm": 1.0,
    "outlet_functional_length_mm": OUTLET_ARC_MM,
    "outlet_horizontal_projection_mm": OUTLET_HORIZONTAL_PROJECTION_MM,
    "outlet_vertical_drop_mm": OUTLET_VERTICAL_DROP_MM,
    "outlet_exit_plane_y_mm": 0.0,
    "outlet_end_plane_y_mm": -OUTLET_HORIZONTAL_PROJECTION_MM,
    "outlet_inner_width_at_exit_mm": 32.0,
    "outlet_inner_width_at_end_mm": 22.0,
    "outlet_side_wall_mm": 3.0,
    "outlet_floor_thickness_mm": 2.5,
    "outlet_floor_top_at_exit_mm": 5.0,
    "outlet_floor_top_at_end_mm": 2.5,
    "outlet_rim_profile_peak_y_mm": -15.0,
    "outlet_rim_profile_peak_top_z_mm": 14.0,
    "grid_z_bottom_mm": 15.0,
    "grid_z_top_mm": 18.2,
    "grid_strut_width_mm": 3.2,
    "grid_pitch_mm": 14.0,
    "grid_typical_opening_mm": 10.8,
    "grid_y_min_mm": 18.0,
    "grid_y_max_mm": 100.0,
    "zones": {
        "dish_brush": {"x_min": -112.0, "x_max": -42.0, "reference_envelope_mm": [55.0, 70.0]},
        "sponge": {"x_min": -35.0, "x_max": 35.0, "reference_envelope_mm": [65.0, 75.0]},
        "detergent_bottle": {"x_min": 42.0, "x_max": 112.0, "reference_envelope_mm": [65.0, 65.0]},
    },
    "nominal_fdm_nozzle_mm": 0.4,
    "nominal_layer_height_mm": 0.2,
}


def box(name: str, x0: float, x1: float, y0: float, y1: float, z0: float, z1: float):
    bpy.ops.mesh.primitive_cube_add(location=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = (x1 - x0, y1 - y0, z1 - z0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def tapered_prism(
    name: str,
    y0: float,
    y1: float,
    left0: float,
    right0: float,
    left1: float,
    right1: float,
    bottom0: float,
    top0: float,
    bottom1: float,
    top1: float,
):
    vertices = [
        (left0, y0, bottom0), (right0, y0, bottom0), (right0, y0, top0), (left0, y0, top0),
        (left1, y1, bottom1), (right1, y1, bottom1), (right1, y1, top1), (left1, y1, top1),
    ]
    faces = [
        (0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
        (3, 7, 6, 2), (0, 4, 7, 3), (1, 2, 6, 5),
    ]
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def open_u_channel(name: str):
    """One watertight tapered U-channel with no internal Boolean seams."""
    end_y = -OUTLET_HORIZONTAL_PROJECTION_MM
    mid_y = -15.0
    mid_fraction = abs(mid_y) / OUTLET_HORIZONTAL_PROJECTION_MM
    mid_outer = 19.0 + mid_fraction * (14.0 - 19.0)
    mid_inner = 16.0 + mid_fraction * (11.0 - 16.0)
    mid_floor = 5.0 - mid_fraction * OUTLET_VERTICAL_DROP_MM
    sections = [
        # y, outer half-width, inner half-width, bottom, hydraulic floor, side top
        (2.0, 19.0, 16.0, 2.5, 5.0, 10.0),
        (0.0, 19.0, 16.0, 2.5, 5.0, 10.0),
        (mid_y, mid_outer, mid_inner, mid_floor - 2.5, mid_floor, 14.0),
        (end_y, 14.0, 11.0, 0.0, 2.5, 8.0),
    ]
    vertices = []
    for y, outer, inner, bottom, floor, top in sections:
        vertices.extend([
            (-outer, y, bottom), (outer, y, bottom),
            (outer, y, top), (inner, y, top), (inner, y, floor),
            (-inner, y, floor), (-inner, y, top), (-outer, y, top),
        ])
    faces = []
    ring = 8
    for section in range(len(sections) - 1):
        a, b = section * ring, (section + 1) * ring
        for edge in range(ring):
            nxt = (edge + 1) % ring
            faces.append((a + edge, b + edge, b + nxt, a + nxt))
    faces.append(tuple(reversed(range(ring))))
    last = (len(sections) - 1) * ring
    faces.append(tuple(last + index for index in range(ring)))
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def add_grid(pieces: list, zone_name: str, x0: float, x1: float) -> None:
    y0, y1 = P["grid_y_min_mm"], P["grid_y_max_mm"]
    z0, z1 = P["grid_z_bottom_mm"], P["grid_z_top_mm"]
    width, pitch = P["grid_strut_width_mm"], P["grid_pitch_mm"]
    half = width / 2
    pieces.extend([
        box(f"{zone_name}_frame_x0", x0, x0 + width, y0, y1, z0, z1),
        box(f"{zone_name}_frame_x1", x1 - width, x1, y0, y1, z0, z1),
        box(f"{zone_name}_frame_y0", x0, x1, y0, y0 + width, z0, z1),
        box(f"{zone_name}_frame_y1", x0, x1, y1 - width, y1, z0, z1),
    ])
    x = x0 + pitch
    index = 0
    while x < x1 - width:
        pieces.append(box(f"{zone_name}_rib_x_{index:02d}", x - half, x + half, y0, y1, z0, z1))
        x += pitch
        index += 1
    y = y0 + pitch
    index = 0
    while y < y1 - width:
        pieces.append(box(f"{zone_name}_rib_y_{index:02d}", x0, x1, y - half, y + half, z0, z1))
        y += pitch
        index += 1


def union_exact(pieces: list):
    base = pieces[0]
    bpy.context.view_layer.objects.active = base
    base.select_set(True)
    for index, tool in enumerate(pieces[1:], start=1):
        modifier = base.modifiers.new(name=f"union_{index:03d}", type="BOOLEAN")
        modifier.operation = "UNION"
        modifier.solver = "EXACT"
        modifier.object = tool
        bpy.context.view_layer.objects.active = base
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        bpy.data.objects.remove(tool, do_unlink=True)
    base.name = CANDIDATE
    bpy.context.view_layer.objects.active = base
    base.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=0.0005)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    triangulate = base.modifiers.new(name="triangulate", type="TRIANGULATE")
    bpy.ops.object.modifier_apply(modifier=triangulate.name)
    return base


def build():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    pieces = []
    # Catch floor: the top drops monotonically from rear (8 mm) to outlet (5 mm).
    pieces.append(tapered_prism("body_floor", 0.0, 110.0, -120.0, 120.0, -120.0, 120.0, 1.0, 5.0, 1.0, 8.0))
    # Perimeter walls; the central 38 mm of the front remains the hydraulic outlet.
    pieces.extend([
        box("left_wall", -120.0, -116.8, 0.0, 110.0, 1.0, 30.0),
        box("right_wall", 116.8, 120.0, 0.0, 110.0, 1.0, 30.0),
        box("rear_wall", -120.0, 120.0, 106.8, 110.0, 1.0, 30.0),
        box("front_wall_left", -120.0, -18.5, 0.0, 3.2, 1.0, 24.0),
        box("front_wall_right", 18.5, 120.0, 0.0, 3.2, 1.0, 24.0),
    ])
    # Three real through-open grids, not cosmetic recesses.
    for zone_name, zone in P["zones"].items():
        add_grid(pieces, zone_name, zone["x_min"], zone["x_max"])
    # Discrete 4 x 4 mm supports join each grid to the catch floor.  They avoid
    # coplanar Boolean seams and leave the collector volume open around them.
    for zone_name, zone in P["zones"].items():
        for ix, x in enumerate((zone["x_min"] + 1.6, zone["x_max"] - 1.6)):
            for iy, y in enumerate((P["grid_y_min_mm"] + 1.6, P["grid_y_max_mm"] - 1.6)):
                pieces.append(box(f"{zone_name}_support_{ix}_{iy}", x - 2.0, x + 2.0, y - 2.0, y + 2.0, 3.0, 15.5))
    # Open U-channel.  It overlaps two millimetres into the main body so the
    # Boolean union is robust; functional measurement remains y=0 to y=-50.
    # Hydraulic invert is monotone: 5.0 -> 2.5 mm. Its 3D centreline arc is
    # exactly 50.0 mm; the horizontal projection is therefore slightly shorter.
    # Only the side-wall crest
    # rises at y=-15 to provide the requested rim-clearance cue without a trap.
    pieces.append(open_u_channel("open_u_channel"))
    solid = union_exact(pieces)
    material = bpy.data.materials.new("Drainage blue")
    material.diffuse_color = (0.06, 0.32, 0.55, 1.0)
    solid.data.materials.append(material)
    return solid


def export_all(solid, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    bpy.context.view_layer.objects.active = solid
    bpy.ops.object.select_all(action="DESELECT")
    solid.select_set(True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_dir / f"{CANDIDATE}.blend"))
    bpy.ops.wm.stl_export(filepath=str(output_dir / f"{CANDIDATE}.stl"), export_selected_objects=True, ascii_format=False)
    bpy.ops.export_scene.gltf(
        filepath=str(output_dir / f"{CANDIDATE}.glb"),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(argv)
    solid = build()
    export_all(solid, args.output_dir)
    parameter_path = args.output_dir / "design-parameters.json"
    parameter_path.write_text(json.dumps({"candidate": CANDIDATE, "requirements_revision": REVISION, "parameters": P}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"candidate": CANDIDATE, "vertices": len(solid.data.vertices), "polygons": len(solid.data.polygons), "output": str(args.output_dir)}))


if __name__ == "__main__":
    main()
