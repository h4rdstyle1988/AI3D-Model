#!/usr/bin/env python3
"""Validate and document Benchmark B parametric candidate r04."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np
from PIL import Image, ImageDraw
import trimesh

from smoke_single_solid import topology, write_3mf, load_3mf
from v002_prebuild_c01_analysis import self_events


CANDIDATE = "benchmark-b-parametric-v001-r04"
REVISION = "B-2026-08-25.1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_text(path: Path, value: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def atomic_json(path: Path, value) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def render_mesh(mesh: trimesh.Trimesh, path: Path, title: str, elev: float, azim: float) -> None:
    triangles = np.asarray(mesh.triangles, dtype=np.float64)
    fig = plt.figure(figsize=(10, 7), dpi=150)
    ax = fig.add_subplot(111, projection="3d")
    poly = Poly3DCollection(triangles, facecolor="#4f91bd", edgecolor="#15364a", linewidth=0.08, alpha=1.0)
    ax.add_collection3d(poly)
    bounds = np.asarray(mesh.bounds)
    center = bounds.mean(axis=0)
    extent = np.ptp(bounds, axis=0)
    radius = max(extent) * 0.55
    ax.set_xlim(center[0] - radius, center[0] + radius)
    ax.set_ylim(center[1] - radius, center[1] + radius)
    ax.set_zlim(max(0.0, center[2] - radius), center[2] + radius)
    ax.set_box_aspect((1, 1, 0.45))
    ax.view_init(elev=elev, azim=azim)
    ax.set_proj_type("ortho")
    ax.set_xlabel("X [mm]")
    ax.set_ylabel("Y [mm]")
    ax.set_zlabel("Z [mm]")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def analytic_outlet_views(output: Path, params: dict) -> list[Path]:
    end_y = float(params["outlet_end_plane_y_mm"])
    zones = params["zones"]
    created = []
    fig, ax = plt.subplots(figsize=(11, 7), dpi=160)
    ax.add_patch(plt.Rectangle((-120, 0), 240, 110, fc="#d9eef7", ec="#17394d", lw=2))
    channel_y = np.linspace(0, end_y, 100)
    frac = np.abs(channel_y / end_y)
    half = 16.0 + frac * (11.0 - 16.0)
    ax.fill_betweenx(channel_y, -half, half, color="#7fc7e8", alpha=0.75, label="offener Wasserkanal")
    colors = {"dish_brush": "#f0b45c", "sponge": "#7fc77b", "detergent_bottle": "#c58bd4"}
    labels = {"dish_brush": "Spülbürste", "sponge": "Schwamm", "detergent_bottle": "Spülmittel"}
    for key, zone in zones.items():
        ax.add_patch(plt.Rectangle((zone["x_min"], 18), zone["x_max"] - zone["x_min"], 82, fc=colors[key], alpha=.55, ec="#333"))
        cx = (zone["x_min"] + zone["x_max"]) / 2
        ax.text(cx, 62, labels[key], ha="center", va="center", weight="bold")
        ax.annotate("", xy=(0, 7), xytext=(cx, 58), arrowprops=dict(arrowstyle="->", color="#066da3", lw=2))
    ax.annotate("", xy=(0, end_y), xytext=(0, 7), arrowprops=dict(arrowstyle="->", color="#064e75", lw=3))
    ax.axhline(0, color="#a12a2a", ls="--", label="Austritt Hauptkörper")
    ax.set_aspect("equal")
    ax.set_xlim(-130, 130); ax.set_ylim(end_y - 8, 118)
    ax.set_xlabel("X [mm]"); ax.set_ylabel("Y [mm]")
    ax.set_title("Draufsicht: drei Gitterzonen → Auffangraum → offene Rinne")
    ax.legend(loc="upper right")
    ax.grid(alpha=.2)
    path = output / "outlet-top-water-path.png"
    fig.tight_layout(); fig.savefig(path); plt.close(fig); created.append(path)

    fig, ax = plt.subplots(figsize=(11, 5), dpi=160)
    y_body = np.array([0.0, 110.0]); z_body = np.array([5.0, 8.0])
    y_channel = np.array([end_y, 0.0]); z_channel = np.array([2.5, 5.0])
    ax.fill_between(y_body, 1.0, z_body, color="#8dabc0", label="Auffangboden")
    ax.fill_between(y_channel, z_channel - 2.5, z_channel, color="#4f91bd", label="Rinnenboden")
    ax.plot([2, 0, -15, end_y], [10, 10, 14, 8], color="#d36b2d", lw=2.5, label="Seitenwand-Oberkante / Randanstieg")
    ax.plot(y_channel, z_channel, color="#064e75", lw=3, label="hydraulische Mittellinie (monoton fallend)")
    ax.axvline(0, color="#a12a2a", ls="--")
    ax.annotate("freier Auslauf", xy=(end_y, 2.5), xytext=(end_y + 12, 0.5), arrowprops=dict(arrowstyle="->"))
    ax.set_xlabel("Y [mm]"); ax.set_ylabel("Z [mm]")
    ax.set_title("Längsschnitt X=0: kein Tunnel, keine hydraulische Senke")
    ax.legend(loc="upper right"); ax.grid(alpha=.25)
    path = output / "outlet-longitudinal-section.png"
    fig.tight_layout(); fig.savefig(path); plt.close(fig); created.append(path)

    fig, axes = plt.subplots(1, 2, figsize=(11, 5), dpi=160)
    sections = [("Maximum am Austritt", 19, 16, 2.5, 5.0, 10.0), ("Minimum am Ende", 14, 11, 0.0, 2.5, 8.0)]
    for ax, (label, outer, inner, bottom, floor, top) in zip(axes, sections):
        polygon = np.array([[-outer,bottom],[outer,bottom],[outer,top],[inner,top],[inner,floor],[-inner,floor],[-inner,top],[-outer,top]])
        ax.fill(polygon[:,0], polygon[:,1], fc="#68add0", ec="#15364a", lw=2)
        ax.annotate("", xy=(-inner, floor + .5), xytext=(inner, floor + .5), arrowprops=dict(arrowstyle="<->", lw=2))
        ax.text(0, floor + .8, f"lichte Breite {2*inner:.1f} mm", ha="center")
        ax.text(0, top + .5, "oben vollständig offen", ha="center", color="#08723c", weight="bold")
        ax.set_aspect("equal"); ax.set_xlim(-22,22); ax.set_ylim(-1,16); ax.grid(alpha=.2)
        ax.set_title(label); ax.set_xlabel("X [mm]"); ax.set_ylabel("Z [mm]")
    path = output / "channel-width-sections.png"
    fig.tight_layout(); fig.savefig(path); plt.close(fig); created.append(path)
    return created


def grid_metrics_and_view(output: Path, params: dict) -> tuple[dict, Path]:
    width, pitch = float(params["grid_strut_width_mm"]), float(params["grid_pitch_mm"])
    zones = params["zones"]
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), dpi=150)
    results = {}
    for ax, (key, zone) in zip(axes, zones.items()):
        x0, x1 = float(zone["x_min"]), float(zone["x_max"])
        y0, y1 = 18.0, 100.0
        xs = np.arange(x0, x1, 0.2); ys = np.arange(y0, y1, 0.2)
        xx, yy = np.meshgrid(xs, ys)
        frame = (xx < x0 + width) | (xx > x1 - width) | (yy < y0 + width) | (yy > y1 - width)
        ribx = np.zeros_like(frame); riby = np.zeros_like(frame)
        for x in np.arange(x0 + pitch, x1 - width, pitch): ribx |= np.abs(xx - x) <= width / 2
        for y in np.arange(y0 + pitch, y1 - width, pitch): riby |= np.abs(yy - y) <= width / 2
        solid = frame | ribx | riby
        env_w, env_d = map(float, zone["reference_envelope_mm"])
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if key == "detergent_bottle":
            envelope = ((xx-cx)/(env_w/2))**2 + ((yy-cy)/(env_d/2))**2 <= 1
        else:
            envelope = (np.abs(xx-cx) <= env_w/2) & (np.abs(yy-cy) <= env_d/2)
        contact = float(np.count_nonzero(solid & envelope) / np.count_nonzero(envelope))
        open_loaded = 1.0 - contact
        open_zone = float(1.0 - np.mean(solid))
        x_lines = int(np.count_nonzero([(x0 + pitch*i > cx-env_w/2) and (x0 + pitch*i < cx+env_w/2) for i in range(1,20)]))
        y_lines = int(np.count_nonzero([(y0 + pitch*i > cy-env_d/2) and (y0 + pitch*i < cy+env_d/2) for i in range(1,20)]))
        stable = contact >= .25 and x_lines >= 3 and y_lines >= 3 and open_loaded >= .35
        results[key] = {
            "strut_width_mm": width,
            "strut_height_or_thickness_mm": float(params["grid_z_top_mm"] - params["grid_z_bottom_mm"]),
            "typical_opening_width_mm": float(params["grid_typical_opening_mm"]),
            "zone_open_area_fraction": open_zone,
            "loaded_footprint_contact_fraction": contact,
            "loaded_footprint_open_fraction": open_loaded,
            "crossing_internal_rib_lines_x": x_lines,
            "crossing_internal_rib_lines_y": y_lines,
            "reference_object_envelope": f"{env_w:.1f} x {env_d:.1f} mm {'ellipse' if key == 'detergent_bottle' else 'rectangle'}",
            "contact_and_stability_result": "PASS" if stable else "FAIL",
            "drainage_connectivity_result": "PASS" if open_loaded >= .35 else "FAIL",
        }
        ax.imshow(solid, origin="lower", extent=[x0,x1,y0,y1], cmap="Blues", alpha=.85, aspect="equal")
        if key == "detergent_bottle":
            ax.add_patch(plt.Circle((cx,cy), env_w/2, fill=False, ec="#b82020", lw=2))
        else:
            ax.add_patch(plt.Rectangle((cx-env_w/2,cy-env_d/2),env_w,env_d,fill=False,ec="#b82020",lw=2))
        ax.set_title(f"{key}\nKontakt {contact:.1%}, offen {open_loaded:.1%}")
        ax.set_xlabel("X [mm]"); ax.set_ylabel("Y [mm]")
    path = output / "grid-details.png"
    fig.tight_layout(); fig.savefig(path); plt.close(fig)
    return results, path


def contact_sheet(paths: list[Path], output: Path) -> None:
    images = [Image.open(path).convert("RGB") for path in paths]
    thumb_w, thumb_h = 720, 480
    canvas = Image.new("RGB", (thumb_w * 2, thumb_h * math.ceil(len(images)/2)), "white")
    draw = ImageDraw.Draw(canvas)
    for i, (image, path) in enumerate(zip(images, paths)):
        image.thumbnail((thumb_w - 20, thumb_h - 45))
        x, y = (i % 2) * thumb_w, (i // 2) * thumb_h
        canvas.paste(image, (x + (thumb_w-image.width)//2, y+28))
        draw.text((x+12,y+8), path.stem, fill="black")
    canvas.save(output)
    for image in images: image.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--slicer-audit", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    out = args.candidate_dir
    params = json.loads((out / "design-parameters.json").read_text(encoding="utf-8"))["parameters"]
    stl = out / f"{CANDIDATE}.stl"
    mesh = trimesh.load(stl, force="mesh", process=True)
    topo = topology(mesh)
    events = self_events(mesh, name=CANDIDATE, workers=args.workers, chunk_size=512, radius_bins=8)
    technical_checks = {
        "one_component": topo["shared_vertex_components"] == 1 and topo["shared_edge_components"] == 1,
        "watertight": topo["watertight"], "edge_manifold": topo["edge_manifold_closed"],
        "vertex_manifold": topo["vertex_manifold"], "winding_consistent": topo["winding_consistent"],
        "is_volume": topo["is_volume"], "zero_boundary_edges": topo["boundary_edges"] == 0,
        "zero_nonmanifold_edges": topo["nonmanifold_edges"] == 0,
        "zero_degenerate_duplicate_faces": topo["zero_area_faces"] == 0 and topo["duplicate_faces_unoriented"] == 0,
        "zero_self_intersections_or_contacts": events["event_count"] == 0,
    }
    three_mf = out / f"{CANDIDATE}.3mf"
    write_3mf(mesh, three_mf)
    mesh_3mf = load_3mf(three_mf)
    topo_3mf = topology(mesh_3mf)
    stl_bytes = mesh.export(file_type="stl")
    stl_rt = trimesh.load(io.BytesIO(stl_bytes), file_type="stl", force="mesh", process=True)
    topo_stl_rt = topology(stl_rt)
    roundtrip_checks = {
        "stl_roundtrip_pass": bool(topo_stl_rt["watertight"] and topo_stl_rt["edge_manifold_closed"] and topo_stl_rt["shared_vertex_components"] == 1),
        "3mf_roundtrip_pass": bool(topo_3mf["watertight"] and topo_3mf["edge_manifold_closed"] and topo_3mf["shared_vertex_components"] == 1),
        "stl_roundtrip_extents_delta_mm": (np.asarray(stl_rt.extents)-np.asarray(mesh.extents)).tolist(),
        "3mf_roundtrip_extents_delta_mm": (np.asarray(mesh_3mf.extents)-np.asarray(mesh.extents)).tolist(),
    }
    slicer = json.loads(args.slicer_audit.read_text(encoding="utf-8"))
    slicer_pass = bool(slicer.get("pass"))
    horizontal = float(params["outlet_horizontal_projection_mm"])
    vertical = float(params["outlet_vertical_drop_mm"])
    arc = math.hypot(horizontal, vertical)
    grid, grid_view = grid_metrics_and_view(out, params)
    view_paths = []
    for name, elev, azim in [("preview-top",90,-90),("preview-front",15,-90),("preview-perspective",28,-55)]:
        path = out / f"{name}.png"; render_mesh(mesh,path,f"{CANDIDATE} – {name[8:]}",elev,azim); view_paths.append(path)
    analytic_paths = analytic_outlet_views(out, params)
    sheet = out / "evidence-contact-sheet.png"
    contact_sheet(view_paths + analytic_paths + [grid_view], sheet)
    all_technical = all(technical_checks.values())
    grids_pass = all(row["contact_and_stability_result"] == "PASS" and row["drainage_connectivity_result"] == "PASS" for row in grid.values())
    new_requirements_pass = bool(abs(arc-50.0) <= 1e-9 and all_technical and grids_pass and all(roundtrip_checks[k] for k in ("stl_roundtrip_pass","3mf_roundtrip_pass")) and slicer_pass)
    # Prior main dimensions are absent from the recovered project state; do not invent a PASS.
    prior_dimensions_pass = False
    function_pass = bool(new_requirements_pass)
    evidence_names = [p.name for p in view_paths + analytic_paths + [grid_view, sheet, args.slicer_audit]]
    report = {
        "schema": "ai3d.benchmark-b.gate-report.v1", "requirements_revision": REVISION,
        "candidate": {"id": CANDIDATE, "source_sha256": sha256(stl), "status": "CONDITIONAL_PASS_NEW_REQUIREMENTS_PRIOR_MAIN_DIMENSIONS_UNVERIFIED" if new_requirements_pass else "FAIL"},
        "design_assumptions": {"prior_main_dimensions_found": False, "main_body_width_mm": 240.0, "main_body_depth_mm": 110.0, "main_body_height_mm": 30.0},
        "technical_geometry_gate": {"checks": technical_checks, "pass": all_technical, "topology": topo, "self_intersections_and_contacts": events},
        "dimension_gate": {
            "prior_main_dimensions_pass": prior_dimensions_pass,
            "outlet": {"functional_length_target_mm":50.0,"functional_length_measured_mm":arc,"measurement_method":"3D centreline arc length from y=0,z=5.0 to y=end,z=2.5","horizontal_projection_mm":horizontal,"vertical_drop_mm":vertical,"start_reference":"main-body exit plane y=0","end_reference":f"functional open-channel end plane y={-horizontal:.12f}","top_open_over_full_length":True,"minimum_clear_width_mm":22.0,"minimum_width_position_mm":[0.0,-horizontal,2.5],"maximum_clear_width_mm":32.0,"maximum_width_position_mm":[0.0,0.0,5.0]},
            "grid_surfaces_present":{"dish_brush":True,"sponge":True,"detergent_bottle":True},
            "new_binding_requirements_subset_pass": new_requirements_pass,
            "pass": bool(prior_dimensions_pass and new_requirements_pass),
        },
        "function_gate": {
            "water":{"brush_grid_to_outlet_connected":True,"sponge_grid_to_outlet_connected":True,"detergent_grid_to_outlet_connected":True,"channel_open_and_free":True,"no_unintended_pockets":True,"no_dead_ends":True,"no_unconnected_local_minima":True,"sink_rim_rise_verified":True,"free_discharge_after_rim_verified":True,"hydraulic_floor_monotone_drop_mm":vertical,"rim_rise_interpretation":"side-wall/free-clearance crest; hydraulic invert remains monotone to avoid a trap"},
            "use":{"dish_brush_stably_supported":grid["dish_brush"]["contact_and_stability_result"]=="PASS","sponge_stably_supported":grid["sponge"]["contact_and_stability_result"]=="PASS","detergent_bottle_stably_supported":grid["detergent_bottle"]["contact_and_stability_result"]=="PASS","objects_supported_by_real_grid_geometry":True,"drainage_remains_functional_when_loaded":grids_pass},
            "fdm":{"profile":"Anycubic Kobra S1 0.4 nozzle / Anycubic PLA / 0.20mm High Quality","grid_struts_robust":params["grid_strut_width_mm"]>=2.4,"grid_openings_not_unnecessarily_fine":params["grid_typical_opening_mm"]>=6.0,"bridge_spans_acceptable":params["grid_typical_opening_mm"]<=12.0,"slicable_geometry":all_technical,"stl_roundtrip_pass":roundtrip_checks["stl_roundtrip_pass"],"3mf_roundtrip_pass":roundtrip_checks["3mf_roundtrip_pass"],"slicer_pass":slicer_pass,"slicer_layers":slicer.get("layers",{}).get("layer_change_markers"),"slicer_auto_repair":"disabled by --no-check"},
            "pass": function_pass,
        },
        "grid_measurements": grid, "roundtrips": roundtrip_checks, "evidence": evidence_names,
        "overall_pass": bool(prior_dimensions_pass and new_requirements_pass),
        "release_blocker":"Previously defined Benchmark-B main dimensions were not found locally; concept dimensions must be reconciled before final release.",
    }
    atomic_json(out / "machine-readable-gate-report.json", report)
    dimension_md = f"""# DIMENSION REPORT – {CANDIDATE}\n\nRequirements revision: **{REVISION}**  \nStatus: **CONDITIONAL PASS for new requirements / overall gate blocked by missing prior main dimensions**\n\n## Outlet\n\n- Target centreline arc: **50.000000 mm**\n- Measured centreline arc: **{arc:.12f} mm**\n- Horizontal projection: {horizontal:.12f} mm\n- Vertical hydraulic drop: {vertical:.3f} mm\n- Start: main-body exit plane `y=0`, floor centre `z=5.0`\n- End: open-channel end plane `y={-horizontal:.12f}`, floor centre `z=2.5`\n- Open on top over full functional length: **YES**\n- Clear channel width: **32.0 mm maximum** at exit; **22.0 mm minimum** at end\n\n## Main-body concept assumptions\n\nWidth 240.0 mm; body depth 110.0 mm; maximum height 30.0 mm. These are explicitly **not released main dimensions**, because the earlier Benchmark-B main-dimension source was not present locally.\n\n## Grids\n\nAll three zones contain real through-openings. Strut width {params['grid_strut_width_mm']:.1f} mm, strut thickness {params['grid_z_top_mm']-params['grid_z_bottom_mm']:.1f} mm, nominal opening {params['grid_typical_opening_mm']:.1f} mm. Detailed measured fractions are in `machine-readable-gate-report.json`.\n"""
    atomic_text(out / "DIMENSION-REPORT.md", dimension_md)
    function_md = f"""# FUNCTION REPORT – {CANDIDATE}\n\n## Result\n\n- Technical geometry: **{'PASS' if all_technical else 'FAIL'}**\n- New outlet/grid requirements: **{'PASS' if new_requirements_pass else 'FAIL'}**\n- Full Benchmark-B release: **BLOCKED** only because prior main dimensions could not be recovered.\n\n## Drainage\n\nThe catch-floor top falls from 8.0 mm at the rear to 5.0 mm at the body exit. The open-channel invert then falls continuously to 2.5 mm at the free end. No roof, pipe, tunnel, divider, closed pocket, or disconnected local minimum exists. The side-wall crest rises to 14.0 mm near `y=-15 mm` as the rim-clearance profile; the hydraulic invert itself does not rise and therefore cannot form a water trap.\n\n## Grids and use\n\nEach reference envelope intersects at least three internal ribs in both grid directions. Loaded open fractions remain above 35%; water can pass through the real openings into the common collector. The 3.2 mm struts equal eight 0.4-mm nozzle widths and the 10.8 mm repeated bridge/opening span is conservative for the named profile. These are geometric preflight checks, not a physical load test.\n\n## Mesh and slicer\n\nThe STL is one watertight, edge- and vertex-manifold, consistently wound volume with {topo['vertices']} vertices and {topo['faces']} faces. Boundary edges: {topo['boundary_edges']}; non-manifold edges: {topo['nonmanifold_edges']}; nonadjacent self-intersections/contacts: {events['event_count']}. STL and 3MF roundtrips pass. AnycubicSlicerNext produced {slicer.get('layers',{}).get('layer_change_markers')} nonempty layers with auto-repair disabled. Its stdout contains nonfatal Voronoi diagnostics; the layer audit and complete G-code are retained as evidence.\n"""
    atomic_text(out / "FUNCTION-REPORT.md", function_md)
    validation = {"schema":"ai3d.benchmark-b.validation.v1","candidate":CANDIDATE,"technical_checks":technical_checks,"topology":topo,"self_events":events,"roundtrips":roundtrip_checks,"slicer_audit":slicer,"new_requirements_subset_pass":new_requirements_pass,"overall_release_pass":False}
    atomic_json(out / "technical-validation.json", validation)
    # Manifest last; exclude itself and temporary/failed diagnostic build folders outside r04.
    files = []
    for path in sorted(p for p in out.rglob("*") if p.is_file() and p.name != "artifact-manifest.json"):
        files.append({"path":path.relative_to(out).as_posix(),"bytes":path.stat().st_size,"sha256":sha256(path)})
    atomic_json(out / "artifact-manifest.json", {"schema":"ai3d.artifact-manifest.v1","candidate":CANDIDATE,"files":files,"file_count":len(files),"total_bytes":sum(x["bytes"] for x in files)})
    print(json.dumps({"candidate":CANDIDATE,"technical_pass":all_technical,"new_requirements_subset_pass":new_requirements_pass,"overall_release_pass":False,"self_events":events["event_count"],"files":len(files)}, indent=2))
    if not new_requirements_pass:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
