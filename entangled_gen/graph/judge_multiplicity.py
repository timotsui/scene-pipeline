"""MULTIPLICITY JUDGE (J8) — one box or several? Which box ships?
(PLAN_VOTEBOX_DOWNSTREAM Phase A; DESIGN v2.1 ADOPTED 2026-08-07 R-S2-35.)

CONTRACT: GETS one docket case = a resolved node + the AUTO vote doubts
that admitted it (large_empty_notch / pano_vs_cluster / culled_clusters /
low_plan_fill / rebox_rejected_smaller / rebox_truncated — Rule #1: no
user-routing channel, the pipeline raises its own questions) plus the
v2.1 stimuli.
DECIDES, representation first: (1) the OUTCOME — ONE_BOX / SPLIT /
NO_GOOD_BOX / UNCLEAR — (2) WHICH GEOMETRY SHIPS when the outcome is
ONE_BOX (which of the boxes on record is the object is undecidable from
geometry alone; it is exactly what the judge is here to solve), and (3)
on a SPLIT, the IDENTITY ANNOTATION — one_structure / copies(k) /
distinct + per-part owners.
NO_GOOD_BOX (v2.3, the obj_021 ruling): the evidence DOES settle it and
the answer is "none of these boxes is usable" — every candidate badly
cuts the object and/or mostly contains things that are not it. It is NOT
UNCLEAR (which means the evidence does not settle the question); it
carries a `reason`, has no `ship`, and materialize keeps the node's
current shipping geometry and raises it as an open question.

THE SHIP CHOICE IS PER CASE (v2.2, user ruling 2026-08-08 ~04:30 — "allow
it to ship the boxes it is able to evaluate"). The old fixed enum
(ship_pano | ship_vote | either) was a VOTED node's vocabulary: it named
two boxes a vote-EXEMPT node does not have, so obj_018 — which had
correctly seen that its box over-reaches into ceiling architecture and
that the REJECTED magenta candidate is the actual fixture — had no legal
way to say "ship the magenta one" and was forced to answer UNCLEAR. So
every case now carries its OWN CANDIDATE BOX LIST, built from the boxes
that actually exist for that node, each with a stable key, its dimensions
and its provenance sentence:
    voted node  "vote" (boxes.vote2, the elected cluster)
                 "pano" (boxes.pano, the founding-mask share)
    exempt node  "current" (the shipping box = the ORIGINAL pre-vote box
                 after the shell clip — it never voted)
                 "rebox_candidate" (the face-on re-box the guard REJECTED;
                 shipping it ADOPTS the smaller measured box)
    both         "either" — ONLY when two of the above agree within
                 AGREE_TOL on every face.
The answer field is "ship": <one key from THIS case's list>; the prompt
lists that case's keys verbatim and the parser rejects any other value
(legacy ship_vote/ship_pano/either replies map onto vote/pano/either).
v2.3 asks that choice as a COMPARISON with tolerance — pick the BETTER
box, COMPLETE (contains the whole object) before TIGHT ENOUGH (not mostly
empty space or another object's territory), a box only has to be
REASONABLE — and each key's old failure-mode sentence is demoted to a
HINT, never the test.
It NEVER edits the graph — verdicts land in the graph/multiplicity.json
sidecar; materialize (Phase C) is the editor. A mistake looks like:
splitting a real single object, blessing one box around two real
instances, or picking the occlusion-shaved box over the true extent.

FACTS FROM THE GRAPH'S OWN EDGES (v2.1, the obj_063 rule): every
relational fact in the docket line is READ from graph["voted_edges"]
— the 4g2 edges re-derived on the VOTED boxes by the Phase-B2
loop-back (graph/rederive_voted_edges.py), carrying J0 triage and J1
SAME_CANDIDATE verdicts. J8 computes NO private overlap lists: the v2
private top-6 list dropped obj_063 (the other sofa, ~85% of its volume
inside obj_011's box) behind six pillows and the judge ruled the sofa
case without the decisive fact. Same-class neighbours are NEVER
truncated; unrelated-class facts are capped at FACT_CAP by relevance.

STIMULI v2.1 (the anti-drift design, one-look rule): the object's OWN
vote renders — the four view-tunnel cards (+ eye-height / isolation
cards when the ladder escalated) and the plan render the vote detected
on — with the vote's 3D boxes PROJECTED onto them:
    ORANGE  = boxes.vote2 (the gate-3 vote-cluster box)
    CYAN    = boxes.pano  (this node's pano-mask-filtered box)
    GREEN   = a SAME-CLASS neighbour node's voted box, labelled with its
              id (v2.1) — the is-the-rest-another-object evidence made
              visible, not just numeric. Boxes come VERBATIM from
              scene_manifest_slicevote_preview.json.
    RED DASHED (plan view only) = the large_empty_notch rectangle
    MAGENTA = the face-on re-box candidate the vote REJECTED (exempt
              cases only, see below)

THE BOX-CONTENT PANEL (v2.2, exempt cases only — the evidence gap traced
on obj_018): a face-on render of the SCENE cannot settle "one fixture or
two", because the ceiling architecture around the fixture is in the
picture too. So an exempt case also gets an ISOLATED render of its box's
OWN CONTENT — only the gaussians inside the node's box, grown a small
margin in-plane and opened BOXC_OPEN along the plane normal into the room
so a fixture that hangs down is not sliced off, viewed along that normal
from the room side. The machinery is graph/split_cuts.py's (Splat subset
write + the WSL render call), imported not re-implemented, with the same
params-sidecar staleness gate: a render is REUSED only when its sidecar
hash (camera + res + region + the source ply's identity) matches, and is
deleted and regenerated otherwise. A failed render is a BUILD NOTE and a
missing panel — never a fabricated one.

VOTE-EXEMPT CASES (2026-08-08, the rebox_rejected_smaller and
rebox_truncated doubts — a re-box the vote threw away for being far too
small, and a re-box it accepted after the frame clipped most of the
sides it was meant to measure): a kept_wall / kept_ceiling node skipped
the vote, so it has NO cone-map entry, NO cards and NO plan detection —
the stimulus above cannot be built for it. Its one real observation is
the vote's FACE-ON (perp) render, whose camera the vote wrote to its
own params sidecar
(pool_retake/slices/vote_<id>_perp.params.json: eye/aim/fov/res as
rendered). That render is the case's single panel, annotated with the
same convention: ORANGE = the node's CURRENT (shipping) box, GREEN =
same-class neighbours, MAGENTA = the rejected face-on candidate (the
rejection kind only — a truncated re-box was ACCEPTED, so it has no
rejected candidate and no magenta wireframe; its opening says so). The
camera is READ from the sidecar, never recomputed; a missing sidecar or
png means NO panel and a build note, never a guessed camera.
The projection uses vote_cams.py — the SAME camera module the vote's
renderer used — so an overlay cannot drift from the render it annotates.
Card cameras come from each render's own votetgt sidecar (fallback: the
conemap views record); the plan camera is rebuilt with
vote_cams.top_cam_for and is only drawn when its eye VALIDATES against
the eye the vote recorded (within EYE_TOL). No guessed projections.

DEPENDENCY-ORDERED JUDGING (v2.4, user ruling 2026-08-08 — "judge INNER
BEFORE OUTER"): a case's verdict is placed against its NEIGHBOURS' boxes,
and another case's verdict can MOVE one of those boxes. J8 ruled obj_063
ship=vote, growing it from x -1.532..0.335 to -1.514..0.636 — while the
split judge had already cut obj_011 at x=0.335, chosen BECAUSE that was
obj_063's edge; the two nodes ended up overlapping by 0.30 m. Every case
was built up front and judged in parallel, so no case could ever see
another's result. Now:
  * ONE SETTLED MAP is the geometry every case reads. It starts as the
    vote's SHIPPING boxes (scene_manifest_slicevote_preview.json,
    verbatim) and each ONE_BOX verdict REPLACES its own node's entry with
    the box it NAMED, resolved from the VOTE's own records exactly as
    materialize resolves it (vote -> the vote report's boxes.vote2, pano
    -> boxes.pano, rebox_candidate -> the rejected face-on re-box on the
    node's own doubt). SPLIT / UNCLEAR / NO_GOOD_BOX leave the entry
    untouched. It ships in the sidecar as `settled_boxes`.
  * DEPENDENCY ORDER over the docket, from geometry only: for two docket
    boxes whose overlap is >= DEP_FRAC of the SMALLER box's volume
    (containment-ish), the SMALLER is judged FIRST. Cases are grouped into
    LEVELS (`judge_order` in the sidecar); a level's cases are independent
    and still run concurrently, levels run in sequence. Same number of
    model calls, just sequenced.
  * SHEETS ARE BUILT LAZILY, inside the per-case work, so a case sees the
    settled map AS IT STANDS AT THAT MOMENT. A moved neighbour box changes
    the prompt and the panels, so the case cache key MISSES — that is the
    correct behaviour, not a bug.
  * A POST-PASS CONSISTENCY CHECK (pure arithmetic, no model calls)
    re-measures every docket pair afterwards and records any pair whose
    overlap fraction GREW under `post_judge_conflicts`. It is RECORDED,
    never acted on — it catches dependencies that only appear after a box
    grows.

REVIEW-FIRST: --sheets-only builds one self-contained HTML sheet + the
verbatim prompt per case (graph/multiplicity_sheets/) with ZERO model
calls — USER GATE A1 eyeballs the stimuli before any verdict runs. It
builds every sheet against the INITIAL settled map and judges nothing.

Run:  python graph/judge_multiplicity.py --scene living_marble --sheets-only
      python graph/judge_multiplicity.py --scene living_marble
      [--only obj_011,...] [--model sonnet] [--concurrency 8]
"""
import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent.parent
GRAPH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(GRAPH_DIR))   # sibling stage modules (split_cuts)
import paths  # noqa: E402
from vote_cams import (FOV_GOOD, RES, WALL_PAD,  # noqa: E402
                        make_cam, top_cam_for)

MODEL = "sonnet"
CONCURRENCY = 8   # user ruling 08-04: lanes are couriers, compute is cloud-side
CALL_TIMEOUT_S = 600   # s — raised from 240 (2026-08-08): image-heavy cases
                       # legitimately run long; a timeout is a failed attempt,
                       # never a crash (see run_case)
OUTCOMES = ("ONE_BOX", "SPLIT", "UNCLEAR",           # v2.1 — representation
            "NO_GOOD_BOX")                           # v2.3 — the kill
IDENTITIES = ("one_structure", "copies", "distinct")  # v2.1 — annotation
# v2.2: the ONE_BOX answer is "ship": <key from THIS case's candidate list>.
# The old fixed enum survives only as an inbound compatibility mapping so a
# cached/legacy reply still parses.
LEGACY_SHIP = {"ship_vote": "vote", "ship_pano": "pano", "either": "either"}
AGREE_TOL = 0.05   # m — per face. Two candidate boxes closer than this on
#                    every face are the same claim, and only then does the
#                    case offer "either".
FACT_CAP = 8       # unrelated-class fact lines kept, by relevance; same-class
#                    facts are NEVER truncated (the obj_063 rule)
DEP_FRAC = 0.5     # v2.4 — two docket boxes whose overlap is at least this
#                    share of the SMALLER box's volume are a containment-ish
#                    pair: the SMALLER one is judged FIRST (inner before
#                    outer), so the bigger one sees a settled box.
SETTLED_BASE = ("vote shipping box (scene_manifest_slicevote_preview.json)"
                ", verbatim")   # the settled map's starting provenance

# ---- the box-content panel (exempt cases; machinery from split_cuts.py) --
BOXC_FOV = 50.0      # deg — the adopted isolated-render lens (split_cuts)
BOXC_RES = 1024      # px  — ditto
BOXC_MARGIN = 0.05   # m — the box is grown this much on its two IN-PLANE
#                      axes before the gaussians are cut out
BOXC_OPEN = 0.30     # m — and opened this much along the plane NORMAL, into
#                      the room, so a fixture hanging off a flat box is not
#                      sliced off by the box that is under question
BOXC_STANDOFF = 0.50  # m — minimum clearance between the camera and the
#                       room-side face of the region it is looking at
BOXC_AXIS_TOL = 1e-3  # m — the vote's face-on camera must be axis-aligned
#                       to this, or the normal is not recoverable and no
#                       panel is built (a camera is never guessed)

# ---- overlay drawing ----
COL_VOTE = (255, 153, 0)     # orange — boxes.vote2 (matches the cone map)
COL_PANO = (0, 188, 212)     # cyan   — boxes.pano
COL_NOTCH = (255, 40, 40)    # red dashed — the large_empty_notch rectangle
COL_NEIGH = (0, 230, 90)     # green  — a same-class neighbour's voted box
COL_REJECT = (255, 0, 200)   # magenta — the REJECTED face-on re-box candidate
NEAR_Z = 0.05                # clip box edges to this camera-space depth
EYE_TOL = 1e-3               # m — plan-camera reconstruction must match the
#                              eye the vote recorded, or no overlay ships


# ---- claude bridge (judge-chain pattern) ---------------------------------

def claude_env():
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(k, None)  # stale-API-key hijack gotcha (project memory)
    return env


def call_claude(prompt, cwd, model):
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("[multiplicity] claude.exe not on PATH")
    r = subprocess.run([exe, "-p", prompt, "--model", model],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=claude_env(), cwd=str(cwd),
                       timeout=CALL_TIMEOUT_S)
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if r.returncode != 0:
        raise RuntimeError(f"claude exit {r.returncode}: "
                           f"{err[:400] or out[:400]}")
    low = (out + " " + err).lower()
    for bad in ("invalid_api_key", "authentication_error", "credit balance"):
        if bad in low:
            raise RuntimeError(f"claude API-billing/auth error: {out[:400]}")
    return out


def _clean_parts(parts):
    """Validate the parts list: [{name, owner}] with owner in
    this_node | existing:<id> | missing_instance. None = malformed."""
    if not isinstance(parts, list) or not parts:
        return None
    clean = []
    for p in parts:
        if not isinstance(p, dict):
            return None
        owner = p.get("owner")
        ok = owner in ("this_node", "missing_instance") or (
            isinstance(owner, str)
            and owner.startswith("existing:")
            and owner[len("existing:"):].strip())
        if not ok:
            return None
        clean.append({"name": str(p.get("name", "")).strip(),
                      "owner": owner})
    return clean


def parse_verdict(text, ship_keys=()):
    """PARSER v4 — the v2.2 judge reply: {"outcome", "ship"?, "identity"?,
    "count"?, "parts"?, "confidence", "reason"}.

    `ship_keys` is THIS CASE's candidate-box key list (build_candidates).
    The ship value is validated against it — an unknown key is a malformed
    reply, not a silent pass-through — and a legacy `box_ruling` value is
    accepted when it maps (LEGACY_SHIP) onto a key this case really has.
    A case with NO candidate boxes cannot be asked which box ships, so
    `ship` is optional there and absent from the verdict.

    Conditional-key rules (required EXACTLY when the answer demands them):
      outcome     enum ONE_BOX | SPLIT | NO_GOOD_BOX | UNCLEAR
      ship        required + in ship_keys iff outcome == ONE_BOX and the
                  case has candidate boxes. NEVER carried on any other
                  outcome — NO_GOOD_BOX names no box on purpose.
      identity    required + valid iff outcome == SPLIT
      count       required positive int iff identity == "copies"
      parts       required non-empty valid list iff identity == "distinct"
                  (accepted, not required, on the other identities)
      confidence  clamped to [0, 1], default 0.5
      reason      string (empty when absent); REQUIRED non-empty iff
                  outcome == NO_GOOD_BOX — a kill with no stated fault is
                  a malformed reply, not a verdict

    Returns the validated verdict dict, or None on any malformed reply
    (caller retries once, then ships the UNCLEAR fallback)."""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    raw = m.group(1) if m else None
    if raw is None:
        i = text.find("{")
        if i >= 0:
            try:
                obj, _ = json.JSONDecoder().raw_decode(text[i:])
                raw = json.dumps(obj)
            except ValueError:
                raw = None
    if raw is None:
        return None
    try:
        v = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(v, dict) or v.get("outcome") not in OUTCOMES:
        return None
    outcome = v["outcome"]
    out = {"outcome": outcome}
    if outcome == "ONE_BOX" and ship_keys:
        ship = v.get("ship")
        if ship not in ship_keys:
            # legacy vocabulary (a cached reply, or a model quoting the
            # old enum) — accepted only when it names a box this case has
            ship = LEGACY_SHIP.get(v.get("box_ruling"))
            if ship not in ship_keys:
                return None
        out["ship"] = ship
    if outcome == "SPLIT":
        identity = v.get("identity")
        if identity not in IDENTITIES:
            return None
        out["identity"] = identity
        if identity == "copies":
            try:
                count = int(v.get("count"))
            except (TypeError, ValueError):
                return None
            if count <= 0:
                return None
            out["count"] = count
        parts = _clean_parts(v.get("parts"))
        if identity == "distinct":
            if parts is None:
                return None
            out["parts"] = parts
        elif parts is not None:
            out["parts"] = parts        # optional on the other identities
    try:
        conf = float(v.get("confidence", 0.5))
    except (TypeError, ValueError):
        conf = 0.5
    out["confidence"] = round(min(1.0, max(0.0, conf)), 2)
    reason = v.get("reason")
    out["reason"] = reason.strip() if isinstance(reason, str) else ""
    if outcome == "NO_GOOD_BOX" and not out["reason"]:
        return None      # a kill must say what is wrong with the boxes
    return out


# ---- THE SETTLED MAP + THE DEPENDENCY ORDER (v2.4) -----------------------
# THE BUG THIS EXISTS FOR (traced 2026-08-08): a case's cut/verdict is
# placed against a NEIGHBOUR's box, and another case can MOVE that
# neighbour's box. Every case used to be built up front and judged in
# parallel, so nobody saw anyone else's result — J8 grew obj_063 to
# x..0.636 after the split judge had already cut obj_011 at obj_063's OLD
# edge x=0.335, leaving the two nodes overlapping by 0.30 m.
#
# THE RULING (user, over re-running the chain to a fixed point — too much
# compute): JUDGE INNER BEFORE OUTER. The map below is the single geometry
# every case reads; the order below settles the contained box first.
#
# NOTE ON SCOPE: these overlaps decide ORDER ONLY. They are never shown to
# the judge and never become a relational fact — the obj_063 rule (v2.1,
# "J8 computes NO private overlap lists") still holds for everything the
# prompt says.

def box_vol(b):
    lo, hi = b["lo"], b["hi"]
    return (max(0.0, float(hi[0]) - float(lo[0]))
            * max(0.0, float(hi[1]) - float(lo[1]))
            * max(0.0, float(hi[2]) - float(lo[2])))


def box_overlap_vol(a, b):
    d = [max(0.0, min(float(a["hi"][k]), float(b["hi"][k]))
             - max(float(a["lo"][k]), float(b["lo"][k]))) for k in range(3)]
    return d[0] * d[1] * d[2]


def frac_of_smaller(a, b):
    """(overlap / the SMALLER box's volume, overlap m3) — the
    containment-ish number both the dependency order and the post-pass
    consistency check speak."""
    ov = box_overlap_vol(a, b)
    small = min(box_vol(a), box_vol(b))
    return (ov / small if small > 1e-9 else 0.0), ov


def same_box(a, b):
    """Byte-for-byte-equal boxes, to float noise. boxes_agree is the same
    face-by-face test — this only pins the tolerance to "identical", not
    to AGREE_TOL (which is a JUDGEMENT tolerance, 5 cm)."""
    return boxes_agree(a, b, 1e-6)


def named_box(nid, key, report, doubts):
    """The box a J8 ship key NAMES, resolved from the VOTE's own records —
    the same lookup materialize_layers.named_box does, so the map J8 judges
    against and the geometry materialize will actually apply cannot drift:
        "vote"            -> the vote report's boxes.vote2
        "pano"            -> the vote report's boxes.pano
        "rebox_candidate" -> the rejected face-on re-box the vote recorded
                             on this node's rebox_rejected_smaller doubt
        "current"/"either"-> NO-OPs: they name the box that already ships
    Returns (box|None, source). None means there is nothing to apply — the
    entry stands; a box is NEVER guessed."""
    bx = report.get(nid) or {}
    if key == "vote":
        return bx.get("vote2"), "pool_retake/slicevote_report.json boxes.vote2"
    if key == "pano":
        return bx.get("pano"), "pool_retake/slicevote_report.json boxes.pano"
    if key == "rebox_candidate":
        for d in doubts.get(nid) or []:
            if d.get("kind") == "rebox_rejected_smaller" \
                    and d.get("proposed_box"):
                return d["proposed_box"], ("vote doubt rebox_rejected_"
                                           "smaller.proposed_box")
        return None, "vote doubts (no rebox_rejected_smaller.proposed_box)"
    return None, ""          # "current" / "either" — the shipping box stands


def init_settled(voted_boxes):
    """The settled map at the start of a run: the vote's SHIPPING boxes,
    verbatim, for EVERY id in the preview manifest (not just the docket —
    a case's neighbours and a later stage's cover boxes are often
    non-docket nodes)."""
    return {i: {"lo": list(lo), "hi": list(hi), "source": SETTLED_BASE}
            for i, (lo, hi) in voted_boxes.items()}


def settle_verdict(settled, nid, v, report, doubts):
    """Fold ONE case's verdict into the settled map and return the record
    of what happened. ONLY a ONE_BOX verdict moves a box — it NAMES one,
    and the named box is resolved from the vote's own records (never from
    the J8 sidecar). SPLIT / UNCLEAR / NO_GOOD_BOX leave the entry exactly
    as it was. Each verdict touches only its OWN node's entry, so the
    order verdicts are applied in cannot change the final map."""
    v = v or {}
    rec = {"id": nid, "outcome": v.get("outcome"), "ship": v.get("ship"),
           "changed": False}
    if v.get("outcome") != "ONE_BOX":
        rec["why"] = "not a ONE_BOX verdict — the entry stands"
        return rec
    key = v.get("ship")
    if not key:
        rec["why"] = "ONE_BOX with no ship key (this case had no candidate " \
                     "boxes) — the entry stands"
        return rec
    b, src = named_box(nid, key, report, doubts)
    if b is None:
        rec["why"] = (f"ship={key} names no box to apply"
                      + (f" ({src})" if src else " (it names the box that "
                         "already ships)") + " — the entry stands")
        return rec
    cur = settled.get(nid)
    new = {"lo": [float(x) for x in b["lo"]], "hi": [float(x) for x in b["hi"]],
           "source": f"J8 ONE_BOX ship={key} -> {src}"}
    if cur is not None and same_box(cur, new):
        rec["why"] = "the named box already IS this node's shipping box"
        return rec
    if cur is not None:
        rec["was"] = {"lo": list(cur["lo"]), "hi": list(cur["hi"])}
    rec["now"] = {"lo": list(new["lo"]), "hi": list(new["hi"])}
    rec["changed"] = True
    rec["why"] = f"ship={key} named a different box — the entry MOVES"
    rec["source"] = new["source"]
    settled[nid] = new
    return rec


def dependency_levels(ids, settled, notes):
    """JUDGE INNER BEFORE OUTER. Edges come from GEOMETRY ONLY, over the
    docket cases: for two docket boxes whose overlap is at least DEP_FRAC
    of the SMALLER box's volume, the SMALLER must be judged BEFORE the
    bigger one. Remaining ties break on (volume, id), which is a strict
    TOTAL order — so every edge points forward in that order and the graph
    provably cannot cycle. The cycle branch below is therefore a safety
    net, not a normal path: it takes the smallest remaining member, marks
    the order ARBITRARY on the record, and keeps going rather than
    dropping cases.

    Returns {"levels": [[id, ...], ...], "edges": [...], "arbitrary":
    [...], "rule": ...}. Cases inside one level are independent and may
    still run concurrently; levels run in sequence."""
    ids = list(ids)
    key = {}
    for i in ids:
        e = settled.get(i)
        if e is None:
            notes.append(f"{i}: no box in the settled map — no dependency "
                         "could be computed for it (judged in level 0)")
            key[i] = (0.0, i)
        else:
            key[i] = (box_vol(e), i)
    order = sorted(ids, key=lambda i: key[i])
    deps = {i: set() for i in ids}          # i waits for every id in deps[i]
    pairs = []
    for ai in range(len(order)):
        for bi in range(ai + 1, len(order)):
            a, b = order[ai], order[bi]     # key[a] < key[b] -> a is smaller
            ea, eb = settled.get(a), settled.get(b)
            if ea is None or eb is None:
                continue
            f, ov = frac_of_smaller(ea, eb)
            if f < DEP_FRAC:
                continue
            deps[b].add(a)
            pairs.append({"before": a, "after": b,
                          "overlap_frac_of_smaller": round(f, 3),
                          "overlap_m3": round(ov, 4),
                          "vol_before_m3": round(box_vol(ea), 4),
                          "vol_after_m3": round(box_vol(eb), 4),
                          "why": f"{f:.0%} of {a}'s volume is inside {b} "
                                 f"(>= {DEP_FRAC:.0%}) — the smaller box is "
                                 "settled first"})
    lvl, remaining, arbitrary, n = {}, set(ids), set(), 0
    while remaining:
        ready = sorted((i for i in remaining if not (deps[i] & remaining)),
                       key=lambda i: key[i])
        if not ready:
            # SAFETY NET (unreachable while the (volume, id) total order
            # holds): mutual heavy overlap. Fall back to smaller-first and
            # SAY SO — an arbitrary order is recorded, never hidden.
            ready = [min(remaining, key=lambda i: key[i])]
            arbitrary.update(ready)
            notes.append(f"{ready[0]}: dependency cycle (mutual heavy "
                         "overlap) — its position in the judge order is "
                         "ARBITRARY (smaller-first/id fallback)")
        for i in ready:
            lvl[i] = n
        remaining -= set(ready)
        n += 1
    levels = [sorted((i for i in ids if lvl[i] == k), key=lambda i: key[i])
              for k in range(n)]
    return {"levels": levels, "edges": pairs, "arbitrary": sorted(arbitrary),
            "dep_frac": DEP_FRAC,
            "rule": "INNER BEFORE OUTER (user ruling 2026-08-08): for two "
                    "docket boxes whose overlap is >= "
                    f"{DEP_FRAC:.0%} of the SMALLER box's volume, the "
                    "smaller is judged first so the bigger one sees a "
                    "SETTLED neighbour box. Ties break on (volume, id). "
                    "Cases in one level are independent and run "
                    "concurrently; levels run in sequence."}


def post_judge_conflicts(ids, before, after, verdicts):
    """PURE ARITHMETIC, ZERO model calls. After every case is judged,
    re-measure each docket PAIR and record any pair whose overlap fraction
    GREW versus the pre-judging boxes — a dependency that only appeared
    once a box moved. RECORDED ONLY: this function never changes a box and
    never re-opens a case."""
    out = []
    ids = sorted(i for i in ids if i in before and i in after)
    for ai in range(len(ids)):
        for bi in range(ai + 1, len(ids)):
            a, b = ids[ai], ids[bi]
            f0, ov0 = frac_of_smaller(before[a], before[b])
            f1, ov1 = frac_of_smaller(after[a], after[b])
            if f1 <= f0 + 1e-6 or f1 <= 0.0:
                continue
            out.append({
                "a": a, "b": b,
                "overlap_frac_of_smaller_before": round(f0, 3),
                "overlap_frac_of_smaller_after": round(f1, 3),
                "overlap_m3_before": round(ov0, 4),
                "overlap_m3_after": round(ov1, 4),
                "verdicts": {i: {"outcome": (verdicts.get(i) or {}).get(
                                     "outcome"),
                                 "ship": (verdicts.get(i) or {}).get("ship"),
                                 "box_moved": not same_box(before[i],
                                                           after[i])}
                             for i in (a, b)},
                "note": "the two boxes overlap MORE after judging than "
                        "before. RECORDED ONLY — no box was changed and no "
                        "case was re-opened."})
    return out


# ---- relational facts: READ from graph["voted_edges"] -------------------
# J8 computes NO private overlap lists (the obj_063 rule, v2.1). Everything
# below only FORMATS the loop-back's own edges.

def other_end(nid, e):
    return e["b"] if e["a"] == nid else e["a"]


def is_arch(i):
    return isinstance(i, str) and i.startswith("arch_")


def node_class(i, names):
    """The class token a node is compared on: its resolved name/label.
    Architecture nodes have no class and are never 'same class'."""
    return "" if is_arch(i) else (names.get(i) or "").strip().lower()


def edges_touching(nid, edges):
    return [e for e in edges if nid in (e["a"], e["b"])]


def _num(ev, *keys):
    for k in keys:
        if isinstance(ev.get(k), (int, float)):
            return float(ev[k])
    return None


def fact_relevance(nid, e):
    """Ordering key for the unrelated-class cap. Tier first (identity
    verdicts and architecture/support facts are few and load-bearing, so
    they are never the lines that get cut), then |overlap|."""
    ev = e.get("evidence") or {}
    if e["type"] == "SAME_CANDIDATE":
        tier = 2
    elif is_arch(other_end(nid, e)):
        tier = 1
    else:
        tier = 0
    mag = _num(ev, "overlap_vol_m3")
    if mag is None:
        mag = _num(ev, "frac_of_smaller", "containment", "iou") or 0.0
    return (tier, mag)


def _ev_bits(ev, keys):
    out = []
    for k, label, kind in keys:
        v = ev.get(k)
        if v is None:
            continue
        if kind == "pct":
            out.append(f"{label} {float(v):.0%}")
        elif kind == "m3":
            out.append(f"{label} {float(v):.3f} m3")
        elif kind == "m":
            out.append(f"{label} {float(v):.3f} m")
        else:
            out.append(f"{label} {v}")
    return ", ".join(out)


def settled_note(o, settled):
    """The SETTLED-BOX addendum for a fact line (v2.4). An edge's evidence
    numbers were measured by the loop-back on the VOTED boxes; if an
    EARLIER case in this same run has since moved `o`'s box, the judge must
    be told the number it is reading is about the old box and what the box
    is NOW. Returns "" when the box has not moved — so an unaffected case's
    prompt is byte-identical to before and still hits the cache."""
    e = (settled or {}).get(o)
    if not e or e.get("source") == SETTLED_BASE:
        return ""
    lo, hi = e["lo"], e["hi"]
    return (f"\n    SETTLED SINCE: {o}'s box was moved by an EARLIER verdict "
            f"in this same run ({e['source']}). It is NOW x {lo[0]:.3f}.."
            f"{hi[0]:.3f}, y {lo[1]:.3f}..{hi[1]:.3f}, z {lo[2]:.3f}.."
            f"{hi[2]:.3f} — that is the box drawn on the panels. The numbers "
            "on this edge were measured on its PRE-verdict vote box.")


def edge_fact_line(nid, e, names, neighbor_ids, settled=None):
    """One fact line for one edge of graph['voted_edges'] that touches
    this node — the relation phrased from THIS node's side, with the
    edge's own evidence numbers, plus the J1 verdict when the edge is a
    judged SAME_CANDIDATE, plus (v2.4) the SETTLED-BOX addendum when an
    earlier verdict in this run has moved the other end's box."""
    t = e["type"]
    o = other_end(nid, e)
    a_is_me = e["a"] == nid
    oname = "architecture" if is_arch(o) else (names.get(o) or "?")
    who = f"{o} ({oname})"
    tag = " (SAME CLASS)" if node_class(o, names) and \
        node_class(o, names) == node_class(nid, names) else ""
    if o in neighbor_ids:
        tag += " [drawn GREEN on the panels]"
    ev = e.get("evidence") or {}

    if t == "IN":
        phrase = (f"this node's box is INSIDE {who}" if a_is_me
                  else f"{who} is INSIDE this node's box")
        bits = _ev_bits(ev, [("overlap_vol_m3", "overlap", "m3"),
                             ("frac_of_smaller", "= share of the smaller "
                              "box's volume:", "pct"),
                             ("vol_small_m3", "smaller box", "m3"),
                             ("vol_big_m3", "bigger box", "m3")])
    elif t == "INTERPENETRATES":
        phrase = f"this node's box INTERPENETRATES {who}"
        bits = _ev_bits(ev, [("overlap_vol_m3", "overlap", "m3"),
                             ("frac_of_smaller", "= share of the smaller "
                              "box:", "pct")])
    elif t == "ON":
        phrase = (f"this node RESTS ON {who}" if a_is_me
                  else f"{who} RESTS ON this node")
        bits = _ev_bits(ev, [("gap_m", "gap", "m"),
                             ("overlap_frac_of_a", "footprint overlap", "pct"),
                             ("supporter", "supporter", "raw")])
    elif t == "IN_WALL":
        phrase = f"this node's box sits IN the wall plane {who}"
        bits = _ev_bits(ev, [("wall_distance_m", "wall distance", "m"),
                             ("wall_axis", "axis", "raw")])
    elif t == "ATTACHED":
        phrase = f"this node is ATTACHED to {who}"
        bits = _ev_bits(ev, [("gap_m", "gap", "m"),
                             ("overlap_vol_m3", "overlap", "m3"),
                             ("frac_of_smaller", "= share of the smaller "
                              "box:", "pct")])
    elif t == "NEAR":
        phrase = f"this node is NEAR {who}"
        bits = _ev_bits(ev, [("relation_hint", "hint", "raw"),
                             ("gap_m", "gap", "m"),
                             ("distance_m", "distance", "m")])
    elif t == "SAME_CANDIDATE":
        phrase = (f"this node was flagged as POSSIBLY THE SAME OBJECT as "
                  f"{who}")
        bits = _ev_bits(ev, [("iou", "iou", "raw"),
                             ("containment", "containment", "pct"),
                             ("zone", "zone", "raw"),
                             ("center_height_diff_m", "center height diff",
                              "m")])
    else:
        phrase = f"{t} with {who}"
        bits = ", ".join(f"{k} {v}" for k, v in ev.items()
                         if isinstance(v, (int, float, str)))

    line = f"- {t}{tag}: {phrase}" + (f" — {bits}" if bits else "")
    v = e.get("verdict")
    if t == "SAME_CANDIDATE" and isinstance(v, dict) and v.get("verdict"):
        conf = v.get("confidence")
        conf = f", confidence {float(conf):.2f}" if isinstance(
            conf, (int, float)) else ""
        line += (f"\n    J1 ruled {v['verdict']}{conf}: "
                 f"\"{(v.get('reason') or '').strip()}\"")
    return line + settled_note(o, settled)


def fmt_box(b):
    s = [round(float(h) - float(l), 2) for l, h in zip(b["lo"], b["hi"])]
    return f"{s[0]}x{s[1]}x{s[2]}m"


# ---- the per-case CANDIDATE BOX LIST (v2.2) ------------------------------
# The ONE_BOX answer is a choice AMONG THE BOXES THAT EXIST FOR THIS NODE.
# Nothing is invented here: every candidate is a box already on record
# (the vote report via the cone-map stand-in, or the vote's own doubt),
# copied verbatim. A node with one candidate is offered one; a node with
# none is not asked the question at all.

def boxes_agree(a, b, tol=AGREE_TOL):
    return all(abs(float(a["lo"][i]) - float(b["lo"][i])) <= tol
               and abs(float(a["hi"][i]) - float(b["hi"][i])) <= tol
               for i in range(3))


def build_candidates(c):
    """[{key, box, colour, what}] for one case — the ONLY values the
    judge may answer "ship" with. `box` is None on the "either" key
    (it names an agreement between the two boxes above it, not a box)."""
    bx = c["cm"]["boxes"]
    out = []
    if c.get("exempt"):
        if bx.get("shipping"):
            out.append({
                "key": "current", "box": bx["shipping"], "colour": "ORANGE",
                "what": "this node's CURRENT box — the one that ships "
                        "today. It is the ORIGINAL pre-vote detection box "
                        "after the room-shell clip, NOT a measurement: this "
                        "node never voted, because flat wall/ceiling "
                        "objects skip the slice-and-vote vote. Shipping "
                        "it changes nothing."})
        if bx.get("rejected"):
            d = next((d for d in c["doubts"]
                      if d["kind"] == "rebox_rejected_smaller"), {})
            out.append({
                "key": "rebox_candidate", "box": bx["rejected"],
                "colour": "MAGENTA",
                "what": "the FACE-ON RE-BOX the vote measured in the "
                        f"panel and then THREW AWAY (detection score "
                        f"{float(d.get('score', 0.0)):.2f}, "
                        f"{d.get('claimed', '?')} claimed dots; it spans "
                        f"{fmt_ratios(d.get('extent_ratio'))} of the "
                        "current box's two in-plane extents, and a sanity "
                        "guard refused a shrink that large). It is the "
                        "ONLY measurement this node has ever had. Shipping "
                        "it ADOPTS that smaller measured box in place of "
                        "the current one."})
    else:
        if bx.get("vote2"):
            out.append({
                "key": "vote", "box": bx["vote2"], "colour": "ORANGE",
                "what": "WHERE IT CAME FROM: the ELECTED CLUSTER box "
                        "(boxes.vote2) — the points most vote cameras "
                        "agreed on. (HINT, NOT THE TEST: of the two, this "
                        "is usually the fuller box, because the cyan cut "
                        "can be occlusion-shaved down to a partial view. "
                        "Judge it by what you SEE, not by this hint.)"})
        if bx.get("pano"):
            out.append({
                "key": "pano", "box": bx["pano"], "colour": "CYAN",
                "what": "WHERE IT CAME FROM: the FOUNDING-MASK SHARE of "
                        "that cluster (boxes.pano) — the part this node's "
                        "own founding masks vouch for. (HINT, NOT THE "
                        "TEST: of the two, this is usually the tighter "
                        "box, because the orange vote box can absorb a "
                        "neighbour. Judge it by what you SEE, not by this "
                        "hint.)"})
    if len(out) == 2 and boxes_agree(out[0]["box"], out[1]["box"]):
        out.append({
            "key": "either", "box": None, "colour": None,
            "what": f"the two boxes above agree to within {AGREE_TOL} m on "
                    "every face — whichever ships, the geometry is the "
                    "same."})
    return out


def candidate_block(cands, indent="    "):
    """The candidate list as the prompt prints it: key — size — why."""
    lines = []
    for cd in cands:
        head = f'"{cd["key"]}"'
        if cd["box"]:
            head += (f' — {fmt_box(cd["box"])}, drawn {cd["colour"]} on the '
                     "panels")
        lines.append(f"{indent}{head} — {cd['what']}")
    return "\n".join(lines)


# ---- box projection (cameras from vote_cams — never re-derived here) ----

def box_corners(lo, hi):
    return np.array([[hi[0] if i & 4 else lo[0],
                      hi[1] if i & 2 else lo[1],
                      hi[2] if i & 1 else lo[2]] for i in range(8)],
                    dtype=np.float64)


BOX_EDGES = sorted({tuple(sorted((i, i ^ b)))
                    for i in range(8) for b in (1, 2, 4)})


def _seg(dr, p0, p1, color, width, dash):
    """Draw one screen segment; dash > 0 splits it into dash-px pieces."""
    for p in (p0, p1):
        if not all(np.isfinite(p)):
            return
    if max(abs(p0[0]), abs(p0[1]), abs(p1[0]), abs(p1[1])) > 1e5:
        return
    if not dash:
        dr.line([tuple(p0), tuple(p1)], fill=color, width=width)
        return
    d = np.array(p1) - np.array(p0)
    L = float(np.hypot(*d))
    if L < 1e-6:
        return
    n = max(1, int(L / dash))
    for k in range(0, n, 2):
        a = np.array(p0) + d * (k / n)
        b = np.array(p0) + d * (min(k + 1, n) / n)
        dr.line([tuple(a), tuple(b)], fill=color, width=width)


def draw_box_wire(dr, cam, lo, hi, color, width=3, dash=0):
    """12 wireframe edges of an axis-aligned box, near-plane clipped at
    NEAR_Z (an edge crossing the camera plane is cut, not dropped)."""
    P = box_corners(lo, hi)
    z = ((P - cam.pos) @ cam.R.T)[:, 2]
    for i, j in BOX_EDGES:
        p0, p1, z0, z1 = P[i], P[j], z[i], z[j]
        if z0 < NEAR_Z and z1 < NEAR_Z:
            continue
        if z0 < NEAR_Z:
            p0 = p0 + (NEAR_Z - z0) / (z1 - z0) * (p1 - p0)
        elif z1 < NEAR_Z:
            p1 = p1 + (NEAR_Z - z1) / (z0 - z1) * (p0 - p1)
        u, v, _ = cam.project(np.array([p0, p1]))
        _seg(dr, (float(u[0]), float(v[0])), (float(u[1]), float(v[1])),
             color, width, dash)


def project_corners(cam, box):
    """(u, v, z) of the 8 corners — the sanity print for the gate."""
    return cam.project(box_corners(box["lo"], box["hi"]))


def label_at_corner(dr, cam, lo, hi, text, color, size):
    """Stamp `text` beside a VISIBLE corner of the box (the highest
    on-screen corner in front of the camera). Silently draws nothing when
    no corner lands in frame — a label is never guessed off-screen."""
    w, h = size
    u, v, z = cam.project(box_corners(lo, hi))
    best = None
    for k in range(8):
        if not (z[k] > NEAR_Z and np.isfinite(u[k]) and np.isfinite(v[k])):
            continue
        if not (0 <= u[k] < w and 0 <= v[k] < h):
            continue
        if best is None or v[k] < v[best]:
            best = k
    if best is None:
        return False
    tw, th = 7 * len(text) + 6, 14
    x = min(max(float(u[best]) + 5, 2), max(2, w - tw - 2))
    y = min(max(float(v[best]) + 5, 2), max(2, h - th - 2))
    dr.rectangle([x - 3, y - 2, x + tw, y + th - 2], fill=(0, 0, 0))
    dr.text((x, y), text, fill=color)
    return True


# ---- camera resolution per panel ----------------------------------------

def cam_from_sidecar(sidecar):
    """The camera that MADE a card render, from the render's own votetgt
    sidecar (eye/aim/fov as handed to the renderer)."""
    v = json.loads(sidecar.read_text())
    v = v[0] if isinstance(v, list) else v
    return (make_cam(v["eye"], v["aim"], v["fov"], RES),
            f"votetgt sidecar {sidecar.name} (eye/aim/fov as rendered)")


# ---- stimuli -------------------------------------------------------------

CARD_CAPTION = {
    "card0": "card0 — view-tunnel card, +x side, object height",
    "card1": "card1 — view-tunnel card, -x side, object height",
    "card2": "card2 — view-tunnel card, +z side, object height",
    "card3": "card3 — view-tunnel card, -z side, object height",
}


def panel_caption(view):
    if view in CARD_CAPTION:
        return CARD_CAPTION[view]
    if view.startswith("eyecard"):
        return f"{view} — eye-height escalation card (tier 2)"
    if view.startswith("iso"):
        return f"{view} — isolation retry, slice alone on black (tier 3)"
    if view in ("top", "ctop"):
        return ("plan view — the render the vote ran its top detection on"
                if view == "top" else
                "plan view (clip-top) — camera above the clipped ceiling")
    return view


def perp_params(c, sd, notes):
    """(params dict, path) of the vote's FACE-ON render sidecar for a
    vote-exempt node — slicevote.render_gate wrote eye/aim/fov/res
    there. (None, path) plus a build note when it is missing or unusable:
    this pipeline never invents a camera for a picture it cannot place."""
    nid = c["id"]
    side = sd / "pool_retake" / "slices" / f"vote_{nid}_perp.params.json"
    if not side.exists():
        notes.append(f"{nid}: face-on render has no params sidecar "
                     f"({side.name}) — camera unknown (no camera is ever "
                     "guessed)")
        return None, side
    try:
        p = json.loads(side.read_text(encoding="utf-8"))
        [float(v) for v in p["eye"]], [float(v) for v in p["aim"]]
        float(p["fov"])
    except (ValueError, KeyError, TypeError) as e:               # noqa: BLE001
        notes.append(f"{nid}: params sidecar {side.name} unusable ({e})")
        return None, side
    return p, side


def perp_panels(c, sd, sheets_dir, notes):
    """The stimuli for a VOTE-EXEMPT node: (1) its one FACE-ON (perp)
    render of the SCENE, camera READ from that render's own params
    sidecar, and (2) the BOX-CONTENT render — only what is inside its own
    box. Either may be missing; a missing one is a build note, never a
    fabricated panel."""
    nid = c["id"]
    png = sd / "pool_retake" / "slices" / f"vote_{nid}_perp.png"
    p, side = perp_params(c, sd, notes)
    if not png.exists():
        notes.append(f"{nid}: vote-exempt, and no face-on render "
                     f"({png.name}) on disk — panel SKIPPED")
        panels = []
    elif p is None:
        notes.append(f"{nid}: face-on render {png.name} shipped NO panel — "
                     "its camera is not recoverable")
        panels = []
    else:
        cam = make_cam(p["eye"], p["aim"], float(p["fov"]),
                       int(p.get("res", RES)))
        plane = next((d.get("plane") for d in c["doubts"]
                      if d["kind"] in ("rebox_rejected_smaller",
                                       "rebox_truncated")), None)
        cap = ("perp — the FACE-ON view the vote re-boxed this exempt node "
               "from" + (f" (plane {plane})" if plane else ""))
        panels = [annotate(png, sheets_dir, f"{nid}_perp.png", cam,
                           c["cm"]["boxes"], None, cap,
                           f"perp render params sidecar {side.name} "
                           "(eye/aim/fov/res as rendered)", c["neighbors"])]
    panels += boxcontent_panels(c, sd, sheets_dir, notes, p)
    return panels


# ---- the BOX-CONTENT panel (v2.2) ----------------------------------------
# ONLY the gaussians inside this node's own box, seen face-on from the room
# side. The face-on SCENE render cannot settle "one fixture or two" — the
# architecture around the fixture is in the picture too; an isolated render
# of the box's own content can. The subset-ply write and the WSL render call
# are graph/split_cuts.py's, IMPORTED (one copy of that machinery), with the
# same params-sidecar staleness rule: reuse only on a hash match.

_SPLATS = {}          # ply path -> split_cuts.Splat (read once per process)
_SPLAT_LOCK = threading.Lock()   # v2.4: panels are now built INSIDE the
#                                  per-case worker threads, so two exempt
#                                  cases in one level can reach this cache
#                                  at the same time. The ply is hundreds of
#                                  MB — read it once, not once per thread.


def _split_cuts():
    import split_cuts                                          # noqa: E402
    return split_cuts


def _splat(ply):
    sc = _split_cuts()
    key = str(ply)
    with _SPLAT_LOCK:
        if key not in _SPLATS:
            _SPLATS[key] = sc.Splat(ply)
        return _SPLATS[key]


def boxcontent_region(box, axis, sign):
    """The node's box grown BOXC_MARGIN on its two IN-PLANE axes and
    opened BOXC_OPEN along the plane normal INTO the room (the +sign
    side, where the vote's own face-on camera stands)."""
    lo = [float(v) for v in box["lo"]]
    hi = [float(v) for v in box["hi"]]
    for i in range(3):
        if i != axis:
            lo[i] -= BOXC_MARGIN
            hi[i] += BOXC_MARGIN
    if sign > 0:
        hi[axis] += BOXC_OPEN
    else:
        lo[axis] -= BOXC_OPEN
    return {"lo": lo, "hi": hi}


def boxcontent_target(region, axis, sign, name, label):
    """Camera looking ALONG the plane normal from the room side, framed
    on the region's two in-plane extents."""
    lo, hi = region["lo"], region["hi"]
    ctr = [(lo[i] + hi[i]) / 2 for i in range(3)]
    inplane = max(hi[i] - lo[i] for i in range(3) if i != axis)
    dist = max(1.15 * inplane / 2 / math.tan(math.radians(BOXC_FOV) / 2),
               (hi[axis] - lo[axis]) / 2 + BOXC_STANDOFF)
    eye = list(ctr)
    eye[axis] = ctr[axis] + sign * dist
    return {"name": name, "label": label, "eye": eye, "aim": ctr,
            "fov": BOXC_FOV}


def boxcontent_render(scene, region, tgt, out_dir, notes, nid):
    """Render the region's gaussians alone. STALENESS GATE (split_cuts'
    rule): the png is reused ONLY when its params sidecar hash — camera,
    resolution, region, and the source ply's identity — still matches;
    otherwise the png is deleted so the WSL renderer (which skips by
    FILENAME) must regenerate it. Returns (png, provenance) or
    (None, why)."""
    sc = _split_cuts()
    ply_src = paths.ply(scene)
    if not ply_src.exists():
        return None, f"no splat on disk ({ply_src})"
    st = ply_src.stat()
    payload = {"eye": [round(float(v), 6) for v in tgt["eye"]],
               "aim": [round(float(v), 6) for v in tgt["aim"]],
               "fov": float(tgt["fov"]), "res": BOXC_RES,
               "lo": [round(v, 6) for v in region["lo"]],
               "hi": [round(v, 6) for v in region["hi"]],
               "ply": str(ply_src), "ply_bytes": st.st_size,
               "ply_mtime": int(st.st_mtime)}
    h = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]
    out_dir.mkdir(parents=True, exist_ok=True)
    png = out_dir / f"{tgt['name']}.png"
    side = out_dir / f"{tgt['name']}.params.json"
    old = None
    if side.exists():
        try:
            old = json.loads(side.read_text(encoding="utf-8"))
        except ValueError:
            old = None
    if png.exists() and old and old.get("hash") == h:
        return png, (f"box-content render REUSED — params sidecar "
                     f"{side.name} hash {h} unchanged")
    png.unlink(missing_ok=True)      # the WSL renderer skips existing files
    sub = out_dir / f"_{tgt['name']}.ply"
    tf = out_dir / f"_{tgt['name']}_target.json"
    try:
        n = _splat(ply_src).write_subset(region["lo"], region["hi"], sub)
        tf.write_text(json.dumps([tgt], indent=1), encoding="utf-8")
        py = "/root/miniconda3/envs/splatanalyzer/bin/python"
        scr = sc.to_wsl(HERE / "analyzer" / "render_targets_wsl.py")
        cmd = (f"wsl -d Ubuntu-24.04 -- bash -c \"cd /root/splat_analyzer && "
               f"{py} '{scr}' --targets '{sc.to_wsl(tf)}' "
               f"--ply '{sc.to_wsl(sub)}' --out '{sc.to_wsl(out_dir)}' "
               f"--res {BOXC_RES}\"")
        subprocess.run(cmd, check=True, timeout=900, shell=True)
    except Exception as e:                                     # noqa: BLE001
        notes.append(f"{nid}: box-content render FAILED "
                     f"({type(e).__name__}: {str(e)[:160]}) — panel omitted")
        return None, "render failed"
    finally:
        sub.unlink(missing_ok=True)
    if not png.exists():
        notes.append(f"{nid}: box-content renderer produced no {png.name} — "
                     "panel omitted")
        return None, "renderer wrote no png"
    side.write_text(json.dumps({"hash": h, "gaussians": n, **payload},
                               indent=1), encoding="utf-8")
    return png, (f"box-content render, {n:,} gaussian(s) inside the region; "
                 f"camera in its params sidecar {side.name}")


def boxcontent_panels(c, sd, sheets_dir, notes, p=None):
    """The exempt case's box-content panel, or [] plus a build note.

    The plane NORMAL is READ from the vote's own face-on camera (eye
    minus aim): that camera was built perpendicular to the plane, so its
    axis IS the normal and its side IS the room side. Nothing is
    estimated — if that camera is not axis-aligned to BOXC_AXIS_TOL, or
    the node has no shipping box, there is no panel."""
    nid = c["id"]
    box = (c["cm"]["boxes"] or {}).get("shipping")
    if box is None:
        notes.append(f"{nid}: no shipping box on record — box-content "
                     "panel SKIPPED")
        return []
    if p is None:
        p, _ = perp_params(c, sd, notes)
    if p is None:
        notes.append(f"{nid}: box-content panel SKIPPED — the plane normal "
                     "is read from the vote's face-on camera and that "
                     "camera is not on record")
        return []
    d = np.array(p["eye"], float) - np.array(p["aim"], float)
    axis = int(np.argmax(np.abs(d)))
    off = float(np.linalg.norm(np.delete(d, axis)))
    if off > BOXC_AXIS_TOL or abs(d[axis]) < 1e-6:
        notes.append(f"{nid}: the vote's face-on camera is not axis-aligned "
                     f"(off-axis {off:.4f} m) — the plane normal is not "
                     "recoverable, box-content panel SKIPPED")
        return []
    sign = 1.0 if d[axis] >= 0 else -1.0
    region = boxcontent_region(box, axis, sign)
    tgt = boxcontent_target(region, axis, sign, f"{nid}_boxcontent",
                            f"{c['id']} {c['name']} box content")
    out_dir = sd / "graph" / "multiplicity_boxcontent"
    png, prov = boxcontent_render(c["scene"], region, tgt, out_dir, notes,
                                  nid)
    if png is None:
        return []
    cam = make_cam(tgt["eye"], tgt["aim"], tgt["fov"], BOXC_RES)
    ax = "xyz"[axis]
    cap = ("box content — ONLY WHAT IS INSIDE THE BOX. Nothing else in the "
           "scene is drawn: these are the gaussians inside this node's own "
           f"box (grown {BOXC_MARGIN} m on its two in-plane axes and opened "
           f"{BOXC_OPEN} m along the {ax} plane-normal into the room, so a "
           "fixture that hangs off a flat box is not sliced off), seen "
           "face-on from the room side. Whatever you see here is what this "
           "one box contains — count the objects in it.")
    return [annotate(png, sheets_dir, f"{nid}_boxcontent.png", cam,
                     c["cm"]["boxes"], None, cap, prov, ())]


def build_panels(c, sd, sheets_dir, notes):
    """Write one annotated PNG per existing render of this node. Returns
    [{"file", "view", "caption", "cam_from", "overlay"}]."""
    if c.get("exempt"):
        return perp_panels(c, sd, sheets_dir, notes)
    nid = c["id"]
    sdir = sd / "pool_retake" / "slices"
    rdir = sd / "pool_retake"
    rec = {v["view"]: v for v in c["cm"]["views"]}
    aim = c["cm"]["aim"]
    boxes = c["cm"]["boxes"]
    panels = []

    # --- the slice's own cards (object height, eye height, isolation) ---
    order = ([f"card{k}" for k in range(4)]
             + [f"eyecard{k}" for k in range(4)]
             + [f"iso{k}" for k in range(4)])
    for view in order:
        png = sdir / f"vote_{nid}_{view}.png"
        if not png.exists():
            continue
        sidecar = sdir / f"votetgt_vote_{nid}_{view}.json"
        cam, prov = None, ""
        if sidecar.exists():
            cam, prov = cam_from_sidecar(sidecar)
            if view in rec:
                d = float(np.linalg.norm(
                    np.array(cam.pos) - np.array(rec[view]["eye"])))
                if d > EYE_TOL:
                    notes.append(f"{nid} {view}: sidecar eye differs from "
                                 f"the conemap record by {d:.4f} m")
        elif view in rec:
            cam = make_cam(rec[view]["eye"], aim, FOV_GOOD, RES)
            prov = "conemap views record (eye) + object aim + FOV_GOOD"
        else:
            notes.append(f"{nid} {view}: no camera record — panel shipped "
                         "WITHOUT boxes")
        panels.append(annotate(png, sheets_dir, f"{nid}_{view}.png", cam,
                               boxes, None, panel_caption(view), prov,
                               c["neighbors"]))

    # --- the plan render the vote detected on ---
    tv, tcam, prov = plan_cam(c, sd, notes)
    if tv is not None:
        png = rdir / f"{nid}_{tv}.png"
        notch = None
        for d in c["doubts"]:
            if d["kind"] == "large_empty_notch" and boxes.get("vote2"):
                notch = {"rect_m": d["rect_m"],
                         "y": [boxes["vote2"]["lo"][1],
                               boxes["vote2"]["hi"][1]]}
        panels.append(annotate(png, sheets_dir, f"{nid}_{tv}.png", tcam,
                               boxes, notch, panel_caption(tv), prov,
                               c["neighbors"]))
    return panels


def plan_cam(c, sd, notes):
    """Rebuild the plan camera with vote_cams.top_cam_for and VALIDATE
    it against the eye the vote recorded for this node. Returns
    (view_name, cam, provenance) or (None, None, why). The cull
    predicates are stand-ins: a candidate's PARAMETERS never depend on
    the cull, only its presence in the list does — and we then pick the
    candidate whose render exists AND whose eye matches the record, so a
    wrong pick cannot survive."""
    nid = c["id"]
    rdir = sd / "pool_retake"
    # drive the cull BOTH ways to enumerate both branches: pass=True
    # yields the in-room 'top' standpoint, pass=False forces the
    # clip-top 'ctop' fallback. Parameters are identical either way —
    # only which candidates EXIST depends on the cull, and the record
    # check below decides which one the vote actually used.
    cands = []
    for allow in (True, False):
        got, _c0 = top_cam_for(c["geo"], np.array(c["eye0"], float),
                               c["ceil_y"], WALL_PAD,
                               lambda e, ok=allow: ok, lambda e: 0, 1)
        for cand in got:
            if cand[0] not in [x[0] for x in cands]:
                cands.append(cand)
    rec = {v["view"]: v["eye"] for v in c["cm"]["views"]}
    # eyes the vote itself recorded for a plan standpoint: the top
    # voter's eye, and the "slice" row (= tcands[0]'s eye by construction)
    known = [rec[k] for k in ("top", "slice") if k in rec]
    tgt = {}
    ptf = rdir / "pool_targets.json"
    if ptf.exists():
        try:
            tgt = {t["name"]: t for t in json.loads(ptf.read_text())}
        except (ValueError, KeyError, TypeError):
            tgt = {}
    for name, eye, fov in cands:
        png = rdir / f"{nid}_{name}.png"
        if not png.exists():
            continue
        src = []
        ok = False
        for k in known:
            if float(np.linalg.norm(eye - np.array(k, float))) <= EYE_TOL:
                ok = True
        if ok:
            src.append("eye matches the vote's recorded plan standpoint")
        t = tgt.get(f"{nid}_{name}")
        if t is not None:
            de = float(np.linalg.norm(eye - np.array(t["eye"], float)))
            if de <= EYE_TOL and abs(fov - float(t["fov"])) <= 1e-6:
                ok = True
                src.append(f"eye+fov match the render sidecar "
                           f"pool_targets.json[{nid}_{name}]")
            else:
                notes.append(f"{nid} {name}: rebuilt camera disagrees with "
                             f"pool_targets.json (d_eye {de:.4f} m) — plan "
                             "overlay SKIPPED")
                return None, None, "render-sidecar mismatch"
        if not ok:
            continue
        return name, make_cam(eye, c["geo"]["center"], fov, RES), \
            "vote_cams.top_cam_for, validated (" + "; ".join(src) + ")"
    notes.append(f"{nid}: no plan render whose camera validates — plan "
                 "panel omitted")
    return None, None, "no validated plan camera"


def annotate(src_png, sheets_dir, out_name, cam, boxes, notch, caption,
             prov, neighbors=()):
    """Copy a render into the sheet dir with the boxes drawn on it.

    `neighbors` = the SAME-CLASS neighbour nodes' VOTED boxes (verbatim
    from scene_manifest_slicevote_preview.json), drawn GREEN and labelled
    with the neighbour id near a visible corner (v2.1). Only same-class
    neighbours are ever drawn — the caller does that filtering."""
    im = Image.open(src_png).convert("RGB")
    overlay = []
    if cam is not None:
        dr = ImageDraw.Draw(im)
        for nb in neighbors:
            draw_box_wire(dr, cam, nb["lo"], nb["hi"], COL_NEIGH, 2)
            label_at_corner(dr, cam, nb["lo"], nb["hi"], nb["id"],
                            COL_NEIGH, im.size)
        if neighbors:
            overlay.append("green same-class neighbour(s) "
                           + "/".join(nb["id"] for nb in neighbors))
        if boxes.get("vote2"):
            draw_box_wire(dr, cam, boxes["vote2"]["lo"],
                          boxes["vote2"]["hi"], COL_VOTE, 3)
            overlay.append("orange vote2")
        elif boxes.get("shipping"):
            # vote-EXEMPT node: there is no elected vote box, so ORANGE
            # is the box that actually ships (the one under question)
            draw_box_wire(dr, cam, boxes["shipping"]["lo"],
                          boxes["shipping"]["hi"], COL_VOTE, 3)
            overlay.append("orange current/shipping box")
        if boxes.get("rejected"):
            draw_box_wire(dr, cam, boxes["rejected"]["lo"],
                          boxes["rejected"]["hi"], COL_REJECT, 3)
            label_at_corner(dr, cam, boxes["rejected"]["lo"],
                            boxes["rejected"]["hi"], "face-on detection",
                            COL_REJECT, im.size)
            overlay.append("magenta rejected face-on candidate")
        if boxes.get("pano"):
            draw_box_wire(dr, cam, boxes["pano"]["lo"],
                          boxes["pano"]["hi"], COL_PANO, 3)
            overlay.append("cyan pano")
        if notch:
            x0, z0, x1, z1 = notch["rect_m"]
            y0, y1 = notch["y"]
            draw_box_wire(dr, cam, [x0, y0, z0], [x1, y1, z1],
                          COL_NOTCH, 3, dash=10)
            overlay.append("red dashed notch")
    im.save(sheets_dir / out_name)
    return {"file": out_name, "src": str(src_png), "caption": caption,
            "cam_from": prov, "overlay": ", ".join(overlay) or "NONE"}


# ---- prompt --------------------------------------------------------------

OPENINGS = {
    "large_empty_notch":
        "THE DOUBT THAT OPENED THIS CASE — LARGE EMPTY NOTCH. Inside this "
        "node's own plan footprint there is a {notch_m2:.2f} m2 contiguous "
        "EMPTY rectangle (drawn RED DASHED on the plan panel; world "
        "{rect_m}). Is that empty rectangle (a) a missing limb of ONE "
        "non-rectangular object, (b) another object's territory that this "
        "node's box has swallowed, or (c) nothing at all — just floor the "
        "box happens to span?",
    "pano_vs_cluster":
        "THE DOUBT THAT OPENED THIS CASE — PANO vs CLUSTER. The founding "
        "masks that created this node (its identity evidence from the "
        "original standpoint) vouch for only {ratio:.0%} of the elected "
        "mass — under half. Is this ONE object that the founding view saw "
        "only partly (occluded / clipped), or is the elected cluster a "
        "SHARED cluster covering this object plus something else?",
    "culled_clusters":
        "THE DOUBT THAT OPENED THIS CASE — CULLED CLUSTER. The election "
        "produced {n} disconnected elected blob(s) beyond the winning one, "
        "and anchoring DISCARDED them. Was the discarded blob part of THIS "
        "object (the box is shaved), or a different object / a second "
        "instance that happens to sit in the same slice?",
    "low_plan_fill":
        "THE DOUBT THAT OPENED THIS CASE — LOW PLAN FILL. The elected dots "
        "cover only {fill:.0%} of the box's own footprint. Is this one "
        "object with a non-rectangular footprint, or one box spanning "
        "several objects with empty floor between them?",
    "rebox_rejected_smaller":
        "THE DOUBT THAT OPENED THIS CASE — THE FACE-ON VIEW FOUND SOMETHING "
        "MUCH SMALLER THAN THIS BOX. This node is VOTE-EXEMPT ({status}): "
        "it was never sliced or voted on, so its box is still the one the "
        "original detection produced. To check that box, the vote rendered "
        "ONE view looking straight at plane {plane} — the panel below — and "
        "detected the object in it (score {score:.2f}, {claimed} claimed "
        "dots). What it found spans only {shrink} of this box's two in-plane "
        "extents: the MAGENTA wireframe. A sanity guard refused to shrink "
        "the box that far, so the ORANGE box is what ships TODAY — but you "
        "may overrule that: shipping the magenta candidate is one of your "
        "choices below. Look at what is actually inside the orange box, in "
        "the face-on view and in the box-content panel. Is it (a) ONE "
        "object the detector only caught part of, (b) ONE object plus empty "
        "space the box over-reaches — in which case the magenta box is the "
        "object and should ship — or (c) TWO OR MORE separate fixtures "
        "sharing this one box, of which the magenta one is a single "
        "instance?",
    "rebox_truncated":
        "THE DOUBT THAT OPENED THIS CASE — THE FACE-ON VIEW COULD NOT SEE "
        "THE WHOLE OBJECT, SO MOST OF THIS BOX IS STILL A GUESS. This node "
        "is VOTE-EXEMPT ({status}): it was never sliced or voted on, so "
        "the only measurement it has ever had is ONE view looking straight "
        "at plane {plane} — the panel below — in which the object was "
        "detected (score {score:.2f}, {claimed} claimed dots). But that "
        "detection's mask ran OFF THE EDGE OF THE FRAME on {edges}. Those "
        "sides therefore were NOT measured: the vote left them on the "
        "extents the ORIGINAL detection had already assumed. Only "
        "{n_measured} of the {n_sides} in-plane sides of the ORANGE box — "
        "the box that ships — rests on evidence from this view; the rest "
        "is prior. (There is no magenta wireframe on this case: the re-box "
        "was ACCEPTED, it simply had almost nothing to measure.) Look at "
        "what is actually inside the orange box in that view and decide "
        "what it contains. Is it (a) ONE object whose true extent really "
        "does run past the edge of this view, so the box is right and only "
        "the evidence is short, (b) MORE THAN ONE thing sharing this one "
        "box, the unmeasured sides having left it stretched across a "
        "neighbour, or (c) ONE object that is largely HIDDEN by another "
        "object standing in front of it, so what the view could measure is "
        "mostly the thing in front rather than this node?",
}
# priority: the most specific admitting doubt opens the case
TRIGGER_ORDER = ("rebox_rejected_smaller", "rebox_truncated",
                 "large_empty_notch", "pano_vs_cluster", "culled_clusters",
                 "low_plan_fill")

# ---- THE LEGEND IS PER NODE TYPE (v2.2 rule) ----------------------------
# Never describe a colour that will not appear on THIS case's panels. The
# voted legend is the vote/pano vocabulary; an exempt node has neither a
# vote nor a pano box (it never voted), so its legend must not mention
# them — that vocabulary is exactly what pushed obj_018 into UNCLEAR.

NEIGHBOUR_LEGEND = """  GREEN wireframe  = a SAME-CLASS NEIGHBOUR node's own voted box,
                     labelled with that neighbour's id. It is a DIFFERENT
                     node of the same class that the graph says touches
                     or overlaps this one — if the extent you are ruling
                     on already belongs to a green box, say so."""

VOTED_LEGEND = """Every panel is one of THIS object's own vote renders with 3D boxes
projected on it by the same camera that made the render:
  ORANGE wireframe = the VOTE box (boxes.vote2) — the elected cluster.
  CYAN wireframe   = the PANO box (boxes.pano) — the part of the elected
                     cluster this node's own founding masks vouch for.
                     (Absent when the vote produced no pano box.)
{neighbour}
  RED DASHED (plan panel only) = the large empty notch rectangle.
The cards are "view tunnels": the full scene is rendered minus the
occluders between the camera and the object, so context is intact and
what sits INSIDE the wireframes is what you are ruling on."""

EXEMPT_LEGEND = """The boxes are projected onto each panel by the same camera that made
that render:
  ORANGE wireframe = this node's CURRENT box — the box that ships today.
                     It is this node's ORIGINAL pre-vote detection box
                     after the room-shell clip. THIS NODE NEVER VOTED:
                     flat wall- and ceiling-mounted objects skip the
                     slice-and-vote vote entirely, so there is no elected
                     cluster here and no founding-mask share — the orange
                     box is a prior, not a measurement.{magenta}
{neighbour}
The face-on panel is a "view tunnel": the full scene rendered minus the
occluders between the camera and the object, so the object's surroundings
are intact and what sits INSIDE the wireframes is what you are ruling on.
The box-content panel, when present, is the opposite kind of picture:
NOTHING but the gaussians inside this node's own box, so it answers "how
many things are in this box" without the room around them arguing."""

EXEMPT_MAGENTA = """
  MAGENTA wireframe = the FACE-ON RE-BOX CANDIDATE the vote's guard
                     REJECTED for being far smaller than the current box
                     ({size}). It is the ONLY measurement this node has
                     ever had."""


def legend_for(c):
    """The legend block for THIS case — voted or exempt, and only the
    colours its own panels actually carry."""
    neigh = NEIGHBOUR_LEGEND if c["neighbors"] else ""
    if not c.get("exempt"):
        return VOTED_LEGEND.format(
            neighbour=neigh or
            "  (No same-class neighbour touches this node, so no green "
            "wireframe appears.)")
    rej = (c["cm"]["boxes"] or {}).get("rejected")
    return EXEMPT_LEGEND.format(
        magenta=EXEMPT_MAGENTA.format(size=fmt_box(rej)) if rej else "",
        neighbour=neigh or
        "  (No same-class neighbour touches this node, so no green "
        "wireframe appears.)")


TAXONOMY_TAIL = """- SPLIT — one box is NOT enough: this footprint must become >= 2
  sub-boxes. You do NOT cut the rectangles: CODE decomposes the occupied
  footprint into axis-aligned rectangles mechanically, each carrying the
  elected heights. You CLASSIFY, and you annotate the split two ways:

  (a) IDENTITY — what the sub-boxes are, as a whole:
      "one_structure" — ONE physical object that spans the sub-boxes (the
                        L read as one sectional, a corner desk, a
                        wrap-around counter). The parts are linked
                        PART_OF_STRUCTURE; they are not separate objects.
      "copies"        — the SAME product, placed k times inside this box
                        (the "6 matching chairs" family). Give
                        "count" = k, a positive integer.
      "distinct"      — DIFFERENT objects share this box.

  (b) OWNERS — "parts": [{"name": "<short name>", "owner": ...}], one
      entry per sub-box you see, with owner one of:
        "this_node"        — the part this node should keep,
        "existing:<id>"    — a part ALREADY covered by another node. Use
                             a node id from the RELATIONS block; when a
                             GREEN-drawn same-class neighbour is the
                             thing you are looking at, that is the id to
                             cite (e.g. "existing:obj_063").
        "missing_instance" — a real object no node covers yet (a work
                             order for the loop-back, NOT an edit you are
                             making).
      "parts" is REQUIRED when identity is "distinct"; it is welcome and
      optional on "one_structure" and "copies".

- NO_GOOD_BOX — EVERY candidate box is GROSSLY wrong: each one badly
  cuts the object, and/or mostly contains things that are not it. Give
  "reason" — say what is wrong with the boxes — and do NOT give "ship".
  This is NOT the same as UNCLEAR: UNCLEAR means the evidence does not
  settle the question, NO_GOOD_BOX means the evidence DOES settle it and
  the answer is "none of these boxes is usable". Use it only for GROSSLY
  wrong boxes, never for merely imperfect ones — remember the error
  tolerance above.

- UNCLEAR — the evidence does not settle it. The shipping default stands
  and the doubt stays open on the record as a work order. Use this rather
  than guessing.

TIEBREAK (design rule): when the parts read as the SAME product, PREFER
identity "copies" over "distinct". Copies is the cheaper claim (one
asset, k placements) and a later same-product judge verifies sameness;
"distinct" requires a VISIBLE identity difference, otherwise it is
unfalsifiable."""

ONE_BOX_HEAD = """OUTCOME — REPRESENTATION FIRST. Choose exactly ONE:

- ONE_BOX — ONE box represents this node. YOU MUST ALSO SAY WHICH BOX
  SHIPS, as "ship": "<key>". THIS IS A COMPARISON: look at the candidate
  boxes on the panels and pick the BETTER one. Better means, IN THIS
  ORDER:
    1. COMPLETE — it contains the WHOLE object. A box that CUTS THROUGH
       the object is worse: part of the object visibly continues outside
       the wireframe in a panel, or the box floats above the surface the
       object plainly rests on while the object clearly reaches down to
       that surface.
    2. TIGHT ENOUGH — it is not mostly empty space, and not mostly
       another object's territory.
  PERFECTION IS NOT REQUIRED, and there is real error tolerance: a box
  only has to be REASONABLE, not exact. Some slack around the object, or
  a face a few centimetres off, is FINE — that is not a fault and not a
  reason to reject a box. If BOTH candidates are reasonable, ship the one
  that is MORE COMPLETE without being loose.
  The keys below are THE BOXES THAT EXIST FOR THIS NODE — the complete
  list for this case, built from what the vote actually recorded. Each
  says WHERE ITS BOX CAME FROM; any bracketed HINT is only how that box
  usually goes wrong and is NOT the test. The test is the two criteria
  above, applied to what you SEE in the panels. Answer with exactly one
  of them:
{candidates}
  Valid "ship" values on this case: {keys}. Nothing else is accepted."""

ONE_BOX_HEAD_NONE = """OUTCOME — REPRESENTATION FIRST. Choose exactly ONE:

- ONE_BOX — ONE box represents this node. This case has NO alternative
  box on record (the vote recorded only the box that already ships), so
  omit "ship"."""


def taxonomy_for(cands):
    """The taxonomy block with the ONE_BOX bullet rewritten around THIS
    case's candidate boxes (v2.2 — the enum was replaced by a choice among
    the boxes that exist)."""
    head = ONE_BOX_HEAD.format(
        candidates=candidate_block(cands, "    "),
        keys=" | ".join(f'"{cd["key"]}"' for cd in cands)) if cands \
        else ONE_BOX_HEAD_NONE
    return head + "\n" + TAXONOMY_TAIL


PROMPT = """You are the MULTIPLICITY JUDGE (J8) in a 3D scene-understanding
pipeline. A vote stage repaired one detected object's 3D box by slicing
the splat, re-rendering it from several sides, detecting in each render
and electing the points most cameras agree on. The vote recorded a DOUBT
about this node and cannot settle it from geometry. You settle it.

CASE {nid} — "{name}"  (vote status {status}; escalation {tiers})

{opening}

THE PANELS (image files in this directory — open them; everything you
need is there, do NOT look for any other file):
{panel_list}
{legend}

CASE FACTS (meters; y is the height axis, y-DOWN — smaller y is higher):
{facts}

{taxonomy}

Reply with ONE JSON object only, no prose around it:
{{"outcome": "ONE_BOX" | "SPLIT" | "NO_GOOD_BOX" | "UNCLEAR",
  "ship": "<one key from this case's list above>",     // ONE_BOX only
  "identity": "one_structure" | "copies" | "distinct", // SPLIT only
  "count": <positive int>,                             // identity "copies" only
  "parts": [{{"name": "<short name>",
             "owner": "this_node" | "existing:<node_id>" |
                      "missing_instance"}}],            // required when
                                                       // identity is "distinct"
  "confidence": <0..1>,
  "reason": "<one or two sentences citing what you SEE in a named panel>"}}
                                                       // "reason" is REQUIRED
                                                       // on NO_GOOD_BOX
Omit the keys that do not apply to your answer."""


def fmt_rect(r):
    """large_empty_notch rect_m is [x0, z0, x1, z1] — spell the axes out
    so the judge cannot read it as an xyz pair."""
    return f"x {r[0]}..{r[2]} m, z {r[1]}..{r[3]} m"


def fmt_ratios(rs):
    """The perp re-box's per-axis extent ratios as percentages."""
    return "/".join(f"{float(r):.0%}" for r in (rs or [])) or "n/a"


def fmt_edges(es):
    """The image borders the face-on mask ran off, named as the judge
    sees them in the panel (left / right / top / bottom)."""
    return "/".join(str(e) for e in (es or [])) or "n/a"


def n_inplane_sides(d):
    """How many sides a face-on re-box could have measured, recovered
    from the doubt itself (sides left on priors + sides measured) rather
    than restated here — the recorder owns that constant."""
    return len(d.get("truncation_kept_sides") or []) \
        + int(d.get("n_measured_sides") or 0)


def case_opening(c):
    for kind in TRIGGER_ORDER:
        for d in c["doubts"]:
            k = d["kind"]
            if k == "arm_vs_cluster":
                k = "pano_vs_cluster"   # run-5 records carry the old name
            if k != kind:
                continue
            return OPENINGS[kind].format(
                notch_m2=d.get("notch_m2", 0.0),
                rect_m=fmt_rect(d["rect_m"]) if d.get("rect_m") else "n/a",
                ratio=d.get("ratio", 0.0),
                n=d.get("n", 0),
                fill=d.get("fill", 0.0),
                status=c["status"],
                plane=d.get("plane", "?"),
                score=float(d.get("score", 0.0)),
                claimed=d.get("claimed", 0),
                shrink=fmt_ratios(d.get("extent_ratio")),
                edges=fmt_edges(d.get("truncated_edges")),
                n_measured=d.get("n_measured_sides", "?"),
                n_sides=n_inplane_sides(d))
    return ("THE DOUBT THAT OPENED THIS CASE: "
            + "; ".join(d.get("text", d["kind"]) for d in c["doubts"]))


def case_facts(c):
    lines = []
    lines.append(("- current (shipping) box size: " if c.get("exempt")
                  else "- voted (shipping) box size: ") + str(c['voted_size']))
    lines.append(f"- original resolved box size: {c['original_size']}"
                 + ("  (the shipping box is this box after the room-shell "
                    "clip — the vote measured neither)" if c.get("exempt")
                    else ""))
    lines.append(f"- resolved cluster: {c['n_members']} member "
                 f"detections across views")
    bx = c["cm"]["boxes"]
    if bx.get("vote2"):
        lines.append(f'- ORANGE "vote" box (boxes.vote2): '
                     f"{fmt_box(bx['vote2'])}"
                     f"  lo {bx['vote2']['lo']} hi {bx['vote2']['hi']}")
    elif bx.get("shipping"):
        lines.append(f'- ORANGE "current" (shipping) box: '
                     f"{fmt_box(bx['shipping'])}  lo {bx['shipping']['lo']} "
                     f"hi {bx['shipping']['hi']}")
    if bx.get("rejected"):
        lines.append(f'- MAGENTA "rebox_candidate" box: '
                     f"{fmt_box(bx['rejected'])}  lo {bx['rejected']['lo']} "
                     f"hi {bx['rejected']['hi']}")
    if bx.get("pano"):
        lines.append(f'- CYAN "pano" box (boxes.pano): {fmt_box(bx["pano"])}'
                     f"  lo {bx['pano']['lo']} hi {bx['pano']['hi']}")
    elif not c.get("exempt"):
        lines.append("- CYAN pano box: none produced by the vote")
    lines.append(f"- slice provenance: {c['slice']}")
    for d in c["doubts"]:
        if d["kind"] in ("pano_vs_cluster", "arm_vs_cluster"):
            # old-name doubts (run-5 records) carry arm_box
            pb = d.get("pano_box") or d.get("arm_box")
            lines.append(
                f"- PANO vs CLUSTER: pano-filtered box is {d['ratio']:.0%} "
                f"of the vote-cluster volume (pano-filtered "
                f"{fmt_box(pb)} vs cluster "
                f"{fmt_box(d['cluster_box'])})")
        if d["kind"] == "culled_clusters":
            lines.append(f"- {d['n']} vote cluster(s) CULLED by anchoring "
                         "(a coherent dot cluster the election rejected — "
                         "possible second instance)")
        if d["kind"] == "slice_fallback":
            lines.append("- slice used the wedge fallback (no plan-view "
                         "detection) — geometry lower-confidence")
        if d["kind"] == "low_plan_fill":
            lines.append(f"- LOW PLAN FILL: elected dots cover "
                         f"{d['fill']:.0%} of the box footprint")
        if d["kind"] == "large_empty_notch":
            lines.append(f"- LARGE EMPTY NOTCH: {d['notch_m2']:.2f} m2 "
                         f"contiguous empty rectangle in the footprint "
                         f"(world {fmt_rect(d['rect_m'])}) — non-box "
                         "shape (L?)")
        if d["kind"] == "rebox_rejected_smaller":
            pb = d.get("proposed_box")
            sh = d.get("center_shift_m")
            lines.append(
                f"- VOTE-EXEMPT ({c['status']}) on plane {d.get('plane')}: "
                "this node skipped the slice/vote vote entirely — no cards, "
                "no plan detection, no elected cluster. Its observations "
                "are the panels listed above.")
            lines.append(
                f"- FACE-ON RE-BOX REJECTED (too small): the detection in "
                f"that view (score {float(d.get('score', 0.0)):.2f}, "
                f"{d.get('claimed')} claimed dots) spans "
                f"{fmt_ratios(d.get('extent_ratio'))} of the current box's "
                "two in-plane extents"
                + (f", its in-plane centre {sh} m from the box's centre"
                   if sh is not None else "")
                + (f"; MAGENTA proposed box {fmt_box(pb)}  lo {pb['lo']} "
                   f"hi {pb['hi']}" if pb else "")
                + ". The vote's guard: \""
                + str(d.get("rejected_because", "")).strip()
                + "\" — so the orange box is what ships today. That guard "
                "is mechanical, not a judgement: if the magenta box IS the "
                "object, ship \"rebox_candidate\".")
        if d["kind"] == "rebox_truncated":
            fb = d.get("final_box")
            kept = d.get("truncation_kept_sides") or []
            lines.append(
                f"- VOTE-EXEMPT ({c['status']}) on plane {d.get('plane')}: "
                "this node skipped the slice/vote vote entirely — no cards, "
                "no plan detection, no elected cluster. Its observations "
                "are the panels listed above.")
            lines.append(
                f"- FACE-ON RE-BOX MOSTLY UNMEASURED: the detection in that "
                f"view (score {float(d.get('score') or 0.0):.2f}, "
                f"{d.get('claimed')} claimed dots) ran off the frame on "
                f"{fmt_edges(d.get('truncated_edges'))}, so {len(kept)} of "
                f"the {n_inplane_sides(d)} in-plane sides kept the ORIGINAL "
                f"detection's prior extent and only "
                f"{d.get('n_measured_sides')} was measured from this view"
                + (f"; the ORANGE box that ships is {fmt_box(fb)}  lo "
                   f"{fb['lo']} hi {fb['hi']}" if fb else "")
                + ". A side on a prior is a guess, not an observation.")
    lines.append("")
    lines.append("RELATIONS — read VERBATIM from the scene graph's own "
                 "edges (re-derived on the VOTED boxes; this judge "
                 "computes no overlaps of its own):")
    lines += c["fact_lines"]
    return "\n".join(lines)


def edge_fact_lines(nid, edges, names, neighbor_ids, settled=None):
    """The relational fact block for one case. Same-class neighbours are
    listed FIRST and are NEVER truncated (the obj_063 rule); the rest are
    capped at FACT_CAP by relevance, with the count of what was cut said
    out loud so the judge knows the list is not the whole world. `settled`
    (v2.4) is the run's settled geometry map — a fact about a node whose
    box an earlier verdict has already moved says so, verbatim."""
    touching = edges_touching(nid, edges)
    if not touching:
        return ["- (this node has no edges in the voted-edge layer: it "
                "neither contains, sits in, touches nor duplicates any "
                "other node)"]
    mine = node_class(nid, names)
    same, rest = [], []
    for e in touching:
        o = other_end(nid, e)
        (same if (mine and node_class(o, names) == mine) else rest).append(e)
    rest.sort(key=lambda e: fact_relevance(nid, e), reverse=True)
    kept, cut = rest[:FACT_CAP], rest[FACT_CAP:]
    out = [edge_fact_line(nid, e, names, neighbor_ids, settled)
           for e in same + kept]
    if cut:
        out.append(f"- (+{len(cut)} further edge(s) of lower relevance not "
                   "listed: "
                   + ", ".join(f"{e['type']} {other_end(nid, e)}"
                               for e in cut) + ")")
    return out


def same_class_neighbors(nid, edges, names, settled, notes):
    """The SAME-CLASS nodes joined to this node by ANY voted edge, with
    their boxes taken from the run's SETTLED MAP (v2.4) — the vote's
    shipping box verbatim until an EARLIER verdict in this run has named a
    different one, in which case the settled box is what gets drawn GREEN.
    These are the nodes that get a green wireframe on every panel; only
    same-class neighbours are ever drawn (v2.1)."""
    mine = node_class(nid, names)
    out, seen = [], set()
    if not mine:
        return out
    for e in edges_touching(nid, edges):
        o = other_end(nid, e)
        if o in seen or node_class(o, names) != mine:
            continue
        seen.add(o)
        geo = settled.get(o)
        if geo is None:
            notes.append(f"{nid}: same-class neighbour {o} has no box in the "
                         "settled map (absent from the preview manifest) — "
                         "NOT drawn")
            continue
        out.append({"id": o, "name": names[o], "via": e["type"],
                    "lo": list(geo["lo"]), "hi": list(geo["hi"]),
                    "box_source": geo.get("source", SETTLED_BASE),
                    "settled": geo.get("source", SETTLED_BASE)
                    != SETTLED_BASE})
    return sorted(out, key=lambda n: n["id"])


# ---- the sheet -----------------------------------------------------------

SHEET_CSS = """
body{font-family:system-ui,sans-serif;margin:22px;background:#111;color:#eee}
h1{font-size:19px;margin:0 0 2px} h2{font-size:14px;margin:22px 0 6px;
color:#ffd27a}
.meta{font-size:12px;color:#bbb;margin:0 0 14px}
.legend span{display:inline-block;margin-right:14px;font-size:12px}
.sw{display:inline-block;width:22px;height:0;border-top:3px solid;
vertical-align:middle;margin-right:5px}
.grid{display:flex;flex-wrap:wrap;gap:10px}
figure{margin:0;flex:0 0 auto;width:390px}
figure img{width:390px;border:1px solid #444;background:#000}
figcaption{font-size:11px;color:#cfd8ff;margin-top:3px}
figcaption .prov{color:#8a94b8}
pre{background:#1b1b1b;border:1px solid #444;padding:12px;font-size:12px;
white-space:pre-wrap;line-height:1.35}
"""


SW_VOTED = """
<span><i class='sw' style='border-color:#ff9900'></i>"vote" box
(boxes.vote2) — the elected cluster</span>
<span><i class='sw' style='border-color:#00bcd4'></i>"pano" box
(boxes.pano)</span>
<span><i class='sw' style='border-color:#ff2828;border-top-style:dashed'
></i>large_empty_notch rectangle</span>"""

SW_EXEMPT = """
<span><i class='sw' style='border-color:#ff9900'></i>"current" box — this
node's original pre-vote box, shell-clipped (it never voted)</span>
<span><i class='sw' style='border-color:#ff00c8'></i>"rebox_candidate" —
the face-on re-box the vote REJECTED</span>"""

SW_NEIGH = """
<span><i class='sw' style='border-color:#00e65a'></i>same-class neighbour
node's voted box (labelled with its id)</span>"""


def build_sheet(c, sheets_dir):
    neigh_txt = ", ".join(
        f"{n['id']} ({n['name']}, via {n['via']}; box: {n.get('box_source', SETTLED_BASE)})"
        for n in c["neighbors"]) or (
        "none — this node has no same-class neighbour in the voted edges")
    # the sheet's legend follows the SAME per-node-type rule as the
    # prompt's: never a swatch for a colour this case's panels lack
    swatches = SW_EXEMPT if c.get("exempt") else SW_VOTED
    if c["neighbors"]:
        swatches += SW_NEIGH
    cand_txt = "<br>".join(
        f"<b>&quot;{cd['key']}&quot;</b>"
        + (f" — {fmt_box(cd['box'])}" if cd["box"] else "")
        + f" — {cd['what']}" for cd in c["candidates"]) or \
        "none — this case has no alternative box on record"
    figs = "".join(
        f"<figure><img src='{p['file']}' loading='lazy'>"
        f"<figcaption><b>{p['caption']}</b><br>"
        f"<span class='prov'>boxes: {p['overlay']} &middot; camera: "
        f"{p['cam_from']}</span></figcaption></figure>"
        for p in c["panels"])
    html = f"""<!doctype html><meta charset='utf-8'>
<title>J8 multiplicity — {c['id']} {c['name']}</title>
<style>{SHEET_CSS}</style>
<h1>J8 · MULTIPLICITY CASE — {c['id']} “{c['name']}”</h1>
<p class='meta'>vote status <b>{c['status']}</b> · escalation
{'→'.join(c['tiers']) or 'none'} · admitting doubts:
{', '.join(d['kind'] for d in c['doubts'])} · {len(c['panels'])}
panel(s)</p>
<p class='legend'>{swatches}</p>
<p class='meta'>same-class neighbours drawn: {neigh_txt}</p>
<h2>CANDIDATE BOXES — the complete "ship" vocabulary for THIS case</h2>
<p class='meta'>{cand_txt}</p>
<h2>STIMULI — this node's own vote renders, boxes projected by the
camera that made each render</h2>
<div class='grid'>{figs}</div>
<h2>THE PROMPT (verbatim — also written as {c['id']}_prompt.txt)</h2>
<pre>{c['prompt'].replace('&', '&amp;').replace('<', '&lt;')}</pre>
"""
    p = sheets_dir / f"{c['id']}.html"
    p.write_text(html, encoding="utf-8")
    return p.name


def build_stimuli(c, sd, sheets_dir, settled, edges, names, notes):
    """LAZY SHEET BUILD (v2.4). Everything a case shows the judge — its
    green neighbour boxes, its relational fact block, its annotated panels,
    its prompt and its HTML sheet — is built HERE, inside the per-case
    work, against the SETTLED MAP AS IT STANDS AT THIS MOMENT.

    This is the whole point of the dependency order: sheets used to be
    built for the entire docket up front, so a case could only ever see the
    vote's boxes, never a neighbour box an earlier verdict had already
    moved. A moved neighbour changes the prompt text AND the panel pixels,
    so the case cache key misses — that is CORRECT, not a bug: it is a
    different question than the one that was cached.

    `c` is mutated in place and returned; one case is only ever touched by
    one worker."""
    nid = c["id"]
    c["neighbors"] = same_class_neighbors(nid, edges, names, settled, notes)
    c["fact_lines"] = edge_fact_lines(
        nid, edges, names, {n["id"] for n in c["neighbors"]}, settled)
    c["panels"] = build_panels(c, sd, sheets_dir, notes)
    if not c["panels"]:
        print(f"[multiplicity] {nid}: NO stimulus images found — "
              "case ships UNCLEAR-by-no-stimulus", flush=True)
        c["no_stimulus"] = True
    panel_list = "\n".join(
        f"  {p['file']}  — {p['caption']}"
        + ("" if p["overlay"] != "NONE"
           else "   [no boxes drawn: camera not recoverable]")
        for p in c["panels"])
    c["prompt"] = PROMPT.format(
        nid=nid, name=c["name"], status=c["status"],
        tiers="→".join(c["tiers"]) or "none",
        opening=case_opening(c), panel_list=panel_list,
        legend=legend_for(c), facts=case_facts(c),
        taxonomy=taxonomy_for(c["candidates"]))
    (sheets_dir / f"{nid}_prompt.txt").write_text(c["prompt"],
                                                  encoding="utf-8")
    c["sheet"] = build_sheet(c, sheets_dir)
    c["neighbor_boxes_settled"] = [n["id"] for n in c["neighbors"]
                                   if n.get("settled")]
    print(f"[multiplicity] {nid:>8} {c['name']:<12} "
          f"{len(c['panels'])} panel(s) "
          f"[{', '.join(p['file'] for p in c['panels']) or 'none'}]"
          f" · ship keys "
          f"[{', '.join(cd['key'] for cd in c['candidates']) or 'none'}]"
          + (" · SETTLED neighbour box(es) "
             + "/".join(c["neighbor_boxes_settled"])
             if c["neighbor_boxes_settled"] else "")
          + f" -> {c['sheet']}", flush=True)
    return c


def build_index(cases, sheets_dir, scene, notes):
    rows = "".join(
        f"<tr><td><a href='{c['id']}.html'>{c['id']}</a></td>"
        f"<td>{c['name']}</td><td>{c['status']}</td>"
        f"<td>{', '.join(d['kind'] for d in c['doubts'])}</td>"
        f"<td>{len(c['panels'])}</td>"
        f"<td>{'yes' if any(p['caption'].startswith('plan') for p in c['panels']) else 'NO'}</td>"
        f"<td>{', '.join(cd['key'] for cd in c['candidates']) or '—'}</td>"
        f"<td>{', '.join(n['id'] for n in c['neighbors']) or '—'}</td>"
        f"</tr>" for c in cases)
    warn = ("<h2>build notes</h2><ul>"
            + "".join(f"<li>{n}</li>" for n in notes) + "</ul>") if notes \
        else "<p class='meta'>build notes: none — every panel got a "\
             "validated camera.</p>"
    html = f"""<!doctype html><meta charset='utf-8'>
<title>J8 multiplicity docket — {scene}</title>
<style>{SHEET_CSS}
table{{border-collapse:collapse;font-size:13px}}
td,th{{border:1px solid #444;padding:5px 9px;text-align:left}}
a{{color:#8ec7ff}}</style>
<h1>J8 · MULTIPLICITY DOCKET — {scene}</h1>
<p class='meta'>{len(cases)} case(s), AUTO doubts only (Rule #1).
Sheets-only build — zero model calls. USER GATE A1.</p>
<table><tr><th>case</th><th>name</th><th>vote status</th>
<th>admitting doubts</th><th>panels</th><th>plan overlay</th>
<th>candidate boxes ("ship" keys)</th>
<th>green same-class neighbours</th></tr>
{rows}</table>
{warn}
"""
    p = sheets_dir / "index.html"
    p.write_text(html, encoding="utf-8")
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--sheets-only", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--concurrency", type=int, default=CONCURRENCY)
    a = ap.parse_args()
    sd = paths.scene_dir(a.scene)
    g = json.loads((sd / "scene_graph.json").read_text(encoding="utf-8"))
    vote = g.get("vote") or {}
    if not vote:
        raise SystemExit("[multiplicity] no vote block — run "
                         "record_vote_doubts.py --apply first")
    nodes = g["resolved"]["nodes"]
    by_id = {n["id"]: n for n in nodes}
    # v2.1: relational facts come from the loop-back's voted-edge layer.
    # No layer -> no facts -> the judge would rule blind, so this is fatal.
    ce = g.get("voted_edges") or {}
    if not ce.get("edges"):
        raise SystemExit("[multiplicity] no graph['voted_edges'] — run "
                         "graph/rederive_voted_edges.py --apply (Phase B2 "
                         "loop-back) first; J8 v2.1 reads its relational "
                         "facts from that layer and computes none itself")
    edges = ce["edges"]
    names = {n["id"]: n["name"] for n in nodes}
    voted_boxes = {}
    prev = sd / "scene_manifest_slicevote_preview.json"
    voted_sizes = {}
    if prev.exists():
        for o in json.loads(prev.read_text())["objects"]:
            voted_boxes[o["id"]] = (o["aabb_min"], o["aabb_max"])
            voted_sizes[o["id"]] = [round(v, 2) for v in o["size"]]
    # v2.4 — the VOTE's own records, the only place a J8 ship key's box may
    # be resolved from (the same two sources materialize reads).
    report = {}
    rep_f = sd / "pool_retake" / "slicevote_report.json"
    if rep_f.exists():
        report = {r["id"]: (r.get("boxes") or {}) for r in json.loads(
            rep_f.read_text(encoding="utf-8"))["results"]}
    all_doubts = {i: (n.get("doubts") or [])
                  for i, n in (vote.get("nodes") or {}).items()}
    cm_f = sd / "pool_retake" / "conemap.json"
    if not cm_f.exists():
        raise SystemExit("[multiplicity] no pool_retake/conemap.json — run "
                         "slicevote.py first (the stimuli come from "
                         "its renders + view records)")
    cm_by_id = {o["id"]: o for o in json.loads(
        cm_f.read_text(encoding="utf-8"))["objects"]}
    shell = json.loads((sd / "room_shell.json").read_text())
    eye0 = json.loads((sd / "rig_sp0" / "pano_selfrender_meta.json")
                      .read_text())["eye_raw"]
    # docket: multiplicity-relevant AUTO doubts only (Rule #1).
    # Admission triggers (user 08-07): ownership gap, discarded
    # candidate, shape gap (plan-fill rule 3 / the notch); plus
    # (2026-08-08) two EVIDENCE gaps on a vote-EXEMPT node, both from
    # its single face-on view: the size gap (a confident detection at
    # under a third of the box's extents, thrown away by the vote's 3x
    # guard) and the measurement gap (the mask ran off the frame, so
    # most of the box's sides ship on priors — user ruling: the same
    # routing carries both). Without them the exempt paths raise no
    # doubt at all and never reach this judge.
    docket = {}
    for nid, cn in vote.get("nodes", {}).items():
        kinds = {d["kind"] for d in cn.get("doubts", [])}
        if kinds & {"pano_vs_cluster", "arm_vs_cluster",   # old name too
                    "culled_clusters", "low_plan_fill",
                    "large_empty_notch", "rebox_rejected_smaller",
                    "rebox_truncated"}:
            docket[nid] = cn
    if a.only:
        keep = set(a.only.split(","))
        docket = {k: v for k, v in docket.items() if k in keep}

    sheets_dir = sd / "graph" / "multiplicity_sheets"
    sheets_dir.mkdir(parents=True, exist_ok=True)
    # Wipe only what THIS run rebuilds (2026-08-08): an --only run used to
    # wipe every sheet and then write a sidecar holding just its own
    # case(s), silently destroying the rest of the docket — the same
    # clobber bug the vote had before merge-on-write. A full run still
    # clears everything (the v2.1 sheet form must not mix with older).
    _keep_ids = set(docket) if a.only else None
    for old in list(sheets_dir.glob("*.png")) + \
            list(sheets_dir.glob("*.html")) + \
            list(sheets_dir.glob("*_prompt.txt")):
        if _keep_ids is None or any(old.name.startswith(i)
                                    for i in _keep_ids):
            old.unlink()

    notes, cases = [], []
    for nid, cn in sorted(docket.items()):
        rn = by_id.get(nid)
        if rn is None:
            print(f"[multiplicity] {nid}: not in resolved — skipped")
            continue
        doubts = cn.get("doubts", [])
        # VOTE-EXEMPT node: the vote skipped it, so conemap.json has no
        # entry, there are no cards and no plan detection. Stand a minimal
        # cone-map record in for it — its CURRENT (shipping) box verbatim
        # from the preview manifest as the ORANGE box, plus the rejected
        # face-on candidate as the MAGENTA one — and let build_panels take
        # the perp branch. A node with neither a cone-map entry nor a
        # shipping box has no stimulus at all and is still skipped.
        cm, exempt = cm_by_id.get(nid), False
        if cm is None:
            box = voted_boxes.get(nid)
            if box is None:
                print(f"[multiplicity] {nid}: not in conemap.json — no vote "
                      "renders, case skipped")
                notes.append(f"{nid}: absent from conemap.json (no renders) "
                             "and from the preview manifest (no box)")
                continue
            cm = {"id": nid, "aim": rn["geometry"]["center"], "views": [],
                  "boxes": {"shipping": {"lo": list(box[0]),
                                         "hi": list(box[1])}}}
            for d in doubts:
                if d["kind"] == "rebox_rejected_smaller" and \
                        d.get("proposed_box"):
                    cm["boxes"]["rejected"] = d["proposed_box"]
            exempt = True
        c = {"id": nid, "name": rn["name"], "scene": a.scene,
             "status": cn.get("status", "?"),
             "tiers": cn.get("tiers", []),
             "slice": cn.get("slice") or ("none — vote exempt, never "
                                          "sliced" if exempt else "?"),
             "doubts": doubts,
             "geo": rn["geometry"],
             "eye0": eye0,
             "ceil_y": shell["ceiling_y_raw"],
             "cm": cm,
             "exempt": exempt,
             "voted_size": voted_sizes.get(nid, "n/a"),
             "original_size": [round(v, 2) for v in rn["geometry"]["size"]],
             "n_members": len(rn.get("members", []))}
        # v2.2: the ONE_BOX vocabulary is built PER CASE from the boxes
        # this node actually has — the prompt lists these keys verbatim and
        # the parser accepts nothing else. It depends only on THIS node's
        # own boxes, so it is safe to build up front (v2.4).
        c["candidates"] = build_candidates(c)
        cases.append(c)

    # ---- v2.4: THE SETTLED MAP + THE DEPENDENCY ORDER -------------------
    # Everything the cases read comes from this one map; it starts as the
    # vote's shipping boxes and moves only where a ONE_BOX verdict names
    # a different box. Sheets are built INSIDE the per-case work so a case
    # judged later sees the boxes earlier cases settled.
    settled = init_settled(voted_boxes)
    pre_judging = {i: {"lo": list(e["lo"]), "hi": list(e["hi"])}
                   for i, e in settled.items()}
    order = dependency_levels([c["id"] for c in cases], settled, notes)
    for k, lv in enumerate(order["levels"]):
        print(f"[multiplicity] LEVEL {k}: {', '.join(lv)}", flush=True)
    for dep in order["edges"]:
        print(f"[multiplicity]   dep: {dep['before']} BEFORE {dep['after']} "
              f"— {dep['why']}", flush=True)
    if not order["edges"]:
        print("[multiplicity]   dep: none — no docket pair is "
              f"containment-ish (>= {DEP_FRAC:.0%} of the smaller box)",
              flush=True)

    if a.sheets_only:
        for c in cases:
            build_stimuli(c, sd, sheets_dir, settled, edges, names, notes)
        idx = build_index(cases, sheets_dir, a.scene, notes)
        for n in notes:
            print(f"[multiplicity] NOTE: {n}", flush=True)
        print(f"[multiplicity] docket: {len(cases)} case(s) -> {sheets_dir}",
              flush=True)
        print(f"[multiplicity] index: {idx}", flush=True)
        print("[multiplicity] sheets-only — zero model calls (USER GATE A1 "
              "reviews the stimuli first); every sheet was built against "
              "the INITIAL settled map (no verdict has moved a box)",
              flush=True)
        return

    cache_f = sd / "graph" / "judge_multiplicity_cache.json"
    cache = json.loads(cache_f.read_text()) if cache_f.exists() else {}

    def case_key(c):
        h = hashlib.sha256()
        h.update(c["prompt"].encode())
        for p in c["panels"]:
            h.update((sheets_dir / p["file"]).read_bytes())
        return h.hexdigest()[:24]

    def run_case(c, snap):
        # v2.4 — the stimulus is built HERE, against `snap` (the settled
        # map as it stood when this level started), not up front.
        build_stimuli(c, sd, sheets_dir, snap, edges, names, notes)
        if c.get("no_stimulus"):
            return {**c, "verdict": {
                "outcome": "UNCLEAR", "confidence": 0.0,
                "reason": "no stimulus images on disk"}, "cached": False}
        k = case_key(c)
        if k in cache:
            return {**c, "verdict": cache[k], "cached": True}

        # ONE CASE MAY NEVER KILL THE RUN (2026-08-08): a slow claude.exe
        # hitting CALL_TIMEOUT_S raised TimeoutExpired straight out of
        # ex.map and took a whole 10-case docket down with it. Every call
        # failure is now a failed ATTEMPT — retried once, then recorded
        # as UNCLEAR with the reason, so the rest of the docket lands.
        keys = tuple(cd["key"] for cd in c["candidates"])

        def attempt(prompt, keys=keys):
            try:
                return parse_verdict(call_claude(prompt, sheets_dir,
                                                 a.model), keys), None
            except Exception as e:                    # noqa: BLE001
                return None, f"{type(e).__name__}: {str(e)[:160]}"

        v, err = attempt(c["prompt"])
        if v is None:
            v, err2 = attempt(c["prompt"] + "\n\nREPLY WITH THE JSON "
                              "OBJECT ONLY.")
            err = err2 or err
        if v is None:
            v = {"outcome": "UNCLEAR", "confidence": 0.0,
                 "reason": (f"judge call failed x2 — {err}" if err
                            else "malformed model reply x2")}
        v = {**v, "model": a.model, "date": date.today().isoformat()}
        cache[k] = v
        return {**c, "verdict": v, "cached": False}

    # LEVELS RUN IN SEQUENCE; a level's cases are independent and still run
    # concurrently. After each level its ONE_BOX verdicts are folded into
    # the settled map, so the next level's sheets are built against them.
    by_case_id = {c["id"]: c for c in cases}
    done, settle_log = {}, []
    for k, lv in enumerate(order["levels"]):
        snap = {i: dict(e) for i, e in settled.items()}   # frozen per level
        batch = [by_case_id[i] for i in lv]
        print(f"[multiplicity] === judging LEVEL {k} "
              f"({len(batch)} case(s), concurrency {a.concurrency}) ===",
              flush=True)
        with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
            got = list(ex.map(lambda c: run_case(c, snap), batch))
        for r in got:
            r["judge_level"] = k
            if r["id"] in order["arbitrary"]:
                r["judge_order_arbitrary"] = True
                r["judge_order_note"] = (
                    "a dependency cycle (mutual heavy overlap) put this "
                    "case in an ARBITRARY position in the judge order "
                    "(smaller-first/id fallback)")
            done[r["id"]] = r
            rec = settle_verdict(settled, r["id"], r["verdict"], report,
                                 all_doubts)
            rec["level"] = k
            settle_log.append(rec)
            if rec["changed"]:
                print(f"[multiplicity] SETTLED {r['id']}: {rec['why']} "
                      f"-> lo {[round(v, 3) for v in rec['now']['lo']]} hi "
                      f"{[round(v, 3) for v in rec['now']['hi']]}", flush=True)
    results = [done[c["id"]] for c in cases if c["id"] in done]
    cache_f.write_text(json.dumps(cache, indent=1))

    idx = build_index(results, sheets_dir, a.scene, notes)
    for n in notes:
        print(f"[multiplicity] NOTE: {n}", flush=True)
    print(f"[multiplicity] docket: {len(results)} case(s) -> {sheets_dir}",
          flush=True)
    print(f"[multiplicity] index: {idx}", flush=True)

    out_f = sd / "graph" / "multiplicity.json"
    fresh = [{k: v for k, v in c.items() if k not in ("prompt", "cm", "geo")}
             for c in results]
    # MERGE-ON-WRITE (2026-08-08, same rule as the vote): an --only run
    # REPAIRS its cases and keeps every other case on disk verbatim, so
    # debugging one node can never destroy the rest of the docket.
    if a.only and out_f.exists():
        try:
            prev = json.loads(out_f.read_text(encoding="utf-8"))
            done = {c["id"] for c in fresh}
            kept = [c for c in prev.get("cases", [])
                    if c.get("id") not in done]
            print(f"[multiplicity] merge: {len(fresh)} from this run + "
                  f"{len(kept)} kept verbatim")
            fresh = sorted(fresh + kept, key=lambda c: c.get("id", ""))
        except Exception as e:                        # noqa: BLE001
            print(f"[multiplicity] previous sidecar unreadable ({e}) — "
                  "writing THIS RUN'S cases only", flush=True)

    # ---- v2.4: the SETTLED MAP that ships ------------------------------
    # Rebuilt from the vote's shipping boxes + EVERY case on the record
    # (this run's and, on an --only run, the ones kept verbatim). A verdict
    # only ever touches its OWN node's entry, so the order they are applied
    # in cannot change the result — which is what lets an --only run write
    # a COMPLETE map instead of regressing the cases it did not judge.
    settled_out = init_settled(voted_boxes)
    for c in sorted(fresh, key=lambda c: c.get("id", "")):
        settle_verdict(settled_out, c["id"], c.get("verdict"), report,
                       all_doubts)
    conflicts = post_judge_conflicts(
        [c["id"] for c in fresh], pre_judging, settled_out,
        {c["id"]: c.get("verdict") for c in fresh})
    for k in conflicts:
        print(f"[multiplicity] POST-JUDGE CONFLICT {k['a']} / {k['b']}: "
              f"overlap {k['overlap_frac_of_smaller_before']:.0%} -> "
              f"{k['overlap_frac_of_smaller_after']:.0%} of the smaller box "
              "(RECORDED ONLY)", flush=True)
    if not conflicts:
        print("[multiplicity] post-judge consistency check: no docket pair "
              "overlaps MORE than it did before judging", flush=True)
    out_f.write_text(json.dumps({
        "scene": a.scene, "built": date.today().isoformat(),
        "source": "graph/judge_multiplicity.py (J8) — verdicts REFERENCE "
                  "nodes; materialize (Phase C) is the editor. Consumers: "
                  "materialize_layers.py + same-product judge (membership). "
                  "v2.2: a ONE_BOX verdict carries \"ship\" = one key from "
                  "that case's own `candidates` list (vote|pano|current|"
                  "rebox_candidate|either), NOT the retired ship_pano/"
                  "ship_vote/either enum. `candidates` is recorded per case "
                  "for audit; materialize resolves the named box from the "
                  "VOTE's own records, never from this file. v2.3: the "
                  "ONE_BOX ask is a COMPARISON with error tolerance (pick "
                  "the BETTER box — COMPLETE first, then TIGHT ENOUGH), and "
                  "a fourth outcome NO_GOOD_BOX carries a required "
                  "\"reason\" and NO \"ship\" key: every candidate was "
                  "grossly wrong. On NO_GOOD_BOX materialize keeps the "
                  "node's current shipping geometry unchanged (rule "
                  "j8_no_good_box) and raises it as an open question — it "
                  "is never a silent accept and never a dropped node. v2.4: "
                  "DEPENDENCY-ORDERED JUDGING (judge INNER before OUTER). "
                  "`settled_boxes` is the geometry every case was judged "
                  "AGAINST and the geometry downstream stages must use: the "
                  "vote's shipping boxes with every ONE_BOX verdict's named "
                  "box already applied (resolved from the VOTE's own "
                  "records, exactly as materialize resolves it). "
                  "`judge_order` records the levels the docket ran in. "
                  "`post_judge_conflicts` is a pure-arithmetic post-pass: "
                  "docket pairs that overlap MORE after judging than before "
                  "— RECORDED ONLY, never acted on.",
        "settled_boxes": settled_out,
        "settled_boxes_note": "{id: {lo, hi, source}} for EVERY id in the "
                              "vote preview manifest. `source` says whether "
                              "the box is the vote's shipping box or the "
                              "box a J8 verdict NAMED. SPLIT / UNCLEAR / "
                              "NO_GOOD_BOX never move an entry.",
        "judge_order": order,
        "settle_log": settle_log,
        "post_judge_conflicts": conflicts,
        "cases": fresh}, indent=1))
    for c in results:
        v = c["verdict"]
        extra = (f"ship={v['ship']}" if v.get("ship")
                 else v.get("identity") or "")
        if v["outcome"] == "NO_GOOD_BOX":
            extra = "ship=NONE (no usable candidate box)"
        if v.get("count"):
            extra += f"({v['count']})"
        if v.get("parts"):
            extra += " parts " + "/".join(p["owner"] for p in v["parts"])
        print(f"[multiplicity] {c['id']:>8} {c['name']:<14} "
              f"{v['outcome']:<11} {extra:<35} "
              f"conf {v.get('confidence', 0.0):.2f} "
              f"{'(cache)' if c.get('cached') else ''} — "
              f"{v.get('reason', '')[:80]}", flush=True)
    print(f"[multiplicity] -> {out_f}", flush=True)


if __name__ == "__main__":
    main()
