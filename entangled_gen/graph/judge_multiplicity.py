"""MULTIPLICITY JUDGE (J8) — one object or several? (PLAN_CARVE_DOWNSTREAM
Phase A; USER GO 2026-08-07.)

CONTRACT: GETS the carve block's multiplicity docket — AUTO DOUBTS ONLY
(pano_vs_cluster / culled_clusters; Rule #1: no user-routing channel,
the pipeline raises its own questions) — with visual stimuli assembled
from the SAME evidence class the user judged in R-S2-26..30 (cone-map
figure + plan-view/card detection renders).
DECIDES per case: ONE_OBJECT | MULTIPLE (named parts, each covered by
this node / an existing node / a missing instance) | UNCLEAR (ships
open as a work order). It NEVER edits the graph — verdicts land in the
graph/multiplicity.json sidecar; materialize (Phase C) is the editor.
A mistake looks like: splitting a real single object, or blessing one
box that wraps two real instances.

REVIEW-FIRST: --sheets-only builds the case sheets + verbatim prompts
(graph/multiplicity_sheets/) with ZERO model calls — USER GATE A eyeballs
the stimuli before any verdict runs.

Facts each case carries (numbers, not vibes): carve status/tiers,
pano-vs-cluster volume ratio + both boxes, culled-cluster count, carved
vs original size, resolved member count, and WHICH OTHER RESOLVED NODES
overlap the vote-cluster box (the "is the rest of it another existing
object?" evidence).

Box-color legend (drawn by the carve's cone-map renders, stated in the
prompt): gray = original resolved box · red = all-agree strict box ·
orange = gate-3 vote box · cyan = pano-filtered box (the node's founding
pano-funnel masks' share of the elected dots).

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

MODEL = "sonnet"
CONCURRENCY = 8   # user ruling 08-04: lanes are couriers, compute is cloud-side
CALL_TIMEOUT_S = 240
TILE_H = 420
VERDICTS = ("ONE_OBJECT", "MULTIPLE", "UNCLEAR")
OVERLAP_MIN_FRAC = 0.05   # of the smaller box's volume


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


def parse_verdict(text):
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
    if not isinstance(v, dict) or v.get("verdict") not in VERDICTS:
        return None
    if not isinstance(v.get("reason"), str) or not v["reason"].strip():
        return None
    try:
        conf = float(v.get("confidence"))
    except (TypeError, ValueError):
        return None
    parts = v.get("parts") or []
    if v["verdict"] == "MULTIPLE" and not parts:
        return None
    return {"verdict": v["verdict"],
            "n_parts": int(v.get("n_parts") or len(parts) or 1),
            "parts": parts,
            "confidence": round(min(1.0, max(0.0, conf)), 2),
            "reason": v["reason"].strip()}


# ---- geometry helpers ----------------------------------------------------

def box_vol(lo, hi):
    return float(np.prod(np.maximum(np.array(hi) - np.array(lo), 1e-6)))


def overlap_frac(lo_a, hi_a, lo_b, hi_b):
    lo = np.maximum(np.array(lo_a), np.array(lo_b))
    hi = np.minimum(np.array(hi_a), np.array(hi_b))
    if np.any(hi <= lo):
        return 0.0
    inter = float(np.prod(hi - lo))
    return inter / min(box_vol(lo_a, hi_a), box_vol(lo_b, hi_b))


def overlapping_nodes(cluster_box, nid, nodes, carved_boxes):
    out = []
    for n in nodes:
        if n["id"] == nid:
            continue
        geo = carved_boxes.get(n["id"])
        if geo is None:
            geo = (n["geometry"]["aabb_min"], n["geometry"]["aabb_max"])
        f = overlap_frac(cluster_box["lo"], cluster_box["hi"], *geo)
        if f >= OVERLAP_MIN_FRAC:
            out.append((n["id"], n["name"], round(f, 2)))
    return sorted(out, key=lambda x: -x[2])[:6]


# ---- stimuli -------------------------------------------------------------

def case_tiles(pr, nid):
    """Ordered stimulus images that exist for this node (newest carve
    vintage first: plain files are run-4 cache names)."""
    tiles = []
    for name in ([f"conemap_obj_{nid.split('_', 1)[1]}.png"]
                 if nid.startswith("obj_") else []):
        p = pr / name
        if p.exists():
            tiles.append(p)
    for suffix in ("ctop_det", "top_det", "ctop", "top"):
        p = pr / f"{nid}_{suffix}.png"
        if p.exists():
            tiles.append(p)
            break
    cards = sorted(pr.glob(f"{nid}_card?_det.png"))[:2]
    tiles += cards
    return tiles


def build_sheet(tiles, out_png, header):
    ims = []
    for t in tiles:
        im = Image.open(t).convert("RGB")
        w = int(im.width * TILE_H / im.height)
        ims.append((t.name, im.resize((w, TILE_H))))
    if not ims:
        return False
    pad, cap = 6, 16
    W = sum(w for _, im in ims for w in [im.width]) + pad * (len(ims) + 1)
    H = TILE_H + cap * 2 + pad * 2 + 24
    sheet = Image.new("RGB", (W, H), (16, 16, 16))
    dr = ImageDraw.Draw(sheet)
    dr.text((pad, 4), header, fill=(255, 210, 120))
    x = pad
    for name, im in ims:
        sheet.paste(im, (x, 24 + cap))
        dr.text((x, 24), name, fill=(160, 200, 255))
        x += im.width + pad
    sheet.save(out_png)
    return True


# ---- prompt --------------------------------------------------------------

PROMPT = """You are the MULTIPLICITY JUDGE in a 3D scene-understanding
pipeline. One detected object node may actually cover SEVERAL real
objects (two adjacent same-class objects boxed as one; a neighbor's
geometry leaked into the box), or genuinely be ONE object whose
per-view masks disagree. Your verdict is recorded; a later stage edits
the graph. Do NOT invent objects the evidence does not show.

CASE {nid} ("{name}") — carve status {status}, escalation tiers {tiers}.
Facts (meters, y = height):
{facts}

Look at the stimulus sheet image (ONE look should answer it):
  {sheet}
Box colors in the renders: gray = original box, red = strict all-agree
box, orange = gate-3 vote box, cyan = this node's pano-filtered box.
The question: does the ORANGE/GRAY extent contain ONE real object, or
does it wrap several (of which the CYAN pano-filtered box is this
node's true part)?

Reply with ONE JSON object only:
{{"verdict": "ONE_OBJECT" | "MULTIPLE" | "UNCLEAR",
  "n_parts": <int>,
  "parts": [{{"name": "<short name>",
             "covered_by": "this_node" | "existing:<node_id>" |
                            "missing_instance"}}, ...],
  "confidence": <0..1>,
  "reason": "<one or two sentences, cite what you SEE>"}}
parts is required for MULTIPLE (n_parts entries: which real objects the
big extent contains and who owns each — use existing:<id> when a listed
overlapping node already covers it). ONE_OBJECT: parts = []."""


def case_facts(c):
    lines = []
    lines.append(f"- carved (shipping) box size: {c['carved_size']}")
    lines.append(f"- original resolved box size: {c['original_size']}")
    lines.append(f"- resolved cluster: {c['n_members']} member "
                 f"detections across views")
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
        if d["kind"] == "large_empty_notch":
            lines.append(f"- LARGE EMPTY NOTCH: {d['notch_m2']:.2f} m2 "
                         f"contiguous empty rectangle in the footprint "
                         f"(world x/z {d['rect_m']}) — non-box shape (L?)")
    if c["overlaps"]:
        lines.append("- other nodes overlapping the vote-cluster box: "
                     + ", ".join(f"{i} ({n}, {f:.0%} of smaller)"
                                 for i, n, f in c["overlaps"]))
    else:
        lines.append("- no other node overlaps the vote-cluster box")
    return "\n".join(lines)


def fmt_box(b):
    s = [round(float(h) - float(l), 2) for l, h in zip(b["lo"], b["hi"])]
    return f"{s[0]}x{s[1]}x{s[2]}m"


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
    carved_boxes = {}
    prev = sd / "scene_manifest_slicevote_preview.json"
    carved_sizes = {}
    if prev.exists():
        for o in json.loads(prev.read_text())["objects"]:
            carved_boxes[o["id"]] = (o["aabb_min"], o["aabb_max"])
            carved_sizes[o["id"]] = [round(v, 2) for v in o["size"]]
    # docket: multiplicity-relevant AUTO doubts only (Rule #1).
    # Admission triggers (user 08-07): ownership gap, discarded
    # candidate, shape gap (plan-fill rule 3).
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

    pr = sd / "pool_retake"
    sheets_dir = sd / "graph" / "multiplicity_sheets"
    sheets_dir.mkdir(parents=True, exist_ok=True)

    cases = []
    for nid, cn in sorted(docket.items()):
        rn = by_id.get(nid)
        if rn is None:
            print(f"[multiplicity] {nid}: not in resolved — skipped")
            continue
        doubts = cn.get("doubts", [])
        cluster_box = None
        for d in doubts:
            if d.get("cluster_box"):
                cluster_box = d["cluster_box"]
        if cluster_box is None:
            gm = rn["geometry"]
            cluster_box = {"lo": gm["aabb_min"], "hi": gm["aabb_max"]}
        c = {"id": nid, "name": rn["name"],
             "status": cn.get("status", "?"),
             "tiers": cn.get("tiers", []),
             "doubts": doubts,
             "carved_size": carved_sizes.get(nid, "n/a"),
             "original_size": [round(v, 2) for v in rn["geometry"]["size"]],
             "n_members": len(rn.get("members", [])),
             "overlaps": overlapping_nodes(cluster_box, nid, nodes,
                                           carved_boxes)}
        tiles = case_tiles(pr, nid)
        sheet = sheets_dir / f"{nid}.png"
        ok = build_sheet(tiles, sheet,
                         f"{nid} {rn['name']} — multiplicity case "
                         f"({c['status']}; {len(tiles)} views)")
        if not ok:
            print(f"[multiplicity] {nid}: NO stimulus images found — "
                  "case ships UNCLEAR-by-no-stimulus")
            c["no_stimulus"] = True
        c["sheet"] = sheet.name
        c["prompt"] = PROMPT.format(nid=nid, name=rn["name"],
                                    status=c["status"],
                                    tiers="->".join(c["tiers"]) or "none",
                                    facts=case_facts(c), sheet=sheet.name)
        (sheets_dir / f"{nid}_prompt.txt").write_text(c["prompt"],
                                                      encoding="utf-8")
        cases.append(c)

    print(f"[multiplicity] docket: {len(cases)} case(s) -> {sheets_dir}",
          flush=True)
    if a.sheets_only:
        print("[multiplicity] sheets-only — zero model calls (USER GATE A "
              "reviews the stimuli first)", flush=True)
        return

    cache_f = sd / "graph" / "judge_multiplicity_cache.json"
    cache = json.loads(cache_f.read_text()) if cache_f.exists() else {}

    def case_key(c):
        h = hashlib.sha256()
        h.update(c["prompt"].encode())
        sp = sheets_dir / c["sheet"]
        if sp.exists():
            h.update(sp.read_bytes())
        return h.hexdigest()[:24]

    def run_case(c):
        if c.get("no_stimulus"):
            return {**c, "verdict": {
                "verdict": "UNCLEAR", "n_parts": 1, "parts": [],
                "confidence": 0.0,
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
            v = {"verdict": "UNCLEAR", "n_parts": 1, "parts": [],
                 "confidence": 0.0, "reason": "malformed model reply x2"}
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
        "cases": [{k: v for k, v in c.items() if k != "prompt"}
                  for c in results]}, indent=1))
    for c in results:
        v = c["verdict"]
        print(f"[multiplicity] {c['id']:>8} {c['name']:<14} "
              f"{v['verdict']:<10} conf {v['confidence']:.2f} "
              f"{'(cache)' if c.get('cached') else ''} — "
              f"{v['reason'][:80]}", flush=True)
    print(f"[multiplicity] -> {out_f}", flush=True)


if __name__ == "__main__":
    main()
