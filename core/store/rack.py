"""The rack — SQLite CRUD for jigs (your forged tools).

A jig is any forged thing: skill, tool, hook, script, agent config, CLI, TUI. The
rack tracks each jig's kind, status and payback so disposability is visible. CRUD
=> SQLite, per the ground rules (deterministic state lives in code/data, not in
the agent). Lives in the shared `jigsmith.db`. The `forge-jig` / `dispose-jig`
skills write here. The rack starts empty — it fills as you forge jigs.
"""
from __future__ import annotations

from datetime import datetime, timezone

from core.store.db import DB_PATH, connect  # noqa: F401

KINDS = ["skill", "tool", "hook", "script", "agent", "tui", "cli"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS jigs (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    kind         TEXT NOT NULL,
    build_min    INTEGER NOT NULL DEFAULT 0,
    payback      TEXT DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'active',  -- active | candidate | retired
    path         TEXT DEFAULT '',
    definition   TEXT DEFAULT '',
    created      TEXT DEFAULT ''
);
"""


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def init(seed: bool = False) -> None:  # seed kept for call-site compat; rack starts empty
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def list_jigs() -> list[dict]:
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM jigs ORDER BY name ASC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_jig(jig_id: str) -> dict | None:
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM jigs WHERE id = ?", (jig_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def upsert_jig(jig: dict) -> None:
    cols = ["id", "name", "kind", "build_min", "payback",
            "status", "path", "definition", "created"]
    jig.setdefault("created", _now())
    vals = [jig.get(c, "") for c in cols]
    placeholders = ",".join("?" for _ in cols)
    updates = ",".join(f"{c}=excluded.{c}" for c in cols if c != "id")
    conn = connect()
    try:
        conn.execute(
            f"INSERT INTO jigs ({','.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}", vals)
        conn.commit()
    finally:
        conn.close()


def delete_jig(jig_id: str) -> None:
    conn = connect()
    try:
        conn.execute("DELETE FROM jigs WHERE id = ?", (jig_id,))
        conn.commit()
    finally:
        conn.close()
