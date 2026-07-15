"""Stage 2: objathor retrieval per verified placement — description AND
dimension match, "pick object after layout": the box dims exist first, assets
are filtered to fit them.

Pipeline per placement: numeric shortlist (mount flag + size-aspect score +
label/description token overlap) -> surrogate agent ranks the shortlist
against the placement's label/reason + scene style -> composed_assets.json.
Swap points: shortlist scoring (e.g. CLIP later), ranking (e.g. thumbnails).
"""
import gzip
import json
import re

import numpy as np

from comp_paths import ANNOTATIONS, paths
from bridge import call_agent_json

SHORTLIST = 20
_CATALOG = None


def catalog():
    global _CATALOG
    if _CATALOG is None:
        ann = json.load(gzip.open(ANNOTATIONS, "rt", encoding="utf-8"))
        _CATALOG = [v for v in ann.values()
                    if v.get("size") and v.get("description")]
        for a in _CATALOG:  # tokenize once; shortlist scans run per box
            a["_cat_toks"] = _tokens(a["category"])
            a["_desc_toks"] = a["_cat_toks"] | _tokens(a.get("description", ""))
            # y-up gate: the annotation "size" is z-up ordered for ~72% of the
            # catalog (and inconsistent for the rest) — measured 2026-07-14
            # against the THOR mesh bboxes. The bbox itself is y-up and
            # real-scale by construction, so it approximates the asset's
            # dimensions; everything downstream uses size_yup_cm, never raw
            # "size". Truly measured mesh extents (measure.py cache) override
            # below — the metadata bbox itself lies for a fat minority (open
            # window shutters: bbox z=14cm, mesh z=54cm).
            bb = ((a.get("thor_metadata") or {}).get("assetMetadata")
                  or {}).get("boundingBox")
            if bb:
                a["size_yup_cm"] = [round((bb["max"][k] - bb["min"][k]) * 100)
                                    for k in ("x", "y", "z")]
            else:
                s = a["size"]
                a["size_yup_cm"] = ([s[0], s[2], s[1]] if isinstance(s, list)
                                    and len(s) == 3 else s)
        try:
            from measure import load_cache
            measured = load_cache()
            n = 0
            for a in _CATALOG:
                m = measured.get(a["uid"])
                if m:
                    a["size_yup_cm"] = m
                    n += 1
            if n:
                print(f"[retrieve] {n} sizes from measured-mesh cache", flush=True)
        except Exception as e:
            print(f"[retrieve] measured-size cache unavailable ({e})", flush=True)
        print(f"[retrieve] catalog: {len(_CATALOG)} annotated assets", flush=True)
    return _CATALOG


def _tokens(s):
    return set(re.findall(r"[a-z]+", s.lower()))


def size_score(box_m, size_cm):
    """Aspect-ratio distance after normalizing overall scale (we rescale on
    placement, so only shape matters). Lower = better."""
    a = np.sort(np.asarray(box_m, float).ravel())
    b = np.sort(np.asarray(size_cm, float).ravel() / 100.0)
    if len(a) != 3 or len(b) != 3 or (a <= 0).any() or (b <= 0).any():
        return 9.9
    a, b = a / a.max(), b / b.max()
    return float(np.abs(np.log(a / b)).sum())


def shortlist(p, k=SHORTLIST):
    mount = p.get("mount", "floor")
    toks = _tokens(p["label"]) | _tokens(p.get("reason", ""))
    rows = []
    for a in catalog():
        if mount == "wall" and not a.get("onWall"):
            continue
        if mount == "floor" and not (a.get("onFloor") or a.get("onObject")):
            continue
        overlap = len(toks & a["_cat_toks"]) * 2 + len(toks & a["_desc_toks"])
        if overlap == 0:
            continue
        rows.append((overlap - size_score(p["size"], a["size"]), a))
    rows.sort(key=lambda r: -r[0])
    return [a for _, a in rows[:k]]


def _pick_prompt(p, cands, scene_prompt):
    lines = "\n".join(
        f'- uid {a["uid"]} | {a["category"]} | {a["size"][0]}x{a["size"][1]}x{a["size"][2]} cm | {a["description"][:140]}'
        for a in cands)
    return f"""You are selecting a 3D asset from a catalog to fill a planned placement in a scene.

Scene style/description: {scene_prompt[:600]}

Planned placement: label = {p['label']}, size (m, WxHxD) = {p['size']}, mount = {p.get('mount', 'floor')}, reason = {p.get('reason', '')}

Candidates (uid | category | size | description):
{lines}

Pick the single best asset: match the described object and style first, then prefer dimensions close to the planned size (assets are rescaled, so shape/aspect matters more than absolute size). Reply with ONLY a JSON object: {{"uid": "<uid>", "why": "one line"}}"""


def run(sc, model="sonnet"):
    import comp_paths
    pkg = paths.package_dir(sc)
    prop = json.loads((pkg / "compose_proposal.json").read_text())
    pf = comp_paths.scene_prompt_file(sc)
    scene_prompt = pf.read_text(encoding="utf-8").strip() if pf else ""
    out = []
    for i, p in enumerate(prop["placements"]):
        cands = shortlist(p)
        if not cands:
            print(f"[retrieve] {p['label']}: NO candidates — skipped", flush=True)
            out.append({"placement_idx": i, "label": p["label"], "uid": None})
            continue
        by_uid = {a["uid"]: a for a in cands}
        def _val(o, _by=by_uid):
            if o.get("uid") not in _by:
                raise ValueError(f"uid must be one of the listed candidates, got {o.get('uid')}")
        pick = call_agent_json(_pick_prompt(p, cands, scene_prompt), validate=_val,
                               model=model, tag=f"retrieve_{i}")
        a = by_uid[pick["uid"]]
        out.append({"placement_idx": i, "label": p["label"], "uid": a["uid"],
                    "category": a["category"], "description": a["description"],
                    "asset_size_cm": a["size"], "box_size_m": p["size"],
                    "why": pick.get("why", "")})
        print(f"[retrieve] {p['label']} -> {a['category']} ({a['uid'][:8]}): "
              f"{a['description'][:80]}", flush=True)
    (pkg / "composed_assets.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    args = ap.parse_args()
    run(args.scene)
