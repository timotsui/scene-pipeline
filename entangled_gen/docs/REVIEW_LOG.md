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

_(further entries appended as artifacts land)_
