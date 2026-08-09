"""SAME-PRODUCT JUDGE — its own pass in the graph judge chain (USER
RULING 2026-08-06 late: NOT part of the multiplicity judge; a different
question — "same product across separate objects?" vs "one object or
several?").

⚠ STATUS: UNTESTED PROMOTION (cone-map session). Verdicts write a
SIDECAR (graph/same_product.json); nothing consumes it yet. The intended
consumer chain: shopping retrieves ONE asset per SAME_PRODUCT group at
the canonical size. Default is --dry-run-less full mode; use --dry-run
to see groups without any LLM call.

1. CANDIDATE GROUPS (deterministic, scene-agnostic — Rule #1, no class
   lists): same-name resolved nodes, greedy plan-proximity clusters
   (2.5 m), geometric shared-anchor detection (nearest node with >=2x
   footprint area). Sizes prefer the slice-vote carve preview when it
   exists. Carve doubts (graph/carve_doubts.json) ride along as context.
2. CONTACT SHEETS (PLAN_CARVE_DOWNSTREAM.md Phase B upgrade): per group
   one image, graph/same_product_sheets/group_<n>_<label>.png — one row
   per member (id + carved size at left, up to 2 evidence crops resized
   to a uniform 200 px height side by side; crops resolved via the
   judge_pairs.py pattern: resolved node -> source nodes ->
   evidence.members[*].crop under graph/crops/). Plus an index.html.
   Sheets are built in BOTH modes; --dry-run stops after sheets (no LLM
   calls, no same_product.json).
3. VERDICT (one claude.exe call per group, judge-chain pattern): the
   judge OPENS the group's contact sheet (one-look rule — the sheet
   alone answers "do these look like the same product?") plus the size
   facts. Same product? canonical size? Judge may exclude members via
   set_members (a "chair" that is really something else stays out).

⚠ KNOWN OPEN, NOT FIXED HERE (2026-08-08): the ANSWER FORM is unstable
by construction. The judge is asked to name a SUBSET of the group and is
never asked to account for the members it leaves out, and it gets ONE
set slot per group — so a group that is really two products can only be
answered by discarding members. Two runs 20 min apart on near-identical
pillow data returned DISJOINT sets ({obj_024, obj_037} vs {obj_015,
obj_016, obj_026}); both are correct answers to the question as written.
The redesign (assign EVERY member to a set or to "alone", allow more
than one set per group) is the next piece of work — user ruling
2026-08-08: fix the plumbing first, review a sheet, then redesign.

CHAIN ALIGNMENT LANDED 2026-08-08 — J9 was the odd one out on four
mechanical counts, each matched to what J8/J8s already do:
  · VERDICT CACHE (graph/judge_same_product_cache.json, key = prompt +
    contact-sheet bytes). Every other judge had one; J9 re-decided every
    run. This makes a re-run free — it does NOT make the answer right
    (see the open above).
  · MODEL = sonnet (J8/J8s constant). The old default was haiku.
  · NO STIMULUS -> UNCLEAR WITHOUT A CALL. A group whose members have no
    detection crops produced a picture-free sheet and the judge answered
    anyway from the numbers, while the prompt told it to look (living
    group 1, magazine obj_005_c00 + obj_017_c00: pano-cluster nodes,
    evidence.members empty). Members with no photo in a MIXED group are
    now named in the prompt as unseeable and recorded as
    no_photo_members — recorded, not decided.
  · RETRY ONCE, then record. A malformed reply used to be a dead group
    (living group 2, magazine x3: "judge call failed").
  · groups run CONCURRENTLY (the 08-04 parallelism ruling); they were
    strictly sequential.

Run:  python graph/judge_same_product.py --scene living_marble --dry-run
      python graph/judge_same_product.py --scene living_marble
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent.parent
GRAPH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(GRAPH_DIR))   # sibling stage modules (split_cuts)
import paths  # noqa: E402
from carve_cams import make_cam  # noqa: E402  (THE camera math, shared)

# A STAGE MUST NOT DIE ON ITS OWN LOG LINE (2026-08-08): the closing
# "wrote ... (⚠ UNTESTED)" print raised UnicodeEncodeError under a cp1252
# console AFTER same_product.json was already on disk — the work was done
# and the run still exited non-zero. Same latent bug in carve_slicevote.py
# (≥), graph/build_edges.py (→) and compose/uniform_instances.py (⚠).
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                       # noqa: BLE001 — piped/older
        pass

GROUP_RADIUS = 2.5
ANCHOR_AREA_RATIO = 2.0
MODEL = "sonnet"       # the judge-chain constant (J8, J8s). J9 had been
                       # defaulting to haiku — an undocumented outlier, not
                       # a recorded decision (2026-08-08)
CONCURRENCY = 8        # user ruling 08-04: independent calls run concurrently
CALL_TIMEOUT_S = 600   # s — raised from 180 (2026-08-08): image-heavy
                       # contact sheets legitimately run long
CROPS_PER_MEMBER = 2       # judge_pairs.py pattern: up to 2 crops/node
CROP_H = 200               # uniform crop height on the contact sheet
LABEL_W = 260              # left text column (id + carved size)
PAD = 12


def claude_env():
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(k, None)   # stale-API-key hijack gotcha (project memory)
    return env


def call_claude(prompt, model, cwd=None):
    # cwd MUST be the sheets dir when the prompt references image files:
    # claude -p can only Read within its working directory (the J9
    # first-run failure 2026-08-07 — absolute out-tree paths were
    # unreadable and the model replied prose, not JSON; J8 always
    # passed cwd)
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("[same_product] claude.exe not on PATH")
    r = subprocess.run([exe, "-p", prompt, "--model", model],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=claude_env(),
                       cwd=(str(cwd) if cwd else None),
                       timeout=CALL_TIMEOUT_S)
    out = (r.stdout or "").strip()
    if r.returncode != 0:
        raise RuntimeError(f"claude exit {r.returncode}: "
                           f"{(r.stderr or out)[:400]}")
    low = (out + " " + (r.stderr or "")).lower()
    for bad in ("invalid_api_key", "authentication_error",
                "credit balance"):
        if bad in low:
            raise RuntimeError(f"claude auth/billing error: {out[:400]}")
    return out


def parse_json_obj(text):
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    raw = m.group(1) if m else None
    if raw is None:
        i, j = text.find("{"), text.rfind("}")
        raw = text[i:j + 1] if i >= 0 and j > i else None
    return json.loads(raw) if raw else None


def normalize_ids(raw, member_ids):
    """set_members comes back in whatever shape the judge felt like:
    proper ids ('obj_024'), bare ints (29), or numeric strings ('29').
    Normalise to real node ids of THIS group; drop anything that does not
    resolve (recorded by the caller as a shrunken set, never silently
    invented). Consumers — shopping, materialize — need ids, not digits.
    """
    if not raw:
        return None
    by_num = {}
    for mid in member_ids:
        digits = re.sub(r"\D", "", mid)
        if digits:
            by_num.setdefault(str(int(digits)), mid)
    out = []
    for v in raw:
        s = str(v).strip()
        if s in member_ids:
            out.append(s)
            continue
        d = re.sub(r"\D", "", s)
        hit = by_num.get(str(int(d))) if d else None
        if hit and hit not in out:
            out.append(hit)
    return out or None


def parse_assignments(raw, member_ids):
    """The assign-every-member reply -> {id: (set_label, reason)}.

    Ids come back in whatever shape the judge felt like (see
    normalize_ids); set labels are normalised to set_1/set_2/... or
    "alone". Anything that does not resolve to a member of THIS pool is
    dropped, and members the judge never mentioned are returned as
    `missing` — recorded as a defect, never quietly filled in.
    """
    got, seen = {}, []
    for row in (raw or []):
        if not isinstance(row, dict):
            continue
        rid = normalize_ids([row.get("id")], member_ids)
        if not rid or rid[0] in got:
            continue
        s = str(row.get("set") or "").strip().lower().replace(" ", "_")
        if s in ("alone", "none", "null", "", "no", "single"):
            lab = "alone"
        else:
            d = re.sub(r"\D", "", s)
            lab = f"set_{int(d)}" if d else "alone"
        got[rid[0]] = (lab, str(row.get("reason") or "").strip())
        seen.append(rid[0])
    missing = [m for m in member_ids if m not in got]
    return got, missing


def sets_from_assignments(got, members, status_by, doubts_by):
    """Group the per-member assignments into sets, and give each set with
    2+ members its exemplar size. A "set" the judge left with a single
    member is NOT a product set — it is recorded as alone, with the
    judge's own reason kept."""
    by_set = {}
    for mid, (lab, _r) in got.items():
        if lab != "alone":
            by_set.setdefault(lab, []).append(mid)
    sets, alone = [], [m for m, (l, _) in got.items() if l == "alone"]
    for lab in sorted(by_set):
        mem = sorted(by_set[lab])
        if len(mem) < 2:
            alone.extend(mem)          # a set of one is not a set
            continue
        entry = {"set_id": lab, "members": mem,
                 "reasons": {m: got[m][1] for m in mem}}
        sized = canonical_from_exemplar(members, mem, status_by, doubts_by)
        if sized:
            entry.update(sized)
        sets.append(entry)
    return sets, sorted(set(alone))


def plan_center(geo):
    return np.array([(geo["aabb_min"][0] + geo["aabb_max"][0]) / 2,
                     (geo["aabb_min"][2] + geo["aabb_max"][2]) / 2])


def footprint_area(geo):
    return geo["size"][0] * geo["size"][2]


def find_anchor(node, nodes):
    c = plan_center(node["geometry"])
    area = footprint_area(node["geometry"])
    best, best_d = None, 1e9
    for m in nodes:
        if m["id"] == node["id"]:
            continue
        if footprint_area(m["geometry"]) < ANCHOR_AREA_RATIO * area:
            continue
        d = float(np.linalg.norm(plan_center(m["geometry"]) - c))
        if d < best_d:
            best, best_d = m, d
    return (best["id"], best["name"], round(best_d, 2)) if best else None


def member_crop_paths(src_ids, src_nodes, crops_dir):
    """Up to CROPS_PER_MEMBER crops for one pool member, highest det score
    first — the judge_pairs.py node_crops pattern.

    `src_ids` are RECORD node ids (g["nodes"]), already walked down from
    whatever the member is: a settled node's members are RESOLVED ids and
    a resolved node's members are record ids, so a split piece or a merge
    survivor needs two hops, not one. Getting that wrong shows up as a
    silent NO CROPS row, which is why the walk is done by the caller and
    passed in."""
    dets = []
    for sid in src_ids:
        src = src_nodes.get(sid)
        if src:
            dets += src.get("evidence", {}).get("members", [])
    dets.sort(key=lambda m: -m.get("score", 0.0))
    out = []
    for m in dets:
        p = crops_dir / m.get("crop", "")
        if m.get("crop") and p.exists():
            out.append(p)
        if len(out) == CROPS_PER_MEMBER:
            break
    return out


def sheet_font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:          # older Pillow: no size kwarg
        return ImageFont.load_default()


def build_sheet(gr, crops_by_id, out_path):
    """One contact sheet: one row per member — id + carved size in the
    left column, up to 2 crops (uniform CROP_H height) side by side."""
    font = sheet_font(18)
    font_small = sheet_font(15)
    rows = []
    for m in gr["members"]:
        imgs = []
        for p in crops_by_id.get(m["id"], []):
            im = Image.open(p).convert("RGB")
            w = max(1, round(im.width * CROP_H / im.height))
            imgs.append(im.resize((w, CROP_H)))
        rows.append((m, imgs))
    width = LABEL_W + max((sum(im.width for im in imgs)
                           + PAD * len(imgs) for _, imgs in rows),
                          default=0) + PAD
    height = PAD + len(rows) * (CROP_H + PAD)
    sheet = Image.new("RGB", (max(width, LABEL_W + PAD), height),
                      (245, 245, 245))
    draw = ImageDraw.Draw(sheet)
    y = PAD
    for m, imgs in rows:
        draw.text((PAD, y + 4), m["id"], fill=(0, 0, 0), font=font)
        size_txt = "size " + " x ".join(f"{v:.2f}" for v in m["size"]) \
                   + " m"
        draw.text((PAD, y + 30), size_txt, fill=(60, 60, 60),
                  font=font_small)
        if not imgs:
            draw.text((PAD, y + 56), "NO CROPS", fill=(180, 0, 0),
                      font=font_small)
        x = LABEL_W
        for im in imgs:
            sheet.paste(im, (x, y))
            x += im.width + PAD
        y += CROP_H + PAD
    sheet.save(out_path)


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "group"


# ---- the box view: the set's geometry, in a real render ------------------
# USER ASK 2026-08-08: show the size box and the selection boxes ON THE
# SHEET. Projected into an RGB render, never drawn as an abstract plan
# diagram — the standing ruling is that plan views are not useful and 3D
# boxes belong projected into the views (lift-verification ruling).
#
# One top-down render per group, containing only the gaussians in the
# union of the set's boxes, with two things drawn on it:
#   VIOLET  each member's own carved box (thick + named on the exemplar)
#   PINK    the canonical size, drawn at every member's box CENTRE
# so "one size for the whole set" can be read against each real instance.
# Centre-aligned on purpose: no up-axis assumption is made anywhere here
# (this frame is y-down and sign mistakes on up have bitten before).
BOXVIEW_PAD = 0.25           # m — breathing room around the union box
COL_MEMBER = (124, 77, 255)      # violet — matches the viewer's sp_members
COL_CANON = (255, 64, 129)       # pink   — matches the viewer's sp_sizes
COL_EXEMPLAR = (255, 214, 0)     # amber  — the member the size came from


def _union_box(boxes):
    lo = [min(b["aabb_min"][k] for b in boxes) - BOXVIEW_PAD
          for k in range(3)]
    hi = [max(b["aabb_max"][k] for b in boxes) + BOXVIEW_PAD
          for k in range(3)]
    return {"lo": lo, "hi": hi}


def build_box_view(sc_mod, splat, gr, verdict, boxes, out_dir, gi):
    """Render + annotate ONE group's box view. Returns the png name, or
    None when the pieces needed are not on disk (never a crash: the sheet
    degrades to the crops it already had)."""
    from PIL import ImageFont
    picked = [m for m in (verdict.get("set_members") or []) if m in boxes]
    if len(picked) < 1:
        return None
    csize = verdict.get("canonical_size")
    exemplar = verdict.get("canonical_size_from")
    region = _union_box([boxes[m] for m in picked])
    stem = f"boxview_{gi}_{slugify(gr['name'])}"
    png, tgt, n_g = sc_mod.render_region(splat, region, out_dir,
                                         stem + "_raw", gr["name"])
    cam = make_cam(tgt["eye"], tgt["aim"], tgt["fov"], sc_mod.RES)
    img = Image.open(png).convert("RGB")
    dr = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arialbd.ttf", 22)
    except OSError:
        font = sheet_font(22)

    def tag(lo, hi, colour, text, width):
        u, v, z = cam.project(sc_mod.box_corners(lo, hi))
        vis = [(u[k], v[k]) for k in range(8)
               if z[k] > sc_mod.NEAR_Z and 0 <= u[k] < img.width
               and 0 <= v[k] < img.height]
        if not vis or not text:
            return
        tx, ty = min(p[0] for p in vis) + 6, min(p[1] for p in vis) + 4
        tw = dr.textlength(text, font=font)
        dr.rectangle([tx - 4, ty - 2, tx + tw + 4, ty + 26], fill=(0, 0, 0))
        dr.text((tx, ty), text, fill=colour, font=font)

    # the size box first, so a member's own box always draws on top of it
    for mid in picked:
        b = boxes[mid]
        if not csize:
            break
        c = b["center"]
        h = [float(v) / 2 for v in csize]
        lo = [c[k] - h[k] for k in range(3)]
        hi = [c[k] + h[k] for k in range(3)]
        sc_mod.draw_box_wire(dr, cam, lo, hi, COL_CANON, 3, (10, 7))
    for mid in picked:
        b = boxes[mid]
        is_ex = (mid == exemplar)
        col = COL_EXEMPLAR if is_ex else COL_MEMBER
        sc_mod.draw_box_wire(dr, cam, b["aabb_min"], b["aabb_max"], col,
                             5 if is_ex else 3)
        tag(b["aabb_min"], b["aabb_max"], col,
            f"{mid}" + (" — SIZE COMES FROM HERE" if is_ex else ""), 5)

    # legend strip: say what each colour is, in the picture, so the sheet
    # answers in one look without scrolling back to a caption
    lh = 84
    strip = Image.new("RGB", (img.width, img.height + lh), (18, 18, 18))
    strip.paste(img, (0, 0))
    d2 = ImageDraw.Draw(strip)
    y = img.height + 10
    rows = [(COL_EXEMPLAR, f"{exemplar} — the member the size was copied "
                           f"from, its own measured box", False),
            (COL_MEMBER, "the other set members, each its own measured "
                         "box", False),
            (COL_CANON, f"the size being bought {csize} m, drawn at every "
                        f"member's centre", True)]
    for col, text, dash in rows:
        x = 12
        for seg in range(0, 46, 12 if dash else 46):
            d2.line([x + seg, y + 9, x + seg + (7 if dash else 46),
                     y + 9], fill=col, width=4)
        d2.text((70, y), text, fill=(235, 235, 235), font=font)
        y += 24
    out_png = out_dir / f"{stem}.png"
    strip.save(out_png)
    png.unlink(missing_ok=True)
    print(f"[same_product]   box view {out_png.name} — {len(picked)} "
          f"members, {n_g:,} gaussians", flush=True)
    return out_png.name


# ---- the canonical size: CODE'S JOB, not the judge's ---------------------
# USER RULING 2026-08-08: EXEMPLAR, NOT BLEND. The size shopping buys is ONE
# member's measured box, verbatim.
#
# Why the judge stopped deciding this: its canonical_size was, in all four
# living groups, EXACTLY the per-axis median of the members it kept — it was
# doing arithmetic, and we were taking it on trust. Worse, the per-axis
# median is the WRONG arithmetic: the boxes are aligned to the ROOM's axes,
# not to each object, so one member's width is another's depth (pillow
# obj_026 measured 0.494 x 0.257 on the floor while obj_013/015 measured
# ~0.38 x ~0.46 — same product, axes swapped). And when the members simply
# disagree — the chairs' floor extents spread 0.44 m, with two of the five
# already flagged by the carve — a median launders flagged measurements into
# a confident-looking number. So: pick the member we measured best and copy
# its box. Same shape as the settled J8s ruling (the judge speaks the
# vocabulary; code does the snapping).
#
# The rank is computed WITHIN THE GROUP, against its own members, so no
# global list of "bad" doubt kinds is needed and no threshold is introduced:
# a doubt only counts against a member relative to its group-mates. (Every
# ceiling light carries `exemption` — a blanket "no doubts" rule would have
# disqualified all of them and left the group with no exemplar at all.)
NEVER_MEASURED = ("kept", "kept_outlier")   # the carve shipped the ORIGINAL
#                                             box: no measurement was taken


def plan_long_short(size):
    """The two floor dimensions, largest first. Comparable across members;
    raw w and d are not, because the objects face different ways."""
    return max(size[0], size[2]), min(size[0], size[2])


def canonical_from_exemplar(members, picked, status_by, doubts_by):
    """One member's box, verbatim, plus the disagreement it hides.

    Rank: measured before never-measured, then fewest carve doubts, then
    closest to the set's MEDIAN HEIGHT (height is the one axis that is
    directly comparable — every object shares "up"), then id, so the pick
    is deterministic.
    """
    sizes = {m["id"]: m["size"] for m in members}
    chosen = [p for p in picked if p in sizes]
    if not chosen:
        return None
    heights = sorted(sizes[p][1] for p in chosen)
    n = len(heights)
    med_h = (heights[n // 2] if n % 2 else
             (heights[n // 2 - 1] + heights[n // 2]) / 2)

    def rank(mid):
        return (1 if status_by.get(mid) in NEVER_MEASURED else 0,
                len(doubts_by.get(mid, [])),
                abs(sizes[mid][1] - med_h),
                mid)

    ordered = sorted(chosen, key=rank)
    best = ordered[0]
    best_rank = rank(best)[:2]
    eligible = [m for m in ordered if rank(m)[:2] == best_rank]
    ls = [plan_long_short(sizes[p]) for p in chosen]
    spread = lambda v: round(max(v) - min(v), 3)          # noqa: E731
    med = lambda v: round(sorted(v)[len(v) // 2], 3)      # noqa: E731
    return {
        "canonical_size": [round(float(v), 3) for v in sizes[best]],
        "canonical_size_from": best,
        "canonical_size_rule":
            "EXEMPLAR — this member's measured box, verbatim, in its own "
            "world-axis order (w, h, d). No blending: the members' floor "
            "dimensions are not comparable across differently-facing "
            "objects, and averaging a flagged box into the answer hides "
            "that it was flagged.",
        "canonical_size_basis": {
            "n_members": len(members),
            "n_in_set": len(chosen),
            "n_tied_for_exemplar": len(eligible),
            "tied_for_exemplar": eligible,
            "ranked": [{"id": p, "status": status_by.get(p),
                        "doubts": doubts_by.get(p, []),
                        "size": [round(float(v), 3) for v in sizes[p]]}
                       for p in ordered],
            "set_spread_long_m": spread([a for a, _ in ls]),
            "set_spread_short_m": spread([b for _, b in ls]),
            "set_spread_height_m": spread([sizes[p][1] for p in chosen]),
            "set_median_long_short_height": [med([a for a, _ in ls]),
                                             med([sizes[p][1]
                                                  for p in chosen]),
                                             med([b for _, b in ls])],
            "note": "set_spread_* is how much the members of this set "
                    "disagree, after sorting each member's two floor "
                    "dimensions by size. Large spread does NOT invalidate "
                    "the exemplar — it says the set is not a clean "
                    "measurement, and it is recorded so nothing "
                    "downstream mistakes the chairs for the ceiling "
                    "lights."}}


def build_sheets(groups, nodes, crops_dir, sheets_dir):
    """Build every group's contact sheet. Returns {group_index:
    sheet_path} and prints crop coverage; annotates each group dict with
    its sheet filename and per-member crop counts."""
    src_nodes = nodes  # id -> top-level node (crop evidence lives here)
    sheets_dir.mkdir(parents=True, exist_ok=True)
    sheet_paths = {}
    for i, gr in enumerate(groups, 1):
        crops_by_id = {}
        for m in gr["members"]:
            crops_by_id[m["id"]] = member_crop_paths(
                m["_src_ids"], src_nodes, crops_dir)
            m["n_crops"] = len(crops_by_id[m["id"]])
        out_path = sheets_dir / f"group_{i}_{slugify(gr['name'])}.png"
        build_sheet(gr, crops_by_id, out_path)
        gr["sheet"] = out_path.name
        sheet_paths[i] = out_path
        no_crops = [m["id"] for m in gr["members"] if m["n_crops"] == 0]
        cov = ", ".join(f"{m['id']}:{m['n_crops']}"
                        for m in gr["members"])
        print(f"[same_product]   sheet {out_path.name} -- crops {cov}"
              + (f"  WARNING NO CROPS: {no_crops}" if no_crops else ""),
              flush=True)
    return sheet_paths


def _set_card(s, colour="#0a7d28"):
    """One product SET: what to buy, from which member, and how much the
    members disagree."""
    basis = s.get("canonical_size_basis") or {}
    size = s.get("canonical_size")
    src = s.get("canonical_size_from")
    tied = basis.get("n_tied_for_exemplar", 1)
    head = (f'<b style="color:{colour}">{s["set_id"].replace("_", " ")} '
            f'&mdash; {len(s["members"])} of the same product</b>: '
            f'{", ".join(s["members"])}')
    if size and src:
        head += (f'<br><b>buy one at {size} m</b> &mdash; copied verbatim '
                 f'from <b>{src}</b>, the member measured best'
                 + (f' (one of {tied} equally good; height decided it)'
                    if tied > 1 else "")
                 + f'. These {len(s["members"])} disagree by '
                 f'<b>{basis.get("set_spread_long_m")} m</b> on the long '
                 f'floor side, {basis.get("set_spread_short_m")} m on the '
                 f'short one, {basis.get("set_spread_height_m")} m on '
                 f'height. Nothing was averaged.')
    ranked = basis.get("ranked") or []
    if ranked:
        head += ('<br><small>measured, best first: ' + " &middot; ".join(
            f'<b>{r["id"]}</b> {r["size"]} {r.get("status") or ""}'
            + (f' [{", ".join(r["doubts"])}]' if r.get("doubts") else "")
            for r in ranked) + "</small>")
    reasons = s.get("reasons") or {}
    if reasons:
        head += ("<br><small>" + " &middot; ".join(
            f"<b>{m}</b> {r}" for m, r in reasons.items()) + "</small>")
    return (f'<div style="border-left:6px solid {colour};padding:6px 12px;'
            f'margin:8px 0;background:#fafafa">{head}</div>')


def write_index(groups, sheets_dir, verdicts=None):
    """The review page. --dry-run writes the sheets alone; a full run
    writes each pool's outcome above its sheet — every set, every object
    left alone WITH ITS REASON, and the box view per set."""
    rows = []
    for i, gr in enumerate(groups, 1):
        cov = ", ".join(f"{m['id']}:{m.get('n_crops', 0)}"
                        for m in gr["members"])
        no_crops = [m["id"] for m in gr["members"]
                    if not m.get("n_crops")]
        v = (verdicts or {}).get(i) or {}
        body = ""
        reasons = {r["id"]: r.get("reason") or ""
                   for r in (v.get("assignments") or [])}
        for s in v.get("sets") or []:
            body += _set_card(s)
            png = (gr.get("box_views") or {}).get(s["set_id"])
            if png:
                body += (f'<p style="margin:2px 0"><small>'
                         f'{s["set_id"].replace("_", " ")} from above '
                         f'&mdash; amber is the member the size came '
                         f'from, violet the others, dashed pink the size '
                         f'being bought drawn at every member&rsquo;s '
                         f'centre. Centres are aligned, not floors.'
                         f'</small></p>'
                         f'<img src="{png}" style="max-width:100%">')
        alone = v.get("alone") or []
        if alone:
            body += ('<div style="border-left:6px solid #8a5a00;'
                     'padding:6px 12px;margin:8px 0;background:#fafafa">'
                     f'<b style="color:#8a5a00">alone &mdash; {len(alone)}'
                     ' with nothing else here the same product</b><br>'
                     + "<br>".join(f'<b>{m}</b> {reasons.get(m, "")}'
                                   for m in alone) + "</div>")
        if v.get("unassigned"):
            body += ('<div style="border-left:6px solid #a11;padding:6px '
                     '12px;margin:8px 0;background:#fff3f3">'
                     '<b style="color:#a11">UNASSIGNED after a retry '
                     '&mdash; the judge never ruled on '
                     f'{", ".join(v["unassigned"])}</b>. Recorded, not '
                     'guessed.</div>')
        if not (v.get("sets") or alone) and v.get("reason"):
            body += ('<div style="border-left:6px solid #a11;padding:6px '
                     '12px;margin:8px 0;background:#fff3f3">'
                     '<b style="color:#a11">no verdict</b> &mdash; '
                     f'{v["reason"]}</div>')
        if v:
            body += (f'<small>{v.get("model") or "&mdash;"} &middot; '
                     f'{v.get("date") or ""} &middot; '
                     f'{"from cache" if v.get("_cached") else "fresh call"}'
                     + (f' &middot; attempts {v["attempts"]}'
                        if v.get("attempts") else "")
                     + (f' &middot; <b>no photo: '
                        f'{", ".join(v["no_photo_members"])}</b>'
                        if v.get("no_photo_members") else "") + "</small>")
        rows.append(
            f"<h2>{gr['name']} &mdash; every one in the room "
            f"({len(gr['members'])})</h2>" + body
            + f"<p>crops per member: {cov}"
            + (f" &mdash; <b>NO CROPS: {', '.join(no_crops)}</b>"
               if no_crops else "") + "</p>"
            f'<img src="{gr["sheet"]}" style="max-width:100%">')
    (sheets_dir / "index.html").write_text(
        "<!doctype html><meta charset='utf-8'>"
        "<title>same-product contact sheets</title>"
        "<style>body{font:15px/1.5 system-ui,sans-serif;max-width:1100px;"
        "margin:24px auto;padding:0 16px}</style>"
        "<h1>Same-product judge (J9)</h1>"
        "<p>One block per KIND of object, holding <b>every</b> one of "
        "them in the room &mdash; they are not split by where they "
        "stand, because the same lamp can be bought twice and hung at "
        "opposite ends of a room. The judge puts each one in a set with "
        "the others that are the same product, or leaves it alone, and "
        "says why either way. Code then picks which member's measured "
        "box becomes the size to buy.</p>"
        + ("<p><b>Sheets only &mdash; no verdicts in this file.</b></p>"
           if not verdicts else "")
        + "".join(rows), encoding="utf-8")
    print(f"[same_product] wrote {sheets_dir / 'index.html'}", flush=True)


def anchors_from_edges(edges, nodes_by_id):
    """What each node is RECORDED as attached to / resting in — read off
    the graph's own edges, not guessed from footprint areas.

    The old find_anchor (nearest node with >=2x the footprint) returned
    NOTHING for the chairs, the pillows and both light groups — the three
    cases that mattered — while the edge layer has the answer written
    down: every ceiling light is ATTACHED to arch_ceiling, every pillow is
    IN the sofa. Generic floor contact is dropped: "stands on the floor"
    is true of half the room and is not context.

    CONTEXT ONLY. This never groups anything (that was the bug) — it is a
    line in the prompt so the judge knows four of these stand at one desk.
    """
    KINDS = ("ATTACHED", "IN", "ON", "IN_WALL", "INTERPENETRATES")
    GENERIC = ("arch_floor",)
    out = {}
    for e in edges or []:
        t, a, b = e.get("type"), e.get("a"), e.get("b")
        if t not in KINDS or b in GENERIC or a == b:
            continue
        nm = (nodes_by_id.get(b) or {}).get("name") or b
        out.setdefault(a, []).append((t, b, nm))
    return out


def pick(table, node):
    """Look a per-object record up for a pool member.

    Everything J6 and the carve recorded is keyed by PRE-SETTLEMENT ids,
    and a settled node may be a split piece (obj_011#1) or a merge
    survivor that swallowed another node. So: try the node's own id, then
    the id it came from, then anything it absorbed. Returns the first
    hit — never merges two objects' records into one."""
    for key in ([node["id"], node.get("_origin")]
                + list(node.get("_merged") or [])
                + list(node.get("members") or [])):
        if key and key in table:
            return table[key]
    return None


def candidate_pools(nodes, carved, appearance, anchors):
    """ONE POOL PER KIND — every node of that name in the scene.

    USER RULING 2026-08-08: grouping must be SEMANTIC, and product
    identity is a different question from physical arrangement. The old
    rule split each name into plan-proximity clusters (GROUP_RADIUS
    2.5 m), which DECIDED identity before the judge ever spoke:
      · the room's 7 ceiling lights fell into a 4 and a 3 because the
        nearest pair across the two patches is 2.74 m. The judge then
        described BOTH groups as "oval flush-mount ceiling lights" and
        returned exemplars agreeing to 4 mm — two purchases for one
        product;
      · worse, bookshelf x3, door x2, sofa x2 and plant x2 never reached
        the docket AT ALL, because no two of them were within 2.5 m.
    Distance is a fair proxy for "is this a matched set around one table".
    It is a poor proxy for "is this the same product": the same lamp
    bought twice can be at opposite ends of a room.

    Physical arrangement (the role layer — "these four are at the desk")
    now rides in as CONTEXT via `anchors`, and never partitions the pool.
    """
    by_name = {}
    for n in nodes:
        by_name.setdefault(n["name"], []).append(n)
    pools = []
    for name, members in sorted(by_name.items()):
        if len(members) < 2:
            continue
        pools.append({
            "name": name,
            "members": [{
                "id": m["id"],
                "size": carved.get(m["id"], m["geometry"]["size"]),
                "center": [round(float(v), 2)
                           for v in m["geometry"]["center"]],
                "appearance": pick(appearance, m) or {},
                "anchors": pick(anchors, m) or [],
                "_src_ids": m["_src_ids"],   # crop walk; not serialized
                "_origin": m.get("_origin")}
                for m in sorted(members, key=lambda x: x["id"])]})
    return pools


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--concurrency", type=int, default=CONCURRENCY)
    ap.add_argument("--no-box-views", action="store_true",
                    help="skip the per-group top renders (they go "
                         "through WSL and take the longest)")
    ap.add_argument("--no-cache", action="store_true",
                    help="ignore cached verdicts (re-ask every group) — "
                         "the stability probe")
    a = ap.parse_args()
    sd = paths.scene_dir(a.scene)
    g = json.loads((sd / "scene_graph.json").read_text(encoding="utf-8"))

    # JUDGE THE SETTLED LAYER, NOT THE RAW CARVE (user ruling 2026-08-08).
    # graph['carved'] is the node set and the boxes AFTER J8's box
    # rulings, J8s's splits and J1's merges. Reading the carve manifest
    # instead meant judging geometry those verdicts had already replaced —
    # on living run 17, obj_011 was still the uncut 2.80 m L, obj_020 had
    # been merged away and was nonetheless a set's EXEMPLAR, and obj_021's
    # box had been swapped. Build it with:
    #     graph/materialize_carve.py --scene <s> --settle-only --apply
    # Fallback (no settled layer yet): the resolved nodes + carve manifest,
    # the old behaviour, announced so it is never a silent downgrade.
    # a resolved node's members are RECORD ids — the second hop the crop
    # walk needs when a pool member is a split piece or a merge survivor
    res_src = {n["id"]: (n.get("members") or [n["id"]])
               for n in g["resolved"]["nodes"]}

    def src_ids(resolved_ids):
        out = []
        for r in resolved_ids:
            for s in res_src.get(r, [r]):
                if s not in out:
                    out.append(s)
        return out

    cv = g.get("carved") or {}
    settled = [n for n in (cv.get("nodes") or []) if n.get("geometry")]
    carved = {}
    if settled:
        nodes = []
        for n in settled:
            mem = n.get("members") or [n["id"]]
            merged = (n.get("merged_members")
                      or n.get("merged_from") or [])
            nodes.append({
                "id": n["id"], "name": n.get("name") or "",
                "geometry": n["geometry"], "members": mem,
                "_origin": (n.get("split_from")
                            or (n["id"] if n["id"] in res_src
                                else (mem[0] if mem else n["id"]))),
                "_merged": list(merged),
                "_src_ids": src_ids(list(mem) + list(merged))})
        carved = {n["id"]: n["geometry"]["size"] for n in nodes}
        print(f"[same_product] geometry = graph['carved'] (SETTLED): "
              f"{len(nodes)} nodes, built {cv.get('built')}", flush=True)
    else:
        nodes = [{**n, "_origin": n["id"], "_merged": [],
                  "_src_ids": src_ids([n["id"]])}
                 for n in g["resolved"]["nodes"]]
        prev = sd / "scene_manifest_slicevote_preview.json"
        if prev.exists():
            for o in json.loads(prev.read_text())["objects"]:
                carved[o["id"]] = o["size"]
        print("[same_product] ⚠ no graph['carved'] — falling back to the "
              "RAW carve manifest, which J8/J8s/J1 may have superseded. "
              "Run materialize_carve.py --settle-only --apply first.",
              flush=True)
    doubts = {}
    df = sd / "graph" / "carve_doubts.json"
    if df.exists():
        for nd in json.loads(df.read_text())["nodes"]:
            doubts[nd["id"]] = [d["kind"] for d in nd["doubts"]]

    # the carve's own record is keyed by PRE-SETTLEMENT ids; re-key it onto
    # the node set actually being judged, so a split piece or a merge
    # survivor still carries the doubts and the status of what it came
    # from. Without this every settled piece looks doubt-free, which would
    # quietly make it eligible to become the size exemplar.
    status_src = {}
    cnodes = (g.get("carve") or {}).get("nodes") or {}
    if isinstance(cnodes, dict):
        for nid, c in cnodes.items():
            if isinstance(c, dict):
                status_src[nid] = c.get("status")
    doubts = {n["id"]: (pick(doubts, n) or []) for n in nodes}
    status_by = {n["id"]: pick(status_src, n) for n in nodes}

    # the J6 descriptions (graph/describe_nodes.py) — written from the
    # crops and keyed by an EVIDENCE hash, so carve re-runs do not stale
    # them; J6's appearance phase is geometry-blind by design
    appearance = {}
    apf = sd / "graph" / "appearance_cache_v2.json"
    if apf.exists():
        for nid, ent in (json.loads(apf.read_text(encoding="utf-8"))
                         .get("nodes") or {}).items():
            if isinstance(ent, dict) and ent.get("appearance"):
                appearance[nid] = ent["appearance"]
    # the recorded relations (post-carve layer when it exists)
    edges = ((g.get("carved_edges") or {}).get("edges")
             or g.get("edges") or [])
    anchors = anchors_from_edges(edges, {n["id"]: n for n in nodes})

    groups = candidate_pools(nodes, carved, appearance, anchors)
    print(f"[same_product] {len(groups)} pool(s) — ONE PER KIND, whole "
          f"scene, no distance rule", flush=True)
    for gr in groups:
        have = sum(1 for m in gr["members"] if m.get("appearance"))
        print(f"[same_product]   {gr['name']}: "
              f"{[m['id'] for m in gr['members']]} "
              f"({have}/{len(gr['members'])} described)", flush=True)

    src_nodes = {n["id"]: n for n in g["nodes"]}  # crop evidence here
    crops_dir = sd / "graph" / "crops"
    sheets_dir = sd / "graph" / "same_product_sheets"
    sheet_paths = build_sheets(groups, src_nodes, crops_dir, sheets_dir)

    if a.dry_run:
        write_index(groups, sheets_dir)
        print("[same_product] dry run — sheets built, no LLM calls, "
              "no same_product.json", flush=True)
        return

    cache_f = sd / "graph" / "judge_same_product_cache.json"
    cache = (json.loads(cache_f.read_text(encoding="utf-8"))
             if cache_f.exists() and not a.no_cache else {})

    def build_prompt(gi, gr):
        lines = []
        for m in gr["members"]:
            dstr = (f"\n      carve doubts: {', '.join(doubts[m['id']])}"
                    if m["id"] in doubts else "")
            ap = m.get("appearance") or {}
            desc = ap.get("description")
            bits = []
            if ap.get("colors"):
                bits.append("colours " + "/".join(ap["colors"]))
            if ap.get("material"):
                bits.append("material " + str(ap["material"]))
            if ap.get("style"):
                bits.append("style " + str(ap["style"]))
            anc = ", ".join(f"{t.lower()} {nm}"
                            for t, _b, nm in (m.get("anchors") or [])[:3])
            lines.append(
                f"  {m['id']}: size {m['size']} m (w x h x d)"
                + ("" if m.get("n_crops") else "   [NO PHOTO — its row "
                                               "of the sheet is empty]")
                + (f"\n      described earlier as: \"{desc}\""
                   if desc else "")
                + (f"\n      {'; '.join(bits)}" if bits else "")
                + (f"\n      in the room: {anc}" if anc else "") + dstr)
        blind = [m["id"] for m in gr["members"] if not m.get("n_crops")]
        n = len(gr["members"])
        return (
            "You are judging object instances found in ONE real room by a "
            "noisy 3D reconstruction pipeline. The question is SHOPPING: "
            "each distinct product has to be bought once, so we need to "
            "know which of these are literally the same product.\n"
            f"First open the contact sheet image "
            f"{Path(sheet_paths[gi]).name} (in your working directory) — "
            "each row is one member's photos, with its id and measured "
            "size printed at the left of the row.\n\n"
            f"Here are ALL {n} objects in this room named \"{gr['name']}\""
            ". They are NOT pre-sorted — some may be the same product, "
            "some may be a second product of the same kind, and some may "
            "be neither (a mis-detection, or a duplicate of another "
            "one).\n" + "\n".join(lines)
            + (f"\n\nNOTE — no photograph exists for {', '.join(blind)}. "
               "You cannot see "
               + ("it" if len(blind) == 1 else "them")
               + ", so leave "
               + ("it" if len(blind) == 1 else "them")
               + " alone and say why, rather than deciding from the "
                 "numbers.\n" if blind else "")
            + "\n\nJudge from what the objects LOOK like — the photos "
            "first, the earlier descriptions second. Measured sizes vary "
            "a lot because reconstruction is noisy, so a size difference "
            "is weak evidence and a LOOK difference is strong evidence. "
            "Being far apart in the room is NOT evidence against the same "
            "product: the same lamp can be bought twice and hung at "
            "opposite ends of a room.\n\n"
            "ASSIGN EVERY OBJECT. Give each id exactly one of:\n"
            "  \"set_1\", \"set_2\", ... — this object is the same "
            "product as the others in that set (a set needs at least 2 "
            "members; use set_2 only if there is genuinely a SECOND "
            "distinct product here)\n"
            "  \"alone\" — nothing else here is the same product as this "
            "one, or you cannot tell\n"
            f"All {n} ids must appear exactly once. Every one gets its "
            "own short reason — the objects you leave alone matter as "
            "much as the ones you group, because nothing downstream "
            "learns why unless you say it.\n"
            "Answer STRICT JSON only:\n"
            "{\"assignments\": [{\"id\": \"obj_000\", \"set\": \"set_1\" "
            "or \"alone\", \"reason\": \"one short sentence\"}, ...]}")

    def group_key(gi, prompt):
        h = hashlib.sha256()
        h.update(prompt.encode())
        h.update(Path(sheet_paths[gi]).read_bytes())
        return h.hexdigest()[:24]

    def run_group(item):
        gi, gr = item
        blind = [m["id"] for m in gr["members"] if not m.get("n_crops")]
        # NO STIMULUS -> NO CALL (the J8 rule). A sheet with no photo on
        # ANY row cannot answer a question about what things look like;
        # answering from the numbers is what produced the living-room
        # magazine verdict on an empty picture.
        ids = [m["id"] for m in gr["members"]]
        if len(blind) == len(ids):
            return gi, {"assignments": None, "no_photo_members": blind,
                        "reason": "no photos on the contact sheet — every "
                                  "row is empty, so there is nothing to "
                                  "look at (not asked)",
                        "model": None, "date": date.today().isoformat(),
                        "attempts": 0, "_cached": False}
        prompt = build_prompt(gi, gr)
        k = group_key(gi, prompt)
        if k in cache:
            return gi, {**cache[k], "_cached": True}

        # A call failure is a failed ATTEMPT, never a crash and never a
        # dead group: retry once telling it to reply with JSON only, then
        # record the failure (the J8 pattern).
        def attempt(p):
            try:
                v = parse_json_obj(call_claude(
                    p, a.model, cwd=Path(sheet_paths[gi]).parent))
                if v is None:
                    raise ValueError("no JSON in judge output")
                return v, None
            except Exception as e:              # noqa: BLE001
                return None, f"{type(e).__name__}: {str(e)[:160]}"

        v, err = attempt(prompt)
        tries = 1
        got_a, missing = (parse_assignments(v.get("assignments"), ids)
                          if v else ({}, ids))
        # AN INCOMPLETE ANSWER IS A FAILED ATTEMPT. The whole point of the
        # form is that nothing is silently left out, so a reply that skips
        # members gets ONE retry that names them — then whatever is still
        # missing is recorded as `unassigned`, never invented.
        if v is None or missing:
            extra = ("\n\nREPLY WITH THE JSON OBJECT ONLY." if v is None
                     else "\n\nYou did not assign these ids: "
                          + ", ".join(missing)
                          + ". Reply again with the FULL list — every id "
                            "exactly once, each with its own reason.")
            v2, err2 = attempt(prompt + extra)
            tries = 2
            if v2 is not None:
                g2, m2 = parse_assignments(v2.get("assignments"), ids)
                if len(g2) > len(got_a):
                    v, got_a, missing = v2, g2, m2
            err = err2 if v is None else err
        v = v if isinstance(v, dict) else {}
        v = {"assignments": [{"id": i, "set": got_a[i][0],
                              "reason": got_a[i][1]}
                             for i in ids if i in got_a],
             "unassigned": missing,
             "reason": (f"judge call failed x{tries} — {err}"
                        if not got_a else
                        (f"{len(missing)} of {len(ids)} left unassigned "
                         f"after a retry" if missing else "")),
             "model": a.model, "date": date.today().isoformat(),
             "attempts": tries}
        if blind:
            v["no_photo_members"] = blind
        cache[k] = v
        return gi, {**v, "_cached": False}

    print(f"[same_product] judging {len(groups)} group(s), model "
          f"{a.model}, concurrency {a.concurrency}"
          + (" (cache ignored)" if a.no_cache else ""), flush=True)
    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        got = dict(ex.map(run_group, list(enumerate(groups, 1))))

    cache_f.write_text(json.dumps(cache, indent=1), encoding="utf-8")

    # THE SIZE IS CODE'S JOB, computed here from the judge's assignment.
    # (status_by / doubts were re-keyed onto the settled node set above.)
    pools = []
    for gi, gr in enumerate(groups, 1):
        verdict = dict(got[gi])
        assign = {r["id"]: (r["set"], r.get("reason") or "")
                  for r in (verdict.get("assignments") or [])}
        sets, alone = sets_from_assignments(assign, gr["members"],
                                            status_by, doubts)
        verdict["sets"] = sets
        verdict["alone"] = alone
        got[gi] = verdict
        pools.append({
            "name": gr["name"],
            "members": [{k: v for k, v in m.items()
                         if k not in ("_res_node", "appearance")}
                        for m in gr["members"]],
            "sheet": gr.get("sheet"),
            **{k: v for k, v in verdict.items() if k != "_cached"}})
        if verdict.get("unassigned"):
            print(f"[same_product]   ⚠ {gr['name']}: UNASSIGNED "
                  f"{verdict['unassigned']}", flush=True)
        for s in sets:
            print(f"[same_product]   {gr['name']} {s['set_id']}: "
                  f"{s['members']} size={s.get('canonical_size')} from "
                  f"{s.get('canonical_size_from')} "
                  f"{'(cache)' if verdict.get('_cached') else ''}",
                  flush=True)
        if alone:
            print(f"[same_product]   {gr['name']} alone: {alone}",
                  flush=True)
        if not sets and not alone:
            print(f"[same_product]   {gr['name']}: no verdict — "
                  f"{verdict.get('reason')}", flush=True)

    # LEGACY VIEW — one entry per SET, in the shape consumers already
    # read (same_object / set_members / canonical_size). Emitted so
    # materialize_carve.py rule 5 keeps working unchanged; `pools` above
    # is the full record, including every member left alone and why.
    results = []
    for p in pools:
        for s in p.get("sets") or []:
            results.append({
                "name": p["name"], "set_id": s["set_id"],
                "members": [m for m in p["members"]
                            if m["id"] in s["members"]],
                "same_object": True,
                "set_members": s["members"],
                "reason": "; ".join(f"{m}: {r}" for m, r
                                    in (s.get("reasons") or {}).items()),
                **{k: v for k, v in s.items()
                   if k.startswith("canonical_size")},
                "model": p.get("model"), "date": p.get("date")})

    # BOX VIEWS — the set's geometry projected into a real top render, one
    # per group (user ask 08-08: show the size box and the selection boxes
    # ON THE SHEET). Optional and non-fatal: the renderer runs through WSL,
    # and a sheet without them is still a sheet.
    if not a.no_box_views:
        ply = sd / "gen_raw.ply"
        # boxes come from THE SAME geometry the verdicts were made on —
        # the settled layer when there is one. Reading the carve manifest
        # here would silently drop every node the judges created (the
        # split piece obj_011#1 is not in it), and drawing a set minus
        # one of its members is exactly the stale picture that started
        # this.
        boxes = {n["id"]: {"aabb_min": n["geometry"]["aabb_min"],
                           "aabb_max": n["geometry"]["aabb_max"],
                           "center": n["geometry"]["center"],
                           "size": n["geometry"]["size"]}
                 for n in nodes}
        if boxes and ply.exists():
            try:
                import split_cuts as sc_mod
                splat = sc_mod.Splat(ply)
                for gi, gr in enumerate(groups, 1):
                    gr["box_views"] = {}
                    for s in got[gi].get("sets") or []:
                        if not s.get("canonical_size"):
                            continue
                        v = {"set_members": s["members"],
                             "canonical_size": s["canonical_size"],
                             "canonical_size_from":
                                 s.get("canonical_size_from")}
                        try:
                            gr["box_views"][s["set_id"]] = build_box_view(
                                sc_mod, splat, gr, v, boxes, sheets_dir,
                                f"{gi}{s['set_id'].replace('set_', '')}")
                        except Exception as e:      # noqa: BLE001
                            print(f"[same_product]   box view "
                                  f"{gr['name']}/{s['set_id']} failed: "
                                  f"{type(e).__name__}: {str(e)[:200]}",
                                  flush=True)
            except Exception as e:                  # noqa: BLE001
                print(f"[same_product] box views unavailable: "
                      f"{type(e).__name__}: {str(e)[:200]}", flush=True)
        else:
            print("[same_product] box views skipped — need node geometry "
                  "+ gen_raw.ply", flush=True)

    for p, gr in zip(pools, groups):
        p["box_views"] = gr.get("box_views") or {}
    write_index(groups, sheets_dir, got)
    outd = sd / "graph"
    outd.mkdir(exist_ok=True)
    out = outd / "same_product.json"
    out.write_text(json.dumps(
        {"scene": a.scene, "status": "UNTESTED",
         "form": "assign-every-member v2 (2026-08-08): ONE POOL PER KIND "
                 "(whole scene, no distance rule), the judge assigns "
                 "EVERY member to a set or to `alone` with its own "
                 "reason, more than one set per pool allowed, and the "
                 "canonical size is an EXEMPLAR chosen by code.",
         "source": "graph/judge_same_product.py — SAME-PRODUCT pass "
                   "(own judge-chain pass per user ruling 2026-08-06); "
                   "consumer (shopping) NOT wired",
         "reading_this_file": "`pools` is the record — every member of "
                              "every kind, with where it landed and why. "
                              "`groups` is a derived view, one entry per "
                              "SET in the shape older consumers read "
                              "(same_object / set_members / "
                              "canonical_size).",
         "pools": pools,
         "groups": results}, indent=1, ensure_ascii=False),
        # EXPLICIT utf-8: ensure_ascii=False writes the judges' em-dashes
        # as real characters, and write_text() would otherwise encode them
        # through the Windows locale codepage and produce a file nothing
        # downstream can read back (hit immediately, 2026-08-08).
        encoding="utf-8")
    print(f"[same_product] wrote {out} (⚠ UNTESTED)", flush=True)
    print(f"[same_product] cache: {cache_f}", flush=True)


if __name__ == "__main__":
    main()
