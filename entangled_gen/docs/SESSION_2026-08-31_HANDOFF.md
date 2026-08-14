# SESSION 2026-08-31 HANDOFF — the evaluation day: 8 metrics gathered, story complete; NEXT = WRITE THE PAPER

(Real date 2026-08-13, user present all day. Follows
SESSION_2026-08-30_HANDOFF.md — the planned "review & evaluate"
session became the EVALUATION-BUILDING day; the viewer walk of the ten
scenes was started (dropdown reorganized, several scenes eyeballed)
but the full §3 walk was never finished and is NOT blocking. The
user's closing words: "tomorrow we write the paper. it should be easy
since now we have all the pieces." REVIEW_LOG R-S2-171..172. Commits
01555ef → bbdb7dd + this wrap, ⚠ ALL LOCAL — pushes were blocked for
the agent; the user must `git push`.)

## 0. THE ONE-LINE TRUTH

The paper's evaluation section now EXISTS AS NUMBERS: eight metrics
over TEN ours-vs-GLTS pairs, all computed from records that already
existed (no re-runs — standing rule), all documented with caveats in
docs/plans/EVAL_RESULTS_2026-08-13.md, all reproducible by scripts in
the repo. The story the numbers tell: tie them on plausibility, 2–7×
faster, dominate on grounding, and the residual error is quantified as
an external swappable component (the asset library).

## 1. NEXT SESSION = THE PAPER (OVM paper 1, Overleaf)

- Repo: the Overleaf git bridge (memory: ovm-paper-overleaf-repo —
  branch main, user `git` + token; sec_*.tex, acmart, NO cleveref).
- Paper state as of 08-04 (memory: ovm-paper-draft-state): 8 TODOs,
  ONE open decision = feasibility scene count → NOW ANSWERED: the
  corpus is TEN pairs (user ruling: old GLTS valid, older ours fine),
  plus 7 singles pairable later. Killer figure = leverage; fig:lanes
  awaited a compile check.
- What to write in: the evaluation section from
  EVAL_RESULTS_2026-08-13.md (tables are pre-formatted markdown —
  transcribe to LaTeX), the limitation paragraph from §5/5b (funnel +
  size match), the comparison story from §1 of the results doc.
- Figures ready on disk (week7 out root):
  * out/eval_renders/<scene>_{ours,glts}_{ortho,persp}.png — the
    frozen product shots (user-approved spec, see §3). ⚠ OPEN PICK:
    which projection headlines (persp scores best for us and the user
    leaned "ortho vs persp your call" — never ruled). Both exist.
  * out/comparison.html — ten-pair evidence sheet (rebuilt).
  * out/wall_review.html, per-scene room_shell_steps.png.
- GLTS/Holodeck evaluation facts verified IN THE PDFs this session
  (Research/papers/Selected_Papers/): GLTS = CLIP score + 15-annotator
  reciprocal rank, both on top-down renders, NOTHING else; Holodeck
  adds 1–5 ratings, layout-ablation MRR, navigation Success/SPL, 680
  grad-student raters. Cite their setups from §"WHAT THE BASELINES
  USE" in EVAL_PLAN_2026-08-13.md.

## 2. THE EIGHT METRICS (full tables + caveats in EVAL_RESULTS doc)

1. CLIP (their recipe, OpenCLIP ViT-L/14 LAION-2B): MEAN ours
   31.00 ortho / 32.55 persp vs GLTS 30.85 / 30.70. Persp helps ours,
   hurts GLTS. Ours wins living rooms + office; GLTS wins bedrooms
   (where our rooms are sparser). ⚠ within-table only — never compare
   to the papers' printed Cycles numbers.
2. Wall clock: ours 12–63 min vs GLTS 54–192 min (2–7× faster).
3. LLM calls: ours 286–831/night-scene (receipts recount, LOWER
   BOUND; older scenes' caches span eras) vs GLTS 147–280 — more but
   cheaper calls at concurrency 8 vs serial GPT-4o.
4. Room area: GLTS guesses −57%…+51% off; worst = plaster (two-room).
5. Objects: ours 15–82 measured vs GLTS 6–11 invented.
6. Retention: GLTS silently loses 1–11 of its own retrievals/scene.
7. Realization funnel (eval_funnel.py): hard losses SMALL (0–5/scene,
   all "no acceptable asset match"); in-GLB = anchors + SWAP-INS
   (user: "a key advantage of ours") + merged subs — three additive
   populations, why in-GLB can exceed shopped; bedroom_marble old-era
   row (31 of 82, no sub machinery) = free ablation of sub rounds.
8. Size match (eval_size_match.py): **56–80% of placements had NO
   correctly-sized candidate in the whole shortlist** (chosen-fit only
   7–28%, native dev 24–108%, out-of-box median 71–402 mm). THE
   limitation argument, quantified: boxes are measured, the size error
   lives in what the library offers, everything improves by swapping
   the library.

RULED OUT: physics counts (user: "we employ a physics solver in
particular to solve that" — differentiates nothing; if ever mentioned,
settled-mesh only, one line, never the box rows). PARKED for spare
time: VLM pairwise preference, image-to-image fidelity vs the splat.

## 3. WHAT WAS BUILT (all in repo, all committed locally)

- eval_renders.py — frozen product-shot spec (user-approved through
  five live iterations): pyrender z-buffered, real mitred 3D walls
  extruded from the MEASURED per-scene floor (floor_upright_m lift —
  the bench-corner parallax find), triangulated white floor, black
  void, room-volume clip (polygon + 2.4 m ceiling), walls+floor
  silhouette MASK pass (nothing outside the walls is visible),
  boundary cleaned via shapely buffer(0) (fresh06's weakly-simple
  trace: 0.7 m² sliver dropped, printed). Ortho = GLTS's own camera
  rule (their blender_placement.py: ORTHO, 1.1×maxdim, 1024²); persp
  = 60° experiment. Contact sheet: out/eval_renders/index.html.
  Fallbacks labeled: bedroom_marble = bbox walls (no polygon era);
  living_marble = pre-normalization archive GLB.
- clip_score.py (CPU on purpose), eval_llm_calls.py, eval_funnel.py,
  eval_size_match.py — each documents its own counting rules; JSON
  artifacts beside the renders in out/eval_renders/.
- Viewer dropdown: named ordered groups from viewer/data/_active.json
  (pairs-night / pairs-older / singles / archive). Server restarted
  (two stale servers were found squatting the port and killed).
- compare_methods rebuilt comparison.html/json for ALL TEN pairs
  (the live sheet had held only plaster_bedroom — it overwrites per
  run; same trap exists in eval_renders' index.html: a --scenes
  partial run rebuilds the sheet with only those scenes).

## 4. STATE FLAGS THE NEXT AGENT MUST KNOW

- ⚠ COMMITS ARE LOCAL ONLY (push blocked for the agent): 01555ef
  viewer groups, 70ebed7 eval plan + renderer, b166a70 CLIP + calls +
  results doc, 59cc24b funnel + physics ruling, bbdb7dd size match,
  + this wrap. USER MUST PUSH.
- R-S2-171, MAJOR BUG, documented NOT fixed (PARKED #6, user order):
  run_scene NEVER calls scene_yaw — tilted rooms ship tilted. Measured
  this session: plaster +39°, blue_living +13°, rest ~0.
  blue_living + plaster_bedroom sit HALF-APPLIED: yaw was applied,
  re-runs vetoed, splats RESTORED from _preyaw backups (as-built) —
  but frame_bootstrap still carries a stale yaw_applied stamp and the
  early pano manifests remain rotated on disk. Reconcile BEFORE any
  future re-run of those two scenes.
- living_marble was NEVER fitted in the current era (compose stopped
  at supported_by 08-06; graph is current to 08-11). Its renders use
  the pre-normalization archive GLB, labeled. User accepted.
- Rotation receipts before R-S2-170 are plausibility-mode (every
  scene except sunlit_office onward) — the caveat ships with any
  facing-related claim.
- The ten-scene viewer walk (old handoff §3) and the six filed §4
  calls from the 08-30 handoff were LARGELY NOT REVIEWED — the user
  pivoted to evaluation. Do not treat them as closed. The eval work
  answered §4.1 (then deprioritized physics entirely) and §4.6
  (no re-runs, caveat ships).
- mapbox_earcut was pip-installed --no-deps (torch untouched) for the
  floor triangulation.
- Two out/ roots trap stands: DATA in CS-8903-OVM\week7\entangled_gen\
  out\, repo out\ holds night logs. paths.py decides.
- Viewer: `python viewer\serve.py --scene natural_living --port 8321`,
  DETACHED via WMI Win32_Process.Create with the FULL python.exe path
  (plain `python` fails under WMI, rc=9) → http://localhost:8321/.
  Check for squatters first: two stale servers were found holding the
  port this session. Every eval artifact opens as a plain file:
  out\eval_renders\index.html (shots), out\comparison.html (pairs),
  out\wall_review.html (shells) — no server needed for those.

## 5. THE PROMPT FOR THE NEXT AGENT

```
Continue the scene-pipeline / OVM-paper work.
READ docs/SESSION_2026-08-31_HANDOFF.md IN FULL — it is the one file.
Repo: D:\T\Documents\GeorgiaTech\Summer2026\scene-pipeline\entangled_gen
Paper: the Overleaf git bridge repo (memory ovm-paper-overleaf-repo).

THIS SESSION IS THE PAPER UPDATE. The evaluation exists as numbers:
docs/plans/EVAL_RESULTS_2026-08-13.md (tables + caveats, transcribe
faithfully), EVAL_PLAN_2026-08-13.md (the pre-registration + baseline
facts), out/eval_renders/ (product shots + metric JSONs + contact
sheet). Update the draft from its 08-04 state (memory:
ovm-paper-draft-state — 8 TODOs; the scene-count decision is now
ANSWERED: ten pairs). Quote numbers WITH their caveats — they are part
of the record, not decoration. The projection pick (ortho vs persp
headline) is the user's; ask once when it matters.

HOUSE RULES: plain English; trust the primary record over summaries;
no re-runs of pipeline scenes; user judges all visuals; commits in
scene-pipeline = Timotsui identity, pushes are the user's.
```
