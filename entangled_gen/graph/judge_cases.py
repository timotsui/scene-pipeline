"""
RETIRED AS A PIPELINE STAGE (user correction 2026-07-26 late): the
closure-loop design this module anchored (case rounds alternating with
whole-room coherence re-scans) is REVOKED -- "the loop is not the right
place". The settled design: J1-J5 unchanged, J4 runs ONCE, and the J6
appearance pass (describe_nodes.py) absorbs these queues in its single
terminal pass; unsettled flags ship to the placement stage. This
module's queue/adjudication machinery is the donor code for that J6
merge (PLAN_SCENE_GRAPH.md 0a.8); keep it runnable, do not wire it into
any orchestration. Its bedroom_marble verdicts (2026-07-26) stand.

Original docstring follows.
---------------------------------------------------------------------------
Pass 2 -- JUDGE, sub-pass J7: CASE-CLOSING (user 2026-07-26: "by the end
of the appearance judge we have a closed file that at least self-agrees
to hand off to the composition stage").

Gives every open coherence-judge case the one lens it never had --
PIXELS -- so the judged graph ships with no un-adjudicated flags. Three
queues, one module:

  A. EXISTENCE (the disputed nodes): crops + the coherence flag + its
     hypotheses + cheap facts -> verdict
       REAL      -> existence: "confirmed" (re-enters the graph; may
                    carry what_it_is as a rename with provenance)
       NOT_REAL  -> existence: "rejected" (stays skipped -- stronger,
                    pixel-backed)
       UNCLEAR   -> stays "disputed" (honest)
  B. RENAME (coherence rename_candidates + appearance
     label_agreement:false): canonical name from crops, J3-style.
  C. RE-EXAMINE (the escalation queue): BOTH objects' crops + full
     coordinates (footprints, spans -- the fact style the text
     experiment validated on the basket case) -> verdict
       {true_arrangement, edge_verdict: CONFIRM|REJECT|REINTERPRET,
        suspect_box: <id|null>}
     written onto the flagged relation in the judged view. SEMANTIC
     truth closes HERE; actual box surgery stays with the placement
     stage (suspect_box is its work order).

REVIEW-FIRST: --sheets-only builds the case-file contact sheets +
verbatim prompts, zero model calls (standing user rule). Bridge /
strict-JSON / firmer-retry / PROMPT_VERSION-salted cache identical to
the other judges. Degradation: failed cases keep their current status.

WRITE-BACK (additive-only): existence_verdict / naming / edge verdicts
+ judged.cases_meta. Record untouched. Cache:
out/<scene>/graph/judge_cases_cache.json keyed by case id.

After this pass the closure loop is: rerun judge_coherence.py (new
digest -> fresh self-agreement check) and describe_nodes.py (an
increment: newly confirmed/renamed clusters get described under their
final names -- the per-cluster name-salted cache re-describes exactly
those).

Run:
  python graph/judge_cases.py --scene bedroom_marble --sheets-only
  python graph/judge_cases.py --scene bedroom_marble
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
CROPS_EXIST = 3           # crops per disputed node
CROPS_RENAME = 2
CROPS_REEX = 2            # per object, per re-examine case
TILE = 256
LABEL_H = 22
SHEET_COLS = 4
CTX_PAD_FACTOR = 1.2      # context margin = this x the box's larger side
CTX_MIN_PAD = 200         # px, floor on that margin
PROMPT_VERSION = "2"      # v2: context tiles + truncation facts +
                          # PART_OF_STRUCTURE (the obj_138 door-frame case)

EXIST_VERDICTS = ("REAL", "NOT_REAL", "PART_OF_STRUCTURE", "UNCLEAR")
EDGE_VERDICTS = ("CONFIRM", "REJECT", "REINTERPRET")

T_EXIST = """\
{firm}A 3D-scan extraction flagged the objects below as POSSIBLY NOT \
REAL (weak evidence + a physically impossible relationship). You get \
their actual image crops on this contact sheet:
  {sheet}
Tile labels like "2a" mean crop a of case 2. A tile labeled "2x" is \
that case's ZOOMED-OUT CONTEXT view: the same detection outlined in \
red inside its surroundings -- use it to judge what the outlined \
pixels belong to. Crops are small low-resolution renders; judge only \
what you can see.

For EACH numbered case decide what the outlined pixels really are:
  "REAL"      -- a real standalone object is visible (say what it is)
  "NOT_REAL"  -- texture/reflection/duplicate/artifact, not an object
  "PART_OF_STRUCTURE" -- real pixels, but they belong to a larger \
structure or object (door frame, window frame, wall trim, molding, \
built-in shelving, part of a furniture piece) -- name that host
  "UNCLEAR"   -- the crops cannot settle it
A case noted as CUT OFF at the image edge shows only a fragment of \
something -- check its context tile for what the fragment extends \
into before naming a small standalone object.
Return ONE fenced ```json block, a JSON ARRAY, one object per case, \
same order:
{{"id": "<the id given>", "verdict": \
"REAL|NOT_REAL|PART_OF_STRUCTURE|UNCLEAR", "what_it_is": "<short \
lowercase name of the object, or of the HOST structure for \
PART_OF_STRUCTURE; else null>", "confidence": 0.0-1.0, \
"reason": "one sentence"}}
Output ONLY the fenced JSON block.

{items}"""

T_RENAME = """\
{firm}These objects from a 3D-scan extraction have DOUBTED names (a \
room-level plausibility check or an appearance check disagreed with the \
label). Look at their crops on this contact sheet:
  {sheet}
Tile labels like "2a" mean crop a of item 2. A tile labeled "2x" is \
that item's ZOOMED-OUT CONTEXT view: the same detection outlined in \
red inside its surroundings -- use it to judge what the pixels belong \
to (an item CUT OFF at the image edge may be a fragment of a larger \
structure such as a door or window frame; name what it IS, e.g. \
"door frame"). Pick the best everyday name from what you SEE -- \
lowercase, at most 3 words. The doubts are given as context; you are \
free to confirm the current name if the crops support it.
Return ONE fenced ```json block, a JSON ARRAY, one object per item, \
same order:
{{"id": "<the id given>", "name": "<chosen name>", "confidence": \
0.0-1.0, "reason": "one sentence"}}
Output ONLY the fenced JSON block.

{items}"""

T_REEX = """\
{firm}A 3D-scan extraction recorded physically implausible \
relationships between object pairs. For each case you get BOTH \
objects' crops (this contact sheet) plus their exact box coordinates.
  {sheet}
Tile labels: "2A-a" = case 2, object A, crop a; "2B-a" = case 2, \
object B, crop a.

For EACH case, decide from pixels + numbers what is physically true:
  "CONFIRM"     -- the recorded relationship is actually right
  "REJECT"      -- no meaningful relationship; boxes merely overlap
  "REINTERPRET" -- something else is true (state it)
Also name the box most likely wrong/oversized ("suspect_box"), or null.
Return ONE fenced ```json block, a JSON ARRAY, one object per case, \
same order:
{{"case": <n>, "edge_verdict": "CONFIRM|REJECT|REINTERPRET", \
"true_arrangement": "one specific spatial sentence", \
"suspect_box": "<id or null>", "confidence": 0.0-1.0, \
"reason": "one sentence"}}
Output ONLY the fenced JSON block.

{items}"""

FIRM = ("Your previous response was malformed. This time output ONLY "
        "one fenced ```json code block containing the JSON array, no "
        "prose.\n\n")


# ---------------------------------------------------------------- shared

def claude_env():
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(k, None)
    return env


def call_claude(prompt, cwd, model):
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("[cases] claude.exe not on PATH")
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
            raise RuntimeError(f"claude API/auth error: {out[:400]}")
    return out


def parse_array(text):
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    raw = m.group(1) if m else None
    if raw is None:
        i = text.find("[")
        if i >= 0:
            try:
                arr, _ = json.JSONDecoder().raw_decode(text[i:])
                raw = json.dumps(arr)
            except ValueError:
                return None
        else:
            return None
    try:
        arr = json.loads(raw)
    except ValueError:
        return None
    return arr if isinstance(arr, list) else None


def node_crops(nid, det, crops_dir, k):
    members = sorted(det[nid]["evidence"].get("members", []),
                     key=lambda m: (-m.get("score", 0.0),
                                    m.get("member", 0)))
    out = []
    for m in members:
        p = crops_dir / m.get("crop", "")
        if m.get("crop") and p.exists():
            out.append(p)
        if len(out) == k:
            break
    return out


def cluster_all_crops(jn, det, crops_dir, k):
    out = []
    for mid in sorted(jn["members"]):
        out += node_crops(mid, det, crops_dir, k)
    return out[:k]


def build_sheet(tiles, sheet_path):
    """tiles: [(label, path)] -> numbered grid PNG."""
    cols = SHEET_COLS
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * TILE, rows * (TILE + LABEL_H)),
                      (245, 245, 245))
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


def facts(jn, floor_y):
    g = jn["geometry"]
    s = g["size"]
    return (f'{s[0]:.2f}x{s[2]:.2f}x{s[1]:.2f} m, footprint x '
            f'[{g["aabb_min"][0]:.2f},{g["aabb_max"][0]:.2f}] z '
            f'[{g["aabb_min"][2]:.2f},{g["aabb_max"][2]:.2f}], spans '
            f'{floor_y - g["aabb_max"][1]:.2f}-'
            f'{floor_y - g["aabb_min"][1]:.2f} m above the floor, '
            f'{jn["n_detections"]} views (peak {jn["peak_score"]:.2f})')


def best_member(jn, det):
    """Highest-scoring member detection that has a crop on disk."""
    best = None
    for mid in sorted(jn["members"]):
        for m in det[mid]["evidence"].get("members", []):
            if not m.get("crop"):
                continue
            if best is None or m.get("score", 0.0) > best.get("score", 0.0):
                best = m
    return best


def context_tile(jn, det, frames_dir, out_dir):
    """Zoomed-out evidence tile: the best member's source view with the
    detection box outlined in red, cropped to the box plus a generous
    margin (so the judge sees what the pixels belong to -- the obj_138
    lesson: a tight crop of a door frame reads as a picture frame).
    Returns the tile path, or None if the source frame is missing."""
    m = best_member(jn, det)
    if m is None:
        return None
    src = Path(frames_dir) / f'{m["view"]}.webp'
    if not src.exists():
        return None
    im = Image.open(src).convert("RGB")
    x0, y0, x1, y1 = m["box_2d"]
    ImageDraw.Draw(im).rectangle([x0, y0, x1, y1],
                                 outline=(255, 40, 40), width=4)
    pad = max(CTX_PAD_FACTOR * max(x1 - x0, y1 - y0), CTX_MIN_PAD)
    box = (max(0, int(x0 - pad)), max(0, int(y0 - pad)),
           min(im.width, int(x1 + pad)), min(im.height, int(y1 + pad)))
    out = Path(out_dir) / f'ctx_{jn["id"]}.png'
    im.crop(box).save(out)
    return out


def trunc_note(jn, det):
    """One prompt line when the box is truncated at the image edge --
    warns the judge it is looking at a fragment. '' when not."""
    tot = cut = 0
    for mid in sorted(jn["members"]):
        for m in det[mid]["evidence"].get("members", []):
            tot += 1
            if m.get("truncated"):
                cut += 1
    if cut == 0:
        return ""
    return (f"  CUT OFF at the image edge in {cut}/{tot} of its views "
            f"-- the visible pixels are a fragment; the true extent is "
            f"unknown.\n")


def build_exist_job(q_exist, det, crops_dir, frames_dir, sheets_dir,
                    floor_y):
    """Assemble the existence-resolution contact sheet + prompt items
    (tight crops + context tile + truncation facts). Shared by
    describe_nodes.py phase A and retry harnesses -- one code path so
    experiments exercise exactly what the pipeline runs."""
    tiles, items = [], []
    for i, (jn, f) in enumerate(q_exist, 1):
        crops = cluster_all_crops(jn, det, crops_dir, CROPS_EXIST)
        labs = []
        for k, p in enumerate(crops):
            lab = f"{i}{'abc'[k]}"
            labs.append(lab)
            tiles.append((lab, p))
        ctx = context_tile(jn, det, frames_dir, sheets_dir)
        if ctx is not None:
            lab = f"{i}x"
            labs.append(lab + " (context)")
            tiles.append((lab, ctx))
        items.append(
            f'Case {i}: id={jn["id"]}, currently named '
            f'"{jn["name"]}", tiles {", ".join(labs)} -- '
            f'{facts(jn, floor_y)}.\n'
            + trunc_note(jn, det)
            + f'  why doubted: {f["issue"] if f else "?"}\n'
            f'  hypotheses: '
            f'{"; ".join(f["hypotheses"]) if f else "?"}')
    sheet = Path(sheets_dir) / "cases_existence.png"
    build_sheet(tiles, sheet)
    return sheet, "\n\n".join(items)


def case_hash(*parts):
    h = hashlib.sha256()
    h.update(PROMPT_VERSION.encode())
    for p in parts:
        if isinstance(p, Path):
            h.update(p.read_bytes())
        else:
            h.update(str(p).encode())
    return h.hexdigest()[:32]


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--sheets-only", action="store_true")
    args = ap.parse_args()

    gdir = paths.scene_dir(args.scene)
    gpath = gdir / "scene_graph.json"
    crops_dir = gdir / "graph" / "crops"
    sheets_dir = gdir / "graph" / "case_sheets"
    cache_path = gdir / "graph" / "judge_cases_cache.json"
    graph = json.loads(gpath.read_text())
    judged = graph.get("judged")
    if not judged:
        raise SystemExit("[cases] run build_judged.py first")
    det = {n["id"]: n for n in graph["nodes"] if n["source"] == "detection"}
    floor_y = next(n for n in graph["nodes"] if n["id"] == "arch_floor")[
        "geometry"]["plane"]["value_raw"]
    jn_by_id = {jn["id"]: jn for jn in judged["nodes"]}
    flags = judged.get("coherence_flags", [])

    # ---- queue A: existence (disputed nodes + their flag) ----
    q_exist = []
    for jn in sorted(judged["nodes"], key=lambda n: n["id"]):
        if jn.get("existence") != "disputed":
            continue
        f = next((f for f in flags
                  if f["target"].split("->")[0] == jn["id"]
                  and f["suggested_action"] == "existence_disputed"), None)
        q_exist.append((jn, f))

    # ---- queue B: rename (coherence rename_candidates +
    #      appearance label_agreement false), non-disputed only ----
    doubts = {}
    for f in flags:
        if f["suggested_action"] == "rename_candidate" \
                and f["target"] in jn_by_id:
            doubts.setdefault(f["target"], []).append(
                "plausibility check: " + f["issue"])
    for jn in judged["nodes"]:
        a = jn.get("appearance")
        if a and not a.get("label_agreement"):
            doubts.setdefault(jn["id"], []).append(
                "appearance check: " + a["description"])
    # nodes this module already pixel-renamed don't re-queue on stale
    # doubts (their appearance re-describes under the new name later)
    q_rename = [(jn_by_id[i], doubts[i]) for i in sorted(doubts)
                if jn_by_id[i].get("existence") != "disputed"
                and jn_by_id[i].get("naming", {}).get("source")
                != "judge_cases"]

    # ---- queue C: re-examine (escalation flags on edges) ----
    q_reex = []
    for f in flags:
        if f["suggested_action"] != "reexamine_with_crops":
            continue
        ids = [x for x in f["target"].split("->") if x in jn_by_id]
        if len(ids) == 2:
            q_reex.append((f, ids))

    print(f"[cases] queues: existence {len(q_exist)}, rename "
          f"{len(q_rename)}, re-examine {len(q_reex)}")

    sheets_dir.mkdir(parents=True, exist_ok=True)
    cache = (json.loads(cache_path.read_text())
             if cache_path.exists() else {"meta": {"calls": 0},
                                          "cases": {}})
    jobs = []          # (kind, prompt_template, sheet, items, cases)
    crops_by_id = {}   # cluster id -> crop paths (hash evidence; NEVER
                       # stored on the node -- Paths must not reach json)

    # existence sheet
    if q_exist:
        tiles, items = [], []
        for i, (jn, f) in enumerate(q_exist, 1):
            crops = cluster_all_crops(jn, det, crops_dir, CROPS_EXIST)
            labs = []
            for k, p in enumerate(crops):
                lab = f"{i}{'abc'[k]}"
                labs.append(lab)
                tiles.append((lab, p))
            hyp = "; ".join(f["hypotheses"]) if f else "?"
            issue = f["issue"] if f else "?"
            items.append(
                f'Case {i}: id={jn["id"]}, currently named '
                f'"{jn["name"]}", tiles {", ".join(labs)} -- '
                f'{facts(jn, floor_y)}.\n'
                f'  why doubted: {issue}\n  hypotheses: {hyp}')
            crops_by_id[jn["id"]] = crops
        sheet = sheets_dir / "cases_existence.png"
        build_sheet(tiles, sheet)
        jobs.append(("existence", T_EXIST, sheet, "\n\n".join(items),
                     q_exist))

    # rename sheet
    if q_rename:
        tiles, items = [], []
        for i, (jn, why) in enumerate(q_rename, 1):
            crops = cluster_all_crops(jn, det, crops_dir, CROPS_RENAME)
            labs = []
            for k, p in enumerate(crops):
                lab = f"{i}{'ab'[k]}"
                labs.append(lab)
                tiles.append((lab, p))
            items.append(
                f'Item {i}: id={jn["id"]}, current name "{jn["name"]}", '
                f'tiles {", ".join(labs)} -- {facts(jn, floor_y)}.\n'
                + "\n".join(f"  doubt: {w}" for w in why))
            crops_by_id[jn["id"]] = crops
        sheet = sheets_dir / "cases_rename.png"
        build_sheet(tiles, sheet)
        jobs.append(("rename", T_RENAME, sheet, "\n\n".join(items),
                     q_rename))

    # re-examine sheets (4 cases per sheet: 16 tiles)
    for si in range(0, len(q_reex), 4):
        chunk = q_reex[si:si + 4]
        tiles, items = [], []
        for ci, (f, (ida, idb)) in enumerate(chunk, 1):
            n = si + ci
            ja, jb = jn_by_id[ida], jn_by_id[idb]
            labs = {"A": [], "B": []}
            for side, jn in (("A", ja), ("B", jb)):
                crops = cluster_all_crops(jn, det, crops_dir, CROPS_REEX)
                for k, p in enumerate(crops):
                    lab = f"{n}{side}-{'ab'[k]}"
                    labs[side].append(lab)
                    tiles.append((lab, p))
            items.append(
                f'Case {n}: recorded fact: {f["issue"]}\n'
                f'  A = {ida} "{ja["name"]}", tiles '
                f'{", ".join(labs["A"])} -- {facts(ja, floor_y)}\n'
                f'  B = {idb} "{jb["name"]}", tiles '
                f'{", ".join(labs["B"])} -- {facts(jb, floor_y)}')
        sheet = sheets_dir / f"cases_reexamine_{si // 4 + 1}.png"
        build_sheet(tiles, sheet)
        jobs.append(("reexamine", T_REEX, sheet, "\n\n".join(items),
                     chunk))

    if args.sheets_only:
        for kind, tmpl, sheet, items, _ in jobs:
            print(f"\n[cases] ===== {kind} prompt ({sheet}) =====")
            print(tmpl.format(firm="", sheet=sheet, items=items))
        print(f"\n[cases] SHEETS-ONLY -- {len(jobs)} calls prepared, "
              f"none made, no write-back")
        return

    # ---- live calls ----
    def run(job):
        kind, tmpl, sheet, items, cases = job
        for attempt, firm in ((1, False), (2, True)):
            prompt = tmpl.format(firm=FIRM if firm else "", sheet=sheet,
                                 items=items)
            try:
                out = call_claude(prompt, sheets_dir, args.model)
            except (RuntimeError, subprocess.TimeoutExpired) as ex:
                print(f"[cases]   {kind}: call failed ({ex})")
                continue
            arr = parse_array(out)
            if arr is not None and len(arr) >= 1:
                return arr
            print(f"[cases]   {kind}: malformed (attempt {attempt})")
        return None

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        results = list(ex.map(run, jobs))
    cache["meta"]["calls"] = cache["meta"].get("calls", 0) + len(jobs)

    today = date.today().isoformat()
    prov = {"model": args.model, "date": today,
            "prompt_version": PROMPT_VERSION, "source": "judge_cases"}
    summary = {"confirmed": [], "rejected": [], "unclear": [],
               "renamed": [], "edges": []}

    for (kind, _, _, _, cases), arr in zip(jobs, results):
        if arr is None:
            print(f"[cases] {kind}: FAILED -- statuses unchanged")
            continue
        if kind == "existence":
            by_id = {e.get("id"): e for e in arr if isinstance(e, dict)}
            for jn, f in cases:
                e = by_id.get(jn["id"])
                if not e or e.get("verdict") not in EXIST_VERDICTS:
                    summary["unclear"].append(jn["id"] + " (no verdict)")
                    continue
                v = {**{k: e.get(k) for k in
                        ("verdict", "what_it_is", "confidence", "reason")},
                     **prov,
                     "evidence_hash": case_hash(
                         jn["id"], *crops_by_id.get(jn["id"], []))}
                jn["existence_verdict"] = v
                if e["verdict"] == "REAL":
                    jn["existence"] = "confirmed"
                    wi = e.get("what_it_is")
                    if isinstance(wi, str) and wi.strip():
                        # names stay short: first clause, max 3 words
                        # (the verdict may answer in a full phrase --
                        # "small box or pot on windowsill" -> "small box")
                        short = re.split(r"\b(?:or|on|in|with|near|beside)"
                                         r"\b", wi.strip().lower())[0]
                        short = " ".join(short.split()[:3]).strip(" ,;-")
                        if short and short != jn["name"]:
                            jn["name"] = short
                            jn["naming"] = {**prov,
                                            "reason": e.get("reason"),
                                            "what_it_is_full": wi.strip(),
                                            "via": "existence_verdict"}
                    summary["confirmed"].append(
                        f'{jn["id"]}={jn["name"]}')
                elif e["verdict"] == "NOT_REAL":
                    jn["existence"] = "rejected"
                    summary["rejected"].append(jn["id"])
                else:
                    summary["unclear"].append(jn["id"])
                cache["cases"][f'exist:{jn["id"]}'] = v
        elif kind == "rename":
            by_id = {e.get("id"): e for e in arr if isinstance(e, dict)}
            for jn, _ in cases:
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
                summary["renamed"].append(f'{jn["id"]}: {old} -> '
                                          f'{jn["name"]}')
                cache["cases"][f'rename:{jn["id"]}'] = jn["naming"]
        else:  # reexamine
            by_case = {e.get("case"): e for e in arr
                       if isinstance(e, dict)}
            base = q_reex.index(cases[0]) + 1
            for off, (f, (ida, idb)) in enumerate(cases):
                e = by_case.get(base + off)
                if not e or e.get("edge_verdict") not in EDGE_VERDICTS:
                    continue
                v = {**{k: e.get(k) for k in
                        ("edge_verdict", "true_arrangement",
                         "suspect_box", "confidence", "reason")}, **prov}
                # attach to the matching judged edge(s)
                for je in judged["edges"]:
                    if {je["a"], je["b"]} == {ida, idb}:
                        je["case_verdict"] = v
                f["resolution"] = v
                summary["edges"].append(
                    f'{ida}~{idb}: {e["edge_verdict"]} -- '
                    f'{e.get("true_arrangement", "")[:80]}')
                cache["cases"][f'reex:{ida}~{idb}'] = v

    judged["cases_meta"] = {**prov,
                            "calls": len(jobs), "summary": summary}
    cache_path.write_text(json.dumps(cache, indent=1))
    gpath.write_text(json.dumps(graph, indent=1))

    print(f"[cases] wrote {gpath}")
    for k, v in summary.items():
        print(f"[cases] {k} ({len(v)}):")
        for line in v:
            print(f"           {line}")


if __name__ == "__main__":
    main()
