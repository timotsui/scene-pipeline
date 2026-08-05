"""
PICK (compose lane, after shopping.py; user rulings 2026-08-03: "look
and feel is just as important" -- and orientation does NOT join this
step, it gets its own later pass).

shopping.py ranks candidates by SIZE FIT alone and the naive pick was
#1 of that list. This module adds LOOKS: the top PICK_K candidates per
item are judged by style against the room itself, and the final order
blends the two rankings. Nothing else changes -- boxes, candidate
lists and fit scores come from shopping.json verbatim.

STYLE (judged, bounded -- one row-sheet call per BATCH items): the top
PICK_K candidates' thumbnails per item, numbered on a color-framed row
(describe_nodes v5 row-sheet lessons), judged against the room MOOD
SHEET (four level pano crops -- the sandbox ruling's one remaining job
for the room photos) plus the item's judged appearance testimony from
the graph. The judge ranks by look & feel ONLY (size is already scored
by code).

Final order = equal-weight blend of size-fit rank and style rank, fit
rank as tiebreak (BLEND WEIGHT = open user decision; 50/50 default);
candidates beyond PICK_K keep fit order behind the judged ones.
Output: compose/picks.json -- the full re-ranked list per item + the
pick. fit_preview.py places ranked[0] when picks.json exists (the fit
loop later walks the same order).

REVIEW-FIRST (standing rule): --sheets-only builds the mood sheet,
every candidate row-sheet and the verbatim prompts with ZERO model
calls -- nothing written where fit_preview would find it.

Cache: compose/pick_cache.json keyed by item id, hash over
PROMPT_VERSION + ordered candidate uids + testimony (mood is per-scene
constant). Degradation: a failed batch leaves its items UNJUDGED --
they keep fit order, style_rank null, nothing fabricated.

Run:
  python compose/pick.py --scene bedroom_marble --sheets-only
  python compose/pick.py --scene bedroom_marble
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402

sys.path.insert(0, str(paths.REPO_ROOT / "composition"))

MODEL = "sonnet"
CALL_TIMEOUT_S = 480
CONCURRENCY = 8   # 3 until 2026-08-04; compute is cloud-side, local lanes are couriers (user ruling; measured 2.5x at 6 lanes, contention not crash risk)
PICK_K = 8            # candidates judged for style per item
BATCH = 4             # items per sheet/call
TILE = 256            # px per thumbnail cell
ROW_SEP = 16
ROW_BORDER = 5
TILE_GAP = 12              # dark bar BETWEEN tiles in a row (v2: the
                           # mega-panel lesson applied within rows --
                           # flush white thumbs bled into each other)
ROW_COLORS = [(230, 40, 40), (40, 90, 230), (30, 170, 60),
              (240, 140, 20)]
COLOR_NAMES = ["red", "blue", "green", "orange"]
MOOD_YAWS = ("y000", "y090", "y180", "y270")   # level pano crops
PROMPT_VERSION = "2"       # v2 (08-03B): within-row tile gaps +
                           # tile-separation prompt language

TEMPLATE = """\
{firm}You are choosing which PRODUCT to buy for each spot in a real \
room. Size fit is already scored by code -- you judge LOOK & FEEL \
ONLY: style, color, material, era, how naturally the product would \
belong in THIS room.

Open and look at these two images:
  ROOM MOOD (four views of the actual room): {mood}
  CANDIDATES SHEET: {sheet}

Candidates-sheet layout: each ITEM occupies exactly ONE ROW, framed \
in that item's border color; rows are separated by thick dark \
horizontal bars. WITHIN a row, each candidate product sits in its own \
tile, separated from its neighbors by dark VERTICAL bars, with the \
candidate NUMBER painted in the top-left corner of ITS tile. One tile \
= one distinct product photographed alone on white -- NEVER read two \
adjacent tiles as one product, and never let a neighboring tile's \
color or shape bleed into your judgment of a tile. Thumbnails in \
DIFFERENT rows belong to DIFFERENT items -- never compare across \
rows. Thumbnails are small renders -- judge only what you can \
actually see.

For EACH item below, rank its candidates from the one you would buy \
FIRST to the one you would buy LAST for this room. Use the room mood \
images plus the item's testimony (what actually stood in that spot). \
When the testimony describes the original's look, prefer candidates \
that match it; when there is no testimony, match the room's overall \
mood. If several candidates are equally plausible, still order them. \
If a candidate clearly does not belong in this room, rank it last and \
say so in style_notes.

Return ONE fenced ```json block containing a JSON ARRAY with EXACTLY \
one object per item, in the same order as listed:
{{"id": "<the id given>", "ranking": [candidate numbers, best first, \
ALL of them exactly once], "style_notes": "one short line: what drove \
the top choice / any misfit"}}
Output ONLY the fenced JSON block.

{items}"""

FIRM_PREFIX = ("Your previous response was malformed. This time output "
               "ONLY one fenced ```json code block containing the JSON "
               "array, no prose.\n\n")


# --------------------------------------------------------------------------
# sheets (deterministic)
# --------------------------------------------------------------------------

def build_mood_sheet(scene, out_path):
    """2x2 grid of the four level pano crops -- the room's look & feel.
    Missing crops leave their cell white (honest, printed)."""
    cell = 512
    im = Image.new("RGB", (cell * 2, cell * 2), (255, 255, 255))
    missing = []
    for i, yaw in enumerate(MOOD_YAWS):
        p = paths.pano_crops_dir(scene) / f"pano_{yaw}_pp00.webp"
        if not p.exists():
            missing.append(p.name)
            continue
        tile = Image.open(p).convert("RGB").resize((cell, cell))
        im.paste(tile, ((i % 2) * cell, (i // 2) * cell))
    im.save(out_path)
    if missing:
        print(f"[pick] mood sheet missing crops: {missing}")
    return out_path


def build_item_row(it, thumb_of, color):
    """ONE item's strip: its top-K candidate thumbs numbered 1..K,
    separated by dark TILE_GAP bars (v2 -- tiles must be visually
    distinct, the mega-panel lesson), the whole strip framed in the
    item's color. Returned as an Image; also the per-item review
    artifact (row_<id>.png)."""
    k = len(it["style_cands"])
    w = ROW_BORDER * 2 + TILE * k + TILE_GAP * (k - 1)
    h = ROW_BORDER * 2 + TILE
    row = Image.new("RGB", (w, h), (25, 25, 25))
    ImageDraw.Draw(row).rectangle([0, 0, w - 1, h - 1], outline=color,
                                  width=ROW_BORDER)
    for j, c in enumerate(it["style_cands"]):
        tp = thumb_of(c)
        if tp and Path(tp).exists():
            tile = Image.open(tp).convert("RGB")
            if tile.size != (TILE, TILE):
                tile = tile.resize((TILE, TILE))
        else:
            tile = Image.new("RGB", (TILE, TILE), (180, 180, 180))
            print(f'[pick] no thumb for {c["uid"]} {c["perm"]}')
        d = ImageDraw.Draw(tile)
        txt = str(j + 1)
        d.rectangle([0, 0, 14 + 13 * len(txt), 24], fill=(0, 0, 0))
        d.text((8, 3), txt, fill=(255, 255, 60))
        row.paste(tile, (ROW_BORDER + j * (TILE + TILE_GAP),
                         ROW_BORDER))
    return row


def build_row_sheet(batch, thumb_of, out_path, sdir=None):
    """One color-framed item strip per row (describe_nodes v5
    pattern), thick dark bars between rows. Each item's strip is also
    saved alone as row_<id>.png (viewer: 'what the judge saw')."""
    rows = []
    for i, it in enumerate(batch):
        r = build_item_row(it, thumb_of, ROW_COLORS[i % len(ROW_COLORS)])
        if sdir is not None:
            r.save(sdir / f'row_{it["id"]}.png')
        rows.append(r)
    W = max(r.width for r in rows)
    H = sum(r.height for r in rows) + ROW_SEP * (len(rows) - 1)
    sheet = Image.new("RGB", (W, H), (25, 25, 25))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height + ROW_SEP
    sheet.save(out_path)
    return out_path


def batch_prompt(batch, mood_path, sheet_path, firm=False):
    lines = []
    for row, it in enumerate(batch):
        color = COLOR_NAMES[row % len(COLOR_NAMES)]
        lines.append(f'ITEM {row + 1} ({color} row) id={it["id"]} '
                     f'"{it["name"]}"')
        lines.append(f'  testimony: {it["testimony"]}')
        for j, c in enumerate(it["style_cands"]):
            sz = "x".join(str(v) for v in c["size_cm"])
            lines.append(f'  {j + 1}) {c["category"]} | {sz} cm | '
                         f'{c["description"][:90]}')
    return TEMPLATE.format(firm=FIRM_PREFIX if firm else "",
                           mood=mood_path, sheet=sheet_path,
                           items="\n".join(lines))


# --------------------------------------------------------------------------
# claude bridge (project pattern: stdin, stripped env, error sniff)
# --------------------------------------------------------------------------

def claude_env():
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(k, None)  # stale-API-key hijack gotcha (project memory)
    return env


def call_claude(prompt, cwd, model):
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("[pick] claude.exe not on PATH")
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
    for bad in ("invalid_api_key", "authentication_error",
                "credit balance"):
        if bad in low:
            raise RuntimeError(f"claude API-billing/auth error: "
                               f"{out[:400]}")
    return out


def parse_response(text, batch):
    """-> {id: {ranking, style_notes}} for entries that validate: the
    ranking must be a permutation of 1..K for that item."""
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
    want = {it["id"]: len(it["style_cands"]) for it in batch}
    good = {}
    for e in arr:
        if not isinstance(e, dict) or e.get("id") not in want:
            continue
        k = want[e["id"]]
        rk = e.get("ranking")
        if (isinstance(rk, list) and sorted(rk) == list(range(1, k + 1))):
            good[e["id"]] = {"ranking": rk,
                             "style_notes":
                                 str(e.get("style_notes", ""))[:200]}
    return good


# --------------------------------------------------------------------------

def testimony_of(graph, oid):
    for jn in graph.get("judged", {}).get("nodes", []):
        if jn["id"] != oid:
            continue
        ap = jn.get("appearance") or {}
        if not ap.get("description"):
            break
        bits = []
        if ap.get("colors"):
            bits.append("/".join(ap["colors"][:3]))
        if ap.get("material"):
            bits.append(ap["material"])
        if ap.get("style"):
            bits.append(ap["style"])
        head = ", ".join(bits)
        return (f'{head} -- "{ap["description"][:140]}"' if head
                else f'"{ap["description"][:140]}"')
    return "(invented item -- no room testimony; match the room mood)"


def main():
    t0 = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--sheets-only", action="store_true",
                    help="build sheets + prompts, ZERO model calls, "
                         "no picks.json")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--concurrency", type=int, default=CONCURRENCY)
    args = ap.parse_args()

    cdir = paths.compose_dir(args.scene)
    sl = json.loads((cdir / "shopping.json").read_text(encoding="utf-8"))
    graph = json.loads((paths.scene_dir(args.scene) / "scene_graph.json")
                       .read_text(encoding="utf-8"))

    # ---- items: shopping order VERBATIM (size fit only) --------------
    items = []
    for r in sl["items"]:
        if not r.get("candidates"):
            continue
        cands = [dict(c) for c in r["candidates"]]
        for i, c in enumerate(cands):
            c["fit_rank"] = i
        items.append({
            "id": r["id"], "name": r["name"], "mount": r["mount"],
            "source": r.get("source", "detected"),
            "testimony": testimony_of(graph, r["id"]),
            "ranked": cands,
            "style_cands": cands[:PICK_K] if len(cands) > 1 else [],
        })

    n_judge = sum(1 for it in items if it["style_cands"])
    print(f"[pick] {len(items)} items, {n_judge} to style-judge "
          f"(PICK_K={PICK_K}, batches of {BATCH})")

    # ---- sheets ------------------------------------------------------
    sdir = cdir / "pick_sheets"
    sdir.mkdir(parents=True, exist_ok=True)
    mood_path = build_mood_sheet(args.scene, sdir / "mood_sheet.png")

    import thumbs  # deferred: pulls pyrender/GL
    need = [(c["uid"], c["perm"]) for it in items
            for c in it["style_cands"]]
    thumbs.ensure(need)

    def thumb_of(c):
        p = thumbs.thumb_path(c["uid"], c["perm"])
        return p if p.exists() else thumbs.thumb_path(c["uid"], "xyz")

    judged_items = [it for it in items if it["style_cands"]]
    batches = [judged_items[i:i + BATCH]
               for i in range(0, len(judged_items), BATCH)]
    manifest_rows = []
    for bi, batch in enumerate(batches):
        sheet = build_row_sheet(batch, thumb_of,
                                sdir / f"sheet_{bi:03d}.png", sdir=sdir)
        prompt = batch_prompt(batch, mood_path, sheet)
        (sdir / f"prompt_{bi:03d}.txt").write_text(prompt,
                                                   encoding="utf-8")
        manifest_rows.append({"sheet": sheet.name,
                              "prompt": f"prompt_{bi:03d}.txt",
                              "items": [it["id"] for it in batch]})
    (sdir / "sheets_manifest.json").write_text(
        json.dumps({"scene": args.scene, "built": str(date.today()),
                    "prompt_version": PROMPT_VERSION,
                    "mood": mood_path.name, "batches": manifest_rows},
                   indent=1), encoding="utf-8")
    print(f"[pick] {len(batches)} sheets + prompts in {sdir}")

    if args.sheets_only:
        print("[pick] sheets-only: no model calls, no picks.json")
        return

    # ---- style judging (cached, concurrent, honest degrade) ----------
    cache_path = cdir / "pick_cache.json"
    cache = (json.loads(cache_path.read_text(encoding="utf-8"))
             if cache_path.exists() else {"meta": {"calls": 0},
                                          "items": {}})

    def item_hash(it):
        blob = PROMPT_VERSION \
            + json.dumps([c["uid"] for c in it["style_cands"]]) \
            + it["testimony"]
        return hashlib.sha256(blob.encode()).hexdigest()[:16]

    verdicts = {}
    todo_batches = []
    for bi, batch in enumerate(batches):
        missing = False
        for it in batch:
            ent = cache["items"].get(it["id"])
            if ent and ent.get("hash") == item_hash(it):
                verdicts[it["id"]] = ent["verdict"]
            else:
                missing = True
        if missing:
            todo_batches.append(bi)
    print(f"[pick] style: {len(verdicts)} cache hits, "
          f"{len(todo_batches)} batches to call")

    def run_batch(bi):
        batch = batches[bi]
        sheet = sdir / f"sheet_{bi:03d}.png"
        bt = time.time()
        got = {}
        for attempt, firm in enumerate((False, True)):
            try:
                reply = call_claude(
                    batch_prompt(batch, mood_path, sheet, firm=firm),
                    cwd=sdir, model=args.model)
                got = parse_response(reply, batch)
            except (RuntimeError, subprocess.TimeoutExpired) as ex:
                print(f"[pick] batch {bi} attempt {attempt + 1} "
                      f"failed: {str(ex)[:200]}")
                got = {}
            if len(got) == len(batch):
                break
        print(f"[pick] batch {bi}: {len(got)}/{len(batch)} judged "
              f"in {time.time() - bt:.0f}s")
        return bi, got

    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        for bi, got in ex.map(run_batch, todo_batches):
            for it in batches[bi]:
                if it["id"] in got:
                    verdicts[it["id"]] = got[it["id"]]
                    cache["items"][it["id"]] = {
                        "hash": item_hash(it),
                        "verdict": got[it["id"]]}
                else:
                    print(f'[pick] {it["id"]} UNJUDGED '
                          f"(batch {bi}) -- keeps fit order")
    cache["meta"]["calls"] = (cache["meta"].get("calls", 0)
                              + len(todo_batches))
    cache_path.write_text(json.dumps(cache, indent=1),
                          encoding="utf-8")

    # ---- STYLE-ONLY output (user 08-03B): a SEPARATE ranking, NOT
    # blended with fit -- the combine policy is still an open user
    # decision. Fit order lives in shopping.json; nothing here
    # overrides it. THE SHOPPING PROCESS ENDS AT final_candidates =
    # the style judge's TOP 3 per box (user ruling 08-03B, "k=3
    # candidates for each object box"); unjudged items fall back to
    # the fit top 3, honestly marked.
    FINAL_K = 3
    for it in items:
        ks = it.pop("style_cands")
        allc = it.pop("ranked")
        v = verdicts.get(it["id"])
        it["style_judged"] = bool(v)
        it["style_notes"] = v["style_notes"] if v else None
        if v:
            order = [num - 1 for num in v["ranking"]]
            for pos, i in enumerate(order):
                ks[i]["style_rank"] = pos
            it["style_ranked"] = [ks[i] for i in order]
        else:
            it["style_ranked"] = []
        it["final_candidates"] = (it["style_ranked"] or allc)[:FINAL_K]

    out = {
        "scene": args.scene, "built": str(date.today()),
        "generated_by": "compose/pick.py",
        "graph_fingerprint": paths.graph_fingerprint(args.scene),
        "prompt_version": PROMPT_VERSION,
        "elapsed_s": round(time.time() - t0, 1),
        "note": ("STYLE-ONLY ranking per anchor (looks judge over the "
                 "top %d size-fit candidates; mood sheet + testimony); "
                 "NOT blended with fit -- combine policy open. "
                 "final_candidates = the style top 3 = THE shopping "
                 "output the fit loop walks (user 08-03B). Orientation "
                 "is NOT scored here (separate later step, user "
                 "ruling 08-03)." % PICK_K),
        "counts": {"items": len(items),
                   "style_judged": sum(1 for it in items
                                       if it["style_judged"])},
        "items": items,
    }
    opath = cdir / "picks.json"
    opath.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"[pick] wrote {opath}")
    print(f"[pick] counts: {json.dumps(out['counts'])}")
    print(f"[pick] TOTAL {time.time() - t0:.1f}s wall "
          f"({len(todo_batches)} model calls this run)")
    for it in items:
        if not it["style_judged"]:
            print(f'    {it["id"]} "{it["name"]}" UNJUDGED')
            continue
        p = it["style_ranked"][0]
        print(f'    {it["id"]} "{it["name"]}" style#1 = {p["category"]} '
              f'{p["uid"][:8]} (fit #{p["fit_rank"] + 1}) '
              f'-- {it["style_notes"]}')


if __name__ == "__main__":
    main()
