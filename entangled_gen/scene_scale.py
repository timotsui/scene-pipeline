"""Scene scale normalization — measure the scene's true metric scale and
rescale it into real-world meters, ONCE (design settled with the user
2026-08-06, PLAN_SCENE2_LIVING.md).

WHY: Marble's export scale varies per world (bedroom ~1.0; living measured
0.74 — both doors at 1.50 m, chairs/sofas/lamp all ~0.74 of typical).
Every downstream constant is meters-tuned and shopping fits assets at
native real size, so an off-scale scene poisons everything. Fix at the
source: after this stage the scene IS in meters, like a correctly
exported bundle — zero scale-aware call sites anywhere downstream.

CONTRACT:
  gets     the f30 manifest (lifted sizes at raw scale) + frame block
  decides  one number: scale_to_meters, MEASURED via LLM class-size
           priors (vocab_build pattern: judgment call, cached, never a
           curated table) — robust median of observed/typical over
           confident objects of tight-reliability classes
  mistake  a wrong scale silently resizes the whole room -> evidence
           table recorded in scene_scale.json; DEGRADES CONSERVATIVELY
           (scale 1.0 + loud warning) if n < MIN_N or spread > MAX_SPREAD

APPLY (skipped with --measure-only): gen_raw.ply (xyz *= k, log-scales
+= ln k), collider_registered.glb (trimesh apply_scale), frame_bootstrap
floor/ceiling/extents. Originals kept as *_prescale.* backups. A second
apply is REFUSED (frame_bootstrap.scale_applied guard) — re-measure is
always allowed. Pass-1 manifests are NOT rescaled: the protocol is
two-pass (measure at raw scale -> normalize -> re-run from pano in true
meters), so they regenerate.

Run:  python scene_scale.py --scene <sc> [--measure-only] [--fresh]
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np

import paths
from splat_place import read_ply, write_ply
from vocab_build import call_claude

MIN_N = 5          # confident measurements needed to trust the median
MAX_SPREAD = 0.15  # relative MAD gate; wider = degrade to 1.0
MIN_SCORE = 0.30   # manifest score floor for a measurement to count

PRIOR_PROMPT = """You are sizing object classes for an interior-scene pipeline. For each class below, give the typical real-world size of its MOST STANDARDIZED dimension.

Classes: {labels}

Rules:
- "axis": "height" (floor-to-top overall height) for floor-standing furniture and doors; "width" (largest horizontal span) for wall-flat objects like televisions
- "typical_m": one number in meters, the typical adult-world value
- "reliability": "tight" only if real instances cluster within ~15% of typical (doors, seating, tables, televisions, floor lamps); "loose" for anything that genuinely varies a lot (plants, pictures, pillows, books, decor, windows, curtains, shelves, generic 'lamp'/'light' fixtures)
- Output ONLY one JSON object, one line: {{"<class>": {{"axis": "...", "typical_m": 0.0, "reliability": "..."}}, ...}}"""


def get_priors(labels, sdir, fresh):
    cache = sdir / "scale_priors_cache.json"
    key = hashlib.sha1(json.dumps(sorted(labels)).encode()).hexdigest()
    if cache.exists() and not fresh:
        c = json.loads(cache.read_text(encoding="utf-8"))
        if c.get("key") == key:
            print(f"[scale] priors: cache hit ({len(c['priors'])} classes)")
            return c["priors"]
    raw = call_claude(PRIOR_PROMPT.format(labels=", ".join(sorted(labels))),
                      sdir)
    start, end = raw.find("{"), raw.rfind("}")
    priors = json.loads(raw[start:end + 1])
    cache.write_text(json.dumps({"key": key, "priors": priors}, indent=1))
    return priors


def measure(man, priors):
    rows = []
    for o in man["objects"]:
        lab = o["label"]
        p = priors.get(lab)
        if not p or p.get("reliability") != "tight":
            continue
        if float(o.get("score", 0)) < MIN_SCORE:
            continue
        sz = [abs(v) for v in o["size"]]
        obs = sz[1] if p["axis"] == "height" else max(sz[0], sz[2])
        t = float(p["typical_m"])
        if obs <= 0 or t <= 0:
            continue
        rows.append({"id": o["id"], "label": lab, "axis": p["axis"],
                     "observed_m": round(obs, 3), "typical_m": t,
                     "ratio": round(obs / t, 3)})
    return rows


def scale_derived_state(sdir, k):
    """Multiply every meter-bearing DERIVED artifact of the scene state
    (the state-transform half of the user's 08-06 ruling): all pano-track
    manifests, the lift pool, the recorded pano eye. 2D pixel boxes and
    view lists are scale-free and untouched."""
    scaled = []

    def _obj(o):
        for key in ("aabb_min", "aabb_max", "center", "size"):
            if key in o and o[key] is not None:
                o[key] = [round(v * k, 4) for v in o[key]]

    for f in sorted(sdir.glob("scene_manifest_pano*.json")):
        man = json.loads(f.read_text(encoding="utf-8"))
        fr = man.get("frame")
        if fr:
            for key in ("floor_y", "ceiling_y"):
                if key in fr:
                    fr[key] = round(fr[key] * k, 4)
            for key in ("extent_p1", "extent_p99"):
                if key in fr:
                    fr[key] = [round(v * k, 4) for v in fr[key]]
        for sec in ("objects", "refuted", "filtered_out"):
            for o in man.get(sec) or []:
                _obj(o)
        man["scale_note"] = f"scene_scale.py multiplied by k={k:.4f}"
        f.write_text(json.dumps(man, indent=1))
        scaled.append(f.name)

    for f in sorted((sdir / "rig_sp0").glob("lift_pool*.json")):
        pool = json.loads(f.read_text(encoding="utf-8"))
        if "floor_y" in pool:
            pool["floor_y"] = round(pool["floor_y"] * k, 4)
        for p in pool.get("pool", []):
            for key in ("lo", "hi"):        # 3D bounds; p["box"] is 2D px
                if key in p and p[key] is not None:
                    p[key] = [round(v * k, 4) for v in p[key]]
        f.write_text(json.dumps(pool))
        scaled.append(f.name)

    mf = sdir / "rig_sp0" / "pano_selfrender_meta.json"
    if mf.exists():
        meta = json.loads(mf.read_text(encoding="utf-8"))
        meta["eye_raw"] = [round(v * k, 6) for v in meta["eye_raw"]]
        meta["eye_note"] = ("eye scaled by scene_scale.py — the standpoint "
                            "is part of the scene state; eye_height_m no "
                            "longer literal")
        mf.write_text(json.dumps(meta, indent=2))
        scaled.append(mf.name)
    return scaled


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--measure-only", action="store_true")
    ap.add_argument("--fresh", action="store_true", help="ignore prior cache")
    a = ap.parse_args()
    sc = a.scene
    sdir = paths.scene_dir(sc)

    boot_f = sdir / "frame_bootstrap.json"
    boot = json.loads(boot_f.read_text(encoding="utf-8")) if boot_f.exists() \
        else None
    man = json.loads(
        (sdir / "scene_manifest_pano2c_rc_f30.json").read_text(
            encoding="utf-8"))

    labels = sorted({o["label"] for o in man["objects"]})
    priors = get_priors(labels, sdir, a.fresh)
    rows = measure(man, priors)
    ratios = np.array([r["ratio"] for r in rows], float)

    if len(ratios):
        s = float(np.median(ratios))
        spread = float(np.median(np.abs(ratios - s)) / s)
    else:
        s, spread = 1.0, 0.0
    ok = len(ratios) >= MIN_N and spread <= MAX_SPREAD
    if not ok:
        print(f"[scale] WARNING: evidence too weak (n={len(ratios)}, "
              f"spread={spread:.2f}) — DEGRADING to scale 1.0, scene "
              f"left untouched")
        s_use = 1.0
    else:
        s_use = s
    k = 1.0 / s_use

    for r in rows:
        print(f"  {r['id']:8s} {r['label']:14s} {r['axis']:6s} "
              f"obs {r['observed_m']:5.2f}  typ {r['typical_m']:5.2f}  "
              f"ratio {r['ratio']:.2f}")
    print(f"[scale] scene scale s = {s:.3f} (n={len(ratios)}, rel-MAD "
          f"{spread:.3f}) -> multiply geometry by k = 1/s = {k:.3f}"
          + ("" if ok else "  [DEGRADED]"))

    record = {"scene": sc, "scale_measured": round(s, 4),
              "scale_applied": None, "k": round(k, 4),
              "n": len(rows), "rel_mad": round(spread, 4),
              "evidence_ok": ok, "rows": rows,
              "priors_used": {r["label"]: priors[r["label"]]
                              for r in rows},
              "note": "two-pass protocol: pass-1 manifests stay at raw "
                      "scale and regenerate on the post-normalization "
                      "re-run"}

    if a.measure_only or not ok or abs(k - 1.0) < 1e-9:
        (sdir / "scene_scale.json").write_text(
            json.dumps(record, indent=1))
        print(f"[scale] measure-only record -> scene_scale.json")
        return

    if boot and boot.get("scale_applied"):
        raise SystemExit(
            f"[scale] REFUSING second apply: scene already normalized "
            f"(scale_applied={boot['scale_applied']}). Re-measure with "
            f"--measure-only; to redo, restore the *_prescale.* backups "
            f"first.")

    # ---- apply, with originals preserved ----
    ply_f = paths.ply(sc)
    coll_f = sdir / "collider_registered.glb"
    for f in (ply_f, coll_f, boot_f):
        bak = f.with_name(f.stem + "_prescale" + f.suffix)
        if not bak.exists():
            shutil.copyfile(f, bak)

    names, data = read_ply(ply_f)
    ix = {n: i for i, n in enumerate(names)}
    for ax in ("x", "y", "z"):
        data[:, ix[ax]] *= k
    for scn in ("scale_0", "scale_1", "scale_2"):
        data[:, ix[scn]] += np.log(k)
    write_ply(ply_f, names, data)
    print(f"[scale] gen_raw.ply rescaled ({len(data):,} gaussians)")

    import trimesh
    mesh = trimesh.load(coll_f, force="mesh")
    mesh.apply_scale(k)
    mesh.export(coll_f)
    print(f"[scale] collider rescaled (bounds now "
          f"{np.round(mesh.bounds, 2).tolist()})")

    derived = scale_derived_state(sdir, k)
    print(f"[scale] derived state rescaled: {', '.join(derived)}")

    for key in ("floor_y", "ceiling_y"):
        boot[key] = round(boot[key] * k, 3)
    for key in ("extent_p1", "extent_p99"):
        if key in boot:
            boot[key] = [round(v * k, 3) for v in boot[key]]
    boot["scale_applied"] = round(s, 4)
    boot["scale_note"] = ("scene_scale.py normalized this scene to true "
                          "meters (evidence: scene_scale.json); originals "
                          "in *_prescale.* files")
    boot_f.write_text(json.dumps(boot, indent=1))

    record["scale_applied"] = round(s, 4)
    (sdir / "scene_scale.json").write_text(json.dumps(record, indent=1))
    print(f"[scale] frame block updated: floor {boot['floor_y']} / "
          f"ceiling {boot['ceiling_y']}  -> scene_scale.json written")


if __name__ == "__main__":
    main()
