"""
Build the VLM/LLM composition package for a lifted scene:
out/<scene>/package/ = GUIDE.md (frame + object table + occupancy grid + OUTPUT
CONTRACT) + scene_manifest.json + the ID-annotated overlay views + raw views.

Format thesis (2026-07-05): geometry lives in JSON/text (LLMs reason over
coordinates, VLMs can't measure pixels), images are for grounding/veto only
(object IDs painted in the photoreal views match manifest IDs), and free
space is EXPLICIT (ASCII occupancy grid) so composing = constraint
satisfaction, not scene understanding.

Run:  python agent_package.py --scene bedroom
"""
import argparse, json, shutil
from pathlib import Path
import numpy as np

import paths

HERE = Path(__file__).parent
GRID = 24          # occupancy grid resolution (cells per axis)
WALL_LABELS = {"window", "door", "curtain", "picture"}  # not floor obstacles


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="playroom")
    args = ap.parse_args()
    sc = args.scene

    seg_dir = paths.seg_dir(sc)
    views_dir = paths.views_dir(sc)
    man = json.loads(paths.manifest(sc).read_text())
    pkg = paths.package_dir(sc)
    pkg.mkdir(parents=True, exist_ok=True)

    fr = man["frame"]
    floor_y, ceil_y = fr["floor_y"], fr["ceiling_y"]
    sx, sy, sz = fr.get("raw_to_render", [1.0, 1.0, 1.0])
    # sy=-1 -> RAW up=-y (floor_y > ceiling_y numerically); elevation of a
    # numeric y above the floor is sy*(y - floor_y) in either convention.
    if "extent_p1" in fr:
        (x0, _, z0), (x1, _, z1) = fr["extent_p1"], fr["extent_p99"]
    else:  # older manifest: derive extent from objects, padded
        los = np.array([o["aabb_min"] for o in man["objects"]])
        his = np.array([o["aabb_max"] for o in man["objects"]])
        x0, z0 = los[:, 0].min() - 0.3, los[:, 2].min() - 0.3
        x1, z1 = his[:, 0].max() + 0.3, his[:, 2].max() + 0.3

    # ---- occupancy grid: X occupied by an object footprint, . free floor ----
    # wall-mounted classes don't block the floor; everything else does.
    grid = [["." for _ in range(GRID)] for _ in range(GRID)]
    for o in man["objects"]:
        if o["label"] in WALL_LABELS:
            continue
        lo, hi = o["aabb_min"], o["aabb_max"]
        bottom_elev = min(sy * (lo[1] - floor_y), sy * (hi[1] - floor_y))
        if bottom_elev > 1.0:          # floats well above floor (shelf items)
            continue
        c0 = max(0, int((lo[0] - x0) / (x1 - x0) * GRID))
        c1 = min(GRID - 1, int((hi[0] - x0) / (x1 - x0) * GRID))
        r0 = max(0, int((lo[2] - z0) / (z1 - z0) * GRID))
        r1 = min(GRID - 1, int((hi[2] - z0) / (z1 - z0) * GRID))
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                grid[r][c] = "X"
    # mark the rig origin
    oc = int((0 - x0) / (x1 - x0) * GRID); orow = int((0 - z0) / (z1 - z0) * GRID)
    if 0 <= orow < GRID and 0 <= oc < GRID:
        grid[orow][oc] = "*"
    grid_txt = "\n".join("".join(row) for row in grid)

    # ---- object table ----
    rows = []
    for o in man["objects"]:
        rows.append(f'| {o["id"]} | {o["label"]} | '
                    f'{o["size"][0]:.2f} x {o["size"][1]:.2f} x {o["size"][2]:.2f} | '
                    f'({o["center"][0]:.2f}, {o["center"][1]:.2f}, {o["center"][2]:.2f}) | '
                    f'{o["score"]:.2f} |')
    table = "\n".join(rows)

    overlays = sorted(seg_dir.glob("manifest_overlay_*.png"))
    for f in overlays:
        shutil.copy2(f, pkg / f.name)
    for f in sorted(views_dir.glob("gpu_yaw*.webp")):
        shutil.copy2(f, pkg / f.name)
    shutil.copy2(paths.manifest(sc), pkg / "scene_manifest.json")

    up_txt = ("+y" if sy > 0 else
              "**-y** (RAW frame: y DECREASES upward, so floor_y > ceiling_y numerically)")
    yaw_dirs = " / ".join(
        f"{'+' if s > 0 else '-'}{ax}"
        for s, ax in ((sz, "z"), (sx, "x"), (-sz, "z"), (-sx, "x")))
    on_floor = f"floor_y {'+' if sy > 0 else '-'} h/2 = {floor_y} {'+' if sy > 0 else '-'} h/2"
    guide = f"""# {sc} — scene composition package (generated splat -> lifted manifest)

Room extracted from a generated 3D Gaussian splat. Units ~meters.
ALL coordinates below (object table, extents, your placements) are RAW-frame.

## Frame
- Up = {up_txt}. Floor y = {floor_y}, ceiling y = {ceil_y}.
- Camera rig at origin (0,0,0), standing eye height; views look along {yaw_dirs}
  (yaw000/090/180/270).
- Room extent (p1..p99): x in [{x0:.2f}, {x1:.2f}], z in [{z0:.2f}, {z1:.2f}].

## Existing objects (from scene_manifest.json; same IDs painted in the overlay PNGs)
| id | label | size WxHxD | center (x,y,z) | conf |
|----|-------|-----------|----------------|------|
{table}

Wall-mounted classes ({", ".join(sorted(WALL_LABELS))}) do not block floor space.

## Floor occupancy ({GRID}x{GRID} over the extent; row 0 = z={z0:.2f} (top), col 0 = x={x0:.2f} (left); X = occupied, . = free floor, * = rig origin)
```
{grid_txt}
```

## Images
- `manifest_overlay_gpu_yaw*.png` — photoreal views with lifted 3D boxes + IDs
  (use to verify semantics/style; do NOT measure from pixels — use the table).
- `gpu_yaw*.webp` — clean views.

## OUTPUT CONTRACT for a composition request
Reply with `compose_proposal.json`:
```json
{{"instruction": "<the request>",
  "placements": [{{"label": "desk", "center": [x, y, z], "size": [w, h, d],
                   "yaw_deg": 0, "mount": "floor", "reason": "one line"}}]}}
```
`mount` is "floor" (default) or "wall" (wall-hung/window-mounted items).
Hard constraints:
1. Floor objects: `center_y = {on_floor}` (h/2 physically above the floor; mind the up sign).
   Wall objects instead: whole AABB vertically between floor and ceiling, against a wall.
2. Whole AABB inside the room extent above.
3. No AABB intersection with any manifest object or other placement.
4. Floor objects leave a >= 0.5 m walking corridor to the rig origin.
5. Sizes must be real-world plausible for the label.
"""
    (pkg / "GUIDE.md").write_text(guide, encoding="utf-8")
    print(f"[package] wrote {pkg} ({len(man['objects'])} objects, "
          f"{len(overlays)} overlays)", flush=True)


if __name__ == "__main__":
    main()
