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

from core import run
from core.mine import SIGNALS_PATH
from core.store.db import REPO_ROOT

PROFILE_PATH = os.path.join(REPO_ROOT, "tui", "config", "profile.json")
PATTERNS_PATH = os.path.join(REPO_ROOT, "patterns.json")
PHASE_TIMEOUT = 1200  # hard cap per agent phase so a stuck run can't hang forever

# source name -> absolute path
SOURCES = {
    "signals": SIGNALS_PATH,        # core.mine (deterministic, phase 1)
    "patterns": PATTERNS_PATH,      # scanner analyze phase (agentic)
}

# The agent runs the per-section fan-out internally (see the scanner /
# build-profile skills); the store just hands it the two prompts at the explicit
# Run action. Phase 1 is in-process Python — no agent.
ANALYZE_PROMPT = (
    "Run the scanner skill's ANALYZE phase. signals.json is already fresh "
    "(do NOT re-run the miner). Read sections.json (the section registry) and the "
    "matching slices of signals.json; fan out one analyst per section to judge "
    "the 90% patterns, then the recommendations rollup. Surface EVERY painpoint "
    "each lens sees — not just forge-able ones: dispose candidates and manual / "
    "no-build habit nudges too. The one bar: every painpoint carries a suggested "
    "solution (a pure observation with nothing to do is a descriptive finding, not "
    "a painpoint). Write patterns.json: a ranked list of forge/dispose/suggest "
    "candidates in the uniform suggestion shape — narrative (name, section, "
    "painpoint, frequency, evidence), fix {approach, tool_type, summary, what, why, "
    "where}, and gate {kind, mechanical_or_craft, payback, confidence}. Set "
    "`section` correctly on each — phase 3 routes painpoints back to their Profile "
    "lens by it. Don't ask questions; write the file."
)
REPORT_PROMPT = (
    "Run the build-profile skill. Read signals.json, sections.json and "
    "patterns.json, and write tui/config/profile.json FRESH (it was reset to an "
    "empty skeleton — build from scratch, do not merge). One Profile section per "
    "registry lens, composed from the fixed components, every section carrying an "
    "explicit id. Each section gets its own `prose` text box (placed first), at "
    "least one data box from signals.json, and — last — a `Painpoints` blocks box "
    "of that lens's painpoints (filter patterns.json by `section`; skip the box if "
    "none). Do NOT write a `forge` Profile section; the full board lives on the "
    "Forge tab. No section may be text-only. Inline values must match the JSON "
    "exactly. Don't ask questions; write the file."
)


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

    # ---- phases 2-3: agentic (the documented quarantine exception) ----
    def analyze_phase(self) -> tuple[bool, str]:
        """signals.json -> patterns.json (one headless agent run). Reloads after."""
        ok, msg = run.headless(ANALYZE_PROMPT, cwd=REPO_ROOT, add_dir=REPO_ROOT,
                               timeout=PHASE_TIMEOUT)
        self.load()
        if ok and not self.has("patterns"):
            return False, "agent finished but patterns.json missing"
        return (ok, "patterns.json written") if ok else (ok, msg)

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

    def report_phase(self) -> tuple[bool, str]:
        """patterns.json -> tui/config/profile.json (one headless agent run)."""
        self.reset_profile()
        ok, msg = run.headless(REPORT_PROMPT, cwd=REPO_ROOT, add_dir=REPO_ROOT,
                               timeout=PHASE_TIMEOUT)
        return (ok, "profile.json rebuilt") if ok else (ok, msg)
