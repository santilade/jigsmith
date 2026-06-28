"""Config inventory — what agent configs are INSTALLED (read-only).

The second input to the Harness section's `inventory ⋈ usage` join: skills,
agents, commands, output-styles, MCP servers, plugins, memory files — global and
per-project, per inspected agent. Pairs with usage (what's actually invoked) to
find dead config (installed+unused) vs load-bearing.

Read-only. This is the surviving *read* half of the removed workbench scanner —
no deploy/undeploy, just discovery for analysis.
"""
from __future__ import annotations

import json
import os

from core import agents

# settings-key -> inventory kind, for dir-listing kinds
_DIR_KINDS = {"skills": "skill", "agents": "agent", "commands": "command",
              "output_styles": "output-style"}


def _read_json(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _desc(path: str) -> str:
    try:
        with open(path, errors="ignore") as f:
            head = [next(f, "") for _ in range(40)]
    except Exception:
        return ""
    for line in head:
        s = line.strip()
        if s.lower().startswith("description:"):
            return s.split(":", 1)[1].strip().strip('"\'')[:120]
    return ""


def _entries(d: str) -> list[str]:
    try:
        return sorted(n for n in os.listdir(d) if not n.startswith("."))
    except Exception:
        return []


def _scan_dir(items, agent, scope, kind, directory):
    if not os.path.isdir(directory):
        return
    for name in _entries(directory):
        full = os.path.join(directory, name)
        disp = name[:-3] if name.endswith(".md") else name
        detail = _desc(os.path.join(full, "SKILL.md")) if os.path.isdir(full) else _desc(full)
        items.append({"agent": agent, "scope": scope, "kind": kind, "name": disp,
                      "path": full, "detail": detail,
                      "mtime": _mtime(full)})


def _mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def _scan_agent(agent_id: str, settings: dict, scope: str, items: list) -> None:
    for key, kind in _DIR_KINDS.items():
        if key in settings:
            _scan_dir(items, agent_id, scope, kind, settings[key])
    mem = settings.get("memory")
    if mem and os.path.isfile(mem):
        items.append({"agent": agent_id, "scope": scope, "kind": "memory",
                      "name": os.path.basename(mem), "path": mem,
                      "detail": f"{os.path.getsize(mem)} bytes",
                      "size": os.path.getsize(mem), "mtime": _mtime(mem)})
    mcp_file = settings.get("mcp")
    if mcp_file and os.path.isfile(mcp_file):
        cfg = _read_json(mcp_file)
        servers = cfg.get("mcpServers") or cfg.get("mcp") or {}
        for name, sc in (servers or {}).items():
            items.append({"agent": agent_id, "scope": scope, "kind": "mcp",
                          "name": name, "path": mcp_file,
                          "detail": _mcp_detail(sc), "mtime": _mtime(mcp_file)})
    conf = settings.get("config")
    if conf and os.path.isfile(conf):
        sc = _read_json(conf)
        for name, on in (sc.get("enabledPlugins") or {}).items():
            items.append({"agent": agent_id, "scope": scope, "kind": "plugin",
                          "name": name, "path": conf,
                          "detail": "enabled" if on else "disabled", "mtime": _mtime(conf)})


def _mcp_detail(cfg) -> str:
    if not isinstance(cfg, dict):
        return ""
    if cfg.get("command"):
        c = cfg["command"]
        return f"{cfg.get('type', 'stdio')}: {' '.join(c) if isinstance(c, list) else c}"[:120]
    if cfg.get("url"):
        return f"{cfg.get('type', 'http')}: {cfg['url']}"[:120]
    return cfg.get("type", "")


def inventory() -> dict:
    """{global:[items], projects:{path:[items]}} across inspected agents."""
    glob_items: list = []
    for m in agents.to_inspect():
        _scan_agent(m.id, m.settings_paths(), "global", glob_items)

    projects: dict = {}
    cj = _read_json(os.path.expanduser("~/.claude.json"))
    for path in (cj.get("projects") or {}):
        if not os.path.isdir(path):
            continue
        cdir = os.path.join(path, ".claude")
        items: list = []
        _scan_agent("claude", {
            "skills": os.path.join(cdir, "skills"),
            "agents": os.path.join(cdir, "agents"),
            "commands": os.path.join(cdir, "commands"),
            "memory": os.path.join(path, "CLAUDE.md"),
            "mcp": os.path.join(path, ".mcp.json"),
        }, path, items)
        if items:
            projects[path] = items
    return {"global": glob_items, "projects": projects}
