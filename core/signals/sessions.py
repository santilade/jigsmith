"""Sessions & orchestration signals — how you drive.

Ports the old timeline.json catalog (parallel/overlap, consecutive/chains,
responsiveness/babysitting, busiest days) onto the shared Event stream + timing
layer. Cross-agent aware: parallel detection now spans agents, so running Claude
and opencode at once shows up as overlap. Deterministic.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from core.events import sessions_from_events
from core.helpers import percentile, utc
from core.timing import (ACTIVE_GAP, CHAIN_GAP, WAIT_CAP, active_intervals,
                         attribute_days, sweep)


def _hms(ts):
    return utc(ts).strftime("%H:%M:%S")


def _date(ts):
    return utc(ts).strftime("%Y-%m-%d")


def compute(events) -> dict:
    sessions = sessions_from_events(events)
    intervals = active_intervals(events)

    active_secs = defaultdict(float)
    for s, e, sid, _ in intervals:
        active_secs[sid] += e - s
    total_active = sum(active_secs.values())

    return {
        "overall": _overall(sessions, intervals, total_active),
        "parallel": _parallel(intervals),
        "consecutive": _consecutive(sessions),
        "responsiveness": _responsiveness(events, total_active),
        "busiest_days": _busiest(events, sessions),
        "meta": {"active_gap_seconds": ACTIVE_GAP, "chain_gap_seconds": CHAIN_GAP,
                 "wait_cap_seconds": WAIT_CAP},
    }


def _overall(sessions, intervals, total_active):
    segs = sweep(intervals)
    ever_parallel = set()
    for _, _, active in segs:
        if len(active) >= 2:
            ever_parallel |= set(active)
    chains = _chains(sessions)
    in_chain = {sid for c in chains if len(c) >= 2 for sid in c}
    starts = [s.start for s in sessions.values() if s.start is not None]
    ends = [s.end for s in sessions.values() if s.end is not None]
    return {
        "total_sessions": len(sessions),
        "total_active_hours": round(total_active / 3600, 2),
        "total_active_seconds": round(total_active),
        "total_active_intervals": len(intervals),
        "sessions_ever_parallel": len(ever_parallel),
        "sessions_always_solo": len(sessions) - len(ever_parallel),
        "sessions_in_chain": len(in_chain),
        "sessions_standalone": len(sessions) - len(in_chain),
        "date_range": {"min": _iso(min(starts)) if starts else None,
                       "max": _iso(max(ends)) if ends else None},
    }


def _parallel(intervals):
    segs = sweep(intervals)
    union = ge2 = ge3 = same = cross = 0.0
    maxc = 0
    days: dict = {}
    episodes: list = []
    cur = None
    for s, e, active in segs:
        dur = e - s
        n = len(active)
        maxc = max(maxc, n)
        union += dur
        if n >= 2:
            ge2 += dur
            projects = set(active.values())
            if len(projects) > 1:
                cross += dur
            else:
                same += dur
            attribute_days(days, s, e)
            if cur and abs(cur["end"] - s) < 1e-6:
                cur["end"] = e
                cur["sids"] |= set(active)
                cur["projects"] |= projects
            else:
                if cur:
                    episodes.append(cur)
                cur = {"start": s, "end": e, "sids": set(active), "projects": projects}
        else:
            if cur:
                episodes.append(cur)
                cur = None
        if n >= 3:
            ge3 += dur
    if cur:
        episodes.append(cur)

    episodes.sort(key=lambda ep: ep["end"] - ep["start"], reverse=True)
    longest = [{"start": _iso(ep["start"]), "end": _iso(ep["end"]),
                "duration_min": round((ep["end"] - ep["start"]) / 60, 1),
                "sessionIds": sorted(ep["sids"]), "projects": sorted(ep["projects"]),
                "cross_project": len(ep["projects"]) > 1} for ep in episodes[:20]]
    return {
        "max_concurrency": maxc,
        "active_wall_seconds_union": round(union),
        "overlapped_wall_seconds": round(ge2),
        "seconds_concurrency_ge3": round(ge3),
        "hours_concurrency_ge2": round(ge2 / 3600, 2),
        "hours_concurrency_ge3": round(ge3 / 3600, 2),
        "pct_active_wall_overlapped": round(100 * ge2 / union, 1) if union else 0,
        "overlap_seconds_same_project": round(same),
        "overlap_seconds_cross_project": round(cross),
        "total_overlap_episodes": len(episodes),
        "cross_project_episodes": sum(1 for ep in episodes if len(ep["projects"]) > 1),
        "same_project_episodes": sum(1 for ep in episodes if len(ep["projects"]) == 1),
        "longest_episodes": longest,
        "parallel_days_count": len(days),
        "parallel_minutes_per_day": {d: round(s / 60) for d, s in sorted(days.items())},
    }


def _chains(sessions):
    ordered = sorted((s for s in sessions.values() if s.start is not None),
                     key=lambda s: s.start)
    chains, cur = [], []
    for s in ordered:
        if not cur:
            cur = [s.id]
            prev_end = s.end
            continue
        gap = s.start - prev_end
        if gap < CHAIN_GAP:
            cur.append(s.id)
        else:
            chains.append(cur)
            cur = [s.id]
        prev_end = s.end
    if cur:
        chains.append(cur)
    return chains


def _consecutive(sessions):
    ordered = sorted((s for s in sessions.values() if s.start is not None),
                     key=lambda s: s.start)
    gap_buckets = Counter()
    same = switch = 0
    for a, b in zip(ordered, ordered[1:]):
        gap = b.start - a.end
        gap_buckets[_gap_bucket(gap)] += 1
        if gap < CHAIN_GAP:
            if a.project == b.project:
                same += 1
            else:
                switch += 1
    chains = _chains(sessions)
    multi = [c for c in chains if len(c) >= 2]
    by_id = {s.id: s for s in sessions.values()}
    longest = []
    for c in sorted(multi, key=len, reverse=True)[:10]:
        ss = [by_id[i] for i in c]
        projs = [s.project for s in ss]
        longest.append({"date": _date(ss[0].start), "length": len(c),
                        "total_span_min": round((ss[-1].end - ss[0].start) / 60, 1),
                        "projects_in_order": projs,
                        "same_project_throughout": len(set(projs)) == 1})
    return {
        "n_adjacent_pairs": max(0, len(ordered) - 1),
        "gap_buckets": dict(gap_buckets),
        "n_chains": len(chains), "n_multi_session_chains": len(multi),
        "chain_length_distribution": dict(Counter(len(c) for c in chains)),
        "longest_chains": longest,
        "handoffs_same_project": same, "handoffs_switch_project": switch,
    }


def _gap_bucket(gap):
    if gap < 0:
        return "overlap(<0)"
    m = gap / 60
    for hi, name in [(5, "0-5min"), (15, "5-15min"), (30, "15-30min"),
                     (60, "30-60min"), (180, "1-3hr")]:
        if m < hi:
            return name
    return ">3hr"


def _responsiveness(events, total_active):
    by_sess = defaultdict(list)
    for e in events:
        if e.ts is None:
            continue
        if e.role == "user" and e.kind == "prompt" and e.is_real_prompt:
            by_sess[e.session_id].append((e.ts, "human"))
        elif e.role == "assistant" and e.kind == "response":
            by_sess[e.session_id].append((e.ts, "asst"))
    waits: list[float] = []
    think_total = 0.0
    by_project_acc = defaultdict(lambda: {"wait": 0.0, "turns": 0})
    # Summary records carry no cwd → "(unknown)"; skip them so a trailing
    # summary line doesn't clobber a session's real project (last wins).
    proj_of = {e.session_id: e.project for e in events if e.kind != "summary"}
    for sid, seq in by_sess.items():
        seq.sort()
        humans = [i for i, (_, k) in enumerate(seq) if k == "human"]
        for idx, hi in enumerate(humans):
            t_prompt = seq[hi][0]
            next_human = seq[humans[idx + 1]][0] if idx + 1 < len(humans) else None
            last_asst = None
            for t, k in seq[hi + 1:]:
                if next_human is not None and t >= next_human:
                    break
                if k == "asst":
                    last_asst = t
            if last_asst is not None:
                w = min(last_asst - t_prompt, WAIT_CAP)
                waits.append(w)
                by_project_acc[proj_of.get(sid, "(unknown)")]["wait"] += w
                by_project_acc[proj_of.get(sid, "(unknown)")]["turns"] += 1
                if next_human is not None:
                    think_total += min(next_human - last_asst, WAIT_CAP)
    total_wait = sum(waits)
    by_project = {p: {"wait_hours": round(d["wait"] / 3600, 2), "turns": d["turns"],
                      "mean_wait_sec": round(d["wait"] / d["turns"], 1) if d["turns"] else 0}
                  for p, d in sorted(by_project_acc.items(),
                                     key=lambda kv: kv[1]["wait"], reverse=True)}
    return {
        "measured_turns": len(waits),
        "total_wait_seconds": round(total_wait), "total_wait_hours": round(total_wait / 3600, 2),
        "median_turn_wait_sec": round(percentile(waits, 50), 1),
        "mean_turn_wait_sec": round(total_wait / len(waits), 1) if waits else 0,
        "p90_turn_wait_sec": round(percentile(waits, 90), 1),
        "max_turn_wait_sec": round(max(waits), 1) if waits else 0,
        "total_human_think_hours": round(think_total / 3600, 2),
        "pct_active_wall_waiting": round(100 * total_wait / total_active, 1) if total_active else 0,
        "wait_cap_seconds": WAIT_CAP, "by_project": by_project,
    }


def _busiest(events, sessions):
    human = defaultdict(int)
    for e in events:
        if e.role == "user" and e.kind == "prompt" and e.is_real_prompt:
            human[e.session_id] += 1
    by_day = defaultdict(list)
    for s in sessions.values():
        if s.start is not None:
            by_day[_date(s.start)].append(s)
    spd = {d: len(ss) for d, ss in sorted(by_day.items())}
    top_days = sorted(spd.items(), key=lambda kv: kv[1], reverse=True)[:5]
    timelines = {}
    for d, _ in top_days:
        ss = sorted(by_day[d], key=lambda s: s.start)
        timelines[d] = [{"start_hms": _hms(s.start), "end_hms": _hms(s.end),
                         "project": s.project, "n_human_prompts": human.get(s.id, 0)}
                        for s in ss]
    return {"sessions_per_day": spd,
            "top_days": [{"date": d, "sessions_started": n} for d, n in top_days],
            "timelines": timelines}


def _iso(ts):
    return utc(ts).isoformat() if ts else None
