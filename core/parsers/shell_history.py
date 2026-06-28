"""Shell history parsers → the ShellCmd stream (zsh / bash / fish).

Shells are inspect-sources just like agents — a history location + a format. They
don't go through the agent Event registry (they're commands, not turns); the
`shell` signal section reads them via `parse_shell()` and correlates them to agent
active-intervals. zsh is fully supported (the format we have data for); bash and
fish are handled best-effort. New shells register via the `register-shell` skill.

The dominant-bulk-ts filter is load-bearing: zsh import lumps many commands under
one identical epoch; that most-common ts is unreliable, so entries carrying it are
flagged `reliable=False` and excluded from time-correlation (but still counted in
vocabulary).
"""
from __future__ import annotations

import os
import re
from collections import Counter

from core.events import ShellCmd
from core.helpers import scrub, verb as leading_verb

# id -> default history path
SHELLS = {
    "zsh": "~/.zsh_history",
    "bash": "~/.bash_history",
    "fish": "~/.local/share/fish/fish_history",
}

_ZSH_HEADER = re.compile(r"^: (\d+):\d+;(.*)$", re.S)


def _zsh(path: str) -> list[tuple[int | None, str]]:
    out: list[tuple[int | None, str]] = []
    try:
        raw = open(path, "r", errors="replace").read()
    except Exception:
        return out
    logical: list[str] = []
    for line in raw.splitlines():
        if logical and logical[-1].endswith("\\"):
            logical[-1] = logical[-1][:-1] + "\n" + line
        else:
            logical.append(line)
    for entry in logical:
        m = _ZSH_HEADER.match(entry)
        if m:
            out.append((int(m.group(1)), m.group(2).strip()))
        elif entry.strip():
            out.append((None, entry.strip()))
    return out


def _bash(path: str) -> list[tuple[int | None, str]]:
    out: list[tuple[int | None, str]] = []
    try:
        lines = open(path, "r", errors="replace").read().splitlines()
    except Exception:
        return out
    pending_ts: int | None = None
    for line in lines:
        if line.startswith("#") and line[1:].strip().isdigit():
            pending_ts = int(line[1:].strip())
            continue
        if line.strip():
            out.append((pending_ts, line.strip()))
            pending_ts = None
    return out


def _fish(path: str) -> list[tuple[int | None, str]]:
    out: list[tuple[int | None, str]] = []
    try:
        lines = open(path, "r", errors="replace").read().splitlines()
    except Exception:
        return out
    cmd = None
    for line in lines:
        if line.startswith("- cmd:"):
            cmd = line.split(":", 1)[1].strip()
        elif line.strip().startswith("when:") and cmd is not None:
            try:
                out.append((int(line.split(":", 1)[1].strip()), cmd))
            except ValueError:
                out.append((None, cmd))
            cmd = None
    return out


_RAW = {"zsh": _zsh, "bash": _bash, "fish": _fish}


def parse_shell(path: str, shell: str) -> list[ShellCmd]:
    """Parse one shell history file into ShellCmds, with the bulk-ts reliability flag."""
    path = os.path.expanduser(path)
    raw = _RAW.get(shell, _zsh)(path)
    ts_counts = Counter(ts for ts, _ in raw if ts is not None)
    dominant = ts_counts.most_common(1)[0][0] if ts_counts else None
    out: list[ShellCmd] = []
    for ts, cmd in raw:
        if not cmd:
            continue
        out.append(ShellCmd(ts=float(ts) if ts is not None else None, shell=shell,
                            verb=leading_verb(cmd) or "", command=scrub(cmd),
                            reliable=ts is not None and ts != dominant))
    return out, dominant
