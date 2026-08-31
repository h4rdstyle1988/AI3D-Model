# REPRODUKTION R14

Run from the repository root:

```powershell
python outputs\herbst-igel-r02-exterior-surface-surgery-r14\reproduction-scripts\r14_mesh_probe.py `
  'D:\3D-Models\generated\herbst-igel-r02-r08-input\outputs\herbst-igel-r02-trellis-optik-retry-r07\trellis-raw\seed-00000042\herbst-igel-r02-trellis-raw-seed-42.ply' --output outputs\herbst-igel-r02-exterior-surface-surgery-r14\audits\topology-before.json
python outputs\herbst-igel-r02-exterior-surface-surgery-r14\reproduction-scripts\r14_surface_surgery.py
python outputs\herbst-igel-r02-exterior-surface-surgery-r14\reproduction-scripts\validate_r14.py
```

The script hash-gates Seed 42 and both references. It does not invoke a heightfield, radial hull, voxel hull, convex hull, or global Poisson reconstruction.
