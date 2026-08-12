# SESSION 2026-08-16 HANDOFF — DETECTION CHOICE FIXED, SPLITTER'S ROUND CAP FOUND; NEXT IS J9

(Real date 2026-08-08 evening. Evidence: REVIEW_LOG R-S2-45 (this
session) and R-S2-44 (J8 v2.4, user-accepted earlier the same day).
Commits: 99070ab (detection ranking + framing + re-shoot), 09791e5
(splitter fewest-cuts), plus the wrap-up commit carrying docs/map.
PUSH PENDING.)

## START HERE NEXT SESSION

**The one thing left before the chain is fully settled: J9, the
same-product judge.** Everything above it is done and user-passed.
J9's known problem is INSTABILITY — two runs 20 minutes apart on
near-identical data gave DISJOINT sets (pillows went {obj_024,
obj_037} -> {obj_015, obj_016, obj_026}). It has no verdict cache, so
it re-decides every run. Three candidate fixes, none chosen yet:
  1. a verdict cache (stability by fiat, like the other judges),
  2. repeat-vote consensus (run it 3x, keep the majority),
  3. pairwise same/different comparisons instead of asking it to pick
     a subset out of 9 members at once.
Nothing downstream of J9 is trustworthy until this settles.

## CURRENT STATE (all current, all on disk)

Carve **run 17**: 46 objects, canon-eligible, statuses
{carved_pano 28, kept_wall 7, kept_ceiling 7, kept 2, kept_outlier 2}.
Chain re-run on it: J0 1 nomination · J1 obj_068+obj_020 SAME (the
chair duplicate, caught again now that obj_068's box is chair-sized) ·
J8 8 cases (2 swaps, 5 kept, 1 SPLIT) · J8s 1 cut / 1 piece ·
J9 6 groups · materialize 46 -> 45 nodes, 1 conflict, 9 open questions.

**Review pages, all rebuilt:**
- `out/living_marble/cone_map.html` — carve tiles
- `out/living_marble/judge_cards.html` — J8 cases as visual cards
- `out/living_marble/graph/multiplicity_sheets/index.html` — J8
- `out/living_marble/graph/split_sheets/index.html` — the sofa cut
- `out/living_marble/graph/same_product_sheets/index.html` — J9
- `out/living_marble/graph/materialize_report.html` — every node's fate
- viewer :8321 — the cyan layer now labels itself with the run id

## WHAT LANDED THIS SESSION

1. **Detection choice is a RANKING, not highest-confidence.**
   combo = detector score x prior match x 0.7 if the box touches a
   frame border. The old rule picked a NEIGHBOURING chair on obj_020
   (0.430 confidence, 36% inside the prior) over the correct one
   (0.413, 98% inside) — the right box was already in the list.
2. **Framing check** — if the object doesn't fit the overhead frame,
   pull the camera back and re-render before detecting.
3. **Re-shoot ladder** — a detection touching a border is cut off;
   take another shot rather than patch the footprint.
4. **⭐ The splitter's round cap was changing its answer.** Told it had
   3 rounds it deferred work and used 3 calls / 10 min for 2 pieces;
   told it had 1 it settled the same object in ONE cut at HIGHER
   confidence. Fix: keep the ceiling, call it a ceiling, say fewest
   cuts wins. **Generalizes to every judge we give retries to.**
5. Viewer labels compose from the data (a hard-coded "run 10" caption
   was showing over run 16 boxes).

## CARRIED OPENS

- **J9 instability** (above) — the blocker.
- **Two outlier-guard trips**, both shipping their original box with
  the oversized box recorded as a doubt: obj_019 pillow at exactly 8x
  (no pano box; overlapping pillow pile) and obj_029 magazine at 40x —
  its top view finds NO detection at all, so it falls back to the
  full-height wedge and the bookshelf wins the vote. obj_029 is the
  more interesting one: nothing yet handles "no top detection".
- **A judge that sees something its form can't express.** J1 twice
  wrote "obj_068 is likely a table, mislabeled as chair" and had no
  field for it. Same shape as the three J8 blockers fixed in R-S2-44.
  A typed "wrong class / spurious node" channel is still missing, and
  it belongs BEFORE the carve.
- **post_judge_conflicts** — 5 pairs whose overlap grew after judging
  (R-S2-44), recorded not acted on.
- **Materialize gaps** (R-S2-43): the L loses its one_structure link,
  piece ids contain "#", edges not re-derived after materialize.

## GOTCHAS

Renders are gated on a params sidecar — never hand-wipe pngs. `--only`
MERGES in the carve, J8 and the splitter (repairs one case, keeps the
rest). Judge call failures are attempts, not crashes — check verdicts
for "judge call failed". A judge's prompt change invalidates its cache
by design; the splitter's cache made a re-run free (0 calls). Timing:
each model call is 2-3.5 min, renders are seconds; the splitter is the
only stage whose calls are strictly sequential. Viewer restarts: WMI +
absolute python path.
