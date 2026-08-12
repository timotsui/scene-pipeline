# Overnight handoff — 2026-07-06 (HW1 gen-backend run, user asleep)

> **NIGHT CLOSED ~01:45, machine SAFE, WSL deliberately STOPPED.** Do not
> relaunch anything. Results: both panos done (pending user eyes); scenegen
> not viable locally (2 attempts, 2 clean guard saves — RAM-bound, not
> VRAM-bound). Current state + morning agenda: GEN_BACKEND_EVAL_PLAN.md
> status log (2026-07-06 ~01:45 entry). The rest of this doc is the night's
> operational detail, kept for reference.

> For a fresh session after a crash/reboot: this + GEN_BACKEND_EVAL_PLAN.md's
> status log is everything. Frame/coordinate context: SESSION_2026-07-05C.
> The USER IS ASLEEP — do not wait on them; do not judge any image.

## INCIDENT 00:58 — deadman fired (and worked)

During the first safe-mode bedroom pano, WSL ballooned to its full 24 GB cap
and Windows free RAM fell to 946 MB; the deadman executed `wsl --shutdown`.
Machine saved, night jobs killed. Structural fix applied: .wslconfig
memory=20GB (Windows keeps ~11 GB — the squeeze CANNOT recur) + swap=24GB
(so the ~34 GB bf16 working set fits in 20+24 without oom-kill; slow swap
I/O per denoise step is the accepted price). Queue relaunched 01:05,
bedroom-only.

## SCOPE (user, 00:55): ONE SCENE PER PIPELINE

Not one pipeline total — each backend runs ONE scene (bedroom) first;
second scenes only after cross-backend comparison. Tonight hw1 runs
bedroom only (stage 2 playroom cut from overnight_hw1.sh; run later:
`bash run_panogen.sh "a cozy playroom with a rug and shelves" playroom_hw1 0`).

## PRIME DIRECTIVE (user, 00:50): a crash is UNRECOVERABLE tonight

The machine does NOT come back without a physical button press. Prevention
outranks throughput and even results. Consequences applied:
- Panos run in **safe mode**: HW1_SEQ_OFFLOAD=1 sequential offload, bf16, NO
  fp8 flags → peak VRAM <1 GB (vs ~12 GB at the driver-hang edge). Slower is
  irrelevant. (Patch in repo demo_panogen.py; mode arg in run_panogen.sh —
  "fast" mode exists but is ATTENDED-ONLY.)
- **Scenegen stage CUT from the night** (double FluxFill load = highest
  crash-risk event). Weights still prefetch (network-only). Run attended
  tomorrow.
- Do NOT relaunch anything GPU-heavy beyond the two safe-mode panos tonight,
  even if they finish early. Idle is a feature.
- If this Claude session dies, its WSL-keepalive pings stop and the WSL VM
  may idle-stop, taking the detached jobs with it. That is SAFE (machine
  fine, artifacts partial) — do not add aggressive keepalive hacks for it.

## What was running when this was written (~00:45)

ALL jobs launch through ONE entry point — `gen/hunyuanworld/start_night.sh` —
run by a single hidden persistent `wsl.exe` started from PowerShell:

    Start-Process -FilePath 'wsl.exe' -ArgumentList @('-d','Ubuntu-24.04',
      '--','bash','/mnt/d/T/Documents/GeorgiaTech/Summer2026/scene-pipeline/entangled_gen/gen/hunyuanworld/start_night.sh') -WindowStyle Hidden

start_night.sh runs, in parallel, and `wait`s on: overnight_hw1.sh (FLUX
check → bedroom pano SAFE mode; playroom + scenegen stages are cut inside
the script), prepare_scenegen.sh (Fill-dev/ZIM/DINO/MoGe downloads),
follow_playroom.sh (waits for runner exit + bedroom pano, then playroom pano
per the user's standing order). Logs: `out/logs/overnight_hw1.log` (+
`_resources.log`), `/root/{overnight_hw1_launcher,prep_scenegen,follow_playroom}.log`.

HARD-WON LAUNCH LESSONS (2026-07-06, three failed attempts):
1. `setsid nohup ... & disown` via a transient `wsl bash -c` dies if the WSL
   VM idle-stops seconds later (needs an active session; monitors' 30 s pings
   only help once armed). 2. Passing a quoted command string through
   `Start-Process wsl.exe -- bash -c "..."` gets re-split by wsl.exe into a
   bare stdin-waiting `bash` — jobs hang forever doing nothing. Hence: ONE
   zero-argument starter script, ONE hidden wsl.exe that stays alive.
   Everything is idempotent — relaunch the same line after any death.

Windows-side (die with the Claude session, NOT needed for the jobs):
deadman watchdog (auto `wsl --shutdown` on Windows-RAM<1.2 GB or WSL
unresponsive ~2 min) + a log-tail monitor. The WSL VM needs SOME periodic
`wsl.exe` activity to stay alive — if relaunching jobs from a fresh session,
also arm a keepalive/watchdog loop.

## Post-crash diagnosis order

1. `out/logs/overnight_hw1.log` — which stage was last; rc lines.
2. `out/logs/overnight_hw1_resources.log` — last samples before death
   (ram/swap/vram climbing = OOM story; flat then stop = external kill).
3. Scene logs: `out/<scene>/panogen.log`, `out/<scene>/scenegen/scenegen.log`.
4. If the box hard-froze: the deadman was supposed to prevent that — note it
   in the plan doc as a data point AGAINST local HW1 runs (feeds decision 1.4).

## Success/failure states per artifact

- `out/bedroom_hw1/panorama.png` (+ playroom) — EXISTS = pano stage worked;
  queue for USER EYES in the morning, no exceptions.
- Pano missing + error in panogen.log — safe mode already IS the low-VRAM
  fallback (sequential offload). If it errored anyway, diagnose from the log;
  do not escalate to fast mode unattended.
- Scenegen: intentionally not run tonight (see PRIME DIRECTIVE). Tomorrow
  attended: `bash gen/hunyuanworld/run_scenegen.sh bedroom_hw1` after
  `.scenegen_ready` exists. OOM there = expected data point for decision 1.4
  (park vs cloud rental — USER decides, default lean (b) park & batch w/ Exp 4).
- Next automatic steps if meshes exist: mesh → splat adapter
  `gen/hunyuanworld/mesh_to_splat.py` (DRAFTED overnight, UNTESTED — before
  first use run a round-trip check: write a tiny synthetic ply, read it with
  rendertools load_splat, compare xyz/rgb/radius) → render_views → seg →
  lift (auto frame calib) → viewer prep. All numbers-only; safe without user.

## Blocked / waiting-on-user

- SPAG4d (Exp 2): cloned at repos/SPAG4d, harness in gen/spag4d/ — env
  install (setup_env.sh) needs the user present (permission classifier:
  new external repo execution). ~15 min. Then `run_spag.sh <pano> <scene>`.
- Panos + any meshes: user's composition judgment (the actual eval).
- Any spend (cloud rental) and Matrix-3D install: user decisions.

## Environment facts a fresh session needs

- WSL conda env `HunyuanWorld` (verified); gotchas in gen/hunyuanworld/
  setup_env.sh. Call `/root/miniconda3/envs/HunyuanWorld/bin/huggingface-cli`
  by ABSOLUTE PATH. HF login done (user `timotsuihc`, both FLUX licenses).
- `.wslconfig`: memory=24GB swap=16GB (raised for the LoRA-fuse RAM spike).
- WSL /tmp is wiped on VM restart — never log there.
- Windows-side background PowerShell tasks were being killed repeatedly this
  session; detached-in-WSL + Monitor tasks were reliable.
