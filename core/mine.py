"""mine — the deterministic orchestrator (phase 1).

Ingests every inspected agent + shell into the normalized stream, runs each
signal section, and writes one `signals.json` keyed by section. No agent is ever
called here (quarantine): this is pure Python the TUI can run in-process every
refresh. The agentic ANALYZE phase reads `signals.json`; it is never re-derived.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from core import agents, ingest
from core.inventory import configs, packages
from core.signals import context, harness, loop, sessions, shell, usage
from core.store.db import REPO_ROOT

SIGNALS_PATH = os.path.join(REPO_ROOT, "signals.json")


def run(out_path: str = SIGNALS_PATH) -> tuple[bool, str]:
    """Compute all signals and write signals.json. Returns (ok, message)."""
    try:
        events = ingest.ingest_events()
        shells = ingest.ingest_shells()
        config_inv = configs.inventory()
        pkg_inv = packages.inventory()

        out = {
            "meta": {
                "generated": datetime.now(tz=timezone.utc).isoformat(),
                "agents_inspected": [m.id for m in agents.to_inspect()],
                "total_events": len(events),
                "package_count": pkg_inv.get("count", 0),
            },
            "usage": usage.compute(events),
            "sessions": sessions.compute(events),
            "loop": loop.compute(events),
            "context": context.compute(events, config_inv),
            "harness": harness.compute(events, config_inv),
            "shell": shell.compute(events, shells, pkg_inv),
        }
        with open(out_path, "w") as f:
            json.dump(out, f, indent=1, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001 - never crash the caller
        return False, f"mine failed: {e}"

    n = out["meta"]["total_events"]
    s = out["usage"]["overview"]["total_sessions"]
    return True, f"mined {n} events across {s} sessions → {os.path.basename(out_path)}"


def main() -> None:
    ok, msg = run()
    print(("OK: " if ok else "ERR: ") + msg)
    if ok:
        with open(SIGNALS_PATH) as f:
            d = json.load(f)
        print("sections:", [k for k in d if k != "meta"])
        print("agents:", d["meta"]["agents_inspected"])
        ba = d["usage"]["by_agent"]
        for a, v in ba.items():
            print(f"  {a}: {v['sessions']} sessions, {v['events']} events")


if __name__ == "__main__":
    main()
