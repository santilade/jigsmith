# Rubric — Context (context engineering)

What actually enters the model's window each session. Dead/bloated context costs
tokens and attention on every turn.

## Read for
- **Memory weight (`memory_files`).** Oversized CLAUDE.md / AGENTS.md load on every
  turn. Flag the largest; ask whether all of it earns its place. Candidate: split
  rarely-needed sections into on-demand skills.
  - **Exclude the Jigsmith repo's own scaffold.** Drop any `memory_files` entry whose
    `scope` is the Jigsmith repo itself (its `CLAUDE.md` / `AGENTS.md`). That's the
    tool measuring its own constitution, not a workflow signal — it's load-bearing by
    design and governed by `tend-workbench`, not a Context finding. Never headline it.
- **Repeated preambles.** The same long setup re-typed across sessions =
  re-explaining → a memory entry or a skill. High-repeat preambles are a clean
  forge candidate (cross-ref Sessions' relaunch tax).
- **MCP surface (`mcp_surface`).** `configured` ≫ `exercised` = servers whose tool
  schemas load into context every turn but are never called. Dead surface. Candidate:
  disable the never-exercised ones (cross-ref Harness, which owns the inventory side).
- **Context rot (cross-ref Loop's `loop_control_commands`).** Long sessions
  accumulate stale turns — superseded plans, dead-end branches, resolved errors —
  that dilute the signal the model is steering by. Sparse `/clear` ÷ `/compact`
  relative to long unbroken sessions = rot left to build → the noise crowds the
  signal until the loop degrades. Candidate: a compaction habit or a checkpoint
  that resets the window at natural seams. The *signal* lives in Loop; the *cost*
  (a polluted window every subsequent turn) is a Context finding — name it here.

## Current best practice (tend this)
- Smallest sufficient context — signal over noise. Every token that isn't earning
  its place is competing with the ones that are; **delete ruthlessly** beats padding.
- Memory files hold *stable* facts, not transient task state. Prefer just-in-time
  retrieval (a skill that loads detail on demand) over an always-loaded wall of text.
- Each enabled MCP server spends a context budget every turn — keep only what you
  actually call.
- A long session is not a free context window: prune it at seams (`/clear` ÷
  `/compact`) before rot dilutes the signal.

## Payback framing
- Per-instance cost = tokens + attention on *every* turn, so even small bloat has
  high cumulative cost. This is exactly the invisible 90%.
