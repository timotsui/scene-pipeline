# GO / NO-GO — the 100-scene batch (written 2026-08-11C, after fresh04)

## THE CONTRACT — what this document is

**What it gets:** the evidence of 2026-08-11 — fresh02 (six resumes),
fresh03 (two resumes, both fixes validated), fresh04 (ZERO resumes,
the bar met), and the day's code changes.
**What it decides:** whether the machinery is ready for an unattended
batch, and what that batch honestly costs. It does NOT pick worlds —
world selection is the user's, explicitly (interiors only, user ruling
2026-08-11C; the worlds gate is open work).
**What a mistake looks like:** arithmetic that quietly assumes cache-warm
timings, or a "go" that hides the known open items.

## THE VERDICT: GO, with the stated limits

`python run_scene.py --scene fresh04 --bundle <never-run colliderless
world>` completed **all 46 stages, one command, zero intervention, final
gate PASS** (R-S2-114). That was the bar (SESSION_2026-08-25C §2), and it
was met on the hardest available terms: a world the pipeline had never
seen, with no collider, immediately after two scene-agnostic fixes.

## THE HONEST ARITHMETIC

- **~65 min per fresh scene** (fresh04: 3916 s, all 46 stages, caches
  cold where a fresh scene's caches ARE cold — vocab, propose_edits and
  consistency only buy re-runs, R-S2-105/109).
- **Sequential by design**, one scene at a time, GPU clock-locked
  (`nvidia-smi -lgc 0,1500` from an ADMIN shell; dies on reboot; the
  boot task re-applies — verify per POWER_CRASHES.md).
- **100 scenes ≈ 108 machine-hours ≈ 4.5 days** of continuous runtime.
  25 scenes ≈ 27 h; 50 ≈ 54 h. Plan nights, not an afternoon.
- **Corpus: 318 runnable worlds** since the collider became optional
  (R-S2-110/111; catalogue rebuilt). Which of them are worth running is
  the user's call — `CORPUS_REVIEW.html` is the review surface, box-room
  interiors are the stated constraint (PARKED §3: the shell cannot
  represent slanted walls).

## WHAT THE BATCH WILL DO AT SCALE (known, counted, parked)

- `slice_fallback` counts vary widely by room (fresh04: 2/39; bedroom:
  55/82). Reported per scene in every fleet report; PARKED §1.
- `scene_scale` degrades to 1.0 when rulers disagree (fresh04 did,
  spread 0.25) — unnormalised scenes ship and say so.
- `fit_feedback` verdicts land on disk and nothing re-shops (PARKED §5).
- A crash mid-batch is a reboot: the clock lock re-applies at boot, the
  fleet's `--resume` skips finished scenes, `write_atomic` + the scene
  lock protect the graphs.

## THE ONE UNPROVEN PIECE

A fleet that EXECUTES several scenes in sequence has not run: tonight
proved one-scene execute (08-25) and three-scene resume-skip
(R-S2-114). The first real batch night doubles as that proof — run it
`--stop-on-fail` OFF, read the morning report, and expect the FIRST
night to surface fleet-level defects the same way fresh scenes surfaced
stage-level ones. Start with a 3–5 scene night before committing to 100.

## RECOMMENDED FIRST NIGHT

3–5 box-room interiors from the runnable set, user-picked, launched as
one `run_fleet.py --scenes ... --resume` in the evening with the clock
lock verified and ONE watch_gpu instance. Read the morning report
before scaling further.
