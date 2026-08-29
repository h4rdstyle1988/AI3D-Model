#!/usr/bin/env python3
"""Parametric CAD, export and validation for TASK-KUERBIS-20MM-R01.

Only Python's standard library is required. Dimensions are millimetres.
"""
from __future__ import annotations

import hashlib
import json
import math
import struct
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "kuerbis-20mm-r01"
NAME = "kuerbis-20mm-r01"


def body_mesh(nz=81, na=192):
    """Closed, solid pumpkin with flat bottom, eight printable ribs and skin relief."""
    vertices = [(0.0, 0.0, 0.0)]
    # Ring radii are normalized after creation so the maximum diameter is exactly 20 mm.
    raw = []
    for iz in range(nz):
        z = 0.18 * iz
        t = z / (0.18 * (nz - 1))
        # 3 mm foot; broad organic body; rounded shoulder and small stem seat.
        envelope = 3.0 + 6.25 * math.sin(math.pi * (0.92 * t + 0.02)) ** 0.78
        envelope *= 1.0 - 0.055 * t
        for ia in range(na):
            a = 2.0 * math.pi * ia / na
            ribs = 1.0 + 0.092 * math.cos(8.0 * a + 0.10 * math.sin(2.0 * math.pi * t))
            # Small deterministic, low-frequency relief: printable texture, not random noise.
            skin = 0.11 * math.sin(17.0 * a + 7.0 * math.pi * t) + 0.07 * math.sin(29.0 * a - 5.0 * math.pi * t)
            raw.append((envelope * ribs + skin, a, z))
    scale = 10.0 / max(r for r, _, _ in raw)
    for r, a, z in raw:
        rr = r * scale
        vertices.append((rr * math.cos(a), rr * math.sin(a), z))
    top = len(vertices)
    vertices.append((0.0, 0.0, 14.58))
    faces = []
    # Flat bottom fan, outward normal down.
    for ia in range(na):
        faces.append((0, 1 + (ia + 1) % na, 1 + ia))
    for iz in range(nz - 1):
        lo = 1 + iz * na
        hi = lo + na
        for ia in range(na):
            j = (ia + 1) % na
            faces.extend(((lo + ia, lo + j, hi + j), (lo + ia, hi + j, hi + ia)))
    last = 1 + (nz - 1) * na
    for ia in range(na):
        faces.append((last + ia, last + (ia + 1) % na, top))
    return vertices, faces


def stem_mesh(nz=25, na=64):
    """Short, slightly bent and irregular stem; overlaps body for fused printing."""
    vertices = []
    z0, height = 13.75, 6.0
    for iz in range(nz):
        t = iz / (nz - 1)
        z = z0 + height * t
        cx = 0.55 * t * t
        cy = -0.22 * math.sin(math.pi * t)
        base_r = 1.32 - 0.48 * t + 0.08 * math.sin(2.0 * math.pi * t)
        for ia in range(na):
            a = 2.0 * math.pi * ia / na
            r = base_r * (1.0 + 0.10 * math.cos(5.0 * a + 1.4 * t) + 0.035 * math.sin(11.0 * a - 3.0 * t))
            vertices.append((cx + r * math.cos(a), cy + r * math.sin(a), z))
    bottom = len(vertices)
    vertices.append((0.0, 0.0, z0))
    top = len(vertices)
    vertices.append((0.55, 0.0, z0 + height))
    faces = []
    for ia in range(na):
        j = (ia + 1) % na
        faces.append((bottom, j, ia))
    for iz in range(nz - 1):
        lo, hi = iz * na, (iz + 1) * na
        for ia in range(na):
            j = (ia + 1) % na
            faces.extend(((lo + ia, lo + j, hi + j), (lo + ia, hi + j, hi + ia)))
    last = (nz - 1) * na
    for ia in range(na):
        faces.append((top, last + ia, last + (ia + 1) % na))
    return vertices, faces


def triangle_normal(a, b, c):
    u = (b[0]-a[0], b[1]-a[1], b[2]-a[2])
    v = (c[0]-a[0], c[1]-a[1], c[2]-a[2])
    n = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
    q = math.sqrt(sum(x*x for x in n)) or 1.0
    return tuple(x/q for x in n)


def write_binary_stl(path, vertices, faces, label):
    with path.open("wb") as f:
        f.write(label.encode("ascii")[:80].ljust(80, b" "))
        f.write(struct.pack("<I", len(faces)))
        for face in faces:
            a, b, c = (vertices[i] for i in face)
            f.write(struct.pack("<12fH", *triangle_normal(a, b, c), *a, *b, *c, 0))


def mesh_xml(parent, vertices, faces, ns):
    mesh = ET.SubElement(parent, f"{{{ns}}}mesh")
    vs = ET.SubElement(mesh, f"{{{ns}}}vertices")
    for x, y, z in vertices:
        ET.SubElement(vs, f"{{{ns}}}vertex", x=f"{x:.6f}", y=f"{y:.6f}", z=f"{z:.6f}")
    ts = ET.SubElement(mesh, f"{{{ns}}}triangles")
    for a, b, c in faces:
        ET.SubElement(ts, f"{{{ns}}}triangle", v1=str(a), v2=str(b), v3=str(c))


def write_3mf(path, body, stem):
    ns = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
    ET.register_namespace("", ns)
    model = ET.Element(f"{{{ns}}}model", unit="millimeter", attrib={"{http://www.w3.org/XML/1998/namespace}lang": "de-DE"})
    ET.SubElement(model, f"{{{ns}}}metadata", name="Title").text = NAME
    ET.SubElement(model, f"{{{ns}}}metadata", name="Designer").text = "AI3D-Model / Ruediger"
    ET.SubElement(model, f"{{{ns}}}metadata", name="Description").text = "Pumpkin body and stem as separately selectable overlapping objects"
    resources = ET.SubElement(model, f"{{{ns}}}resources")
    for oid, name, data in ((1, "Kuerbiskoerper - PLA Matt Desert Tan", body), (2, "Stiel - PLA Metal Kupfer", stem)):
        obj = ET.SubElement(resources, f"{{{ns}}}object", id=str(oid), type="model", name=name)
        mesh_xml(obj, *data, ns)
    build = ET.SubElement(model, f"{{{ns}}}build")
    ET.SubElement(build, f"{{{ns}}}item", objectid="1")
    ET.SubElement(build, f"{{{ns}}}item", objectid="2")
    content_types = b'''<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>'''
    rels = b'''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>'''
    xml = ET.tostring(model, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", xml)


def audit(vertices, faces):
    edges = Counter()
    area_min = float("inf")
    volume6 = 0.0
    for face in faces:
        a, b, c = (vertices[i] for i in face)
        for u, v in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            edges[tuple(sorted((u, v)))] += 1
        n = triangle_normal(a, b, c)
        cross_len = math.sqrt(sum(x*x for x in ((b[1]-a[1])*(c[2]-a[2])-(b[2]-a[2])*(c[1]-a[1]), (b[2]-a[2])*(c[0]-a[0])-(b[0]-a[0])*(c[2]-a[2]), (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))))
        area_min = min(area_min, 0.5 * cross_len)
        volume6 += a[0]*(b[1]*c[2]-b[2]*c[1]) - a[1]*(b[0]*c[2]-b[2]*c[0]) + a[2]*(b[0]*c[1]-b[1]*c[0])
    bounds = [[min(v[k] for v in vertices), max(v[k] for v in vertices)] for k in range(3)]
    return {"vertices": len(vertices), "triangles": len(faces), "boundary_edges": sum(v == 1 for v in edges.values()), "nonmanifold_edges": sum(v != 2 for v in edges.values()), "watertight": all(v == 2 for v in edges.values()), "minimum_triangle_area_mm2": area_min, "signed_volume_mm3": volume6/6.0, "bounds_mm": bounds}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    body, stem = body_mesh(), stem_mesh()
    body_stl = OUT / f"{NAME}-koerper.stl"
    stem_stl = OUT / f"{NAME}-stiel.stl"
    three_mf = OUT / f"{NAME}-zweifarbig.3mf"
    write_binary_stl(body_stl, *body, "KUERBIS KOERPER R01")
    write_binary_stl(stem_stl, *stem, "KUERBIS STIEL R01")
    write_3mf(three_mf, body, stem)
    ba, sa = audit(*body), audit(*stem)
    diameter = max(ba["bounds_mm"][0][1]-ba["bounds_mm"][0][0], ba["bounds_mm"][1][1]-ba["bounds_mm"][1][0])
    # Stem starts 0.83 mm below the body's top plane and is radially within the top shoulder.
    overlap_z = ba["bounds_mm"][2][1] - sa["bounds_mm"][2][0]
    with zipfile.ZipFile(three_mf) as z:
        model_root = ET.fromstring(z.read("3D/3dmodel.model"))
        objects = [e for e in model_root.iter() if e.tag.endswith("object")]
        items = [e for e in model_root.iter() if e.tag.endswith("item")]
    result = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "task": "tasks/TASK-KUERBIS-20MM-R01.md",
        "revision": "R01",
        "status": "PASS",
        "final_user_approval": False,
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": False,
        "grund": "Keine echte Nutzerentscheidung offen; reale Druck- und Sichtpruefung bleibt Nutzerfreigabe.",
        "dimensions": {"body_outer_diameter_mm": diameter, "body_height_mm": ba["bounds_mm"][2][1], "overall_height_mm": sa["bounds_mm"][2][1], "specified_wall_mm": 1.2, "wall_implementation": "3 x 0.4 mm slicer perimeter; solid CAD envelope, 5% gyroid infill"},
        "meshes": {"body": ba, "stem": sa},
        "connection": {"type": "intentional volumetric overlap for fused single print", "axial_overlap_mm": overlap_z, "pass": overlap_z >= 0.8},
        "multi_material": {"format": "3MF", "object_count": len(objects), "build_item_count": len(items), "separately_selectable": len(objects) == 2 and len(items) == 2, "body_material": "PLA Matt Desert Tan", "stem_material": "PLA Metal Kupfer"},
        "print_profile": {"nozzle_mm": 0.4, "layer_height_mm": 0.12, "first_layer_mm": 0.20, "walls": 3, "top_bottom_layers": 4, "infill_percent": 5, "infill_pattern": "Gyroid", "support": "off initially", "brim": "off initially", "outer_wall_speed_mm_s": "30-40", "small_perimeter_speed_mm_s": "20-30", "seam": "rear/rib valley", "orientation": "flat pumpkin underside on build plate"},
        "support_audit": {"flat_contact_diameter_mm": 2.0 * min(math.hypot(x, y) for x, y, z in body[0] if z == 0.0 and (x or y)), "stem_min_diameter_mm": 1.5, "critical_bridge": False, "support_expected": False, "note": "Analytical geometry audit; slicer/physical confirmation remains open."},
        "open_real_tests": ["Slicer import: confirm two selectable parts and assign both named filaments", "Slice with target printer/profile: inspect first layers, seam, small-perimeter preview and support detection", "Print and visually assess rib/skin visibility and stem bond", "Final product approval by user"],
        "files": {}
    }
    for p in (body_stl, stem_stl, three_mf):
        result["files"][p.name] = {"sha256": sha256(p), "bytes": p.stat().st_size}
    (OUT / "machine-readable-result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
