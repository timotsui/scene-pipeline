"""Step 7 — view-pack: render ~15 splat views + GaussianCut COLMAP dataset.

Renders the bedroom splat from the 7 proven judge-rig cameras (same
standpoint/yaws/tilts as render_judge_views.py — blind-zone-free) plus 8
views from 3 offset standpoints (parallax so the graph cut can associate
2D masks to Gaussians in depth), then writes everything as the dataset
GaussianCut's vendored 3DGS loader expects (see FEASIBILITY_GAUSSIANCUT.md
section 2a) and a contact sheet for the Checkpoint 3 review.

Inputs   (all through paths.py):
  out/<scene>/gen_raw.ply          the splat, RAW space
  out/<scene>/scene_manifest.json  frame block + lamp boxes (RAW coords)
  splat-transform CLI on PATH      GPU renderer (lossless webp out)
  rendertools/03_render.py Cam     independent projection cross-check

Outputs  (all under out/<scene>/cut/dataset/):
  images/<view>.png            clean 900x900 renders (GaussianCut gt;
                               PNG converted from the lossless webp)
  render_webp/<view>.webp      renderer originals (provenance)
  sidecars/<view>.json         shot.py-format cam/look/up/fov, RENDER frame
  sparse/0/cameras.txt         COLMAP text PINHOLE intrinsics
  sparse/0/images.txt          COLMAP text world-to-camera qvec/tvec
  sparse/0/points3D.ply        tiny valid dummy cloud (content unused)
  overlays/<view>.png          render + lamp box projected via the COLMAP
                               pose (box hugging the lamp = camera math ok)
  contact_sheet.html           Checkpoint 3 review page
  verification.json            numeric round-trip / projection checks

FRAME CONTRACT (the #1 silent-failure risk — do not "fix" signs here):
  * Sidecar cam/look/up are RENDER-frame (y up, floor ~0): the coords fed
    to splat-transform, which applies rot180Z on import of the RAW ply
    (SESSION_2026-07-05C handoff, user-calibrated via cube8.ply).
  * gen_raw.ply vertices are RAW space; physical up = -y there.
    raw = render * (-1,-1,1) elementwise (self-inverse, det=+1).
  * COLMAP files are in the RAW frame (the frame GaussianCut loads the ply
    in), OpenCV camera basis (x right, y down, z forward), images.txt row
    = world-to-camera:  x_cam = R(qvec) @ X_raw + tvec.
  * --fov given to splat-transform is VERTICAL degrees; images are square
    (900x900) so fx = fy = (H/2)/tan(fov/2) — asserted in code.

Verification is numeric only (the USER judges all visuals): quaternion +
camera-center round trips, and the lamp box center projected through the
new COLMAP pose vs through rendertools' Cam (the projector behind the
user-validated amodal overlays). Any mismatch aborts before the sheet.

Usage:  python prep_views.py --scene bedroom_marble [--views 15] [--force]
"""
import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import paths  # noqa: E402

r3 = paths.load_r3()

RES = 900                      # square; fx=fy only holds because w == h
RING_FOV = 75.0                # judge ring + offset views
DOWN_FOV = 85.0                # judge straight-down view
NEAR = 0.2
BACKGROUND = "0.08,0.08,0.1"   # same as shot.py / render_judge_views.py
R2R = np.array([-1.0, -1.0, 1.0])   # render <-> raw, elementwise, self-inverse

JUDGE_CAM = (0.0, 1.6, 0.0)    # render frame: the proven judge standpoint
JUDGE_LOOK_DIST = 3.0
JUDGE_LOOK_H = 0.85            # ~14 deg down-tilt
OFF_LOOK_DIST = 3.0
OFF_LOOK_H = 0.9
OFF_EYE_H = 1.5
FLANK_DEG = 33.0               # flank views: lamp stays ~50 px inside frame
# offset standpoints (render frame), inside the room envelope (asserted):
OFFSETS = {"b": (1.2, OFF_EYE_H, 1.0),     # +x side, mid-room
           "c": (-1.6, OFF_EYE_H, 0.8),    # -x side, mid-room
           "d": (-0.3, OFF_EYE_H, 2.5)}    # near the lamp wall (close range)
WALL_MARGIN = 0.4              # min camera distance to the room extent

PALETTE = ["#ff5252", "#40c4ff", "#ffd740", "#69f0ae", "#e040fb"]
CENTER_TOL_PX = 0.5            # COLMAP vs r3.Cam lamp-center agreement
ROUNDTRIP_TOL = 1e-4           # camera-center round trip (meters)


# ---------- camera rig (render frame) ----------

def rig(lamp_render, n_views):
    """[(name, cam, look, up, fov, expect_lamp)] — judge 7 + offset views.

    expect_lamp: the primary lamp's box center must project in-frame
    (asserted numerically). n_views trims the offset list (judge 7 kept).
    """
    views = []
    for yaw in range(0, 360, 60):
        th = math.radians(yaw)
        look = (JUDGE_LOOK_DIST * math.sin(th), JUDGE_LOOK_H,
                JUDGE_LOOK_DIST * math.cos(th))
        views.append((f"judge_yaw{yaw:03d}", JUDGE_CAM, look, (0, 1, 0),
                      RING_FOV, yaw == 0))
    views.append(("judge_down", JUDGE_CAM, (0.0, 0.0, 0.0), (0, 0, -1),
                  DOWN_FOV, False))

    def aimed(sp, bearing_off):
        """look target LOOK_DIST out from standpoint sp, rotated
        bearing_off deg from the lamp bearing, at OFF_LOOK_H height."""
        cam = OFFSETS[sp]
        th = math.atan2(lamp_render[0] - cam[0], lamp_render[2] - cam[2]) \
            + math.radians(bearing_off)
        return (cam[0] + OFF_LOOK_DIST * math.sin(th), OFF_LOOK_H,
                cam[2] + OFF_LOOK_DIST * math.cos(th))

    lamp_at = tuple(float(v) for v in lamp_render)
    extra = [  # priority order for --views trimming: lamp-aimed first
        ("cut_b_lamp", OFFSETS["b"], lamp_at, (0, 1, 0), RING_FOV, True),
        ("cut_c_lamp", OFFSETS["c"], lamp_at, (0, 1, 0), RING_FOV, True),
        ("cut_d_lamp", OFFSETS["d"], lamp_at, (0, 1, 0), RING_FOV, True),
        ("cut_b_left", OFFSETS["b"], aimed("b", -FLANK_DEG), (0, 1, 0), RING_FOV, True),
        ("cut_b_right", OFFSETS["b"], aimed("b", FLANK_DEG), (0, 1, 0), RING_FOV, True),
        ("cut_c_left", OFFSETS["c"], aimed("c", -FLANK_DEG), (0, 1, 0), RING_FOV, True),
        ("cut_c_right", OFFSETS["c"], aimed("c", FLANK_DEG), (0, 1, 0), RING_FOV, True),
        ("cut_d_back", OFFSETS["d"], (0.2, OFF_LOOK_H, -0.3), (0, 1, 0), RING_FOV, False),
    ]
    return views + extra[:max(0, n_views - len(views))]


# ---------- COLMAP conversion (render sidecar -> RAW world-to-camera) ----------

def colmap_pose(cam, look, up):
    """Render-frame cam/look/up -> (R, t): COLMAP world-to-camera in RAW.

    raw = render * R2R (proper rotation, so cross products carry over).
    OpenCV rows: x=image right = fwd x up, y=image down = -(right x fwd),
    z=forward. Matches rendertools Cam (u = cx + f*x/z, v = cy - f*y_up/z),
    the projector the user-validated overlays were drawn with.
    """
    c = np.asarray(cam, np.float64) * R2R
    f = np.asarray(look, np.float64) * R2R - c
    f /= np.linalg.norm(f)
    r = np.cross(f, np.asarray(up, np.float64) * R2R)
    r /= np.linalg.norm(r)
    d = -np.cross(r, f)                    # image down
    R = np.stack([r, d, f])
    return R, -R @ c


def rotmat2qvec(R):
    """COLMAP's rotmat2qvec (read_write_model.py), qw >= 0."""
    Rxx, Ryx, Rzx, Rxy, Ryy, Rzy, Rxz, Ryz, Rzz = R.flat
    K = np.array([
        [Rxx - Ryy - Rzz, 0, 0, 0],
        [Ryx + Rxy, Ryy - Rxx - Rzz, 0, 0],
        [Rzx + Rxz, Rzy + Ryz, Rzz - Rxx - Ryy, 0],
        [Ryz - Rzy, Rzx - Rxz, Rxy - Ryx, Rxx + Ryy + Rzz]]) / 3.0
    vals, vecs = np.linalg.eigh(K)
    q = vecs[[3, 0, 1, 2], np.argmax(vals)]
    return -q if q[0] < 0 else q


def qvec2rotmat(q):
    """COLMAP's qvec2rotmat (matches the vendored colmap_loader.py)."""
    w, x, y, z = q
    return np.array([
        [1 - 2 * y * y - 2 * z * z, 2 * x * y - 2 * w * z, 2 * x * z + 2 * w * y],
        [2 * x * y + 2 * w * z, 1 - 2 * x * x - 2 * z * z, 2 * y * z - 2 * w * x],
        [2 * x * z - 2 * w * y, 2 * y * z + 2 * w * x, 1 - 2 * x * x - 2 * y * y]])


def focal(fov_deg):
    return (RES / 2) / math.tan(math.radians(fov_deg) / 2)


def project_colmap(R, t, fov, pts_raw):
    """RAW-space points -> pixel (u, v, depth) via the COLMAP pose."""
    cam = pts_raw @ R.T + t
    z = cam[:, 2]
    fl = focal(fov)
    return fl * cam[:, 0] / z + RES / 2, fl * cam[:, 1] / z + RES / 2, z


# ---------- rendering ----------

def fmt(v):
    return ",".join(f"{c:g}" for c in v)


def render_all(views, ply, ddir, gpu, force):
    wdir, idir, sdir = ddir / "render_webp", ddir / "images", ddir / "sidecars"
    for d in (wdir, idir, sdir):
        d.mkdir(parents=True, exist_ok=True)
    for name, cam, look, up, fov, _ in views:
        webp, png, side = wdir / f"{name}.webp", idir / f"{name}.png", sdir / f"{name}.json"
        meta = {"file": png.name, "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "preset": "cut_viewpack", "cam": fmt(cam), "look": fmt(look),
                "up": fmt(up), "fov": fov, "near": NEAR, "box": "", "sphere": "",
                "res": f"{RES}x{RES}", "ply": str(ply)}
        same = (side.exists() and webp.exists() and png.exists() and not force
                and all(json.loads(side.read_text()).get(k) == meta[k]
                        for k in ("cam", "look", "up", "fov", "res")))
        if same:
            print(f"skip {name} (exists, same camera)")
            continue
        cmd = ["splat-transform", "-w", "-g", gpu, str(ply),
               "--camera", fmt(cam), "--look-at", fmt(look), "--up", fmt(up),
               "--fov", str(fov), "--near", str(NEAR),
               "--resolution", f"{RES}x{RES}", "--background", BACKGROUND, str(webp)]
        print(f"rendering {name}  cam={fmt(cam)} look={fmt(look)} up={fmt(up)} "
              f"fov={fov} ...", flush=True)
        subprocess.run(cmd, check=True, shell=True, timeout=600)
        Image.open(webp).convert("RGB").save(png)   # lossless webp -> exact png
        side.write_text(json.dumps(meta, indent=2))
    # drop leftovers from an older camera set so dataset == images.txt exactly
    keep = {v[0] for v in views}
    for d, ext in ((wdir, ".webp"), (idir, ".png"), (sdir, ".json")):
        for p in d.glob(f"*{ext}"):
            if p.name[:-len(ext)] not in keep:
                p.unlink()
                print(f"removed stale {p.name}")


# ---------- COLMAP text files ----------

def write_colmap(views, poses, ddir, room_raw):
    sp = ddir / "sparse" / "0"
    sp.mkdir(parents=True, exist_ok=True)
    fovs = sorted({v[4] for v in views})
    cam_id = {fv: i + 1 for i, fv in enumerate(fovs)}
    lines = ["# Camera list with one line of data per camera:",
             "#   CAMERA_ID, MODEL, WIDTH, HEIGHT, PARAMS[]",
             f"# Number of cameras: {len(fovs)}"]
    for fv in fovs:
        fl = focal(fv)
        lines.append(f"{cam_id[fv]} PINHOLE {RES} {RES} "
                     f"{fl:.10f} {fl:.10f} {RES / 2:.1f} {RES / 2:.1f}")
    (sp / "cameras.txt").write_text("\n".join(lines) + "\n")

    lines = ["# Image list with two lines of data per image:",
             "#   IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME",
             "#   POINTS2D[] as (X, Y, POINT3D_ID)",
             f"# Number of images: {len(views)}"]
    for i, (name, _, _, _, fov, _) in enumerate(views):
        q, t = poses[name]["qvec"], poses[name]["tvec"]
        lines.append(f"{i + 1} " + " ".join(f"{x:.10f}" for x in [*q, *t])
                     + f" {cam_id[fov]} {name}.png")
        lines.append("")                    # empty POINTS2D line (required)
    (sp / "images.txt").write_text("\n".join(lines) + "\n")

    # tiny valid points3D.ply (fetchPly wants x/y/z, nx/ny/nz, rgb; content unused)
    lo, hi = room_raw
    pts = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1])
           for z in (lo[2], hi[2])]
    hdr = ["ply", "format ascii 1.0", f"element vertex {len(pts)}",
           "property float x", "property float y", "property float z",
           "property float nx", "property float ny", "property float nz",
           "property uchar red", "property uchar green", "property uchar blue",
           "end_header"]
    body = [f"{x:.4f} {y:.4f} {z:.4f} 0 0 0 128 128 128" for x, y, z in pts]
    (sp / "points3D.ply").write_text("\n".join(hdr + body) + "\n")
    return cam_id


# ---------- numeric verification (user judges visuals, we judge numbers) ----------

def verify(views, poses, lamps):
    report, fails = [], []
    for name, cam, look, up, fov, expect in views:
        R, t = poses[name]["R"], poses[name]["t"]
        q = poses[name]["qvec"]
        qerr = float(np.abs(qvec2rotmat(q) - R).max())
        c_raw = np.asarray(cam, np.float64) * R2R
        cerr = float(np.linalg.norm(-qvec2rotmat(q).T @ np.asarray(poses[name]["tvec"]) - c_raw))
        if qerr > 1e-9:
            fails.append(f"{name}: quaternion round-trip err {qerr:.3e}")
        if cerr > ROUNDTRIP_TOL:
            fails.append(f"{name}: camera-center round-trip err {cerr:.3e} m")
        cam3 = r3.Cam(cam, look, up, fov, RES, RES)     # the validated projector
        lamp_rows = {}
        for i, o in enumerate(lamps):
            ctr = np.asarray(o["center"], np.float64)[None]
            u1, v1, z1 = project_colmap(R, t, fov, ctr)
            u2, v2, z2 = cam3.project((ctr * R2R).astype(np.float32))
            diff = float(math.hypot(u1[0] - u2[0], v1[0] - v2[0]))
            inf1 = bool(z1[0] > NEAR and 0 <= u1[0] < RES and 0 <= v1[0] < RES)
            inf2 = bool(z2[0] > NEAR and 0 <= u2[0] < RES and 0 <= v2[0] < RES)
            if diff > CENTER_TOL_PX:
                fails.append(f"{name}/{o['id']}: colmap vs rendertools "
                             f"projection differ {diff:.3f} px")
            if inf1 != inf2:
                fails.append(f"{name}/{o['id']}: in-frame verdicts disagree "
                             f"(colmap {inf1} vs rendertools {inf2})")
            if i == 0 and inf1 != expect:
                fails.append(f"{name}: primary lamp in-frame={inf1}, "
                             f"designed expectation={expect}")
            lamp_rows[o["id"]] = {
                "uv_colmap": [round(float(u1[0]), 2), round(float(v1[0]), 2)],
                "uv_rendertools": [round(float(u2[0]), 2), round(float(v2[0]), 2)],
                "diff_px": round(diff, 4), "depth_m": round(float(z1[0]), 3),
                "in_frame": inf1}
        report.append({"view": name, "fov": fov, "cam_render": list(cam),
                       "cam_raw": [round(float(x), 4) for x in c_raw],
                       "qvec": [round(float(x), 8) for x in q],
                       "tvec": [round(float(x), 8) for x in poses[name]["tvec"]],
                       "quat_roundtrip_err": qerr,
                       "center_roundtrip_err_m": cerr,
                       "expected_lamp_in_frame": expect, "lamp": lamp_rows})
    return report, fails


# ---------- overlays + contact sheet ----------

def draw_lamp_boxes(im, R, t, fov, lamps, colors):
    dr = ImageDraw.Draw(im)
    for o, col in zip(lamps, colors):
        lo, hi = np.asarray(o["aabb_min"], np.float64), np.asarray(o["aabb_max"], np.float64)
        corners = np.array([[x, y, z] for x in (lo[0], hi[0])
                            for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        u, v, z = project_colmap(R, t, fov, corners)
        if np.median(z) < NEAR:
            continue
        ok = z > NEAR
        for i in range(8):
            for j in range(i + 1, 8):
                if bin(i ^ j).count("1") == 1 and ok[i] and ok[j]:
                    dr.line([(u[i], v[i]), (u[j], v[j])], fill=col, width=3)
        cu, cv, cz = project_colmap(R, t, fov, np.asarray(o["center"], np.float64)[None])
        if cz[0] > NEAR:
            x, y = float(cu[0]), float(cv[0])
            dr.line([(x - 8, y), (x + 8, y)], fill=col, width=2)
            dr.line([(x, y - 8), (x, y + 8)], fill=col, width=2)
        if ok.any():
            dr.text((float(np.clip(u[ok].min(), 2, RES - 120)),
                     float(np.clip(v[ok].min() - 16, 2, RES - 16))),
                    f'{o["id"]} {o["label"]}', fill=col)


def minimap_svg(views, lamps, room_render):
    """Top-down schematic (render x right, z DOWN — same orientation as the
    judge_down render): room extent, standpoints, view directions, lamp."""
    (x0, z0), (x1, z1) = room_render
    s = 200.0 / max(x1 - x0, z1 - z0)
    pad = 16
    w, h = (x1 - x0) * s + 2 * pad, (z1 - z0) * s + 2 * pad

    def m(x, z):
        return pad + (x - x0) * s, pad + (z - z0) * s

    dot_col = {"judge": "#9aa0ac", "cut_b": "#ff8a65", "cut_c": "#4dd0e1",
               "cut_d": "#aed581"}
    parts = [f'<svg width="{w:.0f}" height="{h:.0f}" '
             f'xmlns="http://www.w3.org/2000/svg" style="background:#101216">',
             f'<rect x="{pad}" y="{pad}" width="{(x1 - x0) * s:.1f}" '
             f'height="{(z1 - z0) * s:.1f}" fill="none" stroke="#555"/>']
    for o, col in zip(lamps, PALETTE):
        (a, b), (c, d) = m(-o["aabb_max"][0], o["aabb_min"][2]), \
                         m(-o["aabb_min"][0], o["aabb_max"][2])   # raw x -> render x
        parts.append(f'<rect x="{a:.1f}" y="{b:.1f}" width="{c - a:.1f}" '
                     f'height="{d - b:.1f}" fill="{col}" opacity="0.85"/>')
    seen = set()
    for name, cam, look, up, fov, _ in views:
        key = name[:5] if name.startswith("cut_") else "judge"
        col = dot_col.get(key, "#ccc")
        cx, cz = m(cam[0], cam[2])
        dx, dz = look[0] - cam[0], look[2] - cam[2]
        n = math.hypot(dx, dz)
        if n > 0.2:
            parts.append(f'<line x1="{cx:.1f}" y1="{cz:.1f}" '
                         f'x2="{cx + dx / n * 26:.1f}" y2="{cz + dz / n * 26:.1f}" '
                         f'stroke="{col}" stroke-width="1.5" opacity="0.6"/>')
        if key not in seen:
            seen.add(key)
            label = {"judge": "A (judge)", "cut_b": "B", "cut_c": "C",
                     "cut_d": "D"}[key]
            parts.append(f'<circle cx="{cx:.1f}" cy="{cz:.1f}" r="4" fill="{col}"/>'
                         f'<text x="{cx + 6:.1f}" y="{cz - 5:.1f}" fill="{col}" '
                         f'font-size="11" font-family="system-ui">{label}</text>')
    parts.append("</svg>")
    return "".join(parts)


def contact_sheet(views, poses, lamps, report, ddir, scene):
    odir = ddir / "overlays"
    odir.mkdir(exist_ok=True)
    rows = {r["view"]: r for r in report}
    for name, cam, look, up, fov, _ in views:
        im = Image.open(ddir / "images" / f"{name}.png").convert("RGB")
        draw_lamp_boxes(im, poses[name]["R"], poses[name]["t"], fov, lamps, PALETTE)
        im.save(odir / f"{name}.png")
    man = json.loads(paths.manifest(scene).read_text())
    p1 = np.asarray(man["frame"]["extent_p1"], np.float64) * R2R
    p99 = np.asarray(man["frame"]["extent_p99"], np.float64) * R2R
    lo, hi = np.minimum(p1, p99), np.maximum(p1, p99)
    svg = minimap_svg(views, lamps, ((lo[0], lo[2]), (hi[0], hi[2])))

    legend = "".join(
        f'<span class="chip"><span class="sw" style="background:{col}"></span>'
        f'{o["id"]} — {o["label"]} (score {o.get("score", "?")})</span>'
        for o, col in zip(lamps, PALETTE))
    groups = [("Standpoint A — judge rig (0, 1.6, 0), the proven 7-view pattern",
               [v for v in views if v[0].startswith("judge")]),
              ("Standpoint B — offset (+x side)", [v for v in views if v[0].startswith("cut_b")]),
              ("Standpoint C — offset (-x side)", [v for v in views if v[0].startswith("cut_c")]),
              ("Standpoint D — offset (near lamp wall)", [v for v in views if v[0].startswith("cut_d")])]
    figs = ""
    for title, vs in groups:
        if not vs:
            continue
        figs += f"<h2>{title}</h2><div class='grid'>"
        for name, cam, look, up, fov, expect in vs:
            r = rows[name]
            lamp_txt = " · ".join(
                f'{oid}: ({d["uv_colmap"][0]:.0f}, {d["uv_colmap"][1]:.0f}) px'
                for oid, d in r["lamp"].items() if d["in_frame"]) or "lamp not in frame"
            tag = ("<span class='in'>lamp expected in frame</span>" if expect
                   else "<span class='out'>lamp not expected</span>")
            figs += (f"<figure><a href='overlays/{name}.png'>"
                     f"<img src='overlays/{name}.png' loading='lazy'></a>"
                     f"<figcaption><b>{name}</b> · fov {fov:g}° · "
                     f"cam ({fmt(cam)})<br>{tag}<br>{lamp_txt}</figcaption></figure>")
        figs += "</div>"

    html = f"""<!doctype html><meta charset="utf-8">
<title>Checkpoint 3 — view-coverage review — {scene}</title>
<style>
 body{{background:#15171c;color:#dcdfe6;font:14px/1.5 system-ui;margin:20px;max-width:1500px}}
 .banner{{background:#3a1f1f;border:2px solid #c94f4f;border-radius:8px;padding:12px 18px;margin-bottom:16px}}
 .banner h1{{margin:0 0 6px;font-size:20px;color:#ff9c9c}}
 h2{{margin:26px 0 8px;font-size:16px;color:#aeb6c4}}
 .grid{{display:flex;flex-wrap:wrap;gap:10px}}
 figure{{margin:0;width:300px}} figure img{{width:300px;display:block;border-radius:4px}}
 figcaption{{font-size:12px;color:#9aa0ac;padding:4px 2px}}
 .chip{{display:inline-flex;align-items:center;gap:6px;margin-right:18px}}
 .sw{{display:inline-block;width:14px;height:14px;border-radius:3px}}
 .in{{color:#8fd18f}} .out{{color:#777}}
 .map{{display:flex;gap:24px;align-items:flex-start;margin:10px 0}}
 .map p{{max-width:520px}}
 code{{color:#c8d3f5}}
</style>
<div class="banner"><h1>🔴 WAITING ON YOU — Checkpoint 3: view-coverage review</h1>
<ol>
 <li><b>Lamp coverage</b> — the colored box should sit on the freestanding lamp in
     every view tagged <span class="in">lamp expected in frame</span> (8 views, 4 standpoints).</li>
 <li><b>Camera math</b> — the box should <i>hug</i> the lamp (not float beside,
     mirror across the room, or sit upside-down). A box hugging the lamp in every
     view = the COLMAP conversion is right.</li>
 <li><b>Frame sanity</b> — every render upright, nothing mirrored.</li>
 <li><b>Room coverage</b> — together the views should show most of the room
     (minimap below; plan orientation matches the judge_down render: +x right, +z down).</li>
</ol></div>
<p>Lamp candidates from <code>scene_manifest.json</code>: {legend}</p>
<div class="map">{svg}
<p>Dots = camera standpoints, lines = view directions, colored rect = lamp box
footprint. Clean (overlay-free) copies of these renders are the GaussianCut
dataset at <code>images/</code>; COLMAP cameras at <code>sparse/0/</code>;
numeric checks at <code>verification.json</code>. Click any image for full size
(overlay drawn from the COLMAP pose, so it tests the new camera files, not the
old pipeline).</p></div>
{figs}
"""
    out = ddir / "contact_sheet.html"
    out.write_text(html, encoding="utf-8")
    return out


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scene", required=True)
    ap.add_argument("--views", type=int, default=15,
                    help="total view count, 7..15 (judge 7 always kept)")
    ap.add_argument("--gpu", default="0")
    ap.add_argument("--force", action="store_true",
                    help="re-render views that already exist")
    a = ap.parse_args()
    if not 7 <= a.views <= 15:
        raise SystemExit("--views must be 7..15 (the 7 judge views are fixed)")

    ply = paths.ply(a.scene)
    if not ply.exists():
        raise SystemExit(f"no splat: {ply}")
    man = json.loads(paths.manifest(a.scene).read_text())
    if list(man["frame"].get("raw_to_render", [])) != list(R2R):
        raise SystemExit(f"manifest raw_to_render {man['frame'].get('raw_to_render')} "
                         f"!= expected {list(R2R)} — frame contract changed, stop")
    lamps = [o for o in man["objects"] if "lamp" in o["label"].lower()]
    if not lamps:
        raise SystemExit("no object with 'lamp' in its label in the manifest")
    lamps.sort(key=lambda o: -o.get("score", 0))
    primary = lamps[0]
    lamp_render = np.asarray(primary["center"], np.float64) * R2R
    print(f"lamp candidates: {[(o['id'], o['label']) for o in lamps]}; "
          f"primary {primary['id']} render-frame center {np.round(lamp_render, 3)}")

    views = rig(lamp_render, a.views)

    # cameras must sit inside the room envelope
    p1 = np.asarray(man["frame"]["extent_p1"], np.float64) * R2R
    p99 = np.asarray(man["frame"]["extent_p99"], np.float64) * R2R
    lo, hi = np.minimum(p1, p99), np.maximum(p1, p99)
    for name, cam, *_ in views:
        c = np.asarray(cam, np.float64)
        if ((c[[0, 2]] < lo[[0, 2]] + WALL_MARGIN).any()
                or (c[[0, 2]] > hi[[0, 2]] - WALL_MARGIN).any()
                or not lo[1] < c[1] < hi[1]):
            raise SystemExit(f"{name}: camera {cam} outside room envelope "
                             f"{np.round(lo, 2)}..{np.round(hi, 2)} (render frame)")

    ddir = paths.scene_dir(a.scene) / "cut" / "dataset"
    render_all(views, ply, ddir, a.gpu, a.force)

    poses = {}
    for name, cam, look, up, fov, _ in views:
        R, t = colmap_pose(cam, look, up)
        poses[name] = {"R": R, "t": t, "qvec": rotmat2qvec(R), "tvec": t}
    room_raw = (np.minimum(man["frame"]["extent_p1"], man["frame"]["extent_p99"]),
                np.maximum(man["frame"]["extent_p1"], man["frame"]["extent_p99"]))
    write_colmap(views, poses, ddir, room_raw)

    report, fails = verify(views, poses, lamps)
    summary = {
        "max_quat_roundtrip_err": max(r["quat_roundtrip_err"] for r in report),
        "max_center_roundtrip_err_m": max(r["center_roundtrip_err_m"] for r in report),
        "max_lamp_proj_diff_px": max(d["diff_px"] for r in report
                                     for d in r["lamp"].values()),
        "checks_passed": not fails, "failures": fails}
    (ddir / "verification.json").write_text(json.dumps(
        {"scene": a.scene, "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
         "resolution": [RES, RES], "colmap_world": "raw (gen_raw.ply space)",
         "raw_to_render": list(R2R),
         "lamp_candidates": [{"id": o["id"], "label": o["label"],
                              "center_raw": o["center"]} for o in lamps],
         "summary": summary, "views": report}, indent=1))
    print(f"verification: quat_rt {summary['max_quat_roundtrip_err']:.2e}  "
          f"center_rt {summary['max_center_roundtrip_err_m']:.2e} m  "
          f"proj_diff {summary['max_lamp_proj_diff_px']:.4f} px")
    if fails:
        for f in fails:
            print("FAIL:", f)
        raise SystemExit(2)

    sheet = contact_sheet(views, poses, lamps, report, ddir, a.scene)
    print("dataset ->", ddir)
    print("contact sheet ->", sheet)


if __name__ == "__main__":
    main()
