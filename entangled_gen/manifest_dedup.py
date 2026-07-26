"""Duplicate-box merge — post-processing step 2 (after manifest_filter.py).

Design settled with user 2026-07-26:
  - Two distinct rigid objects cannot occupy the same 3D volume, so high
    mutual overlap = ONE object detected twice; only the LABEL is ambiguous.
    Merge geometry, keep every label (primary = highest-scoring member,
    rest -> alt_labels). Box-in-box nesting (book inside bookshelf) has
    high containment but LOW IoU, so an IoU gate lets it through untouched.
  - CONFIDENT zone: IoU >= 0.60 -> merge, no model involved.
  - GRAY zone: 0.40 <= IoU < 0.60 AND containment >= 0.90 -> geometry
    cannot tell "same object twice" from "part of the other" — ask an LLM
    about the LABEL pair (claude.exe haiku, ONE batched call per scene,
    verdicts cached to dedup_llm_cache.json). Merge only on verdict "same".
  - NO hard-coded synonym/label lists anywhere (user rule: the pipeline
    must run on all scenes unmodified; local LLM is the someday-swap for
    users who avoid online calls). If the LLM is unavailable or a verdict
    fails to parse, degrade conservatively: keep both boxes.
  - Everything else kept; near-misses (IoU >= 0.25, unmerged) printed and
    stored in the output as overlap_report for user review.

Run:  python manifest_dedup.py --scene bedroom_marble
Out:  <manifest stem>_dd.json   (merged; removed members preserved under
      "dedup_removed", each pointing at its survivor)
"""
import argparse
import json
import os
import shutil
import subprocess

import paths

MODEL = "haiku"
CALL_TIMEOUT_S = 240
IOU_MERGE = 0.60
IOU_GRAY = 0.40
CONTAIN_GRAY = 0.90
IOU_REPORT = 0.25

LLM_PROMPT = """An object detector working on 3D scans of indoor scenes produced pairs of 3D bounding boxes that overlap almost entirely (geometry stats given per pair). Two distinct rigid objects cannot occupy the same volume, so each pair is either:
  - "same": two detections of ONE physical object under two names (e.g. a ceiling fixture detected as both "lamp" and "ceiling light"), OR
  - "part": one box is a component/sub-part or sub-region of the other object (e.g. a "shelf" board that is part of a "bookshelf", a row of "book" spines on a "shelf") — both boxes describe real, different-granularity things.

For each pair below, answer with your best judgment of the MOST PLAUSIBLE case.

{pairs}

Output ONLY a JSON array, one object per pair, no other text:
[{{"a": "<label a>", "b": "<label b>", "verdict": "same"}} , ...]"""


# ---------------- geometry --------------------------------------------------

def vol(o):
    a, b = o["aabb_min"], o["aabb_max"]
    return max(0.0, (b[0] - a[0]) * (b[1] - a[1]) * (b[2] - a[2]))


def inter(o1, o2):
    v = 1.0
    for i in range(3):
        lo = max(o1["aabb_min"][i], o2["aabb_min"][i])
        hi = min(o1["aabb_max"][i], o2["aabb_max"][i])
        if hi <= lo:
            return 0.0
        v *= hi - lo
    return v


def pair_stats(o1, o2):
    V = inter(o1, o2)
    if V <= 0:
        return 0.0, 0.0
    v1, v2 = vol(o1), vol(o2)
    return V / (v1 + v2 - V), V / min(v1, v2)


# ---------------- LLM bridge (claude.exe, same contract as vocab_build) -----

def claude_env():
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(k, None)   # stale-API-key hijack gotcha (project memory)
    return env


def call_claude(prompt, cwd):
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("claude(.exe) not on PATH")
    r = subprocess.run([exe, "-p", prompt, "--model", MODEL],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=claude_env(), cwd=str(cwd),
                       timeout=CALL_TIMEOUT_S)
    out = (r.stdout or "").strip()
    if r.returncode != 0:
        raise RuntimeError(f"claude exit {r.returncode}: "
                           f"{(r.stderr or out)[:400]}")
    return out


def parse_verdicts(raw):
    """Find the JSON array in the output; {} on any failure (conservative)."""
    s, e = raw.find("["), raw.rfind("]")
    if s < 0 or e <= s:
        return {}
    try:
        arr = json.loads(raw[s:e + 1])
    except json.JSONDecodeError:
        return {}
    out = {}
    for it in arr:
        if (isinstance(it, dict) and it.get("verdict") in ("same", "part")
                and it.get("a") and it.get("b")):
            out[pair_key(it["a"], it["b"])] = it["verdict"]
    return out


def pair_key(a, b):
    return " | ".join(sorted((str(a).lower(), str(b).lower())))


def judge_labels(pairs, sdir, skip_llm):
    """pairs: [(la, lb, iou, contain)] -> {pair_key: 'same'|'part'}.
    Cached in <scene>/dedup_llm_cache.json; ONE batched call for misses."""
    cache_f = sdir / "dedup_llm_cache.json"
    cache = json.loads(cache_f.read_text()) if cache_f.exists() else {}
    todo = [(la, lb, i, c) for la, lb, i, c in pairs
            if pair_key(la, lb) not in cache]
    if todo and not skip_llm:
        lines = [f'- "{la}" vs "{lb}"  (IoU {i:.2f}, smaller box '
                 f"{c:.0%} inside larger)" for la, lb, i, c in todo]
        try:
            raw = call_claude(LLM_PROMPT.format(pairs="\n".join(lines)), sdir)
            got = parse_verdicts(raw)
            missing = [pair_key(la, lb) for la, lb, _, _ in todo
                       if pair_key(la, lb) not in got]
            if missing:
                print(f"[dedup] LLM answered {len(got)}/{len(todo)} pairs; "
                      f"unanswered kept unmerged: {missing}")
            cache.update(got)
            cache_f.write_text(json.dumps(cache, indent=2))
            print(f"[dedup] LLM verdicts: {len(got)} new, cached -> "
                  f"{cache_f.name}")
        except Exception as ex:                       # degrade: keep boxes
            print(f"[dedup] LLM unavailable ({ex}); gray zone kept unmerged")
    elif todo:
        print(f"[dedup] --skip-llm: {len(todo)} gray pairs kept unmerged")
    return cache


# ---------------- merge -----------------------------------------------------

def merge_group(members):
    members = sorted(members, key=lambda o: -o["score"])
    head = members[0]
    m = dict(head)
    m["aabb_min"] = [min(o["aabb_min"][i] for o in members) for i in range(3)]
    m["aabb_max"] = [max(o["aabb_max"][i] for o in members) for i in range(3)]
    m["center"] = [(m["aabb_min"][i] + m["aabb_max"][i]) / 2 for i in range(3)]
    m["size"] = [m["aabb_max"][i] - m["aabb_min"][i] for i in range(3)]
    m["id"] = min(o["id"] for o in members)
    alt = [o["label"] for o in members if o["label"] != head["label"]]
    if alt:
        m["alt_labels"] = sorted(set(alt))
    m["views"] = sorted({v for o in members for v in o.get("views", [])})
    m["members"] = [x for o in members for x in o.get("members", [])]
    m["n_detections"] = sum(o.get("n_detections", 0) for o in members)
    m["flags"] = sorted({f for o in members
                         for f in o.get("flags", [])} | {"dedup_merged"})
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--manifest", default="scene_manifest_pano2c_rc_f30.json")
    ap.add_argument("--skip-llm", action="store_true")
    a = ap.parse_args()
    sd = paths.scene_dir(a.scene)
    src = sd / a.manifest
    man = json.loads(src.read_text())
    objs = man["objects"]

    confident, gray, report = [], [], []
    for i in range(len(objs)):
        for j in range(i + 1, len(objs)):
            iou, con = pair_stats(objs[i], objs[j])
            if iou >= IOU_MERGE:
                confident.append((i, j, iou, con))
            elif iou >= IOU_GRAY and con >= CONTAIN_GRAY:
                gray.append((i, j, iou, con))
            elif iou >= IOU_REPORT:
                report.append((i, j, iou, con))

    verdicts = judge_labels(
        [(objs[i]["label"], objs[j]["label"], iou, con)
         for i, j, iou, con in gray], sd, a.skip_llm)

    edges = [(i, j) for i, j, _, _ in confident]
    for i, j, iou, con in gray:
        v = verdicts.get(pair_key(objs[i]["label"], objs[j]["label"]))
        if v == "same":
            edges.append((i, j))
        else:
            report.append((i, j, iou, con))

    parent = list(range(len(objs)))                    # union-find

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, j in edges:
        parent[find(i)] = find(j)

    groups = {}
    for i in range(len(objs)):
        groups.setdefault(find(i), []).append(objs[i])

    merged, removed = [], []
    for g in groups.values():
        m = merge_group(g) if len(g) > 1 else g[0]
        merged.append(m)
        for o in g:
            if len(g) > 1 and o["id"] != m["id"]:
                d = dict(o)
                d["merged_into"] = m["id"]
                removed.append(d)
    merged.sort(key=lambda o: o["id"])

    rep = [{"a": objs[i]["id"], "a_label": objs[i]["label"],
            "b": objs[j]["id"], "b_label": objs[j]["label"],
            "iou": round(iou, 3), "containment": round(con, 3)}
           for i, j, iou, con in sorted(report, key=lambda r: -r[2])]

    out = sd / f"{src.stem}_dd.json"
    out.write_text(json.dumps(
        {"scene": man.get("scene", a.scene),
         "source": f"manifest_dedup.py — {a.manifest}: IoU>={IOU_MERGE} "
                   f"merge + LLM-judged gray zone ({IOU_GRAY}-{IOU_MERGE}, "
                   f"containment>={CONTAIN_GRAY})",
         "frame": man["frame"],
         "n_objects": len(merged),
         "objects": merged,
         "refuted": man.get("refuted", []),
         "filtered_out": man.get("filtered_out", []),
         "dedup_removed": removed,
         "overlap_report": rep}, indent=2))

    print(f"[dedup] {src.name}: {len(objs)} -> {len(merged)} objects "
          f"({len(confident)} confident pairs, {len(gray)} gray pairs, "
          f"{len(removed)} boxes absorbed) -> {out.name}")
    for m in merged:
        if "dedup_merged" in m.get("flags", []):
            print(f"  = {m['id']} {m['label']} "
                  f"(+ {', '.join(m.get('alt_labels', [])) or 'same label'})")
    if rep:
        print(f"[dedup] kept-but-overlapping (review list, IoU>={IOU_REPORT}):")
        for r in rep:
            print(f"  ? {r['a']} {r['a_label']} <-> {r['b']} {r['b_label']} "
                  f"IoU {r['iou']}")


if __name__ == "__main__":
    main()
