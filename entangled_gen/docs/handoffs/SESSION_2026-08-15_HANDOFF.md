# SESSION 2026-08-15 HANDOFF — J8 SETTLED (comparison ask, per-node candidates, inner-before-outer)

(Real date 2026-08-08, continuing the same waking stretch as
SESSION_2026-08-14_HANDOFF.md. Evidence: REVIEW_LOG R-S2-44.
USER ACCEPTED the J8 verdicts: "they all make sense. this is the one we
use." PUSH PENDING.)

## REVIEW THIS FIRST

`out/living_marble/judge_cards.html` — all 10 J8 cases as visual cards:
the panels the judge saw, the boxes it was offered, which it picked,
its reason, before/after sizes. Every image and link verified.

Then: `graph/materialize_report.html` (every node's fate) ·
`graph/split_sheets/index.html` (the sofa cut) · viewer :8321 amber
"materialized" layer.

## WHAT SETTLED THIS SESSION (all three user rulings)

1. **ASK FOR A COMPARISON, NOT A DIAGNOSIS.** ONE_BOX now means: compare
   the candidate boxes, pick the better one — COMPLETE first (contains
   the whole object; cutting through it, or floating above the surface
   it rests on, is worse), then TIGHT ENOUGH. Explicit error tolerance:
   perfection is not required. The old failure-mode conditions are
   hints, not tests. NEW OUTCOME `NO_GOOD_BOX` when every candidate is
   grossly wrong (distinct from UNCLEAR).
2. **RULE ON THE BOXES A NODE ACTUALLY HAS.** Per-case candidate list
   (carved: vote|pano; carve-exempt: current|rebox_candidate; "either"
   only when they agree within 5 cm). This unblocked exempt nodes, which
   previously could not answer at all. Exempt cases also gained the
   BOX-CONTENT panel (only the gaussians inside the node's own box).
3. **JUDGE INNER BEFORE OUTER** (chosen over a fixed-point loop — "too
   much compute"). Cases sort into LEVELS; where one docket box sits
   >=50% inside another the smaller is judged first; each level's
   verdicts fold into a SETTLED GEOMETRY MAP that later levels and
   split_cuts read. Fixed a live 0.30 m overlap -> 0.000 m.

Result: 10 cases, 3 levels, **4 boxes changed** (obj_018 light
1.25x0.03x0.52 -> 0.17x0.05x0.16 · obj_021 chair · obj_019 pillow ·
obj_063 sofa — three GREW because the object continued past the smaller
box), 5 kept, 1 SPLIT. Materialize applied all four.

## NEXT

1. **J9 INSTABILITY — still the biggest open.** Two runs 20 min apart
   gave disjoint same-product sets. Options: a verdict cache, repeat-vote
   consensus, or pairwise comparisons instead of subset-picking. Nothing
   downstream of J9 is trustworthy until this settles.
2. **post_judge_conflicts** — 5 pairs whose overlap GREW after judging
   (obj_024/obj_063 0->32%, obj_013/obj_019 60->71%). Second-order
   dependencies the level order cannot see. Recorded, not acted on; the
   user accepted the trade. Decide whether they need a second pass.
3. **Materialize gaps** (R-S2-43): the L loses its one_structure linkage
   (would shop two sofas) · obj_063 has no machine-readable pointer to
   the discarded back-run · piece ids contain "#" · edges not re-derived
   after materialize · 3 of 6 rules never fired on real data · J9
   canonical size vs carved box precedence undefined.
4. **Carried:** 4g2 pillow-ON gap · one-scene-only rule validation · a
   two-shot stitch for wall objects too wide to frame.

## RULE ADDED TO MEMORY THIS SESSION

**Never present a fact derived from human observation — or from the
quantity under question — as an automated measurement.** I ran an
occlusion test seeded by the user's eyeball, sampled over one of the
boxes under judgement, and reported it as a pipeline fact. Before
proposing any new fact for a judge: state what it is computed from and
check every input is available to a blind run. (RULE #1 addendum.)

## GOTCHAS

`--only` now MERGES in both the carve and J8 (repairs one case, keeps
the rest) — but an `--only --sheets-only` run still rewrites the sheets
index narrow until the next full build. J8 call failures are attempts,
not crashes: check verdicts for "judge call failed" before trusting a
docket. Renders are gated on a params sidecar — do not hand-wipe pngs.
Viewer restarts: WMI + absolute python path.
