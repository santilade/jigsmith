# Rubric — Harness (the static rig)

The installed config that shapes every session, joined against what's actually
invoked. The home of **dispose** candidates.

## Read for (the inventory ⋈ usage join)
- **Installed + unused.** Skills/agents/MCP servers/plugins present but never
  invoked in the window → dispose candidates. The `join.skills_unused` /
  `mcp_unused` / `agents_unused` lists are the raw material.
- **Most-used.** What earns its keep — leave alone, and note as the spine of the
  workflow.
- **Per-project clutter.** Projects carrying many configs that don't get exercised.

## Judgment (critical)
- **"Unused" is window-bounded.** A skill used once a quarter looks dead in a 30-day
  mine. Before proposing dispose, weigh: is it dead, or rare-but-load-bearing
  (incident response, release ritual)? Report install + use-count; recommend, don't
  condemn. The dev confirms.
- MCP clutter is the highest-value find — each dead server also bloats Context every
  turn (cross-ref). Disposing it wins twice.

## Current best practice (tend this)
- Keep the global skill/agent set lean; install per-project what's per-project.
- Don't hoard MCP servers "just in case" — they cost context whether or not used.
- Audit the rig periodically; the join makes it a number, not a vibe.

## Payback framing
- Dispose payback = recovered attention + (for MCP/memory) recovered context tokens
  every turn. Cheap to act on, compounding to keep.
