# docs/ layout (reorganized 2026-08-12, user request)

**The root holds only LIVE documents** — things a running session reads
or writes:

- `REVIEW_LOG.md` — the primary record. Every fix, every ruling.
- `PARKED.md` — deliberately not being worked on. Read before "fixing".
- `POWER_CRASHES.md` — the GPU crash playbook (clock lock, watch_gpu).
- `AUTOMATION_READINESS.md`, `GO_NOGO_100_BATCH.md` — batch-night refs.
- `NEXT_SESSION_PROMPT.md` — paste-ready prompt for the next agent.
- `SESSION_*_HANDOFF.md` — **exactly ONE: the current handoff.**

## ⚠ THE HANDOFF RULE (a hook depends on it)

The SessionStart hook in `Summer2026/.claude/settings.local.json` globs
`docs/SESSION_*_HANDOFF.md` and auto-loads the newest into every new
session. So:

1. A new handoff is written to `docs/` ROOT.
2. In the same commit, `git mv` the superseded one into `handoffs/`.

Never leave two handoffs at the root; never write one into `handoffs/`
directly (the hook would load a stale one).

## Subfolders

- `handoffs/` — every superseded session handoff, July onward. History,
  not instructions; the REVIEW_LOG outranks them all (trust the primary
  record over summaries).
- `plans/` — PLAN_*/SPEC_* docs and design notes (SLICEVOTE.md,
  S4_SHOPPING_DESIGN_NOTES.md, RETAKE_DESIGNS.md, ...). Some are CANON
  records still cited from code comments — citations were updated to
  `docs/plans/...` when this layout landed; keep them accurate if files
  move again.
- `archive/` — superseded one-offs (the pre-resolution README).

Authority order is unchanged: pipeline_map.html → the owning PLAN doc →
REVIEW_LOG → docstrings → summaries.
