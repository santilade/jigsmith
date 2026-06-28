"""Shell & manual-work signals — what you still do by hand.

Ports the old shell.json catalog (vocabulary, session correlation) onto the
ShellCmd stream + the shared timing layer, and adds the `inventory ⋈ usage` join
against installed packages: installed-but-unused tools, and used-but-suboptimal
verbs (raw git daily while lazygit sits idle). Deterministic.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from core.helpers import utc
from core.timing import EDGE_WINDOW, MARGIN, active_intervals, in_any_interval

_CATEGORIES = {
    "session_control": {"clear", "exit"},
    "navigation": {"cd", "ls", "pwd"},
    "port_process": {"lsof", "kill", "pkill", "ps"},
    "pkg_managers": {"pnpm", "npm", "npx", "uv", "pip", "pip3", "brew"},
    "containers": {"docker", "docker-compose"},
    "editors_open": {"open", "code", "vim", "nvim", "nano"},
    "python_node_runtime": {"python", "python3", "node", "ts-node", "deno", "bun"},
}
# verb you run a lot -> a sharper installed tool that would cover it
UPGRADES = {"git": "lazygit", "cat": "bat", "find": "fd", "grep": "rg",
            "ls": "eza", "du": "dust", "ps": "procs", "top": "btop",
            "diff": "delta", "man": "tldr", "df": "duf"}


def compute(events, shells: dict, packages: dict) -> dict:
    intervals = active_intervals(events)
    day_has_session = {utc(s).strftime("%Y-%m-%d") for s, _, _, _ in intervals}

    all_cmds = [c for sh in shells.values() for c in sh["commands"]]
    reliable = [c for c in all_cmds if c.reliable and c.ts is not None]

    verbs = Counter(c.verb for c in all_cmds if c.verb)
    full = Counter(c.command for c in all_cmds if c.command)
    git_sub = Counter()
    cats = defaultdict(int)
    for c in all_cmds:
        if c.verb == "git":
            from core.helpers import git_subcommand
            gs = git_subcommand(c.command)
            if gs:
                git_sub[gs] += 1
        for cat, members in _CATEGORIES.items():
            if c.verb in members:
                cats[cat] += 1
        if c.command.startswith("claude"):
            cats["claude_launches"] += 1

    during = outside = 0
    hour = Counter()
    prox = Counter()
    prox_ex = defaultdict(list)
    verbs_during, verbs_outside = Counter(), Counter()
    days_shell, days_both = set(), set()
    for c in reliable:
        hour[utc(c.ts).hour] += 1
        day = utc(c.ts).strftime("%Y-%m-%d")
        days_shell.add(day)
        if day in day_has_session:
            days_both.add(day)
        if in_any_interval(c.ts, intervals, MARGIN):
            during += 1
            verbs_during[c.verb] += 1
        else:
            outside += 1
            verbs_outside[c.verb] += 1
            b = _edge_bucket(c.ts, intervals, day_has_session)
            prox[b] += 1
            if len(prox_ex[b]) < 8:
                prox_ex[b].append(c.command)

    return {
        "parse": _parse_block(shells, all_cmds, reliable),
        "vocabulary": {
            "top_verbs": [{"verb": v, "count": n} for v, n in verbs.most_common(30)],
            "top_full_commands": [{"cmd": c, "count": n} for c, n in full.most_common(25)],
            "git_subcommands": dict(git_sub),
            "categories": {**{k: cats.get(k, 0) for k in _CATEGORIES},
                           "claude_launches": cats.get("claude_launches", 0),
                           "version_control": git_sub.total() if hasattr(git_sub, "total") else sum(git_sub.values())},
        },
        "correlation": {
            "claude_intervals_count": len(intervals),
            "reliable_correlated": during + outside,
            "hour_of_day_utc": {str(h): hour.get(h, 0) for h in range(24)},
            "during_session": {"count": during, "pct": _pct(during, during + outside)},
            "outside_session": {"count": outside, "pct": _pct(outside, during + outside)},
            "outside_proximity_buckets": {"counts": dict(prox), "examples": dict(prox_ex)},
            "top_verbs_during": [{"verb": v, "count": n} for v, n in verbs_during.most_common(15)],
            "top_verbs_outside": [{"verb": v, "count": n} for v, n in verbs_outside.most_common(15)],
            "reliable_days_with_shell_activity": len(days_shell),
            "reliable_days_also_with_claude": len(days_both),
        },
        "inventory_join": _join(verbs, packages),
    }


def _join(verbs: Counter, packages: dict) -> dict:
    installed = {t["name"] for t in packages.get("tools", [])}
    used = set(verbs)
    installed_unused = sorted(installed - used)
    suboptimal = []
    for verb, n in verbs.most_common(40):
        better = UPGRADES.get(verb)
        if better and better in installed and verbs.get(better, 0) < n / 4:
            suboptimal.append({"verb": verb, "uses": n, "installed_alt": better,
                               "alt_uses": verbs.get(better, 0)})
    return {
        "installed_count": len(installed),
        "installed_unused": installed_unused[:40],
        "installed_unused_count": len(installed_unused),
        "used_suboptimal": suboptimal,
        "note": "unused is window-bounded — a rarely-used tool isn't necessarily dead",
    }


def _parse_block(shells, all_cmds, reliable):
    ts_all = [c.ts for c in all_cmds if c.ts is not None]
    dominant = None
    for sh in shells.values():
        if sh.get("dominant_bulk_ts"):
            dominant = sh["dominant_bulk_ts"]
            break
    return {
        "shells": sorted(shells.keys()),
        "total_entries": len(all_cmds),
        "entries_with_ts": len(ts_all),
        "distinct_ts": len(set(ts_all)),
        "dominant_bulk_ts": dominant,
        "reliable_entry_count": len(reliable),
        "reliable_date_range_utc": {
            "min": utc(min(c.ts for c in reliable)).isoformat() if reliable else None,
            "max": utc(max(c.ts for c in reliable)).isoformat() if reliable else None},
    }


def _edge_bucket(ts, intervals, day_has_session) -> str:
    day = utc(ts).strftime("%Y-%m-%d")
    if day not in day_has_session:
        return "no-session-that-day"
    for s, e, _, _ in intervals:
        if 0 <= s - ts <= EDGE_WINDOW:
            return "launching"
        if 0 <= ts - e <= EDGE_WINDOW:
            return "wrapping-up"
    return "gap"


def _pct(n, total):
    return round(100 * n / total, 1) if total else 0
