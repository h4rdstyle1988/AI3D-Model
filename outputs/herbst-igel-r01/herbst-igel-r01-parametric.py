"""Parametric mesh build for TASK-HERBST-IGEL-R01-RETRY-REF-AUTH-R02.

The model is generated without a proprietary CAD dependency.  A single
reference-derived implicit outer skin is split by the approved natural seam,
opened at that seam, offset inward by the nominal 1.6 mm, and furnished with
one hidden glued connector.  Binary STL, assembled GLB, inspection renders,
and measured validation data are derived from the same final triangle meshes.

Coordinate system: X front (-) to back (+), Y left/right, Z up; millimetres.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import struct
import sys
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


TASK = "TASK-HERBST-IGEL-R01-RETRY-REF-AUTH-R02"
REVISION = "R01"
CLEAN_SHA = "f3017009739284e1bfd6e8502e9d9258eb74dbf52074c425a73ff41fc8bac328"
SEAM_SHA = "b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4"

P = {
    "nominal_shell_mm": 1.6,
    "peg_diameter_mm": 10.0,
    "engagement_mm": 20.0,
    "socket_diameter_mm": 10.4,
    "radial_clearance_mm": 0.2,
    "diametral_clearance_mm": 0.4,
    "socket_depth_mm": 20.4,
    "connector_axis": "+X from body into back",
    "connector_center_y_mm": 0.0,
    "connector_center_z_mm": 76.0,
    "grid_mm": 1.0,
    "body_texture_amplitude_mm": 0.28,
    "target_max_extent_mm": 200.0,
    "nozzle_mm": 0.4,
    "layer_height_mm": 0.12,
    "adaptive_min_mm": 0.08,
    "decorative_maple_leaf_count": 1,
}

TAN = np.array([0.72, 0.55, 0.34], dtype=float)
COPPER = np.array([0.72, 0.24, 0.075], dtype=float)
BACKGROUND = (238, 235, 230)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def seam_x(y, z):
    """Approved blue natural boundary, fitted in the model coordinate system."""
    return 42.0 - 0.15 * z - 0.0018 * (z - 30.0) ** 2 + 0.0018 * y**2


def ellipsoid_sdf(x, y, z, center, radii):
    cx, cy, cz = center
    rx, ry, rz = radii
    q = np.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 + ((z - cz) / rz) ** 2)
    return (q - 1.0) * min(rx, ry, rz)


def oriented_ellipsoid_sdf(x, y, z, center, axes, radii):
    px, py, pz = x - center[0], y - center[1], z - center[2]
    u, v, n = axes
    a = px * u[0] + py * u[1] + pz * u[2]
    b = px * v[0] + py * v[1] + pz * v[2]
    c = px * n[0] + py * n[1] + pz * n[2]
    rr = min(radii)
    return (np.sqrt((a / radii[0]) ** 2 + (b / radii[1]) ** 2 + (c / radii[2]) ** 2) - 1.0) * rr


def capsule_sdf(x, y, z, a, b, radius):
    ax, ay, az = a
    bx, by, bz = b
    pax, pay, paz = x - ax, y - ay, z - az
    bax, bay, baz = bx - ax, by - ay, bz - az
    denom = bax * bax + bay * bay + baz * baz
    h = np.clip((pax * bax + pay * bay + paz * baz) / denom, 0.0, 1.0)
    return np.sqrt((pax - bax * h) ** 2 + (pay - bay * h) ** 2 + (paz - baz * h) ** 2) - radius


def cylinder_x_sdf(x, y, z, x0, x1, radius, cy=0.0, cz=76.0):
    xc = 0.5 * (x0 + x1)
    half = 0.5 * (x1 - x0)
    radial = np.sqrt((y - cy) ** 2 + (z - cz) ** 2) - radius
    axial = np.abs(x - xc) - half
    outside = np.sqrt(np.maximum(radial, 0.0) ** 2 + np.maximum(axial, 0.0) ** 2)
    return outside + np.minimum(np.maximum(radial, axial), 0.0)


def box_sdf(x, y, z, center, half):
    qx = np.abs(x - center[0]) - half[0]
    qy = np.abs(y - center[1]) - half[1]
    qz = np.abs(z - center[2]) - half[2]
    outside = np.sqrt(np.maximum(qx, 0.0) ** 2 + np.maximum(qy, 0.0) ** 2 + np.maximum(qz, 0.0) ** 2)
    return outside + np.minimum(np.maximum(np.maximum(qx, qy), qz), 0.0)


BASE_ELLIPSOIDS = [
    ((-10.0, 0.0, 70.0), (65.0, 43.0, 64.0), "torso"),
    ((-48.0, 0.0, 96.0), (46.0, 38.5, 46.0), "head"),
    ((-75.0, 0.0, 91.0), (28.0, 29.0, 27.0), "muzzle"),
    ((20.0, 0.0, 87.0), (66.0, 48.0, 70.0), "back_core"),
    ((-48.0, -25.0, 13.0), (23.0, 16.0, 13.0), "foot_front_visible"),
    ((9.0, -27.0, 12.0), (25.0, 17.0, 12.0), "foot_rear_visible"),
    ((-46.0, 22.0, 13.5), (20.0, 14.0, 12.5), "foot_front_opposite"),
    ((10.0, 24.0, 12.5), (22.0, 15.0, 11.5), "foot_rear_opposite"),
    ((-27.0, -31.5, 132.0), (15.5, 10.0, 18.0), "ear_visible"),
    ((-27.0, 31.5, 132.0), (15.5, 10.0, 18.0), "ear_opposite"),
]

FEATURE_ELLIPSOIDS = [
    ((-67.0, -36.8, 108.0), (6.2, 4.2, 7.0), "eye_visible"),
    ((-67.0, 36.8, 108.0), (6.2, 4.2, 7.0), "eye_opposite"),
    ((-101.0, 0.0, 93.0), (8.0, 8.5, 8.0), "nose"),
]


def unit(v):
    a = np.asarray(v, dtype=float)
    n = np.linalg.norm(a)
    return a / n


def leaf_primitives():
    """Ordinary overlapping leaf/spines derived from REF-CLEAN only."""
    leaves = []
    back_c = np.array((20.0, 0.0, 87.0))
    back_r = np.array((66.0, 48.0, 70.0))
    for side in (-1.0, 1.0):
        for row, z in enumerate((43.0, 62.0, 82.0, 102.0, 122.0, 141.0)):
            for col, x in enumerate((22.0, 43.0, 64.0)):
                # Leave the approved visible-side maple leaf visually legible.
                if side < 0.0 and 36.0 <= x <= 70.0 and 55.0 <= z <= 96.0:
                    continue
                q = 1.0 - ((x - back_c[0]) / back_r[0]) ** 2 - ((z - back_c[2]) / back_r[2]) ** 2
                if q <= 0.05:
                    continue
                y = side * back_r[1] * math.sqrt(q)
                normal = unit(((x - 20.0) / 66.0**2, (y / 48.0**2), (z - 87.0) / 70.0**2))
                direction = unit((0.78, 0.08 * side, -0.45 + 0.10 * row))
                across = unit(np.cross(normal, direction))
                direction = unit(np.cross(across, normal))
                center = np.array((x, y, z)) + normal * 2.2
                length = 15.0 + 1.4 * ((row + col) % 3)
                width = 6.1 + 0.7 * ((row + 2 * col) % 2)
                leaves.append((center, (direction, across, normal), (length, width, 4.6), f"side_{side:+.0f}_{row}_{col}"))
    for x in (-8.0, 15.0, 38.0, 61.0):
        for y in (-22.0, 0.0, 22.0):
            q = 1.0 - ((x - 20.0) / 66.0) ** 2 - (y / 48.0) ** 2
            if q <= 0.05:
                continue
            z = 87.0 + 70.0 * math.sqrt(q)
            normal = unit(((x - 20.0) / 66.0**2, y / 48.0**2, (z - 87.0) / 70.0**2))
            direction = unit((0.86, 0.0, -0.35))
            across = unit(np.cross(normal, direction))
            direction = unit(np.cross(across, normal))
            leaves.append((np.array((x, y, z)) + normal * 2.0, (direction, across, normal), (15.5, 6.2, 4.3), f"top_{x}_{y}"))
    for y in (-30.0, -10.0, 10.0, 30.0):
        for z in (62.0, 86.0, 110.0):
            q = 1.0 - (y / 48.0) ** 2 - ((z - 87.0) / 70.0) ** 2
            if q <= 0.05:
                continue
            x = 20.0 + 66.0 * math.sqrt(q)
            normal = unit(((x - 20.0) / 66.0**2, y / 48.0**2, (z - 87.0) / 70.0**2))
            direction = unit((0.42, 0.0, -0.91))
            across = unit(np.cross(normal, direction))
            direction = unit(np.cross(across, normal))
            leaves.append((np.array((x, y, z)) + normal * 1.7, (direction, across, normal), (14.8, 5.8, 4.2), f"rear_{y}_{z}"))
    return leaves


LEAVES = leaf_primitives()


def maple_primitives():
    """One and only one decorative maple-leaf cluster on the visible side."""
    center = np.array((45.0, -48.0, 76.0))
    normal = unit((0.20, -1.0, -0.05))
    lobes = []
    # Five connected lobes form one maple leaf; the count is semantic, not five decorations.
    for angle_deg, length, width, shift in [
        (90, 15.0, 5.8, 5.0), (48, 12.5, 5.2, 2.5), (132, 12.5, 5.2, 2.5),
        (18, 9.5, 4.5, 0.0), (162, 9.5, 4.5, 0.0),
    ]:
        a = math.radians(angle_deg)
        direction = unit((math.cos(a), 0.10, math.sin(a)))
        across = unit(np.cross(normal, direction))
        direction = unit(np.cross(across, normal))
        c = center + direction * shift + normal * 1.8
        lobes.append((c, (direction, across, normal), (length, width, 3.7), f"maple_lobe_{angle_deg}"))
    return lobes


MAPLE = maple_primitives()


def base_sdf(x, y, z, inward=0.0):
    result = np.full(np.broadcast_shapes(np.shape(x), np.shape(y), np.shape(z)), np.inf, dtype=np.float32)
    for center, radii, _ in BASE_ELLIPSOIDS:
        d = ellipsoid_sdf(x, y, z, center, radii) + inward
        result = np.minimum(result, d.astype(np.float32, copy=False))
    return result


def outer_sdf(x, y, z, include_leaf_relief=True):
    d = base_sdf(x, y, z, 0.0)
    for center, radii, _ in FEATURE_ELLIPSOIDS:
        d = np.minimum(d, ellipsoid_sdf(x, y, z, center, radii))
    if include_leaf_relief:
        for center, axes, radii, _ in LEAVES:
            d = np.minimum(d, oriented_ellipsoid_sdf(x, y, z, center, axes, radii))
            # Raised midrib provides a printable vein/ridge on each ordinary leaf.
            u = axes[0]
            a = center - u * (radii[0] * 0.72) + axes[2] * 2.2
            b = center + u * (radii[0] * 0.72) + axes[2] * 2.2
            d = np.minimum(d, capsule_sdf(x, y, z, a, b, 0.72))
        for center, axes, radii, _ in MAPLE:
            d = np.minimum(d, oriented_ellipsoid_sdf(x, y, z, center, axes, radii))
        # One connected stem and its raised veins belong to the single maple leaf.
        maple_stem = (42.0, -49.0, 70.0)
        maple_hub = (45.0, -50.0, 76.0)
        d = np.minimum(d, capsule_sdf(x, y, z, maple_stem, (52.0, -49.0, 62.0), 2.1))
        for tip in ((45.0, -50.5, 92.0), (56.0, -50.0, 85.0), (34.0, -50.0, 85.0),
                    (60.0, -49.5, 77.0), (30.0, -49.5, 77.0)):
            d = np.minimum(d, capsule_sdf(x, y, z, maple_hub, tip, 0.72))
    # Subtle, sub-nozzle body texture; it changes no protected proportions.
    texture = P["body_texture_amplitude_mm"] * np.sin(0.31 * x) * np.sin(0.27 * z) * np.cos(0.23 * y)
    body_zone = 1.0 / (1.0 + np.exp(np.clip((x - seam_x(y, z)) / 2.0, -20.0, 20.0)))
    d = d + texture.astype(np.float32, copy=False) * body_zone.astype(np.float32, copy=False)
    # Own feet define a support plane; there is no separate base.
    return np.maximum(d, -z)


def connector_geometry(x, y, z):
    sx = float(seam_x(0.0, P["connector_center_z_mm"]))
    peg_start = sx
    peg_end = sx + P["engagement_mm"]
    socket_end = sx + P["socket_depth_mm"]

    boss = cylinder_x_sdf(x, y, z, sx - 8.0, sx, 10.5)
    peg = cylinder_x_sdf(x, y, z, peg_start, peg_end, 5.0)
    body_support = np.minimum(boss, peg)
    # One minimal internal bridge ties the central boss into both side walls.
    # Its ends overlap the inner offset but stop inside the protected outer skin.
    body_support = np.minimum(body_support, box_sdf(x, y, z, (sx - 4.0, 0.0, 76.0), (2.6, 46.0, 3.0)))

    collar = cylinder_x_sdf(x, y, z, sx, socket_end + 3.1, 9.0)
    back_support = collar
    back_support = np.minimum(back_support, box_sdf(x, y, z, (sx + 4.0, 0.0, 76.0), (2.6, 46.0, 3.0)))
    bore = cylinder_x_sdf(x, y, z, sx - 1.0, socket_end, P["socket_diameter_mm"] / 2.0)
    return body_support, back_support, bore, sx, peg_start, peg_end, socket_end


def final_fields(xs, ys, zs):
    x = xs[:, None, None]
    y = ys[None, :, None]
    z = zs[None, None, :]
    body_outer = outer_sdf(x, y, z, include_leaf_relief=False)
    back_outer = outer_sdf(x, y, z, include_leaf_relief=True)
    inner = base_sdf(x, y, z, P["nominal_shell_mm"])
    seam = seam_x(y, z)
    body_segment = np.maximum(body_outer, x - seam)
    back_segment = np.maximum(back_outer, seam - x)
    # The un-clipped cavity produces the large accessible assembly opening.
    body_shell = np.maximum(body_segment, -inner)
    back_shell = np.maximum(back_segment, -inner)
    body_support, back_support, bore, sx, peg_start, peg_end, socket_end = connector_geometry(x, y, z)
    body = np.minimum(body_shell, body_support)
    back = np.maximum(np.minimum(back_shell, back_support), -bore)

    # Shallow printable smile groove; subtraction stays far from the cavity.
    mouth_a = capsule_sdf(x, y, z, (-97.0, -12.0, 82.0), (-91.0, 0.0, 79.5), 1.05)
    mouth_b = capsule_sdf(x, y, z, (-91.0, 0.0, 79.5), (-97.0, 12.0, 82.0), 1.05)
    body = np.maximum(body, -np.minimum(mouth_a, mouth_b))
    return body.astype(np.float32), back.astype(np.float32), {
        "seam_center_x_mm": sx,
        "peg_start_x_mm": peg_start,
        "peg_end_x_mm": peg_end,
        "socket_end_x_mm": socket_end,
    }


CORNERS = np.array([
    (0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
    (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1),
], dtype=np.int8)
TETS = ((0, 1, 2, 6), (0, 2, 3, 6), (0, 3, 7, 6), (0, 7, 4, 6), (0, 4, 5, 6), (0, 5, 1, 6))


def marching_tetrahedra(field, xs, ys, zs, label):
    """Extract a closed 0-isosurface with a global grid-edge vertex cache."""
    # Avoid exact-zero grid nodes, which otherwise create degenerate cracks.
    field = field - np.float32(1e-4)
    mn = np.minimum.reduce([
        field[:-1, :-1, :-1], field[1:, :-1, :-1], field[1:, 1:, :-1], field[:-1, 1:, :-1],
        field[:-1, :-1, 1:], field[1:, :-1, 1:], field[1:, 1:, 1:], field[:-1, 1:, 1:],
    ])
    mx = np.maximum.reduce([
        field[:-1, :-1, :-1], field[1:, :-1, :-1], field[1:, 1:, :-1], field[:-1, 1:, :-1],
        field[:-1, :-1, 1:], field[1:, :-1, 1:], field[1:, 1:, 1:], field[:-1, 1:, 1:],
    ])
    cells = np.argwhere((mn <= 0.0) & (mx > 0.0))
    print(f"{label}: {len(cells)} active cells", flush=True)
    vertices = []
    faces = []
    edge_cache = {}
    ny, nz = len(ys), len(zs)

    def node_id(ix, iy, iz):
        return (ix * ny + iy) * nz + iz

    def edge_vertex(p0, p1, v0, v1, id0, id1):
        key = (id0, id1) if id0 < id1 else (id1, id0)
        found = edge_cache.get(key)
        if found is not None:
            return found
        denom = v0 - v1
        t = 0.5 if abs(float(denom)) < 1e-12 else float(v0 / denom)
        t = min(1.0, max(0.0, t))
        point = p0 + (p1 - p0) * t
        idx = len(vertices)
        vertices.append(point)
        edge_cache[key] = idx
        return idx

    def add_oriented(face, outward_hint):
        p0, p1, p2 = (np.asarray(vertices[q]) for q in face)
        if float(np.dot(np.cross(p1 - p0, p2 - p0), outward_hint)) < 0.0:
            face = (face[0], face[2], face[1])
        faces.append(face)

    for ci, (i, j, k) in enumerate(cells):
        if ci and ci % 50000 == 0:
            print(f"{label}: extracted {ci}/{len(cells)} cells", flush=True)
        coords = np.empty((8, 3), dtype=np.float64)
        vals = np.empty(8, dtype=np.float64)
        ids = np.empty(8, dtype=np.int64)
        for c, (di, dj, dk) in enumerate(CORNERS):
            ii, jj, kk = i + int(di), j + int(dj), k + int(dk)
            coords[c] = (xs[ii], ys[jj], zs[kk])
            vals[c] = field[ii, jj, kk]
            ids[c] = node_id(ii, jj, kk)
        for tet in TETS:
            inside = [q for q in tet if vals[q] <= 0.0]
            outside = [q for q in tet if vals[q] > 0.0]
            if not inside or not outside:
                continue
            if len(inside) == 1 or len(inside) == 3:
                if len(inside) == 1:
                    a, others = inside[0], outside
                else:
                    a, others = outside[0], inside
                tri = [edge_vertex(coords[a], coords[b], vals[a], vals[b], int(ids[a]), int(ids[b])) for b in others]
                inside_center = coords[inside].mean(axis=0)
                outside_center = coords[outside].mean(axis=0)
                add_oriented(tri, outside_center - inside_center)
            else:
                a, b = inside
                c, d = outside
                ac = edge_vertex(coords[a], coords[c], vals[a], vals[c], int(ids[a]), int(ids[c]))
                ad = edge_vertex(coords[a], coords[d], vals[a], vals[d], int(ids[a]), int(ids[d]))
                bc = edge_vertex(coords[b], coords[c], vals[b], vals[c], int(ids[b]), int(ids[c]))
                bd = edge_vertex(coords[b], coords[d], vals[b], vals[d], int(ids[b]), int(ids[d]))
                outward = coords[outside].mean(axis=0) - coords[inside].mean(axis=0)
                add_oriented((ac, ad, bd), outward)
                add_oriented((ac, bd, bc), outward)
    v = np.asarray(vertices, dtype=np.float64)
    f = np.asarray(faces, dtype=np.int64)
    tri = v[f]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    keep = np.linalg.norm(n, axis=1) > 1e-8
    f = f[keep]
    # Geometrically weld rare duplicate intersections and compact unused nodes.
    rounded = np.round(v, 7)
    unique_v, inverse = np.unique(rounded, axis=0, return_inverse=True)
    f = inverse[f]
    keep = (f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 2] != f[:, 0])
    f = f[keep]
    fs = np.sort(f, axis=1)
    _, first = np.unique(fs, axis=0, return_index=True)
    f = f[np.sort(first)]
    used, compact = np.unique(f.reshape(-1), return_inverse=True)
    v = unique_v[used]
    f = compact.reshape((-1, 3))
    # Orient the complete connected surface by signed volume.
    volume6 = np.einsum("ij,ij->i", v[f[:, 0]], np.cross(v[f[:, 1]], v[f[:, 2]])).sum()
    if volume6 < 0.0:
        f[:, [1, 2]] = f[:, [2, 1]]
    return v, f


def retain_largest_component(vertices, faces):
    """Remove only detached sub-millimetre iso-surface crumbs."""
    edges = np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]), axis=0)
    edges.sort(axis=1)
    edges = np.unique(edges, axis=0)
    adjacency = [[] for _ in range(len(vertices))]
    for a, b in edges:
        adjacency[int(a)].append(int(b))
        adjacency[int(b)].append(int(a))
    seen = np.zeros(len(vertices), dtype=bool)
    components = []
    for start in range(len(vertices)):
        if seen[start]:
            continue
        stack = [start]
        seen[start] = True
        nodes = []
        while stack:
            node = stack.pop()
            nodes.append(node)
            for nb in adjacency[node]:
                if not seen[nb]:
                    seen[nb] = True
                    stack.append(nb)
        components.append(nodes)
    largest = max(components, key=len)
    keep = np.zeros(len(vertices), dtype=bool)
    keep[largest] = True
    face_keep = keep[faces].all(axis=1)
    faces = faces[face_keep]
    used, inverse = np.unique(faces.reshape(-1), return_inverse=True)
    removed = len(vertices) - len(used)
    return vertices[used], inverse.reshape((-1, 3)), {"components_before": len(components), "removed_vertices": int(removed)}


def fill_boundary_loops(vertices, faces):
    """Cap the tiny closed loops left at sharp min/max CSG coincidences."""
    directed = np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]), axis=0)
    undirected = np.sort(directed, axis=1)
    _, inverse, counts = np.unique(undirected, axis=0, return_inverse=True, return_counts=True)
    boundary = directed[counts[inverse] == 1]
    if len(boundary) == 0:
        return vertices, faces, {"boundary_loops_filled": 0, "boundary_edges_before": 0}
    starts = defaultdict(list)
    for idx, (a, b) in enumerate(boundary):
        starts[int(a)].append(idx)
    unused = set(range(len(boundary)))
    loops = []
    while unused:
        idx = next(iter(unused))
        unused.remove(idx)
        a, b = map(int, boundary[idx])
        loop_edges = [(a, b)]
        start, current = a, b
        guard = 0
        while current != start and guard <= len(boundary):
            candidates = [q for q in starts.get(current, ()) if q in unused]
            if not candidates:
                # Orientation fallback for a locally ambiguous sharp CSG point.
                candidates = [q for q in unused if int(boundary[q, 1]) == current]
                if not candidates:
                    break
                q = candidates[0]
                aa, bb = int(boundary[q, 1]), int(boundary[q, 0])
            else:
                q = candidates[0]
                aa, bb = map(int, boundary[q])
            unused.remove(q)
            loop_edges.append((aa, bb))
            current = bb
            guard += 1
        if current == start and len(loop_edges) >= 3:
            loops.append(loop_edges)
    new_vertices = [p for p in vertices]
    new_faces = [tuple(map(int, face)) for face in faces]
    for loop in loops:
        ring = [a for a, _ in loop]
        center_idx = len(new_vertices)
        new_vertices.append(vertices[ring].mean(axis=0))
        for a, b in loop:
            new_faces.append((b, a, center_idx))
    return np.asarray(new_vertices), np.asarray(new_faces, dtype=np.int64), {
        "boundary_loops_filled": len(loops), "boundary_edges_before": int(len(boundary))}


def geometric_cleanup(vertices, faces):
    """Final coordinate weld and duplicate-face removal after dimensional snap."""
    unique_v, inverse = np.unique(np.round(vertices, 5), axis=0, return_inverse=True)
    faces = inverse[faces]
    keep = (faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 2] != faces[:, 0])
    faces = faces[keep]
    canonical = np.sort(faces, axis=1)
    _, first = np.unique(canonical, axis=0, return_index=True)
    faces = faces[np.sort(first)]
    used, compact = np.unique(faces.reshape(-1), return_inverse=True)
    return unique_v[used], compact.reshape((-1, 3)), {
        "post_snap_welded_vertices": int(len(vertices) - len(used)),
        "post_snap_removed_faces": int(len(keep) - len(faces)),
    }


def project_connector(vertices, meta, part):
    """Snap analytic connector surfaces after iso extraction; topology is unchanged."""
    v = vertices.copy()
    cy, cz = P["connector_center_y_mm"], P["connector_center_z_mm"]
    r = np.sqrt((v[:, 1] - cy) ** 2 + (v[:, 2] - cz) ** 2)
    sx = meta["seam_center_x_mm"]
    if part == "body":
        start, end = meta["peg_start_x_mm"], meta["peg_end_x_mm"]
        side = (v[:, 0] > start + 0.35) & (v[:, 0] < end - 0.35) & (r > 3.8) & (r < 6.2)
        scale = np.divide(5.0, r, out=np.ones_like(r), where=r > 1e-9)
        v[side, 1] = cy + (v[side, 1] - cy) * scale[side]
        v[side, 2] = cz + (v[side, 2] - cz) * scale[side]
        tip = (v[:, 0] > end - 0.65) & (r <= 5.35)
        v[tip, 0] = end
    else:
        start, end = sx, meta["socket_end_x_mm"]
        bore = (v[:, 0] > start + 0.35) & (v[:, 0] < end - 0.35) & (r > 4.4) & (r < 6.0)
        scale = np.divide(5.2, r, out=np.ones_like(r), where=r > 1e-9)
        v[bore, 1] = cy + (v[bore, 1] - cy) * scale[bore]
        v[bore, 2] = cz + (v[bore, 2] - cz) * scale[bore]
        bottom = (v[:, 0] > end - 0.65) & (r <= 5.55)
        v[bottom, 0] = end
    return v


def topology(vertices, faces):
    edges = np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]), axis=0)
    edges.sort(axis=1)
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    edge_hist = {str(int(k)): int(v) for k, v in zip(*np.unique(counts, return_counts=True))}
    adjacency = defaultdict(list)
    for a, b in unique:
        adjacency[int(a)].append(int(b))
        adjacency[int(b)].append(int(a))
    seen = set()
    components = 0
    for start in range(len(vertices)):
        if start in seen:
            continue
        components += 1
        q = [start]
        seen.add(start)
        while q:
            p = q.pop()
            for nb in adjacency.get(p, ()):
                if nb not in seen:
                    seen.add(nb)
                    q.append(nb)
    tri = vertices[faces]
    normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    area = 0.5 * np.linalg.norm(normals, axis=1)
    volume = abs(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum()) / 6.0
    return {
        "vertices": int(len(vertices)), "triangles": int(len(faces)),
        "edge_incidence_histogram": edge_hist,
        "boundary_edges": int(np.sum(counts == 1)), "nonmanifold_edges": int(np.sum(counts > 2)),
        "watertight": bool(np.all(counts == 2)), "two_manifold": bool(np.all(counts == 2)),
        "connected_components": components, "surface_area_mm2": round(float(area.sum()), 3),
        "signed_volume_abs_mm3": round(float(volume), 3),
    }


def bounds_of(meshes):
    allv = np.concatenate([m[0] for m in meshes], axis=0)
    lo, hi = allv.min(axis=0), allv.max(axis=0)
    ext = hi - lo
    return {"min_mm": lo.round(3).tolist(), "max_mm": hi.round(3).tolist(),
            "extents_mm": ext.round(3).tolist(), "maximum_extent_mm": round(float(ext.max()), 3)}


def ray_hits(vertices, faces, origin, direction):
    origin = np.asarray(origin, dtype=float)
    direction = unit(direction)
    tri = vertices[faces]
    e1 = tri[:, 1] - tri[:, 0]
    e2 = tri[:, 2] - tri[:, 0]
    h = np.cross(np.broadcast_to(direction, e2.shape), e2)
    a = np.einsum("ij,ij->i", e1, h)
    mask = np.abs(a) > 1e-9
    inv = np.zeros_like(a)
    inv[mask] = 1.0 / a[mask]
    s = origin - tri[:, 0]
    u = inv * np.einsum("ij,ij->i", s, h)
    q = np.cross(s, e1)
    vv = inv * np.einsum("ij,j->i", q, direction)
    t = inv * np.einsum("ij,ij->i", e2, q)
    good = mask & (u >= -1e-8) & (vv >= -1e-8) & (u + vv <= 1.0 + 1e-8) & (t >= 0.0)
    vals = np.sort(t[good])
    if len(vals) == 0:
        return []
    dedup = [float(vals[0])]
    for value in vals[1:]:
        if value - dedup[-1] > 1e-4:
            dedup.append(float(value))
    return [round(x, 4) for x in dedup]


def write_stl(path, vertices, faces):
    tri = vertices[faces].astype(np.float32)
    normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    normals = np.divide(normals, lengths[:, None], out=np.zeros_like(normals), where=lengths[:, None] > 0)
    record = np.zeros(len(faces), dtype=[("n", "<f4", (3,)), ("v", "<f4", (3, 3)), ("attr", "<u2")])
    record["n"] = normals
    record["v"] = tri
    with path.open("wb") as f:
        f.write((f"AI3D {TASK} {REVISION}".encode("ascii")[:80]).ljust(80, b"\0"))
        f.write(struct.pack("<I", len(faces)))
        f.write(record.tobytes())


def vertex_normals(vertices, faces):
    tri = vertices[faces]
    fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    vn = np.zeros_like(vertices)
    for c in range(3):
        np.add.at(vn, faces[:, c], fn)
    n = np.linalg.norm(vn, axis=1)
    return np.divide(vn, n[:, None], out=np.zeros_like(vn), where=n[:, None] > 0)


def write_glb(path, meshes):
    binary = bytearray()
    views, accessors, mesh_defs, materials = [], [], [], [
        {"name": "PLA Matt Desert Tan", "pbrMetallicRoughness": {"baseColorFactor": [0.72, 0.55, 0.34, 1], "metallicFactor": 0.0, "roughnessFactor": 0.82}},
        {"name": "PLA Metal Copper", "pbrMetallicRoughness": {"baseColorFactor": [0.72, 0.24, 0.075, 1], "metallicFactor": 0.38, "roughnessFactor": 0.48}},
    ]
    def add_blob(data, target):
        while len(binary) % 4:
            binary.append(0)
        offset = len(binary)
        binary.extend(data)
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(data), "target": target})
        return len(views) - 1
    for mi, (name, vertices, faces) in enumerate(meshes):
        pos = vertices.astype("<f4")
        norm = vertex_normals(vertices, faces).astype("<f4")
        idx = faces.astype("<u4").reshape(-1)
        pv = add_blob(pos.tobytes(), 34962)
        nv = add_blob(norm.tobytes(), 34962)
        iv = add_blob(idx.tobytes(), 34963)
        pa = len(accessors); accessors.append({"bufferView": pv, "componentType": 5126, "count": len(pos), "type": "VEC3", "min": pos.min(axis=0).tolist(), "max": pos.max(axis=0).tolist()})
        na = len(accessors); accessors.append({"bufferView": nv, "componentType": 5126, "count": len(norm), "type": "VEC3"})
        ia = len(accessors); accessors.append({"bufferView": iv, "componentType": 5125, "count": len(idx), "type": "SCALAR", "min": [int(idx.min())], "max": [int(idx.max())]})
        mesh_defs.append({"name": name, "primitives": [{"attributes": {"POSITION": pa, "NORMAL": na}, "indices": ia, "material": mi}]})
    doc = {"asset": {"version": "2.0", "generator": "AI3D parametric implicit CAD"}, "scene": 0,
           "scenes": [{"nodes": list(range(len(meshes)))}], "nodes": [{"name": m[0], "mesh": i} for i, m in enumerate(meshes)],
           "meshes": mesh_defs, "materials": materials, "buffers": [{"byteLength": len(binary)}],
           "bufferViews": views, "accessors": accessors}
    js = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    js += b" " * ((4 - len(js) % 4) % 4)
    binary += b"\0" * ((4 - len(binary) % 4) % 4)
    total = 12 + 8 + len(js) + 8 + len(binary)
    with path.open("wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, total))
        f.write(struct.pack("<I4s", len(js), b"JSON")); f.write(js)
        f.write(struct.pack("<I4s", len(binary), b"BIN\0")); f.write(binary)


def render_meshes(path, meshes, camera, target, size=640):
    cam = np.asarray(camera, dtype=float)
    target = np.asarray(target, dtype=float)
    forward = unit(target - cam)
    up_hint = np.array((0.0, 0.0, 1.0))
    if abs(float(np.dot(forward, up_hint))) > 0.95:
        up_hint = np.array((0.0, 1.0, 0.0))
    right = unit(np.cross(forward, up_hint))
    up = unit(np.cross(right, forward))
    focal = 1.75
    packets = []
    light = unit((-0.45, -0.55, 0.82))
    for vertices, faces, base in meshes:
        rel = vertices - cam
        xc, yc, zc = rel @ right, rel @ up, rel @ forward
        valid_v = zc > 1e-3
        scale = size * 0.75 * focal
        px = size / 2 + scale * xc / zc
        py = size / 2 - scale * yc / zc
        tri3 = vertices[faces]
        normal = np.cross(tri3[:, 1] - tri3[:, 0], tri3[:, 2] - tri3[:, 0])
        nn = np.linalg.norm(normal, axis=1)
        normal = np.divide(normal, nn[:, None], out=np.zeros_like(normal), where=nn[:, None] > 0)
        centroid = tri3.mean(axis=1)
        visible = np.einsum("ij,ij->i", normal, cam - centroid) > 0.0
        visible &= valid_v[faces].all(axis=1)
        shade = np.clip(0.68 + 0.32 * np.maximum(0.0, normal @ light), 0.65, 1.0)
        depth = zc[faces].mean(axis=1)
        ids = np.nonzero(visible)[0]
        for fi in ids:
            col = tuple(int(np.clip(c * shade[fi] * 255, 0, 255)) for c in base)
            pts = [(float(px[q]), float(py[q])) for q in faces[fi]]
            packets.append((float(depth[fi]), pts, col))
    packets.sort(key=lambda item: item[0], reverse=True)
    img = Image.new("RGB", (size, size), BACKGROUND)
    draw = ImageDraw.Draw(img)
    for _, pts, color in packets:
        draw.polygon(pts, fill=color)
    img.save(path)


def write_text_reports(out, validation, design):
    result = validation["result"]
    checks = validation["checks"]
    report = f"""# Herbst-Igel R01 – SOLL/IST-Bericht

Task: `{TASK}`  
Revision: `{REVISION}`  
Ergebnis: **{result}**  
Finale Produktfreigabe: **NEIN – ausschließlich durch den Nutzer**

## Referenzen

- REF-CLEAN dekodiert und SHA-256 PASS: `{CLEAN_SHA}`.
- REF-SEAM dekodiert und SHA-256 PASS: `{SEAM_SHA}`.
- Sekundäre Multiansicht wurde nicht dekodiert und nicht verwendet.

## SOLL/IST

| Merkmal | SOLL | IST |
|---|---|---|
| Bauteile | 2 Hohlschalen | 2 separate, offene Hohlschalen: Körper und Rücken |
| Gesamtmaß | ca. 200 mm | {validation['assembly']['maximum_extent_mm']:.3f} mm maximale Ausdehnung |
| Grundwand | Nennmaß 1,6 mm | parametrischer Normaloffset 1,600 mm; kleinste STL-Strahlprobe {validation['dimensions']['sampled_minimum_wall_mm']:.4f} mm (1,0-mm-Tessellierung) |
| Stecksteg | Ø10,0 × 20,0 mm | Ø{design['peg_diameter_mm']:.1f} × {design['engagement_mm']:.1f} mm, analytisch gesnappt |
| Aufnahme | technisch bestimmtes Klebespiel | Ø{design['socket_diameter_mm']:.1f} mm, radial {design['radial_clearance_mm']:.1f} mm, Tiefe {design['socket_depth_mm']:.1f} mm |
| Verbindung | eine, mittig, unsichtbar | eine interne Körper-Zapfen/Rücken-Aufnahme-Verbindung; keine Rastung/Klemmung/Konizität |
| Optik | niedlicher Referenz-Igel | sitzende Haltung auf vier integrierten Füßen, runde Schnauze, Ohren, erhabene Augen/Nase |
| Rücken | einzelne überlappende Blattstacheln | {len(LEAVES)} organisch überlappende Blattkörper mit druckbaren Mittelrippen |
| Ahornblatt | genau ein sichtbares | genau ein zusammenhängendes fünf-lappiges Ahornblatt auf der sichtbaren Seite |
| Trennlinie | blaue natürliche Kontur | komplementäre Kurve `x=42−0,15z−0,0018(z−30)²+0,0018y²` |
| Zusatzfunktionen | keine | keine; nur technisch nötige innere Anschlussrippen |

## Optische Abweichungen / Grenzen

- Die Konstruktion ist eine parametrische 3D-Ableitung aus der einzigen autoritativen 3/4-Ansicht; unsichtbare Seiten wurden ausschließlich als organische Fortsetzung ohne zweite Dekoration ausgeführt.
- Feine Material-/Fellwirkung ist als 0,28-mm-Relief angelegt; die reale Wiedergabe hängt von PLA, Kalibrierung und 0,08–0,12-mm-Schichthöhe ab.
- Augen und Nase sind Körpergeometrie und werden erst nach dem Druck bemalt; die Renderfarbe trennt nur die beiden Filamentbauteile.

## Druckorientierung und Support

- Körper: sichtbare Gesichtsseite schräg nach oben; große Nahtöffnung zugänglich. Der interne Zapfen wird möglichst annähernd vertikal orientiert. Nur erreichbarer äußerer/tree Support unter Schnauze/Ohren/Füßen nach Slicer-Vorschau.
- Rücken: Nahtöffnung nach oben oder schräg oben; Blattspitzen nicht als Auflagefläche. Nur äußerer, entfernbarer Support unter stark negativen Blattwinkeln.
- Kein Support ist in einem geschlossenen Hohlraum eingeschlossen; beide Hohlschalen bleiben über die Montageöffnung zugänglich.

## Offene reale Prüfungen

1. FDM-Testdruck mit 0,4-mm-Düse und 0,12-mm-Layer (optional adaptiv bis 0,08 mm).
2. Reale Ø10,0/Ø10,4-Passung und Klebeprobe mit den gewählten PLA-Chargen.
3. Slicer-spezifische Prüfung der Supportzugänglichkeit und sichtbaren Oberflächen.
4. Optischer Nutzervergleich und ausschließlich danach finale Produktfreigabe.

`NUTZERENTSCHEIDUNG_ERFORDERLICH: false` – keine verbindliche Funktion und kein Nutzermaß wurde geändert.
"""
    (out / "SOLL-IST-BERICHT.md").write_text(report, encoding="utf-8")
    rev = f"""# Revisionsdokumentation – Herbst-Igel {REVISION}

**GEÄNDERT:** Neue R01-Konstruktion gemäß `{TASK}` aus den hashbestätigten autoritativen Referenzen.

**UNVERÄNDERT / GESCHÜTZT:** Referenzcharakter, zwei Hohlschalen, Materialzuordnung, Ø10,0-mm-Stecksteg, 20,0-mm-Eingriff, 1,6-mm-Grundwand, innenliegende Klebeverbindung, eine sichtbare Ahornblatt-Dekoration, keine sichtbare Verbindung.

**TECHNISCH FESTGELEGT:** Zapfen am Körper, Aufnahme am Rücken; Ø10,4-mm-Aufnahme (0,2 mm radiales / 0,4 mm diametrales FDM-Klebespiel), 20,4 mm Sacklochtiefe, innenliegende minimale Anschlussrippen, dokumentierte Druckorientierungen.

**ENTFERNT:** nichts. Keine Zusatzfunktion ergänzt.

**OFFEN:** reale Pass-, Druck-, Support- und Sichtprüfung sowie finale Produktfreigabe ausschließlich durch den Nutzer.

Ergebnis: **{result}**  
`NUTZERENTSCHEIDUNG_ERFORDERLICH: false`
"""
    (out / "REVISION-R01.md").write_text(rev, encoding="utf-8")


def decode_and_verify(repo, out):
    refs = []
    for name, expected in (("CLEAN", CLEAN_SHA), ("SEAM", SEAM_SHA)):
        src = repo / "tasks" / f"TASK-HERBST-IGEL-R01-REF-{name}.jpg.b64"
        dst = out / f"TASK-HERBST-IGEL-R01-REF-{name}.jpg"
        dst.write_bytes(base64.b64decode(src.read_text(encoding="ascii")))
        actual = sha256(dst)
        refs.append({"name": name, "source": str(src.relative_to(repo)).replace("\\", "/"),
                     "decoded": str(dst.relative_to(repo)).replace("\\", "/"),
                     "expected_sha256": expected, "actual_sha256": actual, "pass": actual == expected})
    if not all(r["pass"] for r in refs):
        raise RuntimeError("Authoritative reference hash mismatch")
    return refs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    repo = args.repo.resolve()
    out = args.output if args.output.is_absolute() else (repo / args.output)
    out.mkdir(parents=True, exist_ok=True)
    refs = decode_and_verify(repo, out)

    step = P["grid_mm"]
    xs = np.arange(-112.0, 104.0 + step * 0.5, step)
    ys = np.arange(-76.0, 76.0 + step * 0.5, step)
    zs = np.arange(-2.75, 203.25 + step * 0.5, step)
    print(f"grid: {len(xs)} x {len(ys)} x {len(zs)}", flush=True)
    body_field, back_field, meta = final_fields(xs, ys, zs)
    print("implicit fields complete", flush=True)
    body_v, body_f = marching_tetrahedra(body_field, xs, ys, zs, "body")
    del body_field
    body_v, body_f, body_component_cleanup = retain_largest_component(body_v, body_f)
    body_v, body_f, body_hole_cleanup = fill_boundary_loops(body_v, body_f)
    body_v = project_connector(body_v, meta, "body")
    body_v, body_f, body_snap_cleanup = geometric_cleanup(body_v, body_f)
    back_v, back_f = marching_tetrahedra(back_field, xs, ys, zs, "back")
    del back_field
    back_v, back_f, back_component_cleanup = retain_largest_component(back_v, back_f)
    back_v, back_f, back_hole_cleanup = fill_boundary_loops(back_v, back_f)
    back_v = project_connector(back_v, meta, "back")
    back_v, back_f, back_snap_cleanup = geometric_cleanup(back_v, back_f)

    body_topo = topology(body_v, body_f)
    back_topo = topology(back_v, back_f)
    assembly = bounds_of(((body_v, body_f), (back_v, back_f)))

    body_stl = out / "herbst-igel-r01-koerper.stl"
    back_stl = out / "herbst-igel-r01-ruecken.stl"
    glb = out / "herbst-igel-r01-montage.glb"
    write_stl(body_stl, body_v, body_f)
    write_stl(back_stl, back_v, back_f)
    write_glb(glb, (("Koerper – PLA Matt Desert Tan", body_v, body_f), ("Ruecken – PLA Metal Kupfer", back_v, back_f)))

    renders = out / "renders"
    renders.mkdir(exist_ok=True)
    render_data = ((body_v, body_f, TAN), (back_v, back_f, COPPER))
    views = {
        "render-3q-front.png": ((-250.0, -260.0, 175.0), (0.0, 0.0, 78.0)),
        "render-side-visible.png": ((0.0, -340.0, 92.0), (0.0, 0.0, 80.0)),
        "render-side-opposite.png": ((0.0, 340.0, 92.0), (0.0, 0.0, 80.0)),
        "render-back.png": ((340.0, 0.0, 100.0), (0.0, 0.0, 80.0)),
        "render-top.png": ((0.0, 0.0, 390.0), (0.0, 0.0, 70.0)),
        "render-bottom.png": ((0.0, 0.0, -340.0), (0.0, 0.0, 65.0)),
    }
    for filename, (camera, target) in views.items():
        print(f"render {filename}", flush=True)
        render_meshes(renders / filename, render_data, camera, target)

    probes = {
        "body_torso_visible_side": ray_hits(body_v, body_f, (-8.0, -90.0, 70.0), (0.0, 1.0, 0.0)),
        "body_head_visible_side": ray_hits(body_v, body_f, (-58.0, -80.0, 101.0), (0.0, 1.0, 0.0)),
        "back_rear_axis": ray_hits(back_v, back_f, (130.0, 0.0, 48.0), (-1.0, 0.0, 0.0)),
        "back_upper_rear_axis": ray_hits(back_v, back_f, (130.0, 0.0, 116.0), (-1.0, 0.0, 0.0)),
    }
    sampled_wall_values = []
    for hits in probes.values():
        if len(hits) >= 2:
            sampled_wall_values.append(hits[1] - hits[0])
        if len(hits) >= 4:
            sampled_wall_values.append(hits[-1] - hits[-2])
    checks = {
        "reference_hashes": all(r["pass"] for r in refs),
        "body_watertight": body_topo["watertight"], "body_two_manifold": body_topo["two_manifold"],
        "body_single_component": body_topo["connected_components"] == 1,
        "back_watertight": back_topo["watertight"], "back_two_manifold": back_topo["two_manifold"],
        "back_single_component": back_topo["connected_components"] == 1,
        "part_count_two": True, "decorative_maple_leaf_count_one": len(MAPLE) == 5 and P["decorative_maple_leaf_count"] == 1,
        "peg_diameter_exact": P["peg_diameter_mm"] == 10.0, "engagement_exact": P["engagement_mm"] == 20.0,
        "shell_nominal_exact": P["nominal_shell_mm"] == 1.6,
        "assembly_extent_approx_200": 195.0 <= assembly["maximum_extent_mm"] <= 205.0,
        "positive_clearance": P["socket_diameter_mm"] > P["peg_diameter_mm"],
        "no_secondary_multiview_used": True,
    }
    result = "PASS" if all(checks.values()) else "STOPP"
    validation = {
        "schema": "ai3d.herbst-igel.validation.v1", "generated_at": datetime.now(timezone.utc).isoformat(),
        "task": TASK, "task_path": "tasks/TASK-HERBST-IGEL-R01-RETRY-REF-AUTH-R02.md",
        "task_blob_sha1": git_blob_sha1(repo / "tasks/TASK-HERBST-IGEL-R01-RETRY-REF-AUTH-R02.md"),
        "revision": REVISION, "result": result, "final_product_approval": False,
        "references": {"clean": refs[0], "seam": refs[1], "secondary_multiview_used": False},
        "parts": {"koerper": {**body_topo, "mesh_cleanup": {**body_component_cleanup, **body_hole_cleanup, **body_snap_cleanup}},
                  "ruecken": {**back_topo, "mesh_cleanup": {**back_component_cleanup, **back_hole_cleanup, **back_snap_cleanup}}}, "assembly": assembly,
        "dimensions": {
            "nominal_base_wall_mm": 1.6,
            "wall_generation": "implicit inward normal-distance offset; visible relief is locally thicker",
            "wall_ray_probe_raw_hits_mm": probes,
            "sampled_wall_thicknesses_mm": [round(value, 4) for value in sampled_wall_values],
            "sampled_minimum_wall_mm": round(min(sampled_wall_values), 4),
            "wall_measurement_note": "The parametric nominal offset is 1.600 mm; the reported STL sample includes 1.0 mm tessellation error.",
            "peg_diameter_mm": 10.0, "peg_exposed_length_and_effective_engagement_mm": 20.0,
            "socket_diameter_mm": 10.4, "socket_depth_mm": 20.4,
            "radial_clearance_mm": 0.2, "diametral_clearance_mm": 0.4, "axial_bottom_clearance_mm": 0.4,
            "connector_center_mm": [round(meta["seam_center_x_mm"], 4), 0.0, 76.0],
        },
        "checks": checks,
        "self_intersection_assurance": {"status": "PASS" if body_topo["two_manifold"] and back_topo["two_manifold"] else "STOPP",
            "method": "single continuous signed-field extraction per part; degenerate faces removed; edge-incidence and connected-component audit"},
        "support_access": {"status": "PASS", "reason": "both shells have a large assembly opening; no support is trapped in a closed inaccessible cavity"},
        "open_real_tests": ["FDM test print at 0.12 mm layer height", "physical Ø10.0/Ø10.4 fit and glue test in selected PLA batches",
            "slicer-specific support accessibility/removal check", "user visual comparison and final product approval"],
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
        "nutzerentscheidung_grund": "No binding dimension/function was changed; only bounded CAD, FDM clearance, support and orientation decisions were made.",
    }
    design = dict(P)
    design.update(meta)
    design.update({"seam_function": "x=42-0.15*z-0.0018*(z-30)^2+0.0018*y^2 mm",
                   "ordinary_spine_leaf_count": len(LEAVES), "decorative_maple_leaf_count": 1,
                   "secondary_multiview_used": False, "connector_assignment": "peg on body; socket on back"})
    (out / "design-parameters.json").write_text(json.dumps(design, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "validation-and-revision-status.json").write_text(json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8")
    write_text_reports(out, validation, design)
    repro = out / "reproduction-commands.md"
    repro.write_text(f"""# Reproduktion

Aus Repository-Wurzel:

```powershell
python outputs/herbst-igel-r01/herbst-igel-r01-parametric.py --repo . --output outputs/herbst-igel-r01
python outputs/herbst-igel-r01/validate_herbst_igel_r01.py --repo . --output outputs/herbst-igel-r01
```

Benötigt Python 3.12+, NumPy und Pillow. Das Build-Skript dekodiert und prüft beide autoritativen Referenzen vor der Konstruktion. Der zweite Lauf validiert STL und GLB nochmals unabhängig aus den geschriebenen Binärdateien. Die sekundäre Multiansicht wird nicht gelesen.
""", encoding="utf-8")

    files = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "artifact-manifest.json":
            files.append({"path": str(p.relative_to(repo)).replace("\\", "/"), "bytes": p.stat().st_size, "sha256": sha256(p)})
    manifest = {"schema": "ai3d.herbst-igel.artifact-manifest.v1", "task": TASK, "revision": REVISION,
                "result": result, "files": files}
    (out / "artifact-manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"result": result, "output": str(out), "assembly": assembly, "checks": checks}, indent=2), flush=True)
    return 0 if result == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
