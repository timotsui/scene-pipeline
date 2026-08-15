# SESSION 2026-08-30 HANDOFF — the comparison night: 4 wave + 6 pairs, ALL DONE; next = REVIEW & EVALUATE

(Real date 2026-08-13, user asleep for the night phase, awake from
mid-morning. REVIEW_LOG **R-S2-169..170**. All committed AND PUSHED
(0fa032b, d926db3 + this wrap). PIPELINE.md carries the two contract
changes. The user's closing words: "Next session I want to review and
evaluate." That is the whole next session: THE USER JUDGES, the agent
drives the viewer and brings receipts.)

## 0. THE ONE-LINE TRUTH

Everything the 08-29 handoff ordered ran to completion — the wave
(4/4 PASS, fresh05 de-tilted first) and all SIX overnight pairs
(ours full chain + GLTS layout, filed in out/comparison.html); credit
never died; two real bugs were found by the receipts and fixed at
source (R-S2-169 sub-round crash, R-S2-170 rotation_check's silently
dead reference sheets).

## 1. THE SCORE (all filed in out/comparison.html, ONE fixed sheet)

Wave: fresh05 (yaw −2.25° applied, verified ~0), fresh06, fresh08,
fresh09 — full chains through sub_rounds → merge_subs → gravity →
prep_viewer. GPU clock lock held (max 1500 MHz all night).

| pair | ours | GLTS | GLTS area guess |
|---|---|---|---|
| natural_living | PASS (1 recorded hole: obj_144) | 105.8 min / 172 calls | +1.9% |
| sunlit_office | PASS (first refs-live rotation: 13 non-zero) | 150.3 min / 234 calls | −36% |
| blue_living | PASS 54 min, zero failures | 120.8 min / 184 calls | +2.3% |
| panel_bedroom | PASS 45 min, zero failures | 123.0 min / 196 calls | −39% |
| arch_bedroom | PASS (arch = expected vertical-plane approx) | 132.5 min / 179 calls | −29% |
| plaster_bedroom | PASS (two-room live test) | 94.3 min / 147 calls | **−57%** |

Paper-ready pattern: GLTS invents 7–10 objects vs ours 15–60 measured;
area guesses swing −57%…+2% (worst exactly on the two-room hard case);
GLTS's own search loses 1–11 of its retrieved furniture per scene.

## 2. CODE CHANGES (both pushed, PIPELINE.md updated)

- **R-S2-169 (0fa032b):** cp3's `boards_used` summary sorted None
  (wall-rider subs) against ints and killed the anchor. One line;
  fresh05 healed by a sub_rounds re-run (re-run guard held: 7 skipped,
  1 merged, no duplicates).
- **R-S2-170 (d926db3), THE FIND OF THE NIGHT:** rotation_check read
  the RETIRED pano_crops/ dir for reference photos — a dir NO current
  scene has — so since the reorg EVERY facing judgment ran
  plausibility-only with zero ref sheets, looking healthy. Fixed with
  the precedented rule (member img → rig_sp0/crops → legacy; third
  appearance of the retired-dir class after pick.py and
  node_evidence). ⚠ CONSEQUENCE FOR EVALUATION: rotation receipts
  BEFORE sunlit_office are plausibility-mode; sunlit onward are
  refs-live (sunlit: 44/45 answered, 13 non-zero, 898 s).

## 3. THE REVIEW AGENDA (next session = the user judges; bring these up ONE AT A TIME with receipts)

1. **The viewer walk, 10 scenes:** http://localhost:8321/?scene=<name>
   (fresh05/06/08/09 + the six new). out/wall_review.html now carries
   ALL TEN scenes (regenerated at wrap). Walk order suggestion: the
   wave four first (does the outline hold on 05/06/09 like it did on
   08?), then new scenes simplest→hardest, arch + plaster last (the
   two ⚠ cases: arch's alcove trace, plaster's partition).
2. **out/comparison.html** — the six-pair evidence for the paper.
   Known metric caveat FIRST (§4.1) before quoting numbers.
3. The six filed judgment calls in §4.

## 4. FILED FOR THE USER'S JUDGMENT (untouched, receipts in night logs
at out/night_logs/<scene>_{ours,glts}.log — repo out root)

1. **Comparison physics rows count BOXES, not gravity-settled meshes**
   — "ours 35 floating" on sunlit is pre-gravity; the GLB already
   fixed it. compare_methods.py metric question BEFORE the paper.
2. **All four wave scenes still stamp "vote NOT canon-eligible
   (partial/multi-revision)"** — the wave was expected to clean these.
   From-shell re-votes but lift-minted boxes predate the revision.
   Question: is the stamp too strict, or does canon need a from-lift
   run?
3. **natural_living obj_144:** no standpoint can see it (all 95 inside
   furniture/blocked) — completed via the SANCTIONED --allow-holes
   (gap recorded IN the layer, AUTOMATION_READINESS §4). Re-run hard
   if the user prefers.
4. **cp1 StopIteration on anchors with no fitted pose** (fresh08
   obj_008 through-glass, fresh09 obj_039 wall shelf) — honest
   failures, ugly raw-traceback receipts; pre-skip with a stated
   reason is a fleet-semantics call.
5. **Ceiling-light support class again** (fresh05 obj_036 gravity
   dropped 2.21 m to floor; fresh09 flags two more "NEAR floor"
   fallbacks) — the R-S2-168 support-judge question grows.
6. **Rotation uniformity:** scenes before the R-S2-170 fix
   (natural_living, all wave scenes) carry plausibility-mode rotation
   receipts. Option: re-run `--phase compose --from rotation_check`
   per scene (~15 min each + closing/sub/gravity tail) for uniform
   refs-live receipts before evaluation numbers are quoted.
7. (minor) fresh05 WARN "scale output older than input" — explained:
   the yaw apply rewrote manifests after scale ran. A scale re-run
   clears it if it nags.

## 5. TRAPS

- **TWO out/ roots.** DATA lives in
  `CS-8903-OVM\week7\entangled_gen\out\` (scenes, comparison.html,
  wall_review.html, NIGHT_STATUS mirror). The REPO's
  `entangled_gen\out\` holds night_logs/ + NIGHT_STATUS.md canonical.
  paths.py decides; don't hand-build scene paths.
- GLTS output roots: `Research\code\working\TreeSearchGen\
  output_ovm_<scene>\` — the inner log.ansi lives at DIFFERENT depths
  per run; watchers keyed on it false-alarmed twice. GLTS step 13 can
  go 45+ min wrapper-quiet while healthy.
- GLTS has NO mid-run resume; ours resumes `--from` any stage.
  Two-lane max stands (R-S2-135). Launch discipline unchanged:
  WMI-detach, ONE watch_gpu, clocks ≤1500 verified (held all night).
- New-scene GLTS needs only bundle_path.txt — pre-writing it lets
  GLTS start before ours' intake (used all night, works; run_scene
  accepts the pre-made file: "already points at this bundle").
- The stale ANTHROPIC_API_KEY gotcha never fired tonight (claude.exe
  bridge behaved).
- pipeline_map.html was user-blessed for PH2r/PH2g (047ae64) BEFORE
  tonight; R-S2-169/170 are fixes inside existing stages — no map
  change expected, but the map is the authority: confirm with the
  user if anything looks off during review.

## 6. THE PROMPT FOR THE NEXT AGENT (verbatim — THIS HANDOFF IS THE
ONLY FILE; NEXT_SESSION_PROMPT.md just points here)

```
Continue the scene-pipeline work.
Repo: D:\T\Documents\GeorgiaTech\Summer2026\scene-pipeline\entangled_gen
READ docs/SESSION_2026-08-30_HANDOFF.md IN FULL — it is the one file.
Skim REVIEW_LOG R-S2-169..170; read entries you touch.
docs/PARKED.md items stay parked.

THIS SESSION IS THE USER'S REVIEW & EVALUATION of the comparison
night: 10 finished scenes (4 wave re-runs + 6 new paired scenes) and
the six-pair ours-vs-GLTS sheet (out/comparison.html).

YOUR JOB: drive, don't judge. Serve the review agenda in §3 one item
at a time — viewer walks (:8321), wall_review.html (all 10 scenes),
then the seven filed calls in §4 WITH their receipts (night logs, run
logs, REVIEW_LOG entries). The user rules on each; you file rulings
in REVIEW_LOG with the contract intro and fix at source only what
they order, scene-agnostically.

BEFORE QUOTING COMPARISON NUMBERS anywhere: surface §4.1 (physics
rows count boxes, not the gravity-settled GLB) and §4.6 (pre-fix
scenes' rotation receipts are plausibility-mode) — the user decides
whether numbers ship as-is or after re-runs.

HOUSE RULES: no observation-triggered tuning; the user judges ALL
visuals; trust the primary record over summaries; plain English;
long processes DETACHED (WMI); ONE watch_gpu; clock lock verified
under load; two-lane max; descriptive scene names.
```

## 7. WHERE EVERYTHING IS

- Commits: 64c6310 → 0fa032b → d926db3 → (this wrap). All pushed.
- Comparison: out/comparison.html + .json (week7 out root).
- Sheets: out/wall_review.html (ALL 10 scenes, regenerated at wrap);
  out/<scene>/room_shell_steps.png per scene.
- Night record: out/NIGHT_STATUS.md (both out roots) — the full
  batch-by-batch log of the night; docs/plans/PLAN_NIGHT_2026-08-13.md
  — the strategy + credit-death analysis it ran under.
- Night logs: repo out/night_logs/<scene>_{ours,glts}.log; wave logs
  at repo out/<scene>/logs/night_wave.log.
- GLTS raw outputs: Research\code\working\TreeSearchGen\
  output_ovm_<scene>\ (incl. 13_furniture_layout.json/png).
- Viewer: python viewer/serve.py --port 8321 (route-table server,
  already detached); payloads viewer/data/<scene>.bin ×10, all fresh.
