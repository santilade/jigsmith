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

## Quickstart

A **starter template**, not an app you install. Uses [uv](https://docs.astral.sh/uv/).
The engine is stdlib-only; the TUI needs Textual (in `pyproject.toml`).

```bash
git clone https://github.com/santilade/jigsmith.git && cd jigsmith
rm -rf .git && git init   # start your own history — it's all yours now
uv sync

# open the workbench
uv run jigsmith
```

Inside: `Fingerprint` = your mirror; `Workbench` = your rack; `Forge` = candidates.
Press `r` to run the scanner, `q` to quit, command palette to jump around and
to pick **agents to inspect** / the **default agent**. To find what's worth forging,
run the **`scanner`** pipeline, then **`forge-jig`**.

See `CLAUDE.md` for the operating constitution (philosophy, surfaces, repo layout,
status) and `ARCHITECTURE.md` for the data contracts and pipeline wiring.
