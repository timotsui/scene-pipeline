# Session 2026-08-01 — R2/R4 passed · snap re-run · propose_edits first full run · viewer = 3 new review modes

⭐ **FINAL STATE (read this block first)**

All existing-module gates are now provisionally passed: **R1, R2, R4 =
provisional PASS; R3 ruled (floor). R5 (propose_edits) = OPEN** — first
full run done, and the **NEXT SESSION'S FOCUS (user-declared): improve
the propose_edits module**, starting from the R5 findings below.
`PLAN_COMPOSE_LOOP.md` (R2/R4 user verdicts, R5 entry, the
dependent-placement contract in the PH1 section) is the full record.

## Gates ruled this session

1. **R2 consistency = PASS** (provisional, "results make sense"). The
   user-spotted invariant VERIFIED: no DROP can touch a supported_by
   relation — structural (matched edges are code-stamped before the LLM
   sees leftovers, consistency.py:245) + empirical (0/13 drops conflict
   with any option incl. alternates/against).
2. **R4 snap = PASS** (provisional) after re-run on the v6 layer:
   18 LARGE (was 7 stale); obj_001 floor-snap 0.191 = exactly its known
   truncation float; obj_002 AC 0.255 ghost = the demoted verdict
   quantified (eyeball still open). **STANDING USER RULING: dependents
   have no exact position target by nature until real meshes (books need
   shelf LEVELS the box model doesn't carry) — large dependent
   corrections = expected noise; stage invariants = anchors correct +
   relationship edges correct.** Contract recorded in PLAN (PH1 section)
   + S4_SHOPPING_DESIGN_NOTES.md (relative placement = the
   mesh-independent evidence, derive at shopping time; children
   re-resolve against shopped parent's interior, chain order).

## R5 · propose_edits first full run — OPEN, next session's work

Run (v6 layer): 4 delete candidates → **3 DELETE / 1 KEEP** ·
**5 ADDs** (blanket on:obj_008 0.8 · keyboard on:obj_039 0.75 · mouse
on:obj_039 0.6 · wardrobe floor 0.55 · trash can floor 0.55).

**PROVISIONAL FINDING (the improvement seed):** the two book DELETEs
(obj_061 0.72, obj_076 0.70) look WRONG with cause understood — the
aggregator's duplicate-regex matched consistency DROP reasons saying
"Duplicate wall contact" = duplicate **FACT** (R2's inherited-wall-touch
consolidation family), not duplicate **OBJECT**; the LLM confirmed
deletion from that misread signal alone (existence was never in doubt).
obj_083 plant DELETE 0.75 = the genuine call (v6 intrinsic "seen
through glass") — user eyes on ctx crops decide. obj_093 shelf KEEP =
correctly deferred to SAME_CANDIDATE judging. Adds read sane +
conservative.

**PROVENANCE of the poison signal (traced with the user, 4 links):**
(1) consistency.py's PROMPT defines DROP with "the losing duplicate
when one object was recorded inside two different containers" — seeded
the word in the OBJECT sense. (2) The sonnet judge reused it in the
FACT sense in v6 reasons ("Duplicate wall contact inherited…"); the
07-26G run had phrased the same family with no "duplicate" at all —
run-to-run prose drift armed the trap. (3) propose_edits' dup_re
/duplicat/i was calibrated on ONE 07-26G sentence (the genuine
obj_093-IN-obj_080 duplicate-shelf hint). (4) The aggregator's f-string
authored "possible duplicate" — an assertion nobody upstream made.
Lesson: the one semantic judgment in the chain was done by grep.

**REFRAMED IMPROVEMENT PLAN (user discussion 08-01 — supersedes the
earlier "split the signals / feed existence evidence" fix ideas):**
(a) DELETE tripwire #2 (duplicate-regex) outright — edge-consolidation
drops are RESOLUTIONS (R2 settled: object fine, edge redundant), and
even genuine object-duplicate hints don't belong in a delete channel:
the remedy for a true duplicate is MERGE (evidence consolidates), not
delete. Remaining delete sources (none_plausible, all-support-dropped +
weak conf, existence disputes) correctly produced obj_083 and stayed
silent on the books. (b) Duplicate hints become a PETITION TO REOPEN
SAME_CANDIDATE dedup cases with new evidence. Checked in the data: the
graph stage's dedup judging DID run and merge (14 record pairs, real
merges: chair 000+004, mat triple 031+033+055, bookshelf 022+069…) BUT
the shelf nest obj_043/080/093/140 had only 1 of 6 pairs ever
NOMINATED (043–080, gray zone, judged distinct); obj_093/obj_140 were
never charged — nomination is geometric-only (IoU/containment), and
all the duplicate evidence (R2 flag, 30 multi-option runner-ups in the
nest, snap's book cluster) arrived AFTER that court closed. The
loop-in-loop design predicted exactly this feedback: compose evidence →
reopen/nominate dedup cases next loop iteration. Map records this as
card text, explicitly NOT built.

Module contract (for the improvement work): reads supported_by.json +
consistency.json + graph provenance ONLY (no images, no boxes); signals
aggregated deterministically (propose_edits.py:179-215); one batched
delete confirm/deny + one batched add call; PROMPT_VERSION 1;
WEAK_TOP_CONF 0.5; output isolated in compose/edit_proposals.json,
nothing consumes it (map: dashed).

## Viewer additions (all on the scene-graph row header, :8321)

Three new review modes (checkbox each, newest-gate precedence
edits > snap > consistency > supported_by review), all with click-card
sections:
- **consistency** (jCsRev): box colors = per-edge verdicts on edges the
  object is SUBJECT of (green all-KEEP / red all-DROP / orange mixed /
  dim code-settled); card lists per-edge verdict+reason, both roles.
- **snap** (jSnRev): colors by correction size (red >10 cm / yellow
  2–10 cm / green ok / dim no-move-by-design); white ghost outline =
  snapped AABB + correction line; card shows disposition+magnitude.
- **edits** (jEpRev): red DELETE / green KEEP / yellow unjudged / dim
  never-flagged; blue floating "+ADD" labels at declared support; card
  shows verdict + raw doubt signals.
- serve.py: new routes /consistency.json, /snap.json,
  /edit_proposals.json.

## Ops

- Viewer RUNNING on :8321 at session end — restart:
  `python viewer/serve.py --scene bedroom_marble --port 8321`.
- **NOT COMMITTED** — everything from 07-30→08-01 (describe_nodes,
  supported_by, viewer index+serve, map, docs, this session's 3 viewer
  modes + doc updates) uncommitted in scene-pipeline (commit as
  Timotsui / timotsuihc@gmail.com).
- Eyeball items still open: obj_002 AC (anchor-class, snap ghost shows
  the stake), obj_013 (0.9 shelf-top). Parked: multi-option magenta
  threshold · hybrid escalation re-time · obj_013 dual-contact watch.
