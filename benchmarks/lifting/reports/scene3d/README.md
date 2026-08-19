# Interactive 3D lifting diagnostic

This report overlays the metric reconstruction, visible ground truth, raw
Splat Analyzer proposals, final active boxes, Zoo3D boxes, and the 90 proposal
camera directions for the Kitchen and Dining Room development scenes.

From the repository root:

```powershell
python -m http.server 8765
```

Then open:

<http://127.0.0.1:8765/benchmarks/lifting/reports/scene3d/>

Regenerate the packaged scene data from local benchmark artifacts with:

```powershell
python benchmarks/lifting/build_scene3d_report.py --benchmark-root <hypersim-output-root>
```

The generated report data are visualization-only; the benchmark predictions
and metrics remain unchanged.
