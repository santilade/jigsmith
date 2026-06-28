# Jigsmith — architecture & contracts

This is the load-bearing reference: the data contracts every layer agrees on.
`CLAUDE.md` is the operating constitution (how the agent behaves); this file is
the wiring (what the pieces are and how they connect). Read both before forging.

## The one pipeline

```
 INGEST            SIGNALS              ANALYZE            RENDER
 (deterministic)   (deterministic)      (agentic)          (deterministic)

 agent history ─┐
 shell history ─┼─► Event stream ─► signals.json ─► profile.json ─► TUI
 inventory  ────┘   (normalized)     (+ section      (+ rack rows)    (reads
 (configs+pkgs)                       slices)                          only json)
```

One hard rule governs the whole thing — the **quarantine**:

> Deterministic code (ingest, signals, render) **never calls an agent**. The
> agent runs only at an explicit, user-triggered action, writes its result to
> disk, and deterministic code then only *reads* that result. The system never
> re-derives at runtime what stored data already knows.

The single sanctioned crossing: the user presses **Run** (or runs the
`scanner` skill), which shells out to the default agent for the ANALYZE
phase. Gated, explicit, writes JSON. Nowhere else.

## Layer 1 — INGEST: the normalized Event stream

Every agent and every shell is read by a **parser** and emitted as one common
vocabulary, so all downstream code is agent-agnostic. The key decoupling:

> **Agents are data; formats are code.** A new agent that reuses a known log
> format = a manifest, zero code. Only a genuinely new format needs a parser.

### Agent source adapter = manifest (data) + format (code)

A manifest (`core/agents/builtin/*.json`, or user manifests under
`~/.config/jigsmith/agents/*.json`) declares both roles an agent can play:

```jsonc
{
  "id": "codex", "label": "Codex CLI", "tag": "cx", "cli": "codex",
  "run": {                                   // RUN role (default agent only)
    "headless":    ["codex","exec","--cd","{cwd}","{prompt}"],
    "interactive": ["codex","--cd","{cwd}"]   // optional; prompt prefilled if present
  },
  "inspect": {                               // INSPECT role (agents to inspect)
    "history":  {"glob": "~/.codex/sessions/**/*.jsonl", "format": "openai-jsonl"},
    "settings": {                            // for the harness inventory ⋈ usage join
      "config": "~/.codex/config.toml",
      "mcp":    "~/.codex/config.toml",
      "agents": "~/.codex/prompts",
      "memory": "AGENTS.md"
    }
  }
}
```

Run-argv templates substitute `{prompt} {cwd} {add_dir} {timeout}`. Capabilities
are independent: `can_run` needs `cli` on PATH + a `run.headless`; `can_inspect`
needs `inspect.history` to resolve + a parser for its `format`. You **inspect**
many agents; you **run** one default.

### Format parsers (keyed by format, shared across agents)

`core/parsers/` registers `FORMAT -> parser(paths) -> Iterable[Event]`. Built in:
`claude-jsonl`, `openai-jsonl` (codex & most newer CLIs), `opencode-store`,
and `shell-history` (zsh/bash/fish). Hermes/openclaw/pi reusing any of these need
no code.

### The Event / Session / ShellCmd schema (`core/events.py`)

```
Session   id, agent, project, raw_project, cwd, start, end,
          models[], entrypoint, git_branches[]
Event     session_id, agent, ts (epoch utc), role(user|assistant|system),
          kind(prompt|response|tool_call|summary|meta),
          text, is_real_prompt, is_sidechain,
          tokens{in,out,cache_create,cache_read}, model,
          tool: ToolCall|None, project, raw_project, cwd, git_branch
ToolCall  raw_name, kind, summary, detail{}
          kind ∈ read|edit|write|search|bash|web|subagent|skill|mcp|todo|other
          detail examples: bash→{command,verb,git_sub}; skill→{skill};
                           subagent→{subagent_type}; mcp→{server,tool}
ShellCmd  ts (epoch|None), shell(zsh|bash|fish), verb, command(scrubbed),
          raw_redacted, reliable(bool)
```

Normalizing each agent's tool names into `ToolCall.kind` is what makes
cross-agent comparison possible (`Edit`/codex-edit/opencode-edit → `edit`).

## Layer 2 — SIGNALS: deterministic, per section

`core/signals/<section>.py` consumes the Event stream (+ inventory) and emits its
slice of `signals.json`. Each section owns its own signals — no reaching into
another's slice. The full signal catalog these must preserve is the union of the
old `aggregates.json` + `timeline.json` + `shell.json` keys (see git history of
`poc-extraction/`); nothing is dropped, only reorganized under section keys.

### The `inventory ⋈ usage` join (the core primitive)

Two sections (Harness, Shell) take a **second input** — what's *installed* — and
their value is the join with what's *used*:

| quadrant | meaning | recommended `jig_kind` |
|---|---|---|
| installed + used | earning its keep | — |
| installed + unused | clutter / dead weight | `dispose` |
| used + no tool (manual) | doing it by hand | `forge` |
| used + suboptimal tool | reaching for wrong thing | `suggest` |

"Unused" is **window-bounded** — signals report `install + use-count + lookback`;
the agent (judgment) decides dead vs rare-but-load-bearing. Package
inventory uses `brew leaves` / top-level `npm -g` (chosen tools), never the
dependency closure.

## Layer 3 — ANALYZE: agentic, one specialist per section

The section registry (`sections.json`, data) drives a **fan-out**: one agent per
section reads only its signal slice + its rubric (`knowledge/<section>.md`) and
emits a section spec (boxes) for `profile.json`, plus zero or more suggestions in
a **uniform shape**:

```jsonc
{ "title": "...", "evidence": "the number that proves it",
  "jig_kind": "forge|dispose|suggest", "section": "shell",
  "frequency": "...", "est_per_instance_cost": "...", "payback": "..." }
```

The **Recommendations rollup** runs last (not a parallel section): it collects
every section's suggestions, dedups, ranks by payback, and writes `patterns.json`
(the **Forge tab's** candidates) + the rack candidate rows. It is NOT a Profile
section — the Profile is the mirror; the Forge tab owns the candidates. Payback
shown, always: `frequency × per_instance_cost  vs  build + upkeep`.

### Section registry (`sections.json`)

```jsonc
[ { "id": "usage",    "title": "Usage",                  "signals": ["usage"],    "rubric": "knowledge/usage.md",    "analyzer": "usage-analyst" },
  { "id": "sessions", "title": "Sessions & orchestration","signals": ["sessions"], "rubric": "knowledge/sessions.md", "analyzer": "sessions-analyst" },
  { "id": "loop",     "title": "Loop",                   "signals": ["loop"],     "rubric": "knowledge/loop.md",     "analyzer": "loop-analyst" },
  { "id": "context",  "title": "Context",                "signals": ["context"],  "rubric": "knowledge/context.md",  "analyzer": "context-analyst" },
  { "id": "harness",  "title": "Harness",                "signals": ["harness"],  "rubric": "knowledge/harness.md",  "analyzer": "harness-analyst" },
  { "id": "shell",    "title": "Shell & manual work",    "signals": ["shell"],    "rubric": "knowledge/shell.md",    "analyzer": "shell-analyst" },
  { "id": "forge",    "title": "Forge Candidates",       "rollup": true,          "rubric": "knowledge/forge.md",    "analyzer": "recommendations" } ]
```

Sections are **fixed lenses, agent-authored content**. The list is stable (so you
can re-run and diff yourself over time); what fills each section is dynamic.
Adding a lens = a registry entry + a rubric, zero renderer code.

## Layer 4 — RENDER: the fixed component vocabulary (unchanged)

`profile.json` is the agent-authored render spec; the TUI reads only it (never
the signal json). Schema and components preserved verbatim from the prior build:

```jsonc
{ "generated": "ISO", "sections": [
  { "id": "slug", "title": "...", "boxes": [
    { "component": "...", ... },           // a box
    { "row": [ {box}, {box} ] }            // 2- or 4-col grid
  ] } ] }                                  // no "forge" section — it's the Forge tab
```

Component types (fixed; new TYPE is rare, via `forge-component`):
- `counters` — `{items:[{value,label,note,hot}]}` full-width stat strip
- `bars` — `{title,data:[[label,value]],note,label_w,bar_w}` horizontal bars
- `histogram` — `{title,data:[v…],labels?,tones?,height,note}` full-width vertical
- `blocks` — ranked cards `{items:[{rank,name,kind,stack,command,frequency,payback,detail,craft}],verdict}`
- `prose` — `{text}` (discouraged; data boxes carry meaning in a verbose `note`)

Tones map to theme roles via `tone_colors` (`warn/high/hot`→warning,
`regular/mid/data`→data, `dim/low/mute`→note). Render references roles, not hex.

## The two surfaces (the dashboard)

- **Profile (home)** — the mirror: the fixed section-lenses, agent-authored,
  rendered from `profile.json`. Press **Run** to mine→analyze→report.
- **Workbench (the rack)** — forged jigs, disposability visible.
  (This is the *jig rack*, not config management — that scope was dropped; tools
  like CC Switch already own cross-assistant config deploy.)

Forge is the *action* on a candidate, not a peer surface: pick a ranked
candidate → suspend → hand to the default agent's interactive session prefilled
with a `forge-jig` brief → on return, deterministic re-read of the rack.

## Settings (the only agent config)

Two choices, persisted in `settings` (sqlite k/v):
- **default agent** — runs headless (analyze) + interactive (forge). One.
- **agents to inspect** — whose history + inventory the mirror reads. Many.
- (shells to inspect follow the same manifest model: a shell is just an
  inspect-source with a history location + `shell-history` format.)

New agents/shells self-onboard via the `register-agent` / `register-shell`
skills, which write a manifest (and a parser only if the format is new).
