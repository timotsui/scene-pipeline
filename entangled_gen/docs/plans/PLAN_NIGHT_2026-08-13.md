# PLAN — NIGHT OF 2026-08-13: the wave, then six paired scenes

**What:** (1) Re-run fresh05/06/08/09 from the shell stage so they pick
up the convexity-night wall fixes. (2) Run the six user-picked new
scenes, each as a PAIR: Ours (full chain) + GLTS (layout-only), filed
into out/comparison.html.

**Why:** The wave ships the approved wall outline and un-crushes
05/06/09; the pairs build the comparison corpus. Pairs are the unit of
value — a scene with only one side done is worth almost nothing.

**Look for (morning review):** wall_review.html + room_shell_steps.png
for the four wave scenes (walls on the correct side, no crushed items,
fresh08 bay open); out/comparison.html rows for each completed pair;
sub-fleet tallies + gravity settle receipts (their first fully
automatic outing); viewer at http://localhost:8321/?scene=<name>.

## USER INSTRUCTIONS IF YOU WAKE UP

- **Review without stopping anything:** the viewer (:8321), the sheets,
  and out/NIGHT_STATUS.md are read-only — look anytime.
- **Status:** `out/NIGHT_STATUS.md` — updated at every batch boundary;
  says what is done, what is running, what is next.
- **To stop the night:** create the file `out/STOP_NIGHT.txt` (any
  content), or just message the Claude session. I check before every
  new launch. In-flight lanes are left to finish (Ours resumes anyway;
  killing GLTS mid-run wastes the whole run) — nothing NEW starts.

## RUN STRATEGY (orchestrator's design, per the handoff mandate)

**Lane budget: 2 claude lanes maximum at all times** (two-lane rule;
R-S2-135: 3-way contention stretches wall-clock up to 3x and triples
GLTS).

**Phase 1 — THE WAVE (Ours-only lanes, fully resumable):**
- First: apply fresh05's measured −2.25° yaw (scene_yaw.py; *_preyaw
  backups; partial crash → restore backups before anything).
- Batch W1: fresh05 + fresh06 in parallel (2 lanes).
- Batch W2: fresh08 + fresh09 in parallel (2 lanes).
- Command: `python run_scene.py --scene <s> --phase all --from shell`
- Receipts read after each batch as the user would (sub fleet tallies,
  gravity settles, wall sheets).

**Phase 2 — THE OVERNIGHT (six sequential batches, one pair each):**
- Batch = ONE scene: Ours lane + GLTS lane launched together, next
  batch only after BOTH finish and the pair is filed.
- Order (simplest box rooms first, user-fixed): natural_living,
  sunlit_office, blue_living, panel_bedroom, arch_bedroom,
  plaster_bedroom.
- Ours: `python run_scene.py --scene <name> --bundle <root>\<world-id>
  --phase all` (bundle root:
  `...\CS-8903-OVM\week8\marble-harvest\worlds\`; audited dry-run
  exit 0 on a virgin scene 08-13).
- GLTS: `python glts_run.py --scene <name> --end-step 13` (layout
  only, claude bridge; NO mid-run resume).
- After each batch: `python compare_methods.py` files the pair into
  out/comparison.html; NIGHT_STATUS.md updated; STOP file checked.

**Why pair-parallel, batches sequential (credit-death analysis):**
The claude subscription is shared and may die without warning.
- Credit dies during the WAVE: both lanes are Ours → both resume
  mid-stage later. Loss ≈ zero.
- Credit dies during a PAIR: at most ONE pair in flight. The Ours side
  resumes; the GLTS side restarts from zero. Worst-case loss = one
  partial GLTS run (≤ ~65 min of credit). Every earlier batch is a
  COMPLETE pair — the comparison keeps everything finished.
- More parallelism (e.g. two pairs at once = 4 lanes) would break the
  two-lane rule, stretch GLTS up to 3x (R-S2-135), and double the
  worst-case credit-death loss. Rejected.
- Expected wall-clock: wave ~2 h (from-shell is the back half of the
  66–81 min full chain, ×2 batches); each pair ~1.5 h under 2-way
  contention → all six ≈ 9 h. If morning arrives first, the completed
  prefix is the cleanest scenes by design.

## LAUNCH DISCIPLINE CHECKLIST (every lane)

1. WMI-detached: `Invoke-CimMethod Win32_Process Create` — never a
   tool-shell background job (08-27: those were mass-killed mid-run).
2. Each lane logs to `out/<scene>/logs/night_<stage>.log` (cmd line
   redirects); PID recorded in NIGHT_STATUS.md.
3. ONE watch_gpu only — check it is running before launching; verify
   clocks.sm ≤ 1500 under load in gpu_watch.csv after the first lane
   is up (laptop hard-powers-off if the clock lock is not holding).
4. Orchestrator watcher: a background poller per batch watches the
   lane PIDs and wakes the orchestrator when both exit; receipts are
   then read BEFORE the next launch.
5. STOP file checked immediately before every launch.
6. No observation-triggered tuning: if a scene's output looks wrong,
   it is FILED with receipts (REVIEW_LOG / NIGHT_STATUS), not patched
   mid-night. Only infrastructure failures (crash, hang, disk) get
   intervention.

## SCENES + WORLD IDS (FINAL, user-picked)

| # | scene | world id |
|---|---|---|
| 1 | natural_living | 6cf716a8-d750-4e06-b28b-ebad2eebf538 |
| 2 | sunlit_office | b6f5f206-ae53-4d36-a1bc-5d52c4759920 |
| 3 | blue_living | 270dd75d-794b-4dcf-99fd-e0b59e73f33c |
| 4 | panel_bedroom | 748cf5e5-f148-48c3-b077-8ddfcd8a50b8 |
| 5 | arch_bedroom | a1ddded0-594a-41e9-a1c5-63447aeae4a8 |
| 6 | plaster_bedroom | 2bf68fde-c0f6-49ec-87e7-3e58c1a5cb53 |

arch_bedroom: arched alcove — expect an approximated trace (vertical
planes only). plaster_bedroom: two rooms + partition — live test of
interior walls. Both deliberately LAST.

## DECISIONS TAKEN WITHOUT ASKING (logged here)

- fresh05 yaw: APPLIED (user rule 08-13: measured tilt is always
  straightened, no threshold).
- Overnight authorized: user 08-13 "yeah they keep running, i will be
  sleeping" — with the stop-in-the-middle guarantee above.
