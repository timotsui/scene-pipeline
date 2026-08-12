# SESSION 2026-08-11 HANDOFF — THE FOUR-RUN NIGHT (carve hardened, user-passed)

(Real date 2026-08-06 evening → 08-07 early; names run ahead. Continues
SESSION_2026-08-10_HANDOFF.md. That session's queue items 1+2 are
RESOLVED: R-S2-26 user gate PASSED, bedroom regression WAIVED by user.
Evidence trail: REVIEW_LOG R-S2-26 verdict + R-S2-27/28/29/30.
docs/CARVE_SLICEVOTE.md carries the design update section.
The cone-map session's base carve IS committed (0734d50/5e2a353/
51613eb); TONIGHT'S DELTAS are uncommitted: carve_slicevote.py
(tunnel/exemptions/guard/ladder), viewer/serve.py (slicevote layer),
pipeline_map.html, CARVE_SLICEVOTE.md, REVIEW_LOG, this handoff.
Commit is the user's call, queued below; push also pending.)

## WHAT HAPPENED (one line each)

1. User passed R-S2-26 (the 8-object gate) with caveats routed: sofa
   L → multiplicity judge; shaved chairs → compose snap will catch;
   matching chairs = judge_same_product.py (confirmed half-built);
   bedroom regression waived ("we don't run bedroom again").
2. RUN 1, whole living blind (44 obj, ~10 min): furniture fine, but
   ceiling lights blew up ×288–×5027 (floor-anchored height band
   slices the room column; thin sp0 → cluster fallback) — R-S2-27.
3. User ruled: context behind the slice, then refined mid-flight to
   the VIEW TUNNEL (full scene minus camera→slice hole); ceiling
   objects exempt (geometric, no label lists). RUN 2 (~18 min):
   blowups gone, chair heights partly recovered (0.85-0.89 vs run-1's
   0.49-0.58 shave), but no_redetect 6→16 and obj_004 book + obj_038
   window elections went EMPTY — R-S2-28.
4. User: "the picture is the big problem — anything can be a picture"
   (obj_002 ×369, wall-flush = no plan footprint, wedge slices a room
   column) + outlier rule. RUN 3 (~15 min): kept_wall exemption
   (0.20 m flush + 0.30 m thin) + outlier guard 8× (fired ZERO times)
   — R-S2-29, USER PASS ("i think this is good").
5. Slicevote layer wired into the 3D viewer (serve.py box_sources,
   cyan, "slice-vote carve (R-S2-29 user PASS)"); server restarted
   (WMI-detached).
6. User designed the DETECTION ESCALATION LADDER: object-height cards
   → (≥3 of 4 unproductive) EYE-HEIGHT cards as extra voters (Marble
   eye-height capture bias) → (empty) isolation retry on black →
   (still empty) original box. RUN 4 (~20 min): book went 0/4 → 4/4
   detections at eye height → real 0.40×0.08×0.47 box; only object
   to escalate scene-wide; ZERO kept-by-failure left — R-S2-30, USER
   PASS ("awesome").

## FINAL STATE

- carve_slicevote.py = the full ruleset (docstring is the contract):
  exemptions → prism/wedge slice → tunnel cards → ladder → 6+-voter
  election gate 3 → arm assignment → outlier guard. rule.tiers records
  each object's escalation path.
- Living run 4: 45 objects = 28 carved_arm / 2 carved / 8 kept_wall /
  7 kept_ceiling. (45 vs earlier 44: exemptions catch an object that
  previously died silently at the <100-dot skip — understand before
  runner wiring.)
- Viewer :8321: "slice-vote carve" box layer (cyan) + cone-map layer
  (temporary). Server pid changes on restart; /conemap.json and the
  slicevote entry need the current serve.py.
- Files: out/living_marble/{scene_manifest_slicevote_preview.json,
  cone_map.html, pool_retake/slicevote_report.json, conemap.json,
  slicevote_full_run{,2,3,4}.log}. Map card + node current.

## QUEUE (user 08-07: "next we keep running this along the pipeline")

1. COMMIT + PUSH (user's call): the 5 modified files + this handoff
   (see header). The graph/compose helpers were already committed in
   0734d50.
2. Doubts into the record: graph/record_carve_doubts.py output →
   description-making pass → node cards carry arm/culled/fallback/
   exemption doubts (the standard record-then-judge flow). NOTE: rerun
   record_carve_doubts.py first — carve_doubts.json predates runs 2-4.
3. Multiplicity judge (PART_OF_STRUCTURE) — still unbuilt; obj_011
   sofa L is its first case; carve doubts are its typed evidence.
4. Same-product judge verdicts (judge_same_product.py — grouping
   verified, claude.exe verdicts NEVER run) → user review → wire
   shopping (one asset per SAME_PRODUCT group at canonical size).
5. S1/compose consumes scene_manifest_slicevote_preview.json (snap /
   supported-by on carved boxes — the chairs' shaved bottoms are the
   test case the user predicted compose would fix).
6. Runner wiring + map promotion (draw the carve node solid) — only
   after 2-5 prove out downstream.
7. Carried review opens (R-S2-30): thin boxes obj_010/020/041; surprise
   wall exemptions obj_017_c00 magazine + obj_022 plant (eyeball their
   originals); degenerate-ballot rule still unimplemented.

## GOTCHAS (carried + new)

PYTHONUTF8=1 MANDATORY when redirecting carve stdout to a file
(cp1252 dies on the ≥ glyph — cost one crashed launch). out/ root
lives OUTSIDE the repo: CS-8903-OVM/week7/entangled_gen/out (via
local_paths.json — a repo-relative log path cost another launch).
Full living run ≈ 15-20 min under the 1500 MHz clock lock (do NOT
trust gut estimates — check the log mtimes; user caught a phantom
"2-hour" claim). Clock lock survives since the 08-06 02:xx recovery
(reboot 01:22 predates it); re-lock after any reboot
(nvidia-smi -lgc 0,1500, admin). Transient votectx plys ≈ 250 MB × 4
per object, self-deleting. Renders are deterministic (byte-identical
reruns → identical detections) BUT any slice-geometry edit ⇒ wipe
slices/vote_*.png manually. --only runs CLOBBER the whole-scene
report/manifest/conemap — full rerun is the clean path after logic
changes. HF_HUB_OFFLINE=1 for the seg models. Viewer restarts: WMI
Win32_Process.Create only.
