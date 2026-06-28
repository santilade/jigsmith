"""Parser for opencode's SQLite session store (`~/.local/share/opencode/opencode.db`).

Recent opencode versions migrated their on-disk JSON store into SQLite. Three
tables matter: `session` (directory, metadata), `message` (one row per turn, JSON
in `data` with role/model/tokens/time), and `part` (the turn's content fragments,
JSON in `data`: `text` and `tool` types). A message's text is the concatenation of
its text parts; each tool part becomes one tool_call Event.

Opened read-only/immutable so a live opencode process never blocks the miner. A
bad row is skipped, never fatal. For the older JSON-file layout see
`opencode_store.py`.
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from collections.abc import Iterable

from core.events import Event, ToolCall
from core.helpers import (git_subcommand, is_real_prompt, normalize_project,
                          raw_project, scrub, verb as bash_verb)
from core.parsers import register

# opencode builtin tool name -> normalized kind. Anything not here is treated as
# an MCP tool (opencode names those `<server>_<tool>`).
_KIND = {
    "read": "read", "edit": "edit", "multiedit": "edit", "patch": "edit",
    "write": "write", "grep": "search", "glob": "search", "list": "search",
    "bash": "bash", "webfetch": "web", "task": "subagent", "agent": "subagent",
    "skill": "skill", "todowrite": "todo", "todoread": "todo",
    "lsp": "other", "question": "other", "invalid": "other",
}


def _ms(v):
    if isinstance(v, (int, float)):
        return float(v) / (1000.0 if v > 1e12 else 1.0)
    return None


def _tool_call(name: str, inp: dict) -> ToolCall:
    name = name or "(unknown)"
    inp = inp if isinstance(inp, dict) else {}
    kind = _KIND.get(name.lower())
    detail: dict = {}
    summary = ""
    if kind is None:  # not a builtin -> MCP tool, named <server>_<tool>
        kind = "mcp"
        server, _, tool = name.partition("_")
        detail = {"server": server, "tool": tool}
        summary = f"{server}:{tool}" if tool else server
    elif kind == "bash":
        cmd = inp.get("command") if isinstance(inp.get("command"), str) else ""
        detail = {"command": scrub(cmd), "verb": bash_verb(cmd) or "",
                  "git_sub": git_subcommand(cmd) or ""}
        summary = detail["command"]
    elif kind == "skill":
        detail = {"skill": inp.get("name") or inp.get("skill") or "(unknown)"}
        summary = detail["skill"]
    elif kind == "subagent":
        detail = {"subagent_type": inp.get("subagentType") or inp.get("agent")
                  or inp.get("description") or "(unknown)"}
        summary = detail["subagent_type"]
    return ToolCall(raw_name=name, kind=kind, summary=summary, detail=detail)


@register("opencode-db")
def parse(paths: list[str], agent_id: str) -> Iterable[Event]:
    for path in paths:
        try:
            con = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
        except Exception:
            continue
        try:
            yield from _records(con, agent_id)
        except Exception:
            continue
        finally:
            con.close()


def _records(con: sqlite3.Connection, agent_id: str) -> Iterable[Event]:
    dirs = {sid: d for sid, d in con.execute("SELECT id, directory FROM session")}

    # parts grouped by message, in on-disk order
    parts: dict[str, list[dict]] = defaultdict(list)
    for mid, data in con.execute(
            "SELECT message_id, data FROM part ORDER BY time_created, id"):
        try:
            parts[mid].append(json.loads(data))
        except Exception:
            continue

    for mid, sid, data in con.execute(
            "SELECT id, session_id, data FROM message ORDER BY time_created, id"):
        try:
            m = json.loads(data)
        except Exception:
            continue
        role = m.get("role") or ""
        if role not in ("user", "assistant"):
            continue
        cwd = ((m.get("path") or {}).get("cwd")) or dirs.get(sid, "") or ""
        ts = _ms((m.get("time") or {}).get("created"))
        model = m.get("modelID") or (m.get("model") or {}).get("modelID") or ""
        mp = parts.get(mid, [])
        text = "\n".join(p["text"] for p in mp
                         if p.get("type") == "text" and isinstance(p.get("text"), str))
        common = dict(session_id=sid, agent=agent_id, ts=ts,
                      project=normalize_project(cwd), raw_project=raw_project(cwd),
                      cwd=cwd, model=model)

        if role == "user":
            yield Event(role="user", kind="prompt", text=text,
                        is_real_prompt=is_real_prompt(text), **common)
            continue

        tok = m.get("tokens") or {}
        cache = tok.get("cache") or {}
        yield Event(role="assistant", kind="response", text=text,
                    tokens={"in": tok.get("input", 0) or 0,
                            "out": tok.get("output", 0) or 0,
                            "cache_create": cache.get("write", 0) or 0,
                            "cache_read": cache.get("read", 0) or 0},
                    **common)
        for p in mp:
            if p.get("type") != "tool":
                continue
            state = p.get("state") if isinstance(p.get("state"), dict) else {}
            inp = state.get("input") if isinstance(state.get("input"), dict) else p.get("input")
            yield Event(role="assistant", kind="tool_call",
                        tool=_tool_call(p.get("tool") or p.get("name") or "", inp or {}),
                        **common)
