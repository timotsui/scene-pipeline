"""Step 9 — mask-pack: object masks for GaussianCut (SAM2 video propagation).

DECISION HISTORY (Checkpoint 5):
  * First pass (2026-07-21): plain full-frame SAM box prompts
    (facebook/sam-vit-base). REJECTED by the user — cut_c_lamp bled onto
    the WINDOW behind the lamp, cut_d_lamp onto part of the table,
    cut_c_right missed part of the lamp, general bleed. Root cause: the
    lamp was only 0.2-2% of the 900x900 frame.
  * Second pass ("Option A"): crop-zoom + point prompts, same checkpoint.
    Recipe revision A (positive at the 3D-box-CENTER pixel) was
    numerically falsified before review (spill 16-50% upward into the
    projected window box; the center pixel lands on window pixels between
    pole and shade). Revision B (shade-point positive + corner/top-edge/
    window negatives + box-consistent candidate pick) fixed 5/8 views but
    3 views had NO box-consistent SAM candidate. ALSO REJECTED by the user.
    Numeric guards failed to predict the user's judgment → demoted to
    hints (see below).
  * Third pass (THIS DEFAULT; user decision "go", 2026-07-21): SAM2 VIDEO
    PROPAGATION (download approved). New standing rule recorded at the
    same time: ALL manual fallbacks are permanently BANNED — "no manual
    work in the pipeline — the pipeline is text to CAD"; the user only
    reviews. Gating relaxed: masks get only a quick user glance; the real
    quality gate moves to the graph-cut output (Checkpoint 6) since
    GaussianCut is designed to refine coarse masks — do not over-optimize
    for pixel perfection.
      - Integration: HF transformers' built-in Sam2VideoModel/
        Sam2VideoProcessor (transformers 5.13.0 supports it natively) —
        ZERO new packages, system torch untouched (2.6.0+cu124, verified
        before/after every run and hard-stopped on any change).
      - Model: facebook/sam2.1-hiera-large (~856 MB); automatic retry on
        facebook/sam2.1-hiera-base-plus if the large model runs out of
        the 12 GB VRAM (recorded in mask_stats.json when it happens).
      - Pseudo-video: the object-seeing views ordered into a maximally
        smooth camera path — greedy nearest neighbor on (camera position,
        viewing direction) from the sidecars, distance = |dpos| +
        1.0 * |dforward|, ties broken by view name; path STARTS at the
        init view. Order recorded in mask_stats.json.
      - Init frame: cut_d_lamp (closest range, object largest in frame);
        init prompt = the projected manifest box + the pass-2 shade
        positive point (both automatic). Every view's mask comes out of
        the propagation session (the init frame's from its conditioning
        prompt) — no independent single-image segmentation anywhere. If
        the init view sat mid-path, the reversed sequence would be
        propagated too (generic code path; with the path starting at the
        init view a single forward pass covers everything).
  * Fourth pass (2026-07-21, driven by the graph-cut diagnostic
    out/<scene>/cut/<object>/score_diagnostic.json): the cut's R4 region —
    296 Gaussians in the box footprint just BELOW the manifest box bottom
    (y = -0.675, the lamp BASE) — was rendered in all masked views but had
    coarse score exactly 0.0: pass-3 masks structurally never covered base
    pixels because every prompt came from the manifest box. Fix (approved):
    same sam2-video strategy, ONE change — the PROMPT box bottom is
    extended to 0.50 m physical height (-y convention: aabb_max.y
    -0.675 -> -0.50) via --extend-bottom-to 0.50; top/sides, shade point,
    ordering, init frame and model are identical to pass 3. Numeric
    verification required and built in: R4 base probes (footprint center
    + corners in the 5 cm band below the original box bottom) are
    projected into every view and checked against the new masks
    (base_coverage in mask_stats.json); per-view area growth vs the
    pass-3 archive > 3x raises a "desk-grab(>3x pass3)" hint.
  * The pass-2 recipe stays selectable via --strategy crop-points for
    provenance runs; earlier-pass stats+overlays are archived as
    mask_stats_pass{1,2,3}.json and mask_overlays/pass{1,2,3}/.
  * Option C (a stronger single-image checkpoint) is superseded by SAM2.

The prompt rectangle everywhere = the object's RAW-space manifest box
corners projected with the rendertools Cam projector that prep_views.py
verified against the COLMAP files (Checkpoint 3: user confirmed the box
hugs the lamp), 2D-bounded, + margin, clamped.

Inputs   (dataset = out/<scene>/cut/dataset/, built by prep_views.py):
  images/<view>.png            the 900x900 renders
  sidecars/<view>.json         shot.py-format cam/look/up/fov, RENDER frame
  sparse/0/images.txt          canonical view order (ordering only)
  verification.json            in-frame cross-check (when the object is in it)
  out/<scene>/scene_manifest.json   object (+ window) RAW-space aabbs

Outputs  (mask format per FEASIBILITY_GAUSSIANCUT.md section 2c):
  multiview_masks/<view>.png   single-channel 0/255 mask, stem == image stem.
                               NOTHING else may live in this folder —
                               GaussianCut iterates over its files, and a
                               stem matching no camera crashes the loader
                               (stale stems are deleted on every run).
  mask_overlays/<view>.png     render + mask + prompt overlays
  mask_overlays/pass1/ pass2/  archived earlier-pass overlays (comparison)
  mask_stats.json              stats + full provenance per view. NUMERIC
                               STATS ARE HINTS ONLY — demoted as a gate
                               after pass 2 (they failed to predict user
                               judgment); the real gate is Checkpoint 6.
  mask_review.html             Checkpoint 5 third-pass quick-glance page

multiview_masks/ holds masks for ONE object at a time (recorded in
mask_stats.json); switching --object requires --force and clears the folder.
To drop a view after review, delete its PNG from multiview_masks/ before
Step 10 (a later rerun would regenerate it).

Usage:  python make_masks.py --scene bedroom_marble --object obj_004
        [--strategy sam2-video|crop-points]   default sam2-video
        [--extend-bottom-to 0.50]  PASS 4: extend the PROMPT box bottom to
                                   this physical height in m (-y units);
                                   omit for the plain pass-3 behavior
        [--init-view cut_d_lamp]              sam2: propagation init frame
        [--sam2-model facebook/sam2.1-hiera-large]
        [--force]                  re-run even where outputs exist
        [--views v1 v2 ...]        crop-points only; sam2 propagation is
                                   all-or-nothing and rejects --views
        [--margin-frac 0.03]       prompt-rect margin, fraction of frame side
        [--crop-factor 2.0]        crop-points: crop side vs rect long side
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import paths  # noqa: E402

SAM_ID = "facebook/sam-vit-base"     # pass-1/2 checkpoint (crop-points strategy)
SAM2_ID = "facebook/sam2.1-hiera-large"
SAM2_FALLBACK_ID = "facebook/sam2.1-hiera-base-plus"   # if large OOMs on 12 GB
MODE_SAM2 = "pass3: sam2-video propagation, init box+shade-point"
MODE_CROP = ("pass2revB: crop-zoom + box + shade-positive + corner/top-edge/"
             "window negatives + box-consistent candidate pick")
STATS_ROLE = ("hint only — demoted as a gate after pass 2 (numeric guards "
              "failed to predict user judgment); real gate = Checkpoint 6 "
              "on the graph-cut output")
DIR_WEIGHT = 1.0                     # ordering metric: |dpos| + w*|dforward|
R2R = np.array([-1.0, -1.0, 1.0])    # raw <-> render, elementwise, self-inverse
MASK_FILL = (255, 64, 208)           # overlay fill (magenta, 45% blend)
RECT_COL = "#ffd740"                 # prompt-rectangle outline (yellow)
CROP_COL = "#9aa0ac"                 # crop-boundary outline (gray)
POS_COL = "#69f0ae"                  # positive point (green circle)
NEG_COL = "#ff5252"                  # negative points (red X)
CROP_MIN = 128                       # crop-points: never crop tighter (px)
CORNER_INSET = 4                     # crop-points: corner negatives inset
TOP_NEG_OFFSET = 10                  # crop-points: top-edge negatives offset
TOP_NEG_XS = (0.3, 0.5, 0.7)         # crop-points: top-edge negative fractions
NEG_RECT_DILATE = 10                 # crop-points: window-negative clearance
SHADE_FRAC = 0.20                    # positive: this far below the box top plane
SELECT_INSIDE_MIN = 0.90             # crop-points: candidate consistency bar
TINY_PCT = 0.1                       # hint: mask area < 0.1% of frame
HUGE_PCT = 30.0                      # hint: mask area > 30% of frame
INSIDE_MIN = 0.5                     # hint: < 50% of mask inside prompt rect


# ---------- dataset reading ----------

def read_sidecar(ddir, name):
    d = json.loads((ddir / "sidecars" / f"{name}.json").read_text())
    w, h = (int(x) for x in d["res"].split("x"))
    if w != h:
        raise SystemExit(f"{name}: non-square render {d['res']} — fx=fy assumption breaks")
    return {"cam": tuple(float(x) for x in d["cam"].split(",")),
            "look": tuple(float(x) for x in d["look"].split(",")),
            "up": tuple(float(x) for x in d["up"].split(",")),
            "fov": float(d["fov"]), "near": float(d["near"]), "res": w}


def view_order(ddir):
    """Dataset view stems in images.txt order (the canonical camera order)."""
    txt = ddir / "sparse" / "0" / "images.txt"
    stems = []
    if txt.exists():
        for line in txt.read_text().splitlines():
            parts = line.split()
            if len(parts) == 10 and not line.startswith("#"):
                stems.append(parts[9].rsplit(".", 1)[0])
    if not stems:
        stems = sorted(p.stem for p in (ddir / "sidecars").glob("*.json"))
    return stems


# ---------- projection (rendertools Cam — the Checkpoint-3-verified path) ----------

def box_corners_raw(obj):
    lo = np.asarray(obj["aabb_min"], np.float64)
    hi = np.asarray(obj["aabb_max"], np.float64)
    return np.array([[x, y, z] for x in (lo[0], hi[0])
                     for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])


def shade_point_raw(obj):
    """Box horizontal center, SHADE_FRAC below the box TOP plane.

    RAW frame has up = -y (asserted in main), so the top plane is
    aabb_min[1]; going 20% of the height toward aabb_max[1] lands in the
    lampshade region — the widest, most solid part of a lamp.
    """
    lo, hi = obj["aabb_min"], obj["aabb_max"]
    return [(lo[0] + hi[0]) / 2, lo[1] + SHADE_FRAC * (hi[1] - lo[1]),
            (lo[2] + hi[2]) / 2]


def project_center(cam3, sc, pt_raw):
    """RAW point -> (u, v, in_frame) through the render-frame camera."""
    u, v, z = cam3.project((np.asarray(pt_raw, np.float64)[None] * R2R)
                           .astype(np.float32))
    in_frame = bool(z[0] > sc["near"] and 0 <= u[0] < sc["res"]
                    and 0 <= v[0] < sc["res"])
    return float(u[0]), float(v[0]), in_frame


def prompt_rect(cam3, sc, obj, margin_frac):
    """Clamped 2D bounding rect of the in-front projected box corners + margin."""
    u, v, z = cam3.project((box_corners_raw(obj) * R2R).astype(np.float32))
    ok = z > sc["near"]
    if ok.sum() < 4:
        return None
    res, m = sc["res"], margin_frac * sc["res"]
    x0 = int(max(0, math.floor(u[ok].min() - m)))
    y0 = int(max(0, math.floor(v[ok].min() - m)))
    x1 = int(min(res - 1, math.ceil(u[ok].max() + m)))
    y1 = int(min(res - 1, math.ceil(v[ok].max() + m)))
    if x1 - x0 < 10 or y1 - y0 < 10:
        return None
    return [x0, y0, x1, y1]


# ---------- pseudo-video ordering (sam2-video strategy) ----------

def order_smooth(names, sidecars, start):
    """Greedy nearest-neighbor camera path from `start`.

    Distance = |camera position delta| + DIR_WEIGHT * |unit-forward delta|
    (positions in meters, render frame, from the sidecars). Ties broken by
    view name for determinism.
    """
    def state(n):
        sc = sidecars[n]
        c = np.asarray(sc["cam"], np.float64)
        f = np.asarray(sc["look"], np.float64) - c
        return c, f / np.linalg.norm(f)

    st = {n: state(n) for n in names}

    def dist(a, b):
        return (float(np.linalg.norm(st[a][0] - st[b][0]))
                + DIR_WEIGHT * float(np.linalg.norm(st[a][1] - st[b][1])))

    path, left = [start], sorted(n for n in names if n != start)
    while left:
        nxt = min(left, key=lambda n: (dist(path[-1], n), n))
        path.append(nxt)
        left.remove(nxt)
    return path


# ---------- crop-points prompts (pass-2 strategy, kept for provenance) ----------

def crop_square(rect, res, factor):
    """Square crop around the rect: side = factor * long side, kept in frame."""
    x0, y0, x1, y1 = rect
    side = int(min(res, max(CROP_MIN, round(factor * max(x1 - x0 + 1, y1 - y0 + 1)))))
    cx0 = int(round((x0 + x1) / 2 - side / 2))
    cy0 = int(round((y0 + y1) / 2 - side / 2))
    cx0 = max(0, min(res - side, cx0))
    cy0 = max(0, min(res - side, cy0))
    return [cx0, cy0, side]


def build_points(rect, pos_uv, win_uv, crop):
    """Deterministic point prompts for crop-points, full-frame coords."""
    x0, y0, x1, y1 = rect
    cx0, cy0, side = crop
    i = CORNER_INSET
    pos = [[round(pos_uv[0], 1), round(pos_uv[1], 1)]]
    corners = [[x0 + i, y0 + i], [x1 - i, y0 + i],
               [x0 + i, y1 - i], [x1 - i, y1 - i]]
    top = []
    ty = max(y0 - TOP_NEG_OFFSET, cy0 + 2)
    if ty < y0:
        top = [[round(x0 + f * (x1 - x0), 1), ty] for f in TOP_NEG_XS]
    win = []
    if win_uv is not None:
        wu, wv = win_uv
        d = NEG_RECT_DILATE
        if (cx0 + 2 <= wu <= cx0 + side - 3 and cy0 + 2 <= wv <= cy0 + side - 3
                and not (x0 - d <= wu <= x1 + d and y0 - d <= wv <= y1 + d)):
            win = [[round(wu, 1), round(wv, 1)]]
    return pos, corners, top, win


# ---------- numeric stats (HINTS ONLY since pass 2 — user gate is visual) ----------

def mask_stats(mask, rect, res):
    x0, y0, x1, y1 = rect
    area = int(mask.sum())
    pct = 100.0 * area / (res * res)
    inside = int(mask[y0:y1 + 1, x0:x1 + 1].sum())
    inside_frac = inside / area if area else 0.0
    if area:
        ys, xs = np.nonzero(mask)
        bb = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
        iw = max(0, min(bb[2], x1) - max(bb[0], x0) + 1)
        ih = max(0, min(bb[3], y1) - max(bb[1], y0) + 1)
        inter = iw * ih
        a_bb = (bb[2] - bb[0] + 1) * (bb[3] - bb[1] + 1)
        a_rc = (x1 - x0 + 1) * (y1 - y0 + 1)
        bbox_iou = inter / (a_bb + a_rc - inter)
    else:
        bb, bbox_iou = None, 0.0
    hints = []
    if pct < TINY_PCT:
        hints.append("tiny")
    if pct > HUGE_PCT:
        hints.append("huge")
    if inside_frac < INSIDE_MIN:
        hints.append("mostly-outside-prompt")
    return {"area_px": area, "area_pct": round(pct, 3),
            "inside_prompt_frac": round(inside_frac, 4), "mask_bbox": bb,
            "bbox_iou_vs_prompt": round(bbox_iou, 4), "hints": hints}


# ---------- R4 base-region verification (Gaussian-level, pass 4) ----------

def r4_gaussians(scene, obj, pad=0.05):
    """The cut diagnostic's R4 proxy: splat Gaussians in the object's
    footprint (padded +-pad in x/z) BELOW the manifest box bottom (all the
    way down — measurement 2026-07-21: the region reaches the floor).
    These are the exact points whose coarse score the graph cut computes,
    so mask coverage is measured on them, not on synthetic probe pixels.
    """
    r3 = paths.load_r3()
    xyz = r3.load_splat(str(paths.ply(scene)), opacity_min=0.0)[0]
    lo, hi = np.asarray(obj["aabb_min"]), np.asarray(obj["aabb_max"])
    sel = ((xyz[:, 0] >= lo[0] - pad) & (xyz[:, 0] <= hi[0] + pad)
           & (xyz[:, 2] >= lo[2] - pad) & (xyz[:, 2] <= hi[2] + pad)
           & (xyz[:, 1] > hi[1]))
    return xyz[sel].astype(np.float64)


def base_coverage(pts_raw, cam3, sc, mask):
    """How many R4 Gaussians project inside the mask in this view."""
    if len(pts_raw) == 0:
        return {"r4_gaussians": 0, "in_frame": 0, "in_mask": 0, "frac": 0.0}
    u, v, z = cam3.project((pts_raw * R2R).astype(np.float32))
    res = sc["res"]
    inf = (z > sc["near"]) & (u >= 0) & (u < res) & (v >= 0) & (v < res)
    ui = np.clip(u[inf].round().astype(int), 0, res - 1)
    vi = np.clip(v[inf].round().astype(int), 0, res - 1)
    hits = int(mask[vi, ui].sum()) if inf.any() else 0
    return {"r4_gaussians": int(len(pts_raw)), "in_frame": int(inf.sum()),
            "in_mask": hits, "frac": round(hits / max(int(inf.sum()), 1), 4)}


# ---------- strategy: sam2-video (pass 3, default) ----------

def run_sam2_video(ddir, path_order, init_view, geo, model_id):
    """Propagate the init prompt through the ordered pseudo-video.

    Returns (per-view {name: (mask, score_logit, source)}, model_id used,
    torch versions (before, after)). Retries once on base-plus if the
    large model OOMs. Every mask comes from the propagation session.
    """
    import torch
    ver_before = torch.__version__
    from transformers import Sam2VideoModel, Sam2VideoProcessor
    device = "cuda" if torch.cuda.is_available() else "cpu"
    frames = [Image.open(ddir / "images" / f"{n}.png").convert("RGB")
              for n in path_order]
    res = frames[0].height
    init_idx = path_order.index(init_view)
    g = geo[init_view]
    model = None
    tried = [model_id]
    while True:
        mid = tried[-1]
        try:
            print(f"loading SAM2 ({mid}) on {device}...", flush=True)
            model = Sam2VideoModel.from_pretrained(mid).to(device)
            model.eval()
            proc = Sam2VideoProcessor.from_pretrained(mid)
            session = proc.init_video_session(video=frames,
                                              inference_device=device)
            proc.add_inputs_to_inference_session(
                session, frame_idx=init_idx, obj_ids=1,
                input_boxes=[[[float(v) for v in g["rect"]]]],
                input_points=[[[[float(g["pos"][0][0]), float(g["pos"][0][1])]]]],
                input_labels=[[[1]]])
            results = {}
            for reverse in ([False, True] if init_idx > 0 else [False]):
                for out in model.propagate_in_video_iterator(
                        session, start_frame_idx=init_idx, reverse=reverse):
                    m = proc.post_process_masks(
                        [out.pred_masks], original_sizes=[[res, res]])[0]
                    m = np.asarray(m.cpu()).squeeze()
                    if m.ndim != 2:
                        raise SystemExit(f"unexpected SAM2 mask shape {m.shape}")
                    name = path_order[out.frame_idx]
                    score = (float(np.asarray(out.object_score_logits
                                              .float().cpu()).reshape(-1)[0])
                             if out.object_score_logits is not None else None)
                    src = ("init-frame (conditioned on the prompt)"
                           if out.frame_idx == init_idx else
                           f"propagation-{'reverse' if reverse else 'forward'}")
                    results[name] = (m.astype(bool), score, src)
            missing = [n for n in path_order if n not in results]
            if missing:
                raise SystemExit(f"propagation left views unmasked: {missing}")
            return results, mid, (ver_before, torch.__version__)
        except torch.cuda.OutOfMemoryError:
            if SAM2_FALLBACK_ID in tried:
                raise SystemExit(f"OOM on both {tried} — 12 GB VRAM insufficient")
            print(f"OOM on {mid} — retrying with {SAM2_FALLBACK_ID}", flush=True)
            del model
            torch.cuda.empty_cache()
            tried.append(SAM2_FALLBACK_ID)


# ---------- strategy: crop-points (pass 2, provenance) ----------

def load_sam():
    import torch
    from transformers import SamModel, SamProcessor
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"loading SAM ({SAM_ID}) on {device}...", flush=True)
    sam = SamModel.from_pretrained(SAM_ID).to(device)
    sam.eval()
    proc = SamProcessor.from_pretrained(SAM_ID)
    return torch, sam, proc, device


def run_sam(torch, sam, proc, device, img, rect, crop, points, labels):
    """Crop-zoomed box+point SAM with box-consistent candidate selection."""
    cx0, cy0, side = crop
    crop_img = img.crop((cx0, cy0, cx0 + side, cy0 + side))
    rx0, ry0 = rect[0] - cx0, rect[1] - cy0
    rx1, ry1 = rect[2] - cx0, rect[3] - cy0
    box = [[[float(rx0), float(ry0), float(rx1), float(ry1)]]]
    pts = [[[[float(u - cx0), float(v - cy0)] for u, v in points]]]
    inputs = proc(crop_img, input_boxes=box, input_points=pts,
                  input_labels=[[labels]], return_tensors="pt").to(device)
    with torch.no_grad():
        outs = sam(**inputs, multimask_output=True)
    masks = proc.image_processor.post_process_masks(
        outs.pred_masks.cpu(), inputs["original_sizes"].cpu(),
        inputs["reshaped_input_sizes"].cpu())[0][0]
    iou = outs.iou_scores.reshape(-1).cpu()
    cands = []
    for i in range(masks.shape[0]):
        m = masks[i].numpy().astype(bool)
        area = int(m.sum())
        ins = int(m[ry0:ry1 + 1, rx0:rx1 + 1].sum()) / area if area else 0.0
        cands.append({"idx": i, "pred_iou": round(float(iou[i]), 4),
                      "area_px": area, "inside_prompt_frac": round(ins, 4)})
    ok = [c for c in cands if c["inside_prompt_frac"] >= SELECT_INSIDE_MIN
          and c["area_px"] > 0]
    if ok:
        pick, fallback = max(ok, key=lambda c: c["pred_iou"])["idx"], False
    else:
        pick = max(cands, key=lambda c: (c["inside_prompt_frac"],
                                         c["pred_iou"]))["idx"]
        fallback = True
    full = np.zeros((img.height, img.width), bool)
    full[cy0:cy0 + side, cx0:cx0 + side] = masks[pick].numpy().astype(bool)
    return full, pick, float(iou[pick]), cands, fallback


# ---------- outputs ----------

def write_overlay(img, mask, rect, out_path, crop=None, pos=(), negs=(),
                  note=""):
    base = np.asarray(img.convert("RGB")).astype(np.float32)
    base[mask] = 0.55 * base[mask] + 0.45 * np.asarray(MASK_FILL, np.float32)
    im = Image.fromarray(base.astype(np.uint8))
    dr = ImageDraw.Draw(im)
    if crop is not None:
        cx0, cy0, side = crop
        dr.rectangle([cx0, cy0, cx0 + side - 1, cy0 + side - 1],
                     outline=CROP_COL, width=1)
    dr.rectangle(rect, outline=RECT_COL, width=2)
    for u, v in pos:
        dr.ellipse([u - 6, v - 6, u + 6, v + 6], outline=POS_COL, width=3)
    for u, v in negs:
        dr.line([u - 5, v - 5, u + 5, v + 5], fill=NEG_COL, width=3)
        dr.line([u - 5, v + 5, u + 5, v - 5], fill=NEG_COL, width=3)
    if note:
        dr.text((8, 8), note, fill="#ffffff")
    im.save(out_path)


def review_page(ddir, scene, obj, stats, order):
    rows = [v for v in order if v in stats["views"]]
    names = ", ".join(rows)
    hinted = [v for v in rows if stats["views"][v]["hints"]]
    is_sam2 = stats["strategy"] == "sam2-video"
    pass_no = stats.get("pass", 3)
    is_p4 = pass_no == 4
    pass_word = "FOURTH" if is_p4 else "THIRD"
    prev_dir, prev_cap = (("pass3", "pass 3 — superseded (lamp base "
                           "structurally unmasked)") if is_p4 else
                          ("pass2", "pass 2 — REJECTED (crop-zoom + points)"))
    cards = ""
    for name in rows:
        s = stats["views"][name]
        badges = "".join(f'<span class="hint">{h}</span>' for h in s["hints"])
        if not (ddir / "multiview_masks" / f"{name}.png").exists():
            badges += '<span class="hint">mask file deleted — view is dropped</span>'
        p2fig = ""
        if (ddir / "mask_overlays" / prev_dir / f"{name}.png").exists():
            p2fig = (f'<figure><a href="mask_overlays/{prev_dir}/{name}.png">'
                     f'<img src="mask_overlays/{prev_dir}/{name}.png"></a>'
                     f'<figcaption>{prev_cap}</figcaption></figure>')
        extra = (f"propagation order #{s['order_idx']} · {s['mask_source']} · "
                 f"object-score logit {s['object_score_logit']}"
                 if is_sam2 else s.get("selection", ""))
        bc = s.get("base_coverage")
        if bc:
            extra += (f" · base Gaussians in mask {bc['in_mask']}/"
                      f"{bc['in_frame']} "
                      f"({'COVERED' if bc['in_mask'] else 'NOT covered'})")
        if s.get("area_px_pass3"):
            extra += f" · pass-3 area was {s['area_px_pass3']:,} px"
        cards += f"""
<section>
<h2>{name} {badges}</h2>
<div class="row">
 <figure><a href="images/{name}.png"><img src="images/{name}.png"></a>
  <figcaption>original render</figcaption></figure>
 {p2fig}
 <figure><a href="mask_overlays/{name}.png"><img src="mask_overlays/{name}.png"></a>
  <figcaption>pass {pass_no} — SAM2 mask (magenta), prompt-box rect (yellow)</figcaption></figure>
 <figure><a href="multiview_masks/{name}.png"><img src="multiview_masks/{name}.png"></a>
  <figcaption>raw mask (what GaussianCut gets)</figcaption></figure>
</div>
<p class="stats">area {s['area_px']:,} px ({s['area_pct']}% of frame) ·
 inside manifest-box rect {100 * s['inside_prompt_frac']:.1f}% · {extra}<br>
 <i>numbers are hints only — they failed to predict your pass-2 verdict;
 the deciding review is Checkpoint 6 on the cut renders</i></p>
<div class="verdict">Quick glance for <b>{name}</b>: sane ☐ / not sane ☐
 — reply e.g. <code>not sane: {name}</code></div>
</section>"""

    hint_note = (f"<p>Numeric hints raised on: {', '.join(hinted)} "
                 "(area/overlap heuristics — glance harder there first).</p>"
                 if hinted else "<p>No numeric hints raised.</p>")
    ext = stats.get("box_bottom_extension")
    p4driver = ""
    if is_p4 and ext:
        p4driver = (f'<p><b>Why a fourth pass:</b> the graph cut itself '
                    f'diagnosed the pass-3 masks (score_diagnostic.json, '
                    f'region R4): the lamp BASE — 296 Gaussians in the box '
                    f'footprint just below the manifest box bottom — was '
                    f'rendered in the masked views but scored exactly 0.0: '
                    f'structurally unmasked, because every prompt came from '
                    f'the manifest box. One change: the PROMPT box bottom is '
                    f'extended from y {ext["prompt_box_bottom_y_from"]} to '
                    f'y {ext["prompt_box_bottom_y_to"]} '
                    f'({ext["physical_height_m"]} m physical height); '
                    f'top/sides, shade point, ordering, init frame and model '
                    f'are identical to pass 3. Base-probe coverage is '
                    f'reported per view below.</p>')
    html = f"""<!doctype html><meta charset="utf-8">
<title>Checkpoint 5 ({pass_word.lower()} pass, quick glance) — {scene}</title>
<style>
 body{{background:#15171c;color:#dcdfe6;font:14px/1.5 system-ui;margin:20px;max-width:1560px}}
 .banner{{background:#3a1f1f;border:2px solid #c94f4f;border-radius:8px;padding:12px 18px;margin-bottom:16px}}
 .banner h1{{margin:0 0 6px;font-size:20px;color:#ff9c9c}}
 h2{{margin:26px 0 8px;font-size:16px;color:#aeb6c4}}
 .row{{display:flex;flex-wrap:wrap;gap:10px}}
 figure{{margin:0;width:300px}} figure img{{width:300px;display:block;border-radius:4px}}
 figcaption{{font-size:12px;color:#9aa0ac;padding:4px 2px}}
 .stats{{font-size:13px;color:#aeb6c4;margin:6px 0}}
 .hint{{background:#7a6a2f;color:#fff;border-radius:4px;padding:1px 8px;font-size:12px;margin-left:8px}}
 .verdict{{border:1px dashed #6a7080;border-radius:6px;padding:6px 12px;display:inline-block;margin:2px 0 8px}}
 .changed{{background:#1f2a3a;border:1px solid #4f7ac9;border-radius:6px;padding:8px 14px;margin:8px 0}}
 code{{color:#c8d3f5}} b{{color:#e8ebf2}} i{{color:#8b93a3}}
 .foot{{color:#777;font-size:12px;margin-top:28px}}
</style>
<div class="banner"><h1>🔴 WAITING ON YOU — Checkpoint 5, {pass_word} PASS: quick glance only</h1>
<p><b>Route:</b> SAM2 video propagation, per your decision ("go", 2026-07-21).
Passes 1 and 2 (single-image SAM) are rejected history; manual fallback is
BANNED under your standing rule — no manual work in the pipeline, the
pipeline is text to CAD; you only review.</p>
{p4driver}
<div class="changed"><b>How the masks are made:</b> the {len(rows)} views are treated as
a pseudo-video along a smooth camera path
({' → '.join(stats['view_order'])}). SAM2
({stats['model']}) got ONE automatic prompt on the init frame
<b>{stats['init_view']}</b> (the projected manifest box + the shade point) and
propagated the object through all other views with its video memory — no
per-view prompting, no manual input anywhere.</div>
<p><b>This page is a QUICK GLANCE, not a gate:</b> per view, does the magenta
mask look sane on the lamp — yes/no. GaussianCut is designed to refine coarse
masks, so do not judge pixel perfection here. The REAL verdict happens at
Checkpoint 6, on the actual cut renders (before/after of the splat).</p>
{hint_note}
<ol>
 <li>Glance over the {len(rows)} views: {names}.</li>
 <li>Reply "masks sane, go" — or name the insane ones
     (e.g. <code>not sane: cut_c_left</code>); those get dropped from the
     mask set (GaussianCut accepts any subset) and we proceed to the cut.</li>
</ol></div>
{cards}
<p class="foot">{pass_word} PASS · strategy {stats['strategy']} · model
{stats['model']} on {stats['device']} · torch {stats['torch_before']} before /
{stats['torch_after']} after (unchanged) · init {stats['init_view']}, prompt =
{'manifest box with bottom extended to ' + str(ext['physical_height_m']) + ' m'
 if ext else 'manifest box'} + shade point · numeric stats:
{stats['numeric_stats_role']} · generated {stats['generated']} · details in
<code>mask_stats.json</code> (earlier passes archived:
<code>mask_stats_pass1/2{'/3' if is_p4 else ''}.json</code>)</p>
"""
    out = ddir / "mask_review.html"
    out.write_text(html, encoding="utf-8")
    return out


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scene", required=True)
    ap.add_argument("--object", required=True, help="manifest object id, e.g. obj_004")
    ap.add_argument("--strategy", choices=["sam2-video", "crop-points"],
                    default="sam2-video",
                    help="sam2-video = pass 3 (default); crop-points = the "
                         "rejected pass-2 recipe, kept for provenance")
    ap.add_argument("--extend-bottom-to", type=float, default=None,
                    help="PASS 4: extend the PROMPT box bottom down to this "
                         "physical height (m, -y convention), e.g. 0.50; "
                         "prompting only — the manifest is never touched")
    ap.add_argument("--init-view", default="cut_d_lamp",
                    help="sam2-video: propagation init frame")
    ap.add_argument("--sam2-model", default=SAM2_ID)
    ap.add_argument("--views", nargs="*", default=None,
                    help="crop-points only: (re)generate just these views")
    ap.add_argument("--force", action="store_true",
                    help="re-run even where outputs exist")
    ap.add_argument("--margin-frac", type=float, default=0.03,
                    help="prompt-rect margin as a fraction of the frame side")
    ap.add_argument("--crop-factor", type=float, default=2.0,
                    help="crop-points: SAM crop side = factor * rect long side")
    a = ap.parse_args()
    if a.strategy == "sam2-video" and a.views:
        raise SystemExit("--views is incompatible with sam2-video: propagation "
                         "is all-or-nothing (every mask comes from one session)")

    ddir = paths.scene_dir(a.scene) / "cut" / "dataset"
    for sub in ("images", "sidecars"):
        if not (ddir / sub).is_dir():
            raise SystemExit(f"dataset incomplete ({ddir / sub} missing) — run prep_views.py first")

    man = json.loads(paths.manifest(a.scene).read_text())
    if list(man["frame"].get("raw_to_render", [])) != list(R2R):
        raise SystemExit(f"manifest raw_to_render {man['frame'].get('raw_to_render')} "
                         f"!= expected {list(R2R)} — frame contract changed, stop")
    if list(man["frame"].get("up", [])) != [0.0, -1.0, 0.0]:
        raise SystemExit(f"manifest frame.up {man['frame'].get('up')} != [0,-1,0] "
                         f"— shade-point top-plane logic would be wrong, stop")
    obj = next((o for o in man["objects"] if o["id"] == a.object), None)
    if obj is None:
        ids = [o["id"] for o in man["objects"]]
        raise SystemExit(f"{a.object} not in manifest (has: {ids})")
    window = next((o for o in man["objects"]
                   if "window" in o["label"].lower() and o["id"] != a.object), None)
    print(f"target {obj['id']} '{obj['label']}'  aabb {obj['aabb_min']}..{obj['aabb_max']} (RAW)")

    # PASS 4: extended PROMPT box (bottom pulled down to --extend-bottom-to;
    # -y convention, so a lower bottom = larger aabb_max.y). Prompting only.
    prompt_obj = obj
    if a.extend_bottom_to is not None:
        new_y = -a.extend_bottom_to
        if new_y <= obj["aabb_max"][1]:
            raise SystemExit(f"--extend-bottom-to {a.extend_bottom_to} does not "
                             f"extend downward (box bottom y {obj['aabb_max'][1]})")
        prompt_obj = dict(obj)
        prompt_obj["aabb_max"] = [obj["aabb_max"][0], new_y, obj["aabb_max"][2]]
        print(f"prompt box bottom extended: y {obj['aabb_max'][1]} -> {new_y} "
              f"({a.extend_bottom_to} m physical) — cut-diagnostic R4 fix")

    r3 = paths.load_r3()
    order = view_order(ddir)
    shade_raw = shade_point_raw(obj)
    seeing, geo, sidecars = [], {}, {}
    for name in order:
        sc = read_sidecar(ddir, name)
        sidecars[name] = sc
        cam3 = r3.Cam(sc["cam"], sc["look"], sc["up"], sc["fov"], sc["res"], sc["res"])
        cu, cv, in_frame = project_center(cam3, sc, obj["center"])
        if not in_frame:
            continue
        rect = prompt_rect(cam3, sc, prompt_obj, a.margin_frac)
        if rect is None:
            raise SystemExit(f"{name}: object center in frame but box rect "
                             f"degenerate — check the manifest box")
        crop = crop_square(rect, sc["res"], a.crop_factor)
        su, sv, s_in = project_center(cam3, sc, shade_raw)
        pos_uv, pos_kind = ((su, sv), "shade") if s_in else ((cu, cv), "center-fallback")
        win_uv = None
        if window is not None:
            wu, wv, win_in = project_center(cam3, sc, window["center"])
            if win_in:
                win_uv = (wu, wv)
        pos, corners, top, wneg = build_points(rect, pos_uv, win_uv, crop)
        seeing.append(name)
        geo[name] = {"rect": rect, "crop": crop, "res": sc["res"], "pos": pos,
                     "pos_kind": pos_kind, "corners": corners, "top": top,
                     "wneg": wneg}

    vpath = ddir / "verification.json"
    if vpath.exists():
        ver = json.loads(vpath.read_text())
        for row in ver.get("views", []):
            rec = row.get("lamp", {}).get(a.object)
            if rec and rec["in_frame"] != (row["view"] in seeing):
                raise SystemExit(f"{row['view']}: in-frame disagrees with "
                                 f"verification.json — projection drift, stop")
    print(f"views seeing {a.object}: {len(seeing)}/{len(order)} — {seeing}")

    mdir, odir = ddir / "multiview_masks", ddir / "mask_overlays"
    mdir.mkdir(exist_ok=True)
    odir.mkdir(exist_ok=True)
    spath = ddir / "mask_stats.json"
    old = json.loads(spath.read_text()) if spath.exists() else {}
    if old.get("object") not in (None, a.object):
        if not a.force:
            raise SystemExit(f"multiview_masks currently holds {old['object']} "
                             f"masks — pass --force to switch to {a.object}")
        for p in list(mdir.glob("*")) + list(odir.glob("*.png")):
            p.unlink()
        old = {}
        print(f"cleared previous {a.object}-foreign masks (--force)")

    # masks whose stem matches no dataset image would CRASH GaussianCut
    image_stems = {p.stem for p in (ddir / "images").glob("*.png")}
    for p in mdir.glob("*"):
        if p.stem not in image_stems or p.suffix.lower() != ".png":
            p.unlink()
            print(f"removed {p.name} from multiview_masks (matches no camera)")
        elif p.stem not in seeing:
            print(f"WARNING: mask {p.name} is for a view that does not see "
                  f"{a.object} — left in place, review it")

    if a.strategy == "sam2-video":
        if a.init_view not in seeing:
            raise SystemExit(f"init view {a.init_view} does not see {a.object} "
                             f"(valid: {seeing})")
        done = (old.get("strategy") == "sam2-video"
                and old.get("extend_bottom_to") == a.extend_bottom_to
                and set(old.get("views", {})) == set(seeing)
                and all((mdir / f"{v}.png").exists() for v in seeing))
        if done and not a.force:
            print("sam2-video outputs exist — rebuilding review page only "
                  "(--force to re-propagate)")
            stats = old
        else:
            path_order = order_smooth(seeing, sidecars, a.init_view)
            print(f"pseudo-video order: {' -> '.join(path_order)}")
            results, model_id, (t_before, t_after) = run_sam2_video(
                ddir, path_order, a.init_view, geo, a.sam2_model)
            if t_before != t_after:
                raise SystemExit(f"torch changed {t_before} -> {t_after} — "
                                 f"HARD STOP, report this")
            prev = {}
            prev_path = ddir / "mask_stats_pass3.json"
            if a.extend_bottom_to is not None and prev_path.exists():
                prev = {k: v["area_px"] for k, v in
                        json.loads(prev_path.read_text())["views"].items()}
            r4_pts = (r4_gaussians(a.scene, obj)
                      if a.extend_bottom_to is not None else np.empty((0, 3)))
            if len(r4_pts):
                print(f"R4 base region: {len(r4_pts)} Gaussians below the box "
                      f"bottom in the padded footprint (verification target)")
            vstats = {}
            for name in seeing:
                mask, score, src = results[name]
                Image.fromarray(mask.astype(np.uint8) * 255, "L").save(
                    mdir / f"{name}.png")
                g = geo[name]
                img = Image.open(ddir / "images" / f"{name}.png").convert("RGB")
                is_init = name == a.init_view
                write_overlay(
                    img, mask, g["rect"], odir / f"{name}.png",
                    pos=(g["pos"] if is_init else ()),
                    note=f"#{path_order.index(name)} "
                         + ("INIT" if is_init else "propagated"))
                s = mask_stats(mask, g["rect"], g["res"])
                # R4 base coverage: actual base Gaussians inside the mask
                base_cov = None
                if len(r4_pts):
                    sc = sidecars[name]
                    cam3 = r3.Cam(sc["cam"], sc["look"], sc["up"], sc["fov"],
                                  sc["res"], sc["res"])
                    base_cov = base_coverage(r4_pts, cam3, sc, mask)
                    if base_cov["in_mask"] == 0:
                        s["hints"].append("base-not-covered")
                if name in prev and prev[name] > 0 \
                        and s["area_px"] > 3 * prev[name]:
                    s["hints"].append("desk-grab(>3x pass3)")
                s.update({"prompt_mode": MODE_SAM2,
                          "prompt_rect": g["rect"],
                          "order_idx": path_order.index(name),
                          "mask_source": src,
                          "base_coverage": base_cov,
                          "area_px_pass3": prev.get(name),
                          "object_score_logit": (round(score, 3)
                                                 if score is not None else None)})
                vstats[name] = s
                btxt = (f"base {base_cov['in_mask']}/{base_cov['in_frame']}"
                        if base_cov else "base n/a")
                print(f"  {name}: area {s['area_px']:,} px ({s['area_pct']}%)  "
                      f"inside {s['inside_prompt_frac']:.2f}  {btxt}  "
                      f"{src}  hints {s['hints'] or 'none'}", flush=True)
            ext = None
            if a.extend_bottom_to is not None:
                ext = {"prompt_box_bottom_y_from": obj["aabb_max"][1],
                       "prompt_box_bottom_y_to": -a.extend_bottom_to,
                       "physical_height_m": a.extend_bottom_to,
                       "reason": "cut diagnostic R4: lamp base (296 Gaussians "
                                 "below the manifest box bottom) had coarse "
                                 "score 0.0 — structurally unmasked in pass 3"}
            stats = {
                "scene": a.scene, "object": a.object, "label": obj["label"],
                "pass": 4 if a.extend_bottom_to is not None else 3,
                "strategy": "sam2-video", "prompt_mode": MODE_SAM2,
                "model": model_id, "model_requested": a.sam2_model,
                "device": "cuda", "torch_before": t_before,
                "torch_after": t_after,
                "integration": "transformers built-in Sam2Video (no new packages)",
                "view_order": path_order, "init_view": a.init_view,
                "ordering_metric": f"greedy NN, |dpos| + {DIR_WEIGHT}*|dforward|, "
                                   f"name tie-break",
                "init_prompt": {"box": geo[a.init_view]["rect"],
                                "positive_shade": geo[a.init_view]["pos"],
                                "positive_kind": geo[a.init_view]["pos_kind"]},
                "extend_bottom_to": a.extend_bottom_to,
                "box_bottom_extension": ext,
                "margin_frac": a.margin_frac,
                "numeric_stats_role": STATS_ROLE,
                "hint_thresholds": {"tiny_pct": TINY_PCT, "huge_pct": HUGE_PCT,
                                    "inside_min": INSIDE_MIN},
                "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
                "views": vstats}
            spath.write_text(json.dumps(stats, indent=1))
    else:                              # crop-points (pass-2 recipe, provenance)
        targets = seeing if not a.views else [v for v in seeing if v in a.views]
        bad = [] if not a.views else [v for v in a.views if v not in seeing]
        if bad:
            raise SystemExit(f"--views {bad} do not see {a.object} (valid: {seeing})")
        vstats = {k: v for k, v in old.get("views", {}).items()
                  if v.get("prompt_mode") == MODE_CROP}
        todo = [v for v in targets if a.force or not (
            (mdir / f"{v}.png").exists() and v in vstats)]
        print(f"crop-points, to segment: {len(todo)} view(s)")
        if todo:
            torch, sam, proc, device = load_sam()
            for name in todo:
                img = Image.open(ddir / "images" / f"{name}.png").convert("RGB")
                g = geo[name]
                negs = g["corners"] + g["top"] + g["wneg"]
                points = g["pos"] + negs
                labels = [1] * len(g["pos"]) + [0] * len(negs)
                mask, idx, pred_iou, cands, fb = run_sam(
                    torch, sam, proc, device, img, g["rect"], g["crop"],
                    points, labels)
                Image.fromarray(mask.astype(np.uint8) * 255, "L").save(
                    mdir / f"{name}.png")
                write_overlay(img, mask, g["rect"], odir / f"{name}.png",
                              crop=g["crop"], pos=g["pos"], negs=negs)
                s = mask_stats(mask, g["rect"], g["res"])
                if fb:
                    s["hints"].append("no-box-consistent-candidate")
                s.update({"prompt_mode": MODE_CROP, "prompt_rect": g["rect"],
                          "crop": g["crop"],
                          "prompts": {"positive": g["pos"],
                                      "positive_kind": g["pos_kind"],
                                      "negative_corners": g["corners"],
                                      "negative_top_edge": g["top"],
                                      "negative_window": g["wneg"]},
                          "sam_mask_idx": idx,
                          "sam_pred_iou": round(pred_iou, 4),
                          "sam_candidates": cands,
                          "selection": "fallback-least-outside" if fb
                                       else "box-consistent"})
                vstats[name] = s
                print(f"  {name}: area {s['area_px']:,} px  "
                      f"inside {s['inside_prompt_frac']:.2f}  "
                      f"hints {s['hints'] or 'none'}", flush=True)
        vstats = {k: v for k, v in vstats.items() if k in seeing}
        stats = {"scene": a.scene, "object": a.object, "label": obj["label"],
                 "pass": 2, "strategy": "crop-points", "prompt_mode": MODE_CROP,
                 "model": SAM_ID, "device": "cuda",
                 "torch_before": "n/a", "torch_after": "n/a",
                 "view_order": seeing, "init_view": "n/a",
                 "margin_frac": a.margin_frac, "crop_factor": a.crop_factor,
                 "numeric_stats_role": STATS_ROLE,
                 "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
                 "views": vstats}
        spath.write_text(json.dumps(stats, indent=1))

    page = review_page(ddir, a.scene, obj, stats, order)
    vstats = stats["views"]
    print(f"\n{'view':14s} {'area_px':>9s} {'area%':>7s} {'inside':>7s} "
          f"{'base':>7s}  hints")
    for name in (v for v in order if v in vstats):
        s = vstats[name]
        bc = s.get("base_coverage")
        base = f"{bc['in_mask']}/{bc['in_frame']}" if bc else "n/a"
        print(f"{name:14s} {s['area_px']:>9,} {s['area_pct']:>7.3f} "
              f"{s['inside_prompt_frac']:>7.3f} {base:>7s}  "
              f"{', '.join(s['hints']) or '-'}")
    print(f"\nmasks   -> {mdir}")
    print(f"stats   -> {spath}")
    print(f"review  -> {page}")


if __name__ == "__main__":
    main()
