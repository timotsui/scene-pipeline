# SESSION 2026-07-26 HANDOFF — pano-track post-processing (filter + dedup)

Read `docs/PLAN_SELF_PANO_RIG.md` first — its top UPDATE blocks carry the
full state. This session was the daytime review/post-processing session on
top of the canonical pano track.

## What happened (all user-directed)

1. **f30 hard score filter ADOPTED** (user: "i think this works").
   `manifest_filter.py` (NEW, generic --thr, no reruns) at 0.30:
   108 -> 102 objects; the 6 drops include 3 retake-confirmed boxes
   (filter overrules the verifier — caveat logged in R8) and the stray
   `conditioner` label artifact. Drops preserved in `filtered_out`.
2. **Dedup merge BUILT + RUN** (`manifest_dedup.py`, NEW): 102 -> 92.
   Physics rule: high mutual 3D IoU = one object, merge geometry, keep all
   labels (`alt_labels`); nesting survives (high containment, low IoU).
   IoU>=0.6 = pure geometry; gray zone (0.4-0.6 + containment>=0.9) judged
   by ONE batched claude.exe haiku call on the label pair, cached in
   `out/<scene>/dedup_llm_cache.json` (door|window=same;
   bookshelf|shelf + book|shelf=part-of). Degrades by keeping boxes.
3. **USER RULE saved to memory (automated-pipeline-rule):** NO hard-coded
   per-scene knowledge anywhere; pipeline must run on all scenes
   unmodified; semantic judgments via cheap LLM calls, swappable to a
   local LLM. This killed the synonym-whitelist option.

## AWAITING USER JUDGMENT (resume here)

- **R9 (dedup)** in `docs/REVIEW_LOG.md`: toggle "pano track · f30+dedup"
  (92) vs "pano track · f30" (102) in the viewer (:8321,
  launch_viewer.bat). Look-fors: wrong merges? the 3 door+window merges;
  the kept bookshelf thicket (obj_043/080/093/140).
- **R8**: canonical-layer verdict line still open (f30 line filled).

## Current chain (bedroom_marble)

scene_manifest_pano2c_rc.json (canonical, 108)
  -> _f30 (score>=0.30, 102)  [ADOPTED]
  -> _f30_dd (dedup, 92)      [AWAITING R9]

## Next candidates (from the post-processing queue, none started)

- floor snap (bottoms within epsilon of floor -> exact contact)
- room-envelope clamp (nothing through walls/ceiling)
- whatever the R9 viewer pass surfaces
- then the consumer rewires (scene graph first — map's marked next)
