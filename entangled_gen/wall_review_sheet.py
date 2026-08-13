"""wall_review_sheet.py — one HTML page holding every wall-trace review
image, so the review is one browser tab instead of copy-pasted paths
(user ask 2026-08-12, during the wall/arch design review).

Collects, per scene, whichever of these exist in the scene folder:

    room_shell_steps.png      the 8-panel how-the-trace-is-made sheet
                              (room_shell.py --steps-sheet)
    room_shell_step4_why.png  why cells are excluded from open space
    room_shell_rawtrace.png   the raw walk alone over the density map
    room_shell_poly.png       the classic overlay (clean over raw + v1)

and writes out/wall_review.html with relative image paths — the page
lives next to the scene folders, so it works as a plain file:// open
and refreshes on re-generation of any image. READ-ONLY on scene data;
the page is the only thing written.

    python wall_review_sheet.py --scenes fresh09,fresh05,fresh06
"""
import argparse
import html
from datetime import date

import paths

IMAGES = [
    ("room_shell_steps.png", "How the outline is made — steps 1-8",
     "Find the FIRST panel where a missed wall disappears; that step "
     "owns the failure. 1 material seen from above; 2 'solid' = dense + "
     "reaches 1.4 m (walls but also shelves/curtains); 3 floor evidence "
     "+ rough box; 4 open-space regions and the picked room; 5 the 3 m "
     "leash; 6 the raw walk; 7 straighten/label; 8 the cleanup (bold) "
     "vs raw (faint) vs old v1 box (dotted cyan)."),
    ("room_shell_step4_why.png", "Step 4 zoom — why cells are NOT open",
     "white = open. red = tall material in/next to the cell (walls, but "
     "also wardrobes, curtains, splat fog). blue = outside the rough "
     "box with no floor-level splat seen (single-standpoint occlusion). "
     "purple = both."),
    ("room_shell_rawtrace.png", "The raw walk alone",
     "The trace before any cleanup, over the material map."),
    ("room_shell_poly.png", "Classic overlay (what ships today)",
     "Green/orange/purple = the cleaned walls consumers get; faint "
     "lavender = the raw trace; dotted cyan = the old v1 4-plane box."),
]

CSS = """
body{background:#141414;color:#ddd;font:15px/1.5 Segoe UI,Arial,sans-serif;
 margin:0 auto;padding:1.5em;max-width:120em}
h1{font-size:1.4em} h2{font-size:1.2em;border-top:2px solid #555;
 padding-top:.7em;margin-top:1.6em;color:#fff}
h3{font-size:1em;margin:1em 0 .2em;color:#9cf}
img{max-width:100%;border:1px solid #444;display:block;background:#fff}
p.k{font-size:.88em;color:#aaa;margin:.2em 0 .6em}
a{color:#9cf}
nav a{margin-right:1.2em}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", required=True, help="comma-separated")
    a = ap.parse_args()
    scenes = [s.strip() for s in a.scenes.split(",") if s.strip()]
    h = [f"<title>wall review</title><style>{CSS}</style>",
         "<h1>Wall / arch review — every trace artifact, one page</h1>",
         f'<p class="k">generated {date.today()} by wall_review_sheet.py; '
         f"images are referenced relative, so regenerating any image "
         f"refreshes here on reload (F5)</p>",
         "<nav>" + " ".join(f'<a href="#{html.escape(s)}">{html.escape(s)}</a>'
                            for s in scenes) + "</nav>"]
    for sc in scenes:
        sd = paths.scene_dir(sc)
        h.append(f'<h2 id="{html.escape(sc)}">{html.escape(sc)}</h2>')
        found = False
        for name, title, key in IMAGES:
            if not (sd / name).exists():
                continue
            found = True
            h.append(f"<h3>{html.escape(title)}</h3>")
            h.append(f'<p class="k">{html.escape(key)}</p>')
            h.append(f'<img src="{html.escape(sc)}/{name}" loading="lazy">')
        if not found:
            h.append('<p class="k">no wall review images for this scene '
                     'yet — run room_shell.py --steps-sheet</p>')
    out = paths.OUT / "wall_review.html"
    out.write_text("\n".join(h), encoding="utf-8")
    print(f"[wall-review] {out}  ({len(scenes)} scene(s))")


if __name__ == "__main__":
    main()
