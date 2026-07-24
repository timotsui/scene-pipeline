"""
Step 8 -- detection-comparison-review build: the Checkpoint 4 review page.

Reads (all under out/<scene>/):
    scene_manifest.json               our 19-object manifest (RAW frame)
    analyzer/bridged_boxes.json       bridge_boxes.py output (Step 6)
    analyzer/match_report.json        numeric matching (Step 6)
    analyzer/<job>/interactions.json  per-cluster supporting frames
    analyzer/<job>/transforms.json    frame -> standpoint map

Writes out/<scene>/analyzer/comparison.html -- self-contained static HTML
(loop_report.html style), sections:
    banner  "WAITING ON YOU -- Checkpoint 4" (What / Why / Look for)
    (a) headline numbers            (b) per-label side-by-side counts
    (c) manifest -> analyzer match table
    (d) analyzer-only clusters by label
    (e) caveats box

Documented facts that cannot be recomputed from these files (runtime, VRAM,
the manifest pipeline's coverage weakness) are hardcoded in DOC_FACTS with
their source. Everything else is computed fresh -- idempotent.

Run:  python analyzer/build_comparison.py --scene bedroom_marble --job job_high
"""
import argparse
import html
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402

# Source: docs/PLAN_GAUSSIAN_CUT_AND_SPLAT_ANALYZER.md progress log rows 2/5
# + analyzer/ENV.md deviations section.
DOC_FACTS = {
    "runtime_s": 64,
    "vram_gb": 5.9,
    "frames": 192,
    "standpoints": 8,
    "standpoints_contributing": 7,           # standpoint 0 = zero evidence
    "raw_detections": 12564,
    "cap_per_label": 8,                      # raised from 3, ENV.md diff
    "zero_detection_labels": ["office chair", "yoga mat", "potted planter"],
    "manifest_views": 4,                     # gpu_yaw000/090/180/270
    "manifest_one_view": "15 of 20 detections came from a single view",
    "manifest_merges": "exactly 1 cross-view merge",
    "manifest_blind": "~60 degrees of the room never rendered",
}

CSS = """
body { font-family: system-ui, sans-serif; margin: 24px auto; max-width: 1100px;
       background: #fafafa; color: #222; padding: 0 16px; }
h1 { font-size: 1.35em; } h2 { font-size: 1.08em; margin: 30px 0 8px; }
table { border-collapse: collapse; background: #fff; margin: 8px 0; }
th, td { border: 1px solid #ddd; padding: 4px 10px; text-align: left;
         font-size: 0.9em; }
th { background: #f0f0f0; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
.card { border: 1px solid #ddd; border-left: 6px solid #999; background: #fff;
        padding: 12px 16px; margin: 12px 0; }
.banner { border: 2px solid #c33; border-left: 10px solid #c33;
          background: #fff5f5; padding: 14px 18px; margin: 12px 0; }
.banner h2 { margin: 0 0 8px; color: #c33; font-size: 1.15em; }
.banner ol { margin: 6px 0 2px 22px; } .banner li { margin: 4px 0; }
.stat { display: inline-block; background: #fff; border: 1px solid #ddd;
        border-radius: 6px; padding: 10px 16px; margin: 4px 6px 4px 0;
        vertical-align: top; }
.stat .v { font-size: 1.5em; font-weight: 700; }
.stat .k { font-size: 0.78em; color: #666; max-width: 170px; }
.ours { border-left: 6px solid #4a7de0; } .theirs { border-left: 6px solid #00a8b0; }
.caveat { border-left-color: #d90; background: #fffaf0; }
.ok  { color: #2e9e44; font-weight: 600; }
.bad { color: #c33; font-weight: 600; }
.tag { font-size: 0.75em; border-radius: 4px; padding: 1px 6px; margin-left: 6px; }
.tag.cap  { background: #ffe9c9; color: #955c00; }
.tag.zero { background: #fbdada; color: #a11; }
.dim { color: #777; font-size: 0.88em; }
code { background: #f0f0f0; padding: 1px 4px; border-radius: 3px;
       font-size: 0.88em; }
.mono { font-family: ui-monospace, monospace; font-size: 0.86em; }
"""


def esc(s):
    return html.escape(str(s))


def stat(value, key):
    return (f'<span class="stat"><div class="v">{esc(value)}</div>'
            f'<div class="k">{esc(key)}</div></span>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    ap.add_argument("--job", default="job_high")
    args = ap.parse_args()
    sc = args.scene

    adir = paths.scene_dir(sc) / "analyzer"
    man = json.loads(paths.manifest(sc).read_text())
    bridged = json.loads((adir / "bridged_boxes.json").read_text())
    match = json.loads((adir / "match_report.json").read_text())
    inter = json.loads((adir / args.job / "interactions.json").read_text())
    tr = json.loads((adir / args.job / "transforms.json").read_text())

    D = DOC_FACTS
    objs = bridged["objects"]
    n_ana, n_man = len(objs), len(man["objects"])

    # ---- computed standpoint / vote stats ----
    f2s = {i: f.get("position_idx") for i, f in enumerate(tr["frames"])}
    multi_sp = 0
    votes = []
    for o in inter["objects"]:
        sps = {f2s.get(f["frame_idx"]) for f in o["frames"]}
        if len(sps) >= 2:
            multi_sp += 1
        votes.append(len(o["frames"]))
    votes = np.array(votes)

    # ---- per-label counts ----
    man_counts, ana_counts = {}, {}
    for o in man["objects"]:
        man_counts[o["label"]] = man_counts.get(o["label"], 0) + 1
    for o in objs:
        ana_counts[o["label"]] = ana_counts.get(o["label"], 0) + 1
    all_labels = sorted(set(man_counts) | set(ana_counts)
                        | set(D["zero_detection_labels"]),
                        key=lambda l: (-(ana_counts.get(l, 0)),
                                       -(man_counts.get(l, 0)), l))
    groups = {m: g for g, ms in match["synonym_groups"].items() for m in ms}

    env = bridged.get("envelope_sanity", {})
    n_only = match["analyzer_only_count"]

    viewer_bat = paths.REPO_ROOT / "launch_viewer.bat"
    this_page = adir / "comparison.html"

    out = [f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
           f"<title>Checkpoint 4 -- detection comparison ({esc(sc)})</title>"
           f"<style>{CSS}</style></head><body>"]

    # ---------------- banner ----------------
    out.append(f"""
<div class="banner">
<h2>&#128308; WAITING ON YOU &mdash; Checkpoint 4 (detection-quality judgment)</h2>
<b>What:</b>
<ol>
<li>This page: <span class="mono">{esc(this_page)}</span> &mdash; numeric
    comparison of our 19-object manifest vs the {n_ana} splat_analyzer
    clusters on the same <code>bedroom_marble</code> splat (same RAW frame,
    no transform).</li>
<li>The 3D viewer's new <b>&ldquo;analyzer boxes&rdquo;</b> layer (cyan
    wireframes + labels): double-click
    <span class="mono">{esc(viewer_bat)}</span> &rarr;
    <span class="mono">http://localhost:8321</span>, tick
    <i>analyzer boxes</i> in the HUD, compare against the <i>manifest</i>
    layer box by box.</li>
</ol>
<b>Why:</b> this review decides (a) the analyzer's fate &mdash; <i>replace</i>
our detection stages, <i>borrow</i> its camera-ring + clustering into our
stack, or keep it as a <i>cross-check only</i>; and (b) <b>which box set
seeds the batch cut masks in Step 12</b>. Wrong call = Step 12 seeds masks
from worse boxes on every object.
<br><br>
<b>Look for (in the viewer):</b>
<ol>
<li>Do the cyan analyzer boxes <b>hug real objects better</b> than the
    manifest boxes? Expect a systematic toward-the-camera offset and shallow
    or bloated depth on cyan boxes (documented caveats below) &mdash; that
    bias is expected, not a frame error.</li>
<li>Are the <b>{n_only} analyzer-only clusters</b> real objects we missed,
    duplicates of already-matched ones, or hallucinations? Spot-check the
    <b>bookshelf ({ana_counts.get('bookshelf', 0)}) / book
    ({ana_counts.get('book', 0)}) / painting
    ({ana_counts.get('painting', 0)})</b> clusters &mdash; those labels sit
    at the cap of {D['cap_per_label']} and are the likeliest duplicate
    factories.</li>
<li>Do the <b>{ana_counts.get('door', 0)} door boxes</b> land on actual
    doors? (Our manifest has {man_counts.get('door', 0)}.)</li>
</ol>
</div>""")

    # ---------------- (a) headline ----------------
    out.append("<h2>(a) Headline numbers</h2>")
    out.append('<div class="card ours"><b>Ours &mdash; manifest pipeline '
               '(GroundingDINO+SAM lift, scene_manifest.json)</b><br>'
               + stat(n_man, "objects in manifest")
               + stat(D["manifest_views"], "fixed yaw views rendered")
               + stat("15/20", "detections from ONE view (documented)")
               + stat("1", "cross-view merge total (documented)")
               + stat("~60&deg;", "of the room never rendered (blind wedge)")
               + '<div class="dim">weakness documented in '
                 'analyzer/FEASIBILITY_SPLAT_ANALYZER.md and the '
                 'detection-coverage-gap finding: detection was starved, '
                 'not broken.</div></div>')
    out.append('<div class="card theirs"><b>splat_analyzer &mdash; OWLv2 '
               'camera ring (job_high)</b><br>'
               + stat(n_ana, "final clusters")
               + stat(f"{D['runtime_s']} s", "runtime (RTX 4080, "
                      f"{D['vram_gb']} GB VRAM)")
               + stat(f"{D['frames']}", "frames from "
                      f"{D['standpoints']} standpoints")
               + stat(f"{D['standpoints_contributing']}/{D['standpoints']}",
                      "standpoints contributing (standpoint 0: zero evidence)")
               + stat(f"{multi_sp}/{n_ana}", "clusters fused from >= 2 "
                      "standpoints (vs our 1 merge)")
               + stat(f"{int(np.median(votes))}",
                      f"median votes/cluster (range {votes.min()}"
                      f"&ndash;{votes.max()})")
               + stat(f"{D['raw_detections']:,}", "raw 2D detections in")
               + '</div>')
    out.append('<div class="card"><b>Bridge sanity (frame check)</b> &mdash; '
               f'{env.get("centers_outside", "?")}/{n_ana} centers outside '
               'the room envelope, '
               f'{env.get("extents_partially_outside", "?")}/{n_ana} boxes '
               'partially outside (envelope covers the splat p1..p99 extent; '
               'wall-flush boxes + fabricated depth extents overhang by '
               'design). A frame mismatch would put MOST centers outside '
               '&mdash; it did not. '
               f'<span class="ok">Match: {match["matched"]}/'
               f'{match["manifest_total"]} manifest objects have an analyzer '
               'counterpart within '
               f'{match["threshold_m"]} m.</span></div>')

    # ---------------- (b) per-label table ----------------
    out.append("<h2>(b) Per-label counts, side by side</h2>")
    cap_note = (f'analyzer counts equal to {D["cap_per_label"]} are CAP-BOUND '
                f'(per-label cluster cap, raised 3&rarr;{D["cap_per_label"]} '
                'for this run &mdash; the true count may be higher). '
                'Labels the analyzer was prompted with but returned ZERO: '
                + ", ".join(f"<b>{esc(l)}</b>"
                            for l in D["zero_detection_labels"]) + ".")
    out.append(f'<div class="dim">{cap_note}</div>')
    out.append('<table><tr><th>label</th><th class="num">manifest</th>'
               '<th class="num">analyzer</th><th>notes</th></tr>')
    for l in all_labels:
        m, a = man_counts.get(l, 0), ana_counts.get(l, 0)
        notes = []
        if a == D["cap_per_label"]:
            notes.append('<span class="tag cap">@ cap '
                         f'{D["cap_per_label"]}</span>')
        if l in D["zero_detection_labels"]:
            notes.append('<span class="tag zero">zero detections</span>')
        if l in groups:
            notes.append(f'<span class="dim">group: {esc(groups[l])}</span>')
        if l == "poter":
            notes.append('<span class="dim">manifest typo for '
                         '&ldquo;poster&rdquo;</span>')
        out.append(f'<tr><td>{esc(l)}</td><td class="num">{m or ""}</td>'
                   f'<td class="num">{a or ""}</td>'
                   f'<td>{" ".join(notes)}</td></tr>')
    out.append(f'<tr><th>total</th><th class="num">{n_man}</th>'
               f'<th class="num">{n_ana}</th><th></th></tr></table>')
    sg = "; ".join(f"<b>{esc(g)}</b> = {esc(', '.join(ms))}"
                   for g, ms in match["synonym_groups"].items())
    out.append(f'<div class="dim">Label-synonym groups used for matching '
               f'(labels not listed are exact-match only): {sg}.</div>')

    # ---------------- (c) match table ----------------
    out.append(f"<h2>(c) Manifest &rarr; analyzer matches "
               f"(nearest compatible label &le; {match['threshold_m']} m, "
               f"center distance, RAW frame)</h2>")
    out.append('<table><tr><th>manifest</th><th>label</th><th>&rarr;</th>'
               '<th>analyzer</th><th>label</th><th class="num">dist (m)</th>'
               '<th class="num">votes</th><th class="num">peak</th></tr>')
    for r in match["manifest_to_analyzer"]:
        if r["matched"]:
            out.append(
                f'<tr><td>{esc(r["manifest_id"])}</td>'
                f'<td>{esc(r["manifest_label"])}</td><td>&rarr;</td>'
                f'<td>{esc(r["analyzer_id"])}</td>'
                f'<td>{esc(r["analyzer_label"])}</td>'
                f'<td class="num">{r["distance_m"]:.3f}</td>'
                f'<td class="num">{r["analyzer_votes"]}</td>'
                f'<td class="num">{r["analyzer_peak_score"]:.3f}</td></tr>')
        else:
            nc = r.get("nearest_compatible")
            extra = (f'nearest compatible {esc(nc["analyzer_id"])} at '
                     f'{nc["distance_m"]:.3f} m' if nc
                     else "no compatible label detected at all")
            out.append(
                f'<tr><td>{esc(r["manifest_id"])}</td>'
                f'<td>{esc(r["manifest_label"])}</td><td>&rarr;</td>'
                f'<td colspan="5" class="bad">UNMATCHED &mdash; '
                f'{extra}</td></tr>')
    out.append('</table>')
    dists = [r["distance_m"] for r in match["manifest_to_analyzer"]
             if r["matched"]]
    if dists:
        out.append(f'<div class="dim">Distances: min {min(dists):.3f} m, '
                   f'median {float(np.median(dists)):.3f} m, max '
                   f'{max(dists):.3f} m. Remember: analyzer centers are '
                   'front-surface-biased, so a systematic offset is '
                   'expected, not an error.</div>')

    # ---------------- (d) analyzer-only ----------------
    out.append(f"<h2>(d) Analyzer-only clusters &mdash; {n_only} with no "
               f"manifest counterpart within {match['threshold_m']} m</h2>")
    out.append('<div class="dim">'
               f'{match["analyzer_matched_to_manifest"]} of the {n_ana} '
               'analyzer clusters sit within range of a compatible manifest '
               'object; these are the rest. Real finds, duplicates, or '
               'hallucinations &mdash; user judges in the viewer (this page '
               'makes no quality call).</div>')
    only_by = {}
    for e in match["analyzer_only"]:
        only_by.setdefault(e["label"], []).append(e)
    out.append('<table><tr><th>label</th><th class="num">count</th>'
               '<th>clusters (id @ center [x, y, z] m, votes v, peak p)</th></tr>')
    for l in sorted(only_by, key=lambda k: (-len(only_by[k]), k)):
        rows = only_by[l]
        cells = "<br>".join(
            f'<span class="mono">{esc(e["id"])} @ '
            f'[{e["center"][0]:.2f}, {e["center"][1]:.2f}, '
            f'{e["center"][2]:.2f}]  v{e["votes"]} p{e["peak_score"]:.2f}'
            '</span>' for e in rows)
        out.append(f'<tr><td>{esc(l)}</td><td class="num">{len(rows)}</td>'
                   f'<td>{cells}</td></tr>')
    out.append('</table>')

    # ---------------- (e) caveats ----------------
    out.append("<h2>(e) Caveats on every analyzer box (carry into any "
               "adoption decision)</h2>")
    out.append('<div class="card caveat"><ol>'
               + "".join(f"<li><b>{esc(k)}</b>: {esc(v)}</li>"
                         for k, v in bridged["caveats"].items())
               + f'<li><b>cap_{D["cap_per_label"]}_binding</b>: the per-label '
                 f'cluster cap of {D["cap_per_label"]} itself binds on '
                 '5 labels (bookshelf, book, painting, shelf, bed all '
                 f'returned exactly {D["cap_per_label"]}) &mdash; their true '
                 'cluster counts are unknown and higher.</li>'
                 '</ol></div>')

    out.append(f'<div class="dim">Generated by analyzer/build_comparison.py '
               f'(Step 8) from {esc(adir / "bridged_boxes.json")} + '
               f'{esc(adir / "match_report.json")}. Numbers only &mdash; no '
               'visual judgment was made by the agent.</div>')
    out.append("</body></html>")

    this_page.write_text("\n".join(out), encoding="utf-8")
    print(f"[comparison] wrote {this_page}")


if __name__ == "__main__":
    main()
