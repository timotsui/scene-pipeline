# SESSION 2026-08-29 HANDOFF — the re-run night that became the convexity night

(Real date 2026-08-12 evening → 08-13 early morning, user in the loop
nearly the whole way. REVIEW_LOG **R-S2-159..166b**. Previous handoff:
SESSION_2026-08-28. All committed AND PUSHED through **4236190**;
nothing owed on git. Written while the user was away post the bed-fix
verification; no reply received to the standing shell-wave question.)

## 0. THE ONE-LINE TRUTH

The 08-28 work order ran to completion (scale applies + chain re-runs
PASS on fresh05/08, yaw state-apply built and proven on fresh06 +12°,
fresh09 wall re-run PASS) — and then the user walked fresh08 in the
viewer and found that slicevote's wall capture and shell clip still
assumed a CONVEX room, which the new polygons are not: 9-26 wall items
per scene were crushed to slivers. The rest of the night was
user-driven find-and-fix: the convexity fix, the rug tier rule, the
density gate + walk-through slab (sheet-approved), the add-channel
kill, the outside-snap, and the bed-facing pair (166 + the 166b
self-correction).

## 1. SCENE STATE RIGHT NOW (all gates PASS)

| scene | shipped state |
|---|---|
| fresh05 | metric (s=0.639), full re-run PASS, 47 nodes — BUT wall items still crushed (pre-fix vote) + yaw −2.25° un-applied |
| fresh06 | DE-TILTED (+12° applied, verify 0.00), full re-run PASS — wall items still crushed (pre-fix vote) |
| fresh08 | THE SHOWCASE: metric (arch tier, verify s=1.0), post-fix vote (1 crushed = window seat), bed placed AND facing right (dot 1.0), chair anchor via rug rule, ZERO invented adds, wardrobe snapped inside, 22 placed |
| fresh09 | wall re-run PASS 35/35 — but 26/27 wall exempts crushed (pre-fix vote); its office is the worst convexity casualty |

**fresh08 is the only scene carrying the R-S2-161..166b fixes in
shipped state.** fresh05/06/09 need `--from vote` minimum.

## 2. THE STANDING DECISION (asked, unanswered — the next session's
first question)

**The `--from shell` wave.** The user APPROVED the new wall outline on
the fresh08 sheet ("the outline is good") — density gate (Otsu split,
4x guard) + walk-through slab (waist 0.9 → crown 1.9). It is
SHEET-ONLY in shipped state but **the CODE IS LIVE**: any shell run
now produces the new outline. A from-shell wave over
fresh05/06/08/09 ships it everywhere AND fixes 05/06/09's crushed
wall items (from-shell includes the vote) AND likely rescues fresh08's
window seat (the bay now opens to the glass line, so the bench box
lands inside the polygon). ~45-60 min/scene, two-lane proven.

## 3. THE FIX STACK (headers; read the entry before touching)

- 159: de-tilt made truly sheet-only + plan_yaw_deg actually recorded
- 160: scene_yaw.py (yaw state-apply; extents RECOMPUTED not
  corner-rotated — the third build finding; *_preyaw backups)
- 161: THE CONVEXITY FIX — wall capture needs REACH + majority-REST
  (family spans); shell_clip = AABB of (footprint ∩ interior polygon),
  Sutherland-Hodgman; verified on the exact failing boxes
- 162: rug tier rule — flat-on-floor hosts (FLAT_AXIS_M reused) are
  see-through for the tier; bed/chair stay anchors
- 163: PRE-REGISTRATION ONLY: vote-internal pipelining (the speed
  lever); j3/j4/j6 stage-parallel REJECTED (both write
  scene_graph.json — single-baton design)
- 164: density gate + walk-through slab (USER-DESIGNED off the sheet;
  sheet-approved; v1-vs-polygon disagreement WIDENS — §3 item)
- 165: add channel KILLED (--keep-adds revives); out-of-room swap
  boxes snap flush to the closest wall (point-in-polygon defense)
- 166/166b: pillow facing = hard evidence, 90/270 allowed at the canon
  15% (FACE_EVIDENCE_TOL); the pca "fix" REVERTED same night (user
  caught the bed sideways; dot 0.5 was the tell — the omission was a
  design decision wearing a bug's costume)

## 4. OPEN QUESTIONS FOR THE USER (bring with receipts)

1. The from-shell wave (§2) — the big one.
2. fresh05's −2.25° yaw: apply + re-run (~80 min), or below caring?
3. fresh05's scale verification reads s=0.884 (consensus, richer ruler
   population post-eye-fix pulls low) vs fresh08's clean 1.0 (arch).
   Same watch-class as fresh09's doors 1.087 vs ceiling 0.832.
4. Canon eligibility: fresh08's vote is stamped NOT canon-eligible
   (partial re-runs mix code revisions). A full single-revision pass
   per scene would clean it — cheapest as part of the from-shell wave.
5. v1-vs-polygon widening (R-S2-164 note): node_views + envelope still
   read v1 walls; under the new rules the two rooms disagree MORE.
   The §3 consumer round (snap/supported_by infinite planes, compose
   box-only walls) is now overdue.
6. Speed: R-S2-163 pre-registered (vote pipelining); two-lane
   run_fleet wiring still awaits a formal go.
7. PARKED.md: untouched all night, incl. item 4 (wall-embed). The bay
   OUTLINE resolution (164) is adjacent but distinct — deep bay
   objects still flatten (obj_058's pocket curtain).

## 5. TRAPS

- The new shell rules are LIVE CODE, sheet-approved, NOT shipped.
  Do not run any shell stage casually — it ships the new outline.
  That is expected for the wave, but say so.
- fresh08's grouped/vote state is post-fix; 05/06/09's is NOT.
  compare_methods / the viewer read whatever is shipped per scene.
- scene_yaw applies ONCE (yaw_applied guard; *_preyaw backups). A
  crash mid-apply leaves partial state — restore *_preyaw first
  (happened once, fresh06, receipts in R-S2-160).
- propose_edits: adds come back with --keep-adds ONLY. The swap snap
  needs a polygon (v1-only scenes skip it).
- Launch discipline unchanged: WMI-detach, ONE watch_gpu (running,
  PID 7896 era — check), clock lock via boot task, verify clocks.sm
  <= 1500 under load in gpu_watch.csv. Three lanes proven safe again.
- The viewer server on :8321 was launched detached tonight (WMI).

## 6. WHERE EVERYTHING IS

- Commits: 284c2c0, 4584e65, 40c3cfd, 679254a, d041379, 3e5796d,
  4236190 (+ this handoff). All pushed.
- New tool: scene_yaw.py (measure/apply/verify, R-S2-121 pattern).
- Sheets: out/<scene>/room_shell_steps.png regenerate read-only via
  `python room_shell.py --scene <sc> --steps-sheet` — fresh08's shows
  the approved outline (density gate + slab); others still old-rule
  until regenerated.
- Receipts scripts from the night: scratchpad diag_*.py (session temp,
  not repo).
- fresh08 viewer: http://localhost:8321/?scene=fresh08
