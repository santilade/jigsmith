# Rubric — Forge Candidates (the rollup)

Not a lens — the **reconciler**. Runs after every section analyst. Collects all
their suggestions, dedups, ranks, and writes `patterns.json` (the **Forge tab's**
candidates) + rack candidate rows. It is NOT rendered as a Profile section — the
Profile is the mirror; the Forge tab owns these candidates.

`core.scan` already collected + validated every analyst's suggestions and hands you
the consolidated candidate list inline (uniform shape: `name, section, painpoint,
frequency, evidence, fix{approach, tool_type, summary, what, why, where},
gate{kind, mechanical_or_craft, payback, confidence}`). You reconcile:

1. **Dedup.** The same idea surfaces from multiple lenses (a dead MCP shows in both
   Harness and Context). Merge into one, keeping the strongest evidence and the
   primary lens's `section`.
2. **Source-check (painpoint FIRST, type LAST).** For **every** candidate — never let
   the form pre-filter the search — do the ONE web pass the per-lens analysts skipped.
   Hunt the *painpoint* across registries: code hosts for CLIs/TUIs (`gh search repos`,
   github.com/trending), the **official skill marketplace** (`anthropics/skills`) for an
   existing skill/agent, and MCP registries for a missing capability. Good fit →
   `fix.approach: download` (its own form sets `fix.tool_type`). Partial/no fit →
   `custom`, then pick the lightest form that fits — and **favor a `CLI + skill`** combo
   when the pattern has a deterministic mechanic *and* a judgment layer. Unreachable web
   → judgment + drop `gate.confidence` a notch.
3. **Rank by cumulative cost (the 90%), not loudness.** `frequency ×
   per_instance_cost` vs `build + upkeep`. Mix `forge`, `dispose`, `suggest` in one
   ranked list — a dead-MCP dispose can outrank a marginal forge.
4. **Gate.** Drop anything that doesn't clear payback. Flag thin-N as directional.
   Never rank a craft-flagged item as a forge — surface it as leave-alone.

`core.scan` re-validates your `patterns.json` through the shape contract on write,
so keep every item in the uniform shape with an accurate `section`.

## Output discipline
- `patterns.json` = ranked candidates ONLY. Descriptive findings stay in their
  sections.
- Add strong `forge` candidates to the rack as `status="candidate"`; `dispose`
  candidates point at existing rack rows / installed config.
- **Never auto-build or auto-delete.** The rollup *recommends*; the dev acts
  (`forge-jig` / `dispose-jig`).

## The gate (Jigsmith's core bet)
This is where you prove a real recurring pattern with payload beating build cost
falls out of the data. If the top candidate is weak, say so plainly — a thin rollup
is an honest result, not a failure to find.
