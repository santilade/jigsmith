"""DataStore — the read side of the quarantine boundary.

The deterministic engine (`core.mine`) writes `signals.json` at an explicit
action; the agentic phases write `patterns.json` + `profile.json`. The TUI only
ever *reads* that JSON — it never re-derives what the engine already computed.

Data-need keys are dotted and source-prefixed, e.g.
    "signals.usage.tools.global_frequency"
    "signals.sessions.responsiveness.total_wait_hours"
    "patterns.patterns"
The first segment selects the source; the rest walks into the JSON.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone

from core import scan
from core.mine import SIGNALS_PATH
from core.store.db import DB_PATH, REPO_ROOT

PROFILE_PATH = os.path.join(REPO_ROOT, "tui", "config", "profile.json")
PATTERNS_PATH = os.path.join(REPO_ROOT, "patterns.json")

# source name -> absolute path
SOURCES = {
    "signals": SIGNALS_PATH,        # core.mine (deterministic, phase 1)
    "patterns": PATTERNS_PATH,      # scanner analyze phase (agentic)
}

# The per-lens fan-out, validation, retry, and rollup assembly are deterministic
# Python now (`core.scan`); the store just triggers the two agentic phases at the
# explicit Run action and reloads the result. Phase 1 is in-process Python — no
# agent. This keeps orchestration on the deterministic side of the line; only the
# per-lens judgment and the rollup reconciliation cross to the agent.


class DataStore:
    def __init__(self) -> None:
        self._cache: dict[str, object] = {}
        self.load()

    def load(self) -> None:
        """(Re)read every source from disk. Never raises on a missing/bad file."""
        for name, path in SOURCES.items():
            try:
                with open(path, "r", errors="replace") as fh:
                    self._cache[name] = json.load(fh)
            except Exception:
                self._cache[name] = None

    def get(self, dotted: str, default=None):
        """Walk a source-prefixed dotted key. Returns default if any hop misses."""
        parts = dotted.split(".")
        node = self._cache.get(parts[0])
        for p in parts[1:]:
            if isinstance(node, dict):
                node = node.get(p)
            elif isinstance(node, list):
                try:
                    node = node[int(p)]
                except (ValueError, IndexError):
                    return default
            else:
                return default
        return default if node is None else node

    def has(self, source: str) -> bool:
        return self._cache.get(source) is not None

    def freshness(self, source: str = "signals") -> datetime | None:
        path = SOURCES.get(source, "")
        try:
            return datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
        except OSError:
            return None

    # ---- phase 1: deterministic, in-process (no agent) ----
    def run_miner(self) -> tuple[bool, str]:
        """Run the deterministic engine, then reload. BLOCKING — call from a worker."""
        from core import mine
        ok, msg = mine.run()
        self.load()
        return ok, msg

    # ---- reset to fresh-clone state (explicit action) ----
    def reset_workspace(self) -> tuple[bool, str]:
        """Wipe all mined data + machine-local settings back to a fresh clone.

        Deletes the gitignored artifacts (signals.json, patterns.json,
        jigsmith.db = rack + settings) and blanks the tracked Profile spec back
        to its empty skeleton. The next launch re-onboards, exactly as on a fresh
        download. Keeps a profile.json.bak for safety. Reloads after.
        """
        removed = []
        for path in (SIGNALS_PATH, PATTERNS_PATH, DB_PATH, DB_PATH + "-journal"):
            try:
                if os.path.exists(path):
                    os.remove(path)
                    removed.append(os.path.basename(path))
            except OSError as e:
                return False, f"could not remove {os.path.basename(path)}: {e}"
        self.reset_profile()
        self.load()
        return True, "cleared " + (", ".join(removed) if removed else "nothing") \
            + " + reset profile.json"

    # ---- phases 2-3: agentic (the documented quarantine exception) ----
    def analyze_phase(self, cancel=None, on_line=None) -> tuple[bool, str]:
        """signals.json -> patterns.json. Deterministic per-lens fan-out + rollup
        (`core.scan`); only the per-lens judgment crosses to the agent. Reloads."""
        ok, msg = scan.analyze(cancel=cancel, on_line=on_line)
        self.load()
        if ok and not self.has("patterns"):
            return False, "analyze finished but patterns.json missing"
        return ok, msg

    def reset_profile(self) -> None:
        """Blank profile.json (keep a .bak) so the report rebuilds from scratch."""
        try:
            if os.path.exists(PROFILE_PATH):
                shutil.copyfile(PROFILE_PATH, PROFILE_PATH + ".bak")
        except OSError:
            pass
        skeleton = {
            "_comment": ("Agent-authored Profile spec — the DYNAMIC content layer. "
                         "Reset to empty by the report phase; build-profile rewrites "
                         "it fresh. Prior version saved as profile.json.bak."),
            "generated": datetime.now(timezone.utc).date().isoformat(),
            "sections": [],
        }
        with open(PROFILE_PATH, "w") as fh:
            json.dump(skeleton, fh, indent=2)

    def report_phase(self, cancel=None, on_line=None) -> tuple[bool, str]:
        """patterns.json -> tui/config/profile.json. Resets the spec to a blank
        skeleton, then `core.scan` composes it fresh and structurally validates."""
        self.reset_profile()
        return scan.report(cancel=cancel, on_line=on_line)
