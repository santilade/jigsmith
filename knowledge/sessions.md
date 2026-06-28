# Rubric — Sessions & orchestration

How the developer drives. The densest source of forge candidates after Shell.

## Read for
- **Parallelism shape.** `overlap_seconds_same_project` ≫ `cross_project` = a
  **manual sub-agent swarm** (many sessions on one project) → candidate: a real
  sub-agent/workflow harness to replace the hand-coordination. `cross_project` ≫
  `same` = **project juggling** → candidate: per-project context/launch jigs, not
  swarm tooling. They look alike in raw counts; the split decides the tool.
- **Chains & re-onboarding tax.** Many short consecutive sessions with tiny gaps +
  high `/clear`/`/exit` = one effort chopped into fresh-context relaunches. Each
  relaunch re-explains setup → a memory/skill/CLAUDE.md candidate (cross-ref
  Context's repeated-preambles).
- **Babysitting (`responsiveness`).** High `pct_active_wall_waiting` or p90 turn
  wait = the developer idle, waiting on the agent. Candidates: faster checks
  (incremental typecheck, scoped tests), backgrounded servers, parallel work to
  fill the wait. **Reframe payback**: a saved wait-second is idle time reclaimed,
  not just a keystroke.

## Current best practice (tend this)
- Prefer one well-scoped sub-agent harness over N hand-launched parallel sessions.
- Background long-running commands; don't block a turn on a watch process.
- Short, frequent context resets are a smell — a stable memory file usually beats
  re-explaining every relaunch.

## Flag (craft, leave alone)
- Deep single-session flow on hard problems is craft. Parallelism that's
  deliberate thinking-in-public, not coordination overhead, isn't a forge.
