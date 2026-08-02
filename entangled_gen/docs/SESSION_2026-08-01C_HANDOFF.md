# Session 2026-08-01C (evening) — R6+R7 passed · compose chain fresh · viewer = "scene model" current-only

⭐ **FINAL STATE (read this block first)**

The graph re-run (R6) got a provisional PASS, the compose chain
(supported_by → consistency → snap) was RE-RUN on the new 82-cluster
resolved layer and got its own provisional PASS (R7, reviewed via the
new snapped-preview view). The viewer was overhauled into a
current-only "scene model" view. **NEXT SESSION (user-declared): run
`compose/propose_edits.py --scene bedroom_marble` (it is the ONLY
stale compose file) and review the fresh output — the R5b gate
re-opens against it.** Everything remains UNCOMMITTED in
scene-pipeline (this session touched: viewer/index.html,
viewer/serve.py, docs/PLAN_COMPOSE_LOOP.md, this handoff; earlier
sessions' uncommitted changes still pending too — commit as
Timotsui / timotsuihc@gmail.com when convenient).

## Gates ruled this session (all provisional, PLAN_COMPOSE_LOOP.md)

- **R6 PASS** ("i think this is good") — the 82-shipping resolved
  layer. NOT individually ruled, carried forward as open eyeball
  items: obj_002 AC (wall vs bookshelf — snap's 0.255 m hop to
  bookshelf-top is the stake), obj_062 lamp→"air conditioner" rename
  (second ceiling AC suspicious), obj_083 plant REJECTED (its ctx
  crops only reachable via the record layer now).
- **R7 PASS** ("the snap seems fine") — the fresh compose chain:
  supported_by 82/82, 30 anchors / 9 demoted / 16 multi-option
  (was 30 — runner-ups died with the duplicate shelves) / 0
  none_plausible · consistency 77 confirmed / 11 alt / 11 DROP +
  4 KEEP, 0 audit flags (new drops: obj_027 picture-IN-book,
  obj_054 basket-IN-chair) · snap 18 LARGE (anchor knowns persist;
  book-cluster LARGEs = dependents = advisory per the 08-01 ruling).
- Row 6 (R1 gate) fixed — it had sat stale as "OPEN" since the 07-31
  provisional pass; caused a user "wtf are we past S1?" moment.
  Lesson: update gate rows the moment a verdict lands.

## Viewer overhaul (user-driven, this session)

1. **STALE GATE** — serve.py `_compose_json()`: any compose file older
   than scene_graph.json serves as `{stale:true}` stub; viewer treats
   it as not-built and shows "⚠ stale, hidden: …" in the row.
   Un-stales automatically on module re-run. This is the generic
   loop-hygiene mechanism (no per-scene/date logic).
2. **Renamed** "supported_by graph (canonical)" → **"scene model
   (resolved · canonical)"**; row header "scene model: N objects".
3. **HUD current-only**: removed composed / collisions / analyzer-cams
   layers (code out, routes+files stay) and ALL box-source layers
   (serve registry returns [] — entries commented in serve.py for
   one-line re-enable). Kept collapsed "audit / archive": graph
   record (audit) + graph contact edges. Axes triad + origin sphere
   behind default-off "axes" checkbox (the "weird blue" complaint #1).
4. **Existence colors neutralized** in resolved view — obj_027/obj_054
   rendered green ("confirmed real", settled pass-2 history) among
   blue boxes (complaint #2); now uniform ship-blue, story in card.
5. **Sub-checkboxes → ONE "view" dropdown** (complaint #3), then
   TRIMMED after the R7 verdict (complaint #4: closed-gate colorings
   are noise): live set = **snapped preview (default) · edit proposals
   (only when fresh) · plain boxes**; anchor tiers / support /
   consistency / snap review appear only with `?allviews=1` (dim hint
   in the row). Legend + tooltip follow the mode; arrows/ghosts/
   ADD-labels auto-switch. jFocusApply reads jMode(); jViewApply also
   TRANSLATES box groups to snapped centers in snapped-preview mode
   (snap is translation-only; display-only, observed centers restored
   in every other mode).

## Next session queue

1. `python compose/propose_edits.py --scene bedroom_marble` (from
   entangled_gen; ~1–2 sonnet calls) → R5b re-review on the fresh
   file. Old-run look-fors that carry over: plant DELETE-vs-KEEP now
   moot (obj_083 was REJECTED upstream — check the candidate list
   reflects that), add-variance question (blanket vanished v1→v2),
   0-petitions correctness. "edit proposals" appears in the viewer
   dropdown automatically once the file is fresh.
2. The three eyeball items under R6/R7 (obj_002 · obj_062 · obj_083).
3. Then: screening design (parked draft at the bottom of
   PLAN_COMPOSE_LOOP.md; the settled direction includes the
   non-visual dedup consuming reopen_petitions) → S4 shopping
   (S4_SHOPPING_DESIGN_NOTES.md).

## Ops

- Viewer RUNNING on :8321 at session end (task bo8my5vje);
  restart: `python viewer/serve.py --scene bedroom_marble --port 8321`
  from entangled_gen.
- Syntax checks used this session: node --check on the extracted
  module script; ast.parse on serve.py.
- Compose caches are per-object evidence-hash — the chain re-run cost
  only 33 fresh judgments out of 82.
