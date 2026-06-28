"""Context signals — what enters the model's window each session (dynamic).

Distinct from Harness (the static rig): this is what actually loads into context.
Memory-file weight, repeated prompt preambles (re-explaining the same setup every
session → a memory/skill candidate), and MCP surface configured vs actually
exercised (dead surface still costs tokens every turn). Deterministic.
"""
from __future__ import annotations

import re
from collections import Counter


def compute(events, inv: dict) -> dict:
    # --- memory weight (from the config inventory's memory items) ---
    memory = []
    for it in inv.get("global", []):
        if it["kind"] == "memory" and "size" in it:
            memory.append({"agent": it["agent"], "name": it["name"],
                           "bytes": it["size"], "scope": "global"})
    for path, items in inv.get("projects", {}).items():
        for it in items:
            if it["kind"] == "memory" and "size" in it:
                memory.append({"agent": it["agent"], "name": it["name"],
                               "bytes": it["size"], "scope": path})
    memory.sort(key=lambda m: m["bytes"], reverse=True)

    # --- repeated prompt preambles (re-explaining) ---
    heads = Counter()
    for e in events:
        if e.role == "user" and e.kind == "prompt" and e.is_real_prompt:
            txt = re.sub(r"\s+", " ", (e.text or "").strip())
            if len(txt) >= 80:
                heads[txt[:100]] += 1
    preambles = [{"preamble": k, "repeats": v} for k, v in heads.most_common(10)
                 if v >= 2]

    # --- MCP surface configured vs exercised ---
    configured = {it["name"] for it in inv.get("global", []) if it["kind"] == "mcp"}
    exercised = {e.tool.detail.get("server", "") for e in events
                 if e.kind == "tool_call" and e.tool and e.tool.kind == "mcp"}
    exercised.discard("")

    return {
        "memory_files": memory[:20],
        "memory_total_bytes": sum(m["bytes"] for m in memory),
        "repeated_preambles": preambles,
        "mcp_surface": {
            "configured": len(configured),
            "exercised": len(configured & exercised),
            "never_exercised": sorted(configured - exercised),
            "note": "configured-but-never-called MCP servers burn context every turn",
        },
    }
