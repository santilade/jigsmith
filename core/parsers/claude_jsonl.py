"""Parser for Claude Code's session transcripts (`~/.claude/projects/*/*.jsonl`).

One JSON object per line. Record types: user, assistant, system, summary,
ai-title. Emits the normalized Event stream. Defensive: a bad line is skipped,
never fatal. This is the reference parser — the richest source.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable

from core.events import Event, ToolCall
from core.helpers import (epoch, get_text, git_subcommand, is_real_prompt,
                          normalize_project, raw_project, scrub, verb as bash_verb)
from core.parsers import register

# Claude tool name -> normalized kind
_KIND = {
    "Read": "read", "Edit": "edit", "MultiEdit": "edit", "NotebookEdit": "edit",
    "Write": "write", "Grep": "search", "Glob": "search",
    "Bash": "bash", "BashOutput": "bash", "KillShell": "bash", "KillBash": "bash",
    "WebFetch": "web", "WebSearch": "web", "Task": "subagent", "Agent": "subagent",
    "Skill": "skill", "TodoWrite": "todo",
}
_CMD_TAG = re.compile(r"\s*<command-name>\s*(/[^<\s]+)")


def _tool_kind(name: str) -> str:
    if name in _KIND:
        return _KIND[name]
    if name.startswith("mcp__"):
        return "mcp"
    return "other"


def _tool_call(block: dict) -> ToolCall:
    name = block.get("name") or "(unknown)"
    inp = block.get("input") or {}
    kind = _tool_kind(name)
    detail: dict = {}
    summary = ""
    if kind == "bash":
        cmd = inp.get("command") if isinstance(inp.get("command"), str) else ""
        detail = {"command": scrub(cmd), "verb": bash_verb(cmd) or "",
                  "git_sub": git_subcommand(cmd) or ""}
        summary = detail["command"]
    elif kind == "skill":
        detail = {"skill": inp.get("skill") or inp.get("command") or "(unknown)"}
        summary = detail["skill"]
    elif kind == "subagent":
        detail = {"subagent_type": inp.get("subagent_type") or "(unknown)"}
        summary = detail["subagent_type"]
    elif kind == "mcp":
        parts = name.split("__")
        detail = {"server": parts[1] if len(parts) > 1 else "",
                  "tool": parts[2] if len(parts) > 2 else ""}
        summary = f"{detail['server']}:{detail['tool']}"
    return ToolCall(raw_name=name, kind=kind, summary=summary, detail=detail)


@register("claude-jsonl")
def parse(paths: list[str], agent_id: str) -> Iterable[Event]:
    for path in paths:
        try:
            fh = open(path, "r", errors="replace")
        except Exception:
            continue
        with fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                yield from _records(r, agent_id)


def _records(r: dict, agent_id: str) -> Iterable[Event]:
    t = r.get("type")
    if t == "summary":
        s = r.get("summary")
        if isinstance(s, str) and s.strip() and not s.startswith("API Error"):
            yield Event(session_id=r.get("sessionId") or "", agent=agent_id,
                        ts=None, role="system", kind="summary", text=s.strip()[:160])
        return
    if t == "ai-title":
        s = r.get("aiTitle")
        if isinstance(s, str) and s.strip():
            yield Event(session_id=r.get("sessionId") or "", agent=agent_id,
                        ts=None, role="system", kind="summary", text=s.strip()[:160])
        return
    if t not in ("user", "assistant", "system"):
        return

    sid = r.get("sessionId") or ""
    cwd = r.get("cwd") or ""
    ts = epoch(r.get("timestamp"))
    branch = r.get("gitBranch") or ""
    proj, rawp = normalize_project(cwd), raw_project(cwd)
    msg = r.get("message") or {}
    content = msg.get("content")

    common = dict(session_id=sid, agent=agent_id, ts=ts, project=proj,
                  raw_project=rawp, cwd=cwd, git_branch=branch,
                  is_sidechain=bool(r.get("isSidechain")))

    if t == "system":
        yield Event(role="system", kind="meta", text=r.get("entrypoint") or "",
                    **common)
        return

    if t == "user":
        txt = get_text(content)
        only_tool = False
        if isinstance(content, list):
            types = {b.get("type") for b in content if isinstance(b, dict)}
            only_tool = bool(types) and types.issubset({"tool_result", "image"})
        yield Event(role="user", kind="prompt", text=txt,
                    is_real_prompt=is_real_prompt(txt, is_meta=bool(r.get("isMeta")),
                                                  only_tool_result=only_tool),
                    **common)
        return

    # assistant: one response event (tokens/model/text) + one per tool_use
    usage = msg.get("usage") or {}
    yield Event(role="assistant", kind="response", text=get_text(content),
                model=msg.get("model") or "",
                tokens={"in": usage.get("input_tokens", 0) or 0,
                        "out": usage.get("output_tokens", 0) or 0,
                        "cache_create": usage.get("cache_creation_input_tokens", 0) or 0,
                        "cache_read": usage.get("cache_read_input_tokens", 0) or 0},
                **common)
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                yield Event(role="assistant", kind="tool_call",
                            tool=_tool_call(b), model=msg.get("model") or "",
                            **common)
