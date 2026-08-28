# Reproduktionsbefehle

Arbeitsverzeichnis: `C:\Users\h4rds\Documents\ChatGPT\AI3D Model`

```powershell
wsl -d Ubuntu-24.04 -- bash -lc "cd '/mnt/c/Users/h4rds/Documents/ChatGPT/AI3D Model' && /home/h4rds/ai3d/trellis2-venv/bin/python work/build_benchmark_b_spuelenablage_v004_split.py --output-dir outputs/benchmark-b-spuelenablage/benchmark-b-spuelenablage-v004-r01-rebuild --source-3mf '/mnt/c/Users/h4rds/Documents/spuelenablage.3mf'"
```

Die beiden STL-Dateien werden nativ und ohne Rotation gesliced. Die Wanne verwendet das mitgelieferte Profil `profiles/0.24mm-split-wanne-tree-support.json`; der Einsatz `profiles/0.24mm-einsatz-no-support.json`. Maschine: Anycubic Kobra S1, 0,4-mm-Düse; Filament: Anycubic PETG. CLI-Optionen: `--ensure-on-bed --arrange 1 --no-check --slice 0`.

```powershell
wsl -d Ubuntu-24.04 -- bash -lc "cd '/mnt/c/Users/h4rds/Documents/ChatGPT/AI3D Model' && python3 work/analyze_anycubic_gcode.py --gcode outputs/benchmark-b-spuelenablage/benchmark-b-spuelenablage-v004-r01/slicer-wanne-petg-tree-support-no-repair/plate_1.gcode --stdout outputs/benchmark-b-spuelenablage/benchmark-b-spuelenablage-v004-r01/slicer-wanne-petg-tree-support-no-repair/slicer.stdout.txt --stderr outputs/benchmark-b-spuelenablage/benchmark-b-spuelenablage-v004-r01/slicer-wanne-petg-tree-support-no-repair/slicer.stderr.txt --output outputs/benchmark-b-spuelenablage/benchmark-b-spuelenablage-v004-r01/slicer-wanne-petg-tree-support-no-repair/gcode-audit.json --filament 'Anycubic PETG @Anycubic Kobra S1 0.4 nozzle'"
wsl -d Ubuntu-24.04 -- bash -lc "cd '/mnt/c/Users/h4rds/Documents/ChatGPT/AI3D Model' && python3 work/analyze_anycubic_gcode.py --gcode outputs/benchmark-b-spuelenablage/benchmark-b-spuelenablage-v004-r01/slicer-einsatz-petg-no-support-no-repair/plate_1.gcode --stdout outputs/benchmark-b-spuelenablage/benchmark-b-spuelenablage-v004-r01/slicer-einsatz-petg-no-support-no-repair/slicer.stdout.txt --stderr outputs/benchmark-b-spuelenablage/benchmark-b-spuelenablage-v004-r01/slicer-einsatz-petg-no-support-no-repair/slicer.stderr.txt --output outputs/benchmark-b-spuelenablage/benchmark-b-spuelenablage-v004-r01/slicer-einsatz-petg-no-support-no-repair/gcode-audit.json --filament 'Anycubic PETG @Anycubic Kobra S1 0.4 nozzle'"
wsl -d Ubuntu-24.04 -- bash -lc "cd '/mnt/c/Users/h4rds/Documents/ChatGPT/AI3D Model' && /home/h4rds/ai3d/trellis2-venv/bin/python work/validate_benchmark_b_spuelenablage_v004_split.py outputs/benchmark-b-spuelenablage/benchmark-b-spuelenablage-v004-r01"
```
