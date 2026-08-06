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

## 2026-08-05C — SUB ROUNDS CP1: seed transform (isolated, obj_043)

- **What:** the 8 deferred subs' placement seeds — observed anchor→sub
  offsets re-expressed on the fitted obj_043 pose (user ruling: same
  relative position, large margin later). Deterministic; no judge.
- **Why:** the anchor moved during fitting (declip −0.06 x, floor-snap
  +0.154 y raw; yaw 0), so raw observed positions are stale by exactly
  that transform. CP1 is the foundation every later CP builds on.
- **Look for (page: compose/sub_experiment/cp1/index.html):** green
  seed boxes sitting on/inside the real shelf in both views at the
  same spots the orange observed boxes occupy (move was small —
  near-overlap = PASS); heights spread over distinct boards (0.79 →
  2.11 m, basket on top); no seed off the shelf or mid-air between
  boards.
- **Found on the way (real, kept in the script):** fitted_preview
  fit_box is RAW-frame (byte-identical x/z to the observed box) while
  declip_move_m is RENDER-frame — verified against the GLB mesh, which
  is the placed truth. And shot.py silently renders EMPTY above
  1024 px (1024 fine, 1050 blank) — RES pinned 1024 + a blank-render
  size guard added.
- **Provisional verdict (mechanics only, not the visuals):** PASS —
  delta matches the GLB exactly; offsets all within the shelf
  footprint. USER GATE OPEN.

## 2026-08-05C — SUB ROUNDS CP2: board extraction (isolated, obj_043)

- **What:** the fitted stand-in mesh's REAL support surfaces — upward
  faces height-clustered into boards (height, footprint, headroom).
  Pure geometry, no judge.
- **Why:** this is the reason the subs were deferred: books need
  actual boards, not the anchor's outer box.
- **Look for (page: compose/sub_experiment/cp2/index.html):** 6
  rectangles (B0..B5, 0.05→1.77 m, ~0.34 m spacing) drawn AT board
  height over the real shelf photo. Sensible count/spacing/extent?
  Any real board missed, any phantom? Rectangles are the STAND-IN's
  boards — offset vs the real shelf's board lines = retrieval
  fidelity to weigh, not an extraction bug.
- **Provisional verdict (mechanics only):** PASS — sub observed
  heights (0.79/1.13/1.46/1.79) each sit ~4 cm above a board
  (B2..B5); the 2.11 m basket rides above the top surface. USER GATE
  OPEN.

## 2026-08-05C — SUB ROUNDS CP3: board assignment + seed clamp

- **What:** each CP1 seed assigned to its nearest CP2 board (bottom
  snapped on, footprint clamped inside, too-tall/too-wide flags
  recorded not resolved). Pure geometry, no judge.
- **Why:** the placement round needs a legal start on a real surface;
  this is the step that turns "roughly there" into "on THIS board".
- **Look for (page: compose/sub_experiment/cp3/index.html):** every
  light-blue start box standing ON a board in the front view (no
  floating, no wrong level); top-down: nothing outside its board
  rect. Red = flagged (none this run).
- **Provisional verdict (mechanics only):** PASS — 8/8 assigned to
  B2..B5 reproducing the observed per-level pairing; snaps ≤ 0.14 m,
  clamps ≤ 46 mm, zero flags. USER GATE OPEN.

## 2026-08-05C — SUB ROUNDS CP4: cheap-by-class retrieval

- **What:** top-1 asset per sub by category match + native-size fit
  (anchors' shopping machinery reused verbatim), NO judge calls —
  user ruling; weak matches flagged, never silently shipped.
- **Why:** effort follows error cost — a wrong-ish book spine costs
  nothing visually; judge spend is reserved for distinctive items.
- **Look for (page: compose/sub_experiment/cp4/index.html):** is each
  thumbnail the right KIND of thing at a believable size for its box?
  Only an UNFLAGGED wrong pick fails the gate (flags = already
  marked for a later judged pass; none this run).
- **Provisional verdict (mechanics only):** PASS — 8/8 tier-0 exact
  category, worst-axis fit 0.12–0.25, zero flags. Book boxes are
  rows → picks carry k=2/3 copies for CP5 to honor. USER GATE OPEN.

## 2026-08-05C — SUB ROUNDS CP5: raw placement on boards

- **What:** the CP4 assets actually standing on their CP3 boards —
  place_candidate reused verbatim (perm, host-inherited facing, k
  tiles, bottom-on-board), PCA snap OFF (user: raw first), no
  jiggle/declip; overlaps recorded not resolved.
- **Why:** see what untreated assets do before spending any
  correction machinery on them.
- **Look for (page: compose/sub_experiment/cp5/index.html):** books/
  basket ON their boards, spines out, roughly where the real ones
  are (front + composed + top-down). Tilt/crookedness is the
  expected raw-asset mess. 1 same-board overlap pair in the table.
- **Provisional verdict (mechanics only):** PASS — 8/8 placed, rows
  tile the right axis, bottoms on boards. CAVEAT for the next lever:
  the canon PCA snap corrects YAW only — the books' visible LEAN is
  baked roll/pitch in-file and needs a different fixup (or different
  assets via the recorded runner-ups). USER GATE OPEN.

## 2026-08-05C — SUB ROUNDS CP5b: the align trick

- **What:** align_upright() — OBB axes snapped to nearest world axes
  per asset (minimal rotation) before placement; canon PCA stays on.
  Fixes the baked roll/pitch lean the yaw-only PCA cannot.
- **Why:** the raw pass showed the library books lie/lean in-file
  (user-confirmed); scene-agnostic geometric fix, no judge.
- **Look for (page: compose/sub_experiment/cp5_align/index.html,
  raw|align side-by-side):** books now standing upright on their
  boards, spines out; nothing that flipped to lying-down (the
  near-45° ambiguity — three assets applied 45.5° and could snap
  either way in general).
- **Provisional verdict (mechanics only):** PASS — applied angles
  2.3–45.5°, all 8 upright in-render, face dot 1.0 across the board.
  USER GATE OPEN.

## 2026-08-05C — SUB ROUNDS: align-before-shop + final pass

- **What:** user insight applied — the align trick changes an
  asset's AABB, so shopping must fit on ALIGNED sizes: top-12
  catalog candidates re-measured post-alignment (cached per uid),
  re-ranked; placement rerun on the new picks.
- **Why:** a leaning asset's catalog AABB overstates footprint and
  understates height → wrong fit scores and wrong k multipliers.
- **Look for:** cp4_aligned/index.html — 4/8 picks CHANGED (tagged
  with what cp4 had); cp5_final/index.html — the final shelf. Same
  gate as before: right kind of thing, upright, on its board.
- **Provisional verdict (mechanics only):** PASS — the 45.5° leaner
  was dropped from every slot (its AABB lied the most), best fit
  improved 0.231→0.082, placed uids verified equal to the picks,
  8/8 upright. USER GATE OPEN.

## 2026-08-05C — SUB ROUNDS: level-1 fleet (all 15 anchors)

- **What:** the canonized recursion (SR0–SR7) run over every anchor
  with deferred subs — seeds → boards → assignment → aligned shop →
  aligned place, per anchor, serial (GPU pacing).
- **Why:** the obj_043 gates ratified the machinery; this is the
  same machinery at fleet scale, deterministic, 0 judge calls.
- **Look for (page: compose/sub_experiment/index.html):** per-anchor
  final front shot — things standing on real surfaces where the real
  ones are. Warnings are records, not errors: NO_BOARD skip (ceiling
  light), pick flags, overlap counts.
- **Provisional verdict (mechanics only):** PASS with known debt —
  56/64 placed · 6 level-2 riders correctly deferred (hosts first) ·
  1 no-board skip · 77 same-board overlap pairs concentrated in the
  crowded shelves (obj_022 = 28 subs) = the quantified case for the
  missing sub-jiggle. One fleet bug found+fixed (empty-GLB export on
  a nothing-placeable anchor). USER GATE OPEN.

## 2026-08-05C — SR4b: the host-covers-it rule (door-handle autopsy)

- **What:** user asked what obj_006's 1 sub was → autopsy: invented
  "door handle" add tier-1 matched category "door" and BOUGHT A
  WHOLE DOOR (fit 18.28, POOR_FIT-flagged) to stand on the door's
  molding ledge. Fix wired: sub category == host category →
  HOST_COVERS, no buy (shopping.py's anchor-tier header rule,
  applied to the cheap path).
- **Why not tier-0-only:** the fleet data killed that idea — tier-1
  "computer monitor"→monitor and "framed picture"→picture are
  CORRECT; host-covers-it discriminates exactly.
- **Look for (overview page, obj_006/127/128 rows):** door subs now
  HOST_COVERS with no placement; monitor + picture picks unchanged.
- **Provisional verdict (mechanics only):** PASS — 3/3 handles
  dropped, 0 collateral. USER GATE OPEN (rides the fleet gate).

## 2026-08-05C — SR4c: sub dry-list = anchor rule 9, same loop

- **What:** user ruling ("our goal is to use the same loop"): the
  anchors' all-3-dry rule re-enters at sub tier — shortlist runners
  are the walk; best of the WHOLE shortlist over DRY 0.65 → adds
  drop entirely, detections drop with a recorded complaint (library
  gap; no re-shop exists — the full category pool was already
  searched).
- **Look for (overview, obj_017 row):** obj_059 "small glass
  decorative" now DRY, unplaced, complaint recorded ("no glass
  within 0.65 of [0.05, 0.09, 0.03] m", best was 0.931). The
  borderline obj_013 picture (0.538) correctly SURVIVES with its
  POOR_FIT flag.
- **Provisional verdict (mechanics only):** PASS — 1 firing, 0
  collateral; constants shared with the anchor tier, nothing new
  invented. USER GATE OPEN (rides the fleet gate).

## 2026-08-05C — SR4b-v: host-covers verification, rung 1

- **What:** HOST_COVERS verdicts now VERIFY against the host's
  placed asset — rung 1 = part word in the catalog description
  (free, code-only); silent description → UNVERIFIED flag queuing
  the rung-2 thumbnail judge (uid × part cache). Rung 3 (part
  verified missing → face-mount on the host) recorded as open.
- **Look for (overview, door rows):** all 3 handle firings
  verified_text — matched 'handle' in "brown wooden door with
  silver handle" / "fruitwood ... with brass handles". Zero
  UNVERIFIED this scene.
- **Provisional verdict (mechanics only):** PASS — the assumption
  SR4b made is now evidence for every current firing. USER GATE
  OPEN (rides the fleet gate).

## 2026-08-05C — SR3b + SR4b-v2 + SR4d (the obj_014 window autopsy)

- **What:** user pulled the thread on obj_014's sub → the invented
  in-wall window was standing on a curtain fold. Three rules wired:
  SR3b attachment-class gate (in-wall observed box → wall channel,
  never boards; OBSERVED box tested, not the seed — the curtain's
  wall-flush had dragged the seed 1 cm past the threshold) ·
  SR4b-v2 rung-2 thumbnail judge (autonomous, cached; the curtain
  asset judged NOT to include a window, HIGH — so the window stays a
  live WALL_CHANNEL need) · SR4d sub-brings-host (the window pick
  "with green curtain" would duplicate the host — prefer clean
  candidates).
- **Note (judge vs user eyeball):** user saw "a window" in the
  render; the judge says the ASSET has none — likely the real
  scene's window in the splat behind the ghosted curtain. If the
  asset thumbnail disagrees on inspection, that is a rung-2 prompt
  defect to chase.
- **Look for (overview, obj_014 row):** window unplaced, flags
  NOT_A_BOARD_RIDER + WALL_CHANNEL, judge verdict in the record.
  Fleet re-run applying SR4d everywhere in progress.
- **Provisional verdict (mechanics only):** PASS — the gates fire in
  order, every decision carries evidence. USER GATE OPEN.

## 2026-08-05C — SR8: sub-jiggle + the capacity finding

- **What:** cp6 — fit_declip at depth 1, final form = per-board 1D
  legalization (deterministic two-pass sweep; bounce-apart tried and
  replaced after it oscillated and created an overlap). Boards whose
  contents exceed their span are OVER_CAPACITY: untouched, recorded
  with need vs span.
- **The finding:** the fleet's 77 overlap pairs are ~all
  OVER-CAPACITY, not jitter — e.g. obj_022 board 6: 6.37 m of items
  on a 1.5 m board. Height collapse: short stand-ins push several
  observed shelf levels onto one board. Jiggle is the wrong tool by
  measurement; SR9 (capacity-aware redistribution, walk-class) is
  queued.
- **Look for (per-anchor cp6 pages, overview links):** legalized
  boards clean (before|after fronts), over-capacity tables honest,
  nothing shoved off an edge, wide-exempt untouched.
- **Provisional verdict (mechanics only):** PASS as machinery,
  and the machinery's real product today is the MEASUREMENT that
  redistribution, not jiggle, is the next lever. USER GATE OPEN.

## 2026-08-05C — SR9: capacity triage (tile-drop → spill → kill)

- **What:** the no-converge cure, run BEFORE legalization: k-tiled
  rows shed copies first (user: "we don't have to kill the entire
  box"), then height-collapse victims spill to the nearest-height
  board with room, kills only when nothing has room (none fired).
- **Look for (per-anchor cp6 pages + overview):** shelves readable
  again — obj_022 67→3, obj_032 9→0, obj_043 1→0. Tile drops (32,
  each freed length listed), spills (14, dy recorded — books DID
  change shelf level; judge whether that reads acceptably vs the
  photo), zero kills. Residual = one B4 triple, wide+tall flagged
  since CP3 (walk-down material).
- **Provisional verdict (mechanics only):** PASS — 77→3 with no
  content killed; every departure from the observation is a recorded
  decision. USER GATE OPEN.

## 2026-08-06 — SUB ROUNDS CP7: host-aware walk-downs (obj_022)

- **What:** experiments/sub_round_cp7.py — the host mesh joins the
  sub physics (user: "this is not jiggling with the host object
  itself"). Underside-boards (flipped-normal plank bottoms, 44–48 mm
  below a full board) detected → kept as compartment CEILINGS, their
  squatters re-seated up; too-tall items walk their cp4 runners
  (trial-placed native, align trick) → 4 walked, 7 TOO_TALL_DRY kept;
  per-board FREE INTERVALS measured on fit_check's 2 cm voxel
  lattice (dividers/panels subtracted; access test for doored
  compartments) become pseudo-boards for SR9/SR8; cross-level pairs
  + ceiling protrusions + host clips now counted (cp6 counted
  same-board only).
- **Findings on the way:** B1 is dividers, not doors (mesh evidence;
  front coverage 0.11) — three cubbies; short intervals flipped
  their long axis to the board depth (the obj_030 wrong-cubby clip)
  → axis pinned via force_ax.
- **Numbers:** cross-level 28→7 · protrusions 9→4 · host clips 13→3 ·
  residual = the B4 trio (too-tall, runners dry, wide-exempt,
  over-capacity) + one 2 mm graze. COST: 4 kills on B3 (obj_018/042/
  049/050, "no board has room") — the stand-in-under-capacity
  complaint, anchor-walk feedback material.
- **Verdict:** USER PASS ("great. this is better").

## 2026-08-06 — CP7 fleet: host-aware pass over all 15 anchors

- **What:** cp7 run per anchor (serial, paced); overview rebuilt
  with cp7 shots/links. Fixes on the way: mattress-relief threshold
  (Y_BLOCK_MIN 0.10 — obj_008's pillow was killed by duvet folds
  read as obstacles; ⚠ flagged constant) + walked-then-killed guard
  + idle/empty-scene guards.
- **Look for (overview: sub_experiment/index.html):** obj_022 as
  already gated; obj_032 — 2 re-seated, cross-level 7→0, host 6→3,
  but protrusions 3→4 (re-seating SURFACES violations that were
  hidden inside planks; 4 dry = library gap); obj_008 — pillow
  survives, 1 relief-contact clip; obj_043 host 3→0; the 8
  idle/quiet anchors unchanged.
- **Provisional verdict (mechanics only):** PASS — every residual
  is recorded and traces to too-tall dry items or stand-in
  under-capacity, none to the machinery.
- **Verdict:** USER PASS + CANONIZED as SR10–SR12 ("i think this is
  great. lets cannonize all this"); viewer subs layer added same
  session (user: "great, show in 3d viewer" → /subs_preview.glb +
  "subs" checkbox, server restarted PID 24668). Nits deferred to
  next session (user).

## 2026-08-07 — NITS: SR12b relocation + SR10 at the source + the
## rowable tiling gate (obj_022 shelf, obj_039 desk)

- **What:** three scene-agnostic fixes from the nits walk, each
  user-spotted in the 3D viewer / renders. (1) **SR12b
  HEIGHT-AWARE RELOCATION** (sub_round_cp7.py): SR9 spill targets
  must clear headroom (pseudo-boards carry ceil_y), and the walk-
  down gains a last rung before TOO_TALL_DRY — rigid move to the
  nearest-observed-height standing board that fits height AND
  footprint (the board-4 books stabbed the plank above while the
  shelf top sat empty). (2) **SR10 AT THE SOURCE** (user: "the
  upper board facing down was extracted as level"): cp2 classifies
  undersides at extraction (underside_of in boards.json, ·ceil on
  the overlay, role column on the page); cp3 assigns and cp6
  spills to STANDING boards only; cp7's re-seat stays as a safety
  net and ran 0 times on the re-run — the classification holds
  through the chain. (3) **ROWABLE TILING GATE** (shopping.py
  ROWABLE_CATS = book/books; native_fit(rowable=)): k>1 tiling is
  the book-row convention and was FABRICATING objects — one
  detected desk lamp became 3 tiled lamps, one monitor became
  twins (obj_039). Singular categories now place ONE copy at
  native size; the unfilled span is an honest fit deviation.
- **Look for:** obj_022 — 0 clips / 0 cross-level / 0 protrusions,
  13 placed, 7 kills (honest under-capacity complaints, walk-back
  food for the queued anchor re-shop); obj_039 desk — lamp
  relocated board 4→5 (the desktop), k=1 single tripod lamp, and
  the k=1 re-rank flipped the monitor pick from the sci-fi arm to
  a real monitor. Fleet: 15/15 clean, totals 2 relief-scale clips
  (obj_008, obj_023) · 0 xlvl · 0 prot · 0 dry · 8 kills.
- **Verdict:** USER PASS ("good shit… any imperfections is fine
  now, it's good enough"); tiling-gate direction user-ruled
  ("we do want to take care of the tile stuff"; library asset
  QUALITY explicitly out of scope for the paper). QUEUED with user
  agreement: **multiplicity judge** at the graph stage — per-object
  crop question "one instance or a row (~how many)?" recorded as a
  node attribute, consumed by shopping as the k ceiling, replacing
  the category whitelist (detect/lift individuates only what it
  can spatially separate; per-object pixel interpretation is
  judge-pass territory).

_(further entries appended as artifacts land)_

## R-S2-0 - SCENE #2 living_marble: intake frame contract (CP0 + frame saga)
- **What / path:** viewer `localhost:8321/?scene=living_marble` (splat + rotated collider); raw page `/raw?scene=living_marble` (bundle as shipped); module `entangled_gen/frame_bootstrap.py`; evidence trail in `docs/PLAN_SCENE2_LIVING.md`
- **Why:** gates the whole scene-2 run - every stage consumes the pipeline frame this intake defines (trust bundle + splat-transform rot180x constant, zero estimation).
- **Look for:** room right-side-up, orange mesh lying ON the splat, no mirror.
- **PROVISIONAL (Claude):** n/a - user reviewed live.
- **USER VERDICT: PASS 2026-08-06 ("this is correctly aligned and rotated")**

## R-S2-1 - CP1 pano self-render (module-reproduced)
- **What / path:** `out\living_marble\rig_sp0\pano_selfrender.png` (8192x4096, eye +0.523, signs -x+y+z); gate composite vs Marble pano: scratchpad `cp1_pano_gate.jpg` (that composite showed the earlier eye +0.531 render; current pano re-stitched blind by the module chain, eye moved 8 mm)
- **Why:** the canonical pano - all detection crops are resamples of it.
- **Look for:** upright, same handedness as Marble's pano (landmark left-right ORDER matches), furniture nameable in crops. 180-degree front/back start-direction offset vs Marble = cosmetic (yaw origin choice).
- **PROVISIONAL (Claude): PASS - high confidence** on frame grounds (signs + floor now proven by the settled contract; user viewed the near-identical +0.531 render and objected only to the start-direction offset). 8 mm eye change cannot alter content.
- **USER VERDICT:**

## R-S2-2 - FINAL frame design: bundle frame pipeline-wide (supersedes R-S2-0/1 artifacts)
- **What / path:** rebuilt living_marble (intake -r 180,0,0 un-rotate, collider byte-copy, A2 pano); viewer + cp1_pano_gate_v2.jpg
- **Why:** the frame contract every stage consumes; one convention pipeline-wide (bedroom class = Marble bundle frame).
- **USER VERDICT: PASS 2026-08-06 ("bro this is good. excellent") - viewer + pano both. CP0+CP1 closed.**

## R-S2-3 - P2 crop rig + P3 vocab (living)
- **What / path:** crops `out\living_marble\rig_sp0\crops\` (20 webp + camera sidecars); vocab `out\living_marble\vocab.json` (23 gdino query terms; concreteness-pass drops recorded in the file)
- **Why:** crops are the only pixels detection ever sees; vocab is the only vocabulary it may name.
- **Look for:** crops upright + furniture nameable; vocab has no abstractions (the "elegance/warmth" leak class) and nothing obviously missing for a living room.
- **PROVISIONAL (Claude):** PASS on mechanics (20/20 crops, both vocab source fixes verified in output: pano leg non-empty, door present).
- **USER VERDICT:**

## R-S2-4 - P3 seg_batched (crash + capped re-run; full 20 views)
- **What / path:** `out\living_marble\rig_sp0\seg_batched20\` - per-view `*_boxes.png` / `*_masks.png` + `detections.json` (all 20 views, single post-crash run under the 1500 MHz clock lock)
- **Why:** every 3D object in the record originates as one of these detections; nothing else enters the pipeline.
- **Look for:** boxes sit on real objects with sane labels; up-40 views nearly empty is EXPECTED (ceiling); no fabricated repeats.
- **PROVISIONAL (Claude):** PASS on numbers (171 detections lift-worthy downstream; label mix reads like a living room). Crash forensics + fix: PLAN_SCENE2_LIVING.md "CRASH + RECOVERY".
- **USER VERDICT:**

## R-S2-5 - P4 pano_lift (verified cameras, robust merge)
- **What / path:** `out\living_marble\scene_manifest_pano2c.json` (+`_gated`, kept 75/75); console: cams verified 18/20 (FAILs = the two up-40 views y000_pp40 corr 0.124, y270_pp40 0.091 - their detections excluded by the house rule), 171 dets -> 75 objects, floor-ish gap median +0.033
- **Why:** the first 3D manifest - box quality here bounds everything downstream.
- **Look for:** viewer `localhost:8321/?scene=living_marble` pano-track layer: boxes ON furniture, no floaters/through-floor.
- **PROVISIONAL (Claude):** PASS-leaning on numbers (floor-gap stats match bedroom's healthy profile); the 2 cam FAILs are both ceiling-aimed - consistent with the short-ceiling scene property, watch it recur.
- **USER VERDICT:**

## R-S2-6 - P5 recenter (complete / verify / enrich) - THE CANONICAL MANIFEST
- **What / path:** `out\living_marble\scene_manifest_pano2c_rc.json` (65 objects + 1 book child); shots + per-target purpose/corr/confirmed: `out\living_marble\rig_sp0\rcc\` + `targets.json`; delta layer `scene_manifest_pano_rcdelta.json` (10 refuted + 14 pre-refinement boxes); skipped too-wide: 2 curtains (119/102 deg - cylindrical-strip customers)
- **Why:** the design thesis stage - every deletion must have a photograph behind it; this manifest feeds the room graph verbatim.
- **Look for:** (1) each refuted drop's shot really shows no such object (obj_034/035/037/049/050/052/055/070/072/073); (2) refinement deltas shrink toward the truth, not away.
- **PROVISIONAL (Claude):** MIXED - refutation rate (10 of 17 verify targets) matches bedroom's profile (42/57), BUT 9/38 shot cameras FAILED mechanical verify, clustered on ceiling lights / lighting fixtures / floor lamp -> those targets stayed UNVERIFIED-KEPT. Short-ceiling scene property suspected; possible generality issue to fix at source if it recurs at the graph judge passes.
- **USER VERDICT:**

## R-S2-7 - P6 score filter
- **What / path:** `out\living_marble\scene_manifest_pano2c_rc_f30.json` - keep 66 / drop 0 at thr 0.30 (bedroom dropped 6 of 108)
- **Why:** the adopted feed for the graph record.
- **Look for:** nothing visual - zero drops means recenter's evidence-based kills already did the cleaning on this scene.
- **PROVISIONAL (Claude):** PASS (trivial pass-through).
- **USER VERDICT:**

## R-S2-8 - OVERNIGHT RE-RUN supersedes R-S2-3..7 (canonical 0.20 + synonym pass)
- **What / path:** the afternoon run had MY threshold deviation (seg at default 0.35, not the canonical 0.20/topk40). Overnight redo, blind vocab (user stopped the TV-motivated hand-tune; the generic LLM detector-phrasing pass replaced it and produced tv/couch/drapes/overhead-light/photo/artwork/houseplant with zero scene knowledge). Timings for every module: `out\living_marble\stage_timings.csv`.
- **Why:** canon compliance + the automation-rule correction, in one run.
- **Look for:** nothing separately - the stages below are the review surface.
- **USER VERDICT:**

## R-S2-9 - P3/P4/P5 redo (seg 630 raw dets -> lift 124 obj -> recenter 105 -> f30 94)
- **What / path:** `seg_batched20\` overlays (20 views, canonical floor); `scene_manifest_pano2c.json` (124 obj; cams 18/20 - same two up-40 FAILs); recenter: 59 shots, 24 refinements, 19 refuted-with-photo (`rig_sp0\rcc\` + `targets.json`, delta layer `scene_manifest_pano_rcdelta.json`); filter -> 94 (`_rc_f30.json`; 2 drops were retake-confirmed = the known filter-overrules-verifier caveat).
- **Why:** the permissive floor is the design: 3.7x the raw detections, cleaned by evidence downstream.
- **Look for:** viewer pano-track layers; the 19 refutation photos; **TV story: detected in 6 views (television x3 objects), but the 2 low-score TV objects were REFUTED by their verify shots - the glossy-screen finding now has a full evidence trail** (detection can name it; verification can't re-find it; reflections still win). Wordpiece artifact "##apes" (from "drapes") made 2 phantom objects - both killed by verification; canonicalize hardening = queued source fix.
- **PROVISIONAL (Claude):** PASS on numbers; the TV + ##apes items are FINDINGS, deliberately not patched mid-test.
- **USER VERDICT:**

## R-S2-10 - SOURCE FIX: recenter stale-shot cache (bug found live overnight)
- **What / path:** first re-run produced 40/59 corr~0 cam FAILs + 16 FALSE refutations - rc2_NN shots are cached BY INDEX; a changed manifest re-aims index NN at a different object (stale image + fresh camera). Fix: content fingerprint of the target list gates the cache (`pano_recenter.py`, commit 22d855d); same fingerprint = crash-resume, else wipe shots + shot-seg. Second run = the healthy numbers in R-S2-9.
- **Why:** fires on ANY scene the moment recenter re-runs after upstream changes - scene-agnostic by construction.
- **Look for:** the fix's cleared-files log line in `overnight_run.log` lineage; REVIEW: agree the first-run refutations were artifacts (they included obj_100/obj_107 televisions AND 6 legit objects).
- **USER VERDICT:**

## R-S2-11 - Room shell W1 on an OPEN-PLAN scene (+ extent-clip source fix)
- **What / path:** `room_shell.json` + `room_shell_audit.png`. First fit was garbage (floor -10.4, a 25-point "wall" at -6.8): open-plan floater gaussians outside the room dragged the midpoint splits. Fix at source: clip to the frame block's robust extents before histogramming (audit path already did) - **bedroom regression bit-identical** (commit 22d855d). Second fit: floor -1.056 / ceil +1.079 (the 2.2 m short room), 4 walls all collider-agreed 5-20 mm.
- **Why:** the shell feeds graph architecture nodes + snap planes + declip sandbox.
- **Look for:** **W3-class DESIGN QUESTION, not patched: z_low -2.492 is the collider's artificial CAP plane (the open end CP1 flagged), now recorded as a wall; there is also real splat space beyond x_low (audit bound -2.9 vs wall -1.86).** Consequence: room dims stop at the caps; anything beyond reads IN_WALL. Needs your ruling on what an open boundary IS.
- **PROVISIONAL (Claude):** numbers PASS for a box-room approximation; open-boundary semantics = user decision.
- **USER VERDICT:**

## R-S2-12 - Graph record + full judge chain (G1..J7): 100 nodes -> 51 shipped
- **What / path:** `scene_graph.json` (record -> judged -> resolved); appearance sheets `graph\appearance_sheets\`; case sheets for the 8 rejections. Chain: G2 self-checks PASS; J0 nominated 16 semantic pairs; J1 64/64 (0 unresolved); J2 merge PASS (16-name queue); J3 16/16 named; J4 disputed all 7 wall-sized "picture" artifacts + obj_004; J6 REJECTED all 8, renamed tray+vent, 51/51 described; J7 shipped 51 nodes / 130 edges, 3 suspect-box work orders.
- **Why:** graph[resolved] is THE canonical handoff - box quality + identity verdicts bound everything in compose.
- **Look for:** J1 gems worth eyeballing: hedge-through-the-glass ruled DISTINCT from the door; sheer vs heavy curtain layers kept DISTINCT; the synonym-label lighting families merged (the map-back fix in 22d855d will pre-merge these next scene - tonight the judges absorbed it, by design). J4's existence disputes all landed on physics reasons.
- **PROVISIONAL (Claude):** PASS - every self-check green, zero unresolved verdicts.
- **USER VERDICT:**

## R-S2-13 - Compose S1/S2/PH1 (support truth -> consistency -> snap)
- **What / path:** `compose\supported_by.json` (51/51 resolved, 0 needs_review, 10 crude-rule demotions); `compose\consistency.json` (drops all box-noise adjudications); `compose\snap.json` (43 snapped; sofa obj_018 refit z 2.88->1.25 m on 8/9 view agreement = a suspect-box work order RESOLVED; 8 large corrections all pillows->sofas = advisory per the dependent-placement contract).
- **Why:** the support truth is what placement builds on; snap fixes anchors, not dependents.
- **Look for:** the sofa refit (biggest single geometry change of the night) in the viewer; the S2 drop list reads.
- **PROVISIONAL (Claude):** PASS-leaning; the sofa refit is the one item worth your one-look.
- **USER VERDICT:**

## R-S2-14 - S3 edits + S4 shopping/pick (living)
- **What / path:** `compose\edit_proposals.json` (0 deletes / 8 adds / 4 swaps / 2 reopen petitions); `compose\shopping.json` + `picks.json` (33 anchors shopped, 0 NO_MATCH); pick sheets `compose\pick_sheets\`.
- **Why:** proposals-only layer + the library filter; adds enter only via placement.
- **Look for:** pick sheets (the mood-sheet style ranking); the 4 swaps' in-assets - swap_r2n1_in1 "floor-to-ceiling window" placed with fit_box reaching x=6.32 (1.77 m out of box, declip moved it 3.12 m) = SUSPECT, and swap_r1n1_in1 framed picture wall-push 1.67 m = SUSPECT. The adds are small wall fixtures (light switches) - sane.
- **PROVISIONAL (Claude):** shopping/picks PASS; two of four swaps look geometrically broken - review before trusting the swap channel on this scene.
- **USER VERDICT:**

## R-S2-15 - PH2 fit loop -> DRY (4 rounds) + rotation pass + closing place
- **What / path:** `compose\fitted_preview.glb/.json` (33 placed, all k=1); loop timings in `stage_timings.csv`; final `fit_check.json`: **14 clips, 0 out-of-bounds**; `fit_walk.json` 5 complaints (re-shop food, QUEUED as on bedroom); `compose\rotation_check.json` + `rotation_check\` sheets - verdicts recorded, **0 applied** (no HIGH-confidence free-standing verdict passed the rule-7 gate; door 90-degree low-conf + window 90-degree medium-conf flags carried on the placements).
- **Why:** the posed scene = the fleet's truth; clips list = the honesty ledger.
- **Look for:** viewer fitted-preview layer one-look; the 14 clips (several involve the suspect swaps and the sofa pair obj_086/obj_093 - the J4 reexamine pair that shipped as a work order); big declip moves: obj_008 door 1.78 m, obj_018 sofa 1.4 m out_of_box.
- **PROVISIONAL (Claude):** MIXED - core anchors look sane (TV wall-flush at 76 mm out-of-box, tables/shelves ~100-300 mm), but the swap-channel items and the two-sofa corner are the clip hotspots. Bedroom comparison: 15/15 clean there vs 14 clips here - most trace to swaps + the unresolved sofa pair, honest work orders either way.
- **USER VERDICT:**

## R-S2-16 - Sub-round fleet + subs preview (thin on this scene)
- **What / path:** `compose\sub_experiment\index.html` (fleet overview) + per-anchor cp7 pages; `compose\subs_preview.glb`. Totals: 11 cp7-active anchors, **12 sub items placed** (1 swap, 3 dry, 1 tile drop, 3 spills, 0 reseats/relocations).
- **Why:** hosts-before-riders; the level's truth is the fitted GLB.
- **Look for:** the overview page; NOTE the thinness vs bedroom's 37 subs - upstream cause visible in R-S2-9: recenter attached **0 children** on living (15 raw child candidates, all deduped away). Under-enrichment on this scene type = a real finding (short room -> enrichment shots fail cams? correlate with the ceiling-shot FAIL cluster).
- **PROVISIONAL (Claude):** fleet mechanics PASS; the empty child layer is the scene-2 generality finding to chase, at the source, in a design session.
- **USER VERDICT:**

## R-S2-17 - Overnight run ledger (times, cost, open items)
- **What / path:** `stage_timings.csv` (every module, wall-clock); `overnight_run.log` (raw console); commits 22d855d + 4903b26 (9-file frame-block fallback). GPU: entire night under the 1500 MHz clock lock, no crash; watchdog log `out\logs\gpu_watch.csv`.
- Chain totals: sensing redo ~8 min - graph+judges ~11 min - S1..PH1 ~7.5 min - S3/S4 ~12.5 min - fit loop+rotation+closing ~10 min - sub fleet ~9 min. END-TO-END (detect -> subs preview) ~58 min wall-clock on this hardware.
- **OPEN ITEMS FOR YOU (decisions, not tasks):** (1) W3 open-boundary ruling (R-S2-11); (2) swap-channel geometry (R-S2-14/15); (3) empty child layer (R-S2-16); (4) size-normalization design - untouched, awaits you; (5) the TV finding is now a full arc: synonym-detected -> 2 weak boxes refuted -> best box PLACED wall-flush (obj_013) - eyeball it in the viewer.
- **USER VERDICT:**

## R-S2-18 - SIZE NORMALIZATION designed + applied (scene_scale.py, NEW STAGE)
- **What / path:** `scene_scale.py` (measure via LLM class-size priors -> rescale ply/collider/frame ONCE); evidence `out\living_marble\scene_scale.json` (s=0.699, n=31, rel-MAD 0.097); originals kept as `*_prescale.*`. Design settled with user: rescale-once + LLM priors (both recommended options taken). Known caveat: f30-manifest source includes pre-judge fragments (hand-check on graph[resolved] gave 0.74); ceiling lands at 3.12 m.
- **Why:** Marble export scale varies per world (bedroom ~1.0, living 0.70); all constants are meters-tuned and shopping fits at native size - an off-scale scene poisons everything. Two-pass protocol: measure at raw scale -> normalize -> re-run in true meters.
- **USER VERDICT: PASS 2026-08-06 ("this normalization is correct") - viewer one-look of the rescaled scene; proceed to the normalized re-run.**
- Queued refinement (not blocking): move the measurement input to graph[resolved] (fragments merged, artifacts removed) once the two-pass order is drawn on the map.

## R-S2-19 - THE CLEAN RUN: bundle -> record, canonized design (supersedes all prior living sensing)
- **What / path:** one gapless run of committed code, raw bundle to graph record, 9 min 21 s total (`stage_timings.csv` C_ rows): intake 2.8s - pano 36.3s (faces rendered FRESH, fingerprint-gated) - crops - vocab - seg 143.8s - lift 6.6s - recenter 203.2s - filter - **N1 normalize 77.1s** - shell - envelope - record. Log: `out\living_marble\clean_run.log`.
- **Why:** the state before this had patch-provenance (stale-face poisoning, overwrites); user ordered a from-scratch run under the finished design. Two stale-cache source fixes (pano_stitch faces fingerprint, N1 verify-file separation) rode in commits 8b84aaf/a5ff2a9.
- **The numbers:** N1 measured **s=0.698** (n=25, rel-MAD 0.106; independently reproduces yesterday's 0.699) and applied it to ply + collider + frame + ALL manifests + lift pool + pano eye; **blind post-apply verify = 1.000 exactly** (`scene_scale_verify.json`). Doors: 2.14 m. Room: 3.13 m tall. f30: 82 objects. Record: 88 nodes / 335 edges, self-checks PASS, judged=False (judges NOT yet run - the record is the handoff under review).
- **Look for:** viewer `localhost:8321/?scene=living_marble` - boxes on furniture in the true-meter room; `scene_scale.json` evidence table; the record's SAME_CANDIDATE queue sanity.
- **PROVISIONAL (Claude):** PASS - every self-check green, verify closed at 1.000, provenance gapless.
- **USER VERDICT:** (2026-08-06) SCALE PASS - "the scale is right". NEW FINDING: some boxes outrageously large in the 3D viewer; user suspects the lift. Investigation open before judges run.
