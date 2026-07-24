"""Step 11 — cut-review build: before/after renders + lamp crops + C6 page.

Renders the GaussianCut outputs (cut/<object>/background.ply = scene with
the object removed; foreground.ply = the extracted object alone) from the
EXACT cameras the originals were rendered with, so every before/after pair
is pixel-comparable:

  * all 15 Step-7 view-pack cameras (7 judge-rig + 8 offset-standpoint) —
    camera parameters read from cut/dataset/sidecars/<view>.json, the same
    sidecars splat-transform originally consumed; same fov/res/near/background
  * foreground.ply alone from the 3 lamp-aimed offset cameras, black
    background (renderer has no alpha output)

Then cuts ~360 px square crops centered on the object's projected pixel
location (cut/dataset/verification.json, uv_colmap) from both the before
image and the after render for every view that sees the object, and writes
the Checkpoint 6 review page.

Outputs (all under out/<scene>/cut/<object>/):
  renders/after_<view>.png        background.ply from each of the 15 cameras
  renders/fg_<view>.png           foreground.ply alone (3 lamp-aimed views)
  renders/before_crop_<view>.png  object region, original render (8 views)
  renders/after_crop_<view>.png   object region, after the cut (same box)
  renders/webp/*.webp             renderer originals (provenance)
  cut_review.html                 the Checkpoint 6 review page

NO VISUAL JUDGMENT HERE: this script renders, crops, and lays out. The
verdict on cut quality is the user's (Checkpoint 6); tonight the
orchestrator records a provisional one.

Idempotent: existing renders are skipped unless --force; crops + page are
always rebuilt (cheap, deterministic).

Usage:  python render_cut_review.py --scene bedroom_marble --object obj_004
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import paths  # noqa: E402

RES = 900
NEAR = 0.2
BACKGROUND = "0.08,0.08,0.1"   # same as shot.py / prep_views.py (before renders)
FG_BACKGROUND = "0,0,0"        # foreground-only renders: black, object pops
CROP = 360                     # crop side length, px (~1:1 lamp region)
FG_VIEWS = ["cut_d_lamp", "cut_b_lamp", "cut_c_lamp"]   # closest first


def render(ply, cam, look, up, fov, background, out_webp, gpu):
    cmd = ["splat-transform", "-w", "-g", gpu, str(ply),
           "--camera", cam, "--look-at", look, "--up", up,
           "--fov", str(fov), "--near", str(NEAR),
           "--resolution", f"{RES}x{RES}", "--background", background,
           str(out_webp)]
    print(f"rendering {out_webp.name}  cam={cam} look={look} fov={fov} ...",
          flush=True)
    subprocess.run(cmd, check=True, shell=True, timeout=600)


def to_png(webp, png):
    im = Image.open(webp).convert("RGB")
    if im.size != (RES, RES):
        raise SystemExit(f"{webp}: unexpected size {im.size}, want {RES}x{RES}")
    im.save(png)


def crop_box(uv):
    """Clamped CROP-square box centered on the projected pixel."""
    u = min(max(int(round(uv[0])) - CROP // 2, 0), RES - CROP)
    v = min(max(int(round(uv[1])) - CROP // 2, 0), RES - CROP)
    return (u, v, u + CROP, v + CROP)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scene", required=True)
    ap.add_argument("--object", default="obj_004")
    ap.add_argument("--variant", default="",
                    help="cut variant suffix: reads/writes cut/<object>_<variant>"
                         " (dataset object id stays <object>)")
    ap.add_argument("--gpu", default="0")
    ap.add_argument("--force", action="store_true",
                    help="re-render outputs that already exist")
    a = ap.parse_args()

    dirname = a.object + ("_" + a.variant if a.variant else "")
    odir = paths.scene_dir(a.scene) / "cut" / dirname
    ddir = paths.scene_dir(a.scene) / "cut" / "dataset"
    bg_ply, fg_ply = odir / "background.ply", odir / "foreground.ply"
    stats_f, verif_f = odir / "stats.json", ddir / "verification.json"
    for f in (bg_ply, fg_ply, stats_f, verif_f):
        if not f.exists():
            raise SystemExit(f"missing input: {f}")
    stats = json.loads(stats_f.read_text())
    verif = json.loads(verif_f.read_text())
    obj_id = a.object
    views = verif["views"]                       # canonical order, all 15
    lamp_views = [r for r in views if r["lamp"][obj_id]["in_frame"]]
    if len(views) != 15 or len(lamp_views) != 8:
        raise SystemExit(f"expected 15 views / 8 object-visible, got "
                         f"{len(views)} / {len(lamp_views)} — dataset changed?")

    rdir = odir / "renders"
    wdir = rdir / "webp"
    wdir.mkdir(parents=True, exist_ok=True)

    def sidecar(view):
        d = json.loads((ddir / "sidecars" / f"{view}.json").read_text())
        return d["cam"], d["look"], d["up"], d["fov"]

    def before_path(view):        # existing original-splat render for this cam
        if view.startswith("judge_"):
            return paths.views_dir(a.scene) / f"{view}.webp"
        return ddir / "images" / f"{view}.png"

    # ---- after renders: background.ply from all 15 cameras ----
    n_rendered = 0
    for r in views:
        view = r["view"]
        if not before_path(view).exists():
            raise SystemExit(f"missing before image: {before_path(view)}")
        png = rdir / f"after_{view}.png"
        if png.exists() and not a.force:
            print(f"skip after_{view} (exists)")
            continue
        cam, look, up, fov = sidecar(view)
        webp = wdir / f"after_{view}.webp"
        render(bg_ply, cam, look, up, fov, BACKGROUND, webp, a.gpu)
        to_png(webp, png)
        n_rendered += 1

    # ---- foreground-only renders: the extracted object alone ----
    for view in FG_VIEWS:
        png = rdir / f"fg_{view}.png"
        if png.exists() and not a.force:
            print(f"skip fg_{view} (exists)")
            continue
        cam, look, up, fov = sidecar(view)
        webp = wdir / f"fg_{view}.webp"
        render(fg_ply, cam, look, up, fov, FG_BACKGROUND, webp, a.gpu)
        to_png(webp, png)
        n_rendered += 1

    # ---- crops: same clamped box from before and after ----
    for r in lamp_views:
        view = r["view"]
        box = crop_box(r["lamp"][obj_id]["uv_colmap"])
        before = Image.open(before_path(view)).convert("RGB")
        after = Image.open(rdir / f"after_{view}.png").convert("RGB")
        if before.size != (RES, RES) or after.size != (RES, RES):
            raise SystemExit(f"{view}: before {before.size} / after "
                             f"{after.size}, want {RES}x{RES}")
        before.crop(box).save(rdir / f"before_crop_{view}.png")
        after.crop(box).save(rdir / f"after_crop_{view}.png")
        print(f"crops {view}: box {box}")

    # ---- review page ----
    page = build_page(a.scene, obj_id, stats, views, lamp_views)
    out_html = odir / "cut_review.html"
    out_html.write_text(page, encoding="utf-8")
    n_files = sorted(p.name for p in rdir.glob("*.png"))
    print(f"renders this run: {n_rendered}; renders dir now has "
          f"{len(n_files)} pngs")
    print("review page ->", out_html)


def build_page(scene, obj_id, stats, views, lamp_views):
    def before_src(view):
        if view.startswith("judge_"):
            return f"../../views/{view}.webp"
        return f"../dataset/images/{view}.png"

    fine = stats.get("fine_run", {})
    spatial = stats.get("fg_spatial_check", {})
    band = stats.get("fg_plausible_band", ["?", "?"])
    fg_n = stats["foreground_gaussians"]
    bg_n = stats["background_gaussians"]

    crop_figs = ""
    for r in lamp_views:
        view = r["view"]
        d = r["lamp"][obj_id]
        crop_figs += f"""
<div class="pair">
 <h3>{view} <span class="dim">· lamp at ({d['uv_colmap'][0]:.0f}, {d['uv_colmap'][1]:.0f}) px · depth {d['depth_m']:.2f} m</span></h3>
 <div class="row">
  <figure><a href="renders/before_crop_{view}.png"><img src="renders/before_crop_{view}.png"></a>
   <figcaption>BEFORE (original splat)</figcaption></figure>
  <figure><a href="renders/after_crop_{view}.png"><img src="renders/after_crop_{view}.png"></a>
   <figcaption>AFTER (background.ply — lamp cut out)</figcaption></figure>
 </div>
</div>"""

    full_figs = ""
    for r in views:
        view = r["view"]
        sees = r["lamp"][obj_id]["in_frame"]
        tag = ('<span class="in">sees the lamp</span>' if sees
               else '<span class="dim">lamp not in this view</span>')
        full_figs += f"""
<div class="pair">
 <h3>{view} <span class="dim">· fov {r['fov']:g}°</span> · {tag}</h3>
 <div class="row">
  <figure><a href="{before_src(view)}"><img src="{before_src(view)}" loading="lazy"></a>
   <figcaption>BEFORE</figcaption></figure>
  <figure><a href="renders/after_{view}.png"><img src="renders/after_{view}.png" loading="lazy"></a>
   <figcaption>AFTER</figcaption></figure>
 </div>
</div>"""

    fg_figs = "".join(f"""
  <figure><a href="renders/fg_{v}.png"><img src="renders/fg_{v}.png" loading="lazy"></a>
   <figcaption>fg_{v} — foreground.ply alone (black background)</figcaption></figure>"""
                      for v in FG_VIEWS)

    return f"""<!doctype html><meta charset="utf-8">
<title>Checkpoint 6 — cut-quality review — {scene} {obj_id}</title>
<style>
 body{{background:#15171c;color:#dcdfe6;font:14px/1.5 system-ui;margin:20px;max-width:1500px}}
 .banner{{background:#3a1f1f;border:2px solid #c94f4f;border-radius:8px;padding:12px 18px;margin-bottom:16px}}
 .banner h1{{margin:0 0 6px;font-size:20px;color:#ff9c9c}}
 .banner b{{color:#ffd27f}}
 h2{{margin:30px 0 8px;font-size:17px;color:#aeb6c4;border-bottom:1px solid #2c313c;padding-bottom:4px}}
 h3{{margin:16px 0 6px;font-size:14px;color:#c8d3f5}}
 .row{{display:flex;flex-wrap:wrap;gap:12px}}
 figure{{margin:0}}
 .crops figure img{{width:{CROP}px;height:{CROP}px;display:block;border-radius:4px;image-rendering:auto}}
 .full figure img{{width:440px;display:block;border-radius:4px}}
 .fg figure img{{width:440px;display:block;border-radius:4px}}
 figcaption{{font-size:12px;color:#9aa0ac;padding:3px 2px}}
 .in{{color:#8fd18f}} .dim{{color:#778}}
 .stats{{background:#1b1f27;border:1px solid #2c313c;border-radius:8px;padding:12px 16px;margin:14px 0;max-width:980px}}
 .stats td{{padding:2px 14px 2px 0;vertical-align:top}}
 .stats td:first-child{{color:#8899aa;white-space:nowrap}}
 .flag{{color:#ffb86b}}
 code{{color:#c8d3f5}}
</style>

<div class="banner"><h1>🔴 WAITING ON YOU — Checkpoint 6: cut-quality judgment</h1>
<p><b>What:</b> before/after renders of the GaussianCut result for the freestanding
lamp ({obj_id}) in {scene} — every pair is rendered from the IDENTICAL camera
(same pose/fov/resolution/background), before = original <code>gen_raw.ply</code>,
after = <code>background.ply</code> (the splat with the lamp's {fg_n} Gaussians
removed). Also on this page: the extracted lamp rendered alone, and a stats box.
The same layers are live in the 3D viewer (<code>launch_viewer.bat</code> →
localhost:8321): checkboxes <b>cut background</b> and <b>lamp only (cut fg)</b>.</p>
<p><b>Why:</b> this is THE gate for the whole cut lane. A pass approves the
mask→graph-cut method for the batch run (Step 12 — cut all manifest objects) and
for the integration demo (composition over the cut background). A bad cut here
means the masks or the graph-cut parameters need rework before anything
downstream is built on them.</p>
<p><b>Look for:</b></p>
<ol>
 <li><b>Lamp GONE in every after-crop</b> (section 1) — no floating remnants, no
     half-lamp, no leftover shade/arm/base fragments.</li>
 <li><b>What's revealed behind the lamp</b> — acceptable: a soft blur/hole where
     the lamp stood (nothing was ever observed behind it, so there is no data
     there); bad: torn window/curtain/desk geometry around the hole. Note from
     Checkpoint 3: the lamp stands against the window — the known 0.205 m
     lamp×window interpenetration zone is exactly the place to scrutinize.</li>
 <li><b>No collateral damage in the full frames</b> (section 2) — walls, floor,
     desk, bed, curtains everywhere else must be pixel-identical to the before
     side (the cut removed only {fg_n} of {fg_n + bg_n:,} Gaussians).</li>
 <li><b>The extracted lamp is complete</b> (section 3) — the fg renders should
     look like a whole lamp alone (shade + arm + base), nothing else. Known
     numeric caveat: no foreground Gaussians below 0.865 m physical height (the
     thin-pole band below every mask prompt), so the very bottom of the pole may
     be missing — judge whether that matters visually.</li>
</ol></div>

<h2>1. Lamp region, 1:1 crops — before | after ({len(lamp_views)} views that see the lamp)</h2>
<p class="dim">Crops are {CROP}×{CROP} px cut from the 900×900 renders, centered on the
lamp's projected pixel location (<code>cut/dataset/verification.json</code>), the SAME
crop box on both sides. This is the heart of the review.</p>
<div class="crops">{crop_figs}</div>

<h2>2. Full frames — before | after (all 15 cameras)</h2>
<p class="dim">7 judge-rig views (the standard whole-room coverage) + 8
offset-standpoint views. Everything except the lamp should be identical.</p>
<div class="full">{full_figs}</div>

<h2>3. The extracted lamp alone — foreground.ply ({fg_n} Gaussians)</h2>
<div class="fg"><div class="row">{fg_figs}</div></div>

<h2>4. Cut stats (from <code>stats.json</code>)</h2>
<div class="stats"><table>
<tr><td>foreground (lamp)</td><td><b>{fg_n}</b> Gaussians</td></tr>
<tr><td>background (scene)</td><td><b>{bg_n:,}</b> Gaussians (of {fg_n + bg_n:,} total; counts verified 3 ways)</td></tr>
<tr><td>coarse threshold</td><td>{stats.get('threshold_used')} — chosen by the census+purity rule; a full rerun at 0.3 was
    BIT-IDENTICAL (choice provably moot for this cut)</td></tr>
<tr><td>fine stage runtime</td><td>{fine.get('run_seconds')} s</td></tr>
<tr><td>spatial containment</td><td>{spatial.get('fg_frac_within_box_plus_0.15m', 0) * 100:.0f}% of foreground Gaussians inside
    the manifest box +0.15 m; foreground stops 0.09 m short of the window face
    (no curtain/window grab, numerically)</td></tr>
<tr><td class="flag">fg_in_plausible_band</td><td class="flag">false — {fg_n} &lt; {band[0]} (band [{band[0]}, {band[1]}], derived from a
    box census of {stats.get('box_census')} Gaussians). Explanation on record: the census counts
    floor/window plane slices that pass through the box, which the cut correctly
    left in the background; flagged here for honest review, not hidden.</td></tr>
<tr><td>mask evidence caveat</td><td>the lamp's wall-facing side had no mask evidence (physically unobservable
    from in-room, Checkpoint 3); whatever the cut did there is extrapolation —
    judge the window region in the crops.</td></tr>
</table></div>

<p class="dim">Generated {time.strftime('%Y-%m-%d %H:%M:%S')} by
<code>scene-pipeline/entangled_gen/cut/render_cut_review.py</code> (Step 11 — cut-review
build). Mechanical build only — no visual judgment was made by the tooling.</p>
"""


if __name__ == "__main__":
    main()
