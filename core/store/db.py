"""Shared SQLite connection for Jigsmith.

One file, `jigsmith.db` at the repo root, holds every deterministic store the
app keeps: the jig rack (`core/store/rack.py`) and app settings
(`core/store/settings.py`). Gitignored — the developer's machine-local state.
Auto-renames a legacy `rack.db` on first open so existing jigs survive.
"""
from __future__ import annotations

import os
import sqlite3

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(REPO_ROOT, "jigsmith.db")
_LEGACY_PATH = os.path.join(REPO_ROOT, "rack.db")


def _migrate_legacy() -> None:
    if not os.path.exists(DB_PATH) and os.path.exists(_LEGACY_PATH):
        try:
            os.rename(_LEGACY_PATH, DB_PATH)
        except OSError:
            pass


def connect() -> sqlite3.Connection:
    _migrate_legacy()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
