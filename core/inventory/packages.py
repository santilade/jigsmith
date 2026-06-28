"""Package inventory — what CLI tools are INSTALLED (read-only).

The second input to the Shell section's join: the user-facing tools you chose to
install, paired with the verbs you actually run. Surfaces installed+unused
("lazygit sits idle") and used+suboptimal ("raw git daily, lazygit available").

Uses CHOSEN tools (`brew leaves`, top-level `npm -g`, `pipx list`), never the
dependency closure — otherwise the signal drowns in transitive libs. Defensive:
a missing package manager just contributes nothing.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess


def _run(argv: list[str], timeout: int = 8) -> str:
    binary = shutil.which(argv[0])
    if not binary:
        return ""
    try:
        p = subprocess.run([binary, *argv[1:]], capture_output=True, text=True,
                           timeout=timeout)
        return p.stdout if p.returncode == 0 else ""
    except Exception:
        return ""


def _brew_leaves() -> list[str]:
    return [l.strip() for l in _run(["brew", "leaves"]).splitlines() if l.strip()]


def _npm_global() -> list[str]:
    out = _run(["npm", "ls", "-g", "--depth=0", "--json"])
    try:
        deps = json.loads(out).get("dependencies", {}) if out else {}
        return sorted(deps.keys())
    except Exception:
        return []


def _pipx() -> list[str]:
    out = _run(["pipx", "list", "--json"])
    try:
        return sorted((json.loads(out).get("venvs", {}) if out else {}).keys())
    except Exception:
        return []


def inventory() -> dict:
    """{tools:[{name,source}], path_bins:[...]} — chosen, user-facing tools."""
    tools: list[dict] = []
    for name in _brew_leaves():
        tools.append({"name": name, "source": "brew"})
    for name in _npm_global():
        tools.append({"name": name.split("/")[-1], "source": "npm-g"})
    for name in _pipx():
        tools.append({"name": name, "source": "pipx"})
    # de-dup by name, first source wins
    seen, uniq = set(), []
    for t in tools:
        if t["name"] not in seen:
            seen.add(t["name"])
            uniq.append(t)
    return {"tools": uniq, "count": len(uniq)}
