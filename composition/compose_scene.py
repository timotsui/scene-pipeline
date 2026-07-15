"""Automated composition orchestrator (stage 7 of the pipeline, end to end).

python compose_scene.py --scene bedroom_marble --until place

--until gates (each later stage assumes the earlier artifacts exist):
  propose   stage 1 only: boxes + verify/revise      -> compose_proposal.json
  retrieve  + stage 2: objathor asset per box         -> composed_assets.json
  place     + stage 3: composite renders              -> composed_view_*.png   [USER CHECKPOINT]
  loop      + stage 4: VLM jiggle refinement          -> updated state + renders

--skip-propose reuses an existing compose_proposal.json (e.g. after a manual
edit at a checkpoint).
"""
import argparse
import sys

STAGES = ["propose", "retrieve", "place", "loop"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--mode", choices=["recreate", "augment"], default="recreate",
                    help="recreate: rebuild EVERY manifest box from assets "
                         "(the manifest is the layout); augment: LLM proposes "
                         "additional placements per the scene prompt")
    ap.add_argument("--until", choices=STAGES, default="place")
    ap.add_argument("--skip-propose", action="store_true")
    ap.add_argument("--model", default="sonnet")
    args = ap.parse_args()
    stop = STAGES.index(args.until)

    if args.mode == "recreate":
        if stop >= 1:
            import recreate
            recreate.run(args.scene, model=args.model)   # -> composed_state.json
        if stop >= 2:
            import place
            place.render(args.scene)
    else:
        if not args.skip_propose:
            import propose
            if not propose.run(args.scene, model=args.model):
                print("[compose] propose did not converge — stopping", flush=True)
                sys.exit(1)
        if stop >= 1:
            import retrieve
            retrieve.run(args.scene, model=args.model)
        if stop >= 2:
            import place
            place.run(args.scene)
    if stop >= 3:
        import jiggle
        jiggle.run(args.scene, model=args.model)
    print(f"[compose] done through '{args.until}' (mode={args.mode})", flush=True)


if __name__ == "__main__":
    main()
