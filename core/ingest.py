"""Ingest — turn the configured agents (and shells) into normalized streams.

The single front door the signal layer calls. Deterministic; reads disk only.
"""
from __future__ import annotations

from core import agents
from core.events import Event, ShellCmd
from core.parsers import parse_agent
from core.parsers.shell_history import SHELLS, parse_shell


def ingest_events(agent_ids: list[str] | None = None) -> list[Event]:
    """Events from the agents to inspect (settings-driven unless ids given)."""
    if agent_ids is None:
        manifests = agents.to_inspect()
    else:
        manifests = [m for m in (agents.by_id(a) for a in agent_ids) if m]
    events: list[Event] = []
    for m in manifests:
        events.extend(parse_agent(m))
    events.sort(key=lambda e: (e.ts is None, e.ts or 0.0))
    return events


def ingest_shells(shell_ids: list[str] | None = None) -> dict:
    """ShellCmd streams keyed by shell id, plus the dominant bulk-ts per shell."""
    from core.store import settings
    if shell_ids is None:
        shell_ids = settings.inspect_shells() or ["zsh"]
    out: dict[str, dict] = {}
    for sid in shell_ids:
        path = SHELLS.get(sid)
        if not path:
            continue
        cmds, dominant = parse_shell(path, sid)
        out[sid] = {"commands": cmds, "dominant_bulk_ts": dominant}
    return out
