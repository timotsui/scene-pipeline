# Interactive 3D lifting diagnostic

This report overlays the full trained Gaussian splat, visible ground truth,
raw Splat Analyzer proposals, final active boxes, Zoo3D boxes, and the 90
proposal-camera directions for the Kitchen and Dining Room development scenes.

From the repository root:

```powershell
python benchmarks/lifting/serve_scene3d.py --benchmark-root <hypersim-output-root>
```

Then open:

<http://127.0.0.1:8765/benchmarks/lifting/reports/scene3d/>

Regenerate the packaged scene data from local benchmark artifacts with:

```powershell
python benchmarks/lifting/build_scene3d_report.py --benchmark-root <hypersim-output-root>
```

The custom server streams the 100+ MB trained PLY files directly from the
machine-local benchmark output, so they are not copied into git. A plain static
server still works, but the report then falls back to its downsampled point
preview. The generated report data are visualization-only; benchmark
predictions and metrics remain unchanged.
