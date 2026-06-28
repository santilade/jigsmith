"""App settings — a tiny key/value table in the shared jigsmith.db.

Deterministic, machine-local state the developer tends from Settings: the
default agent (runs the agentic flows), which agents to inspect (whose history +
inventory the mirror reads), and the theme. Values are JSON-encoded. Reads never
raise (return the default) so a missing table can't crash a frame; call `init()`
once at startup.
"""
from __future__ import annotations

import json
import sqlite3

from core.store.db import connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
"""


def init() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def get(key: str, default=None):
    conn = connect()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key = ?",
                           (key,)).fetchone()
    except sqlite3.OperationalError:
        return default
    finally:
        conn.close()
    if not row:
        return default
    try:
        return json.loads(row["value"])
    except (ValueError, TypeError):
        return default


def set(key: str, value) -> None:  # noqa: A001 - dict-ish api on purpose
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value)),
        )
        conn.commit()
    finally:
        conn.close()


# ---- typed accessors --------------------------------------------------------

def inspect_agents() -> list[str] | None:
    """Agent ids to inspect, or None when never set (→ treat as all inspectable)."""
    v = get("inspect_agents")
    return v if isinstance(v, list) else None


def set_inspect_agents(ids: list[str]) -> None:
    set("inspect_agents", list(ids))


def default_agent() -> str | None:
    v = get("default_agent")
    return v if isinstance(v, str) else None


def set_default_agent(aid: str) -> None:
    set("default_agent", aid)


def inspect_shells() -> list[str] | None:
    v = get("inspect_shells")
    return v if isinstance(v, list) else None


def set_inspect_shells(ids: list[str]) -> None:
    set("inspect_shells", list(ids))


def theme(default: str = "jigsmith") -> str:
    v = get("theme", default)
    return v if isinstance(v, str) else default


def set_theme(name: str) -> None:
    set("theme", name)
