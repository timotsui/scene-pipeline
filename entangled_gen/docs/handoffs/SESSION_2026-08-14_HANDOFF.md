# SESSION 2026-08-14 HANDOFF — THE RENDER-PRINCIPLE NIGHT (+ first materialize)

(Real date 2026-08-08 01:00-04:00, continuing the same waking day as
SESSION_2026-08-13_HANDOFF.md; user asleep for the last stretch, work
authorized: "commit after the run, run to the same-product judge, try
and implement one and see if it works — I'll review when I wake up."
Evidence: REVIEW_LOG R-S2-43. Commits: 1df4ef5 (partial runs) ·
36fca9d (plane framing + near-face cull + params-gated renders) ·
d8a7097 (perp renders keep the scene) · 20d90d2 (exempt→J8, crash-proof,
J9 ids) · plus the materialize commit. PUSH PENDING.)

## READ FIRST — what to review, in order

1. **`out/living_marble/cone_map.html`** — every tile is new. The flat
   objects' face-on shots now show the room, not black void.
2. **`out/living_marble/graph/multiplicity_sheets/index.html`** — 10 J8
   cases including the two NEW exempt ones (obj_018 ceiling light,
   obj_038 window).
3. **`out/living_marble/graph/materialize_report.html`** — THE NEW
   THING: every resolved node → its fate + the rule that decided it.
4. Viewer :8321 — run-14 boxes + the violet judge-preview layer.

## WHAT LANDED (detail in R-S2-43)

- **The render principle (user):** the slice is an INVISIBLE locator;
  renders cull only what is BETWEEN camera and object; everything else
  stays. Applied to cards AND perp shots (anchor = nearer of box face
  and plane). Flat objects are framed from their PLANE.
- **Stale renders killed at the root:** the renderer skips by FILENAME,
  which poisoned run 11 (new cameras, old images). Renders now carry a
  params-hash sidecar; mismatch deletes the png. Manual-wipe rule
  RETIRED.
- **Partial runs are first-class:** `--only` merges instead of
  clobbering, with provenance stamps and canon_eligible. Debug loop
  15-20 min → ~2 min. This is the biggest quality-of-life change.
- **Exempt objects can reach J8** via two new doubt kinds
  (rebox_rejected_smaller, rebox_truncated).
- **Crash-proofing:** a timed-out judge call no longer kills a docket.
- **Full chain re-run** on run-14 geometry, all benches; **first
  materialize** built and run (additive `graph["carved"]`).

## NEXT SESSION

1. **USER GATES (all open):** run-14 tiles · the 14 boxes that moved
   >10 cm under the new culling · the 10 J8 verdicts · the materialize
   report · and a ruling on J9 instability (below).
2. **J9 INSTABILITY — decide the fix.** Two runs 20 min apart gave
   DISJOINT pillow sets and flipped a light group. Options: a verdict
   cache (stability by fiat), repeat-vote consensus (3 runs, keep the
   majority), or pairwise same/different comparisons instead of asking
   for a subset of 9. Nothing else downstream is trustworthy until this
   settles.
3. **MATERIALIZE v2 — the six honest gaps** (R-S2-43 provisional):
   PART_OF_STRUCTURE linkage lost for the L (would shop two sofas) ·
   obj_063 carries no machine-readable pointer to the discarded
   back-run · piece ids contain "#" · edges not re-derived after
   materialize · 3 of 6 rules never fired on real data · J9 canonical
   size vs carved box precedence undefined for shopping.
4. **Carried:** 4g2 pillow-ON gap (carve turns resting relations into
   IN edges) · one-scene-only rule validation · a two-shot stitch for
   wall objects too wide to frame (obj_038 still truncates 3 sides).

## GOTCHAS (new tonight)

Renders are gated on a params sidecar now — do NOT hand-wipe pngs.
`--only` is safe and merges; a partial run marks the documents
`canon_eligible: false` until a full run. claude.exe judges MUST run
with cwd = their sheets dir (Read is cwd-scoped). A judge call failure
is an attempt, not a crash — check verdicts for "judge call failed"
before trusting a docket. Viewer restarts: WMI + absolute python path.
Backups from tonight: `pool_retake/run*_canonical_backup/`,
`out/_carve_partial_baseline/`, `graph/scene_graph_pre_carved.json.bak`.
