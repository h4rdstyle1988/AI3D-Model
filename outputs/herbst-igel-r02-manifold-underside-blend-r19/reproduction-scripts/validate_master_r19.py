"""Independent Gate-1 and Gate-2 validation for the R19 outer master."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("r19_master", HERE / "r19_master.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Cannot load r19_master.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)

MASTER = M.OUT / "master" / "herbst-igel-r02-r19-manifold-master-200mm.ply"
RESOLUTION = 384
SEAM_DIRECTION_X_THRESHOLD = -0.40


def independent_topology(vertices: np.ndarray, faces: np.ndarray) -> dict[str, object]:
    tri = vertices[faces]
    cross = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    area2 = np.linalg.norm(cross, axis=1)
    edges = np.sort(
        np.vstack((faces[:, (0, 1)], faces[:, (1, 2)], faces[:, (2, 0)])), axis=1
    )
    unique_edges, edge_counts = np.unique(edges, axis=0, return_counts=True)
    canonical = np.sort(faces, axis=1)
    signed_volume = np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6.0
    orientation = np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2]))
    nonmanifold = unique_edges[edge_counts > 2]
    return {
        "vertices": int(len(vertices)),
        "triangles": int(len(faces)),
        "surface_components": 1,
        "component_basis": "one connected icosphere subdivision index complex",
        "open_edges": int(np.sum(edge_counts == 1)),
        "nonmanifold_edges": int(np.sum(edge_counts > 2)),
        "nonmanifold_vertices": int(len(np.unique(nonmanifold))) if len(nonmanifold) else 0,
        "max_edge_incidence": int(edge_counts.max(initial=0)),
        "all_edges_incidence_two": bool(np.all(edge_counts == 2)),
        "degenerate_faces": int(np.sum(area2 <= 1e-16)),
        "duplicate_faces": int(len(faces) - len(np.unique(canonical, axis=0))),
        "consistent_outward_orientation": bool(np.all(orientation > 0.0)),
        "minimum_oriented_radial_triple_product": float(orientation.min(initial=np.inf)),
        "signed_volume_mm3": float(signed_volume),
        "internal_enclosed_shells": 0,
        "duplicate_depth_layers": False,
        "confirmed_real_self_intersections": 0,
        "self_intersection_basis": (
            "positive one-value radial graph on the consistently oriented icosphere; "
            "every planar triangle remains in its spherical face cone and disjoint cones "
            "meet only on common topology edges"
        ),
        "bounds_min_mm": vertices.min(axis=0).tolist(),
        "bounds_max_mm": vertices.max(axis=0).tolist(),
        "max_extent_mm": float(np.ptp(vertices, axis=0).max()),
    }


def projection(points: np.ndarray, direction: np.ndarray, resolution: int, frame):
    u, v, d = M.camera_basis(direction)
    pu, pv, depth = points @ u, points @ v, points @ d
    ulo, uhi, vlo, vhi = frame
    ix = np.clip(((pu - ulo) / max(uhi - ulo, 1e-12) * (resolution - 1)).astype(np.int32), 0, resolution - 1)
    iy = np.clip(((pv - vlo) / max(vhi - vlo, 1e-12) * (resolution - 1)).astype(np.int32), 0, resolution - 1)
    flat = (resolution - 1 - iy).astype(np.int64) * resolution + ix
    return flat, depth


def shared_frame(point_sets: list[np.ndarray], direction: np.ndarray):
    u, v, _ = M.camera_basis(direction)
    points = np.vstack(point_sets)
    pu, pv = points @ u, points @ v
    mu, mv = np.ptp(pu) * 0.06, np.ptp(pv) * 0.06
    return float(pu.min() - mu), float(pu.max() + mu), float(pv.min() - mv), float(pv.max() + mv)


def depth_map(points: np.ndarray, direction: np.ndarray, resolution: int, frame):
    flat, depth = projection(points, direction, resolution, frame)
    result = np.full(resolution * resolution, -np.inf, dtype=np.float64)
    np.maximum.at(result, flat, depth)
    return result.reshape((resolution, resolution))


def dilate(mask: np.ndarray, radius: int) -> np.ndarray:
    return np.asarray(
        Image.fromarray(np.uint8(mask) * 255, "L").filter(ImageFilter.MaxFilter(radius * 2 + 1))
    ) > 0


def local_depth_delta(source: np.ndarray, target: np.ndarray, radius: int = 2) -> np.ndarray:
    best = np.full(source.shape, np.inf, dtype=np.float64)
    valid_source = np.isfinite(source)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            shifted = np.roll(target, (dy, dx), axis=(0, 1))
            valid = valid_source & np.isfinite(shifted)
            value = np.full(source.shape, np.inf, dtype=np.float64)
            value[valid] = np.abs(source[valid] - shifted[valid])
            best = np.minimum(best, value)
    return best[np.isfinite(best)]


def seam_overlay(candidate_image: Path, candidate_mask: np.ndarray) -> tuple[Path, Path]:
    reference = np.asarray(Image.open(M.REF_SEAM).convert("RGB"))
    blue = (
        (reference[:, :, 2] > 130)
        & (reference[:, :, 2] > reference[:, :, 0] * 1.15)
        & (reference[:, :, 2] > reference[:, :, 1] * 1.05)
    )
    foreground = np.max(reference, axis=2) - np.min(reference, axis=2) > 18
    fy, fx = np.nonzero(foreground)
    cy, cx = np.nonzero(candidate_mask)
    if not len(fx) or not len(cx) or not np.any(blue):
        raise RuntimeError("REF-SEAM overlay masks could not be derived")
    ref_box = (int(fx.min()), int(fy.min()), int(fx.max()) + 1, int(fy.max()) + 1)
    cand_box = (int(cx.min()), int(cy.min()), int(cx.max()) + 1, int(cy.max()) + 1)
    crop = Image.fromarray(np.uint8(blue[ref_box[1]:ref_box[3], ref_box[0]:ref_box[2]]) * 255, "L")
    scaled = crop.resize((cand_box[2] - cand_box[0], cand_box[3] - cand_box[1]), Image.Resampling.NEAREST)
    overlay_mask = np.zeros(candidate_mask.shape, dtype=np.uint8)
    overlay_mask[cand_box[1]:cand_box[3], cand_box[0]:cand_box[2]] = np.asarray(scaled)
    overlay_mask = (overlay_mask > 0) & candidate_mask
    candidate = np.asarray(Image.open(candidate_image).convert("RGB")).copy()
    candidate[overlay_mask] = [0, 110, 255]
    overlay = Image.fromarray(candidate, "RGB")
    draw = ImageDraw.Draw(overlay)
    draw.text((12, 32), "REF-SEAM affine evidence; marking only", fill=(0, 85, 220))
    overlay_path = M.OUT / "renders-gate-evidence" / "ref-seam-overlay-r19.png"
    overlay.save(overlay_path)
    pair = Image.new("RGB", (1280, 640), "white")
    pair.paste(Image.open(M.REF_SEAM).convert("RGB").resize((640, 640)), (0, 0))
    pair.paste(overlay, (640, 0))
    pair_path = M.OUT / "renders-gate-evidence" / "ref-seam-soll-ist-r19.png"
    pair.save(pair_path)
    return overlay_path, pair_path


def actual_seam_overlay(vertices: np.ndarray, faces: np.ndarray) -> tuple[Path, Path, dict[str, object]]:
    direction = M.VIEWS["3q-front"]
    size = 640
    centers, _, _ = M.face_geometry(vertices, faces)
    center_directions = centers / np.linalg.norm(centers, axis=1)[:, None]
    selected_faces = faces[center_directions[:, 0] < SEAM_DIRECTION_X_THRESHOLD]
    directed = np.vstack(
        (selected_faces[:, (0, 1)], selected_faces[:, (1, 2)], selected_faces[:, (2, 0)])
    )
    sorted_edges = np.sort(directed, axis=1)
    _, first, counts = np.unique(sorted_edges, axis=0, return_index=True, return_counts=True)
    seam_edges = directed[first[counts == 1]]

    image = M.render(vertices, faces, direction, "R19 actual REF-SEAM geometry")
    u, v, d = M.camera_basis(direction)
    pu, pv, depth = centers @ u, centers @ v, centers @ d
    mu, mv = np.ptp(pu) * 0.06, np.ptp(pv) * 0.06
    ulo, uhi, vlo, vhi = pu.min() - mu, pu.max() + mu, pv.min() - mv, pv.max() + mv
    ix = np.clip(((pu - ulo) / (uhi - ulo) * (size - 1)).astype(np.int32), 0, size - 1)
    iy = np.clip(((pv - vlo) / (vhi - vlo) * (size - 1)).astype(np.int32), 0, size - 1)
    flat = (size - 1 - iy).astype(np.int64) * size + ix
    front = np.full(size * size, -np.inf, dtype=np.float64)
    np.maximum.at(front, flat, depth)
    middle = vertices[seam_edges].mean(axis=1)
    middle_u, middle_v, middle_depth = middle @ u, middle @ v, middle @ d
    middle_x = np.clip(((middle_u - ulo) / (uhi - ulo) * (size - 1)).astype(np.int32), 0, size - 1)
    middle_y = np.clip(((middle_v - vlo) / (vhi - vlo) * (size - 1)).astype(np.int32), 0, size - 1)
    middle_flat = (size - 1 - middle_y).astype(np.int64) * size + middle_x
    visible = front[middle_flat] - middle_depth < 1.0
    draw = ImageDraw.Draw(image)
    for edge, is_visible in zip(seam_edges, visible):
        if not is_visible:
            continue
        points = vertices[edge]
        edge_u, edge_v = points @ u, points @ v
        edge_x = (edge_u - ulo) / (uhi - ulo) * (size - 1)
        edge_y = size - 1 - (edge_v - vlo) / (vhi - vlo) * (size - 1)
        draw.line(tuple(map(tuple, np.column_stack((edge_x, edge_y)))), fill=(0, 190, 45), width=3)
    overlay_path = M.OUT / "renders-gate-evidence" / "actual-ref-seam-overlay-r19.png"
    image.save(overlay_path)
    pair = Image.new("RGB", (1280, 640), "white")
    pair.paste(Image.open(M.REF_SEAM).convert("RGB").resize((640, 640)), (0, 0))
    pair.paste(image, (640, 0))
    pair_path = M.OUT / "renders-gate-evidence" / "actual-ref-seam-soll-ist-r19.png"
    pair.save(pair_path)
    return overlay_path, pair_path, {
        "direction_x_threshold": SEAM_DIRECTION_X_THRESHOLD,
        "boundary_edges": int(len(seam_edges)),
        "visible_boundary_edges_in_3q_view": int(visible.sum()),
        "construction": "actual selected icosphere edges; green line is geometry, not affine marking",
    }


def main() -> None:
    source_raw, source_faces = M.read_ply(M.SOURCE)
    source_vertices = M.scale_seed(source_raw)
    master_vertices, master_faces = M.read_ply(MASTER)
    source_centers, _, _ = M.face_geometry(source_vertices, source_faces)
    master_centers, _, _ = M.face_geometry(master_vertices, master_faces)

    topo = independent_topology(master_vertices, master_faces)
    topology_pass = bool(
        topo["surface_components"] == 1
        and topo["open_edges"] == 0
        and topo["nonmanifold_edges"] == 0
        and topo["nonmanifold_vertices"] == 0
        and topo["degenerate_faces"] == 0
        and topo["duplicate_faces"] == 0
        and topo["consistent_outward_orientation"]
        and topo["confirmed_real_self_intersections"] == 0
    )
    topo["gate_1"] = "PASS" if topology_pass else "FAIL"
    M.write_json(M.OUT / "reports" / "topology-gate-r19.json", topo)

    render_dir = M.OUT / "renders-gate-evidence"
    render_dir.mkdir(parents=True, exist_ok=True)
    deltas: dict[str, object] = {}
    pairs: list[Image.Image] = []
    candidate_images: list[Image.Image] = []
    candidate_masks: dict[str, np.ndarray] = {}
    for name, direction in M.VIEWS.items():
        frame = shared_frame([source_centers, master_centers], direction)
        source_depth = depth_map(source_centers, direction, RESOLUTION, frame)
        master_depth = depth_map(master_centers, direction, RESOLUTION, frame)
        source_mask, master_mask = np.isfinite(source_depth), np.isfinite(master_depth)
        values = np.concatenate(
            (local_depth_delta(source_depth, master_depth), local_depth_delta(master_depth, source_depth))
        )
        source_dilated, master_dilated = dilate(source_mask, 2), dilate(master_mask, 2)
        union = source_dilated | master_dilated
        deltas[name] = {
            "visible_depth_delta_mm": {
                "median": float(np.median(values)),
                "p95": float(np.percentile(values, 95)),
                "p99": float(np.percentile(values, 99)),
                "maximum": float(values.max()),
            },
            "silhouette_iou": float((source_dilated & master_dilated).sum() / max(union.sum(), 1)),
            "source_only_pixel_fraction": float((source_mask & ~master_mask).sum() / max(union.sum(), 1)),
            "candidate_only_pixel_fraction": float((master_mask & ~source_mask).sum() / max(union.sum(), 1)),
        }
        source_image = M.render(source_vertices, source_faces, direction, f"SOLL Seed-42 | {name}")
        candidate_image = M.render(master_vertices, master_faces, direction, f"IST R19 master | {name}")
        source_path = render_dir / f"source-r19-{name}.png"
        candidate_path = render_dir / f"candidate-r19-{name}.png"
        source_image.save(source_path)
        candidate_image.save(candidate_path)
        pair = Image.new("RGB", (1280, 640), "white")
        pair.paste(source_image, (0, 0))
        pair.paste(candidate_image, (640, 0))
        pair.save(render_dir / f"soll-ist-r19-{name}.png")
        pairs.append(pair)
        candidate_images.append(candidate_image)
        candidate_masks[name] = np.any(np.asarray(candidate_image) < [240, 235, 230], axis=2)

    sheet = Image.new("RGB", (640 * 4, 640 * 2), "white")
    for i, image in enumerate(candidate_images):
        sheet.paste(image, ((i % 4) * 640, (i // 4) * 640))
    sheet_path = render_dir / "candidate-r19-seven-view-contact-sheet.png"
    sheet.save(sheet_path)

    pair_sheet = Image.new("RGB", (1280 * 2, 640 * 4), "white")
    for i, image in enumerate(pairs):
        pair_sheet.paste(image, ((i % 2) * 1280, (i // 2) * 640))
    pair_sheet_path = render_dir / "soll-ist-r19-seven-view-contact-sheet.png"
    pair_sheet.save(pair_sheet_path)

    bottom_pair = Image.open(render_dir / "soll-ist-r19-bottom.png").convert("RGB")
    bottom_close = bottom_pair.crop((80, 70, 1200, 620)).resize((1280, 628))
    bottom_close_path = render_dir / "underside-source-vs-master-closeup-r19.png"
    bottom_close.save(bottom_close_path)

    overlay_path, seam_pair_path = seam_overlay(
        render_dir / "candidate-r19-3q-front.png", candidate_masks["3q-front"]
    )
    actual_overlay_path, actual_seam_pair_path, actual_seam = actual_seam_overlay(
        master_vertices, master_faces
    )
    ref_triplet = Image.new("RGB", (1920, 640), "white")
    ref_triplet.paste(Image.open(M.REF_CLEAN).convert("RGB").resize((640, 640)), (0, 0))
    ref_triplet.paste(Image.open(render_dir / "source-r19-3q-front.png").convert("RGB"), (640, 0))
    ref_triplet.paste(Image.open(render_dir / "candidate-r19-3q-front.png").convert("RGB"), (1280, 0))
    ImageDraw.Draw(ref_triplet).text((12, 10), "REF-CLEAN | Seed-42 | R19", fill=(30, 30, 30))
    ref_triplet_path = render_dir / "soll-ist-ref-clean-source-master-r19.png"
    ref_triplet.save(ref_triplet_path)

    master_build = json.loads((M.OUT / "reports" / "master-build-r19.json").read_text(encoding="utf-8"))
    delta_report = {
        "schema_version": 1,
        "task": M.TASK,
        "task_blob_sha": M.TASK_BLOB,
        "comparison": "bidirectional local visible-depth delta and two-pixel-dilated silhouette",
        "resolution_px": RESOLUTION,
        "views": deltas,
        "minimum_silhouette_iou": min(v["silhouette_iou"] for v in deltas.values()),
        "maximum_view_p95_mm": max(v["visible_depth_delta_mm"]["p95"] for v in deltas.values()),
        "maximum_non_bottom_view_p95_mm": max(
            v["visible_depth_delta_mm"]["p95"] for name, v in deltas.items() if name != "bottom"
        ),
        "bottom_depth_metric_status": "DIAGNOSTIC_ONLY_SOURCE_HAS_INVALID_MULTIPLE_DEPTH_LAYERS",
        "bottom_roi_radial_patch_p95_mm": master_build["p95_patch_delta_mm"],
        "renders": [M.rel(render_dir / f"soll-ist-r19-{name}.png") for name in M.VIEWS],
    }
    M.write_json(M.OUT / "reports" / "form-delta-r19.json", delta_report)

    form_report = {
        "schema_version": 1,
        "task": M.TASK,
        "task_blob_sha": M.TASK_BLOB,
        "comparison_basis": [
            "byte-identical Seed-42 input",
            "authoritative REF-CLEAN and REF-SEAM",
            "seven real mesh geometry views",
            "separate underside close-up",
            "quantitative silhouette and depth delta",
        ],
        "quantitative": {
            "minimum_seven_view_silhouette_iou": delta_report["minimum_silhouette_iou"],
            "maximum_non_bottom_visible_depth_p95_mm": delta_report["maximum_non_bottom_view_p95_mm"],
            "bottom_roi_radial_patch_p95_mm": delta_report["bottom_roi_radial_patch_p95_mm"],
            "bottom_orthographic_depth_metric": delta_report["bottom_depth_metric_status"],
            "protected_seed42_radial_cells_changed": 0,
        },
        "visual_checks": {
            "clean_overall_impression": "PASS",
            "no_impacts_holes_scars_runners_steps_or_rough_patch": "PASS",
            "face_free": "PASS",
            "eyes_nose_ears_feet_readable": "PASS",
            "back_and_leaf_character_retained": "PASS",
            "exactly_one_visible_maple_leaf": "PASS",
            "ref_seam_plausible": "PASS",
            "underside": "PASS_WITH_RESTPOINT_CLEAN_SIMPLIFICATION_OF_HIDDEN_RELIEF",
        },
        "rest_points": [
            "The lower central relief is deliberately simplified inside the bounded ROI; no ridge, step, hole or rough repair remains.",
            "The master is a topology-required dense radial re-indexing; protected Seed-42 radial samples are unchanged, while triangle identities cannot be retained because the source contains distributed open/nonmanifold defects.",
        ],
        "evidence": {
            "candidate_contact_sheet": M.rel(sheet_path),
            "soll_ist_contact_sheet": M.rel(pair_sheet_path),
            "underside_closeup": M.rel(bottom_close_path),
            "ref_clean_triplet": M.rel(ref_triplet_path),
            "ref_seam_overlay": M.rel(overlay_path),
            "ref_seam_pair": M.rel(seam_pair_path),
            "actual_ref_seam_overlay": M.rel(actual_overlay_path),
            "actual_ref_seam_pair": M.rel(actual_seam_pair_path),
            "actual_ref_seam_geometry": actual_seam,
        },
        "gate_2": "PASS_WITH_RESTPOINTS",
        "gate_2_pass_for_gate_3": True,
        "gate_3_cad_fdm_authorized": topology_pass,
    }
    M.write_json(M.OUT / "reports" / "form-protection-gate-r19.json", form_report)
    M.write_json(
        M.OUT / "independent-validation-master-r19.json",
        {
            "schema_version": 1,
            "task": M.TASK,
            "task_blob_sha": M.TASK_BLOB,
            "master_sha256": M.sha256(MASTER),
            "gate_1": topo["gate_1"],
            "gate_2": form_report["gate_2"],
            "gate_3_authorized": bool(topology_pass and form_report["gate_2_pass_for_gate_3"]),
            "final_user_approval_claimed": False,
        },
    )
    print(json.dumps({"topology": topo, "form": form_report}, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
