"""SLICE-VOTE CARVE — the box-repair stage (USER-DESIGNED 2026-08-06
cone-map session; hardened over 4 whole-scene living runs 08-06/07,
REVIEW_LOG R-S2-26..30, all USER-PASSED).

STATUS: user-passed on living_marble (R-S2-29 + R-S2-30); bedroom
regression WAIVED by user 08-06. NOT yet wired into the canonical
runner — map promotion pending. Output stays a PREVIEW manifest until
wiring. Served in the viewer as the "slicevote" box-source layer.

Per resolved graph node:
0. EXEMPTIONS (geometric, never label lists): ceiling-mounted (top
   within 0.35 m of the shell ceiling + bottom in the upper half of
   the room) -> kept_ceiling; wall-flush (within 0.20 m of a shell
   wall plane + < 0.30 m thin along its normal) -> kept_wall;
   floor-flush (bottom within 0.20 m of the shell floor + < 0.30 m
   tall) -> kept_floor (user ruling 2026-08-07: rugs/mats are the
   wall-flush disease rotated to the floor — protected structurally,
   no class names). All keep the resolved box verbatim — flat objects
   have no side silhouette and their slices degenerate.
0b. SHELL ELECTORATE FILTER (user ruling 2026-08-07, the L-notch floor
   finding): a dot lying on a measured shell plane (floor/wall/ceiling
   within SHELL_EPS) is STRUCTURE and cannot be ELECTED as an object
   member — claims are ray volumes with no depth test, so notch/gap
   floor dots collect claims from cameras whose rays end on the object
   behind them. Renders/claims unchanged (caches stay valid); the
   filter zeroes those dots' votes at tally time. Exempt (kept_*)
   objects never vote, so flat-on-shell objects are unaffected.
1. SLICE: PRIMARY = top-box vertical prism — GroundingDINO box on the
   cached WSL top/ctop plan render (prior-location-gated), corners
   cast across the OBJECT's height band, margin min(30%, 0.35 m)/side.
   FALLBACK (no top detection) = original-box wedge, capped margin.
2. RENDER + DETECT, escalation ladder (user design 08-07):
   TIER 1  4 near-cardinal VIEW-TUNNEL cards at object height (full
           scene minus the camera->slice hole; occluders culled,
           context intact; re-detect gated to the slice's screen box);
   TIER 2  if >=3 of 4 cards unproductive (<50 claimed dots): add 4
           EYE-HEIGHT cardinal tunnel cards as extra voters (Marble is
           biased toward eye-height capture — proven on obj_004 book:
           0/4 at object height, 4/4 at eye height);
   TIER 3  election still empty: isolation retry (slice alone on
           black) with the cards re-detected;
   TIER 4  original box ships, status 'kept' (recorded, never silent).
3. VOTE: cards + TOP view's mask + ORIGINAL standpoint (member-mask
   union = ONE voter); dot kept at >=3 votes (gate degrades only when
   fewer voters exist); anchored cluster wins, culled ones recorded.
4. ARM ASSIGNMENT (user option-2): each node keeps the vote survivors
   ITS OWN original masks vouch for (L-sectional split); cluster-box
   fallback when sp0 coverage is thin; <50%-volume flag -> judge.
5. OUTLIER GUARD (user rule): shipping box > OUTLIER_K x original
   volume -> original ships (kept_outlier), vote box recorded as doubt.

Outputs (per scene): scene_manifest_slicevote_preview.json,
pool_retake/slicevote_report.json (rule.tiers records escalation),
pool_retake/conemap.json (viewer cone-map layer), conemap_obj_*.png,
cone_map.html.

Run:  PYTHONUTF8=1 HF_HUB_OFFLINE=1 python carve_slicevote.py
      --scene living_marble [--only obj_004,...] [--gate 3] [--res 768]
      (PYTHONUTF8 required when stdout is redirected — cp1252 chokes
      on the vote glyphs)
"""
import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.spatial import ConvexHull
from matplotlib.path import Path as MplPath

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paths  # noqa: E402
from pano_lift import crop_cam_raw  # noqa: E402
from sweep_recenter import c2w_from_eye_aim  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--scene", required=True)
ap.add_argument("--only", default="",
                help="comma-separated node ids (default: all resolved)")
ap.add_argument("--gate", type=int, default=3,
                help="votes required (degrades when fewer voters exist)")
ap.add_argument("--res", type=int, default=768)
a = ap.parse_args()

SCENE = a.scene
RES = a.res
DET_THR = 0.20
PAD = 0.30
CAP_M = 0.35
FOV_GOOD = 55.0
OFF_AXIS = 10.0
WALL_PAD = 0.30
EMPTY_R = 0.30
EMPTY_MAX = 1500
DIL_ISO = 8
OUTLIER_K = 8.0
SHELL_EPS = 0.03   # m — shell electorate filter (user 2026-08-07, in the
                   # approved 2-3 cm band; shell is collider-agreed 5-36mm)

sd = paths.scene_dir(SCENE)
rdir = sd / "pool_retake"
rdir.mkdir(exist_ok=True)
sdir = rdir / "slices"
sdir.mkdir(exist_ok=True)
# renders are slice+camera dependent: stale-cache poison — wipe det
# overlays always; the renderer itself skips byte-identical re-renders
for f in sdir.glob("vote_*_det.png"):
    f.unlink()


def to_wsl(p):
    p = str(Path(p).resolve())
    return "/mnt/" + p[0].lower() + p[2:].replace("\\", "/")


# ---- raw ply rows (subset writing keeps every gaussian attribute) ----
PLY = paths.ply(SCENE)
print("[carve] reading raw ply rows ...", flush=True)
_f = open(PLY, "rb")
_header = [_f.readline(), _f.readline()]
_names, _n = [], None
while True:
    line = _f.readline()
    _header.append(line)
    ls = line.strip()
    if ls.startswith(b"element vertex"):
        _n = int(ls.split()[-1])
    elif ls.startswith(b"property"):
        _names.append(ls.split()[2].decode())
    elif ls == b"end_header":
        break
ROWS = np.fromfile(_f, dtype="<f4",
                   count=_n * len(_names)).reshape(_n, len(_names))
_f.close()
col = {nm: i for i, nm in enumerate(_names)}
alpha_all = 1 / (1 + np.exp(-ROWS[:, col["opacity"]]))
KEEP = alpha_all > 0.3
ROWS_K = ROWS[KEEP]
xyz = ROWS_K[:, [col["x"], col["y"], col["z"]]].astype(np.float32)
print(f"[carve] {len(xyz):,} gaussians after opacity filter", flush=True)


def write_subset_ply(mask, out_path):
    sub = ROWS_K[mask]
    with open(out_path, "wb") as f:
        for line in _header:
            if line.strip().startswith(b"element vertex"):
                f.write(f"element vertex {len(sub)}\n".encode())
            else:
                f.write(line)
        sub.astype("<f4").tofile(f)
    return len(sub)


g = json.loads((sd / "scene_graph.json").read_text(encoding="utf-8"))
nodes = g["resolved"]["nodes"]
if a.only:
    want = set(a.only.split(","))
    nodes = [n for n in nodes if n["id"] in want]
eye0 = np.array(json.loads((sd / "rig_sp0" / "pano_selfrender_meta.json")
                           .read_text())["eye_raw"])
sh = json.loads((sd / "room_shell.json").read_text())
CEIL, FLOOR = sh["ceiling_y_raw"], sh["floor_y_raw"]
below_ceil = xyz[:, 1] > (CEIL + 0.08)
_r2r = sh["frame"]["raw_to_render"]
_xs, _zs = [], []
for w in sh["walls"]:
    v = w["plane_upright_m"] * (_r2r[0] if w["axis"] == "x" else _r2r[2])
    (_xs if w["axis"] == "x" else _zs).append(v)
XLO, XHI, ZLO, ZHI = min(_xs), max(_xs), min(_zs), max(_zs)


def in_bounds(eye):
    return (XLO + WALL_PAD < eye[0] < XHI - WALL_PAD
            and ZLO + WALL_PAD < eye[2] < ZHI - WALL_PAD
            and CEIL + WALL_PAD < eye[1] < FLOOR - WALL_PAD)


def empty_at(eye):
    d = xyz - eye
    return int((np.einsum("ij,ij->i", d, d) < EMPTY_R * EMPTY_R).sum())


class MatCamLite:
    def __init__(self, R, pos, f, cx, cy):
        self.R, self.pos = R, pos
        self.f, self.cx, self.cy = f, cx, cy

    def project(self, pts):
        rel = (pts - self.pos) @ self.R.T
        x, y, z = rel[:, 0], rel[:, 1], rel[:, 2]
        with np.errstate(divide="ignore", invalid="ignore"):
            u = self.cx + self.f * x / z
            v = self.cy - self.f * y / z
        return u, v, z


def make_cam(eye, aim, fov, res):
    M = c2w_from_eye_aim(eye, aim, [0.0, -1.0, 0.0])
    R = np.stack([M[:3, 0], -M[:3, 1], M[:3, 2]])
    f = res / (2 * math.tan(math.radians(fov) / 2))
    return MatCamLite(R, np.asarray(eye, np.float64), f, res / 2, res / 2)


def roty(v, deg):
    th = math.radians(deg)
    ca, sa = math.cos(th), math.sin(th)
    return np.array([ca * v[0] + sa * v[2], v[1], -sa * v[0] + ca * v[2]])


def top_cam_for(n):
    geo = n["geometry"]
    c = np.array(geo["center"], float)
    half = max(geo["size"]) / 2
    dist = float(np.clip(
        1.5 * max(half, 0.15) / math.tan(math.radians(FOV_GOOD) / 2),
        1.2, 4.0))
    d0 = c - eye0
    d0[1] = 0
    if np.linalg.norm(d0) < 0.3:
        d0 = np.array([1.0, 0, 0])
    d0 /= np.linalg.norm(d0)
    out = []
    tilt = math.radians(max(OFF_AXIS, 15.0))
    up_dir = np.array([math.sin(tilt) * d0[0], -math.cos(tilt),
                       math.sin(tilt) * d0[2]])
    up_dir /= np.linalg.norm(up_dir)
    eye = c + up_dir * dist
    eye[1] = max(c[1] + up_dir[1] * dist, CEIL + WALL_PAD + 0.05)
    top_ok = False
    if in_bounds(eye) and empty_at(eye) <= EMPTY_MAX:
        dist_act = float(np.linalg.norm(eye - c))
        fov = float(np.clip(math.degrees(
            2 * math.atan(1.5 * max(half, 0.15) / dist_act)), 35, 75))
        out.append(("top", eye, fov))
        top_ok = True
    need = 1.5 * max(half, 0.15) / math.tan(math.radians(FOV_GOOD) / 2)
    if not top_ok or dist < need - 1e-6:
        up = np.array([math.sin(math.radians(10)) * d0[0], -1.0,
                       math.sin(math.radians(10)) * d0[2]])
        up /= np.linalg.norm(up)
        eye = c + up * max(need, 2.0)
        fov = float(np.clip(math.degrees(
            2 * math.atan(1.5 * max(half, 0.15)
                          / float(np.linalg.norm(eye - c)))), 35, 75))
        out.append(("ctop", eye, fov))
    return out, c


import torch  # noqa: E402
dev = "cuda" if torch.cuda.is_available() else "cpu"
from transformers import (AutoProcessor,  # noqa: E402
                          GroundingDinoForObjectDetection,
                          SamModel, SamProcessor)
print("[carve] loading detector ...", flush=True)
gd_proc = AutoProcessor.from_pretrained("IDEA-Research/grounding-dino-base")
gd = GroundingDinoForObjectDetection.from_pretrained(
    "IDEA-Research/grounding-dino-base").to(dev)
gd.eval()
sam = SamModel.from_pretrained("facebook/sam-vit-base").to(dev)
sam_proc = SamProcessor.from_pretrained("facebook/sam-vit-base")

man = json.loads((sd / "scene_manifest_pano2c_rc_f30.json").read_text())
f30_by_id = {o["id"]: o for o in man["objects"]}
pool_j = json.loads((sd / "rig_sp0" / "lift_poolc.json").read_text())["pool"]
dets_all = json.loads((sd / "rig_sp0" / "seg_batched20" /
                       "detections.json").read_text())
_vc, _vm = {}, {}


def member_mask(m):
    view = m["view"]
    if view not in _vm:
        f = sd / "rig_sp0" / "seg_batched20" / f"{view}_masks.npy"
        _vm[view] = np.load(f) if f.exists() else None
    masks = _vm[view]
    if masks is None:
        return None
    for i, d in enumerate(dets_all.get(view, [])):
        if all(abs(d["box"][k] - m["box"][k]) < 1.0 for k in m["box"]):
            return masks[i] if i < len(masks) else None
    return None


def view_cam0(view):
    if view not in _vc:
        side = json.loads((sd / "rig_sp0" / "crops" / f"{view}.json")
                          .read_text())
        _vc[view] = crop_cam_raw(side, list(eye0))
    return _vc[view]


def gdino_best(img, prompt, prior_box=None):
    inputs = gd_proc(images=img, text=prompt + ".",
                     return_tensors="pt").to(dev)
    with torch.no_grad():
        outputs = gd(**inputs)
    det = gd_proc.post_process_grounded_object_detection(
        outputs, inputs["input_ids"], threshold=DET_THR,
        text_threshold=0.25, target_sizes=[img.size[::-1]])[0]
    W, H = img.size
    best = None
    for score, box in zip(det["scores"], det["boxes"]):
        b = [float(x) for x in box]
        if (b[2] - b[0]) >= 0.95 * W and (b[3] - b[1]) >= 0.95 * H:
            continue
        if prior_box is not None:
            ix0, iy0 = max(b[0], prior_box[0]), max(b[1], prior_box[1])
            ix1, iy1 = min(b[2], prior_box[2]), min(b[3], prior_box[3])
            inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
            area = (b[2] - b[0]) * (b[3] - b[1]) + 1e-9
            if inter / area < 0.3:
                continue
        if best is None or float(score) > best[0]:
            best = (float(score), b)
    return best


def sam_mask(img, box, dil):
    sinp = sam_proc(img, input_boxes=[[box]], return_tensors="pt").to(dev)
    with torch.no_grad():
        souts = sam(**sinp, multimask_output=False)
    mask = sam_proc.image_processor.post_process_masks(
        souts.pred_masks.cpu(), sinp["original_sizes"].cpu(),
        sinp["reshaped_input_sizes"].cpu())[0].squeeze(1).numpy()[0] > 0
    return ndimage.binary_dilation(mask, iterations=dil)


def fragments_box(K, prior_lo, prior_hi):
    if len(K) < 50:
        return None, []
    vox = np.floor(K / 0.15).astype(np.int64)
    uniq, inv_idx = np.unique(vox, axis=0, return_inverse=True)
    parent = list(range(len(uniq)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    vset = {tuple(v): i for i, v in enumerate(uniq)}
    for i, v in enumerate(uniq):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    j = vset.get((v[0] + dx, v[1] + dy, v[2] + dz))
                    if j is not None and j != i:
                        ri, rj = find(i), find(j)
                        if ri != rj:
                            parent[rj] = ri
    roots = np.array([find(i) for i in range(len(uniq))])
    frag_of_pt = roots[inv_idx]
    frags = []
    for root in np.unique(frag_of_pt):
        m = frag_of_pt == root
        if m.sum() < 50:
            continue
        flo = np.percentile(K[m], 1, axis=0)
        fhi = np.percentile(K[m], 99, axis=0)
        ilo, ihi = np.maximum(flo, prior_lo), np.minimum(fhi, prior_hi)
        ov = (np.prod(np.clip(ihi - ilo, 0, None))
              / max(np.prod(fhi - flo), 1e-9))
        frags.append({"n_pts": int(m.sum()), "overlap_prior": float(ov),
                      "lo": flo, "hi": fhi})
    if not frags:
        return None, []
    frags.sort(key=lambda f: (-round(f["overlap_prior"], 2), -f["n_pts"]))
    return frags[0], frags


import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

VIEW_COLORS = {"card0": "#e41a1c", "card1": "#377eb8",
               "card2": "#4daf4a", "card3": "#984ea3",
               "eyecard0": "#ff9e9e", "eyecard1": "#9ecfff",
               "eyecard2": "#a8e6b0", "eyecard3": "#d9a8e8",
               "iso0": "#b01214", "iso1": "#2a5f8f",
               "iso2": "#3a8a41", "iso3": "#763f80",
               "top": "#ff7f00", "sp0-original": "#888888",
               "slice": "#ffffff"}


def draw_box(ax, lo, hi, ax0, ax1, color, ls, lw, label=None, flip1=False):
    x0, x1 = lo[ax0], hi[ax0]
    y0, y1 = lo[ax1], hi[ax1]
    if flip1:
        y0, y1 = -hi[ax1], -lo[ax1]
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False,
                           edgecolor=color, linestyle=ls, linewidth=lw,
                           label=label))


# ================= per-object: slice -> render -> detect -> vote =======
rows_html = []
cm_objects = []
kept_exempt = []
for n in nodes:
    nid, name = n["id"], n["name"]
    geo = n["geometry"]
    lo0 = np.array(geo["aabb_min"])
    hi0 = np.array(geo["aabb_max"])
    corners = np.array([[x, y, z] for x in (lo0[0], hi0[0])
                        for y in (lo0[1], hi0[1]) for z in (lo0[2], hi0[2])])
    print(f"[carve] {nid} {name}", flush=True)

    # CEILING EXEMPTION (user ruling 2026-08-06 after R-S2-27): a flat
    # ceiling-mounted object has no side silhouette for the cardinals,
    # and the floor-anchored height band slices the whole room column
    # beneath it (the x288-x5027 blowups). Geometric test only — hangs
    # from the ceiling plane AND stays in the upper half of the room
    # (y-down frame: CEIL < FLOOR) — never a label list.
    room_h = FLOOR - CEIL
    if (lo0[1] - CEIL) < 0.35 and (hi0[1] - CEIL) < 0.5 * room_h:
        print("[carve]  ceiling-mounted — carve exempt, resolved box "
              "kept verbatim", flush=True)
        kept_exempt.append({
            "id": nid, "name": name, "nviews_vote": 0,
            "status": "kept_ceiling",
            "boxes": {"original":
                      {"lo": [round(float(v), 3) for v in lo0],
                       "hi": [round(float(v), 3) for v in hi0]}},
            "rule": {"kept": "ceiling-mounted — carve exempt "
                             "(geometric: top within 0.35 m of the "
                             "shell ceiling, bottom in the upper half "
                             "of the room)"}})
        continue

    # WALL-FLUSH EXEMPTION (user ruling 2026-08-06b after R-S2-28):
    # same disease on walls — a wall-flush object has no plan-view
    # footprint, so the top detection can't start and the full-height
    # wedge slices a room column in front of the wall (obj_002 x369).
    # Geometric only: flush to a measured shell wall (< 0.20 m) AND
    # thin along that wall's normal axis (< 0.30 m). A deep bookshelf
    # against the wall is flush but not thin -> still carved.
    _wall_hit = None
    for _axi, _planes in ((0, (XLO, XHI)), (2, (ZLO, ZHI))):
        for _v in _planes:
            if (min(abs(lo0[_axi] - _v), abs(hi0[_axi] - _v)) < 0.20
                    and (hi0[_axi] - lo0[_axi]) < 0.30):
                _wall_hit = (_axi, _v)
    if _wall_hit is not None:
        print("[carve]  wall-flush — carve exempt, resolved box kept "
              "verbatim", flush=True)
        kept_exempt.append({
            "id": nid, "name": name, "nviews_vote": 0,
            "status": "kept_wall",
            "boxes": {"original":
                      {"lo": [round(float(v), 3) for v in lo0],
                       "hi": [round(float(v), 3) for v in hi0]}},
            "rule": {"kept": "wall-flush — carve exempt (geometric: "
                             "within 0.20 m of a shell wall plane and "
                             "< 0.30 m thin along its normal)"}})
        continue

    # FLOOR-FLUSH EXEMPTION (user ruling 2026-08-07, with the shell
    # electorate filter): rugs/floor mats are the wall-flush disease
    # rotated to the floor — flush to the shell floor AND thin
    # vertically. Must run BEFORE the electorate filter below, which
    # would otherwise gut a flat floor object's entire electorate.
    # y-down frame: an object's bottom is hi0[1]; FLOOR > CEIL.
    if (FLOOR - hi0[1]) < 0.20 and (hi0[1] - lo0[1]) < 0.30:
        print("[carve]  floor-flush — carve exempt, resolved box kept "
              "verbatim", flush=True)
        kept_exempt.append({
            "id": nid, "name": name, "nviews_vote": 0,
            "status": "kept_floor",
            "boxes": {"original":
                      {"lo": [round(float(v), 3) for v in lo0],
                       "hi": [round(float(v), 3) for v in hi0]}},
            "rule": {"kept": "floor-flush — carve exempt (geometric: "
                             "bottom within 0.20 m of the shell floor "
                             "and < 0.30 m tall)"}})
        continue

    # ---- SLICE: prism primary, wedge fallback ----
    slice_mask, slice_info = None, ""
    top_ctx = None          # (cam, box, img, view name, score, eye)
    tcands, c0 = top_cam_for(n)
    for vname, teye, tfov in tcands:
        png = rdir / f"{nid}_{vname}.png"
        if not png.exists():
            continue
        cam = make_cam(teye, list(c0), tfov, RES)
        u, vv_, z = cam.project(corners)
        ok = z > 0.2
        pb = ([float(np.clip(u[ok].min(), 0, RES)),
               float(np.clip(vv_[ok].min(), 0, RES)),
               float(np.clip(u[ok].max(), 0, RES)),
               float(np.clip(vv_[ok].max(), 0, RES))] if ok.any() else None)
        img = Image.open(png).convert("RGB")
        best = gdino_best(img, name, prior_box=pb)
        if best is None:
            slice_info = f"{vname}: no detection"
            continue
        tb = best[1]
        top_ctx = (cam, tb, img, vname, best[0], teye)

        def ray_plane_xz(u_px, v_px, y_plane):
            d = np.array([(u_px - cam.cx) / cam.f,
                          -(v_px - cam.cy) / cam.f, 1.0]) @ cam.R
            t = (y_plane - cam.pos[1]) / d[1]
            p = cam.pos + t * d
            return [p[0], p[2]]

        # footprint from the beam only across the OBJECT's height band
        # (prior top - 0.3m margin, down to the floor) — casting ceiling
        # to floor smeared the tilted beam ~0.7m sideways (obj_041/020
        # finding); the CUT below stays full-height, only the footprint
        # tightens
        y_top = max(CEIL + 0.1, lo0[1] - 0.3)
        foot = []
        for uu, vv2 in ((tb[0], tb[1]), (tb[2], tb[1]),
                        (tb[2], tb[3]), (tb[0], tb[3])):
            for yp in (y_top, FLOOR):
                foot.append(ray_plane_xz(uu, vv2, yp))
        foot = np.array(foot)
        cen = foot.mean(axis=0)
        span = foot.max(axis=0) - foot.min(axis=0)
        marg = np.minimum(PAD * span, CAP_M)
        foot = cen + (foot - cen) * ((span + 2 * marg)
                                     / np.maximum(span, 1e-6))
        hull = MplPath(foot[ConvexHull(foot).vertices])
        slice_mask = below_ceil & hull.contains_points(xyz[:, [0, 2]])
        slice_info = f"PRISM ({vname} ok {best[0]:.2f})"
        break
    if slice_mask is None:
        # FALLBACK: original-box wedge, capped margin, full height
        slice_mask = np.zeros(len(xyz), bool)
        nb = 0
        for fid in n.get("members", []):
            fo = f30_by_id.get(fid)
            if not fo:
                continue
            for mi in fo.get("members", []):
                if mi >= len(pool_j):
                    continue
                m = pool_j[mi]
                cam0 = view_cam0(m["view"])
                b = [m["box"]["xmin"], m["box"]["ymin"],
                     m["box"]["xmax"], m["box"]["ymax"]]
                dist0 = float(np.linalg.norm(
                    np.array(geo["center"], float) - eye0))
                cap_px = cam0.f * CAP_M / max(dist0, 0.5)
                pw = min(PAD * (b[2] - b[0]), cap_px)
                u, vv_, z = cam0.project(xyz)
                slice_mask |= ((z > 0.05) & (u >= b[0] - pw)
                               & (u <= b[2] + pw))
                nb += 1
        slice_mask &= below_ceil
        slice_info = f"FALLBACK WEDGE ({nb} sp0 boxes; {slice_info})"
    cidx = np.nonzero(slice_mask)[0]
    dots = xyz[cidx]
    # SHELL ELECTORATE FILTER (user ruling 2026-08-07): dots on a
    # measured shell plane are structure — ineligible for election.
    # Claims/renders untouched (caches stay valid); votes zeroed at
    # tally. Census printed + recorded (measure-first doctrine).
    elig = ((np.abs(dots[:, 1] - FLOOR) > SHELL_EPS)
            & (np.abs(dots[:, 1] - CEIL) > SHELL_EPS)
            & (np.abs(dots[:, 0] - XLO) > SHELL_EPS)
            & (np.abs(dots[:, 0] - XHI) > SHELL_EPS)
            & (np.abs(dots[:, 2] - ZLO) > SHELL_EPS)
            & (np.abs(dots[:, 2] - ZHI) > SHELL_EPS))
    n_shell_dots = int((~elig).sum())
    print(f"[carve] slice: {len(dots):,} dots  [{slice_info}]  "
          f"(shell-plane ineligible: {n_shell_dots:,})", flush=True)
    if len(dots) < 100:
        print("[carve]   too few dots, skipping", flush=True)
        continue
    plyp = sdir / f"vote_{nid}.ply"
    write_subset_ply(slice_mask, plyp)

    # ---- RENDER: 4 near-cardinals of the slice, WSL renderer ----
    ctr = dots.mean(axis=0)
    dlo = np.percentile(dots, 2, axis=0)
    dhi = np.percentile(dots, 98, axis=0)
    half = float(max(dhi - dlo) / 2)
    dist = max(1.4 * max(half, 0.2)
               / math.tan(math.radians(FOV_GOOD) / 2), 1.2)
    views = []
    for k, base in enumerate([np.array([1.0, 0, 0]),
                              np.array([-1.0, 0, 0]),
                              np.array([0, 0, 1.0]),
                              np.array([0, 0, -1.0])]):
        dirv = roty(base, OFF_AXIS)
        eye = ctr + dirv * dist
        views.append({"name": f"vote_{nid}_card{k}",
                      "label": f"{nid} {name} card{k}",
                      "eye": [float(v) for v in eye],
                      "aim": [float(v) for v in ctr], "fov": FOV_GOOD})
    # clean 3/4 slice view for the page (rendered in the same WSL batch)
    d34 = np.array([1.0, 0.0, 0.65])
    d34 /= np.linalg.norm(d34)
    eye34 = ctr + d34 * dist
    eye34[1] = ctr[1] - 0.55 * dist        # y-down: minus = raise camera
    views.append({"name": f"vote_{nid}_slice34",
                  "label": f"{nid} {name} slice 3/4 view",
                  "eye": [float(v) for v in eye34],
                  "aim": [float(v) for v in ctr], "fov": FOV_GOOD})
    # VIEW TUNNEL (user design 2026-08-06 after R-S2-27): each card
    # renders the FULL scene minus a tunnel — gaussians inside this
    # camera's view cone (small pad for splat tails), nearer than the
    # slice's far depth, and not slice members are culled. Occluders
    # gone, side/background context intact. Claims are still counted on
    # slice dots only. Per-card plys are transient (≈ whole scene).
    def ctx_render_jobs(card_views):
        jobs = []
        for v in card_views:
            veye = np.array(v["eye"], float)
            vdir = np.array(v["aim"], float) - veye
            vdir /= np.linalg.norm(vdir)
            t_far = float(((dots - veye) @ vdir).max())
            camk = make_cam(v["eye"], v["aim"], v["fov"], RES)
            uu, vv_, zz = camk.project(xyz)
            in_cone = ((zz > 0.05) & (uu >= -40) & (uu < RES + 40)
                       & (vv_ >= -40) & (vv_ < RES + 40))
            hole = (in_cone & (((xyz - veye) @ vdir) < (t_far + 0.05))
                    & ~slice_mask)
            cply = sdir / f"votectx_{v['name']}.ply"
            write_subset_ply(~hole, cply)
            ctf = sdir / f"votetgt_{v['name']}.json"
            ctf.write_text(json.dumps([v], indent=1))
            jobs.append((ctf, cply, True))
        return jobs

    def run_renders(jobs):
        _py = "/root/miniconda3/envs/splatanalyzer/bin/python"
        _scr = to_wsl(HERE / 'analyzer' / 'render_targets_wsl.py')
        parts = [f"{_py} '{_scr}' --targets '{to_wsl(t)}' "
                 f"--ply '{to_wsl(p)}' --out '{to_wsl(sdir)}' --res {RES}"
                 for t, p, _tr in jobs]
        cmd = ("wsl -d Ubuntu-24.04 -- bash -c \"cd /root/splat_analyzer"
               " && " + " && ".join(parts) + "\"")
        subprocess.run(cmd, check=True, timeout=1800, shell=True)
        for _t, p, transient in jobs:
            if transient:
                p.unlink(missing_ok=True)

    def card_votes(card_views):
        """Detect+SAM each card render. Returns [(claims|None, info)];
        claims are over slice dots only."""
        out = []
        for v in card_views:
            vname = v["name"].split(f"vote_{nid}_", 1)[-1]
            png = sdir / f"{v['name']}.png"
            info = {"view": vname, "eye": v["eye"]}
            if not png.exists():
                info["why"] = "no_render"
                out.append((None, info))
                continue
            img = Image.open(png).convert("RGB")
            cam = make_cam(v["eye"], v["aim"], v["fov"], RES)
            u, vv2, z = cam.project(dots)
            inb = ((z > 0.05) & (u >= 0) & (u < RES - 1)
                   & (vv2 >= 0) & (vv2 < RES - 1))
            # context in frame: gate the re-detect to the slice's screen
            # footprint (same prior mechanism as the top view) so a
            # same-class object in the backdrop can't be picked
            pb = ([float(max(0, u[inb].min() - 20)),
                   float(max(0, vv2[inb].min() - 20)),
                   float(min(RES, u[inb].max() + 20)),
                   float(min(RES, vv2[inb].max() + 20))]
                  if inb.any() else None)
            best = gdino_best(img, name, prior_box=pb)
            if best is None:
                info["why"] = "no_redetect"
                out.append((None, info))
                print(f"[carve] {vname} no_redetect", flush=True)
                continue
            mask = sam_mask(img, best[1], DIL_ISO)
            ov = img.convert("RGBA")
            layer = Image.new("RGBA", ov.size, (0, 0, 0, 0))
            px = layer.load()
            ys, xs = np.nonzero(mask)
            for yy, xx in zip(ys[::4], xs[::4]):
                px[int(xx), int(yy)] = (0, 255, 90, 100)
            ov = Image.alpha_composite(ov, layer).convert("RGB")
            dr = ImageDraw.Draw(ov)
            dr.rectangle(best[1], outline=(255, 40, 40), width=4)
            ov.save(sdir / f"{v['name']}_det.png")
            cl = np.zeros(len(dots), bool)
            ui = u[inb].astype(np.int64)
            vi = vv2[inb].astype(np.int64)
            cl[np.nonzero(inb)[0]] = mask[vi, ui]
            info["why"] = f"ok({best[0]:.2f})"
            info["claimed"] = int(cl.sum())
            out.append((cl, info))
            print(f"[carve] {vname} ok({best[0]:.2f}) claims "
                  f"{int(cl.sum())}/{len(dots)}", flush=True)
        return out

    # ---- TIER 1: context cards at object height ----
    jobs = ctx_render_jobs(views[:4])
    tf = sdir / f"votetgt_{nid}.json"
    tf.write_text(json.dumps([views[4]], indent=1))  # clean slice34
    jobs.append((tf, plyp, False))
    run_renders(jobs)
    card_res = card_votes(views[:4])
    tiers = ["context"]

    # ---- TIER 2: eye-height escalation (user design 2026-08-07) ----
    # Marble scenes are biased toward eye-height capture: splat quality
    # and the detector are both strongest from eye-height viewpoints.
    # When MOST object-height cardinals are unproductive (>=3 of 4 with
    # no detection or <50 claimed dots), add 4 eye-height cardinals
    # (same tunnel carve) as EXTRA voters.
    productive = sum(1 for cl, inf in card_res
                     if cl is not None and inf.get("claimed", 0) >= 50)
    if productive <= 1:
        tiers.append("eyeheight")
        print("[carve]  escalate: eye-height cardinals", flush=True)
        eye_y = max(CEIL + WALL_PAD, FLOOR - 1.6)
        eviews = []
        for k, base in enumerate([np.array([1.0, 0, 0]),
                                  np.array([-1.0, 0, 0]),
                                  np.array([0, 0, 1.0]),
                                  np.array([0, 0, -1.0])]):
            dirv = roty(base, OFF_AXIS)
            eeye = ctr + dirv * dist
            eeye = eeye.copy()
            eeye[1] = eye_y
            eviews.append({"name": f"vote_{nid}_eyecard{k}",
                           "label": f"{nid} {name} eyecard{k}",
                           "eye": [float(x) for x in eeye],
                           "aim": [float(x) for x in ctr],
                           "fov": FOV_GOOD})
        run_renders(ctx_render_jobs(eviews))
        card_res = card_res + card_votes(eviews)
    # ---- v4: the TOP view votes too (its SAM mask on the plan render)
    tcl, tinfo = None, None
    if top_ctx is not None:
        tcam, tb, timg, tvname, tscore, teye_v = top_ctx
        tmask = sam_mask(timg, tb, DIL_ISO)
        ovt = timg.convert("RGBA")
        layer = Image.new("RGBA", ovt.size, (0, 0, 0, 0))
        px = layer.load()
        ys, xs = np.nonzero(tmask)
        for yy, xx in zip(ys[::4], xs[::4]):
            px[int(xx), int(yy)] = (0, 255, 90, 100)
        ovt = Image.alpha_composite(ovt, layer).convert("RGB")
        ImageDraw.Draw(ovt).rectangle(tb, outline=(255, 40, 40), width=4)
        ovt.save(sdir / f"vote_{nid}_top_det.png")
        u, vv2, z = tcam.project(dots)
        inb = ((z > 0.05) & (u >= 0) & (u < RES - 1)
               & (vv2 >= 0) & (vv2 < RES - 1))
        cl = np.zeros(len(dots), bool)
        ui = u[inb].astype(np.int64)
        vi = vv2[inb].astype(np.int64)
        cl[np.nonzero(inb)[0]] = tmask[vi, ui]
        tcl = cl
        tinfo = {"view": "top", "why": f"ok({tscore:.2f})",
                 "eye": [float(v) for v in teye_v],
                 "claimed": int(cl.sum())}
        print(f"[carve] top   ok({tscore:.2f}) claims "
              f"{int(cl.sum())}/{len(dots)}", flush=True)
    # ---- v4: the ORIGINAL standpoint votes too (union of member masks)
    ocl = np.zeros(len(dots), bool)
    n_msk = 0
    for fid in n.get("members", []):
        fo = f30_by_id.get(fid)
        if not fo:
            continue
        for mi in fo.get("members", []):
            if mi >= len(pool_j):
                continue
            m = pool_j[mi]
            mk = member_mask(m)
            if mk is None:
                continue
            mkd = ndimage.binary_dilation(mk, iterations=6)
            cam0 = view_cam0(m["view"])
            hh, ww = mkd.shape
            u, vv2, z = cam0.project(dots)
            inb = ((z > 0.05) & (u >= 0) & (u < ww - 1)
                   & (vv2 >= 0) & (vv2 < hh - 1))
            hit = np.zeros(len(dots), bool)
            ui = u[inb].astype(np.int64)
            vi = vv2[inb].astype(np.int64)
            hit[np.nonzero(inb)[0]] = mkd[vi, ui]
            ocl |= hit
            n_msk += 1
    oinfo = None
    if n_msk:
        oinfo = {"view": "sp0-original",
                 "why": f"{n_msk} member mask(s)",
                 "eye": [float(v) for v in eye0],
                 "claimed": int(ocl.sum())}
        print(f"[carve] sp0   {n_msk} masks   claims "
              f"{int(ocl.sum())}/{len(dots)}", flush=True)

    # ---- ELECTION (assemble + tally; re-runnable for tier 3) ----
    def assemble(card_res_):
        cls, inf = [], []
        for cl, i in card_res_:
            i = dict(i)
            if cl is not None:
                cls.append(cl)
                i["idx"] = len(cls) - 1
            inf.append(i)
        if tcl is not None:
            ti = dict(tinfo)
            cls.append(tcl)
            ti["idx"] = len(cls) - 1
            inf.append(ti)
        if oinfo is not None:
            oi = dict(oinfo)
            cls.append(ocl)
            oi["idx"] = len(cls) - 1
            inf.append(oi)
        return cls, inf

    def tally(cls):
        # USER 2026-08-06 late: 3-vote gate; degrades only when fewer
        # voters exist
        n = len(cls)
        vts = (np.sum(cls, axis=0).astype(np.int64) if cls
               else np.zeros(len(dots), np.int64))
        vts[~elig] = 0   # shell electorate filter (user 2026-08-07)
        need = min(a.gate, n) if n else 1
        p_and, _ = (fragments_box(dots[vts == n], lo0, hi0)
                    if n else (None, []))
        p_v2, frags = fragments_box(dots[vts >= need], lo0, hi0)
        return n, vts, need, p_and, p_v2, frags

    claims, infos = assemble(card_res)
    (n_ok, votes, need_votes,
     prim_and, prim_v2, frags_v2) = tally(claims)

    # ---- TIER 3: isolation retry (user-approved 2026-08-07) ----
    # Election still empty -> re-render the object-height cards with the
    # slice ALONE on black (run-1 mode, proven on small objects like the
    # book) and re-elect with the extra voters. Only after this can the
    # original box ship.
    if prim_v2 is None:
        tiers.append("isolation")
        print("[carve]  escalate: isolation retry (slice on black)",
              flush=True)
        iviews = [{"name": f"vote_{nid}_iso{k}",
                   "label": f"{nid} {name} iso{k}",
                   "eye": views[k]["eye"], "aim": views[k]["aim"],
                   "fov": FOV_GOOD} for k in range(4)]
        itf = sdir / f"votetgt_{nid}_iso.json"
        itf.write_text(json.dumps(iviews, indent=1))
        run_renders([(itf, plyp, False)])
        card_res = card_res + card_votes(iviews)
        claims, infos = assemble(card_res)
        (n_ok, votes, need_votes,
         prim_and, prim_v2, frags_v2) = tally(claims)
    rule_flag = ""
    if frags_v2:
        biggest = max(frags_v2, key=lambda f: f["n_pts"])
        if biggest is not prim_v2:
            rule_flag = (f"anchored cluster ({prim_v2['n_pts']} pts) is "
                         f"not the biggest ({biggest['n_pts']} pts)")
    # ---- ARM ASSIGNMENT (⚠ UNTESTED, user option-2 2026-08-06): multi-
    # node structures (L-sectional) share one vote cluster, so every
    # sibling node wraps the whole L. Each node keeps only the vote
    # survivors ITS OWN original masks vouch for. Guard: falls back to
    # the cluster box when sp0 coverage of the survivors is too thin
    # (junk member masks must not starve the node).
    prim_arm, arm_flag = None, ""
    if n_msk and prim_v2 is not None:
        surv = votes >= need_votes
        armk = surv & ocl
        if (armk.sum() >= 200
                and armk.sum() >= 0.10 * max(1, surv.sum())):
            lo_a = np.percentile(dots[armk], 1, axis=0)
            hi_a = np.percentile(dots[armk], 99, axis=0)
            prim_arm = {"lo": lo_a, "hi": hi_a, "n_pts": int(armk.sum())}
            va = np.prod(np.maximum(hi_a - lo_a, 1e-6))
            vv = np.prod(np.maximum(
                np.array(prim_v2["hi"]) - np.array(prim_v2["lo"]), 1e-6))
            if va < 0.5 * vv:
                arm_flag = ("arm box is <50% of the cluster box volume "
                            "— possible multi-node structure (L?); "
                            "multiplicity judge territory")
        else:
            arm_flag = "sp0 coverage too thin — arm fallback to cluster"
    # OUTLIER GUARD (user rule 2026-08-06b): a repair may refine, never
    # explode — if the box that would ship is > OUTLIER_K x the original
    # resolved volume, the original ships instead (kept_outlier). The
    # oversized vote box stays recorded (honest fallback, judge fodder).
    outlier_flag = ""
    _fin = prim_arm if prim_arm is not None else prim_v2
    if _fin is not None:
        _vf = np.prod(np.maximum(
            np.array(_fin["hi"]) - np.array(_fin["lo"]), 1e-6))
        _vo = np.prod(np.maximum(hi0 - lo0, 1e-6))
        if _vf > OUTLIER_K * _vo:
            outlier_flag = (f"carved box is {_vf/_vo:.0f}x the original "
                            f"volume (> {OUTLIER_K:.0f}x) — outlier "
                            "guard: original box ships, vote box "
                            "recorded as doubt")
    # PLAN-FILL (user rule 3, 2026-08-07 — adopted from the scene-wide
    # census: natural break 0.58 | 0.73, threshold 0.65 in open water):
    # elected dots' 10 cm-voxel footprint coverage of the vote box. Low
    # fill = the dots don't cover their own footprint — non-box shape
    # (L-sectional) or sparse giant. Recorded here; the doubt fires in
    # record_carve_doubts.py; the split-cell judge rules.
    plan_fill = None
    if prim_v2 is not None:
        _el = dots[votes >= need_votes]
        if len(_el):
            _lo2 = np.array(prim_v2["lo"]); _hi2 = np.array(prim_v2["hi"])
            _g = np.floor((_el[:, [0, 2]] - _lo2[[0, 2]]) / 0.10)
            _occ = len(set(map(tuple, _g.astype(np.int64))))
            _tot = int(np.prod(np.maximum(
                np.ceil((_hi2 - _lo2)[[0, 2]] / 0.10), 1)))
            plan_fill = round(min(_occ / max(_tot, 1), 2.0), 3)
    ur = ("empty" if prim_v2 is None else
          " x ".join(f"{prim_v2['hi'][i]-prim_v2['lo'][i]:.2f}"
                     for i in range(3)))
    ua = ("" if prim_arm is None else
          "  arm " + " x ".join(f"{prim_arm['hi'][i]-prim_arm['lo'][i]:.2f}"
                                for i in range(3)))
    print(f"[carve]  VOTE ≥{need_votes} of {n_ok}: {ur} m{ua}"
          + (f"  (culled {len(frags_v2)-1})" if len(frags_v2) > 1 else "")
          + (f"  ⚠ {rule_flag}" if rule_flag else "")
          + (f"  ⚠ {arm_flag}" if arm_flag else "")
          + (f"  ⚠ {outlier_flag}" if outlier_flag else ""), flush=True)

    # ---- figure ----
    Pc = dots[votes >= need_votes]
    wbase = Pc if len(Pc) >= 50 else dots
    wlo = np.minimum(np.percentile(wbase, 0.5, axis=0), lo0) - 0.4
    whi = np.maximum(np.percentile(wbase, 99.5, axis=0), hi0) + 0.4
    inw = np.all((dots >= wlo) & (dots <= whi), axis=1)
    Pw, votes_w = dots[inw], votes[inw]
    minis = [i for i in infos if "idx" in i]
    ncols = max(3, len(minis))
    fig, axes = plt.subplots(2, ncols, figsize=(4.2 * ncols, 9))
    fig.suptitle(f"{nid}  \u201c{name}\u201d \u2014 v3 slice+vote "
                 f"({slice_info}; {n_ok} cardinals)", fontsize=15)
    projs = [("plan view (from above)", 0, 2, False),
             ("front (x vs height)", 0, 1, True),
             ("side (z vs height)", 2, 1, True)]
    vmax = max(1, n_ok)
    for k in range(ncols):
        for r in (0, 1):
            axes[r, k].set_aspect("equal")
    for k, (title, a0, a1, flip) in enumerate(projs):
        ax = axes[0, k]
        y = -Pw[:, a1] if flip else Pw[:, a1]
        sc = ax.scatter(Pw[:, a0], y, c=votes_w, cmap="viridis", vmin=0,
                        vmax=vmax, s=2, alpha=0.7)
        ax.set_xlim(wlo[a0], whi[a0])
        ax.set_ylim((-whi[a1], -wlo[a1]) if flip else (wlo[a1], whi[a1]))
        draw_box(ax, lo0, hi0, a0, a1, "#888888", "--", 1.5,
                 "original box", flip)
        if prim_and is not None:
            draw_box(ax, prim_and["lo"], prim_and["hi"], a0, a1,
                     "#d62728", "-", 2.2, "ALL cardinals", flip)
        if prim_v2 is not None:
            draw_box(ax, prim_v2["lo"], prim_v2["hi"], a0, a1,
                     "#ff9900", "-", 1.6,
                     f"\u2265{need_votes} votes (anchored)", flip)
        if prim_arm is not None:
            draw_box(ax, prim_arm["lo"], prim_arm["hi"], a0, a1,
                     "#00bcd4", "-", 1.8, "arm (own-mask survivors)",
                     flip)
        ax.set_title(title, fontsize=11)
        if k == 0:
            ax.legend(fontsize=8, loc="upper right")
    for k in range(len(projs), ncols):
        axes[0, k].axis("off")
    cbar = fig.colorbar(sc, ax=axes[0, :].tolist(), shrink=0.8,
                        ticks=range(vmax + 1), pad=0.01)
    cbar.set_label("cameras claiming the dot (4 cardinals + top + orig)")
    for k, info in enumerate(minis):
        ax = axes[1, k]
        cl = claims[info["idx"]][inw]
        colr = VIEW_COLORS.get(info["view"], "#000000")
        ax.scatter(Pw[~cl, 0], Pw[~cl, 2], c="#dddddd", s=2)
        ax.scatter(Pw[cl, 0], Pw[cl, 2], c=colr, s=2)
        ex_, ez_ = info["eye"][0], info["eye"][2]
        ax.annotate("", xy=(ctr[0], ctr[2]), xytext=(ex_, ez_),
                    arrowprops=dict(arrowstyle="->", color=colr, lw=1.6))
        ax.plot([ex_], [ez_], "o", color=colr, markersize=7)
        ax.set_title(f"{info['view']}  {info['why']}\n"
                     f"claims {info.get('claimed', 0)}/{len(dots)} dots",
                     fontsize=10)
    for k in range(len(minis), ncols):
        axes[1, k].axis("off")
    fig_path = rdir / f"conemap_{nid}.png"
    fig.savefig(fig_path, dpi=110, bbox_inches="tight")
    plt.close(fig)

    # ---- viewer export ----
    rng = np.random.default_rng(0)
    sub = (np.arange(len(dots)) if len(dots) <= 12000 else
           np.sort(rng.choice(len(dots), 12000, replace=False)))
    bits = np.zeros(len(dots), np.int64)
    for bi, cl in enumerate(claims):
        bits |= cl.astype(np.int64) << bi
    views_exp = [{"view": i["view"], "why": i["why"], "role": "",
                  "eye": i["eye"],
                  "color": VIEW_COLORS.get(i["view"], "#ffffff"),
                  "claimed": i.get("claimed")}
                 for i in infos if "idx" in i]
    bits |= np.ones(len(dots), np.int64) << len(claims)
    views_exp.append({"view": "slice", "why": slice_info, "role": "",
                      "eye": [float(v) for v in
                              (tcands[0][1] if tcands else eye0)],
                      "color": "#ff7f00", "claimed": int(len(dots))})

    def _box(prim):
        return (None if prim is None else
                {"lo": [round(float(v), 3) for v in prim["lo"]],
                 "hi": [round(float(v), 3) for v in prim["hi"]]})

    cm_objects.append({
        "id": nid, "name": name, "aim": [float(v) for v in ctr],
        "nviews_vote": n_ok,
        "boxes": {"original": {"lo": [round(float(v), 3) for v in lo0],
                               "hi": [round(float(v), 3) for v in hi0]},
                  "strict": _box(prim_and), "vote2": _box(prim_v2),
                  "arm": _box(prim_arm)},
        "rule": {"need_votes": need_votes, "flag": rule_flag,
                 "arm_flag": arm_flag, "outlier": outlier_flag,
                 "tiers": tiers,
                 "culled_clusters": max(0, len(frags_v2) - 1),
                 "shell_ineligible_dots": n_shell_dots,
                 "plan_fill": plan_fill,
                 "slice": slice_info},
        "views": views_exp,
        "points": {"pos": [round(float(v), 3)
                           for v in dots[sub].reshape(-1)],
                   "votes": votes[sub].astype(int).tolist(),
                   "bits": bits[sub].astype(int).tolist()}})

    # ---- html row ----
    sz = lambda b: " x ".join(f"{b['hi'][i]-b['lo'][i]:.2f}" for i in range(3))  # noqa: E731
    stats = [f"original box: "
             f"{' x '.join(f'{v:.2f}' for v in geo['size'])} m",
             f"slice: {len(dots):,} dots ({slice_info})"]
    if prim_v2 is not None:
        stats.append(f"vote box (\u2265{need_votes} of {n_ok}, anchored): "
                     f"{sz(prim_v2)} m"
                     + (f" (+{len(frags_v2)-1} culled)"
                        if len(frags_v2) > 1 else ""))
    else:
        stats.append("vote box: (empty)")
    if prim_and is not None:
        stats.append(f"ALL-cardinals box: {sz(prim_and)} m")
    if rule_flag:
        stats.append(f"\u26a0 FLAG: {rule_flag}")
    if outlier_flag:
        stats.append(f"\u26a0 OUTLIER: {outlier_flag}")
    if len(tiers) > 1:
        stats.append("escalated: " + " \u2192 ".join(tiers))
    strip = ""
    f34 = sdir / f"vote_{nid}_slice34.png"
    if f34.exists():
        strip += (f"<figure><img src='pool_retake/slices/{f34.name}' "
                  f"loading='lazy'><figcaption>THE SLICE · clean 3/4 "
                  f"view ({len(dots):,} dots)</figcaption></figure>")
    ftop = sdir / f"vote_{nid}_top_det.png"
    if ftop.exists():
        strip += (f"<figure><img src='pool_retake/slices/{ftop.name}' "
                  f"loading='lazy'><figcaption>TOP VOTER · plan render, "
                  f"its mask+box</figcaption></figure>")
    for fsp in sorted(rdir.glob(f"conemap_sp0_{nid}_*.png")):
        strip += (f"<figure><img src='pool_retake/{fsp.name}' "
                  f"loading='lazy'><figcaption>ORIGINAL VOTER · sp0 "
                  f"member mask</figcaption></figure>")
    for i in infos:
        vn = i["view"]
        if vn in ("top", "sp0-original"):
            continue
        f = sdir / f"vote_{nid}_{vn}_det.png"
        f2 = sdir / f"vote_{nid}_{vn}.png"
        src = f.name if f.exists() else (f2.name if f2.exists() else None)
        if src:
            strip += (f"<figure><img src='pool_retake/slices/{src}' "
                      f"loading='lazy'><figcaption>{vn} "
                      f"\u00b7 {i.get('why', '?')}</figcaption></figure>")
    rows_html.append(f"""
<section>
<h2>{nid} \u2014 {name}</h2>
<p>{' &nbsp;\u00b7&nbsp; '.join(stats)}</p>
<img class='big' src='pool_retake/{fig_path.name}'>
<div class='strip'>{strip}</div>
</section>""")

html = f"""<!doctype html><meta charset='utf-8'>
<title>v3 slice+vote \u2014 {SCENE}</title>
<style>
body{{font-family:system-ui,sans-serif;margin:24px;background:#fafafa}}
h1{{font-size:20px}} h2{{font-size:16px;margin:28px 0 4px}}
img.big{{max-width:100%;border:1px solid #ccc;background:#fff}}
.strip{{display:flex;gap:8px;overflow-x:auto;margin-top:8px}}
.strip figure{{margin:0;flex:0 0 auto}}
.strip img{{height:190px;border:1px solid #ccc}}
.strip figcaption{{font-size:11px;max-width:200px}}
p{{font-size:13px}}
</style>
<h1>v3 slice + vote \u2014 {SCENE}</h1>
<p>DESIGN (updated 2026-08-06b): slice = top-box vertical prism (capped
margin; fallback = original-box wedge) \u2192 each card rendered by the
real WSL renderer as the FULL SCENE minus a VIEW TUNNEL (occluders
inside the camera cone and nearer than the slice are culled; side and
background context intact; re-detect gated to the slice's screen
footprint) \u2192 detector+SAM per render \u2192 6-voter election. Boxes: gray
dashed = original, red = all cardinals agree, orange = the vote gate,
cyan = arm. Ceiling-mounted and wall-flush objects are CARVE-EXEMPT
(geometric tests) and keep their resolved box; a carved box growing
past the outlier guard (8x original volume) also falls back to the
original (kept_outlier), with the vote box recorded as doubt.</p>
{("<p><b>carve-exempt (resolved box kept):</b> "
  + ", ".join(f"{k['id']} {k['name']} [{k['status']}]"
              for k in kept_exempt) + "</p>")
 if kept_exempt else ""}
{''.join(rows_html)}
"""
(sd / "cone_map.html").write_text(html, encoding="utf-8")
(rdir / "conemap.json").write_text(
    json.dumps({"scene": SCENE, "objects": cm_objects}), encoding="utf-8")

# ---- PREVIEW manifest + report (⚠ UNTESTED promotion) ----
objs, by_status = [], {}
for o in cm_objects:
    if o["rule"].get("outlier"):
        box, status = o["boxes"]["original"], "kept_outlier"
    else:
        box = (o["boxes"].get("arm") or o["boxes"].get("vote2")
               or o["boxes"]["original"])
        status = ("carved_arm" if o["boxes"].get("arm")
                  else ("carved" if o["boxes"].get("vote2") else "kept"))
    by_status[status] = by_status.get(status, 0) + 1
    lo, hi = box["lo"], box["hi"]
    flags = [status] + [f for f in (o["rule"]["flag"],
                                    o["rule"]["arm_flag"],
                                    o["rule"].get("outlier", "")) if f]
    objs.append({"id": o["id"],
                 "label": o["name"] + f" ({status} "
                          f"{o['rule']['need_votes']}v/"
                          f"{o['nviews_vote']})",
                 "score": 1.0, "aabb_min": lo, "aabb_max": hi,
                 "center": [round((x + y) / 2, 4)
                            for x, y in zip(lo, hi)],
                 "size": [round(y - x, 4) for x, y in zip(lo, hi)],
                 "n_detections": 1, "views": [], "flags": flags})
for kc in kept_exempt:
    by_status[kc["status"]] = by_status.get(kc["status"], 0) + 1
    b = kc["boxes"]["original"]
    lo, hi = b["lo"], b["hi"]
    objs.append({"id": kc["id"],
                 "label": kc["name"] + f" ({kc['status']})",
                 "score": 1.0, "aabb_min": lo, "aabb_max": hi,
                 "center": [round((x + y) / 2, 4)
                            for x, y in zip(lo, hi)],
                 "size": [round(y - x, 4) for x, y in zip(lo, hi)],
                 "n_detections": 1, "views": [],
                 "flags": [kc["status"], kc["rule"]["kept"]]})
(sd / "scene_manifest_slicevote_preview.json").write_text(json.dumps(
    {"scene": SCENE, "status": "UNTESTED-PREVIEW",
     "source": "carve_slicevote.py — slice-vote carve (top-box prism / "
               "wedge fallback; view-tunnel context cards; 6-voter "
               f"election, gate {a.gate}; per-node arm assignment; "
               "ceiling/wall-flush exempt = kept_ceiling/kept_wall; "
               f"outlier guard {OUTLIER_K:.0f}x = kept_outlier). "
               "Preview only; not on the pipeline map.",
     "frame": {"space": "raw", "up": [0.0, -1.0, 0.0]},
     "n_objects": len(objs), "objects": objs}, indent=2))
(rdir / "slicevote_report.json").write_text(json.dumps(
    {"scene": SCENE, "stage": "carve_slicevote",
     "status": "UNTESTED-PREVIEW", "gate": a.gate,
     "params": {"DET_THR": DET_THR, "PAD": PAD, "CAP_M": CAP_M,
                "FOV_GOOD": FOV_GOOD, "OFF_AXIS": OFF_AXIS,
                "DIL_ISO": DIL_ISO, "OUTLIER_K": OUTLIER_K},
     "by_status": by_status,
     "results": [{k: o[k] for k in ("id", "name", "nviews_vote",
                                    "boxes", "rule")}
                 for o in cm_objects] + kept_exempt}, indent=1))
print(f"[carve] statuses {by_status}; wrote cone_map.html + conemap.json "
      f"+ scene_manifest_slicevote_preview.json + slicevote_report.json "
      f"(⚠ UNTESTED-PREVIEW)", flush=True)
