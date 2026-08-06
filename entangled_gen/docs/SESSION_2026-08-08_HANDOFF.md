# SESSION 2026-08-08 HANDOFF — CRASH DAY + N1 NORMALIZATION CANONIZED + THE CLEAN RECORD

(Real date 2026-08-06; handoff names run ahead — see PLAN_SCENE2_LIVING.md.)
Continues SESSION_2026-08-07_HANDOFF.md. READ PLAN_SCENE2_LIVING.md TOP TO
BOTTOM first — it carries the full evidence trail of a very eventful day.

## WHERE WE ARE (the resume point)

**living_marble: CLEAN RUN bundle → graph record DONE, at USER GATE
R-S2-19.** One gapless 9m21s run of committed code (stage_timings.csv C_
rows): intake → pano → crops → vocab → seg → lift → recenter → f30 →
**N1 scene_scale (s=0.698 applied, blind verify = 1.000 exactly)** →
shell → envelope → record (88 nodes / 335 edges, self-checks PASS).
Doors 2.14 m, room 3.13 m. Judges NOT run — the record is the gate.

**NEXT: user record verdict → run judges J0–J7 → compose chain → reviews**
— all for the first time on a true-meter scene. "We continue to debug"
(user's parting word). Viewer :8321 (record boxes = audit/archive →
"graph record (audit)" checkbox; main-row "scene model" needs
graph[resolved], exists only after J7). OPEN OFFER user didn't answer:
move the record layer to the HUD main row while it's the review surface.

## THE DAY'S LANDINGS

1. **CRASH SOLVED**: machine hard-off during GPU seg (01:18) = the known
   power-delivery fault. REAL FIX VERIFIED: `nvidia-smi -lgc 0,1500`
   (admin; -pl is OEM-locked). Whole day under the lock, peaks ~85–105 W,
   zero crashes. ⚠ LOCK RESETS ON REBOOT — reapply before ANY GPU work.
2. **N1 · scene_scale CANONIZED** (map node + card, PIPELINE.md section):
   measured normalization via LLM class-size priors; **STATE TRANSFORM
   ruling (user): multiply the meter-bearing state (ply, collider, frame,
   manifests, pool, pano eye), NEVER re-run P1–P5.** The P1-re-entry
   experiment (archived) proved re-sensing injects variance (0.846
   wide-spread vs multiply=exact). Marble scale varies per world:
   bedroom ~1.0, living 0.698.
3. **STALE-CACHE DISEASE — 3 source fixes** (all the same content-
   fingerprint pattern): pano_recenter rc2_NN shot cache (index-keyed →
   16 false refutations), pano_stitch cube-face cache (stale faces
   re-stitched under a fresh eye POISONED an afternoon sensing pass —
   forensics in plan doc), scene_scale verify-vs-apply record clobber.
4. **PRIME DIRECTIVE RE-ELEVATED to RULE #1** (memory + MEMORY.md):
   the TV-synonym incident — observation-triggered tuning during a test
   scene = answer-key contamination even if the fix looks generic. The
   doctrine-legal fix (generic LLM detector-phrasing pass in vocab_build)
   went in instead and WORKS (tv/couch/drapes/… zero scene knowledge).
5. Other source fixes: seg_batched per-view detections persistence,
   paths.frame_block() fallback (11 files), room_shell extent clip
   (open-plan floaters; bedroom regression bit-identical), G1's envelope
   input satisfied by running the parked envelope stage.
6. **Findings archive** (pre-norm run, still valid as findings):
   TV detected-then-refuted-then-placed arc; 2/4 swap placements
   geometrically broken; sub layer thin (0 children attached);
   up-aimed cam-verify FAIL cluster (short-ceiling suspect).

## STATE / FILES

- Scene dir: ONLY clean-run artifacts + `archive_2026-08-06_pre_
  normalization/` (compose_prescale_era · postN1_partial_chain ·
  poisoned_pass2_and_scaled_state) + logs/ledger + LLM caches.
- REVIEW_LOG: R-S2-8..19 (8..17 = pre-norm run, now findings-only;
  18 = normalization PASS; **19 = the live gate**).
- Commits this session: 2080c98 … 2204363 (12). PUSH = user's job.
- QUEUED: measure-from-graph[resolved] refinement (0.74-vs-0.699
  fragment pollution) · judge chain on true meters · multiplicity judge ·
  wall channel · level-2 riders · anchor re-shop · size-normalization
  ripple checks at S1–S4 (real-size assets in a 3.13 m room should now
  JUST FIT).

## WATCH LIST (carried + new)

Room yaw (unchanged) · anchor-loop five + cp2 board constants (now
meaningful for the first time — they were tuned in true meters!) ·
Y_BLOCK_MIN 0.10 · judge caches: bedroom-era entries are content-keyed,
harmless · viewer HUD eyeball STILL pending from 08-07.
