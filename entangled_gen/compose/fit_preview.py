"""
FIT PREVIEW (part of the shopping output process, 2026-08-03): place
every anchor's picked mesh -- compose/picks.json style #1 when the pick
stage has run (user 08-03B: final_candidates = THE shopping output),
else compose/shopping.json size-fit #1 -- into its box -- perm rotation + uniform scale + tiling, bottom-aligned (wall
items y-centered, ceiling items top-aligned) -- and write the result
as a RAW-frame GLB the scene viewer serves as its "fitted preview"
layer (viewer/serve.py /fitted_preview.glb, checkbox in the HUD).

This is the PLACER the fit loop drives (place -> jiggle -> check ->
walk, then the closing pass): it re-reads walk choices, snap seats,
rotation verdicts and its own prior output each round. Since R-S2-124
it also enforces the SIZE BAR: an item whose best candidate exceeds
DRY 0.65 on its worst axis is NOT placed and lands in `not_placed`
with a receipt -- better absent than wrong-sized (user 2026-08-12).
Re-run after every shopping.py run to refresh the layer.

Placement happens in the RENDER frame (y up, like the asset meshes),
then the whole scene is rotated into the RAW frame with the manifest's
raw_to_render signs (self-inverse, and rot180-about-z is a PROPER
rotation -- no mirroring) so the viewer needs no browser-side flip.

Output: out/<scene>/compose/fitted_preview.glb + fitted_preview.json
(what was placed: uid / perm / scale / tiles per item).

Run:  python compose/fit_preview.py --scene bedroom_marble
"""
import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402
from arch_walls import wall_axis_planes  # noqa: E402
# scene_state lives in the sibling graph/ package, not beside us, so its
# directory has to go on the path too (same two-step the other compose
# modules use, e.g. uniform_instances.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "graph"))
import scene_state  # noqa: E402

sys.path.insert(0, str(paths.REPO_ROOT / "composition"))
from assets_thor import load_asset  # noqa: E402
from thumbs import perm_rotation  # noqa: E402


def yaw_matrix(deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    T = np.eye(4)
    T[0, 0], T[0, 2], T[2, 0], T[2, 2] = c, s, -s, c
    return T


def yaw_about(center, deg):
    # same convention as rotation_check.py (+90 maps +z to +x)
    R = yaw_matrix(deg)
    T1 = np.eye(4); T1[:3, 3] = -np.asarray(center)
    T2 = np.eye(4); T2[:3, 3] = np.asarray(center)
    return T2 @ R @ T1


def footprint_cardinal_angle(m):
    """PCA CARDINAL SNAP (user 08-04, the obj_032 lesson): yaw (deg, to
    APPLY) that brings the mesh's TRUE footprint axes onto the room
    cardinals. ~1/3 of library meshes are baked mis-rotated inside
    their canonical frame, which inflates the AABB and fakes oversize
    verdicts. Min-area rotated rectangle over the footprint hull
    (rotating calipers); 0.0 when the oriented rectangle is not
    meaningfully tighter than the AABB (round / already-cardinal
    shapes must not be touched)."""
    pts = np.asarray(m.vertices[:, [0, 2]], np.float64)
    try:
        from scipy.spatial import ConvexHull
        pts = pts[ConvexHull(pts).vertices]
    except Exception:
        pass
    aabb_area = float(np.ptp(pts[:, 0]) * np.ptp(pts[:, 1]))
    best = None
    n = len(pts)
    for i in range(n):
        e = pts[(i + 1) % n] - pts[i]
        L = float(np.hypot(e[0], e[1]))
        if L < 1e-9:
            continue
        c, s = e[0] / L, e[1] / L
        q = pts @ np.array([[c, -s], [s, c]])   # yaw_matrix(theta) in 2D
        area = float(np.ptp(q[:, 0]) * np.ptp(q[:, 1]))
        if best is None or area < best[0]:
            best = (area, float(np.degrees(np.arctan2(s, c))))
    if best is None or best[0] > 0.95 * aabb_area:
        return 0.0
    ang = ((best[1] + 45.0) % 90.0) - 45.0
    return float(ang) if abs(ang) > 1.0 else 0.0


#: the fit canon's own tolerance (shopping's "every axis within 15%"),
#: granted to the 90/270 yaws ONLY when measured facing evidence
#: (pillows) demands the rotation — R-S2-166: a bed with its head at
#: the foot is a worse lie than a 15% overhang, and 1.05 vs 1.15 is
#: exactly what shipped fresh08's bed backwards (needed swap over by
#: 2%, both compliant yaws tied at dot 0, coin flip won).
FACE_EVIDENCE_TOL = 1.15


def place_candidate(mesh, cand, lo, hi, mount, face_dir=None,
                    face_hard=False):
    """One candidate mesh -> (posed instances filling the render-frame
    box [lo, hi] (k tiles along cand's tile axis), chosen facing yaw).

    FACING RULE (08-03, user: bookshelves faced the wall): library
    front convention = asset +z (verified by the user on a 32-asset
    front-view sheet). Among the four compass yaws whose footprint
    still fits the (sub-)box, pick the one pointing the front along
    face_dir (unit xz: away from the nearest wall, else toward the
    room middle). face_hard (R-S2-166): the direction is MEASURED
    evidence, not a preference — if no strict-fitting yaw can meet it,
    the 90/270 pair is retried at the fit canon's 15% before the tie
    is allowed to ship."""
    m = mesh.copy()
    P = perm_rotation(cand.get("perm", "xyz"))
    m.apply_transform(P)
    m.apply_scale(cand["scale"])
    # de-rotate crooked-in-file geometry to cardinal BEFORE any
    # footprint or facing logic reads the bounds
    pca_deg = footprint_cardinal_angle(m)
    if pca_deg:
        b0 = m.bounds
        m.apply_transform(yaw_about((b0[0] + b0[1]) / 2, pca_deg))
    k, axis = cand.get("k", 1), cand.get("axis", 0)
    face_deg, face_dot = 0, None
    if face_dir is not None:
        s0 = m.bounds[1] - m.bounds[0]
        sub_w = (hi[0] - lo[0]) / (k if axis == 0 else 1)
        sub_d = (hi[2] - lo[2]) / (k if axis == 2 else 1)
        # the front must be computed through the SAME pipeline the mesh
        # went through — perm, then the pca de-rotation, then the yaw
        # (the pca term was silently omitted before R-S2-166)
        rot_pca = yaw_matrix(pca_deg)[:3, :3] if pca_deg else np.eye(3)

        def _pick(swap_tol):
            best = None
            for deg in (0, 90, 180, 270):
                # 0/180 keep the placed footprint EXACTLY -- never gate
                # them (the old gate vetoed 180 whenever the scaled
                # asset legitimately overhung its box, so 12/30 items
                # silently kept arbitrary facing -- the backwards-shelf
                # bug). 90/270 swap extents: allow within swap_tol.
                if deg % 180 != 0:
                    ex, ez = s0[2], s0[0]
                    if ex > sub_w * swap_tol or ez > sub_d * swap_tol:
                        continue
                f = (yaw_matrix(deg)[:3, :3] @ rot_pca @ P[:3, :3]
                     @ np.array([0.0, 0.0, 1.0]))
                score = f[0] * face_dir[0] + f[2] * face_dir[1]
                if best is None or score > best[0]:
                    best = (score, deg)
            return best

        best = _pick(1.05)
        if face_hard and (best is None or best[0] <= 0.0):
            # measured evidence unreachable at the strict gate: grant
            # the canon 15% to the rotated pair (R-S2-166)
            relaxed = _pick(FACE_EVIDENCE_TOL)
            if relaxed is not None and relaxed[0] > (
                    best[0] if best else -2.0):
                best = relaxed
                print(f"[fit] facing evidence honored at the canon "
                      f"15% swap tolerance (strict 5% blocked the "
                      f"needed yaw) — dot {best[0]:+.2f}", flush=True)
        if best:
            face_deg, face_dot = best[1], round(float(best[0]), 2)
            if face_deg:
                m.apply_transform(yaw_matrix(face_deg))
    step = (hi[axis] - lo[axis]) / k
    out = []
    for i in range(k):
        inst = m.copy()
        blo, bhi = inst.bounds
        ctr = (blo + bhi) / 2
        t = np.zeros(3)
        for ax in (0, 2):
            target = (lo[ax] + hi[ax]) / 2
            if ax == axis:
                target = lo[ax] + step * (i + 0.5)
            t[ax] = target - ctr[ax]
        if mount == "ceiling":
            t[1] = hi[1] - bhi[1]
        elif mount == "wall":
            t[1] = (lo[1] + hi[1]) / 2 - ctr[1]
        else:
            t[1] = lo[1] - blo[1]
        inst.apply_translation(t)
        out.append(inst)
    return out, face_deg, face_dot, pca_deg


def main():
    t0 = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    args = ap.parse_args()

    cdir = paths.compose_dir(args.scene)
    sl = json.loads((cdir / "shopping.json").read_text(encoding="utf-8"))
    # STYLE PICKS (user 08-03B: picks.json final_candidates = THE shopping
    # output the fit loop walks). The preview places the style #1 when the
    # pick stage has run; shopping's size-fit #1 is only the fallback for
    # items the pick stage didn't cover.
    cur_uids_early = {it["id"]: {c["uid"]
                                 for c in (it.get("candidates") or [])}
                      for it in sl["items"]}
    style_pick = {}
    picks_p = cdir / "picks.json"
    if picks_p.exists():
        pk = json.loads(picks_p.read_text(encoding="utf-8"))
        for it in pk.get("items", []):
            fc = it.get("final_candidates") or []
            # same staleness guard as the walk choices below (R-S2-128)
            if fc and fc[0].get("uid") in cur_uids_early.get(it["id"],
                                                            set()):
                style_pick[it["id"]] = fc[0]
            elif fc:
                print(f"[fit_preview] VOIDING stale style pick for "
                      f"{it['id']}: not in the current candidate list")
    # CANDIDATE WALK overrides (compose/fit_walk.py): the fit loop's
    # verdict beats the style #1 when the pick overshoots its box.
    # ⚠ VALIDATED AGAINST CURRENT SHOPPING (R-S2-128, 2026-08-12):
    # walk choices deliberately accumulate across rounds, but a stored
    # choice whose uid is no longer in the item's CURRENT candidate
    # list was made against a shopping that no longer exists — that is
    # how a bed chosen from the withdrawn escalation pool kept standing
    # in for a console table through two canon changes. Void it, say
    # so, and let the current pick/candidates decide.
    cur_uids = {it["id"]: {c["uid"] for c in (it.get("candidates") or [])}
                for it in sl["items"]}
    walked = set()
    walk_p = cdir / "fit_walk.json"
    if walk_p.exists():
        wj = json.loads(walk_p.read_text(encoding="utf-8"))
        for iid, ch in (wj.get("choices") or {}).items():
            cand = ch.get("candidate")
            if not cand:
                continue
            if cand.get("uid") not in cur_uids.get(iid, set()):
                print(f"[fit_preview] VOIDING stale walk choice for "
                      f"{iid}: {cand.get('uid', '')[:8]} "
                      f"({cand.get('category')}) is not in the current "
                      f"candidate list")
                continue
            style_pick[iid] = cand
            walked.add(iid)
    man = {"frame": paths.frame_block(args.scene)}
    graph = json.loads((paths.scene_dir(args.scene) / "scene_graph.json")
                       .read_text(encoding="utf-8"))
    r2r = np.array(man["frame"].get("raw_to_render", [1, 1, 1]),
                   np.float32)
    # .get + skip: a W5 polygon CONNECTOR wall carries no axis-aligned
    # value_raw — it must not blow up this map (outline-only geometry)
    shell = {n["id"]: n["geometry"]["plane"]["value_raw"]
             for n in graph["nodes"] if n["id"].startswith("arch_")
             and (n["geometry"].get("plane") or {}).get("value_raw")
             is not None}
    xs_raw, zs_raw, _floor_raw, _ceil_raw = wall_axis_planes(graph["nodes"])
    wx = sorted((xs_raw[0] * r2r[0], xs_raw[-1] * r2r[0]))
    wz = sorted((zs_raw[0] * r2r[2], zs_raw[-1] * r2r[2]))
    room_c = ((wx[0] + wx[1]) / 2, (wz[0] + wz[1]) / 2)

    # OBSERVED facing (describe pass v8, user ruling: define forward
    # upstream -- the room already shows which way things face). RAW
    # world_dir -> render frame. Detected objects use this; invented
    # adds/swap-ins keep the wall/room-middle heuristic fallback.
    # THE CURRENT LAYER carries this testimony, with `judged` kept only as
    # a fallback for older graphs that have no layer. Reading `judged`
    # alone returned nothing for exactly the nodes the pipeline changed: a
    # piece the judges SPLIT off never existed in `judged`, and a node
    # merged away is still in it — so those items silently fell back to the
    # wall/room-middle guess instead of the facing the room actually shows.
    face_src = {n["id"]: (n.get("appearance") or {})
                for n in scene_state.nodes(graph)}
    for jn in graph.get("judged", {}).get("nodes", []):
        face_src.setdefault(jn["id"], jn.get("appearance") or {})
    observed_face = {}
    for nid, app in face_src.items():
        wd = (app.get("facing") or {}).get("world_dir")
        if wd:
            observed_face[nid] = (wd[0] * float(r2r[0]),
                                  wd[1] * float(r2r[2]))

    # PILLOW EVIDENCE (user GT 08-03: the bed lies SIDE-against the
    # wall, so wall-hug's touching-wall=back assumption broke): a
    # pillow sub marks its host's HEAD end; front = the opposite end.
    # Measured scene data (the pillow's recorded box), scene-agnostic,
    # fires only when a pillow sub exists.
    #
    # THE AXIS COMES FROM THE PILLOW'S OWN DISPLACEMENT, not the box
    # shape (user go 2026-08-12, the fresh03 bed): the old rule assumed
    # the head lies along the box's LONG horizontal axis and only asked
    # the pillow which END — but fresh03's bed lifted a near-square box
    # (2.333 x vs 2.294 z) and 4 cm of box noise picked the wrong axis
    # while the pillow sat 1.40 m up the other one. The pillow's
    # displacement vector from the host center carries the axis AND the
    # end; the box shape carries neither. Multiple pillows sum — they
    # agree at the head and their sideways scatter cancels.
    pillow_disp = {}   # host id -> summed pillow offset (render x, z)
    for s in sl.get("subs_deferred", []):
        if "pillow" not in s.get("name", "") or not s.get("box"):
            continue
        hb = next((it for it in sl["items"]
                   if it["id"] == s.get("host")), None)
        if not hb:
            continue
        hlo = np.asarray(hb["box"]["aabb_min"], np.float32) * r2r
        hhi = np.asarray(hb["box"]["aabb_max"], np.float32) * r2r
        hlo, hhi = np.minimum(hlo, hhi), np.maximum(hlo, hhi)
        plo = np.asarray(s["box"]["aabb_min"], np.float32) * r2r
        phi = np.asarray(s["box"]["aabb_max"], np.float32) * r2r
        pc, hc = (plo + phi) / 2, (hlo + hhi) / 2
        d = pillow_disp.setdefault(hb["id"], [0.0, 0.0])
        d[0] += float(pc[0] - hc[0])
        d[1] += float(pc[2] - hc[2])
    pillow_head = {}   # host id -> unit front (render frame)
    for hid, d in pillow_disp.items():
        ax = 0 if abs(d[0]) >= abs(d[1]) else 1
        if abs(d[ax]) < 1e-6:
            continue               # pillow dead-center: no evidence
        sign = 1.0 if d[ax] > 0 else -1.0
        pillow_head[hid] = ((-sign, 0.0) if ax == 0 else (0.0, -sign))

    def face_dir_of(item_id, lo, hi, mount):
        """(unit xz front direction, evidence source) -- layered by
        evidence strength (obj_096 + obj_032 lessons: witness facing
        is +-45deg quantized and oblique for wall-adjacent things,
        but geometry constrains them completely):
          wall-mounted            -> the wall's inward normal
          wall-HUGGING (box EDGE within 0.15 m of a wall -- center
            distance lied for deep furniture) -> that wall's normal
          else observed witness facing (line-of-sight converted)
          else near-wall / room-middle heuristic (invented adds,
          no_front items). Ceiling items have no facing."""
        if mount == "ceiling":
            return None, None
        # edge gap to each wall: (gap, axis, inward normal)
        walls = [(lo[0] - wx[0], "x", (1.0, 0.0)),
                 (wx[1] - hi[0], "x", (-1.0, 0.0)),
                 (lo[2] - wz[0], "z", (0.0, 1.0)),
                 (wz[1] - hi[2], "z", (0.0, -1.0))]
        # THIN-AXIS RULE (obj_127 door / obj_043 corner-shelf lesson):
        # a wall thing faces along its thin horizontal axis (a door
        # slab's normal, a shelf's depth) -- near a corner the SIDE
        # wall can be nearer by gap than the thing's own wall. Prefer
        # thin-axis walls among the candidates; nearest gap only for
        # near-square boxes or when no thin-axis wall qualifies.
        sx, sz = hi[0] - lo[0], hi[2] - lo[2]
        thin = "x" if sx * 1.3 < sz else "z" if sz * 1.3 < sx else None

        def pick(cands):
            pref = [w for w in cands if w[1] == thin] if thin else []
            g, _, nrm = min(pref or cands)
            return g, nrm

        if mount == "wall":
            return pick(walls)[1], "wall_constraint"
        if item_id in pillow_head:   # measured head-end evidence
            return pillow_head[item_id], "pillow_evidence"
        # 0.30: lift boxes run fat (obj_032 flush shelf measured a
        # 0.23 m edge gap); true huggers here are <= 0.23, the next
        # nearest walls 0.37+, so 0.30 splits them with margin
        hug = [w for w in walls if w[0] < 0.30]
        if hug:
            return pick(hug)[1], "wall_hug"
        d = min(walls)[0]
        n = min(walls)[2]
        if item_id in observed_face:
            return observed_face[item_id], "observed"
        if d < 0.6:
            return n, "heuristic"
        cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
        v = np.array([room_c[0] - cx, room_c[1] - cz])
        L = float(np.hypot(v[0], v[1]))
        return ((v[0] / L, v[1] / L) if L > 1e-6 else None), "heuristic"
    # FIT TARGET = SNAPPED BOX (user ruling 08-04): meshes fit into the
    # PH1-adjudicated snapped positions, not the observed graph boxes --
    # the observed box is the record, the snapped box is where a real
    # thing can physically stand (the bed's observed box sat 84 mm into
    # the floor). Invented adds/swaps have no snap record and keep their
    # proposal boxes.
    snap_box, snap_disp = {}, {}
    sp = cdir / "snap.json"
    if sp.exists():
        snj = json.loads(sp.read_text(encoding="utf-8"))
        for o in snj.get("objects", []):
            if o.get("snapped_aabb"):
                snap_box[o["id"]] = o["snapped_aabb"]
                snap_disp[o["id"]] = o.get("disposition")

    # ROTATION APPLY GATE (user-approved 08-04, PLAN_FIT_LOOP.md): apply
    # rotation_check.json verdicts ONLY at HIGH confidence and non-zero
    # -- 13/31 tail answers flip between stimulus framings, so low and
    # medium non-zero verdicts are recorded as flags for the fit loop's
    # judge, never applied. EXCEPTION (08-05, with the wall-legality
    # menu): a verdict chosen from a legality-CONSTRAINED menu
    # (mapping < 4 options) applies at any confidence -- every option
    # offered was a legal in-wall pose, so the worst case is the wrong
    # LEGAL flip, never a sideways door. Effort follows error cost. The verdict is an extra yaw about the placed
    # item's combined-bounds center (render frame), exactly how
    # rotation_check spun its candidate renders.
    # Verdicts are DELTAS on the preview rotation_check measured: a 0
    # verdict on a corrected object means KEEP the correction. The
    # carried basis comes from the record's measured_applied_deg;
    # records from before that field fall back to the prior
    # fitted_preview.json on disk (= the preview that was measured).
    prior_applied = {}
    fp_path = cdir / "fitted_preview.json"
    if fp_path.exists():
        for p in json.loads(fp_path.read_text(
                encoding="utf-8")).get("placed", []):
            prior_applied[p["id"]] = (p.get("uid"),
                                      p.get("rotcheck_applied_deg", 0.0))
    rot_verdicts = {}
    rc_path = cdir / "rotation_check.json"
    if rc_path.exists():
        rc = json.loads(rc_path.read_text(encoding="utf-8"))
        for run in rc.get("runs", []):
            deg = run.get("degrees")
            if deg is None:
                continue
            constrained = 0 < len(run.get("mapping") or {}) < 4
            rot_verdicts[run["item"]] = {
                "degrees": float(deg),
                "confidence": run.get("confidence"),
                "measured_uid": run.get("measured_uid"),
                "measured_applied_deg": run.get("measured_applied_deg"),
                "constrained_menu": constrained,
                "apply": ((run.get("confidence") == "high" or constrained)
                          and abs(deg) > 1e-6)}

    if float(np.prod(r2r)) < 0:
        print("[fit_preview] WARNING: raw_to_render has odd sign count "
              "-- render->raw would MIRROR meshes; check the frame")
    to_raw = np.diag([r2r[0], r2r[1], r2r[2], 1.0])

    scene = trimesh.Scene()
    placed, failed, not_placed = [], [], []
    fdir_by = {}   # item id -> decided front (render frame)
    # THE SIZE BAR = the ruled DRY constant, one knob, no new number.
    # The user ruled this whole design ONCE ALREADY (2026-08-05C SR4c,
    # sub tier): "best of the WHOLE shortlist over DRY 0.65 -> adds
    # drop entirely, detections drop with a recorded complaint" — the
    # anchor tier simply never inherited it because the sub rounds sat
    # deferred in experiments/. R-S2-124 brings the anchors under the
    # same rule at the same bar.
    from fit_feedback import DRY_SCORE as SIZE_BAR
    for r in sl["items"]:
        c = style_pick.get(r["id"]) or (r["candidates"][0]
                                        if r.get("candidates") else None)
        if not c:
            continue
        # NOTHING TRULY FITS -> NOT PLACED, for EVERY item (user rulings
        # 2026-08-12, R-S2-123 + 124). Assets place at NATIVE SIZE
        # (08-03B canon, no rescale), so "the point of the boxes is that
        # they should be around that size. a single bed is sized as a
        # single bed, a door is sized as a door not a barn. nothing
        # will be exact due to assets, so slightly generous margins."
        # An item whose BEST candidate misses its box by more than
        # SIZE_BAR on the worst axis stands NOWHERE rather than at a
        # wrong size — counted and named in `not_placed`. This scene's
        # own data: a door whose best was 219% off and a console at
        # 1718% off both stood in the preview before this bar.
        # (fit_feedback's DRY_SCORE 0.65 walk-back records are separate
        # and unchanged.)
        bs = min((float(c2.get("score", 9.9))
                  for c2 in (r.get("candidates") or [])),
                 default=9.9)
        if bs > SIZE_BAR:
            not_placed.append(
                {"id": r["id"], "name": r["name"],
                 "source": r.get("source"),
                 "best_score": round(bs, 3),
                 "why": (f"no candidate within the size bar "
                         f"(best worst-axis {bs:.0%} > "
                         f"{SIZE_BAR:.0%}) — left out by user ruling "
                         f"2026-08-12: better absent than wrong-sized")})
            continue
        try:
            mesh = load_asset(c["uid"])
        except Exception as ex:
            failed.append({"id": r["id"], "uid": c["uid"],
                           "error": str(ex)[:200]})
            continue
        sb = snap_box.get(r["id"])
        raw_lo = sb["mn"] if sb else r["box"]["aabb_min"]
        raw_hi = sb["mx"] if sb else r["box"]["aabb_max"]
        lo = np.asarray(raw_lo, np.float32) * r2r
        hi = np.asarray(raw_hi, np.float32) * r2r
        lo, hi = np.minimum(lo, hi), np.maximum(lo, hi)
        fdir, fsrc = face_dir_of(r["id"], lo, hi, r["mount"])
        fdir_by[r["id"]] = fdir
        insts, face_deg, face_dot, pca_deg = place_candidate(
            mesh, c, lo, hi, r["mount"], face_dir=fdir,
            face_hard=(fsrc == "pillow_evidence"))
        rv = rot_verdicts.get(r["id"])
        # basis + delta, only when measured on THIS asset -- a verdict
        # corrects one mesh's canonical-front quirk (the bed lesson)
        # and does not transfer to a different pick
        uid_ok = bool(rv and rv.get("measured_uid") == c["uid"])
        base_deg = 0.0
        if uid_ok:
            base_deg = rv.get("measured_applied_deg")
            if base_deg is None:   # pre-field record: prior preview
                pu = prior_applied.get(r["id"])
                base_deg = (pu[1] if pu and pu[0] == c["uid"] else 0.0)
        rot_deg = (base_deg
                   + (rv["degrees"] if uid_ok and rv["apply"] else 0.0)
                   ) % 360.0
        if rot_deg:
            allb = np.vstack([i.bounds for i in insts])
            ctr = (allb.min(axis=0) + allb.max(axis=0)) / 2
            spin = yaw_about(ctr, rot_deg)
            for inst in insts:
                inst.apply_transform(spin)
        # MESH-FLUSH SNAP (user 08-04): the ACTUAL mesh back face must
        # touch the wall plane -- box alignment leaves an air gap
        # whenever the asset is thinner than its box. fdir for wall
        # mounts is exactly the chosen wall's inward normal, so the
        # push direction and plane are already decided. After the spin,
        # so final bounds are used.
        flush_push = None
        if r["mount"] == "wall" and fdir is not None:
            allb = np.vstack([i.bounds for i in insts])
            mlo, mhi = allb.min(axis=0), allb.max(axis=0)
            d = np.zeros(3)
            if abs(fdir[0]) >= abs(fdir[1]):
                d[0] = (wx[0] - mlo[0]) if fdir[0] > 0 else (wx[1] - mhi[0])
            else:
                d[2] = (wz[0] - mlo[2]) if fdir[1] > 0 else (wz[1] - mhi[2])
            if abs(d[0]) + abs(d[2]) > 1e-4:
                for inst in insts:
                    inst.apply_translation(d)
            flush_push = round(float(d[0] + d[2]), 3)
        # DUAL ATTACHMENT (user 08-04: "a door belongs to both a wall
        # and a floor"): a wall item whose FIT BOX reaches the floor
        # is floor-standing -- bottom-align the mesh (the box bottom =
        # the floor where snap agreed), never center it mid-air. The
        # attachment set is box-derived, no categories.
        attach = [r["mount"]]
        fy = shell["arch_floor"] * r2r[1]
        if (r["mount"] == "wall"
                and lo[1] - fy < 0.10):
            allb = np.vstack([i.bounds for i in insts])
            dy = lo[1] - allb[:, 1].min()
            if abs(dy) > 1e-4:
                for inst in insts:
                    inst.apply_translation([0.0, dy, 0.0])
            attach.append("floor")
        for j, inst in enumerate(insts):
            inst.apply_transform(to_raw)   # render -> raw, baked
            scene.add_geometry(inst,
                               node_name=f'{r["id"]}_t{j}',
                               geom_name=f'{r["id"]}_t{j}')
        placed.append({"id": r["id"], "name": r["name"],
                       "uid": c["uid"], "perm": c.get("perm", "xyz"),
                       "scale": c["scale"], "k": c.get("k", 1),
                       "face_yaw_deg": face_deg,
                       "face_source": fsrc,
                       # dot(achieved front, target); < 0.9 = the
                       # chosen perm cannot reach the target with a
                       # footprint-legal turn -- a FIT-LOOP work item
                       # (orientation must join candidate scoring)
                       "face_dot": face_dot,
                       "face_conflict": (face_dot is not None
                                         and face_dot < 0.9),
                       # dot <= 0: every footprint-legal yaw is
                       # perpendicular-or-worse to the evidence — the
                       # shipped facing is a TIE-BREAK, not a decision
                       # (the fresh03 bed shipped headboard-at-foot on
                       # exactly this silent coin flip, user 08-12)
                       "face_unmet": (face_dot is not None
                                      and face_dot <= 0.0),
                       "front_dir_raw": (
                           [round(float(fdir[0] * float(r2r[0])), 3),
                            round(float(fdir[1] * float(r2r[2])), 3)]
                           if fdir else None),
                       "rotcheck_applied_deg": round(rot_deg, 1),
                       "rotcheck_flag": (
                           {"degrees": rv["degrees"],
                            "confidence": rv["confidence"],
                            "measured_uid": rv.get("measured_uid")}
                           if rv and abs(rv["degrees"]) > 1e-6
                           and not (uid_ok and rv["apply"]) else None),
                       "pick_source": ("walk" if r["id"] in walked
                                       else "style_pick"
                                       if r["id"] in style_pick
                                       else "size_fit"),
                       "fit_box": {"aabb_min": list(raw_lo),
                                   "aabb_max": list(raw_hi)},
                       "snap_disposition": snap_disp.get(r["id"]),
                       # signed metres the mesh moved to touch its wall
                       "wall_flush_push_m": flush_push,
                       # crooked-asset correction applied (deg, 0 = none)
                       "pca_snap_deg": round(pca_deg, 1),
                       # box-derived attachment set (wall+floor = door)
                       "attachment": attach,
                       "mount": r["mount"], "score": c["score"]})

    # SUB FACING = HOST INHERITANCE (obj_032 lesson: things in/on a
    # shelf face wherever the shelf faces; their own photo readings
    # are grazing-angle noise). Walk the host chain until it reaches
    # a placed item's decided front; unresolvable hosts (e.g. the
    # ceiling light) leave the sub without a preview front. The sub
    # placement round applies the same contract with real meshes.
    host_of = {s["id"]: s.get("host")
               for s in sl.get("subs_deferred", [])}
    sub_front = {}
    for _ in range(4):   # host chains are short; sub-of-sub resolves
        for sid, h in host_of.items():
            if sid in sub_front or not h:
                continue
            f = fdir_by.get(h) or sub_front.get(h)
            if f:
                sub_front[sid] = f
    subs_front = [{"id": sid, "host": host_of[sid],
                   "face_source": "host_inherit",
                   "front_dir_raw":
                       [round(float(f[0] * float(r2r[0])), 3),
                        round(float(f[1] * float(r2r[2])), 3)]}
                  for sid, f in sorted(sub_front.items())]

    gpath = cdir / "fitted_preview.glb"
    gpath.write_bytes(scene.export(file_type="glb"))
    (cdir / "fitted_preview.json").write_text(json.dumps({
        "scene": args.scene, "built": str(date.today()),
        "generated_by": "compose/fit_preview.py",
        "graph_fingerprint": paths.graph_fingerprint(args.scene),
        "note": "NAIVE #1-candidate placement (no fit loop); RAW-frame "
                "glb for the viewer's fitted-preview layer; "
                "rotation_check HIGH-confidence verdicts applied "
                "(rotcheck_applied_deg), lower-confidence non-zero "
                "verdicts flagged (rotcheck_flag)",
        "elapsed_s": round(time.time() - t0, 1),
        "placed": placed, "subs_front": subs_front, "failed": failed,
        "not_placed": not_placed,
    }, indent=1), encoding="utf-8")
    napp = sum(1 for p in placed if p["rotcheck_applied_deg"])
    nflag = sum(1 for p in placed if p["rotcheck_flag"])
    print(f"[fit_preview] wrote {gpath} "
          f"({gpath.stat().st_size / 1e6:.1f} MB, {len(placed)} items, "
          f"{napp} rotations applied, {nflag} flagged, "
          f"{len(failed)} failed, {len(not_placed)} left out (nothing "
          f"fits), {time.time() - t0:.0f}s)")
    for np_ in not_placed:
        print(f"  NOT PLACED {np_['id']:16s} {str(np_['name']):22s} "
              f"{np_['why']}")


if __name__ == "__main__":
    main()
