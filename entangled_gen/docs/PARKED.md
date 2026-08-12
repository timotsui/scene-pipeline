# PARKED — known, understood, and deliberately not being worked on

Opened 2026-08-11 by user instruction: *"Right now I annex the top view
problem and anything specific to j9. They are not the most important fish
to fry. But please document them explicitly somewhere obvious."*

**This file is not a bug list.** Everything here is a decision to WAIT.
Each item is understood, measured, and has a named consequence. None of
them stops a scene; all of them make scenes worse in a way that is
counted and reported rather than hidden.

**Nothing in here should be "fixed" opportunistically.** They are parked
because the user has other priorities, not because nobody has noticed.
If you are an agent reading this mid-run: leave these alone and say so.

Where these show up while parked:
- `graph/scene_gate.py` reports the top-view cost as an INFO line on
  EVERY scene, so it appears in every fleet report.
- `run_fleet.py`'s morning table carries those INFO lines beside each
  scene's verdict.

---

## 1. THE TOP VIEW — `ctop` has never detected anything

**Parked 2026-08-11. Previously out of scope by the same ruling
(AUTOMATION_READINESS §4.1); re-affirmed after the fresh-scene numbers
came in much worse.**

### What it is

The vote's plan view has two cameras:

| camera | where | detections |
|---|---|---|
| `top` | inside the room, looking down | **22 of 23** |
| `ctop` | above the ceiling, ceiling deleted, near-vertical | **0 of 11** |

`ctop` is the FALLBACK camera, so by design it is handed the hardest
objects — tall things, things high on shelves, things `top` could not
see. It has never once produced a detection.

### What it costs

When the plan view finds nothing, the slice falls back to a full-height
wedge. A wedge only constrains left–right, so **nothing re-measures the
box and it ships roughly as it arrived from detection.**

Measured, per scene, at the `grouped` layer:

```
living room   9 of 46 objects (20%)
bedroom      55 of 82 objects (67%)
```

The bedroom is the honest number for a room this was NOT developed
against, and it is three times worse. Two thirds of that scene's objects
were never actually measured by the vote.

`materialize` flags them `slice_fallback`; `scene_gate.quality_notes`
counts them on every scene and prints the count with a pointer here.

### Why it is not a quick fix

It is a design question about how the vote sees tall and flat objects,
not a broken camera. `ctop` looks nearly straight down through a deleted
ceiling; whatever is wrong is about what that view can show a detector,
which is a modelling decision, not a parameter.

### What NOT to do meanwhile

Do not tune thresholds to make the number look better. The count is a
measurement of how much of a scene was really measured; a lower number
obtained by loosening a gate is worse than an honest high one.

---

## 2. ANYTHING SPECIFIC TO J9 (same-product grouping)

**Parked 2026-08-11.** J9 runs, produces verdicts, and the chain
completes. These are open questions about the QUALITY of what it is
shown and what it is asked, not about whether it works.

### 2.1 How many pictures each member is shown

`graph/judge_same_product.py` -> `member_crop_paths()` early-returns
`[shown[mid]]` — the main photo alone — when a node has one.
`CROPS_PER_MEMBER` is 2 and the sheet builder already lays out two side
by side, so the second slot is simply unused.

Each node also carries supplementary views (235 across the living scene)
that J9 is NOT given. For a "same product?" judgement two angles may
well beat one. Changing it changes what the judge sees, so it wants a
ruling rather than a tweak.

⚠ If those views are ever switched on: some are **cone-culled** —
occluders in front of the object were deleted — and each is marked
`occluders_removed`. The user has ruled that acceptable as evidence, but
the judge is not currently told. If they go in, say so in the prompt.

### 2.2 The chair pool on `living_marble`

The old gate question was "obj_021+028 vs obj_041+068 — two chair models
or one?". **It no longer applies**: `obj_068` was merged into `obj_020`
by J1 (96% containment, recorded in `obj_020.merged_from`). The pool is
now five: `obj_010, obj_020, obj_021, obj_028, obj_041`. The question
has to be asked again against that set.

### 2.3 J9 degrades rather than refusing

With no `shown` layer, or a stale one, J9 falls back to detector crops
and says so in the log — then completes normally. That was a deliberate
choice so a scene that skipped `node_evidence` still finishes. In an
unattended run it means a scene can be judged on crops cut around boxes
that have since moved, and still report success. The gate reports the
fallback; nothing refuses on it.

---

## 3. SLANTED WALLS AND PITCHED ROOFS — the shell only knows vertical planes

**Parked 2026-08-11B by user ruling:** *"not something I would like to
get into unless it's easy to adjust our room boundary to support slanted
walls. but I don't think it's worth rn."* It is not easy — it needs a new
shell primitive, not a parameter.

### What it is

`room_shell.py` fits vertical wall planes and one flat floor + one flat
ceiling. A room whose ceiling slopes (an attic, a loft, anything under a
pitched roof) has no representation: the fit puts the "ceiling" plane
somewhere in the middle of the slope.

### What it costs, measured

`fresh02` (a rustic attic, the first fresh scene) came out **1.64 m tall
everywhere**. That propagated: `scene_scale` saw three ceiling
observations at 0.33/0.41/0.47 of the 2.8 m prior, the evidence spread
blew past MAX_SPREAD, and the stage correctly degraded to scale 1.0 —
the scene shipped unnormalised. Machinery fine, geometry wrong.

### What to do meanwhile

Pick BOX-SHAPED rooms for test scenes and batches. The corpus page
(`marble-harvest/catalog/CORPUS_REVIEW.html`) shows every runnable
world's prompt; avoid attics, lofts, A-frames, vaulted ceilings.

## 4. SUB ROUNDS (PH2r) — deferred until a batch runs clean

**Deferred 2026-08-11B**, not rejected: user-passed on the measurements,
drawn on the map, but the code lives in `experiments/` and the base
pipeline has run end to end on exactly ONE scene. Promoting experimental
code before the base is proven across a batch adds risk to the thing
being validated. Revisit after a clean multi-scene run.

## 5. `fit_feedback`'s RE-SHOP — deliberately not built

**User ruling 2026-08-11B:** *"shopping is highly dependent on the asset
library quality which is out of scope. I just need to prove that our
pipeline is rich and functional."* The stage RUNS and writes its
rejections (5 real complaints on fresh02); nothing consumes them
automatically, and that is now a decision rather than an omission. The
verdicts sit on disk where a future deliberate re-shop can read them.

## WHAT IS *NOT* PARKED, AND IS OFTEN CONFUSED WITH THESE

Do not read this file as parking the whole vote or the whole judge
chain. Still live, still expected to work:

- the Phase-B2 loop-back (J0/J1 re-run on `voted_edges` before J8) —
  this was MISSING from the stage table until 2026-08-11 and is now in;
  it is what answers a duplicate the vote itself created
- everything in the compose chain
- the record -> judged -> resolved half, which is not yet automated

---

## HOW TO UN-PARK

Delete the item from this file in the same commit that fixes it, and say
in the REVIEW_LOG that it was un-parked and by whose ruling. An item
that is fixed but still listed here is worse than one that was never
listed, because the next reader will trust the list.

## 4. WALL-EMBEDDED OBJECTS - wall things are forced flat (parked 2026-08-12)

**Parked by user instruction 2026-08-12: "stuff on walls are flat, but we
need to enable embedded-inside-walls objects ... enable very deep objects
as long as their faces are on the face of the wall. but that is annexed
for now. just note it."**

### What it is
Objects mounted on or set into walls (niches, recessed shelves, built-in
cabinets, deep window reveals, wall-mounted units with real depth) are
currently represented as thin plates on the wall plane - the wall is a
hard boundary, so an object's box gets flattened against it rather than
allowed to extend INTO it.

### The idea, when it is picked up
Allow arbitrarily deep boxes for wall-attached objects as long as the
object's FRONT FACE lies on the wall face. The wall plane stops being a
clamp on depth and becomes the anchor for the visible face; declip and
the shell treat the behind-the-wall volume as legitimate for these
objects instead of pushing them out.

### Consequences while parked
Wall objects (pictures, TVs, ACs, panels) stay flat plates; anything
genuinely recessed reads as a surface decal. Nothing crashes; depth
information for such objects is simply not represented.
