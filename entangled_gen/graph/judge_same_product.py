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

Run:  python graph/judge_same_product.py --scene living_marble --dry-run
      python graph/judge_same_product.py --scene living_marble
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import paths  # noqa: E402

GROUP_RADIUS = 2.5
ANCHOR_AREA_RATIO = 2.0
CALL_TIMEOUT_S = 180
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


def build_sheets(groups, nodes, crops_dir, sheets_dir):
    """Build every group's contact sheet + index.html. Returns
    {group_index: sheet_path} and prints crop coverage; annotates each
    group dict with its sheet filename and per-member crop counts."""
    src_nodes = nodes  # id -> top-level node (crop evidence lives here)
    sheets_dir.mkdir(parents=True, exist_ok=True)
    sheet_paths = {}
    index_rows = []
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
        index_rows.append(
            f"<h2>group {i} — {gr['name']} "
            f"({len(gr['members'])} members)</h2>\n"
            f"<p>crops per member: {cov}"
            + (f" — <b>NO CROPS: {', '.join(no_crops)}</b>"
               if no_crops else "") + "</p>\n"
            f'<img src="{out_path.name}" style="max-width:100%">\n')
    (sheets_dir / "index.html").write_text(
        "<!doctype html><meta charset='utf-8'>"
        "<title>same-product contact sheets</title>\n"
        "<h1>same-product candidate groups</h1>\n"
        + "\n".join(index_rows), encoding="utf-8")
    print(f"[same_product] wrote {sheets_dir / 'index.html'}", flush=True)
    return sheet_paths


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
    ap.add_argument("--model", default="haiku")
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
        print("[same_product] dry run — sheets built, no LLM calls, "
              "no same_product.json", flush=True)
        return

    results = []
    for gi, gr in enumerate(groups, 1):
        lines = []
        for m in gr["members"]:
            dstr = (f" [carve doubts: {', '.join(doubts[m['id']])}]"
                    if m["id"] in doubts else "")
            lines.append(f"  {m['id']}: size {m['size']} m (w x h x d), "
                         f"center {m['center']}{dstr}")
        prompt = (
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
        try:
            verdict = parse_json_obj(
                call_claude(prompt, a.model,
                            cwd=Path(sheet_paths[gi]).parent))
            if verdict is None:
                raise ValueError("no JSON in judge output")
        except Exception as e:  # noqa: BLE001 — external judge output
            verdict = {"same_object": None, "set_members": None,
                       "canonical_size": None,
                       "reason": f"judge call failed: {e}"}
        gr_out = {**gr, "members": [
            {k: v for k, v in m.items() if k != "_res_node"}
            for m in gr["members"]]}
        results.append({**gr_out, **verdict})
        print(f"[same_product]   {gr['name']}: "
              f"same={verdict.get('same_object')} "
              f"size={verdict.get('canonical_size')} — "
              f"{verdict.get('reason')}", flush=True)

    outd = sd / "graph"
    outd.mkdir(exist_ok=True)
    out = outd / "same_product.json"
    out.write_text(json.dumps(
        {"scene": a.scene, "status": "UNTESTED",
         "source": "graph/judge_same_product.py — SAME-PRODUCT pass "
                   "(own judge-chain pass per user ruling 2026-08-06); "
                   "consumer (shopping) NOT wired",
         "groups": results}, indent=1))
    print(f"[same_product] wrote {out} (⚠ UNTESTED)", flush=True)


if __name__ == "__main__":
    main()
