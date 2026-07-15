"""C7 loop: propose→verify refinement of composed_state2.json over a typed
edit space. v1 ops: add + nudge (contract: README "C7 loop contract" —
swap/remove/flip_facing bolt on later without touching this skeleton).

Each iteration: render the current state from the judge cameras, show the VLM
ORIGINAL/RECREATION pairs (one call, all views), get a structured critique
with proposed edits, then per edit: free geometric validation → apply (add
re-enters the C1–C5 chain for that one box) → re-render → VLM before/after
verify. Accept ONLY "better" (neutral reverts, anti-drift); every attempt is
journaled to package/edits.jsonl, and rejected edits are fed back into the
critique prompt so they are never re-proposed (Reflexion memory).

The VLM talks RENDER frame (y up, meters — the frame the view sidecars use);
centers/deltas convert to RAW via frame.raw_to_render (elementwise,
self-inverse) at ingest. `yaw` on a state entry is a free render-frame
rotation about +y (place2 applies it about the placed mesh's bbox center).

Files: composed_state2.json stays THE state (updated in place on accept;
snapshotted once to composed_state2_base.json); loop renders live under
package/loop/ so canonical composed2_view_*.png are only rewritten at the
end. Accepted adds are appended to shortlists2.json + picks2.json
(source: "loop") so the viewers can inspect them.

Run: python loop.py --scene <sc> [--max-iters 4] [--max-edits 4]
"""
import argparse
import json
import shutil

import numpy as np
from PIL import Image

import collide
import measure
import pick as pick_policy
import place2
import retrieve2
import thumbs
from bridge import call_agent_json
from comp_paths import paths
from retrieve import catalog

MAX_ITERS = 4
EDITS_PER_ITER = 4
MAX_VLM_CALLS = 30           # critique + verify calls, hard stop
NUDGE_DPOS_MAX = 0.5         # m, per-axis |dpos component| per edit
NUDGE_DYAW_MAX = 45.0        # deg per edit
NUDGE_DSCALE = (0.8, 1.25)   # per edit
ADD_AXIS_RANGE = (0.01, 3.5) # m, sane extents (0.01 keeps rugs/mats addable)
ROOM_TOL = 0.15              # m a box may poke past the room shell


def _iid(e):
    return f'{e["group"]}.{e["part"]}'


def _ctx(sc):
    """Manifest frame -> render-frame room bounds + the raw<->render map."""
    man = json.loads(paths.manifest(sc).read_text())
    fr = man["frame"]
    r2r = np.asarray(fr.get("raw_to_render", [1.0, 1.0, 1.0]), np.float64)
    p1 = np.asarray(fr["extent_p1"], np.float64) * r2r
    p2 = np.asarray(fr["extent_p99"], np.float64) * r2r
    return {"fr": fr, "r2r": r2r, "floor": fr["floor_y"] * r2r[1],
            "room_lo": np.minimum(p1, p2), "room_hi": np.maximum(p1, p2)}


def _render_box(e, r2r):
    c = np.asarray(e["center"], np.float64) * r2r
    s = np.asarray(e["size"], np.float64)
    return c - s / 2, c + s / 2


def _in_room(lo, hi, ctx):
    return (bool((lo >= ctx["room_lo"] - ROOM_TOL).all())
            and bool((hi <= ctx["room_hi"] + ROOM_TOL).all()))


def edit_key(edit):
    """Canonical dedup key; adds snap to a 25 cm grid so a rejected add
    blocks near-identical re-proposals, not just exact ones."""
    if edit["op"] == "add":
        c = ",".join(f"{round(float(v) * 4) / 4:g}" for v in edit["center"])
        s = ",".join(f"{round(float(v) * 4) / 4:g}" for v in edit["size"])
        return f'add:{edit["label"].strip().lower()}@{c}#{s}'
    d = edit.get("dpos", [0, 0, 0])
    return (f'nudge:{edit["id"]}:'
            + ",".join(f"{float(v):.2f}" for v in d)
            + f':{float(edit.get("dyaw_deg", 0)):.0f}'
            + f':{float(edit.get("dscale", 1)):.2f}')


# ---------------------------------------------------------------- nudge

def apply_nudge(edit, state, ctx):
    """-> (new_state, reason). Caps -> apply -> room check -> mesh-voxel
    collision (collide.py); a collision is only fatal if the edit made it
    worse past RATIO_MAX (lifted scenes already interpenetrate — don't
    punish pre-existing sin)."""
    r2r = ctx["r2r"]
    dpos = np.asarray(edit.get("dpos", [0, 0, 0]), np.float64)
    dyaw = float(edit.get("dyaw_deg", 0.0))
    ds = float(edit.get("dscale", 1.0))
    if float(np.abs(dpos).max()) > NUDGE_DPOS_MAX + 1e-9:
        return None, f"a |dpos| component > {NUDGE_DPOS_MAX} m"
    if abs(dyaw) > NUDGE_DYAW_MAX:
        return None, f"|dyaw| > {NUDGE_DYAW_MAX} deg"
    if not NUDGE_DSCALE[0] <= ds <= NUDGE_DSCALE[1]:
        return None, f"dscale outside {NUDGE_DSCALE}"
    if not np.linalg.norm(dpos) and not dyaw and ds == 1.0:
        return None, "no-op nudge"
    new = json.loads(json.dumps(state))
    tgt = next((e for e in new["objects"] if _iid(e) == edit["id"]), None)
    if tgt is None:
        return None, f'no instance {edit["id"]}'
    tgt["center"] = [round(float(v), 4) for v in
                     np.asarray(tgt["center"]) + dpos * r2r]
    if ds != 1.0:
        tgt["size"] = [round(float(v) * ds, 4) for v in tgt["size"]]
    if dyaw:
        tgt["yaw"] = round(float(tgt.get("yaw", 0.0)) + dyaw, 2)
    lo, hi = _render_box(tgt, r2r)
    if not _in_room(lo, hi, ctx):
        return None, "box leaves the room shell"
    before = collide.worst(state, ctx["fr"], only=edit["id"])
    after = collide.worst(new, ctx["fr"], only=edit["id"])
    b = before["ratio"] if before else 0.0
    a = after["ratio"] if after else 0.0
    if a > collide.RATIO_MAX and a > b + 1e-6:
        return None, (f'mesh collision with {after["b"] if after["a"] == edit["id"] else after["a"]}: '
                      f"ratio {a:.3f} (was {b:.3f}), > {collide.RATIO_MAX}")
    return new, None


# ---------------------------------------------------------------- add

def apply_add(sc, edit, state, sl, ctx, model):
    """Geometric checks, then the single-box C1–C5 chain (categories ->
    shortlist -> measure -> re-shortlist -> pick gate; no CLIP for a loop
    add — there is no detection crop, best fit wins). -> (new_state,
    (box_rec, pick_rec), reason)."""
    r2r = ctx["r2r"]
    size = [float(v) for v in edit["size"]]
    c_render = np.asarray(edit["center"], np.float64)
    if not all(ADD_AXIS_RANGE[0] <= v <= ADD_AXIS_RANGE[1] for v in size):
        return None, None, f"size outside {ADD_AXIS_RANGE} m"
    lo, hi = c_render - np.asarray(size) / 2, c_render + np.asarray(size) / 2
    if not _in_room(lo, hi, ctx):
        return None, None, "box leaves the room shell"
    label = edit["label"].strip().lower()
    mount = edit.get("mount", "floor")

    tier, cats = retrieve2.match_categories(label)
    if tier == 3:
        try:
            fix = retrieve2.map_labels_agent([label], model=model)
            cats, tier = [c.lower() for c in fix.get(label, [])], "agent"
        except Exception as e:
            return None, None, f"label map failed: {e}"
    if not cats:
        return None, None, "no catalog category for label"
    box = {"size": size}
    cands = retrieve2.shortlist_box(box, mount, cats)
    if not cands:
        return None, None, "no candidates"
    measure.ensure([c["uid"] for c in cands])
    sizes = measure.load_cache()
    for a in catalog():                    # refresh in place; by_category()
        m = sizes.get(a["uid"])            # holds the same row objects
        if m:
            a["size_yup_cm"] = m
    cands = retrieve2.shortlist_box(box, mount, cats)

    med = pick_policy.scene_median_scale(sl["boxes"])
    slo, shi = pick_policy.SCALE_BAND[0] * med, pick_policy.SCALE_BAND[1] * med
    adm = [c for c in cands
           if c["score"] <= pick_policy.FIT_CAP and slo <= c["scale"] <= shi]
    relaxed = not adm
    if relaxed:
        adm = sorted(cands, key=lambda c: c["score"])[:pick_policy.FALLBACK_N]
    w = adm[0]
    thumbs.ensure([(c["uid"], c["perm"]) for c in adm])

    gids = {e["group"] for e in state["objects"]}
    gid = next(f"add_{i:03d}" for i in range(1000) if f"add_{i:03d}" not in gids)
    c_raw = [round(float(v), 4) for v in c_render * r2r]
    new = json.loads(json.dumps(state))
    for i, (c, s) in enumerate(place2._sub_boxes(c_raw, size, w["axis"], w["k"])):
        new["objects"].append({"label": label, "group": gid, "part": i,
                               "uid": w["uid"], "category": w["category"],
                               "center": c, "size": s, "perm": w["perm"],
                               "scale": w["scale"], "mount": mount,
                               "source": "loop"})
    new_iids = {f"{gid}.{i}" for i in range(w["k"])}
    hit = collide.worst(new, ctx["fr"], only=new_iids)
    if hit and hit["ratio"] > collide.RATIO_MAX:
        other = hit["b"] if hit["a"] in new_iids else hit["a"]
        return None, None, (f"mesh collision with {other}: "
                            f'ratio {hit["ratio"]:.3f} > {collide.RATIO_MAX}')
    aabb = np.asarray(c_raw) - np.asarray(size) / 2, \
        np.asarray(c_raw) + np.asarray(size) / 2
    box_rec = {"id": gid, "label": label, "conf": None, "center": c_raw,
               "size": size,
               "aabb_min": [round(float(v), 4) for v in np.minimum(*aabb)],
               "aabb_max": [round(float(v), 4) for v in np.maximum(*aabb)],
               "views": [], "mount": mount, "match_tier": tier,
               "categories": cats, "candidates": adm, "source": "loop"}
    pick_rec = {"uid": w["uid"], "category": w["category"], "k": w["k"],
                "axis": w["axis"], "perm": w["perm"], "scale": w["scale"],
                "fit": w["score"], "clip": None, "clip_txt": None,
                "n_admissible": len(adm), "gate_relaxed": relaxed,
                "source": "loop",
                "alternates": [{"uid": c["uid"], "fit": c["score"],
                                "clip": None} for c in adm[1:5]]}
    return new, (box_rec, pick_rec), None


# ---------------------------------------------------------------- VLM

def _views(sc):
    """[(stem, cam, unit look dir, fov)] from the view sidecars (render frame)."""
    out = []
    for metaf in sorted(paths.views_dir(sc).glob("gpu_yaw*.json")):
        meta = json.loads(metaf.read_text())
        cam = [float(t) for t in meta["cam"].split(",")]
        look = [float(t) for t in meta["look"].split(",")]
        d = np.asarray(look) - np.asarray(cam)
        d = d / max(np.linalg.norm(d), 1e-9)
        out.append((metaf.stem, cam, [round(float(v), 2) for v in d],
                    meta["fov"]))
    return out


def ensure_targets(sc, loopdir):
    """The ORIGINAL splat renders as PNGs (webp -> png once)."""
    tg = {}
    for metaf in sorted(paths.views_dir(sc).glob("gpu_yaw*.json")):
        meta = json.loads(metaf.read_text())
        src = paths.views_dir(sc) / meta["file"]
        if not src.exists():
            continue
        dst = loopdir / f"target_{metaf.stem}.png"
        if not dst.exists():
            Image.open(src).convert("RGB").save(dst)
        tg[metaf.stem] = dst
    return tg


def _scene_summary(state, ctx, sc):
    lines = [f'Coordinate frame: meters, +y up, floor at y={ctx["floor"]:.2f}.',
             "Room bounds (axis-aligned): min "
             + str([round(float(v), 2) for v in ctx["room_lo"]]) + " max "
             + str([round(float(v), 2) for v in ctx["room_hi"]]) + ".",
             "Cameras (all views):"]
    for stem, cam, d, fov in _views(sc):
        lines.append(f"  {stem}: at {cam}, looking along {d}, fov {fov} deg")
    inst = [{"id": _iid(e), "label": e["label"], "category": e["category"],
             "center": [round(float(v), 2)
                        for v in np.asarray(e["center"]) * ctx["r2r"]],
             "size": [round(float(v), 2) for v in e["size"]],
             "yaw": e.get("yaw", 0.0), "mount": e["mount"]}
            for e in state["objects"]]
    lines.append("Placed instances (centers in this frame):")
    lines.append(json.dumps(inst))
    return "\n".join(lines)


def vlm_critique(sc, state, ctx, cur, targets, rejected, max_edits, model):
    pairs = "\n".join(
        f"- {stem}: ORIGINAL {targets[stem]} | RECREATION "
        + str(next(p for p in cur if stem in p.name))
        for stem in sorted(targets) if any(stem in p.name for p in cur))
    rej = ("\nPreviously REJECTED edits, with why. Do NOT re-propose one "
           "as-is; a corrected variant that addresses its reason IS "
           "allowed:\n" + json.dumps(rejected)) if rejected else ""
    prompt = f"""You are judging a 3D scene recreation. The ORIGINAL images are renders of a
Gaussian-splat scene. Each RECREATION image is a MESH-ONLY render of the
retrieved catalog assets from the SAME camera on a flat grey background — it
contains no original imagery at all. An object visible in the ORIGINAL with
no corresponding mesh in the RECREATION is missing (candidate "add"). Judge
the mesh arrangement (presence, position, size, orientation); ignore
texture/style mismatch, lighting, and the flat background.

Read every image with the Read tool, then compare each pair:
{pairs}

{_scene_summary(state, ctx, sc)}
{rej}
Propose AT MOST {max_edits} edits, most important first, from exactly these
two ops (all coordinates in the frame above):
- {{"op":"add","label":"<object>","center":[x,y,z],"size":[sx,sy,sz],
   "mount":"floor|wall|free","why":"..."}} — an object clearly present in the
  ORIGINAL views but missing from the RECREATION meshes. size = axis-aligned
  extents in meters; center y for a floor object ~ floor + sy/2.
- {{"op":"nudge","id":"<instance id>","dpos":[dx,dy,dz],"dyaw_deg":n,
   "dscale":n,"why":"..."}} — move/rotate/rescale ONE placed instance toward
  where the original shows it. Caps: each |dpos component| <=
  {NUDGE_DPOS_MAX} m, |dyaw_deg| <= {NUDGE_DYAW_MAX}, dscale
  {NUDGE_DSCALE[0]}..{NUDGE_DSCALE[1]}. Omit fields you don't change.
  A bigger correction takes multiple accepted nudges across iterations.

Propose an edit ONLY where the pair comparison clearly supports it; an empty
list is a valid answer. Reply with ONLY a JSON object:
{{"issues":[{{"view":"gpu_yaw000","kind":"missing|misplaced|wrong_size|other",
"detail":"..."}}],"edits":[...]}}"""
    iids = {_iid(e) for e in state["objects"]}

    def _val(r):
        if (not isinstance(r.get("edits"), list)
                or not isinstance(r.get("issues"), list)):
            raise ValueError('need {"issues":[...],"edits":[...]}')
        for ed in r["edits"]:
            if ed.get("op") == "add":
                if not (ed.get("label") and len(ed.get("center", [])) == 3
                        and len(ed.get("size", [])) == 3):
                    raise ValueError(f"bad add: {ed}")
            elif ed.get("op") == "nudge":
                if ed.get("id") not in iids:
                    raise ValueError(f'nudge id {ed.get("id")!r} not one of '
                                     f"{sorted(iids)}")
            else:
                raise ValueError(f'op must be add|nudge: {ed}')
    return call_agent_json(prompt, validate=_val, model=model, tag="critique")


def vlm_verify(edit, targets, before, after, model):
    rows = "\n".join(
        f"- {stem}: ORIGINAL {targets[stem]} | BEFORE "
        + str(next(p for p in before if stem in p.name)) + " | AFTER "
        + str(next(p for p in after if stem in p.name))
        for stem in sorted(targets)
        if any(stem in p.name for p in before)
        and any(stem in p.name for p in after))
    prompt = f"""A scene-recreation edit was applied. ORIGINAL is the target (a Gaussian-splat
render); BEFORE and AFTER are MESH-ONLY renders of the recreation (flat grey
background, no original imagery) around this single edit:

{json.dumps(edit)}

Read every image with the Read tool:
{rows}

Does AFTER match the ORIGINAL more closely than BEFORE? Judge only the mesh
arrangement (presence, position, size, orientation) — the edit's own object
first, collateral damage to the rest second. "better" ONLY if the match
clearly improved; when in doubt say "neutral".
Reply with ONLY: {{"verdict":"better|worse|neutral","why":"..."}}"""

    def _val(r):
        if r.get("verdict") not in ("better", "worse", "neutral"):
            raise ValueError('verdict must be better|worse|neutral')
    return call_agent_json(prompt, validate=_val, model=model, tag="verify")


# ---------------------------------------------------------------- loop

def _load_journal(f):
    rejected, last_it = {}, -1
    if f.exists():
        for line in f.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            last_it = max(last_it, r.get("iter", -1))
            if not r.get("accepted"):
                why = (r.get("reason") if not r.get("valid", True)
                       else f'verify said {r.get("verdict")}')
                rejected[r["key"]] = {"edit": r["edit"], "why": why}
            else:
                rejected.pop(r["key"], None)
    return rejected, last_it


def run(sc, max_iters=MAX_ITERS, max_edits=EDITS_PER_ITER, model="sonnet"):
    pkg = paths.package_dir(sc)
    loopdir = pkg / "loop"
    loopdir.mkdir(exist_ok=True)
    statef = pkg / "composed_state2.json"
    basef = pkg / "composed_state2_base.json"
    state = json.loads(statef.read_text())
    if not basef.exists():
        shutil.copy2(statef, basef)
        print(f"[loop] snapshotted base -> {basef.name}", flush=True)
    slf = pkg / "shortlists2.json"
    sl = json.loads(slf.read_text())
    picksf = pkg / "picks2.json"
    picks = json.loads(picksf.read_text())
    ctx = _ctx(sc)
    targets = ensure_targets(sc, loopdir)
    journalf = pkg / "edits.jsonl"
    rejected, last_it = _load_journal(journalf)
    calls = n_accepted = 0

    def journal(rec):
        with journalf.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

    for it in range(last_it + 1, last_it + 1 + max_iters):
        cur = place2.composite_views(sc, state, loopdir, f"it{it:02d}_cur_",
                                     splat_bg=False)
        crit = vlm_critique(sc, state, ctx, cur, targets,
                            list(rejected.values()), max_edits, model)
        calls += 1
        (loopdir / f"critique_it{it:02d}.json").write_text(
            json.dumps(crit, indent=1))
        print(f"[loop] iter {it}: {len(crit['issues'])} issues, "
              f"{len(crit['edits'])} proposed edits", flush=True)
        n_iter = n_reject_new = 0
        for j, edit in enumerate(crit["edits"][:max_edits]):
            key = edit_key(edit)
            if key in rejected:
                print(f"[loop]   skip (already rejected): {key}", flush=True)
                continue
            extras = None
            if edit["op"] == "nudge":
                new_state, reason = apply_nudge(edit, state, ctx)
            else:
                new_state, extras, reason = apply_add(sc, edit, state, sl,
                                                      ctx, model)
            if new_state is None:
                rejected[key] = {"edit": edit, "why": reason}
                n_reject_new += 1
                journal({"iter": it, "edit": edit, "key": key, "valid": False,
                         "reason": reason, "accepted": False})
                print(f"[loop]   INVALID {key}: {reason}", flush=True)
                continue
            after = place2.composite_views(sc, new_state, loopdir,
                                           f"it{it:02d}e{j}_", splat_bg=False)
            v = vlm_verify(edit, targets, cur, after, model)
            calls += 1
            accepted = v["verdict"] == "better"
            journal({"iter": it, "edit": edit, "key": key, "valid": True,
                     "verdict": v["verdict"], "why": v.get("why", ""),
                     "accepted": accepted,
                     "renders": [str(p) for p in after]})
            print(f"[loop]   {v['verdict'].upper():7s} {key}: "
                  f"{v.get('why', '')[:80]}", flush=True)
            if accepted:
                state, cur, n_iter = new_state, after, n_iter + 1
                n_accepted += 1
                statef.write_text(json.dumps(state, indent=1))
                if extras:
                    box_rec, pick_rec = extras
                    sl["boxes"].append(box_rec)
                    slf.write_text(json.dumps(sl, indent=1))
                    picks[box_rec["id"]] = pick_rec
                    picksf.write_text(json.dumps(picks, indent=1))
            else:
                rejected[key] = {"edit": edit,
                                 "why": f'verify said {v["verdict"]}'}
                n_reject_new += 1
            if calls >= MAX_VLM_CALLS:
                break
        if (n_iter == 0 and n_reject_new == 0) or calls >= MAX_VLM_CALLS:
            # an all-rejected iteration still continues: the fresh reasons
            # feed the next critique, which may propose corrected variants
            print(f"[loop] stopping: "
                  + ("VLM call cap" if calls >= MAX_VLM_CALLS
                     else "iteration produced nothing new"), flush=True)
            break
    if n_accepted:
        place2.composite_views(sc, state)     # canonical composed2_view_*
        place2.export_glb(sc, state)
    print(f"[loop] done: {n_accepted} accepted edits, {calls} VLM calls, "
          f"journal {journalf}", flush=True)
    return state


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--max-iters", type=int, default=MAX_ITERS)
    ap.add_argument("--max-edits", type=int, default=EDITS_PER_ITER)
    ap.add_argument("--model", default="sonnet")
    args = ap.parse_args()
    run(args.scene, max_iters=args.max_iters, max_edits=args.max_edits,
        model=args.model)
