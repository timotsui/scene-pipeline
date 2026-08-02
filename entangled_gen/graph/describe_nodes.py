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

07-30 (appearance prompt v4+v5, PLAN_COMPOSE_LOOP.md R3): phase B item
lines are GEOMETRY-BLIND (v4 -- the witness must not hear the geometry
its testimony is weighed against by supported_by), and the contact
sheet is a ROW-SHEET (v5 -- one item per color-framed row; the old
mixed grid cross-contaminated neighboring items: obj_001 3/3 wrong on
grids, correct on row-sheets, same cost). Phase A keeps geometry
(jc.facts) on purpose: judges arbitrate, witnesses stay blind.

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
# (v5 row-sheets replaced the 4-col grid; LABEL_H/SHEET_COLS retired)
PROMPT_VERSION = "6"       # v6 (07-31): STRUCTURED TESTIMONY -- the
                           # prose description becomes INTRINSIC-ONLY
                           # (never mentions other objects) and support
                           # moves to support_view: a LIST of GENERIC
                           # visible contacts (floor / horizontal_surface
                           # / vertical_surface / ceiling / not_visible)
                           # with not_visible as a first-class honest
                           # answer. The witness reports contact
                           # geometry; supported_by matches it against
                           # its candidate list -- naming the supporter
                           # is the judge's job, not the witness's
                           # (probe run 07-30: obj_001 floor, obj_083
                           # honest not_visible, no invented neighbors).
                           # v5 (07-30): ROW-SHEETS -- one item per row,
                           # per-row color frame, item number burned INTO
                           # each crop, thick dark separators, and the
                           # prompt forbids reading other rows as context.
                           # The old 4-col mixed grid caused cross-tile
                           # contamination: obj_001 (floor plant) came
                           # back "on a wooden shelf" 3/3 on grid sheets
                           # but correct on solo calls, one-by-one feeds,
                           # AND the row-sheet (15.0s vs 16.1s grid --
                           # the fix is free). Controlled experiment
                           # 07-30, PLAN_COMPOSE_LOOP.md R3.
                           # v4 (07-30): GEOMETRY-BLIND item lines -- box
                           # size + floor-height dropped from PHASE B.
                           # Appearance is pixel TESTIMONY that
                           # supported_by weighs AGAINST measured
                           # geometry; "bottom 0.19 m above the floor"
                           # pre-answered the support question (obj_001
                           # -> invented shelf), and geometry was never
                           # in the cache hash. Label-geometry conflicts
                           # route via J4 -> phase A, which keeps
                           # jc.facts() on purpose (arbitration).
                           # v3: CONTEXT crops (padded view, extra below,
                           # red outline) -- tight crops cut off what the
                           # object stands on and the VLM invented support
                           # ("sitting on a shelf" for a floor plant beside
                           # a bookshelf: the obj_001 lesson, 07-26G)

# context-crop padding, fractions of the 2D box (extra BELOW: support
# lives there); min px guards tiny boxes
CTX_PAD_SIDE = 0.35
CTX_PAD_TOP = 0.35
CTX_PAD_BOTTOM = 0.75
CTX_MIN_PAD = 40

# row-sheet layout (v5): one item per row, framed in its own color; the
# frame color + burned-in number give the model TWO redundant mappings
ROW_SEP = 16               # px, dark bar between rows
ROW_BORDER = 5             # px, per-row color frame
ROW_COLORS = [(230, 40, 40), (40, 90, 230), (30, 170, 60), (240, 140, 20),
              (200, 40, 200), (20, 180, 190), (200, 180, 20),
              (130, 60, 220)]
COLOR_NAMES = ["red", "blue", "green", "orange", "magenta", "cyan",
               "yellow", "purple"]   # cycled if BATCH_SIZE ever exceeds 8

REQUIRED_KEYS = {"id", "colors", "material", "style", "description",
                 "support_view", "is_label"}
# support_view contact vocabulary (v6): generic surfaces only -- the
# witness never names the supporting OBJECT, and not_visible beats a
# plausibility guess
SV_CONTACTS = {"floor", "horizontal_surface", "vertical_surface",
               "ceiling", "not_visible"}

TEMPLATE = """\
{firm}You are describing objects detected in a 3D indoor-scene \
reconstruction. Open and look at this contact sheet image:
  {sheet}
Layout: each ITEM occupies exactly ONE ROW -- its crops side by side, \
the whole row framed in that item's border color, and the item NUMBER \
painted in the top-left corner of each crop. Rows are separated by \
thick dark bars. Crops in DIFFERENT rows are DIFFERENT items -- never \
read another row's pixels as context for this item. Crops are small, \
low-resolution renders -- describe only what you can actually see, do \
NOT invent detail. Each crop shows the target object OUTLINED IN RED \
with its surroundings included. Describe ONLY the outlined object; the \
surroundings are there so you can see what it visibly rests on, hangs \
from, or is mounted to -- mention that support context when (and only \
when) the pixels actually show it.

For EACH numbered item below, look at its row and return one JSON \
object with TWO SEPARATE parts:

1. "description": the object ITSELF only -- color, material, shape, \
style. NEVER mention any other object, surface, or where it sits; \
identifying the surroundings is a downstream job.

2. "support_view": a LIST of physical contacts you can actually SEE \
holding this object up, in GENERIC surface terms only -- never name or \
guess what the supporting thing is. Allowed "contact" values:
  "floor"               -- bottom visibly meets the room's ground plane
  "horizontal_surface"  -- bottom rests on some raised horizontal surface
  "vertical_surface"    -- held against / mounted on a vertical surface
  "ceiling"             -- hangs from or mounts to the ceiling
  "not_visible"         -- the contact region is NOT visible in the crops
"detail" = a short generic phrase about the visible contact (e.g. \
"bottom edge meets a flat wooden surface"), still naming no objects. \
Multiple entries are allowed (e.g. a leaning object: bottom on a \
horizontal surface AND back against a vertical one). If you cannot see \
what holds it up, the ONLY honest answer is \
[{{"contact": "not_visible", "detail": "..."}}] -- do NOT guess from \
plausibility.

"is_label": answer honestly -- do the crops actually show a "<name>" \
as given? false if they clearly show something else.

Return ONE fenced ```json block containing a JSON ARRAY with EXACTLY \
one object per item, in the same order:
{{"id": "<the id given>", "colors": ["dominant color words"], \
"material": "best guess, e.g. wood/fabric/metal/ceramic", \
"style": "a few words, e.g. modern minimal", \
"description": "ONE sentence, the object only", \
"support_view": [{{"contact": "...", "detail": "..."}}], \
"is_label": true or false}}
Output ONLY the fenced JSON block.

{items}"""

FIRM_PREFIX = ("Your previous response was malformed. This time output "
               "ONLY one fenced ```json code block containing the JSON "
               "array, no prose.\n\n")


# --------------------------------------------------------------------------
# crop selection + contact sheets (deterministic)
# --------------------------------------------------------------------------

def context_crop(nid, m, frames_dir, ctx_dir):
    """Context variant of a member crop: the source view cropped to the
    detection box plus a generous margin -- EXTRA below, where support
    lives -- with the box outlined in red so the judge knows which object
    is meant (judge_cases.context_tile pattern; the obj_001 floor-plant
    lesson). Deterministic, skips existing files. None if no frame."""
    src = Path(frames_dir) / f'{m["view"]}.webp'
    if not src.exists():
        return None
    out = ctx_dir / f'{nid}_m{m["member"]:03d}.png'
    if out.exists():
        return out
    im = Image.open(src).convert("RGB")
    x0, y0, x1, y1 = m["box_2d"]
    ImageDraw.Draw(im).rectangle([x0, y0, x1, y1],
                                 outline=(255, 40, 40), width=4)
    w, h = x1 - x0, y1 - y0
    ps = max(CTX_PAD_SIDE * w, CTX_MIN_PAD)
    pt = max(CTX_PAD_TOP * h, CTX_MIN_PAD)
    pb = max(CTX_PAD_BOTTOM * h, CTX_MIN_PAD)
    box = (max(0, int(x0 - ps)), max(0, int(y0 - pt)),
           min(im.width, int(x1 + ps)), min(im.height, int(y1 + pb)))
    if box[2] <= box[0] or box[3] <= box[1]:
        return None
    im.crop(box).save(out)
    return out


def cluster_crops(jn, det, crops_dir, ctx=None):
    """Top crops for a cluster: best-scoring crop of each member first
    (diversity for merged clusters), then next-best overall; cap
    CROPS_PER_CLUSTER. Deterministic ordering. ctx=(frames_dir, ctx_dir):
    each selected crop is swapped for its CONTEXT variant (context_crop)
    when buildable, falling back to the tight crop."""
    per_member, rest = [], []
    for mid in sorted(jn["members"]):
        ms = sorted(det[mid]["evidence"].get("members", []),
                    key=lambda m: (-m.get("score", 0.0), m.get("member", 0)))
        found_first = False
        for m in ms:
            p = crops_dir / m.get("crop", "")
            if not m.get("crop") or not p.exists():
                continue
            entry = (round(-m.get("score", 0.0), 4), m.get("member", 0),
                     p, mid, m)
            if not found_first:
                per_member.append(entry)
                found_first = True
            else:
                rest.append(entry)
    key = lambda e: e[:2]                    # dicts in [3:] aren't orderable
    per_member.sort(key=key)
    rest.sort(key=key)
    chosen = per_member[:CROPS_PER_CLUSTER]
    for e in rest:
        if len(chosen) >= CROPS_PER_CLUSTER:
            break
        chosen.append(e)
    out = []
    for _, _, p, mid, m in chosen:
        cp = context_crop(mid, m, *ctx) if ctx else None
        out.append(cp or p)
    return out


def build_sheet(batch, sheet_path):
    """batch: [(jn, [crop paths])]. v5 ROW-SHEET: one item per ROW (its
    crops side by side), the row framed in its own color, item number
    burned INTO each crop's corner, thick dark separators. The old
    4-col mixed grid let neighboring items' pixels contaminate each
    other (obj_001 grid=shelf 3/3, row-sheet=floor; 07-30 experiment).
    Returns {cluster_id: {"row": i, "color": name}}."""
    row_map = {}
    ncols = max(len(crops) for _, crops in batch)
    W = ncols * TILE + (ncols + 1) * ROW_BORDER
    H = len(batch) * (TILE + 2 * ROW_BORDER + ROW_SEP) - ROW_SEP
    sheet = Image.new("RGB", (W, H), (15, 15, 15))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arialbd.ttf", 26)
    except OSError:
        font = ImageFont.load_default()
    for i, (jn, crops) in enumerate(batch):
        col = ROW_COLORS[i % len(ROW_COLORS)]
        row_map[jn["id"]] = {"row": i + 1,
                             "color": COLOR_NAMES[i % len(COLOR_NAMES)]}
        y0 = i * (TILE + 2 * ROW_BORDER + ROW_SEP)
        draw.rectangle([0, y0, W - 1, y0 + TILE + 2 * ROW_BORDER - 1],
                       fill=col)
        for k, p in enumerate(crops):
            im = Image.open(p).convert("RGB")
            f = min(TILE / im.width, TILE / im.height)
            im = im.resize((max(1, round(im.width * f)),
                            max(1, round(im.height * f))), Image.LANCZOS)
            cell = Image.new("RGB", (TILE, TILE), (40, 40, 40))
            cell.paste(im, ((TILE - im.width) // 2,
                            (TILE - im.height) // 2))
            d2 = ImageDraw.Draw(cell)
            d2.rectangle([0, 0, 54, 36], fill=col)
            d2.text((14, 3), str(i + 1), fill=(255, 255, 255), font=font)
            sheet.paste(cell, (ROW_BORDER + k * (TILE + ROW_BORDER),
                               y0 + ROW_BORDER))
    sheet.save(sheet_path)
    return row_map


def cluster_hash(jn, crops):
    h = hashlib.sha256()
    h.update(PROMPT_VERSION.encode())
    h.update(jn["name"].encode())
    for p in crops:
        h.update(Path(p).read_bytes())
    return h.hexdigest()[:32]


def item_block(i, jn, row_info):
    # v4: geometry-blind on purpose -- the witness must not hear the
    # geometry its testimony will be weighed against (supported_by).
    # v5: row + frame color = the redundant text half of the mapping.
    return (f'Item {i}: id={jn["id"]}, name="{jn["name"]}" -- '
            f'row {row_info["row"]} ({row_info["color"]} frame)')


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
    # prompt via STDIN, not argv: Windows CreateProcess caps the command
    # line at ~32k chars (supported_by hit it first, 07-31); stdin has
    # no such limit and scales to any scene
    r = subprocess.run([exe, "-p", "--model", model],
                       input=prompt,
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
        sv = e["support_view"]
        if not (isinstance(sv, list) and sv
                and all(isinstance(s, dict)
                        and s.get("contact") in SV_CONTACTS
                        and isinstance(s.get("detail", ""), str)
                        for s in sv)):
            continue
        good[e["id"]] = {"colors": e["colors"],
                         "material": e["material"].strip(),
                         "style": e["style"].strip(),
                         "description": e["description"].strip(),
                         "support_view": [
                             {"contact": s["contact"],
                              "detail": (s.get("detail") or "").strip()}
                             for s in sv],
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
    ap.add_argument("--appearance-only", action="store_true",
                    help="skip PHASE A flag resolution (already ran once); "
                         "refresh appearance descriptions only")
    ap.add_argument("--no-ctx", action="store_true",
                    help="use the tight evidence crops instead of the "
                         "context variants (pre-07-27 behavior)")
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
    frames_dir = Path(graph.get("lineage", {}).get("crop_source")
                      or (gdir / "rig_sp0" / "crops"))

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
    if args.appearance_only:
        print("[j6/cases] --appearance-only: PHASE A SKIPPED (flag "
              "resolution already ran once; refreshing appearance only)")
        q_exist, q_rename, q_reex = [], [], []
    case_jobs = []
    if q_exist or q_rename or q_reex:
        case_sheets.mkdir(parents=True, exist_ok=True)
    if q_exist:
        sheet, items = jc.build_exist_job(q_exist, det, crops_dir,
                                          frames_dir, case_sheets,
                                          floor_y)
        case_jobs.append(("existence", jc.T_EXIST, sheet, items,
                          q_exist))
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
            ctx = jc.context_tile(jn, det, frames_dir, case_sheets)
            if ctx is not None:
                lab = f"{i}x"
                labs.append(lab + " (context)")
                tiles.append((lab, ctx))
            items.append(
                f'Item {i}: id={jn["id"]}, current name "{jn["name"]}", '
                f'tiles {", ".join(labs)} -- {jc.facts(jn, floor_y)}.\n'
                + jc.trunc_note(jn, det)
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
        summary = {"confirmed": [], "rejected": [], "structure": [],
                   "unclear": [], "renamed": [], "edges": []}
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
                    elif e["verdict"] == "PART_OF_STRUCTURE":
                        # real pixels, but they belong to a door/window/
                        # trim/furniture host -- the node must not ship
                        # as a standalone furnishing
                        jn["existence"] = "structure"
                        summary["structure"].append(
                            f'{jn["id"]} -> part of '
                            f'{e.get("what_it_is") or "?"}')
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
                if jn.get("existence") not in ("disputed", "rejected",
                                               "structure")]
    skipped = [jn["id"] for jn in judged["nodes"]
               if jn.get("existence") in ("disputed", "rejected",
                                          "structure")]
    cache = (json.loads(cache_path.read_text())
             if cache_path.exists() else {"meta": {"calls": 0}, "nodes": {}})

    ctx = None
    if not args.no_ctx:
        ctx_dir = gdir / "graph" / "crops_ctx"
        ctx_dir.mkdir(parents=True, exist_ok=True)
        ctx = (frames_dir, ctx_dir)
    todo, hits, no_crops = [], 0, []
    for jn in clusters:
        crops = cluster_crops(jn, det, crops_dir, ctx=ctx)
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
        row_map = build_sheet([(jn, crops) for jn, _, crops in batch],
                              sheet_path)
        items = "\n".join(
            item_block(i + 1, jn, row_map[jn["id"]])
            for i, (jn, _, _) in enumerate(batch))
        prompt = TEMPLATE.format(firm="", sheet=sheet_path, items=items)
        prepared.append((batch, sheet_path, row_map, items))
        manifest.append({
            "sheet": str(sheet_path),
            "clusters": [{"id": jn["id"], "name": jn["name"],
                          "row": row_map[jn["id"]],
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
        batch, sheet_path, row_map, items = job
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
