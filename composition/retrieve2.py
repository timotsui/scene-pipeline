"""Retrieval v2: category-first, dimension-fit shortlists per manifest box.

Two-gate design (2026-07-14 session): candidate selection is CATEGORY ONLY —
the label is matched against the catalog `category` field in tiers (exact
string > token subset > any token overlap); descriptions never vote, so "rug"
can't be hijacked by "footstool with a red rug on it". Style stays out: the
shortlist is judged visually (review_server.py) instead of by a blind agent
pick.

Fit is yaw-aware and scale-coherent: per-axis log-ratios at 0/90 deg yaw with
the optimal uniform scale factored out — the residual is aspect mismatch, and
|log scale| is penalized so an asset built at dollhouse or giant native size
loses to one whose real size matches the box ("objects live together in the
same scale"). Tiling k=1..3 along the long horizontal axis is kept from
recreate.py (shelf x2 worked).

Labels with no lexical category match (lift noise like "poter") go through one
batch agent call mapping them to catalog categories; offline they are flagged
unmatched for the viewer.

Writes package/shortlists2.json. __main__ prints the per-box table
(--compare adds recreate.py's v0 pick row for contrast).
"""
import json
import re

import numpy as np

from comp_paths import paths
from retrieve import catalog

TOP_N = 24
LAMBDA_SCALE = 0.5           # weight of |log uniform-scale| vs aspect residual
TILE_PENALTY = 0.25          # per extra tiled instance
MAX_TILES = 3
MIN_CONF = 0.35
WALL_LABELS = {"window", "door", "curtain", "picture", "poster", "painting"}

_BY_CAT = None


def _norm(tok):
    return tok[:-1] if tok.endswith("s") and len(tok) > 3 else tok


def _toks(s):
    return {_norm(t) for t in re.findall(r"[a-z]+", s.lower())}


def by_category():
    """category string -> [annotation rows], built once over the catalog."""
    global _BY_CAT
    if _BY_CAT is None:
        _BY_CAT = {}
        for a in catalog():
            _BY_CAT.setdefault(a["category"].strip().lower(), []).append(a)
    return _BY_CAT


def match_categories(label):
    """-> (tier, [category strings]) for a box label; tier 3 = unmatched.
    Tiers: 0 exact string, 1 token subset either way, 2 any token overlap."""
    lab = label.strip().lower()
    lt = _toks(lab)
    tiers = ([], [], [])
    for cat in by_category():
        ct = _toks(cat)
        if not ct:
            continue
        if _norm(lab) == _norm(cat) or lt == ct:
            tiers[0].append(cat)
        elif ct <= lt or lt <= ct:
            tiers[1].append(cat)
        elif lt & ct:
            tiers[2].append(cat)
    for tier, cats in enumerate(tiers):
        if cats:
            return tier, cats
    return 3, []


PERMS = ("xyz", "zyx", "xzy", "yxz", "zxy", "yzx")  # world (x,y,z) <- asset axes
_AX = {"x": 0, "y": 1, "z": 2}
UPRIGHT_PENALTY = 0.3   # perms that change which asset axis points up: only a
                        # mis-authored mesh (e.g. a rug standing on its side)
                        # should win one of these


def fit(box_m, size_cm):
    """Orientation-aware fit of an asset (size cm) into a box (m, xyz extents).
    -> (score, perm, scale, aspect_resid, log_scale); lower score = better.
    perm[i] = the asset axis lying along world axis i (world y = up): "xyz" is
    identity, "zyx" the 90-deg yaw, the other four re-up the asset (penalized).
    Any dims permutation is realizable as a proper rotation (signs absorb
    parity) — thumbs.perm_rotation builds it for thumbnails and placement.
    Optimal uniform scale is factored out per perm: resid = aspect mismatch
    after that rescale, |log s| = how far off native size the asset is."""
    b = np.asarray(box_m, np.float64)
    a0 = np.asarray(size_cm, np.float64) / 100.0
    if b.shape != (3,) or a0.shape != (3,) or (b <= 0).any() or (a0 <= 0).any():
        return 99.0, "xyz", 1.0, 99.0, 0.0
    best = None
    for perm in PERMS:
        a = a0[[_AX[c] for c in perm]]
        d = np.log(b / a)
        ls = d.mean()                       # optimal uniform log-scale
        resid = float(np.abs(d - ls).sum())
        score = (resid + LAMBDA_SCALE * abs(ls)
                 + (0.0 if perm[1] == "y" else UPRIGHT_PENALTY))
        if best is None or score < best[0]:
            best = (score, perm, float(np.exp(ls)), resid, float(ls))
    return best


def _sub_box_size(box_size, k):
    """Size of one tile when the box is split k ways along its long horizontal
    axis. -> (tile_size, axis)."""
    s = list(box_size)
    axis = 0 if s[0] >= s[2] else 2
    s[axis] = s[axis] / k
    return s, axis


def best_fit_config(box_size, a):
    """Best (score, k, axis, perm, scale) for asset a over k=1..MAX_TILES."""
    best = None
    for k in range(1, MAX_TILES + 1):
        s, axis = _sub_box_size(box_size, k)
        sc, perm, scale, resid, ls = fit(s, a["size_yup_cm"])
        sc += TILE_PENALTY * (k - 1)
        if best is None or sc < best[0]:
            best = (sc, k, axis, perm, scale, resid, ls)
    return best


def _mount(o, floor_y, sy):
    """Same contract as recreate.py: wall labels -> wall; bottom near floor ->
    floor; else free (elevated items keep their box y)."""
    if o["label"].strip().lower() in WALL_LABELS:
        return "wall"
    ys = (o["aabb_min"][1], o["aabb_max"][1])
    bottom_elev = min(sy * (y - floor_y) for y in ys)
    return "floor" if bottom_elev < 0.25 else "free"


def _mount_ok(a, mount):
    if mount == "wall":
        return bool(a.get("onWall"))
    return bool(a.get("onFloor") or a.get("onObject"))


def shortlist_box(o, mount, cats, n=TOP_N):
    """Rank all assets of the matched categories by fit into o's box."""
    rows = []
    for cat in cats:
        for a in by_category()[cat]:
            if not _mount_ok(a, mount):
                continue
            sc, k, axis, perm, scale, resid, ls = best_fit_config(o["size"], a)
            rows.append({"uid": a["uid"], "category": a["category"],
                         "description": a["description"],
                         "size_cm": a["size_yup_cm"], "score": round(sc, 3),
                         "k": k, "axis": axis, "perm": perm,
                         "scale": round(scale, 3),
                         "aspect_resid": round(resid, 3),
                         "log_scale": round(ls, 3)})
    rows.sort(key=lambda r: r["score"])
    return rows[:n]


def map_labels_agent(labels, model="sonnet"):
    """One batch call: lift-noise labels -> catalog categories (or [])."""
    from bridge import call_agent_json
    cats = sorted(by_category())
    prompt = f"""These object labels came from a noisy open-vocabulary detector run on renders
of an indoor scene. For each label, list the categories from the catalog below
that the detector most plausibly meant (typos and near-synonyms included, e.g.
"poter" is probably "poster"). If the catalog has no direct match, list
functionally/visually similar categories that could stand in when rescaled
(e.g. a "doormat" or "place mat" can stand in for a rug). Use ONLY category
strings from the catalog; give [] only if nothing could plausibly stand in.

Labels: {json.dumps(labels)}

Catalog categories: {json.dumps(cats)}

Reply with ONLY a JSON object mapping each label to a list of categories."""
    def _val(r):
        bad = [c for v in r.values() for c in v if c.lower() not in by_category()]
        if set(r) != set(labels) or bad:
            raise ValueError(f"must map every label to catalog categories; bad: {bad}")
    return call_agent_json(prompt, validate=_val, model=model, tag="label_map")


def run(sc, use_agent=True, model="sonnet"):
    man = json.loads(paths.manifest(sc).read_text())
    fr = man["frame"]
    sy = fr.get("raw_to_render", [1, 1, 1])[1]
    objs = [o for o in man["objects"] if o["score"] >= MIN_CONF]
    print(f"[retrieve2] {len(objs)}/{len(man['objects'])} boxes (conf >= {MIN_CONF})",
          flush=True)

    matched, unmatched = {}, []
    for o in objs:
        tier, cats = match_categories(o["label"])
        matched[o["id"]] = {"tier": tier, "cats": cats}
        if tier == 3:
            unmatched.append(o["label"])
    if unmatched and use_agent:
        try:
            fix = map_labels_agent(sorted(set(unmatched)), model=model)
            for o in objs:
                m = matched[o["id"]]
                if m["tier"] == 3 and fix.get(o["label"]):
                    m.update(tier="agent", cats=[c.lower() for c in fix[o["label"]]])
        except Exception as e:
            print(f"[retrieve2] agent label map failed ({e}); "
                  f"unmatched stay flagged", flush=True)

    out = []
    for o in objs:
        m = matched[o["id"]]
        mount = _mount(o, fr["floor_y"], sy)
        cands = shortlist_box(o, mount, m["cats"]) if m["cats"] else []
        out.append({"id": o["id"], "label": o["label"], "conf": o["score"],
                    "center": o["center"], "size": o["size"],
                    "aabb_min": o["aabb_min"], "aabb_max": o["aabb_max"],
                    "views": o.get("views", []), "mount": mount,
                    "match_tier": m["tier"], "categories": m["cats"],
                    "candidates": cands})
        tag = f"tier {m['tier']}" if m["cats"] else "UNMATCHED"
        print(f"[retrieve2] {o['id']} {o['label']:18s} {mount:5s} {tag}: "
              f"{len(cands)} candidates from {len(m['cats'])} categories", flush=True)
    outf = paths.package_dir(sc) / "shortlists2.json"
    outf.write_text(json.dumps({"scene": sc, "boxes": out}, indent=1))
    print(f"[retrieve2] wrote {outf}", flush=True)
    return out


def print_table(boxes, compare=False, top=8):
    for b in boxes:
        dims = "x".join(f"{v:.2f}" for v in b["size"])
        print(f"\n== {b['id']} {b['label']} | box {dims} m | {b['mount']} | "
              f"tier {b['match_tier']} | cats: {', '.join(b['categories'][:6])}"
              f"{' ...' if len(b['categories']) > 6 else ''}")
        if not b["candidates"]:
            print("   (no candidates)")
            continue
        for r in b["candidates"][:top]:
            szs = "x".join(str(v) for v in r["size_cm"])
            tile = f" x{r['k']}" if r["k"] > 1 else ""
            print(f"   {r['score']:6.3f}  {r['category']:22.22s}{tile} "
                  f"{r['perm']} sc{r['scale']:5.2f} | {szs:>12s} cm | "
                  f"{r['description'][:58]}")
        if compare:
            from recreate import best_configuration
            o = {"label": b["label"], "size": b["size"]}
            k, _, short = best_configuration(o)
            v0 = short[0] if short else None
            if v0 is not None:
                print(f"   v0 top: {v0['category']}"
                      f"{' x' + str(k) if k > 1 else ''} | "
                      f"{v0['description'][:70]}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--compare", action="store_true",
                    help="also print recreate.py v0's top pick per box")
    ap.add_argument("--no-agent", action="store_true",
                    help="skip the batch label-map agent call (offline)")
    ap.add_argument("--top", type=int, default=8)
    args = ap.parse_args()
    boxes = run(args.scene, use_agent=not args.no_agent)
    print_table(boxes, compare=args.compare, top=args.top)
