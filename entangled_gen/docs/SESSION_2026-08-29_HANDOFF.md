# SESSION 2026-08-29 HANDOFF — the convexity night; next = the wave, then PAIRED new runs

(Real date 2026-08-12 evening → 08-13 morning, user in the loop nearly
throughout. REVIEW_LOG **R-S2-159..167b**. All committed AND PUSHED;
nothing owed on git. PIPELINE.md carries the contract changes;
steps sheets ×4 + wall_review.html regenerated under the new rules.
pipeline_map.html is STALE w.r.t. tonight (map edits need the user's
blessing — bring as a question).)

## 0. THE ONE-LINE TRUTH

The 08-28 work order completed (scale applies + re-runs PASS, yaw
state-apply built and proven on fresh06 +12°), and then the user's
viewer walk found that the wall consumers still assumed a CONVEX room
— the rest of the night was user-driven find-and-fix (R-S2-161..167b),
ending with fresh08 fully verified: every box and mesh on the correct
side of every wall, bed facing right, no invented objects.

## 1. WORK ORDER FOR THE NEXT AGENT

**Step 1 — THE WAVE (pre-authorized in direction, launch discipline
applies):** `--phase all --from shell` on **fresh05, fresh06, fresh08,
fresh09** — ships the user-APPROVED wall outline (density gate +
walk-through slab; "the outline is good" on the fresh08 sheet), fixes
05/06/09's crushed wall items (from-shell includes the vote), opens
fresh08's bay (window seat + bookshelf become interior furniture),
and cleans the canon-eligibility stamps. Two-lane max, WMI-detached,
monitored, receipts read as the user would. OPTIONAL rider, ask
first: fresh05's −2.25° yaw apply (scene_yaw.py) before its run.

**Step 2 — NEW RUNS, AS PAIRS (user design, this session):** every new
scene runs BOTH pipelines — **Ours (run_scene full chain) + GLTS
(layout-only, treesearchgen claude bridge)** — so comparisons are
paired. **Batch = one scene's pair, run the pair IN PARALLEL within
the batch, batches SEQUENTIAL.** Rationale (user): the claude credit
limit is unknown and may run out mid-night — a completed pair per
batch survives; two half-done unpaired runs do not. GLTS has NO
mid-run resume — if credit dies mid-GLTS, that scene's GLTS restarts.
File GLTS results into out/comparison.html (compare_methods.py, ONE
fixed sheet).

**Step 3 — the overnight scene list:** see §2. Intake each picked
world (frame_bootstrap → the fresh-scene chain), name them fresh10..
onward, run the pairs in the user's priority order until morning or
credit exhaustion.

## 2. OVERNIGHT SCENE CANDIDATES (simple interiors, box rooms, unused
worlds; user picks — PICKS PENDING, patch this list when they answer)

| world id | type | why |
|---|---|---|
| a1ddded0 | bedroom | "minimalist bedroom, photorealistic, clean lines, uncluttered" — the simplest prompt in the corpus |
| 6cf716a8 | living room | "natural-style living room, clean and peaceful, warm natural light" |
| 2bf68fde | bedroom | "minimalist bedroom in an old building, bed on a low platform" |
| b6f5f206 | office | "cozy modern office, soft morning sunlight" — shortest prompt of the set |
| 748cf5e5 | bedroom | "minimalist contemporary bedroom, calm" |
| 270dd75d | living room | "contemporary living room, blue hues, calm" |

(46 candidates passed the filters: downloaded, unrejected, unused,
interior room type, no attic/loft/vault/cabin per PARKED §3. The six
above are the simplest by prompt. Full list re-derivable via the
filter script — MASTER_catalogue.csv is the source.)

## 3. THE FIX STACK (headers; read the entry before touching)

- 159: de-tilt truly sheet-only + plan_yaw_deg recorded
- 160: scene_yaw.py (extents RECOMPUTED, never corner-rotated;
  *_preyaw backups; partial-crash → restore backups first)
- 161: THE CONVEXITY FIX — capture = REACH + majority-REST (family
  spans); shell_clip = AABB of (footprint ∩ interior polygon)
- 162: rug tier see-through (beds on rugs stay anchors)
- 163: PRE-REGISTRATION ONLY: vote-internal pipelining; j3/j4/j6
  stage-parallel REJECTED (both write scene_graph.json — single baton)
- 164: density gate + walk-through slab (USER-DESIGNED, sheet-approved,
  LIVE CODE — ships with the wave; v1-vs-polygon disagreement WIDENS)
- 165: add channel KILLED; swap-in outside defense DISTANCE-TIERED
  (near → EXTERIOR-face snap; far → dropped). Delete-at-proposer
  REJECTED TWICE — do not re-propose.
- 166/166b: pillow facing hard at canon 15%; pca term reverted (the
  omission was a design decision — dot 0.5 was the tell)
- 167/167b: declip never kidnaps fully-outside meshes (near →
  EXTERIOR-face snap quantized DOWN; far → left where measured);
  VERIFIED: fresh08 bed dot 1.0 / window seat in bay / bookshelf
  flush exterior

## 4. OPEN QUESTIONS (bring with receipts)

1. fresh05 −2.25° yaw: apply with the wave, or below caring?
2. fresh05 scale verify s=0.884 (consensus, rich ruler population) +
   fresh09 doors 1.087 vs ceiling 0.832 — the post-normalization
   watch class.
3. v1-vs-polygon consumer round (§3 of the 08-28 handoff): node_views
   + envelope still read v1 walls; snap/supported_by use infinite
   planes; compose uses the outer box. The gap WIDENS under 164.
4. pipeline_map.html stale (R-S2-115..167 not drawn) — needs blessing.
5. Speed: R-S2-163 build; two-lane run_fleet wiring.
6. obj_008-class through-glass detections: survive as placed scenery
   meshes (left-where-measured). Killing them is a detection/delete-
   judge question, deliberately NOT a proposer rule.
7. PARKED.md untouched, incl. wall-embed (item 4) — deep-bay objects
   still flatten (obj_058's pocket curtain).

## 5. TRAPS

- The wave RE-SHELLS: v1 fitter unchanged → the two-rooms disagreement
  is bigger under the new polygon; expect consumer noise until the
  §4.3 round.
- Post-wave, re-judge sheets vs shipped state (steps sheets + 
  wall_review.html regenerate read-only anytime).
- GLTS: no resume; subscription = ONE lane; under 3-way contention it
  ran 3x slower (R-S2-135) — the batch design exists for this.
- Launch discipline: WMI-detach, ONE watch_gpu, clock lock via boot
  task (verify clocks.sm ≤1500 under load in gpu_watch.csv).
- scene_yaw partial crash → restore *_preyaw.* before anything.
- Adds return ONLY with --keep-adds.
- The viewer server on :8321 runs detached (WMI-launched 08-12).

## 6. WHERE EVERYTHING IS

- Commits: 284c2c0 → 4bc96eb+ (this handoff last). All pushed.
- PIPELINE.md: contract-changes block 2026-08-12/13 = the night's API.
- Sheets: out/<scene>/room_shell_steps.png (×4, current rules);
  out/wall_review.html (4 scenes); out/comparison.html (GLTS vs ours).
- fresh08 viewer: http://localhost:8321/?scene=fresh08
- Candidate filter script: session scratchpad pick_scenes.py (logic
  documented in §2; re-derive from MASTER_catalogue.csv).
