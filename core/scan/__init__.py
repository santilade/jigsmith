"""scan — the deterministic scanner orchestrator (phases 2-3).

The fan-out is Python's job, the judgment is the agent's. This module sequences
the agentic phases the way `core.mine` sequences the deterministic one:

- **analyze** loops the registry lenses, runs one analyst per lens *in parallel*
  (each a sanctioned `run.headless` crossing handed an inlined rubric + signal
  slice), validates and retries each, then hands the consolidated candidate list
  to one rollup agent for cross-lens dedup + the web source-check + ranking.
  Python owns the loop, the validation, and the final write; the agent owns only
  the per-lens and reconciliation judgment.
- **report** runs the single Profile composition and structurally validates it.

Quarantine intact: this is deterministic code crossing to the agent only at the
explicit Run action, one-shot, writing to disk; the TUI then only reads the
result. The line the old single-prompt fan-out blurred — orchestration smuggled
into the agentic phase — is restored here: orchestration is deterministic again.
"""
from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Callable

from core import run, sections
from core.mine import SIGNALS_PATH
from core.store.db import REPO_ROOT
from core.scan import shape

PATTERNS_PATH = os.path.join(REPO_ROOT, "patterns.json")
PROFILE_PATH = os.path.join(REPO_ROOT, "tui", "config", "profile.json")
# Per-call scratch: one analyst's raw output per lens, before the rollup folds
# them together. Gitignored — intermediate, regenerated every run.
SCRATCH_DIR = os.path.join(REPO_ROOT, "patterns.d")

LENS_TIMEOUT = 1200     # per analyst; parallel, so wall-clock ≈ slowest lens
ROLLUP_TIMEOUT = 1200   # the reconciler (does the web source-check)
REPORT_TIMEOUT = 1800   # the single Profile composition
ANALYST_CONCURRENCY = 4  # bounded fan-out; a local model thrashes if every lens
#                          hits it at once. Tune up for a hosted/fast agent.

OnLine = Callable[[str], None] | None
Cancel = threading.Event | None


# ---- helpers ----------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: str):
    try:
        with open(path, "r", errors="replace") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001 - missing/bad file is a retry signal, not a crash
        return None


def _read_text(rel: str) -> str:
    try:
        with open(os.path.join(REPO_ROOT, rel), "r", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def _wrap(on_line: OnLine, tag: str) -> OnLine:
    """Prefix each streamed step with its lens, so the interleaved parallel tail
    in the progress popup stays attributable."""
    if on_line is None:
        return None
    return lambda line: on_line(f"[{tag}] {line}")


def _cancelled(cancel: Cancel) -> bool:
    return cancel is not None and cancel.is_set()


def _is_terminal(msg: str) -> bool:
    """A timeout or cancel is the worst case already — don't retry it (the
    ai-code-review rule). Any other agent error is worth one more attempt."""
    return "timed out" in msg or "cancelled" in msg


# ---- phase 2: analyze -------------------------------------------------------

def _analyst_prompt(lens: dict, slice_data, out_path: str) -> str:
    sid = lens["id"]
    rubric = _read_text(lens.get("rubric", f"knowledge/{sid}.md")) or "(rubric missing — lean on the data)"
    rel_out = os.path.relpath(out_path, REPO_ROOT)
    return (
        f"You are the {lens.get('analyzer', sid + '-analyst')} for Jigsmith — the "
        f"**{lens['title']}** lens.\n\n"
        f"Lens: {lens.get('lens', '')}\n\n"
        f"Judge ONLY this lens. You are handed everything you need inline — do not "
        f"read another lens's slice, and do not re-run the miner.\n\n"
        f"== YOUR RUBRIC (knowledge/{sid}.md) ==\n{rubric}\n\n"
        f"== YOUR SIGNAL SLICE (signals.{sid}) ==\n"
        f"{json.dumps(slice_data, indent=1, ensure_ascii=False)}\n\n"
        f"== THE UNIFORM SUGGESTION SHAPE ==\n{shape.SHAPE_CONTRACT}\n\n"
        f"Surface EVERY painpoint this lens sees — forge, dispose, and manual/no-build "
        f"nudges — each carrying a suggested solution. A pure observation with nothing "
        f"to do is NOT a painpoint (leave it for the Profile prose); never manufacture "
        f"a fix to smuggle an observation onto the board. Do LOCAL source-checks only "
        f"(installed-but-idle tools in the slice) — the rollup does the one web pass on "
        f"the painpoint, not you. Set `fix.approach` PROVISIONALLY (local signal + "
        f"judgment); the rollup's source-check may flip it to download. Flag craft; "
        f"never propose automating judgment away.\n\n"
        f"Write your suggestions as a JSON array to `{rel_out}` — `[ <suggestion>, ... ]`, "
        f"an empty array `[]` if this lens is clean. Set every field of the shape. "
        f"Don't ask questions; write the file."
    )


def _run_lens(lens: dict, slice_data, cancel: Cancel, on_line: OnLine) -> tuple[str, list, str]:
    """Run one analyst with validate + one retry. Returns (id, suggestions, err).

    A lens that fails is non-fatal: it contributes no suggestions and a warning,
    rather than corrupting the whole run. `section` is forced to the lens id —
    a per-lens analyst owns exactly one lens, so mis-tagging is impossible."""
    sid = lens["id"]
    out_path = os.path.join(SCRATCH_DIR, f"{sid}.json")
    try:
        os.remove(out_path)
    except OSError:
        pass
    prompt = _analyst_prompt(lens, slice_data, out_path)
    wl = _wrap(on_line, sid)
    last = ""
    for _attempt in (1, 2):
        if _cancelled(cancel):
            return sid, [], "cancelled"
        ok, msg = run.headless(prompt, cwd=REPO_ROOT, add_dir=REPO_ROOT,
                               timeout=LENS_TIMEOUT, cancel=cancel, on_line=wl)
        last = msg
        if not ok:
            if _is_terminal(msg):
                return sid, [], msg
            continue  # agent error — retry once
        parsed = _read_json(out_path)
        suggestions = shape.normalize_many(parsed, section=sid)
        if suggestions is not None:  # recognizable array (possibly empty) → accept
            return sid, suggestions, ""
        # wrote nothing / unparseable container → retry once
    return sid, [], f"{sid}: no valid output ({last})"


def _rollup_prompt(candidates: list, count_by_lens: dict[str, int]) -> str:
    rubric = _read_text("knowledge/forge.md") or "(forge rubric missing)"
    tally = ", ".join(f"{k} ×{v}" for k, v in sorted(count_by_lens.items())) or "none"
    rel_out = os.path.relpath(PATTERNS_PATH, REPO_ROOT)
    return (
        f"You are the recommendations rollup for Jigsmith — the reconciler that turns "
        f"the per-lens analysts' candidates into the final ranked Forge board.\n\n"
        f"The analysts already ran (in parallel) and their output is validated and "
        f"collected for you below ({tally}). You do NOT re-analyze the lenses.\n\n"
        f"== CANDIDATES (already in the uniform shape) ==\n"
        f"{json.dumps(candidates, indent=1, ensure_ascii=False)}\n\n"
        f"== RUBRIC (knowledge/forge.md) ==\n{rubric}\n\n"
        f"Do three things:\n"
        f"1. **Dedup** — the same idea surfaces from multiple lenses (a dead MCP shows "
        f"in both Harness and Context). Merge into one, keep the strongest evidence, "
        f"and keep the merged item's `section` as its primary lens.\n"
        f"2. **Source-check (painpoint FIRST, type LAST)** — for EVERY candidate, never "
        f"pre-filtering by form, do ONE web pass on the painpoint across registries: code "
        f"hosts for CLIs/TUIs (`gh search repos`, github.com/trending), the official skill "
        f"marketplace (`anthropics/skills`) for an existing skill/agent, and MCP registries "
        f"for a missing capability. Good fit → `fix.approach: download` (its own form sets "
        f"`fix.tool_type`). Partial/no fit → `custom`, then pick the lightest fitting form "
        f"— favor a `CLI + skill` combo when the pattern has a mechanic AND a judgment "
        f"layer. Web unreachable → judgment + drop `gate.confidence` a notch.\n"
        f"3. **Rank by cumulative cost (the 90%), not loudness** — frequency × "
        f"per-instance cost vs build + upkeep, mixing forge/dispose/suggest in one list. "
        f"Never rank a craft-flagged item as a forge.\n\n"
        f"Write `{rel_out}`: "
        f'{{"generated": "<ISO8601>", "patterns": [ <suggestion>, ... ]}} — every item '
        f"in the uniform shape, `section` accurate (phase 3 routes painpoints back to "
        f"their Profile lens by it). Don't ask questions; write the file."
    )


def analyze(cancel: Cancel = None, on_line: OnLine = None) -> tuple[bool, str]:
    """signals.json → patterns.json. Parallel per-lens fan-out + agentic rollup.

    Returns (ok, message). Per-lens failures are non-fatal (logged into the
    message); the phase fails only if signals are missing or the rollup can't
    produce a valid patterns.json."""
    signals = _read_json(SIGNALS_PATH)
    if not isinstance(signals, dict):
        return False, "signals.json missing or unreadable — run the miner first"
    lenses = sections.lenses()
    if not lenses:
        return False, "no lenses in sections.json"
    os.makedirs(SCRATCH_DIR, exist_ok=True)

    results: dict[str, list] = {}
    warnings: list[str] = []
    workers = min(ANALYST_CONCURRENCY, len(lenses))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_run_lens, lens, signals.get(lens["id"]), cancel, on_line): lens
                for lens in lenses}
        for fut in as_completed(futs):
            sid, suggestions, err = fut.result()
            results[sid] = suggestions
            if err:
                warnings.append(err)

    if _cancelled(cancel):
        return False, "cancelled"

    candidates = [s for sid in results for s in results[sid]]
    count_by_lens = {sid: len(v) for sid, v in results.items() if v}
    if on_line:
        on_line(f"· {len(candidates)} candidates from {len(count_by_lens)} lenses → rollup")

    ok, msg = _rollup(candidates, count_by_lens, cancel, on_line)
    if not ok:
        return False, msg
    if warnings:
        msg += "  (warnings: " + "; ".join(warnings) + ")"
    return True, msg


def _rollup(candidates: list, count_by_lens: dict[str, int],
            cancel: Cancel, on_line: OnLine) -> tuple[bool, str]:
    prompt = _rollup_prompt(candidates, count_by_lens)
    wl = _wrap(on_line, "rollup")
    last = ""
    for _attempt in (1, 2):
        if _cancelled(cancel):
            return False, "cancelled"
        ok, msg = run.headless(prompt, cwd=REPO_ROOT, add_dir=REPO_ROOT,
                               timeout=ROLLUP_TIMEOUT, cancel=cancel, on_line=wl)
        last = msg
        if not ok:
            if _is_terminal(msg):
                return False, msg
            continue
        data = _read_json(PATTERNS_PATH)
        raw = data.get("patterns") if isinstance(data, dict) else None
        final = shape.normalize_many(raw, section=None)
        if final is not None:
            # Re-write through the validator so the on-disk shape is guaranteed,
            # whatever the agent emitted. `section` kept per-item (rollup may
            # legitimately carry a cross-lens merge under its primary lens).
            valid_ids = sections.ids()
            stray = [p["name"] for p in final if p["section"] not in valid_ids]
            with open(PATTERNS_PATH, "w") as fh:
                json.dump({"generated": _now_iso(), "patterns": final}, fh,
                          indent=1, ensure_ascii=False)
            note = f"patterns.json: {len(final)} candidates"
            if stray:
                note += f"  (off-registry section on: {', '.join(stray)})"
            return True, note
    return False, f"rollup produced no valid patterns.json ({last})"


# ---- phase 3: report --------------------------------------------------------

REPORT_PROMPT = (
    "Run the build-profile skill. Read signals.json, sections.json and "
    "patterns.json, and write tui/config/profile.json FRESH (it was reset to an "
    "empty skeleton — build from scratch, do not merge). One Profile section per "
    "registry lens, composed from the fixed components, every section carrying an "
    "explicit id. Each section gets its own `prose` text box (placed first), at "
    "least one data box from signals.json, and — last — a `Painpoints` blocks box "
    "of that lens's painpoints (filter patterns.json by `section`; skip the box if "
    "none). Do NOT write a `forge` Profile section; the full board lives on the "
    "Forge tab. No section may be text-only. Inline values must match the JSON "
    "exactly. Don't ask questions; write the file."
)

_COMPONENTS = {"counters", "bars", "histogram", "blocks", "prose"}


def _profile_check() -> tuple[bool, str]:
    """Structural validation of profile.json against the build-profile rules:
    every descriptive lens present, ids in registry, prose box first, no
    text-only section, known component types. Soft gate — the caller treats a
    warning as non-fatal (a partial Profile beats a blank one)."""
    data = _read_json(PROFILE_PATH)
    if not isinstance(data, dict):
        return False, "not a JSON object"
    secs = data.get("sections")
    if not isinstance(secs, list) or not secs:
        return False, "no sections"
    want = sections.lens_ids()
    seen: list[str] = []
    for s in secs:
        sid = s.get("id")
        if sid not in want:
            return False, f"unknown/forge section id {sid!r}"
        boxes = s.get("boxes")
        if not isinstance(boxes, list) or not boxes:
            return False, f"{sid}: no boxes"
        comps = [b.get("component") for b in boxes]
        bad = [c for c in comps if c not in _COMPONENTS]
        if bad:
            return False, f"{sid}: bad component {bad[0]!r}"
        if comps[0] != "prose":
            return False, f"{sid}: first box is not prose"
        if not any(c != "prose" for c in comps):
            return False, f"{sid}: text-only section"
        seen.append(sid)
    missing = want - set(seen)
    if missing:
        return False, "missing sections: " + ", ".join(sorted(missing))
    return True, f"{len(seen)} sections"


def report(cancel: Cancel = None, on_line: OnLine = None) -> tuple[bool, str]:
    """patterns.json → profile.json (single composition), then validate + retry.

    The caller resets profile.json to the empty skeleton first. A structurally
    invalid profile after the retry is surfaced as a warning, not a hard fail —
    the TUI renders profile.json defensively and a partial mirror still helps."""
    wl = _wrap(on_line, "report")
    last = ""
    for attempt in (1, 2):
        if _cancelled(cancel):
            return False, "cancelled"
        ok, msg = run.headless(REPORT_PROMPT, cwd=REPO_ROOT, add_dir=REPO_ROOT,
                               timeout=REPORT_TIMEOUT, cancel=cancel, on_line=wl)
        last = msg
        if not ok:
            if _is_terminal(msg):
                return False, msg
            continue
        good, detail = _profile_check()
        if good:
            return True, f"profile.json rebuilt ({detail})"
        if attempt == 1 and on_line:
            on_line(f"· profile invalid ({detail}) — retrying")
    good, detail = _profile_check()
    if good:
        return True, f"profile.json rebuilt ({detail})"
    return True, f"profile.json rebuilt with warnings: {detail}"
