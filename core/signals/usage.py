"""Usage signals — the what/when/how-much lens.

Ports the old aggregates.json catalog onto the Event stream, and adds the
cross-agent breakdown (sessions/tokens/tools per agent) — the multi-agent
headline. Pure function of the event stream; deterministic.
"""
from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict

from core.events import sessions_from_events
from core.helpers import dist, top, utc

_SLASH = re.compile(r"(?:^|\s)(/[a-zA-Z][\w:-]*)")
_CMD_TAG = re.compile(r"\s*<command-name>\s*(/[^<\s]+)")
_DOW = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_BUCKETS = [(1, "<1min"), (5, "1-5min"), (15, "5-15min"), (30, "15-30min"),
            (60, "30-60min"), (120, "1-2hr"), (240, "2-4hr"), (1e9, ">4hr")]


def _bucket(mins: float) -> str:
    for hi, name in _BUCKETS:
        if mins < hi:
            return name
    return ">4hr"


def compute(events) -> dict:
    sessions = sessions_from_events(events)

    user_n = asst_n = sidechain = real_prompts = slash_prompts = 0
    tool_freq, kind_freq, skill_freq, subagent_freq = (Counter() for _ in range(4))
    model_freq, first_word, slash_in, cmd_tags = (Counter() for _ in range(4))
    hour, dow = Counter(), Counter()
    prompt_lengths: list[int] = []
    intents: list[str] = []
    seen_intents: set = set()
    quotes: list[dict] = []
    quote_projs: Counter = Counter()
    by_agent = defaultdict(lambda: {"sessions": set(), "events": 0, "tokens": 0,
                                     "tools": Counter()})
    proj = defaultdict(lambda: {"sessions": set(), "user_msgs": 0, "asst_msgs": 0,
                                "in": 0, "out": 0, "cache_create": 0, "cache_read": 0,
                                "first": None, "last": None, "branches": set(),
                                "tools": Counter(), "agents": set()})
    ts_min = ts_max = None

    for e in events:
        A = by_agent[e.agent]
        A["events"] += 1
        if e.session_id:
            A["sessions"].add(e.session_id)
        # Summary records carry no cwd → "(unknown)"; folding them into
        # per_project would double-count every real session that has a
        # summary line into a phantom "(unknown)" bucket. Skip the join
        # (summaries still feed intents/temporal below; they just don't
        # carry a project).
        P = proj[e.project] if e.kind != "summary" else None
        if P is not None:
            if e.session_id:
                P["sessions"].add(e.session_id)
            if e.agent:
                P["agents"].add(e.agent)
            if e.git_branch:
                P["branches"].add(e.git_branch)
        if e.ts is not None:
            ts_min = e.ts if ts_min is None else min(ts_min, e.ts)
            ts_max = e.ts if ts_max is None else max(ts_max, e.ts)
            hour[utc(e.ts).hour] += 1
            dow[utc(e.ts).strftime("%A")] += 1
            if P is not None:
                P["first"] = e.ts if P["first"] is None else min(P["first"], e.ts)
                P["last"] = e.ts if P["last"] is None else max(P["last"], e.ts)
        if e.is_sidechain:
            sidechain += 1

        if e.kind == "summary":
            key = e.text[:160]
            if key and key not in seen_intents:
                seen_intents.add(key)
                intents.append(key)
        elif e.role == "user" and e.kind == "prompt":
            user_n += 1
            P["user_msgs"] += 1
            mt = _CMD_TAG.match(e.text or "")
            if mt:
                cmd_tags[mt.group(1)] += 1
            if e.is_real_prompt:
                real_prompts += 1
                txt = (e.text or "").strip()
                prompt_lengths.append(len(txt))
                words = txt.split()
                if words:
                    fw = re.sub(r"[^\w/:-]", "", words[0].lower())
                    if fw:
                        first_word[fw] += 1
                sl = _SLASH.findall(txt)
                if sl:
                    slash_prompts += 1
                    for s in sl:
                        slash_in[s] += 1
                if len(quotes) < 15 and quote_projs[e.project] < 3 and 8 <= len(txt) <= 600:
                    quotes.append({"project": e.project,
                                   "text": re.sub(r"\s+", " ", txt)[:200]})
                    quote_projs[e.project] += 1
        elif e.role == "assistant" and e.kind == "response":
            asst_n += 1
            P["asst_msgs"] += 1
            if e.model:
                model_freq[e.model] += 1
            for k in ("in", "out", "cache_create", "cache_read"):
                P[k] += e.tokens.get(k, 0)
            A["tokens"] += e.tokens.get("in", 0) + e.tokens.get("out", 0)
        elif e.kind == "tool_call" and e.tool:
            tc = e.tool
            tool_freq[tc.raw_name] += 1
            kind_freq[tc.kind] += 1
            P["tools"][tc.raw_name] += 1
            A["tools"][tc.raw_name] += 1
            if tc.kind == "skill":
                skill_freq[tc.detail.get("skill", "(unknown)")] += 1
            elif tc.kind == "subagent":
                subagent_freq[tc.detail.get("subagent_type", "(unknown)")] += 1

    durations = [(s.end - s.start) / 60.0 for s in sessions.values()
                 if s.start is not None and s.end is not None and s.end >= s.start]
    dur_buckets = Counter(_bucket(d) for d in durations)
    spd = defaultdict(set)
    for s in sessions.values():
        if s.start is not None:
            spd[utc(s.start).strftime("%Y-%m-%d")].add(s.id)

    per_project = {}
    for name, P in sorted(proj.items(), key=lambda kv: len(kv[1]["sessions"]), reverse=True):
        per_project[name] = {
            "sessions": len(P["sessions"]), "user_msgs": P["user_msgs"],
            "asst_msgs": P["asst_msgs"], "input_tokens": P["in"],
            "output_tokens": P["out"], "cache_creation_tokens": P["cache_create"],
            "cache_read_tokens": P["cache_read"],
            "first_ts": _iso(P["first"]), "last_ts": _iso(P["last"]),
            "git_branches": sorted(P["branches"]),
            "agents": sorted(P["agents"]),
            "top_tools": top(P["tools"], 10),
        }

    return {
        "overview": {
            "total_sessions": len(sessions), "total_events": len(events),
            "date_range": {"min": _iso(ts_min), "max": _iso(ts_max)},
            "total_user_messages": user_n, "total_assistant_messages": asst_n,
            "sidechain_subagent_messages": sidechain,
            "distinct_projects": len([p for p in proj if p != "(unknown)"]),
        },
        "by_agent": {a: {"sessions": len(d["sessions"]), "events": d["events"],
                         "tokens": d["tokens"], "top_tools": top(d["tools"], 8)}
                     for a, d in sorted(by_agent.items())},
        "per_project": per_project,
        "tools": {"global_frequency": top(tool_freq), "by_kind": top(kind_freq, 12),
                  "skill_invocations": top(skill_freq),
                  "subagent_spawns": top(subagent_freq),
                  "total_skill_uses": sum(skill_freq.values()),
                  "total_subagent_spawns": sum(subagent_freq.values())},
        "models": top(model_freq),
        "prompts": {"total_real_prompts": real_prompts,
                    "length_chars_distribution": dist(prompt_lengths),
                    "first_word_frequency": top(first_word),
                    "prompts_with_slash_command": slash_prompts,
                    "slash_commands_in_prompts": top(slash_in),
                    "command_tags": top(cmd_tags),
                    "representative_quotes": quotes},
        "temporal": {
            "by_hour_of_day": {str(h): hour.get(h, 0) for h in range(24)},
            "by_day_of_week": {d: dow.get(d, 0) for d in _DOW},
            "sessions_per_calendar_day": dict(sorted((d, len(s)) for d, s in spd.items())),
            "session_duration_minutes": {"distribution": dist(durations),
                                         "buckets": dict(dur_buckets)},
        },
        "session_intents_sample": intents[:30],
    }


def _iso(ts):
    return utc(ts).isoformat() if ts else None
