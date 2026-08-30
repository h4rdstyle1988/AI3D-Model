# spuelenablage-lappenhalter-r01

Technisch validierte R01-Geometrie für einen PETG-Testdruck. **Keine finale Nutzerfreigabe.**

Hauptdateien:

- `spuelenablage-lappenhalter-r01.stl` – finale Druckgeometrie
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
