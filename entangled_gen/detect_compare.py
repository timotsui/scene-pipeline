"""DETECT bake-off page: GroundingDINO+SAM (ours) vs OWLv2 (analyzer) on the
SAME sweep frames with the SAME vocab.json word list.

Ours   = seg_sweep/detections.json (raw per-frame, top-20, thr 0.35)
Theirs = analyzer/<job>/interactions.json frame_annotations — POST-VOTE
         survivors only (the tool never writes pre-vote detections), so the
         comparison is raw-vs-survivors by construction; the page says so.

Writes OUT/<scene>/detect_compare/frame_XXXX_owlv2.png (their boxes drawn)
and OUT/<scene>/detect_compare.html (ours = seg_sweep's existing *_boxes.png).

  python detect_compare.py --scene bedroom_marble
"""
import argparse, json, math
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw

import paths
from vocab_from_prompt import canonicalize

COLORS = ["#00e5ff", "#ffd24d", "#ff7ad0", "#7dff8a", "#ffa25e", "#b0a2ff"]


def frame_azel(t, fp):
    for f in t["frames"]:
        if f["file_path"] == fp:
            m = f["transform_matrix"]
            fx, fy, fz = m[0][2], m[1][2], m[2][2]
            az = (math.degrees(math.atan2(fx, fz)) + 360.0) % 360.0
            el = math.degrees(math.asin(max(-1.0, min(1.0, -fy))))
            return f["position_idx"], az, el
    return None, 0, 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--job", default="job_high")
    args = ap.parse_args()
    sc = args.scene
    sdir = paths.scene_dir(sc)
    jdir = sdir / "analyzer" / args.job
    seg_dir = sdir / "seg_sweep"
    out_dir = sdir / "detect_compare"
    out_dir.mkdir(exist_ok=True)

    ours = json.loads((seg_dir / "detections.json").read_text())
    inter = json.loads((jdir / "interactions.json").read_text())
    trans = json.loads((jdir / "transforms.json").read_text())
    vocab = json.loads((sdir / "vocab.json").read_text())
    known = list(vocab["canonical"].keys())
    pano_dir = sdir / "seg_pano_v2"     # ours on pano crops, same vocab.json
    pano = (json.loads((pano_dir / "detections.json").read_text())
            if (pano_dir / "detections.json").exists() else {})

    theirs = {}   # frame stem -> [{label, score, box[x1,y1,x2,y2]}]
    for fidx, anns in (inter.get("frame_annotations") or {}).items():
        stem = f"frame_{int(fidx):04d}"
        theirs[stem] = [{"label": a["label"], "score": a.get("score", 0),
                         "box": a["box"]} for a in anns]

    # ---- their overlays ----
    for stem, dets in theirs.items():
        src = jdir / "frames" / f"{stem}.png"
        if not src.exists():
            continue
        img = Image.open(src).convert("RGB")
        dr = ImageDraw.Draw(img)
        for i, d in enumerate(dets):
            c = COLORS[i % len(COLORS)]
            x1, y1, x2, y2 = d["box"]
            dr.rectangle([x1, y1, x2, y2], outline=c, width=2)
            dr.text((x1 + 2, max(0, y1 - 11)), f'{d["label"]} {d["score"]:.2f}', fill=c)
        img.save(out_dir / f"{stem}_owlv2.png")

    # ---- per-label canonical counts ----
    def counts(detmap):
        c = Counter()
        for dets in detmap.values():
            for d in dets:
                c[canonicalize(d["label"], vocab=known) or d["label"]] += 1
        return c
    co, ct, cp = counts(ours), counts(theirs), counts(pano)
    labels = sorted(set(co) | set(ct) | set(cp), key=lambda k: -(co[k] + ct[k] + cp[k]))
    n_ours = sum(co.values()); n_theirs = sum(ct.values()); n_pano = sum(cp.values())
    f_ours = sum(1 for v in ours.values() if v)
    f_theirs = sum(1 for v in theirs.values() if v)

    rows = "".join(
        f"<tr><td>{lb}</td><td>{co.get(lb, 0)}</td><td>{ct.get(lb, 0)}</td>"
        f"<td>{cp.get(lb, 0)}</td></tr>"
        for lb in labels)

    # ---- per-frame gallery grouped by standpoint ----
    stems = sorted(set(ours) | set(theirs))
    by_pos = {}
    for st in stems:
        pos, az, el = frame_azel(trans, f"frames/{st}.png")
        by_pos.setdefault(pos, []).append((el, az, st))
    sections = []
    for pos in sorted(by_pos, key=lambda p: (p is None, p)):
        cells = []
        for el, az, st in sorted(by_pos[pos], key=lambda t: (-t[0], t[1])):
            our_img = f"seg_sweep/{st}_boxes.png"
            their_img = f"detect_compare/{st}_owlv2.png"
            has_their = (out_dir / f"{st}_owlv2.png").exists()
            no = len(ours.get(st, [])); nt = len(theirs.get(st, []))
            if no == 0 and nt == 0:
                continue
            cells.append(
                f'<div class="pair"><div class="cap">{st} · az {az:.0f}° el {el:+.0f}° '
                f'· ours {no} · theirs {nt}</div>'
                f'<div class="imgs"><figure><img loading="lazy" src="{our_img}">'
                f'<figcaption>ours (raw, thr .35)</figcaption></figure>'
                + (f'<figure><img loading="lazy" src="{their_img}">'
                   f'<figcaption>theirs (post-vote)</figcaption></figure>'
                   if has_their else '<figure class="none">no surviving OWLv2 boxes</figure>')
                + '</div></div>')
        if cells:
            sections.append(f'<section><h2>standpoint {pos}</h2>{"".join(cells)}</section>')

    # ---- pano-crop gallery (ours only — sharper pixels, same vocab) ----
    if pano:
        cells = []
        for st in sorted(pano):
            n = len(pano.get(st, []))
            if n == 0:
                continue
            cells.append(
                f'<div class="pair"><div class="cap">{st} · ours {n}</div>'
                f'<div class="imgs"><figure><img loading="lazy" '
                f'src="seg_pano_v2/{st}_boxes.png">'
                f'<figcaption>ours on pano crop (raw, thr .35)</figcaption></figure>'
                f'</div></div>')
        sections.append('<section><h2>pano crops — ours (no analyzer '
                        'equivalent: it never sees the pano)</h2>'
                        + "".join(cells) + '</section>')

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DETECT bake-off — GroundingDINO+SAM vs OWLv2 ({sc})</title>
<style>
 body {{ font-family: "Segoe UI", system-ui, sans-serif; margin: 0; background: #F3F5F7; color: #1C2530; }}
 @media (prefers-color-scheme: dark) {{ body {{ background:#141A21; color:#DCE3EA; }}
  table, .pair, figure {{ background:#1C242E !important; border-color:#2C3742 !important; }} }}
 .wrap {{ max-width: 1240px; margin: 0 auto; padding: 24px 20px 80px; }}
 h1 {{ font-size: 21px; margin: 0 0 6px; }}
 .sub {{ color: #5A6B7E; font-size: 13px; max-width: 78ch; line-height: 1.5; }}
 table {{ border-collapse: collapse; background: #fff; border: 1px solid #D5DCE3;
          border-radius: 8px; margin: 14px 0 22px; font-size: 13px; }}
 td, th {{ padding: 4px 14px; border-bottom: 1px solid #D5DCE3; text-align: left; }}
 h2 {{ font-size: 15px; margin: 22px 0 8px; }}
 .pair {{ background: #fff; border: 1px solid #D5DCE3; border-radius: 8px;
          padding: 8px; margin-bottom: 10px; }}
 .cap {{ font-size: 12px; color: #5A6B7E; font-family: Consolas, monospace; margin-bottom: 6px; }}
 .imgs {{ display: flex; gap: 10px; flex-wrap: wrap; }}
 figure {{ margin: 0; }}
 figure img {{ width: 384px; max-width: 45vw; border-radius: 4px; display: block; }}
 figcaption {{ font-size: 11px; color: #5A6B7E; text-align: center; padding-top: 3px; }}
 figure.none {{ width: 384px; display: flex; align-items: center; justify-content: center;
                color: #8B97A3; font-size: 12px; border: 1px dashed #D5DCE3; border-radius: 4px; }}
</style></head><body><div class="wrap">
<h1>DETECT bake-off — same 192 frames, same vocab.json</h1>
<p class="sub"><b>Asymmetry disclosed:</b> ours = raw per-frame GroundingDINO+SAM
(threshold 0.35, top-20/frame); theirs = OWLv2 detections that SURVIVED the
analyzer's vote filter (≥8 frames + peak ≥0.40) — the tool never writes its
raw pre-vote boxes. Labels in the table are canonicalized both sides.
Ours: <b>{n_ours}</b> detections in <b>{f_ours}</b> frames ·
theirs: <b>{n_theirs}</b> surviving boxes in <b>{f_theirs}</b> frames ·
ours on the {len(pano)} pano crops: <b>{n_pano}</b> detections (sharper
pixels, same vocab — the analyzer has no pano equivalent).</p>
<table><tr><th>label (canonical)</th><th>ours · sweep</th><th>theirs · sweep (post-vote)</th><th>ours · pano crops</th></tr>{rows}</table>
{''.join(sections)}
</div></body></html>"""
    out = sdir / "detect_compare.html"
    out.write_text(html, encoding="utf-8")
    print("wrote", out)
    print(f"ours {n_ours} dets / {f_ours} frames · theirs {n_theirs} boxes / {f_theirs} frames")


if __name__ == "__main__":
    main()
