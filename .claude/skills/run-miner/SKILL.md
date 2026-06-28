---
name: run-miner
description: Refresh Jigsmith's deterministic signals (phase 1). Runs the core engine over every inspected agent's history + shell history + installed config/package inventory and writes signals.json. No judgment, no agent — pure tally. Use to get fresh numbers before analyzing, or when the developer just wants the data updated.
---

# Run the miner (phase 1 — deterministic)

The cheap, deterministic refresh. Ingests every agent you inspect into one
normalized Event stream, computes all signal sections, and writes `signals.json`
at the repo root. Never names a pattern, never calls an agent.

## Do this

```bash
uv run python -m core      # ingest + signals → signals.json
```

That's the whole phase. It prints a one-line summary and the per-agent split.

In the TUI this is the phase-1 step of the `r` pipeline (also runnable alone from
the command palette). It runs **in-process** (`core.mine.run()`), so it's fast and
needs no subprocess.

## What it produces

`signals.json`, keyed by section (the registry is `sections.json`):

- `meta` — generated time, agents inspected, event count
- `usage` — overview, **by_agent** (the cross-agent split), per_project, tools, models, prompts, temporal, intents
- `sessions` — overall, parallel/overlap, consecutive/chains, responsiveness, busiest_days
- `context` — memory weight, repeated preambles, MCP surface configured-vs-exercised
- `harness` — config inventory ⋈ usage (installed-vs-used skills/agents/MCP)
- `shell` — shell vocabulary, session correlation, installed-vs-used tools

## Boundaries

- **Deterministic only.** Read side of the quarantine. It does not analyze, rank,
  or name patterns — that's `scanner` (agentic, phases 2-3).
- It reads whatever is in *agents to inspect* + *shells to inspect* (Settings).
  To add a new agent/shell, run `register-agent` / `register-shell` first.
- Empty sources (an agent you haven't used yet) contribute nothing — never an error.
- Stdlib-only and defensive: a bad history line is skipped, never crashes.
- Output is gitignored (the developer's own data). Safe to regenerate anytime.

After this, run `scanner` (analyze + report) to turn the numbers into
ranked, payback-scored candidates and rebuild the Profile.
