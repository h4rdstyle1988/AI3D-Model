#!/usr/bin/env python3
"""Build the approved Spuelenablage Lappenhalter R01.

The model is an analytic, section-controlled sweep.  The first 18.0 mm are
an unchanged straight regular hexagonal prism.  Above that datum a quintic
transition grows tangentially into the 12 x 10 mm arm section.  No boolean
repair or post-export shape change is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


MODEL_ID = "spuelenablage-lappenhalter-r01"
REVISION = "R01"
EXPECTED_TASK_BLOB_SHA = "6035fd3c381ced7e52bef73f5df6c9b190e1edfa"
HEX_FLAT_MM = 8.90
HEX_APOTHEM_MM = HEX_FLAT_MM / 2.0
HEX_CORNER_MM = 2.0 * HEX_APOTHEM_MM / math.sqrt(3.0)
PLUG_LENGTH_MM = 18.0
ROOT_MORPH_LENGTH_MM = 12.0
VERTICAL_TO_BEND_MM = 50.0
ARM_WIDTH_MM = 12.0
ARM_HEIGHT_MM = 10.0
EDGE_RADIUS_MM = 2.0
MAIN_INNER_RADIUS_MM = 6.0
MAIN_CENTRE_RADIUS_MM = MAIN_INNER_RADIUS_MM + ARM_HEIGHT_MM / 2.0
RAIL_UNDERSIDE_Z_MM = 74.0
RAIL_CENTRE_Z_MM = RAIL_UNDERSIDE_Z_MM + ARM_HEIGHT_MM / 2.0
PROJECTION_TO_STOP_MM = 90.0
STOP_LENGTH_MM = 8.0
STOP_RISE_MM = 8.0
STOP_INNER_RADIUS_MM = 4.0
STOP_TOP_Z_MM = RAIL_CENTRE_Z_MM + ARM_HEIGHT_MM / 2.0 + STOP_RISE_MM
RING_POINTS = 72


def smooth5(t: float) -> float:
    """Quintic smoothstep: zero first and second derivative at both ends."""
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def rounded_rect_radius(theta: float, half_u: float, half_v: float, radius: float) -> float:
    """Ray intersection radius for a rounded rectangle centred at the origin."""
    du, dv = math.cos(theta), math.sin(theta)
    if radius <= 1e-12:
        limits = []
        if abs(du) > 1e-12:
            limits.append(half_u / abs(du))
        if abs(dv) > 1e-12:
            limits.append(half_v / abs(dv))
        return min(limits)

    def sdf(scale: float) -> float:
        u, v = abs(scale * du), abs(scale * dv)
        qu = u - (half_u - radius)
        qv = v - (half_v - radius)
        outside = math.hypot(max(qu, 0.0), max(qv, 0.0))
        inside = min(max(qu, qv), 0.0)
        return outside + inside - radius

    lo, hi = 0.0, 2.0 * math.hypot(half_u, half_v)
    for _ in range(64):
        mid = 0.5 * (lo + hi)
        if sdf(mid) <= 0.0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def hex_radius(theta: float) -> float:
    """Exact radial boundary of the approved pointy-Y regular hexagon."""
    du, dv = abs(math.cos(theta)), abs(math.sin(theta))
    by_flat = math.inf if du < 1e-12 else HEX_APOTHEM_MM / du
    by_slopes = 2.0 * HEX_APOTHEM_MM / (du + math.sqrt(3.0) * dv)
    return min(by_flat, by_slopes)


ANGLES = np.linspace(0.0, 2.0 * math.pi, RING_POINTS, endpoint=False)


def section_ring(
    centre: tuple[float, float, float],
    axis_u: tuple[float, float, float],
    radius_function,
) -> np.ndarray:
    c = np.asarray(centre, dtype=float)
    u_axis = np.asarray(axis_u, dtype=float)
    u_axis /= np.linalg.norm(u_axis)
    v_axis = np.asarray((0.0, 1.0, 0.0), dtype=float)
    points = []
    for theta in ANGLES:
        radius = float(radius_function(float(theta)))
        points.append(c + radius * (math.cos(theta) * u_axis + math.sin(theta) * v_axis))
    return np.asarray(points, dtype=float)


def rr_function(half_u: float, half_v: float, radius: float = EDGE_RADIUS_MM):
    return lambda theta: rounded_rect_radius(theta, half_u, half_v, radius)


def build_rings() -> list[np.ndarray]:
    rings: list[np.ndarray] = []
    vertical_u = (1.0, 0.0, 0.0)

    # Exactly constant approved plug, z = 0 ... 18 mm.
    rings.append(section_ring((0.0, 0.0, 0.0), vertical_u, hex_radius))
    rings.append(section_ring((0.0, 0.0, PLUG_LENGTH_MM), vertical_u, hex_radius))

    # Tangential, monotone root morph.  No step exists at z=18 or z=30.
    root_steps = 12
    for index in range(1, root_steps + 1):
        t = index / root_steps
        blend = smooth5(t)

        def morph(theta: float, blend_value: float = blend) -> float:
            start = hex_radius(theta)
            end = rounded_rect_radius(theta, ARM_HEIGHT_MM / 2.0, ARM_WIDTH_MM / 2.0, EDGE_RADIUS_MM)
            return start + blend_value * (end - start)

        z = PLUG_LENGTH_MM + ROOT_MORPH_LENGTH_MM * t
        rings.append(section_ring((0.0, 0.0, z), vertical_u, morph))

    # Preserve the confirmed bend-start datum 50 mm above the plug.
    bend_start_z = PLUG_LENGTH_MM + VERTICAL_TO_BEND_MM
    rings.append(section_ring((0.0, 0.0, bend_start_z), vertical_u, rr_function(5.0, 6.0)))

    # Main 90-degree bend: R6 inner, R11 centre, R16 outer.
    bend_steps = 45
    bend_cx, bend_cz = MAIN_CENTRE_RADIUS_MM, bend_start_z
    for index in range(1, bend_steps + 1):
        theta = math.pi - (math.pi / 2.0) * index / bend_steps
        x = bend_cx + MAIN_CENTRE_RADIUS_MM * math.cos(theta)
        z = bend_cz + MAIN_CENTRE_RADIUS_MM * math.sin(theta)
        # Continuous right normal: +X on vertical leg, -Z on horizontal arm.
        axis_u = (-math.cos(theta), 0.0, -math.sin(theta))
        rings.append(section_ring((x, 0.0, z), axis_u, rr_function(5.0, 6.0)))

    # Straight defined 12 x 10 mm main section.
    rings.append(section_ring((86.0, 0.0, RAIL_CENTRE_Z_MM), (0.0, 0.0, -1.0), rr_function(5.0, 6.0)))

    # Existing end-stop function and 8 mm envelope are preserved.  The inner
    # boundary remains R4; the outer radius eases from 14 to 12 mm so the new
    # 10-mm arm joins tangentially and the old x=98 maximum remains unchanged.
    end_steps = 45
    end_cx, end_cz = 86.0, 88.0
    for index in range(1, end_steps + 1):
        t = index / end_steps
        theta = -math.pi / 2.0 + (math.pi / 2.0) * t
        outer_radius = 14.0 - 2.0 * smooth5(t)
        half_depth = 0.5 * (outer_radius - STOP_INNER_RADIUS_MM)
        centre_radius = STOP_INNER_RADIUS_MM + half_depth
        radial = (math.cos(theta), 0.0, math.sin(theta))
        centre = (
            end_cx + centre_radius * radial[0],
            0.0,
            end_cz + centre_radius * radial[2],
        )
        rings.append(section_ring(centre, radial, rr_function(half_depth, 6.0)))

    # Short stop stem plus R2 upper edge roll-off.
    rings.append(section_ring((94.0, 0.0, 90.0), (1.0, 0.0, 0.0), rr_function(4.0, 6.0)))
    cap_steps = 8
    for index in range(1, cap_steps + 1):
        dz = 2.0 * index / cap_steps
        cap_radius = math.sqrt(max(0.0, EDGE_RADIUS_MM ** 2 - dz ** 2))
        half_u = 2.0 + cap_radius
        half_v = 4.0 + cap_radius
        rings.append(
            section_ring(
                (94.0, 0.0, 90.0 + dz),
                (1.0, 0.0, 0.0),
                rr_function(half_u, half_v, cap_radius),
            )
        )
    return rings


def triangulate(rings: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    vertices = np.vstack(rings).tolist()
    faces: list[tuple[int, int, int]] = []
    for ring_index in range(len(rings) - 1):
        lower = ring_index * RING_POINTS
        upper = (ring_index + 1) * RING_POINTS
        for point_index in range(RING_POINTS):
            next_index = (point_index + 1) % RING_POINTS
            a, b = lower + point_index, lower + next_index
            c, d = upper + next_index, upper + point_index
            faces.append((a, b, c))
            faces.append((a, c, d))

    bottom_centre = len(vertices)
    vertices.append([0.0, 0.0, 0.0])
    for point_index in range(RING_POINTS):
        next_index = (point_index + 1) % RING_POINTS
        faces.append((bottom_centre, next_index, point_index))

    top_ring = (len(rings) - 1) * RING_POINTS
    top_centre = len(vertices)
    vertices.append([94.0, 0.0, STOP_TOP_Z_MM])
    for point_index in range(RING_POINTS):
        next_index = (point_index + 1) % RING_POINTS
        faces.append((top_centre, top_ring + point_index, top_ring + next_index))
    return np.asarray(vertices, dtype=float), np.asarray(faces, dtype=np.int64)


def face_normals(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    triangles = vertices[faces]
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    normals /= lengths[:, None]
    return normals


def write_binary_stl(path: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    normals = face_normals(vertices, faces)
    header = (f"{MODEL_ID} analytic sweep; dimensions in mm").encode("ascii")[:80].ljust(80, b" ")
    with path.open("wb") as handle:
        handle.write(header)
        handle.write(struct.pack("<I", len(faces)))
        for normal, face in zip(normals, faces):
            values = [*normal, *vertices[face[0]], *vertices[face[1]], *vertices[face[2]]]
            handle.write(struct.pack("<12fH", *values, 0))


def font(size: int, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def render_mesh(
    vertices: np.ndarray,
    faces: np.ndarray,
    output: Path,
    title: str,
    camera: tuple[float, float, float],
    face_mask: np.ndarray | None = None,
    subtitle: str = "Render der tatsaechlichen finalen STL-Geometrie",
) -> None:
    width, height = 1600, 1100
    canvas = Image.new("RGB", (width, height), "#f3f1ec")
    draw = ImageDraw.Draw(canvas)
    camera_vector = np.asarray(camera, dtype=float)
    camera_vector /= np.linalg.norm(camera_vector)
    world_up = np.asarray((0.0, 0.0, 1.0))
    right = np.cross(world_up, camera_vector)
    if np.linalg.norm(right) < 1e-9:
        right = np.asarray((1.0, 0.0, 0.0))
    right /= np.linalg.norm(right)
    up = np.cross(camera_vector, right)
    up /= np.linalg.norm(up)
    projected = np.column_stack((vertices @ right, vertices @ up, vertices @ camera_vector))

    selected_faces = faces if face_mask is None else faces[face_mask]
    selected_indices = np.unique(selected_faces.ravel())
    xy = projected[selected_indices, :2]
    lo, hi = xy.min(axis=0), xy.max(axis=0)
    span = np.maximum(hi - lo, 1e-6)
    scale = min((width - 150) / span[0], (height - 230) / span[1])
    centre = 0.5 * (lo + hi)

    def screen(points: np.ndarray) -> list[tuple[float, float]]:
        x = (points[:, 0] - centre[0]) * scale + width / 2.0
        y = height / 2.0 - (points[:, 1] - centre[1]) * scale + 35.0
        return list(zip(x.tolist(), y.tolist()))

    normals = face_normals(vertices, selected_faces)
    depths = projected[selected_faces, 2].mean(axis=1)
    order = np.argsort(depths)
    light = np.asarray((0.35, -0.45, 0.82), dtype=float)
    light /= np.linalg.norm(light)
    for index in order:
        normal = normals[index]
        if float(np.dot(normal, camera_vector)) <= -0.02:
            continue
        brightness = 0.50 + 0.42 * max(0.0, float(np.dot(normal, light)))
        base = np.asarray((226, 137, 42), dtype=float)
        colour = tuple(np.clip(base * brightness + 22.0, 0, 255).astype(int))
        polygon = screen(projected[selected_faces[index], :2])
        draw.polygon(polygon, fill=colour)

    draw.rectangle((0, 0, width, 126), fill="#17345f")
    draw.text((55, 25), title, font=font(42, True), fill="white")
    draw.text((57, 78), subtitle, font=font(22), fill="#dce8f6")
    draw.text((55, height - 48), f"{MODEL_ID} | mm | PETG/FDM 0.4 mm", font=font(20), fill="#17345f")
    canvas.save(output)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    # Repository text files are Git-normalized to LF (Windows worktree is CRLF).
    payload = payload.replace(b"\r\n", b"\n")
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--task-file", type=Path, required=True)
    args = parser.parse_args()
    live_task_blob = git_blob_sha(args.task_file)
    if live_task_blob != EXPECTED_TASK_BLOB_SHA:
        raise SystemExit(f"Approved task identity mismatch: expected {EXPECTED_TASK_BLOB_SHA}, got {live_task_blob}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    rings = build_rings()
    vertices, faces = triangulate(rings)
    # Render and STL export use the same final float32 vertex coordinates.
    vertices = vertices.astype(np.float32).astype(np.float64)
    stl_path = args.output_dir / f"{MODEL_ID}.stl"
    write_binary_stl(stl_path, vertices, faces)

    render_mesh(vertices, faces, args.output_dir / "render-3-4-ansicht.png", "3/4-ANSICHT", (0.75, -1.0, 0.52))
    render_mesh(vertices, faces, args.output_dir / "render-seitenansicht.png", "SEITENANSICHT", (0.0, -1.0, 0.02))
    centres = vertices[faces].mean(axis=1)
    root_mask = (centres[:, 0] < 18.0) & (centres[:, 2] < 42.0)
    render_mesh(
        vertices,
        faces,
        args.output_dir / "render-steckzapfen-uebergang.png",
        "STECKZAPFEN UND LASTGERECHTER UEBERGANG",
        (-0.72, -1.0, 0.28),
        root_mask,
        "Detail aus derselben finalen STL-Geometrie | Zapfen z=0..18 mm unveraendert",
    )

    parameters = {
        "schema": "ai3d.spuelenablage-lappenhalter.design-parameters.v1",
        "task": {"path": str(args.task_file).replace("\\", "/"), "blob_sha": live_task_blob, "approval_identity_verified": True, "sha256": sha256(args.task_file)},
        "model_id": MODEL_ID,
        "revision": REVISION,
        "units": "mm",
        "material": "PETG",
        "nozzle_mm": 0.4,
        "plug": {"shape": "straight regular hexagonal prism", "flat_to_flat_mm": HEX_FLAT_MM, "corner_to_corner_mm": HEX_CORNER_MM, "straight_length_mm": PLUG_LENGTH_MM, "taper": False, "count": 1},
        "arm": {"main_section_width_mm": ARM_WIDTH_MM, "main_section_height_mm": ARM_HEIGHT_MM, "projection_to_stop_start_mm": PROJECTION_TO_STOP_MM, "vertical_bend_start_above_plug_mm": VERTICAL_TO_BEND_MM, "main_inner_radius_mm": MAIN_INNER_RADIUS_MM},
        "root_transition": {"start_z_mm": PLUG_LENGTH_MM, "end_z_mm": PLUG_LENGTH_MM + ROOT_MORPH_LENGTH_MM, "length_mm": ROOT_MORPH_LENGTH_MM, "interpolation": "quintic smoothstep radial morph", "end_derivatives_zero": True, "step_or_sharp_notch": False},
        "stop": {"function_preserved": True, "start_x_mm": PROJECTION_TO_STOP_MM, "maximum_x_mm": PROJECTION_TO_STOP_MM + STOP_LENGTH_MM, "rise_above_arm_top_mm": STOP_RISE_MM, "inner_radius_mm": STOP_INNER_RADIUS_MM},
        "generation": {"method": "single closed analytic section sweep", "ring_points": RING_POINTS, "boolean_repairs": False, "mesh_smoothing": False, "shape_changing_repair": False},
        "print_orientation": {"orientation": "side lying; local Y becomes printer Z", "support": "localized, accessible support under the narrower hex plug", "reason": "keeps service bending tension/compression predominantly within X-Z layer planes"},
        "artifacts": {"stl": stl_path.name, "stl_sha256": sha256(stl_path), "renders": ["render-3-4-ansicht.png", "render-seitenansicht.png", "render-steckzapfen-uebergang.png"]},
    }
    (args.output_dir / "design-parameters.json").write_text(json.dumps(parameters, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"model": MODEL_ID, "vertices": len(vertices), "faces": len(faces), "stl": str(stl_path), "sha256": sha256(stl_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
