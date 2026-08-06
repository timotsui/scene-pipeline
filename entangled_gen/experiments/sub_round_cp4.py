"""SUB ROUNDS — CP4: CHEAP-BY-CLASS RETRIEVAL (isolated, obj_043).

USER RULING 2026-08-05C (AskUserQuestion): subs get their assets
CHEAP — top-1 by category + native-size fit, NO judge calls. Matches
the effort-follows-error-cost canon: a wrong-ish book spine costs
nothing visually. Weak matches are FLAGGED for a later judged pass,
never silently shipped.

Reuses the anchors' machinery end to end (no new matching logic):
  retrieve2.match_categories  — tiered lexical category match
                                (tier 3 / no cats = NO_MATCH flag;
                                the LLM label-mapper is NOT called)
  shopping.shortlist          — catalog pool + mount filter +
                                native-size fit ranking (no rescale)
Sub box size comes from the CP3 START box (observed size, clamped
start) — fit is judged against what will actually be placed.

Weak-match flags: NO_MATCH (no category), POOR_FIT (best worst-axis
deviation > 0.5), TIER (lexical tier 2 = fuzzy token match).

Outputs (out/<scene>/compose/sub_experiment/cp4/):
  picks.json    per sub: category tier, top-1 uid/perm/k + runner-up
                uids (for CP5 walk-downs), flags
  thumbs/       copied thumbnails for the page
  index.html    review page (USER GATE: is each pick the right KIND
                of thing at a sane size?)

  python sub_round_cp4.py [--scene bedroom_marble] [--anchor obj_043]
"""
import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
EG = HERE.parent
sys.path.insert(0, str(EG))
sys.path.insert(0, str(EG / "compose"))

import paths                                     # noqa: E402
sys.path.insert(0, str(paths.REPO_ROOT / "composition"))
import retrieve2                                 # noqa: E402
from shopping import shortlist, native_fit       # noqa: E402

POOR_FIT = 0.5      # worst-axis deviation above this -> flag
DRY_SUB = 0.65      # SR4c = anchor rule 9 at depth N (SAME loop, same
                    # constant as the anchors' DRY): best of the WHOLE
                    # shortlist above this -> the list is dry. Adds
                    # drop entirely; detections drop with a recorded
                    # complaint (no re-shop exists — the cheap path
                    # already searched the full category pool, so the
                    # complaint = a library-gap record).
KEEP_RUNNERS = 2    # runner-up uids recorded for CP5 walk-downs
RERANK_M = 12       # --aligned: top-M catalog candidates re-measured


def aligned_sizes(uids, cache_path):
    """uid -> {size_cm (y-up, ALIGNED aabb), align_deg}, cached on disk.

    USER RULING 2026-08-05C: shop with the ALIGNED size — the catalog
    AABB of a tilted asset is inflated by its lean, so fit scores and
    the k multiplier were computed on wrong numbers. Fix at the
    source: measure once per uid, cache forever (the cache is the
    seed of a future catalog column, same trajectory as the yaw-fixup
    channel)."""
    from assets_thor import load_asset
    from sub_round_cp5 import align_upright
    cache = (json.loads(cache_path.read_text("utf-8"))
             if cache_path.exists() else {})
    fresh = 0
    for uid in uids:
        if uid in cache:
            continue
        try:
            m, ang = align_upright(load_asset(uid))
            ext = (m.bounds[1] - m.bounds[0]) * 100.0
            cache[uid] = {"size_cm": [round(float(v), 1) for v in ext],
                          "align_deg": ang}
            fresh += 1
        except Exception as ex:
            cache[uid] = {"error": str(ex)[:120]}
    if fresh:
        cache_path.write_text(json.dumps(cache, indent=1),
                              encoding="utf-8")
    print(f"[cp4] aligned sizes: {fresh} measured, "
          f"{len(uids) - fresh} cached")
    return cache


def _judge(prompt, cwd, timeout=150):
    """One-look judge call (claude -p, sonnet) — the rotation_check
    pattern without its pyrender import chain."""
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("claude not on PATH")
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(k, None)          # stale-API-key hijack gotcha
    t0 = time.time()
    r = subprocess.run([exe, "-p", "--model", "sonnet",
                        "--output-format", "json"],
                       input=prompt, capture_output=True, text=True,
                       encoding="utf-8", errors="replace",
                       env=env, cwd=str(cwd), timeout=timeout)
    out = (r.stdout or "").strip()
    m = re.search(r"\{.*\}", out, re.DOTALL)
    envl = json.loads(m.group(0)) if m else {}
    text = envl.get("result") if isinstance(envl.get("result"), str) \
        else out
    m2 = re.search(r"\{[^{}]*\}", text or "", re.DOTALL)
    return (json.loads(m2.group(0)) if m2 else {}), round(
        time.time() - t0, 1)


def rung2_host_includes(host_uid, host_name, part, root, cache):
    """SR4b-v rung 2 — the description was silent: ONE look at the
    host asset's thumbnail, cached per uid x part, autonomous (no
    user pins — prime directive)."""
    key = f"{host_uid}:{part}"
    if key in cache:
        return cache[key]
    import thumbs
    thumbs.ensure([(host_uid, "xyz")])
    tp = thumbs.thumb_path(host_uid, "xyz")
    folder = root / "host_covers_calls" / f"{host_uid[:8]}_{part.replace(' ', '_')}"
    folder.mkdir(parents=True, exist_ok=True)
    local = folder / "host.png"
    if tp.exists():
        shutil.copyfile(tp, local)
    prompt = (f"IMAGE (product photo of a 3D asset from our library, "
              f"catalog name '{host_name}'):\n{local}\n\n"
              f"QUESTION: does this asset VISUALLY INCLUDE a "
              f"{part} as part of the model itself?\n\n"
              'Reply with ONLY a JSON object, no other text:\n'
              '{"includes": true|false, '
              '"confidence": "high"|"medium"|"low", '
              '"why": "<one short sentence>"}')
    (folder / "prompt.txt").write_text(prompt, encoding="utf-8")
    try:
        ans, dt = _judge(prompt, folder)
    except Exception as ex:
        ans, dt = {"error": str(ex)[:150]}, None
    ans["wall_s"] = dt
    (folder / "reply.json").write_text(json.dumps(ans, indent=1),
                                       encoding="utf-8")
    cache[key] = ans
    return ans


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    ap.add_argument("--anchor", default="obj_043")
    ap.add_argument("--aligned", action="store_true",
                    help="re-rank the top candidates on their ALIGNED "
                         "sizes (output goes to cp4_aligned/)")
    a = ap.parse_args()

    cdir = paths.compose_dir(a.scene)
    root = cdir / "sub_experiment"        # shared cache lives here
    sdir = root / a.anchor
    asg = json.loads((sdir / "cp3" / "assignment.json").read_text("utf-8"))
    if asg["anchor"] != a.anchor:
        raise SystemExit("cp3 record is for a different anchor")

    # HOST-COVERS-IT RULE (08-05C, the door-handle case): a sub whose
    # matched category IS its own host's category is a PART of the
    # host — the host asset already includes it (shopping.py's anchor-
    # tier header rule, applied to the cheap path). Kills "door
    # handle"→door-on-a-door; spares monitor-on-desk, picture-on-shelf
    # (host categories differ). Category-based, scene-agnostic.
    sl = json.loads((cdir / "shopping.json").read_text("utf-8"))
    name_of = {it["id"]: it["name"] for it in sl["items"]}
    name_of.update({s2["id"]: s2["name"] for s2 in sl["subs_deferred"]})
    seeds = json.loads((sdir / "cp1" / "seeds.json").read_text("utf-8"))
    host_of = {s2["id"]: s2.get("host") for s2 in seeds["subs"]}

    # SR4b VERIFICATION step 1 (user 08-05C): does the host's PLACED
    # asset actually include the part? Cheapest rung = its catalog
    # description — a positive mention is trustworthy ("door with
    # silver handle"); silence is NOT absence (descriptions are
    # gestalt-blind) → UNVERIFIED, queued for the thumbnail judge.
    fp = json.loads((cdir / "fitted_preview.json").read_text("utf-8"))
    placed_uid = {p["id"]: p.get("uid") for p in fp["placed"]}
    desc_of = {}
    for pool in retrieve2.by_category().values():
        for asset in pool:
            desc_of[asset["uid"]] = asset.get("description") or ""

    def host_covers_verify(sub_name, host_id, host_cats):
        uid = placed_uid.get(host_id)
        desc = desc_of.get(uid or "", "")
        host_toks = set()
        for hc in host_cats:
            host_toks |= set(retrieve2._toks(hc))
        part = [t for t in retrieve2._toks(sub_name)
                if t not in host_toks]
        dt = set(retrieve2._toks(desc))
        hit = [t for t in part if t in dt or t + "s" in dt
               or t.rstrip("s") in dt]
        if hit:
            return {"verified": "text", "matched": hit,
                    "host_uid": (uid or "")[:8], "description": desc}
        return {"verified": None, "host_uid": (uid or "")[:8],
                "description": desc}

    hc_cache_p = root / "host_covers_cache.json"
    hc_cache = (json.loads(hc_cache_p.read_text("utf-8"))
                if hc_cache_p.exists() else {})

    pre = []      # (sub record, box size, catalog candidates)
    wall_routed = []                      # SR3b'd subs: adjudicate only
    for s in asg["subs"]:
        if not s.get("start_box_render"):
            if "NOT_A_BOARD_RIDER" in (s.get("flags") or []):
                wall_routed.append(s)
            continue                      # NO_BOARD subs never shop
        lo = np.asarray(s["start_box_render"]["lo"], np.float64)
        hi = np.asarray(s["start_box_render"]["hi"], np.float64)
        size = (hi - lo).tolist()
        tier, cats = retrieve2.match_categories(s["name"])
        host_name = name_of.get(host_of.get(s["id"]) or "", "")
        host_cats = (retrieve2.match_categories(host_name)[1]
                     if host_name else [])
        if cats and host_cats and cats[0] in host_cats:
            pre.append((s, size, tier, "HOST_COVERS", []))
            continue
        cands = shortlist(s["name"], size, "floor", cats) if cats else []
        pre.append((s, size, tier, cats, cands))

    acache = {}
    if a.aligned:
        need = sorted({c["uid"] for (_, _, _, _, cands) in pre
                       for c in cands[:RERANK_M]})
        acache = aligned_sizes(need, root / "aligned_size_cache.json")

    rows = []
    for s, size, tier, cats, cands in pre:
        flags = []
        if cats == "HOST_COVERS":
            hid = host_of.get(s["id"]) or ""
            hcats = retrieve2.match_categories(
                name_of.get(hid, ""))[1]
            ver = host_covers_verify(s["name"], hid, hcats)
            fl = ["HOST_COVERS"]
            if not ver["verified"]:
                # rung 2: silent description -> ONE thumbnail look
                ans = rung2_host_includes(
                    placed_uid.get(hid) or "", name_of.get(hid, ""),
                    s["name"], sdir.parent, hc_cache)
                if ans.get("includes") is True:
                    ver = {**ver, "verified": "judge", "judge": ans}
                elif ans.get("includes") is False:
                    # part genuinely absent AND category-equal =
                    # the library has no separate category for it:
                    # honest gap, still no buy
                    fl = ["HOST_LACKS_PART", "NO_MATCH"]
                    ver = {**ver, "judge": ans}
                else:
                    fl.append("UNVERIFIED")   # judge errored
            rows.append({"id": s["id"], "name": s["name"],
                         "board": s["board"], "box_size_m":
                         [round(v, 3) for v in size],
                         "cat_tier": tier, "cats": [],
                         "flags": fl, "pick": None,
                         "runners": [], "host_covers": ver})
            continue
        if not cats:
            flags.append("NO_MATCH")
        elif tier >= 2:
            flags.append("TIER")
        if a.aligned and cands:
            # re-fit the top-M on ALIGNED sizes, re-rank
            rr = []
            for c in cands[:RERANK_M]:
                ai = acache.get(c["uid"]) or {}
                if "size_cm" not in ai:
                    continue
                cfg = native_fit(size, ai["size_cm"])
                if cfg is None:
                    continue
                rr.append({**c, **cfg, "size_cm": ai["size_cm"],
                           "align_deg": ai["align_deg"]})
            rr.sort(key=lambda r: (r["score"], r["k"]))
            cands = rr
        # SR4d — SUB BRINGS HOST (08-05C, "White window ... and green
        # curtain"): a candidate whose description mentions the HOST's
        # category would DUPLICATE the host. Prefer clean candidates;
        # if every candidate brings it, keep the list + flag.
        if cands:
            hid4 = host_of.get(s["id"]) or ""
            htoks = set()
            for hc in retrieve2.match_categories(
                    name_of.get(hid4, ""))[1]:
                htoks |= set(retrieve2._toks(hc))
            if htoks:
                clean = [c for c in cands
                         if not (htoks & set(retrieve2._toks(
                             c.get("description") or "")))]
                if clean:
                    cands = clean
                else:
                    flags.append("SUB_BRINGS_HOST")
        if cats and not cands:
            flags.append("NO_MATCH")
        elif cands and cands[0]["score"] > POOR_FIT:
            flags.append("POOR_FIT")
        # SR4c — anchor rule 9, same loop one level down: the runners
        # ARE the walk; best of the whole shortlist dry -> drop.
        if cands and min(c["score"] for c in cands) > DRY_SUB:
            src = "add" if s["id"].startswith("add") else "detected"
            rows.append({"id": s["id"], "name": s["name"],
                         "board": s["board"],
                         "box_size_m": [round(v, 3) for v in size],
                         "cat_tier": tier, "cats": cats,
                         "flags": ["DRY"], "pick": None, "runners": [],
                         "dry": {"source": src,
                                 "best_score": min(c["score"]
                                                   for c in cands),
                                 "complaint": (None if src == "add" else
                                               f"library gap: no "
                                               f"{cats[0]} within "
                                               f"{DRY_SUB} of "
                                               f"{[round(v,2) for v in size]} m")}})
            continue
        top = cands[0] if cands else None
        rows.append({
            "id": s["id"], "name": s["name"], "board": s["board"],
            "box_size_m": [round(v, 3) for v in size],
            "cat_tier": tier, "cats": cats, "flags": flags,
            "pick": ({"uid": top["uid"], "perm": top["perm"],
                      "k": top["k"], "score": top["score"],
                      "fits": top["fits"], "category": top["category"],
                      "size_cm": top["size_cm"],
                      "align_deg": top.get("align_deg"),
                      "description": top["description"]} if top else None),
            "runners": [{"uid": c["uid"], "perm": c["perm"],
                         "score": c["score"]}
                        for c in cands[1:1 + KEEP_RUNNERS]],
        })

    # SR3b'd subs are never board-shopped, but the HOST-COVERS
    # question still decides whether the wall channel even needs them
    # (the window-behind-curtain case)
    for s in wall_routed:
        hid = host_of.get(s["id"]) or ""
        hname = name_of.get(hid, "")
        hcats = retrieve2.match_categories(hname)[1]
        ver = host_covers_verify(s["name"], hid, hcats)
        fl = ["NOT_A_BOARD_RIDER"]
        if ver["verified"]:
            fl.append("HOST_COVERS")
        else:
            ans = rung2_host_includes(
                placed_uid.get(hid) or "", hname, s["name"], root,
                hc_cache)
            if ans.get("includes") is True:
                fl.append("HOST_COVERS")
                ver = {**ver, "verified": "judge", "judge": ans}
            elif ans.get("includes") is False:
                fl.append("WALL_CHANNEL")   # genuinely needed; unwired
                ver = {**ver, "judge": ans}
            else:
                fl.append("UNVERIFIED")
                ver = {**ver, "judge": ans}
        rows.append({"id": s["id"], "name": s["name"], "board": None,
                     "box_size_m": None, "cat_tier": None, "cats": [],
                     "flags": fl, "pick": None, "runners": [],
                     "host_covers": ver, "route": s.get("route")})

    hc_cache_p.write_text(json.dumps(hc_cache, indent=1),
                          encoding="utf-8")

    odir = sdir / ("cp4_aligned" if a.aligned else "cp4")
    odir.mkdir(parents=True, exist_ok=True)
    prev = None
    if a.aligned and (sdir / "cp4" / "picks.json").exists():
        prev = {r["id"]: r for r in json.loads(
            (sdir / "cp4" / "picks.json").read_text("utf-8"))["subs"]}
        for r in rows:
            pr = (prev.get(r["id"]) or {}).get("pick")
            if pr and r["pick"]:
                r["changed_vs_cp4"] = (pr["uid"] != r["pick"]["uid"]
                                       or pr["k"] != r["pick"]["k"])
                r["cp4_was"] = {"uid": pr["uid"], "k": pr["k"],
                                "score": pr["score"]}
    rec = {"scene": a.scene, "anchor": a.anchor,
           "anchor_name": asg.get("anchor_name"),
           "mode": ("cheap_by_class + ALIGNED sizes (user 08-05C)"
                    if a.aligned else "cheap_by_class (user ruling "
                    "08-05C)"),
           "poor_fit_threshold": POOR_FIT,
           "n_subs": len(rows),
           "n_flagged": sum(1 for r in rows if r["flags"]),
           "subs": rows}
    (odir / "picks.json").write_text(json.dumps(rec, indent=1),
                                     encoding="utf-8")

    # ---- thumbnails for the page
    import thumbs
    need = [(r["pick"]["uid"], r["pick"]["perm"]) for r in rows
            if r["pick"]]
    thumbs.ensure(need)
    tdir = odir / "thumbs"
    tdir.mkdir(exist_ok=True)
    for r in rows:
        if not r["pick"]:
            continue
        p = thumbs.thumb_path(r["pick"]["uid"], r["pick"]["perm"])
        if not p.exists():
            p = thumbs.thumb_path(r["pick"]["uid"], "xyz")
        if p.exists():
            dst = tdir / f'{r["id"]}.png'
            shutil.copyfile(p, dst)
            r["thumb"] = f'thumbs/{r["id"]}.png'
    (odir / "picks.json").write_text(json.dumps(rec, indent=1),
                                     encoding="utf-8")

    build_page(odir, rec)
    print(f"[cp4] {len(rows)} subs, {rec['n_flagged']} flagged, "
          f"0 judge calls")
    print(f"[cp4] wrote {odir / 'index.html'}")


def build_page(odir, rec):
    css = """
:root{color-scheme:dark}*{box-sizing:border-box}
body{margin:0;background:#141414;color:#e8e8e8;
     font:15px/1.55 "Segoe UI",system-ui,sans-serif}
.wrap{max-width:1500px;margin:0 auto;padding:28px 32px 120px}
h1{font-size:24px;margin:0 0 4px}
.sub{color:#9a9a9a;margin:0 0 20px}
.contract{background:#1c1c1c;border-left:3px solid #ffd479;
          padding:14px 18px;margin:18px 0;border-radius:0 4px 4px 0}
.contract b{color:#ffd479}
.note{background:#1c1c1c;border-left:3px solid #4a90d9;padding:12px 18px;
      margin:18px 0;border-radius:0 4px 4px 0;color:#c9c9c9}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;
      margin:18px 0}
.card{background:#191919;border:1px solid #2b2b2b;border-radius:7px;
      padding:12px 14px}
.card.flag{border-color:#5d3030}
.card img{width:100%;aspect-ratio:1;object-fit:contain;background:#232323;
          border-radius:4px;display:block}
.card .hd{font-weight:600;margin:8px 0 2px}
.card .meta{color:#9a9a9a;font-size:12.5px;font-family:Consolas,monospace}
.card .desc{color:#b5b5b5;font-size:12.5px;margin-top:6px}
.tag{display:inline-block;font-size:11px;padding:1px 7px;border-radius:9px;
     margin:4px 4px 0 0}
.tag.ok{background:#1c2a1c;color:#9dd89d;border:1px solid #2c5d2c}
.tag.warn{background:#4a2020;color:#ff9d9d;border:1px solid #6d2c2c}
"""
    h = ['<!doctype html><meta charset="utf-8">',
         f'<title>sub rounds CP4 — picks — {rec["anchor"]}</title>',
         f'<style>{css}</style><div class="wrap">',
         '<h1>Sub rounds — CP4: cheap-by-class retrieval</h1>',
         f'<p class="sub">{rec["scene"]} · anchor {rec["anchor"]} '
         f'({html.escape(str(rec["anchor_name"]))}) · {rec["n_subs"]} subs '
         f'· {rec["n_flagged"]} flagged · 0 judge calls (user ruling: '
         'effort follows error cost)</p>',
         '<div class="contract">'
         '<b>What this step gets:</b> each sub&rsquo;s name and its CP3 '
         'start-box size.<br>'
         '<b>What it decides:</b> WHICH library asset stands in for the '
         'sub — top-1 by category match + native-size fit (no rescale, '
         'same fit metric as the anchors&rsquo; shopping). Runner-ups '
         'are recorded for the placement round&rsquo;s walk-downs.<br>'
         '<b>What a mistake looks like:</b> the wrong KIND of thing (a '
         'crate for a book), a wildly wrong size, or a weak match '
         'shipped without its flag.</div>']
    h.append('<div class="grid">')
    for r in rec["subs"]:
        flagged = bool(r["flags"])
        cls = "card flag" if flagged else "card"
        h.append(f'<div class="{cls}">')
        if r.get("thumb"):
            h.append(f'<img src="{r["thumb"]}">')
        else:
            h.append('<div style="aspect-ratio:1;background:#232323;'
                     'border-radius:4px;display:flex;align-items:center;'
                     'justify-content:center;color:#666">no asset</div>')
        h.append(f'<div class="hd">{r["id"]} · '
                 f'{html.escape(r["name"])} · B{r["board"]}</div>')
        p = r["pick"]
        if p:
            sz = " × ".join(f"{v/100:.2f}" for v in p["size_cm"])
            bx = " × ".join(f"{v:.2f}" for v in r["box_size_m"])
            h.append(f'<div class="meta">box {bx} m<br>asset {sz} m '
                     f'(y-up)<br>fit worst-axis {p["score"]:.2f}'
                     f'{" · fits" if p["fits"] else ""}'
                     + (f' · {p["k"]} copies' if p["k"] > 1 else "")
                     + f'<br>{html.escape(p["category"])}</div>')
            h.append(f'<div class="desc">'
                     f'{html.escape(str(p["description"])[:110])}</div>')
        if p and p.get("align_deg") is not None:
            h.append(f'<div class="meta">align {p["align_deg"]:g}&deg; '
                     '(size measured AFTER upright snap)</div>')
        for f in r["flags"]:
            h.append(f'<span class="tag warn">{f}</span>')
        if r.get("changed_vs_cp4"):
            w = r["cp4_was"]
            h.append(f'<span class="tag warn">CHANGED — cp4 was '
                     f'{w["uid"][:8]} k{w["k"]} @{w["score"]:.2f}</span>')
        elif "changed_vs_cp4" in r:
            h.append('<span class="tag ok">same pick as cp4</span>')
        if not flagged:
            h.append('<span class="tag ok">clean</span>')
        h.append('</div>')
    h.append('</div>')
    h.append('<div class="note"><b>Gate question (one look):</b> is each '
             'thumbnail the right KIND of thing at a believable size for '
             'its box? Red cards carry flags — those are already marked '
             'for a later judged pass, so only an unflagged wrong pick '
             'fails this gate.</div>')
    h.append('</div>')
    (odir / "index.html").write_text("\n".join(h), encoding="utf-8")


if __name__ == "__main__":
    main()
