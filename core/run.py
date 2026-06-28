"""Run the default agent — the sanctioned quarantine crossing.

Deterministic code calls these ONLY at an explicit, user-triggered action (the
Run / scanner pipeline, the Forge hand-off). The agent runs as a one-shot
that writes its result to disk; deterministic code then only reads that result.
Never per-frame, never implicit. Argv comes from the default agent's manifest.
"""
from __future__ import annotations

import shutil
import subprocess

from core import agents


def headless(prompt: str, *, cwd: str, add_dir: str,
             timeout: int) -> tuple[bool, str]:
    """One headless prompt via the default agent. Returns (ok, msg); never raises."""
    m = agents.default()
    if m is None:
        return False, "no default agent configured"
    argv = m.headless_argv(prompt, cwd=cwd, add_dir=add_dir, timeout=timeout)
    if not argv:
        return False, f"{m.label} has no headless runner"
    return _exec(argv, cwd=cwd, timeout=timeout)


def interactive_argv(prompt: str | None = None, *, add_dir: str = "") -> list[str] | None:
    m = agents.default()
    return m.interactive_argv(prompt, add_dir=add_dir) if m else None


def _exec(argv: list[str], *, cwd: str, timeout: int) -> tuple[bool, str]:
    binary = shutil.which(argv[0])
    if not binary:
        return False, f"{argv[0]} not found on PATH"
    try:
        proc = subprocess.run([binary, *argv[1:]], cwd=cwd, capture_output=True,
                              text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s"
    except Exception as e:  # noqa: BLE001 - never crash the caller
        return False, f"error: {e}"
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-160:]
        return False, f"agent exit {proc.returncode}: {tail}"
    return True, "done"
