# Rubric — Forge Candidates (the rollup)

Not a lens — the **reconciler**. Runs after every section analyst. Collects all
their suggestions, dedups, ranks, and writes `patterns.json` (the **Forge tab's**
candidates) + rack candidate rows. It is NOT rendered as a Profile section — the
Profile is the mirror; the Forge tab owns these candidates.

## Job
1. **Collect** every section's suggestions (uniform shape: `name, section,
   jig_kind, evidence, frequency, est_per_instance_cost, payback,
   mechanical_or_craft, confidence, automatable_as`).
2. **Dedup.** The same idea surfaces from multiple lenses (a dead MCP shows in both
   Harness and Context). Merge into one, keeping the strongest evidence and citing
   both sections.
3. **Rank by cumulative cost (the 90%), not loudness.** `frequency ×
   per_instance_cost` vs `build + upkeep`. Mix `forge`, `dispose`, `suggest` in one
   ranked list — a dead-MCP dispose can outrank a marginal forge.
4. **Gate.** Drop anything that doesn't clear payback. Flag thin-N as directional.
   Never rank a craft-flagged item as a forge — surface it as leave-alone.

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
