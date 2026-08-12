# NEXT SESSION PROMPT (written 2026-08-12 at the compose-canon session's close)

Copy-paste for the next agent:

---

Continue the scene-pipeline work. Repo:
D:\T\Documents\GeorgiaTech\Summer2026\scene-pipeline\entangled_gen

READ FIRST, in this order â€” do not skip, do not work from summaries:
1. docs/SESSION_2026-08-26_HANDOFF.md â€” all of it. Â§1 is the canon
   that changed (13 rulings in one night), Â§3 the open decisions that
   are MINE not yours, Â§4 the traps that bit last session.
2. docs/PARKED.md â€” do not work on these.
3. graph/stages.py â€” the pipeline IS this file.
4. REVIEW_LOG R-S2-110..128 â€” skim headers; read any entry you touch.

THE GOAL: keep making our way to the 100-scene automation. The corpus
is 318 runnable worlds; the one-command bar has been met once (fresh04);
the compose canon just matured. What that means concretely, in order:

0. HEAL fresh04 (one command, also verifies R-S2-128): 
       python run_scene.py --scene fresh04 --phase compose --from fit_preview
   Expect the VOIDING line; obj_000 must place from the table aisle.
1. COMMIT CHECKPOINT after that. Many sessions uncommitted. Commit as
   Timotsui / timotsuihc@gmail.com with a message that names the
   R-S2 range. Do this before touching anything.
2. fresh05 â€” THE VALIDATION RUN. Every compose ruling of last night
   (size bar, flat-axis metric, substitution walk, minimal-clip,
   directional hug, J9 coverage, trimmed scale, verify-not-crash) has
   executed only on fresh04. Pick a NEVER-RUN box-shaped interior
   (colliderless is fine now), read its prompt, confirm unclaimed
   (no out/*/bundle_path.txt), then ONE command:
       python run_scene.py --scene fresh05 --bundle <world-folder>
   Zero intervention is the bar. If a stage fails: fix at the source,
   scene-agnostically, log at the NEXT FREE R-S2 number (contract
   intro first), resume â€” and the bar moves to the NEXT fresh world.
3. THE FIRST FLEET NIGHT â€” after fresh05 is clean, ask me for 3-5
   world picks and run run_fleet.py over them. This doubles as the
   multi-scene-execute proof (only resume-skip and single-scene are
   proven). Read the morning report the way I will.
4. Bring me the OPEN DECISIONS from handoff Â§3 when relevant scenes
   make them concrete (wall definition, invented-anchor authority,
   panels, bar nudges). Never decide them yourself.

THE HOUSE RULES THAT ARE LOAD-BEARING (they all fired last night):
- Rule #1: no observation-triggered tuning. Eye-calibrated knobs
  (ALLOW_L, HUG_DRIFT_M, DRY bar) move on MY say-so only.
- Fresh scenes are the only evidence; a passing re-run proves nothing.
- Trust the primary record over any summary â€” including your own.
- Modules load fresh per stage: you may fix code ahead of a running
  pipeline, but NEVER judge the preview mid-run.
- âš  `--from X --phase all` re-runs the OTHER phases IN FULL (it
  scopes only X's own table). This burned an hour last night.
- Every fix gets a REVIEW_LOG entry with What/Why/Mistake-looks-like.
- GPU: clock lock protocol per docs/POWER_CRASHES.md; ONE watch_gpu.
- Plain English everywhere. Say ids when discussing objects (the
  viewer cards now show name, description, shot tile, asset info,
  substitution trail â€” use them, and extend them if I ask).

---
