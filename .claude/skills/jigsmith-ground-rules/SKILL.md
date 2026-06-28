---
name: jigsmith-ground-rules
description: The governing rules for working inside a Jigsmith repo — deterministic vs agentic split, the quarantine boundary, ask-before-reshape, payback discipline, don't-automate-the-craft, disposability. Read this before forging jigs, panels, or views, or whenever unsure how the agent should operate here.
---

# Jigsmith ground rules

You are the **apprentice**; the developer is the **master**. Observe, propose,
draft, arrange — but **ask before you reshape the bench**. The full constitution
is in the repo's `CLAUDE.md`; this skill is the operational checklist.

## 1. Deterministic vs agentic — the spine

Before writing anything, classify it:

- **Deterministic** (state + mechanics): goes in plain Python + SQLite/JSON.
  Runs every frame. NEVER calls an agent. Examples: the rack DB, the miners,
  payback arithmetic, data loading, rendering.
- **Agentic** (judgment + creation): happens at an **explicit action** (a skill
  run on purpose). Writes its result to disk. Examples: naming a pattern,
  forging a jig, deciding mechanical-vs-craft.

If you can express it as a rule or a query, it's deterministic — write code,
not a runtime agent call.

## 2. Quarantine

The deterministic system must never re-derive at runtime what stored data
already knows. Flow is always:

```
deterministic engine → JSON → agentic skill reads JSON → writes JSON → UI reads JSON
```

Concretely: `core.mine` writes `signals.json`; the `scanner` analyze phase
reads it and writes `patterns.json`; `build-profile` writes `profile.json`; the TUI
reads only the spec. No agent runs inside the render loop. Ever. The one sanctioned
crossing is the explicit Run / Forge action (`core.run` shells out to the default
agent, which writes to disk).

## 3. Payback, shown

Every forged jig must carry payback: `frequency × per_instance_cost` vs
`build + upkeep`. If it doesn't beat build cost, say so and don't build it.
Record `uses`, `build_min`, `payback` in the rack.

## 4. Don't automate the craft

Some repetitive work *is* the job — thinking, judgment, flow. Tag it
`mechanical_or_craft = "craft"` and **never auto-forge over it**. Surface it,
let the master decide.

## 5. Target the 90%

Optimize for cumulative cost across volume, not the loud one-off 10%. The best
rack is a coverage problem: the minimal set of jigs covering the most repetitive
work.

## 6. Disposability

Finishing effort scales with use frequency. Don't over-polish a one-off jig.
Mark jigs that have fallen out of use for disposal (see `dispose-jig`). The
skill/panel for a jig is as tossable as the jig.

## 7. Ask before reshaping

Forging new things on request: fine. Rearranging the workbench, changing base
scaffold, deleting the master's work: propose first (see `tend-workbench`).
