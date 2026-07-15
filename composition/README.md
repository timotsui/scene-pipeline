# composition — automated stage-7 composer (test-run v0, 2026-07-14)

Automates: propose layout boxes -> verify/revise -> retrieve assets (objathor,
description+dimension match) -> place meshes into the splat views -> VLM
feedback loop ("jiggle"). Every stage is a separate module with file-based
I/O so any piece can be swapped later:

| stage | module | reads | writes |
|-------|--------|-------|--------|
| 1 propose | `propose.py` | `out/<scene>/package/` (GUIDE, overlays) | `package/compose_proposal.json` (+ proposal renders via entangled_gen/render_proposal.py) |
| 2 retrieve | `retrieve.py` | compose_proposal.json + objathor annotations | `package/composed_assets.json` + `asset_thumbs.png` |
| 3 place | `place.py` | composed_assets.json + views | `package/composed_view_*.png` + `composed_state.json` |
| 4 loop | `jiggle.py` | composed_state.json + composites | updated state + renders + `jiggle_history.jsonl` |

Run: `python compose_scene.py --scene bedroom_marble --until place`
(`--until` gates: propose / retrieve / place / loop — retrieval and placement
are USER CHECKPOINTS before the VLM loop runs.)

LLM/VLM = the Claude agent surrogate (`bridge.py`: claude.exe -p, subscription,
same wrapper as the TreeSearchGen bridge). Frame: all placement coords RAW
(up=-y for rot180 scenes); meshes/views composited in the RENDER frame via
frame.raw_to_render.

Known v0 limits (improve later): no per-pixel occlusion vs the splat (meshes
drawn over), uniform scale to box height only, no asset orientation
canonicalization (yRotOffset ignored), text-only retrieval ranking (no
thumbnail/CLIP visual match).
