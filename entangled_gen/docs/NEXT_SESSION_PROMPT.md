Continue the scene-pipeline work. Repo: D:\T\Documents\GeorgiaTech\Summer2026\scene-pipeline\entangled_gen
READ FIRST, in order:
  1. docs/SESSION_2026-08-28_HANDOFF.md â€” all of it. Â§1 is your work
     order, Â§5 the traps.
  2. docs/PARKED.md â€” do not work on these (item 4 = wall-embed, new).
  3. REVIEW_LOG R-S2-136..158 â€” skim headers; read any entry you touch.

THE SESSION IS THE RE-RUNS (user: "the next agent will be rerunning the
scenes we need to rerun"):
  1. fresh05 + fresh08: scale apply (scene_scale.py, no --measure-only)
     then the two-pass chain re-run from stitch. Detached launches,
     clock-lock verified, sequential. Read the morning-report style
     receipts as the user would.
  2. Build the yaw state-apply (R-S2-158 Â§: splat xyz + gaussian quats,
     collider, manifests, boot guard; frame contract STAYS sign-flips).
     Pre-register in REVIEW_LOG before running.
  3. Wall-fix re-run on fresh05/06/09: new room_shell stack into shipped
     state, graph wall rebuild, downstream chain. Regenerate the steps
     sheets + wall_review.html so the user can compare shipped vs sheet.
  4. Do NOT design: v1-merge, interior-wall architecture, compose wall
     consumers, bed census â€” those need user rulings, bring them as
     questions with receipts.

HOUSE RULES: no observation-triggered tuning; fixes at source,
scene-agnostically; every fix gets a REVIEW_LOG entry with the contract
intro; the user judges ALL visuals; trust the primary record over
summaries; plain English; long processes DETACHED; ONE watch_gpu.

