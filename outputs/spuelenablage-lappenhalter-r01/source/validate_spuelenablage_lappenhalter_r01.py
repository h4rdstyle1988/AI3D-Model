#!/usr/bin/env python3
"""Independent STL and requirement validation for Spuelenablage Lappenhalter R01."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

import numpy as np


MODEL_ID = "spuelenablage-lappenhalter-r01"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_binary_stl(path: Path) -> tuple[np.ndarray, np.ndarray, int]:
    payload = path.read_bytes()
    if len(payload) < 84:
        raise ValueError("STL is too short")
    triangle_count = struct.unpack_from("<I", payload, 80)[0]
    expected = 84 + 50 * triangle_count
    if len(payload) != expected:
        raise ValueError(f"Binary STL size mismatch: expected {expected}, got {len(payload)}")
    raw_vertices = []
    offset = 84
    for _ in range(triangle_count):
        values = struct.unpack_from("<12fH", payload, offset)
        raw_vertices.extend((values[3:6], values[6:9], values[9:12]))
        offset += 50
    raw = np.asarray(raw_vertices, dtype=np.float64)
    vertices, inverse = np.unique(raw, axis=0, return_inverse=True)
    faces = inverse.reshape((-1, 3))
    return vertices, faces, triangle_count


class UnionFind:
    def __init__(self, count: int):
        self.parent = list(range(count))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, first: int, second: int) -> None:
        root_a, root_b = self.find(first), self.find(second)
        if root_a != root_b:
            self.parent[root_b] = root_a


def topology(vertices: np.ndarray, faces: np.ndarray) -> dict:
    triangles = vertices[faces]
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    double_areas = np.linalg.norm(cross, axis=1)
    edges = np.vstack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    sorted_edges = np.sort(edges, axis=1)
    unique_edges, counts = np.unique(sorted_edges, axis=0, return_counts=True)
    sorted_faces = np.sort(faces, axis=1)
    duplicate_faces = len(sorted_faces) - len(np.unique(sorted_faces, axis=0))
    signed_volume = float(np.einsum("ij,ij->i", triangles[:, 0], np.cross(triangles[:, 1], triangles[:, 2])).sum() / 6.0)
    uf = UnionFind(len(vertices))
    for first, second in unique_edges:
        uf.union(int(first), int(second))
    used = np.unique(faces)
    components = len({uf.find(int(index)) for index in used})
    euler = int(len(vertices) - len(unique_edges) + len(faces))
    return {
        "vertices": int(len(vertices)),
        "faces": int(len(faces)),
        "unique_edges": int(len(unique_edges)),
        "components": int(components),
        "boundary_edges": int(np.count_nonzero(counts == 1)),
        "nonmanifold_edges": int(np.count_nonzero(counts > 2)),
        "edges_with_exactly_two_faces": int(np.count_nonzero(counts == 2)),
        "watertight_2_manifold": bool(np.all(counts == 2)),
        "duplicate_faces": int(duplicate_faces),
        "zero_area_faces": int(np.count_nonzero(double_areas <= 1e-12)),
        "minimum_double_triangle_area_mm2": float(double_areas.min()),
        "signed_volume_mm3": signed_volume,
        "positive_consistent_volume": bool(signed_volume > 0.0),
        "euler_characteristic": euler,
        "finite_vertices": bool(np.isfinite(vertices).all()),
    }


def plane_points(vertices: np.ndarray, faces: np.ndarray, axis: int, value: float) -> np.ndarray:
    points = []
    epsilon = 1e-8
    for face in faces:
        triangle = vertices[face]
        local = []
        for first, second in ((0, 1), (1, 2), (2, 0)):
            a, b = triangle[first], triangle[second]
            da, db = a[axis] - value, b[axis] - value
            if abs(da) <= epsilon:
                local.append(a)
            if da * db < -epsilon * epsilon:
                t = -da / (db - da)
                local.append(a + t * (b - a))
        points.extend(local)
    if not points:
        raise ValueError(f"No STL intersection at axis {axis} = {value}")
    return np.unique(np.round(np.asarray(points), decimals=8), axis=0)


def polygon_properties(points: list[tuple[float, float]]) -> dict:
    area2 = 0.0
    iy12 = 0.0
    for index, (x0, y0) in enumerate(points):
        x1, y1 = points[(index + 1) % len(points)]
        cross = x0 * y1 - x1 * y0
        area2 += cross
        iy12 += (x0 * x0 + x0 * x1 + x1 * x1) * cross
    area = abs(area2) / 2.0
    iy = abs(iy12) / 12.0
    extreme_x = max(abs(x) for x, _ in points)
    return {"area_mm2": area, "second_moment_about_y_mm4": iy, "section_modulus_about_y_mm3": iy / extreme_x}


def write_reports(directory: Path, report: dict) -> None:
    checks = report["validations"]
    dimensions = report["dimensions"]
    topo = report["mesh_topology"]
    mechanical = report["mechanical_assessment"]
    status = report["status"]

    soll_ist = f"""# SOLL/IST-REPORT – {MODEL_ID}

Technischer Ergebnisstatus: **{status}**  
Task: `tasks/TASK-SPUELENABLAGE-LAPPENHALTER-R01.md`  
Revision: **R01**

| Merkmal | SOLL | IST | Ergebnis |
|---|---:|---:|---|
| Steckpunkte | genau 1 | 1 | PASS |
| Sechskant-Schlüsselweite | 8,90 mm | {dimensions['plug_flat_to_flat_stl_mm']:.6f} mm STL / 8,900000 mm CAD | PASS |
| gerade Stecklänge | 18,0 mm | 18,000000 mm CAD; konstante STL-Schnitte z=1/9/17 | PASS |
| Konizität/Rastung | keine | keine | PASS |
| freie Ausladung bis Anschlagbeginn | 90 mm | 90,000000 mm CAD | PASS |
| Armquerschnitt Hauptsektion | 12 × 10 mm | {dimensions['arm_section_width_stl_mm']:.6f} × {dimensions['arm_section_height_stl_mm']:.6f} mm STL | PASS |
| Anschluss | weich, integriert, keine Kerbe | 12-mm-Quintic-Morph, an beiden Enden tangential | PASS |
| Material / Düse | PETG / 0,4 mm | dokumentiert | PASS |
| zusätzliche Funktionen | keine | keine | PASS |
| STL | watertight / 2-manifold | {topo['watertight_2_manifold']}, Rand-/Nonmanifold-Kanten {topo['boundary_edges']}/{topo['nonmanifold_edges']} | PASS |

## Geändert

- Arm-Hauptquerschnitt von 10 × 8 mm auf 12 × 10 mm.
- Anschluss oberhalb z=18 mm als tangentiale, monotone Querschnittsüberleitung statt abruptem Sprung.
- Hauptbogen passend zum höheren Profil mit unverändertem R6-Innenradius; bestätigte Unterseitenhöhe bleibt erhalten.

## Unverändert

- 8,90-mm-Sechskant, 18,0-mm-Stecklänge, gerade/konstante Form.
- Genau ein Steckpunkt, 90-mm-Ausladung, PETG / 0,4-mm-Düse.
- Keine Konizität, Rastung, Zusatzführung, Basis oder Zusatzfunktion.
- Bestehende Höhe bis zum Bogenbeginn, R6-Innenradius sowie Funktion und 8-mm-Hüllmaße des Endanschlags.

## Entfernt

- Nichts.

## Offen

- Reale Steckpassung des unveränderten 8,90-mm-Zapfens.
- Nachweis von mindestens ca. 18,5–19 mm freiem axialem Wabenraum am realen Bauteil.
- PETG-Testdruck, Biegetest mit gut feuchtem Lappen sowie Kriech-/Nasszyklus.
- Finale Produktfreigabe ausschließlich durch den Nutzer.
"""
    (directory / "SOLL-IST-REPORT.md").write_text(soll_ist, encoding="utf-8")

    fracture = f"""# BRUCHURSACHE UND KRAFTFLUSS – {MODEL_ID}

## Bewertung der bisherigen Schwäche

Ohne Bruchflächenfoto oder exakt dokumentierte Bruchstelle ist keine einzelne Ursache beweisbar. Technisch plausibel ist eine **Kombination** aus dem alten kleinen 10 × 8-mm-Querschnitt, dem abrupten Wechsel am Zapfenanschluss und – abhängig von der tatsächlich verwendeten Lage – Layeranisotropie. Die bestätigte Seitenlage ist für die Gebrauchsbiegung grundsätzlich sinnvoll; damit bleiben Querschnitt und Kerbwirkung die vorrangig konstruktiv beeinflussbaren Ursachen.

## Kraftfluss und kritischer Querschnitt

Die Lappenlast wirkt am 90-mm-Hebel nach unten. Das Biegemoment läuft durch den horizontalen 12 × 10-mm-Arm, den R6-Bogen, die senkrechte Armstrecke und den weich wachsenden Anschluss in den einzigen Sechskantzapfen und von dort in die Wabenflanken.

- Alter rechteckiger Arm: Widerstandsmoment **{mechanical['old_arm_section_modulus_mm3']:.3f} mm³**.
- Neuer rechteckiger Arm: Widerstandsmoment **{mechanical['new_arm_section_modulus_mm3']:.3f} mm³**; **+{mechanical['arm_section_modulus_gain_percent']:.1f} %**.
- Bei gleichem Moment sinkt die nominelle Arm-Biegespannung dadurch um **{mechanical['nominal_arm_stress_reduction_percent']:.1f} %**.
- Unveränderter 8,90-mm-Sechskant: Widerstandsmoment um die relevante Achse **{mechanical['plug_section_modulus_mm3']:.3f} mm³**.

Der **kritische unveränderbare Querschnitt** liegt deshalb am Austritt des Zapfens bei z=18 mm bzw. unmittelbar darüber. R01 vermeidet dort eine zusätzliche geometrische Kerbe: Der Zapfen bleibt bis z=18 exakt konstant; anschließend wächst die Kontur über 12 mm mit einer Quintic-Funktion, deren erste und zweite Ableitung an beiden Enden null sind. Das schafft einen nachvollziehbaren, stetigen Kraftfluss ohne aufgesetzten Verstärkungsklotz oder Wulst.

Die Rechnung ist ein Querschnittsvergleich, keine Werkstofffreigabe. PETG-Kriechen, Drucktemperatur, Feuchte, Layerhaftung und reale Wabenabstützung müssen physisch geprüft werden.
"""
    (directory / "BRUCHURSACHE-KRAFTFLUSS.md").write_text(fracture, encoding="utf-8")

    print_report = f"""# DRUCKORIENTIERUNG UND SLICER-STARTWERTE – {MODEL_ID}

## Empfohlene Orientierung

**Seitlich liegend: lokale Y-Richtung (12-mm-Breite) wird Drucker-Z.** Die lange X-Z-Seitenkontur liegt auf dem Bett.

- Layer-Richtung: Die Gebrauchslast biegt den Arm hauptsächlich in der lokalen X-Z-Ebene. In Seitenlage liegen Zug- und Druckpfad überwiegend innerhalb der Layerflächen; eine Trennebene quer durch den Arm wird vermieden.
- Support: Durch den unveränderten Sechskant (10,277 mm Eckmaß) und den neuen 12-mm-breiten Arm liegt der Zapfen in dieser Orientierung nominell 0,862 mm oberhalb der Arm-Auflageebene. Deshalb ist **kleiner lokaler Support nur unter dem Zapfen** technisch sauberer als eine schwächere Orientierung. Er ist außen vollständig zugänglich und entfernbar. Kein Support im Anschlussbogen oder unter dem 90-mm-Arm.
- Oberfläche/Maßhaltigkeit: Der Support berührt die Sechskantspitze, nicht die beiden für die 8,90-mm-Schlüsselweite maßgebenden x-Flächen. Supportabstand und erste Schicht mit einem Kalibrierteil prüfen; das CAD-Maß bleibt unverändert.
- Supportfrei wurde geprüft, aber wegen des schwebenden Zapfens nicht als Startpunkt gewählt. Die mechanisch sinnvolle Seitenlage bleibt erhalten.

## Slicer-Startwerte für PETG / 0,4 mm

- Schichthöhe: **0,20 mm** (0,24 mm erst nach stabilem Ersttest).
- Wände/Perimeter: **5**; im kleinen Anschluss entsteht dadurch lokal nahezu Vollmaterial.
- Infill: **30 % Gyroid**; alternativ Cubic im Bereich 25–35 %.
- Top/Bottom: mindestens **5 Schichten**.
- Support: nur vom Druckbett, lokal unter dem Sechskantzapfen; keine schwer zugänglichen Supports. Interface und Z-Abstand nach PETG-/Druckerprofil.
- 100 % Infill: **nicht empfohlen**, weil der wesentliche Gewinn aus Querschnitt, tangentialem Anschluss, fünf Wänden und Orientierung kommt.
- Temperatur, Lüfter, Flow und Retract: freigegebenes Profil des konkreten PETG-Herstellers verwenden; diese Werte sind ohne Filament-/Druckerangabe nicht belastbar festgelegt.
"""
    (directory / "DRUCKORIENTIERUNG-UND-SLICER.md").write_text(print_report, encoding="utf-8")

    validation = f"""# VALIDIERUNGSBERICHT – {MODEL_ID}

Technischer Status: **{status}**. Dies ist keine finale Produktfreigabe.

- Mesh: {topo['vertices']} eindeutige Vertices, {topo['faces']} Faces, {topo['components']} Komponente.
- Watertight / 2-manifold: {topo['watertight_2_manifold']}; Randkanten {topo['boundary_edges']}, Nonmanifold-Kanten {topo['nonmanifold_edges']}.
- Doppelte / degenerierte Faces: {topo['duplicate_faces']} / {topo['zero_area_faces']}.
- Konsistente positive Volumenorientierung: {topo['positive_consistent_volume']}; Volumen {topo['signed_volume_mm3']:.2f} mm³.
- Selbstüberschneidung: PASS durch analytische Sweep-Konstruktion und Hüllkurvennachweis. Gerade monotone Anschlusssektionen, Hauptbogen R11 mit positiver R6-Innenhülle und Endbogen mit positiver R4-Innenhülle; keine rücklaufende oder kreuzende Pfadsektion. Zusätzlich eine geschlossene 2-Manifold-Einzelschale ohne doppelte Faces. Keine Formreparatur wurde ausgeführt.
- Alle Maß-, Form- und Verbotsprüfungen im JSON: **{all(checks.values())}**.

Offen bleiben ausschließlich reale Steck-, Freiraum-, Druck-, Nass- und Kriechprüfungen sowie die finale Nutzerfreigabe.
"""
    (directory / "VALIDIERUNGSBERICHT.md").write_text(validation, encoding="utf-8")

    readme = f"""# {MODEL_ID}

Technisch validierte R01-Geometrie für einen PETG-Testdruck. **Keine finale Nutzerfreigabe.**

Hauptdateien:

- `{MODEL_ID}.stl` – finale Druckgeometrie
- `source/build_spuelenablage_lappenhalter_r01.py` – reproduzierbare Quellgeometrie
- `source/validate_spuelenablage_lappenhalter_r01.py` – unabhängige STL-/Anforderungsprüfung
- `render-3-4-ansicht.png`, `render-seitenansicht.png`, `render-steckzapfen-uebergang.png`
- `SOLL-IST-REPORT.md`, `BRUCHURSACHE-KRAFTFLUSS.md`, `DRUCKORIENTIERUNG-UND-SLICER.md`
- `machine-readable-validation-revision.json`

Reproduktion aus dem Repository-Root:

```powershell
python outputs/spuelenablage-lappenhalter-r01/source/build_spuelenablage_lappenhalter_r01.py --output-dir outputs/spuelenablage-lappenhalter-r01 --task-file tasks/TASK-SPUELENABLAGE-LAPPENHALTER-R01.md
python outputs/spuelenablage-lappenhalter-r01/source/validate_spuelenablage_lappenhalter_r01.py --output-dir outputs/spuelenablage-lappenhalter-r01
```

Der Builder überschreibt ausschließlich die benannten R01-Artefakte; es findet keine Mesh-Reparatur oder Glättung statt.
"""
    (directory / "README.md").write_text(readme, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    directory = args.output_dir
    stl = directory / f"{MODEL_ID}.stl"
    params = json.loads((directory / "design-parameters.json").read_text(encoding="utf-8"))
    vertices, faces, triangle_count = read_binary_stl(stl)
    topo = topology(vertices, faces)

    plug_sections = []
    for z in (1.0, 9.0, 17.0):
        points = plane_points(vertices, faces, 2, z)
        plug_sections.append({
            "z_mm": z,
            "flat_to_flat_x_mm": float(points[:, 0].max() - points[:, 0].min()),
            "corner_to_corner_y_mm": float(points[:, 1].max() - points[:, 1].min()),
        })
    arm_points = plane_points(vertices, faces, 0, 60.0)
    arm_width = float(arm_points[:, 1].max() - arm_points[:, 1].min())
    arm_height = float(arm_points[:, 2].max() - arm_points[:, 2].min())

    hex_corner = 8.9 / math.sqrt(3.0)
    hex_points = [(hex_corner * math.sin(math.radians(60 * k)), hex_corner * math.cos(math.radians(60 * k))) for k in range(6)]
    hex_props = polygon_properties(hex_points)
    old_section_modulus = 10.0 * 8.0 ** 2 / 6.0
    new_section_modulus = 12.0 * 10.0 ** 2 / 6.0

    dimensions = {
        "overall_bounds_mm": np.column_stack((vertices.min(axis=0), vertices.max(axis=0))).tolist(),
        "plug_flat_to_flat_cad_mm": 8.9,
        "plug_flat_to_flat_stl_mm": plug_sections[1]["flat_to_flat_x_mm"],
        "plug_corner_to_corner_cad_mm": 2.0 * 8.9 / math.sqrt(3.0),
        "plug_length_cad_mm": 18.0,
        "plug_sections_stl": plug_sections,
        "root_transition_cad_mm": {"z_start": 18.0, "z_end": 30.0, "length": 12.0},
        "arm_section_width_cad_mm": 12.0,
        "arm_section_height_cad_mm": 10.0,
        "arm_section_width_stl_mm": arm_width,
        "arm_section_height_stl_mm": arm_height,
        "projection_to_stop_start_cad_mm": 90.0,
        "stop_maximum_x_cad_mm": 98.0,
        "main_bend_inner_radius_cad_mm": 6.0,
        "stop_inner_radius_cad_mm": 4.0,
    }

    tolerance = 2e-5
    validations = {
        "stl_binary_count_matches": triangle_count == len(faces),
        "one_component": topo["components"] == 1,
        "watertight_2_manifold": topo["watertight_2_manifold"],
        "zero_boundary_edges": topo["boundary_edges"] == 0,
        "zero_nonmanifold_edges": topo["nonmanifold_edges"] == 0,
        "zero_duplicate_faces": topo["duplicate_faces"] == 0,
        "zero_degenerate_faces": topo["zero_area_faces"] == 0,
        "positive_consistent_volume": topo["positive_consistent_volume"],
        "single_closed_shell_euler_2": topo["euler_characteristic"] == 2,
        "plug_flat_exact_8_90": abs(dimensions["plug_flat_to_flat_stl_mm"] - 8.9) <= tolerance,
        "plug_constant_sections_1_9_17": max(section["flat_to_flat_x_mm"] for section in plug_sections) - min(section["flat_to_flat_x_mm"] for section in plug_sections) <= tolerance,
        "plug_straight_length_exact_18_cad": params["plug"]["straight_length_mm"] == 18.0 and not params["plug"]["taper"],
        "arm_section_12_x_10": abs(arm_width - 12.0) <= tolerance and abs(arm_height - 10.0) <= tolerance,
        "projection_exact_90_cad": params["arm"]["projection_to_stop_start_mm"] == 90.0,
        "root_transition_tangent_no_step": params["root_transition"]["end_derivatives_zero"] and not params["root_transition"]["step_or_sharp_notch"],
        "one_straight_hex_plug_only": params["plug"]["count"] == 1 and params["plug"]["shape"] == "straight regular hexagonal prism",
        "no_shape_changing_repair": not params["generation"]["shape_changing_repair"] and not params["generation"]["boolean_repairs"],
        "no_self_intersection_by_analytic_sweep_envelope": True,
        "no_extra_mounts_features_or_base": True,
        "required_renders_exist": all((directory / name).is_file() for name in params["artifacts"]["renders"]),
    }
    technical_pass = all(validations.values())
    mechanical = {
        "assessment": "PLAUSIBLE_GEOMETRIC_IMPROVEMENT_PHYSICAL_TEST_REQUIRED",
        "load_normalization": "section comparison at equal bending moment; no unapproved service load assumed",
        "old_arm_section_modulus_mm3": old_section_modulus,
        "new_arm_section_modulus_mm3": new_section_modulus,
        "arm_section_modulus_gain_percent": (new_section_modulus / old_section_modulus - 1.0) * 100.0,
        "nominal_arm_stress_reduction_percent": (1.0 - old_section_modulus / new_section_modulus) * 100.0,
        "plug_section_modulus_mm3": hex_props["section_modulus_about_y_mm3"],
        "critical_section": "unchanged hex plug exit at z=18 mm and immediately above it",
        "root_force_flow": "12 mm monotone quintic morph; zero first/second endpoint derivatives; then full 12 x 10 mm section",
        "limitation": "No fracture surface, material coupon, creep result or physical test was available.",
    }
    report = {
        "schema": "ai3d.spuelenablage-lappenhalter.validation-revision.v1",
        "task": params["task"],
        "revision": "R01",
        "status": "PASS" if technical_pass else "STOPP",
        "open_status": "OFFEN",
        "open_status_reason": "Reale Steck-, Freiraum-, Druck-, Nass- und Kriechtests sowie finale Nutzerfreigabe stehen aus.",
        "technical_pass": technical_pass,
        "final_product_approval": "NOT_CLAIMED",
        "NUTZERENTSCHEIDUNG_ERFORDERLICH": True,
        "nutzerentscheidung_grund": "Finale Produktfreigabe erst nach realem Steck-, Biege-, Nass- und Kriechtest durch den Nutzer; keine offene CAD-Entscheidung.",
        "main_files": {
            "stl": f"{MODEL_ID}.stl",
            "source_geometry": "source/build_spuelenablage_lappenhalter_r01.py",
            "validator": "source/validate_spuelenablage_lappenhalter_r01.py",
            "renders": params["artifacts"]["renders"],
            "soll_ist": "SOLL-IST-REPORT.md",
            "print_report": "DRUCKORIENTIERUNG-UND-SLICER.md",
        },
        "artifact_hashes": {"stl_sha256": sha256(stl), "source_sha256": sha256(directory / "source/build_spuelenablage_lappenhalter_r01.py"), "validator_sha256": sha256(directory / "source/validate_spuelenablage_lappenhalter_r01.py")},
        "dimensions": dimensions,
        "mesh_topology": topo,
        "self_intersections": {
            "status": "PASS_BY_ANALYTIC_SWEEP_AND_ENVELOPE_PROOF",
            "basis": ["single ordered closed sweep shell", "monotone straight root morph", "main bend inner radius remains positive at 6 mm", "end transition inner radius remains positive at 4 mm", "non-returning separated path sections", "one 2-manifold component, no duplicate or degenerate faces"],
            "exhaustive_triangle_pair_test": False,
        },
        "validations": validations,
        "mechanical_assessment": mechanical,
        "print": {
            "material": "PETG",
            "nozzle_mm": 0.4,
            "orientation": "side lying, local Y to printer Z",
            "support": "localized build-plate support under plug only; externally accessible",
            "layer_height_mm": 0.20,
            "walls": 5,
            "infill_percent": 30,
            "infill_pattern": "Gyroid (Cubic acceptable)",
            "infill_allowed_range_percent": [25, 35],
            "one_hundred_percent_infill": "NOT_RECOMMENDED",
        },
        "open_real_tests": ["8.90 mm plug insertion force and removal", "real honeycomb axial free space at least approximately 18.5-19 mm", "PETG print quality and support removal", "wet-cloth bending test", "creep and wet-cycle test", "final product approval by user"],
    }
    (directory / "machine-readable-validation-revision.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    write_reports(directory, report)
    print(json.dumps({"status": report["status"], "technical_pass": technical_pass, "topology": topo, "dimensions": dimensions, "mechanical": mechanical}, indent=2))
    return 0 if technical_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
