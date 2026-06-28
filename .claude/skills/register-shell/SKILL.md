---
name: register-shell
description: Teach Jigsmith to inspect a shell beyond the built-in zsh/bash/fish — or enable/disable which shells the Shell section mines. A shell is just an inspect-source with a history location + format, the same plug-in model as agents. Use when the developer wants the mirror to read a different or additional shell history (e.g. fish, nushell).
---

# Register a shell

Shells follow the same **inspect-source** model as agents: a history location +
a format. The Shell section correlates shell commands to agent active-intervals
and joins them against installed packages (used-vs-installed tools).

## Enable / choose shells

Which shells get mined is a setting (default: `["zsh"]`). To change it:

```bash
uv run python -c "from core.store import settings; settings.set_inspect_shells(['zsh','fish'])"
```

Built-in, ready to use: **zsh**, **bash**, **fish** (paths in
`core.parsers.shell_history.SHELLS`). zsh is the best-tested (the format we have
data for). Enabling one with no history just contributes nothing.

## Add a NEW shell (different history format)

If the shell isn't built in (e.g. nushell), teach the parser its format:

1. In `core/parsers/shell_history.py`, add the shell's default history path to
   `SHELLS` and a raw-parse function returning `[(epoch|None, command)]` (model it
   on `_zsh` / `_fish`). Wire it into the `_RAW` dispatch.
2. The shared `parse_shell()` then handles scrubbing (credential redaction +
   truncation), verb extraction, and the dominant-bulk-ts reliability flag — you
   only supply the raw `(timestamp, command)` extraction.

## Notes

- **Redaction is automatic.** `parse_shell` runs credential scrubbing before any
  command string is stored — never emit raw history.
- The **dominant-bulk-ts** filter matters: bulk-imported history lumps many
  commands under one timestamp; those are flagged unreliable and excluded from
  time-correlation (but still counted in vocabulary). Keep it for any new shell.

## Verify

```bash
uv run python -c "
from core.ingest import ingest_shells
out = ingest_shells()
for sid, d in out.items(): print(sid, len(d['commands']), 'cmds')
"
```

Then run `run-miner` — the shell stream feeds the Shell section's vocabulary,
session correlation, and the installed-vs-used tool join.
