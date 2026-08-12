# SESSION 2026-08-17 HANDOFF — THE PIPELINE IS A CHAIN OF WHOLE LAYERS NOW; NEXT IS THE J9 GATE

(Real date 2026-08-09. Evidence: REVIEW_LOG R-S2-46..53.
Commits 03f74df..3c2a078, all pushed — the remote matches local.)

## START HERE NEXT SESSION

**One thing needs YOU before anything downstream moves: the J9 gate.**

J9 split two pools on claimed LOOK differences, and only you can say
whether they are real in the crops:

- **ceiling lights, 7 in the room -> 2 sets.** set_1 {obj_008, obj_018}
  "warm gold/bronze metallic trim ring, thicker"; set_2 {obj_023,
  obj_027, obj_030, obj_031, obj_045} "thin dark/gray trim". J6's own
  earlier description never mentioned gold on obj_008 — it said "white
  oval ceiling light". One of the two readings is wrong.
- **chairs -> 2 sets.** set_1 {obj_021, obj_028} "uniformly black/glossy
  upholstered"; set_2 {obj_041, obj_068} "curved tan/brown wood-grain
  shell". obj_010 alone ("a flat, glossy black rectangular panel" — not
  a chair).

If those splits are NOT real, the sets merge and everything J9 feeds
changes. **J9's product groups feed shopping directly, so this gates the
whole compose stage** — the graph itself is ready (below).

Look at: `out/living_marble/graph/same_product_sheets/index.html`
(each verdict sits above its contact sheet and its box view) and the
viewer on localhost:8321.

## THE STATE OF THE PIPELINE

    record -> judged -> resolved -> voted -> settled -> grouped
     71/175   51/110    46/92      46/82    45/77     45/77   (nodes/edges)

Every layer is a WHOLE graph — nodes AND edges, plus everything the layer
before it carried — named for what its stage did. **0 dangling edges,
0 edgeless nodes, 0 conflicts.** `graph/scene_state.py` declares the
chain once; every reader asks it for the current layer instead of naming
one, and the writing stage stamps `graph["layer"]["canonical"]` so the
file states the answer too. Full contracts: PIPELINE.md "THE LAYER
CHAIN".

Run the chain with:

    python graph/build_voted.py        --scene living_marble --apply
    python graph/materialize_layers.py --scene living_marble --settle-only --apply
    python graph/judge_same_product.py --scene living_marble
    python graph/materialize_layers.py --scene living_marble --apply

## WHAT LANDED

1. **J9 rebuilt from the plumbing up.** It was the only judge with no
   verdict cache, the only one on haiku, the only one that would answer
   a question about what things LOOK like over a sheet with no photo on
   it, and the only one where a malformed reply killed the group. All
   four aligned with J8/J8s.
2. **Grouping is semantic now, not spatial.** The old 2.5 m proximity
   rule split the room's 7 ceiling lights into a 4 and a 3 because the
   nearest cross-patch pair is 2.74 m — and silently dropped bookshelf
   x3, door x2, sofa x2 and plant x2 off the docket entirely, since no
   two of them were within 2.5 m. One pool per KIND now, whole scene.
3. **The judge assigns EVERY member** to a set or to `alone`, each with
   its own reason; more than one set per pool allowed. An incomplete
   reply is a failed attempt (one retry naming the missing ids, then
   `unassigned` is recorded, never invented).
4. **The canonical size is an EXEMPLAR, computed by code.** The judge's
   size was, in all four groups, exactly the per-axis median — and that
   is the wrong arithmetic, because boxes are aligned to the ROOM and
   these objects face different ways. Now: rank the set members
   (measured before never-measured, then fewest doubts, then closest to
   the set's median height) and copy the winner's box verbatim. The
   spread is recorded so shopping can tell the chairs (0.44 m of
   disagreement) from the lights (0.02 m).
5. **⭐ Every stage now EDITS the graph** (user design rule). Before
   this, six modules ran after `resolved` and not one handed on a graph —
   each read the frozen layer and dropped a verdict file beside it. 43
   of 46 boxes disagreed with the elected one and nothing was MARKED
   superseded, so nothing could detect it was reading old data.
6. **carve -> vote.** 799 occurrences, 25 files, zero `carve` left in any
   .py. The stage never carved anything; it elects boxes.
7. **Rotation in the compose jiggle** (user idea, same day): a bounded
   yaw is preferred whenever it clears a clip with ZERO translation.
   Measured on bedroom_marble: residual clips 3 -> 2 from a single -5°
   yaw. Scene restored afterwards.

## THE FINDINGS WORTH CARRYING

- **A stated retry budget changes how much a model attempts** (from the
  splitter, still true) — and the same shape appeared again: the ANSWER
  FORM shapes the answer. Asking for a subset with no account of what is
  left out produces an arbitrary subset.
- **Re-derivation cannot regenerate what a judge CREATED.** J0 nominates
  pairs below the geometric SAME_CANDIDATE gate; the chair duplicate
  obj_068/obj_020 rides on exactly such an edge (iou 0.387 vs a 0.40
  gate) and carries J1's SAME verdict. Test is provenance
  (`nominated_by`), never a type list.
- **A doubt-free node is eligible to be a size exemplar.** A split piece
  born without its parent's doubts could have supplied the size to buy
  on information it never had.
- **Hand-written labels went stale five times this week.** Run numbers,
  status tallies, layer names. Read them from the data, never type them.
- **A report must not be able to stop a stage from writing its result** —
  and a piped `grep` hides the crash from `set -e`. Use `pipefail`.

## OPEN, IN THE ORDER I'D TAKE THEM

1. **The J9 gate** (above). Gates compose.
2. **The pillow pool.** 7 of 8 pools reproduced EXACTLY on a fresh ask
   with changed prompt wording; only the pillows moved
   ({013,015,016,026}+{037,048} -> {013,015,016}+{024,026}+{037,046,048},
   obj_019 alone). The instability is confined to that one pool of nine
   near-identical noisy objects — not general to the form.
3. **Declip rotation oscillation.** 3 rotation events produced 1 net yaw;
   two cancelled out. Fix before it goes near canon. Also runtime 21s ->
   89s, all voxelisation.
4. **`label` / `labels` / `evidence` / `nesting` still live only on the
   record.** Nothing in compose asks a node for them; `evidence` is the
   bulky one and is reachable through `members`.
5. **`compose/support_clip.py` rewrites `resolved` geometry in place** —
   the pattern this week removed. Retirement candidate.
6. **obj_005_c00 / obj_017_c00** — pano-cluster nodes with no crops and
   no appearance. They are why J9 has a no-stimulus path at all.
7. **9 stale PNGs** in `same_product_sheets/` from the old J9 form,
   unreferenced; the old numbering overlaps the new, so opening one
   directly misleads. Offered to delete, not done — copies are in
   `graph/_approved_2026-08-08_subset_form/`.

## BACKUPS ON DISK (all deliberate)

- `living_marble/scene_graph_pre_vote_rename.json.bak` — pre-rename graph
- `living_marble/graph/_approved_2026-08-08_subset_form/` — the J9
  verdicts the user passed, in the old subset form
- `bedroom_marble/compose/_declip_baseline/` — the preview as found
- `bedroom_marble/compose/_declip_rotation_trial/` — the rotation trial

## GOTCHAS

Renders are gated on a params sidecar — never hand-wipe pngs. Judge call
failures are attempts, not crashes. A judge's prompt change invalidates
its cache BY DESIGN (the carve->vote rename did exactly that, and the
free re-ask became the stability measurement above). Viewer restarts: WMI
+ absolute python path. `fit_declip.py` applies IN PLACE to
fitted_preview.glb — back it up before any test run. living_marble has NO
live compose preview (only an archived pre-normalization one);
bedroom_marble is the live compose scene.
