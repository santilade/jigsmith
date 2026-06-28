"""Harness signals — the static rig that shapes every session.

Config inventory (skills/agents/commands/MCP/plugins, global + per project) joined
against what's actually invoked in the Event stream. The join surfaces dead
weight: skills installed but never run, MCP servers configured but never called,
subagents defined but never spawned. "Unused" is window-bounded — reported with
counts so the analyst (judgment) decides dead vs rare-but-load-bearing.
"""
from __future__ import annotations

from collections import Counter


def compute(events, inv: dict) -> dict:
    used_skills, used_mcp, used_agents = Counter(), Counter(), Counter()
    for e in events:
        if e.kind != "tool_call" or not e.tool:
            continue
        if e.tool.kind == "skill":
            used_skills[e.tool.detail.get("skill", "")] += 1
        elif e.tool.kind == "mcp":
            used_mcp[e.tool.detail.get("server", "")] += 1
        elif e.tool.kind == "subagent":
            used_agents[e.tool.detail.get("subagent_type", "")] += 1

    g = inv.get("global", [])
    by_kind = Counter(it["kind"] for it in g)
    n_projects = len(inv.get("projects", {}))
    proj_items = sum(len(v) for v in inv.get("projects", {}).values())

    def installed(kind, scope_items):
        return {it["name"] for it in scope_items if it["kind"] == kind}

    skills_g = installed("skill", g)
    mcp_g = installed("mcp", g)
    agents_g = installed("agent", g)

    # MCP servers are namespaced in tool calls; match loosely by membership
    used_mcp_names = {k for k in used_mcp if k}

    return {
        "inventory_summary": {
            "global": dict(by_kind),
            "projects_with_config": n_projects,
            "project_config_items": proj_items,
            "per_agent": _per_agent(g),
        },
        "join": {
            "skills_installed": len(skills_g),
            "skills_used": len([s for s in skills_g if used_skills.get(s)]),
            "skills_unused": sorted(skills_g - set(k for k in used_skills if used_skills[k])),
            "mcp_installed": len(mcp_g),
            "mcp_unused": sorted(s for s in mcp_g if s not in used_mcp_names),
            "agents_installed": len(agents_g),
            "agents_unused": sorted(a for a in agents_g if not used_agents.get(a)),
            "note": "unused is window-bounded; verify before disposing",
        },
        "most_used": {
            "skills": [{"name": k, "count": v} for k, v in used_skills.most_common(15) if k],
            "subagents": [{"name": k, "count": v} for k, v in used_agents.most_common(15) if k],
            "mcp_servers": [{"name": k, "count": v} for k, v in used_mcp.most_common(15) if k],
        },
    }


def _per_agent(items) -> dict:
    out: dict = {}
    for it in items:
        out.setdefault(it["agent"], Counter())[it["kind"]] += 1
    return {a: dict(c) for a, c in out.items()}
