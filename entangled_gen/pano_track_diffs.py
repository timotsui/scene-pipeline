"""Difference manifests for the pano-track funnel viewer layers (user
2026-07-26: the three stages are upstream->downstream, so the upstream
layers should show only their DELTA, not duplicate the whole set).

  gate kills      = ungated (118) minus gated (85): the 33 objects whose
                    best detection never reached 0.40
  recenter delta  = what the recenter round changed on the gated set:
                    the refuted objects (deleted, with evidence) + the
                    PRE-refinement boxes of objects whose bounds moved
                    (toggle against canonical to see old vs new bounds)

Run:  python pano_track_diffs.py --scene bedroom_marble
Out:  scene_manifest_pano_gatekills.json + scene_manifest_pano_rcdelta.json
"""
import argparse, json

import paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--suffix", default="b")
    a = ap.parse_args()
    sd = paths.scene_dir(a.scene)
    sfx = a.suffix
    ungated = json.loads((sd / f"scene_manifest_pano2{sfx}.json").read_text())
    gated = json.loads(
        (sd / f"scene_manifest_pano2{sfx}_gated.json").read_text())
    rc = json.loads((sd / f"scene_manifest_pano2{sfx}_rc.json").read_text())

    gated_ids = {o["id"] for o in gated["objects"]}
    kills = []
    for o in ungated["objects"]:
        if o["id"] in gated_ids:
            continue
        k = dict(o)
        k["flags"] = list(o.get("flags", [])) + ["gate_killed"]
        kills.append(k)
    f1 = sd / "scene_manifest_pano_gatekills.json"
    f1.write_text(json.dumps(
        {"scene": a.scene,
         "source": "pano_track_diffs.py — gate kills only (delta layer)",
         "frame": ungated["frame"], "n_objects": len(kills),
         "objects": kills}, indent=2))
    print(f"[diffs] gate kills: {len(kills)} -> {f1}")

    refuted = set(rc.get("refuted", []))
    rc_by_id = {o["id"]: o for o in rc["objects"]}
    delta = []
    for o in gated["objects"]:
        n = rc_by_id.get(o["id"])
        if o["id"] in refuted:
            d = dict(o)
            d["flags"] = list(o.get("flags", [])) + ["refuted_by_recenter"]
            delta.append(d)
        elif n is not None and "recenter_refined" in n.get("flags", []) \
                and (n["aabb_min"] != o["aabb_min"]
                     or n["aabb_max"] != o["aabb_max"]):
            d = dict(o)
            d["flags"] = list(o.get("flags", [])) + ["pre_refinement"]
            delta.append(d)
    f2 = sd / "scene_manifest_pano_rcdelta.json"
    f2.write_text(json.dumps(
        {"scene": a.scene,
         "source": "pano_track_diffs.py — recenter delta (refuted + "
                   "pre-refinement bounds)",
         "frame": gated["frame"], "n_objects": len(delta),
         "objects": delta}, indent=2))
    n_ref = sum(1 for d in delta if "refuted_by_recenter" in d["flags"])
    print(f"[diffs] recenter delta: {len(delta)} ({n_ref} refuted, "
          f"{len(delta) - n_ref} pre-refinement boxes) -> {f2}")


if __name__ == "__main__":
    main()
