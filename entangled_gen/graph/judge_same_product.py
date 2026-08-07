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
2. VERDICT (one claude.exe call per group, judge-chain pattern): same
   product? canonical size? Judge may exclude members (a "chair" that is
   really something else stays out of the set).

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

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import paths  # noqa: E402

GROUP_RADIUS = 2.5
ANCHOR_AREA_RATIO = 2.0
CALL_TIMEOUT_S = 180


def claude_env():
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(k, None)   # stale-API-key hijack gotcha (project memory)
    return env


def call_claude(prompt, model):
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("[same_product] claude.exe not on PATH")
    r = subprocess.run([exe, "-p", prompt, "--model", model],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=claude_env(),
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
                               for v in m["geometry"]["center"]]}
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
    if a.dry_run:
        print("[same_product] dry run — no LLM calls, nothing written",
              flush=True)
        return

    results = []
    for gr in groups:
        lines = []
        for m in gr["members"]:
            dstr = (f" [carve doubts: {', '.join(doubts[m['id']])}]"
                    if m["id"] in doubts else "")
            lines.append(f"  {m['id']}: size {m['size']} m (w x h x d), "
                         f"center {m['center']}{dstr}")
        prompt = (
            "You are judging furniture/object instances found in ONE "
            "real room by a noisy 3D reconstruction pipeline.\n"
            f"Group — {len(gr['members'])} objects all detected as "
            f"\"{gr['name']}\""
            + (f", all nearest to the same larger object "
               f"\"{gr['shared_anchor'][1]}\"" if gr["shared_anchor"]
               else "") + ":\n" + "\n".join(lines)
            + "\n\nMeasured sizes vary because reconstruction is noisy. "
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
            verdict = parse_json_obj(call_claude(prompt, a.model))
            if verdict is None:
                raise ValueError("no JSON in judge output")
        except Exception as e:  # noqa: BLE001 — external judge output
            verdict = {"same_object": None, "set_members": None,
                       "canonical_size": None,
                       "reason": f"judge call failed: {e}"}
        results.append({**gr, **verdict})
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
