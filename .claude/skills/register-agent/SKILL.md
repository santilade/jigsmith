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
    "headless":    ["hermes", "run", "{prompt}"],
    "interactive": ["hermes"]                  // {prompt} {cwd} {add_dir} {timeout} substitute
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

## If the history is a NEW format (the only code case)

If no parser fits, add one:

1. Create `core/parsers/<format>.py` that `@register("<format>")`s a generator
   `parse(paths, agent_id) -> Iterable[Event]` (copy `claude_jsonl.py` as a
   template — emit `Event`/`ToolCall` from `core.events`, map raw tool names to the
   normalized `kind` taxonomy, scrub bash commands).
2. Import it in `core/parsers/__init__.py` so it self-registers.
3. Set the manifest's `format` to your new id.

## Verify

```bash
uv run python -c "
from core import agents
m = agents.by_id('<id>')
print('can_inspect', m.can_inspect(), 'files', len(m.history_paths()), 'fmt', m.history_format())
print('can_run', m.can_run())
"
```

Then add it under **Settings → Agents to inspect** (or it's picked up
automatically if no inspect-set is saved), and run `run-miner`. Its events join the
normalized stream and show up in the `by_agent` split + every section.
