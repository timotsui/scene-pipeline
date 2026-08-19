# SESSION 2026-08-18 HANDOFF — lift-only paper results and 3D comparison viewer

User closing instruction: wrap up now; next session will debug what happened
with the comparison viewer's camera feel and full-splat performance.

## 0. One-line truth

The lift-only development comparison and five-scene interactive viewer exist
and are pushed, but the viewer's final navigation/performance change has not
yet been user-verified. Start next session by testing that change, not by
changing benchmark numbers or the paper.

## 1. Start here next session

Repository:

```text
D:\T\Documents\GeorgiaTech\Summer2026\scene-pipeline
```

Double-click:

```text
launch_lifting_viewer.bat
```

That should start the custom splat-streaming server on port 8765 and open:

```text
http://localhost:8765/benchmarks/lifting/reports/scene3d/?scene=ai_051_002
```

The session's background server was deliberately stopped during wrap-up, so
the launcher should start a fresh process rather than reuse tonight's server.

Use a hard refresh if an older tab is open. Wait until “Streaming full
Gaussian splat…” disappears before judging movement. The bottom status line
now reports FPS.

Latest pushed code commit:

```text
d2f7674 Match pipeline viewer navigation performance
```

## 2. What the viewer contains

The viewer now covers every development scene and every reported external
comparison:

| Scene | GT | Ours | Zoo3D | Boxer |
|---|---:|---:|---:|---:|
| Living room (`ai_051_002`) | 20 | 34 | 22 | 34 |
| Kitchen (`ai_002_006`) | 21 | 32 | 8 | 4 |
| Bedroom (`ai_006_008`) | 26 | 34 | 4 | 3 |
| Dining room (`ai_037_007`) | 15 | 0 | 15 | 8 |
| Office (`ai_003_009`) | 5 | 23 | 1 | 0 |
| **Total** | **87** | **123** | **50** | **49** |

Toggleable layers: full trained Gaussian splat, visible GT, rectangular/raw
proposals, our final slice-vote boxes, Zoo3D, Boxer, and all 90 proposal-view
camera directions. Clicking a box shows label, score, best same-class GT IoU,
matched GT ID, center, and size.

The 100–207 MB trained PLYs stay outside git. `serve_scene3d.py` streams them
from the machine-local benchmark output. Committed 120k-point payloads are
only loading/failure fallbacks.

## 3. Coordinate-frame correction already made

The first viewer incorrectly treated the benchmark as Z-up. The preparation
record explicitly says:

```text
Hypersim metric rotated to physical-up=-Y
```

This matches the World Labs raw-splat convention used by the pipeline viewer.
The comparison viewer now keeps splat, boxes, points, cameras, and clicks in
the recorded raw frame and applies one display-only rotation:

```text
X=0°, Y=0°, Z=180°
```

The three rotation fields remain visible for diagnosis. Do not introduce a
second splat-only transform; every layer must share the same parent display
rotation.

## 4. Navigation/performance issue and final unverified fix

User report after the full-splat upgrade:

1. Orbit did not have the pipeline viewer's eye-relative pivot.
2. Movement became very slow when the Gaussian splat was visible.

Concrete differences were found in `reports/scene3d/viewer.js`:

- The comparison viewer used up to `devicePixelRatio=2`; on a 2x display this
  shades about four times as many pixels as the pipeline viewer.
- Orbit damping remained enabled, continuing camera changes and splat
  redraw/sort work after input stopped.
- `Fit scene` put `controls.target` at the distant room center instead of the
  pipeline viewer's pivot 0.4 m ahead of the eye.
- It used a manual `requestAnimationFrame` loop rather than the pipeline
  viewer's `renderer.setAnimationLoop` structure.

Commit `d2f7674` changed all four to match the pipeline viewer:

- explicit pixel ratio 1;
- damping off;
- `setPose()` normalizes the look direction and places the target 0.4 m ahead;
- `renderer.setAnimationLoop()`;
- live FPS at the bottom.

WASD/EQ/RF controls were copied from the pipeline viewer in commit `f09d924`:
W/S horizontal forward/back, A/D strafe, E/Q or R/F vertical, Shift fast.
Camera and orbit target translate together.

The user ended the session before confirming whether `d2f7674` fixed the
feel/performance. Treat that as the first open gate.

## 5. Minimal debugging sequence

1. Start with `launch_lifting_viewer.bat`; hard-refresh the page.
2. Test Living Room after its full 207 MB splat finishes loading. Record the
   displayed resting FPS and moving FPS.
3. Press `Fit scene`, rotate in place, and verify the camera no longer swings
   around the room center. In code, the eye-to-target distance should be 0.4 m.
4. Test WASD with and without the Gaussian-splat checkbox. Confirm that
   movement speed stays metric-time-based rather than frame-based.
5. Repeat on Kitchen (113 MB) to separate scene size from viewer overhead.
6. Compare against `launch_viewer.bat` / the pipeline viewer at port 8321.
   Relevant reference code is `entangled_gen/viewer/index.html`: `setPose()`
   near lines 126–141, full-splat loading near 385–402, display rotation near
   490–500, and fly navigation near 3404–3445.
7. Only if FPS remains poor after the 1x/damping fix, A/B
   `gpuAcceleratedSort: true`. Current value is `false`, deliberately matching
   the pipeline viewer's safe default. Measure before keeping that change.
8. Later levers, in order: render-scale selector below 1x, antialias off, then
   a converted/compressed splat format. Do not downsample benchmark geometry
   merely to hide a viewer problem.

Potential trap: an old server can squat on port 8765. The launcher detects an
existing viewer endpoint and opens it. If behavior contradicts the current
source, inspect `netstat -ano | Select-String ':8765'`, stop only the verified
viewer-server PID, relaunch, and hard-refresh.

## 6. Why Dining Room is zero

This viewer was created because the Dining Room result looked suspicious.
Confirmed facts:

- 15 visible target GT boxes.
- 0 rectangular/raw proposals and therefore 0 final active predictions.
- The trained Gaussian reconstruction is recognizable/good at source or
  held-out cameras (roughly 24–27 dB PSNR in inspected comparisons).
- The 90 global proposal renders looked gray/black, blurred, overhead, or
  otherwise badly placed.

Current diagnosis: Dining is a global proposal-camera/discovery failure, not a
failed reconstruction. Do not present its zero as clean evidence about the box
refinement stage until the camera sweep is debugged.

Kitchen is different: 21 GT and 32 predictions. Its best same-class cabinet
box has IoU 0.4876, so it counts at AP25 but narrowly misses AP50.

## 7. Important files

```text
launch_lifting_viewer.bat
benchmarks/lifting/serve_scene3d.py
benchmarks/lifting/build_scene3d_report.py
benchmarks/lifting/reports/scene3d/index.html
benchmarks/lifting/reports/scene3d/viewer.js
benchmarks/lifting/reports/scene3d/viewer.css
benchmarks/lifting/reports/scene3d/data/manifest.json
benchmarks/lifting/reports/scene3d/README.md
```

Benchmark artifacts:

```text
D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\lifting_benchmark\hypersim
```

Full splat pattern:

```text
training\<scene>_gsplat5000\ply\point_cloud_4999.ply
```

## 8. Repository and paper state

Scene-pipeline viewer code on branch `master` is pushed through `d2f7674`;
this handoff is the following documentation commit. The only unrelated
working-tree item before this handoff was:

```text
?? entangled_gen/eval_full_asset_audit.py
```

It belongs to other work and must remain untouched.

Lift-paper Overleaf repository:

```text
D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\paper\overleaf
```

It is clean at `29472db Keep visual benchmark report out of Overleaf`. The 3D
viewer is intentionally only in `scene-pipeline`; do not copy HTML, viewer
data, or PLYs into Overleaf.

## 9. Prompt for the next agent

```text
Continue the lift-only paper viewer debugging.
Read entangled_gen/docs/handoffs/SESSION_2026-08-18_LIFTING_VIEWER_HANDOFF.md
in full before acting. Start launch_lifting_viewer.bat, hard-refresh, wait for
the full Living Room splat, and have the user judge pivot and movement while
recording the displayed FPS. The final d2f7674 navigation/performance fix is
not yet user-verified. Do not change paper results first. Preserve the shared
physical-up=-Y raw frame and display rotation (0,0,180); splat, boxes, points,
cameras, and clicks must remain in one parent transform. If performance is
still poor, measure and A/B GPU sorting rather than guessing.
```
