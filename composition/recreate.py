"""Recreate mode: rebuild the ENTIRE neural-gen scene from library assets.

The lifted manifest is the layout ("pick object after layout"): every object
box becomes one or more asset instances. Per box:
  1. numeric fit search over configurations — single asset, 90-deg swap, or
     k=2..3 tiling along the box's long horizontal axis (two shelves end to
     end, several small pictures instead of one big one) — scored by
     aspect-ratio distance + label/description token match;
  2. the surrogate agent picks style within the winning configuration's
     shortlist (scene prompt + object label + asset descriptions).

Writes package/recreate_assets.json and package/composed_state.json (flat
instance list: tiled boxes = several instances sharing a group id) — place.py
and jiggle.py consume it unchanged.
"""
import json

import numpy as np

import comp_paths
from comp_paths import paths
from bridge import call_agent_json
from retrieve import catalog, size_score, _tokens

WALL_LABELS = {"window", "door", "curtain", "picture"}
SHORTLIST = 15
TILE_PENALTY = 0.25          # per extra instance, favors single assets when close
MAX_TILES = 3
MIN_CONF = 0.35              # skip the noisiest lifted boxes


def _sub_boxes(center, size, axis, k):
    """Split a box into k equal boxes along one horizontal axis (0=x, 2=z)."""
    step = size[axis] / k
    subs = []
    for i in range(k):
        c = list(center)
        c[axis] = center[axis] - size[axis] / 2 + (i + 0.5) * step
        s = list(size)
        s[axis] = step
        subs.append((c, s))
    return subs


def _config_score(box_size, a, k):
    """Fit score for k copies of asset a tiled along the long axis (lower=better)."""
    s = list(box_size)
    axis = 0 if s[0] >= s[2] else 2
    s[axis] /= k
    return size_score(s, a["size"]) + TILE_PENALTY * (k - 1), axis


def best_configuration(o):
    """-> (k, axis, shortlist) for object box o over the whole catalog."""
    toks = _tokens(o["label"])
    mount = "wall" if o["label"] in WALL_LABELS else "floor"
    rows = []
    for a in catalog():
        if mount == "wall" and not a.get("onWall"):
            continue
        if mount == "floor" and not (a.get("onFloor") or a.get("onObject")):
            continue
        overlap = (len(toks & a["_cat_toks"]) * 2
                   + len(toks & a["_desc_toks"]))
        if overlap == 0:
            continue
        for k in range(1, MAX_TILES + 1):
            fit, axis = _config_score(o["size"], a, k)
            rows.append((fit - 0.6 * overlap, k, axis, a))
    if not rows:  # dims-only fallback for labels with no lexical match
        for a in catalog():
            fit, axis = _config_score(o["size"], a, 1)
            rows.append((fit, 1, axis, a))
    rows.sort(key=lambda r: r[0])
    k, axis = rows[0][1], rows[0][2]
    short = [a for _, kk, _, a in rows if kk == k][:SHORTLIST]
    return k, axis, short


def _pick_prompt(o, k, cands, scene_prompt):
    lines = "\n".join(
        f'- uid {a["uid"]} | {a["category"]} | {a["size"][0]}x{a["size"][1]}x{a["size"][2]} cm | {a["description"][:140]}'
        for a in cands)
    tiling = (f" The box will be filled with {k} copies of the chosen asset "
              f"side by side (none fit it whole)." if k > 1 else "")
    return f"""You are recreating a generated 3D scene with real library assets. Pick the
asset that best matches this object from the original scene.

Scene style/description: {scene_prompt[:600]}

Object to recreate: label = {o['label']}, box size (m, WxHxD) = {[round(v, 2) for v in o['size']]}.{tiling}

Candidates (uid | category | size | description):
{lines}

Match the object type and the scene's style first, then shape (assets are
rescaled). Reply with ONLY a JSON object: {{"uid": "<uid>", "why": "one line"}}"""


def _mount(o, floor_y, sy):
    """wall labels -> wall; box bottom near the floor -> floor (snap);
    else free (elevated items like pillows/shelf contents stay at box y)."""
    if o["label"] in WALL_LABELS:
        return "wall"
    ys = (o["aabb_min"][1], o["aabb_max"][1])
    bottom_elev = min(sy * (y - floor_y) for y in ys)
    return "floor" if bottom_elev < 0.25 else "free"


def run(sc, model="sonnet"):
    pkg = paths.package_dir(sc)
    man = json.loads(paths.manifest(sc).read_text())
    fr = man["frame"]
    sy = fr.get("raw_to_render", [1, 1, 1])[1]
    pf = comp_paths.scene_prompt_file(sc)
    scene_prompt = pf.read_text(encoding="utf-8").strip() if pf else ""
    picked, instances = [], []
    objs = [o for o in man["objects"] if o["score"] >= MIN_CONF]
    print(f"[recreate] {len(objs)}/{len(man['objects'])} boxes (conf >= {MIN_CONF})",
          flush=True)
    for o in objs:
        k, axis, cands = best_configuration(o)
        by_uid = {a["uid"]: a for a in cands}
        def _val(r, _by=by_uid):
            if r.get("uid") not in _by:
                raise ValueError(f"uid must be one of the listed candidates")
        pick = call_agent_json(_pick_prompt(o, k, cands, scene_prompt),
                               validate=_val, model=model,
                               tag=f"recreate_{o['id']}")
        a = by_uid[pick["uid"]]
        mount = _mount(o, fr["floor_y"], sy)
        picked.append({"id": o["id"], "label": o["label"], "uid": a["uid"],
                       "k": k, "category": a["category"],
                       "description": a["description"],
                       "asset_size_cm": a["size"], "box_size_m": o["size"],
                       "why": pick.get("why", "")})
        for i, (c, s) in enumerate(_sub_boxes(o["center"], o["size"], axis, k)):
            instances.append({"label": o["label"], "group": o["id"], "part": i,
                              "uid": a["uid"], "center": c, "size": s,
                              "yaw_deg": 0, "mount": mount})
        tile = f" x{k}" if k > 1 else ""
        print(f"[recreate] {o['id']} {o['label']:16s} -> {a['category']}{tile} "
              f"({a['uid'][:8]}): {a['description'][:70]}", flush=True)
    (pkg / "recreate_assets.json").write_text(json.dumps(picked, indent=1))
    (pkg / "composed_state.json").write_text(json.dumps(
        {"scene": sc, "mode": "recreate", "round": 0, "objects": instances},
        indent=1))
    return instances


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    args = ap.parse_args()
    run(args.scene)
