# Session 2026-07-26F — COMPOSE+LOOP stage designed · anchor filter · map redrawn

⭐ **FINAL STATE (read this block first)**

The last pipeline stage — **STEP 3 · COMPOSE + LOOP** — was designed from
scratch this session (user-led brainstorm) and is now DRAWN in
`pipeline_map.html` as the authority. Nothing of the new stage is built
yet except S1 (the anchor set, live as a viewer filter). **Next session
starts the SEMANTIC sub-stage: S2 screening** (compose-or-skip per
anchor — the doors/windows/curtain question is its first decision).

## The stage design (all user rulings this session)

- **The stage is a LOOP over two SUB-STAGES, each a chain of modules:**
  - **3.1 SEMANTIC — WHAT:** S1 anchor set → S2 screening
    (compose-or-skip) → S3 shopping (cast list; donor = old C1–C5,
    queries use judged name + J6 appearance + graph crops)
  - **3.2 PHYSICAL — WHERE, LEGALLY:** PH1 snap-to-support (planes from
    the graph shell) → PH2 collide gate (collide.py) → PH3 box surgery
    (suspect-box work orders + shrink-donor lessons land here)
  - **JUDGE** closes the loop: add/delete/replace edits re-enter S2,
    move/nudge re-enter PH1. Manual review at every step for now.
- **SOLE INPUT: `graph["resolved"]`** — the sandbox (measured shell +
  every box) is built upstream and rides in the graph. **Envelope is OUT
  of the stage** (parked; kept on disk as the splat-truth /
  unlabeled-geometry reference — candidate add-op reality check later).
  Its historical consumers were the OLD augment path
  (suggest_spots.py / splat_probe.py), drawn as a dashed reference
  arrow; NO composition/ script ever imported it.
- **ANCHOR RULE (user): anchor = ANY object with a support edge
  (ON / IN / IN_WALL / ATTACHED) to an architecture node** — floor, wall
  or ceiling contact; back-to-back wall contact counts. Tint tier:
  floor > wall > ceiling. bedroom_marble: 44 anchors (floor 16 ·
  wall 26 · ceiling 2), 45 dependents. Dependents enter only after the
  anchor loop stands; their support will be the placed parent MESH.
  Known borderlines deliberately visible: 5 books + pillow + basket +
  desk lamp (flush-shelf wall graze), plant obj_083 (suspect deep box).
- **Old C1–C7 chain + agent package: moved aside** on the map as a
  dimmed reference column (donor code, not a stage). agent_package's
  pending rewires are moot — the new stage reads the graph directly;
  whether any package folder survives is an open S-design question.

## Built this session

1. **Viewer (:8321) scene-graph row cleanup + anchor filter**
   (`entangled_gen/viewer/index.html`):
   - Sub-row simplified to ONE line (user: "just the graph and edges").
     Removed: 5 category toggles, RESOLVED checkbox (resolved IS the
     view; `?audit=1` = pre-edit judged audit), pre-shrink toggle,
     legend paragraph, edge→resolved count arrows.
   - Then edge checkboxes removed entirely (user: "not filtering by
     edge but by object") — ALL edge types always drawn, incl.
     INTERPENETRATES.
   - **"anchor focus" checkbox (default on):** floor anchors orange
     `#ffa64d`, wall cyan `#44ddff`, ceiling violet `#c09aff`;
     dependents dimmed (box edges 10 %, sprites 12 % opacity); arch
     slabs untouched. Classification client-side from resolved edges.
2. **pipeline_map.html redrawn** (bottom section): sub-stage bands
   3.1/3.2 (shaded, new-lane width only), module nodes S1–S3 /
   PH1–PH3 / JUDGE with full contract cards, loop-back arrows, sole-
   input edge label, old compose column dimmed at x=544, envelope
   parked (no pipeline consumer; dashed historical arrow to the old
   augment path), new decision card "COMPOSE+LOOP — semantic ⇄
   physical, anchors first".

## Anchor classification data (from graph["resolved"], bedroom_marble)

- FLOOR 16: chairs ×2, plant, doors ×3, bed, baskets ×3, bookshelves
  ×2, side table, yoga mat, desk, rug
- WALL 26 / CEILING 2 (ceiling light, lamp obj_062)
- 13 objects carry BOTH arch + object support (basket-on-floor-under-
  table etc.); rule keeps them anchors
- `wall_distance_m` does NOT separate "mounted" from "flush-shelf
  graze" (book obj_038 = 0.0 like the AC unit) — no cheap numeric fix;
  the filter makes the 8 oddballs visible instead

## Next session — SEMANTIC sub-stage

1. **S2 screening design + build**: compose-or-skip per anchor. First
   decisions: doors ×3 / windows / curtain — compose assets or leave as
   architecture? Suspect-box anchors (obj_014, obj_083, obj_035/096)
   held back or shopped?
2. Then S3 shopping rework (donor C1–C5) with judged names +
   appearance; cast-list file contract to define.
3. Per production workflow: start `docs/PLAN_COMPOSE_LOOP.md` (plan +
   progress rows + REVIEW_LOG) when building starts.

## File inventory (this session)

- `entangled_gen/viewer/index.html` — sub-row rewrite ×2 + anchor focus
- `pipeline_map.html` — the whole compose section + cards + decision
  card + envelope parking
- this handoff
