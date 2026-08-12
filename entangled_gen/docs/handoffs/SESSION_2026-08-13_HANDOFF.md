# SESSION 2026-08-13 HANDOFF — THE FULL-CHAIN DAY (every bench ran; splitter designed live to convergence)

(Real date 2026-08-07 morning → 08-08 ~01:00; names run ahead. Continues
SESSION_2026-08-12_HANDOFF.md. Evidence trail: REVIEW_LOG R-S2-35..42.
PLAN_CARVE_DOWNSTREAM.md = the working plan, all statuses current.
pipeline_map.html re-drawn throughout (authority). Commits this
session: c48c87e (rename + run-6 fixes + notch rule + J8 v2 design),
6fb1d64 (loop-back + J8 v2.1 canon verdicts + runs 7-10 rules), and
the session-close commit carrying the splitter + J9 + this handoff.
PUSH PENDING: master is ahead of origin — `git push origin master`.)

## WHAT HAPPENED (compressed; the log entries carry the detail)

1. Pano-mask rename (arm→pano everywhere live; readers dual-name).
2. obj_014 bookshelf wall-leak → 4 carve fixes → RUN 6 (R-S2-35);
   plan-fill k-sweep honest negative → large_empty_notch ADOPTED
   (1.52 m² vs 0.18 census) → THE L ON THE DOCKET BY RULE.
3. J8 v2 sheets + 3 trial verdicts; user reframe → v2.1
   (ONE_BOX|SPLIT|UNCLEAR, facts-from-edges after the obj_063
   stimulus gap, green neighbor wireframes).
4. Loop-back B2 IMPLEMENTED + RUN (rederive_carved_edges.py, additive
   carved_edges layer; J0/J1 via --edges-from; chair dup obj_020↔041
   SAME; window↔curtain DISTINCT). J8 canonical verdicts (7 cases).
5. Glass-door root cause (mass 100% beyond the wall) → PROTRUSION
   exemption (<=0.20 m) + SHELL CLIP → runs 7-8 + NEVER-SILENT kept
   path (recovered obj_005_c00 + obj_017_c00; scene = 46).
6. Slice clamp TRIED + REVERTED (walls must stay in the tiles; the
   half-space electorate filter alone carries the fix) → RUN 9;
   TV stand recovered full extent (0.98→3.38 m) + rejoined docket.
7. PERP-CAM RE-BOX for flat wall/ceiling objects → RUN 10 = BOX CANON
   (13/14 re-boxed; glass door drift corrected 0.53 m).
8. SPLITTER DESIGNED LIVE (R-S2-40..42): box-content top render →
   named dynamic grid + measured S-lines → one-cut-per-call chain
   (k=3 cap) → keep/discard + residue criterion + INDEPENDENT-SUPPORT
   eligibility → THE L CONVERGED: 1 call, 1 cut (S1 verbatim),
   0 doubts; representation = 1 new piece + obj_063's + obj_006's
   existing boxes. USER: "this is the right design, done with j8."
9. J9 FIRST VERDICTS EVER (crop contact sheets; cwd bug found+fixed:
   claude -p reads only inside its working dir): 6/6 — chair set
   020+041+028 @0.57×0.75×0.23, burgundy-pillow set ×5, light set
   ×3 + pair 031+045, magazines NOT same (both groups).
10. Viewer: J8/J1 verdict lines on cards, /multiplicity.json route,
    JUDGE-PREVIEW box layer (violet, default off: ship_vote swap for
    obj_068, obj_011 → its piece, obj_024 dropped:covered).

## STATE

- Carve run 10 = BOX CANON. Statuses {carved_pano 28, carved 2,
  kept_wall 7, kept 2, kept_ceiling 7} = 46 objects, none silent.
- EVERY judge bench has now RUN end-to-end: doubts → carved_edges →
  J0/J1 → J8 (7 verdicts) → J8s (converged) → J9 (6 groups).
- Sidecars: multiplicity.json, split_cuts.json, same_product.json,
  carve_doubts.json — all current; canonical layers UNTOUCHED.
- Review surfaces: loopback_j8_review.html · notch_review.html ·
  cone_map.html (exempt rows incl. perp strips) · multiplicity_sheets/
  · split_sheets/ · same_product_sheets/ · viewer :8321 (restart via
  WMI only; slicevote layer = run 10, judge-preview layer new).

## NEXT SESSION (user: "we will be back for j9")

1. **J9 GATES:** user eyeball of same_product_sheets/index.html + the
   6 verdicts (REVIEW_LOG R-S2-41 lists them). Known nits queued:
   set_members id format inconsistent (bare numbers vs obj_ prefixes
   — normalize before shopping consumes); obj_005_c00/obj_017_c00
   have NO crops (carve-recovered nodes lack funnel evidence — decide
   their evidence channel); the chair set contains the J1 dup pair
   (consistent, merges to 2 chairs of 1 product).
2. **PHASE C MATERIALIZE design** — every input now exists. Must
   define merge semantics: J1 SAME merges (020+041, 013+048) +
   J8 identity (one_structure → PART_OF_STRUCTURE) + J8s geometry
   (pieces; not-this-object/dropped pieces NEVER grow the named
   neighbor) + J8 box rulings (ship_vote obj_068) + J9 sets (one
   asset per set at canonical size). The judge-preview viewer layer
   is the visual spec of what materialize should produce.
3. **Carried opens:** 4g2 pillow-ON gap (carve turns resting
   relations into IN edges — support re-derivation needed before
   compose; independent-support eligibility depends on it too) ·
   J8 confidence clustering (all .62-.83) · TV-stand extent + curtain
   re-box eyeballs · plan-fill legacy threshold recalibration
   (glass door fires nothing now — low_plan_fill may be dead weight)
   · notch/protrusion rules tested on ONE scene.

## GOTCHAS (carried + new)

PYTHONUTF8=1 on any redirected stdout. HF_HUB_OFFLINE=1 for seg.
GPU clock lock survives this boot (re-lock after reboot:
nvidia-smi -lgc 0,1500, admin). Viewer restarts: WMI
Win32_Process.Create with absolute python path (PATH absent in WMI).
claude -p judges MUST run with cwd = the sheets dir (Read is
cwd-scoped — the J9 first-run failure). Carve card renders are wiped
only on slice-geometry edits; --only runs still CLOBBER whole-scene
outputs (backup first: run5-9 backups live in pool_retake/). Agents
interrupted mid-launch may still have completed their edits — verify
file state before re-issuing (happened twice: clamp revert, recursive
splitter). Rule #1 held all session: every rule geometric, every
threshold from a blind census, the docket auto-only.
