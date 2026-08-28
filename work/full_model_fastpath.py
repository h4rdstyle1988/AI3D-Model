#!/usr/bin/env python3
"""Build and fast-validate the 0.5 mm C01 + selected-tail candidate.

This is a non-destructive candidate builder.  It never edits the source STL,
the frozen C01 smoke result, or any Phase-4 artifact.  It deliberately excludes
the C07/C09 duplicate skins and uses two small local capsules to connect the
visible C05/C08 tail parts before a single joint voxel reconstruction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import numpy as np
import trimesh
from scipy import ndimage
from trimesh.voxel import ops as voxel_ops

from phase4_component_atlas import extract_component, face_component_labels
from smoke_layer_slice_audit import audit_mesh
from smoke_single_solid import (
    atomic_bytes,
    atomic_json,
    atomic_npz,
    load_3mf,
    topology,
    topology_gate,
    write_3mf,
)
from v002_prebuild_c01_analysis import self_events

SOURCE_SHA256 = "58f6a915c53b587e8e796283b1750bd0c060104a90b4616c935c6ccc70771a7d"
FROZEN_SMOKE_SHA256 = "df3ccf828dce355a0df611919eccd135179775a7346ed86d178234f63a4e89ab"
TARGET_HEIGHT_MM = 190.0
PITCH_MM = 0.5
PREFIX = "full-model-fastpath-0500um-CANDIDATE"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def peak_rss_bytes() -> int:
    # Linux ru_maxrss is KiB; this runner is intentionally WSL-only.
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)


class Profiler:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self.logical_cpus = max(1, os.cpu_count() or 1)
        self.started = time.perf_counter()

    @contextmanager
    def stage(self, name: str):
        wall0 = time.perf_counter()
        cpu0 = time.process_time()
        rss0 = peak_rss_bytes()
        yield
        wall = time.perf_counter() - wall0
        cpu = time.process_time() - cpu0
        self.rows[name] = {
            "wall_seconds": wall,
            "process_cpu_seconds": cpu,
            "process_cpu_equivalent_cores": cpu / wall if wall else 0.0,
            "estimated_whole_machine_cpu_percent": 100.0 * cpu / wall / self.logical_cpus if wall else 0.0,
            "peak_rss_bytes_after_stage": peak_rss_bytes(),
            "peak_rss_growth_bytes": max(0, peak_rss_bytes() - rss0),
        }

    def summary(self) -> dict[str, Any]:
        return {
            "stages": self.rows,
            "total_wall_seconds": time.perf_counter() - self.started,
            "peak_rss_bytes": peak_rss_bytes(),
            "logical_cpu_count": self.logical_cpus,
            "gpu_utilization": {
                "status": "NOT_MEASURED",
                "reason": "The production voxel/mesh path is CPU-only; WSL amd-smi/rocm-smi cannot read utilization through /dev/dxg.",
            },
        }


def load_scaled_components(source: Path) -> tuple[list[trimesh.Trimesh], dict[str, Any]]:
    if sha256(source).lower() != SOURCE_SHA256:
        raise RuntimeError("Source SHA-256 mismatch; refusing to build from an unapproved source")
    mesh = trimesh.load(source, force="mesh", process=True)
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    labels = face_component_labels(vertices, faces)
    order = sorted(
        range(int(labels.max()) + 1),
        key=lambda value: int(np.count_nonzero(labels == value)),
        reverse=True,
    )
    components = [extract_component(vertices, faces, np.flatnonzero(labels == raw_label)) for raw_label in order]
    if len(components) != 19:
        raise RuntimeError(f"Expected exactly 19 processed components, got {len(components)}")
    scale = TARGET_HEIGHT_MM / float(np.ptp(components[0].bounds[:, 1]))
    for part in components:
        part.apply_scale(scale)
    record = {
        "path": str(source),
        "sha256": SOURCE_SHA256,
        "processed_component_count": len(components),
        "millimeters_per_source_unit": scale,
        "target_C01_height_mm": TARGET_HEIGHT_MM,
    }
    return components, record


def capsule_between(a: np.ndarray, b: np.ndarray, radius: float, sections: int = 32) -> trimesh.Trimesh:
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    vector = b - a
    length = float(np.linalg.norm(vector))
    if length <= 0:
        raise ValueError("Capsule endpoints must differ")
    align = trimesh.geometry.align_vectors([0.0, 0.0, 1.0], vector / length)
    align[:3, 3] = (a + b) / 2.0
    cylinder = trimesh.creation.cylinder(radius=radius, height=length, sections=sections, transform=align)
    end_a = trimesh.creation.icosphere(subdivisions=2, radius=radius)
    end_a.apply_translation(a)
    end_b = trimesh.creation.icosphere(subdivisions=2, radius=radius)
    end_b.apply_translation(b)
    return trimesh.util.concatenate([cylinder, end_a, end_b])


def triangle_geometry_digest(mesh: trimesh.Trimesh, quantum_mm: float = 1e-5) -> str:
    triangles = np.asarray(mesh.triangles, dtype=np.float64)
    quantized = np.rint(triangles / quantum_mm).astype(np.int64)
    quantized.sort(axis=1)
    flat = quantized.reshape(len(quantized), 9)
    order = np.lexsort(tuple(flat[:, col] for col in range(8, -1, -1)))
    return hashlib.sha256(flat[order].tobytes()).hexdigest()


def manifest_tree(root: Path) -> dict[str, Any]:
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != "artifact-manifest.json"):
        files.append({"path": str(path.relative_to(root)), "bytes": path.stat().st_size, "sha256": sha256(path)})
    return {"schema": "ai3d.full-model-fastpath.artifact-manifest.v1", "files": files}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--tail-analysis", required=True, type=Path)
    parser.add_argument("--frozen-smoke-stl", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--bridge-radius-mm", type=float, default=2.5)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {args.output}")
    if sha256(args.frozen_smoke_stl).lower() != FROZEN_SMOKE_SHA256:
        raise RuntimeError("Frozen successful 0.5 mm candidate hash mismatch")
    tail = json.loads(args.tail_analysis.read_text(encoding="utf-8"))
    if tail["source"]["sha256"].lower() != SOURCE_SHA256 or tail["selection_decision"]["visible_tail_components_to_keep"] != [5, 8]:
        raise RuntimeError("Tail analysis is not the approved C05+C08 selection")

    args.output.mkdir(parents=True, exist_ok=False)
    profiler = Profiler()
    with profiler.stage("load_and_component_classification"):
        components, source_record = load_scaled_components(args.source)
        c01, c05, c08 = components[0], components[4], components[7]

    def witnesses(pair: str) -> tuple[np.ndarray, np.ndarray]:
        item = tail["pairwise"][pair]["exact_CPU"]["global_minimum"]
        return np.asarray(item["witness_point_a"], dtype=np.float64), np.asarray(item["witness_point_b"], dtype=np.float64)

    with profiler.stage("minimal_local_tail_connections"):
        c05_root, c01_root = witnesses("C05_C01")
        c05_tip, c08_tip = witnesses("C05_C08")
        root_bridge = capsule_between(c05_root, c01_root, args.bridge_radius_mm)
        curl_bridge = capsule_between(c05_tip, c08_tip, args.bridge_radius_mm)
        visible_input = trimesh.util.concatenate([c01, c05, c08, root_bridge, curl_bridge])

    with profiler.stage("surface_voxelization"):
        grid = visible_input.voxelized(PITCH_MM, method="subdivide")
        surface = np.asarray(grid.matrix, dtype=bool)
        grid_shape = list(surface.shape)
        surface_voxels = int(surface.sum())
        _, surface_components = ndimage.label(surface, structure=ndimage.generate_binary_structure(3, 1))
    with profiler.stage("binary_solid_reconstruction"):
        filled = ndimage.binary_fill_holes(surface)
        filled_voxels = int(filled.sum())
        occupied_labels, occupied_components = ndimage.label(filled, structure=ndimage.generate_binary_structure(3, 1))
        del occupied_labels
        if occupied_components != 1:
            raise RuntimeError(f"Joint reconstruction produced {occupied_components} solids; refusing any largest-component deletion")
    with profiler.stage("mesh_extraction"):
        candidate = voxel_ops.matrix_to_marching_cubes(filled, pitch=PITCH_MM)
        candidate.apply_translation(np.asarray(grid.transform[:3, 3], dtype=np.float64))
        candidate.remove_unreferenced_vertices()
        if not candidate.is_winding_consistent or candidate.volume < 0:
            candidate.fix_normals(multibody=True)
    del surface, filled, grid

    with profiler.stage("quick_topology_working_mesh"):
        working_topology = topology(candidate)
    with profiler.stage("robust_exact_self_intersection_working_mesh"):
        working_events = self_events(candidate, name=f"{PREFIX}/working", workers=args.workers, chunk_size=768, radius_bins=8)
        working_gate = topology_gate(working_topology, working_events)

    npz_path = args.output / f"{PREFIX}-working-mesh.npz"
    stl_path = args.output / f"{PREFIX}.stl"
    mf_path = args.output / f"{PREFIX}.3mf"
    with profiler.stage("working_npz_export"):
        atomic_npz(npz_path, vertices=np.asarray(candidate.vertices), faces=np.asarray(candidate.faces))
    with profiler.stage("stl_export"):
        atomic_bytes(stl_path, candidate.export(file_type="stl"))
    with profiler.stage("3mf_export"):
        write_3mf(candidate, mf_path)
    with profiler.stage("stl_roundtrip_load_and_topology"):
        stl_mesh = trimesh.load(stl_path, force="mesh", process=True)
        stl_topology = topology(stl_mesh)
    with profiler.stage("3mf_roundtrip_load_and_topology"):
        mf_mesh = load_3mf(mf_path)
        mf_topology = topology(mf_mesh)

    working_digest = triangle_geometry_digest(candidate)
    stl_digest = triangle_geometry_digest(stl_mesh)
    mf_digest = triangle_geometry_digest(mf_mesh)
    transferred_events = {
        "basis": "triangle multiset digest at 1e-5 mm plus equal topology; exact working-mesh event result transfers only when digest matches",
        "working_digest": working_digest,
        "stl_digest": stl_digest,
        "3mf_digest": mf_digest,
    }
    roundtrips = {}
    for name, mesh, metrics, digest in (
        ("stl", stl_mesh, stl_topology, stl_digest),
        ("3mf", mf_mesh, mf_topology, mf_digest),
    ):
        if digest == working_digest:
            events = working_events
            event_mode = "TRANSFERRED_FROM_IDENTICAL_QUANTIZED_TRIANGLE_MULTISET"
        else:
            with profiler.stage(f"robust_exact_self_intersection_{name}_roundtrip"):
                events = self_events(mesh, name=f"{PREFIX}/{name}", workers=args.workers, chunk_size=768, radius_bins=8)
            event_mode = "RECOMPUTED"
        roundtrips[name] = {"topology": metrics, "events": events, "event_mode": event_mode, "gate": topology_gate(metrics, events)}

    with profiler.stage("layer_loop_slicability_working"):
        layer_working = audit_mesh(candidate, 0.5, 1e-5)
    with profiler.stage("layer_loop_slicability_stl"):
        layer_stl = audit_mesh(stl_mesh, 0.5, 1e-5)
    with profiler.stage("layer_loop_slicability_3mf"):
        layer_mf = audit_mesh(mf_mesh, 0.5, 1e-5)

    technical_pass = (
        working_gate["pass"]
        and roundtrips["stl"]["gate"]["pass"]
        and roundtrips["3mf"]["gate"]["pass"]
        and layer_working["pass"]
        and layer_stl["pass"]
        and layer_mf["pass"]
    )
    report = {
        "schema": "ai3d.full-model-fastpath.build-and-fast-gate.v1",
        "status": "FAST_GATE_PASS" if technical_pass else "FAST_GATE_FAIL",
        "classification": "CANDIDATE / NON-MASTER / NOT YET VISUALLY ACCEPTED",
        "source": source_record,
        "frozen_success_reference": {"path": str(args.frozen_smoke_stl), "sha256": FROZEN_SMOKE_SHA256, "overwritten": False},
        "component_selection": {
            "included_original_components": [1, 5, 8],
            "excluded_duplicate_inner_tail_skins": [7, 9],
            "other_original_components_not_introduced": [3, 4, 6, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
        },
        "connections": {
            "radius_mm": args.bridge_radius_mm,
            "C05_to_C01": {"surface_gap_mm": float(np.linalg.norm(c05_root - c01_root)), "endpoint_C05_mm": c05_root.tolist(), "endpoint_C01_mm": c01_root.tolist()},
            "C05_to_C08": {"surface_gap_mm": float(np.linalg.norm(c05_tip - c08_tip)), "endpoint_C05_mm": c05_tip.tolist(), "endpoint_C08_mm": c08_tip.tolist()},
            "method": "two minimal straight capsules between exact closest-surface witnesses; 32-section cylinder plus low-order spherical end caps",
        },
        "backend": {
            "surface_voxelization": "trimesh.voxelized(method='subdivide')",
            "inside_outside": "scipy.ndimage.binary_fill_holes",
            "surface_extraction": "trimesh.voxel.ops.matrix_to_marching_cubes / skimage; no smoothing",
            "pitch_mm": PITCH_MM,
            "morphological_closing": False,
            "smoothing": False,
            "decimation": False,
            "separate_inner_shell": False,
            "invalidated_methods_not_used": ["invalidated-cumesh-raytrace-v1", "invalidated-edge-connectivity-split-v1"],
        },
        "voxel_grid": {
            "shape": grid_shape,
            "surface_voxels": surface_voxels,
            "filled_voxels": filled_voxels,
            "surface_components": int(surface_components),
            "occupied_components_after_fill": int(occupied_components),
        },
        "working": {"topology": working_topology, "events": working_events, "gate": working_gate},
        "roundtrips": roundtrips,
        "triangle_digest_transfer": transferred_events,
        "layer_loop_slicability": {"working": layer_working, "stl": layer_stl, "3mf": layer_mf},
        "timings_and_resources": profiler.summary(),
        "artifacts": {
            "working_npz": {"path": str(npz_path), "bytes": npz_path.stat().st_size, "sha256": sha256(npz_path)},
            "stl": {"path": str(stl_path), "bytes": stl_path.stat().st_size, "sha256": sha256(stl_path)},
            "3mf": {"path": str(mf_path), "bytes": mf_path.stat().st_size, "sha256": sha256(mf_path)},
        },
        "software": {"python": platform.python_version(), "numpy": np.__version__, "trimesh": trimesh.__version__, "platform": platform.platform()},
    }
    atomic_json(args.output / f"{PREFIX}-fast-gate.json", report)
    atomic_json(args.output / "artifact-manifest.json", manifest_tree(args.output))
    print(json.dumps({"status": report["status"], "output": str(args.output), "total_seconds": report["timings_and_resources"]["total_wall_seconds"], "peak_rss_bytes": report["timings_and_resources"]["peak_rss_bytes"]}, indent=2))
    if not technical_pass:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
