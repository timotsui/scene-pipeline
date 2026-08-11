# SESSION 2026-08-23 HANDOFF — BUG-HUNT DAY; NEXT SESSION FINISHES THE SCENE

(Real date 2026-08-10. REVIEW_LOG R-S2-66..71. Previous handoff:
SESSION_2026-08-22_HANDOFF.md — the poly-shell wiring story.)

## THE HEADLINE

The user walked the J9 grounding page top to bottom and every oddity they
poked turned into a real bug. All fixed at the source, all verified on
living_marble. The obj_018 saga is CLOSED. The pipeline map is caught up.

**NEXT SESSION = FINISH THE SCENE:**
1. **The J9 gate is ONE question now:** the chair split — are
   obj_021+obj_028 vs obj_041+obj_068 two chair models or one?
   Page: out/living_marble/graph/same_product_sheets/index.html
   (backup of the pre-rebuild verdict page sits next to it).
   If the user rules the split WRONG, the parked fix is the prompt bar
   ("same kind in one room is one product unless they LOOK different;
   size is never a reason to split") — one re-judge + materialize.
2. **Then compose/shopping**: supported_by → shopping/pick → fit/place →
   loop. The graph is ready (appearance forward, scene_state reads, all
   compose modules rewired R-S2-65). EXPECT small wiring issues — the
   chain has not executed since the restructure. That is the point of
   running it.

## WHAT LANDED THIS SESSION (all user-driven, in order)

1. **J9 grounding review page** (R-S2-66 prelude): --dry-run now writes a
   GROUNDING page — per pool, why the members share it (the NAME is the
   only pooling rule) + the exact facts the judge's prompt carries +
   never-judged singletons. Built so the user could review pooling
   BEFORE any model call.
2. **Children keep their photos** (R-S2-66): SP4 enrichment children were
   born photo-less (2D rect + image thrown away at mint). Fixed at
   source (members_inline) + build_graph cuts their crops + counted
   zero-crop warning + living backfilled (obj_005_c00/obj_017_c00 now
   have crops + J6 descriptions). SECOND BUG documented+skipped (user:
   "relatively small"): children of merged parents are never compared as
   duplicates; designed fix on the shelf in R-S2-66.
3. **Stale crop files** (R-S2-67): 9 of 246 crops showed OTHER objects'
   pictures — the 08-06 re-run renumbered everything, the crops folder
   was never emptied, and skip-existing served dead objects' photos
   (obj_005 "bookshelf" wore the old coffee table's crop). Fix =
   ownership: build_graph wipes+recuts graph/crops every run (--recrop
   gone); describe_nodes wipes crops_ctx. All 246 re-cut, census 0
   mismatches. J6 was never poisoned (context crops were always fresh);
   J9's sheets were.
4. **Same product = a relationship** (R-S2-68, USER DESIGN RULE): no size
   rides on the relationship — materialize rule 5 now writes pairwise
   SAME_PRODUCT edges AND writes the product size INTO each member's box
   in its OWN orientation (door on two perpendicular walls = width/
   thickness swapped), anchored at the SUPPORT FACE (user: always).
   Sheet card prints "L wide x H tall x S thick". Shopping's fitter
   already tried assets turned 90° — the graph needed this, not the
   fitter.
5. **The ballot fix — obj_018 CLOSED** (R-S2-69): principle on record =
   "the gate escalates, never decides". A guard-blocked measurement now
   rides its doubt as a named candidate into J8's docket
   (rejected: proposed_box, truncated: NEW measured_candidate). Proven
   live: J8 shipped obj_018's small box at conf 0.85 on the two-name
   ballot (vs 0.62 for the big box when it had no choice). Chain rebuilt
   through grouped: settled 0.17x0.05x0.16, grouped 0.199x0.031x0.139.
   Retry (reshoot) stays undesigned — wanted only if J8 goes UNCLEAR.
6. **Pipeline map caught up** (R-S2-70, subagent): 19 sections; J8/J8s
   un-dashed, J9 v2 card, poly shell story, ballot principle. THREE map
   decisions left for the user: J9 dash-vs-solid, stale chain counts,
   trimming dated history.
7. **Sub-objects skip J9** (R-S2-71, USER RULE): `sub_object` flag →
   never pooled (small, inconsequential; bought by own box+photos);
   still face J1/J8. 3 excluded on living (incl. obj_039). Magazine
   pool re-judged on corrected crops: ALL THREE shelf stacks now ONE set
   (obj_029's "alone" was a stale-crop verdict).

## STATE OF THE GRAPH (living_marble)

- Chain whole through `grouped` (45 nodes), additive checks PASS
  everywhere. 1 known conflict (obj_011 J8-swap vs J8s-split, old).
- J9 verdicts CURRENT (no re-run needed): lights = ONE set of 7,
  chairs = the open split, doors/sofa/bookshelf/pillows/magazines
  settled. 36 SAME_PRODUCT edges, 18 boxes at product size.
- Preview manifest still run_kind=partial, canon_eligible FALSE — a FULL
  vote re-run is owed sometime (also refreshes old-vocab doubt texts).

## GOTCHAS FOUND THIS SESSION (for the unattended chain)

- record_vote_doubts WITHOUT --apply updates vote_doubts.json but not
  the graph `vote` block J8 reads — J8 judged stale doubts once before
  it was caught. KNOWN-OPEN: freshness check or make --apply the only
  mode.
- VOCABULARY: pre-rename DATA still says "carve" (multiplicity.json 103x,
  vote_doubts 21x, preview manifest 44x, split_cuts 4x) — TRANSLATE when
  quoting; the CODE is clean. User corrected this for the third time.
- Old numbering only survives as FILES; the wipe rule killed the last
  known door. Any per-object file folder that tops up across re-runs is
  suspect.

## UNCOMMITTED (now ~5 sessions deep — worth a commit checkpoint)

scene-pipeline working tree: slicevote.py, pano_recenter.py,
room_shell.py, graph/{build_graph, build_edges, describe_nodes,
judge_same_product, judge_multiplicity, materialize_layers,
record_vote_doubts, migrate_walls_w5, view_cams, node_views,
rederive_voted_edges}.py, viewer/serve.py, pipeline_map.html,
PIPELINE.md, docs (REVIEW_LOG R-S2-57..71, handoffs, plans).
Commit as Timotsui / timotsuihc@gmail.com when the user says go.

## QUEUE AFTER THE SCENE IS FINISHED

Card-race audit (~100 cached replays, user-approved) · culled-camera
audit renders (await go) · node_views 55 retake renders (await go) ·
full vote re-run for canon · ballot retry design (only if J8 goes
UNCLEAR) · declip rotation idea (parked) · viewer drawer for the
CONNECTOR arch node.
