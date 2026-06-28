"""Format parser registry — keyed by FORMAT, shared across agents.

A parser turns one agent's on-disk history (a list of resolved file paths) into
the normalized Event stream. Agents are data (manifests); formats are code
(here). Many agents reuse one format, so the long tail of new agents needs zero
code as long as they speak a format we already parse.
"""
from __future__ import annotations

from collections.abc import Iterable

from core.events import Event

# format id -> parser(paths: list[str], agent_id: str) -> Iterable[Event]
PARSERS: dict = {}


def register(fmt: str):
    def deco(fn):
        PARSERS[fmt] = fn
        return fn
    return deco


def has_parser(fmt: str) -> bool:
    return fmt in PARSERS


def parse_agent(manifest) -> list[Event]:
    """Run the right parser for an agent manifest. Never raises."""
    fn = PARSERS.get(manifest.history_format())
    if not fn:
        return []
    try:
        return list(fn(manifest.history_paths(), manifest.id))
    except Exception:
        return []


# import the built-in parsers so they self-register
from core.parsers import (claude_jsonl, openai_jsonl,  # noqa: E402,F401
                          opencode_db, opencode_store)
