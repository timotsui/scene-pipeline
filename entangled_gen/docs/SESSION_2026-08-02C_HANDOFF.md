# SESSION 2026-08-02C HANDOFF — propose v6 canon, SCREENING DISSOLVED, shopping v1, first test fit

Recovered from a session crash (the crashed session's v6 work was
uncommitted on disk and its run had actually COMPLETED). Commits this
session: a3b8885 (propose v6 canon) → a9fad3e (shopping v1) → map+
handoff commit after this file. Push is the user's.

## 1. Propose module v6 CANON (a3b8885, user: "this is our form")

- Prompt v6: adds split into `implied` (dependency, quoted evidence,
  `evidence_found` substring check) vs `expected` (convention); bulky
  open-floor furniture = swap-only PROMPT context; loop cap 3.
- MODULE SPLIT: loop output frozen to `edit_proposals_raw.json` before
  step 3; step 3 = `size_and_place()`; `--size-only` re-entry = 0
  model calls (dev re-entry only; canonical runs stay one invocation).
- RELATION ROUTER (the "window standing on the curtain, through the
  ceiling" postmortem): placement rule picked by the reply's relation,
  not the anchor id prefix. mounted_on/hangs_from walk the support
  chain to the wall/ceiling (slab height-clamped); inside → interior;
  near → beside the host on its parent surface; honest fails.
  Re-place: 13/13 boxed, window IN-WALL behind curtain overlap 1.0.
- Known warts (screening's- er, now the FIT LOOP's problem): light
  switch mis-anchored to the ceiling light (hangs at ceiling); remote
  #1 landed on the OTHER air conditioner (referent name-substring hit
  the wrong twin of duplicate detections).
- AFK REVIEW FORM (user liked): project boxes into the 7 judge views,
  SendUserFile. Scratchpad script; rebuild when needed.

## 2. THE BIG REFRAME (user rulings, on the record)

1. **SANDBOX:** the original scene's job ended at extraction. NO truth
   gate — proposals are never pixel-checked against the original
   scene. Its photos survive only as a STYLE guide (pick time).
   (Supersedes the R14 pixel-check standing rule.)
2. **SCREENING IS DISSOLVED** as a module. The "filter" = shopping's
   library-match step: no matching category → not bought → the host
   asset covers it (door handle). About OUR LIBRARY vs the proposal,
   never the original scene.
3. "Comes-with" checks (beds pre-dressed?) PARKED until real problems.
4. PLAIN-ENGLISH REGISTER RULE hardened (memory updated): whole
   register, not just terms — no noun-stacks, no arrow chains in prose.

## 3. Shopping v1 (a9fad3e) — ordered candidates per ANCHOR box

`compose/shopping.py` → `compose/shopping.json`. Anchors first (user:
limit the search tree; run until fit, THEN subs per fitted anchor).
bedroom_marble: 32 anchors / 32 with candidates (rug → tiled doormat
stand-ins via the one batched label-mapper call) / 63 subs deferred /
2 swapped out. Sub-hosting through swaps handled (books → wardrobe,
glass → future wall shelf). Window add is currently a SUB of the
curtain (quirk, flagged to user). Viewer:
`python composition/review_server.py --scene bedroom_marble --shopping`
(:8322, real-view crop + candidate cards). obj_062 (second AC,
rename-suspect): NO view sees its box even with judge views — box
suspect, open eyeball. Plan doc: docs/PLAN_SHOPPING.md.

## 4. First TEST FIT rendered (scratchpad/test_fit.py, review sent)

All 32 #1 candidates naively placed (perm+uniform scale+tiling,
bottom/center/top-aligned by mount) in the measured shell, rendered
from the 7 judge cameras SIDE BY SIDE with the real renders. User is
reviewing. NOT the fit loop — no judging, no candidate walking.

## 5. NEXT SESSION: design the FIT LOOP (S5 on the map)

Per anchor: place candidate → render → judge → next candidate until
fit; then sub rounds per fitted anchor. Inherits the parked policies:
uniform-vs-stretch scaling, asset facing rule (front=+z check never
done), style tiebreak (room photos as mood), the two v6 warts above,
collide gate placement (map: PH2 per selected model). Map redrawn
this session: S4 = SHOPPING (built), S5 = FIT LOOP (next).
