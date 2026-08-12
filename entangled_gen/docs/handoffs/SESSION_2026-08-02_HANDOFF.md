# SESSION 2026-08-02 HANDOFF — the autonomy session (4/4 blind GT)

**Read first:** `PLAN_COMPOSE_LOOP.md` (R5c + R8–R13b review entries +
rows 6r–6y tell today's whole story). Map: `pipeline_map.html` (step-3
arrows are now STATE-ORIENTED: each arrow = the full scene-graph state;
a module's write joins the state; upstream rerun ⇒ downstream stale).

## Where things stand (all committed, pushed through 2a41a00)

**THE PRIME DIRECTIVE (elevated by user, top of memory):** fully
automated pipeline, no human in the loop. Ground truth is an ANSWER KEY
(`out/<scene>/compose/gt_labels.json`), scored after every blind S1 run
(`GT MATCH/MISMATCH` print + `gt_check` layer metadata) — it never
enters any prompt. Bench: obj_002 AC (wall), obj_127 door (embedded),
obj_009 basket (floor under side table), obj_001 plant (floor) —
**all 4 blind-matched by the current stack.**

**Current module versions (bedroom_marble state is fresh, whole chain):**
- witness `describe_nodes.py` **v7** — adjacency verbs only ("appears to
  meet", "flush against"); never weight verbs; full re-describe done.
- `supported_by.py` **v12** — surface vocabulary (on_top / inside /
  mounted_on / hangs_from / embedded_in; rests_on+leans_on retired),
  bottom-edge evidence lines, real-gap rule, type-prior tiebreak,
  nearest-wall ALWAYS offered, "nearest things" distance line, CARRY
  TEST for inside, mis-lift rule, **BOX ERROR MODEL** (jitter /
  truncation / bleed / mis-lift / missing objects — judge names the
  assumed mode). 31 anchors · 4 multi-option · 0 unresolved.
- `consistency.py` **v7** — against-slot ≠ confirmed (the AC bug);
  17 coherent drops on the v12 layer (doors' floor contacts = swing
  clearance).
- `snap.py` **v1.2** — snap proposes; flagged docket → typed-menu agent
  (adopt-refit / snap / no-snap / defer); MAD refit from lift-pool
  members; evidence-keyed verdict cache + `snap_rulings.json` user pins
  (currently empty); curtain refit ADOPT 0.85 stable (0.449→0.206 m);
  LARGE = 8.
- `propose_edits.py` **v2** — R5c passed; current adds: keyboard 0.8 /
  blanket 0.75 / mouse 0.7 / wastebasket 0.55. Add-pass run-variance is
  a standing design question (union-of-N?) for screening.

## TOMORROW: S4 SCREENING, then S5 SHOPPING (user: "hopefully finish
the pipeline")

1. **S4 screening design first** — parked draft at the bottom of
   PLAN_COMPOSE_LOOP.md (COMPOSE / SKIP_ARCH / HOLD per anchor, one
   batched call). It must absorb: S3 adds+deletes (the same door as the
   judge re-entry), reopen_petitions (non-visual dedup), doors/windows/
   curtain special cases (S3's window add from an earlier run belongs
   here), and the union-of-N decision for add-pass variance.
2. **S5 shopping** — donors ready: `docs/S4_SHOPPING_DESIGN_NOTES.md`
   (mined from old C1–C5: contracts, worked/failed, 17 open questions),
   retrieval-v2 shortlists + pick viewer, asset yaw canonicalization.
   Note the vocabulary matters here: `inside` items (39!) are shelf/
   container contents — cast-list strategy for them ≠ anchors.

## Open items (non-blocking)

- **Review gates formally open:** R8, R10b, R11, R13/R13b — arguably
  superseded by the 4/4 blind result; user can sweep them in one pass.
- **Eyeballs:** obj_062 "second air conditioner" (rename suspicion; it
  snapped wall-flush 0.128 this run) · obj_083 crops (record layer
  only) · obj_096 wall-mounted vs standing-on-shelf (affects what
  shopping buys). Each eyeball can become a gt_labels entry for free.
- Snap adjudication cache is evidence-keyed, so S1 version bumps
  re-roll the docket verdicts (obj_096 flipped between runs); pins
  exist if one needs freezing.

## Today's method lessons (worth keeping)

1. Wrong verdict → autopsy → fix the SOURCE (scene-agnostic) → blind
   re-test → keep the label as regression. Never patch the verdict.
2. Starved judge ≠ dumb judge: pipe the evidence (bottom-edge lines,
   nearest-things) before blaming the model.
3. Prompt-rule accretion has a limit — rules interact (v9 churn);
   prefer structure: vocabulary, evidence lines, caches.
4. Witnesses report what pixels show (adjacency), judges weigh it
   against geometry — cameras can't see weight.
5. The regression bench caught v11 breaking the plant IN THE SAME RUN
   it fixed the door. Labels are cheap; add one per eyeball.
