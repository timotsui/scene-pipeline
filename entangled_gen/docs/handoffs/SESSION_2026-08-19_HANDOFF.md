# SESSION 2026-08-19 HANDOFF — THE REUSE GATE IS CANON; obj_018'S DETECTION IS NEXT

(Real date 2026-08-09. Evidence: REVIEW_LOG R-S2-57 and R-S2-58.
The scene graph was NOT touched this session — the state is exactly as
J8/materialize left it, verified by diff.)

## START HERE — NEXT SESSION'S WORK, IN THE USER'S WORDS

**"We will continue with this detection next session."** The detection
is obj_018's, and R-S2-58 has the full story. The short version:

obj_018 (ceiling light) had a USER-ACCEPTED box of 0.17x0.05x0.16 — J8
shipped the rejected rebox candidate on run-14 geometry, the first J8
verdict ever to change a box. Run 17 re-ran the vote that evening,
UNGATED. Its perp-shot detection grabbed the round light + the lit
strip as ONE object (score 0.29), ran off the photo on 2 of 4 sides,
and the truncation rule filled those sides from the original oversized
prior. Result: today's shipping box is 1.214x0.034x0.541 — and J8
could not fix it because `rebox_truncated` records NO alternative, so
its ballot held exactly one name, `current`.

Three chances the perp shot never had: **no retry** (one detection,
accepted even clipped at 0.29), **no memory** (each run REPLACES the
last measurement; the correct run-14 answer is unreachable), **no
challenge** (a one-name ballot). Direction candidates on record, none
designed: truncated rebox leaves the replaced box ON THE BALLOT; the
R-S2-55 fourth condition (a box a later judge disbelieved never feeds
evidence); node_views' fresh shots as the re-measure substrate.

See it yourself: cone_map.html → obj_018's `obj_018_perp_det.png` —
the red rectangle covers light + strip and is cut off at the frame.

## CANON THIS SESSION (R-S2-57)

**The reuse gate.** graph/node_views.py + graph/view_cams.py (camera
math lifted verbatim from experiments/pool_retake.py). View set =
f(CURRENT box). Reuse an existing pool shot when it still frames
TODAY'S box through its own recorded camera: in-frame >= 0.95 AND zoom
>= 1/1.5 of what a RETAKE would deliver — the bar is the retake, not
an ideal (the obj_008 ruling: a clamped camera can never fill the
frame with a 16 cm object). 3D IoU was tried and REJECTED (2 cm on a
16 cm object destroys IoU with zero visible drift). Blind spot on
record: geometry only — cannot see occlusion.

Living result: 220 standable views = **165 reused + 55 freshly shot
(86 s wall, 0 blank, current-box overlay on all 55)**; 114 culled with
named walls, 110/114 agreeing with pool_retake's own cull. obj_011#1
got the first pictures ever aimed at its own box.

Docs already updated: PIPELINE.md "NODE VIEWS" contract ·
pipeline_map.html `nviews` node now IN THE LANE (J8s → node views →
J9; moved by subagent, seam verified) + full detail card · memory
node-views-reuse-rule.md.

## THE J9 GATE — STILL OPEN, FOURTH SESSION

    out/living_marble/graph/same_product_sheets/index.html

Ceiling-light trim split + chair split (the on-disk chair reason is
BACKREST SHAPE). Still blocks compose. Untouched again.

## OPEN, IN THE ORDER I'D TAKE THEM

1. **The obj_018 detection thread** (above) — the user's named next.
2. **The J9 gate** — blocks compose.
3. **Judge packaging — designed in conversation, NOT built:** which
   views each judge is SHOWN (strip per node, fixed card0..card3 order
   + plan, the count stated in words so a multiplicity judge cannot
   read N views as N objects). node_views deliberately does not decide
   this.
4. **Culled-camera audit renders:** the decision sheet exists; the 114
   audit renders were once made, then deleted on the user's "kill all
   the things we just rendered" (57 were lost with the folder — noted
   as a real loss). Re-rendering awaits an explicit go.
5. Carried from R-S2-54: the split-piece fixes (verdict fan-out
   guard; pieces need their own descriptions).
6. Carried: declip rotation oscillation; compose/support_clip.py
   retirement candidate.

## WHAT IS ON DISK

Committed: NOTHING from this session. Uncommitted in scene-pipeline:
graph/view_cams.py + graph/node_views.py (new), PIPELINE.md,
docs/REVIEW_LOG.md (R-S2-57, R-S2-58), pipeline_map.html, this file.

Review sheets (out/living_marble/graph/, all read-only, regenerable):

    views_as_j8_left_them/   the baseline — every node, every existing
                             picture, J8 verdicts, nothing decided
    reuse_decision/          the ruling evidence — BOTH boxes drawn
                             through each shot's own camera (blue =
                             aimed-at resolved box, yellow = today's);
                             retakes outlined red with reasons
    node_views/              the gate's decision report + the 55 fresh
                             renders (+_box overlays) + 220 sidecars
    vote_vs_render/          the sheet that killed the CPU tile

Scratchpad scripts (NOT in the repo; move in if adopted):
j8_state_sheet.py, reuse_decision_sheet.py, vote_vs_render.py,
why_culled.py, reuse_rule_dryrun.py, wire_reuse_gate.py,
reshot_reasons_patch.py, canon_docs_update.py, append_r58.py,
shift_map.py + pipeline_map.html.bak (pre-move backup).

## GOTCHAS EARNED THIS SESSION

- **NEVER RENDER BEFORE THE USER SAYS GO** — now verification-workflow
  rule 9, after two renders were stopped mid-flight. A mixed batch
  queues the user's half FIRST (the first batch was ordered kept-first
  and its interruption wasted the audit the user wanted).
- **pool_targets.json only survives the LAST render batch** — 14 of
  220 pool shots have no recorded camera and can never pass the reuse
  test. node_views writes a per-view sidecar precisely so this cannot
  happen to its own renders.
- **"Don't we already have them?" comes first.** Before proposing any
  render, count what exists: the culled views had 4 pictures of 114 —
  a culled view is by definition one nothing ever rendered.
- **The strict gate and volumetric IoU both mis-measure "same box".**
  The user's meaning was "the full box is already in the view
  correctly" — a framing test. Numbers that killed the alternatives:
  strict reuses 0, IoU-0.9 reuses 14/199, the canon rule 165.
- **cone_map.html is a RUN-17 artifact** (08-08 20:49) — the latest
  cone map that exists, but two layers behind `grouped`; exempt nodes
  (obj_018 among them) have no vote data on it at all.
