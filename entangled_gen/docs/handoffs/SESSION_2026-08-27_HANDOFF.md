# SESSION 2026-08-27 HANDOFF — six scenes in one night, and the camera was in the ceiling

(Real date 2026-08-12, one overnight autonomous session, the user in the
loop from ~11:30. REVIEW_LOG **R-S2-129..135** — seven entries. Previous
handoff: SESSION_2026-08-26 (compose canon matured). Tree COMMITTED
through **85cc1a3**; ⚠ **push still owed** — the session's git push was
permission-blocked, run `git push` once by hand.)

**CLOSE-OUT STATE: everything quiet, nothing running, nothing owed but
the push.** All edits committed with their log entries. The viewer has
all six scenes (viewer/data/fresh04..09.bin, each written by its own
run's prep_viewer).

## 0. THE ONE-LINE TRUTH

**SIX scenes passed in one night (fresh04..fresh09) — fresh08 with ZERO
intervention (one command, 46 stages, 78 min: the bar met on the new
fix stack) — and the night's biggest find is that two "dud worlds" were
never duds: our pano camera sat 1.6 RAW UNITS above the floor, which at
Marble's arbitrary export scale put it inside one room's ceiling and
ABOVE another's (R-S2-134, 8 detections → 505 after the fix).**

## 1. WHAT CHANGED (R-S2-129..135, all committed, no threshold moved)

| R-S2 | fix |
|---|---|
| 129 | a REPORT LINE killed lift: print_gap_stats on zero floor-ish lifts → empty arrays print `(none)` |
| 130 | a priors reply with no JSON killed scale → retry once, then EMPTY priors = the module's own MIN_N degrade-to-1.0 path; only parsed replies cached |
| 131 | a zero-object funnel shipped an empty `judged` layer + a gate stamping contradiction → build_graph now REFUSES (exit 2) with the receipt: "this world gave us nothing measurable" is a fleet verdict, not a scene |
| 132 | **the §4 trap CLOSED**: under `--phase all`, `--from/--until` scope the WHOLE chain (earlier phases = prerequisites, skipped loudly; later-than---until dropped). Explicit-phase mismatches and typo'd stage names now REFUSE instead of silently running everything |
| 133 | a degenerate polygon fit (3 segments, two 70 m long, ONE wall per axis) folded silently and crashed compose 26 stages later → the fold refuses < 2 axis walls per axis and routes into the EXISTING v1-degrade path |
| 134 | ⭐ **the eye-height fix**: stitch eye = EYE_FRAC (1.6/2.8) of measured room height, never an absolute raw distance. Identical camera on metric rooms; correct sightline on off-scale ones. fresh05: 48→330 detections, 15/20→20/20 cams. fresh07: 8→505 |
| 135 | the parallel-run experiment + GLTS numbers (below) |

## 2. THE SCENES (all final gate PASS, all in the viewer)

| scene | world | story |
|---|---|---|
| fresh04 | 0f874584 bedroom | healed: R-S2-128 voiding verified live, obj_000 = console table (not the stale bed); 0 clips |
| fresh05 | f47d4f9d living room | condemned as a dud at 03:00, exonerated at 10:00 by the eye fix; 51/51 evidence, 30 placed / 3 receipts |
| fresh06 | eee7c890 painterly bedroom | polygon fit escaped the room → R-S2-133; passed on the degraded v1 shell; 0 clips, 10 placed / 3 receipts |
| fresh07 | 881c3d9a stylized living room | the second "dud" (eye ABOVE the ceiling); after the fix: 101 nodes, 99/99 evidence |
| fresh08 | 4e4ef9d4 modern bedroom | ⭐ **THE BAR: one command, zero intervention, 78 min, PASS** |
| fresh09 | 18ae5c1e office | first fully COLLIDERLESS world end-to-end; 54/54 evidence; ran in PARALLEL with fresh05 |

## 3. PARALLEL RUNS + GLTS (R-S2-135)

- **No crossfire.** fresh05 + fresh09 concurrent (staggered: B's GPU
  intake under A's LLM judges), then two GLTS runs on top. Zero file
  collisions, zero clock-over-lock samples, zero VRAM-over-11GB
  samples, no contention-attributable judge failures. **Cost is
  wall-clock only** — everything shares the one claude.exe lane.
- **GLTS layout-only (steps 0-13): fresh04 ok 185.9 min / 280 calls;
  fresh06 ok 192.5 min / 279 calls.** Ours the same night: a FULL
  46-stage scene in 78 min. Comparison filed:
  `out/comparison_20260812T193036Z.{json,html}` (fresh06 highlights:
  prompt nouns ours 12/22 vs GLTS 6/22; objects ours 31 measured vs
  GLTS 11 invented; GLTS guessed 26.6 m² for a 14.9 m² room).
- **Operational law for fleet nights:** launch long runs DETACHED (WMI
  Win32_Process.Create — the watch_gpu pattern). Background tool-shell
  tasks were mass-killed mid-run at 09:15; every pipeline scene resumed
  mid-stage with nothing lost, GLTS (no mid-run resume) repaid its
  first hour in full.

## 4. THE REVIEW AGENDA (the user wants to walk the output WITH you)

1. Start the viewer: `python viewer/serve.py --port 8321` → all six
   scenes in the dropdown. The user judges ALL visuals — you never
   conclude from images.
2. Comparison page:
   `D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\comparison_20260812T193036Z.html`
3. Standing eye-calls from the 08-26 handoff §3, now with more scenes
   to look at: headboard→bed stand-in (fresh04), the bar nudge
   (0.65→0.70 would admit the rug's doormat), wall-definition,
   invented-anchor authority, panels-as-objects. NONE are yours to
   decide.
4. NEW user decisions this night surfaced: (a) two-lane staggered
   fleet — proven safe, needs their ruling to change run_fleet; (b)
   R-S2-134 means previously-condemned starved worlds deserve
   re-examination (corpus may be richer than the catalog suggests);
   (c) GLTS at stage 15 (Blender) for a scene or two, if the
   comparison should carry final GLBs.

## 5. TRAPS (updated)

- The §4 `--from/--phase all` trap is FIXED (R-S2-132) — but the new
  semantic means `--from X` SKIPS earlier phases; if you actually want
  the funnel re-run, say `--phase core --from frame`.
- Long runs from tool shells DIE with the shell. WMI-detach anything
  over ~10 min (see R-S2-135; watch_gpu.ps1 header has the pattern).
- GLTS has NO mid-run resume — never kill it casually.
- The preview file is rewritten mid-run; never judge it in flight.
- ONE watch_gpu; the GPUClockLock task re-applies the clock lock at
  boot (unelevated shells can neither apply nor query it — verify via
  clocks.sm ≤1500 in gpu_watch.csv under load).
- pipeline_map.html S4/PLACE/JIGGLE/CHECK card notes are still stale
  w.r.t. R-S2-115..127 — map edits need the user's blessing; bring
  exact proposed text.

## 6. THE PROMPT FOR THE NEXT AGENT (verbatim, also in NEXT_SESSION_PROMPT.md)

```
Continue the scene-pipeline work. Repo: D:\T\Documents\GeorgiaTech\Summer2026\scene-pipeline\entangled_gen
READ FIRST, in order:
  1. docs/SESSION_2026-08-27_HANDOFF.md — all of it. §1 = the fix stack
     (7 entries), §4 = the review agenda, §5 = the traps.
  2. docs/PARKED.md — do not work on these.
  3. REVIEW_LOG R-S2-129..135 — skim headers; read any entry you touch.

THE SESSION OPENS WITH A REVIEW: I want to walk the night's output with
you. Start the viewer (python viewer/serve.py --port 8321; launch it
DETACHED via the WMI pattern or it dies with your tool shell), open the
comparison page (out/comparison_20260812T193036Z.html), and take me
scene by scene through fresh04..fresh09 — what placed, what's absent
and why (every absence has a receipt), what changed under which R-S2
ruling. I judge all visuals; you narrate the receipts. Bring the
standing eye-calls (handoff §4.3) as they come up on screen. Never
decide them yourself.

AFTER THE REVIEW, the road continues: 1) git push (owed). 2) The first
fleet night — I pick 3-5 worlds, you run run_fleet.py and read the
morning report the way I will; sequential unless I rule on the two-lane
design. 3) R-S2-134 re-examination sweep of previously-condemned
worlds, if I say go.

HOUSE RULES: no observation-triggered tuning; fresh scenes are the only
evidence; trust the primary record over summaries; every fix gets a
REVIEW_LOG entry with the contract intro; fixes at source,
scene-agnostically; GPU clock-lock protocol, ONE watch_gpu; long
processes launch DETACHED; plain English everywhere.
```

## 7. WHERE EVERYTHING IS

Same table as SESSION_2026-08-25C §6, plus: tonight's record =
REVIEW_LOG R-S2-129..135; commits 7337ec3, 1ade940, 3f1b8aa, 7dfda88,
85cc1a3; the comparison = out/comparison_20260812T193036Z.{json,html};
GLTS raw = Research\code\working\TreeSearchGen\output_ovm_fresh0{4,6}\;
console logs of the detached relaunches = the session scratchpad
(ephemeral, already mined into the log entries).
