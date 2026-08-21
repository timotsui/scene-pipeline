# SESSION 2026-08-19 HANDOFF — LIFTING PAPER; DEBUG THE ZERO FIRST

User closing instruction:

> Next time we do this, we will keep debugging the test. I keep feeling there
> is a problem since it cannot be zero.

## 0. One-line truth

Do **not** treat the dining-room zero as settled evidence and do **not** advance
the lifting-paper claims next session. First explain why the analyzer returned
zero proposals on `ai_037_007`. The current five-scene results remain a
development snapshot whose headline values may change if the test pipeline is
repaired.

The user is the visual standard. The agent must expose the exact saved evidence
and ask the user to judge it; the agent must not claim that a frame, splat, or
box placement looks correct.

## 1. Start here next session

Repository:

```text
D:\T\Documents\GeorgiaTech\Summer2026\scene-pipeline
```

Read this file in full, then double-click:

```text
launch_lifting_viewer.bat
```

The launcher now opens the ten-stage walkthrough. Go directly to Dining Room:

```text
http://localhost:8765/benchmarks/lifting/reports/pipeline_walkthrough/?scene=ai_037_007&stage=sweep
```

Relevant adjacent stages are `verify`, `detect`, and `native`. The heavy 3D
viewer remains linked from the walkthrough and is also available directly:

```text
http://localhost:8765/benchmarks/lifting/reports/scene3d/?scene=ai_037_007
```

Have the user inspect the saved sweep. Do not start by changing thresholds,
re-running the paper summary, or editing prose.

## 2. Why the zero is now an open test failure, not a paper conclusion

The following facts are verified from saved artifacts:

- Dining Room is Hypersim `ai_037_007`, camera `cam_00`.
- It has 15 visible target-category ground-truth boxes.
- Its trained splat passes the predeclared reconstruction gate:
  - held-out PSNRs: 25.87, 23.93, 26.66, 27.02, and 25.66 dB;
  - mean: 25.83 dB;
  - minimum: 23.93 dB.
- The analyzer completed all 90 configured RGB renders and all 90 paired depth
  renders.
- Its analyzer `transforms.json` contains five standpoints and 90 camera poses.
- Its `interactions.json` is exactly an empty object set:

```json
{"objects": [], "frame_annotations": {}}
```

- Therefore rectangular lift, global SAM lift, and active SliceVote all receive
  zero proposals and all correctly remain empty downstream.
- This is **not currently evidence of a SAM, SliceVote, adapter, or evaluator
  failure**. The zero exists at or before the analyzer's OWLv2 discovery output.
- Independent pipelines do not return an empty scene: the common-schema
  comparison contains 15 Zoo3D predictions and 8 Boxer predictions for Dining.
  That does not prove the analyzer is wrong, but it makes the empty analyzer
  branch important to explain.
- `reports/assets/zoo3d-comparison/dining-room.png` is a copied Hypersim source
  RGB frame. It is not rendered from the splat and must not be used as proof of
  analyzer-render quality.

The previous paper text calls this an end-to-end discovery failure. That is a
description of where the saved run ended, not a validated diagnosis of why it
ended there. The user's ruling is to keep debugging.

## 3. Exact next debugging sequence

Keep every diagnostic output separate from the frozen development directories.
Never overwrite `ai_037_007_splat_analyzer_medium_min1`.

### A. Have the user classify the 90 saved views

Use the walkthrough's `sweep` stage and scrub RGB and depth. Record, by frame
number and standpoint, the user's answers to only these questions:

1. Is the room upright?
2. Is recognizable room content in view?
3. Are target objects large and clear enough to detect?
4. Is the camera inside geometry, in empty space, or aimed mostly at a wall,
   ceiling, or floor?

There are 18 frames per standpoint. Do not summarize the views as good or bad
without the user's ruling.

### B. Split renderer/camera failure from detector failure

Run the exact frozen OWLv2 vocabulary and 0.12 threshold on several original
prepared Hypersim RGB frames, beginning with `frame_0000.png`. This is a
diagnostic only, not a replacement benchmark condition.

- If source frames also yield no target detections, investigate the detector,
  prompt vocabulary, image preprocessing, and score distribution.
- If source frames yield detections while analyzer renders do not, investigate
  the splat-render/camera path before changing the detector.

Save raw per-frame OWLv2 detections and scores. The released analyzer's
`interactions.json` contains only post-cluster survivors, so the present empty
file cannot distinguish "zero raw detections" from "raw detections rejected
later." Instrument or add a detector-only diagnostic that writes the pre-filter
counts; do not infer this from the empty final JSON.

### C. Audit Dining's five sampled standpoints numerically

Dining's recorded analyzer parameters are:

```text
scene_center = [-0.7435303, -0.1435022, -0.7411082]
scene_radius = 4.1515005
resolution   = 512 x 512
fl_x = fl_y  = 119.3747605  (130-degree horizontal FOV)
physical up  = raw -Y
```

The five saved camera positions are:

```text
[-5.4284,  1.3143, 1.1724]
[-1.2639,  2.4266, 1.6781]
[-1.7900, -0.4227, 2.9135]
[-2.7219, -1.6742, 2.0418]
[-0.7358,  1.6950, 3.5073]
```

Check each against the splat density, source-camera envelope, and visible room
interior. The analyzer computes nearby `look_targets`, but its pose builder does
**not** use them; it performs a pure 360-degree azimuth/elevation panorama from
each accepted position. The density-aware sampler can therefore pass a
numerical density test without placing the camera at a useful interior view.
This is a hypothesis to test, not the established cause.

Also verify the raw-frame convention. The analyzer expects physical up = file
`-Y`, which matches the preparation record. A hidden extra rotation or a wrong
PLY input would silently degrade every view.

### D. Isolate PLY/rendering from viewpoint selection

Render the Dining PLY through the analyzer renderer at one known prepared
Hypersim camera and compare its saved numeric/camera setup with the existing
verification render. This uses a camera already known to pass reconstruction
validation and removes standpoint selection from the experiment.

- If the analyzer renderer disagrees at the same camera, debug PLY loading,
  camera convention, SH/color handling, or render settings.
- If it agrees, the trained splat and renderer are probably usable and the
  density-sampled viewpoints become the main suspect.

The user judges the paired images. The agent checks matrices, intrinsics, file
identity, and hashes.

### E. Only then run controlled diagnostics

Threshold changes may be used to expose raw score behavior, but not to rescue
the paper result post hoc. Useful diagnostics, in order:

1. frozen detector on original source frames;
2. frozen detector on a known prepared-camera splat render;
3. frozen detector on the 90 existing analyzer frames with raw scores saved;
4. the same PLY with source-camera standpoints or verified interior cameras;
5. only after the above, a threshold sweep labelled diagnostic.

Write every diagnostic to a new directory such as:

```text
predictions\ai_037_007_debug_<specific-test>
```

Do not mutate the frozen output in place.

## 4. Decision rule after finding the cause

- If the zero is a genuine outcome under a correct frozen test, preserve it and
  document the evidence that makes it credible.
- If the implementation, camera convention, renderer, sampler, prompt, or
  bookkeeping is wrong, fix the cause and re-run the affected method on **all
  five development scenes** under one configuration. Do not patch Dining alone
  into the aggregate.
- After any repaired five-scene run, regenerate adapters, SAM/global outputs,
  SliceVote outputs, metrics, bootstrap summaries, interactive reports, and all
  paper-facing numbers from the new saved receipts.
- The held-out split remains untouched until the development test and method
  configuration are genuinely frozen again.

## 5. Paper claims currently on hold

The existing draft reports this development snapshot:

| Method | Scene-macro AP25 | Recall25 | AP50 | Predictions |
|---|---:|---:|---:|---:|
| Rectangular lift | 0.124 | 0.131 | 0.007 | 123 |
| Global SAM lift | 0.054 | 0.066 | 0.021 | 123 |
| Active re-observation | 0.180 | 0.255 | 0.062 | 123 |
| Zoo3D external reference | 0.194 | 0.249 | 0.151 | 50 |
| Boxer external reference | 0.019 | 0.057 | 0.000 | 49 |

The controlled active-minus-rectangular AP25 delta is currently 0.056 with a
five-scene bootstrap interval of `[0.008, 0.133]`. These values are reproducible
from the saved development run, but they are **not cleared for final use while
the Dining test remains disputed**. The zero contributes a tie and affects the
scene-macro values, confidence intervals, prediction total, and wording that
active wins all four nonempty scenes.

Do not edit the paper to strengthen these claims next session. If the Dining
run changes, search and regenerate every occurrence of:

```text
123 proposals
0.124 / 0.054 / 0.180
0.131 / 0.066 / 0.255
0.007 / 0.021 / 0.062
4/1/0
0.056 [0.008, 0.133]
Dining room yields none / zero proposals
```

The fixed-proposal and external comparisons must remain separate. Zoo3D and
Boxer use native proposal paths and are context, not causal ablations.

## 6. New interactive walkthrough from this session

The walkthrough shows the actual saved evidence for the modules that ran:

1. Hypersim benchmark input;
2. 3D Gaussian training;
3. held-out reconstruction verification;
4. analyzer standpoints and 90-view sweep (`asp`, `asw`);
5. OWLv2 detection and voting (`adet`);
6. native rectangular lift (`a1`);
7. SAM mask lift (`segb`, `plift` adaptation);
8. active SliceVote (`vote`);
9. evaluation;
10. Zoo3D/Boxer external adapters.

Files:

```text
benchmarks/lifting/build_pipeline_walkthrough.py
benchmarks/lifting/reports/pipeline_walkthrough/index.html
benchmarks/lifting/reports/pipeline_walkthrough/app.js
benchmarks/lifting/reports/pipeline_walkthrough/styles.css
benchmarks/lifting/reports/pipeline_walkthrough/data.json
benchmarks/lifting/serve_scene3d.py
launch_lifting_viewer.bat
```

The walkthrough is now a diagnostic evidence viewer, not a presentation-only
summary. Every stage states its saved input, exact operation, saved output, and
missing evidence. Across the five scenes it exposes 250 prepared RGB/depth
pairs, 450 analyzer RGB/depth/raw-depth views, 271 exact cached SAM masks, 1,466
per-object SliceVote visuals, 250 Zoo3D input/mask pairs, and 250 Boxer
RGB/depth frames with all saved CSV rectangles. All 4,587 unique referenced
local artifact URLs resolve to existing files; representative URLs from every
route returned HTTP 200. JavaScript syntax, Python compilation, and whitespace
checks pass. Browser click automation was unavailable in the session, and the
user has not yet performed the visual pass.

For Dining, steps 4–9 show an explicit unresolved-zero panel. Step 5 keeps all
90 RGB/depth views visible even though there are no annotations and states the
precise missing evidence: raw pre-filter OWLv2 boxes/scores were not saved, so
the current run cannot distinguish zero raw detections from later
filtering/clustering removal.

## 7. Benchmark artifact locations

Root:

```text
D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\lifting_benchmark\hypersim
```

Dining inputs and evidence:

```text
prepared\ai_037_007\benchmark_manifest.json
prepared\ai_037_007\images\frame_0000.png
prepared\ai_037_007\transforms.json
training\ai_037_007_gsplat5000\training_receipt.json
training\ai_037_007_gsplat5000\ply\point_cloud_4999.ply
verification\ai_037_007_gsplat5000\reconstruction_metrics.json
verification\ai_037_007_gsplat5000\frame_*.comparison.png
predictions\ai_037_007_splat_analyzer_medium_min1\transforms.json
predictions\ai_037_007_splat_analyzer_medium_min1\frames\frame_*.png
predictions\ai_037_007_splat_analyzer_medium_min1\frames\depth_*.npy
predictions\ai_037_007_splat_analyzer_medium_min1\interactions.json
```

Analyzer design/environment references:

```text
entangled_gen/analyzer/ENV.md
entangled_gen/analyzer/FEASIBILITY_SPLAT_ANALYZER.md
benchmarks/lifting/hypersim_split.v1.json
benchmarks/lifting/README.md
```

## 8. Repository state — preserve it

Scene-pipeline current base commit:

```text
25d11b7 Add lifting viewer session handoff
```

Current lifting work is uncommitted:

```text
M  benchmarks/lifting/reports/scene3d/viewer.js
M  benchmarks/lifting/serve_scene3d.py
M  launch_lifting_viewer.bat
?? benchmarks/lifting/build_pipeline_walkthrough.py
?? benchmarks/lifting/reports/pipeline_walkthrough/
?? entangled_gen/docs/handoffs/SESSION_2026-08-19_LIFTING_PAPER_HANDOFF.md
```

The scene3d viewer also has today's unverified performance/navigation changes:
65-degree FOV, a 256-pixel pathological splat-size cap, and a start pose at the
robust scene-bounds center. Preserve them for user testing; do not call them
visually accepted.

Unrelated user-owned file:

```text
?? entangled_gen/eval_full_asset_audit.py
```

Do not modify, delete, stage, or claim that file.

The report server was running at handoff as Python PID 39240 on port 8765.
Treat that PID as ephemeral; use the launcher next session and verify the exact
process before stopping anything.

## 9. Overleaf state — do not trample it

Paper repository:

```text
D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\paper\overleaf
```

Current commit:

```text
a8e2324 Restore standard pipeline paper front matter
```

The Overleaf worktree contains unrelated live edits:

```text
M  README.md
D  main.tex
M  notes/questions.tex
?? pipeline_paper_acm.tex
?? pipeline_paper_ieee.tex
```

`lifting_paper.tex` itself is currently not listed as modified. Do not clean,
reset, stage, or overwrite the unrelated paper-front-matter work. The current
lifting claims are in `lifting_paper.tex`, and the lifting notes are in
`lifting-paper/notes/NOTES.md` and `RESULTS_PLAN.md`.

## 10. What not to do

- Do not accept zero merely because the evaluator faithfully reports it.
- Do not assert a visual diagnosis without the user's ruling.
- Do not tune Dining alone and retain the old five-scene statistics.
- Do not run the held-out 20 scenes before the development pipeline is frozen.
- Do not collapse the fixed-proposal ablation and external-system comparison.
- Do not replace the full splat with the attractive source RGB frame; they are
  different artifacts with different purposes.
- Do not change downstream SAM/SliceVote code until discovery is shown to be
  nonempty; they cannot recover proposals they never receive.

## 11. Prompt for the next agent

```text
Continue debugging the disputed Dining Room zero for the lifting paper. Read
entangled_gen/docs/handoffs/SESSION_2026-08-19_LIFTING_PAPER_HANDOFF.md in full
before acting. Do not edit or strengthen the paper claims first. Open the
pipeline walkthrough at scene ai_037_007, stage sweep, and let the user judge
the exact 90 saved RGB/depth views. The verified boundary is: reconstruction
passes (mean held-out PSNR 25.83 dB), all 90 analyzer views exist, but
interactions.json has zero objects and zero frame annotations. Split the failure
into detector vs render/viewpoint causes: save raw OWLv2 detections on original
prepared RGB, on a known-camera splat render, and on existing sweep frames;
audit the five density-sampled standpoints and the raw -Y-up convention. Keep
all diagnostics in new directories and never overwrite the frozen output. If a
pipeline defect is found, rerun one corrected configuration on all five
development scenes and regenerate every metric and paper number. The user is
the visual standard; report numeric/file evidence and ask for visual rulings.
Preserve unrelated Overleaf changes and entangled_gen/eval_full_asset_audit.py.
```
