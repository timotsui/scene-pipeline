# 2026-07-14B handoff — retrieval v2 chain, base composition, amodal-box comparison

## Where this session ended

The stage-by-stage rework of retrieval+placement (queued by the earlier
2026-07-14 handoff) is BUILT and ran E2E on bedroom_marble. User verdict so
far: shortlists/picks "much better"; base-composition renders reviewed but
orientation facing is the visible gap; extraction (amodal) comparison built,
awaiting user judgment of which method feeds the lift.

## The chain (composition/, all file-contract stages — see composition/README.md)

C1 `retrieve2.py` → C2 `thumbs.py` → C2.5 `measure.py` → C3 `relevance.py`
→ C4 `review_server.py` (inspection, :8322) → C5 `pick.py` → C6 `place2.py`.
Re-run everything: retrieve2 → measure → retrieve2 → thumbs → relevance →
pick → place2 (measure→retrieve2 twice: real sizes shift shortlists).

Key decisions/findings (details in composition/README.md):
- Category-ONLY candidate gate (descriptions never vote); batch agent call
  maps noise labels ("poter"→poster, rug→doormat/place mat — objathor has NO
  rug category).
- Y-UP GATE: annotation `size` is z-up ordered for ~72% of catalog; then the
  thor_metadata bbox itself lies for a fat minority (window ann z=14cm, mesh
  54cm) → `measure.py` caches TRUE mesh extents; catalog() overrides.
- Fit = orientation-aware (6 axis perms, `perm` field; UPRIGHT_PENALTY
  catches standing-rug meshes; `thumbs.perm_rotation` realizes perms as
  proper rotations for thumbs AND placement).
- Scene is internally non-metric (median implied rescale ×0.77-0.83; doors
  130-160cm in a 2.8m room) → "fits in box at native scale" is unsatisfiable;
  coherence anchored on the SCENE-MEDIAN scale. Paper-worthy.
- C5 pick: fit is a tolerance band (fit≤0.8 + scale ×0.5-1.6 of scene
  median), argmax CLIP inside; top-5 finalists kept as alternates.
- C6 place2: perm rotation + uniform geometric-mean scale from REAL mesh
  bounds; floor-snap. FACING (0/180 about y) UNRESOLVED — parity flip makes
  it arbitrary. Next: dot-product facing rule vs room interior (discussed on
  the shelves example; user walked through it).

## Amodal box comparison (extraction experiment, entangled_gen/)

`amodal_boxes.py` (3 methods: splat-occupancy / collider / floor-prior,
downward-only) → out/<sc>/amodal_boxes.json; `amodal_compare.py` →
out/<sc>/amodal_comparison/COMPARISON.html (overlays + table). Result:
splat extends 6 occluded boxes to floor AND correctly leaves wall-shelf
obj_014 elevated (prior wrongly floors it); collider FAILED registration
(IoU 0.37, likely scale mismatch — needs scale estimation before use).
NOT wired into the lift — comparison only, user to bless a method.

> **SUPERSEDED 2026-07-15 (this paragraph's collider claims were wrong).**
> The registration failure was not scale — it was a MISSING TRANSLATION: the
> old search tried 8 sign flips and no translation, and a sign flip mirrors
> about the origin, so with the frames' origins 1.23 m apart nothing in that
> search space could register. `collider_register.py` (48 signed perms scored
> on voxel occupancy, then ICP) finds identity rotation, scale 0.9498,
> t_y −1.23 → voxel IoU 0.683, splat→surface p50 1.4 cm. The 3 collider
> "shelf" extensions this paragraph reports were artifacts of the broken
> transform. Re-run with the correct one, the collider adds NOTHING (agrees
> with splat on 5/6 boxes, misses the lamp): it is derived FROM the splat and
> is closed out as an amodal source. Live choice is splat vs prior — and note
> the collider's agreement is NOT independent corroboration of splat for the
> same reason. See PIPELINE.md "What the sources can and cannot know".

## Viewers

- retrieval inspection :8322 — `python composition/review_server.py --scene
  bedroom_marble` (two strips: dim-fit + CLIP; FITS frames; PICK/#n badges;
  look-only by user decision).
- 3D viewer :8321 — `python entangled_gen/viewer/serve.py --scene
  bedroom_marble` (new: composed-glb layer, GLTS-baseline layer parked next
  to the room on +x for side-by-side walking, amodal per-method box toggles,
  master splat on/off toggle, WASD + E/Q fly navigation, dropdown grouped by
  viewer/data/_active.json).

## Open queue (user: "improve later in the week")

1. Facing rule in place2 (one dot product per object).
2. Bless an amodal method → promote into the lift as a proper stage.
   (2026-07-15: now a 2-way choice, splat vs prior — collider closed out.)
3. ~~Collider scale-registration (rescues the Marble collider as a source).~~
   DONE 2026-07-15 and it did NOT rescue it — registration solved
   (`collider_register.py`), collider proven to add nothing. Closed.
4. Occlusion/lighting in composites; render-variant judging of the top-5
   alternates; C7 loop.
5. Extraction upgrade: pano manifest (98 objects) after re-lift verification.
   NB the pano is the SAME viewpoint as the 4 views — more boxes, not more
   parallax; it does not help the occlusion problem.
6. NEW: off-center render test — the splat is a 3D asset, so it can be
   rendered from cameras Marble never generated from (behind the bed, across
   the room). If the geometry holds up there, real parallax replaces the
   amodal heuristics entirely; if it is hollow, splat-occupancy is the
   ceiling and item 2 resolves to "pick splat". Not yet run — this is the
   question that decides item 2.
