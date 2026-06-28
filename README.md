# Jigsmith

A self-revising toolsmith for agent-driven development.

Jigsmith is not a product or a fixed platform. It is a **generator plus a living
model of how you work** — a system that observes how a developer actually drives
coding agents, makes that picture legible, and helps forge personal tools that
fit. As your workflow changes, the tools change with it.

---

## Why it exists

Two forces, equal weight:

1. **The field moves weekly.** There is no settled way to work with coding agents.
   Methods shift constantly, so any fixed tool ages out fast.
2. **Every developer works differently.** Even at one moment there is no single
   workflow — some run swarms of sub-agents, some stay in one deep session, some
   juggle several agents across projects.

The problem is two-dimensional: tooling must track change **over time** *and* fit
divergence **across people**. A fixed platform fails both. The only thing that
survives both axes is the coding agent itself, because skills and tools let it
reshape to any workflow. So: don't build the tools. Build the thing that **builds
and maintains the tools** — fitted to one developer, now, and re-fitted as that
changes.

---

## Philosophy

**Restore the craftsman.** A craftsman makes their own jigs and balances their own
hammer. In an era where AI threatens to turn developers into assembly-line
prompt-feeders, Jigsmith rebuilds the craftsman who forges personal tools — the
human-system and the tool-system co-evolving, Engelbart-style, for one person.

**The developer is the master; the agent is the apprentice.** The dev owns the
workbench and has final say. The agent observes, proposes, drafts, arranges — but
asks before it reshapes the bench. A workbench is *tended*, never silently
*configured*.

**No types, no buckets.** The moment you match a person to an archetype you stop
fitting *them*. Every workbench is N=1 — grown from the individual's own data, never
selected from a menu. (The Profile's *sections* are fixed analytical **lenses**, not
person-types — they let you compare yourself to yourself over time.)

**Human-driven, not autonomous.** The goal is not a Jarvis that hides the work. It
is to make the developer **more conscious** of their own workflow, so painpoints are
easy to see and act on. Consciousness over convenience.

**Disposability is a feature.** Finishing scales with frequency. Daily staples earn
real polish; one-off jigs get minimal finishing and are tossed when done.

---

## The core target: the 90%

The instinct is to automate the **10%** — the acute, novel, annoying task that
announces itself. Wrong target. The leverage is the **90%**: the repetitive daily
work that is individually too cheap to bother automating but in aggregate is where
the hours go. It is invisible precisely because no single instance hurts.
**Jigsmith's first job is to make that aggregate visible.**

This sets the measure: **volume and cumulative cost, not per-instance pain.** Two
disciplines keep it honest:

- **Payback math, shown.** Frequency × per-instance cost must beat build + upkeep.
- **Don't automate the craft.** Some repetitive work *is* the job — thinking,
  judgment, flow. The mechanical 90% and the essential 90% look alike to a miner;
  the human decides which is which.

The pitch: **automate the mechanical 90% to reclaim attention for the 10% that is
actually craft.**

---

## How it works

Agents already keep a logbook of every session. Jigsmith mines it — and your shell
history, and your installed config — through one pipeline:

```
INGEST                 SIGNALS              ANALYZE              RENDER
agent history ─┐
shell history ─┼─► Event stream ─► signals.json ─► profile.json ─► TUI
inventory  ────┘   (normalized)     (per-section)   (+ rack)
```

- **Multi-agent by construction.** Every agent (Claude Code, opencode, codex, and
  any you register) is read by a *format parser* into one normalized **Event
  stream**, so the analysis is agent-agnostic and shows which agent you use for what.
- **The `inventory ⋈ usage` join.** What's *installed* (skills, MCP servers, CLI
  tools) joined against what you *actually use* surfaces dead config to dispose and
  manual work to forge.
- **One specialist per lens.** Fixed sections (Usage, Sessions, Loop, Context,
  Harness, Shell), each analyzed by a focused agent reading a curated best-practice rubric,
  rolled up into ranked, payback-scored candidates.
- **The deterministic/agentic line.** State and mechanics are plain Python + JSON,
  run every frame, never calling an agent. Judgment and creation happen only at an
  explicit action that writes to disk; the system never re-derives at runtime what
  stored data already knows.

---

## The surfaces

- **Profile (home) — the mirror.** Your workflow across the fixed section-lenses,
  agent-authored from the mined signals. Press **`r`** to mine → analyze → report.
- **Workbench — the rack.** Your forged jigs, disposability visible.
- **Forge — the hand-off.** Pick a mined candidate; Jigsmith hands it to a live
  agent session prefilled with a `forge-jig` brief. Forging stays human-driven.

(Cross-assistant *config management* is deliberately out of scope — tools like CC
Switch already own that. Jigsmith is the mirror, not a config manager.)

---

## Quickstart

A **starter template**, not an app you install. Uses [uv](https://docs.astral.sh/uv/).
The engine is stdlib-only; the TUI needs Textual (in `pyproject.toml`).

```bash
git clone <repo> jigsmith && cd jigsmith
rm -rf .git && git init   # start your own history — it's all yours now
uv sync

# 1. extract your workflow data (deterministic, in-process)
uv run python -m core      # → signals.json

# 2. open the workbench
uv run jigsmith            # or: uv run python -m tui
```

Inside: `Profile` = your mirror; `Workbench` = your rack; `Forge` = candidates.
Press `r` to run the scanner, `q` to quit, command palette to jump around and
to pick **agents to inspect** / the **default agent**. To find what's worth forging,
run the **`scanner`** pipeline, then **`forge-jig`**.

## Repo layout

| Path | What | Layer |
|---|---|---|
| `core/` | deterministic engine: ingest, parsers, inventory, signals → `signals.json` | base |
| `core/agents/` | agent source adapters = manifests (data) + registry | base |
| `core/parsers/` | history-format parsers (claude/openai/opencode/shell) | base |
| `core/signals/` | one module per section lens | base |
| `core/store/` | deterministic state: db, settings, the jig rack | base |
| `sections.json` | the section registry (the lenses) | base |
| `knowledge/` | curated best-practice rubrics, one per lens — **tend these** | yours |
| `tui/` | the Textual workbench (shell, components, screens) | base |
| `tui/panels/` | fixed reusable boxes; `forged/` = new TYPEs you forge (rare) | base/forged |
| `tui/config/profile.json` | agent-authored Profile spec (boxes + inline data) | yours |
| `signals.json` · `patterns.json` | mined data + ranked candidates (gitignored) | yours |
| `ARCHITECTURE.md` | the data contracts | base |
| `.claude/` | the agent's operating manual (constitution + skills) | base seed |

`base` = load-bearing scaffold, edit with care. `yours` = grow freely. After clone
the split is for legibility, not protection — it's all yours.

Skills: `jigsmith-ground-rules`, `run-miner`, `scanner`, `build-profile`,
`forge-jig`, `forge-component`, `tend-workbench`, `dispose-jig`, `register-agent`,
`register-shell`. See `CLAUDE.md` for the constitution and `ARCHITECTURE.md` for the
wiring.

## Status

The deterministic engine is rebuilt and proven on real history: the mine pipeline
runs in-process, multi-agent-ready, with the inventory ⋈ usage join. The gate —
does a real recurring pattern with payback fall out? — is **green** on first data
(dead installed skills, raw `git` while `lazygit` idle, hours of babysitting wait).
The agentic analyze/report fan-out is wired; the next proof is a forged jig whose
payback holds up in use.
