#!/usr/bin/env python3
"""Render the actual deterministic R11 master candidate for the optic gate."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from PIL import Image

from reconstruct_deterministic_body_r11 import read_binary_ply


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
MASTER = OUT / "masterform" / "herbst-igel-r02-masterform-deterministic-r11-NON-APPROVED.ply"
RAW = OUT / "source-seed42" / "herbst-igel-r02-trellis-raw-seed-42.ply"
REF = OUT / "reference-audit" / "ref-clean-r11.jpg"
SEAM = OUT / "reference-audit" / "ref-seam-r11.jpg"
RENDERS = OUT / "renders-optik-gate"
REPORT = OUT / "reports" / "real-geometry-renders-r11.json"
R10_RENDER_BLOB = "5852187b6f3827c910a9d61afcfb44bfa7fa7fbb"


def load_render_primitives() -> dict[str, object]:
    code = subprocess.check_output(["git", "cat-file", "blob", R10_RENDER_BLOB], cwd=ROOT).decode("utf-8")
    code = code.replace("from reconstruct_implicit_body_r10 import read_binary_ply", "")
    namespace: dict[str, object] = {
        "__name__": "r10_render_primitives",
        "__file__": str(OUT / "reproduction-scripts" / "r10_render_primitives.py"),
        "read_binary_ply": read_binary_ply,
    }
    exec(compile(code, namespace["__file__"], "exec"), namespace)
    return namespace


R = load_render_primitives()
render = R["render"]
sheet = R["sheet"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    RENDERS.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    vertices, faces = read_binary_ply(MASTER)
    views = [
        ("3q-front", (-1.0, -1.0, 0.35), "3/4 vorne"),
        ("left", (0.0, -1.0, 0.12), "links / Referenzseite"),
        ("right", (0.0, 1.0, 0.12), "rechts"),
        ("rear", (1.0, 0.0, 0.12), "hinten"),
        ("top", (0.0, 0.0, 1.0), "oben"),
        ("bottom", (0.0, 0.0, -1.0), "unten"),
    ]
    paths: list[Path] = []
    records: list[dict[str, object]] = []
    for slug, camera, label in views:
        path = RENDERS / f"masterform-{slug}.png"
        render(vertices, faces, camera, path, f"R11 DETERMINISTISCH (NICHT FREIGEGEBEN): {label}")
        paths.append(path)
        records.append({"view": slug, "camera_vector": list(camera), "path": path.relative_to(ROOT).as_posix()})
    preliminary = RENDERS / "preliminary-front-sides-r11.png"
    sheet(paths[:3], [x[2] for x in views[:3]], preliminary, 3, (520, 520))
    contact = RENDERS / "masterform-contact-sheet-r11.png"
    sheet(paths, [x[2] for x in views], contact, 3, (520, 520))

    raw_vertices, raw_faces = read_binary_ply(RAW)
    raw_cmp = RENDERS / "raw-seed42-3q-front-comparison.png"
    render(raw_vertices, raw_faces, views[0][1], raw_cmp, "Seed 42 roh: 3/4 vorne")
    soll_ist = RENDERS / "soll-ist-optik-gate-r11.png"
    sheet(
        [REF, SEAM, raw_cmp, paths[0], paths[1], paths[2]],
        ["SOLL REF-CLEAN", "SOLL REF-SEAM", "IST Seed 42 roh", "IST R11 3/4", "IST R11 Referenzseite", "IST R11 Gegenseite"],
        soll_ist,
        3,
        (520, 520),
    )
    payload = {
        "schema_version": 1,
        "task": "tasks/TASK-HERBST-IGEL-R02-DETERMINISTIC-BODY-REBUILD-R11.md",
        "source_geometry": MASTER.relative_to(ROOT).as_posix(),
        "source_geometry_sha256": sha256(MASTER),
        "source_is_actual_reconstructed_geometry": True,
        "approval_status": "NON_APPROVED_PENDING_OPTIK_GATE",
        "preliminary_front_sides": preliminary.relative_to(ROOT).as_posix(),
        "selected_views": records,
        "contact_sheet": contact.relative_to(ROOT).as_posix(),
        "soll_ist_sheet": soll_ist.relative_to(ROOT).as_posix(),
        "reference_files_untouched": {
            "clean_sha256": sha256(REF),
            "seam_sha256": sha256(SEAM),
        },
    }
    REPORT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
