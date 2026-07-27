"""
Pass 2 -- JUDGE, sub-pass J6 (v3): the single TERMINAL pass --
J4-FLAG RESOLUTION + APPEARANCE together (PLAN_SCENE_GRAPH.md 0a.8).

v3 (user ruling 2026-07-26 late, supersedes the revoked closure loop):
J1-J5 unchanged, J4 runs ONCE, and THIS module consumes J4's flag
queues in the same single invocation that describes appearance:

  PHASE A -- resolution (donor code: graph/judge_cases.py, proven on
    bedroom_marble): existence flags -> REAL / NOT_REAL / UNCLEAR from
    crops; rename flags (+ any pixel doubts) -> short name from crops;
    edge re-examine flags -> CONFIRM / REJECT / REINTERPRET +
    suspect_box. All resolution calls run CONCURRENTLY.
  PHASE B -- appearance (v2 machinery below, unchanged): contact-sheet
    description of every shipping cluster under its FINAL post-phase-A
    name (the name-salted cache re-describes exactly the renamed /
    newly-confirmed ones).

Runs ONCE. Whatever phase A leaves unsettled (UNCLEAR existence,
low-confidence flags) SHIPS with the graph as placement-stage work
orders. There is NO re-scan after this pass.

`--sheets-only` builds BOTH phases' contact sheets + verbatim prompts
with zero model calls (standing review-first rule). NOTE: in that mode
phase B sheets show pre-resolution names (renames happen live).

--------------------------------------------------------------------------
v2 docstring (appearance machinery, still accurate) follows.
--------------------------------------------------------------------------
Pass 2 -- JUDGE, sub-pass J6 (v2): APPEARANCE per judged cluster.

v2 REWORK (2026-07-26, PLAN_SCENE_GRAPH.md 0a.7 J6 + 3a). v1 described
the 103 analyzer-seeded ana_XXX nodes from analyzer frames (25-30 min/
scene: the CLI opened 6-8 crop images as SEQUENTIAL model turns). Gone:
the analyzer seeding is deprecated, the record already carries member
crops, and the judged view is the thing worth describing. v1's output
survives archived in scene_graph_v1.json; the old ana-keyed cache is
retired (ids AND crops changed -- nothing to carry over).

WHAT v2 DOES
  Describes every NON-DISPUTED judged cluster (merged objects described
  ONCE under their canonical post-J3 name; the existence-disputed set is
  skipped -- no describing objects that probably don't exist). Fields
  per cluster: colors / material / style / one-sentence description /
  is_label (does the image actually show a "<canonical name>"?).

CONTACT SHEETS (the 3a fix #1)
  Per batch of BATCH_SIZE clusters, the member crops (top
  CROPS_PER_CLUSTER by detector score, at most one per member for
  merged clusters) are composited into ONE numbered grid PNG:
  out/<scene>/graph/appearance_sheets/sheet_NNN.png -- tile labels
  "3a"/"3b" match the prompt's item list. One call = ONE image read
  (~3x), plus CONCURRENCY parallel calls (3a fix #2) => est. 2-4 min
  per scene instead of ~30. Sheets are deterministic (sorted clusters,
  fixed layout) and are themselves the review artifact.

REVIEW-FIRST: `--sheets-only` builds every sheet + writes
  appearance_sheets/sheets_manifest.json + prints the batch-1 prompt,
  and makes NO model calls -- the user eyeballs what the judge would
  see before any spend (user request 2026-07-26).

PROMPT SCHEMA: fixed versioned template, deterministic fill,
PROMPT_VERSION salted into the per-cluster cache hash (the judge_near
v2 lesson). Bridge: claude.exe subscription, API-key env stripped,
strict fenced-JSON, malformed -> one firmer retry. Degradation:
failures keep appearance null + appearance_vlm_failed: true -- nothing
fabricated.

WRITE-BACK (additive-only): appearance blocks on graph["judged"] nodes
+ judged.appearance_meta. The record layer is never touched.
Cache: out/<scene>/graph/appearance_cache_v2.json, keyed by cluster id,
hash over PROMPT_VERSION + that cluster's own crop bytes + its
canonical name (batch composition does NOT invalidate neighbors).

Run:
  python graph/describe_nodes.py --scene bedroom_marble --sheets-only
  python graph/describe_nodes.py --scene bedroom_marble
  python graph/describe_nodes.py --scene bedroom_marble --smoke  # 1 batch
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

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402

MODEL = "sonnet"
CALL_TIMEOUT_S = 480
CONCURRENCY = 3
BATCH_SIZE = 8
CROPS_PER_CLUSTER = 2
TILE = 256                 # px, square cell for each crop
LABEL_H = 22               # px, label strip under each cell
SHEET_COLS = 4
PROMPT_VERSION = "2"

REQUIRED_KEYS = {"id", "colors", "material", "style", "description",
                 "is_label"}

TEMPLATE = """\
{firm}You are describing objects detected in a 3D indoor-scene \
reconstruction. Open and look at this contact sheet image (a numbered \
grid of small evidence crops):
  {sheet}
Tile labels like "3a"/"3b" mean: crop a/b of item 3. Crops are small, \
low-resolution renders -- describe only what you can actually see, do \
NOT invent detail.

For EACH numbered item below, look at its tiles and return one JSON \
object. "is_label": answer honestly -- do the tiles actually show a \
"<name>" as given? false if they clearly show something else.

Return ONE fenced ```json block containing a JSON ARRAY with EXACTLY \
one object per item, in the same order:
{{"id": "<the id given>", "colors": ["dominant color words"], \
"material": "best guess, e.g. wood/fabric/metal/ceramic", \
"style": "a few words, e.g. modern minimal", \
"description": "ONE sentence, plain language", \
"is_label": true or false}}
Output ONLY the fenced JSON block.

{items}"""

FIRM_PREFIX = ("Your previous response was malformed. This time output "
               "ONLY one fenced ```json code block containing the JSON "
               "array, no prose.\n\n")


# --------------------------------------------------------------------------
# crop selection + contact sheets (deterministic)
# --------------------------------------------------------------------------

def cluster_crops(jn, det, crops_dir):
    """Top crops for a cluster: best-scoring crop of each member first
    (diversity for merged clusters), then next-best overall; cap
    CROPS_PER_CLUSTER. Deterministic ordering."""
    per_member, rest = [], []
    for mid in sorted(jn["members"]):
        ms = sorted(det[mid]["evidence"].get("members", []),
                    key=lambda m: (-m.get("score", 0.0), m.get("member", 0)))
        found_first = False
        for m in ms:
            p = crops_dir / m.get("crop", "")
            if not m.get("crop") or not p.exists():
                continue
            entry = (round(-m.get("score", 0.0), 4), m.get("member", 0), p)
            if not found_first:
                per_member.append(entry)
                found_first = True
            else:
                rest.append(entry)
    per_member.sort()
    rest.sort()
    out = [p for _, _, p in per_member[:CROPS_PER_CLUSTER]]
    for _, _, p in rest:
        if len(out) >= CROPS_PER_CLUSTER:
            break
        out.append(p)
    return out


def build_sheet(batch, sheet_path):
    """batch: [(jn, [crop paths])]. One numbered grid PNG; returns the
    tile-label map {cluster_id: ["1a", "1b"]}."""
    tiles = []
    tile_map = {}
    for i, (jn, crops) in enumerate(batch, 1):
        labels = []
        for k, p in enumerate(crops):
            lab = f"{i}{'abcdef'[k]}"
            labels.append(lab)
            tiles.append((lab, p))
        tile_map[jn["id"]] = labels
    cols = SHEET_COLS
    rows = (len(tiles) + cols - 1) // cols
    W = cols * TILE
    H = rows * (TILE + LABEL_H)
    sheet = Image.new("RGB", (W, H), (245, 245, 245))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 15)
    except OSError:
        font = ImageFont.load_default()
    for idx, (lab, p) in enumerate(tiles):
        r, c = divmod(idx, cols)
        x0, y0 = c * TILE, r * (TILE + LABEL_H)
        im = Image.open(p).convert("RGB")
        f = min(TILE / im.width, TILE / im.height)
        im = im.resize((max(1, round(im.width * f)),
                        max(1, round(im.height * f))), Image.LANCZOS)
        sheet.paste(im, (x0 + (TILE - im.width) // 2,
                         y0 + (TILE - im.height) // 2))
        draw.rectangle([x0, y0 + TILE, x0 + TILE, y0 + TILE + LABEL_H],
                       fill=(20, 20, 20))
        draw.text((x0 + 8, y0 + TILE + 3), lab, fill=(255, 255, 100),
                  font=font)
        draw.rectangle([x0, y0, x0 + TILE - 1, y0 + TILE + LABEL_H - 1],
                       outline=(180, 180, 180))
    sheet.save(sheet_path)
    return tile_map


def cluster_hash(jn, crops):
    h = hashlib.sha256()
    h.update(PROMPT_VERSION.encode())
    h.update(jn["name"].encode())
    for p in crops:
        h.update(Path(p).read_bytes())
    return h.hexdigest()[:32]


def item_block(i, jn, tile_labels, floor_y):
    g = jn["geometry"]
    s = g["size"]
    bottom = floor_y - g["aabb_max"][1]
    return (f'Item {i}: id={jn["id"]}, name="{jn["name"]}", tiles: '
            f'{", ".join(tile_labels)} -- '
            f'{s[0]:.2f}x{s[2]:.2f}x{s[1]:.2f} m, bottom {bottom:.2f} m '
            f'above the floor')


# --------------------------------------------------------------------------
# claude bridge (project pattern)
# --------------------------------------------------------------------------

def claude_env():
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(k, None)  # stale-API-key hijack gotcha (project memory)
    return env


def call_claude(prompt, cwd, model):
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("[appearance] claude.exe not on PATH")
    r = subprocess.run([exe, "-p", prompt, "--model", model],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=claude_env(), cwd=str(cwd),
                       timeout=CALL_TIMEOUT_S)
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if r.returncode != 0:
        raise RuntimeError(f"claude exit {r.returncode}: "
                           f"{err[:400] or out[:400]}")
    low = (out + " " + err).lower()
    for bad in ("invalid_api_key", "authentication_error", "credit balance"):
        if bad in low:
            raise RuntimeError(f"claude API-billing/auth error: {out[:400]}")
    return out


def parse_response(text, want_ids):
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
        good[e["id"]] = {"colors": e["colors"],
                         "material": e["material"].strip(),
                         "style": e["style"].strip(),
                         "description": e["description"].strip(),
                         "label_agreement": bool(e["is_label"])}
    return good


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--concurrency", type=int, default=CONCURRENCY)
    ap.add_argument("--sheets-only", action="store_true",
                    help="build contact sheets + manifest + sample prompt; "
                         "NO model calls, no write-back")
    ap.add_argument("--smoke", action="store_true", help="1 batch only")
    args = ap.parse_args()

    gdir = paths.scene_dir(args.scene)
    gpath = gdir / "scene_graph.json"
    crops_dir = gdir / "graph" / "crops"
    sheets_dir = gdir / "graph" / "appearance_sheets"
    cache_path = gdir / "graph" / "appearance_cache_v2.json"
    graph = json.loads(gpath.read_text())
    judged = graph.get("judged")
    if not judged:
        raise SystemExit("[appearance] no judged view -- run "
                         "build_judged.py first")
    det = {n["id"]: n for n in graph["nodes"] if n["source"] == "detection"}
    floor_y = next(n for n in graph["nodes"] if n["id"] == "arch_floor")[
        "geometry"]["plane"]["value_raw"]

    # ================= PHASE A -- resolve J4's flags (once) =============
    import judge_cases as jc
    jn_by_id = {jn["id"]: jn for jn in judged["nodes"]}
    flags = judged.get("coherence_flags", [])
    case_sheets = gdir / "graph" / "case_sheets"
    case_cache_path = gdir / "graph" / "judge_cases_cache.json"
    case_cache = (json.loads(case_cache_path.read_text())
                  if case_cache_path.exists()
                  else {"meta": {"calls": 0}, "cases": {}})

    q_exist = []
    for jn in sorted(judged["nodes"], key=lambda n: n["id"]):
        if jn.get("existence") != "disputed":
            continue
        f = next((f for f in flags
                  if f["target"].split("->")[0] == jn["id"]
                  and f["suggested_action"] == "existence_disputed"), None)
        q_exist.append((jn, f))
    doubts = {}
    for f in flags:
        if f["suggested_action"] == "rename_candidate" \
                and f["target"] in jn_by_id:
            doubts.setdefault(f["target"], []).append(
                "plausibility check: " + f["issue"])
    q_rename = [(jn_by_id[i], doubts[i]) for i in sorted(doubts)
                if jn_by_id[i].get("existence") != "disputed"
                and jn_by_id[i].get("naming", {}).get("source")
                != "judge_cases"]
    q_reex = []
    for f in flags:
        if f["suggested_action"] != "reexamine_with_crops":
            continue
        ids = [x for x in f["target"].split("->") if x in jn_by_id]
        if len(ids) == 2:
            q_reex.append((f, ids))

    print(f"[j6/cases] queues: existence {len(q_exist)}, rename "
          f"{len(q_rename)}, re-examine {len(q_reex)}")
    case_jobs = []
    if q_exist or q_rename or q_reex:
        case_sheets.mkdir(parents=True, exist_ok=True)
    if q_exist:
        tiles, items = [], []
        for i, (jn, f) in enumerate(q_exist, 1):
            crops = jc.cluster_all_crops(jn, det, crops_dir,
                                         jc.CROPS_EXIST)
            labs = []
            for k, p in enumerate(crops):
                lab = f"{i}{'abc'[k]}"
                labs.append(lab)
                tiles.append((lab, p))
            items.append(
                f'Case {i}: id={jn["id"]}, currently named '
                f'"{jn["name"]}", tiles {", ".join(labs)} -- '
                f'{jc.facts(jn, floor_y)}.\n'
                f'  why doubted: {f["issue"] if f else "?"}\n'
                f'  hypotheses: '
                f'{"; ".join(f["hypotheses"]) if f else "?"}')
        sheet = case_sheets / "cases_existence.png"
        jc.build_sheet(tiles, sheet)
        case_jobs.append(("existence", jc.T_EXIST, sheet,
                          "\n\n".join(items), q_exist))
    if q_rename:
        tiles, items = [], []
        for i, (jn, why) in enumerate(q_rename, 1):
            crops = jc.cluster_all_crops(jn, det, crops_dir,
                                         jc.CROPS_RENAME)
            labs = []
            for k, p in enumerate(crops):
                lab = f"{i}{'ab'[k]}"
                labs.append(lab)
                tiles.append((lab, p))
            items.append(
                f'Item {i}: id={jn["id"]}, current name "{jn["name"]}", '
                f'tiles {", ".join(labs)} -- {jc.facts(jn, floor_y)}.\n'
                + "\n".join(f"  doubt: {w}" for w in why))
        sheet = case_sheets / "cases_rename.png"
        jc.build_sheet(tiles, sheet)
        case_jobs.append(("rename", jc.T_RENAME, sheet,
                          "\n\n".join(items), q_rename))
    for si in range(0, len(q_reex), 4):
        chunk = q_reex[si:si + 4]
        tiles, items = [], []
        for ci, (f, (ida, idb)) in enumerate(chunk, 1):
            n = si + ci
            ja, jb = jn_by_id[ida], jn_by_id[idb]
            for side, jn in (("A", ja), ("B", jb)):
                labs = []
                crops = jc.cluster_all_crops(jn, det, crops_dir,
                                             jc.CROPS_REEX)
                for k, p in enumerate(crops):
                    lab = f"{n}{side}-{'ab'[k]}"
                    labs.append(lab)
                    tiles.append((lab, p))
                if side == "A":
                    la = labs
                else:
                    lb = labs
            items.append(
                f'Case {n}: recorded fact: {f["issue"]}\n'
                f'  A = {ida} "{ja["name"]}", tiles {", ".join(la)} -- '
                f'{jc.facts(ja, floor_y)}\n'
                f'  B = {idb} "{jb["name"]}", tiles {", ".join(lb)} -- '
                f'{jc.facts(jb, floor_y)}')
        sheet = case_sheets / f"cases_reexamine_{si // 4 + 1}.png"
        jc.build_sheet(tiles, sheet)
        case_jobs.append(("reexamine", jc.T_REEX, sheet,
                          "\n\n".join(items), chunk))

    if args.sheets_only:
        for kind, tmpl, sheet, items, _ in case_jobs:
            print(f"\n[j6/cases] ===== {kind} prompt ({sheet}) =====")
            print(tmpl.format(firm="", sheet=sheet, items=items))
    elif case_jobs:
        def run_case(job):
            kind, tmpl, sheet, items, cases_q = job
            for attempt, firm in ((1, False), (2, True)):
                prompt = tmpl.format(firm=jc.FIRM if firm else "",
                                     sheet=sheet, items=items)
                try:
                    out = jc.call_claude(prompt, case_sheets, args.model)
                except (RuntimeError, subprocess.TimeoutExpired) as ex:
                    print(f"[j6/cases]   {kind}: call failed ({ex})")
                    continue
                arr = jc.parse_array(out)
                if arr is not None and len(arr) >= 1:
                    return arr
                print(f"[j6/cases]   {kind}: malformed "
                      f"(attempt {attempt})")
            return None

        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            case_results = list(ex.map(run_case, case_jobs))
        case_cache["meta"]["calls"] = (case_cache["meta"].get("calls", 0)
                                       + len(case_jobs))
        today = date.today().isoformat()
        prov = {"model": args.model, "date": today,
                "prompt_version": jc.PROMPT_VERSION,
                "source": "judge_cases"}
        summary = {"confirmed": [], "rejected": [], "unclear": [],
                   "renamed": [], "edges": []}
        for (kind, _, _, _, cases_q), arr in zip(case_jobs, case_results):
            if arr is None:
                print(f"[j6/cases] {kind}: FAILED -- statuses unchanged")
                continue
            if kind == "existence":
                by_id = {e.get("id"): e for e in arr
                         if isinstance(e, dict)}
                for jn, f in cases_q:
                    e = by_id.get(jn["id"])
                    if not e or e.get("verdict") not in jc.EXIST_VERDICTS:
                        summary["unclear"].append(jn["id"])
                        continue
                    v = {**{k: e.get(k) for k in
                            ("verdict", "what_it_is", "confidence",
                             "reason")}, **prov}
                    jn["existence_verdict"] = v
                    if e["verdict"] == "REAL":
                        jn["existence"] = "confirmed"
                        wi = e.get("what_it_is")
                        if isinstance(wi, str) and wi.strip():
                            short = re.split(
                                r"\b(?:or|on|in|with|near|beside)\b",
                                wi.strip().lower())[0]
                            short = " ".join(
                                short.split()[:3]).strip(" ,;-")
                            if short and short != jn["name"]:
                                jn["name"] = short
                                jn["naming"] = {
                                    **prov, "reason": e.get("reason"),
                                    "what_it_is_full": wi.strip(),
                                    "via": "existence_verdict"}
                        summary["confirmed"].append(
                            f'{jn["id"]}={jn["name"]}')
                    elif e["verdict"] == "NOT_REAL":
                        jn["existence"] = "rejected"
                        summary["rejected"].append(jn["id"])
                    else:
                        summary["unclear"].append(jn["id"])
                    case_cache["cases"][f'exist:{jn["id"]}'] = v
            elif kind == "rename":
                by_id = {e.get("id"): e for e in arr
                         if isinstance(e, dict)}
                for jn, _ in cases_q:
                    e = by_id.get(jn["id"])
                    name = e.get("name") if e else None
                    if not isinstance(name, str) or not name.strip() \
                            or len(name.split()) > 3:
                        continue
                    old = jn["name"]
                    jn["name"] = name.strip().lower()
                    jn["naming"] = {**prov, "reason": e.get("reason"),
                                    "confidence": e.get("confidence"),
                                    "via": "case_rename", "was": old}
                    summary["renamed"].append(
                        f'{jn["id"]}: {old} -> {jn["name"]}')
                    case_cache["cases"][f'rename:{jn["id"]}'] = \
                        jn["naming"]
            else:
                by_case = {e.get("case"): e for e in arr
                           if isinstance(e, dict)}
                base = q_reex.index(cases_q[0]) + 1
                for off, (f, (ida, idb)) in enumerate(cases_q):
                    e = by_case.get(base + off)
                    if not e or e.get("edge_verdict") \
                            not in jc.EDGE_VERDICTS:
                        continue
                    # suspect_box must be an object id; the model
                    # sometimes answers with a tile label ("5B-a") --
                    # map the A/B side back, else null
                    sb = e.get("suspect_box")
                    if sb not in (ida, idb, None):
                        s = str(sb)
                        sb = (ida if "A" in s
                              else idb if "B" in s else None)
                    v = {**{k: e.get(k) for k in
                            ("edge_verdict", "true_arrangement",
                             "confidence", "reason")},
                         "suspect_box": sb, **prov}
                    for je in judged["edges"]:
                        if {je["a"], je["b"]} == {ida, idb}:
                            je["case_verdict"] = v
                    f["resolution"] = v
                    summary["edges"].append(
                        f'{ida}~{idb}: {e["edge_verdict"]}')
                    case_cache["cases"][f'reex:{ida}~{idb}'] = v
        case_cache_path.write_text(json.dumps(case_cache, indent=1))
        judged["j6_cases_meta"] = {"model": args.model,
                                   "date": today,
                                   "calls": len(case_jobs),
                                   "summary": summary}
        print(f"[j6/cases] {summary}")

    # ================= PHASE B -- appearance =============================
    clusters = [jn for jn in sorted(judged["nodes"], key=lambda n: n["id"])
                if jn.get("existence") not in ("disputed", "rejected")]
    skipped = [jn["id"] for jn in judged["nodes"]
               if jn.get("existence") in ("disputed", "rejected")]
    cache = (json.loads(cache_path.read_text())
             if cache_path.exists() else {"meta": {"calls": 0}, "nodes": {}})

    todo, hits, no_crops = [], 0, []
    for jn in clusters:
        crops = cluster_crops(jn, det, crops_dir)
        if not crops:
            no_crops.append(jn["id"])
            continue
        ehash = cluster_hash(jn, crops)
        ent = cache["nodes"].get(jn["id"])
        if ent and ent.get("evidence_hash") == ehash \
                and not args.sheets_only:
            jn["appearance"] = ent["appearance"]
            hits += 1
            continue
        todo.append((jn, ehash, crops))

    print(f"[appearance] {len(clusters)} non-disputed clusters "
          f"({len(skipped)} disputed skipped: {skipped}); "
          f"{hits} cache hits, {len(todo)} to describe, "
          f"{len(no_crops)} without crops {no_crops}")

    sheets_dir.mkdir(parents=True, exist_ok=True)
    batches = [todo[i:i + BATCH_SIZE]
               for i in range(0, len(todo), BATCH_SIZE)]
    if args.smoke:
        batches = batches[:1]

    prepared = []
    manifest = []
    for bi, batch in enumerate(batches, 1):
        sheet_path = sheets_dir / f"sheet_{bi:03d}.png"
        tile_map = build_sheet([(jn, crops) for jn, _, crops in batch],
                               sheet_path)
        items = "\n".join(
            item_block(i + 1, jn, tile_map[jn["id"]], floor_y)
            for i, (jn, _, _) in enumerate(batch))
        prompt = TEMPLATE.format(firm="", sheet=sheet_path, items=items)
        prepared.append((batch, sheet_path, tile_map, items))
        manifest.append({
            "sheet": str(sheet_path),
            "clusters": [{"id": jn["id"], "name": jn["name"],
                          "tiles": tile_map[jn["id"]],
                          "crops": [str(c) for c in crops]}
                         for jn, _, crops in batch]})

    (sheets_dir / "sheets_manifest.json").write_text(
        json.dumps({"prompt_version": PROMPT_VERSION,
                    "batches": manifest}, indent=1))
    print(f"[appearance] {len(prepared)} sheets in {sheets_dir}")

    if args.sheets_only:
        if prepared:
            print("\n[appearance] ===== batch 1 prompt (verbatim) =====")
            print(TEMPLATE.format(firm="", sheet=prepared[0][1],
                                  items=prepared[0][3]))
        print("\n[appearance] SHEETS-ONLY -- no model calls, no write-back")
        return

    def describe(job):
        batch, sheet_path, tile_map, items = job
        want = {jn["id"] for jn, _, _ in batch}
        for attempt, firm in ((1, False), (2, True)):
            prompt = TEMPLATE.format(firm=FIRM_PREFIX if firm else "",
                                     sheet=sheet_path, items=items)
            try:
                out = call_claude(prompt, sheets_dir, args.model)
            except (RuntimeError, subprocess.TimeoutExpired) as ex:
                print(f"[appearance]   batch failed ({ex})")
                continue
            got = parse_response(out, want)
            if len(got) == len(want):
                return got
            print(f"[appearance]   batch: {len(got)}/{len(want)} valid "
                  f"(attempt {attempt})")
        return got if "got" in dir() else {}

    results = []
    if prepared:
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            results = list(ex.map(describe, prepared))

    failed = []
    for (batch, _, _, _), got in zip(prepared, results):
        for jn, ehash, crops in batch:
            v = got.get(jn["id"]) if got else None
            if v is None:
                jn["appearance"] = None
                jn["appearance_vlm_failed"] = True
                failed.append(jn["id"])
                continue
            app = {**v, "model": args.model,
                   "date": date.today().isoformat(),
                   "prompt_version": PROMPT_VERSION,
                   "evidence_hash": ehash, "source": "describe_nodes_v2"}
            jn["appearance"] = app
            jn.pop("appearance_vlm_failed", None)
            cache["nodes"][jn["id"]] = {"evidence_hash": ehash,
                                        "appearance": app}

    for jn in clusters[:8]:
        a = jn.get("appearance")
        if a:
            print(f'  {jn["id"]} ({jn["name"]}): "{a["description"]}" '
                  f'agree={a["label_agreement"]}')

    cache["meta"]["calls"] = cache["meta"].get("calls", 0) + len(prepared)
    cache_path.write_text(json.dumps(cache, indent=1))
    described = sum(1 for jn in clusters if jn.get("appearance"))
    judged["appearance_meta"] = {
        "model": args.model, "last_run": date.today().isoformat(),
        "prompt_version": PROMPT_VERSION,
        "cumulative_calls": cache["meta"]["calls"],
        "described": described, "failed": failed,
        "disputed_skipped": skipped, "no_crops": no_crops}
    gpath.write_text(json.dumps(graph, indent=1))
    print(f"[appearance] wrote {gpath} -- {described}/{len(clusters)} "
          f"described" + (f" (FAILED: {failed})" if failed else ""))


if __name__ == "__main__":
    main()
