# SESSION 2026-08-20 HANDOFF — LIFTING VIEWER; RESUME AT THE DINING ZERO

## User instruction

Wrap up now. Next session, continue visually debugging the lifting test. The
user is the visual standard; the agent must show exact saved evidence and must
not claim that images, splats, masks, or boxes look correct.

## Read first

Read the complete diagnostic record before acting:

```text
entangled_gen/docs/handoffs/SESSION_2026-08-19_LIFTING_PAPER_HANDOFF.md
```

That file contains the verified Dining facts, hypotheses, exact debugging
sequence, frozen development metrics, artifact paths, and paper restrictions.

## Open first next session

Repository:

```text
D:\T\Documents\GeorgiaTech\Summer2026\scene-pipeline
```

Double-click:

```text
launch_lifting_viewer.bat
```

Then open the Dining detector evidence directly:

```text
http://localhost:8765/benchmarks/lifting/reports/pipeline_walkthrough/?scene=ai_037_007&stage=detect
```

Also inspect the preceding sweep:

```text
http://localhost:8765/benchmarks/lifting/reports/pipeline_walkthrough/?scene=ai_037_007&stage=sweep
```

## Current truth about the zero

- Dining reconstruction passes: mean held-out PSNR is 25.83 dB.
- All five analyzer standpoints, 90 RGB views, and 90 paired depth views exist.
- `interactions.json` contains zero objects and zero frame annotations.
- Therefore native lift, SAM, and SliceVote receive no proposal and remain
  empty downstream.
- Zoo3D produces 15 predictions and Boxer produces 8 on the same scene.
- The zero is localized to at or before analyzer detection/discovery output.
- The exact cause is **not yet known**.
- Raw pre-filter OWLv2 boxes, scores, and rejection logs were not saved. The
  current output cannot distinguish "OWLv2 returned nothing" from "filtering
  or clustering removed everything."

Do not call the zero a valid paper result until this is explained. Do not tune
Dining alone. If a pipeline defect is found, rerun one corrected configuration
on all five development scenes and regenerate all dependent metrics.

## What the diagnostic viewer now contains

Every executed stage states:

1. saved input;
2. exact operation and parameters;
3. saved output;
4. missing evidence.

The viewer exposes all inventoried visual material:

- 250 prepared RGB/depth pairs;
- 450 analyzer RGB/depth/raw-depth views;
- 271 exact cached SAM masks with observation and lifted-bound records;
- 1,466 per-object SliceVote plan, vote, detection, and conemap visuals;
- 250 Zoo3D input/mask pairs;
- 250 Boxer RGB/depth frames with every saved CSV rectangle;
- all saved 3D prediction sets, receipts, metrics, and camera transforms.

For Dining, steps 4–9 display an explicit unresolved-zero panel. The detector
stage still exposes all 90 RGB/depth views even though no final annotations
exist.

Primary files:

```text
benchmarks/lifting/build_pipeline_walkthrough.py
benchmarks/lifting/reports/pipeline_walkthrough/index.html
benchmarks/lifting/reports/pipeline_walkthrough/app.js
benchmarks/lifting/reports/pipeline_walkthrough/styles.css
benchmarks/lifting/reports/pipeline_walkthrough/data.json
benchmarks/lifting/serve_scene3d.py
launch_lifting_viewer.bat
```

## First diagnostic action next session

Have the user scrub the 90 Dining sweep views and record frame/standpoint
judgments. Then save raw frozen-configuration OWLv2 detections and scores for:

1. original prepared RGB frames;
2. a known prepared-camera splat render;
3. the existing 90 analyzer sweep frames.

Keep these diagnostics in a new directory. Never overwrite:

```text
predictions/ai_037_007_splat_analyzer_medium_min1
```

## Verification at close

- Viewer data format: `lifting-pipeline-debugger-v2`.
- All 4,587 unique referenced local artifact URLs resolve to files.
- Representative report, benchmark, generated-mask, active-artifact, Zoo3D,
  and Boxer HTTP routes returned 200.
- JavaScript syntax check passes.
- Python builder/server compilation passes.
- `git diff --check` passes; line-ending warnings are pre-existing policy
  warnings, not whitespace errors.
- In-app browser automation was unavailable, so the user has not performed the
  visual acceptance pass.

The report server was still running at close as Python PID 39240 on port 8765.
The PID is ephemeral; verify the exact process before stopping it.

## Repository state to preserve

Lifting work is intentionally uncommitted. Do not reset or clean it. Current
paths include:

```text
M  benchmarks/lifting/reports/scene3d/viewer.js
M  benchmarks/lifting/serve_scene3d.py
M  entangled_gen/docs/handoffs/SESSION_2026-08-18_LIFTING_VIEWER_HANDOFF.md
M  launch_lifting_viewer.bat
?? benchmarks/lifting/build_pipeline_walkthrough.py
?? benchmarks/lifting/reports/pipeline_walkthrough/
?? entangled_gen/docs/handoffs/SESSION_2026-08-19_LIFTING_PAPER_HANDOFF.md
?? entangled_gen/docs/handoffs/SESSION_2026-08-20_LIFTING_VIEWER_FINAL_HANDOFF.md
```

Unrelated user-owned file—do not modify, stage, delete, or claim it:

```text
?? entangled_gen/eval_full_asset_audit.py
```

Preserve the unrelated live Overleaf changes described in the full 2026-08-19
handoff.
