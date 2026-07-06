# Playroom — Agent Starting Guide

A starting orientation package for exploring the **playroom** 3D Gaussian-splat scene.
It fixes a standpoint, defines **North**, and gives you a ring of eye-level views plus
top-down plan views — every image stamped with the exact camera coordinates that made it.
You can render more views yourself (see **Make your own views**).

All coordinates are in the **centered scene** (`data/superspl/playroom_centered.ply`),
where the **standpoint is the origin `(0,0,0)`**. Units are approximately meters.

---

## Orientation frame

| Direction | Axis | Meaning |
|-----------|------|---------|
| **North** | **−z** | forward, toward the staircase / entry |
| South     | +z   | toward the desk / playroom |
| East      | +x   | right when facing North |
| West      | −x   | left when facing North |
| Up        | +y   | ceiling (≈ +2.3) |
| Down      | −y   | floor (≈ −3.2) |

Scene extent: x ∈ [−4.1, 2.3], y ∈ [−5.0, 2.3], z ∈ [−3.2, 2.4].

The standpoint sits at standing eye level (`y=0`): floor ~3.2 below, ceiling ~2.3 above.

---

## Standpoint

- **Eye (where you stand):** `0, 0, 0`
- **Default look (North):** `0, 0, -3`  ·  up `0,1,0`  ·  fov 90

---

## Ring views (eye-level, 8 headings)

All from eye `0,0,0`, `up 0,1,0`, `fov 90`, looking 3 units toward each heading.

| View | Heading | Look | Image |
|------|---------|------|-------|
| North     | N  | `0,0,-3`        | `views/view_north.webp` — staircase, under-stair door, yellow peanut beanbag |
| Northeast | NE | `2.12,0,-2.12`  | `views/view_ne.webp` |
| East      | E  | `3,0,0`         | `views/view_east.webp` |
| Southeast | SE | `2.12,0,2.12`   | `views/view_se.webp` |
| South     | S  | `0,0,3`         | `views/view_south.webp` — desk + monitor, bookshelves, playroom |
| Southwest | SW | `-2.12,0,2.12`  | `views/view_sw.webp` |
| West      | W  | `-3,0,0`        | `views/view_west.webp` |
| Northwest | NW | `-2.12,0,-2.12` | `views/view_nw.webp` |

---

## Plan views (top-down)

Both clip the ceiling/upper half at the standpoint plane (`--box` with `ymax=0`) and
pan-center on the footprint `XZ=(0.5, 0.0)`. In the plan frame:
**screen-right = +x (East), screen-down = +z (South), screen-up = −z (North).**

| Plan | Eye | Look | fov | Image | Note |
|------|-----|------|-----|-------|------|
| **Ortho (recommended)** | `0.5,16,0.0` | `0.5,-1,0.0` | 17 | `views/plan_ortho.webp` | high eye + narrow fov → straight walls, true footprint |
| fov-90 oblique | `0.5,1.2,0.0` | `0.5,-1,0.0` | 90 | `views/plan_fov90.webp` | fov 90 forces a low eye → walls bow, furniture sides show |

Shared: `--up=0,0,-1`, `--box=-4.3,-5,-3.3,2.5,0,2.5`.

Feathered streaks on the North/staircase side of the plan = a real unscanned capture
void in the source data, not a rendering artifact.

---

## Make your own views

If a view is unclear, render another. **From this `package/` directory, just say where to look:**

```
python view.py north      # any heading: n ne e se s sw w nw   (or north, east, ...)
python view.py 135        # ...or a compass angle in degrees   (0=N, 90=E, 180=S, 270=W)
python view.py plan       # clean top-down floor plan
python view.py plan90     # fov-90 oblique plan
```

That's it for the common cases — direction in, image out (saved to `views/`, path printed).

Need more control? Same command, optional `key=value` parts:
```
python view.py east fov=60                 # zoom a heading in
python view.py from=1,0,0 north            # move where you stand, keep the heading
python view.py eye=0,0,-1 look=0,0,2       # arbitrary stand + look point
```

You almost never need anything else. The frame, the centered scene, the up-vector, the
ceiling clip for plans, and the flag-quoting are all handled inside `view.py`.

Rules of thumb:
- **Direction first:** a heading name/number aims from the standpoint at eye level.
- **Pan by moving where you stand:** `from=+x` = East/right, `from=+z` = South/down.
- **Zoom:** lower `fov=` = zoom in, higher = zoom out.
- Every render writes a `.json` sidecar and a `views/shots.csv` row, so any image traces
  back to its exact camera.

<details><summary>Advanced: the underlying renderer (<code>shot.py</code>, one level up)</summary>

`view.py` is a thin wrapper over `../shot.py`. Call it directly only for exotic shots
(custom clip boxes, spheres, HTML orbit viewer):
```
python ../shot.py <eye x,y,z> <look x,y,z> [--up=ux,uy,uz] [--fov DEG] [--box=xmin,ymin,zmin,xmax,ymax,zmax]
```
Use the `=` form for `--up`/`--box` (leading `-` is otherwise read as a flag).
For a plan: look straight down `−y` from a high eye and clip the ceiling with `--box ymax=0`.
</details>

Full machine-readable index of everything above: **`manifest.json`**.
