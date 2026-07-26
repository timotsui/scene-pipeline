"""Hard confidence filter over an existing manifest (user 2026-07-26:
"just a hard filter from the boxes we already have, no reruns").

Drops objects whose peak detection score is below --thr. No detection or
lift is re-run; this is pure post-processing on a manifest file. Dropped
objects are preserved in the output under "filtered_out" (flagged
"score_filtered") so nothing is lost and the cut is auditable — including
the case where the filter overrules a retake_confirmed flag.

Run:  python manifest_filter.py --scene bedroom_marble
Out:  <manifest stem>_f<thr*100>.json  (e.g. scene_manifest_pano2c_rc_f30.json)
"""
import argparse, json

import paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--manifest", default="scene_manifest_pano2c_rc.json",
                    help="input manifest filename inside the scene dir")
    ap.add_argument("--thr", type=float, default=0.30)
    a = ap.parse_args()
    sd = paths.scene_dir(a.scene)
    src = sd / a.manifest
    m = json.loads(src.read_text())

    keep, drop = [], []
    for o in m["objects"]:
        if o["score"] >= a.thr:
            keep.append(o)
        else:
            d = dict(o)
            d["flags"] = list(o.get("flags", [])) + ["score_filtered"]
            drop.append(d)

    out = sd / f"{src.stem}_f{round(a.thr * 100):02d}.json"
    out.write_text(json.dumps(
        {"scene": m.get("scene", a.scene),
         "source": f"manifest_filter.py — {a.manifest} hard-filtered at "
                   f"score >= {a.thr}",
         "frame": m["frame"],
         "score_thr": a.thr,
         "n_objects": len(keep),
         "objects": keep,
         "refuted": m.get("refuted", []),
         "filtered_out": drop}, indent=2))
    overruled = [d for d in drop if "retake_confirmed" in d["flags"]]
    print(f"[filter] {src.name}: keep {len(keep)} / drop {len(drop)} "
          f"at thr {a.thr} -> {out.name}")
    for d in drop:
        tag = " (RETAKE-CONFIRMED — overruled)" if d in overruled else ""
        print(f"  - {d['id']} {d['label']} score {d['score']:.3f}{tag}")


if __name__ == "__main__":
    main()
