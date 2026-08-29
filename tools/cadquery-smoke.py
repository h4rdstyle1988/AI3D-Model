from pathlib import Path
import cadquery as cq

target = Path(__file__).resolve().parents[1] / "work" / "cadquery-smoke.stl"
target.parent.mkdir(parents=True, exist_ok=True)
solid = cq.Workplane("XY").box(10.0, 8.0, 6.0)
cq.exporters.export(solid, str(target))
if not target.is_file() or target.stat().st_size == 0:
    raise SystemExit("STL export failed")
print(target)
