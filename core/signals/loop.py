"""Loop signals — the inner agentic loop, turn by turn.

Where `sessions` is the MACRO lens (parallel runs, chains, babysitting wall-time
*across* sessions), `loop` is the MICRO lens: what happens *inside* one turn. A
turn opens at a real human prompt and runs until the next one; in between the
agent loops — response + tool_call steps. We measure that loop's depth (steps per
turn), its leash (how far it runs autonomously before re-steered), its tool
grammar (the explore→edit→verify cadence, delegation fan-out), and how often the
human cuts in (interrupts, short re-steers, loop-control commands). Deterministic;
sidechain (sub-agent-internal) events are excluded from the main loop so a swarm
doesn't inflate depth — the parent delegation call is what counts.
"""
from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict

from core.helpers import percentile, utc

QUICK_RESTEER = 45        # s: a human prompt within this of the last response = a cut-in
SHORT_PROMPT = 80         # chars: a re-steer/correction, not a fresh task
_CMD_RE = re.compile(r"<command-name>\s*/?([a-zA-Z][\w-]*)")   # claude slash-command marker
_BARE_CMD_RE = re.compile(r"^/([a-zA-Z][\w-]*)")               # bare "/clear" in prompt text
_INTERRUPT_RE = re.compile(r"\[Request interrupted")


def _stat(vals) -> dict | None:
    if not vals:
        return None
    return {
        "count": len(vals),
        "median": round(statistics.median(vals), 1),
        "mean": round(statistics.mean(vals), 1),
        "p90": round(percentile(vals, 90), 1),
        "max": max(vals),
    }


def _depth_bucket(n: int) -> str:
    for hi, name in [(1, "1"), (5, "2-4"), (10, "5-9"), (20, "10-19")]:
        if n < hi:
            return name
    return "20+"


def _date(ts):
    return utc(ts).strftime("%Y-%m-%d") if ts else "(no ts)"


def compute(events) -> dict:
    # Per-session, time-ordered stream. Sidechain events are sub-agent-internal —
    # excluded from the main loop's depth; the parent `subagent` tool_call counts.
    by_sess: dict[str, list] = defaultdict(list)
    for e in events:
        by_sess[e.session_id].append(e)

    turns: list[dict] = []           # one record per human-opened turn
    resteers = 0                     # quick + short human cut-ins
    interrupts = 0                   # explicit "[Request interrupted"
    loop_cmds: Counter = Counter()   # /clear, /compact, /exit … loop-control verbs

    for sid, evs in by_sess.items():
        evs = sorted(evs, key=lambda e: (e.ts is None, e.ts or 0.0))
        prev_resp_ts = None
        cur: dict | None = None

        for e in evs:
            txt = e.text or ""
            if e.role == "user":
                cmd = _CMD_RE.search(txt) or _BARE_CMD_RE.match(txt.lstrip())
                if cmd:
                    loop_cmds[cmd.group(1).lower()] += 1
                if _INTERRUPT_RE.search(txt):
                    interrupts += 1
                if e.kind == "prompt" and e.is_real_prompt and not e.is_sidechain:
                    # close the previous turn, open a new one
                    if cur is not None:
                        turns.append(cur)
                    if (prev_resp_ts is not None and e.ts is not None
                            and (e.ts - prev_resp_ts) <= QUICK_RESTEER
                            and len(txt.strip()) <= SHORT_PROMPT):
                        resteers += 1
                    cur = {"sid": sid, "start": e.ts, "kinds": [],
                           "tools": 0, "responses": 0, "subagents": 0, "todos": 0}
                continue

            if e.is_sidechain or cur is None:
                continue
            if e.role == "assistant" and e.kind == "response":
                cur["responses"] += 1
                if e.ts is not None:
                    prev_resp_ts = e.ts
            elif e.kind == "tool_call" and e.tool is not None:
                cur["tools"] += 1
                k = e.tool.kind
                cur["kinds"].append(k)
                if k == "subagent":
                    cur["subagents"] += 1
                elif k == "todo":
                    cur["todos"] += 1
        if cur is not None:
            turns.append(cur)

    return {
        "overall": _overall(turns),
        "leash": _leash(turns),
        "cycle": _cycle(turns),
        "resteer": _resteer(turns, resteers, interrupts, loop_cmds),
        "meta": {"quick_resteer_seconds": QUICK_RESTEER,
                 "short_prompt_chars": SHORT_PROMPT,
                 "sidechain_excluded": True},
    }


def _overall(turns) -> dict:
    if not turns:
        return {"total_turns": 0}
    tools = [t["tools"] for t in turns]
    steps = [t["tools"] + t["responses"] for t in turns]
    return {
        "total_turns": len(turns),
        "total_tool_calls": sum(tools),
        "total_agent_responses": sum(t["responses"] for t in turns),
        "turns_with_tools": sum(1 for t in turns if t["tools"]),
        "turns_chat_only": sum(1 for t in turns if not t["tools"]),
        "tool_calls_per_turn": _stat(tools),
        "agent_steps_per_turn": _stat(steps),
    }


def _leash(turns) -> dict:
    """How far the agent runs on one human prompt before being re-steered."""
    buckets: Counter = Counter()
    for t in turns:
        buckets[_depth_bucket(t["tools"])] += 1
    order = ["1", "2-4", "5-9", "10-19", "20+"]
    longest = sorted(turns, key=lambda t: t["tools"], reverse=True)[:10]
    # No wall-duration here on purpose: a turn can span a long idle gap before the
    # next human prompt, so raw duration misleads. tool_calls is the honest leash.
    longest_out = [{
        "date": _date(t["start"]),
        "tool_calls": t["tools"],
        "agent_steps": t["tools"] + t["responses"],
        "subagents": t["subagents"],
    } for t in longest if t["tools"]]
    return {
        "tool_depth_buckets": {k: buckets.get(k, 0) for k in order if buckets.get(k)},
        "longest_autonomous_turns": longest_out,
    }


def _cycle(turns) -> dict:
    """The loop's tool grammar: which kinds, and the transitions between them —
    edit→bash is verify-after-change; read/search→edit is explore-then-act."""
    kind_totals: Counter = Counter()
    bigrams: Counter = Counter()
    verify = explore_act = 0
    for t in turns:
        seq = t["kinds"]
        kind_totals.update(seq)
        for a, b in zip(seq, seq[1:]):
            bigrams[f"{a}→{b}"] += 1
            if a in ("edit", "write") and b == "bash":
                verify += 1
            if a in ("read", "search") and b in ("edit", "write"):
                explore_act += 1
    return {
        "tool_kind_totals": dict(kind_totals.most_common()),
        "top_transitions": [{"pair": k, "count": v}
                            for k, v in bigrams.most_common(15)],
        "verify_after_change": verify,            # edit/write → bash
        "explore_then_act": explore_act,          # read/search → edit/write
        "delegation_turns": sum(1 for t in turns if t["subagents"]),
        "total_subagent_calls": sum(t["subagents"] for t in turns),
        "max_fanout_in_turn": max((t["subagents"] for t in turns), default=0),
        "planning_turns": sum(1 for t in turns if t["todos"]),
    }


def _resteer(turns, resteers, interrupts, loop_cmds) -> dict:
    n = len(turns) or 1
    return {
        "quick_short_resteers": resteers,
        "pct_turns_resteered": round(100 * resteers / n, 1),
        "interrupts": interrupts,
        "loop_control_commands": dict(loop_cmds.most_common()),
    }
