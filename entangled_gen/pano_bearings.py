"""Directional prior for detection (user idea 2026-08-06, side-branch test):
where does each vocab term appear on the panorama?

The self-rendered pano (rig_sp0/pano_selfrender.png) is equirect under the
A2 convention (center = +Z = yaw 0, theta grows toward +X, u wraps), i.e.
THE SAME yaw frame the rig crops are cut in — so a term's horizontal
position converts directly: azimuth_deg = (xfrac - 0.5) * 360, comparable
to crop yaw with no offset. (The bundle pano is NOT used: its x-origin
convention is Marble's, unknown.)

One VLM call (claude.exe, same bridge as vocab_build). Terms the VLM cannot
locate get NO bearing and downstream stays global for them — the prior only
ever narrows where we have positive location evidence. Doctrine: in-pipeline
sensing, LLM judgment, no scene knowledge in code.

Writes rig_sp0/vocab_bearings.json: {"bearings_deg": {term: [deg, ...]}}.

Run:  python pano_bearings.py --scene living_marble
"""
import argparse
import json
import time
from pathlib import Path

import paths
from vocab_build import MODEL, call_claude

BEARING_PROMPT = """Read the image file at this absolute path: a 360-degree equirectangular panorama of one indoor room (horizontal axis = full turn, wraps at the edges).

{pano}

For each term in this list, if one or more instances of it are clearly visible, report the horizontal CENTER of each instance as a decimal fraction of image width (left edge 0.0, right edge 1.0):

{terms}

Rules:
- only terms from the list, only ones you actually see
- one line per visible term: "term: 0.12, 0.55" (one fraction per instance)
- skip invisible terms entirely; output nothing else"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    a = ap.parse_args()
    sd = paths.scene_dir(a.scene)
    rig = sd / "rig_sp0"
    pano = rig / "pano_selfrender.png"
    vocab = json.loads((sd / "vocab.json").read_text(encoding="utf-8"))
    terms = list(vocab["canonical"])

    raw = call_claude(BEARING_PROMPT.format(pano=pano, terms=", ".join(terms)),
                      rig)
    bearings = {}
    for ln in raw.splitlines():
        if ":" not in ln:
            continue
        term, frs = ln.split(":", 1)
        term = term.strip().lower().lstrip("-• ").strip('"')
        if term not in terms:
            continue
        degs = []
        for f in frs.split(","):
            try:
                x = float(f.strip())
            except ValueError:
                continue
            if 0.0 <= x <= 1.0:
                degs.append(round(((x - 0.5) * 360.0) % 360.0, 1))
        if degs:
            bearings[term] = degs

    out = {"scene": a.scene, "pano": str(pano),
           "frame": "A2 self-render (center=+Z=yaw0, theta->+X); "
                    "azimuth = (xfrac-0.5)*360, same frame as crop yaws",
           "bearings_deg": bearings,
           "unlocated_terms (stay global)": [t for t in terms
                                             if t not in bearings],
           "meta": {"model": MODEL, "raw": raw,
                    "built": time.strftime("%Y-%m-%d %H:%M:%S")}}
    outf = rig / "vocab_bearings.json"
    outf.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"[bearings] {len(bearings)}/{len(terms)} terms located -> {outf}")
    for t, d in bearings.items():
        print(f"  {t}: {d}")
    print(f"[bearings] global (unlocated): "
          f"{', '.join(t for t in terms if t not in bearings) or '-'}")


if __name__ == "__main__":
    main()
