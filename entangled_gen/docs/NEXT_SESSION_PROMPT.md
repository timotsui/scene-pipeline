# The prompt for the next session (written 2026-08-11 late, session C)

Copy everything below the line into the fresh session.

---

Continue the scene-pipeline work. Repo:
D:\T\Documents\GeorgiaTech\Summer2026\scene-pipeline\entangled_gen

READ FIRST, in this order — do not skip, and do not work from summaries:
1. docs/SESSION_2026-08-25C_HANDOFF.md — §0 (the one-line truth), §2
   (your job, with the order of work), §3 (the trap list), §4 (things
   that look wrong but are right)
2. docs/PARKED.md — five parked items; do not work on them
3. graph/stages.py — the pipeline IS this file: four tuples, 46 stages

THE GOAL: reassure that the pipeline is smooth, runnable and correct, as
preparation for the 100-scene batch. The corpus/world-selection decision
is MINE and not your job.

THE HONEST STATE: yesterday a raw Marble bundle became a furnished room
through all 46 stages with the final gate green — but it took SIX
fix-and-resume cycles, because six defects stood in the way. They are
fixed. **The pipeline has NEVER completed in one uninterrupted
invocation.** That is the bar:

    python run_scene.py --scene <new> --bundle <world-folder>

on a world that has NEVER run, all 46 stages, ZERO intervention, final
gate PASS. If a stage fails: fix at the source, scene-agnostically, log
it (REVIEW_LOG at the NEXT FREE R-S2 number — a parallel session's
docs/PLAN_COLLIDER_OPTIONAL.md has reserved 110+ — contract intro
first), resume — and then
the bar becomes one MORE fresh world clean, because a resumed run is not
the proof. Before the run do the static sweep and gate checks in
handoff §2; after it, prove the fleet path and write the go/no-go with
honest arithmetic (~55 min/scene, sequential, 29 runnable worlds today).

═══ THE WAYS THIS SESSION WILL GO WRONG IF YOU LET IT ═══

1. YOU WILL BE TEMPTED TO TREAT A PASSING CLONE AS EVIDENCE. Six of the
   eight defects found yesterday were invisible on every dev scene,
   because dev scenes carry artifacts the pipeline no longer produces.
   Only a never-run world counts. autotest_* and fresh02 are for gate
   regression checks, nothing more.

2. YOU WILL BE TEMPTED TO RUN A MODULE BY HAND ON A REAL SCENE to check
   something. That is how fresh02 got its four (true, documented) WARNs
   — twice, in the same session that built the locks against it. Use a
   throwaway clone or don't do it.

3. YOU WILL SEE A THRESHOLD A SCENE TRIPPED AND WANT TO MOVE IT. Rule
   #1: observation-triggered tuning is contamination even when the fix
   looks generic. Yesterday's frame-contract change was legal only
   because a 34-world census and my explicit ruling backed it. Measure
   first, then ask me.

4. PICK THE VERIFICATION WORLD CAREFULLY: box-shaped rooms only (the
   shell cannot represent slanted walls — PARKED §3; fresh02 is an attic
   and its geometry is knowingly wrong). Green "runnable" filter in
   marble-harvest/catalog/CORPUS_REVIEW.html, read the prompt, confirm
   no out/*/bundle_path.txt already claims it.

5. GPU: the machine hard powers off under unlocked GPU burst. Clock lock
   protocol and its verification limits are handoff §3.5 — you cannot
   query the lock; only the apply-time receipt or clocks.sm ≤1500 under
   load proves it. One watch_gpu.ps1 instance ONLY.
