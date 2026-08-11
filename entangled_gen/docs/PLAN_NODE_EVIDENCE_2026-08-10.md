# PLAN — THE EVIDENCE EDIT (`recrop_gate` promoted to a graph module)

Session 2026-08-10 (real date). Supersedes the "judge-packaging step"
open item carried since R-S2-57. All four design questions are RULED by
the user; this doc records the rulings and the build order.

## THE PROBLEM, IN ONE LINE

We built a gate that names every node showing the wrong photo, and a
renderer that takes correctly aimed pictures — and wired neither to
anything. `recrop_gate` and `node_views` are both write-only. Meanwhile
J9 (and six other readers) still pick 2 detector crops per member by
detection score, which is exactly the evidence the gate flags as
untrustworthy.

## THE THESIS (user, this session)

> "each module enriches and edits the scenegraph to a better state. the
> graph coming out of this gate module will supersede and be the
> singular best representation of the scene graph"

So this is NOT a serve-time helper that judges call. It is a LAYER EDIT.
It inherits the whole graph, repairs one thing — what each node is seen
as — and hands on a layer that is the best available representation.
Downstream judges stop reaching into `graph/crops` and just read the
node. One edit; everyone inherits it.

## USER RULINGS

1. **Supersede, per condition.** "mostly no is a no."

   | condition | old crop shows | ruling |
   |---|---|---|
   | BORROWED (split piece) | the PARENT, not this piece | superseded |
   | NOT_IN_PHOTO (2b) | box off the edge — something else | superseded |
   | ESCAPED | part of the box, rest cut off | superseded |
   | RE-ZOOMED | right object, wrong scale | **KEEPS its crop** |

   Rationale: in three of four cases the stored crop is a picture of the
   wrong thing. Showing it beside the repair is noise with a caption.

2. **ESCAPED is repaired by RE-CUT, not by a render.** The photo still
   contains the box by definition, so a rectangle around the projected
   box shows the object. Real photographic pixels; no GPU.
   **With generous margins** (user: "it helps to provide some
   surroundings for image recognition") — reuse the EXISTING context-pad
   family from `describe_nodes.py:184`, do NOT invent a constant:
   `CTX_PAD_SIDE 0.35 / CTX_PAD_TOP 0.35 / CTX_PAD_BOTTOM 0.75 /
   CTX_MIN_PAD 40px`. The asymmetric bottom is deliberate — it shows
   what the object sits on.
   BORROWED and NOT_IN_PHOTO have no choice: those must be renders.

3. **Chain position** — the new layer sits between `settled` and
   `grouped`:
   `record → judged → resolved → voted → settled → [shown] → grouped`
   It edits `settled` (boxes final after J8 ship rulings, J8s cuts, J1
   merges) and J9 reads its output.
   **This unties a circularity**: `recrop_gate`'s docstring today
   projects the box from layer `grouped`, which is J9's own OUTPUT. If
   J9 consumes this module, that cannot stand.

4. **Name** — `graph/node_evidence.py`, layer `shown`. It answers "what
   is each node seen as", which is what every downstream judge is
   actually asking. Names the graph effect, not the mechanism.

5. **Render go** — DECIDE AND QUEUE. The module writes the repair plan
   and the counts; the user approves the batch; only then does it
   render. Standing rule (verification-workflow #9): never render before
   the user says go — earned twice, two batches stopped mid-flight.
   `--render` stays available for after the approval.

## WHAT DOES NOT MOVE ON DISK

Supersede means **in what the judge sees, not in the folder.**

- `graph/crops/` stays. A crop is the DETECTION RECORD —
  `evidence.members[*].crop` points at it; deleting breaks the record
  layer.
- Nothing is written INTO `graph/crops/`. `build_graph.cut_crops` wipes
  and rebuilds that folder every run (R-S2-67 ownership rule), so
  anything we left there would die silently on the next run — the exact
  stale-crop failure just closed.
- Repairs live in their own stage-owned folders. Same ownership rule
  applies to them: wipe and rebuild, never top up.

## HONEST LIMITS, ON RECORD

- **A re-cut does not fix viewpoint or occlusion.** Same camera as
  before. An object seen edge-on or half behind the sofa gets a
  correctly framed, still-poor look.
- **A re-cut does not fix resolution.** Zoom is capped by the original
  panorama pixels; a box that is now small in that photo yields a small,
  soft picture. A render is 768x768 aimed close.
- **Both repairs inherit box error equally.** A re-cut's rectangle comes
  from the projected CURRENT box, not from the detector — so a wrong box
  frames the wrong volume, exactly as a render does. (An earlier claim
  in conversation that re-cut was immune to this was WRONG and is
  corrected here.) Box error is J8's problem, not J9's.
- **The stimulus must say which it is** — "aimed render" vs
  "photograph" vs "re-cut" — as a LABEL, not as a second picture.

## BUILD ORDER

- [ ] **B1 — `node_evidence.py`, decide only.** Promote `recrop_gate`:
      same three conditions + 2b, now reading `settled`, emitting a
      repair plan per node (kind: recut / reshoot / keep) and the counts.
      No pixels written. Review: the plan and the per-node reasons.
- [ ] **B2 — the re-cut repair.** Project the current box into the
      source view, pad with the CTX family, cut, write to a stage-owned
      folder. No GPU. Review: the re-cut pictures.
- [ ] **B3 — the reshoot repair.** Call `node_views`' camera math for
      BORROWED / NOT_IN_PHOTO. Queue the batch; WAIT FOR GO; render.
- [ ] **B4 — write the `shown` layer.** Each node carries its evidence
      set + provenance label. `scene_state` CHAIN updated. Additive
      checks pass.
- [ ] **B5 — wire the readers.** J9 first (it is the one blocking the
      scene), then the other six: J1, J3, J4/J6, J5, J6, compose/pick.
- [ ] **B6 — pipeline map + PIPELINE.md.** The map is the authority; it
      must show the new layer before any run leans on it.

## KNOWN CONSEQUENCE, FLAGGED BEFORE STARTING

Re-packaging J9 means **re-judging the affected pools on the new
stimulus** — including the chair split (obj_021+obj_028 vs
obj_041+obj_068) the scene is currently gated on. The existing verdicts
were made on the crops, 9 of which were the stale ones from R-S2-67.
New stimulus, new verdict. The CP1 ruling may be worth deferring until
J9 has re-run on repaired evidence.

## STANDING RULES IN FORCE

- Plan first; no edits before the user's go.
- User judges all visuals; Claude never concludes from images.
- Pipeline map is the authority; deviations need explicit approval.
- Constants are statements of meaning, never fitted to the test scene.
- A stage owns its output folder: rebuilding replaces, never tops up.
- "vote", never "carve" (old DATA files still say carve — translate).
- Commit checkpoint owed (~5 sessions uncommitted).

## PROGRESS LOG

- (start) Plan written from the design conversation. Awaiting build go.
