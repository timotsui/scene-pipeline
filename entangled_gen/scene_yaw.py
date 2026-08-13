"""Scene yaw normalization — measure the room's continuous yaw vs the
axes and de-tilt the WHOLE scene state, ONCE (R-S2-158 shipping half;
pre-registered R-S2-160; the scale-apply pattern of scene_scale.py).

WHY: rooms arrive a few degrees yawed vs the world axes (08-05 finding;
fresh06 measured +12.0 deg) and the pipeline only ever knew 4 discrete
flips. The wall trace is cardinal; a tilted room makes every wall fight
the grid. The trace must NOT privately de-rotate in a state-writing run
(R-S2-159: the polygon would sit rotated against the splat) — the cure
is to rotate the STATE, after which the estimator reads ~0 everywhere.

CONTRACT:
  gets     the scene's upright wall-band footprint (the SAME points and
           the SAME estimator the trace uses: room_shell.measure_plan_yaw,
           spikiness voting, its own guards: >500 pts, 5% win, |yaw|>1)
  decides  one number: plan yaw in degrees, then applies the de-tilting
           rotation to the entire scene state (N1 whole-state canon)
  mistake  rotating the splat but not the gaussian quats (every
           anisotropic gaussian points 12 deg off its surface); a wrong
           sign doubling the tilt — guarded by the built-in POST-CHECK:
           the rotated points are re-measured IN MEMORY and the apply
           REFUSES to write unless the residual is inside the
           estimator's 1-deg dead zone.

FRAME: the rotation is defined in the UPRIGHT frame (raw * raw_to_render
elementwise) about the vertical axis through the pano origin (x=z=0,
where the stitch eye lives), matching the trace's de-rotation formula
x' = x c - z s, z' = x s + z c exactly. In raw space that is
M = D R_up D with D = diag(raw_to_render) — still a pure rotation about
y (det +1, y axis preserved), so THE FRAME CONTRACT STAYS ELEMENTWISE
SIGN FLIPS: no rotation enters raw_to_render, zero *r2r call sites
change.

APPLY (skipped with --measure-only): gen_raw.ply xyz AND rot_0..3 quats
(q' = q_M HAMILTON q, normalized; log-scales untouched — rotation
changes no sizes; f_dc only, sh_degree 0, so color is rotation-
invariant), collider_registered.glb when present, every
scene_manifest_pano*.json box (aabb corners rotated -> new AABB,
center/size re-derived — conservative inflation, honest: the two-pass
re-run regenerates them), lift_pool lo/hi, pano_selfrender_meta
eye_raw, frame_bootstrap extents. floor_y/ceiling_y are y-invariant.
Originals kept as *_preyaw.* backups. A second apply is REFUSED
(frame_bootstrap.yaw_applied guard); a re-run on an applied scene
routes to VERIFICATION (re-measure, expect ~0, append) — the R-S2-121
pattern verbatim.

PROTOCOL: apply -> two-pass chain re-run from stitch (geometry mutated;
every render and detection descends from it).

Run:  python scene_yaw.py --scene <sc> [--measure-only]
"""
import argparse
import json
import shutil

import numpy as np

import paths
from splat_place import read_ply, write_ply
from room_shell import (load_upright_points, measure_floor_ceiling,
                        measure_plan_yaw, WALL_BAND_LO, WALL_BAND_HI,
                        POLY_MARGIN)


def crop_to_extent(pts_up, fr, r2r):
    """run_poly's own pre-crop, mirrored exactly: without it, splat
    leakage outside the room dilutes the spikiness vote (fresh06 read
    0.0 instead of its true +12.0 until this crop was added)."""
    lo = np.minimum(np.array(fr["extent_p1"]) * r2r,
                    np.array(fr["extent_p99"]) * r2r) - POLY_MARGIN
    hi = np.maximum(np.array(fr["extent_p1"]) * r2r,
                    np.array(fr["extent_p99"]) * r2r) + POLY_MARGIN
    return pts_up[np.all((pts_up >= lo) & (pts_up <= hi), axis=1)]


def band_xz(pts_up, floor_m, ceil_m):
    sel = pts_up[(pts_up[:, 1] >= floor_m + WALL_BAND_LO)
                 & (pts_up[:, 1] <= ceil_m - WALL_BAND_HI)]
    return sel[:, [0, 2]]


def rotation_matrices(yaw_deg, r2r):
    """R_up (upright frame, the trace's de-rotation) and M (raw frame)."""
    th = np.radians(yaw_deg)
    c, s = np.cos(th), np.sin(th)
    # matches run_poly's de-tilt exactly: x' = x c - z s, z' = x s + z c
    R_up = np.array([[c, 0.0, -s],
                     [0.0, 1.0, 0.0],
                     [s, 0.0, c]], dtype=np.float64)
    D = np.diag(np.asarray(r2r, dtype=np.float64))
    M = D @ R_up @ D
    return R_up, M


def mat_to_quat(M):
    """Rotation matrix -> quaternion (w, x, y, z). M must be proper."""
    t = np.trace(M)
    if t > 0:
        w = np.sqrt(1.0 + t) / 2.0
        x = (M[2, 1] - M[1, 2]) / (4 * w)
        y = (M[0, 2] - M[2, 0]) / (4 * w)
        z = (M[1, 0] - M[0, 1]) / (4 * w)
    else:
        k = int(np.argmax(np.diag(M)))
        i, j = (k + 1) % 3, (k + 2) % 3
        r = np.sqrt(1.0 + M[k, k] - M[i, i] - M[j, j])
        q = np.empty(4)
        q[1 + k] = r / 2.0
        q[0] = (M[j, i] - M[i, j]) / (2 * r)
        q[1 + i] = (M[i, k] + M[k, i]) / (2 * r)
        q[1 + j] = (M[j, k] + M[k, j]) / (2 * r)
        w, x, y, z = q
    return float(w), float(x), float(y), float(z)


def quat_premul(qm, qw, qx, qy, qz):
    """q' = qm HAMILTON q for arrays (splat_place's pattern generalized)."""
    w1, x1, y1, z1 = qm
    return (w1 * qw - x1 * qx - y1 * qy - z1 * qz,
            w1 * qx + x1 * qw + y1 * qz - z1 * qy,
            w1 * qy - x1 * qz + y1 * qw + z1 * qx,
            w1 * qz + x1 * qy - y1 * qx + z1 * qw)


def rotate_box(lo, hi, M):
    """Rotate an axis-aligned box's 8 corners by M; return the new AABB."""
    lo = np.asarray(lo, dtype=np.float64)
    hi = np.asarray(hi, dtype=np.float64)
    corners = np.array([[x, y, z] for x in (lo[0], hi[0])
                        for y in (lo[1], hi[1])
                        for z in (lo[2], hi[2])])
    rc = corners @ M.T
    return rc.min(axis=0), rc.max(axis=0)


def rotate_derived_state(sdir, M, new_p1, new_p99):
    """The state-transform half (N1 canon): every raw-frame box and
    point in the derived artifacts, same targets scene_scale touches.
    new_p1/new_p99: the recomputed robust extents (frame extents must
    hug the rotated cloud, never corner-rotate — see main())."""
    touched = []

    def _obj(o):
        if not isinstance(o, dict):
            return    # "refuted" carries bare id strings in _rc manifests
        keys = [k for k in ("aabb_min", "aabb_max") if o.get(k) is not None]
        if len(keys) == 2:
            lo, hi = rotate_box(o["aabb_min"], o["aabb_max"], M)
            o["aabb_min"] = [round(float(v), 4) for v in lo]
            o["aabb_max"] = [round(float(v), 4) for v in hi]
            if o.get("center") is not None:
                o["center"] = [round(float(v), 4)
                               for v in (lo + hi) / 2.0]
            if o.get("size") is not None:
                o["size"] = [round(float(v), 4) for v in (hi - lo)]
        elif o.get("center") is not None:
            c = np.asarray(o["center"], dtype=np.float64) @ M.T
            o["center"] = [round(float(v), 4) for v in c]

    for f in sorted(sdir.glob("scene_manifest_pano*.json")):
        man = json.loads(f.read_text(encoding="utf-8"))
        fr = man.get("frame")
        if fr and "extent_p1" in fr and "extent_p99" in fr:
            fr["extent_p1"] = list(new_p1)
            fr["extent_p99"] = list(new_p99)
        for sec in ("objects", "refuted", "filtered_out"):
            for o in man.get(sec) or []:
                _obj(o)
        man["yaw_note"] = ("scene_yaw.py rotated boxes (corner-rotate -> "
                           "new AABB, conservative); regenerated by the "
                           "two-pass re-run")
        f.write_text(json.dumps(man, indent=1))
        touched.append(f.name)

    for f in sorted((sdir / "rig_sp0").glob("lift_pool*.json")):
        pool = json.loads(f.read_text(encoding="utf-8"))
        for p in pool.get("pool", []):
            if p.get("lo") is not None and p.get("hi") is not None:
                lo, hi = rotate_box(p["lo"], p["hi"], M)
                p["lo"] = [round(float(v), 4) for v in lo]
                p["hi"] = [round(float(v), 4) for v in hi]
        f.write_text(json.dumps(pool))
        touched.append(f.name)

    mf = sdir / "rig_sp0" / "pano_selfrender_meta.json"
    if mf.exists():
        meta = json.loads(mf.read_text(encoding="utf-8"))
        eye = np.asarray(meta["eye_raw"], dtype=np.float64) @ M.T
        meta["eye_raw"] = [round(float(v), 6) for v in eye]
        mf.write_text(json.dumps(meta, indent=2))
        touched.append(mf.name)
    return touched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--measure-only", action="store_true")
    a = ap.parse_args()
    sc = a.scene
    sdir = paths.scene_dir(sc)

    boot_f = sdir / "frame_bootstrap.json"
    boot = json.loads(boot_f.read_text(encoding="utf-8"))
    fr = paths.frame_block(sc)
    r2r = np.asarray(fr["raw_to_render"], dtype=np.float64)

    pts_up, _ = load_upright_points(sc, fr)
    pts_up = crop_to_extent(pts_up, fr, r2r)
    floor_m, ceil_m = measure_floor_ceiling(pts_up)
    yaw = measure_plan_yaw(band_xz(pts_up, floor_m, ceil_m))
    print(f"[yaw] {sc}: measured plan yaw {yaw:+.2f} deg "
          f"(0.0 = axis-aligned or below the 1-deg dead zone)")

    already = boot.get("yaw_applied")
    record = {"scene": sc, "yaw_measured_deg": round(yaw, 2),
              "yaw_applied_deg": None,
              "estimator": "room_shell.measure_plan_yaw (R-S2-158 "
                           "spikiness voting; R-S2-159 single source)",
              "note": "two-pass protocol: apply -> chain re-run from "
                      "stitch; manifests corner-rotated conservatively "
                      "and regenerate"}

    if a.measure_only or already is not None or yaw == 0.0:
        outname = ("scene_yaw_verify.json" if already is not None
                   else "scene_yaw.json")
        (sdir / outname).write_text(json.dumps(record, indent=1))
        if already is not None:
            # verification on an applied scene (R-S2-121 pattern):
            # append, never clobber the apply evidence.
            main_f = sdir / "scene_yaw.json"
            rec0 = (json.loads(main_f.read_text(encoding="utf-8"))
                    if main_f.exists() else
                    {"scene": sc, "note": "verification only — no apply "
                                          "record was on disk"})
            from datetime import date as _date
            rec0.setdefault("verifications", []).append(
                {"date": str(_date.today()),
                 "yaw_deg": round(yaw, 2)})
            main_f.write_text(json.dumps(rec0, indent=1))
            print(f"[yaw] scene already de-tilted (yaw_applied="
                  f"{already}) — this re-measure is a VERIFICATION: "
                  f"{yaw:+.2f} deg (~0 = the apply held); appended to "
                  f"scene_yaw.json")
        elif yaw == 0.0 and not a.measure_only:
            print("[yaw] nothing to apply — the room is axis-aligned; "
                  "record written, state untouched")
        print(f"[yaw] measure-only record -> {outname}")
        return

    # ---- apply, with the built-in post-check before any write ----
    R_up, M = rotation_matrices(yaw, r2r)

    # POST-CHECK IN MEMORY: the rotated scene must measure ~0. A wrong
    # sign would read ~2x the tilt; wrong frame reads garbage. Nothing
    # is written unless this passes. Same cropped population the
    # measurement used, rotated in the upright frame (raw-M-then-
    # upright == upright-R_up: D M x = R_up D x by construction).
    chk_up = pts_up @ R_up.T
    f2, c2 = measure_floor_ceiling(chk_up)
    residual = measure_plan_yaw(band_xz(chk_up, f2, c2))
    if residual != 0.0:
        raise SystemExit(
            f"[yaw] REFUSING to write: post-rotation residual reads "
            f"{residual:+.2f} deg (expected inside the 1-deg dead "
            f"zone). The rotation is wrong for this scene's frame; "
            f"nothing was modified.")
    print(f"[yaw] post-check: rotated points re-measure at ~0 "
          f"(inside the 1-deg dead zone) — writing")

    ply_f = paths.ply(sc)
    names, data = read_ply(ply_f)
    ix = {n: i for i, n in enumerate(names)}
    xyz = data[:, [ix["x"], ix["y"], ix["z"]]].astype(np.float64)
    new_xyz = xyz @ M.T

    coll_f = sdir / "collider_registered.glb"
    targets = [ply_f, boot_f] + ([coll_f] if coll_f.exists() else [])
    for f in targets:
        bak = f.with_name(f.stem + "_preyaw" + f.suffix)
        if not bak.exists():
            shutil.copyfile(f, bak)

    data[:, ix["x"]] = new_xyz[:, 0].astype(np.float32)
    data[:, ix["y"]] = new_xyz[:, 1].astype(np.float32)
    data[:, ix["z"]] = new_xyz[:, 2].astype(np.float32)
    qm = mat_to_quat(M)
    qw, qx, qy, qz = (data[:, ix["rot_0"]].astype(np.float64),
                      data[:, ix["rot_1"]].astype(np.float64),
                      data[:, ix["rot_2"]].astype(np.float64),
                      data[:, ix["rot_3"]].astype(np.float64))
    nw, nx, ny, nz = quat_premul(qm, qw, qx, qy, qz)
    norm = np.sqrt(nw * nw + nx * nx + ny * ny + nz * nz)
    norm[norm == 0] = 1.0
    data[:, ix["rot_0"]] = (nw / norm).astype(np.float32)
    data[:, ix["rot_1"]] = (nx / norm).astype(np.float32)
    data[:, ix["rot_2"]] = (ny / norm).astype(np.float32)
    data[:, ix["rot_3"]] = (nz / norm).astype(np.float32)
    write_ply(ply_f, names, data)
    print(f"[yaw] gen_raw.ply rotated ({len(data):,} gaussians, "
          f"xyz + quats)")

    if coll_f.exists():
        import trimesh
        mesh = trimesh.load(coll_f, force="mesh")
        T = np.eye(4)
        T[:3, :3] = M
        mesh.apply_transform(T)
        mesh.export(coll_f)
        print(f"[yaw] collider rotated (bounds now "
              f"{np.round(mesh.bounds, 2).tolist()})")
    else:
        print("[yaw] no registered collider — colliderless scene")

    # extents: RECOMPUTED from the rotated cloud, frame_bootstrap's
    # own recipe (opacity>0.3, p1/p99) — NOT corner-rotated. extent_p1/99
    # is a robust box that must HUG the points; corner-rotating a tilted
    # box inflates it (~1.2 m on fresh06) and run_poly's box-mask indices
    # go negative -> empty interior -> trace crash (found live 08-12).
    alpha = 1 / (1 + np.exp(-data[:, ix["opacity"]]))
    op_xyz = new_xyz[alpha > 0.3]
    new_p1 = np.percentile(op_xyz, 1, axis=0).round(3).tolist()
    new_p99 = np.percentile(op_xyz, 99, axis=0).round(3).tolist()

    touched = rotate_derived_state(sdir, M, new_p1, new_p99)
    print(f"[yaw] derived state rotated: {', '.join(touched)}")

    boot["extent_p1"] = list(new_p1)
    boot["extent_p99"] = list(new_p99)
    boot["yaw_applied"] = round(yaw, 2)
    boot["yaw_note"] = ("scene_yaw.py de-tilted this scene (evidence: "
                        "scene_yaw.json); originals in *_preyaw.* files; "
                        "floor/ceiling y-invariant under the rotation")
    boot_f.write_text(json.dumps(boot, indent=1))

    record["yaw_applied_deg"] = round(yaw, 2)
    record["post_check_residual_deg"] = residual
    (sdir / "scene_yaw.json").write_text(json.dumps(record, indent=1))
    print(f"[yaw] frame_bootstrap updated (yaw_applied={yaw:+.2f}) -> "
          f"scene_yaw.json written")


if __name__ == "__main__":
    main()
