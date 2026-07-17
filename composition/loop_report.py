"""Build a browsable HTML report of what the refinement loop did, edit by
edit, from package/edits.jsonl + the renders in package/loop/.

For every attempted edit (in journal order): the edit itself, verdict +
reason, and ORIGINAL / BEFORE / AFTER image strips for the views where the
edit actually changed pixels (computed by image diff — the other views are
noise). Geometrically invalid edits (never rendered) get a text row.

Output: package/loop/report.html — static, double-click to open, images
referenced relative so the folder stays self-contained.

Run:  python loop_report.py --scene bedroom_marble
"""
import argparse
import html
import json

import numpy as np
from PIL import Image

from comp_paths import paths

DIFF_THRESH = 8      # per-channel intensity delta that counts as changed
MIN_PX = 50          # ignore views with fewer changed pixels (antialias jitter)
MAX_VIEWS = 3        # show at most this many views per edit (most-changed first)

CSS = """
body { font-family: system-ui, sans-serif; margin: 20px; background: #fafafa; }
h1 { font-size: 1.3em; } h2 { font-size: 1.05em; margin: 28px 0 6px; }
.edit { border: 1px solid #ddd; border-left: 6px solid #999; background: #fff;
        padding: 10px 14px; margin: 10px 0; }
.edit.accepted { border-left-color: #2e9e44; }
.edit.worse    { border-left-color: #c33; }
.edit.neutral  { border-left-color: #888; }
.edit.invalid  { border-left-color: #d90; }
.verdict { font-weight: 600; text-transform: uppercase; }
.edit.accepted .verdict { color: #2e9e44; } .edit.worse .verdict { color: #c33; }
.edit.neutral .verdict { color: #666; }    .edit.invalid .verdict { color: #b70; }
.why { color: #444; margin: 4px 0 8px; }
.key { font-family: monospace; font-size: 0.85em; color: #666; }
.strip { display: flex; gap: 8px; margin: 6px 0; flex-wrap: wrap; }
.cell { text-align: center; font-size: 0.78em; color: #555; }
.cell img { width: 290px; display: block; border: 1px solid #ccc; }
.cell a { color: inherit; }
.issues { font-size: 0.85em; color: #555; margin: 2px 0 0 0; }
.nopix { color: #999; font-style: italic; }
"""


def _diff_px(a, b):
    ia = np.asarray(Image.open(a).convert("RGB"), np.int16)
    ib = np.asarray(Image.open(b).convert("RGB"), np.int16)
    if ia.shape != ib.shape:
        return -1
    return int((np.abs(ia - ib).max(axis=2) > DIFF_THRESH).sum())


def _img_cell(loopdir, name, label):
    if not (loopdir / name).exists():
        return f'<div class="cell nopix">{label}<br>missing</div>'
    return (f'<div class="cell"><a href="{name}" target="_blank">'
            f'<img src="{name}" loading="lazy"></a>{label}</div>')


def build(sc):
    pkg = paths.package_dir(sc)
    loopdir = pkg / "loop"
    recs = [json.loads(l) for l in
            (pkg / "edits.jsonl").read_text().splitlines() if l.strip()]

    # view stems ever used, from the target files on disk
    stems = sorted(p.stem.replace("target_", "")
                   for p in loopdir.glob("target_*.png"))

    out = [f"<style>{CSS}</style>",
           f"<h1>Loop report — {sc}</h1>",
           f"<p>{len(recs)} attempted edits from edits.jsonl. Color: "
           f"<b style='color:#2e9e44'>accepted</b> / "
           f"<b style='color:#c33'>worse</b> / "
           f"<b style='color:#666'>neutral (reverted)</b> / "
           f"<b style='color:#b70'>rejected before render</b>. "
           f"Images: ORIGINAL = splat target, BEFORE / AFTER = mesh-only "
           f"recreation around this one edit; only views where the edit "
           f"changed pixels are shown. Click an image for full size.</p>"]

    cur_iter = None
    # BEFORE render prefix per iteration: starts at itNN_cur_, advances to the
    # accepted edit's prefix when an edit is accepted mid-iteration
    before_prefix = None
    for i, r in enumerate(recs):
        it = r.get("iter", -1)
        if it != cur_iter:
            cur_iter = it
            before_prefix = f"it{it:02d}_cur_"
            out.append(f"<h2>Iteration {it}</h2>")
            critf = loopdir / f"critique_it{it:02d}.json"
            if critf.exists():
                crit = json.loads(critf.read_text())
                iss = "; ".join(
                    f'[{x.get("view","?")}] {x.get("kind","?")}: '
                    f'{x.get("detail","")}' for x in crit.get("issues", []))
                if iss:
                    out.append(f'<p class="issues">critique issues: '
                               f'{html.escape(iss)}</p>')

        edit = r["edit"]
        if not r.get("valid", True):
            cls, verdict, why = "invalid", "rejected (geometry)", r.get("reason", "")
        else:
            v = r.get("verdict", "?")
            cls = "accepted" if r.get("accepted") else (
                "worse" if v == "worse" else "neutral")
            verdict = "accepted" if r.get("accepted") else f"{v} → reverted"
            why = r.get("why", "")
        desc = (f'add "{edit.get("label")}" at {edit.get("center")} '
                f'size {edit.get("size")}' if edit.get("op") == "add" else
                f'nudge {edit.get("id")} dpos={edit.get("dpos")} '
                f'dyaw={edit.get("dyaw_deg", 0)} dscale={edit.get("dscale", 1)}')
        out.append(f'<div class="edit {cls}">'
                   f'<span class="verdict">{verdict}</span> — '
                   f'{html.escape(desc)}'
                   f'<div class="why">{html.escape(why)}</div>'
                   f'<div class="key">{html.escape(r.get("key", ""))}</div>')

        if r.get("valid", True):
            # this edit's AFTER prefix, from the journal's render paths
            after_prefix = None
            for p in r.get("renders", []):
                name = p.replace("\\", "/").rsplit("/", 1)[-1]
                for st in stems:
                    if name.endswith(f"{st}.png"):
                        after_prefix = name[: -len(f"{st}.png")]
                        break
                if after_prefix:
                    break
            if after_prefix:
                ranked = []
                for st in stems:
                    b = loopdir / f"{before_prefix}{st}.png"
                    a = loopdir / f"{after_prefix}{st}.png"
                    if b.exists() and a.exists():
                        n = _diff_px(b, a)
                        if n >= MIN_PX:
                            ranked.append((n, st))
                ranked.sort(reverse=True)
                if not ranked:
                    out.append('<div class="nopix">no view shows a pixel '
                               'change (below noise threshold)</div>')
                for n, st in ranked[:MAX_VIEWS]:
                    out.append(f'<div class="strip">'
                               + _img_cell(loopdir, f"target_{st}.png",
                                           f"ORIGINAL {st}")
                               + _img_cell(loopdir, f"{before_prefix}{st}.png",
                                           f"BEFORE {st}")
                               + _img_cell(loopdir, f"{after_prefix}{st}.png",
                                           f"AFTER {st} — {n:,} px changed")
                               + "</div>")
                if r.get("accepted"):
                    before_prefix = after_prefix
            else:
                out.append('<div class="nopix">renders not on disk for this '
                           'edit (older run?)</div>')
        out.append("</div>")

    outf = loopdir / "report.html"
    outf.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {outf}")
    return outf


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    args = ap.parse_args()
    build(args.scene)
