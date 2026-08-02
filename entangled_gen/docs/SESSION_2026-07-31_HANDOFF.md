# Session 2026-07-30→31 — testimony chain rebuilt on evidence (v4→v6) · R1 provisionally passed

⭐ **FINAL STATE (read this block first)**

The obj_001 plant dispute (R3) was RULED (floor) and its root cause
dissected by controlled experiment, which drove three adopted revisions
of the appearance pass and one of supported_by. The full v6 chain
(describe → supported_by → consistency) is RUN and CURRENT on
bedroom_marble. **R1 = provisional PASS (user: "good for now, expecting
changes as we loop"). R2 is OPEN mid-review — the 8 KEEP / 13 DROP
sheet was presented, verdict pending.** `PLAN_COMPOSE_LOOP.md` rows
6j/6k + the extended R3 entry are the full record.

## What was established (the science)

1. **R3 ruling:** user's eyes on the context crops → plant is on the
   FLOOR. Description was wrong.
2. **Root-cause chain, each step a controlled experiment:**
   - geometry leak (item lines fed "bottom 0.19 m above floor") — real
     flaw, fixed in v4, but NOT load-bearing (still said shelf).
   - resolution — EXONERATED (solo call on the same 256px tiles → floor).
   - batch context alone — EXONERATED (one-by-one feed in ONE call,
     shared context kept → floor, 52.6s).
   - **the fused 4-col grid sheet = the culprit** (3/3 wrong across
     independent runs; user's "confused where is where" hypothesis).
3. **Fix adopted at zero cost:** ROW-SHEETS (one item per color-framed
   row, number burned into crops, dark separators) → floor ✓ at 15.0s
   vs 16.1s grid.
4. **v6 STRUCTURED TESTIMONY adopted (user):** description =
   intrinsic-only (never names other objects — misidentifying
   peripheral objects was the invention channel); support_view = LIST
   of GENERIC contacts (floor / horizontal_surface / vertical_surface /
   ceiling / **not_visible** as first-class honesty). supported_by v6
   consumes support_view; the witness reports contact geometry, the
   judge matches it to candidates. Probe 7/8 (obj_013 gave vertical
   only — watch).

## Adopted code changes

- `graph/describe_nodes.py`: PROMPT_VERSION 4→5→6 (geometry-blind →
  row-sheets → split schema + support_view validation); docstring
  updated. Judge half (Phase A) untouched — judges get geometry,
  witnesses stay blind.
- `compose/supported_by.py`: PROMPT_VERSION 6 (Witness-support-view
  lines + rewritten testimony paragraph).
- BOTH claude bridges: prompt via **STDIN** (WinError 206: v6 prompts
  crossed Windows' 32k argv cap on batch 2 — argv prompts don't scale).
- `viewer/index.html`: review-mode colors on the supported_by row
  (yellow demoted / magenta multi-option / red low-conf / tier anchors /
  gray rest); existence badges dropped from box labels + card titles
  (settled history, still in card body); ctx crops in the click card.
- `viewer/serve.py`: `/graph_crops_ctx/` route (subagent-built).
- `pipeline_map.html`: J6 v4/v5/v6 entries; S1 card v6; **OLD C1–C7
  reference column REMOVED (user: "we are over that now")** — code on
  disk, lessons in S4_SHOPPING_DESIGN_NOTES.md.

## Current bedroom_marble state (v6 chain, all current)

- appearance: 89/89 intrinsic-only + support_view.
- supported_by v6: 30 anchors / 14 demoted / 0 added / **30
  multi-option** / 0 none_plausible. Key verdicts: obj_001 rests_on
  floor **0.75** (shelf alt 0.2) · obj_083 rests_on desk 0.35 (stable,
  honest — not_visible testimony) · obj_013 collapsed to rests_on
  bookshelf-top **0.9** · **obj_002 AC DEMOTED** (rests_on bookshelf-top
  0.55 vs wall-mount 0.4 — needs user eyes).
- consistency: 77 confirmed / 26 alt / 2 transitive / 31 kept /
  **13 DROP + 8 KEEP** (R2 sheet), 0 audit flags.
- multi-option 5→30 = mostly 0.2–0.4 runner-ups inside the duplicate
  shelf nest (obj_043/080/093/140) — dedup evidence, not indecision.
  OPEN: viewer "contested" threshold (magenta only when alt within
  ~0.15 of top?).

## Tomorrow's queue (in order)

1. **R2 verdict** — the 8 KEEP / 13 DROP walkthrough is in the chat log
   and reproducible via `scratchpad r2_sheet.py`-style dump; risky
   groups flagged: per-child wall-contact consolidation (design
   choice), obj_071 basket-under-desk keep, obj_080-family keeps vs its
   duplicate suspicion.
2. Eyeballs during R1-adjacent look: **obj_002 AC** (on bookshelf vs
   wall-mount), **obj_013** (0.9 on shelf — old crude-miss example).
3. **R4 snap** — STALE (built on the pre-v6 layer); re-run
   `compose/snap.py` first, then review the LARGE-correction list.
4. **propose_edits full run** — now well fed (obj_083: conf 0.35 +
   71.6cm wall-penetration drop + suspect-box history = three
   independent doubt signals).
5. Decisions parked: multi-option magenta threshold · hybrid
   escalation re-time (first attempt hit API 529) · obj_013
   dual-contact under-report watch.

## Ops notes

- Viewer server RUNNING on :8321 (bedroom_marble) at session end —
  restart: `python viewer/serve.py --scene bedroom_marble --port 8321`.
- NOT COMMITTED — the session's changes (describe_nodes, supported_by,
  viewer, serve, map, docs) are uncommitted in scene-pipeline; commit
  next session if desired (as Timotsui / timotsuihc@gmail.com).
- appearance/supported_by/consistency caches all current on v6 hashes;
  edit_proposals.json remains STALE (pre-v5 sanity output).
