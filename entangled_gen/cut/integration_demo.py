"""Integration demo (overnight priority 5) — the payoff artifact of the cut
lane: the EXISTING composed mesh layout rendered over the CUT background
splat, side by side with the two states it replaces.

Three variants of the same composition (package/composed_state2.json — the
C7-loop accepted state, READ-ONLY here) from the same cameras used in cut
review:

  (a) ghost problem   meshes over the ORIGINAL splat (gen_raw.ply renders):
                      the original lamp is still baked into the splat, so the
                      placed mesh lamp coexists with its ghost.
  (b) cut background  meshes over background.ply (the splat with the lamp's
                      Gaussians removed by GaussianCut) — the payoff: mesh
                      replacement with no ghost, real room intact.
  (c) old workaround  meshes only + splat-tinted synthetic floor (place2
                      --clean): honest about what was placed, but the room
                      itself is gone.

Background source for (b) comes through place2.resolve_background(sc,"auto")
— the background resolver this demo validates (auto = newest cut
background.ply, else tinted fallback).

Writes (all NEW files; composition state and cut outputs are never touched):
  out/<scene>/cut/integration_demo/renders/{a_original,b_cutbg,c_tinted}_<view>.png
  out/<scene>/cut/integration_demo/renders/{a,b,c}_crop_<view>.png
  out/<scene>/cut/integration_demo/integration_demo.html

NO VISUAL JUDGMENT HERE: this script renders and lays out; the verdict is
the user's. Renders are cheap + deterministic — everything is rebuilt on
each run.

Usage:  python integration_demo.py --scene bedroom_marble --object obj_004
"""
import argparse
import json
import sys
import time
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))                       # entangled_gen
sys.path.insert(0, str(HERE.parent.parent / "composition"))  # place2 et al.
import paths   # noqa: E402
import place2  # noqa: E402

RES = 900
CROP = 360     # same crop side as render_cut_review.py — comparable regions

# minimum camera set per the task + every other view that sees the lamp
CAMS = ["judge_yaw000", "cut_d_lamp", "cut_b_lamp", "cut_c_lamp",
        "cut_b_left", "cut_b_right", "cut_c_left", "cut_c_right"]

VARIANTS = [   # (file prefix, splat_bg value, plain-language label)
    ("a_original_", True,    "(a) ghost problem — original splat + mesh lamp"),
    ("b_cutbg_",    "cut",   "(b) cut background + mesh lamp — the payoff"),
    ("c_tinted_",   "clean", "(c) old workaround — tinted-floor clean"),
]


def sidecar_path(sc, view):
    """judge_* cameras live in views/; cut_* cameras in cut/dataset/sidecars."""
    if view.startswith("judge_"):
        return paths.views_dir(sc) / f"{view}.json"
    return paths.scene_dir(sc) / "cut" / "dataset" / "sidecars" / f"{view}.json"


def crop_box(uv):
    """Clamped CROP-square box centered on the projected pixel (same rule as
    render_cut_review.crop_box, so crops match the C6 review pages)."""
    u = min(max(int(round(uv[0])) - CROP // 2, 0), RES - CROP)
    v = min(max(int(round(uv[1])) - CROP // 2, 0), RES - CROP)
    return (u, v, u + CROP, v + CROP)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scene", default="bedroom_marble")
    ap.add_argument("--object", default="obj_004",
                    help="cut object id — used for the crop centers and the "
                         "page's asset provenance")
    a = ap.parse_args()
    sc, obj_id = a.scene, a.object

    # ---- composition state: READ-ONLY ----
    state_f = paths.package_dir(sc) / "composed_state2.json"
    state = json.loads(state_f.read_text())
    lamp_entries = [e for e in state["objects"] if e["group"] == obj_id]
    if not lamp_entries:
        raise SystemExit(f"{state_f} has no instance for {obj_id} — "
                         f"place the top picks2.json lamp first")
    lamp = lamp_entries[0]

    # ---- background resolution: the resolver under validation ----
    splat_bg_cut, cut_bg = place2.resolve_background(sc, "auto")
    if splat_bg_cut != "cut":
        raise SystemExit("resolver did not pick a cut background for this "
                         "scene — demo is meaningless without one")
    cut_dir = cut_bg.parent
    cut_stats = json.loads((cut_dir / "stats.json").read_text())

    # ---- crop centers from the cut dataset's verification file ----
    verif = json.loads((paths.scene_dir(sc) / "cut" / "dataset"
                        / "verification.json").read_text())
    uv = {r["view"]: r["lamp"][obj_id] for r in verif["views"]}
    for view in CAMS:
        if not uv[view]["in_frame"]:
            raise SystemExit(f"{view} does not see {obj_id} — camera set "
                             f"changed?")

    odir = paths.scene_dir(sc) / "cut" / "integration_demo"
    rdir = odir / "renders"
    rdir.mkdir(parents=True, exist_ok=True)
    sidecars = [sidecar_path(sc, v) for v in CAMS]
    for f in sidecars:
        if not f.exists():
            raise SystemExit(f"missing camera sidecar: {f}")

    # ---- renders: 3 variants x len(CAMS) cameras ----
    n = 0
    for prefix, splat_bg, label in VARIANTS:
        print(f"[demo] variant {label}", flush=True)
        outs = place2.composite_views(sc, state, outdir=rdir, prefix=prefix,
                                      splat_bg=splat_bg, sidecars=sidecars,
                                      cut_bg=cut_bg)
        if len(outs) != len(CAMS):
            raise SystemExit(f"{prefix}: {len(outs)} renders for "
                             f"{len(CAMS)} cameras")
        n += len(outs)

    # ---- lamp-region crops, same box across all three variants ----
    for view in CAMS:
        box = crop_box(uv[view]["uv_colmap"])
        for prefix, _, _ in VARIANTS:
            im = Image.open(rdir / f"{prefix}{view}.png").convert("RGB")
            if im.size != (RES, RES):
                raise SystemExit(f"{prefix}{view}: size {im.size}, "
                                 f"want {RES}x{RES}")
            im.crop(box).save(rdir / f"{prefix[0]}_crop_{view}.png")
            n += 1
    print(f"[demo] {n} pngs under {rdir}", flush=True)

    page = build_page(sc, obj_id, state_f, lamp, len(lamp_entries),
                      cut_dir, cut_stats, uv)
    out_html = odir / "integration_demo.html"
    out_html.write_text(page, encoding="utf-8")
    print("[demo] review page ->", out_html, flush=True)


def build_page(sc, obj_id, state_f, lamp, n_lamp, cut_dir, cut_stats, uv):
    figs = ""
    for view in CAMS:
        d = uv[view]
        crop_row = "".join(
            f"""
  <figure><a href="renders/{p[0]}_crop_{view}.png"><img src="renders/{p[0]}_crop_{view}.png"></a>
   <figcaption>{lbl}</figcaption></figure>"""
            for p, _, lbl in VARIANTS)
        full_row = "".join(
            f"""
  <figure><a href="renders/{p}{view}.png"><img src="renders/{p}{view}.png" loading="lazy"></a>
   <figcaption>{lbl}</figcaption></figure>"""
            for p, _, lbl in VARIANTS)
        figs += f"""
<h3>{view} <span class="dim">· lamp at ({d['uv_colmap'][0]:.0f}, {d['uv_colmap'][1]:.0f}) px · depth {d['depth_m']:.2f} m</span></h3>
<div class="crops"><div class="row">{crop_row}</div></div>
<div class="full"><div class="row">{full_row}</div></div>"""

    return f"""<!doctype html><meta charset="utf-8">
<title>Integration demo — composition over the cut background — {sc}</title>
<style>
 body{{background:#15171c;color:#dcdfe6;font:14px/1.5 system-ui;margin:20px;max-width:1560px}}
 .banner{{background:#3a1f1f;border:2px solid #c94f4f;border-radius:8px;padding:12px 18px;margin-bottom:16px}}
 .banner h1{{margin:0 0 6px;font-size:20px;color:#ff9c9c}}
 .banner b{{color:#ffd27f}}
 h3{{margin:26px 0 6px;font-size:14px;color:#c8d3f5;border-top:1px solid #2c313c;padding-top:14px}}
 .row{{display:flex;flex-wrap:wrap;gap:12px}}
 figure{{margin:0}}
 .crops figure img{{width:{CROP}px;height:{CROP}px;display:block;border-radius:4px}}
 .full figure img{{width:480px;display:block;border-radius:4px}}
 figcaption{{font-size:12px;color:#9aa0ac;padding:3px 2px;max-width:480px}}
 .dim{{color:#778}}
 .stats{{background:#1b1f27;border:1px solid #2c313c;border-radius:8px;padding:12px 16px;margin:14px 0;max-width:1000px}}
 .stats td{{padding:2px 14px 2px 0;vertical-align:top}}
 .stats td:first-child{{color:#8899aa;white-space:nowrap}}
 code{{color:#c8d3f5}}
</style>

<div class="banner"><h1>🔴 WAITING ON YOU — integration demo review</h1>
<p><b>What:</b> this page — the SAME composed mesh layout
(<code>package/composed_state2.json</code>, the loop-accepted composition, read-only)
rendered three ways from the same cameras used in the cut review
({len(CAMS)} views that see the lamp, incl. judge_yaw000 + cut_d/b/c_lamp).
(a) = meshes over the ORIGINAL splat, (b) = meshes over the CUT background
(<code>{cut_dir.name}\\background.ply</code>, the splat with the lamp's
{cut_stats['foreground_gaussians']} Gaussians removed), (c) = the old
tinted-floor workaround (meshes + fake floor, no splat at all).</p>
<p><b>Why:</b> this is the entire point of the cut lane — replace a generated
object with a retrieved mesh asset WITHOUT the original ghosting through it.
It also validates the new background resolver (auto = cut background when one
exists, else the tinted fallback) before you decide whether it becomes the
composition default (that call is reserved for you).</p>
<p><b>Look for, in (b):</b></p>
<ol>
 <li>The mesh lamp reads as THE lamp — one lamp, standing where the original
     stood, no ghost lamp behind or bleeding through it. Compare directly
     against (a): same pixels, ghost present.</li>
 <li>The room stays intact around it — window, curtain, desk unharmed right up
     to the mesh (vs (c), where the whole room is replaced by a fake floor).</li>
 <li>The desk-level dark smudge noted in R5 (the reveal where the original
     lamp base was cut) — does the mesh lamp's base cover it, or does it show
     beside/below the mesh?</li>
 <li>The faint arm-trace remnant from R5 — visible through/next to the mesh
     lamp or effectively hidden?</li>
</ol></div>

<div class="stats"><table>
<tr><td>composition state</td><td><code>{state_f}</code> — read-only; {n_lamp} instance(s) for {obj_id}</td></tr>
<tr><td>mesh lamp asset</td><td>uid <code>{lamp['uid']}</code> (category "{lamp['category']}", the picks2.json winner already
    in the composed state) at center {lamp['center']} = {obj_id}'s manifest pose; scale {lamp['scale']}, mount {lamp['mount']}</td></tr>
<tr><td>cut background</td><td><code>{cut_dir}\\background.ply</code> — {cut_stats['background_gaussians']:,} Gaussians
    (variant: {cut_stats.get('variant', cut_dir.name)})</td></tr>
<tr><td>resolver rule</td><td><code>place2.resolve_background(scene, "auto")</code>: newest
    <code>cut/*/background.ply</code> by mtime (re-cut variants supersede their base), else the tinted-floor
    clean path — un-cut scenes keep working unchanged. Overrides: <code>--background cut|tinted|original</code>.</td></tr>
<tr><td>(b) backdrops</td><td>reused from the cut review's <code>after_&lt;view&gt;.png</code> renders
    (background.ply through the identical cameras) — no new splat rendering was needed.</td></tr>
<tr><td>crops</td><td>{CROP}×{CROP} px, centered on the lamp's projected pixel
    (<code>cut/dataset/verification.json</code>), the SAME box across all three variants.</td></tr>
</table></div>

{figs}

<p class="dim">Generated {time.strftime('%Y-%m-%d %H:%M:%S')} by
<code>scene-pipeline/entangled_gen/cut/integration_demo.py</code>. Mechanical build only —
no visual judgment was made by the tooling; the verdict is yours.</p>
"""


if __name__ == "__main__":
    main()
