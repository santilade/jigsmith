"""The normalized cross-agent event vocabulary.

Every parser (Claude, codex/openai, opencode, shells) emits these shapes, so all
downstream signal code is agent-agnostic. See ARCHITECTURE.md §Layer 1.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Normalized tool taxonomy. Each agent names tools differently; parsers map raw
# names onto these so cross-agent comparison (Edit/codex-edit/oc-edit → "edit")
# works. "other" is the safe fallback — never drop a tool_use, just bucket it.
TOOL_KINDS = {"read", "edit", "write", "search", "bash", "web",
              "subagent", "skill", "mcp", "todo", "other"}


@dataclass
class ToolCall:
    raw_name: str                       # e.g. "Edit", "Bash", "Skill", "Task"
    kind: str = "other"                 # one of TOOL_KINDS
    summary: str = ""
    detail: dict = field(default_factory=dict)
    #   bash → {command, verb, git_sub}; skill → {skill};
    #   subagent → {subagent_type}; mcp → {server, tool}


@dataclass
class Event:
    session_id: str
    agent: str
    ts: float | None                    # epoch UTC
    role: str = "user"                  # user | assistant | system
    kind: str = "prompt"               # prompt | response | tool_call | summary | meta
    text: str = ""
    is_real_prompt: bool = False
    is_sidechain: bool = False
    tokens: dict = field(default_factory=dict)   # in,out,cache_create,cache_read
    model: str = ""
    tool: ToolCall | None = None
    project: str = "(unknown)"
    raw_project: str = "(unknown)"
    cwd: str = ""
    git_branch: str = ""


@dataclass
class Session:
    id: str
    agent: str
    project: str = "(unknown)"
    raw_project: str = "(unknown)"
    cwd: str = ""
    start: float | None = None
    end: float | None = None
    models: list = field(default_factory=list)
    entrypoint: str = ""
    git_branches: list = field(default_factory=list)


@dataclass
class ShellCmd:
    ts: float | None
    shell: str                          # zsh | bash | fish
    verb: str = ""
    command: str = ""                   # scrubbed + truncated, safe to emit
    reliable: bool = True               # ts trustworthy (see dominant-bulk filter)


def sessions_from_events(events: list[Event]) -> dict[str, Session]:
    """Fold an event stream into per-session summaries (dominant cwd wins)."""
    from collections import Counter, defaultdict
    cwds: dict[str, Counter] = defaultdict(Counter)
    sess: dict[str, Session] = {}
    for e in events:
        s = sess.get(e.session_id)
        if s is None:
            s = sess[e.session_id] = Session(id=e.session_id, agent=e.agent)
        if e.cwd:
            cwds[e.session_id][e.cwd] += 1
        if e.ts is not None:
            s.start = e.ts if s.start is None else min(s.start, e.ts)
            s.end = e.ts if s.end is None else max(s.end, e.ts)
        if e.model and e.model not in s.models:
            s.models.append(e.model)
        if e.git_branch and e.git_branch not in s.git_branches:
            s.git_branches.append(e.git_branch)
        if e.kind == "meta" and e.text and not s.entrypoint:
            s.entrypoint = e.text
    from core.helpers import normalize_project, raw_project
    for sid, s in sess.items():
        dom = cwds[sid].most_common(1)
        s.cwd = dom[0][0] if dom else ""
        s.project = normalize_project(s.cwd)
        s.raw_project = raw_project(s.cwd)
    return sess
