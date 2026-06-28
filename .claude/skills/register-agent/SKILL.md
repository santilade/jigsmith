---
name: register-agent
description: Teach Jigsmith to inspect (and optionally run) a coding agent it doesn't ship with — hermes, openclaw, pi, or any new CLI. Probes the agent's history location, format, run commands, and config paths, then writes a manifest. Most agents need zero code; only a genuinely new history format needs a parser. Use when the developer wants the mirror to mine an agent beyond the built-in claude/opencode/codex.
---

# Register an agent

Jigsmith treats **agents as data, formats as code**. Adding an agent it can
*inspect* is usually just writing a manifest — no Python — because most agents
reuse a history format Jigsmith already parses.

## The manifest

Write `~/.config/jigsmith/agents/<id>.json` (create the dir). Shape — both roles
are optional; fill what the agent supports:

```jsonc
{
  "id": "hermes", "label": "Hermes", "tag": "hm", "cli": "hermes",
  "run": {                                    // RUN role — only if it'll be the default agent
    "headless":        ["hermes", "run", "--yes", "{prompt}"],     // MUST auto-approve tools — see below
    "headless_stream": ["hermes", "run", "--yes", "--json", "{prompt}"],  // optional: live progress
    "stream_format":   "hermes-json",          // keys the run.py parser; omit if no stream runner
    "interactive":     ["hermes"]              // {prompt} {cwd} {add_dir} {timeout} substitute
  },
  "inspect": {                                // INSPECT role — to mine its history
    "history":  {"glob": "~/.hermes/sessions/**/*.jsonl", "format": "openai-jsonl"},
    "settings": {"config": "~/.hermes/config.json", "mcp": "~/.hermes/config.json",
                 "agents": "~/.hermes/agents", "memory": "AGENTS.md"}
  }
}
```

## How to fill it (probe, don't guess)

1. **CLI + run commands** — `which <cli>`; read `<cli> --help`. Find the headless
   (one-shot, non-interactive — often `run`/`exec`/`-p`) and interactive
   invocations. Use the `{prompt}`/`{cwd}`/`{add_dir}`/`{timeout}` placeholders.
   **Auto-approve tools in the headless runner.** A default agent runs the
   scanner's analyze/report phases, which must *write files* (`patterns.json`,
   `profile.json`). Most CLIs gate edits behind a permission prompt and, with no
   TTY, **auto-reject** them — the phase runs, writes nothing, and fails with
   "patterns.json missing". Find the agent's skip-permissions flag in `--help`
   (`--dangerously-skip-permissions`, `--yes`, `--auto-approve`, `--no-confirm`, …)
   and put it in the `headless` argv. Confirm with the write test in **Verify**.
2. **History location** — find where it writes session transcripts (commonly
   `~/.<agent>/sessions`, `~/.local/share/<agent>`, or `~/.config/<agent>`). Write
   a recursive glob.
3. **History format** — open a transcript and match it to a known parser:
   - one JSON object per line, Claude-style (`type`, `message.content` blocks,
     `sessionId`) → `claude-jsonl`
   - one JSON object per line, OpenAI-style messages (`role`, `content` text
     blocks, `function_call`) → `openai-jsonl` (codex and most newer CLIs)
   - per-session JSON files with `role` + `parts` → `opencode-store`
   If it matches one of these, set `format` to it and you're **done — no code**.
4. **Settings paths** — config file, MCP definitions, agents/skills dir, memory
   file (for the Harness inventory join). Best-effort; omit what doesn't exist.

## Optional: live progress for the default agent (a streaming parser)

The scanner pop-up tails the running agent. To show its steps live, give the
manifest a `headless_stream` runner that emits **newline-delimited JSON events**
(usually a `--json`/`--format json` flag) plus a `stream_format` id, then add one
parser entry in `core/run.py`:

1. Write `_parse_<id>_stream(evt: dict) -> str | None` that maps one decoded event
   to a short log line (or `None` to skip it) — session-start, assistant text, and
   tool-use are the useful ones (copy `_parse_opencode_stream` as a template; reuse
   `_tool_brief` for the tool argument).
2. Register it: `_STREAM_PARSERS["<stream_format>"] = _parse_<id>_stream`.

No stream runner/parser → the run still works, it just tails nothing (falls back to
a plain blocking run). The `headless` runner is what actually has to succeed.

## If the history is a NEW format (the only code case)

If no parser fits, add one:

1. Create `core/parsers/<format>.py` that `@register("<format>")`s a generator
   `parse(paths, agent_id) -> Iterable[Event]` (copy `claude_jsonl.py` as a
   template — emit `Event`/`ToolCall` from `core.events`, map raw tool names to the
   normalized `kind` taxonomy, scrub bash commands).
2. Import it in `core/parsers/__init__.py` so it self-registers.
3. Set the manifest's `format` to your new id.

## Verify

**1. Static check** — the manifest loads and both roles resolve:

```bash
uv run python -c "
from core import agents
m = agents.by_id('<id>')
print('can_inspect', m.can_inspect(), 'files', len(m.history_paths()), 'fmt', m.history_format())
print('can_run', m.can_run())
"
```

**2. Integration test (RUN role)** — `can_run` only checks the binary is on PATH;
it does **not** prove a headless run can write a file. If this agent will be the
default, drive `run.headless` for real and confirm the file lands — this is the
exact path the scanner takes, and the test that catches the auto-reject trap:

```bash
uv run python -c "
import os, tempfile
from core import run
d = tempfile.mkdtemp()
lines = []
ok, msg = run.headless('Create a file named proof.txt containing the word forged, then stop.',
                       cwd=d, add_dir=d, timeout=120, on_line=lambda l: lines.append(l))
wrote = os.path.exists(os.path.join(d, 'proof.txt'))
print('ok', ok, '| msg', msg, '| file written', wrote)
print('streamed', len(lines), 'lines:', lines[:6])
"
```

Both must hold: **`file written True`** (the skip-permissions flag is right — a
`False` here is the auto-reject trap, fix the `headless` argv) and, if you wired a
stream runner, **`streamed > 0`** (the parser id matches `stream_format`). The
agent may resolve the path under `add_dir` rather than `cwd` — check both.

**3. Inspect** — add it under **Settings → Agents to inspect** (or it's picked up
automatically if no inspect-set is saved), and run `run-miner`. Its events join the
normalized stream and show up in the `by_agent` split + every section.
