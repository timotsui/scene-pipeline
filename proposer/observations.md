# Playroom — Explore Observations (v0)

Visual log of the playroom 3DGS scene. LOOK + RECORD only; no proposal JSON.

**Frame (centered standpoint):** origin = standpoint, **North = −z**, **South = +z**,
**East = +x**, **West = −x**, **up = +y** (ceiling ≈ +2.3), floor y ≈ −3.2. Units ≈ meters.
Scene extent: x ∈ [−4.1, 2.3], y ∈ [−5.0, 2.3], z ∈ [−3.2, 2.4].

All approximate locations below are the object *centroid* in this centered frame. Wall
positions inferred from extents + ring views; treat the x/z numbers as ±0.3 m estimates and
the size guesses as coarse (the splat scene has no metric ground-truth, and the North wall
has an unscanned capture void).

---

## Object table

| object | where (wall/heading) | approx frame loc (x,y,z) | size guess (w,h,d) m | anchor? | evidence image | notes |
|--------|----------------------|--------------------------|----------------------|---------|----------------|-------|
| Staircase (wood, with turned balusters) | North wall (−z), spanning center→east | (0.3, −1.0, −3.0) | 2.6 × 2.8 × 1.2 | **YES** | view_north, view_ne, staircase_N | Treads rise W→E (low at left/west, high at right/east). Wooden treads + handrail; white-painted closed stringer/skirt below. Dominant N-wall structure. |
| Under-stair storage / closet door (white, paneled) | North wall (−z), west of stairs | (−1.1, −1.4, −3.0) | 0.85 × 2.0 × 0.1 | structural | view_north, staircase_N, understair_door | Full-height white 4-panel door with lever handle; light switch on wall beside it. Under-stair area to its right has cabinet doors. |
| Under-stair cabinet doors | North wall (−z), beneath the rising treads | (0.6, −2.3, −3.0) | 1.2 × 0.9 × 0.5 | secondary | staircase_N, understair_door | Low white built-in cabinetry filling the triangular under-stair void. |
| Tall wardrobe / built-in cabinet (white, 4-door + lower drawers) | East wall (+x) | (2.1, −1.2, −0.6) | 1.4 × 3.3 × 0.6 | **YES** | view_east, view_se, wardrobe_E, rug_E | Floor-to-near-ceiling white storage. Two upper cabinet doors, two lower doors/drawers, brushed handles. Biggest mass on the E wall. |
| Wall bookshelf (open shelves over lower cabinet) | South wall (+z), east portion / SE corner | (1.9, −1.3, 1.9) | 1.1 × 2.6 × 0.4 | **YES** | view_se, bookshelf_SE, rug_E, bookrack2_SSE | Built-in: 4–5 open upper shelves packed with books/binders/files + lower cabinet with two doors. Sits directly behind the desk's right end. |
| Desk (wood) + monitor | South wall (+z), center | (0.6, −2.0, 2.0) | 1.3 × 0.75 × 0.6 | **YES** | view_south, desk_S, bookrack2_SSE | Wooden top, dark monitor, keyboard, cable bundle below, a small chair tucked under. Faces North into the room. |
| Slanted-front kids' book display rack (white) | South wall (+z), west portion / SW corner | (−1.2, −2.4, 2.0) | 0.8 × 1.2 × 0.3 | secondary | view_sw, bookrack_SW, playkitchen_SSW, kidstable3 | Front-facing tiered picture-book rack, ~4 rows, full of children's books. |
| Curtained recess / alcove (beige curtain) | West wall (−x) | (−2.0, −1.2, 0.8) | 1.4 × 2.4 × 0.2 | structural | view_west, kidstable2, kidstable3 | Large beige curtain covering a wall recess (likely a window or storage niche). Earlier read as a "door"; resolved as a curtained recess via heading-250 shot. |
| Framed train picture (wall art) | West wall (−x), upper | (−2.0, 0.3, 0.3) | 0.5 × 0.3 × 0.05 | no | view_west, west_wall_W, west_door_WNW | Dark framed print of a steam train on the W wall. |
| Wall-mounted train/alphabet abacus toy | West wall (−x), low | (−2.0, −2.0, −0.3) | 0.4 × 0.4 × 0.1 | no | west_wall_W, west_door_WNW, nw_corner | Wooden bead/alphabet train toy on/against the wall, near the floor. |
| Ride-on toy car (red/blue) | floor, near West wall / NW | (−1.6, −2.8, −0.4) | 0.5 × 0.4 × 0.6 | no | west_door_WNW, nw_corner | Child's red ride-on push car. |
| Pram / stroller (blue seat) | floor, East side in front of wardrobe | (1.3, −2.4, −0.7) | 0.6 × 1.0 × 1.0 | no | view_east, view_ne, wardrobe_E | Blue-seat baby stroller parked against the E wall / wardrobe. |
| Yellow "peanut" beanbag | floor, North-center | (0.0, −2.9, −1.8) | 1.0 × 0.4 × 0.5 | no | view_north, view_ne, plan_ortho | Long yellow peanut-shaped beanbag on bare floor in front of stairs. |
| Red round beanbag / pouf | floor, SW on the foam mat | (−1.4, −2.9, 1.2) | 0.7 × 0.4 × 0.7 | no | view_sw, kidstable3, plan_ortho | Round red pouf sitting on the alphabet foam mat. |
| Plush lions (×2) | floor, SW corner near mat | (−1.7, −2.9, 0.9) | 0.3 × 0.3 × 0.3 each | no | view_sw, view_west, kidstable3 | Two stuffed lion toys at the SW edge of the foam mat. |
| Plush elephant/whale toy | floor, SE near wardrobe base | (1.5, −3.0, 1.0) | 0.4 × 0.3 × 0.6 | no | rug_E | Grey plush toy on floor by the striped rug / wardrobe. |
| Kids' table + small chairs | floor, West / SW corner | (−1.8, −2.7, 1.3) | 0.6 × 0.5 × 0.6 | no | view_west, view_sw | Small light-wood child table with little chairs; play-kitchen / cash-register toys on/around it. |
| Play kitchen / cash-register toys | floor, West / SW | (−1.7, −2.8, 1.4) | 0.4 × 0.4 × 0.4 | no | view_west, view_sw, playkitchen_SSW | Assorted role-play toys clustered at the kids' table. |
| Striped runner rug | floor, center→East, running N–S | (1.0, −3.2, 0.8) | 1.0 × 0.02 × 2.2 | no | view_east, rug_E, plan_ortho | Multi-color striped runner (pink/black/blue/red) on the wood floor, oriented roughly N–S along the E side. |
| Foam alphabet puzzle mat | floor, West / SW quadrant | (−1.5, −3.2, 0.8) | 1.8 × 0.02 × 1.8 | no | view_sw, kidstable3, plan_ortho | Interlocking colored foam letter tiles (spell EMOSA / KHOA) covering the SW floor; play zone. |
| Scattered floor toys (cars, wooden toys, blocks) | floor, center | (0.5, −3.1, 0.6) | — | no | rug_E, plan_ortho | Small toys strewn across the central floor / rug. |
| Wall stickers (animals, rocket, tree, balloons) | E / W / S walls | (decals on multiple walls) | — | no | view_east, view_south, west_wall_W, nw_corner | Decorative kids' wall decals: rocket on W wall, animals/balloons on E & S walls. |
| Wood plank floor | floor everywhere | (—, −3.2, —) | room-wide | no | all plan + ring views | Light wood plank flooring throughout, partly covered by the two rugs/mats. |

---

## Prose summary

**Room type / style.** A children's **playroom**, almost certainly a converted under-stair
basement / ground-floor room. Warm-lit, cream-painted walls decorated with kids' wall decals,
light wood plank floor. Style: domestic, soft, toy-filled, lots of built-in white storage.

**Wall-by-wall.**
- **North (−z):** dominated by the **wooden staircase** (treads rising west→east) with white
  under-stair paneling and an integrated **under-stair closet/cabinet**; a full-height white
  **paneled door** sits to the west of the stairs (with a light switch). The yellow peanut
  beanbag rests on the bare floor in front. This is the "entry/staircase" side.
- **East (+x):** a tall floor-to-ceiling **white wardrobe / built-in cabinet** (4 doors +
  lower drawers) — the largest single anchor. The **pram/stroller** is parked in front of it;
  the striped runner rug runs along this side.
- **South (+z):** the "work/reading" wall — a wooden **desk + monitor** in the center, a tall
  built-in **bookshelf** (open shelves over a cabinet) at the SE corner directly behind the
  desk, and a white **slanted kids' book-display rack** at the SW corner.
- **West (−x):** a large **beige curtained recess** (window/niche), a framed **train picture**
  above, a wall-mounted **alphabet/train abacus** toy low down, and the SW **kids' table +
  play-kitchen** cluster with plush lions and a ride-on car nearby.

**Floor / rug layout.** Light wood planks throughout. Two soft zones: a **striped runner rug**
running roughly N–S down the East/center side (in front of the wardrobe), and a **foam
alphabet puzzle mat** filling the SW quadrant where the main play happens (red pouf + lions on
it). The center floor near the stairs is largely open (peanut beanbag + scattered toys).

**Anchors identified (5–6 structural):**
1. **Staircase** — North wall, ≈ (0.3, −1.0, −3.0).
2. **Tall white wardrobe / built-in cabinet** — East wall, ≈ (2.1, −1.2, −0.6).
3. **Built-in bookshelf (shelves + cabinet)** — South wall / SE corner, ≈ (1.9, −1.3, 1.9).
4. **Desk + monitor** — South wall center, ≈ (0.6, −2.0, 2.0).
5. **Kids' slanted book-display rack** — South wall / SW corner, ≈ (−1.2, −2.4, 2.0) (secondary anchor).
6. Plus the **under-stair closet/cabinet** + **curtained West recess** as fixed structural features.

**Open questions / ambiguities (mostly resolved).**
- The West-wall "door" was resolved to a **curtained recess** (kidstable2, heading 250), not a
  swing door. Whether it hides a window or a storage niche is unknown.
- Exact depth of the East wardrobe vs. the room's E extent is approximate (wardrobe may be
  recessed/built-in flush).
- Kids' table + play-kitchen exact extents are partly occluded by the curtain and foam mat;
  a clean isolated framing wasn't achieved (one attempt rendered black — looked into dark
  geometry). Positions are inferred from view_west / view_sw.
- North wall has a real **unscanned capture void** (feathered streaks in plan), so N-wall
  metric estimates are softer than the others.

---

## Images rendered (under `package/views/explore/`)

Useful new renders (15):
- `staircase_N.webp` — staircase + under-stair door (N, fov 55)
- `understair_door.webp` — closer under-stair door + cabinet (from 0,0,−1, N, fov 70)
- `wardrobe_E.webp` — tall white wardrobe + stroller (E, fov 50)
- `rug_E.webp` — striped rug, wardrobe drawers, SE bookshelf, plush toy (down to SE)
- `desk_S.webp` — desk + monitor close (S, fov 50)
- `bookshelf_SE.webp` — SE built-in bookshelf (SE, fov 50)
- `bookrack2_SSE.webp` — desk right end against SE bookshelf (160°, fov 55)
- `bookrack_SW.webp` — slanted kids' book rack + curtain edge (SW, fov 50)
- `playkitchen_SSW.webp` — book rack + desk (200°, fov 50)
- `west_wall_W.webp` — West wall: train picture, abacus, ride-on car (W, fov 55)
- `west_door_WNW.webp` — West wall corner toward SW (290°, fov 55)
- `kidstable2.webp` — beige curtained recess on West wall (250°, fov 55)
- `kidstable3.webp` — SW foam mat, red pouf, lions, book rack (down to SW)
- `nw_corner.webp` — NW corner, under-stair void + W-wall door junction (NW, fov 55)
- `plan_zoom.webp` / `plan_low.webp` — top-down floor plan (≈ same as pack plan_ortho)

Non-useful: `kidstable.webp` (from −1.5,0,1.5 @230° rendered black — pointed into dark
geometry; superseded by kidstable2/kidstable3).
