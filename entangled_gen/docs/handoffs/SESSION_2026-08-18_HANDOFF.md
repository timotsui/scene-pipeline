# SESSION 2026-08-18 HANDOFF — THE CROPS AND THE BOXES HAVE DRIFTED APART

(Real date 2026-08-09. Evidence: REVIEW_LOG R-S2-54..56.
Nothing in the pipeline's state was changed this session. One new module,
`graph/recrop_gate.py`, which decides and writes no pipeline output.)

## START HERE — TWO THINGS, AND THE FIRST IS ONE SENTENCE FROM YOU

**1. You looked at the rendered tiles and said "woah. why? why does it
look like that." Then the session ended. I have not seen the tiles and
will not guess what you saw.** Everything about render-vs-crop hangs on
what surprised you, so say that first.

    D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\living_marble\graph\render_tiles\index.html

8 rows. Per row: the stored crop, three renders at 0/120/240 degrees
using only that node's own gaussians, and one render with 0.9 m of
surroundings. Rows chosen to span the range — obj_041 / obj_000 /
obj_033 are controls whose crops are still good, then obj_023, obj_018
(the bad box), obj_042 (3.4 m), obj_011#1 (the split piece rendered
alone for the first time), obj_001 (the 4 cm sliver).

Two limits that may be what you noticed, stated so you can rule them
out: the renders draw ONLY gaussians strictly inside the box, so
anything the box clips is simply missing (obj_011#1 will show a cut
edge where the sofa continues); and a small region gets soft —
obj_023 has only 872 gaussians to work with.

**2. THE J9 GATE IS STILL OPEN.** It was the top item last session and
was never touched this one. It still gates compose. Unchanged:

    D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\living_marble\graph\same_product_sheets\index.html

Are the ceiling-light trim split and the chair split real in the crops?
NOTE: the on-disk chair reason is about BACKREST SHAPE, not the
wood-grain claim the older handoff quoted.

## WHAT THIS SESSION ESTABLISHED

**A split gives you a shape with no identity.** The piece owns its box,
its edges and the cut's doubts. Its photos, description, name, evidence
and vote record are all the parent's — labelled as borrowed, and
nothing reads the label. Edges are the part that works: re-derived from
the piece's own box, with obj_006 even changing edge TYPE.

**The crops are badly out of date.** They were cut from the detector's
rectangles; the boxes have moved since. **8 of 45 nodes have a crop
that still frames their box. 37 do not.** Among the 44 crops whose
photo fully contains the box, the median shows 67% of it.

**Rendering is cheap.** 1.8M gaussians, load 140 ms once, median 421 ms
per tile, **35 s for the whole room**. Resolution is nearly free. So
cost is not a reason to prefer cropping, and I had been leaning on it.

**The projection is verified** against 231 recorded detections, clean
cases 0.89-0.93. The frame chain, which took two wrong attempts:

    p_photo = (p_graph - eye_raw) * pano_to_raw_signs

then project with the view sidecar's own camera. `eye_raw` is
`[0, -0.749284, 0]` from `rig_sp0/pano_selfrender_meta.json` — the
sidecar's `cam=0,0,0` is photo-LOCAL, and the graph frame is an
improper mirror of the photo frame, so the POINT moves rather than the
camera.

## YOUR RULINGS THIS SESSION

- A re-crop is a **targeted repair, not a blanket pass**.
- Three conditions: box changed enough that framing differs; and your
  own third — a big change in SIZE, so the description is at the right
  zoom, either direction.
- **obj_001 is a separate mode**, to be handled on its own.
- You found **obj_018**: geometry says 1.21 m wide, J9 says the product
  is 0.18 m and that width is a truncation artifact. Both sit in the
  graph, because J9 annotates and never resizes.

## OPEN, IN THE ORDER I'D TAKE THEM

1. **What you saw in the render tiles.** Blocks everything below it.
2. **The J9 gate.** Blocks compose. Untouched for two sessions.
3. **The fourth re-crop condition — designed, NOT built:** never
   re-crop from a box a later judge has disbelieved (obj_018). It is
   provenance, not a number, and is already recorded — the exemplar
   came from a different member.
4. **Multiple tiles per object — never considered.** obj_042 is 3.4 m
   seen from 1.6 m away; no single tile holds it. A real gap.
5. **The one split fix I'd make:** when one node becomes several, stop
   copying the parent's judge rulings onto all of them; record them as
   unassignable. edge_carry keeps three such buckets already; this is a
   fourth case and the only one currently guessed at. Latent, not live
   — living_marble's only split kept one piece.
6. **The deeper split gap, your call, not a code bug:** a piece has no
   photo and no description of its own. Closing it means describing
   each new piece. Bug 3 in R-S2-54 goes away if it is closed.
7. Carried, untouched this session: **declip rotation oscillation**
   (3 rotation events, 1 net yaw; runtime 21s -> 89s) and
   **compose/support_clip.py**, which still rewrites `resolved`
   geometry in place — a retirement candidate.
8. Carried: `label` / `labels` / `evidence` / `nesting` live only on
   the record; obj_005_c00 / obj_017_c00 have no crops and no
   appearance.

## WHAT IS ON DISK

New, committed, decides only — no `--apply`:

    scene-pipeline\entangled_gen\graph\recrop_gate.py

Reports (all read-only artifacts, safe to delete and regenerate):

    out\living_marble\graph\recrop_gate\index.html      37 firing nodes
    out\living_marble\graph\render_tiles\index.html     8 rows, renders
    out\living_marble\graph\reshoot_compare\index.html  crop vs re-crop

Scratchpad scripts that made them (NOT in the repo — move them in if
any of this is adopted):

    ...\scratchpad\verify_proj.py      the 231-detection frame check
    ...\scratchpad\time_render.py      the cost measurement
    ...\scratchpad\render_tiles.py     builds render_tiles
    ...\scratchpad\reshoot_compare.py  builds reshoot_compare

Regenerate the gate with:

    python graph/recrop_gate.py --scene living_marble

## GOTCHAS EARNED THIS SESSION

- **`recrop_gate.py` has no `--apply` on purpose.** Stored crops are
  named `<node>_m<detection>.png` because each one IS a detection. A
  re-crop is not a detection, so writing one over that file erases what
  the detector actually saw. Naming it is a design question.
- **Its two constants are statements of meaning, not measurements.**
  INSIDE_FRAC 0.95, ZOOM_FACTOR 1.5. They were NOT picked by looking at
  what this scene produces — doing that is how a test scene stops being
  a test.
- **Judge a node on its BEST crop, not its worst.** Firing on any bad
  crop made the gate disagree with what the user could plainly see.
- **Separate "outside the crop" from "outside the photo".** Only the
  first is a re-crop's job; the second needs a different view.
- **Do not select example rows by score and then describe them as
  typical.** My first sheet was the top three by overlap, and a ruling
  got made on it.
- The viewer is running from this session on **localhost:8321**
  (living_marble). Restart via WMI + absolute python path.
