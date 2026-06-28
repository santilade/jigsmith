"""Shared deterministic parsing helpers, salvaged + deduped from the old miners.

The three legacy scripts each re-implemented timestamp parsing, prompt
filtering, project normalization, verb extraction, and credential redaction with
subtle drift. This is the one canonical copy. Stdlib only, defensive: every
function returns a safe default rather than raising on bad input.
"""
from __future__ import annotations

import os
import re
import statistics
from collections import Counter
from datetime import datetime, timezone

# ---- timestamps (always UTC epoch floats in the event stream) ----------------

def parse_ts(ts) -> datetime | None:
    """ISO8601 (with trailing Z) -> aware UTC datetime, or None."""
    if not ts or not isinstance(ts, str):
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def epoch(ts) -> float | None:
    dt = parse_ts(ts)
    return dt.timestamp() if dt else None


def utc(epoch_s: float) -> datetime:
    return datetime.fromtimestamp(epoch_s, tz=timezone.utc)


# ---- projects ---------------------------------------------------------------

PROJECTS_ROOT = os.path.join(os.path.expanduser("~"), "Documents", "Projects")


def normalize_project(cwd: str | None) -> str:
    """Collapse a cwd to its top-level project name (subdirs fold together)."""
    if not cwd:
        return "(unknown)"
    root = PROJECTS_ROOT.rstrip("/") + "/"
    if cwd.startswith(root):
        return cwd[len(root):].split("/", 1)[0]
    return os.path.basename(cwd.rstrip("/")) or cwd


def raw_project(cwd: str | None) -> str:
    if not cwd:
        return "(unknown)"
    return os.path.basename(cwd.rstrip("/")) or cwd


# ---- message text + real-prompt filter --------------------------------------

def get_text(content) -> str:
    """Flatten a message.content (str | list of blocks) to its text parts."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


_NONPROMPT_PREFIXES = ("<local-command", "<command-", "<command_", "<bash-",
                       "<system-reminder", "Caveat:", "<local-command-caveat>")
_NONPROMPT_RE = re.compile(r"^\[(Request interrupted|Request|API Error)\b")


def is_real_prompt(text: str, *, is_meta: bool = False,
                   only_tool_result: bool = False) -> bool:
    """True if a user turn is a genuine human-typed prompt (not tool plumbing)."""
    if is_meta or only_tool_result:
        return False
    txt = (text or "").strip()
    if not txt:
        return False
    low = txt.lstrip()
    if low.startswith(_NONPROMPT_PREFIXES):
        return False
    if "DO NOT respond to these messages" in txt:
        return False
    if _NONPROMPT_RE.match(low):
        return False
    return True


# ---- shell / bash command analysis ------------------------------------------

_SEPS = re.compile(r"&&|\|\||;|\|")
_WRAPPERS = {"sudo", "command", "env", "time", "nice", "nohup", "exec"}


def verb(cmd: str | None) -> str | None:
    """Leading executed command verb: skips cd-only segments, VAR=val, wrappers."""
    if not cmd:
        return None
    for seg in _SEPS.split(cmd.strip()):
        seg = seg.strip().lstrip("({ \t")
        toks = seg.split()
        i = 0
        while i < len(toks) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", toks[i]):
            i += 1
        while i < len(toks) and toks[i] in _WRAPPERS:
            i += 1
        if i >= len(toks):
            continue
        v = os.path.basename(toks[i]).strip("`'\"")
        if v == "cd":
            continue
        return v
    return "cd"


_GIT_GLOBAL_FLAGS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}


def git_subcommand(cmd: str | None) -> str | None:
    """The real git subcommand, skipping global flags like `-C path`."""
    if not cmd or "git" not in cmd:
        return None
    toks = (cmd or "").split()
    try:
        i = toks.index("git") + 1
    except ValueError:
        return None
    while i < len(toks):
        t = toks[i]
        if t in _GIT_GLOBAL_FLAGS:
            i += 2
            continue
        if t.startswith("-"):
            i += 1
            continue
        return t if re.match(r"^[a-zA-Z][a-zA-Z-]*$", t) else None
    return None


def norm_cmd(cmd: str | None) -> str:
    return re.sub(r"\s+", " ", (cmd or "").strip())


# ---- credential redaction (run before ANY command string is stored) ---------

_REDACT = "‹redacted›"
_TOKEN_PATTERNS = [
    r"sk-[A-Za-z0-9_-]{16,}", r"ghp_[A-Za-z0-9]{20,}", r"gho_[A-Za-z0-9]{20,}",
    r"github_pat_[A-Za-z0-9_]{20,}", r"xox[baprs]-[A-Za-z0-9-]{10,}",
    r"AKIA[0-9A-Z]{16}", r"ASIA[0-9A-Z]{16}", r"AIza[0-9A-Za-z_-]{30,}",
    r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----",
    r"\b[0-9a-fA-F]{32,}\b", r"\b[A-Za-z0-9+/]{40,}={0,2}\b",
]
_TOKEN_RE = re.compile("|".join(_TOKEN_PATTERNS))
_BEARER = re.compile(r"(?i)\b(bearer|authorization|oauth|token)[:= ]+\S+")
_CONN = re.compile(r"([a-z][a-z0-9+.-]*://[^:\s/]+:)([^@\s]+)(@)")
_SECRET_NAME = re.compile(
    r"(?i)\b([A-Z0-9_]*(KEY|SECRET|TOKEN|PASS|PASSWORD|PWD|CRED|AUTH|OAUTH|"
    r"SESSION|PRIVATE|APIKEY|API_KEY|ACCESS|CLIENT_SECRET)[A-Z0-9_]*)=(\S+)")
_SECRET_FLAG = re.compile(
    r"(?i)(--(?:password|token|secret|api-key|auth)[= ])(\S+)")


def _looks_secretish(val: str) -> bool:
    if len(val) < 12 or " " in val or "/" in val:
        return False
    has_digit = any(c.isdigit() for c in val)
    has_alpha = any(c.isalpha() for c in val)
    return (has_digit and has_alpha and len(val) >= 16) or len(val) >= 28


def redact(cmd: str | None) -> str:
    s = cmd or ""
    s = _TOKEN_RE.sub(_REDACT, s)
    s = _BEARER.sub(lambda m: f"{m.group(1)} {_REDACT}", s)
    s = _CONN.sub(lambda m: m.group(1) + _REDACT + m.group(3), s)
    s = _SECRET_NAME.sub(lambda m: f"{m.group(1)}={_REDACT}", s)
    s = _SECRET_FLAG.sub(lambda m: m.group(1) + _REDACT, s)
    s = re.sub(r"(?i)\b([A-Z0-9_]+)=(\S+)",
               lambda m: f"{m.group(1)}={_REDACT}" if _looks_secretish(m.group(2))
               else m.group(0), s)
    return s


def scrub(cmd: str | None, trunc: int = 120) -> str:
    """Redact + collapse whitespace + truncate. Always safe to emit."""
    s = norm_cmd(redact(cmd))
    return s if len(s) <= trunc else s[: trunc - 1] + "…"


# ---- stats ------------------------------------------------------------------

def percentile(vals: list[float], pct: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    k = max(0, min(len(s) - 1, round(pct / 100 * (len(s) - 1))))
    return s[k]


def dist(vals: list[float]) -> dict | None:
    if not vals:
        return None
    return {"min": min(vals), "median": round(statistics.median(vals), 1),
            "max": max(vals), "mean": round(statistics.mean(vals), 1),
            "count": len(vals)}


def top(counter: Counter, n: int = 30) -> list[dict]:
    return [{"name": k, "count": v} for k, v in counter.most_common(n)]
