---
name: dispose-jig
description: Retire or delete an unused Jigsmith jig and clean up its artifacts. Use when a forged tool has fallen out of use, the job it served is done, or the rack is cluttered. Disposability is a feature — keep the rack honest.
---

# Dispose a jig

Like a blacksmith's one-off jigs, forged tools are meant to be **tossed when the
job is done**. A cluttered rack hides the staples that matter. Disposing is
normal maintenance, not failure.

## When to dispose

- **Job done**: the pattern it served no longer happens.
- **Superseded**: a better jig covers the same work.
- **Negative payback**: upkeep now exceeds the time it saves.
- **Fell out of use**: you no longer reach for it (the miner's signals — skill /
  command / verb counts — can confirm it isn't being invoked anymore).

## Steps

1. **Confirm with the developer** — it's their bench. Show the reason (job done,
   superseded, no longer invoked, negative payback).
2. **Choose retire vs delete:**
   - *Retire* (keep the record, stop using): set `status='retired'`.
     ```bash
     uv run python -c "
     from core.store import rack as db
     j = db.get_jig('JIG_ID'); j['status'] = 'retired'; db.upsert_jig(j)
     "
     ```
   - *Delete* (gone): remove the rack row **and** its artifacts (skill dir,
     script, hook entry, or `profile.json` box + forged component).
     ```bash
     uv run python -c "from core.store import rack as db; db.delete_jig('JIG_ID')"
     ```
3. **Clean artifacts** — for a forged panel also remove its entry from any view;
   for a hook also remove it from settings. Leave no dangling references.

## Rules

- Ask first — never delete the dev's work unprompted (`tend-workbench`).
- Prefer *retire* when unsure; it keeps the history without the clutter.
- Removing a forged component type: delete `tui/panels/forged/<name>.py` and any
  `profile.json` box that uses `"component": "<name>"` so nothing dangles.
