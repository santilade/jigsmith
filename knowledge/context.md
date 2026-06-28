# Rubric — Context (context engineering)

What actually enters the model's window each session. Dead/bloated context costs
tokens and attention on every turn.

## Read for
- **Memory weight (`memory_files`).** Oversized CLAUDE.md / AGENTS.md load on every
  turn. Flag the largest; ask whether all of it earns its place. Candidate: split
  rarely-needed sections into on-demand skills.
- **Repeated preambles.** The same long setup re-typed across sessions =
  re-explaining → a memory entry or a skill. High-repeat preambles are a clean
  forge candidate (cross-ref Sessions' relaunch tax).
- **MCP surface (`mcp_surface`).** `configured` ≫ `exercised` = servers whose tool
  schemas load into context every turn but are never called. Dead surface. Candidate:
  disable the never-exercised ones (cross-ref Harness, which owns the inventory side).

## Current best practice (tend this)
- Smallest sufficient context. Memory files hold *stable* facts, not transient task
  state. Prefer just-in-time retrieval (a skill that loads detail on demand) over a
  always-loaded wall of text.
- Each enabled MCP server spends a context budget every turn — keep only what you
  actually call.

## Payback framing
- Per-instance cost = tokens + attention on *every* turn, so even small bloat has
  high cumulative cost. This is exactly the invisible 90%.
