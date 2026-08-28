#!/usr/bin/env python3
"""Read-only Phase-4 component inventory and diagnostic atlas.

The input mesh is never modified or exported.  The script loads an existing
working copy, reconstructs shared-vertex connectivity in memory, and writes
only reports and PNG diagnostics to the requested output directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
import trimesh


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def face_component_labels(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """Return a connected-component label for every face."""
    a, b, c = faces.T
    rows = np.concatenate((a, b, a, c))
    cols = np.concatenate((b, a, c, a))
    graph = coo_matrix(
        (np.ones(len(rows), dtype=np.uint8), (rows, cols)),
        shape=(len(vertices), len(vertices)),
    ).tocsr()
    _, vertex_labels = connected_components(graph, directed=False)
    raw = vertex_labels[faces[:, 0]]
    _, compact = np.unique(raw, return_inverse=True)
    return compact.astype(np.int32, copy=False)


def extract_component(
    vertices: np.ndarray, faces: np.ndarray, face_ids: np.ndarray
) -> trimesh.Trimesh:
    selected = faces[face_ids]
    used, inverse = np.unique(selected.reshape(-1), return_inverse=True)
    local_faces = inverse.reshape((-1, 3))
    return trimesh.Trimesh(
        vertices=vertices[used].copy(), faces=local_faces, process=False
    )


def edge_metrics(faces: np.ndarray) -> dict[str, Any]:
    edges = np.concatenate(
        (faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]), axis=0
    )
    edges.sort(axis=1)
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    boundary = int(np.count_nonzero(counts == 1))
    nonmanifold = int(np.count_nonzero(counts > 2))
    return {
        "unique_edges": int(len(unique)),
        "boundary_edges": boundary,
        "nonmanifold_edges": nonmanifold,
        "max_edge_incidence": int(counts.max(initial=0)),
        "edge_manifold_allow_boundary": nonmanifold == 0,
        "closed_two_manifold": boundary == 0 and nonmanifold == 0,
    }


def vertex_link_metrics(faces: np.ndarray, vertex_count: int) -> dict[str, Any]:
    """Check whether every incident-face fan is one cycle or one boundary path."""
    incident: list[list[int]] = [[] for _ in range(vertex_count)]
    for face_id, face in enumerate(faces):
        incident[int(face[0])].append(face_id)
        incident[int(face[1])].append(face_id)
        incident[int(face[2])].append(face_id)
    invalid_vertices = 0
    disconnected_fans = 0
    invalid_boundary_degree = 0
    for vertex_id, face_ids in enumerate(incident):
        if not face_ids:
            continue
        neighbor_to_faces: dict[int, list[int]] = {}
        for face_id in face_ids:
            for neighbor in faces[face_id]:
                neighbor_id = int(neighbor)
                if neighbor_id != vertex_id:
                    neighbor_to_faces.setdefault(neighbor_id, []).append(face_id)
        if any(len(items) > 2 for items in neighbor_to_faces.values()):
            invalid_vertices += 1
            continue
        boundary_neighbors = sum(len(items) == 1 for items in neighbor_to_faces.values())
        if boundary_neighbors not in (0, 2):
            invalid_boundary_degree += 1
            invalid_vertices += 1
            continue
        adjacency: dict[int, set[int]] = {face_id: set() for face_id in face_ids}
        for items in neighbor_to_faces.values():
            if len(items) == 2:
                adjacency[items[0]].add(items[1])
                adjacency[items[1]].add(items[0])
        stack = [face_ids[0]]
        reached: set[int] = set()
        while stack:
            current = stack.pop()
            if current in reached:
                continue
            reached.add(current)
            stack.extend(adjacency[current] - reached)
        if len(reached) != len(face_ids):
            disconnected_fans += 1
            invalid_vertices += 1
    return {
        "vertex_link_manifold_allow_boundary": invalid_vertices == 0,
        "nonmanifold_vertex_links": int(invalid_vertices),
        "disconnected_vertex_fans": int(disconnected_fans),
        "invalid_vertex_boundary_degree": int(invalid_boundary_degree),
    }


def component_fingerprint(mesh: trimesh.Trimesh) -> str:
    """Geometry-only stable ID for the exact float32 STL component."""
    triangles = np.asarray(mesh.triangles, dtype="<f4")
    # Canonicalize vertex order inside each triangle, then triangle order.
    canonical = np.empty_like(triangles)
    for i, triangle in enumerate(triangles):
        order = np.lexsort((triangle[:, 2], triangle[:, 1], triangle[:, 0]))
        canonical[i] = triangle[order]
    flat = canonical.reshape((len(canonical), 9))
    order = np.lexsort(tuple(flat[:, column] for column in range(8, -1, -1)))
    return hashlib.sha256(flat[order].tobytes()).hexdigest()


def position_phrase(center: np.ndarray, global_bounds: np.ndarray) -> str:
    minimum, maximum = global_bounds
    span = np.maximum(maximum - minimum, 1e-12)
    normalized = (center - minimum) / span

    def bucket(value: float, low: str, middle: str, high: str) -> str:
        if value < 0.36:
            return low
        if value > 0.64:
            return high
        return middle

    return ", ".join(
        (
            bucket(float(normalized[0]), "links", "mittig-x", "rechts"),
            bucket(float(normalized[1]), "unten", "mittig-y", "oben"),
            bucket(float(normalized[2]), "hinten", "mittig-z", "vorn"),
        )
    )


def load_labels(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None:
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("Label JSON must be an object keyed by component rank")
    return {str(key): dict(item) for key, item in value.items()}


def sampled_face_ids(face_ids: np.ndarray, limit: int) -> np.ndarray:
    if len(face_ids) <= limit:
        return face_ids
    offsets = np.linspace(0, len(face_ids) - 1, limit, dtype=np.int64)
    return face_ids[offsets]


def plot_vertices(vertices: np.ndarray) -> np.ndarray:
    """Map model (x,y-up,z-front) to matplotlib (x,z-front,y-up)."""
    return vertices[:, [0, 2, 1]]


def set_equal_axes(ax: Any, bounds: np.ndarray, margin: float = 0.04) -> None:
    minimum = bounds[0].copy()
    maximum = bounds[1].copy()
    extents = maximum - minimum
    pad = max(float(extents.max()) * margin, 1e-6)
    minimum -= pad
    maximum += pad
    mapped_min = minimum[[0, 2, 1]]
    mapped_max = maximum[[0, 2, 1]]
    ax.set_xlim(mapped_min[0], mapped_max[0])
    ax.set_ylim(mapped_min[1], mapped_max[1])
    ax.set_zlim(mapped_min[2], mapped_max[2])
    ax.set_box_aspect(mapped_max - mapped_min)
    ax.set_axis_off()


def add_mesh_faces(
    ax: Any,
    vertices: np.ndarray,
    faces: np.ndarray,
    face_ids: np.ndarray,
    color: Any,
    alpha: float,
    limit: int,
    linewidth: float = 0.0,
) -> None:
    chosen = sampled_face_ids(face_ids, limit)
    triangles = plot_vertices(vertices)[faces[chosen]]
    collection = Poly3DCollection(
        triangles,
        facecolors=color,
        edgecolors=(0.0, 0.0, 0.0, min(alpha, 0.12)) if linewidth else "none",
        linewidths=linewidth,
        alpha=alpha,
    )
    ax.add_collection3d(collection)


def render_component_map(
    path: Path,
    vertices: np.ndarray,
    faces: np.ndarray,
    face_labels: np.ndarray,
    order: np.ndarray,
    components: list[dict[str, Any]],
    bounds: np.ndarray,
) -> None:
    colors = plt.get_cmap("tab20")(np.linspace(0.0, 1.0, len(order)))
    views = [
        ("Front (+Z)", 0.0, 90.0),
        ("Back (-Z)", 0.0, -90.0),
        ("Perspective", 20.0, 125.0),
    ]
    figure = plt.figure(figsize=(21, 8), dpi=180)
    for panel, (title, elev, azim) in enumerate(views, start=1):
        ax = figure.add_subplot(1, 3, panel, projection="3d")
        for rank, raw_label in enumerate(order, start=1):
            ids = np.flatnonzero(face_labels == raw_label)
            per_component = max(350, int(62000 * len(ids) / len(faces)))
            add_mesh_faces(
                ax,
                vertices,
                faces,
                ids,
                colors[rank - 1],
                0.96,
                per_component,
            )
            center = np.asarray(components[rank - 1]["bounds_center"], dtype=float)
            point = center[[0, 2, 1]]
            ax.text(
                point[0], point[1], point[2], str(rank), color="black", fontsize=7,
                ha="center", va="center",
                bbox={"boxstyle": "circle,pad=0.16", "fc": "white", "ec": colors[rank - 1], "lw": 1.5},
            )
        ax.view_init(elev=elev, azim=azim)
        set_equal_axes(ax, bounds)
        ax.set_title(title, fontsize=13, weight="bold")
    figure.suptitle(
        "Phase 4A – 19 connected components (analysis only)",
        fontsize=16,
        weight="bold",
    )
    figure.tight_layout(rect=(0, 0, 1, 0.95))
    figure.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def render_component_zoom_atlas(
    path: Path,
    meshes: list[trimesh.Trimesh],
    components: list[dict[str, Any]],
) -> None:
    colors = plt.get_cmap("tab20")(np.linspace(0.0, 1.0, len(meshes)))
    figure = plt.figure(figsize=(20, 25), dpi=170)
    for rank, (mesh, metadata) in enumerate(zip(meshes, components), start=1):
        ax = figure.add_subplot(5, 4, rank, projection="3d")
        ids = np.arange(len(mesh.faces), dtype=np.int64)
        add_mesh_faces(
            ax,
            np.asarray(mesh.vertices),
            np.asarray(mesh.faces),
            ids,
            colors[rank - 1],
            0.98,
            6500,
            linewidth=0.08,
        )
        ax.view_init(elev=18.0, azim=125.0)
        set_equal_axes(ax, np.asarray(mesh.bounds), margin=0.12)
        ax.set_title(
            f"#{rank:02d} · {metadata['faces']:,} F · {metadata['surface_percent']:.4f}%\n"
            f"center {np.round(metadata['bounds_center'], 3).tolist()}",
            fontsize=9,
        )
    figure.suptitle(
        "Phase 4A – component zoom atlas (each panel independently scaled)",
        fontsize=16,
        weight="bold",
    )
    figure.tight_layout(rect=(0, 0, 1, 0.97))
    figure.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def render_centers_map(
    path: Path,
    components: list[dict[str, Any]],
    bounds: np.ndarray,
) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(18, 6), dpi=180)
    projections = [
        (0, 1, "Front map: X / Y", "X: left ↔ right", "Y: bottom ↔ top"),
        (2, 1, "Side map: Z / Y", "Z: back ↔ front", "Y: bottom ↔ top"),
        (0, 2, "Top map: X / Z", "X: left ↔ right", "Z: back ↔ front"),
    ]
    colors = plt.get_cmap("tab20")(np.linspace(0.0, 1.0, len(components)))
    for ax, (u, v, title, xlabel, ylabel) in zip(axes, projections):
        for rank, component in enumerate(components, start=1):
            center = np.asarray(component["bounds_center"])
            extents = np.asarray(component["extents"])
            ax.scatter(center[u], center[v], s=max(28, 850 * math.sqrt(component["surface_fraction"])), color=colors[rank - 1], edgecolor="black", linewidth=0.4)
            ax.text(center[u], center[v], str(rank), fontsize=7, ha="center", va="center")
            rectangle = plt.Rectangle(
                (center[u] - extents[u] * 0.5, center[v] - extents[v] * 0.5),
                extents[u], extents[v], fill=False, color=colors[rank - 1], lw=0.7, alpha=0.65,
            )
            ax.add_patch(rectangle)
        ax.set_xlim(bounds[0, u], bounds[1, u])
        ax.set_ylim(bounds[0, v], bounds[1, v])
        ax.set_aspect("equal", adjustable="box")
        ax.grid(True, color="#dddddd", lw=0.6)
        ax.set_title(title, weight="bold")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
    figure.suptitle("Component bounding boxes and centers", fontsize=15, weight="bold")
    figure.tight_layout(rect=(0, 0, 1, 0.94))
    figure.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mesh", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--expected-components", type=int, default=19)
    args = parser.parse_args()

    mesh_path = args.mesh.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    labels = load_labels(args.labels)

    loaded = trimesh.load(mesh_path, force="mesh", process=True)
    if not isinstance(loaded, trimesh.Trimesh):
        raise TypeError(f"Expected a Trimesh, got {type(loaded)!r}")
    vertices = np.asarray(loaded.vertices, dtype=np.float64)
    faces = np.asarray(loaded.faces, dtype=np.int64)
    face_labels = face_component_labels(vertices, faces)
    counts = np.bincount(face_labels)
    order = np.argsort(counts)[::-1]
    if len(order) != args.expected_components:
        raise RuntimeError(
            f"Expected {args.expected_components} components, found {len(order)}"
        )

    face_areas = np.asarray(loaded.area_faces, dtype=np.float64)
    component_areas = np.bincount(face_labels, weights=face_areas)
    total_area = float(component_areas.sum())
    global_bounds = np.asarray(loaded.bounds, dtype=np.float64)
    component_meshes: list[trimesh.Trimesh] = []
    component_rows: list[dict[str, Any]] = []

    for rank, raw_label in enumerate(order, start=1):
        face_ids = np.flatnonzero(face_labels == raw_label)
        submesh = extract_component(vertices, faces, face_ids)
        component_meshes.append(submesh)
        minimum, maximum = np.asarray(submesh.bounds, dtype=np.float64)
        edges = edge_metrics(np.asarray(submesh.faces, dtype=np.int64))
        vertex_links = vertex_link_metrics(
            np.asarray(submesh.faces, dtype=np.int64), len(submesh.vertices)
        )
        semantic = labels.get(str(rank), {})
        row: dict[str, Any] = {
            "id": rank,
            "stable_geometry_id": f"c{rank:02d}-{component_fingerprint(submesh)[:16]}",
            "vertices": int(len(submesh.vertices)),
            "faces": int(len(submesh.faces)),
            "surface_area": float(submesh.area),
            "surface_fraction": float(submesh.area / total_area),
            "surface_percent": float(100.0 * submesh.area / total_area),
            "bounds_min": minimum.tolist(),
            "bounds_max": maximum.tolist(),
            "extents": (maximum - minimum).tolist(),
            "bounds_center": ((minimum + maximum) * 0.5).tolist(),
            "centroid": np.asarray(submesh.centroid, dtype=np.float64).tolist(),
            "oriented_signed_volume": float(submesh.volume),
            "absolute_oriented_volume": float(abs(submesh.volume)),
            "watertight": bool(submesh.is_watertight),
            "is_volume": bool(submesh.is_volume),
            "winding_consistent": bool(submesh.is_winding_consistent),
            **edges,
            **vertex_links,
            "spatial_position": position_phrase((minimum + maximum) * 0.5, global_bounds),
            "classification": semantic.get("classification", "unbekannt"),
            "inferred_function": semantic.get("inferred_function", "visuell noch zuzuordnen"),
            "classification_confidence": semantic.get("confidence", "offen"),
        }
        component_rows.append(row)
        print(
            f"#{rank:02d} {row['stable_geometry_id']} "
            f"V={row['vertices']} F={row['faces']} area={row['surface_percent']:.6f}% "
            f"watertight={row['watertight']} closed2m={row['closed_two_manifold']} "
            f"center={np.round(row['bounds_center'], 4).tolist()}",
            flush=True,
        )

    report = {
        "schema": "ai3d.phase4.component-inventory.v1",
        "analysis_only": True,
        "mesh_mutated": False,
        "source": {
            "path": str(mesh_path),
            "bytes": mesh_path.stat().st_size,
            "sha256": sha256(mesh_path),
            "load_mode": "trimesh process=True in memory; no export",
        },
        "coordinate_system": {"x": "left/right", "y": "up", "z": "front (+Z)"},
        "global": {
            "vertices": int(len(vertices)),
            "faces": int(len(faces)),
            "component_count": int(len(order)),
            "surface_area": total_area,
            "bounds_min": global_bounds[0].tolist(),
            "bounds_max": global_bounds[1].tolist(),
            "extents": (global_bounds[1] - global_bounds[0]).tolist(),
        },
        "components": component_rows,
    }
    atomic_json(output_dir / "phase4-component-inventory.json", report)
    render_component_map(
        output_dir / "phase4-component-map.png",
        vertices,
        faces,
        face_labels,
        order,
        component_rows,
        global_bounds,
    )
    render_component_zoom_atlas(
        output_dir / "phase4-component-zoom-atlas.png", component_meshes, component_rows
    )
    render_centers_map(
        output_dir / "phase4-component-centers-bounds.png", component_rows, global_bounds
    )
    print(f"report={output_dir / 'phase4-component-inventory.json'}")


if __name__ == "__main__":
    main()
