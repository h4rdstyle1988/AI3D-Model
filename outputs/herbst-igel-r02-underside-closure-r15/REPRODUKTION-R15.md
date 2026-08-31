# REPRODUKTION R15

Run from the repository root:

```powershell
python outputs\herbst-igel-r02-underside-closure-r15\reproduction-scripts\analyze_r15_input.py
python outputs\herbst-igel-r02-underside-closure-r15\reproduction-scripts\build_r15_gate1.py
python outputs\herbst-igel-r02-underside-closure-r15\reproduction-scripts\build_r15_underside_variants.py
python outputs\herbst-igel-r02-underside-closure-r15\reproduction-scripts\audit_r15_intersections.py --candidate outputs\herbst-igel-r02-underside-closure-r15\masterform\r15-underside-d4-PARTIAL-NON-APPROVED.ply --attempt-key attempt_a --output outputs\herbst-igel-r02-underside-closure-r15\audits\underside-d4-intersection-audit-r15.json
python outputs\herbst-igel-r02-underside-closure-r15\reproduction-scripts\finalize_r15.py
python outputs\herbst-igel-r02-underside-closure-r15\reproduction-scripts\validate_r15.py
```

No forbidden global hull method is invoked.
