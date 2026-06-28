"""Config loading. `profile.json` is the agent-authored Profile spec — the
dynamic content layer (which boxes, what data, where). User-owned after clone.
"""
from __future__ import annotations

import json
import os
import re

CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_PATH = os.path.join(CONFIG_DIR, "profile.json")


def _slug(text: str) -> str:
    """Lowercase kebab slug safe for a Textual widget id."""
    s = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return s or "section"


def load_profile() -> list[dict]:
    """Return the list of Profile sections (each: id, title, boxes).

    The spec is agent-authored, so `id` may be missing — backfill it from the
    title (uniquely) so the deterministic renderer and palette never crash on a
    spec gap. Quarantine holds: we only normalize what we read.
    """
    try:
        with open(PROFILE_PATH, "r") as fh:
            data = json.load(fh)
        sections = [s for s in data.get("sections", []) if isinstance(s, dict)]
    except Exception:
        return []

    seen: set[str] = set()
    for i, sec in enumerate(sections):
        sid = sec.get("id") or _slug(sec.get("title", "")) or f"section-{i}"
        while sid in seen:
            sid = f"{sid}-{i}"
        sec["id"] = sid
        seen.add(sid)

    # The `forge` rollup is the Forge tab's data (patterns.json), not a Profile
    # section — the Profile is the mirror, the Forge tab owns the candidates. Drop
    # it here in case a stale spec still carries one (see build-profile skill).
    return [s for s in sections if s["id"] != "forge"]
