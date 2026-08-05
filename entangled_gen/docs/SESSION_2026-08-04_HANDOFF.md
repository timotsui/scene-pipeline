# SESSION 2026-08-04 HANDOFF — ROTATION CHECK BUILT, MEASURED TO THE FLOOR, CLOSED

Continues SESSION_2026-08-03C_HANDOFF.md (rotation experiments awaiting
review). One long day, one outcome: **the rotation check is a finished
canon module (PH2a, own node on the map) and is CLOSED as a research
topic.** Next session moves on — fit loop proper.

## NEXT SESSION — FIRST THING

**FIT LOOP (PH2) design.** The rotation check now feeds it. Three small
user gates are parked, none blocking:

1. **APPLY GATE (proposal in PLAN_FIT_LOOP.md final wrap):** apply only
   HIGH-confidence non-zero verdicts (this scene: bed 180°, door obj_127
   180°); low/medium non-zero = flags for the fit loop's judge. Nothing
   has been applied to fitted_preview.
2. **Library front semantics:** ratify per-category definitions ("bed
   front = foot end"), store as a tag next to the canonicalization data,
   flip THIS bed asset's canonical yaw 180° via the fixup channel. Born
   from the day's root-cause find.
3. Placement discrepancies the refcam box check exposed (not rotation
   problems): obj_022 bookshelf 455 px from its photo spot, obj_035
   picture on the wrong wall, yoga mat size mismatch, wall-shelf swap
   638 px from the replaced picture's spot.

## CANON (final form, 3 independent benchmark hits)

`compose/rotation_check.py` → `out/<scene>/compose/rotation_check.json`
+ `rotation_check/` stimuli + `review_shots/index.html` (built by
`experiments/build_rotq_viewer.py`).

Per referenced object, ONE call: mirror-corrected detection photograph
(pano frame is a DEFINED left-right mirror; rose drawn, unconditional) +
FOUR SEPARATE candidate renders (0/90/180/270), object isolated over
walls+floor, from THE PHOTO'S OWN CAMERA (sidecar → pano→raw mirror map →
render frame; verified by the projected-box self-check, 25/28 within px),
each CROPPED to projected-box∪rose, rose in every image, neutral names →
"which candidate matches?" → pick mapped to degrees IN CODE. Swaps
inherit the replaced object's photo (edit_proposals lineage, declared in
prompt). Strict adds → plausibility direct ask. Reply cache is
STIMULUS-KEYED (prompt + image bytes). Failed call = no-answer, never a
run-killer. Every call in its own clean folder. Costs self-measured
(--output-format json). Full scene ≈ 4–6 min wall at --jobs 12.

Canonical record: bed 180° HIGH/6 turns ✓GT · 31/31 answered · 8
non-zero, 2 high-conf. Superseded records kept: rotation_check_2cam /
_roomframed / _4cand / _compass_bed .json.

## What was tried and REJECTED (measurements in PLAN_FIT_LOOP.md; do not rebuild)

- **Two-camera direct ask** (morning canon v1): grounded but the model
  judged vs NOTHING until the user demanded the real scene as reference.
- **Mirrored reference** (first grounded run): pano frame is a defined
  mirror — every facing answer inverted. User caught it.
- **Isolated same-camera direct ask / describe-the-render:** the judge
  misread the stand-in render's facing 6/6 under every prompt, compass,
  and framing variant, while reading the PHOTO right.
- **Signed degrees from the model:** our "+= CCW from above" text reads
  inverted vs map semantics; turns are computed from picks/facings only.
- **Metadata facing channel:** rejected by user — relies on asset
  presets ("front_dir_raw" via pillow rule); and the root cause proved
  the point: **bed asset canonical +z = HEAD, pillow rule front = FOOT →
  ends swapped in the test fit; GT 180 vindicated; face_dot can't see
  semantic flips.**
- **Footprint-prune → binary lineup** (user idea, deterministic,
  geometrically sound, ~15% cheaper): broke the bed bench (180 HIGH →
  0 medium) — 90/270 act as contrast anchors. Behind `--prune`.
- **Two-stage describe→choose:** bed equal, tail fails at the EVIDENCE
  (blurred basket photo), not the format. Free-form describe
  (front/axis/NONE) = the future router: basket self-classified "none"
  in 9 s. Shelved in experiments/desc_choice_test.py.
- **8-tile strip / propose→verify:** morning kills (zoom-tooling;
  verify reversed its own correct answer).

**Tail truth:** 13 of 31 answers flip between ANY two stimulus framings
— tail verdicts are noise, only high-conf verdicts are stable. Hence the
apply gate.

## Also landed today

- **Parallelism ruling pipeline-wide** (user; compute is cloud-side, a
  lane is a courier): CONCURRENCY 3→8 in describe_nodes, judge_pairs,
  judge_near, judge_cases, pick. 12 lanes proven on this machine.
  Queued for approval: fan out consistency/judge_names/triage batch
  loops + propose_edits --add-runs.
- **Map:** PH2a node + full card; fit-loop card slimmed to consumer;
  everything below shifted +42px, viewBox grown.
- **Stimulus rules now in memory** ([[judge-loop-effort-allocation]]):
  answer-in-one-look; if the judge tools up, the format is wrong; the
  stimulus must carry what the prompt claims (the missing-rose lesson);
  clean folder per call; stimulus-keyed caches.
- **Ops:** `claude -p` session transcripts under ~/.claude/projects =
  the way to see WHY a call is slow (caught both zoom expeditions).
  Choice replies print "-> None" in the run log (the line shows the
  degrees field; the record maps picks correctly) — cosmetic.

## State

- Repo: all UNCOMMITTED (push/commit = user's). New: compose/
  rotation_check.py; experiments/ fitloop_rotref_test.py,
  fitloop_rotref_parallel.py, recover_rotref_record.py, refcam_pairs.py,
  compass_overlay_test.py, compass_describe_test.py,
  compass_choice_test.py, desc_choice_test.py; build_rotq_viewer.py
  rewritten (pairs+canon page). Modified: pipeline_map.html, docs/
  PLAN_FIT_LOOP.md, 5 judge modules (CONCURRENCY), run logs.
- Data: out/bedroom_marble/compose/rotation_check/ (per-call folders,
  refcam pairs, sheets), rotation_check*.json records,
  review_shots/index.html. Old experiment folders (rotq/, rotref/,
  rotref_one/) untouched on disk.
- Viewer server :8321 was left running (background task bkx1ofbek).
- fitted_preview: UNTOUCHED by everything today.
