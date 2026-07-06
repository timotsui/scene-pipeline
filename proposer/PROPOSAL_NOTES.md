# Proposal Notes — playroom scene proposer (v0)

Companion to `proposal.json`. Records the anchor verification (clip-box loop), confidence
summary, and what a human should double-check.

## Object count
- **24 objects total**, matching the explore observations table.
- **8 anchors** (`anchor:true`, full geometry): `staircase_N`, `understair_door`,
  `understair_cabinet`, `wardrobe_E`, `bookshelf_SE`, `desk_S`, `bookrack_SW`,
  `curtain_recess_W`.
- **16 non-anchors** (size + support + constraints, no position): monitor, train picture,
  abacus toy, ride-on car, stroller, peanut beanbag, red pouf, plush lions, plush elephant,
  kids table, play kitchen, striped rug, alphabet mat, scattered floor toys, wall decals,
  wood floor.

> Note on anchor count: PROPOSER.md treats the staircase + under-stair door/cabinet as one
> architectural assembly. I split them into 3 anchors (`staircase_N`, `understair_door`,
> `understair_cabinet`) so the composer can place the door/cabinet as discrete features, but
> they share the same North-wall footprint and verify together as one mass (see below).

## Anchors verified with the clip loop (`shot.py --box`)
Renders saved under `package/views/verify/`. The clip loop also produced a hard signal that
the renderer reports **"No Gaussians to write"** for an empty box — empty results were used to
rule out wrong positions, not just blurry ones.

| anchor | verdict | box used (xmin,ymin,zmin,xmax,ymax,zmax) | render | tweak made |
|--------|---------|------------------------------------------|--------|------------|
| `staircase_N` (+ door + understair cabinet) | **GOOD** | `-1.0,-2.6,-3.2, 1.6,0.0,-1.8` | `staircase_box2.webp` | first box (`...,-3.2,...,-0.4,-2.0`) sat too low/shallow — caught floor glow + only paneling. Raised ymax to 0.0 and extended depth to z=-1.8 to catch the rising treads + balusters. Bumped proposal staircase depth 1.2->1.4, center z -2.6->-2.5. |
| `bookrack_SW` | **GOOD** | west half `-2.2,-3.2,1.4, 0.0,-0.4,2.45` | `west_south_box.webp` | none. Colorful slanted kids' book rack ("Tractor" book, colored spines) + alphabet mat below cleanly isolated on the WEST/SW side at x~-1.2. Confirms observations. |
| `desk_S` | **GOOD** | center strip `-0.4,-3.2,1.2, 0.9,-0.4,2.45` | `centerstrip.webp` | none to position. Desk wooden top + monitor/stand legs + chair clearly present at x~0.3-0.6, z~2.0. NOTE: the desk only renders when ymax is high (>=-0.4); featureless wood smears upward toward eye level, so tight low boxes returned empty. |
| `bookshelf_SE` | **GOOD (lower cabinet)** | `1.0,-3.2,1.2, 2.45,-0.4,2.45` | `bookshelf_box.webp` | none. White two-door lower cabinet with brushed handles clean at SE corner (x~1.7-2.2, z~2.0). The OPEN UPPER SHELVES reconstruct poorly (dark/featureless) so only the cabinet base is sharp; the tall shelf above is confirmed only from the ring view (`bookshelf_SE.webp`). |
| `wardrobe_E` | **PARTIAL** | `1.9,-1.6,-1.4, 2.31,0.6,0.2` | `wardrobe_box5.webp` | none. The blue stroller is parked flush in front of the wardrobe and occludes it from every room-center viewpoint; the wardrobe's flat white doors reconstruct as faint white wisps at x~2.0-2.31. Position is consistent with `wardrobe_E.webp` ring view + observations, but the box could not cleanly isolate it from the stroller. |

Five anchors verified (spec asked for 4-5). The remaining anchors not box-verified
(`understair_door`, `understair_cabinet`, `curtain_recess_W`) are lower-risk: the first two are
inside the verified staircase mass, and the curtain recess is a thin wall feature confirmed in
`kidstable2.webp` from the explore pass.

## Confidence summary
- **High (0.6):** desk, staircase, peanut beanbag — clearly seen, box-confirmed or unambiguous.
- **Medium (0.5-0.55):** wardrobe, bookshelf, bookrack, under-stair door, monitor, stroller,
  ride-on car, train picture, alphabet mat, floor.
- **Lower (0.4-0.45):** under-stair cabinet, curtain recess, plush elephant, play kitchen,
  scattered toys, wall decals — partly occluded, thin, or fuzzy in the splat.

## Sizes / handedness caveats
- This is a non-metric 3DGS scene; all sizes are coarse (+/- ~0.3 m). Heights for floor-standing
  anchors were set so `center_y = floor_y(-3.2) + height/2`.
- A screen left/right (handedness) ambiguity in the look-south views initially made it look like
  the colorful book rack was on the EAST. The clip BOXES (which are frame-true regardless of
  screen orientation) resolved it: colorful rack is WEST/SW, white cabinet is the bookshelf_SE
  lower cabinet on the EAST. Final proposal matches the observations layout.

## What a human should double-check
1. **Wardrobe vs. stroller separation on the East wall** — confirm the wardrobe's true depth and
   that the stroller is in front of it (not the wardrobe being shallower than 0.6 m). Best done by
   physically inspecting or a viewpoint above the stroller.
2. **Bookshelf_SE upper shelves height** — only the lower cabinet box-verified; the full 2.6 m
   height is inferred from the ring view. Confirm it reaches near ceiling.
3. **Curtain recess (West wall)** — still unknown whether it hides a window or a storage niche;
   treated as a flush wall feature.
4. **North-wall metric softness** — the North wall has an unscanned capture void, so staircase
   x/z and the under-stair door/cabinet split are softer than the other walls.
5. **GLTS constraint schema** — PROPOSER.md flags an open TODO to reconcile the Holodeck relation
   vocabulary used here (`on`, `against_wall`, `in_front_of`, `near`, etc., plus `above` used for
   wall-art-over-toy) with the exact GLTS composer schema; `above` is not in the listed vocabulary
   and may need remapping.
