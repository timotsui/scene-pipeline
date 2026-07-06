# Scene Proposer — Run Report (v0, 2026-06-23)

End-to-end test of an **isolated** perception→layout step on the playroom 3DGS scene: an
agent is given a starter pack, explores the scene on its own, and emits a structured scene
proposal that a Holodeck/GLTS-style composer can place. No composer/solver is wired in yet —
this run validates the proposer step alone.

---

## 0. Pipeline at a glance

```
                STARTER PACK                EXPLORE LOOP            OUTPUT LOOP
  centered  ->  package/ (north, ring  ->   render + log     ->    structured       ->  (next:
  3DGS PLY      views, plan, view.py)       what's where           proposal + verify       composer
                                            observations.md        proposal.json           placement)
```

Two agent loops, each driven by a markdown instruction file, sharing one fixed coordinate
frame and one render tool.

**Frame (all coords here):** origin = standpoint, **North=−z, East=+x, South=+z, West=−x,
up=+y** (ceiling), floor y≈−3.2. Units ≈ meters (non-metric splat → coords coarse, ±0.3 m).

---

## 1. Input — the starter pack (`package/`)

What the agent starts with, nothing else:

| Item | Purpose |
|---|---|
| `manifest.json` | Machine-readable frame: north, axes, extents, standpoint, all view coords |
| `GUIDE.md` | Human/agent guide to the frame + how to render more |
| `views/view_{n,ne,e,se,s,sw,w,nw}.webp` | 8-direction eye-level ring from the standpoint |
| `views/plan_ortho.webp`, `plan_fov90.webp` | Top-down floor plans (true ortho + fov-90) |
| `view.py` | One-word render tool: `python view.py north|135|plan|eye=..,look=..|out=..` |

Underneath: `shot.py` (raw renderer, GPU via `splat-transform`) on `playroom_centered.ply`
(recentered so the standpoint is the origin). `view.py` hides the frame/up-vector/clip/quoting.

---

## 2. Loop A — EXPLORE (`EXPLORE.md`)

**Instruction:** look at the scene systematically and log what's where. Only LOOK + RECORD;
no proposal yet.

**Steps the agent ran:**
1. Read `EXPLORE.md`, `GUIDE.md`, `manifest.json`, then the 10 pre-rendered pack views.
2. For each wall (N/E/S/W) and each candidate anchor, rendered a closer/zoomed framing via
   `view.py ... out=explore/NAME`, reading each `.webp` back to actually see it.
3. Read the floor layout from plan views; shot extra angles to resolve ambiguities.

**Output:**
- `observations.md` — 24-object table (object | where | approx loc | size guess | anchor? |
  evidence image | notes) + wall-by-wall prose + open questions.
- `package/views/explore/` — **17 renders** of coverage.

**Notable:** resolved the West-wall "door" as a **curtained recess** via an extra heading shot.

---

## 3. Loop B — OUTPUT / proposer (`PROPOSER.md`)

**Instruction:** turn the observations into a composer-ready `proposal.json` describing the
REAL scene (not a redesign), then self-verify anchor geometry.

**Output contract:**
- **Anchors** (`anchor:true`) → full geometry: `size [w,h,d]`, `position [x,y,z]` (center),
  `yaw_deg` (0=faces N), `support`, `against` wall.
- **Non-anchors** (`anchor:false`) → `size` + `support` + `constraints[]` only (NO position —
  the composer solves it), using a Holodeck-aligned relation vocabulary (`on`, `against_wall`,
  `in_front_of`, `left_of/right_of`, `facing`, `near`, `centered_in_room`, `in_corner`,
  `aligned_with`).

**Steps the agent ran:**
1. Read `PROPOSER.md`, `observations.md`, `manifest.json`, `example_proposal.json` (format
   ref), and the key images.
2. Wrote `proposal.json`.
3. **Verification loop** — for each main anchor, computed its bbox (center ± size/2) and ran
   `python shot.py <eye> <look> --box=<bbox>`, read the result: if the clip isolates that one
   object, geometry is good; else adjust and re-render. (An empty box returns "No Gaussians" —
   used as a hard signal that a position is wrong, not just blurry.)

**Output:**
- `proposal.json` — **24 objects: 8 anchors + 16 non-anchors** (valid, contract-compliant).
- `PROPOSAL_NOTES.md` — verification log, confidence summary, human-check list.
- `package/views/verify/` — **12 clip-box verification renders**.

---

## 4. Output we got

**Anchors (8, full geometry):** `staircase_N`, `understair_door`, `understair_cabinet`,
`wardrobe_E`, `bookshelf_SE`, `desk_S`, `bookrack_SW`, `curtain_recess_W`.

**Non-anchors (16, constraints only):** monitor, train picture, abacus toy, ride-on car,
stroller, peanut beanbag, red pouf, plush lions, plush elephant, kids table, play kitchen,
striped rug, alphabet mat, scattered floor toys, wall decals, wood floor.

**Sample entries:**
```jsonc
// anchor — full geometry
{ "id":"desk_S", "category":"desk", "anchor":true,
  "size":[1.3,0.75,0.6], "position":[0.6,-2.83,2.0], "yaw_deg":0,
  "support":"floor", "against":"wall_S", "confidence":0.6 }

// non-anchor — constraints, no position (composer places it)
{ "id":"monitor_desk", "category":"monitor", "anchor":false,
  "size":[0.5,0.4,0.1], "support":"desk_S",
  "constraints":[ {"rel":"on","target":"desk_S"}, {"rel":"facing","target":"wall_N"} ],
  "confidence":0.55 }
```

**Anchor verification (5 box-checked):**

| anchor | verdict | tweak |
|---|---|---|
| `staircase_N` | GOOD | raised ymax + deepened to catch treads; depth 1.2→1.4, z −2.6→−2.5 |
| `bookrack_SW` | GOOD | none (confirmed WEST/SW) |
| `desk_S` | GOOD | none (desk+monitor+chair isolated) |
| `bookshelf_SE` | GOOD (lower cabinet) | none; upper shelves reconstruct poorly, height inferred |
| `wardrobe_E` | PARTIAL | stroller parked flush in front occludes it |

**Errors the loop caught:** a screen left/right handedness mix-up (book rack first read as
EAST) was corrected to WEST/SW by the frame-true clip boxes; the staircase box was retweaked
after the first attempt only caught floor glow.

---

## 5. Limitations / open items (for a human)

1. **Wardrobe vs. stroller** depth separation on the East wall (occlusion).
2. **Bookshelf upper-shelf height** — only the lower cabinet box-verified.
3. **Curtain recess (West)** — window vs. storage niche unknown.
4. **North-wall metric softness** — real unscanned capture void → softer staircase coords.
5. **GLTS constraint schema** — reconcile the Holodeck vocabulary used here with GLTS's exact
   schema; the agent used `above` (wall-art-over-toy), which is outside the listed vocabulary.
6. **Non-metric scene** — all sizes ±~0.3 m; calibrate if the composer needs true metric sizes.

---

## 6. Reproduce

```
cd CS-8903-OVM/week5/splat_to_placement
# Loop A: explore  -> observations.md + views/explore/   (follow proposer/EXPLORE.md)
# Loop B: output   -> proposal.json + views/verify/      (follow proposer/PROPOSER.md)
# render any view:  python package/view.py north
# verify a bbox:    python shot.py 0,0,0 0,0,-3 --box=xmin,ymin,zmin,xmax,ymax,zmax
```

## Files
```
proposer/
  EXPLORE.md            instructions — explore loop
  PROPOSER.md           instructions — output loop (+ contract, relation vocab, verify loop)
  observations.md       OUTPUT of loop A (24-object table)
  proposal.json         OUTPUT of loop B (24 objects: 8 anchors + 16 non-anchors)
  PROPOSAL_NOTES.md     OUTPUT of loop B (verification + caveats)
  example_proposal.json v0 hand sketch (format reference)
  RESULTS.md            this report
package/views/explore/  17 exploration renders
package/views/verify/   12 anchor clip-box verification renders
```
