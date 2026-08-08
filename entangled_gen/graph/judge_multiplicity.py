"""MULTIPLICITY JUDGE (J8) — one box or several? Which box ships?
(PLAN_CARVE_DOWNSTREAM Phase A; DESIGN v2.1 ADOPTED 2026-08-07 R-S2-35.)

CONTRACT: GETS one docket case = a resolved node + the AUTO carve doubts
that admitted it (large_empty_notch / pano_vs_cluster / culled_clusters /
low_plan_fill — Rule #1: no user-routing channel, the pipeline raises its
own questions) plus the v2.1 stimuli.
DECIDES, representation first: (1) the OUTCOME — ONE_BOX / SPLIT /
UNCLEAR — (2) WHICH GEOMETRY SHIPS when the outcome is ONE_BOX (the
pano-vs-vote ambiguity is undecidable from geometry alone; it is exactly
what the judge is here to solve), and (3) on a SPLIT, the IDENTITY
ANNOTATION — one_structure / copies(k) / distinct + per-part owners.
It NEVER edits the graph — verdicts land in the graph/multiplicity.json
sidecar; materialize (Phase C) is the editor. A mistake looks like:
splitting a real single object, blessing one box around two real
instances, or picking the occlusion-shaved box over the true extent.

FACTS FROM THE GRAPH'S OWN EDGES (v2.1, the obj_063 rule): every
relational fact in the docket line is READ from graph["carved_edges"]
— the 4g2 edges re-derived on the CARVED boxes by the Phase-B2
loop-back (graph/rederive_carved_edges.py), carrying J0 triage and J1
SAME_CANDIDATE verdicts. J8 computes NO private overlap lists: the v2
private top-6 list dropped obj_063 (the other sofa, ~85% of its volume
inside obj_011's box) behind six pillows and the judge ruled the sofa
case without the decisive fact. Same-class neighbours are NEVER
truncated; unrelated-class facts are capped at FACT_CAP by relevance.

STIMULI v2.1 (the anti-drift design, one-look rule): the object's OWN
carve renders — the four view-tunnel cards (+ eye-height / isolation
cards when the ladder escalated) and the plan render the carve detected
on — with the carve's 3D boxes PROJECTED onto them:
    ORANGE  = boxes.vote2 (the gate-3 vote-cluster box)
    CYAN    = boxes.pano  (this node's pano-mask-filtered box)
    GREEN   = a SAME-CLASS neighbour node's carved box, labelled with its
              id (v2.1) — the is-the-rest-another-object evidence made
              visible, not just numeric. Boxes come VERBATIM from
              scene_manifest_slicevote_preview.json.
    RED DASHED (plan view only) = the large_empty_notch rectangle
The projection uses carve_cams.py — the SAME camera module the carve's
renderer used — so an overlay cannot drift from the render it annotates.
Card cameras come from each render's own votetgt sidecar (fallback: the
conemap views record); the plan camera is rebuilt with
carve_cams.top_cam_for and is only drawn when its eye VALIDATES against
the eye the carve recorded (within EYE_TOL). No guessed projections.

REVIEW-FIRST: --sheets-only builds one self-contained HTML sheet + the
verbatim prompt per case (graph/multiplicity_sheets/) with ZERO model
calls — USER GATE A1 eyeballs the stimuli before any verdict runs.

Run:  python graph/judge_multiplicity.py --scene living_marble --sheets-only
      python graph/judge_multiplicity.py --scene living_marble
      [--only obj_011,...] [--model sonnet] [--concurrency 8]
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import paths  # noqa: E402
from carve_cams import (FOV_GOOD, RES, WALL_PAD,  # noqa: E402
                        make_cam, top_cam_for)

MODEL = "sonnet"
CONCURRENCY = 8   # user ruling 08-04: lanes are couriers, compute is cloud-side
CALL_TIMEOUT_S = 240
OUTCOMES = ("ONE_BOX", "SPLIT", "UNCLEAR")           # v2.1 — representation
IDENTITIES = ("one_structure", "copies", "distinct")  # v2.1 — annotation
BOX_RULINGS = ("ship_pano", "ship_vote", "either")
FACT_CAP = 8       # unrelated-class fact lines kept, by relevance; same-class
#                    facts are NEVER truncated (the obj_063 rule)

# ---- overlay drawing ----
COL_VOTE = (255, 153, 0)     # orange — boxes.vote2 (matches the cone map)
COL_PANO = (0, 188, 212)     # cyan   — boxes.pano
COL_NOTCH = (255, 40, 40)    # red dashed — the large_empty_notch rectangle
COL_NEIGH = (0, 230, 90)     # green  — a same-class neighbour's carved box
NEAR_Z = 0.05                # clip box edges to this camera-space depth
EYE_TOL = 1e-3               # m — plan-camera reconstruction must match the
#                              eye the carve recorded, or no overlay ships


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


def parse_verdict(text):
    """PARSER v3 — the v2.1 judge reply: {"outcome", "box_ruling"?,
    "identity"?, "count"?, "parts"?, "confidence", "reason"}.

    Conditional-key rules (required EXACTLY when the answer demands them):
      outcome     enum ONE_BOX | SPLIT | UNCLEAR
      box_ruling  required + valid iff outcome == ONE_BOX
      identity    required + valid iff outcome == SPLIT
      count       required positive int iff identity == "copies"
      parts       required non-empty valid list iff identity == "distinct"
                  (accepted, not required, on the other identities)
      confidence  clamped to [0, 1], default 0.5
      reason      string (empty when absent)

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
    if outcome == "ONE_BOX":
        if v.get("box_ruling") not in BOX_RULINGS:
            return None
        out["box_ruling"] = v["box_ruling"]
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
    return out


# ---- relational facts: READ from graph["carved_edges"] -------------------
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


def edge_fact_line(nid, e, names, neighbor_ids):
    """One fact line for one edge of graph['carved_edges'] that touches
    this node — the relation phrased from THIS node's side, with the
    edge's own evidence numbers, plus the J1 verdict when the edge is a
    judged SAME_CANDIDATE."""
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
    return line


def fmt_box(b):
    s = [round(float(h) - float(l), 2) for l, h in zip(b["lo"], b["hi"])]
    return f"{s[0]}x{s[1]}x{s[2]}m"


# ---- box projection (cameras from carve_cams — never re-derived here) ----

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
        return ("plan view — the render the carve ran its top detection on"
                if view == "top" else
                "plan view (clip-top) — camera above the clipped ceiling")
    return view


def build_panels(c, sd, sheets_dir, notes):
    """Write one annotated PNG per existing render of this node. Returns
    [{"file", "view", "caption", "cam_from", "overlay"}]."""
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

    # --- the plan render the carve detected on ---
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
    """Rebuild the plan camera with carve_cams.top_cam_for and VALIDATE
    it against the eye the carve recorded for this node. Returns
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
    # check below decides which one the carve actually used.
    cands = []
    for allow in (True, False):
        got, _c0 = top_cam_for(c["geo"], np.array(c["eye0"], float),
                               c["ceil_y"], WALL_PAD,
                               lambda e, ok=allow: ok, lambda e: 0, 1)
        for cand in got:
            if cand[0] not in [x[0] for x in cands]:
                cands.append(cand)
    rec = {v["view"]: v["eye"] for v in c["cm"]["views"]}
    # eyes the carve itself recorded for a plan standpoint: the top
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
            src.append("eye matches the carve's recorded plan standpoint")
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
            "carve_cams.top_cam_for, validated (" + "; ".join(src) + ")"
    notes.append(f"{nid}: no plan render whose camera validates — plan "
                 "panel omitted")
    return None, None, "no validated plan camera"


def annotate(src_png, sheets_dir, out_name, cam, boxes, notch, caption,
             prov, neighbors=()):
    """Copy a render into the sheet dir with the boxes drawn on it.

    `neighbors` = the SAME-CLASS neighbour nodes' CARVED boxes (verbatim
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
}
# priority: the most specific admitting doubt opens the case
TRIGGER_ORDER = ("large_empty_notch", "pano_vs_cluster", "culled_clusters",
                 "low_plan_fill")

TAXONOMY = """OUTCOME — REPRESENTATION FIRST. Choose exactly ONE:

- ONE_BOX — ONE box represents this node. A BOX RULING IS REQUIRED,
  because which of the two boxes ships is undecidable from geometry alone:
    "ship_pano" — the vote box absorbed a neighbour (the orange box is
                  too big; the cyan pano-filtered box is the object).
    "ship_vote" — the pano cut was occlusion-shaved (the cyan box is a
                  partial view; the orange box is the true extent).
    "either"    — the boxes agree within tolerance.
- SPLIT — one box is NOT enough: this footprint must become >= 2
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

- UNCLEAR — the evidence does not settle it. The shipping default stands
  and the doubt stays open on the record as a work order. Use this rather
  than guessing.

TIEBREAK (design rule): when the parts read as the SAME product, PREFER
identity "copies" over "distinct". Copies is the cheaper claim (one
asset, k placements) and a later same-product judge verifies sameness;
"distinct" requires a VISIBLE identity difference, otherwise it is
unfalsifiable."""

PROMPT = """You are the MULTIPLICITY JUDGE (J8) in a 3D scene-understanding
pipeline. A carve stage repaired one detected object's 3D box by slicing
the splat, re-rendering it from several sides, detecting in each render
and electing the points most cameras agree on. The carve recorded a DOUBT
about this node and cannot settle it from geometry. You settle it.

CASE {nid} — "{name}"  (carve status {status}; escalation {tiers})

{opening}

THE PANELS (image files in this directory — open them; everything you
need is there, do NOT look for any other file):
{panel_list}
Every panel is one of THIS object's own carve renders with 3D boxes
projected on it by the same camera that made the render:
  ORANGE wireframe = the VOTE box (boxes.vote2) — the elected cluster.
  CYAN wireframe   = the PANO box (boxes.pano) — the part of the elected
                     cluster this node's own founding masks vouch for.
                     (Absent when the carve produced no pano box.)
  GREEN wireframe  = a SAME-CLASS NEIGHBOUR node's own carved box,
                     labelled with that neighbour's id. It is a DIFFERENT
                     node of the same class that the graph says touches
                     or overlaps this one — if the extent you are ruling
                     on already belongs to a green box, say so.
                     (Absent when this node has no same-class neighbour.)
  RED DASHED (plan panel only) = the large empty notch rectangle.
The cards are "view tunnels": the full scene is rendered minus the
occluders between the camera and the object, so context is intact and
what sits INSIDE the wireframes is what you are ruling on.

CASE FACTS (meters; y is the height axis, y-DOWN — smaller y is higher):
{facts}

{taxonomy}

Reply with ONE JSON object only, no prose around it:
{{"outcome": "ONE_BOX" | "SPLIT" | "UNCLEAR",
  "box_ruling": "ship_pano" | "ship_vote" | "either",  // ONE_BOX only
  "identity": "one_structure" | "copies" | "distinct", // SPLIT only
  "count": <positive int>,                             // identity "copies" only
  "parts": [{{"name": "<short name>",
             "owner": "this_node" | "existing:<node_id>" |
                      "missing_instance"}}],            // required when
                                                       // identity is "distinct"
  "confidence": <0..1>,
  "reason": "<one or two sentences citing what you SEE in a named panel>"}}
Omit the keys that do not apply to your answer."""


def fmt_rect(r):
    """large_empty_notch rect_m is [x0, z0, x1, z1] — spell the axes out
    so the judge cannot read it as an xyz pair."""
    return f"x {r[0]}..{r[2]} m, z {r[1]}..{r[3]} m"


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
                fill=d.get("fill", 0.0))
    return ("THE DOUBT THAT OPENED THIS CASE: "
            + "; ".join(d.get("text", d["kind"]) for d in c["doubts"]))


def case_facts(c):
    lines = []
    lines.append(f"- carved (shipping) box size: {c['carved_size']}")
    lines.append(f"- original resolved box size: {c['original_size']}")
    lines.append(f"- resolved cluster: {c['n_members']} member "
                 f"detections across views")
    bx = c["cm"]["boxes"]
    if bx.get("vote2"):
        lines.append(f"- ORANGE vote box (boxes.vote2): {fmt_box(bx['vote2'])}"
                     f"  lo {bx['vote2']['lo']} hi {bx['vote2']['hi']}")
    if bx.get("pano"):
        lines.append(f"- CYAN pano box (boxes.pano): {fmt_box(bx['pano'])}"
                     f"  lo {bx['pano']['lo']} hi {bx['pano']['hi']}")
    else:
        lines.append("- CYAN pano box: none produced by the carve")
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
    lines.append("")
    lines.append("RELATIONS — read VERBATIM from the scene graph's own "
                 "edges (re-derived on the CARVED boxes; this judge "
                 "computes no overlaps of its own):")
    lines += c["fact_lines"]
    return "\n".join(lines)


def edge_fact_lines(nid, edges, names, neighbor_ids):
    """The relational fact block for one case. Same-class neighbours are
    listed FIRST and are NEVER truncated (the obj_063 rule); the rest are
    capped at FACT_CAP by relevance, with the count of what was cut said
    out loud so the judge knows the list is not the whole world."""
    touching = edges_touching(nid, edges)
    if not touching:
        return ["- (this node has no edges in the carved-edge layer: it "
                "neither contains, sits in, touches nor duplicates any "
                "other node)"]
    mine = node_class(nid, names)
    same, rest = [], []
    for e in touching:
        o = other_end(nid, e)
        (same if (mine and node_class(o, names) == mine) else rest).append(e)
    rest.sort(key=lambda e: fact_relevance(nid, e), reverse=True)
    kept, cut = rest[:FACT_CAP], rest[FACT_CAP:]
    out = [edge_fact_line(nid, e, names, neighbor_ids) for e in same + kept]
    if cut:
        out.append(f"- (+{len(cut)} further edge(s) of lower relevance not "
                   "listed: "
                   + ", ".join(f"{e['type']} {other_end(nid, e)}"
                               for e in cut) + ")")
    return out


def same_class_neighbors(nid, edges, names, carved_boxes, notes):
    """The SAME-CLASS nodes joined to this node by ANY carved edge, with
    their CARVED boxes verbatim from the preview manifest. These are the
    nodes that get a GREEN wireframe on every panel — only same-class
    neighbours are ever drawn (v2.1)."""
    mine = node_class(nid, names)
    out, seen = [], set()
    if not mine:
        return out
    for e in edges_touching(nid, edges):
        o = other_end(nid, e)
        if o in seen or node_class(o, names) != mine:
            continue
        seen.add(o)
        geo = carved_boxes.get(o)
        if geo is None:
            notes.append(f"{nid}: same-class neighbour {o} has no carved box "
                         "in the preview manifest — NOT drawn")
            continue
        out.append({"id": o, "name": names[o], "via": e["type"],
                    "lo": list(geo[0]), "hi": list(geo[1])})
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


def build_sheet(c, sheets_dir):
    neigh_txt = ", ".join(f"{n['id']} ({n['name']}, via {n['via']})"
                          for n in c["neighbors"]) or (
        "none — this node has no same-class neighbour in the carved edges")
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
<p class='meta'>carve status <b>{c['status']}</b> · escalation
{'→'.join(c['tiers']) or 'none'} · admitting doubts:
{', '.join(d['kind'] for d in c['doubts'])} · {len(c['panels'])}
panel(s)</p>
<p class='legend'>
<span><i class='sw' style='border-color:#ff9900'></i>vote box
(boxes.vote2)</span>
<span><i class='sw' style='border-color:#00bcd4'></i>pano box
(boxes.pano)</span>
<span><i class='sw' style='border-color:#ff2828;border-top-style:dashed'
></i>large_empty_notch rectangle</span>
<span><i class='sw' style='border-color:#00e65a'></i>same-class neighbour
node's carved box (labelled with its id)</span></p>
<p class='meta'>same-class neighbours drawn: {neigh_txt}</p>
<h2>STIMULI — this node's own carve renders, boxes projected by the
camera that made each render</h2>
<div class='grid'>{figs}</div>
<h2>THE PROMPT (verbatim — also written as {c['id']}_prompt.txt)</h2>
<pre>{c['prompt'].replace('&', '&amp;').replace('<', '&lt;')}</pre>
"""
    p = sheets_dir / f"{c['id']}.html"
    p.write_text(html, encoding="utf-8")
    return p.name


def build_index(cases, sheets_dir, scene, notes):
    rows = "".join(
        f"<tr><td><a href='{c['id']}.html'>{c['id']}</a></td>"
        f"<td>{c['name']}</td><td>{c['status']}</td>"
        f"<td>{', '.join(d['kind'] for d in c['doubts'])}</td>"
        f"<td>{len(c['panels'])}</td>"
        f"<td>{'yes' if any(p['caption'].startswith('plan') for p in c['panels']) else 'NO'}</td>"
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
<table><tr><th>case</th><th>name</th><th>carve status</th>
<th>admitting doubts</th><th>panels</th><th>plan overlay</th>
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
    carve = g.get("carve") or {}
    if not carve:
        raise SystemExit("[multiplicity] no carve block — run "
                         "record_carve_doubts.py --apply first")
    nodes = g["resolved"]["nodes"]
    by_id = {n["id"]: n for n in nodes}
    # v2.1: relational facts come from the loop-back's carved-edge layer.
    # No layer -> no facts -> the judge would rule blind, so this is fatal.
    ce = g.get("carved_edges") or {}
    if not ce.get("edges"):
        raise SystemExit("[multiplicity] no graph['carved_edges'] — run "
                         "graph/rederive_carved_edges.py --apply (Phase B2 "
                         "loop-back) first; J8 v2.1 reads its relational "
                         "facts from that layer and computes none itself")
    edges = ce["edges"]
    names = {n["id"]: n["name"] for n in nodes}
    carved_boxes = {}
    prev = sd / "scene_manifest_slicevote_preview.json"
    carved_sizes = {}
    if prev.exists():
        for o in json.loads(prev.read_text())["objects"]:
            carved_boxes[o["id"]] = (o["aabb_min"], o["aabb_max"])
            carved_sizes[o["id"]] = [round(v, 2) for v in o["size"]]
    cm_f = sd / "pool_retake" / "conemap.json"
    if not cm_f.exists():
        raise SystemExit("[multiplicity] no pool_retake/conemap.json — run "
                         "carve_slicevote.py first (the stimuli come from "
                         "its renders + view records)")
    cm_by_id = {o["id"]: o for o in json.loads(
        cm_f.read_text(encoding="utf-8"))["objects"]}
    shell = json.loads((sd / "room_shell.json").read_text())
    eye0 = json.loads((sd / "rig_sp0" / "pano_selfrender_meta.json")
                      .read_text())["eye_raw"]
    # docket: multiplicity-relevant AUTO doubts only (Rule #1).
    # Admission triggers (user 08-07): ownership gap, discarded
    # candidate, shape gap (plan-fill rule 3 / the notch).
    docket = {}
    for nid, cn in carve.get("nodes", {}).items():
        kinds = {d["kind"] for d in cn.get("doubts", [])}
        if kinds & {"pano_vs_cluster", "arm_vs_cluster",   # old name too
                    "culled_clusters", "low_plan_fill",
                    "large_empty_notch"}:
            docket[nid] = cn
    if a.only:
        keep = set(a.only.split(","))
        docket = {k: v for k, v in docket.items() if k in keep}

    sheets_dir = sd / "graph" / "multiplicity_sheets"
    sheets_dir.mkdir(parents=True, exist_ok=True)
    # the v2.1 sheet form supersedes the v2 sheets: wipe, don't mix
    for old in list(sheets_dir.glob("*.png")) + \
            list(sheets_dir.glob("*.html")) + \
            list(sheets_dir.glob("*_prompt.txt")):
        old.unlink()

    notes, cases = [], []
    for nid, cn in sorted(docket.items()):
        rn = by_id.get(nid)
        if rn is None:
            print(f"[multiplicity] {nid}: not in resolved — skipped")
            continue
        if nid not in cm_by_id:
            print(f"[multiplicity] {nid}: not in conemap.json — no carve "
                  "renders, case skipped")
            notes.append(f"{nid}: absent from conemap.json (no renders)")
            continue
        doubts = cn.get("doubts", [])
        c = {"id": nid, "name": rn["name"],
             "status": cn.get("status", "?"),
             "tiers": cn.get("tiers", []),
             "slice": cn.get("slice", "?"),
             "doubts": doubts,
             "geo": rn["geometry"],
             "eye0": eye0,
             "ceil_y": shell["ceiling_y_raw"],
             "cm": cm_by_id[nid],
             "carved_size": carved_sizes.get(nid, "n/a"),
             "original_size": [round(v, 2) for v in rn["geometry"]["size"]],
             "n_members": len(rn.get("members", []))}
        # same-class neighbours joined to this node by ANY carved edge get
        # a GREEN wireframe (v2.1). Their boxes are the carve manifest's,
        # VERBATIM — nothing is recomputed here.
        c["neighbors"] = same_class_neighbors(nid, edges, names,
                                              carved_boxes, notes)
        c["fact_lines"] = edge_fact_lines(
            nid, edges, names, {n["id"] for n in c["neighbors"]})
        c["panels"] = build_panels(c, sd, sheets_dir, notes)
        if not c["panels"]:
            print(f"[multiplicity] {nid}: NO stimulus images found — "
                  "case ships UNCLEAR-by-no-stimulus")
            c["no_stimulus"] = True
        panel_list = "\n".join(
            f"  {p['file']}  — {p['caption']}"
            + ("" if p["overlay"] != "NONE"
               else "   [no boxes drawn: camera not recoverable]")
            for p in c["panels"])
        c["prompt"] = PROMPT.format(
            nid=nid, name=rn["name"], status=c["status"],
            tiers="→".join(c["tiers"]) or "none",
            opening=case_opening(c), panel_list=panel_list,
            facts=case_facts(c), taxonomy=TAXONOMY)
        (sheets_dir / f"{nid}_prompt.txt").write_text(c["prompt"],
                                                      encoding="utf-8")
        c["sheet"] = build_sheet(c, sheets_dir)
        cases.append(c)
        print(f"[multiplicity] {nid:>8} {rn['name']:<12} "
              f"{len(c['panels'])} panel(s) -> {c['sheet']}", flush=True)

    idx = build_index(cases, sheets_dir, a.scene, notes)
    for n in notes:
        print(f"[multiplicity] NOTE: {n}", flush=True)
    print(f"[multiplicity] docket: {len(cases)} case(s) -> {sheets_dir}",
          flush=True)
    print(f"[multiplicity] index: {idx}", flush=True)
    if a.sheets_only:
        print("[multiplicity] sheets-only — zero model calls (USER GATE A1 "
              "reviews the stimuli first)", flush=True)
        return

    cache_f = sd / "graph" / "judge_multiplicity_cache.json"
    cache = json.loads(cache_f.read_text()) if cache_f.exists() else {}

    def case_key(c):
        h = hashlib.sha256()
        h.update(c["prompt"].encode())
        for p in c["panels"]:
            h.update((sheets_dir / p["file"]).read_bytes())
        return h.hexdigest()[:24]

    def run_case(c):
        if c.get("no_stimulus"):
            return {**c, "verdict": {
                "outcome": "UNCLEAR", "confidence": 0.0,
                "reason": "no stimulus images on disk"}, "cached": False}
        k = case_key(c)
        if k in cache:
            return {**c, "verdict": cache[k], "cached": True}
        out = call_claude(c["prompt"], sheets_dir, a.model)
        v = parse_verdict(out)
        if v is None:
            out = call_claude(c["prompt"] + "\n\nREPLY WITH THE JSON OBJECT "
                              "ONLY.", sheets_dir, a.model)
            v = parse_verdict(out)
        if v is None:
            v = {"outcome": "UNCLEAR", "confidence": 0.0,
                 "reason": "malformed model reply x2"}
        v = {**v, "model": a.model, "date": date.today().isoformat()}
        cache[k] = v
        return {**c, "verdict": v, "cached": False}

    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        results = list(ex.map(run_case, cases))
    cache_f.write_text(json.dumps(cache, indent=1))

    out_f = sd / "graph" / "multiplicity.json"
    out_f.write_text(json.dumps({
        "scene": a.scene, "built": date.today().isoformat(),
        "source": "graph/judge_multiplicity.py (J8) — verdicts REFERENCE "
                  "nodes; materialize (Phase C) is the editor. Consumers: "
                  "materialize_carve.py + same-product judge (membership).",
        "cases": [{k: v for k, v in c.items()
                   if k not in ("prompt", "cm", "geo")}
                  for c in results]}, indent=1))
    for c in results:
        v = c["verdict"]
        extra = v.get("box_ruling") or v.get("identity") or ""
        if v.get("count"):
            extra += f"({v['count']})"
        if v.get("parts"):
            extra += " parts " + "/".join(p["owner"] for p in v["parts"])
        print(f"[multiplicity] {c['id']:>8} {c['name']:<14} "
              f"{v['outcome']:<8} {extra:<28} "
              f"conf {v.get('confidence', 0.0):.2f} "
              f"{'(cache)' if c.get('cached') else ''} — "
              f"{v.get('reason', '')[:80]}", flush=True)
    print(f"[multiplicity] -> {out_f}", flush=True)


if __name__ == "__main__":
    main()
