"""SAME-PRODUCT JUDGE — its own pass in the graph judge chain (USER
RULING 2026-08-06 late: NOT part of the multiplicity judge; a different
question — "same product across separate objects?" vs "one object or
several?").

⚠ STATUS: UNTESTED PROMOTION (cone-map session). Verdicts write a
SIDECAR (graph/same_product.json); nothing consumes it yet. The intended
consumer chain: shopping retrieves ONE asset per SAME_PRODUCT group at
the canonical size. Default is --dry-run-less full mode; use --dry-run
to see groups without any LLM call.

1. CANDIDATE GROUPS (deterministic, scene-agnostic — Rule #1, no class
   lists): same-name resolved nodes, greedy plan-proximity clusters
   (2.5 m), geometric shared-anchor detection (nearest node with >=2x
   footprint area). Sizes prefer the slice-vote carve preview when it
   exists. Carve doubts (graph/carve_doubts.json) ride along as context.
2. CONTACT SHEETS (PLAN_CARVE_DOWNSTREAM.md Phase B upgrade): per group
   one image, graph/same_product_sheets/group_<n>_<label>.png — one row
   per member (id + carved size at left, up to 2 evidence crops resized
   to a uniform 200 px height side by side; crops resolved via the
   judge_pairs.py pattern: resolved node -> source nodes ->
   evidence.members[*].crop under graph/crops/). Plus an index.html.
   Sheets are built in BOTH modes; --dry-run stops after sheets (no LLM
   calls, no same_product.json).
3. VERDICT (one claude.exe call per group, judge-chain pattern): the
   judge OPENS the group's contact sheet (one-look rule — the sheet
   alone answers "do these look like the same product?") plus the size
   facts. Same product? canonical size? Judge may exclude members via
   set_members (a "chair" that is really something else stays out).

⚠ KNOWN OPEN, NOT FIXED HERE (2026-08-08): the ANSWER FORM is unstable
by construction. The judge is asked to name a SUBSET of the group and is
never asked to account for the members it leaves out, and it gets ONE
set slot per group — so a group that is really two products can only be
answered by discarding members. Two runs 20 min apart on near-identical
pillow data returned DISJOINT sets ({obj_024, obj_037} vs {obj_015,
obj_016, obj_026}); both are correct answers to the question as written.
The redesign (assign EVERY member to a set or to "alone", allow more
than one set per group) is the next piece of work — user ruling
2026-08-08: fix the plumbing first, review a sheet, then redesign.

CHAIN ALIGNMENT LANDED 2026-08-08 — J9 was the odd one out on four
mechanical counts, each matched to what J8/J8s already do:
  · VERDICT CACHE (graph/judge_same_product_cache.json, key = prompt +
    contact-sheet bytes). Every other judge had one; J9 re-decided every
    run. This makes a re-run free — it does NOT make the answer right
    (see the open above).
  · MODEL = sonnet (J8/J8s constant). The old default was haiku.
  · NO STIMULUS -> UNCLEAR WITHOUT A CALL. A group whose members have no
    detection crops produced a picture-free sheet and the judge answered
    anyway from the numbers, while the prompt told it to look (living
    group 1, magazine obj_005_c00 + obj_017_c00: pano-cluster nodes,
    evidence.members empty). Members with no photo in a MIXED group are
    now named in the prompt as unseeable and recorded as
    no_photo_members — recorded, not decided.
  · RETRY ONCE, then record. A malformed reply used to be a dead group
    (living group 2, magazine x3: "judge call failed").
  · groups run CONCURRENTLY (the 08-04 parallelism ruling); they were
    strictly sequential.

Run:  python graph/judge_same_product.py --scene living_marble --dry-run
      python graph/judge_same_product.py --scene living_marble
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
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import paths  # noqa: E402

# A STAGE MUST NOT DIE ON ITS OWN LOG LINE (2026-08-08): the closing
# "wrote ... (⚠ UNTESTED)" print raised UnicodeEncodeError under a cp1252
# console AFTER same_product.json was already on disk — the work was done
# and the run still exited non-zero. Same latent bug in carve_slicevote.py
# (≥), graph/build_edges.py (→) and compose/uniform_instances.py (⚠).
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                       # noqa: BLE001 — piped/older
        pass

GROUP_RADIUS = 2.5
ANCHOR_AREA_RATIO = 2.0
MODEL = "sonnet"       # the judge-chain constant (J8, J8s). J9 had been
                       # defaulting to haiku — an undocumented outlier, not
                       # a recorded decision (2026-08-08)
CONCURRENCY = 8        # user ruling 08-04: independent calls run concurrently
CALL_TIMEOUT_S = 600   # s — raised from 180 (2026-08-08): image-heavy
                       # contact sheets legitimately run long
CROPS_PER_MEMBER = 2       # judge_pairs.py pattern: up to 2 crops/node
CROP_H = 200               # uniform crop height on the contact sheet
LABEL_W = 260              # left text column (id + carved size)
PAD = 12


def claude_env():
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(k, None)   # stale-API-key hijack gotcha (project memory)
    return env


def call_claude(prompt, model, cwd=None):
    # cwd MUST be the sheets dir when the prompt references image files:
    # claude -p can only Read within its working directory (the J9
    # first-run failure 2026-08-07 — absolute out-tree paths were
    # unreadable and the model replied prose, not JSON; J8 always
    # passed cwd)
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("[same_product] claude.exe not on PATH")
    r = subprocess.run([exe, "-p", prompt, "--model", model],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=claude_env(),
                       cwd=(str(cwd) if cwd else None),
                       timeout=CALL_TIMEOUT_S)
    out = (r.stdout or "").strip()
    if r.returncode != 0:
        raise RuntimeError(f"claude exit {r.returncode}: "
                           f"{(r.stderr or out)[:400]}")
    low = (out + " " + (r.stderr or "")).lower()
    for bad in ("invalid_api_key", "authentication_error",
                "credit balance"):
        if bad in low:
            raise RuntimeError(f"claude auth/billing error: {out[:400]}")
    return out


def parse_json_obj(text):
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    raw = m.group(1) if m else None
    if raw is None:
        i, j = text.find("{"), text.rfind("}")
        raw = text[i:j + 1] if i >= 0 and j > i else None
    return json.loads(raw) if raw else None


def normalize_ids(raw, member_ids):
    """set_members comes back in whatever shape the judge felt like:
    proper ids ('obj_024'), bare ints (29), or numeric strings ('29').
    Normalise to real node ids of THIS group; drop anything that does not
    resolve (recorded by the caller as a shrunken set, never silently
    invented). Consumers — shopping, materialize — need ids, not digits.
    """
    if not raw:
        return None
    by_num = {}
    for mid in member_ids:
        digits = re.sub(r"\D", "", mid)
        if digits:
            by_num.setdefault(str(int(digits)), mid)
    out = []
    for v in raw:
        s = str(v).strip()
        if s in member_ids:
            out.append(s)
            continue
        d = re.sub(r"\D", "", s)
        hit = by_num.get(str(int(d))) if d else None
        if hit and hit not in out:
            out.append(hit)
    return out or None


def plan_center(geo):
    return np.array([(geo["aabb_min"][0] + geo["aabb_max"][0]) / 2,
                     (geo["aabb_min"][2] + geo["aabb_max"][2]) / 2])


def footprint_area(geo):
    return geo["size"][0] * geo["size"][2]


def find_anchor(node, nodes):
    c = plan_center(node["geometry"])
    area = footprint_area(node["geometry"])
    best, best_d = None, 1e9
    for m in nodes:
        if m["id"] == node["id"]:
            continue
        if footprint_area(m["geometry"]) < ANCHOR_AREA_RATIO * area:
            continue
        d = float(np.linalg.norm(plan_center(m["geometry"]) - c))
        if d < best_d:
            best, best_d = m, d
    return (best["id"], best["name"], round(best_d, 2)) if best else None


def member_crop_paths(res_node, src_nodes, crops_dir):
    """Up to CROPS_PER_MEMBER crops for one resolved node, highest det
    score first — the judge_pairs.py node_crops pattern, walked across
    the resolved node's source nodes (node["evidence"]["members"][*]
    ["crop"])."""
    dets = []
    for sid in res_node.get("members", [res_node["id"]]):
        src = src_nodes.get(sid)
        if src:
            dets += src.get("evidence", {}).get("members", [])
    dets.sort(key=lambda m: -m.get("score", 0.0))
    out = []
    for m in dets:
        p = crops_dir / m.get("crop", "")
        if m.get("crop") and p.exists():
            out.append(p)
        if len(out) == CROPS_PER_MEMBER:
            break
    return out


def sheet_font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:          # older Pillow: no size kwarg
        return ImageFont.load_default()


def build_sheet(gr, crops_by_id, out_path):
    """One contact sheet: one row per member — id + carved size in the
    left column, up to 2 crops (uniform CROP_H height) side by side."""
    font = sheet_font(18)
    font_small = sheet_font(15)
    rows = []
    for m in gr["members"]:
        imgs = []
        for p in crops_by_id.get(m["id"], []):
            im = Image.open(p).convert("RGB")
            w = max(1, round(im.width * CROP_H / im.height))
            imgs.append(im.resize((w, CROP_H)))
        rows.append((m, imgs))
    width = LABEL_W + max((sum(im.width for im in imgs)
                           + PAD * len(imgs) for _, imgs in rows),
                          default=0) + PAD
    height = PAD + len(rows) * (CROP_H + PAD)
    sheet = Image.new("RGB", (max(width, LABEL_W + PAD), height),
                      (245, 245, 245))
    draw = ImageDraw.Draw(sheet)
    y = PAD
    for m, imgs in rows:
        draw.text((PAD, y + 4), m["id"], fill=(0, 0, 0), font=font)
        size_txt = "size " + " x ".join(f"{v:.2f}" for v in m["size"]) \
                   + " m"
        draw.text((PAD, y + 30), size_txt, fill=(60, 60, 60),
                  font=font_small)
        if not imgs:
            draw.text((PAD, y + 56), "NO CROPS", fill=(180, 0, 0),
                      font=font_small)
        x = LABEL_W
        for im in imgs:
            sheet.paste(im, (x, y))
            x += im.width + PAD
        y += CROP_H + PAD
    sheet.save(out_path)


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "group"


# ---- the canonical size: CODE'S JOB, not the judge's ---------------------
# USER RULING 2026-08-08: EXEMPLAR, NOT BLEND. The size shopping buys is ONE
# member's measured box, verbatim.
#
# Why the judge stopped deciding this: its canonical_size was, in all four
# living groups, EXACTLY the per-axis median of the members it kept — it was
# doing arithmetic, and we were taking it on trust. Worse, the per-axis
# median is the WRONG arithmetic: the boxes are aligned to the ROOM's axes,
# not to each object, so one member's width is another's depth (pillow
# obj_026 measured 0.494 x 0.257 on the floor while obj_013/015 measured
# ~0.38 x ~0.46 — same product, axes swapped). And when the members simply
# disagree — the chairs' floor extents spread 0.44 m, with two of the five
# already flagged by the carve — a median launders flagged measurements into
# a confident-looking number. So: pick the member we measured best and copy
# its box. Same shape as the settled J8s ruling (the judge speaks the
# vocabulary; code does the snapping).
#
# The rank is computed WITHIN THE GROUP, against its own members, so no
# global list of "bad" doubt kinds is needed and no threshold is introduced:
# a doubt only counts against a member relative to its group-mates. (Every
# ceiling light carries `exemption` — a blanket "no doubts" rule would have
# disqualified all of them and left the group with no exemplar at all.)
NEVER_MEASURED = ("kept", "kept_outlier")   # the carve shipped the ORIGINAL
#                                             box: no measurement was taken


def plan_long_short(size):
    """The two floor dimensions, largest first. Comparable across members;
    raw w and d are not, because the objects face different ways."""
    return max(size[0], size[2]), min(size[0], size[2])


def canonical_from_exemplar(members, picked, status_by, doubts_by):
    """One member's box, verbatim, plus the disagreement it hides.

    Rank: measured before never-measured, then fewest carve doubts, then
    closest to the set's MEDIAN HEIGHT (height is the one axis that is
    directly comparable — every object shares "up"), then id, so the pick
    is deterministic.
    """
    sizes = {m["id"]: m["size"] for m in members}
    chosen = [p for p in picked if p in sizes]
    if not chosen:
        return None
    heights = sorted(sizes[p][1] for p in chosen)
    n = len(heights)
    med_h = (heights[n // 2] if n % 2 else
             (heights[n // 2 - 1] + heights[n // 2]) / 2)

    def rank(mid):
        return (1 if status_by.get(mid) in NEVER_MEASURED else 0,
                len(doubts_by.get(mid, [])),
                abs(sizes[mid][1] - med_h),
                mid)

    ordered = sorted(chosen, key=rank)
    best = ordered[0]
    best_rank = rank(best)[:2]
    eligible = [m for m in ordered if rank(m)[:2] == best_rank]
    ls = [plan_long_short(sizes[p]) for p in chosen]
    spread = lambda v: round(max(v) - min(v), 3)          # noqa: E731
    med = lambda v: round(sorted(v)[len(v) // 2], 3)      # noqa: E731
    return {
        "canonical_size": [round(float(v), 3) for v in sizes[best]],
        "canonical_size_from": best,
        "canonical_size_rule":
            "EXEMPLAR — this member's measured box, verbatim, in its own "
            "world-axis order (w, h, d). No blending: the members' floor "
            "dimensions are not comparable across differently-facing "
            "objects, and averaging a flagged box into the answer hides "
            "that it was flagged.",
        "canonical_size_basis": {
            "n_members": len(members),
            "n_in_set": len(chosen),
            "n_tied_for_exemplar": len(eligible),
            "tied_for_exemplar": eligible,
            "ranked": [{"id": p, "status": status_by.get(p),
                        "doubts": doubts_by.get(p, []),
                        "size": [round(float(v), 3) for v in sizes[p]]}
                       for p in ordered],
            "set_spread_long_m": spread([a for a, _ in ls]),
            "set_spread_short_m": spread([b for _, b in ls]),
            "set_spread_height_m": spread([sizes[p][1] for p in chosen]),
            "set_median_long_short_height": [med([a for a, _ in ls]),
                                             med([sizes[p][1]
                                                  for p in chosen]),
                                             med([b for _, b in ls])],
            "note": "set_spread_* is how much the members of this set "
                    "disagree, after sorting each member's two floor "
                    "dimensions by size. Large spread does NOT invalidate "
                    "the exemplar — it says the set is not a clean "
                    "measurement, and it is recorded so nothing "
                    "downstream mistakes the chairs for the ceiling "
                    "lights."}}


def build_sheets(groups, nodes, crops_dir, sheets_dir):
    """Build every group's contact sheet. Returns {group_index:
    sheet_path} and prints crop coverage; annotates each group dict with
    its sheet filename and per-member crop counts."""
    src_nodes = nodes  # id -> top-level node (crop evidence lives here)
    sheets_dir.mkdir(parents=True, exist_ok=True)
    sheet_paths = {}
    for i, gr in enumerate(groups, 1):
        crops_by_id = {}
        for m in gr["members"]:
            crops_by_id[m["id"]] = member_crop_paths(
                m["_res_node"], src_nodes, crops_dir)
            m["n_crops"] = len(crops_by_id[m["id"]])
        out_path = sheets_dir / f"group_{i}_{slugify(gr['name'])}.png"
        build_sheet(gr, crops_by_id, out_path)
        gr["sheet"] = out_path.name
        sheet_paths[i] = out_path
        no_crops = [m["id"] for m in gr["members"] if m["n_crops"] == 0]
        cov = ", ".join(f"{m['id']}:{m['n_crops']}"
                        for m in gr["members"])
        print(f"[same_product]   sheet {out_path.name} -- crops {cov}"
              + (f"  WARNING NO CROPS: {no_crops}" if no_crops else ""),
              flush=True)
    return sheet_paths


def write_index(groups, sheets_dir, verdicts=None):
    """The review page. Built in BOTH modes: --dry-run writes the sheets
    alone, a full run writes the same page with each group's verdict
    above its sheet, so one scroll answers "what did the judge say, and
    does the picture support it?"."""
    rows = []
    for i, gr in enumerate(groups, 1):
        cov = ", ".join(f"{m['id']}:{m.get('n_crops', 0)}"
                        for m in gr["members"])
        no_crops = [m["id"] for m in gr["members"]
                    if not m.get("n_crops")]
        v = (verdicts or {}).get(i)
        card = ""
        if v:
            same = v.get("same_object")
            tag = ("SAME PRODUCT" if same is True else
                   "NOT the same product" if same is False else
                   "UNCLEAR / no verdict")
            colour = ("#0a7d28" if same is True else
                      "#8a5a00" if same is False else "#a11")
            picked = v.get("set_members") or []
            left_out = [m["id"] for m in gr["members"]
                        if m["id"] not in picked]
            size = v.get("canonical_size")
            basis = v.get("canonical_size_basis") or {}
            sizeline = ""
            if size and v.get("canonical_size_from"):
                tied = basis.get("n_tied_for_exemplar", 1)
                sizeline = (
                    f'<br>\n<b>buy one at {size} m</b> — copied verbatim '
                    f'from <b>{v["canonical_size_from"]}</b>, the member '
                    f'we measured best'
                    + (f' (one of {tied} equally good; height decided it)'
                       if tied > 1 else "")
                    + f'. The set disagrees by '
                    f'<b>{basis.get("set_spread_long_m")} m</b> on its long '
                    f'floor side, {basis.get("set_spread_short_m")} m on '
                    f'the short one, {basis.get("set_spread_height_m")} m '
                    f'on height. Nothing was averaged.'
                    + (f' <span style="color:#a11">The judge would have '
                       f'said {v["judge_canonical_size"]} — the per-axis '
                       f'median, which mixes one member\'s width with '
                       f'another\'s depth.</span>'
                       if v.get("judge_canonical_size") else ""))
            ranked = basis.get("ranked") or []
            if ranked:
                sizeline += (
                    '<br>\n<small>measured, best first: '
                    + " · ".join(
                        f'<b>{r["id"]}</b> {r["size"]} {r.get("status") or ""}'
                        + (f' [{", ".join(r["doubts"])}]'
                           if r.get("doubts") else "")
                        for r in ranked) + "</small>")
            card = (
                f'<div style="border-left:6px solid {colour};'
                f'padding:6px 12px;margin:8px 0;background:#fafafa">'
                f'<b style="color:{colour}">{tag}</b>'
                + (sizeline if sizeline else
                   (f' — buy one at <b>{size}</b> m' if size else ""))
                + "<br>\n"
                f'<b>in the set ({len(picked)}):</b> '
                f'{", ".join(picked) if picked else "—"}<br>\n'
                f'<b>left out ({len(left_out)}):</b> '
                f'{", ".join(left_out) if left_out else "—"}'
                + (' <i>— nothing downstream is told why. The answer form '
                   'does not ask for a per-member decision, so anything '
                   'the reason says about these is volunteered, and only '
                   'the members in the set get a size to buy.</i>'
                   if left_out else "") + '<br>\n'
                f'<b>reason:</b> {v.get("reason", "")}<br>\n'
                f'<small>{v.get("model", "")} · {v.get("date", "")} · '
                f'{"from cache" if v.get("_cached") else "fresh call"}'
                + (f' · attempts {v["attempts"]}'
                   if v.get("attempts") else "")
                + (f' · <b>no photo: {", ".join(v["no_photo_members"])}'
                   f'</b>' if v.get("no_photo_members") else "")
                + "</small></div>\n")
        rows.append(
            f"<h2>group {i} — {gr['name']} "
            f"({len(gr['members'])} members)</h2>\n" + card
            + f"<p>crops per member: {cov}"
            + (f" — <b>NO CROPS: {', '.join(no_crops)}</b>"
               if no_crops else "") + "</p>\n"
            f'<img src="{gr["sheet"]}" style="max-width:100%">\n')
    (sheets_dir / "index.html").write_text(
        "<!doctype html><meta charset='utf-8'>"
        "<title>same-product contact sheets</title>\n"
        "<style>body{font:15px/1.5 system-ui,sans-serif;max-width:1100px;"
        "margin:24px auto;padding:0 16px}</style>\n"
        "<h1>Same-product judge (J9) — candidate groups</h1>\n"
        "<p>Each group is a set of objects with the same name sitting "
        "near each other. The judge answers: are these the same product, "
        "which ones belong, and what one size should be bought.</p>\n"
        + ("<p><b>Sheets only — no verdicts in this file.</b></p>\n"
           if not verdicts else "")
        + "\n".join(rows), encoding="utf-8")
    print(f"[same_product] wrote {sheets_dir / 'index.html'}", flush=True)


def candidate_groups(nodes, carved):
    by_name = {}
    for n in nodes:
        by_name.setdefault(n["name"], []).append(n)
    groups = []
    for name, members in by_name.items():
        if len(members) < 2:
            continue
        left = list(members)
        while left:
            seed = left.pop(0)
            cluster = [seed]
            changed = True
            while changed:
                changed = False
                cen = np.mean([plan_center(m["geometry"])
                               for m in cluster], axis=0)
                for m in list(left):
                    if np.linalg.norm(plan_center(m["geometry"])
                                      - cen) <= GROUP_RADIUS:
                        cluster.append(m)
                        left.remove(m)
                        changed = True
            if len(cluster) < 2:
                continue
            anchors = [find_anchor(m, nodes) for m in cluster]
            anchor_ids = {x[0] for x in anchors if x}
            groups.append({
                "name": name,
                "members": [{
                    "id": m["id"],
                    "size": carved.get(m["id"], m["geometry"]["size"]),
                    "center": [round(float(v), 2)
                               for v in m["geometry"]["center"]],
                    "_res_node": m}  # sheet crop lookup; not serialized
                    for m in cluster],
                "shared_anchor": (anchors[0] if len(anchor_ids) == 1
                                  and anchors[0] else None)})
    return groups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--concurrency", type=int, default=CONCURRENCY)
    ap.add_argument("--no-cache", action="store_true",
                    help="ignore cached verdicts (re-ask every group) — "
                         "the stability probe")
    a = ap.parse_args()
    sd = paths.scene_dir(a.scene)
    g = json.loads((sd / "scene_graph.json").read_text(encoding="utf-8"))
    nodes = g["resolved"]["nodes"]
    carved = {}
    prev = sd / "scene_manifest_slicevote_preview.json"
    if prev.exists():
        for o in json.loads(prev.read_text())["objects"]:
            carved[o["id"]] = o["size"]
    doubts = {}
    df = sd / "graph" / "carve_doubts.json"
    if df.exists():
        for nd in json.loads(df.read_text())["nodes"]:
            doubts[nd["id"]] = [d["kind"] for d in nd["doubts"]]

    groups = candidate_groups(nodes, carved)
    print(f"[same_product] {len(groups)} candidate group(s)", flush=True)
    for gr in groups:
        print(f"[same_product]   {gr['name']}: "
              f"{[m['id'] for m in gr['members']]} "
              f"anchor={gr['shared_anchor']}", flush=True)

    src_nodes = {n["id"]: n for n in g["nodes"]}  # crop evidence here
    crops_dir = sd / "graph" / "crops"
    sheets_dir = sd / "graph" / "same_product_sheets"
    sheet_paths = build_sheets(groups, src_nodes, crops_dir, sheets_dir)

    if a.dry_run:
        write_index(groups, sheets_dir)
        print("[same_product] dry run — sheets built, no LLM calls, "
              "no same_product.json", flush=True)
        return

    cache_f = sd / "graph" / "judge_same_product_cache.json"
    cache = (json.loads(cache_f.read_text(encoding="utf-8"))
             if cache_f.exists() and not a.no_cache else {})

    def build_prompt(gi, gr):
        lines = []
        for m in gr["members"]:
            dstr = (f" [carve doubts: {', '.join(doubts[m['id']])}]"
                    if m["id"] in doubts else "")
            seen = "" if m.get("n_crops") else " [NO PHOTO on the sheet]"
            lines.append(f"  {m['id']}: size {m['size']} m (w x h x d), "
                         f"center {m['center']}{dstr}{seen}")
        blind = [m["id"] for m in gr["members"] if not m.get("n_crops")]
        return (
            "You are judging furniture/object instances found in ONE "
            "real room by a noisy 3D reconstruction pipeline.\n"
            f"First open the contact sheet image "
            f"{Path(sheet_paths[gi]).name} (in your working directory) — "
            "each row is one member's photos (its id and carved size "
            "are printed at the left of the row).\n"
            f"Group — {len(gr['members'])} objects all detected as "
            f"\"{gr['name']}\""
            + (f", all nearest to the same larger object "
               f"\"{gr['shared_anchor'][1]}\"" if gr["shared_anchor"]
               else "") + ":\n" + "\n".join(lines)
            + (f"\n\nNOTE — no photograph exists for {', '.join(blind)}: "
               "that row of the sheet is empty. You cannot see "
               + ("it" if len(blind) == 1 else "them")
               + ", so say so in your reason rather than deciding from "
                 "the numbers alone.\n" if blind else "")
            + "\n\nJudge from what the objects LOOK like in the sheet "
            "first; use the numbers to pick the canonical size. "
            "Measured sizes vary because reconstruction is noisy. "
            "Question: would these plausibly be THE SAME PRODUCT (a "
            "matched set, e.g. dining chairs around one table)? Exclude "
            "members that don't fit the set. If a set exists, choose ONE "
            "canonical size (favor the median of plausible measurements; "
            "ignore obvious outliers).\n"
            "Answer STRICT JSON only:\n"
            "{\"same_object\": true|false, "
            "\"set_members\": [ids] or null, "
            "\"canonical_size\": [w, h, d] or null, "
            "\"reason\": \"one sentence\"}")

    def group_key(gi, prompt):
        h = hashlib.sha256()
        h.update(prompt.encode())
        h.update(Path(sheet_paths[gi]).read_bytes())
        return h.hexdigest()[:24]

    def run_group(item):
        gi, gr = item
        blind = [m["id"] for m in gr["members"] if not m.get("n_crops")]
        # NO STIMULUS -> NO CALL (the J8 rule). A sheet with no photo on
        # ANY row cannot answer a question about what things look like;
        # answering from the numbers is what produced the living-room
        # magazine verdict on an empty picture.
        if len(blind) == len(gr["members"]):
            return gi, {"same_object": None, "set_members": None,
                        "canonical_size": None,
                        "no_photo_members": blind,
                        "reason": "no photos on the contact sheet — every "
                                  "row is empty, so there is nothing to "
                                  "look at (not asked)",
                        "model": None, "date": date.today().isoformat(),
                        "attempts": 0, "_cached": False}
        prompt = build_prompt(gi, gr)
        k = group_key(gi, prompt)
        if k in cache:
            return gi, {**cache[k], "_cached": True}

        # A call failure is a failed ATTEMPT, never a crash and never a
        # dead group: retry once telling it to reply with JSON only, then
        # record the failure (the J8 pattern).
        def attempt(p):
            try:
                v = parse_json_obj(call_claude(
                    p, a.model, cwd=Path(sheet_paths[gi]).parent))
                if v is None:
                    raise ValueError("no JSON in judge output")
                return v, None
            except Exception as e:              # noqa: BLE001
                return None, f"{type(e).__name__}: {str(e)[:160]}"

        v, err = attempt(prompt)
        tries = 1
        if v is None:
            v, err2 = attempt(prompt + "\n\nREPLY WITH THE JSON OBJECT "
                                       "ONLY.")
            err = err2 or err
            tries = 2
        if v is None:
            v = {"same_object": None, "set_members": None,
                 "canonical_size": None,
                 "reason": f"judge call failed x{tries} — {err}"}
        v["set_members"] = normalize_ids(
            v.get("set_members"), [m["id"] for m in gr["members"]])
        if blind:
            v["no_photo_members"] = blind
        v = {**v, "model": a.model, "date": date.today().isoformat(),
             "attempts": tries}
        cache[k] = v
        return gi, {**v, "_cached": False}

    print(f"[same_product] judging {len(groups)} group(s), model "
          f"{a.model}, concurrency {a.concurrency}"
          + (" (cache ignored)" if a.no_cache else ""), flush=True)
    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        got = dict(ex.map(run_group, list(enumerate(groups, 1))))

    cache_f.write_text(json.dumps(cache, indent=1), encoding="utf-8")

    # THE SIZE IS COMPUTED HERE, AFTER THE VERDICT AND OUTSIDE THE CACHE.
    # The prompt still ASKS for canonical_size and we still record what it
    # said (judge_canonical_size) — not because we use it, but because
    # dropping the ask would change the prompt, miss every cached verdict,
    # and re-decide the classification the user has already accepted. The
    # ask goes away when the answer form is redesigned.
    status_by = {}
    cnodes = (g.get("carve") or {}).get("nodes") or {}
    if isinstance(cnodes, dict):
        for nid, c in cnodes.items():
            if isinstance(c, dict):
                status_by[nid] = c.get("status")

    results = []
    for gi, gr in enumerate(groups, 1):
        verdict = dict(got[gi])
        if verdict.get("same_object") and verdict.get("set_members"):
            sized = canonical_from_exemplar(gr["members"],
                                            verdict["set_members"],
                                            status_by, doubts)
            if sized:
                verdict["judge_canonical_size"] = verdict.get(
                    "canonical_size")
                verdict.update(sized)
        gr_out = {**gr, "members": [
            {k: v for k, v in m.items() if k != "_res_node"}
            for m in gr["members"]]}
        results.append({**gr_out,
                        **{k: v for k, v in verdict.items()
                           if k != "_cached"}})
        got[gi] = verdict
        src = (f" from {verdict['canonical_size_from']}"
               if verdict.get("canonical_size_from") else "")
        print(f"[same_product]   {gr['name']}: "
              f"same={verdict.get('same_object')} "
              f"size={verdict.get('canonical_size')}{src} "
              f"{'(cache)' if verdict.get('_cached') else ''} — "
              f"{verdict.get('reason')}", flush=True)

    write_index(groups, sheets_dir, got)
    outd = sd / "graph"
    outd.mkdir(exist_ok=True)
    out = outd / "same_product.json"
    out.write_text(json.dumps(
        {"scene": a.scene, "status": "UNTESTED",
         "source": "graph/judge_same_product.py — SAME-PRODUCT pass "
                   "(own judge-chain pass per user ruling 2026-08-06); "
                   "consumer (shopping) NOT wired",
         "known_open": "THE ANSWER FORM IS UNSTABLE: the judge names a "
                       "SUBSET and never accounts for the members it "
                       "leaves out, and each group gets ONE set slot. "
                       "Redesign pending (2026-08-08).",
         "groups": results}, indent=1))
    print(f"[same_product] wrote {out} (⚠ UNTESTED)", flush=True)
    print(f"[same_product] cache: {cache_f}", flush=True)


if __name__ == "__main__":
    main()
