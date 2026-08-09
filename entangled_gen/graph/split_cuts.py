"""SPLIT CUTS (J8s) — the SPLIT-CUT JUDGE, a FIXED 3-ROUND CHAIN.
(PLAN_VOTEBOX_DOWNSTREAM "PHASE A3 — SPLIT CUTS (fixed 3-round chain)",
user-adopted 2026-08-07. The user ruled NO RECURSION MACHINERY: this is a
plain loop over a flat worklist, at most 3 rounds, and it STOPS.)

CONTRACT: GETS one SPLIT outcome from graph/multiplicity.json (J8 ruled
"one box is not enough") and the node's SETTLED box. DECIDES, one region at
a time, WHERE the box is cut and WHO owns each piece. ONE judge call =
ONE region = ONE decision:

SETTLED GEOMETRY (2026-08-08): every box this stage reads — the region, the
green/red/gray context boxes, the S-lines built from their edges, the
discard cover test — comes from graph/multiplicity.json's `settled_boxes`
when that map is present, and from the preview manifest per id when it is
not. See settled_voted() for why: a cut placed on a neighbour's edge went
stale the moment a J8 verdict moved that neighbour.

    {"decision": "no_cut", "action": "keep", "owner": ...}
  or{"decision": "no_cut", "action": "discard", "note": ...}
  or
    {"decision": "cut", "cut_line": <grid name>, "pieces": [
       {side, "action": "keep", owner, more_cut: bool, exclusions?}
     | {side, "action": "discard", note?}] x2}

PER-SIDE VERDICT (user ruling 08-07 late): each side of a cut is KEPT
(with an owner — this_node | existing:<id> — and a more_cut flag) or
DISCARDED (empty floor, junk, or territory of an object that already has
its own node). A discarded side is DROPPED from this case entirely: it is
recorded in the rounds list with its note but NEVER becomes a final piece
and never carries an owner or a more_cut. Keeping both sides is legal and
normal. The chain continues ONLY where a kept side has more_cut=true and
ends the moment nothing is flagged; the prompt biases the judge to DECIDE
NOW (discard-and-finish or keep-and-finish whenever this one cut settles
the side) and to flag more_cut only when the kept side visibly contains
multiple separable things THIS cut could not separate.

DISCARD CRITERION = REPRESENTATION (user-adopted 2026-08-07; replaces
the R-S2-40 same-class union-cover >= 0.60 rule AND the mostly-empty
exemption with ONE rule). The objective is to REPRESENT this object's
content with boxes — existing boxes already represent THEIR content. A
side may be DISCARDED iff its UNREPRESENTED-CONTENT RESIDUE is small:

    residue = (occupied cells of the side covered by NO eligible
               existing box) / max(1, occupied cells of the side)
            <= RESIDUE_MAX (0.25)

Occupied cells come from the vote's own plan_cells grid (>= OCC_K
dots). ELIGIBLE boxes = the SETTLED boxes (see settled_voted: J8's
`settled_boxes` per id, preview manifest as fallback) of nodes whose
box overlaps the side, ANY class — EXCLUDING RIDERS (the `a` of an ON
edge in graph["voted_edges"] whose `b` is the case node: pillows ON
the sofa — resting objects never represent the region beneath them).
Cover must be INDEPENDENTLY SUPPORTED — an ON edge (as `a`) to
something other than the case node; the voted-edge layer's missing
pillow ON edges is a recorded 4g2 open. Each
eligible box's plan footprint is GROWN by MARGIN (0.10 m) on all sides
before the cover test. Mostly-empty sides pass automatically (few
occupied cells => tiny residue — no separate exemption needed). On
failure the discard is DOWNGRADED to keep {owner: this_node, more_cut:
false} with doubt "discard_unverified — NN% of the side's content is
unrepresented". The residue + eligible box ids + excluded box ids WITH
reasons (rider | no_independent_support) are recorded on EVERY
discard, standing or not — never silent.

The judge answers in GRID VOCABULARY ONLY — lattice line names (letters =
constant-x lines, numbers = constant-z lines), special measured line names
(S1..), or "between X and Y". It never states a coordinate: SNAPPING IS
CODE'S JOB (see snap_line), so a cut can only land on a value the geometry
already contains or an explicitly-recorded midpoint fallback.

A mistake looks like: cutting one physical object in half, leaving two
objects inside one piece, or landing a cut a few cm off a real boundary
that the S-lines had measured exactly.

STIMULUS per region (promoted verbatim from the two user-passed scratchpad
prototypes, 08-07): the BOX-CONTENT top render — ONLY the gaussians inside
this region's box, camera straight above and outside the room, fov 50 —
with (a) the region box + same-class neighbours' voted boxes + overlapping
other-class voted boxes + RIDER boxes thin dashed gray ("resting — not
cover") projected on it by the SAME camera that made the render
(vote_cams.make_cam, the anti-drift module), (b) a DYNAMIC named
lattice (pitch chosen from {0.1,0.2,0.25,0.5,1.0} so the longer plan extent
carries <= 9 lines; chess chips at both ends + the world coordinate),
(c) MAGENTA S-LINES at measured boundaries inside the region (same-class
neighbour box edges + notch-rect edges from the vote doubts, deduped at
0.15 m) named S1.. with a legend strip appended below the render, and
(d) the object's existing J8 card renders as side context.

THE CHAIN (no recursion, no tree): a FLAT WORKLIST walked at most 3 ROUNDS.
  round 1 — the case box gets one judged cut.
  round 2 — every KEPT piece flagged more_cut gets one judged cut (fresh
            sub-render, grid + S-lines re-derived for that piece).
  round 3 — same again. THEN THE LOOP STOPS UNCONDITIONALLY.
The chain also ends the moment NOTHING is flagged more_cut.
GUARDS: a piece with either plan extent < 0.25 m is auto-done and is never
judged; at most 8 pieces per case (the chain stops early and the remaining
more_cut pieces are recorded); any piece still wanting a cut when the
chain stops ships UNCUT with doubt "split_incomplete"; an unparsable model
reply twice ships that region uncut.

Rounds are recorded as a FLAT LIST — [{round, region_box, stimulus,
verdict, snapped_cut, pieces}] — never a tree. Verdicts are a SIDECAR
(graph/split_cuts.json). This judge NEVER edits the graph, the vote or
multiplicity.json — materialize is the editor.

Run:  python graph/split_cuts.py --scene living_marble [--sheets-only]
      [--only obj_011,...] [--rounds 3] [--model sonnet]
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
from datetime import date
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import paths  # noqa: E402
from vote_cams import make_cam  # noqa: E402

MODEL = "sonnet"
CALL_TIMEOUT_S = 600   # s — raised from 240 (2026-08-08); a timeout is a
                       # failed attempt, never a crash (see judge_one_region)
RES = 1024              # stimulus render resolution
FOV = 50.0              # user-adopted top-view lens
PLY_PAD = 0.05          # m — subset ply is the region box grown by this
GRID_PAD = 0.30         # m — lattice extends this far past the region box
PITCHES = (0.1, 0.2, 0.25, 0.5, 1.0)
MAX_LINES = 9           # lattice lines over the longer plan extent
S_MARGIN = 0.10         # m — a measured boundary must be this far inside
S_DEDUPE = 0.15         # m — two measured boundaries this close are one
SNAP_R = 0.25           # m — a lattice pick snaps to an S-line within this
MIN_EXTENT = 0.25       # m — a piece thinner than this is auto-done
MAX_PIECES = 8          # per case
MAX_ROUNDS = 3          # THE HARD STOP (user ruling: no recursion)
RESIDUE_MAX = 0.25      # a discard stands only if at most this fraction
#                         of the side's OCCUPIED cells is covered by NO
#                         eligible box (REPRESENTATION objective, 08-07)
MARGIN = 0.10           # m — an eligible box's plan footprint is grown
#                         this much on all sides before the cover test
OCC_K = 2               # a plan cell is OCCUPIED with >= this many dots
#                         (record_vote_doubts.NOTCH_K, same rule)
NEAR_Z = 0.05
OWNERS = ("this_node",)     # + "existing:<id>"; kept sides only —
#                             nobody's-territory content is a DISCARD now
ACTIONS = ("keep", "discard")

COL_REGION = (255, 152, 0)     # orange — the region being ruled on
COL_SAME = (0, 230, 118)       # green  — same-class neighbour voted box
COL_OTHER = (239, 83, 80)      # red    — overlapping other-class voted box
COL_RIDER = (170, 170, 170)    # gray, thin dashed — resting, not cover
COL_GRID = (150, 195, 235)
COL_S = (255, 64, 255)


# ---- claude bridge (judge-chain pattern, judge_multiplicity) -------------

def claude_env():
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(k, None)   # stale-API-key hijack gotcha (project memory)
    return env


def call_claude(prompt, cwd, model):
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("[splitcuts] claude.exe not on PATH")
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


# ---- reply parsing -------------------------------------------------------

def _owner_ok(o):
    return o in OWNERS or (isinstance(o, str) and o.startswith("existing:")
                           and o[len("existing:"):].strip())


def _clean_exclusions(x):
    """[{"from": <line>, "to": <line>}] — anything else is dropped."""
    out = []
    if not isinstance(x, list):
        return out
    for e in x:
        if isinstance(e, dict) and isinstance(e.get("from"), str) \
                and isinstance(e.get("to"), str):
            out.append({"from": e["from"].strip(), "to": e["to"].strip()})
    return out


def parse_verdict(text):
    """ONE region = ONE decision. Returns the validated dict or None
    (caller retries once, then ships the region UNCUT)."""
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
    if not isinstance(v, dict):
        return None
    dec = v.get("decision")
    if dec not in ("no_cut", "cut"):
        # tolerate the bare-key form {"no_cut_needed": true, "owner": ...}
        if v.get("no_cut_needed") is True:
            dec = "no_cut"
        else:
            return None
    out = {"decision": dec}
    if dec == "no_cut":
        act = str(v.get("action", "keep")).strip().lower()
        if act not in ACTIONS:
            return None
        out["action"] = act
        if act == "keep":
            if not _owner_ok(v.get("owner")):
                return None
            out["owner"] = v["owner"]
        else:   # discard: no owner, no more_cut, optional note
            if v.get("owner") is not None or v.get("more_cut") is not None:
                return None
            note = v.get("note")
            out["note"] = note.strip() if isinstance(note, str) else ""
    else:
        line = v.get("cut_line")
        if not isinstance(line, str) or not line.strip():
            return None
        out["cut_line"] = line.strip()
        pieces = v.get("pieces")
        if not isinstance(pieces, list) or len(pieces) != 2:
            return None
        clean = []
        for p in pieces:
            if not isinstance(p, dict):
                return None
            side = str(p.get("side", "")).strip().lower()
            if side in ("low", "-", "minus", "first", "left", "lower"):
                side = "low"
            elif side in ("high", "+", "plus", "second", "right", "upper"):
                side = "high"
            elif side.startswith("-"):
                side = "low"
            elif side.startswith("+"):
                side = "high"
            else:
                return None
            act = str(p.get("action", "")).strip().lower()
            if act not in ACTIONS:
                return None
            c = {"side": side, "action": act,
                 "name": str(p.get("name", "")).strip()}
            if act == "keep":
                if not _owner_ok(p.get("owner")):
                    return None
                mc = p.get("more_cut", False)
                if not isinstance(mc, bool):
                    return None
                c["owner"] = p["owner"]
                c["more_cut"] = mc
                c["exclusions"] = _clean_exclusions(p.get("exclusions"))
            else:   # discard: owner/more_cut forbidden, optional note
                if p.get("owner") is not None \
                        or p.get("more_cut") is not None:
                    return None
                note = p.get("note")
                c["note"] = note.strip() if isinstance(note, str) else ""
            clean.append(c)
        if {c["side"] for c in clean} != {"low", "high"}:
            return None
        out["pieces"] = clean
    try:
        conf = float(v.get("confidence", 0.5))
    except (TypeError, ValueError):
        conf = 0.5
    out["confidence"] = round(min(1.0, max(0.0, conf)), 2)
    reason = v.get("reason")
    out["reason"] = reason.strip() if isinstance(reason, str) else ""
    return out


# ---- geometry ------------------------------------------------------------

def box_corners(lo, hi):
    return np.array([[hi[0] if i & 4 else lo[0],
                      hi[1] if i & 2 else lo[1],
                      hi[2] if i & 1 else lo[2]] for i in range(8)],
                    dtype=np.float64)


BOX_EDGES = sorted({tuple(sorted((i, i ^ b)))
                    for i in range(8) for b in (1, 2, 4)})


def overlap_vol(a_lo, a_hi, b_lo, b_hi):
    d = [max(0.0, min(a_hi[k], b_hi[k]) - max(a_lo[k], b_lo[k]))
         for k in range(3)]
    return d[0] * d[1] * d[2]


def plan_extents(box):
    return (box["hi"][0] - box["lo"][0], box["hi"][2] - box["lo"][2])


def plan_rect(box):
    return (box["lo"][0], box["lo"][2], box["hi"][0], box["hi"][2])


def grown_rect(lo, hi):
    """An eligible box's plan footprint, GROWN by MARGIN on all sides
    (the user's "allowed some margin") — (x0, z0, x1, z1)."""
    return (lo[0] - MARGIN, lo[2] - MARGIN, hi[0] + MARGIN, hi[2] + MARGIN)


# ---- THE SETTLED GEOMETRY (2026-08-08) -----------------------------------
# THE BUG THIS FIXES: this stage cut obj_011 at x=0.335 because that WAS
# obj_063's box edge — but J8 had (in the same docket) ruled obj_063
# ship=vote, moving that edge to x=0.636. The two nodes ended up
# overlapping by 0.30 m. J8 now judges INNER BEFORE OUTER and publishes
# `settled_boxes` in graph/multiplicity.json: the vote's shipping boxes
# with every ONE_BOX verdict's named box ALREADY APPLIED. When that map is
# present it is the authority for EVERY box this stage draws or measures —
# the case node's own region, the green/red/gray neighbour boxes, the
# S-lines derived from them, and the discard-eligibility cover test. The
# preview manifest stays the PER-ID fallback for any id the map does not
# carry (an older sidecar, or a node J8 never saw).

def settled_voted(mult, voted):
    """(boxes, note): the preview manifest's voted boxes with
    multiplicity.json's `settled_boxes` laid over them, per id. Same shape
    as `voted` ({id: (lo, hi)}) so nothing downstream has to change."""
    sb = (mult or {}).get("settled_boxes") or {}
    if not sb:
        return dict(voted), ("scene_manifest_slicevote_preview.json (the "
                              "voted SHIPPING box), verbatim — "
                              "graph/multiplicity.json carries no "
                              "`settled_boxes` map")
    out, moved, added = dict(voted), [], 0
    for oid, e in sb.items():
        lo, hi = e.get("lo"), e.get("hi")
        if lo is None or hi is None:
            continue
        old = out.get(oid)
        if old is None:
            added += 1
        elif any(abs(float(old[0][k]) - float(lo[k])) > 1e-6
                 or abs(float(old[1][k]) - float(hi[k])) > 1e-6
                 for k in range(3)):
            moved.append(oid)
        out[oid] = (list(lo), list(hi))
    return out, ("graph/multiplicity.json `settled_boxes` (the vote's "
                 "shipping boxes with every J8 ONE_BOX verdict's named box "
                 "applied), with scene_manifest_slicevote_preview.json as "
                 f"the per-id fallback — {len(sb)} settled entr(ies), "
                 f"{len(moved)} of them MOVED by a verdict"
                 + (": " + ", ".join(sorted(moved)) if moved else "")
                 + (f"; {added} not in the manifest" if added else ""))


def eligible_for_side(st, rect):
    """ELIGIBLE existing boxes for a side: the SETTLED boxes (J8's
    `settled_boxes`, preview manifest per-id fallback) of nodes whose
    grown plan footprint overlaps the side's
    plan rect, ANY class — EXCLUDING the case node itself and every
    node in st["excluded"] (user rule 08-07: existing boxes count as
    cover only if they represent INDEPENDENT objects — a node must be
    the `a` of an ON edge to a target OTHER than the case node; a
    RIDER rests ON the case, and a node with no ON edge at all rides
    whatever contains it). Returns (eligible, excluded_overlapping):
    the second list carries every overlapping-but-excluded node with
    its reason (rider | no_independent_support)."""
    x0, z0, x1, z1 = rect
    out, excl = [], []
    for oid, (lo, hi) in st["voted"].items():
        if oid == st["root"]["id"]:
            continue
        g = grown_rect(lo, hi)
        if not (g[0] < x1 and g[2] > x0 and g[1] < z1 and g[3] > z0):
            continue
        reason = st["excluded"].get(oid)
        if reason:
            excl.append({"id": oid, "reason": reason})
        else:
            out.append({"id": oid, "rect": g})
    return (sorted(out, key=lambda d: d["id"]),
            sorted(excl, key=lambda d: d["id"]))


def audit_discard(st, box):
    """THE REPRESENTATION CHECK on a discard verdict (user-adopted
    2026-08-07; replaces the R-S2-40 union-cover rule + the mostly-empty
    exemption). A discard STANDS iff the side's UNREPRESENTED-CONTENT
    RESIDUE is small: residue = occupied cells (>= OCC_K dots, the
    vote's own plan_cells grid) whose center lies inside NO eligible
    box's grown footprint, over max(1, occupied cells), <= RESIDUE_MAX.
    Mostly-empty sides pass automatically (few occupied cells => tiny
    residue). Otherwise the discard is DOWNGRADED to keep {owner:
    this_node, more_cut: false}. Returns (stands, audit_note,
    doubt_or_None); the audit note (residue + eligible box ids +
    excluded box ids WITH the exclusion reason, rider |
    no_independent_support) is recorded on EVERY discard — never
    silent."""
    rect = plan_rect(box)
    elig, excl = eligible_for_side(st, rect)
    audit = {"kind": "discard_residue_check",
             "residue_max": RESIDUE_MAX, "margin_m": MARGIN,
             "eligible_boxes": [e["id"] for e in elig],
             "excluded_boxes": excl}
    pc = st.get("plan_cells")
    n_cells, occ_pts = 0, []
    if pc:
        cm = pc["cell_m"]
        counts = {(ix, iz): c for ix, iz, c in pc["counts"]}
        x0, z0, x1, z1 = rect
        for ix in range(pc["nx"]):
            cx = pc["lo_x"] + (ix + 0.5) * cm
            if not (x0 <= cx <= x1):
                continue
            for iz in range(pc["nz"]):
                cz = pc["lo_z"] + (iz + 0.5) * cm
                if not (z0 <= cz <= z1):
                    continue
                n_cells += 1
                if counts.get((ix, iz), 0) >= OCC_K:
                    occ_pts.append((cx, cz))
    audit["side_cells"] = n_cells
    audit["occupied_cells"] = len(occ_pts)
    if not pc or n_cells == 0:
        # the grid does not reach this side: the residue is unmeasurable
        # — conservative, the discard does NOT stand (recorded as such)
        audit["residue"] = None
        audit["uncovered_cells"] = None
        audit["stands"] = False
        audit["why"] = ("the vote's plan_cells grid does not reach this "
                        "side - residue unmeasurable - DOWNGRADED to "
                        "keep {this_node}")
        return False, audit, ("discard_unverified - the side's content "
                              "could not be measured (no occupancy grid)")
    unc = sum(1 for (cx, cz) in occ_pts
              if not any(e["rect"][0] <= cx <= e["rect"][2]
                         and e["rect"][1] <= cz <= e["rect"][3]
                         for e in elig))
    residue = unc / max(1, len(occ_pts))
    audit["uncovered_cells"] = unc
    audit["residue"] = round(residue, 3)
    if residue <= RESIDUE_MAX:
        audit["stands"] = True
        audit["why"] = (f"only {residue:.0%} of the side's occupied "
                        f"content is unrepresented (<= {RESIDUE_MAX:.0%})"
                        " - the discard stands")
        return True, audit, None
    doubt = (f"discard_unverified - {residue:.0%} of the side's content "
             "is unrepresented")
    audit["stands"] = False
    audit["why"] = (f"{residue:.0%} of the side's occupied content is "
                    f"covered by NO eligible box (> {RESIDUE_MAX:.0%}) - "
                    "DOWNGRADED to keep {this_node}")
    return False, audit, doubt


def _dash_segment(dr, p0, p1, color, width, dash):
    """PIL has no dashed lines: walk the 2D segment in on/off steps."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    if L < 1e-6:
        return
    on, off = dash
    t = 0.0
    while t < L:
        t2 = min(L, t + on)
        dr.line([(x0 + (x1 - x0) * t / L, y0 + (y1 - y0) * t / L),
                 (x0 + (x1 - x0) * t2 / L, y0 + (y1 - y0) * t2 / L)],
                fill=color, width=width)
        t = t2 + off


def draw_box_wire(dr, cam, lo, hi, color, width=3, dash=None):
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
        if not (np.isfinite([u, v]).all()
                and max(abs(u).max(), abs(v).max()) < 1e5):
            continue
        if dash is None:
            dr.line([(u[0], v[0]), (u[1], v[1])], fill=color, width=width)
        else:
            _dash_segment(dr, (u[0], v[0]), (u[1], v[1]), color, width,
                          dash)


# ---- the grid + the measured lines --------------------------------------

def build_grid(box, specials_raw):
    """The stimulus's own vocabulary for ONE region: the dynamic lattice
    (letters = constant-x, numbers = constant-z) and the measured S-lines
    that fall inside this region. Returns a dict the annotator draws and
    the snapper reads — the SAME object, so a name the judge can see is
    always a name the code can resolve."""
    lo, hi = np.array(box["lo"], float), np.array(box["hi"], float)
    x0, x1 = lo[0] - GRID_PAD, hi[0] + GRID_PAD
    z0, z1 = lo[2] - GRID_PAD, hi[2] + GRID_PAD
    span = max(x1 - x0, z1 - z0)
    pitch = next((p for p in PITCHES if span / p <= MAX_LINES), PITCHES[-1])
    xs = [float(v) for v in np.arange(math.ceil(x0 / pitch) * pitch, x1,
                                      pitch)]
    zs = [float(v) for v in np.arange(math.ceil(z0 / pitch) * pitch, z1,
                                      pitch)]
    lines = {}
    for i, gx in enumerate(xs):
        lines[chr(ord("A") + i)] = {"axis": "x", "value": gx,
                                    "kind": "lattice"}
    for j, gz in enumerate(zs):
        lines[str(j + 1)] = {"axis": "z", "value": gz, "kind": "lattice"}
    # measured boundaries: strictly inside the region, deduped
    ded = []
    for ax, v, src in specials_raw:
        k = 0 if ax == "x" else 2
        if not (lo[k] + S_MARGIN < v < hi[k] - S_MARGIN):
            continue
        if any(a2 == ax and abs(v2 - v) < S_DEDUPE for a2, v2, _ in ded):
            continue
        ded.append((ax, v, src))
    specials = []
    for k, (ax, v, src) in enumerate(ded):
        name = f"S{k + 1}"
        lines[name] = {"axis": ax, "value": float(v), "kind": "measured",
                       "source": src}
        specials.append(name)
    return {"pitch": pitch, "x_names": [chr(ord("A") + i)
                                        for i in range(len(xs))],
            "z_names": [str(j + 1) for j in range(len(zs))],
            "s_names": specials, "lines": lines,
            "extent": [x0, x1, z0, z1]}


def specials_for(box, neighbors, notches):
    """Candidate measured boundaries for a region: same-class neighbour
    voted-box edges + vote notch-rect edges. Filtering/dedupe/naming is
    build_grid's job."""
    out = []
    for nb in neighbors:
        for v in (nb["lo"][0], nb["hi"][0]):
            out.append(("x", float(v), f"{nb['id']} box edge"))
        for v in (nb["lo"][2], nb["hi"][2]):
            out.append(("z", float(v), f"{nb['id']} box edge"))
    for r in notches:
        nx0, nz0, nx1, nz1 = r
        out.append(("x", float(nx0), "notch edge"))
        out.append(("x", float(nx1), "notch edge"))
        out.append(("z", float(nz0), "notch edge"))
        out.append(("z", float(nz1), "notch edge"))
    return out


# ---- snapping (CODE, never the judge) ------------------------------------

def snap_line(name, grid):
    """Resolve a grid-vocabulary line NAME to (axis, value, provenance).

    - an S-line pick takes its measured coordinate verbatim;
    - a lattice pick takes that line's value, then SNAPS to the nearest
      measured boundary within SNAP_R if one exists on the same axis;
    - "between X and Y" takes an S-line lying between them when there is
      one, else the midpoint (recorded as midpoint_fallback).
    Returns None when the name is not in this region's vocabulary."""
    lines = grid["lines"]
    raw = (name or "").strip()
    m = re.search(r"between\s+([A-Za-z0-9]+)\s*(?:and|,|-|/)\s*"
                  r"([A-Za-z0-9]+)", raw, re.I)
    if m:
        a, b = _norm(m.group(1), lines), _norm(m.group(2), lines)
        if a is None or b is None or lines[a]["axis"] != lines[b]["axis"]:
            return None
        ax = lines[a]["axis"]
        va, vb = lines[a]["value"], lines[b]["value"]
        lov, hiv = min(va, vb), max(va, vb)
        best = None
        for nm in grid["s_names"]:
            L = lines[nm]
            if L["axis"] == ax and lov < L["value"] < hiv:
                d = abs(L["value"] - (lov + hiv) / 2)
                if best is None or d < best[0]:
                    best = (d, nm, L)
        if best is not None:
            _, nm, L = best
            return (ax, L["value"],
                    {"asked": raw, "resolved": f"{nm} ({L['source']})",
                     "rule": "between -> S-line inside the span",
                     "measured": True})
        return (ax, (lov + hiv) / 2,
                {"asked": raw, "resolved": f"midpoint of {a} and {b}",
                 "rule": "between -> midpoint_fallback (no S-line inside)",
                 "measured": False, "midpoint_fallback": True})
    nm = _norm(raw, lines)
    if nm is None:
        return None
    L = lines[nm]
    if L["kind"] == "measured":
        return (L["axis"], L["value"],
                {"asked": raw, "resolved": f"{nm} ({L['source']})",
                 "rule": "S-line -> measured coordinate verbatim",
                 "measured": True})
    best = None
    for s in grid["s_names"]:
        S = lines[s]
        if S["axis"] != L["axis"]:
            continue
        d = abs(S["value"] - L["value"])
        if d <= SNAP_R and (best is None or d < best[0]):
            best = (d, s, S)
    if best is not None:
        d, s, S = best
        return (L["axis"], S["value"],
                {"asked": raw,
                 "resolved": f"{nm} ({L['axis']}={L['value']:.3f}) snapped "
                             f"to {s} ({S['source']}, {S['axis']}="
                             f"{S['value']:.3f})",
                 "rule": f"lattice -> nearest measured boundary within "
                         f"{SNAP_R} m (d={d:.3f} m)",
                 "measured": True, "snap_d_m": round(d, 4)})
    return (L["axis"], L["value"],
            {"asked": raw, "resolved": f"{nm} ({L['axis']}={L['value']:.3f})",
             "rule": "lattice -> line value (no measured boundary within "
                     f"{SNAP_R} m)", "measured": False})


def _norm(tok, lines):
    t = (tok or "").strip()
    for cand in (t, t.upper(), t.lstrip("0") or t):
        if cand in lines:
            return cand
    return None


# ---- the stimulus render -------------------------------------------------

class Splat:
    """The raw ply rows, read once, subset-written per region (the vote's
    own machinery: every gaussian attribute survives the subset)."""

    def __init__(self, ply):
        f = open(ply, "rb")
        header = [f.readline(), f.readline()]
        names, n = [], None
        while True:
            line = f.readline()
            header.append(line)
            ls = line.strip()
            if ls.startswith(b"element vertex"):
                n = int(ls.split()[-1])
            elif ls.startswith(b"property"):
                names.append(ls.split()[2].decode())
            elif ls == b"end_header":
                break
        rows = np.fromfile(f, dtype="<f4",
                           count=n * len(names)).reshape(n, len(names))
        f.close()
        col = {nm: i for i, nm in enumerate(names)}
        keep = 1 / (1 + np.exp(-rows[:, col["opacity"]])) > 0.3
        self.header, self.rows = header, rows[keep]
        self.xyz = self.rows[:, [col["x"], col["y"], col["z"]]].astype(
            np.float32)
        print(f"[splitcuts] ply: {len(self.xyz):,} gaussians after the "
              "opacity filter", flush=True)

    def write_subset(self, lo, hi, out_path):
        m = np.all((self.xyz >= np.array(lo) - PLY_PAD)
                   & (self.xyz <= np.array(hi) + PLY_PAD), axis=1)
        sub = self.rows[m]
        with open(out_path, "wb") as f:
            for line in self.header:
                if line.strip().startswith(b"element vertex"):
                    f.write(f"element vertex {len(sub)}\n".encode())
                else:
                    f.write(line)
            sub.astype("<f4").tofile(f)
        return int(m.sum())


def to_wsl(p):
    p = str(Path(p).resolve())
    return "/mnt/" + p[0].lower() + p[2:].replace("\\", "/")


def top_target(box, name, label):
    """Camera straight above the region, OUTSIDE the room (y-down: raising
    the camera DECREASES y), framed on the region's longer plan extent."""
    lo, hi = np.array(box["lo"], float), np.array(box["hi"], float)
    ctr = (lo + hi) / 2
    dx, dz = hi[0] - lo[0], hi[2] - lo[2]
    dist = max(2.0, 1.15 * max(dx, dz) / 2
               / math.tan(math.radians(FOV) / 2))
    eye = [float(ctr[0]), float(lo[1] - dist), float(ctr[2])]
    return {"name": name, "label": label, "eye": eye,
            "aim": [float(v) for v in ctr], "fov": FOV}


def render_region(splat, box, out_dir, name, label):
    """Box-content top render: ONLY the gaussians inside this region."""
    png = out_dir / f"{name}.png"
    ply = out_dir / f"_{name}.ply"
    tgt = out_dir / f"_{name}_target.json"
    n = splat.write_subset(box["lo"], box["hi"], ply)
    t = top_target(box, name, label)
    tgt.write_text(json.dumps([t], indent=1), encoding="utf-8")
    png.unlink(missing_ok=True)      # the renderer skips existing files
    py = "/root/miniconda3/envs/splatanalyzer/bin/python"
    scr = to_wsl(HERE / "analyzer" / "render_targets_wsl.py")
    cmd = (f"wsl -d Ubuntu-24.04 -- bash -c \"cd /root/splat_analyzer && "
           f"{py} '{scr}' --targets '{to_wsl(tgt)}' --ply '{to_wsl(ply)}' "
           f"--out '{to_wsl(out_dir)}' --res {RES}\"")
    subprocess.run(cmd, check=True, timeout=900, shell=True)
    ply.unlink(missing_ok=True)
    return png, t, n


def _font(size, bold=False):
    try:
        return ImageFont.truetype("arialbd.ttf" if bold else "arial.ttf",
                                  size)
    except OSError:
        return ImageFont.load_default()


def annotate(png, out_png, box, grid, cam, neighbors, others, riders):
    """Projected boxes + the named lattice + the magenta S-lines + the
    legend strip. Drawn with the SAME camera that made the render.
    NEVER-COVER boxes (riders resting ON the case node + nodes with no
    independent support) draw thin dashed gray — the judge must SEE
    which boxes never count as cover."""
    img = Image.open(png).convert("RGB")
    dr = ImageDraw.Draw(img)
    font, gfont, cfont = _font(26), _font(17), _font(26, True)

    def labelled(lo, hi, color, text, width=4, dash=None):
        draw_box_wire(dr, cam, lo, hi, color, width, dash)
        u, v, z = cam.project(box_corners(lo, hi))
        vis = [(u[k], v[k]) for k in range(8)
               if z[k] > NEAR_Z and 0 <= u[k] < img.width
               and 0 <= v[k] < img.height]
        if not vis:
            return
        tx = min(p[0] for p in vis) + 8
        ty = min(p[1] for p in vis) + 6
        tw = dr.textlength(text, font=font)
        dr.rectangle([tx - 4, ty - 2, tx + tw + 4, ty + 30], fill=(0, 0, 0))
        dr.text((tx, ty), text, fill=color, font=font)

    for nb in neighbors:
        labelled(nb["lo"], nb["hi"], COL_SAME,
                 f"{nb['id']} {nb['name']} (same class)")
    for nb in others:
        labelled(nb["lo"], nb["hi"], COL_OTHER, f"{nb['id']} {nb['name']}")
    for nb in riders:
        why = ("resting" if nb.get("why") == "rider"
               else "not independently supported")
        labelled(nb["lo"], nb["hi"], COL_RIDER,
                 f"{nb['id']} {nb['name']} ({why} - not cover)",
                 width=2, dash=(10, 8))
    labelled(box["lo"], box["hi"], COL_REGION, "THIS REGION")

    gy = float(box["hi"][1])          # y-down: box bottom = floor contact
    x0, x1, z0, z1 = grid["extent"]

    def chip(x, y, text, fg, bg):
        r = 21
        dr.ellipse([x - r, y - r, x + r, y + r], fill=bg, outline=fg, width=2)
        w = dr.textlength(text, font=cfont)
        dr.text((x - w / 2, y - 15), text, fill=fg, font=cfont)

    for nm in grid["x_names"]:
        gx = grid["lines"][nm]["value"]
        u, v, z = cam.project(np.array([[gx, gy, z0], [gx, gy, z1]]))
        if (z > NEAR_Z).all():
            dr.line([(u[0], v[0]), (u[1], v[1])], fill=COL_GRID, width=3)
            for (uu, vv) in ((u[0], v[0]), (u[1], v[1])):
                chip(uu, vv, nm, (255, 235, 59), (40, 40, 40))
            dr.text((u[0] + 26, v[0] - 8), f"x={gx:.2f}", fill=COL_GRID,
                    font=gfont)
    for nm in grid["z_names"]:
        gz = grid["lines"][nm]["value"]
        u, v, z = cam.project(np.array([[x0, gy, gz], [x1, gy, gz]]))
        if (z > NEAR_Z).all():
            dr.line([(u[0], v[0]), (u[1], v[1])], fill=COL_GRID, width=3)
            for (uu, vv) in ((u[0], v[0]), (u[1], v[1])):
                chip(uu, vv, nm, (128, 222, 234), (40, 40, 40))
            dr.text((u[0] - 8, v[0] + 26), f"z={gz:.2f}", fill=COL_GRID,
                    font=gfont)
    legend = []
    for nm in grid["s_names"]:
        L = grid["lines"][nm]
        if L["axis"] == "x":
            pts = np.array([[L["value"], gy, z0], [L["value"], gy, z1]])
        else:
            pts = np.array([[x0, gy, L["value"]], [x1, gy, L["value"]]])
        u, v, z = cam.project(pts)
        if (z > NEAR_Z).all():
            dr.line([(u[0], v[0]), (u[1], v[1])], fill=COL_S, width=4)
            for (uu, vv) in ((u[0], v[0]), (u[1], v[1])):
                chip(uu, vv, nm, COL_S, (30, 0, 30))
        legend.append(f"{nm} = {L['source']} ({L['axis']}="
                      f"{L['value']:.3f} m)")
    strip_h = 26 + 34 * max(1, len(legend))
    canvas = Image.new("RGB", (img.width, img.height + strip_h), (12, 12, 12))
    canvas.paste(img, (0, 0))
    ds = ImageDraw.Draw(canvas)
    if legend:
        for k, txt in enumerate(legend):
            ds.text((14, img.height + 12 + 34 * k), txt, fill=COL_S,
                    font=font)
    else:
        ds.text((14, img.height + 12), "no measured S-lines inside this "
                "region", fill=(160, 160, 160), font=font)
    canvas.save(out_png)
    return legend


# ---- the prompt ----------------------------------------------------------

PROMPT = """You are the SPLIT-CUT JUDGE (J8s) in a 3D scene-understanding
pipeline. An earlier judge ruled that node {nid} ("{name}") is NOT one box:
its voted box has to be cut into pieces. You cut it, ONE REGION AT A TIME.
This call is about ONE region only, and you make ONE decision about it.

GOAL: represent this object's content with boxes — the existing drawn
boxes already represent THEIR content. Discard a side whose content is
already taken care of by existing standalone boxes (or is empty floor);
KEEP only content no box represents. Objects RESTING ON this object
(listed: {riders}) and objects NOT INDEPENDENTLY SUPPORTED — no ON
edge of their own to anything but this object (listed: {unsupported})
— NEVER count as cover. Cut efficiently — the fewest
cuts that separate represented from unrepresented content.

REGION {rid} (round {rnd} of at most {max_rounds}) — plan extent
{dx:.2f} m (x) x {dz:.2f} m (z).
{parent_note}
THE STIMULUS (image files in this directory — open them; everything you
need is there, do NOT look for any other file):
  {stim}  — THE REGION, seen straight from above.
{context}
The top view contains ONLY the gaussians inside this region's box — nothing
outside it is drawn, so every pixel of content you see is content you are
ruling on. On it:
  ORANGE box   = THIS REGION (what you are cutting).
  GREEN box    = a SAME-CLASS neighbour node's own voted box, with its id.
                 If content in this region already belongs to a green box,
                 that content's owner is that node.
  RED box      = an overlapping OTHER-class node's voted box, with its id.
  GRAY DASHED box = an object RESTING ON this one or NOT INDEPENDENTLY
                 SUPPORTED ("not cover"), with its id. It does NOT
                 represent the region beneath it and is NEVER cover
                 for a discard.
  BLUE lattice = the naming grid. LETTER lines (A, B, C ...) are lines of
                 constant x; NUMBER lines (1, 2, 3 ...) are lines of
                 constant z. Every line carries its name in a chip at BOTH
                 ends.
  MAGENTA lines (S1, S2 ...) = MEASURED boundaries that really exist inside
                 this region (a neighbour box edge, an empty-notch edge).
                 The legend strip under the render says what each one is.
                 PREFER an S-line when the cut you want is at a real
                 boundary: S-lines are exact, lattice lines are round
                 numbers.

YOU SPEAK GRID VOCABULARY ONLY. Never give a coordinate: name a line
("S1", "B", "3") or say "between B and C". Code turns the name into a
number and snaps it to the measured boundary when there is one nearby.

DECIDE ONE OF TWO THINGS:

(1) NO CUT NEEDED — the content in this region is ONE thing. Either KEEP
    it (say who owns it) or DISCARD it (see below; give a short note).
(2) ONE CUT — a single straight line splits this region into two sides.
    Give the line, and for EACH of the two sides an INDEPENDENT verdict:
      KEEP    — the side is real territory: say who owns it, and say
                whether it needs more cutting ("more_cut").
                KEEPING BOTH SIDES IS LEGAL AND NORMAL.
      DISCARD — the side is DROPPED from this case entirely: it is empty
                floor, junk, or the territory of an object that ALREADY
                HAS ITS OWN NODE (its box already covers that content).
                Give a short "note" saying what it is; a discarded side
                has NO owner and never a more_cut.
    DISCARD RULES (hard): objects RESTING ON this region (pillows, decor,
    anything sitting on top of it) do NOT own it and are NEVER a reason
    to discard; discard a side only when its content is empty floor/junk
    or is already represented by STANDALONE objects' drawn boxes.
    Discards are MECHANICALLY VERIFIED: code measures how much of the
    side's actual content is covered by NO eligible existing box (the
    gray dashed resting boxes never count); a discard leaving too much
    content unrepresented is downgraded to keep, with a doubt on the
    record.
    DECIDE NOW: whenever this ONE cut settles a side, finish that side —
    discard-and-finish or keep-and-finish. Flag "more_cut": true ONLY
    when the kept side VISIBLY contains multiple separable things that
    THIS cut could not separate. A more_cut side comes back to you in the
    NEXT ROUND as its own region, with a fresh render and a fresh grid —
    so do NOT try to describe more than one cut now. The chain ends the
    moment nothing is flagged.
    FEWEST CUTS WINS. {max_rounds} rounds is a hard CEILING, not a budget
    to spend. The best answer settles this object in as few cuts as
    possible, and ONE cut that settles everything is the ideal outcome.
    Do NOT defer work to a later round just because rounds are available:
    measured on this pipeline, a judge told it had ONE round settled this
    same object correctly in one cut at higher confidence, while the same
    judge given three rounds spread the same decision across three. Flag
    "more_cut" only when you genuinely cannot settle the side now.

OWNER VOCABULARY (kept sides / kept regions only):
  "this_node"      — this is {nid}'s own territory ("{name}").
  "existing:<id>"  — this belongs to a node that already exists; cite the
                     id you see on a GREEN or RED box (e.g.
                     "existing:obj_063").
There is NO other owner: content that belongs to nobody drawn here, or
that another node's box already covers, is a DISCARD with a note.

CASE FACTS (meters; y is the height axis, y-DOWN — smaller y is higher):
{facts}

Reply with ONE JSON object only, no prose around it.
NO CUT:
{{"decision": "no_cut", "action": "keep", "owner": "<owner>",
  "confidence": <0..1>,
  "reason": "<one or two sentences citing what you SEE>"}}
or
{{"decision": "no_cut", "action": "discard", "note": "<what it is>",
  "confidence": <0..1>,
  "reason": "<one or two sentences citing what you SEE>"}}
ONE CUT (each piece is EITHER a keep OR a discard):
{{"decision": "cut",
  "cut_line": "<S1 | a letter | a number | between X and Y>",
  "pieces": [
    {{"side": "low",  "name": "<short name>", "action": "keep",
      "owner": "<owner>", "more_cut": true | false}}
      OR {{"side": "low", "name": "<short name>", "action": "discard",
      "note": "<what it is>"}},
    {{"side": "high", ... the same choice, independently ...}}],
  "confidence": <0..1>,
  "reason": "<one or two sentences citing what you SEE>"}}
"side" is which half of the region the piece is: "low" = the smaller-
coordinate side of the cut line (smaller x for a letter/x line, smaller z
for a number/z line), "high" = the larger-coordinate side.
Optionally a piece may carry "exclusions": [{{"from": "<line>",
"to": "<line>"}}] — a strip of the piece that is NOT part of it."""


def facts_block(box, grid, neighbors, others, riders, root):
    L = [f"- region box: lo {[round(v, 3) for v in box['lo']]} hi "
         f"{[round(v, 3) for v in box['hi']]}",
         f"- the node being cut: {root['id']} \"{root['name']}\" "
         f"(J8 ruled SPLIT / {root['identity']}"
         + (f", {root['count']} copies" if root.get("count") else "") + ")",
         f"- J8's reason: {root['reason']}",
         f"- lattice pitch: {grid['pitch']} m "
         f"(letters {', '.join(grid['x_names']) or 'none'}; numbers "
         f"{', '.join(grid['z_names']) or 'none'})"]
    if grid["s_names"]:
        for nm in grid["s_names"]:
            s = grid["lines"][nm]
            L.append(f"- MEASURED LINE {nm}: {s['source']}, "
                     f"{s['axis']}={s['value']:.3f} m")
    else:
        L.append("- no measured boundary falls inside this region "
                 "(lattice lines only)")
    for nb in neighbors:
        L.append(f"- GREEN {nb['id']} \"{nb['name']}\" (same class, via "
                 f"{nb['via']}): x {nb['lo'][0]:.3f}..{nb['hi'][0]:.3f}, "
                 f"z {nb['lo'][2]:.3f}..{nb['hi'][2]:.3f}")
    for nb in others:
        L.append(f"- RED {nb['id']} \"{nb['name']}\": "
                 f"x {nb['lo'][0]:.3f}..{nb['hi'][0]:.3f}, "
                 f"z {nb['lo'][2]:.3f}..{nb['hi'][2]:.3f} "
                 f"(overlaps this region by {nb['ov']:.3f} m3)")
    for nb in riders:
        why = (f"RESTING ON {root['id']}" if nb.get("why") == "rider"
               else "NOT INDEPENDENTLY SUPPORTED")
        L.append(f"- GRAY DASHED {nb['id']} \"{nb['name']}\" ({why} "
                 f"- not cover): "
                 f"x {nb['lo'][0]:.3f}..{nb['hi'][0]:.3f}, "
                 f"z {nb['lo'][2]:.3f}..{nb['hi'][2]:.3f}")
    return "\n".join(L)


# ---- the chain (a plain loop; NO recursion) ------------------------------

def cut_boxes(box, axis, value):
    k = 0 if axis == "x" else 2
    lo_hi = list(box["hi"])
    lo_hi[k] = value
    hi_lo = list(box["lo"])
    hi_lo[k] = value
    return ({"lo": list(box["lo"]), "hi": lo_hi},
            {"lo": hi_lo, "hi": list(box["hi"])})


def apply_exclusions(box, excl, grid, notes):
    """A piece's excluded strip is applied only when it touches an END of
    the piece along its axis (then the piece shrinks). An interior strip
    would make the piece non-rectangular, so it is RECORDED, not applied."""
    out = {"lo": list(box["lo"]), "hi": list(box["hi"])}
    applied = []
    for e in excl:
        ra, rb = snap_line(e["from"], grid), snap_line(e["to"], grid)
        if ra is None or rb is None or ra[0] != rb[0]:
            notes.append({"kind": "exclusion_unresolved", "excl": e})
            continue
        ax = ra[0]
        k = 0 if ax == "x" else 2
        a, b = sorted((ra[1], rb[1]))
        if a <= out["lo"][k] + 1e-6 and b < out["hi"][k]:
            out["lo"][k] = b
            applied.append({"excl": e, "axis": ax, "from": a, "to": b,
                            "effect": "trimmed the low end"})
        elif b >= out["hi"][k] - 1e-6 and a > out["lo"][k]:
            out["hi"][k] = a
            applied.append({"excl": e, "axis": ax, "from": a, "to": b,
                            "effect": "trimmed the high end"})
        else:
            notes.append({"kind": "interior_exclusion_recorded_not_applied",
                          "excl": e, "axis": ax, "from": a, "to": b})
    return out, applied


def rnd_box(box):
    return {"lo": [round(float(v), 4) for v in box["lo"]],
            "hi": [round(float(v), 4) for v in box["hi"]]}


def judge_one_region(st, item, rnd):
    """ONE region -> ONE stimulus -> ONE judged decision. Returns the flat
    round record; the caller (run_chain) decides what happens next. This
    function NEVER calls itself."""
    box, rid = item["box"], item["id"]
    root = st["root"]
    grid = build_grid(box, specials_for(box, st["neighbors"], st["notches"]))
    stem = f"{root['id']}_{rid}"
    dx, dz = plan_extents(box)
    rec = {"round": rnd, "region_id": rid, "parent_id": item.get("parent"),
           "region_box": rnd_box(box),
           "plan_extent_m": [round(dx, 3), round(dz, 3)],
           "parent_owner": item.get("owner"),
           "grid": {"pitch": grid["pitch"], "x_names": grid["x_names"],
                    "z_names": grid["z_names"],
                    "s_lines": {nm: {"axis": grid["lines"][nm]["axis"],
                                     "value": round(
                                         grid["lines"][nm]["value"], 4),
                                     "source": grid["lines"][nm]["source"]}
                                for nm in grid["s_names"]}},
           "snapped_cut": None, "pieces": [], "doubts": [], "notes": []}

    png, tgt, n_g = render_region(st["splat"], box, st["dir"], stem + "_raw",
                                  f"{root['id']} region {rid}")
    cam = make_cam(tgt["eye"], tgt["aim"], tgt["fov"], RES)
    ann = st["dir"] / f"{stem}.png"
    annotate(png, ann, box, grid, cam, st["neighbors"], st["others"],
             st["rider_boxes"])
    rec["stimulus"] = {"render": png.name, "annotated": ann.name,
                       "gaussians": n_g, "camera": tgt}
    prompt = PROMPT.format(
        nid=root["id"], name=root["name"], rid=rid, rnd=rnd,
        max_rounds=st["max_rounds"], dx=dx, dz=dz,
        riders=", ".join(st["riders"]) or "none",
        unsupported=", ".join(st["unsupported"]) or "none",
        parent_note=item.get("note", ""), stim=ann.name,
        context=st["context_block"],
        facts=facts_block(box, grid, st["neighbors"], st["others"],
                          st["rider_boxes"], root))
    (st["dir"] / f"{stem}_prompt.txt").write_text(prompt, encoding="utf-8")
    rec["stimulus"]["prompt"] = f"{stem}_prompt.txt"

    if st["sheets_only"]:
        rec["verdict"] = None
        rec["outcome"] = "sheets_only"
        return rec, grid

    h = hashlib.sha256()
    h.update(json.dumps(rec["region_box"], sort_keys=True).encode())
    h.update(prompt.encode())
    h.update(ann.read_bytes())
    key = h.hexdigest()[:24]
    if key in st["cache"]:
        v, cached = st["cache"][key], True
    else:
        # A CALL FAILURE MAY NEVER KILL THE CHAIN (2026-08-08): a slow
        # claude.exe hitting CALL_TIMEOUT_S raised TimeoutExpired out of
        # the round loop and lost the whole case. Every failure is a
        # failed ATTEMPT — retried once, then the region ships UNCUT with
        # the reason recorded (same fallback as a malformed reply).
        def attempt(p):
            try:
                return parse_verdict(call_claude(p, st["dir"],
                                                 st["model"])), None
            except Exception as e:                    # noqa: BLE001
                return None, f"{type(e).__name__}: {str(e)[:160]}"

        v, err = attempt(prompt)
        if v is None:
            v, err2 = attempt(prompt + "\n\nREPLY WITH THE JSON OBJECT "
                              "ONLY.")
            err = err2 or err
        if v is None:
            v = {"decision": "no_cut", "action": "keep",
                 "owner": item.get("owner") or "this_node",
                 "confidence": 0.0,
                 "reason": (f"judge call failed x2 ({err}) - region ships "
                            "UNCUT" if err else
                            "malformed model reply x2 - region ships UNCUT")}
            rec["doubts"].append("unclear_ships_uncut")
        v = {**v, "model": st["model"], "date": date.today().isoformat()}
        st["cache"][key] = v
        cached = False
        st["calls"] += 1
    rec["verdict"] = v
    rec["cached"] = cached
    print(f"[splitcuts] {root['id']} r{rnd} {rid:<6} "
          f"{v['decision']:<7} {v.get('cut_line', v.get('owner', '')):<22} "
          f"conf {v.get('confidence', 0):.2f}"
          f"{' (cache)' if cached else ''}", flush=True)
    return rec, grid


def run_chain(st, region):
    """THE FIXED 3-ROUND CHAIN — a plain loop over a flat worklist. No
    recursion, no tree: rounds are appended to one flat list and the loop
    stops unconditionally after st['max_rounds'] rounds."""
    rounds, final = [], []
    work = [{"id": "R", "box": region, "owner": None, "parent": None,
             "note": "This is the WHOLE box: nothing has been cut yet.\n"}]
    st["pieces"] = 1
    seq = 0
    for rnd in range(1, st["max_rounds"] + 1):
        if not work:
            break
        nxt = []
        for item in work:
            rec, grid = judge_one_region(st, item, rnd)
            rounds.append(rec)
            v = rec.get("verdict")
            if v is None:                      # --sheets-only
                final.append({"id": item["id"], "box": rnd_box(item["box"]),
                              "owner": item.get("owner"),
                              "provenance": "sheets_only", "doubts": []})
                continue
            if v["decision"] == "no_cut":
                if v.get("action") == "discard":
                    stands, audit, doubt = audit_discard(st, item["box"])
                    rec["notes"].append(audit)
                    note = v.get("note") or "no note"
                    if stands:
                        rec["outcome"] = "no_cut_discard"
                        rec["notes"].append({"kind": "region_discarded",
                                             "note": v.get("note", "")})
                        print(f"[splitcuts] {st['root']['id']} "
                              f"{item['id']}: region DISCARDED - {note} "
                              f"(residue {audit['residue']:.0%}; "
                              "dropped from this case)", flush=True)
                        continue
                    rec["outcome"] = "no_cut_discard_downgraded"
                    rec["doubts"].append(doubt)
                    final.append(
                        {"id": item["id"], "box": rnd_box(item["box"]),
                         "owner": "this_node",
                         "plan_extent_m": rec["plan_extent_m"],
                         "provenance": f"round {rnd}: judge said discard "
                                       f"(\"{note}\") but the "
                                       "representation check failed - "
                                       "DOWNGRADED to keep",
                         "doubts": list(rec["doubts"]),
                         "residue_check": audit})
                    print(f"[splitcuts] {st['root']['id']} {item['id']}: "
                          f"discard DOWNGRADED to keep - {audit['why']}",
                          flush=True)
                    continue
                rec["outcome"] = "no_cut"
                final.append({"id": item["id"], "box": rnd_box(item["box"]),
                              "owner": v["owner"],
                              "plan_extent_m": rec["plan_extent_m"],
                              "provenance": f"round {rnd}: judged no_cut",
                              "doubts": list(rec["doubts"])})
                continue
            r = snap_line(v["cut_line"], grid)
            k = None
            if r is not None:
                k = 0 if r[0] == "x" else 2
                if not (item["box"]["lo"][k] + 1e-3 < r[1]
                        < item["box"]["hi"][k] - 1e-3):
                    rec["doubts"].append("cut_line_outside_region")
                    rec["notes"].append({"kind": "cut_outside", "axis": r[0],
                                         "value": r[1], "provenance": r[2]})
                    r = None
            if r is None:
                if "cut_line_outside_region" not in rec["doubts"]:
                    rec["doubts"].append("cut_line_not_in_vocabulary")
                    rec["notes"].append({"kind": "unresolvable_cut_line",
                                         "asked": v["cut_line"]})
                rec["outcome"] = "ships_uncut"
                final.append({"id": item["id"], "box": rnd_box(item["box"]),
                              "owner": item.get("owner") or "this_node",
                              "plan_extent_m": rec["plan_extent_m"],
                              "provenance": f"round {rnd}: cut line "
                                            f"'{v['cut_line']}' unusable - "
                                            f"ships UNCUT",
                              "doubts": list(rec["doubts"])})
                print(f"[splitcuts] {st['root']['id']} {item['id']}: cut "
                      f"line '{v['cut_line']}' unusable - ships UNCUT",
                      flush=True)
                continue
            axis, value, prov = r
            rec["snapped_cut"] = {"axis": axis, "value": round(float(value),
                                                               4),
                                  "provenance": prov}
            rec["outcome"] = "cut"
            st["pieces"] += 1                  # one region became two
            lo_box, hi_box = cut_boxes(item["box"], axis, value)
            for piece in v["pieces"]:
                seq += 1
                pid = f"P{seq}"
                pbox = lo_box if piece["side"] == "low" else hi_box
                prov_txt = (f"round {rnd}: {piece['side']} side of the cut "
                            f"{axis}={value:.3f} ({prov['rule']})")
                if piece["action"] == "discard":
                    stands, audit, doubt = audit_discard(st, pbox)
                    pdx, pdz = plan_extents(pbox)
                    note = piece.get("note") or "no note"
                    if stands:
                        rec["pieces"].append(
                            {"id": pid, "side": piece["side"],
                             "name": piece["name"], "action": "discard",
                             "note": piece.get("note", ""),
                             "box": rnd_box(pbox),
                             "plan_extent_m": [round(pdx, 3),
                                               round(pdz, 3)],
                             "residue_check": audit})
                        print(f"[splitcuts] {st['root']['id']} {pid}: "
                              f"{piece['side']} side DISCARDED - {note} "
                              f"(residue {audit['residue']:.0%}; "
                              "dropped from this case)", flush=True)
                        continue
                    # DOWNGRADE (representation objective, 08-07): the
                    # side still holds content NO eligible box represents
                    # - keep it, this_node.
                    rec["pieces"].append(
                        {"id": pid, "side": piece["side"],
                         "name": piece["name"], "action": "keep",
                         "owner": "this_node", "more_cut": False,
                         "box": rnd_box(pbox),
                         "plan_extent_m": [round(pdx, 3), round(pdz, 3)],
                         "guard": None, "doubts": [doubt],
                         "residue_check": audit,
                         "notes": [{"kind": "discard_downgraded",
                                    "judge_note": piece.get("note", "")}]})
                    final.append(
                        {"id": pid, "box": rnd_box(pbox),
                         "owner": "this_node",
                         "plan_extent_m": [round(pdx, 3), round(pdz, 3)],
                         "provenance": prov_txt + " - judge said discard "
                                       f"(\"{note}\") but the "
                                       "representation check failed - "
                                       "DOWNGRADED to keep",
                         "doubts": [doubt], "residue_check": audit})
                    print(f"[splitcuts] {st['root']['id']} {pid}: "
                          f"{piece['side']} side discard DOWNGRADED to "
                          f"keep - {audit['why']}", flush=True)
                    continue
                notes = []
                if piece["exclusions"]:
                    pbox, applied = apply_exclusions(pbox,
                                                     piece["exclusions"],
                                                     grid, notes)
                    if applied:
                        notes.append({"kind": "exclusions_applied",
                                      "applied": applied})
                pdx, pdz = plan_extents(pbox)
                want = piece["more_cut"]
                doubts, stop = [], None
                if want:
                    if min(pdx, pdz) < MIN_EXTENT:
                        stop = "auto_done_small"     # never judged
                    elif st["pieces"] >= MAX_PIECES:
                        stop = "split_incomplete"    # piece budget
                    elif rnd >= st["max_rounds"]:
                        stop = "split_incomplete"    # the chain stops
                rec["pieces"].append(
                    {"id": pid, "side": piece["side"], "name": piece["name"],
                     "action": "keep", "owner": piece["owner"],
                     "more_cut": piece["more_cut"], "box": rnd_box(pbox),
                     "plan_extent_m": [round(pdx, 3), round(pdz, 3)],
                     "guard": stop, "notes": notes})
                if want and stop is None:
                    nxt.append({"id": pid, "box": pbox,
                                "owner": piece["owner"], "parent": item["id"],
                                "note": ("THIS REGION IS A PIECE of a bigger "
                                         "box that was already cut once: the "
                                         "previous cut said this piece "
                                         f"(\"{piece['name'] or pid}\") still "
                                         "needs cutting, and provisionally "
                                         f"assigned it to {piece['owner']}. "
                                         "Rule it fresh.\n")})
                else:
                    if stop:
                        doubts.append(stop)
                    final.append({"id": pid, "box": rnd_box(pbox),
                                  "owner": piece["owner"],
                                  "plan_extent_m": [round(pdx, 3),
                                                    round(pdz, 3)],
                                  "provenance": prov_txt, "doubts": doubts,
                                  "notes": notes})
                    if stop == "split_incomplete":
                        print(f"[splitcuts] {st['root']['id']} {pid}: wanted "
                              "another cut but hit a guard - ships UNCUT "
                              "(doubt split_incomplete)", flush=True)
        work = nxt
    for item in work:      # the chain stopped with pieces still pending
        final.append({"id": item["id"], "box": rnd_box(item["box"]),
                      "owner": item.get("owner") or "this_node",
                      "plan_extent_m": [round(v, 3)
                                        for v in plan_extents(item["box"])],
                      "provenance": f"the {st['max_rounds']}-round chain "
                                    "stopped with this piece still wanting "
                                    "a cut", "doubts": ["split_incomplete"]})
        print(f"[splitcuts] {st['root']['id']} {item['id']}: chain exhausted "
              "- ships UNCUT (doubt split_incomplete)", flush=True)
    return rounds, final


# ---- docket --------------------------------------------------------------

def node_class(i, names):
    return "" if str(i).startswith("arch_") else (names.get(i) or "").lower()


def case_riders(nid, edges):
    """RIDERS of a case node: nodes RESTING ON it — the `a` of an ON
    edge whose `b` is the case node in graph['voted_edges'] (pillows
    ON the sofa). Direction matters: the case's own SUPPORTER (case ON
    arch_floor) is NOT a rider. Resting objects never represent the
    region beneath them — excluded from discard cover and drawn thin
    dashed gray on the stimulus."""
    return sorted({e["a"] for e in edges
                   if e.get("b") == nid
                   and str(e.get("type", "")).upper() == "ON"})


def case_excluded(nid, edges, voted):
    """EVERY node whose voted box NEVER counts as cover for this case,
    as {id: reason}. NEW ELIGIBILITY RULE (user, 08-07: existing boxes
    count as cover only if they represent INDEPENDENT objects): a node
    is INDEPENDENTLY SUPPORTED iff it is the `a` of an ON edge to a
    target OTHER than the case node (the table ON arch_floor —
    eligible). reason "rider" = it rests ON the case node; reason
    "no_independent_support" = it has no such ON edge at all (the
    pillows, whose voted edges came out IN, not ON — it rides
    whatever contains it)."""
    riders = set(case_riders(nid, edges))
    supported = {e["a"] for e in edges
                 if str(e.get("type", "")).upper() == "ON"
                 and e.get("b") != nid}
    out = {}
    for oid in voted:
        if oid == nid:
            continue
        if oid in riders:
            out[oid] = "rider"
        elif oid not in supported:
            out[oid] = "no_independent_support"
    return out


def build_case_context(nid, edges, names, voted, region, excluded):
    """GREEN = same-class neighbours joined by any voted edge (their
    SETTLED boxes VERBATIM — see settled_voted). RED = any OTHER-class node
    whose box overlaps the region (eligible cover, drawn so the
    judge sees it). GRAY DASHED = never-cover nodes (riders + nodes
    with no independent support, per case_excluded) whose box touches
    the region — drawn so the judge sees which boxes never count as
    cover; each carries its "why"."""
    mine = node_class(nid, names)
    same, seen = [], set()
    for e in edges:
        if nid not in (e["a"], e["b"]):
            continue
        o = e["b"] if e["a"] == nid else e["a"]
        if o in seen or o in excluded or not mine \
                or node_class(o, names) != mine:
            continue
        seen.add(o)
        if o not in voted:
            continue
        lo, hi = voted[o]
        same.append({"id": o, "name": names.get(o, "?"), "via": e["type"],
                     "lo": list(lo), "hi": list(hi)})
    others = []
    for o, (lo, hi) in voted.items():
        if o == nid or o in seen or o in excluded \
                or node_class(o, names) == mine:
            continue
        ov = overlap_vol(region["lo"], region["hi"], lo, hi)
        if ov > 0.005:
            others.append({"id": o, "name": names.get(o, "?"), "lo": list(lo),
                           "hi": list(hi), "ov": ov})
    others.sort(key=lambda d: -d["ov"])
    rx = plan_rect(region)
    rider_boxes = []
    for o, why in excluded.items():
        if o not in voted:
            continue
        lo, hi = voted[o]
        g = grown_rect(lo, hi)
        if g[0] < rx[2] and g[2] > rx[0] and g[1] < rx[3] and g[3] > rx[1]:
            rider_boxes.append({"id": o, "name": names.get(o, "?"),
                                "why": why,
                                "lo": list(lo), "hi": list(hi)})
    return (sorted(same, key=lambda d: d["id"]), others[:6],
            sorted(rider_boxes, key=lambda d: d["id"]))


def covered_by_existing(case, voted):
    """MECHANICAL RESOLUTION, zero model calls: a SPLIT/distinct case whose
    parts all map to nodes that ALREADY EXIST with a voted box needs no
    cuts at all — the pieces are already represented. Returns the
    resolution dict, or None when the case needs real geometry (any
    missing_instance part, any identity other than distinct, any cited id
    without a voted box)."""
    v = case["verdict"]
    if v.get("identity") != "distinct":
        return None
    parts = v.get("parts") or []
    if not parts:
        return None
    owners, miss = [], []
    for p in parts:
        o = p["owner"]
        if o == "this_node":
            owners.append(case["id"])
            continue
        if o.startswith("existing:"):
            oid = o[len("existing:"):].strip()
            (owners if oid in voted else miss).append(oid)
            continue
        return None            # missing_instance -> real geometry needed
    if miss:
        return None
    reg = voted[case["id"]]
    cov = []
    for oid in owners:
        lo, hi = voted[oid]
        cov.append({"id": oid,
                    "overlap_m3": round(overlap_vol(reg[0], reg[1], lo, hi),
                                        5)})
    return {"resolution": "covered_by_existing", "owners": owners,
            "coverage": cov, "calls": 0,
            "why": "J8 ruled SPLIT/distinct and every part maps to a node "
                   "that already exists with a voted box (this node's own "
                   "shipping box is its part) - nothing to cut."}


# ---- sheet ---------------------------------------------------------------

CSS = """body{font-family:system-ui,sans-serif;margin:22px;background:#111;
color:#eee}h1{font-size:19px;margin:0 0 4px}h2{font-size:14px;
margin:20px 0 6px;color:#ffd27a}.meta{font-size:12px;color:#bbb}
figure{margin:0 0 14px}figure img{max-width:760px;border:1px solid #444}
figcaption{font-size:12px;color:#cfd8ff}
pre{background:#1b1b1b;border:1px solid #444;padding:10px;font-size:12px;
white-space:pre-wrap}a{color:#8ec7ff}
table{border-collapse:collapse;font-size:12px}td,th{border:1px solid #444;
padding:4px 8px}"""


def round_html(rec):
    v = rec.get("verdict") or {}
    cut = rec.get("snapped_cut")
    head = (f"<b>ROUND {rec['round']} &middot; region {rec['region_id']}</b>"
            f" ({rec['plan_extent_m'][0]}x{rec['plan_extent_m'][1]} m"
            + (f", from {rec['parent_id']}" if rec.get("parent_id") else "")
            + f") &middot; {rec.get('outcome')}")
    bits = []
    if v:
        lbl = v.get("cut_line") or v.get("owner") or ""
        if v.get("decision") == "no_cut" and v.get("action") == "discard":
            lbl = f"DISCARD ({v.get('note', '') or 'no note'})"
        bits.append(f"verdict: {v.get('decision')} {lbl} "
                    f"(conf {v.get('confidence')}) — {v.get('reason', '')}")
    if cut:
        bits.append(f"SNAPPED CUT {cut['axis']}={cut['value']} — "
                    f"{cut['provenance']['resolved']} "
                    f"[{cut['provenance']['rule']}]")
    for p in rec.get("pieces", []):
        cc = p.get("residue_check")
        cov = ""
        if cc:
            cov = (f" · residue {cc['residue']:.0%}"
                   if cc.get("residue") is not None else " · residue n/a")
        if p.get("action") == "discard":
            bits.append(f"piece {p['id']} ({p['side']}, \"{p['name']}\") → "
                        f"DISCARDED — {p.get('note', '') or 'no note'}"
                        + cov)
        else:
            bits.append(f"piece {p['id']} ({p['side']}, \"{p['name']}\") → "
                        f"keep · {p['owner']} · more_cut "
                        f"{str(p.get('more_cut')).lower()}"
                        + (f" · guard {p['guard']}" if p.get("guard")
                           else "")
                        + (f" · DOWNGRADED discard{cov} · doubts "
                           + ", ".join(p["doubts"])
                           if p.get("doubts") else ""))
    if rec.get("doubts"):
        bits.append("doubts: " + ", ".join(rec["doubts"]))
    img = ""
    if rec.get("stimulus"):
        img = (f"<figure><img src='{rec['stimulus']['annotated']}'>"
               f"<figcaption>{rec['stimulus']['gaussians']:,} gaussians "
               f"inside this region &middot; prompt: "
               f"<a href='{rec['stimulus']['prompt']}'>"
               f"{rec['stimulus']['prompt']}</a></figcaption></figure>")
    return (f"<div style='border-left:2px solid #444;padding-left:12px;"
            f"margin:10px 0'><p class='meta'>{head}<br>"
            + "<br>".join(bits) + f"</p>{img}</div>")


def write_case_sheet(d, case, rounds, pieces):
    body = "".join(round_html(r) for r in rounds) or \
        "<p class='meta'>no rounds.</p>"
    rows = "".join(f"<tr><td>{p['id']}</td><td>{p['owner']}</td>"
                   f"<td>{p.get('plan_extent_m')}</td>"
                   f"<td>{p.get('provenance', '')}</td>"
                   f"<td>{', '.join(p.get('doubts') or []) or '-'}</td></tr>"
                   for p in pieces)
    html = f"""<!doctype html><meta charset='utf-8'>
<title>J8s split cuts - {case['id']}</title><style>{CSS}</style>
<h1>J8s - SPLIT CUTS - {case['id']} "{case['name']}"</h1>
<p class='meta'>J8: SPLIT / {case['verdict'].get('identity')} &middot;
resolution: {case.get('resolution')} &middot; fixed
{case.get('max_rounds', MAX_ROUNDS)}-round chain (no recursion)</p>
<h2>FINAL PIECES</h2><table>
<tr><th>piece</th><th>owner</th><th>plan extent</th><th>provenance</th>
<th>doubts</th></tr>{rows}</table>
<h2>THE ROUNDS (flat)</h2>{body}
"""
    (d / "index.html").write_text(html, encoding="utf-8")


# ---- main ----------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--sheets-only", action="store_true")
    ap.add_argument("--rounds", type=int, default=MAX_ROUNDS,
                    help="hard stop on the chain (user ruling: 3)")
    ap.add_argument("--model", default=MODEL)
    a = ap.parse_args()
    sd = paths.scene_dir(a.scene)
    mf = sd / "graph" / "multiplicity.json"
    if not mf.exists():
        raise SystemExit("[splitcuts] no graph/multiplicity.json - run "
                         "graph/judge_multiplicity.py first")
    mult = json.loads(mf.read_text(encoding="utf-8"))
    g = json.loads((sd / "scene_graph.json").read_text(encoding="utf-8"))
    names = {n["id"]: n["name"] for n in g["resolved"]["nodes"]}
    edges = (g.get("voted_edges") or {}).get("edges") or []
    if not edges:
        raise SystemExit("[splitcuts] no graph['voted_edges'] - run "
                         "graph/rederive_voted_edges.py --apply first")
    prev = sd / "scene_manifest_slicevote_preview.json"
    voted = {o["id"]: (o["aabb_min"], o["aabb_max"])
              for o in json.loads(prev.read_text(encoding="utf-8"))["objects"]}
    # SETTLED GEOMETRY (2026-08-08) — J8's `settled_boxes` wins per id over
    # the preview manifest, for EVERY box below: the region being cut, the
    # green/red/gray context boxes, the S-lines built from them, and the
    # discard-cover eligibility test. See settled_voted().
    voted, voted_src = settled_voted(mult, voted)
    print(f"[splitcuts] boxes: {voted_src}", flush=True)
    # plan_cells per node (the vote's own occupancy grid, 0.10 m cells
    # anchored to the vote2 box) — the discard residue check's occupied
    # cells (audit_discard).
    plan_cells = {}
    rep_f = sd / "pool_retake" / "slicevote_report.json"
    if rep_f.exists():
        rep = json.loads(rep_f.read_text(encoding="utf-8"))
        for r in rep.get("results", []):
            pc = (r.get("rule") or {}).get("plan_cells")
            v2 = (r.get("boxes") or {}).get("vote2")
            if pc and v2:
                plan_cells[r["id"]] = {**pc,
                                       "lo_x": float(v2["lo"][0]),
                                       "lo_z": float(v2["lo"][2])}
    doubts = {}
    df = sd / "graph" / "vote_doubts.json"
    if df.exists():
        doubts = {n["id"]: n["doubts"]
                  for n in json.loads(df.read_text(encoding="utf-8"))["nodes"]}

    docket = [c for c in mult["cases"]
              if (c.get("verdict") or {}).get("outcome") == "SPLIT"]
    if a.only:
        keep = set(a.only.split(","))
        docket = [c for c in docket if c["id"] in keep]
    if not docket:
        raise SystemExit("[splitcuts] no SPLIT cases on the J8 docket")
    root_dir = sd / "graph" / "split_sheets"
    root_dir.mkdir(parents=True, exist_ok=True)
    cache_f = sd / "graph" / "split_cuts_cache.json"
    cache = json.loads(cache_f.read_text(encoding="utf-8")) \
        if cache_f.exists() else {}

    splat = None
    out_cases, total_calls = [], 0
    for case in docket:
        nid = case["id"]
        if nid not in voted:
            print(f"[splitcuts] {nid}: no voted box in the preview "
                  "manifest - skipped", flush=True)
            continue
        rec = {"id": nid, "name": case["name"],
               "j8_verdict": case["verdict"],
               "region_box_source": voted_src}
        mech = covered_by_existing(case, voted)
        if mech is not None:
            rec.update(mech)
            rec["rounds"] = []
            rec["pieces"] = [{"id": f"E{k + 1}", "owner": o,
                              "box": {"lo": list(voted[o][0]),
                                      "hi": list(voted[o][1])},
                              "provenance": "covered_by_existing: this "
                                            "part IS an existing node's "
                                            "voted box, verbatim",
                              "doubts": []}
                             for k, o in enumerate(mech["owners"])]
            out_cases.append(rec)
            print(f"[splitcuts] {nid:>8} {case['name']:<10} "
                  f"covered_by_existing (0 calls) owners "
                  f"{'/'.join(mech['owners'])}", flush=True)
            continue
        if splat is None:      # lazy: a docket of only mechanical cases
            splat = Splat(paths.ply(a.scene))   # never reads the ply
        lo, hi = voted[nid]
        region = {"lo": list(lo), "hi": list(hi)}
        riders = case_riders(nid, edges)
        excluded = case_excluded(nid, edges, voted)
        unsupported = sorted(o for o, why in excluded.items()
                             if why == "no_independent_support")
        same, others, rider_boxes = build_case_context(
            nid, edges, names, voted, region, excluded)
        d = root_dir / nid
        d.mkdir(parents=True, exist_ok=True)
        for old in (list(d.glob("*.png")) + list(d.glob("*_prompt.txt"))
                    + list(d.glob("_*_target.json"))):
            old.unlink()   # a shorter chain must not leave the old one's
            #                stimuli behind (region ids are per-run)
        # side context: the J8 sheets' own annotated card renders
        ctx = []
        msheets = sd / "graph" / "multiplicity_sheets"
        for p in sorted(msheets.glob(f"{nid}_card*.png")) + \
                sorted(msheets.glob(f"{nid}_top.png")):
            shutil.copyfile(p, d / f"ctx_{p.name}")
            ctx.append(f"ctx_{p.name}")
        ctx_block = ""
        if ctx:
            ctx_block = ("SIDE CONTEXT (the same object seen in the scene, "
                         "from the earlier judge's panels - use them to "
                         "recognise WHAT the content is; the cut is made on "
                         "the top view):\n"
                         + "\n".join(f"  {c}" for c in ctx) + "\n")
        st = {"root": {"id": nid, "name": case["name"],
                       "identity": case["verdict"].get("identity"),
                       "count": case["verdict"].get("count"),
                       "reason": case["verdict"].get("reason", "")},
              "dir": d, "splat": splat, "neighbors": same, "others": others,
              "riders": riders, "unsupported": unsupported,
              "excluded": excluded, "rider_boxes": rider_boxes,
              "voted": {o: v for o, v in voted.items()},
              "notches": [dd["rect_m"] for dd in doubts.get(nid, [])
                          if dd["kind"] == "large_empty_notch"],
              "cache": cache, "model": a.model, "calls": 0,
              "plan_cells": plan_cells.get(nid),
              "max_rounds": a.rounds, "pieces": 1,
              "sheets_only": a.sheets_only, "context_block": ctx_block}
        rounds, pieces = run_chain(st, region)
        rec.update({"resolution": "split_chain", "max_rounds": a.rounds,
                    "rounds": rounds, "pieces": pieces, "calls": st["calls"],
                    "same_class_neighbors": [n["id"] for n in same],
                    "other_class_drawn": [n["id"] for n in others],
                    "riders_on": riders,
                    "not_independently_supported": unsupported,
                    "never_cover_drawn": [n["id"] for n in rider_boxes]})
        total_calls += st["calls"]
        out_cases.append(rec)
        write_case_sheet(d, {**rec, "verdict": case["verdict"]}, rounds,
                         pieces)
        print(f"[splitcuts] {nid:>8} {case['name']:<10} "
              f"{len(rounds)} round record(s), {len(pieces)} final piece(s), "
              f"{st['calls']} call(s) -> {d}", flush=True)

    cache_f.write_text(json.dumps(cache, indent=1), encoding="utf-8")
    out_f = sd / "graph" / "split_cuts.json"
    out_f.write_text(json.dumps({
        "scene": a.scene, "built": date.today().isoformat(),
        "source": "graph/split_cuts.py (J8s) - executes J8 SPLIT verdicts "
                  "geometrically as a FIXED 3-ROUND CHAIN (a plain loop over "
                  "a flat worklist; no recursion). SIDECAR ONLY: the rounds "
                  "list + final pieces reference nodes; materialize is the "
                  "editor.",
        "boxes_source": voted_src,
        "guards": {"max_rounds": a.rounds, "min_extent_m": MIN_EXTENT,
                   "max_pieces": MAX_PIECES, "snap_radius_m": SNAP_R,
                   "s_dedupe_m": S_DEDUPE,
                   "discard_residue_max": RESIDUE_MAX,
                   "discard_margin_m": MARGIN, "discard_occ_k": OCC_K},
        "cases": out_cases}, indent=1), encoding="utf-8")
    idx = "".join(
        f"<tr><td><a href='{c['id']}/index.html'>{c['id']}</a></td>"
        f"<td>{c['name']}</td><td>{c.get('resolution')}</td>"
        f"<td>{c.get('calls', 0)}</td>"
        f"<td>{len(c.get('rounds', []))}</td>"
        f"<td>{len(c.get('pieces', []))}</td></tr>" for c in out_cases)
    (root_dir / "index.html").write_text(
        f"""<!doctype html><meta charset='utf-8'>
<title>J8s split cuts - {a.scene}</title><style>{CSS}</style>
<h1>J8s - SPLIT CUTS - {a.scene}</h1>
<p class='meta'>{len(out_cases)} SPLIT case(s), {total_calls} model
call(s). FIXED CHAIN: at most {a.rounds} rounds, then it stops. Guards:
min extent {MIN_EXTENT} m (auto-done, never judged), max {MAX_PIECES}
pieces/case, leftovers ship uncut with doubt split_incomplete.</p>
<table><tr><th>case</th><th>name</th><th>resolution</th><th>calls</th>
<th>rounds</th><th>pieces</th></tr>{idx}</table>""", encoding="utf-8")
    print(f"[splitcuts] {len(out_cases)} case(s), {total_calls} model "
          f"call(s) -> {out_f}", flush=True)
    print(f"[splitcuts] sheets: {root_dir / 'index.html'}", flush=True)


if __name__ == "__main__":
    main()
