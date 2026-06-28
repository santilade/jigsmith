"""Load the section registry (`sections.json`) — the fixed analytical lenses.

Deterministic, dependency-light: the registry is data that both the engine and
the scanner orchestrator (`core.scan`) read. The lens *list* is fixed (skeleton
layer 1); only the content within each lens is agent-authored. Keeping the loader
here means the orchestration can iterate lenses in plain Python instead of asking
the agent to discover them.
"""
from __future__ import annotations

import json
import os

from core.store.db import REPO_ROOT

SECTIONS_PATH = os.path.join(REPO_ROOT, "sections.json")


def load() -> list[dict]:
    """The full registry, in file order. Raises if the file is missing/bad —
    the registry is base scaffold, not user data; a broken one is a real error."""
    with open(SECTIONS_PATH, "r") as fh:
        return json.load(fh)


def lenses() -> list[dict]:
    """The descriptive analyst lenses — every non-rollup section, in order."""
    return [s for s in load() if not s.get("rollup")]


def rollup() -> dict | None:
    """The single rollup section (the reconciler), or None if unset."""
    for s in load():
        if s.get("rollup"):
            return s
    return None


def ids() -> set[str]:
    """Every section id in the registry (lenses + rollup)."""
    return {s["id"] for s in load()}


def lens_ids() -> set[str]:
    """Just the descriptive lens ids — the valid Profile section ids."""
    return {s["id"] for s in lenses()}
