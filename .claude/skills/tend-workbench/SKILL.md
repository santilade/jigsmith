---
name: tend-workbench
description: The propose → feedback → adjust loop for changing the Jigsmith workbench. Use before rearranging surfaces, editing base scaffold, changing the developer's views/config, or any reshape of things that already exist (as opposed to forging new jigs). Encodes ask-before-reshape.
---

# Tend the workbench

A workbench is **tended**, never silently configured. The developer owns the
bench. Your job is to keep the picture legible and propose
improvements — not to rearrange behind their back.

## When this applies

- Changing the layout of a surface (tabs, panel arrangement, navigation).
- Editing **base** scaffold (`tui/app.py`, `tui/screens/`, `tui/panels/contract.py`,
  the `core/` engine).
- Modifying the developer's `tui/config/profile.json`, rack contents, or settings.
- Deleting or retiring anything that already exists.

Forging *new* jigs/panels on request does **not** need this dance — just build.

## The loop

1. **Observe** — point at the data/friction that motivates the change (cite the
   Profile, a pattern, a payback number). No data, no reshape.
2. **Propose** — describe the change and its cost/benefit concretely. Show a
   before/after if it's visual.
3. **Feedback** — ask. Let the dev accept, tweak, or reject. Readability and
   usefulness are theirs to judge.
4. **Adjust** — apply only what's agreed. Record what changed.

## Rules

- Bias to the smallest legible change. The dashboard is a calm map, not a
  cockpit — don't add chrome that doesn't earn its space.
- Respect the base/forged line: edits to base scaffold deserve extra caution and
  an explicit heads-up.
- Consciousness over convenience: the goal is to make the developer *more*
  intentional about their workflow, not to hide the work.
