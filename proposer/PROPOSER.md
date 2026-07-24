# Scene Proposer — isolated step (v0)

> Seeded from the week5 real-scan experiments; the starter pack it consumes
> lives in `../real_scan/package/` (paths below are relative to `proposer/`).
> Works equally on a generated scene's package (`entangled_gen` stage 6).

Turn *perception* of the real playroom into a **structured scene proposal** that a
Holodeck/GLTS-style composer can place. Runs in isolation: input is only the starter
pack; output is one JSON. No solver/renderer is wired in yet.

- **Task framing:** DESCRIBE THE REAL SCENE. Report the layout that actually exists in
  the splat — do not invent or redesign.
- **Downstream:** the proposal feeds the **placement step** of a Holodeck/GLTS composer.
  So emit composer-ready input, not finished coordinates for everything (see Output).

## Input (the starter pack, nothing else)
- `../real_scan/package/views/plan_ortho.webp` — top-down footprint (positions, spacing).
- `../real_scan/package/views/view_*.webp` — 8 eye-level headings (appearance, height, what's on what).
- `../real_scan/package/manifest.json` — the frame: origin = standpoint, **North=−z, East=+x,
  South=+z, West=−x, up=+y**, floor y≈−3.2, ceiling≈+2.3, extents. All coords MUST be
  in this frame. Render more views if unsure: `python ../real_scan/package/view.py <heading>`.

## Two stages
1. **Object proposal** — list every object you can identify: `category`, `anchor` flag,
   short `description`, `style`. Anchors = large, layout-defining, floor/wall-mounted
   (desk, bookshelf, wardrobe, bed…) + architectural fixtures (staircase, door, window).
2. **Anchor proposal** — for `anchor:true` only, give `size [w,h,d]`, `position [x,y,z]`
   (object center, frame coords), `yaw_deg` (0=faces North/−z, 90=faces East/+x),
   `support`, `against` (wall). Non-anchors get size + support + **constraints only**.

## Output contract
One JSON (see `example_proposal.json`):
```
{
  "scene":  { room_type, style, north:"-z", bounds:{x,z,floor_y} },
  "objects":[
    // ANCHOR: full geometry
    { id, category, anchor:true,  size:[w,h,d], position:[x,y,z], yaw_deg,
      support, against, description, confidence },
    // NON-ANCHOR: size + support + relations, NO position (composer places it)
    { id, category, anchor:false, size:[w,h,d], support,
      constraints:[ {rel, target} ], description, confidence }
  ]
}
```
Relation vocabulary (Holodeck-aligned): `on`, `against_wall`, `in_front_of`, `behind`,
`left_of`, `right_of`, `facing`, `near`, `centered_in_room`, `in_corner`, `aligned_with`.
`target` is another object `id` or a wall (`wall_N|wall_E|wall_S|wall_W`) / `room`.

> ⬜ TODO before finalizing: confirm the **exact GLTS constraint schema** from its paper
> and reconcile with the Holodeck vocabulary above (names/args may differ).

## Verification loop (isolation, no solver)
For any anchor, re-render its bbox to check size/location against the real scene:
```
python ../real_scan/shot.py 0,0,0 0,0,-3 --box=<xmin,ymin,zmin,xmax,ymax,zmax>
```
If the clip isolates exactly that object, the geometry is right; else adjust and repeat.

## Don'ts
- Don't output absolute positions for non-anchors — emit constraints; the composer solves them.
- Don't use any frame other than the centered standpoint frame.
- Don't invent objects not visible in the pack (this is describe-the-real-scene).
