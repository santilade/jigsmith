"""Run the default agent — the sanctioned quarantine crossing.

Deterministic code calls these ONLY at an explicit, user-triggered action (the
Run / scanner pipeline, the Forge hand-off). The agent runs as a one-shot
that writes its result to disk; deterministic code then only reads that result.
Never per-frame, never implicit. Argv comes from the default agent's manifest.

`on_line` lets a caller *tail* a streaming run: when supplied and the default
agent declares a `headless_stream` runner, we drive the agent in stream mode and
hand each parsed step to the callback as it lands. Still the same one-shot
crossing — deterministic code only reads the agent's stdout, it does not
re-derive judgment. With no callback (or no stream runner) we fall back to the
plain blocking run. Both paths honor `cancel` and `timeout`.
"""
from __future__ import annotations

import json
import queue
import shutil
import subprocess
import threading
import time
from typing import Callable

from core import agents

# Event-format parser registry, keyed by manifest `run.stream_format`. A parser
# maps one decoded event -> a short display line (or None to skip it). Adding a
# new streaming agent format is one entry here, no other code.


def _tool_brief(inp: dict) -> str:
    for k in ("file_path", "filePath", "path", "pattern", "command",
              "description", "prompt"):
        v = inp.get(k)
        if v:
            return f"({str(v).splitlines()[0][:60]})"
    return ""


def _parse_claude_stream(evt: dict) -> str | None:
    t = evt.get("type")
    if t == "system" and evt.get("subtype") == "init":
        return "· session started"
    if t == "assistant":
        out: list[str] = []
        for p in (evt.get("message") or {}).get("content") or []:
            if p.get("type") == "text":
                txt = (p.get("text") or "").strip()
                if txt:
                    out.append(txt.splitlines()[0][:100])
            elif p.get("type") == "tool_use":
                out.append(f"→ {p.get('name') or 'tool'}"
                           f"{_tool_brief(p.get('input') or {})}")
        return "  ".join(out) or None
    return None  # tool results, deltas, the final `result` — not log lines


def _parse_opencode_stream(evt: dict) -> str | None:
    # opencode --format json emits one object per step: step_start, text
    # (assistant prose, reasoning fenced in a <think> block), tool_use, step_finish.
    t = evt.get("type")
    part = evt.get("part") or {}
    if t == "step_start":
        return "· session started"
    if t == "text":
        txt = (part.get("text") or "").strip()
        if "</think>" in txt:  # drop the reasoning prefix, keep the visible answer
            txt = txt.rsplit("</think>", 1)[-1].strip()
        return txt.splitlines()[0][:100] if txt else None
    if t == "tool_use":
        name = part.get("tool") or "tool"
        inp = (part.get("state") or {}).get("input") or {}
        return f"→ {name}{_tool_brief(inp)}"
    return None  # step_finish, results — not log lines


_STREAM_PARSERS: dict[str, Callable[[dict], str | None]] = {
    "claude-stream-json": _parse_claude_stream,
    "opencode-json": _parse_opencode_stream,
}


def headless(prompt: str, *, cwd: str, add_dir: str, timeout: int,
             cancel: threading.Event | None = None,
             on_line: Callable[[str], None] | None = None) -> tuple[bool, str]:
    """One headless prompt via the default agent. Returns (ok, msg); never raises.

    `cancel` is an optional Event; when set mid-run the agent process is killed
    and (False, "cancelled") is returned — the force-exit path for the scanner.

    If `on_line` is given and the agent has a streaming runner, each parsed step
    is pushed to it live; otherwise this blocks until the run completes.
    """
    m = agents.default()
    if m is None:
        return False, "no default agent configured"
    if on_line is not None:
        stream = m.headless_stream_argv(prompt, cwd=cwd, add_dir=add_dir,
                                        timeout=timeout)
        parse = _STREAM_PARSERS.get(m.stream_format())
        if stream and parse:
            return _exec_stream(stream, cwd=cwd, timeout=timeout, cancel=cancel,
                                on_line=on_line, parse=parse)
    argv = m.headless_argv(prompt, cwd=cwd, add_dir=add_dir, timeout=timeout)
    if not argv:
        return False, f"{m.label} has no headless runner"
    return _exec(argv, cwd=cwd, timeout=timeout, cancel=cancel)


def interactive_argv(prompt: str | None = None, *, add_dir: str = "") -> list[str] | None:
    m = agents.default()
    return m.interactive_argv(prompt, add_dir=add_dir) if m else None


def _exec(argv: list[str], *, cwd: str, timeout: int,
          cancel: threading.Event | None = None) -> tuple[bool, str]:
    binary = shutil.which(argv[0])
    if not binary:
        return False, f"{argv[0]} not found on PATH"
    # Popen (not subprocess.run) so the poll loop below can kill the agent on
    # cancel or timeout instead of blocking until it exits on its own.
    try:
        proc = subprocess.Popen([binary, *argv[1:]], cwd=cwd,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True)
    except Exception as e:  # noqa: BLE001 - never crash the caller
        return False, f"error: {e}"
    start = time.monotonic()
    out = err = ""
    while True:
        try:
            out, err = proc.communicate(timeout=0.5)
            break  # process exited
        except subprocess.TimeoutExpired:
            pass
        if cancel is not None and cancel.is_set():
            _kill(proc)
            return False, "cancelled"
        if time.monotonic() - start > timeout:
            _kill(proc)
            return False, f"timed out after {timeout}s"
    if proc.returncode != 0:
        tail = (err or out or "").strip()[-160:]
        return False, f"agent exit {proc.returncode}: {tail}"
    return True, "done"


def _exec_stream(argv: list[str], *, cwd: str, timeout: int,
                 cancel: threading.Event | None,
                 on_line: Callable[[str], None],
                 parse: Callable[[dict], str | None]) -> tuple[bool, str]:
    """Stream one run, parsing newline-delimited events to `on_line` as they
    arrive. A reader thread feeds a queue so the main loop stays free to honor
    cancel + timeout (line iteration on the pipe would otherwise block)."""
    binary = shutil.which(argv[0])
    if not binary:
        return False, f"{argv[0]} not found on PATH"
    try:
        proc = subprocess.Popen([binary, *argv[1:]], cwd=cwd,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, bufsize=1)
    except Exception as e:  # noqa: BLE001 - never crash the caller
        return False, f"error: {e}"

    lines: "queue.Queue[str]" = queue.Queue()

    def _reader() -> None:
        try:
            for raw in proc.stdout or ():
                lines.put(raw)
        except Exception:  # noqa: BLE001 - pipe closed on kill
            pass

    reader = threading.Thread(target=_reader, daemon=True)
    reader.start()
    start = time.monotonic()
    while True:
        try:
            raw = lines.get(timeout=0.25)
        except queue.Empty:
            if proc.poll() is not None and not reader.is_alive():
                break  # process done and pipe drained
            if cancel is not None and cancel.is_set():
                _kill(proc)
                return False, "cancelled"
            if time.monotonic() - start > timeout:
                _kill(proc)
                return False, f"timed out after {timeout}s"
            continue
        line = raw.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except ValueError:
            continue
        disp = parse(evt)
        if disp:
            try:
                on_line(disp)
            except Exception:  # noqa: BLE001 - a bad sink must not kill the run
                pass
    proc.wait()
    if proc.returncode != 0:
        tail = ((proc.stderr.read() if proc.stderr else "") or "").strip()[-160:]
        return False, f"agent exit {proc.returncode}: {tail}"
    return True, "done"


def _kill(proc: subprocess.Popen) -> None:
    """Terminate, escalate to kill, never raise."""
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    except Exception:  # noqa: BLE001
        pass
