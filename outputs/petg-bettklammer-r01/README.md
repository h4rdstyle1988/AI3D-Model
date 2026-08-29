# PETG-Bettklammer R01

Kleiner Passungs- und Funktionstest gemäß aktiver Task. **Keine finale Nutzerfreigabe.**

- `petg-bettklammer-r01.scad`: parametrische CAD-Quelle
- `build_and_validate_r01.ps1`: reproduzierbarer STL-Bau und technischer Validator
- `petg-bettklammer-r01.stl`: erzeugtes Druckmesh
- `technical-validation.json`: maschinenlesbare Prüfung
- `SOLL-IST-UND-REVISION.md`: Maß-, FDM-, Revisions- und Offenbericht

Reproduktion unter PowerShell:

```powershell
& .\outputs\petg-bettklammer-r01\build_and_validate_r01.ps1
```

