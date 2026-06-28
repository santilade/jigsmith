"""Parser for opencode's on-disk session store.

opencode keeps sessions under ~/.local/share/opencode/storage/ as JSON files
(message parts + session metadata). The exact layout shifts between versions, so
this parser is tolerant: it reads each JSON file, pulls role + text + tool parts
where present, and skips the rest. On the dev machine opencode has only a log dir
(no sessions yet), so this is structurally validated only — tighten when real
sessions exist.
"""
from __future__ import annotations

import json
import os
from collections.abc import Iterable

from core.events import Event, ToolCall
from core.helpers import epoch, normalize_project, raw_project, scrub, verb as bash_verb
from core.parsers import register


def _text(parts) -> str:
    if isinstance(parts, str):
        return parts
    if isinstance(parts, list):
        out = []
        for p in parts:
            if isinstance(p, dict) and p.get("type") in ("text", None) and p.get("text"):
                out.append(p["text"])
        return "\n".join(out)
    return ""


def _ts(r: dict):
    for k in ("time", "timestamp", "created", "created_at"):
        v = r.get(k)
        if isinstance(v, dict):
            v = v.get("created") or v.get("start")
        if isinstance(v, (int, float)):
            return float(v) / (1000.0 if v > 1e12 else 1.0)
        if isinstance(v, str):
            e = epoch(v)
            if e is not None:
                return e
    return None


@register("opencode-store")
def parse(paths: list[str], agent_id: str) -> Iterable[Event]:
    for path in paths:
        try:
            with open(path, "r", errors="replace") as f:
                r = json.load(f)
        except Exception:
            continue
        if not isinstance(r, dict):
            continue
        sid = r.get("sessionID") or r.get("sessionId") or r.get("session_id") \
            or os.path.basename(os.path.dirname(path)) or "?"
        cwd = r.get("cwd") or r.get("directory") or ""
        role = r.get("role") or ""
        ts = _ts(r)
        common = dict(session_id=sid, agent=agent_id, ts=ts,
                      project=normalize_project(cwd), raw_project=raw_project(cwd),
                      cwd=cwd)
        parts = r.get("parts") or r.get("content")
        if role == "user":
            txt = _text(parts)
            yield Event(role="user", kind="prompt", text=txt,
                        is_real_prompt=bool(txt.strip()), **common)
        elif role == "assistant":
            yield Event(role="assistant", kind="response", text=_text(parts), **common)
            for p in (parts if isinstance(parts, list) else []):
                if isinstance(p, dict) and p.get("type") in ("tool", "tool_use", "tool-invocation"):
                    name = p.get("tool") or p.get("name") or ""
                    args = p.get("state", {}).get("input") if isinstance(p.get("state"), dict) else p.get("input")
                    cmd = (args or {}).get("command", "") if isinstance(args, dict) else ""
                    kind = "bash" if "bash" in name.lower() or "shell" in name.lower() else "other"
                    yield Event(role="assistant", kind="tool_call",
                                tool=ToolCall(raw_name=name, kind=kind,
                                              summary=scrub(cmd),
                                              detail={"command": scrub(cmd),
                                                      "verb": bash_verb(cmd) or ""} if cmd else {}),
                                **common)
