"""Shared session-timing logic: active intervals, overlap episodes, sweep-line.

The old timeline.py and shell.py each re-implemented active-interval construction
with subtle drift. This is the one copy, working off the Event stream. An "active
interval" is a run of a session's events split whenever the gap exceeds
ACTIVE_GAP; downstream parallel/consecutive/responsiveness/correlation signals
all build on these.
"""
from __future__ import annotations

from collections import defaultdict

ACTIVE_GAP = 1800      # 30 min: splits a session into active intervals / chains
CHAIN_GAP = 1800       # 30 min: max gap to extend a consecutive chain
WAIT_CAP = 1800        # 30 min: cap on turn-wait / think-time (away-from-keyboard)
MARGIN = 90            # ±90s tolerance for "during a session"
EDGE_WINDOW = 120      # within 120s of a session edge = launching / wrapping-up


def active_intervals(events) -> list[tuple[float, float, str, str]]:
    """[(start, end, session_id, project)] active runs, split on ACTIVE_GAP."""
    by_sess: dict[str, list] = defaultdict(list)
    proj: dict[str, str] = {}
    for e in events:
        if e.ts is None:
            continue
        by_sess[e.session_id].append(e.ts)
        proj.setdefault(e.session_id, e.project)
    out: list[tuple[float, float, str, str]] = []
    for sid, times in by_sess.items():
        times.sort()
        start = prev = times[0]
        for t in times[1:]:
            if t - prev > ACTIVE_GAP:
                out.append((start, prev, sid, proj.get(sid, "(unknown)")))
                start = t
            prev = t
        out.append((start, prev, sid, proj.get(sid, "(unknown)")))
    return out


def sweep(intervals):
    """Sweep-line over intervals → list of (seg_start, seg_end, active_set).

    active_set is the set of (sid, project) live during [seg_start, seg_end).
    """
    points = []
    for s, e, sid, pr in intervals:
        points.append((s, 0, sid, pr))   # start sorts before end at equal ts
        points.append((e, 1, sid, pr))
    points.sort(key=lambda p: (p[0], p[1]))
    segments = []
    active: dict[str, str] = {}
    prev_t = None
    for t, kind, sid, pr in points:
        if prev_t is not None and t > prev_t and active:
            segments.append((prev_t, t, dict(active)))
        if kind == 0:
            active[sid] = pr
        else:
            active.pop(sid, None)
        prev_t = t
    return segments


def attribute_days(acc: dict, t0: float, t1: float) -> None:
    """Add seconds [t0,t1) into per-UTC-day buckets, splitting across midnight."""
    from core.helpers import utc
    DAY = 86400
    while t0 < t1:
        day = utc(t0).strftime("%Y-%m-%d")
        midnight = (int(t0) // DAY + 1) * DAY
        chunk_end = min(t1, midnight)
        acc[day] = acc.get(day, 0.0) + (chunk_end - t0)
        t0 = chunk_end


def in_any_interval(epoch_s: float, intervals, margin: float = MARGIN) -> bool:
    return any(s - margin <= epoch_s <= e + margin for s, e, _, _ in intervals)
