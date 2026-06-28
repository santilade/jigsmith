"""Agent registry — loads built-in + user manifests, exposes the two roles.

Built-ins ship as JSON under `builtin/`. User/skill-registered agents live under
~/.config/jigsmith/agents/*.json (written by the `register-agent` skill). Same
shape, one path. Selection (default agent / agents to inspect) reads settings.
"""
from __future__ import annotations

import glob
import json
import os

from core.agents.manifest import AgentManifest

_BUILTIN_DIR = os.path.dirname(__file__) + "/builtin"
_USER_DIR = os.path.expanduser("~/.config/jigsmith/agents")


def _load_dir(d: str) -> dict[str, AgentManifest]:
    out: dict[str, AgentManifest] = {}
    for path in sorted(glob.glob(os.path.join(d, "*.json"))):
        try:
            with open(path) as f:
                out_m = AgentManifest.from_dict(json.load(f))
            out[out_m.id] = out_m
        except Exception:
            continue
    return out


def all_agents() -> dict[str, AgentManifest]:
    """User manifests override built-ins with the same id."""
    reg = _load_dir(_BUILTIN_DIR)
    reg.update(_load_dir(_USER_DIR))
    return reg


def by_id(aid: str) -> AgentManifest | None:
    return all_agents().get(aid)


def runnable() -> list[AgentManifest]:
    return [m for m in all_agents().values() if m.can_run()]


def inspectable() -> list[AgentManifest]:
    """Agents that have mineable history right now."""
    return [m for m in all_agents().values() if m.can_inspect()]


def default() -> AgentManifest | None:
    """The default agent (runs the agentic flows). Settings → first runnable."""
    from core.store import settings
    reg = all_agents()
    chosen = settings.default_agent()
    if chosen and chosen in reg and reg[chosen].can_run():
        return reg[chosen]
    runs = runnable()
    if runs:
        return runs[0]
    return reg.get("claude")


def to_inspect() -> list[AgentManifest]:
    """Agents the mirror should mine: settings filter ∩ inspectable, else all."""
    from core.store import settings
    chosen = settings.inspect_agents()
    insp = inspectable()
    if chosen is None:
        return insp
    return [m for m in insp if m.id in chosen]


def tag(aid: str) -> str:
    m = by_id(aid)
    return m.tag if m else aid[:2]


def label(aid: str) -> str:
    m = by_id(aid)
    return m.label if m else aid
