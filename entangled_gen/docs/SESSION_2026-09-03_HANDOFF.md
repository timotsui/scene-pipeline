# SESSION 2026-09-03 HANDOFF — paper evidence locked; next session is story and talking points

(Real date 2026-08-15, user present. Follows
`SESSION_2026-09-02_HANDOFF.md`, now archived in `docs/handoffs/`.)

## CLOSE-OUT STATE

The evaluation/problem audit and final paper-consistency pass are complete.
Nothing is running. No scene was rerun or corrected. The paper repository is
clean. The manuscript's numbers, scope, causal wording, limitations, and
claim-to-implementation links now agree.

Paper repository:
`D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\paper\overleaf`

Paper commits:

- `7690f54` — align paper claims with evaluated evidence.
- `1567cbf` / `9e4ef38` — a handoff was mistakenly added inside Overleaf and
  then removed. The live handoff is this file, in the pipeline's canonical
  `docs/` location.

Static verification passed: no missing references, citations, figures,
duplicate labels, brace mismatches, or active paper TODOs. All CLIP means and
realization totals reproduce from the displayed rows. A local LaTeX engine was
not installed, so a fresh PDF compile/visual inspection is still required.

## READ FIRST NEXT SESSION

1. This handoff, completely.
2. Paper `PAPER_PROGRESS_2026-08-15.md` — locked story, evidence, and review
   contract.
3. Paper `EVALUATION_PROBLEMS_AND_OPEN_ISSUES.md` — full audit and decisions.
4. Read `sec_abstract.tex`, `sec_intro.tex`, `sec_contributions.tex`, and
   `sec_conclusion.tex` together before editing any of them.

Tomorrow's job is **story structure and talking points**, not another evaluation
redesign.

## THE CURRENT STORY

1. Text-to-3D has two incomplete families: rich generated worlds that are hard
   to control, and editable compositional scenes whose layouts are invented
   from text.
2. We bridge them. A coherent generated world supplies the scene; extraction
   turns its visible organization into a measured semantic scene graph;
   composition makes that organization editable.
3. We reverse the usual order. The world settles the layout first, then the
   system shops for assets that fit measured slots. It does not choose exact
   furniture first and search for somewhere to put it.
4. This produces a modular chain: better world generation, lifting, retrieval,
   assets, or visual judges can improve the output without redesigning the
   entire system.
5. The evaluated output retains selected-asset catalogue identity, native
   scale, mesh, and appearance. Richer asset/output adapters can additionally
   carry collision metadata, rigs, behavior, SKUs, or simulator fields. Those
   richer fields are an enabled application path, not a measured result of the
   current exporter.

## LOCKED EVALUATION FACTS

- Ten ours-versus-GLTS pairs use the same source generation prompts and asset
  inventory. All ten ours-side scenes are raw, unedited pipeline outputs.
- Primary room-type CLIP, orthographic: `31.00` versus `30.85`, delta `+0.15`
  (`+0.5%`). The correct reading is parity.
- Secondary perspective probe: `32.55` versus `30.70`, delta `+1.85`
  (`+6.0%`).
- The three `3D rendering` prompt variants are symmetric, post-hoc
  prompt-sensitivity diagnostics. They remain positive but do not replace the
  primary metric.
- CLIP does not establish full-source-prompt fidelity, object/relation
  correctness, or human preference.
- Structural evidence is separate: measured room geometry, non-rectangular and
  non-cardinal plan shapes, doors, windows, mounted objects, and `15–82`
  evidence-backed objects versus `6–11` invented objects.
- The compatible six-run realization aggregate is `77%` direct, `11%`
  replacement, `12%` missing, and `88%` filled. The table explicitly marks the
  six pooled rows; other recoverable rows are shown but not pooled across record
  contracts.
- Coverage is not fidelity. Only `18/128` comparable direct placements (`14%`)
  meet the 15% native-size tolerance; `88/128` (`69%`) had no fitting
  shortlisted candidate.
- Asset availability is a major ceiling, not the only cause. Small-object merge,
  support, receipt, and replacement-handoff defects also lose content.
- Timing is supporting evidence: approximately `2–7×` faster on the six pairs
  with complete timing (`1.84–6.82×` from displayed rounded minutes), while
  making `3.2×` as many recorded model calls in aggregate.
- Both local systems use the same Claude Sonnet backend. This does not claim
  equivalence to GLTS's published GPT-4o setup.
- Neither evaluated system uses Paint3D. Both use the same comparison rendering
  setup and camera.
- No human study was run.

## LOCKED LIMITATIONS AND CAUSAL LANGUAGE

- Marble is the selected and evaluated source because it produced the richest,
  clearest, most coherent inputs among those tested. Portability is by source
  contract; equal output quality across generators is not claimed.
- Extraction produced meaningful, traceable downstream structure. Detector or
  lifting accuracy against object-level ground truth is not claimed.
- Modularity localizes errors; it does not erase them. Final quality depends on
  the generated guide and every downstream module.
- The shell assumes a flat floor/ceiling and vertical walls, but supports
  non-cardinal walls, cut corners, L-shapes, and connected spaces.
- Deep wall-embedded objects are currently shallow wall-aligned elements.
- Axis-aligned boxes favor cardinal directions. `plaster_bedroom` entered the
  pipeline with roughly 39 degrees of plan yaw, remains unchanged in every
  aggregate, and may have lost CLIP points from inflated boxes/non-canonical
  presentation. This is suspected, not proven.
- `arch_bedroom` contains visibly poor lifted boxes. Lifting is a plausible
  contributor to its loss, not an isolated causal result.
- Visual verification depends on the judge and its evidence. Better models are
  an upgrade path; no model-scaling result is claimed.
- Deterministic mesh collision checking is demonstrated. Stability,
  reachability, navigability, task success, arbitrary physics metadata, rigs,
  and behavior are not.

## DO NOT REOPEN WITHOUT NEW EVIDENCE

- Do not replace the primary CLIP prompt with a post-hoc winner.
- Do not restore the old nearly-lossless funnel or claim every missing object
  has one external cause.
- Do not equate direct placement with a good asset match.
- Do not say the current exporter preserves arbitrary metadata, physics, rigs,
  or behavior.
- Do not remove, correct, or exclude losing scenes.
- Do not turn qualitative bedroom readings into confirmed causes.
- Do not make the paper centrally about speed, CLIP prompt engineering, or the
  internal details of the lifting algorithm.

## NEXT SESSION — EXACT WORK ORDER

1. Write the intended paper story as a short outline before changing prose.
2. Put every author talking point into that outline, then label it as central
   claim, evidence, implication, limitation, or future work.
3. Decide whether the current six contributions collapse into three or four
   memorable contributions.
4. Shorten the long Motivation argument while preserving the central ordering
   claim: observation resolves the high-impact layout decision before exact
   assets are committed.
5. Reduce repetition across Abstract, Introduction, Motivation, Contributions,
   and Conclusion.
6. Decide how much attention robotics, real products, digital twins, games, VR,
   and virtual production receive. Keep current implementation versus enabled
   adapter capability precise.
7. Keep evaluation factual and supporting. The main paper is the workflow,
   semantic grounding, layout-first ordering, and modular bridge.
8. Finish with another contradiction scan and compile/inspect the PDF in
   Overleaf or another LaTeX-equipped environment.

## LIKELY TALKING POINTS TO REVIEW WITH THE USER

- The generated world proposes the scene; the pipeline turns it into controlled,
  editable structure.
- Describe the proposal from observation instead of imagining it from text.
- Settle the layout before shopping for assets.
- Rich coherent world generation and controlled composition are complementary,
  not competing.
- Every module is an upgrade path: better worlds, lifting, catalogues, retrieval,
  and visual judges.
- Non-rectangular/non-cardinal rooms create a path from text to generated world
  to real rooms and real assets.
- Real-product and interactive applications are important enabled directions,
  with present versus future adapter capabilities stated honestly.

