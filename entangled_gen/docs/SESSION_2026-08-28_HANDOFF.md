# SESSION 2026-08-28 HANDOFF — the wall-trace redesign day (all of it sheet-only; YOUR job is the re-runs)

(Real date 2026-08-12, daytime/evening session with the user in the loop
the whole way. REVIEW_LOG **R-S2-136..158** — twenty-three entries in one
session. Previous handoff: handoffs/SESSION_2026-08-27. Tree committed
AND PUSHED through **5ba217b** plus this handoff's commit; nothing owed
on git.)

**CLOSE-OUT STATE: quiet. Nothing running. The one big thing to know:
every wall-trace change (R-S2-145..158) is SHEET-ONLY — no scene's
room_shell.json, graph, or splat has been touched all day. The shipped
scene state everywhere is still the OLD rules. Shipping the new rules =
this next session's re-runs.**

## 0. THE ONE-LINE TRUTH

The user walked the failure modes of the night's six scenes and we fixed
them at the source, one ruling at a time: scale got a doors+ceiling
reference tier (140), the flipped beds got their three distinct causes
fixed (141-143), and the wall trace got a thirteen-entry redesign
(145-158) — floor∪walk union, walking-zone barriers, roof-not-ceiling,
scale-invariant head line, staircase chains with green priority for
planes AND ends, plane coalescing, roof-contact survival, and continuous
room yaw — every rule verified on review sheets without shipping a byte
of scene state.

## 1. WHAT THE NEXT AGENT DOES (user instruction: "the next agent will be
rerunning the scenes we need to rerun")

Work order, pre-authorized in direction but LAUNCH DISCIPLINE applies
(detached via WMI, clock-lock verified, sequential unless the user rules
two-lane):

1. **fresh05 + fresh08 scale apply + chain re-run.** The R-S2-140
   two-tier fix is in scene_scale.py and measure-verified: fresh05 will
   apply s=0.639 (consensus, room ruler included), fresh08 s=0.643 (arch
   tier: 3 doors + ceiling). Run scene_scale WITHOUT --measure-only per
   scene (applies, with *_prescale backups + double-apply refusal), then
   the two-pass re-run from stitch (R-S2-132 semantics: `--phase all
   --from <stitch stage>` — check graph/stages.py for the exact stage
   key; the R-S2-134 face cache keys on the eye so renders refresh
   automatically). fresh05's shell/trace oddities all traced back to raw
   scale — re-judge AFTER this.
2. **Build the yaw state-apply** (R-S2-158's shipping half): rotate the
   scene state once at normalization — splat xyz AND gaussian
   orientations (quats), collider, manifests, boot extents — the
   scale-apply pattern (backups, yaw_applied guard in frame_bootstrap,
   re-measure = verification reading ~0). The frame contract stays
   ELEMENTWISE SIGN FLIPS — do NOT put a rotation into raw_to_render;
   dozens of `* r2r` call sites assume flips. Measured yaws: fresh06
   +12.0°, fresh05 −2.5°, fresh09 0°.
3. **Wall-fix re-run** over the review scenes (fresh05/06/09 at least):
   room_shell (v1 + poly with the new stack) → graph wall rebuild →
   downstream, per the designed chain. THEN the user re-reviews sheets
   against shipped state.
4. Queued behind, needing user rulings first: v1-planes-join-the-merge
   (asked, un-ruled), interior walls as first-class architecture
   (fresh05's 4.6 m partition at x=−1.107 — traced, grouped, destroyed
   by the closed-loop vocabulary), compose's box-only wall consumers +
   snap's infinite planes (see §3), the bed-category census (user:
   "leave asset audits to the end").

## 2. THE DAY'S FIX STACK (all committed; headers only — read the entry
before touching anything)

| R-S2 | what |
|---|---|
| 136-139 | comparison page: screenshot thumbnails; composed-scene top-down renders BOTH sides (GLTS assembled by its own blender_placement recipe, NO Blender needed); ONE fixed path out/comparison.{json,html} |
| 140 | scale two tiers: the room votes (ceiling vs 2.8) + arch-reference fallback (doors+ceiling) when consensus spread fails. fresh05/08 measured, NOT yet applied |
| 141 | pillow VECTOR decides bed facing axis (square-box trap); face_unmet flag on dead ties |
| 142 | bed asset c9ae86a5 yaw fixup 30.18→210.18 (headboard was baked on +z); ~15% of beds flipped per census sample |
| 143 | rotation_check shell/cameras/rose anchored to the MEASURED floor (was y=0; slab hovered mid-room, judge saw "blank floor") |
| 144 | room_shell --steps-sheet: the 9-panel review sheet (sheet mode writes NOTHING else) |
| 145/146 | interior = floor∪walk union: seen floor defeats the solid ring (leash relaxation alone was a measured no-op) |
| 147 | barriers must CROSS the head line (drop ceilings stopped walling rooms; 65% of fresh06's "solid" was hanging) |
| 148/150 | roofed = ANY material above the head line (a drop ceiling IS a roof); head line = floor + (1.4/2.8)×height (scale-invariant) |
| 149 | connector chains → cardinal STAIRCASES (full polyline, no deletion, no diagonal collapse) |
| 151 | panel 7b: pre-snap state, live legs (154 fixed it to draw the pipeline's actual legs) |
| 152 | green priority: legs defer to real wall PLANES |
| 153/155 | roof-contact survival: short walls live if they reach the roof — measured at the SPIKE plane in a 5×5 corridor |
| 156/157 | green ENDS win at corners (ink-gated: only fade legs defer); close-enough plane coalescing (span-capped) |
| 158 | continuous room yaw by SPIKINESS VOTING (calipers rejected — L-hulls lie); apply = state transform, next session |

## 3. THE CONSUMER MAP (agent-verified, drives the post-re-run round)

The polygon is faithful in the graph (one node per segment, correct
extents) but: compose (fit_check/declip/preview/propose_edits/
rotation_check) reduces walls to the OUTER BOX; snap.py and
supported_by.py use INFINITE planes ignoring segment extents; node_views
and envelope still read the v1 `walls` block and never the polygon;
slicevote is the ONLY true polygon consumer. room_shell.json carries two
disagreeing rooms (v1 walls vs polygon) by construction. Fixing these is
the round AFTER the re-runs.

## 4. REVIEW SURFACES

- **wall_review.html** (one page, F5-refreshes):
  `D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\wall_review.html`
  (built by wall_review_sheet.py --scenes fresh09,fresh05,fresh06)
- Steps sheets: `out/<scene>/room_shell_steps.png` — 9 panels; sheet mode
  also prints group table, bar KEEP/DELETE with roof fractions, coalesce
  clusters, and the final wall table (every line name-addressable).
- Comparison: `out/comparison.html` (fixed path, always latest).
- The rotation stimuli, plans, etc. per scene as before.

## 5. TRAPS

- **Sheet-only ≠ shipped.** All shipped shells/graphs are OLD-rule.
  compare_methods, the viewer, compose all read the OLD state until the
  wall-fix re-run.
- `--steps-sheet` is strictly read-only (early return before all
  writes) — safe to run anytime.
- fresh05/fresh08 are STILL at raw Marble scale until step 1 runs; do
  not judge their absolute numbers.
- The scale apply REFUSES a second apply (bootstrap guard) — re-measure
  is a verification append, and the runner re-running the stage on a
  normalized scene routes there automatically (R-S2-121).
- Long runs: WMI-detach, ONE watch_gpu, clock lock verified in
  gpu_watch.csv under load. GLTS has no mid-run resume (not needed this
  session).
- The 08-27 handoff's comparison pointer (timestamped file) is
  superseded: out/comparison.html.

## 6. THE PROMPT FOR THE NEXT AGENT (verbatim; also in NEXT_SESSION_PROMPT.md)

```
Continue the scene-pipeline work. Repo: D:\T\Documents\GeorgiaTech\Summer2026\scene-pipeline\entangled_gen
READ FIRST, in order:
  1. docs/SESSION_2026-08-28_HANDOFF.md — all of it. §1 is your work
     order, §5 the traps.
  2. docs/PARKED.md — do not work on these (item 4 = wall-embed, new).
  3. REVIEW_LOG R-S2-136..158 — skim headers; read any entry you touch.

THE SESSION IS THE RE-RUNS (user: "the next agent will be rerunning the
scenes we need to rerun"):
  1. fresh05 + fresh08: scale apply (scene_scale.py, no --measure-only)
     then the two-pass chain re-run from stitch. Detached launches,
     clock-lock verified, sequential. Read the morning-report style
     receipts as the user would.
  2. Build the yaw state-apply (R-S2-158 §: splat xyz + gaussian quats,
     collider, manifests, boot guard; frame contract STAYS sign-flips).
     Pre-register in REVIEW_LOG before running.
  3. Wall-fix re-run on fresh05/06/09: new room_shell stack into shipped
     state, graph wall rebuild, downstream chain. Regenerate the steps
     sheets + wall_review.html so the user can compare shipped vs sheet.
  4. Do NOT design: v1-merge, interior-wall architecture, compose wall
     consumers, bed census — those need user rulings, bring them as
     questions with receipts.

HOUSE RULES: no observation-triggered tuning; fixes at source,
scene-agnostically; every fix gets a REVIEW_LOG entry with the contract
intro; the user judges ALL visuals; trust the primary record over
summaries; plain English; long processes DETACHED; ONE watch_gpu.
```

## 7. WHERE EVERYTHING IS

Commits this session: d3ca055, 4147d0e, 293ea34, 9984d9b, 72d5b87,
2377f5d, 6f7c990, f8999fd, d3cb95a, 6ac34bd, c04b90e, 99870fc, a93dd4e,
d2fbcf7, 32264b6, d742e0d, 3c06380, b8b80ac, db5ab97, c2e2757, 3588914,
f9dcbf8, b3f254b, 5ba217b (+ this handoff). All pushed. The bed-asset
yaw fix (142) is store-side data (objathor _mesh_yaw.json), not in the
repo — old value recorded in the log entry.
