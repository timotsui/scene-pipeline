# Explore Loop — isolated step (v0)

Build thorough visual coverage of the playroom and log what's where, so the output loop
(`PROPOSER.md`) can describe the scene accurately. You only LOOK and RECORD here — no
proposal JSON yet.

## Tools (run from `package/`)
- `python view.py <heading>` — n ne e se s sw w nw, or degrees (0=N, 90=E, 180=S, 270=W).
- `python view.py plan` / `plan90` — top-down.
- `python view.py eye=x,y,z look=x,y,z [fov=N] out=explore/NAME` — custom shot, named.
- `python view.py from=x,y,z <heading> out=explore/NAME` — move where you stand.
- Read each `.webp` it writes (under `views/`) to actually SEE it.
- Frame: origin = standpoint, **North=−z, East=+x, South=+z, West=−x, up=+y**, floor y≈−3.2.

## Loop (stop when coverage is complete or after ~20 shots)
1. Start from the pack's 8 ring views + `plan_ortho` (already rendered) — read them first.
2. For each wall (N/E/S/W) and each candidate **anchor** (desk, bookshelf, wardrobe,
   shelving, staircase, …): render a closer/zoomed shot that frames just that object.
   - Zoom by lowering fov (e.g. `view.py east fov=45 out=explore/wardrobe_E`).
   - If an object is occluded, step toward it: `view.py from=<closer eye> <heading> out=...`.
3. For the floor, use `plan` and 1–2 panned/zoomed plans to read rug/beanbag placement.
4. Note any ambiguity (what is this object? how big? on floor or wall?) and shoot another
   angle to resolve it.

## Output: `proposer/observations.md`
A running log the proposer will consume. For every object you can identify, one row:

```
| object            | where (wall/heading) | approx frame loc | size guess (w,h,d) | anchor? | evidence (image) | notes |
```
Plus a short prose summary: room type, style, wall-by-wall contents, and any open
questions. List the images you rendered under `views/explore/`.

## Done when
Every wall + every anchor has at least one clear framing, the floor layout is legible,
and `observations.md` covers all identifiable objects with no unresolved "what is this?".
