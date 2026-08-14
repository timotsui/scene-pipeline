# SESSION 2026-09-01 HANDOFF — the paper-writing day: draft COMPLETE, zero TODOs; NEXT = holistic review

(Real date 2026-08-14, user present all day. Follows
SESSION_2026-08-31_HANDOFF.md. This was the OVM-paper session: the whole
day was spent in the Overleaf repo. Overleaf commits 9e65389 → c6384e2,
ALL PUSHED. scene-pipeline got two new scripts + this handoff, LOCAL ONLY
— the user must `git push` scene-pipeline.)

## 0. THE ONE-LINE TRUTH

The paper is COMPLETE as a draft: zero \PAPERTODO markers, evaluation
section live with five tables and verified numbers, four figures in
(teaser, hero, boxes, plus the framework diagrams), the disclosure
paragraph written, THE sentence planted in four places, and a
plain-English pass done. Next session the user reviews the compiled PDF
in its entirety; after that, title + system name + venue.

## 1. WHAT THE PAPER NOW SAYS (the day's rulings, all user's)

- METHOD rewritten to the real pipeline (graph/stages.py, four phases,
  46 stages). fig:system = three lanes (observe II / decide III /
  interactive compose IV; generator = stage I, outside the lanes).
- The composer is OURS. "Standard compositional backend" was our own
  invention pointing at nothing — GONE paper-wide. Composition is a
  ROLE every pipeline has; ours is named INTERACTIVE COMPOSE (their
  narrow compose = place+render, ours = that same core + deterministic
  checks + swaps + gravity). The scene graph is composer-agnostic.
- Comparability rests on what is really shared: the same asset library
  (verified — GLTS's README points at Holodeck's assets) and the same
  role. "We use their stuff so the comparison is clean."
- EVALUATION (sec_evaluation.tex, replaces the feasibility scaffold):
  ten pairs vs GLTS. Headline: PARITY on their own ortho CLIP protocol
  (+0.15 mean, 5-5), LEAD under perspective (+1.85 mean, +6%, 6-4, big
  wins small losses). Structural explanation, verified in both systems'
  records: GLTS places ZERO wall/ceiling objects in all ten scenes
  (vocabulary = floor|on-furniture); every scene of ours has DOORS,
  nine of ten have WINDOWS, 9–54 wall-borne elements per scene.
  Corpus = 3 living + 6 bedrooms + 1 office (fresh04/06 are bedrooms).
  Tables: CLIP w/ per-pair deltas both cameras · area (−57%..+51%) ·
  cost (2–7× faster) · funnel (losses 0–5, one cause) · size match
  (56–80% no fitting candidate = THE limitation, external, swappable).
- FIGURES: teaser = 3-panel killer (rough splat point render BY DESIGN
  / recomposition / edit: sofa moved + table removed, one camera);
  fig:hero = natural_living + sunlit_office persp pairs (56-vs-9,
  67-vs-8 objects); fig:boxes = measured boxes over both heroes (the
  library gap visible). Heroes are the user's pick ("any human will be
  instantly convinced").
- DISCLOSURE (user ruling): asset library used AS-IS, broken-geometry
  cleanup attempted then abandoned, nothing hand-corrected, eras stated.
- GENERATOR story said as it is: Marble for quality; generator = the
  user's choice under the stage-1 contract (splat + prompt only —
  pano self-rendered, collider optional); the four open generators
  were tried and judged weaker (context, not a result).
- THE SENTENCE (Q6 resolved, user's pitch): "a bridge between entangled
  generation and semantic composition, taking from each what the other
  cannot supply: the generated world settles where everything is, our
  extraction recovers what everything is, and composition makes the
  result real and editable." Near-verbatim in abstract, intro,
  motivation gap, conclusion. The ambiguity-ladder phrasing survives
  ONLY in Motivation, right after the plain form.
- PLAIN-ENGLISH RULE extended to the paper: technical terms only where
  defined and load-bearing; decorative jargon outside its defining
  section replaced ("pays down", "level mismatch", "strictly
  dominated", "determinacy" removed from abstract/method/contributions).
- Also fixed in review: single-viewpoint discussion updated (the
  20-crop funnel closed the old coverage hole; crop agreement is not
  independent corroboration), trusted-toolchain frame story, propose_
  edits paragraph rewritten to real mechanics, scope softened for the
  two-room scene, "backend" now means nothing (generators are
  "generators", placers are "composers").

## 2. STATE FLAGS

- Overleaf repo: IN SYNC, everything pushed (HEAD c6384e2). New files:
  sec_evaluation.tex (sec_feasibility.tex deleted), figs/ (8 PNGs).
  notes_questions.tex refreshed: Q3/Q6/Q7/Q9/Q10 resolved, Q8 rebuttal
  list rebuilt for the evaluated paper. refs.bib: + openclip, laion5b.
- ⚠ COMPILE NOT YET CHECKED: the teaser (acmart teaserfigure + TikZ-free
  image grid), fig:hero/fig:boxes tabulars, five booktabs tables, and
  the section renumbering all landed since the last compile the user saw.
  First job of the review: compile and eyeball.
- ⚠ scene-pipeline LOCAL commits the user must push: 98141b9
  (eval_box_overlay.py), 012e122 (eval_killer_panels.py), + this
  handoff's commit. Both scripts are compute-only (no re-runs) and
  regenerate any figure for any scene.
- OPEN DECISIONS, all deferred by the user to after the holistic read:
  Q11 system name (Scribe/Transcribe/Readout/Recompose/none, coupled to
  title), title (T1 stands), venue (PI's only call; sets length limits —
  Motivation is what would shrink).
- Numbers provenance: EVAL_RESULTS_2026-08-13.md + metric JSONs in
  out/eval_renders/; per-pair CLIP deltas recomputed and cross-checked
  this session. GLTS wall/ceiling fact verified in
  TreeSearchGen/output_ovm_*/0/10_full_scene_graph.json (placement =
  floor|other only). Door/window counts verified in each scene's
  scene_graph.json current layer.
- The R-S2-171 yaw bug, half-applied scenes, and rotation-receipt
  caveats are UNCHANGED from the last handoff and are disclosed in the
  paper where they bind.

## 3. THE PROMPT FOR THE NEXT SESSION

```
Continue the OVM-paper work. READ
scene-pipeline/entangled_gen/docs/SESSION_2026-09-01_HANDOFF.md IN FULL.
Paper: the Overleaf git bridge repo (memory ovm-paper-overleaf-repo),
HEAD c6384e2, everything pushed.

THIS SESSION IS THE HOLISTIC REVIEW: the user reads the compiled PDF
end to end. Your job: fix what the user flags, keep the paper's rules —
plain English (technical terms only where defined and load-bearing),
THE bridge sentence stays near-verbatim in its four places, every
number carries its caveat, nothing re-run. After the review: title +
system name (Q11 candidates in main.tex's comment block) + venue (PI).

HOUSE RULES: user judges all visuals; commits in the Overleaf repo =
htsui6 identity (per-repo config), scene-pipeline = Timotsui; pushes of
scene-pipeline are the user's.
```
