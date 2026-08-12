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
           confident objects of tight-reliability classes, PLUS the room
           itself as one ruler (ceiling height vs the 2.8 m standard-room
           constant the stitch eye already uses)
  mistake  a wrong scale silently resizes the whole room -> evidence
           table recorded in scene_scale.json; DEGRADES CONSERVATIVELY
           (scale 1.0 + loud warning) if n < MIN_N or spread > MAX_SPREAD

TWO TIERS (user ruling 2026-08-12, after fresh08's furniture camp and
door camp split 0.3 vs 0.66 and the scene shipped a 1.73 m ceiling
inside a PASS): when the WHOLE population of rulers cannot agree
(spread > MAX_SPREAD), the ARCHITECTURE decides — doors and the ceiling
are the standardized, style-immune rulers in a room, so the fallback
takes their median alone, gated by the same MAX_SPREAD on their own
agreement and ARCH_MIN_N of them present. Furniture can be low-profile
or occlusion-truncated; a door is a door. The arch stats are recorded on
every run (cross-check even when consensus passes); the tier that
decided is named in scene_scale.json.

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
MAX_SPREAD = 0.15  # relative MAD gate; wider = the arch tier decides
MIN_SCORE = 0.30   # manifest score floor for a measurement to count

#: the standard-room constant — the SAME 2.8 m the stitch eye fraction
#: (EYE_FRAC = 1.6/2.8) is built on. The room votes like any other ruler.
ROOM_TYPICAL_M = 2.8
#: architectural rulers needed before the arch tier may decide a scene
ARCH_MIN_N = 3

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
    # A reply with no parseable JSON (empty stdout, refusal, transient
    # backend hiccup) must not kill the stage: one retry, then EMPTY
    # priors — which is zero measurements, which is the module's own
    # MIN_N degrade-to-1.0 path. Only a parsed reply is cached, so a
    # degraded run re-asks next time instead of remembering the failure.
    prompt = PRIOR_PROMPT.format(labels=", ".join(sorted(labels)))
    for attempt in (1, 2):
        raw = call_claude(prompt, sdir)
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            try:
                priors = json.loads(raw[start:end + 1])
                cache.write_text(json.dumps({"key": key, "priors": priors},
                                            indent=1))
                return priors
            except ValueError:
                pass
        print(f"[scale] WARNING: priors reply attempt {attempt} had no "
              f"parseable JSON (head: {raw[:120]!r}) — "
              + ("retrying once" if attempt == 1 else
                 "NO PRIORS; the MIN_N gate will degrade this scene to "
                 "scale 1.0"), flush=True)
    return {}


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


def room_ruler(boot):
    """The room itself as one ruler: measured ceiling height against the
    2.8 m standard room. None when the frame has no ceiling (the
    no-ceiling fallback frames keep working exactly as before)."""
    if not boot:
        return None
    fy, cy = boot.get("floor_y"), boot.get("ceiling_y")
    if fy is None or cy is None:
        return None
    h = abs(float(cy) - float(fy))
    if h <= 0:
        return None
    return {"id": "room", "label": "room height", "axis": "height",
            "observed_m": round(h, 3), "typical_m": ROOM_TYPICAL_M,
            "ratio": round(h / ROOM_TYPICAL_M, 3)}


def is_arch(row):
    """Doors and the room: the standardized, style-immune rulers. Token
    match so 'closet door' counts and 'doormat' does not."""
    return (row["id"] == "room"
            or "door" in row["label"].lower().split())


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
    rr = room_ruler(boot)
    if rr:
        rows.append(rr)
        print(f"[scale] room ruler: ceiling {rr['observed_m']} raw vs "
              f"{ROOM_TYPICAL_M} m standard -> ratio {rr['ratio']}")
    else:
        print("[scale] no ceiling in the frame — the room cannot vote")
    ratios = np.array([r["ratio"] for r in rows], float)

    # TRIMMED CONSENSUS (user go 2026-08-11C, R-S2-120). A "ruler" that
    # disagrees with the median by more than TRIM_X in either direction
    # is not measuring the room's scale — it is a mislabel or a
    # truncated box wearing a ruler's badge (fresh04: a "wall molding"
    # that is really a mirror voted 10.8x against a trim-width prior;
    # a cut-off stool voted 0.19 — while six doors agreed at 0.58-0.70).
    # Those votes must not poison the AGREEMENT check that guards the
    # apply. The gate itself (MIN_N, MAX_SPREAD) is untouched: it now
    # judges the surviving rulers, and the trimmed-away votes are
    # counted and reported, never hidden.
    TRIM_X = 2.0
    n_raw = len(ratios)
    trimmed_out = []
    if len(ratios):
        med0 = float(np.median(ratios))
        keep = (ratios <= med0 * TRIM_X) & (ratios >= med0 / TRIM_X)
        trimmed_out = [rows[i]["id"] for i in range(len(rows))
                       if not keep[i]]
        ratios = ratios[keep]

    if len(ratios):
        s = float(np.median(ratios))
        spread = float(np.median(np.abs(ratios - s)) / s)
    else:
        s, spread = 1.0, 0.0
    if trimmed_out:
        print(f"[scale] trimmed {len(trimmed_out)} ruler(s) disagreeing "
              f">{TRIM_X}x with the median: {', '.join(trimmed_out)}")
    # ---- the two tiers ----
    # arch stats are computed on EVERY run (a recorded cross-check even
    # when the consensus passes); they only DECIDE when consensus fails.
    arch_rows = [r for r in rows if is_arch(r)]
    ar = np.array([r["ratio"] for r in arch_rows], float)
    if len(ar):
        s_arch = float(np.median(ar))
        spread_arch = float(np.median(np.abs(ar - s_arch)) / s_arch)
    else:
        s_arch, spread_arch = None, None
    arch_ok = (len(ar) >= ARCH_MIN_N and spread_arch is not None
               and spread_arch <= MAX_SPREAD)

    consensus_ok = len(ratios) >= MIN_N and spread <= MAX_SPREAD
    if consensus_ok:
        tier, s_use, ok = "consensus", s, True
    elif arch_ok:
        tier, s_use, ok = "arch_reference", s_arch, True
        print(f"[scale] consensus failed (n={len(ratios)}, spread "
              f"{spread:.2f}) -> ARCH REFERENCE decides: doors+ceiling "
              f"n={len(ar)}, s={s_arch:.3f}, rel-MAD {spread_arch:.3f} "
              f"({', '.join(r['id'] for r in arch_rows)})")
    else:
        tier, s_use, ok = "degraded", 1.0, False
        print(f"[scale] WARNING: evidence too weak (consensus n="
              f"{len(ratios)}, spread={spread:.2f}; arch n={len(ar)}, "
              f"spread={'-' if spread_arch is None else f'{spread_arch:.2f}'}) "
              f"— DEGRADING to scale 1.0, scene left untouched")
    k = 1.0 / s_use

    for r in rows:
        print(f"  {r['id']:8s} {r['label']:14s} {r['axis']:6s} "
              f"obs {r['observed_m']:5.2f}  typ {r['typical_m']:5.2f}  "
              f"ratio {r['ratio']:.2f}")
    print(f"[scale] scene scale s = {s_use if ok else s:.3f} "
          f"(tier {tier}) -> multiply geometry by k = 1/s = {k:.3f}"
          + ("" if ok else "  [DEGRADED]"))

    record = {"scene": sc, "scale_measured": round(s_use if ok else s, 4),
              "scale_applied": None, "k": round(k, 4),
              "tier": tier,
              "consensus": {"s": round(s, 4), "n_used": int(len(ratios)),
                            "rel_mad": round(spread, 4),
                            "ok": consensus_ok},
              "arch": {"s": None if s_arch is None else round(s_arch, 4),
                       "n": int(len(ar)),
                       "rel_mad": None if spread_arch is None
                       else round(spread_arch, 4),
                       "ok": arch_ok,
                       "ids": [r["id"] for r in arch_rows]},
              "n": len(rows), "n_used": int(len(ratios)),
              "n_trimmed": n_raw - int(len(ratios)),
              "trimmed_ids": trimmed_out,
              "rel_mad": round(spread, 4),
              "evidence_ok": ok, "rows": rows,
              "priors_used": {r["label"]: priors.get(
                  r["label"], {"axis": "height",
                               "typical_m": ROOM_TYPICAL_M,
                               "reliability": "constant (the room)"})
                              for r in rows},
              "note": "two-pass protocol: pass-1 manifests stay at raw "
                      "scale and regenerate on the post-normalization "
                      "re-run"}

    already = bool(boot and boot.get("scale_applied"))
    if a.measure_only or not ok or abs(k - 1.0) < 1e-9 or already:
        # a measure on an ALREADY-normalized scene is a verification —
        # it must never clobber the apply's evidence record.
        # ⚠ `already` ROUTES HERE AUTOMATICALLY since R-S2-121: the
        # runner has no --measure-only, so the two-pass protocol's
        # regeneration re-ran this stage on the normalized scene and
        # fell into the second-apply REFUSAL below — a guaranteed crash
        # for every normalized scene on every re-run (fresh04 found it;
        # a resumed batch night would have hit it at scale). Verifying
        # is what a re-measure on a normalized scene IS; the refusal
        # below still guards the one thing it must (no double apply).
        outname = ("scene_scale_verify.json" if already
                   else "scene_scale.json")
        (sdir / outname).write_text(json.dumps(record, indent=1))
        if already:
            # THE STAGE'S PROMISE IS scene_scale.json (stages.py), and
            # the gate rightly failed a verify run that left it stale —
            # the no-op trap caught the first version of this fix. A
            # verification APPENDS to the apply record instead of
            # clobbering it: the apply evidence stays, the verification
            # history accumulates, and the promised file is genuinely
            # written by this run.
            main_f = sdir / "scene_scale.json"
            rec0 = (json.loads(main_f.read_text(encoding="utf-8"))
                    if main_f.exists() else
                    {"scene": sc, "note": "verification only — no apply "
                                          "record was on disk"})
            from datetime import date as _date
            rec0.setdefault("verifications", []).append(
                {"date": str(_date.today()),
                 "s": round(s_use if ok else s, 4), "tier": tier,
                 "n_used": int(len(ratios)),
                 "rel_mad": round(spread, 4)})
            main_f.write_text(json.dumps(rec0, indent=1))
            print(f"[scale] scene already normalized "
                  f"(scale_applied={boot['scale_applied']}) — this "
                  f"re-measure is a VERIFICATION: s="
                  f"{s_use if ok else s:.3f} (tier {tier}; 1.0 = "
                  f"perfectly metric); appended to scene_scale.json")
        print(f"[scale] measure-only record -> {outname}")
        return

    if boot and boot.get("scale_applied"):
        raise SystemExit(
            f"[scale] REFUSING second apply: scene already normalized "
            f"(scale_applied={boot['scale_applied']}). Re-measure with "
            f"--measure-only; to redo, restore the *_prescale.* backups "
            f"first.")

    # ---- apply, with originals preserved ----
    ply_f = paths.ply(sc)
    # colliderless scenes are a designed case since 2026-08-11C
    # (R-S2-111): frame_bootstrap registers a collider only when the
    # bundle has one that agrees with the splat
    coll_f = sdir / "collider_registered.glb"
    targets = [ply_f, boot_f] + ([coll_f] if coll_f.exists() else [])
    for f in targets:
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

    if coll_f.exists():
        import trimesh
        mesh = trimesh.load(coll_f, force="mesh")
        mesh.apply_scale(k)
        mesh.export(coll_f)
        print(f"[scale] collider rescaled (bounds now "
              f"{np.round(mesh.bounds, 2).tolist()})")
    else:
        print("[scale] no registered collider — colliderless scene, "
              "nothing to rescale")

    derived = scale_derived_state(sdir, k)
    print(f"[scale] derived state rescaled: {', '.join(derived)}")

    for key in ("floor_y", "ceiling_y"):
        boot[key] = round(boot[key] * k, 3)
    for key in ("extent_p1", "extent_p99"):
        if key in boot:
            boot[key] = [round(v * k, 3) for v in boot[key]]
    boot["scale_applied"] = round(s_use, 4)
    boot["scale_note"] = ("scene_scale.py normalized this scene to true "
                          "meters (evidence: scene_scale.json, tier "
                          f"{tier}); originals in *_prescale.* files")
    boot_f.write_text(json.dumps(boot, indent=1))

    record["scale_applied"] = round(s_use, 4)
    (sdir / "scene_scale.json").write_text(json.dumps(record, indent=1))
    print(f"[scale] frame block updated: floor {boot['floor_y']} / "
          f"ceiling {boot['ceiling_y']}  -> scene_scale.json written")


if __name__ == "__main__":
    main()
