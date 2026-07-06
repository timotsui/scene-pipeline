# proposer — scene-proposer module (seed)

Planned stage: look at a REAL scene (splat renders / extracted manifest) →
produce a scene description / composition proposal that a downstream composer
(Holodeck / GLTS-style) can consume. "Describe what's here, propose what fits."

Status: not yet built as a standalone tool. This folder currently holds the
week5 proposer experiments (2026-06) as the seed:

- `PROPOSER.md` — the original prompt/protocol given to the proposing agent
- `EXPLORE.md`, `observations.md` — the agent's scene exploration notes
- `proposal.json`, `example_proposal.json` — produced placements (contract:
  same `placements` schema the entangled_gen viewer/`render_proposal.py` use)
- `PROPOSAL_NOTES.md`, `RESULTS.md` — what worked / what didn't

When this becomes real code, keep the output contract aligned with
`entangled_gen/PIPELINE.md` stage 7 (`compose_proposal.json` schema) so
proposals stay verifiable/renderable by the existing tooling.
