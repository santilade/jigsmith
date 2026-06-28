---
name: forge-jig
description: Forge a new personal dev tool (a "jig") — a skill, tool, hook, script, agent config, TUI, or CLI — and register it in the Jigsmith rack with its payback. Use when the developer wants to automate a recurring pattern. Pairs with scanner (which finds what's worth forging).
---

# Forge a jig

A **jig** is any forged tool fitted to this developer: a skill, tool, hook,
script, agent config, TUI, or CLI. Forging means: understand the problem, scope
the tool *with* the developer, build it, then record it in the rack so its
payback and disposability stay visible.

The developer owns the bench; you assist. **Forging is human-driven —
you do not auto-build.** Define the tool together, get a go-ahead, then build.

## Phase 0 — understand & scope (do this first, before any build)

Usually you arrive here from the Forge tab with a mined candidate already stated.
A candidate carries three bands: **narrative** (`name`, `painpoint`, `frequency`,
`evidence`), **fix** (`approach` custom|download|manual, `tool_type`, `summary`,
`what`, `why`, `where`), and **gate** (`mechanical_or_craft`, `payback`,
`confidence`). Whether or not you arrive with one:

1. **Restate the pain point** in your own words so you and the developer agree on
   what actually hurts and where. If you came in with a candidate, reflect its
   `painpoint` + `evidence` back.
2. **Gate it.** Confirm it's **mechanical, not craft** — never automate thinking,
   judgment, or flow. Confirm **payback**: frequency × per-instance cost must beat
   build + upkeep. If it's craft, or payback doesn't clear, **say so and stop** —
   tooling busywork is the anti-goal.
3. **Confirm the fix with the dev.** The candidate's `fix.approach`
   (custom / download / manual) and `fix.tool_type` are a *proposal*, not a
   decision. The developer may prefer a custom jig over a suggested download (or
   the reverse, or a plain manual change). Surface the suggested fix — `what`,
   `why`, `where` — and get their explicit call on **approach + form** before you
   scope. This is the one axis to settle first.
4. **Interview to nail scope.** Ask the questions you need — exact inputs/outputs,
   edge cases, where it lives, what "done" looks like, naming. One focused round
   at a time; don't dump twenty questions.
5. **Converge on a short spec** (one paragraph: what it does, its form, where it
   lives, payback). Show it, get an explicit go-ahead.

**Scale the gate to the jig (disposability).** A trivial, throwaway one-off needs
only a quick spec-and-go — restate, confirm payback, one-line spec, build. A daily
staple earns the full interview and an explicit written sign-off before you build.
Match the rigor to how much the jig will be used.

## The payback formula

A jig is only worth it if `frequency × per_instance_cost > build + upkeep`. Pull
the numbers from `scanner` output (`patterns.json`). This is the arithmetic
behind the Phase 0 gate — show it; don't just assert "it pays off".

## Pick the form (ground rule: deterministic vs agentic)

Take the **first** row that fits (lightest → heaviest; cheapest form that kills the
pattern wins). The candidate's `fix.tool_type` is a starting guess — re-walk this at
forge time.

| Need | Form |
|---|---|
| agent keeps missing a fact/rule/preference you re-type | **memory** (a `CLAUDE.md` line / output-style) |
| deterministic state/mechanics | **script** (plain Python) + **SQLite** if CRUD |
| fires automatically on an event | **hook** |
| reusable agent procedure / judgment | **skill** |
| a fitted command surface | **CLI** |
| a fitted interactive surface | **TUI** (Textual) or a Jigsmith **Profile box** (see `build-profile`) |
| a tuned sub-agent | **agent config** |

Deterministic parts must not call an agent at runtime (quarantine).

## Phase 1 — build & register (only after the Phase 0 go-ahead)

1. **Build it** in the right place (e.g. a new `.claude/skills/<name>/SKILL.md`
   for a skill, a script under a `scripts/` dir, etc.). Match the developer's
   existing conventions.
2. **Register it in the rack:**
   ```bash
   uv run python -c "
   from core.store import rack as db
   db.init()
   db.upsert_jig({
       'id': 'commit-ritual',
       'name': 'commit-ritual',
       'kind': 'skill',          # memory|skill|hook|agent|script|cli|tui|alias
       'build_min': 20,
       'payback': '+0.5h/wk',
       'status': 'active',       # active|candidate|retired
       'path': '.claude/skills/commit-ritual',
       'definition': 'stage→commit→push with conventional message',
   })
   "
   ```
   For a pattern found but not yet built, register with `status='candidate'`.
3. **Tell the developer** what was forged, where, and the payback. Offer to wire
   it in (hook into settings, add to a view, etc.).

## Rules

- Finishing scales with frequency (disposability): polish daily staples, keep
  one-offs minimal.
- Ask before reshaping anything that already exists; forging new is fine.
