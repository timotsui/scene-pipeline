"""Duplicate-box merge — RETIRED FROM THE PIPELINE (2026-07-26 late).

USER AMENDMENT (same evening as the geometry-only rework below): the record
keeps BOTH objects of every duplicate-suspect pair and states the
relationship faithfully — graph/build_edges.py computes SAME_CANDIDATE
edges (zone "confident" IoU>=0.6 / "gray" IoU .40-.60 + containment>=.90)
directly from the f30 manifest's boxes, and MERGING IS A JUDGE VERDICT
(pass 2), never a manifest operation. So no dedup stage exists anymore:
graph/build_graph.py reads scene_manifest_*_f30.json directly. This script
is kept runnable for reference only; nothing consumes its output.

--- retired docstring (geometry-only rework, earlier same day) ---

GEOMETRY-ONLY since 2026-07-26 (user decision "all semantics to graph",
R9 pass; design settled as record-then-judge — PLAN_SCENE_GRAPH.md §0a):

  - Two distinct rigid objects cannot occupy the same 3D volume, so high
    mutual overlap = ONE object detected twice; only the LABEL is ambiguous.
    CONFIDENT zone IoU >= 0.60 -> merge geometry, keep every label
    (primary = highest-scoring member, rest -> alt_labels,
    label_provisional: true — the NAME is NOT decided here; the scene-graph
    judge's naming pass picks the canonical name from crops + facts).
  - GRAY zone (0.40 <= IoU < 0.60 AND containment >= 0.90): geometry cannot
    tell "same object twice" from "part of the other". NOT judged here —
    emitted verbatim as the "deferred_semantic" queue; the scene-graph
    record turns each pair into a SAME_CANDIDATE edge and the judge pass
    (VLM with both nodes' crops + label multisets + edge facts) resolves it.
    The former in-line LLM call and dedup_llm_cache.json are RETIRED.
  - Box-in-box nesting (book inside bookshelf) has high containment but LOW
    IoU, so the IoU gate lets it through untouched.
  - NO hard-coded synonym/label lists anywhere (user rule: the pipeline
    must run on all scenes unmodified).
  - Everything else kept; near-misses (IoU >= 0.25, unmerged) printed and
    stored in the output as overlap_report for user review.

Output contract (consumed by graph/build_graph.py — the record builder):
  <manifest stem>_dd.json with
    objects            merged set; merged nodes carry alt_labels +
                       label_provisional + flag "dedup_merged"
    dedup_removed      absorbed boxes, each pointing at its survivor
    deferred_semantic  [{a, a_label, b, b_label, iou, containment}] —
                       ids are SURVIVOR ids (post-merge); pairs whose two
                       members ended up in one confident group are dropped
    overlap_report     kept-but-overlapping pairs (IoU >= 0.25), review list

Run:  python manifest_dedup.py --scene bedroom_marble
"""
import argparse
import json

import paths

IOU_MERGE = 0.60
IOU_GRAY = 0.40
CONTAIN_GRAY = 0.90
IOU_REPORT = 0.25


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
    # the primary label is a placeholder, NOT a decision (naming = judge pass)
    m["label_provisional"] = True
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

    parent = list(range(len(objs)))                    # union-find
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, j, _, _ in confident:
        parent[find(i)] = find(j)

    groups = {}
    for i in range(len(objs)):
        groups.setdefault(find(i), []).append(objs[i])

    merged, removed = [], []
    survivor = {}                       # original id -> surviving id
    for g in groups.values():
        m = merge_group(g) if len(g) > 1 else g[0]
        merged.append(m)
        for o in g:
            survivor[o["id"]] = m["id"]
            if len(g) > 1 and o["id"] != m["id"]:
                d = dict(o)
                d["merged_into"] = m["id"]
                removed.append(d)
    merged.sort(key=lambda o: o["id"])

    # gray zone -> deferred queue, ids remapped to survivors; pairs whose
    # members ended up merged anyway (via a confident chain) are dropped
    deferred = []
    for i, j, iou, con in sorted(gray, key=lambda g: -g[2]):
        sa, sb = survivor[objs[i]["id"]], survivor[objs[j]["id"]]
        if sa == sb:
            continue
        deferred.append({"a": sa, "a_label": objs[i]["label"],
                         "b": sb, "b_label": objs[j]["label"],
                         "iou": round(iou, 3), "containment": round(con, 3)})

    rep = [{"a": objs[i]["id"], "a_label": objs[i]["label"],
            "b": objs[j]["id"], "b_label": objs[j]["label"],
            "iou": round(iou, 3), "containment": round(con, 3)}
           for i, j, iou, con in sorted(report, key=lambda r: -r[2])]

    out = sd / f"{src.stem}_dd.json"
    out.write_text(json.dumps(
        {"scene": man.get("scene", a.scene),
         "source": f"manifest_dedup.py — {a.manifest}: GEOMETRY-ONLY "
                   f"IoU>={IOU_MERGE} merge; gray zone ({IOU_GRAY}-"
                   f"{IOU_MERGE}, containment>={CONTAIN_GRAY}) deferred to "
                   f"the scene-graph judge (deferred_semantic)",
         "frame": man["frame"],
         "n_objects": len(merged),
         "objects": merged,
         "refuted": man.get("refuted", []),
         "filtered_out": man.get("filtered_out", []),
         "dedup_removed": removed,
         "deferred_semantic": deferred,
         "overlap_report": rep}, indent=2))

    print(f"[dedup] {src.name}: {len(objs)} -> {len(merged)} objects "
          f"({len(confident)} confident pairs, {len(removed)} boxes "
          f"absorbed; {len(deferred)} gray pairs DEFERRED) -> {out.name}")
    for m in merged:
        if "dedup_merged" in m.get("flags", []):
            print(f"  = {m['id']} {m['label']} (provisional; "
                  f"+ {', '.join(m.get('alt_labels', [])) or 'same label'})")
    for d in deferred:
        print(f"  ? deferred: {d['a']} {d['a_label']} <-> {d['b']} "
              f"{d['b_label']} IoU {d['iou']} contain {d['containment']}")


if __name__ == "__main__":
    main()
