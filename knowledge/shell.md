# Rubric — Shell & manual work

What the developer still does by hand, in the terminal, outside the agent. The
densest source of **forge** candidates.

## Read for
- **Repeated command families (`top_full_commands`, `git_subcommands`).** Recurring
  rituals — typecheck-and-tail, db-reset smoke loop, dev-server launch, deploy. Note
  variants differing only by a flag/path/`tail -N`; they collapse into one jig
  (script/hook/CLI).
- **Session correlation.** `during_session` vs `outside_session`: is the shell a
  *launcher* (claude/exit dominate) or a parallel workbench? Verbs spiking **during**
  a live session = deliberate division of labor (git by hand while the agent codes)
  — that's a choice, **don't propose handing it back**. `launching`/`wrapping-up`
  proximity buckets reveal pre/post-session rituals worth a jig.
- **The package join (`inventory_join`).**
  - `installed_unused`: tools you installed and never run → dispose/uninstall (low
    stakes; window-bounded — don't nag).
  - `used_suboptimal`: heavy raw verb while a sharper installed tool sits idle (raw
    `git` ×N, `lazygit` 0 uses) → **suggest** trying it. A habit nudge, not a build.

## Current best practice (tend this)
- A 3+-step command ritual run daily is a script or hook, not muscle memory.
- Background dev servers; don't re-launch by hand every session.
- Suggest sharper tools only where the data shows real volume — don't tool-shame.

## Payback framing
- Shell rituals are the canonical invisible 90%: each instance too cheap to bother,
  the aggregate is hours. Lead with frequency × per-instance, shown.
