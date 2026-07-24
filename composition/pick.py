"""C5: automated pick — dimension is a GATE (a tolerance band, never an
argmax), relevance chooses inside it.

Per box: admissible = candidates with fit score <= FIT_CAP whose rescale sits
within SCALE_BAND x the scene-median scale (the scene-coherence anchor: the
lifted world is uniformly off real scale, so coherence is measured against
its own median, not against x1.0). If the band is empty the top FALLBACK_N by
fit are used and the pick is flagged gate_relaxed. Winner = argmax `clip`
(image-image) among admissible; alternates keep the runners-up for a later
render-variants/VLM judgment at placement.

Writes package/picks2.json:
{obj_id: {uid, category, k, axis, perm, scale, fit, clip, clip_txt,
          n_admissible, gate_relaxed, alternates:[{uid, fit, clip}, ...]}}
uid null = box had no candidates at all.
"""
import json

import numpy as np

from comp_paths import paths

FIT_CAP = 0.8
SCALE_BAND = (0.5, 1.6)      # x scene-median implied scale
FALLBACK_N = 5
TOP_N = 5                    # ranked finalists kept per box (winner + N-1)


def scene_median_scale(boxes):
    per_box = [np.median([c["scale"] for c in b["candidates"]])
               for b in boxes if b["candidates"]]
    return float(np.median(per_box)) if per_box else 1.0


def run(sc, top_n=TOP_N):
    pkg = paths.package_dir(sc)
    sl = json.loads((pkg / "shortlists2.json").read_text())
    if not any(c.get("clip") is not None
               for b in sl["boxes"] for c in b["candidates"]):
        print("[pick] WARNING: no clip scores in shortlists2.json — "
              "relevance.py has not run; picking on fit alone", flush=True)
    med = scene_median_scale(sl["boxes"])
    lo, hi = SCALE_BAND[0] * med, SCALE_BAND[1] * med
    print(f"[pick] scene-median scale x{med:.2f} -> admissible band "
          f"x{lo:.2f}..x{hi:.2f}, fit <= {FIT_CAP}", flush=True)
    picks = {}
    for b in sl["boxes"]:
        cands = b["candidates"]
        if not cands:
            picks[b["id"]] = {"uid": None, "reason": "no candidates"}
            print(f"[pick] {b['id']} {b['label']:16s} -> NONE", flush=True)
            continue
        adm = [c for c in cands
               if c["score"] <= FIT_CAP and lo <= c["scale"] <= hi]
        relaxed = not adm
        if relaxed:
            adm = sorted(cands, key=lambda c: c["score"])[:FALLBACK_N]
        ranked = sorted(adm, key=lambda c: (c.get("clip") is not None,
                                            c.get("clip") or 0), reverse=True)
        w = ranked[0]
        picks[b["id"]] = {
            "uid": w["uid"], "category": w["category"], "k": w["k"],
            "axis": w["axis"], "perm": w["perm"], "scale": w["scale"],
            "fit": w["score"], "clip": w.get("clip"),
            "clip_txt": w.get("clip_txt"), "n_admissible": len(adm),
            "gate_relaxed": relaxed,
            "alternates": [{"uid": c["uid"], "fit": c["score"],
                            "clip": c.get("clip")}
                           for c in ranked[1:top_n]]}
        tag = " GATE-RELAXED" if relaxed else ""
        tile = f" x{w['k']}" if w["k"] > 1 else ""
        print(f"[pick] {b['id']} {b['label']:16s} -> {w['category']}{tile} "
              f"({w['uid'][:8]}) fit {w['score']:.2f} clip {w.get('clip')} "
              f"[{len(adm)} admissible]{tag}: {w['description'][:50]}",
              flush=True)
    outf = pkg / "picks2.json"
    outf.write_text(json.dumps(picks, indent=1))
    print(f"[pick] wrote {outf}", flush=True)
    return picks


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--top-n", type=int, default=TOP_N)
    args = ap.parse_args()
    run(args.scene, top_n=args.top_n)
