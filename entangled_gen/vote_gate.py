"""Minimal two-sided vote gate over a merged sweep manifest (ported idea
from the analyzer's a7 / SPEC_3H2_FUSE section 7, static version): keep an
object only if votes (n_detections) >= MIN_VOTES AND peak member score >=
MIN_PEAK. Diagnosis 2026-07-26: junk objects trace to exactly this missing
gate (obj_077 "book": 4 members all <= 0.37 peak; obj_079 "door": 1 vote).

Run:  python vote_gate.py --scene bedroom_marble --man robust
Writes scene_manifest_sweep_gated.json + prints kept/killed breakdown.
"""
import argparse, json
from collections import Counter

import paths

MAN_FILES = {"robust": "scene_manifest_sweep_robust.json",
             "union": "scene_manifest_sweep.json"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--man", default="robust", choices=list(MAN_FILES))
    ap.add_argument("--min-votes", type=int, default=2)
    ap.add_argument("--min-peak", type=float, default=0.40)
    a = ap.parse_args()
    sd = paths.scene_dir(a.scene)
    man = json.loads((sd / MAN_FILES[a.man]).read_text())

    kept, killed = [], []
    for o in man["objects"]:
        ok = o["n_detections"] >= a.min_votes and o["score"] >= a.min_peak
        (kept if ok else killed).append(o)
    for o in killed:
        why = []
        if o["n_detections"] < a.min_votes:
            why.append(f"votes {o['n_detections']}")
        if o["score"] < a.min_peak:
            why.append(f"peak {o['score']}")
        print(f"[gate] KILL {o['id']} {o['label']:16s} "
              f"size {o['size']}  ({', '.join(why)})", flush=True)

    out = dict(man)
    out["source"] = (man.get("source", "") +
                     f" + vote gate (votes>={a.min_votes} & peak>="
                     f"{a.min_peak}; killed {len(killed)})")
    out["objects"] = kept
    out["n_objects"] = len(kept)
    outf = sd / "scene_manifest_sweep_gated.json"
    outf.write_text(json.dumps(out, indent=2))
    print(f"\n[gate] kept {len(kept)} / killed {len(killed)} "
          f"(of {len(man['objects'])})  -> {outf}", flush=True)
    ck = Counter(o["label"] for o in kept)
    cx = Counter(o["label"] for o in killed)
    print("[gate] kept  :", dict(ck.most_common()), flush=True)
    print("[gate] killed:", dict(cx.most_common()), flush=True)


if __name__ == "__main__":
    main()
