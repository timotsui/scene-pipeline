# REVIEW LOG — overnight run 2026-07-21 → 07-22

**For the user's morning pass.** Every review artifact produced overnight gets
an entry here, newest at the bottom. Overnight, Claude's PROVISIONAL verdicts
(user-authorized proxy, 2026-07-21: "use your best judgment if you can and
then assume its right to move on") unblock the pipeline — they are NOT real
verdicts. Tomorrow the user walks this list top to bottom and fills in every
`USER VERDICT:` line; a user reversal invalidates everything downstream of
that entry (the plan doc's progress log maps dependencies).

Claude's known limitation applies to every provisional verdict below: Claude
cannot reliably judge spatial/image quality (see verification-workflow memory
— it has been wrong before). Confidence tags are honest, not reassuring.

Format per entry:
- **What / path** — the artifact
- **Why** — what decision it gates
- **Look for** — the visual pass/fail criteria
- **PROVISIONAL (Claude)** — verdict + confidence + one-line reasoning
- **USER VERDICT:** _(blank — fill tomorrow)_

---

## R1 — Checkpoint 5 pass 3: SAM2-propagated lamp masks
- **What / path:** `D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\bedroom_marble\cut\dataset\mask_review.html` (third-pass section; per view: original | pass-2 [rejected] | pass-3 | raw mask)
- **Why:** these masks feed the lamp graph cut (Step 10). Per the "go" decision the real gate is Checkpoint 6, so this is a sanity glance, not pixel review.
- **Look for:** masks cover the lamp per view without gross window/table grabs; propagation should make them *consistent* across views (same lamp parts in each).
- **PROVISIONAL (Claude): PASS — medium confidence.** I directly viewed 4 of 8
  overlays (init cut_d_lamp + the three views the user rejected in passes 1-2:
  cut_c_lamp, cut_c_right, cut_b_left). In all four: magenta covers the whole
  desk lamp (shade + articulated arm + base) with no visible window, curtain,
  or table painting. Numbers agree (all 8 views 100% inside the box
  projection; areas shrank 2-8x vs pass 2's bloat). Caveats: I did not view
  the other 4 overlays; possible subtle spill at the lamp base onto a small
  adjacent desk item in cut_d_lamp (uncertain at my resolution); my spatial
  judgment is documented-unreliable. Proceeding to the lamp cut on these
  masks — Checkpoint 6 renders are the deciding gate anyway.
- **USER VERDICT:**

## R2 — splat_analyzer orientation sanity (Step 5 phase 1, --quality low)
- **What / path:** frames in `D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\bedroom_marble\analyzer\job_low\frames\` (recommend frame_0018.png = ceiling-ward, upright check; frame_0004/0013 = dark blurs, see below). Detections: `job_low\interactions.json` (11 objects).
- **Why:** gate for running the full-quality analyzer pass; the tool's failure mode is a SILENT upside-down/mirrored render.
- **Look for:** frames upright (ceiling up, floor down), room not mirror-flipped vs what you know from the viewer.
- **PROVISIONAL (Claude): PASS — high-ish confidence.** frame_0018 clearly upright (ceiling top, two doors + AC unit below). Stronger: numeric agreement — analyzer's lamp at RAW (−0.15, −1.46, 3.94) vs manifest obj_004 (−0.12, −1.02, 4.07); a mirror flip would negate an axis. Run took 16 s, 4.3 GB VRAM. Quality notes (not orientation): 2 of 3 low-preset standpoints landed inside geometry (dark-blur frames); all 11 detections came from the single good standpoint. Full run uses a higher preset with more standpoints.
- **USER VERDICT:**

## R3 — Checkpoint 4: detection comparison (splat_analyzer vs our manifest)
- **What / paths:** comparison page `D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\bedroom_marble\analyzer\comparison.html` + the 3D view: `D:\T\Documents\GeorgiaTech\Summer2026\scene-pipeline\launch_viewer.bat` → localhost:8321 → tick the new cyan **"analyzer boxes"** checkbox (103 boxes, labels on sprites) next to the manifest boxes layer. Raw data: `analyzer\bridged_boxes.json`, `match_report.json`.
- **Why:** THE Checkpoint 4 decision, reserved for you (no overnight action taken): (a) analyzer's fate — replace our detection+lift stages / borrow its camera-ring+clustering / cross-check only; (b) which box set seeds the batch masks in Step 12.
- **Look for:** in the viewer — do cyan boxes hug real objects better than our manifest boxes? Are the 67 analyzer-only clusters real objects we missed (books, paintings, baskets…), duplicates, or hallucinations — spot-check the 8 book and 7-8 painting/bookshelf clusters. Do the 7 door boxes land on the 4 real doors (over-split?)? Caveat while judging: analyzer boxes have fabricated depth (z-extent = (w+h)/2), front-surface-biased centers, axis-aligned only.
- **PROVISIONAL (Claude — analysis only, decision untouched): analyzer looks strong numerically.** 19/19 manifest objects matched (min 0.045 m, median 0.258 m, max 0.594 m); lamp obj_004 ↔ ana_101 at 0.109 m; multi-standpoint fusion 91/103 vs our documented single merge; 64 s runtime. Unknowns only your eyes settle: quality of the 67 extra clusters, cap-8 saturation on 5 labels (real multiplicity vs over-clustering), zero detections for office chair/yoga mat/potted planter (real misses — the chair and mat ARE in the room). Watch item logged: observed min cluster votes = 3 vs the reported default min_votes 8 — semantics discrepancy, unresolved, doesn't affect the visual judgment.
- **USER VERDICT (adoption):**
- **USER VERDICT (batch mask seeding):**

## R4 — Checkpoint 6: lamp cut quality, attempt 1
- **What / path:** `D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\bedroom_marble\cut\obj_004\cut_review.html` (before/after crops on 8 lamp views, 15 full-frame pairs, 3 lamp-only renders, stats). Viewer: launch_viewer.bat → :8321 → "cut background" / "lamp only (cut fg)" checkboxes.
- **Why:** THE gate for the cut lane — approves the method for batch cutting + makes the integration demo meaningful.
- **Look for:** lamp fully gone in after-crops; reveal behind lamp acceptable (soft blur OK, torn geometry bad); no collateral damage; extracted lamp complete (shade+arm+base).
- **PROVISIONAL (Claude): PARTIAL FAIL — medium-high confidence.** Viewed before/after crops (cut_d_lamp, cut_b_lamp) + fg render: the extraction captured essentially ONLY the lampshade + upper arm (fg_cut_d_lamp.png shows a shade blob + fragment, not a lamp); after-crops show a faint but clearly visible arm skeleton + base remnants on the desk. Numbers agree: fg=382 vs in-box census 2,232 (flagged `fg_in_plausible_band:false`); no fg below 0.865 m (base never extracted). The graph-cut MACHINERY is verified end-to-end; the selection under-covers thin/low geometry. Overnight action taken (automatic, cheap: fine stage = 196 s): diagnostic sweep at thresholds below 0.3 + per-Gaussian score distribution inside the lamp box → re-cut if a better operating point exists; details in R5 when it lands. Batch cuts + integration demo held pending that result.
- **USER VERDICT:**

## R5 — Checkpoint 6: lamp cut quality, attempt 2 (obj_004_v2, user_weight_term=3)
- **What / path:** `D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\bedroom_marble\cut\obj_004_v2\cut_review.html` (fresh full package). Compare against attempt 1: `...\cut\obj_004\cut_review.html`. Viewer layers point wherever serve routes resolve — check the page's stats box for which variant the viewer serves.
- **Why:** decides the cut method's parameterization for batch Step 12 + whether the integration demo stands on good ground. Sweep data (stats.json): w=3 vs w=10 near-tied on the pole defect (170 vs 174 of 254); w=10 kept in WSL for a cheap flip if you prefer its extra shade capture (364 vs 329).
- **Look for:** (a) after-crops: lamp gone incl. base — remaining defects I could see: faint thin-arm trace against the curtain + a dark smudge at desk level where the base was (unobserved-region reveal — acceptable?); (b) fg renders: shade + arm + base plate present, mid-arm gap visible — complete enough?; (c) R4 hypothesis check (one glance): the region below the box (0–0.70 m, runs to floor) — is it desk-front/floor geometry (masks RIGHT to exclude it) or actual lamp parts? Recorded in score_diagnostic.json as `r4_reinterpretation`.
- **PROVISIONAL (Claude): PASS WITH REMNANTS — medium confidence.** fg 382→582, pole capture 0→170, base-on-desk reached (fg bottom 0.718 m), zero contamination on every purity metric, and visually the v2 extraction looks like a lamp rather than a lampshade. Remnants noted above are real but small; integration demo proceeds on v2. Extra-object batch cuts NOT run tonight — method needed per-object parameter discovery, so batching before your verdict would multiply an unvalidated recipe.
- **USER VERDICT:**

## R6 — Integration demo: composition over cut background + fallback resolver
- **What / path:** `D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\bedroom_marble\cut\integration_demo\integration_demo.html` — 8 cameras × 3 variants: (a) original splat + mesh lamp (ghost problem) / (b) cut background + mesh lamp (the payoff) / (c) tinted-floor workaround. Code: background resolver in `scene-pipeline\composition\place2.py` (`--background {auto,cut,tinted,original}`, auto = newest cut background else tinted fallback — your directive implemented; default paths byte-untouched, verified). PIPELINE.md gained the cut-lane stage contract.
- **Why:** the entire point of the cut lane — mesh replacement without the original ghosting through — plus sign-off on the fallback design before it can become a composition default (your call, not made overnight).
- **Look for:** in (b) per camera: the mesh lamp reads as THE lamp; no white ghost lamp behind/through it (compare (a) directly); background intact; does the mesh cover R5's desk-level dark smudge? Note (c)'s fake floor for contrast.
- **PROVISIONAL (Claude): WORKS, WITH A PRESENTATION CAVEAT — medium confidence.** Numerically verified the backdrop swap took effect (pixel-diff (a) vs (b): ~5,000 changed px in the cut_d_lamp crop, concentrated in the ghost region, max diff 560). Visually the (a)-vs-(b) difference is SUBTLE in these views because the retrieved mesh lamp (large, blue) occludes most of where the ghost was — the dramatic removal is in `obj_004_v2\cut_review.html`'s mesh-free before/afters. If the demo underwhelms, judge the cut there; the resolver + fallback machinery is verified regardless.
- **USER VERDICT:**

---

# End of overnight run (R1–R6). Log continues as the living review queue for all efforts.

## R7 — Checkpoint G1: scene-graph correctness (semantic scene graph effort)
- **What / paths:** deep-dive page `D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\bedroom_marble\graph_review.html` (self-contained, opens from disk) + spatial view: `D:\T\Documents\GeorgiaTech\Summer2026\scene-pipeline\launch_viewer.bat` → localhost:8321 → "graph nodes" checkbox (tier toggles, edge-type toggles, click box → card with description/crops/edges, ⚠ markers on disputes). Data: `out\bedroom_marble\scene_graph.json` (109 nodes / 320 edges / appearance on 102).
- **Why:** the graph becomes the single substrate retrieval/placement/refinement read (Step 5 consumer wiring is gated on this). Also: node seed = analyzer boxes was your deliberate bet — this review polices it, and largely overlaps the R3 verdict.
- **Look for:** (a) ON edges (35) physically right (lamp ON desk, chair ON floor); (b) IN edges (108) real containment vs fabricated-depth swallowing (dimmed rows = suspects); (c) architecture vs movable typing; (d) appearance descriptions vs crops (~a dozen clicks); (e) weak tier (14) + 11 label disputes — name nodes to prune (the three "bed" disputes are likely duplicate clusters); (f) floating list (20) — wall art floating is correct-for-now, mid-room junk is not.
- **Facts on file, no provisional verdict** (daytime checkpoint, proxy mode not in effect): numeric hints only — disputes pre-collected by the VLM's own is_label answers; frame self-check passed; ana_101 lamp description matches its known identity.
- **USER VERDICT (graph structure):**
- **USER VERDICT (nodes to prune):**

## R8 — Canonical pano track + f30 score filter (daytime review session 2026-07-26)
- **What / paths:** viewer at `http://localhost:8321/?scene=bedroom_marble` (start via `D:\T\Documents\GeorgiaTech\Summer2026\scene-pipeline\launch_viewer.bat` if down). Layers: **"PANO TRACK (canonical · thr 0.2)"** (108 objects, `D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\bedroom_marble\scene_manifest_pano2c_rc.json`) vs **"pano track · f30 (score ≥ 0.30)"** (102 objects, `...\scene_manifest_pano2c_rc_f30.json`), plus **"Δ before recenter"** (35 pre-change boxes + refuted phantoms).
- **Why:** (a) THE verdict on the canonical pano-track manifest — the box set every downstream rewire (scene graph, envelope, retrieval, agent package) will consume; (b) whether the hard 0.30 filter is a keeper as the first post-processing step.
- **Look for:** (1) canonical layer: do boxes hug real objects; is junk concentrated in the high-count labels (book 33, picture 15, toy 11, basket 7)? (2) toggle f30 vs canonical: the 6 dropped boxes (3 toy, 2 book, 1 conditioner) — junk or real? NOTE 3 of the 6 were retake-CONFIRMED by their own close-ups (scores .27–.28); the filter overrules the verifier there — if any of those 3 is a real object, the filter needs a confirmed-exemption. (3) Δ layer: spot-check a few refinements (old vs new bounds) and refuted phantoms.
- **Daytime session — no provisional verdict; user judges directly.**
- **USER VERDICT (canonical layer):** _(no explicit verdict yet — user moved to post-processing on top of it)_
- **USER VERDICT (f30 filter adoption):** ADOPTED (user 2026-07-26: "i think this works. lets do this"). f30 manifest is the post-processing base going forward. User's next ask: dedup — box-in-box allowed (genuine nesting), target = highly-overlapping boxes (example given: obj_007 lamp vs obj_057 ceiling light), with the caveat that near-exact cross-label overlap may be ONE object with two valid labels ("lamp ceiling fan" case).

## R9 — Dedup merge (post-processing step 2, 2026-07-26)
- **What / paths:** viewer layer **"pano track · f30+dedup"** (92 objects, `D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\bedroom_marble\scene_manifest_pano2c_rc_f30_dd.json`) toggled against **"pano track · f30"** (102). The 10 absorbed boxes are in the file's `dedup_removed`; unmerged overlaps in `overlap_report`.
- **Why:** gates the dedup method (geometry IoU ≥ 0.6 + LLM-judged gray zone) as a standard post-processing stage for all scenes.
- **Look for:** (1) the 9 merge groups — each should be one real object now wearing multiple names (`alt_labels`): chair+office chair, rug+mat+yoga mat, side table+desk, lamp+ceiling light (your obj_007/obj_057 example), 3× door+window, 2× bookshelf+shelf. Is any merge WRONG — i.e., two genuinely distinct objects glued together? (2) the door+window merges: are those 3 elements really doors (possibly glazed), or did a real window get eaten by a door box? (3) the kept bookshelf thicket (obj_043/080/093/140 area): right call to keep, or are those actually duplicates too? (4) nesting untouched: books/toys still inside bookshelves as before.
- **Daytime session — no provisional verdict; user judges directly.**
- **USER VERDICT (dedup adoption):** DEFERRED (2026-07-26 pm). The user
  reviewed and re-scoped the method instead of adopting: dedup is to be
  reworked GEOMETRY-ONLY (confident IoU ≥ 0.6 merges; gray-zone pairs kept
  unmerged and emitted as a `deferred_semantic` queue; LLM call retired).
  ALL semantic judgment — canonical naming of merged/multi-label objects AND
  the same-vs-part question — moves to the scene graph stage (decision:
  "all semantics to graph"). Rework itself is PAUSED pending the "what is
  the scene graph" design discussion. Adoption verdict re-opens against the
  reworked output (expected ~95 objects — door+window gray merges revert).
- **USER VERDICT (any wrong merges):** One finding, and it's a NAMING bug,
  not a merge bug: lamp+ceiling light (obj_007+obj_057, IoU 0.75, box at
  ceiling height) is one real fixture — merge right — but the merged node
  surfaced as "lamp" because primary label = highest detector score, and
  detectors score generic labels higher. User: "i dont think that is a
  great idea." Root cause + rule confirmed in PLAN_SELF_PANO_RIG.md top
  UPDATE block. Door+window merges and the bookshelf thicket were not
  individually ruled on — re-review with the reworked dedup.

## R10 — Checkpoint R1: the scene-graph RECORD (pass 1, 2026-07-26 evening; REBUILT late same evening per the §0a.0 no-pre-merge amendment)
- **What / paths:** viewer layer **"graph record (stage 3)"** (main toggle
  row) at `http://localhost:8321/?scene=bedroom_marble` — **102 detection
  nodes (= the f30 set verbatim, NOTHING pre-merged) + 6 envelope nodes**
  from
  `D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\bedroom_marble\scene_graph.json`.
  Record layer only: label multisets + 465 referenced evidence crops + geometric
  edges (ON 41 · IN 105 · IN_WALL 29 · ATTACHED 3 · INTERPENETRATES 31)
  + **14 SAME_CANDIDATE edges (10 confident IoU ≥ .6, 4 gray)** — the
  open same-vs-part questions, both nodes of every pair present (user
  amendment: "record both objects and indicate their relationship
  faithfully"; merging is a judge verdict). The dedup stage is retired;
  `_dd` / `_dd_llm` manifests remain on disk unused.
- **Why:** Checkpoint R1 of record-then-judge (PLAN_SCENE_GRAPH.md §0a +
  §0a.0) — the record must be right BEFORE any VLM spend: the judge
  passes consume exactly what this layer shows, and the same-vs-part pass
  will visit each of the 14 pink edges.
- **Look for:** (1) node boxes = real objects (toggle vs "pano · stage 2 ·
  f30"— should be the SAME 102 boxes); (2) the 14 pink pairs — confident
  ones (chair↔office chair, lamp↔ceiling light, door↔window ×2,
  rug/mat/yoga-mat triple, side-table↔desk, bookshelf↔shelf ×2) should
  each look like ONE object detected twice; gray ones (shelf↔book,
  bookshelf↔shelf ×2, door↔window) genuinely ambiguous; anything pink
  that's actually TWO distinct objects is a finding; (3) evidence crops
  on the cards — do they show the object (they feed the judge)?;
  (4) ON edges sane (self-check PASSes numerically); 16 floating = wall
  pictures + plants-on-furniture + ceiling lamp obj_062 (obj_007 is
  ATTACHED to ceiling); (5) the books-in-shelves IN clusters look right.
- **Evening session — no provisional verdict; user judges directly.**
- **USER VERDICT (record correctness / R1 gate):** **PASSED** (2026-07-26,
  follow-up session): "all the graph nodes seems good" — R1 gate closed,
  judge passes unblocked.
- **USER VERDICT (SAME_CANDIDATE pair quality — any pink pair that is really two objects):**
  No per-pair findings raised at review; the 14 pairs go to the judge's
  same-vs-part pass, whose first-run verdicts get their own (dev-time)
  review before the merge view builds on them.
- **USER FINDINGS (the 3 NEAR floaters — recorded as GROUND TRUTH for the
  NEAR-resolution pass acceptance test):**
  - `obj_001` plant → **ON floor**; the box bottom (19 cm up) under-reaches
    because the base is occluded ("the plant is on the floor, although the
    box isn't really doing this"). 2 of 4 member detections carry
    `truncated: true` — evidence to be surfaced onto the NEAR edge.
  - `obj_005` monitor → **supported by the desk** via a mounting arm the
    box doesn't include ("the monitor has an arm that is on the table").
  - `obj_096` picture → **belongs to a wall** (user could not locate it in
    the viewer but ruled it wall-attached; geometry says it touches the
    curtain parallel plane 0.4 m inside arch_wall_x_high).
  - Method ruling that followed: these cases are resolved at the SEMANTIC
    stage (judge), NOT by record-stage snap heuristics — heuristics would
    be category knowledge in disguise (automated-pipeline rule). The only
    record-side change allowed: copy truncation facts onto NEAR edges
    (evidence, not conclusions).

## R11 — Room shell: measured walls / ceiling / floor (W3 gate, 2026-07-26 late)
- **What / paths:** viewer :8321 → "graph record (stage 3)" → the new gray
  **architecture** slabs (4 walls + floor + ceiling), each clickable —
  card shows the fitted plane, fit point count, collider agreement Δ, and
  the recorded parallel surfaces. Data:
  `D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\bedroom_marble\room_shell.json`
  (+ audit: `room_shell_audit.json` / `.png`).
- **Why:** the record's architecture was placeholders off by up to 0.4 m;
  32 IN_WALL facts and the envelope's room bounds now stand on these
  measured planes. Wrong walls poison wall-attachment facts and
  placement bounds.
- **Look for:** (1) toggle the collider mesh layer against the gray wall
  slabs — do the slabs sit ON the collider walls (they should: Δ 5–36 mm
  on all four)?; (2) does each wall slab hug the visible wall in the
  splat, not a curtain/wardrobe face (structural = OUTERMOST strong
  plane by design — the curtain plane +1.51/+1.61 and the z_low face
  −0.73 are recorded as parallel surfaces instead)?; (3) click a wall:
  its IN_WALL neighbors light up — are those really wall-mounted things
  (pictures, windows, doors)?; (4) floor/ceiling slabs at the right
  heights (measured 0.000 / +2.764 upright; collider agrees ≤ 4 mm).
- **Assumptions on record:** vertical-prism walls (floor→ceiling), one
  outer segment per side in v1 (schema already takes N segments),
  parallel candidates recorded not judged.
- **USER VERDICT (shell correctness / W3 gate):** **PASSED** (2026-07-26,
  follow-up session, under the blanket record approval "all the graph
  nodes seems good" — no shell-specific findings raised). W3 closed.

## R12 — Judge first-run verdicts: J1 pairs (14) + J5 floaters (3) — DEV STOP (2026-07-26)
- **What / paths:** the `verdict` blocks now on every SAME_CANDIDATE and
  NEAR edge in
  `D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\bedroom_marble\scene_graph.json`
  (additive; record untouched; caches `graph\judge_pairs_cache.json` /
  `graph\judge_near_cache.json`). Modules:
  `D:\T\Documents\GeorgiaTech\Summer2026\scene-pipeline\entangled_gen\graph\judge_pairs.py`
  / `judge_near.py` (sonnet via claude.exe, 3-way concurrent, one firmer
  retry, failures stay unresolved).
- **Why:** first-ever judge output — J2 (merge view) builds on the SAME
  verdicts and J3 naming on the merged multisets, so a wrong merge here
  cascades. This is a DEV stop (design validation), not a pipeline stage.
- **Results, J1 (14/14, 0 unresolved): 11 SAME / 3 PART_OF / 0 DISTINCT.**
  All three door↔window pairs judged one DOOR detected twice; the
  rug/mat/yoga-mat triple is transitively consistent (SAME×3 → one
  3-node merge cluster); PART_OF: books-cluster obj_068 part of shelf
  obj_023 · obj_080 = upper section of bookshelf obj_043 · obj_047 =
  shelf segment of bookshelf obj_088.
- **Results, J5 (3/3 resolved): 2/3 match the R10 ground truth.**
  ✔ obj_005 monitor → ON obj_039 desk (box_underreach: stand too thin to
  detect) · ✔ obj_096 picture → IN_WALL arch_wall_x_high ·
  **✘ obj_001 plant → ON obj_032 shelf, ground truth says ON floor** —
  the verdict's reason misreads gap −1.32 m as "overlaps the shelf's top
  surface" (a large NEGATIVE gap means the plant sits far BELOW that
  top). Implementation finding: the caches key on crops+evidence only, so
  a prompt fix does NOT bust them — needs a prompt-version salt.
- **Look for:** (1) any SAME verdict that is really two objects (these
  become merges in J2); (2) the three PART_OF directions — is the named
  "part" really the component?; (3) 0 DISTINCT — plausible (every pair
  WAS geometry-flagged) or suspicious agreeableness?; (4) the plant miss:
  accept fix (a) prompt gap-semantics + re-judge, or overrule manually.
- **Provisional verdict (Claude, numbers only — user judges):** J1 SAME
  verdicts align with the R9-era readings (chair, lamp/ceiling-light,
  door×3, mats) and PART_OF directions match the height spans on paper;
  the J5 plant miss is a real prompt defect with a mechanical fix.
- **UPDATE (same session) — plant fix APPLIED + v2 rerun: 3/3 match
  ground truth.** User ruling: "code interprets the numbers, the model
  interprets the pixels" — prompts are fixed versioned templates a
  deterministic script fills; nothing is authored per case (the pipeline
  runs unattended over hundreds of scenes). judge_near.py v2:
  deterministic menu builder (candidates classified plausible / floating
  / RULED OUT from fixed thresholds; SAME-judged duplicates collapse to
  one menu slot), PROMPT_VERSION salted into both judges' cache hashes,
  `--selftest` zero-LLM regression on the plant's recorded menu (PASS).
  Rerun verdicts: plant → ON floor, underreach ("pot base visible
  resting on the floor" — the crops DID show it) · monitor → ON desk,
  underreach · picture → IN_WALL x_high. NOTE: judge_pairs' salt
  invalidates its 14 cache entries — the NEXT judge_pairs run re-judges
  all pairs (~6 min); the verdicts standing in scene_graph.json are the
  reviewed v1 ones.
- **USER VERDICT (J1 pair verdicts — approve for J2 merge view):**
  **APPROVED, all 14** (2026-07-26, follow-up session — "approve all").
- **USER VERDICT (J5 v2 floater verdicts — matches user's own answers; approve):**
  **APPROVED** (same). R12 CLOSED — J2 merge view unblocked.

## R13 — Judge chain J2→J3→J4: merge view + names + coherence flags (2026-07-26, post-R12)
- **What / paths:** `graph["judged"]` inside
  `D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\bedroom_marble\scene_graph.json`
  — 92 clusters (from 102), canonical names on the 9 disputed clusters,
  15 coherence flags, 6 nodes existence-disputed. Modules:
  `graph/build_judged.py` (deterministic) · `graph/judge_names.py`
  (2 calls) · `graph/judge_coherence.py` (1 text-only call over a
  259-line room digest). Caches in `out\bedroom_marble\graph\`.
- **Why:** this IS the judged graph the downstream contract will read
  (G2 gates adoption). Names feed retrieval; disputed nodes get skipped;
  the reexamine queue is the v2 vision-escalation input.
- **Names picked (9/9, all from candidates):** office chair · door ×3 ·
  ceiling light (the R9 lamp fix) · bookshelf ×2 · side table · yoga mat.
- **Existence disputed (6):** obj_138 + obj_139 (pictures 100% inside
  doors — the user's motivating case), obj_059 (5 cm "lamp" inside a
  picture, 1 view), obj_091 ("toy" inside a picture), obj_109 (ghost
  office chair, 2 views @ .30, a basket "inside" it), obj_083 (floating
  plant, 2 weak views).
- **Also flagged, no action yet:** 7 reexamine_with_crops (oversized
  "book" obj_066 swallowing two pictures; side-table↔bookshelf 40%
  interpenetration; picture-ON-picture; toy-in-book; lamp-in-curtain) —
  the recorded v2 escalation queue. 2 rename candidates (obj_062 1 m-wide
  ceiling "lamp"; obj_008 1.06×1.71 m "bed" — child-bed sized).
- **Look for (viewer or judged block):** (1) the 9 merges — any that are
  really two objects?; (2) the 9 names vs crops; (3) the 6 disputed —
  each REAL in the splat? A disputed node that IS real is the finding
  that matters (downstream would silently skip it); (4) does the small
  "bed" size match the scene (the digest can't see pixels)?
- **Provisional verdict (Claude, from numbers only — user judges):** the
  6 disputed all have ≤2 views and peak ≤0.42 except the two pictures
  (1 view each); nothing high-evidence was disputed — the conservative
  bias held.
- **UPDATE (same session) — escalation TEXT experiment:** before building
  any vision escalation, one text-only call got the 7 reexamine flags
  with FULL coordinates (not the digest summaries). On the one
  user-verifiable case it matched ground truth exactly (obj_054 basket
  "on the floor beneath the chair; the chair box spans its wheeled base
  and empty leg-space") — the other 6 answers are specific box-level
  mechanisms awaiting user eyes. Script + results in the session
  scratchpad (see PLAN_SCENE_GRAPH.md §0a.7 experiment note).
- **USER VERDICT (judged view: merges + names + disputed set):**
  **"good enough for me for now"** (2026-07-26) — soft acceptance;
  formal in-viewer eyeball deferred (no judged viewer layer yet).
  DIRECTION SET: next effort = the PLACEMENT stage, where the LLM
  resolves the escalation flags AND affects boxes/placements; pipeline
  formalized in PIPELINE.md + pipeline_map.html (all judges drawn).

## R14 — CLEAN METHOD RERUN (settled design §0a.8) — paused BEFORE J6 for user approval (2026-07-26/27)
- **What / paths:** the derived layer was RESET (loop-era products
  discarded per user: "we don't want products from methods that aren't
  what we want") and the settled chain re-run: build_judged (self-checks
  PASS, mat-support + evidence fixes in) → J3 from cache (9/9, 0 calls)
  → **J4 ONCE** (1 call, 12 flags, 4 existence-disputed:
  obj_059/091/138/139). J6 (terminal: resolution + appearance in one
  pass, `describe_nodes.py` v3 with judge_cases folded in) is BUILT and
  its artifacts are ready, NOT run. Review artifacts:
  `D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\bedroom_marble\graph\case_sheets\`
  (cases_existence.png, cases_reexamine_1/2.png + verbatim prompts) and
  `...\graph\appearance_sheets\` (11 sheets + manifest).
- **Why:** methodological cleanliness — the file must be produced BY the
  drawn pipeline (map = authority, new rule pipeline-viewer-authority),
  not by the revoked loop. J1/J5 verdicts (record-side, R12-approved)
  and the J3/appearance caches were legitimately reused.
- **Note (honest):** J4's fresh run re-found the core suspects but NOT
  identically to the loop era (e.g. the ghost chair obj_109 is now a
  re-examine pair, not an existence flag; obj_035/obj_096 deep-"picture"
  boxes are newly flagged, single-target → they SHIP unadjudicated).
  Run-to-run variance is inherent; whatever J6 leaves ships.
- **J6 queue if approved:** existence 4 · rename 0 · re-examine 5
  (→ ~3 resolution calls, concurrent) + appearance (~86 mostly cache
  hits; fresh sheets only for phase-A-renamed/confirmed clusters).
  Est. 4–6 calls total, then SHIP — no re-scan.
- **USER VERDICT (run J6 terminal pass):** **APPROVED AND RUN**
  (2026-07-27; user first manually inspected the J5 verdicts + the J4
  flag table). J6 results, 4 calls total: existence — obj_138/obj_139
  REAL picture frames (mitred frame corners visible; door-containment =
  geometry error) · obj_059/obj_091 NOT_REAL (artwork content inside
  picture frames, not objects) · 0 unclear. Edges — 5/5 REINTERPRET with
  suspect boxes for placement: lamp≁curtain (curtain box oversized) ·
  basket under chair's leg-space (chair box) · AC wall-mounted, bookshelf
  alignment coincidental (bookshelf box) · two pictures hung 6 cm apart,
  not stacked · book ON shelf, not PART_OF (obj_023 box; model returned a
  tile label as suspect once — validator added, verdict patched).
  Appearance — 90/90 (86 cache hits + 1 fresh sheet). SHIPS OPEN:
  obj_035/obj_096 deep-box flags + obj_083 floating plant (placement
  work orders). **bedroom_marble scene_graph.json is now produced
  end-to-end by the drawn pipeline: record → J1∥J5 → J2 → J3 → J4 once
  → J6 once → ship.**

_(further entries appended as artifacts land)_
