"""AgentManifest — the data shape that declares one inspectable/runnable agent.

A manifest carries two independent capabilities (see ARCHITECTURE.md):
  - RUN     (default agent only): headless + interactive argv templates.
  - INSPECT (agents to inspect):  history location + format + settings paths.

Built-ins ship as JSON under `builtin/`; user/skill-registered agents live under
~/.config/jigsmith/agents/*.json. Same shape, one code path. Deterministic —
this only reads PATH, resolves globs, and substitutes argv templates.
"""
from __future__ import annotations

import glob
import os
import shutil
from dataclasses import dataclass, field


def _expand(p: str) -> str:
    return os.path.expanduser(os.path.expandvars(p))


@dataclass
class AgentManifest:
    id: str
    label: str = ""
    tag: str = ""
    cli: str = ""
    run: dict = field(default_factory=dict)        # {headless:[...], interactive:[...]}
    inspect: dict = field(default_factory=dict)    # {history:{glob,format}, settings:{...}}

    @classmethod
    def from_dict(cls, d: dict) -> "AgentManifest":
        return cls(id=d["id"], label=d.get("label", d["id"]),
                   tag=d.get("tag", d["id"][:2]), cli=d.get("cli", ""),
                   run=d.get("run", {}) or {}, inspect=d.get("inspect", {}) or {})

    # ---- availability ------------------------------------------------------
    def installed(self) -> bool:
        """True if the agent's CLI is on PATH (regardless of run/inspect support)."""
        return bool(self.cli) and shutil.which(self.cli) is not None

    # ---- RUN role ----------------------------------------------------------
    def can_run(self) -> bool:
        return self.installed() and bool(self.run.get("headless"))

    def _argv(self, template: list[str] | None, subs: dict) -> list[str] | None:
        if not template:
            return None
        out: list[str] = []
        for tok in template:
            filled = tok
            for k, v in subs.items():
                filled = filled.replace("{" + k + "}", str(v))
            # drop tokens whose only content was an unfilled placeholder
            if filled == "" and "{" in tok:
                continue
            out.append(filled)
        return out

    def headless_argv(self, prompt: str, *, cwd: str, add_dir: str,
                      timeout: int) -> list[str] | None:
        return self._argv(self.run.get("headless"),
                          {"prompt": prompt, "cwd": cwd, "add_dir": add_dir,
                           "timeout": timeout})

    def headless_stream_argv(self, prompt: str, *, cwd: str, add_dir: str,
                             timeout: int) -> list[str] | None:
        """Streaming variant — emits per-step events for live tailing. Optional;
        only the default agent declares `run.headless_stream`. None → no stream."""
        return self._argv(self.run.get("headless_stream"),
                          {"prompt": prompt, "cwd": cwd, "add_dir": add_dir,
                           "timeout": timeout})

    def stream_format(self) -> str:
        """Event format emitted by the streaming runner (keys run.py's parser)."""
        return self.run.get("stream_format", "")

    def interactive_argv(self, prompt: str | None = None, *,
                         add_dir: str = "") -> list[str] | None:
        return self._argv(self.run.get("interactive"),
                          {"prompt": prompt or "", "add_dir": add_dir})

    # ---- INSPECT role ------------------------------------------------------
    def history_format(self) -> str:
        return (self.inspect.get("history") or {}).get("format", "")

    def history_paths(self) -> list[str]:
        g = (self.inspect.get("history") or {}).get("glob", "")
        return sorted(glob.glob(_expand(g), recursive=True)) if g else []

    def settings_paths(self) -> dict:
        return {k: _expand(v) for k, v in (self.inspect.get("settings") or {}).items()}

    def can_inspect(self) -> bool:
        from core.parsers import has_parser
        return bool(self.history_paths()) and has_parser(self.history_format())
