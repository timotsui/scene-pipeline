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

## R-S2-20 - BIG-BOX FIXES + RERUN vocab->record (commit edaf972)
- **What / path:** three source fixes after the R-S2-19 forensics (whole-frame detection guard, nearest-cluster depth selection + within-cluster trim, image-word query screen), bedroom regression 150/150 max-delta 7mm, then a full living rerun V_vocab->record under the GPU clock lock (F_ rows in stage_timings.csv, 10m: seg 145s, recenter 198.6s). Log: `out\living_marble\bigbox_fix_run.log`. Old vocab/detections/f30 copied to `archive_2026-08-06_bigbox_fix\`.
- **FIXED (verified in data):** the fake-"picture" family is GONE - whole-frame members in pool: 0 (was 20+); "picture" objects 9+ -> 2 (both plausibly real); f30 90 objects. The synonym pass, now banned from image-words, did not emit "photo" at all; the query screen additionally dropped bare "picture". BONUS: the television got DETECTED this run (1 object) - the R-S2-9 undetected-TV finding may be query-composition-sensitive.
- **REMAINING (new finding, mechanism understood):** the through-glass family did NOT shrink - window [6.14,3.31,4.28], door 6.04, curtain 6.96/5.52, plant 5.35, sofa/chair ~4 m deep persist. Cause: for masks over glass/openings the splat content genuinely IS beyond the wall (no pane surface, no depth gap - a contiguous ramp), so no lift-level statistic can place the pane; the box needs WALL knowledge (shell clip / collider depth), i.e. a boundary-aware step, not a better trim. Options parked for user: (a) leave to judges + IN_WALL machinery, (b) shell-clip step post-shell pre-record (pipeline map addition - needs approval), (c) collider z-buffer clamp inside lift (new stage input - needs approval).
- **Other findings:** N1 re-measure on the cleaned pool: s=0.857 rel-MAD 0.250 n=31 -> guard DEGRADED to 1.0, scene untouched (honest; measurement noise = the queued measure-from-graph refinement). New artifact class: raw label "##tee" (GroundingDINO wordpiece of "settee") slipped the canonicalize funnel -> 1 bogus-label object; wordpiece stripping queued. Record: 96 nodes (90 det + 6 arch) / edges incl. 45 SAME_CANDIDATE; self-checks PASS.
- **Look for:** viewer `localhost:8321/?scene=living_marble` (record layer regenerated) - the fake pictures gone, chairs vs the wall behind, and the window/door/curtain monsters that remain by design until a boundary-aware fix.
- **PROVISIONAL (Claude):** PASS on the fix goals (A-family eradicated, bedroom untouched); OPEN on the openings family - awaiting user direction on (a)/(b)/(c).
- **USER VERDICT:** (2026-08-06) "much better, almost solved" + follow-up findings (obj_042 desk deep, obj_060 sofa phantom, obj_094 coffee-table phantom, obj_053 plant deep, ##tee) -> drove the directional-prior test + wordpiece/MAD fixes (R-S2-21).

## R-S2-21 - DIRECTIONAL PRIOR PROMOTED + FIRST FULL JUDGE CHAIN ON TRUE METERS (commits 49cc93c, 0d56abd)
- **What / path:** user's "only look in the vicinity" idea A/B-tested (pano2d vs pano2c: all 4 eyeballed phantoms killed, real sofa improved; USER CONFIRMED "directional is better") then PROMOTED to canonical (map node 2b pano_bearings + seg --bearings; PIPELINE.md section). Wordpiece repair in canonicalize (##tee/she/##ape -> settee/shelf/drape; bedroom 'conditioner' reunites) + MAD bound gate in group_box (n>=4, max(0.4m, 3*MAD)); bedroom regression: no box grew, 150->174 via reduced chain-merging (doctrine-aligned: merging is a judge verdict). Then the promoted chain vocab->J7 in 18m39s (P_ rows): the FIRST full judge pass on a true-meter scene.
- **The numbers:** seg with per-view terms (down to 12-23 terms/view) -> f30 -> RECENTER REFUTED 20 (vs 10 pre-fix - the photo-verifier works far better on clean boxes) -> record 65 detection nodes -> J2: 51 clusters (11 merged) -> J7: 46 shipping, 5 removed, 92 edges. Only 4 nodes with any dim > 3 m (was ~12).
- **Judge highlights:** J4 caught the 6 m "door" as geometrically impossible -> renamed GLASS DOOR (conf 0.85) - settles the door-vs-window question the prior raised, and matches the through-glass forensics. J7 removals read like a human wrote them: "outdoor hedge/greenery viewed through a sliding glass door, not an indoor plant" (the through-glass family, SEEN and articulated), chair-backrest sliver, tv-on-a-chair-leg, empty-crop weak detection. The TV arc closed: real television named vs its 3.3 m tv stand below it.
- **Still standing (size surgery = compose/fit stage's job, or future work):** obj_011 "sofa" 4.04 deep (contiguous floor bleed, same-ray class), obj_039 desk 2.40 deep (down-tilt floor bleed), obj_034 glass door box spans outdoors (flagged), obj_053 curtain 6.94 (possibly a real full-wall run - user judges).
- **Look for:** viewer localhost:8321/?scene=living_marble - the MAIN-ROW scene model (graph[resolved]) exists for living for the first time. Check: table zone clean (no phantom sofa/coffee table), obj_063 sofa compact, obj_039 desk depth, obj_034 glass-door rename, obj_053 curtain, the 5 removals under the graph-record audit layer.
- **PROVISIONAL (Claude):** PASS - the record-then-judge design did what it was designed to do on its first true-meter outing; remaining inflations are the known same-ray bleed class, correctly carried as doubt (rename candidates/flags), not silently baked in.
- **USER VERDICT:** (2026-08-06) "overall this is much better" - detailed: table zone clean; obj_063 sofa correct; obj_011 sofa REAL (long sofa; provisional's "bleed" call wrong) but a bit too long, mild class; obj_034 glass door correctly labeled, dims crazy (awaits boundary clip); NEW FINDINGS: (1) on-table streak class - obj_039 desk / obj_069 plant / obj_004 book protrude DOWN through the table and beyond its edge (forensics: down-tilt rays slip past the silhouette and run contiguously to the floor - no depth gap, nearest-cluster can't cut; needs SUPPORT-surface reasoning, compose S1/PH1 territory); (2) missing sofa middle section between obj_063/obj_011 with obj_026 pillow floating on it (pillow masks own the patch; reduced chain-merging no longer absorbs it silently - S1 should flag the unsupported pillow).

## R-S2-22 - STREAK SURGERY PREVIEWS: parallax retake (user idea) + support clip (commit f595253)
- **What / path:** deep forensics on the streak class (book mask: 41% of pixels z-buffer THROUGH the thin object - splat porosity - onto a gapless tabletop->floor ramp, max jump 6 cm; rig = ONE standpoint so no cross-view check can bound the ray axis). Two prototypes, both PREVIEW-ONLY: compose/support_clip.py (cut ON nodes at supporter surface) and experiments/parallax_retake.py (user idea: second standpoint; carve the original ray axis; v2 = point refilter - original masks' points restricted to the side-established depth slab, ALL axes re-derived; plan-B other side on failure; UNIFORM over all 46 nodes, no human-flagged suspects).
- **Numbers:** 27/46 carved (point_refilter), 17 corr_fail both sides (kept+flagged - side cams near walls/flat targets fail the 192-corr gate), 1 no_redetect (the book - chairs occlude it side-on, kept+flagged), 1 no_overlap. Key carves: desk [2.53,0.79,2.40]->[1.91,0.75,1.38] (legs+height preserved); plant ->[0.14,0.33,0.17]; window depth 2.30->1.85; floor lamp 0.88->0.42; curtain 6.94->6.54. SANITY: known-good boxes barely move (tv stand, pillows +/-3cm) - the carve is ~idempotent on clean geometry. SURPRISE: obj_063 sofa GREW 1.11->2.40 wide - the refilter re-derives from the original detection masks, which cover more sofa than the judged box; possibly the missing-middle recovery for free (user eyeball).
- **ORDER-OF-OPERATIONS FINDING:** the streaks poison support evidence - geometric edge said book ON floor (streak touches floor), and S1's witness reasoned the same ("bottom is at floor height", conf 0.65). Support semantics must run AFTER geometry repair: parallax carve -> S1 -> support_clip -> compose sizes.
- **Look for:** viewer :8321 - two new preview layers: "parallax retake · carved" (green) vs the main-row record; "support clip" (orange, wiring intentionally premature - shown for the mechanism only). Eyeball: desk, plant, window, floor lamp, curtain trim, the GROWN sofa, and whether any carve looks wrong.
- **PROVISIONAL (Claude):** the retake mechanism VALIDATED (idempotent on clean boxes, fixes the user-flagged streaks, degrades conservatively); corr-gate false-alarm rate (17/46) is the main cost - improvable via better standpoint selection/visibility checks. Promotion decision + chain wiring order await user.
- **USER VERDICT:** (2026-08-06) idea works ("much better showing the idea works") but the aimed-view selection is the weakness (missing objects; the book invisible from side views). USER DIRECTION -> the bubble-standpoint design: parallax camera near the starting eye (guaranteed clear + guaranteed visibility), full second sensing round, sets shown separately, intersect. Superseded by R-S2-23.

## R-S2-23 - TWO-STANDPOINT EXPERIMENT: full sensing round from eye+1.1m (user design)
- **What / path:** --rig/--eye-offset params added to pano_stitch/pano_bearings/pano_lift (defaults unchanged); bubble verified EMPTY in all 8 directions at 1.1 m (splat cylinder count = 0 - the generation viewpoint is wide open); offset picked perpendicular to the room's long axis (+1.1 x, scene-agnostic rule); full set-B sensing round rig_sp1 in 4.7 min (pano 37s, crops 8s, bearings 89s, seg 142s, lift 5s; 19/20 cams verified; 90 objects).
- **Set-vs-set (A=92 center, B=90 offset; greedy label-family center match):** 55 matched, 37 A-only, 35 B-only. 10 matched pairs carve >20 cm. ⭐ THE BOOK IS SOLVED BY PURE INTERSECTION: A [0.57,0.80,1.35] ∩ B = [0.42,0.08,0.51] - an 8 cm flat book on the table, no aimed view needed. A's glass-door monster and the 5.4 m plant DID NOT reproduce in B (phantom evidence); B-only includes two strong sofas (0.82/0.80 - possibly the missing middle seen properly) + the magazine family.
- **Honest caveats:** greedy 1:1 center matching is too crude - fragment matches overcarve (obj_011 long sofa ∩ one B fragment -> 0.51 wide); B's own streaks (5 m bookshelf boxes along B's rays) need the same treatment A gets. Proper cross-set correspondence = the record's SAME_CANDIDATE machinery extended across standpoints (record-then-judge absorbs multi-standpoint natively).
- **Look for:** viewer :8321 layers "set A · standpoint center" (yellow) vs "set B · standpoint +1.1x" (blue) - raw sets, no merging. Judge: do B's boxes look like the same scene seen from a step to the right; is the sofa middle present in B; which A-only/B-only objects are real.
- **PROVISIONAL (Claude):** the user's bubble-standpoint + set-intersection design VALIDATED at the evidence level; the missing piece is principled cross-set association (judge territory, machinery exists). Recommend promoting dual-standpoint sensing into the rig and feeding BOTH pools into the record as SAME_CANDIDATE candidates.
- **USER VERDICT:** (2026-08-06, after eyeballing all three surgery approaches side by side) **the aimed PARALLAX RETAKE (R-S2-22) was the most successful of the three** (vs support-clip preview and raw two-standpoint sets). Two-set experiment stays valuable as evidence (book intersection, phantom non-reproduction) but raw sets are noisier than the aimed carve. Follow-up directions: 2 bubble views not 1; NEAR-perpendicular not perpendicular (edge-on thin objects are undetectable lines).

## R-S2-24 - THE CARVE LADDER: bubble retake v2 + 65deg far escalation (commits 8117d1d, a2ff771)
- **What / path:** the promoted-design trial run: (1) BUBBLE PASS - aimed crops per node from TWO bubble panos (rig_sp1 +1.1x, rig_sp2 +1.1z, both true eye height, both bubbles verified empty), GDINO(name)+SAM per crop, each success contributing one ORIENTED LATERAL BAND (its lifted points projected perpendicular to its own ray - the only direction a view measures well); sp0 mask points filtered through all bands, box refit 1/99pct. (2) FAR ESCALATION at 65 deg off-ray (user: sin65=91% parallax, cos65=42% face visible) for bubble failures. (3) merged full-scene preview -> the green viewer layer. Three-iteration band debug on record in commit a2ff771 (axis prisms fail diagonal rays; single-view vertical constraints crush; AABB corners overstate).
- **Numbers:** 39/46 carved (32 bubble - ZERO per-object renders - + 7 far), 7 kept+flagged (corr_fail cohort incl. the glass door). Key: book [0.45,0.33,0.74] (streak cut, residual bottom = support-clip's job), plant [0.17,0.33,0.29], desk [1.91,0.75,1.40], long sofa reinterpreted [3.60,0.85,1.65] (L-arm? USER EYEBALL), second sofa [2.42,0.84,1.23] (missing-middle recovery? USER EYEBALL), tv stand/television/doors stable within cm (idempotence holds). Glass door kept 6.04 (awaits shell-clip, parked).
- **Look for:** viewer :8321, green "parallax retake · carved (preview)" layer (now the merged ladder result) vs main-row record; labels carry (carved bubble xN / carved far / kept: reason). Judge especially the two sofas and the book.
- **PROVISIONAL (Claude):** the ladder is the promotable design - bubble-first (cheap, visibility-guaranteed), oriented point bands (trust only what each view measures), far 65deg escalation, conservative keeps. Cost ~6-8 min/scene, mostly detector calls. NEXT after user pass: promote to map (sensing gains sp1/sp2 pano stages; repair stage between J7 and S1), then S1 -> support_clip -> compose on carved geometry.
- **USER VERDICT:** (2026-08-06) ladder judged WORSE than the first retake (bubble "successes" replaced strong far carves with weak 20-30deg ones and blocked escalation). USER DIRECTION: first-retake method as primary but "more than 1 extra retake" -> v3 COMPOSE (commit c08755c): both 65deg far sides ALWAYS run + bubble bands folded into ONE point refilter; keeps only when zero views verify.
- **v3 RESULT:** 38/46 carved, 8 kept. Book [0.45,0.33,0.74] (bubble bands), plant [0.11,0.34,0.15], desk [1.90,0.75,1.31], sofas [3.33,0.85,1.62]/[2.12,0.84,1.10], curtain 6.94 -> 2.42, television/doors/bookshelves all plausible. Superseded same evening by the POOL design below.

## R-S2-25 - POOL RETAKE (user design, commit 4c9e7f8) - THE STANDING PREVIEW
- **What / path:** per node a CANDIDATE POOL: 4 near-cardinal (20 deg off-axis - exact cardinals hit axis-aligned thin objects edge-on) + 1 near-top (footprint king: both image axes horizontal -> two bands) + 2 near-perp (65 deg); GENERAL cull, no special-cased views (user rule): out-of-shell-bounds or non-empty eye sphere dies - the bottom view dies naturally below the floor. Candidate eyes live in the walkable air layer (standing height, where rooms are empty). Verified survivors contribute HORIZONTAL point-bands only (vertical = support_clip's job); one refilter composes all. Calibrations on record: corr gate 0.12 for defined-convention renders (0.25 punished flat tabletops), emptiness 1500 pts (cull looser than verifier).
- **Numbers:** 33/46 carved, 13 kept. ⭐ book [0.38,0.07,0.33] - a real 7-cm flat book, best carve of the day (top view footprint + horizontal filtering let the TRUE thickness emerge with zero vertical constraints); plant [0.17,0.33,0.29]; desk [1.72,0.74,1.41]; long sofa [1.84,0.85,3.24] (long-in-z again, nearer the user's own description than v3's L-reading); floor lamp recovered (was kept in v3); curtain 3.22; glass door still the one kept monster (shell-clip parked).
- **Look for:** viewer green layer (pool result now) + retake_views.html (rebuilt: 7 columns per object - green contributed / red failed / grey culled). Judge: the two sofas (readings differ across v3/pool!), curtain length, and whether any carve overshot.
- **PROVISIONAL (Claude):** this is the promotion candidate - user-designed end to end (multi-view pool, near-X angles, general cull), best per-object numbers, honest keeps. Costs ~25 min/scene unpruned; visibility-planner pruning is the queued optimization.
- **USER ITERATION (same evening, commits 73134e4 + 548b0c5):** good-lens rule (fov 55, distance derived) + cardinals 20->10 deg + CLIP-TOP plan view (ceiling clipped from the splat, camera above the roof, unclamped stand-off - fires when the in-room top is culled OR the object cannot fit the frame) + OBJECT-CARDINAL camera heights (object height first, cull arbitrates upward - was too "eye level") + EDGE-TRUST bands (a frame-clipped detection side contributes no bound - the "extends beyond one square" fix) + per-view detection overlays saved for the evidence page.
- **⭐ THE PLAN VIEW SETTLED THE SOFA:** obj_011_ctop shows an L-SECTIONAL - the two record sofa nodes are its two arms; the "missing middle + floating pillow" is the L-corner. USER RULING (best-recommendation delegated): keep two honest arm boxes + judged PART_OF_STRUCTURE linkage via the queued multiplicity judge - NO hand-wired edge (scene-specific pin would violate Rule #1).
- **FINAL NUMBERS (pool_full3):** 34/46 carved, 12 kept (6 empty-overlap = views disagreeing, mostly repeated-class mismatches - band-majority-vote queued). Sofa arms [2.48,0.84,1.66]+[2.42,0.84,1.23] (consistent at last), book [0.38,0.07,0.33], plant carved with 6 agreeing views (object-height cameras fixed the wrong-plant match), desk [1.75,0.74,1.41], floor lamp recovered. Curtain wobbles across runs (6.9/2.4/3.2/6.2 - genuinely ambiguous, judge territory). Glass door unchanged (shell-clip parked). Evidence: retake_views.html - 144 annotated views (render + detected box + mask per view).
- **USER VERDICT:** SUPERSEDED without a formal pass/fail — the next session (the cone-map session, R-S2-26) rebuilt the carve design from the cone evidence; the pool retake's k-rule question was answered there by the slice-vote election.

## R-S2-26 - THE CONE-MAP SESSION: slice-vote carve designed + promoted UNTESTED (no commits yet)
- **What / path:** the k-rule calibration session, run as ~10 rapid user-driven experiments on 8 objects (sofas obj_011/obj_063 + all 6 chairs). Full lineage in docs/CARVE_SLICEVOTE.md. Landed design (all USER rulings): slice = TOP-BOX VERTICAL PRISM (plan-view detection box, corners cast across the object's height band — ceiling-to-floor casting smeared the tilted beam ~0.7 m, user-traced on obj_041/obj_020 — margin min(30%, 0.35 m)/side CAPPED (user: margins must not scale with big boxes); fallback = original-box wedge, full height) → slice rendered ALONE (subset .ply, real WSL renderer; CPU renders judged "horrible" and they defeated the detector 6/8) → 6-VOTER ELECTION: 4 near-cardinals on the isolated renders + the top view's mask + the original standpoint (union of member masks = ONE voter — same-eye crops must not corroborate each other) at USER GATE 3 VOTES → anchored cluster, culled clusters recorded.
- **Key evidence findings along the way:** (1) the old coalition's "dropped views" mechanics exposed — chair obj_068 splits into two 0.98-internal/0.00-cross factions (wrong instance), decided by a hair with zero correctness knowledge; (2) any-2 voting over NEUTRAL splat points explodes (obj_063 5×6 m — cones always cross somewhere); (3) USER FOUND a member mask that segmented FLOOR wearing a "sofa" label (pm40 crop) — no pipeline step ever re-checks a mask against its label; (4) gate 3 killed both the degenerate-ballot blowup (a camera claiming 255,347/255,378 dots) and obj_028's unstable-detection regression; (5) detection instability MEASURED: a marginally different render flipped a card's claims 2,281 → 26,308.
- **8-object numbers at gate 3 (orange boxes):** obj_011 2.97×0.86×3.21 (wraps the whole L — known, arm assignment is the answer), obj_063 2.77×0.85×1.51, obj_068 1.27×0.58×0.81, obj_010 0.98×0.50×0.61, obj_020 1.25×0.49×0.60, obj_021 0.48×0.93×0.43, obj_028 0.55×0.89×0.47, obj_041 1.14×0.80×0.60. Some chair heights look shaved (0.49/0.58) — partial-silhouette risk at the stricter gate, USER TO JUDGE.
- **PROMOTED (⚠ ALL UNTESTED, banners in every file):** carve_slicevote.py (the stage, incl. per-node ARM ASSIGNMENT for the L problem — each node keeps vote survivors its own sp0 masks vouch for, thin-coverage fallback, <50%-volume flag; mechanics-verified on the 8, statuses {'carved_arm': 8}) + graph/record_carve_doubts.py (USER RULING: doubts RECORDED never decided — typed open questions arm_vs_cluster/culled_clusters/slice_fallback → graph/carve_doubts.json sidecar; 6 living nodes emitted) + graph/judge_same_product.py (USER RULING: same-product = its OWN graph-chain pass, NOT inside the multiplicity judge; judge-chain claude.exe pattern, carve doubts ride as context; grouping dry-run verified — finds the 6-chair group — LLM VERDICTS NEVER RUN, shopping NOT wired; compose/uniform_instances.py = superseded first draft). Map/docs: dashed UNTESTED node + card on pipeline_map.html between the graph handoff and S1; PIPELINE.md contract section. Viewer: cone-map layer (temporary) with isolation dropdown, per-view cone coloring, legend, arm box; set A/B layers retired (user).
- **Look for:** cone_map.html (slice → voters → claims → boxes per object) + the viewer cone-map layer + scene_manifest_slicevote_preview.json.
- **PROVISIONAL (Claude):** the design converged and each fix traced to user-diagnosed evidence; UNTESTED discipline held (no bedroom run, no map/promotion, preview outputs only). Biggest doubts: shaved chair heights at gate 3, arm assignment inherits junk-member-mask risk, detection instability now measurably in the loop.
- **USER VERDICT (2026-08-06, next-day session):** PASS with routed caveats (see R-S2-27 for the whole-scene run this cleared) — (1) obj_011 L-wrap acknowledged; the answer stays the recorded carve doubts → description pass → multiplicity judge (PART_OF_STRUCTURE, still unbuilt); (2) shaved chair heights accepted as splat-quality damage, expected catch = downstream compose snap/supported-by (bottom-to-floor) — "sometimes objects are obscure"; (3) same-product judge confirmed as the matching-chairs answer (grouping verified, verdicts still never run, shopping unwired); (4) BEDROOM REGRESSION WAIVED by user ("we don't run bedroom again, that's ok"). Cleared to run the carve on living_marble whole-scene (full resolved set), output stays preview.

## R-S2-27 - FULL-SCENE SLICE-VOTE CARVE, living_marble (blind run 2026-08-06 evening)
- **What / path:** first whole-scene run of carve_slicevote.py (gate 3, res 768), cleared by the R-S2-26 user pass + user waiver of the bedroom regression. 44/82 resolved nodes processed (the stage's working set), statuses {carved_arm: 32, carved: 12}. Log: out/living_marble/slicevote_full_run.log. Two launch-env false starts (wrong out/ root; cp1252 UnicodeEncodeError on the ≥ progress print under redirected stdout — fixed with PYTHONUTF8=1 at launch, no code change). GPU under the persisting 1500 MHz clock lock (no reboot since the 02:xx recovery lock).
- **Headline numbers (arm-box vs original volume):** 5/44 ended below half original volume (incl. obj_004 book ×0.13, obj_068 chair ×0.20 — both <50%-of-cluster flags, multiplicity-judge territory; obj_018 ceiling light ×0.04). BLOWUPS: the ceiling-light class explodes — obj_023 ×5027, obj_031 ×4196, obj_008 ×3242, obj_045 ×2786, obj_027 ×860, obj_030 ×288 — every one with "sp0 coverage too thin → arm fallback to cluster"; obj_002 picture ×373 (FALLBACK WEDGE, no ctop detection). Wedge fallbacks also obj_000 door, obj_014 bookshelf (26 sp0 boxes, no ctop detection).
- **EVAL FINDING (recorded, not fixed — Rule #1 blind-test protocol):** the slice height band assumes floor-standing objects (prior top − 0.3 m down to the FLOOR). For ceiling-mounted objects that slices the entire room column beneath the fixture, the vote then wraps furniture below, and thin sp0 coverage falls back to that giant cluster. Same class of finding as the glossy-TV note: goes in the eval notes; any fix (e.g. a height band anchored to the prior's extent rather than the floor) is a design decision for AFTER the test, user-gated.
- **Look for:** cone_map.html (now 44 objects), the viewer :8321 cone-map layer (reload; label auto-counts), scene_manifest_slicevote_preview.json, pool_retake/slicevote_report.json.
- **PROVISIONAL (Claude):** furniture-scale repair looks like the 8-object session promised (sofas/chairs/plants tighten, obj_011 L-wrap persists as expected, flags fire where they should). The stage as-is is NOT safe to wire for ceiling-mounted / wall-mounted classes — the blowups would ship straight into compose. Recommend gating wiring on resolving the height-band finding.
- **USER VERDICT:** (pending — object-by-object in the viewer)

## R-S2-28 - CARVE RERUN with view tunnel + ceiling exemption (2026-08-06 night)
- **What / path:** full living rerun after three USER-RULED design changes from the R-S2-27 review: (1) VIEW TUNNEL cards (user design, superseding a backdrop-only variant mid-session): each card renders the FULL scene minus gaussians that are in the camera cone, nearer than the slice, and not slice members — occluders culled, side/background context intact; claims still counted on slice dots only; (2) CEILING EXEMPTION, geometric (top within 0.35 m of shell ceiling + bottom in upper half of room; no label lists): status kept_ceiling, resolved box verbatim; (3) card re-detect gated to the slice's projected screen box (prior_box, same mechanism as the top view) so backdrop same-class objects can't be picked. Render caches wiped before the run (geometry change). Log: slicevote_full_run2.log.
- **Statuses:** {carved_arm: 32, carved: 3, kept: 2, kept_ceiling: 7}. All 7 ceiling lights exempted — the x288–x5027 blowups are GONE from the manifest.
- **Signals, honest both ways:** no_redetect went 6 → 16 (context makes the card detector fail more often — voter availability regression); 2 elections came up EMPTY (obj_004 book, obj_038 window → original box kept, status 'kept'), where run1 still produced boxes; card claims can collapse with context (obj_068 card0: 15,126 → 2 dots — SAM segments backdrop inside the box; the gate absorbs it but a voter is lost). Chair heights partly recovered (obj_028 0.89, obj_020/041 0.85, obj_068 0.73 vs run1's 0.49/0.58 shave) BUT new thin boxes appeared (obj_010 height 0.26; obj_020/041 z ≈ 0.22). obj_002 picture STILL x369 (wall-flush case — un-ruled, the ceiling test doesn't cover walls). Sofas: obj_011 2.81x0.85x3.31 (L-wrap persists, multiplicity judge's case), obj_063 1.85x0.83x1.36.
- **Look for:** cone_map.html (cards now show the tunnel renders — occluders gone, context visible), viewer :8321 cone-map layer (37 voted objects; 7 exempt listed in the page header), scene_manifest_slicevote_preview.json.
- **PROVISIONAL (Claude):** context is a double-edged sword as measured — it restored chair height where silhouettes were starved, at the cost of noisier voter behavior on small/thin objects. The ceiling exemption did exactly its job. Open design questions for the user: wall-flush objects (obj_002), the no_redetect rise, and whether 'kept' (empty election) should fall back differently.
- **USER VERDICT (2026-08-06/07, via the design dialogue):** effectively PASSED by ruling on its opens — "the picture is the big problem" → wall-flush exemption + outlier guard (run 3, R-S2-29); the empty-election book → isolation fallback + eye-height escalation ladder (run 4, R-S2-30).

## R-S2-29 - CARVE RUN 3: wall-flush exemption + outlier guard (2026-08-06 ~23:43, 15 min)
- **What / path:** full living rerun under the complete rule set after two more USER RULES from the R-S2-28 review ("the picture is the big problem — anything can be a picture"; "fall back on the original lift when the new one is much bigger"): (1) WALL-FLUSH EXEMPTION, geometric (within 0.20 m of a measured shell wall plane AND < 0.30 m thin along its normal) → kept_wall, resolved box verbatim — pictures have no plan footprint, so the top detection can't start and the full-height wedge slices a room column; (2) OUTLIER GUARD OUTLIER_K=8: a shipping box > 8x the original volume ships the ORIGINAL instead (kept_outlier), oversized vote box recorded as doubt. Log: slicevote_full_run3.log.
- **Statuses:** {carved_arm: 27, carved: 2, kept: 1 (obj_004 book, empty election), kept_wall: 8, kept_ceiling: 7}. Outlier guard fired ZERO times — the exemptions removed every pathological case before the backstop was needed. Remaining >3x growers shipping (all under the 8x guard): obj_021 chair x5.2, obj_029 magazine x4.8, obj_032 magazine x6.5.
- **kept_wall roster (user should sanity-check):** obj_000/obj_001 doors, obj_002 picture, obj_033 television, obj_038 window, obj_053 curtain — all expected classes; PLUS two surprises: obj_017_c00 magazine and obj_022 plant went wall-flush-thin. Conservative failure mode (they keep their resolved boxes), but eyeball whether their originals are really wall-slivers.
- **Look for:** cone_map.html (exempt roster in the header; 29 voted objects), viewer :8321 cone-map layer, scene_manifest_slicevote_preview.json (statuses + doubt flags per object).
- **PROVISIONAL (Claude):** the exemption+guard combination did what it was designed to do — no blowup ships, every fallback is recorded, and the guard exists as a backstop for scenes where the structural tests miss. Carried opens: no_redetect rise under context (16), obj_004 empty election, the two surprise wall exemptions, thin boxes from R-S2-28 (obj_010/020/041) unchanged.
- **USER VERDICT (2026-08-07):** PASS — "i think this is good"; next instruction: put the slicevote boxes into the 3D viewer.

## R-S2-30 - CARVE RUN 4: detection escalation ladder (2026-08-07 early, ~20 min)
- **What / path:** full living rerun after the USER-DESIGNED escalation ladder landed (post R-S2-29 pass, viewer wiring done): TIER 1 context cards at object height -> TIER 2 when >=3 of 4 cards are unproductive (no detection or <50 claimed dots): add 4 EYE-HEIGHT cardinal tunnel cards as extra voters (user rationale: Marble is biased toward eye-height capture, so splat quality AND detector priors are strongest there) -> TIER 3 empty election: isolation retry (slice on black, run-1 mode) -> TIER 4 original box (kept, recorded). Tiers recorded per object in rule.tiers; eye/iso cards have own colors in the cone map. Log: slicevote_full_run4.log.
- **Statuses:** {carved_arm: 28, carved: 2, kept_wall: 8, kept_ceiling: 7} — ZERO 'kept' left: every non-exempt object now carries a carved box.
- **The book (obj_004), the ladder's first customer:** object-height cards 0/4 productive -> eye-height 4/4 DETECTED (0.22-0.63, claims 479-2,434) -> election of 8 voters -> 0.40 x 0.08 x 0.47 m — an actual flat book. Isolation tier never needed by any object; exactly ONE object escalated scene-wide. The eye-height hypothesis is empirically confirmed on its first test.
- **Look for:** viewer :8321 slice-vote layer (reload; book box now real), cone_map.html obj_004 row (escalation note + eye-height cards in the strip).
- **PROVISIONAL (Claude):** the ladder is cheap (one extra render round only for objects that need it), fully recorded, and fixed the last non-exempt failure. Carried opens unchanged: thin boxes (obj_010/020/041), two surprise wall exemptions (obj_017_c00 magazine, obj_022 plant), sofa L to the multiplicity judge, same-product verdicts unrun. NOTE: object count is 45 since run 3 (44 before) — the exemptions catch an object that previously died silently at the <100-dot skip; benign, but the count delta should be understood before wiring.
- **USER VERDICT (2026-08-07):** PASS ("awesome") — session wrapped on this. Next directive: keep running the carved output ALONG THE PIPELINE (downstream consumers). Commit remains the user's call; nothing committed.

## R-S2-31 - DOUBTS INTO THE RECORD (description pass) + same-product grouping rerun (2026-08-07)
- **Module contract:** record_carve_doubts.py --apply GETS pool_retake/slicevote_report.json (run 4) + the preview manifest's status flags; it DECIDES nothing — it types the carve's open questions (arm_vs_cluster / culled_clusters / slice_fallback / NEW: exemption) into mechanical plain-English sentences and writes them (a) to the graph/carve_doubts.json sidecar and (b) into scene_graph.json as the ADDITIVE top-level `carve` block (45 nodes, statuses+tiers+slice provenance; nodes/judged/resolved untouched — verified 46/92 resolved, 71 record post-write). A mistake looks like: a doubt on the wrong node, a sentence misdescribing its numbers, or any change to the existing layers.
- **What ran:** (1) doubts rerun on run-4 (stale pre-run-2 file replaced): 13 auto-doubt nodes; with exemptions recorded, 28 nodes carry entries. (2) --apply wrote the carve block; viewer :8321 card now shows carve status/tiers + orange doubt lines when a resolved box is clicked (index.html). (3) USER-ROUTED list added to the block: obj_011 L-sectional -> multiplicity judge (R-S2-26 caveat) — recorded because run 4's arm box did NOT trip the auto 50% rule (ratio above threshold), so the routed case would otherwise vanish from the docket. (4) judge_same_product.py --dry-run on current data: 6 groups — chairs x6 (obj_010/020/021/028/041/068), pillows x9, ceiling lights x4 + x3, magazines x3 (obj_029/032/036, anchor obj_012 bookshelf) + x2 (obj_005_c00/obj_017_c00). LLM verdicts still NOT run.
- **Notables for the user:** chairs group has anchor=None (design expected the table as shared anchor — the 2x-footprint rule found nothing; may matter for the verdict prompt's context). 3 bookshelves each carry slice_fallback (no top detection — plan-view starved class). obj_034 glass door has a culled cluster (possible second instance).
- **Look for:** viewer :8321 -> scene model layer -> click obj_021 chair / obj_011 sofa / obj_012 bookshelf — the card's carve lines; graph/carve_doubts.json; the dry-run group list above.
- **PROVISIONAL (Claude):** the record now carries everything the two new judges need except the judges themselves; nothing decided anywhere (Rule 1 clean: exemptions recorded not filtered, user-routing labeled as user verdict provenance). Open: whether exemption entries on all 15 kept_* nodes is the right grain or too chatty for the card.
- **USER VERDICT:** (pending)

## R-S2-32 - RULE-1 CORRECTION: user-routing channel removed (2026-08-07)
- **What happened:** R-S2-31's doubts pass included a hardcoded USER_ROUTED table in record_carve_doubts.py (obj_011 -> multiplicity, from the R-S2-26 caveat) and the J8 docket consumed it. USER CALLED THE FOUL: the pipeline must expect no human intervention — a scene-keyed routing table in pipeline source is a human answer baked in (same family as the R-S2-26 "NO hand-wired edge" ruling).
- **Correction (same session):** channel deleted from record_carve_doubts.py + judge_multiplicity.py + viewer card + map cards; carve block re-applied (45 nodes, 28 doubts, no user_routed key); J8 sheets rebuilt = 8 AUTO cases (obj_011 out).
- **Standing consequence:** obj_011's L-question is an HONEST MISS on the eval ledger — the auto rules (arm<50%, culled clusters) do not fire on it. If downstream ships a wrapping sofa box, that is the blind-test result. Rule-design CANDIDATE recorded in PLAN_CARVE_DOWNSTREAM (vote-dot fill-fraction of the AABB — from the failure mode, not the instance); adopting it is a user-gated design decision.
- **USER VERDICT:** (this entry IS the user's correction; recorded)

## R-S2-33 - EVAL FINDING (parked by user): obj_081/obj_009 chair false-rejection (2026-08-07)
- USER EYEBALL: "there is a chair. i can see it" at the obj_081 location — J6/judge_cases ruled obj_081 NOT_REAL ("no discernible object", conf 0.7, v2 evidence pack) and obj_009 NOT_REAL as "nested in another chair" (the only containing box = obj_081 at 0.98 — the two reasons do not compose). Detection facts: obj_081 single view, score 0.359, edge-truncated 238x76px strip; obj_009 four views, tiny sliver box.
- CONSEQUENCE IF REAL: room has 7 chairs not 6; same-product chair group missing a member; an existence-judge false-rejection mode on edge-truncated weak single-view crops.
- USER RULING: "not the biggest fish right now" — PARKED, no fix, no re-litigation; goes to the eval notes. Any fix is a scene-agnostic design decision at a future gate.
- **USER VERDICT:** recorded (this entry is the user's finding + parking decision)
- **ADDENDUM (user insight, same session):** design gap named — with same-product context ("6 matching chairs exist; this sliver matches the product") + the position fact (obj_009 overlaps NO surviving chair; its only container was its co-accused obj_081), the existence verdict plausibly flips to REAL-obscured-instance. Two Rule-1-clean design candidates recorded in PLAN_CARVE_DOWNSTREAM: (1) instance-context facts in existence dockets (overlap-with-surviving-same-class + scene instance count — position discriminates duplicate vs new instance); (2) J7 verdict-dependency check (kill-reason referencing a removed node -> case reopens UNCLEAR — obj_009/obj_081 were two suspects vouching against each other). NOT implemented; parked with the finding.

## R-S2-34 - SHELL FILTER + kept_floor + PLAN-FILL RULE 3 ADOPTED; RUN 5 LAUNCHED (2026-08-07 late)
- **The arc (all user-driven):** L-notch floor finding (user: "a lot of the floor framed by the L was categorized as sofa — the projection will almost certainly hit those points"; root cause = ray-volume claims have no depth test) → USER RULED: shell electorate filter + kept_floor exemption (rugs/mats protected geometrically, "as long as we are not fucking with stuff legitimately on the floor") → sofa-only experiment (run-4 canon backed up + restored; --only clobber gotcha respected) → scene-wide plan-fill census → RULE 3 ADOPTED at 0.65.
- **Sofa experiment numbers:** 103,369/243,557 slice dots (42%) shell-ineligible; elected box essentially unchanged (2.98x0.84x3.19 -> 2.98x0.78x3.16) — the 3-vote gate was already absorbing most notch-floor dots; AABB over an L is pinned by the arm tips (electorate hygiene cannot fix shape). Experiment artifacts: pool_retake/sofa_floorfilter_experiment/ (cone_map.html img paths rewritten to ../ for direct opening). ⚠ obj_011's shared conemap figure PNGs were regenerated by the experiment (data JSONs restored; run 5 regenerates all coherently).
- **Plan-fill census (run-4 data, 30 voted objects):** glass door 0.14, L-sofa 0.58 | GAP | 0.73..1.7 everything else (straight sofa 0.90, chairs 0.76-1.7, tables ~1.1). Natural break 0.58|0.73; threshold 0.65 in open water; admits EXACTLY the two known shape problems, zero false admissions. Contamination disclosed (rule conceived on the sofa) — adopted on the failure-mode + blind scene-wide measurement + open-water threshold standard.
- **Code landed (uncommitted):** carve_slicevote.py (kept_floor exemption; SHELL_EPS=0.03 electorate filter — votes zeroed at tally, renders/caches untouched; plan_fill recorded per object; census in log+rule) · record_carve_doubts.py (low_plan_fill doubt kind at <0.65) · judge_multiplicity.py (docket admits low_plan_fill).
- **RUN 5 LAUNCHED** (full scene, caches warm): out/living_marble/slicevote_full_run5.log. After it: doubts --apply rerun -> docket regenerates (sofa on it BY RULE — the legitimate route back after the R-S2-32 Rule-1 correction) -> sheets rebuild in the redesigned form.
- **OPEN AT USER (next session):** the J8 ask redesign — 5-outcome taxonomy (ONE_OBJECT / ONE_OBJECT_NONRECT mechanical rect-decomposition / MULTIPLE_COPIES count-semantics / MULTIPLE_DISTINCT ownership / UNCLEAR) + two sub-decisions: (a) code-cuts-rectangles vs judge-names-parts; (b) copies-vs-distinct tiebreak (prefer COPIES for same-product parts). Proposed, NOT signed off, NOT built.
- **USER VERDICT:** rulings above recorded (shell filter, kept_floor, rule 3 = PASSED by direction); run-5 output + new docket + taxonomy = pending next session.
- **RUN 5 RESULT (post-wrap addendum, overnight):** clean, 45 objects, statuses identical to run 4 (28 arm / 2 carved / 8 wall / 7 ceiling; kept_floor fired 0x — nothing floor-flush in living). ⚠ CALIBRATION FINDING: the in-pipeline plan_fill (FULL elected set) reads systematically higher than the subsampled census the 0.65 threshold was drawn from — obj_011 = 0.85 (census said 0.58), mid-pack between pillows, NO natural break; only obj_034 glass door fires (0.36). Root cause: at full density, stray single dots mark notch voxels occupied; the subsample was accidentally a density filter. RULE 3 AS LANDED DOES NOT CATCH THE L — recorded, NOT retuned (tuning the threshold while staring at the sofa = answer-key contamination). Refinement candidate for the user gate: density-weighted occupancy (cell counts occupied only at >= k dots) — principled version of what the subsample did by accident. Run-5 docket = 7 cases (obj_021 chair dropped off: its arm ratio rose above 0.5 under the shell filter; obj_011 still off-docket = the honest miss stands).

## R-S2-35 - PANO-MASK RENAME + 4 CARVE FIXES + RUN 6 + large_empty_notch ADOPTED: THE L IS ON THE DOCKET BY RULE (2026-08-07 late)
- **Vocabulary (user):** "arm" family renamed to PANO MASK terms — pano masks = the node's founding masks from the original pano-funnel views (rig_sp0 crops), vs the carve's fresh identity-blind card detections. carved_arm→carved_pano, arm_vs_cluster→pano_vs_cluster, arm box→pano-filtered box. Code+viewer+map+living docs; historical records verbatim; readers accept both spellings (run-5 data still loads).
- **obj_014 bookshelf wall-leak (user finding, cone map):** boxes included wall chunks left+right and poked 23-52 cm THROUGH the wall plane. Diagnosis from recorded data: (1) the ±eps electorate band RE-ADMITS dots behind the wall (abs test); (2) FALLBACK WEDGE slice cast from the wall-poking original box put a wall slab on the ballot; (3) in-front wall fuzz beyond 3 cm survives; (4) 26 broad pano masks can't trim. USER RULED: fix at source.
- **4 carve fixes (user-approved batch, subagent-applied per the new delegation rule, diff-reviewed):** (a) HALF-SPACE shell electorate filter — at-or-behind a shell plane (minus SHELL_EPS) is structure, one-sided test; (b) SLICE SHELL CLAMP — a slice may never extend past the measured shell; (c) pano filter intersects the WINNING BLOB only (culled-blob dots out of the share comparison); (d) PLAN-FILL v2 recorded (winning-blob dots, cells clipped to footprint = true 0-1, per-cell dot-count histogram in the report for offline calibration). Legacy plan_fill untouched as the live doubt trigger.
- **RUN 6 (all 293 card renders wiped — slice geometry changed; ~19 min):** statuses {carved_pano 27, carved 3, kept_wall 8, kept_ceiling 7}; ONE shipping-path change scene-wide (obj_034 glass door pano→vote: sp0 share thinned under the winning-blob restriction). obj_014 FIXED: vote box stops at the wall plane minus eps (x hi 2.844→2.630), left/right wall chunks gone (z −0.24..1.51 → 0.08..1.03), fill v2 = 1.0, no flags. Run-5 canon backed up first: pool_retake/run5_canonical_backup/.
- **PLAN-FILL v2 K-SWEEP = HONEST NEGATIVE:** at every k (1-10), obj_011 (0.68-0.70) sits ABOVE pillows/tv stand (0.53-0.66) — small round objects naturally underfill their AABBs. NO global fill threshold isolates the L; the run-5 density-weighting hypothesis is REFUTED on full data.
- **large_empty_notch ADOPTED (user: "lets move on / are we flagging the L"):** largest contiguous empty axis-aligned rectangle in an object's own plan footprint (occupied = cell with >= NOTCH_K=2 winning-blob dots) >= NOTCH_M2=0.50 m² fires a multiplicity doubt. Blind scene-wide census (run 6, 30 objects): obj_011 sofa 1.52 m² | GAP 8.4x | desk 0.18 | tv stand 0.12 | rest <= 0.10; robust to k (identical at k=1). Disclosure: metric conceived from the sofa's failure mode; adopted on the blind census + open-water standard (R-S2-34 precedent). Physically: the notch is where the L's missing limb would park. Wired: record_carve_doubts.py (helper + emission w/ notch_m2, rect_cells, rect_m payload) + judge_multiplicity.py docket admission.
- **DOCKET (run 6, 5 cases):** obj_011 sofa (large_empty_notch — ON BY RULE, no hand-routing, Rule #1 clean) · obj_019 pillow, obj_021 chair, obj_029 magazine (pano_vs_cluster) · obj_032 magazine (culled_clusters). Dropped vs run 5, all mechanical: obj_024/obj_042/obj_068 (ratios moved under winning-blob filter), obj_034 glass door (fill 0.36→1.167/1.0 — half-space+clamp cleaned its election; LOOK-FOR: eyeball the door's box).
- **Review artifacts:** notch_review.html (census table + per-object plan grids, threshold line, notch rectangle drawn) at out/living_marble/; cone_map.html + viewer :8321 serve run 6; scene_graph carve block re-applied (26 nodes with doubts).
- **PROVISIONAL (Claude):** run-6 status stability + the single-object docket entry match intent; biggest doubts: obj_034's cleaned election unverified by eye, in-front wall fuzz (cause 3) only mitigated not eliminated, notch rule tested on ONE scene. USER GATES OPEN: run-6 visuals eyeball (obj_014, obj_034, obj_011), notch-rule read-back on notch_review.html.

## R-S2-36 - AUTONOMOUS RUN-UNTIL-J8 (user AFK, authorized): loop-back B2 + J0/J1 + J8 v2.1 CANONICAL VERDICTS (2026-08-07 late)
- **Authorization:** user parting order "run until j8, prepare the review pages and viewers" + mid-run "improve known qualities as you go" (both saved as standing memory rules). Everything below = verdicts REFERENCING nodes; canonical layers untouched; NOTHING materialized; commit pending user order.
- **Loop-back built + run (Phase B2):** build_edges.py refactored (derive_edges() extracted, regression = field-identical re-derivation of the record); NEW graph/rederive_carved_edges.py wrote additive graph["carved_edges"] (46 resolved nodes x carved boxes verbatim from the preview manifest; obj_005_c00 uncarved; 84 edges; self-check PASS; backup scene_graph_pre_carved_edges.json.bak). GATE-B2 DIFF: 21 appeared / 24 dissolved — findings: obj_020↔obj_041 chairs CONFIDENT same-candidate (IoU .818); obj_034 door wall-flip z_high→x_low + lost ATTACHED + 97.7% inside obj_014; obj_021/obj_068 chairs ON-floor → NEAR-floor gaps .29/.46 m (shaved bottoms — compose-snap case); INTERPENETRATES 18→9.
- **J0/J1 on the layer** (--edges-from carved_edges wired): J0 20 items → 2 nominated; J1 4 verdicts — obj_013↔obj_048 SAME .75, obj_020↔obj_041 SAME .75 (duplicate chair; merges pending materialize), obj_034↔obj_014 DISTINCT .95, obj_019↔obj_048 DISTINCT .62.
- **J8 v2.1 landed** (per the adopted design): facts READ from carved_edges (private overlap list deleted; same-class facts never truncated; J1 verdicts quoted on fact lines), GREEN same-class neighbor wireframes on all panels (obj_063 drawn on obj_011's 5 panels), ONE_BOX|SPLIT|UNCLEAR prompt, parser v3 (14 hand cases pass). Agent-resolved design details flagged for review: relevance tiers for the 8-line fact cap (SC > arch/support > volume), class key = case-folded name, fatal-if-no-carved_edges.
- **CANONICAL J8 VERDICTS (5/5, sonnet):** obj_011 SPLIT/one_structure parts this_node+existing:obj_063 conf .72 (THE L RESOLVED — both sofa nodes keep their limbs; PART_OF_STRUCTURE + mechanical rectangle cut at materialize) · obj_019 ONE_BOX/ship_pano .72 (trial's MULTIPLE_DISTINCT restated cleanly once J1's DISTINCT fact was on the sheet) · obj_021 ONE_BOX/ship_pano .72 · obj_029 ONE_BOX/ship_pano .78 (vote box spanned two shelf compartments) · obj_032 ONE_BOX/either .72.
- **Known-qualities improved en route:** viewer now surfaces J8 + J1 verdicts on node cards (serve.py /multiplicity.json route; card lines with fly-to id links; restarted pid 12964, route 200).
- **Review surfaces for the user:** out/living_marble/loopback_j8_review.html (the catch-up page: B2 diff + J0/J1 + J8 cards + links) · graph/multiplicity_sheets/index.html (v2.1 sheets w/ green neighbors) · viewer :8321 (refresh).
- **PROVISIONAL (Claude):** the L outcome matches the user's own prior eyeball (R-S2-26 era) and the obj_019 pair of verdicts (J1+J8) is internally consistent; doubts: all J8 confidences cluster .72-.78 (low spread — watch for anchoring), obj_029's two-compartment claim and obj_021's ship_pano are unverified by eye, the obj_020/obj_041 SAME merge is consequential (removes a chair) and deserves the user's look at the J1 crops. USER GATES OPEN: Gate A2 (5 J8 verdicts vs their sheets), B2 findings eyeball, then Phase C materialize design.

## R-S2-37 - GLASS-DOOR ROOT CAUSE -> PROTRUSION RULE + SHELL CLIP + NEVER-SILENT FIX (runs 7-8, live review 2026-08-07 late)
- **USER FINDING (cone map):** the glass door is invisible in obj_034's carve tiles. CONFIRMED mechanism: the door's entire dot mass sits at-or-beyond the wall plane (resolved box x 2.844..8.884 vs wall 2.661 — 100% outside; the "depth" is the outdoor view through the glass), so the run-6 slice clamp + half-space filter disenfranchised every door dot; the detector then latched onto the nearest interior structure and the door's box landed on the bookshelf (run-6 vote box == obj_014's carved footprint; the wall-flip/lost-ATTACHED/inside-bookshelf edges were all artifacts). J1's DISTINCT crop verdict was the record catching it. Old kept_wall missed it because the door is flush but not THIN.
- **USER RULE ADOPTED — PROTRUSION (replaces flush+thin):** wall exemption = box touches/crosses a wall plane AND protrudes into the room <= 0.20 m; depth beyond the wall is irrelevant. Census (blind, all wall-touching resolved boxes): openings/flat 0.00-0.16 (doors, glass door, window, tv, curtain, picture) | GAP | plant 0.26, magazines 0.35-0.37, shelves 0.38-0.49. Bonus: un-exempts the R-S2-30 "surprise wall exemptions" (obj_022 plant, obj_017_c00 magazine) — that carried open CLOSES.
- **USER RULE ADOPTED — SHELL CLIP:** every SHIPPING box is intersected with the shell interior ("boolean out all the strictly external volume"); a fully-outside opening becomes a MIN_SLAB 0.02 m panel flush at its wall. vote2/pano/original stay recorded unclipped (evidence). Glass door now ships 2.641..2.661 x full wall extent — a panel in its wall.
- **RUN 7 (warm caches):** panel + plant carved as designed BUT 45->44 objects — obj_017_c00, newly un-exempted, hit the `<100 dots skipping` path which SILENTLY DROPS the object (the latent hole the 08-11 handoff flagged; violates TIER-4 "never silent"). FIXED at source: the skip now ships the original box as status `kept` with reason + dot count recorded. **RUN 8:** 46 objects (the fix recovered a SECOND always-silently-dropped node) — statuses {carved_pano 28, carved 2, kept_wall 7, kept 2, kept_ceiling 7}.
- **Downstream refreshed:** doubts re-applied (46 nodes, 28 with doubts; docket UNCHANGED = the same 5 cases); carved_edges re-derived (84 edges, self-check PASS; obj_034 edges now sane: IN_WALL its wall + ATTACHED ceiling + ON floor; false IN-bookshelf edge gone); J0/J1 re-run = cache-backed (obj_034 pair correctly NOT renominated; 0 live J1 calls); J8 re-run = 4/5 cache hits, obj_019 re-judged fresh (ONE_BOX/ship_pano again, conf .82); loopback_j8_review.html regenerated.
- **PROVISIONAL (Claude):** the door story is closed end-to-end with every artifact traced; remaining unverified-by-eye: the plant's small new box (0.22x0.18x0.24 vs original protrusion 0.26 — plausible but unreviewed), the second recovered kept node's identity, and the run-7/8 cone map tiles. USER GATES OPEN: same as R-S2-36 (Gate A2 verdicts, B2 findings) + the two new carved faces; commit still pending user order.

## R-S2-38 - SLICE CLAMP REVERTED (user ruling: segment WITH walls, disenfranchise at tally) + RUN 9 (2026-08-07 late)
- **USER FINDING (cone map):** walls missing from the segmentation tiles; TV stand no longer singled out ("fine before"). CONFIRMED mechanism at ctx_render_jobs: the tunnel hole = cone MINUS slice within slice depth, so once the clamp shrank the slice to the wall, wall-surface dots became "occluders" and were deleted from every wall-adjacent object's cards. USER RULING: order = segmentation first (full context), vote (half-space filter disenfranchises wall dots), THEN geometric cleanup (protrusion exemption + shipping shell clip). Clamp REMOVED with a do-not-re-add tombstone; renders wiped; RUN 9 full.
- **RUN 9:** 46 objects, statuses unchanged {28/2/7 wall/2 kept/7 ceiling}. REGRESSION TEST PASSED: obj_014 bookshelf vote box still stops at the wall plane (hi_x 2.630) — the half-space electorate filter alone carries the wall-leak fix; the clamp was redundant for voting, destructive for renders. ONE box moved >10 cm: obj_042 tv stand 0.98x0.40x0.49 -> 3.38x0.40x0.51 (with wall context restored, detection spans the full media unit — USER EYEBALL NEEDED: real extent vs over-claim).
- **Downstream refreshed:** doubts (46 nodes, 29 with doubts) · carved_edges re-derived (85 edges, self-check PASS) · J0 0 new nominations / J1 re-attached incl. chair-merge SAME (fresh crops, same verdict) · J8 docket now 7 CASES (obj_021 dropped; obj_024 pillow, obj_042 tv stand, obj_068 chair joined) — all 7 verdicts fresh (renders changed = stimuli changed, no cache): obj_011 SPLIT/one_structure .62 ⚠ parts now this_node/this_node (run-8 verdict said existing:obj_063/this_node — OWNERSHIP DRIFT between runs, flag for the user) · obj_019 ONE_BOX/ship_pano .70 · obj_024 SPLIT/distinct 4 owners .65 · obj_029 ship_pano .62 · obj_032 either .74 · obj_042 ship_pano .83 · obj_068 ship_vote .62 (the shaved chair: vote box bounds the full chair).
- **PROVISIONAL (Claude):** the revert restored segmentation context and the TV stand immediately re-entered the docket and got a full-width box — direction right, extent unverified. Biggest new concern: J8 verdict INSTABILITY across render changes (obj_011's ownership flipped while the geometry barely moved) — argues for pinning ownership mechanically (assign split parts by overlap with existing nodes' boxes, judge rules identity only). USER GATES: run-9 tiles (walls back? TV stand?), the 7 verdicts, then commit.

## R-S2-39 - PERP-CAM RE-BOX FOR FLAT OBJECTS (user design; run 10) (2026-08-07 late)
- **USER DESIGN:** wall/ceiling exempt objects keep drifted one-shot pano-lift boxes — fix in-plane extents with ONE face-on view per object ("perp cam"): view-tunnel render perpendicular to the plane, detect (prior-gated), SAM-claim slab dots, 1-99 percentile re-box of the two in-plane axes only; normal axis untouched; guards (no detection / <200 claimed / >1.0 m shift / >3x extent = KEEP + record, never silent). Scene-agnostic, all four walls + ceiling one code path.
- **RUN 10:** statuses unchanged (46 objects). 13/14 flat objects RE-BOXED, 1 kept with reason (obj_027 ceiling light, 194 claimed < 200). Headline: obj_034 GLASS DOOR — face-on detection FOUND the door (score 0.575, 8009 dots), panel shifted 0.533 m along its wall and tightened 4.22->3.49 m (the drift the user spotted, corrected); ceiling light obj_018 shifted 0.594 m; everything else small tightens (shifts <= 0.12 m). Exempt objects now have their FIRST cone-map review rows (perp render + det overlay strips).
- **Downstream:** doubts re-applied · carved_edges re-derived (84 edges, self-check PASS) · J0 nominated obj_038+obj_053 (window vs curtain — first same-wall overlap surfaced by the re-boxes); J1: DISTINCT .68 ("window opening covered by, not identical to, the curtain panel") · J8: 7/7 cache hits (docket stimuli unchanged — run 10 touched exempt boxes only) · review page regenerated.
- **PROVISIONAL (Claude):** the perp view solved the door's visibility problem (the face-on tunnel render shows the door the cards never could) and the guard ledger worked (one kept, reason recorded); unverified by eye: all 14 perp tiles + the door's corrected panel + whether the curtain's 6.9 m box (dist-clamped camera) re-boxed sensibly. USER GATES: the perp strip rows in cone_map.html + the door in the viewer; then commit (pile now spans c48c87e..working tree).

## R-S2-40 - SPLIT-CUT JUDGE (J8s): grid-vocabulary stimulus DESIGNED LIVE + 3-ROUND CHAIN BUILT, WIRED, RUN (2026-08-07 late)
- **USER-DRIVEN DESIGN ARC (all live this session):** abstract cell-grid candidate figures REJECTED ("show me the real thing") → box-content top render invented (ONLY the case box's gaussians, camera outside the room — the L answers in one look, coffee table visibly separate) → + projected boxes (case orange, same-class green, other-class red) → + named metric grid (chess chips: letters=constant-x, numbers=constant-z) → grid made DYNAMIC (pitch from box size) + MEASURED S-LINES (neighbor box edges + notch edges become named magenta lines with a legend — the true boundary enters the vocabulary) → probe: judge answered in grid vocabulary, 2.5/3, one-line quantization miss (picked E; truth x=0.338 between D/E) = exactly what S-lines fix → user ruling: ONE CUT PER JUDGE CALL, fixed k=3 CHAIN (recursion explicitly rejected), judge picks lines/sides only, CODE SNAPS (S-line=verbatim coordinate; lattice snaps to measured boundary within 0.25 m; never a judge-invented number).
- **BUILT + WIRED:** graph/split_cuts.py (flat 3-round worklist, guards: auto-done <0.25 m pieces, max 8 pieces, split_incomplete at chain end, malformed→ships-uncut) + PLAN Phase A3 + map J8s node (dashed, RAN). Docket = J8 SPLIT cases; SPLIT/distinct with all-existing covering owners resolves MECHANICALLY zero-call (covered_by_existing).
- **RUN (living_marble):** obj_024 = covered_by_existing (owners obj_024/048/013/019, 0 calls). obj_011 = 3 rounds, 3 calls, ZERO guard trips, cache-verified reproducible (re-run = 3/3 hits, identical): R1 cut **S1 verbatim (obj_063 edge x=0.338)** — the S-line design worked, no rounding — P2(+x back run)=this_node done; R2 on the remainder cut S-line z=1.818 → P3=existing:obj_063 done; R3 no_cut, region = "bare floor + coffee table" → P4 owner existing:obj_006. Final pieces: obj_011=back run, obj_063=limb, obj_006=the notch region.
- **⚠ CROSS-JUDGE DISAGREEMENT (Gate A3 headline):** J8s geometry contradicts J8's standing run-9 verdict (one_structure, both parts this_node) and instead matches the run-8 verdict + the visual truth (obj_063 owns a limb). The ownership-drift open (ledger 4) is now expressed as CONFLICTING RECORDED VERDICTS — resolution rule needed at materialize (recommend: geometric ownership wins where an existing node's box covers a piece; identity annotations stay J8's).
- **⚠ P4 CAVEAT:** the chain assigned the whole 1.59x2.04 m notch region "existing:obj_006", but the table's carved box is much smaller — materialize must read not-this-object pieces as "NOT obj_011's" (drop from obj_011), never as growth of the named neighbor.
- **PROVISIONAL (Claude):** the stimulus recipe + one-cut chain is the session's design win — S1-verbatim on the first live case is the exact behavior the format was built for; unverified by eye: every stimulus PNG in graph/split_sheets/obj_011/. USER GATES: A3 (the obj_011 chain sheets + pieces), the J8-vs-J8s conflict ruling, then commit.

## R-S2-41 - SPLIT KEEP/DISCARD v2 + COVERAGE GUARD + J9 FIRST VERDICTS (2026-08-07 latest)
- **Split schema v2 (user ruling):** per side keep|discard + more_cut only on keeps; chain ends when nothing is flagged (k=3 = cap not itinerary). First v2 run: efficiency worked (2 calls, self-terminating) but the judge DISCARDED the sofa's own back run ("pillows resting on it claim it" — the discard definition was too permissive, judge applied it as written). A metre of sofa would have been owned by NOBODY.
- **MECHANICAL COVERAGE GUARD (user-adopted):** every ownership discard is verified — same-class green-box union must cover >= 60% of the side's plan area, else DOWNGRADE to keep{this_node}+doubt discard_unverified; mostly-empty sides (<25% occupied cells) may discard freely. Prompt gains the hard rule: RESTING objects never own a region. Re-run: guard FIRED on the back-run discard (0% cover -> kept, saved) + one conservative false-positive (notch/table region kept-with-doubt: check counts only same-class cover; the table is other-class). REFINEMENT QUEUED: other-class standalone boxes should validate "another object's territory" discards. Final obj_011: 4 tiles, all this_node, 2 doubts, cuts on measured S-lines every round; obj_063 overlap left to materialize's mechanical ownership.
- **J9 SAME-PRODUCT FIRST VERDICTS EVER:** crop contact sheets built (6 groups; obj_005_c00/obj_017_c00 have NO crops — carve-recovered nodes lack funnel evidence, flagged red). First run: ALL 6 calls failed "no JSON" — ROOT CAUSE: call_claude lacked cwd; claude -p can only Read inside its working dir, so the model couldn't open the sheets (J8 always passed cwd). FIXED at source + comment. Second run 6/6: magazines both groups NOT same (size gaps; upright-spines vs flat); lights: obj_031+obj_045 matched pair (partial set) / obj_023+027+030 SAME 0.165x0.02x0.156; chairs: SET obj_020+obj_041+obj_028 0.565x0.75x0.227 (contains the J1 duplicate pair — cross-judge consistent); pillows: 5-member burgundy set 0.402x0.38x0.435. NIT recorded: set_members id format inconsistent across verdicts (bare numbers vs obj_ prefixes) — normalize before shopping consumes.
- **PIPELINE STATE: every judge bench has now RUN end-to-end** (carve r10 canon -> doubts -> carved edges -> J0/J1 -> J8 -> J8s -> J9). UNBUILT: Phase C materialize (the editor). USER GATES OPEN: A3 sheets (tightened chain), J9 sheets+verdicts, the J8/J8s ownership ruling, the queued discard-refinement; then commit (pile spans 6fb1d64..working tree).

## R-S2-42 - REPRESENTATION OBJECTIVE LANDS: residue criterion + independent-support eligibility; the L converges to ONE call (2026-08-08 ~00:30)
- **USER DESIGN (the objective function, finally explicit):** the split's goal is to REPRESENT the object's content with boxes INCLUDING the ones that already exist — discard what's taken care of, keep only unrepresented content, cut efficiently, margin allowed.
- **Engineered as the RESIDUE CRITERION:** a side may discard iff (occupied cells NOT covered by eligible existing boxes grown 0.10 m) <= 25% of its occupied cells; mostly-empty passes automatically. Replaces the two-rule coverage guard.
- **ELIGIBILITY = INDEPENDENTLY SUPPORTED (two live defects found + fixed):** (1) rider matching was direction-agnostic — the sofa's own supporter arch_floor was classed a rider; (2) pillows have NO ON edges in carved_edges (the carve turned them into IN edges — recorded 4g2 OPEN), so they were eligible cover = the pillows-own-the-sofa failure could recur mechanically. NEW RULE: cover must be the `a` of an ON edge to something other than the case node. Live check: eligible = obj_006+obj_063 only; excluded = 9 pillows + 3 ceiling lights (no_independent_support). Never-cover boxes drawn gray dashed + listed in the prompt.
- **FINAL RUN — CONVERGED:** obj_011 = ONE call, ONE cut (S1 verbatim), ONE kept piece (the +x run); the x<0.338 side discarded at residue 0% verified against legitimate cover only ("chaise inside obj_063's box; rest is the table's footprint + empty notch floor — no sofa content unrepresented"). Representation achieved: union(P-piece, obj_063's box, obj_006's box) covers the L with zero doubts, zero guard trips. Evolution across the night: 3 calls/3 pieces -> 2/1 (wrong) -> 4/4 (guarded) -> 1/1 (right) — each step a user design ruling.
- **PROVISIONAL (Claude):** this is the splitter's design settling point; opens: the 4g2 pillow-ON gap (support relations post-carve), J9 set-id normalization, other-scene generalization. USER GATES: final A3 sheet eyeball, then commit + handoff.

## R-S2-43 - THE OVERNIGHT: render principle landed, exempt objects routed to J8, full chain re-run, FIRST MATERIALIZE (2026-08-08 01:00-04:00, user asleep, authorized)
- **RENDER PRINCIPLE (user, the night's design spine):** "the slice is an INVISIBLE bounding region that tells the camera roughly where the object is so we can carve out what is BETWEEN camera and object; everything else stays rendered." Landed in three steps: cards cull at the object's near face (run 13), perp renders likewise with the anchor = NEARER of box face and plane (run 14 — a ceiling light hangs below its plane, a wall opening's box starts beyond its wall; both anchors exercised in opposite directions), and framing for flat objects taken from the PLANE + box in-plane centre (the slab-centroid framing was worse: for a wall opening the slab is 6.6 m of outdoor scenery seen through the glass).
- **STALE-RENDER ROOT CAUSE KILLED:** the WSL renderer skips by FILENAME. Run 11 detected on run 10's images while projecting with new cameras — every flat-object number in it was void (user caught the tile was unchanged). Renders now carry a params sidecar (camera + cull rule + kept-gaussian mask hash); a mismatch deletes the png. The manual-wipe rule that failed twice is retired. Both gate directions verified.
- **PARTIAL RUNS FIRST-CLASS (user order, debugging was too slow):** --only merges into the whole-scene documents (report/manifest/conemap by id in node order, cone_map.html from per-object row sidecars, wipes scoped to processed ids) with per-entry provenance {run_id, params_hash, source_sha} and header canon_eligible (full + uniform only). Acceptance test: partial reproduced the full run BYTE-IDENTICALLY for the processed objects, 46/46 entries preserved. Debug loop went 15-20 min -> ~2 min.
- **RUN 13/14 = the new canon** (46 objects, statuses stable). ⚠ 14 boxes moved >10 cm scene-wide under the new card culling (chair 0.57 m, magazine 0.53 m) — the segmentation genuinely sees different pictures now; UNVERIFIED BY EYE.
- **EXEMPT-OBJECT GAP CLOSED (user finding on obj_018):** wall/ceiling nodes produced no doubts, so they could never reach J8. Two new kinds: rebox_rejected_smaller (detection >3x smaller than the box) and rebox_truncated (>=2 of 4 in-plane sides kept priors). J8 builds exempt cases from the perp render, camera read from its params sidecar. Census: exactly obj_018 and obj_038, nothing else.
- **ROBUSTNESS:** a slow claude.exe hitting the 240 s timeout raised out of the executor and killed a whole 10-case docket. Every call failure is now a failed ATTEMPT (retry, then UNCLEAR/ships-uncut) in J8 + J8s; timeouts 240->600 s.
- **CHAIN RE-RUN (run-14 geometry):** J0 20/0 nominated · J1 magazines obj_029↔036 SAME · **J8 10/10** — obj_011 SPLIT/one_structure now correctly assigns back-run→obj_063, chaise→this_node at **0.82** (the green-neighbour wireframe + edge-derived facts working); obj_018 **UNCLEAR** (judge reads the over-reach as ceiling trim, not a second fixture, and declines to split on one low-score detection — an honest refusal); obj_038 ONE_BOX/ship_vote · **J8s converged 1 call / 1 cut / 0 doubts** · **J9 6/6** (id normalization added at source: sets came back as bare ints from some groups).
- **⚠ J9 INSTABILITY (new open, important):** two runs 20 min apart on near-identical data gave DISJOINT sets — pillows {obj_024, obj_037} → {obj_015, obj_016, obj_026}; lights group 3 flipped false→true. J9 has no verdict cache, so every run re-decides. Needs a cache, repeat-vote consensus, or pairwise comparisons instead of subset-picking from 9.
- **FIRST MATERIALIZE BUILT + RUN (graph/materialize_carve.py, additive graph["carved"]):** 46 resolved → 45 proposed; precedence carve box → J8 ruling → J8s pieces → J1 merges → J9 annotation → open doubts, provenance per rule, conflicts recorded never resolved. Results: obj_011 → obj_011#1 (the chaise piece, box verbatim), obj_036 dropped into obj_029, 12 J9 annotations (no resize — canonical size is shopping's input), ZERO box swaps (all 7 ONE_BOX rulings were ship_pano = already the shipping box; obj_038's ship_vote recorded as ruling_not_applicable since an exempt node has no vote box). 1 CONFLICT: J1 merged obj_029↔036 which J9 ruled NOT same product — recorded, merge wins, J9's false has no effect. Additivity verified twice + idempotent; backup written.
- **PROVISIONAL (Claude) — what does not work yet:** (1) the L loses its one_structure linkage — obj_063 and obj_011#1 ship as two unrelated sofas, so shopping would buy two; (2) obj_063 carries no machine-readable pointer that it represents the discarded back-run (the ownership lives in a discard note's free text); (3) piece ids contain "#" which will break path-shaped consumers; (4) edges are NOT re-derived, so carved_edges still references nodes the carved set no longer has; (5) 3 of 6 materialize rules never fired on real data (ship_vote swap, existing:<id> piece drop, covered_by_existing) — synthetic-only, treat as unproven; (6) J9 canonical sizes diverge sharply from carved boxes (pillow 0.376 vs shipping 0.56) — shopping needs an explicit precedence rule. USER GATES: run-14 tiles + the 14 moved boxes, the 10 J8 verdicts, materialize_report.html, and the J9 instability ruling.

## R-S2-44 - J8 v2.4 USER-ACCEPTED ("they all make sense. this is the one we use"): comparison ask + per-node candidates + dependency order (2026-08-08)
- **THE ARC, all user-driven, all traced from ONE case (obj_021 chair):** the judge shipped the smaller pano box and justified the low plan-fill as "the backrest's overhanging rim seen from above". Probing the splat showed the opposite: the orange-only region holds 1,096 dots at chair height and chair colour (vs 1,478 in the pano core), the chair's mass runs to the floor, and BOTH boxes cut the legs (pano floats 0.296 m, vote 0.112 m). The judge's stated reason ("nothing else present" out there) was factually false, and it chose pano while pano's own stated condition (vote absorbed a neighbour) was explicitly absent from the sheet.
- **⚠ LAUNDERED-OBSERVATION INCIDENT (user correction, now RULE #1 addendum):** I "verified" the user's eyeball observation (the desk hides the chair's lower front) with a ray-box occlusion test and reported "36% blocked / 62% of the lower half" as a pipeline fact to feed the judge. Two faults: the sample was taken over the VOTE BOX — one of the candidates under judgement (circular) — and the whole line of inquiry came from a human looking at a tile. User: "we have no idea of knowing if 62% of the object is blocked... this required my human judgement, again. please make this a rule you always remember." Rule recorded in memory: never present a fact derived from human observation, or from the quantity under question, as an automated measurement; before proposing any new judge fact, state what it is computed from and check every input is available to a blind run.
- **USER RULING 1 — ASK FOR A COMPARISON, NOT A DIAGNOSIS.** The two box keys were described by failure mode ("ship vote when the pano cut was occlusion-shaved / ship pano when the vote box absorbed a neighbour") — which assumes exactly one failure happened, never mentions COMPLETENESS, and left no answer when both boxes are bad. Replaced with: compare the candidates, pick the better one, by ordered criteria COMPLETE (contains the whole object; cutting through it, or floating above the surface it rests on, is worse) then TIGHT ENOUGH; explicit error tolerance ("perfection is not required, a box only has to be reasonable"); the old conditions demoted to hints. NEW OUTCOME NO_GOOD_BOX (all candidates grossly wrong; distinct from UNCLEAR) — materialize keeps geometry + records j8_no_good_box. RESULT: obj_021 flipped to vote at 0.82, citing "the chair's legs visibly continue below the cyan box's bottom edge down toward the floor" — the completeness test the old framing had no vocabulary for.
- **USER RULING 2 (earlier, same arc) — RULE ON THE BOXES A NODE ACTUALLY HAS.** ship_pano|ship_vote|either was unanswerable for a carve-exempt node (no pano, no vote box), so obj_018 had to answer UNCLEAR while its own reason said the box over-reaches and the rejected candidate IS the fixture. Replaced with a per-case candidate list built from what the carve recorded (carved: vote|pano; exempt: current|rebox_candidate; "either" only when they agree within 5 cm). obj_018 now decides: ONE_BOX ship=rebox_candidate 0.87, box 1.25x0.03x0.52 -> 0.17x0.05x0.16 (a 97% volume cut) — the first J8 verdict ever to change a box. Exempt legend rewritten (no vote/pano vocabulary they never had) + BOX-CONTENT panel added (only the gaussians inside the node's own box, isolated) — that panel is what makes "one fixture or two" a one-look question.
- **USER RULING 3 — JUDGE INNER BEFORE OUTER (chosen over a fixed-point loop: "too much compute").** Bug found live: J8 grew obj_063 east to x=0.636, but the splitter had already cut obj_011 at x=0.335 BECAUSE that was obj_063's edge — 0.30 m overlap. Fix: docket cases sorted into LEVELS (box >=50% inside another -> smaller judged first), each level's ONE_BOX verdicts folded into a SETTLED GEOMETRY MAP before the next level's stimuli are built; split_cuts reads the same map. living_marble: 3 levels, obj_063 two levels before obj_011; only 2 live calls (8 cache hits); cut moved 0.335 -> 0.636 snapped verbatim to the settled edge; **final overlap 0.000000 m3**. Deterministic across two runs. Also: --only now MERGES (it used to wipe the other 9 verdicts).
- **FINAL STATE, USER-ACCEPTED:** 10 cases / 3 levels / 4 boxes changed (obj_018 light, obj_021 chair, obj_019 pillow, obj_063 sofa — three of them GREW because the object continued past the smaller box) / 5 kept / 1 SPLIT (obj_011: back-run -> obj_063, chaise -> this node, 0.70). Materialize applied all four swaps; additive check PASS. Review page: judge_cards.html (all 10 with panels, candidates, verdicts; every img/href verified).
- **RECORDED, NOT ACTED ON:** post_judge_conflicts — 5 pairs whose overlap GREW after judging (obj_024/obj_063 0->32%, obj_013/obj_019 60->71%). Second-order dependencies the level order cannot see because the edge did not exist before a box grew. This is the residue the fixed-point loop would have caught; the user accepted the trade.
- **USER VERDICT: ACCEPTED** — "they all make sense. this is the one we use."

## R-S2-45 - THE DETECTION-CHOICE DAY: slice built from the wrong box; ranking + framing + re-shoot; and the SPLITTER'S ROUND CAP WAS CHANGING THE ANSWER (2026-08-08 evening)
- **USER TRACE, start to finish.** From "why is obj_068 a chair" the user walked the chain back: J1 had twice called obj_068 "likely a table, mislabeled as chair" (0.82 / 0.78) with three objects inside its 1.24 m box — a verdict that had NOWHERE TO GO, because J1's form only answers same/distinct. Then: the plan view shows ONLY slice dots, and the slice is drawn around the TOP DETECTION, so a bad detection is unrecoverable — "the vote can only pick inside the slice".
- **THREE CARVE FIXES, all measured before landing:**
  1. **DETECTION CHOICE IS A RANKING.** We kept the highest-CONFIDENCE box passing a 30% admission gate. Probed obj_020's real detections: #0 conf 0.430 / 36% inside prior / off two edges (the NEIGHBOURING chair) beat #1 conf 0.413 / 98% inside / clear of every edge by 0.017. The right answer was already in the list and we discarded it. USER RULING: rank, don't score-pick. First tried a tiered rule (untruncated preference -> prior match -> score) which fixed the chairs but BROKE the glass door (match-only preferred a 0.224 sprawl, because the door's prior IS the drifted box the re-box exists to correct). USER PROPOSED A COMBO: score x match x 0.7-if-touching-a-border. Verified offline first: identical pick on ALL 22 recorded top-view cases AND it fixes the door (0.378 vs 0.181). One rule, no path-specific exception — it replaced both the tiers and my proposed wall-object carve-out.
  2. **FRAMING CHECK before detecting** — obj_068's prior projected to the WHOLE 768px frame, so the admission gate was meaningless; now the camera pulls back until the object fills ~60% and re-renders.
  3. **RE-SHOOT LADDER after detecting** (user: "same mechanism as the other tiles") — a detection touching a border is cut off, so take another shot pulled back rather than patch the footprint. obj_020: shot 1 overlap 0.365 off two edges -> shot 2 overlap 0.980, clear. Recorded per object: top_frame, top_shots, top_choice (full ranked shortlist), top_choice_overruled_score.
- **RUN 17 (46 objects, canon-eligible):** 7 detections overruled, 13 re-framed, 2 re-shot, ~20 boxes moved >2 cm. obj_020 0.32 -> 0.47 m (original 0.47) · obj_068 0.09 -> 0.25x0.68x0.28 (now raises the multi-node flag) · obj_034 door back to 0.02x3.06x2.94. TWO OUTLIER-GUARD TRIPS (original ships, oversized box recorded as doubt): obj_019 pillow at exactly 8x (no pano box, sits in the overlapping pillow pile) and obj_029 magazine at 40x — its top view finds NO detection, so it falls back to the full-height wedge and the bookshelf wins the vote. Both are carried opens.
- **⭐ THE SPLITTER FINDING (user-driven, the session's best):** the sofa took 3 calls / ~10 min and produced 2 pieces. User asked to try depth 1 — the SAME judge settled the SAME object in ONE cut at HIGHER confidence (0.85 vs 0.82), matching the converged result approved in R-S2-42. The round cap was being read as a BUDGET TO SPEND: "there are at most 3 rounds" invited deferring work. USER RULING: keep the ceiling at 3, tell it FEWEST CUTS WINS (ceiling not budget; one cut that settles everything is ideal; flag more_cut only when a side genuinely cannot be settled now), with the measured comparison stated in the prompt so the instruction carries its evidence. Result: 1 call / 1 cut / 1 piece / conf 0.85 / ~3 min. **Generalizes: stating a retry budget changes how much a model attempts per turn — applies to every judge we give retries to.**
- **Also fixed:** the viewer's carve-layer label is composed LIVE from the manifest's provenance (run id + canon flag + object count) — a hard-coded "run 10" caption was showing while the file held run 16 boxes. RULE: never hand-write a run number in a label (third mislabel of this class this session, after the exempt "vote box" legend).
- **CHAIN RE-RUN on run 17:** J0 nominated 1 (obj_068+obj_020); J1 SAME — "the same olive-green chair with thin black metal legs under a table, 96% box containment, duplicate detections" — the chair duplicate is caught again now that obj_068's box is chair-sized. J8: 8 cases, 2 swaps (obj_021, obj_068 both ship=vote, legs continue below the smaller box), 5 kept, 1 SPLIT. J8s: 1 cut. J9: 6 groups (chairs {020,021,028,041} at 0.458x0.747x0.383). Materialize: 46 -> 45 nodes, 3 dropped, 1 piece, 1 conflict, 9 open questions.
- **TIMING MEASURED (user asked where the time goes):** judges dominate, not renders. Each model call is 2-3.5 min; renders are seconds. J9's 6 calls run in parallel (~3 min total); the splitter's are strictly sequential because each round's picture depends on the last cut — which is why the round-cap fix cut the stage from 10 min to 3.
- **USER VERDICT: PASSED** — "i see no problem with the others", "this is amazing find". Wrap-up ruled before J9.


## R-S2-46 - J9 PLUMBING FIXED (cache, sonnet, no-stimulus guard, retry); THE INSTABILITY IS THE ANSWER FORM AND IT IS STILL THERE (2026-08-08 late)
- **CONTRACT.** J9 gets groups of same-named nodes standing near each other, with their carved sizes and up to 2 detection crops each. It decides: same product? which members belong? what ONE size does shopping buy? A mistake buys the wrong asset, or buys one thing twice.
- **USER RULING:** "fix the easy ones. but i think we need to redesign. however, lets fix and run it once and I can review the current state on a sheet." So: plumbing only this session, redesign next, review page first.
- **FIVE DEFECTS FOUND IN THE DATA (not from looking at pictures) — four fixed:**
  1. **No verdict cache.** Every other judge has one on disk (judge_multiplicity_cache, split_cuts_cache, judge_pairs_cache...). J9 was the only judge without, so it re-decided every run. FIXED: graph/judge_same_product_cache.json, key = sha256(prompt + contact-sheet bytes), the J8 pattern. Verified: second run = 0 calls, 5 cache hits.
  2. **Ran on `haiku`.** J8 and J8s hardcode MODEL = "sonnet". J9's haiku default was an undocumented outlier, not a recorded decision. FIXED: MODEL = "sonnet".
  3. **It answered with no picture.** Group 1 (magazine obj_005_c00 + obj_017_c00) are pano-cluster nodes with `evidence.members == []`, so BOTH sheet rows print "NO CROPS" — and the old run still returned `same_object: false` reasoning from heights, while its own prompt told it to look. FIXED: every row blank -> UNCLEAR with NO call (the J8 no_stimulus rule). A MIXED group still runs, but the unseeable members are named in the prompt and recorded as `no_photo_members` — recorded, not decided. That partial path is unexercised on live data (only group 1 is blind, and it is fully blind).
  4. **One shot per call.** Group 2 (magazine x3) had been sitting in same_product.json as `judge call failed: Expecting value: line 1 column 39` — a dead group. FIXED: retry once with "REPLY WITH THE JSON OBJECT ONLY", then record the failure with the attempt count. It answered first try this run.
  5. **⭐ THE ANSWER FORM CANNOT HAVE A STABLE ANSWER — NOT FIXED, BY RULING.** The judge names a SUBSET and is never asked to account for the members it leaves out, and each group gets exactly ONE set slot — so a group that is really two products can only be answered by discarding members. Eight of the nine pillow heights sit at 0.39-0.44 m while widths/depths swing 0.23->0.69 because the boxes are noisy, so any three of them is a defensible "matched set". This is why two runs 20 min apart returned DISJOINT sets. It is the form, not a flaky model, and a cache would have frozen one arbitrary answer and called it settled.
- **ALSO FIXED (a stage must not die on its own log line):** the closing `wrote ... (⚠ UNTESTED)` print raised UnicodeEncodeError under a cp1252 console AFTER same_product.json was already written — work done, run exits non-zero. stdout/stderr now reconfigure to utf-8/replace. SAME LATENT BUG, NOT TOUCHED: carve_slicevote.py (≥), graph/build_edges.py (→), compose/uniform_instances.py (⚠) — one line each when someone is in those files.
- **THE RUN (sonnet, 5 calls, concurrency 8, ~4 min; group 1 not asked):** g1 magazine UNCLEAR/not asked · g2 magazine x3 NOT the same product ("three visually distinct magazine/book piles on different shelves") · g3 ceiling light SAME {008,031,045} at 0.156x0.035x0.199, obj_018 out as the 1.21 m truncation outlier · g4 ceiling light SAME {023,027,030} at 0.165x0.02x0.156 · g5 chair SAME {020,021,028,041,**068**} at 0.44x0.75x0.32, obj_010 out · g6 pillow SAME {013,015,026} at 0.4x0.4x0.45, six left out.
- **TWO THINGS FOR THE USER'S EYE ON THE SHEET:**
  - **The pillows moved AGAIN** — {024,037} -> {015,016,026} -> now {013,015,026}. Three runs, three answers, one member of overlap. Exactly what defect 5 predicts, and the honest evidence that the redesign is the real fix.
  - **obj_068 is now IN the chair set** (it was excluded last run as "too narrow, 0.25 m"). Run 17 gave it a chair-sized box, which is the fix working — but J1 ruled obj_068 and obj_020 the SAME OBJECT (a duplicate detection). So J9 is counting a duplicate as a fifth chair. J9 does not read J1's merges; materialize applies the merge later. Recorded, not acted on.
- **REVIEW PAGE REBUILT** — graph/same_product_sheets/index.html now carries each group's verdict ABOVE its contact sheet: the call, the size to buy, who is in, **who is left out**, the reason, and model/date/cached/attempts. The left-out line says plainly that nothing downstream is told why they were left out and only set members get a size.
- **NOT DONE, ON PURPOSE:** the redesign (assign EVERY member to a set or to `alone`, allow more than one set per group) and the matching materialize_carve.py rule-5 change. Both wait on the user's read of the sheet.

## R-S2-47 - THE CANONICAL SIZE WAS A MEDIAN IN DISGUISE; EXEMPLAR, NOT BLEND (user ruling 2026-08-08 late)
- **USER, after passing the classification:** "the classification is correct. but what about the sizing."
- **FINDING 1 — the judge was not judging size, it was doing arithmetic.** Its canonical_size equals the per-axis MEDIAN of the members it kept, EXACTLY, in all four same_object groups (lights [0.156,0.035,0.199] and [0.165,0.02,0.156] exact; chairs 0.44/0.75/0.32 = median 0.442/0.746/0.323 rounded; pillows 0.4/0.4/0.45 = 0.397/0.401/0.449 rounded). Not the mean — checked. So a model call was buying us a median we could compute exactly, and we were taking it on trust.
- **FINDING 2 — the per-axis median is the WRONG arithmetic.** The boxes are aligned to the ROOM's axes, not to each object, and these objects face different ways: one member's width is another's depth. Pillow obj_026 measures 0.494 x 0.257 on the floor while obj_013/obj_015 measure ~0.38 x ~0.46 — same product, axes swapped. Sorting each member's two floor dimensions into long/short BEFORE combining tightens 3 of the 4 groups; on the pillows the long-axis spread falls 0.224 -> 0.045 m (5x). HEIGHT is the one directly comparable axis (everything shares "up") and it is tight everywhere: the g4 lights agree to 0.000 m, the pillows to 0.027 m.
- **FINDING 3 — the chairs disagree even after sorting, and we shipped a number anyway.** Long-axis spread 0.436 m, short 0.217 m: obj_021 is 0.716 m deep, obj_041 is 0.225 m — they cannot both be the same chair. Sorting cannot fix it because those boxes are wrong at non-90-degree angles and the pipeline never estimates continuous yaw. The carve had ALREADY flagged two of the five (obj_021 low_plan_fill, obj_068 pano_vs_cluster = the J1 duplicate), and the median laundered them into a confident-looking number. Nothing recorded the spread, so shopping could not tell the chairs (0.44 m of disagreement) from the ceiling lights (0.02 m).
- **USER RULING: EXEMPLAR, NOT BLEND.** The canonical size is ONE member's measured box, copied verbatim. Same shape as the settled J8s ruling — the judge speaks the vocabulary, code does the geometry.
- **THE RULE (no thresholds, no global lists).** Rank the set members: measured before never-measured (`kept`/`kept_outlier` = the carve shipped the ORIGINAL box, no measurement was taken), then fewest carve doubts, then closest to the set's MEDIAN HEIGHT, then id for determinism. First place wins; its box ships verbatim in its own world-axis order. **Ranked WITHIN THE GROUP on purpose:** every ceiling light carries `exemption`, so a blanket "no doubts = eligible" rule would have disqualified all of them and left the group with no exemplar. A doubt only counts against a member relative to its own group-mates.
- **RECORDED ALONGSIDE:** canonical_size_from, the full ranked list with each member's status/doubts/size, set_spread_long/short/height (after sorting floor dims), the set median, and judge_canonical_size — what the blend would have said, kept for comparison.
- **RESULT (0 model calls — computed after the verdict, outside the cache, so the accepted classification is untouched):** lights obj_008 [0.177,0.035,0.16] (3 tied, height decided) · lights obj_023 [0.173,0.02,0.156] (3 tied) · **chairs obj_020 [0.474,0.746,0.323]** with obj_021 and obj_068 correctly ranked last · pillows obj_015 [0.363,0.401,0.481] with obj_013 demoted. Spreads now visible: lights 0.02-0.03 m, chairs 0.436 m.
- **DELIBERATE:** the prompt STILL ASKS for canonical_size and we still record the answer. Dropping the ask would change the prompt, miss every cached verdict and re-decide the classification the user just accepted. It goes when the answer form is redesigned.
- **NOT DONE:** materialize_carve.py rule 5 still writes only `canonical_size` into the node — it does not carry canonical_size_from or the spread into the graph provenance. One-line follow-up when materialize is next opened.

## R-S2-48 - THE SET'S GEOMETRY, ON THE SHEET (user ask 2026-08-08 late)
- **USER:** "show the sizing box in the scene... give me the selections boxes too" -> then "i mean in the sheet!". Built for the viewer first (kept, below), then where it was asked for.
- **BOX VIEW, one per same-product group, ON THE SHEET.** A top-down box-content render of the union of the set's boxes (graph/split_cuts.py render_region + Splat, camera from carve_cams.make_cam -- the SAME camera math the renderer used, which is the whole point of the anti-drift module), with three things projected onto it: AMBER the exemplar's own measured box (labelled "SIZE COMES FROM HERE"), VIOLET each other member's own measured box, DASHED PINK the canonical size drawn at EVERY member's centre. Legend strip burned into the image so the picture answers in one look. Colours match the two viewer layers on purpose.
- **PROJECTED INTO AN RGB RENDER, NOT DRAWN AS A PLAN DIAGRAM** -- the standing user ruling (plan views not useful; project the 3D boxes into the views).
- **CENTRE-ALIGNED, NOT FLOOR-ALIGNED, DELIBERATELY.** The size box shares the member's box CENTRE. That needs no up-axis assumption, and this frame is y-down where sign mistakes on up have bitten this pipeline before. Stated in the caption so it is not read as two objects standing on a floor.
- **BUILT:** 4 groups, 0 model calls (verdicts all cached), renders 11k-82k gaussians each. Mechanical check before handing over -- every one of the three colours has pixels in the render area of all 4 images, so nothing silently failed to project. Group 4's pink is only 248 px because those lights agree to 0.026 m and the size box sits under the member boxes: agreement looks like coincidence, which is the honest reading.
- **ALSO BUILT (viewer :8321, kept):** two composed layers, `sp_members` (violet, each set member's own carved box, exemplar labelled) and `sp_sizes` (pink, the canonical box drawn at every member), registered in box_sources + special-cased in /boxes.json, both gated on J9 having run. Same colours as the sheet.
- **WHAT THE NUMBERS SAY TO LOOK FOR:** ceiling lights should look boring (worst 0.05 m / 0.035 m). Chairs are the test -- against obj_020: obj_021 -0.393 m in depth, obj_068 +0.228 m in width (both carve-flagged, so the rule ranking them last is working), but obj_028 -0.120 m and obj_041 +0.098 m are CLEAN and still off, so the open question is whether obj_020 is genuinely the best chair or just the median-height one. Pillows: obj_026 +0.224 m in depth is the axis swap made visible.

## R-S2-49 - J9 v2: POOL PER KIND, ASSIGN EVERY MEMBER, DESCRIPTIONS IN THE PROMPT (user ruling 2026-08-08 late)
- **USER RULING:** grouping must be SEMANTIC, in TWO LAYERS — role ("chairs at a table", "shelves on a wall") vs product identity — and "we have had descriptions previously right?". Layer 2 built this session; layer 1 deferred.
- **THE 2.5 m PROXIMITY RULE IS GONE.** `candidate_groups` (name -> greedy plan-proximity clusters, GROUP_RADIUS 2.5) is now `candidate_pools` (name only, whole scene). What the old rule was doing: (1) the room's 7 ceiling lights fell into a 4 and a 3 because the nearest cross-patch pair is 2.74 m — and the judge then called BOTH groups "oval flush-mount ceiling lights" with exemplars agreeing to 4 mm, i.e. two purchases for one product; (2) worse, **bookshelf x3, door x2, sofa x2 and plant x2 never reached the docket AT ALL** — no two of them were within 2.5 m, so four whole kinds were silently unjudged. Distance is a fair proxy for "matched set around one table"; it is a poor proxy for "same product" — the same lamp can be bought twice and hung at opposite ends of a room.
- **THE ANSWER FORM IS FIXED (the R-S2-46 blocker).** The judge now ASSIGNS EVERY MEMBER: one line per object, `set_1`/`set_2`/.../`alone`, each with its own reason, more than one set per pool allowed. A reply that skips members is a FAILED ATTEMPT — one retry naming the missing ids, then whatever is still missing is recorded as `unassigned`, never invented.
- **THE J6 DESCRIPTIONS ARE IN THE PROMPT.** graph/appearance_cache_v2.json (describe_nodes_v2) has colours/material/style/one-line description for every node — keyed by an EVIDENCE hash and geometry-blind by design, so the carve re-runs never staled them, and J9 had been ignoring them entirely. Also in the prompt now: each member's RECORDED relations (carved_edges ATTACHED/IN/ON/IN_WALL, generic arch_floor dropped) as context — never as a grouping key. The old find_anchor footprint guess returned NOTHING for the chairs, pillows and both light groups; the edge layer has all 7 lights ATTACHED to arch_ceiling and all 9 pillows IN the sofa.
- **THE DESCRIPTIONS ALONE REPRODUCE THE CLASSIFICATION** (checked before building): all 7 lights read "oval / recessed-or-flush / white" ACROSS the old proximity split, and obj_010 reads "a flat, glossy black rectangular panel with sharp angular edges" — which is exactly why it is not a chair.
- **RESULT, 8 pools, 8 calls, sonnet:** bookshelf {012,014} + 005 alone · **ceiling light 2 sets: {008,018} and {023,027,030,031,045}** · chair {020,041} + {021,028} + {010,068} alone · door {000,001} · magazine {032,036} + 3 alone · pillow {013,015,016,026} + {037,048} + 3 alone · plant both alone · sofa {011,063}.
- **THE OUTLIER CASE THE USER FLAGGED IS FIXED, WITHOUT A THRESHOLD.** obj_018 (the 1.21 m light) had been dropped as an outlier; it is now IN a set, and the judge said why: "Same warm gold/bronze metallic trim ring and oval shape as obj_008; its huge measured size is flagged rebox_truncated so it is a bad box on the same small fixture." It could only say that because the carve doubts are now in the prompt. The user's proposed "if X% of a function match, absorb the rest" was aimed at exactly this and is not needed for it.
- **BUT THE SPLITS THAT REMAIN ARE LOOK CLAIMS, NOT SIZE CLAIMS** — lights: "warm gold/bronze trim, thicker" vs "thin dark/gray trim"; chairs: "curved tan/brown wood-grain shell" vs "uniformly black/glossy upholstered". A majority rule would now be overruling a NAMED VISIBLE DIFFERENCE, which is a far riskier override than overruling a measurement. J6's own descriptions never mentioned gold on obj_008 ("white oval ceiling light"), so one of the two readings is wrong. **USER GATE OPEN: are the trim / wood-grain differences real in the crops?** Nothing is built on top until that is answered.
- **ON THE "%":** any specific percentage would be a knob chosen because we looked at this scene (Rule #1). The parameter-free forms are (a) strict majority absorbs the rest, or (b) raise the bar for splitting IN THE PROMPT — "same kind in one room is one product unless they LOOK different; size disagreement is never a reason to split; name the visible difference" — which is the same shape as the splitter's fewest-cuts fix. (b) recommended, both blocked on the gate above.
- **obj_068 IS NOT A J9 PROBLEM:** left alone for a mixed reason (narrow + pano_vs_cluster doubt + odd "in chair" placement), but J1 already ruled it the SAME OBJECT as obj_020. J9 does not read J1's merges — a wiring gap, not a threshold. It now surfaces honestly as a materialize CONFLICT (below).
- **OUTPUT SHAPE:** `pools` is the record (every member, where it landed, why); `groups` is a DERIVED legacy view, one entry per SET in the old shape, so materialize_carve.py rule 5 needed no change.
- **TWO BUGS FIXED IN PASSING:** (1) `ensure_ascii=False` + `write_text()` with no encoding wrote same_product.json through the Windows codepage and made it unreadable as utf-8 — hit immediately, explicit encoding added; (2) box views are now built per SET, not per pool.
- **MATERIALIZE RE-RUN on the new verdicts** (45 nodes, additive check PASS): two honest CONFLICTS recorded — J9 named obj_020 (J1 had merged it into obj_068) and obj_011 (J8s had split it). Exactly the cross-verdict class materialize exists to catch.
- **VIEWER = LATEST AND GREATEST (user ask).** `materialized` is now the FIRST current layer, relabelled "LATEST — the whole chain through J9"; sp_members / sp_sizes follow; slicevote, parallax and judge_preview drop to the collapsed archive (files untouched). Explicit rank map so a new layer cannot quietly push the canonical one down the row.
- **LABEL FIX (user caught it):** "46 obj" read as "46 SLICED boxes". It is not — the layer draws each object's SHIPPING box, and only 28 of 46 went through a slice election; the rest are geometric exemptions or the ORIGINAL pre-carve box (kept / kept_outlier). Label now reads "46 shipped (28 sliced, 18 exempt/kept)", counted from the file, and the note's hand-written status tally was replaced by a counted one — third instance of the never-hand-write-a-count rule this week.
