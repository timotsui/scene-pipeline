"""
Step 3 -- appearance-pass: VLM-describe every DETECTION node's image crops.

Fills the `appearance` block of the 103 detection nodes (88 object + 15
detection-architecture) in out/<scene>/scene_graph.json. The 6 envelope
arch_* nodes are skipped -- they have no pixels to describe. This is the
genuinely NEW semantic extraction of graph v1 (PLAN_SCENE_GRAPH.md Step 3).

DESIGN DECISION (documented per plan): crop-making is FOLDED INTO this module
(no separate make_crops.py) -- crops and descriptions share the node->evidence
mapping and the cache key is (node id + crop hash), so one module owns both.

CROPS
  Source: analyzer/job_high/interactions.json `objects[idx].frames` -- the
  analyzer's own per-evidence 2D detection boxes; node ana_NNN maps to
  objects[NNN] (verified: 0/103 label mismatches on bedroom_marble). Top-K
  (K=3) frames by 2D box area (tie-break: higher det score, lower frame_idx;
  frame_idx deduped), cropped from job_high/frames/frame_XXXX.png with a
  small margin (8% of the larger box side, clamped 4..20 px).
  DOCUMENTED DEVIATION from plain top-K-by-area: evidence is first filtered
  to det score >= 0.5 * the node's own peak evidence score (backfilled by
  area if fewer than K survive). Reason (numeric, found during the smoke
  test): several nodes' LARGEST boxes are their LOWEST-score detections
  (ana_101 desk lamp: biggest box scored 0.235 vs peak 0.677) -- pure area
  ranking prefers junk detections over confident ones. Crops whose
  longer side is < 160 px are LANCZOS-upscaled to ~320 px so the VLM has
  usable pixels (recorded per crop as "upscale").
  Saved to out/<scene>/graph/crops/<node_id>_<k>.png. Node gets
  views.best_crop = absolute path of crop 0 and views.crops = per-crop
  metadata. The 3D-box-projection fallback from the plan was NOT implemented:
  every one of the 103 bedroom_marble nodes has usable analyzer 2D boxes.

VLM ROUTE
  claude.exe (Claude Code CLI, subscription -- the project's established
  bridge pattern, same as the TreeSearchGen backend swap; NO new API keys):
      claude -p "<prompt>" --model sonnet
  run non-interactively with cwd = the crops dir; crop images are referenced
  by absolute path in the prompt and claude reads them itself.
  KNOWN GOTCHA (project memory): a stale User-level ANTHROPIC_API_KEY env var
  hijacks claude.exe onto API billing. This module ALWAYS strips
  ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN from the child environment.

BATCHING + CONTRACT
  ~7 nodes per call, up to 2 crops attached per node (3rd crop stays on disk
  for the review page). Per node the VLM must return STRICT JSON:
    {"id": "...", "colors": [...], "material": "...", "style": "...",
     "description": "one sentence, plain language", "is_label": true/false}
  is_label answers "does this crop actually show a <detector label>?" and is
  stored on the node as appearance.label_agreement (false => a label dispute
  for the report). Malformed / missing entries: the affected nodes are
  retried ONCE in a fresh, firmer call; still-failing nodes get
  appearance: null + "appearance_vlm_failed": true (nothing fabricated).

WRITE-BACK (additive-only)
  scene_graph.json is re-serialized with json.dumps(indent=1) -- byte-
  identical to what build_graph/build_edges wrote, apart from the fields this
  module owns: per-node `appearance` (+ `appearance_vlm_failed` on failures),
  views.best_crop / views.crops, and top-level `appearance_meta`
  (model, dates, cumulative call/failure counts).

CACHE / IDEMPOTENCY
  out/<scene>/graph/appearance_cache.json, keyed by node id, each entry
  storing the sha256 over that node's crop PNG bytes. Reruns re-cut crops
  (deterministic bytes), then skip every node whose crop hash matches a
  cached SUCCESS. Failures are NOT cached -- reruns retry them. Cumulative
  call counts live in the cache's meta block so appearance_meta survives
  cache-hit-only reruns unchanged.

Run:
  python graph/describe_nodes.py --scene bedroom_marble              # full pass
  python graph/describe_nodes.py --scene bedroom_marble --crops-only # no VLM
  python graph/describe_nodes.py --scene bedroom_marble --smoke      # 1-node route check, no write-back
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402

BATCH_SIZE = 7
MAX_CROPS_SAVED = 3      # crops written to disk per node
MAX_CROPS_ATTACHED = 2   # crops referenced in the VLM prompt per node
UPSCALE_IF_BELOW = 160   # px, longer side
UPSCALE_TARGET = 320     # px, longer side after upscale
CALL_TIMEOUT_S = 480
MODEL = "sonnet"

REQUIRED_KEYS = {"id", "colors", "material", "style", "description",
                 "is_label"}


# --------------------------------------------------------------------------
# crops
# --------------------------------------------------------------------------

def pick_evidence(frames):
    """Top-K 2D boxes by area AMONG score >= 0.5*peak evidence (see
    docstring deviation note); backfill by area; dedupe frame_idx."""
    key = lambda f: (-(f["box"][2] - f["box"][0]) * (f["box"][3] - f["box"][1]),
                     -f.get("score", 0.0), f["frame_idx"])
    peak = max((f.get("score", 0.0) for f in frames), default=0.0)
    strong = sorted((f for f in frames
                     if f.get("score", 0.0) >= 0.5 * peak), key=key)
    rest = sorted((f for f in frames
                   if f.get("score", 0.0) < 0.5 * peak), key=key)
    seen, ranked = set(), []
    for f in strong + rest:
        if f["frame_idx"] in seen:
            continue
        seen.add(f["frame_idx"])
        ranked.append(f)
        if len(ranked) == MAX_CROPS_SAVED:
            break
    return ranked


def cut_crops(node, inter_obj, frames_dir, crops_dir):
    """Cut, save, and describe (metadata-wise) this node's crops."""
    metas = []
    for k, ev in enumerate(pick_evidence(inter_obj.get("frames", []))):
        fidx = ev["frame_idx"]
        x1, y1, x2, y2 = ev["box"]
        src = frames_dir / f"frame_{fidx:04d}.png"
        im = Image.open(src).convert("RGB")
        W, H = im.size
        m = min(20.0, max(4.0, 0.08 * max(x2 - x1, y2 - y1)))
        cx1 = max(0, int(round(x1 - m)))
        cy1 = max(0, int(round(y1 - m)))
        cx2 = min(W, int(round(x2 + m)))
        cy2 = min(H, int(round(y2 + m)))
        crop = im.crop((cx1, cy1, cx2, cy2))
        upscale = None
        if max(crop.size) < UPSCALE_IF_BELOW and max(crop.size) > 0:
            f = UPSCALE_TARGET / max(crop.size)
            crop = crop.resize((max(1, round(crop.size[0] * f)),
                                max(1, round(crop.size[1] * f))),
                               Image.LANCZOS)
            upscale = round(f, 2)
        out = crops_dir / f"{node['id']}_{k}.png"
        crop.save(out)
        metas.append({
            "path": str(out),
            "frame_idx": fidx,
            "box_2d": [round(v, 1) for v in ev["box"]],
            "det_score": round(ev.get("score", 0.0), 4),
            "area_px": round((x2 - x1) * (y2 - y1)),
            "upscale": upscale,
        })
    return metas


def crop_hash(metas):
    h = hashlib.sha256()
    for m in metas:
        h.update(Path(m["path"]).read_bytes())
    return h.hexdigest()[:32]


# --------------------------------------------------------------------------
# VLM bridge (claude.exe, subscription -- NO API key)
# --------------------------------------------------------------------------

def claude_env():
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(k, None)  # the stale-API-key hijack gotcha (project memory)
    return env


def call_claude(prompt, cwd):
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("[appearance] claude.exe not on PATH")
    r = subprocess.run([exe, "-p", prompt, "--model", MODEL],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=claude_env(), cwd=str(cwd),
                       timeout=CALL_TIMEOUT_S)
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if r.returncode != 0:
        raise RuntimeError(f"claude exit {r.returncode}: {err[:400] or out[:400]}")
    low = (out + " " + err).lower()
    for bad in ("invalid_api_key", "authentication_error", "credit balance"):
        if bad in low:
            raise RuntimeError(f"claude API-billing/auth error: {out[:400]}")
    return out


def batch_prompt(batch, firm=False):
    lines = []
    if firm:
        lines.append(
            "Your previous response was malformed. Follow the format EXACTLY "
            "this time: output ONLY one fenced ```json code block containing "
            "a JSON array, nothing else -- no prose before or after.")
    lines += [
        "You are describing image crops of objects detected in a 3D indoor "
        "scene reconstruction (a bedroom). For EACH numbered item below, "
        "open and look at its crop image file(s) (absolute paths given), "
        "then return one JSON object.",
        "",
        "Return ONE fenced ```json block containing a JSON ARRAY with "
        "EXACTLY one object per item, in the same order, each of the form:",
        '{"id": "<the id given>", "colors": ["dominant color words"], '
        '"material": "best guess, e.g. wood/fabric/metal/ceramic", '
        '"style": "a few words, e.g. modern minimal", '
        '"description": "ONE sentence, plain language, e.g. \'white '
        "articulated desk lamp with a rounded shade'\", "
        '"is_label": true or false}',
        "",
        '"is_label": answer honestly -- does the crop actually show the '
        "detector's label for that item? false if it clearly shows something "
        "else.",
        "Crops are small and low-resolution renders; describe only what you "
        "can actually see, do NOT invent detail you cannot see.",
        "Output ONLY the fenced JSON block.",
        "",
    ]
    for i, b in enumerate(batch, 1):
        lines.append(f'Item {i}: id={b["id"]}, detector label="{b["label"]}", '
                     f'crop file(s):')
        for m in b["crops"][:MAX_CROPS_ATTACHED]:
            lines.append(f'  {m["path"]}')
    return "\n".join(lines)


def parse_response(text, want_ids):
    """Extract the JSON array; return {id: entry} for valid entries only."""
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    raw = m.group(1) if m else None
    if raw is None:
        i = text.find("[")
        if i >= 0:
            try:
                arr, _ = json.JSONDecoder().raw_decode(text[i:])
                raw = json.dumps(arr)
            except ValueError:
                raw = None
    if raw is None:
        return {}
    try:
        arr = json.loads(raw)
    except ValueError:
        return {}
    if not isinstance(arr, list):
        return {}
    good = {}
    for e in arr:
        if not isinstance(e, dict) or not REQUIRED_KEYS.issubset(e):
            continue
        if e["id"] not in want_ids:
            continue
        if not (isinstance(e["colors"], list) and e["colors"]
                and all(isinstance(c, str) for c in e["colors"])):
            continue
        if not all(isinstance(e[k], str) and e[k].strip()
                   for k in ("material", "style", "description")):
            continue
        if not isinstance(e["is_label"], bool):
            continue
        good[e["id"]] = {
            "colors": [c.strip().lower() for c in e["colors"]],
            "material": e["material"].strip(),
            "style": e["style"].strip(),
            "description": e["description"].strip(),
            "label_agreement": e["is_label"],
        }
    return good


# --------------------------------------------------------------------------
# main pass
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    ap.add_argument("--crops-only", action="store_true")
    ap.add_argument("--smoke", action="store_true",
                    help="one-node route check; no write-back, no cache")
    args = ap.parse_args()
    scene = args.scene

    sdir = paths.scene_dir(scene)
    graph_path = sdir / "scene_graph.json"
    frames_dir = sdir / "analyzer" / "job_high" / "frames"
    gdir = sdir / "graph"
    crops_dir = gdir / "crops"
    cache_path = gdir / "appearance_cache.json"
    crops_dir.mkdir(parents=True, exist_ok=True)

    graph = json.loads(graph_path.read_text())
    inter = json.loads(
        (sdir / "analyzer" / "job_high" / "interactions.json").read_text())
    objs = inter["objects"]

    det_nodes = [n for n in graph["nodes"] if n.get("source") == "detection"]
    print(f"[appearance] {len(det_nodes)} detection nodes "
          f"({sum(1 for n in det_nodes if n['type']=='object')} object + "
          f"{sum(1 for n in det_nodes if n['type']=='architecture')} arch); "
          f"skipping {len(graph['nodes']) - len(det_nodes)} envelope nodes")

    # ---- crops (always refreshed; deterministic bytes) ----
    work = []  # {id,label,node,crops,hash}
    for n in det_nodes:
        idx = int(n["id"].split("_")[1])
        o = objs[idx]
        assert o["label"] == n["label"], f"{n['id']} label drift"
        metas = cut_crops(n, o, frames_dir, crops_dir)
        if not metas:
            print(f"[appearance] WARNING {n['id']} has no usable 2D boxes")
            continue
        n["views"]["best_crop"] = metas[0]["path"]
        n["views"]["crops"] = metas
        work.append({"id": n["id"], "label": n["label"], "node": n,
                     "crops": metas, "hash": crop_hash(metas)})
    print(f"[appearance] crops written for {len(work)} nodes -> {crops_dir}")
    if args.crops_only:
        graph_path.write_text(json.dumps(graph, indent=1))
        print("[appearance] crops-only: views.* written back, no VLM pass")
        return

    if args.smoke:
        w = next((x for x in work if x["id"] == "ana_101"), work[0])
        prompt = batch_prompt([w])
        print(f"[appearance] SMOKE call: {w['id']} ({w['label']}), "
              f"{min(len(w['crops']), MAX_CROPS_ATTACHED)} crop(s)")
        out = call_claude(prompt, crops_dir)
        print("---- raw claude output ----")
        print(out)
        print("---- parsed ----")
        print(json.dumps(parse_response(out, {w["id"]}), indent=1))
        return

    # ---- cache ----
    cache = {"meta": {"model": MODEL, "vlm_calls": 0, "retry_calls": 0,
                      "first_date": None, "last_date": None},
             "nodes": {}}
    if cache_path.exists():
        cache = json.loads(cache_path.read_text())

    todo, cached = [], 0
    for w in work:
        c = cache["nodes"].get(w["id"])
        if c and c.get("crop_hash") == w["hash"] and c.get("appearance"):
            w["node"]["appearance"] = c["appearance"]
            w["node"].pop("appearance_vlm_failed", None)
            cached += 1
        else:
            todo.append(w)
    print(f"[appearance] cache: {cached} hits, {len(todo)} to describe")

    # ---- batched VLM calls ----
    calls = retries = 0
    failed_ids = []
    today = date.today().isoformat()
    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i:i + BATCH_SIZE]
        want = {b["id"] for b in batch}
        print(f"[appearance] batch {i//BATCH_SIZE + 1}: "
              f"{', '.join(sorted(want))}", flush=True)
        try:
            got = parse_response(call_claude(batch_prompt(batch), crops_dir),
                                 want)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            print(f"[appearance]   call FAILED: {e}")
            got = {}
        calls += 1
        missing = [b for b in batch if b["id"] not in got]
        if missing:
            print(f"[appearance]   retrying {len(missing)} malformed/missing")
            try:
                got.update(parse_response(
                    call_claude(batch_prompt(missing, firm=True), crops_dir),
                    {b["id"] for b in missing}))
            except (RuntimeError, subprocess.TimeoutExpired) as e:
                print(f"[appearance]   retry FAILED: {e}")
            calls += 1
            retries += 1
        for b in batch:
            n = b["node"]
            if b["id"] in got:
                n["appearance"] = got[b["id"]]
                n.pop("appearance_vlm_failed", None)
                cache["nodes"][b["id"]] = {
                    "crop_hash": b["hash"], "appearance": got[b["id"]],
                    "model": MODEL, "date": today}
            else:
                n["appearance"] = None
                n["appearance_vlm_failed"] = True
                failed_ids.append(b["id"])
        # persist cache after every batch (interruption-safe)
        m = cache["meta"]
        m["vlm_calls"] = m.get("vlm_calls", 0) + (2 if missing else 1)
        m["retry_calls"] = m.get("retry_calls", 0) + (1 if missing else 0)
        m["first_date"] = m.get("first_date") or today
        m["last_date"] = today
        cache_path.write_text(json.dumps(cache, indent=1))

    # ---- write-back ----
    described = [w for w in work if w["node"].get("appearance")]
    disputes = [w for w in described
                if w["node"]["appearance"]["label_agreement"] is False]
    graph["appearance_meta"] = {
        "step": "Step 3 -- appearance-pass (graph/describe_nodes.py)",
        "model": f"claude.exe -p --model {MODEL} (Claude Code CLI, "
                 f"subscription bridge; ANTHROPIC_API_KEY stripped from "
                 f"child env)",
        "date": cache["meta"].get("last_date"),
        "vlm_calls": cache["meta"].get("vlm_calls", 0),
        "retry_calls": cache["meta"].get("retry_calls", 0),
        "described": len(described),
        "failed": len(work) - len(described),
        "label_disputes": len(disputes),
        "skipped_envelope_nodes": len(graph["nodes"]) - len(det_nodes),
        "cache": str(cache_path),
        "crops_dir": str(crops_dir),
    }
    graph_path.write_text(json.dumps(graph, indent=1))

    # ---- numeric sanity report ----
    print(f"\n[appearance] wrote {graph_path}")
    print(f"[appearance] this run: {calls} calls ({retries} retry calls), "
          f"{cached} cache hits, {len(failed_ids)} failures "
          f"{failed_ids if failed_ids else ''}")
    tiers = {}
    for w in work:
        t = w["node"]["confidence_tier"]
        ok = 1 if w["node"].get("appearance") else 0
        d = tiers.setdefault(t, [0, 0])
        d[0] += ok
        d[1] += 1
    for t, (ok, tot) in sorted(tiers.items()):
        print(f"[appearance]   tier {t:<10} described {ok}/{tot}")
    print(f"[appearance] label disputes ({len(disputes)}):")
    for w in disputes:
        print(f"[appearance]   {w['id']:<8} detector said {w['label']!r} but "
              f"VLM: {w['node']['appearance']['description']!r}")


if __name__ == "__main__":
    main()
