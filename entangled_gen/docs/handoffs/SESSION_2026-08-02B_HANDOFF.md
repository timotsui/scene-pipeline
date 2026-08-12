# SESSION 2026-08-02B HANDOFF — S3 closed at v5 (loop + swap); scale question resolved

**Read first:** PLAN_COMPOSE_LOOP.md R14/R15 entries + the pipeline map
S3 card (v5). Commits this session: 41e1eb6 (v3 per-item canon) →
19c6e9b (v4 sizing+union) → 0c0eb3b (v5 loop+swap + viewer human).
Push is the user's (settings deny `git push` by design).

## S3 propose_edits — CLOSED at v5, evolution in one line each

- v3: per-item forced replies (every item answers "nothing to add" or
  names a gap; final `room` scan slot) — killed the room-level
  brainstorm's rotating tail.
- v4: step-3 size+box (scene-size reference frame, pure-code free-space
  placement, `box_source: estimated_prior`) + briefly the 3-run union.
- **v5 CANON: the LOOP** (user ruling: count is the wrong metric,
  semantic/spatial coherence is): rounds fold proposals into a working
  inventory, stop on dry round or cap 6; round stamp = salience.
  Sizes ride in item lines → adds return size_m inline; T_SIZE is
  fallback. **SWAP channel:** re-interpret N detections as M objects;
  ≥1 out + ≥1 in, out = real detections; code packs in-items into the
  out-envelope → feasible/infeasible verdict; out_children recorded.

**v5 first run (bedroom_marble):** 6 rounds (cap, never dry), 9 adds
all boxed, **1 FEASIBLE swap: picture obj_017 + glass obj_059 →
floating shelf + vase** — caught from the graph's own impossible
support edge ("a flat picture cannot hold an object on top"). The
mirror-on-invented-wardrobe ecosystem effect persists (r5) — screening
gates it.

## The scale question — RESOLVED, no world rescale

Measured against real-world constants: doors 2.12–2.16 m, desk 0.79,
ceiling 2.76, median ratio ≈ 1.0 ± 6%. **The ~0.8× lore was old
asset-fit bias (oversized catalog meshes), not scene scale.** User
ruling: do NOT resize the world. Viewer has a "human 1.75 m" toggle
(baked static CesiumMan, `viewer/assets/human_static.glb`, unlit) as
the eyeball reference. `scale_check.py` (per-scene metric estimator)
stays QUEUED for future scenes, not urgent for this one.

**Bed case study (user eyeballed):** bed 1.71 m is REAL — it ends at
the shelf on both ends, not truncated. Generator (World Labs/Marble)
furniture sizing accepted as scene truth; any wrongness surfaces at
the SHOPPING FIT + RENDER LOOP, which is the sanctioned fix point.
The pillow obj_060 box IS a mis-lift (floor-level, inside the
mattress) — self-heals at mesh time via the dependent-placement
contract. Neither recorded in gt_labels yet (user offered, not done).

## Open threads, in order

1. **User: "still missing the last 'sizing for proposed item' step"**
   — the feeling that add sizing isn't finished. Current state: sizes
   come from the loop inline (scene-referenced) + T_SIZE fallback +
   clamp-to-fit. Unclear what's missing — ASK before building.
2. **v5.1 wart:** adds anchored to other adds (mirror → wardrobe)
   fall back to `floor` support — support_of() only knows obj_/arch
   ids; should say `on:add_r1n5` and place on the proposal box.
3. **S4 SCREENING** — next module. Inherits: entry policy per add/swap
   (OPEN: faithful-reconstruction pixel-check vs plausibility-
   completion with invention labels), round stamps + envelope verdicts
   + out_children as evidence, swap accepted as a UNIT or not at all,
   non-visual dedup (petitions), doors/windows (user ruled: shop them
   too — arch-class marker, not skip). Parked draft in
   PLAN_COMPOSE_LOOP.md; 3 of 4 design decisions answered in-session
   08-02 (arch=shop, HOLD holds dependents, v1 scope), entry policy
   pending.
4. Review gates R8/R10b/R11/R13b still formally open + eyeballs
   obj_062/obj_083/obj_096.

## Session lessons

- The loop experiment (expC) ran 3× total: it diverges without a gate
  (phantom keyboard → mouse 0.75; mirror on invented wardrobe; "full
  computer setup" built from two phantoms). User chose the loop ANYWAY
  — for coherence and native dedup — with screening as the gate. Both
  facts on record; don't relitigate.
- PRIME-DIRECTIVE correction (blunt): NO caches/pins/human-curated
  state in pipeline decision paths. K-runs/loops live INSIDE one
  invocation.
- Fix at the source, verify by measurement, not lore: the 0.8× scale
  belief died to 10 minutes of door-height arithmetic.
