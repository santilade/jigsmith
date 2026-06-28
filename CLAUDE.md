# Jigsmith — operating constitution

This file governs how the agent works inside a Jigsmith repo. Read it before
forging anything. The skills in `.claude/skills/` are the detailed manuals,
`ARCHITECTURE.md` is the wiring, and this is the spine they hang on.

## What Jigsmith is

A **self-revising toolsmith** for one developer. Not a product, not a fixed
platform. It observes how *this* developer drives coding agents — across **every
agent they use** — makes that picture legible, and helps forge personal tools that
fit, re-fitting as the workflow changes. See `README.md` for why it exists.

This repo is a **starter template**, not an app you install. The user cloned it,
deleted `.git`, and started their own history. After that, **it is all theirs** —
the base/forged split below is for legibility, not protection.

## Philosophy

The principles behind the rules below:

- **Restore the craftsman.** A craftsman makes their own jigs and balances their
  own hammer. Where AI threatens to turn developers into assembly-line
  prompt-feeders, Jigsmith rebuilds the craftsman who forges personal tools —
  human-system and tool-system co-evolving, Engelbart-style, for one person.
- **No types, no buckets.** The moment you match a person to an archetype you stop
  fitting *them*. Every workbench is N=1 — grown from the individual's own data,
  never selected from a menu. The Fingerprint's *sections* are fixed analytical
  **lenses**, not person-types: they let you compare yourself to yourself over time.
- **Human-driven, not autonomous.** The goal is not a Jarvis that hides the work.
  It is to make the developer **more conscious** of their own workflow, so
  painpoints are easy to see and act on. Consciousness over convenience.

The **dev-owns-the-bench rule** and **disposability** sections below are the other
two pillars.

## The dev-owns-the-bench rule

The **developer owns the bench**; the agent assists. The dev owns the
workbench and has final say. You may observe, propose, draft, and arrange — but
**ask before you reshape the bench**. Readability and usefulness are the dev's
to judge. A workbench is *tended*, never silently *configured*.

## The one ground rule: deterministic vs agentic

Draw a hard line and keep runtime judgment quarantined:

- **Deterministic** — state and mechanics. Plain Python + SQLite/JSON. The engine
  (`core/` — ingest, parsers, inventory, signals), the rack (`core/store/rack.py`),
  payback arithmetic, data loading (`tui/data/store.py`), rendering. This code runs
  every frame; it must never call an agent (save the one documented exception below).
- **Agentic** — judgment and creation. Naming a "90% pattern", deciding
  mechanical-vs-craft, forging a jig, composing the Fingerprint. This happens at an
  **explicit action** (a skill the agent runs on purpose), writes its result to
  disk, and the deterministic system then only *reads* that result.

**Quarantine:** the system never re-derives at runtime what deterministic code or
stored data already knows. Concretely: `core.mine` (deterministic, in-process)
emits `signals.json`; the `scanner` analyze phase (agentic) reads it and emits
`patterns.json`; `build-profile` (agentic) emits `profile.json`; the TUI
(deterministic) reads only the spec.

**Documented exception (the dev's call).** The `r` key / "Run scanner" runs
the *full* pipeline. Phase 1 (`core.mine.run()`) is deterministic and runs
**in-process**. Phases 2-3 are **orchestrated** by deterministic Python
(`core.scan`, which `DataStore.analyze_phase` / `report_phase` delegate to): it
loops the registry lenses, runs one analyst per lens in parallel via
`core.run.headless`, validates + retries each, then folds them with one rollup
agent — and only the *judgment* (per-lens analysis, rollup dedup/rank/web-check,
Profile composition) crosses to the agent. The loop, the validation, and the
final writes stay in Python. This is allowed *only here*: gated behind an explicit
user action, each agent call is a one-shot that writes to disk, and the TUI then
only *reads* `patterns.json` + `profile.json`. Never per-frame, never implicit.
The Forge hand-off (`launch_interactive`) is the same kind of sanctioned crossing.
A phase-1-only refresh stays in the palette for when you don't want the agent.
Everywhere else the boundary holds — do not widen it without the dev.

## Multi-agent: agents are data, formats are code

Jigsmith inspects every agent the developer uses, not just Claude. Each agent is a
**manifest** (`core/agents/builtin/*.json` or `~/.config/jigsmith/agents/*.json`)
declaring two independent capabilities: **run** (headless + interactive argv — the
*default* agent only) and **inspect** (history location + format + config paths —
the agents to *inspect*). History is parsed by a **format parser** keyed by format,
not agent, so a new agent reusing a known format needs zero code (`register-agent`).
Shells follow the same inspect-source model (`register-shell`).

## The target: the 90%

Optimize for **volume and cumulative cost**, not per-instance pain. Two disciplines:

- **Payback math, shown.** frequency × per-instance cost must beat build + upkeep.
- **Don't automate the craft.** Some repetitive work *is* the job (thinking,
  judgment, flow). Flag craft; never auto-forge over it. The human decides.

The **`inventory ⋈ usage` join** is the engine of recommendations: what's installed
joined against what's used surfaces *dispose* candidates (installed + unused) and
*forge* candidates (used + no tool). "Unused" is window-bounded — recommend, the
dev confirms.

## Disposability

Finishing effort scales with frequency of use. Daily staples get real polish; rare
one-off jigs get minimal finishing and are tossed when done. A forged jig's
skill/panel is as disposable as the jig. A feature, not a failure.

## Layout

```
core/                deterministic engine                                    (base)
  mine.py            orchestrator → signals.json (in-process, phase 1)
  ingest.py events.py helpers.py timing.py   the normalized Event stream
  agents/            source adapters = manifests (data) + registry
  parsers/           history-format parsers (claude/openai/opencode/shell)
  inventory/         read-only probes: configs (harness) + packages (shell)
  signals/           one module per section lens
  store/             deterministic state: db, settings, the jig rack
  run.py             the sanctioned agent shell-out (one headless call)
  scan/              deterministic phase-2/3 orchestrator: per-lens fan-out,
                     validation/retry, rollup assembly (shape.py = the contract)
  sections.py        registry loader (the lenses, in Python)
sections.json        the section registry (the lenses)                       (base)
knowledge/           curated best-practice rubrics, one per lens             (yours)
tui/
  app.py             shell: Fingerprint/Workbench/Forge tabs + command palette (base)
  data/store.py      runs the engine + the agentic phases (reads the JSON)    (base)
  panels/contract.py · components.py   render helpers + fixed component TYPEs  (base)
  panels/forged/     new component TYPEs you forge (rare)                     (FORGED)
  config/profile.json  agent-authored Fingerprint spec (boxes + inline data)  (yours)
  screens/           Fingerprint / Workbench / Forge / pickers                (base)
jigsmith.db          rack + settings (gitignored)                            (yours)
signals.json patterns.json   mined data + ranked candidates (gitignored)      (yours)
.claude/skills/      this operating manual                          (base seed, yours)
```

`base` = load-bearing scaffold, edit with care. `forged`/`yours` = grow freely.

## Fixed vs dynamic (the three layers)

1. **Skeleton** — top-level tabs (Fingerprint / Workbench / Forge) + the **section
   registry** (`sections.json`): the fixed analytical lenses. Stable so you can diff
   yourself over time and each lens has a specialist. Fixed code/data.
2. **Components** — reusable boxes (`counters`, `bars`, `histogram`, `blocks`,
   `prose`). Fixed code; add a new *type* rarely (`forge-component`).
3. **Content** — which boxes per section, what data, where. **Dynamic**: the agent
   writes it into `config/profile.json` from the signals (`build-profile`). Values
   are inline — a snapshot until the next rebuild. This is the dogfood loop.

The lens *list* is fixed (layer 1); the content *within* each lens is agent-authored
(layer 3). Fixed lenses are not buckets-for-people — they are how N=1 compares to
itself over time.

## The surfaces

- **Fingerprint (home)** — the mirror: the six descriptive section-lenses (Usage,
  Sessions, Loop, Context, Harness, Shell), agent-authored from the signals and rendered
  from the fixed components. Run the miner, then rebuild with `build-profile`. The
  `forge` rollup is mined here but *shown on the Forge tab*, not duplicated as a
  Fingerprint section.
- **Workbench** — the rack of forged jigs, disposability visible.
- **Forge** — the hand-off: pick a mined candidate (the `forge` rollup's
  `patterns.json`), hand it to a live agent session.

Cross-assistant config *management* is out of scope (CC Switch et al. own it).

## How to extend (skills)

| Want to… | Run skill |
|---|---|
| understand the rules | `jigsmith-ground-rules` |
| make a new tool/skill/hook/script | `forge-jig` |
| mine → analyze → report the 90% patterns (full pipeline) | `scanner` |
| refresh the signals only (phase 1) | `run-miner` |
| (re)build the Fingerprint from the data (phase 3) | `build-profile` |
| add a new component TYPE (rare) | `forge-component` |
| the propose→feedback→adjust loop | `tend-workbench` |
| retire an unused jig | `dispose-jig` |
| inspect a new agent (hermes, openclaw, …) | `register-agent` |
| inspect a new/different shell | `register-shell` |

## Current status

The deterministic engine is rebuilt and verified on real history (multi-agent
Event stream, all section signals, the inventory ⋈ usage join). The gate — does a
real recurring pattern with payback fall out? — reads **green** on first data. The
agentic analyze/report fan-out (one analyst per lens → ranked rollup) is wired. The
next proof is a forged jig whose payback holds up in use — forge sparingly.
