"""Parser for OpenAI-style message JSONL — Codex CLI and most newer agents.

Codex session rollouts (`~/.codex/sessions/**/rollout-*.jsonl`) and similar tools
write one JSON record per line in an OpenAI-ish message shape. Versions vary, so
this parser is deliberately tolerant: it extracts role + text + function/tool
calls from whatever common fields are present and skips anything it can't read.

No Codex history exists on the dev machine yet, so this is validated structurally
only — refine against real rollouts (or let `register-agent` write a tighter
parser) when the data appears.
"""
from __future__ import annotations

import json
import os
from collections.abc import Iterable

from core.events import Event, ToolCall
from core.helpers import epoch, normalize_project, raw_project, scrub, verb as bash_verb
from core.parsers import register

_TEXT_TYPES = {"text", "input_text", "output_text", "summary_text"}


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") in _TEXT_TYPES)
    return ""


def _ts(r: dict):
    for k in ("timestamp", "ts", "created_at", "time"):
        v = r.get(k)
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            e = epoch(v)
            if e is not None:
                return e
    return None


def _tool(name: str, args) -> ToolCall:
    low = (name or "").lower()
    if low in ("bash", "shell", "exec", "run", "local_shell"):
        cmd = ""
        if isinstance(args, dict):
            cmd = args.get("command") or args.get("cmd") or ""
            if isinstance(cmd, list):
                cmd = " ".join(map(str, cmd))
        return ToolCall(raw_name=name, kind="bash",
                        summary=scrub(cmd),
                        detail={"command": scrub(cmd), "verb": bash_verb(cmd) or ""})
    kind = {"read_file": "read", "write_file": "write", "edit": "edit",
            "apply_patch": "edit", "search": "search", "grep": "search",
            "web_search": "web"}.get(low, "other")
    return ToolCall(raw_name=name or "(unknown)", kind=kind)


@register("openai-jsonl")
def parse(paths: list[str], agent_id: str) -> Iterable[Event]:
    for path in paths:
        sid = os.path.splitext(os.path.basename(path))[0]
        cwd = ""
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
                # session meta lines sometimes carry cwd / id
                cwd = r.get("cwd") or r.get("cwd_path") or cwd
                sid = r.get("session_id") or r.get("id") or sid
                yield from _record(r, agent_id, sid, cwd)


def _record(r: dict, agent_id: str, sid: str, cwd: str) -> Iterable[Event]:
    typ = r.get("type") or ""
    msg = r.get("message") if isinstance(r.get("message"), dict) else r
    role = msg.get("role") or r.get("role") or ""
    ts = _ts(r)
    common = dict(session_id=sid, agent=agent_id, ts=ts,
                  project=normalize_project(cwd), raw_project=raw_project(cwd), cwd=cwd)

    if typ in ("function_call", "tool_use", "tool_call") or r.get("function_call"):
        fc = r.get("function_call") or r
        name = fc.get("name") or msg.get("name") or ""
        args = fc.get("arguments") or fc.get("input") or msg.get("input")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                pass
        yield Event(role="assistant", kind="tool_call", tool=_tool(name, args), **common)
        return

    if role in ("user", "assistant", "system"):
        txt = _text(msg.get("content"))
        if role == "user":
            yield Event(role="user", kind="prompt", text=txt,
                        is_real_prompt=bool(txt.strip()), **common)
        else:
            yield Event(role=role, kind="response", text=txt, **common)
