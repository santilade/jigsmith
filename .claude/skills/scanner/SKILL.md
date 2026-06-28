---
name: scanner
description: The full scanner pipeline — mine the developer's agent-driving history + inventory (deterministic), analyze each section lens into ranked, payback-scored forge/dispose/suggest candidates (agentic, one analyst per section), and rebuild the Profile (agentic). One pass, three phases. Use to find what's worth forging or disposing, or to test Jigsmith's core gate. Writes patterns.json and refreshes the Profile.
---

# Scanner (the pipeline)

One thing, three phases, always run together:

| phase | kind | does | output |
|---|---|---|---|
| 1. **mine** | deterministic | ingest every inspected agent + shell + inventory → all section signals | `signals.json` |
| 2. **analyze** | agentic | one analyst per section judges its lens → ranked forge/dispose/suggest candidates | `patterns.json` |
| 3. **report** | agentic | compose the candidates + findings into the Profile | `tui/config/profile.json` |

**Quarantine intact, orchestration deterministic.** `core.scan` (plain Python)
*sequences* phases 2-3: it loops the registry lenses, runs one analyst per lens in
parallel, validates + retries each, then folds them with one rollup agent. Only the
*judgment* crosses to the agent — the loop, the validation, and the writes are
Python. Phase 1 writes `signals.json`; phase 2 reads it and writes `patterns.json`;
phase 3 reads both. Each phase only reads the prior phase's file.

**Two ways in.** From the TUI (`r`) the fan-out is `core.scan.analyze()` — you
arrive as a *single lens analyst*, handed your rubric + signal slice inline, and you
write only your lens's slice of suggestions. Run interactively (a human invokes this
skill), you play every role in turn yourself, following the same contract below. The
uniform shape and the per-lens discipline are identical either way.

**This pipeline is the gate.** Jigsmith's bet is unproven until a real, recurring
pattern with payback beating build cost falls out of the data. (It already does:
dead skills installed-but-never-run, raw `git` while `lazygit` sits idle, hours of
babysitting wait. Phase 2 is where you name and rank those.)

## Phase 1 — mine (deterministic)

Run the `run-miner` skill, or directly:

```bash
uv run python -m core      # → signals.json
```

`signals.json` is keyed by the sections in `sections.json`. Read it whole, then
work section by section.

## Phase 2 — analyze (agentic judgment, deterministic fan-out)

`core.scan.analyze()` loops **each non-rollup section** of `sections.json` and runs
a focused analyst per lens, in parallel (bounded). Each analyst is handed, inlined
in its prompt, ONLY:

- that section's slice of `signals.json` (the `signals` key in the registry), and
- that section's **rubric** (`knowledge/<section>.md`) — the curated, dev-tended
  best-practice for that lens (MCP hygiene, context engineering, etc.). The rubric
  is how you stay current without guessing; if it's thin, say so and lean on the
  data.

Each analyst owns its lens — the slice is all you get, so reaching into another
lens is impossible by construction. Do **local** source-checks only; the *rollup*
does the single web pass (don't each hit the network). The orchestrator validates
your output against the uniform shape and retries once if it's missing or
malformed — write the file, in shape, or it's redone.

### The four engineering disciplines (the framing)

The lenses sort into the four disciplines of driving an agent — name findings in
these terms so the dev sees *which* discipline a pattern belongs to:

- **prompt engineering** — what you type each turn (the brief, the corrections):
  read in `context`'s `repeated_preambles` and `loop`'s re-steer cadence.
- **context engineering** — what enters the window (`context`): memory, MCP surface.
- **harness engineering** — the static rig (`harness`): installed skills/agents/MCP.
- **loop engineering** — the inner agentic loop (`loop`): how far and how well it
  iterates on one prompt — leash, tool grammar, delegation, interrupts.

(`usage` and `shell` are descriptive context, not a discipline each.)

### The lenses (one analyst each)

1. **usage** — what/when/how-much. Volume, tokens, models, cadence, and the
   **`by_agent` split**: which agent for which job (Claude for deep multi-tool,
   opencode for quick edits?). Cross-agent divergence is a finding, not a forge.
2. **sessions** — how you drive (MACRO). Session shape; sub-agents; **parallelism**
   (`overlap_seconds_same_project` vs `cross_project` → manual sub-agent swarm on
   ONE project vs juggling MANY); consecutive **chains** + `/clear`/`/exit` =
   re-onboarding tax (forge-able); **responsiveness** (`total_wait_hours`,
   `pct_active_wall_waiting`, p90 turn wait) = babysitting, which reframes payback
   (every wait second is the developer idle).
3. **loop** — the inner agentic loop (MICRO, *loop engineering*). Within ONE turn:
   `tool_calls_per_turn` + `tool_depth_buckets` (the **leash**); `cycle` tool grammar
   — `verify_after_change` (edit→bash, the self-correction loop; low vs edits = a
   post-edit check candidate) and `explore_then_act`; `delegation_turns`/
   `max_fanout_in_turn` (fan-out within a turn); `resteer` (`quick_short_resteers`,
   `interrupts`, `loop_control_commands`) = the human cutting in mid-loop. Don't
   double-count with sessions' macro swarm — if both fire, it's one candidate.
4. **context** — what enters the window. `memory_files` weight, `repeated_preambles`
   (re-explaining the same setup → a memory/skill candidate), `mcp_surface`
   configured-vs-exercised (dead surface burns tokens every turn).
5. **harness** — the static rig. The **`inventory ⋈ usage` join**: skills/agents/MCP
   installed but never invoked (dispose candidates), most-used (keep). "Unused" is
   window-bounded — judge dead vs rare-but-load-bearing, don't auto-condemn.
6. **shell** — manual work. Vocabulary, `correlation` (launcher vs parallel
   workbench; verbs that spike *during* a live session = deliberate division of
   labor, don't propose handing back), and the **package join**: installed-unused
   tools, and used-suboptimal (raw `git` × N while `lazygit` idle → suggest).

### The discipline (every lens)

- **Name patterns in the developer's terms** — what they're *doing*, not the tool.
- **Mechanical vs craft.** Craft (thinking, judgment, feel) is flagged, never
  automated away.
- **Payback, shown.** `frequency × per_instance_cost` vs `build + upkeep`. Most
  patterns aren't worth a jig. Flag thin-N as directional, not proven.
- **Rank by cumulative cost (the 90%), not loudness.**
- **Surface every painpoint, not just forge-able ones.** A lens's friction is
  more than build candidates: dead config to **dispose**, and habits worth a
  **manual** nudge (no tool, just stop doing X — `gate.kind: suggest`,
  `fix.approach: manual`). Emit those too. The Forge tab is a painpoint *board*,
  not only a build queue. The one bar: a painpoint always carries a **suggested
  solution** (forge / download / dispose / manual). If the honest call is "nothing
  to do, just noting it," that's a *descriptive finding* (→ Profile prose), not a
  painpoint — don't manufacture a fix to smuggle an observation into the board.

### patterns.json is dual-purpose

The suggestions you emit feed **two** surfaces, both keyed off the `section`
field: the **Forge tab** (the whole ranked board) and each **Profile section's
painpoint annotation** (`build-profile` filters `patterns.json` by `section`). So
set `section` correctly on every suggestion and keep `painpoint` legible on its
own — it is read in the mirror next to that lens's data, not only on the Forge tab.

### The uniform suggestion shape

Every analyst emits zero or more suggestions in ONE shape, so the rollup can merge
and rank across sections. Three bands: **narrative** (what hurts, in the dev's
terms), **fix** (the proposal), **gate** (the discipline / scoring).

```json
{
  "name": "Raw git by hand while lazygit sits idle",   // short title
  "section": "shell",

  // — narrative: the what/why, in the developer's terms —
  "painpoint": "You drive git from the CLI ~8×/day — stage/branch/commit nav by hand — while a sharper tool is installed and never touched.",
  "frequency": "git ×38 over 15 active days (~2.5/day); bursty around commits",
  "evidence": "shell verb git ×38 (commit 22, clone 9); lazygit installed, 0 uses; 94% run during a live session = hand-driven.",

  // — fix: the proposal (the dev confirms `approach` at forge time) —
  "fix": {
    "approach": "download",       // custom | download | manual
    "tool_type": "CLI",           // one, or "+"-joined: memory | skill | hook | agent config | script | CLI | TUI | alias
    "summary": "Adopt lazygit for the staging/review flow you do by hand.",
    "what": "lazygit (jesseduffield/lazygit, 50k★) — visual git TUI",   // download: name it; custom: what to build; manual: what to change
    "why": "covers the ~8×/day nav; zero build cost",
    "where": "global PATH + alias `lg`"   // where it lives on the bench
  },

  // — gate: the 90% discipline (shown as a badge, not prose) —
  "gate": {
    "kind": "suggest",            // forge | dispose | suggest
    "mechanical_or_craft": "mechanical",
    "payback": "directional — try lazygit a week",
    "confidence": "medium"
  }
}
```

`fix.approach`: the **one axis** the forge agent confirms with the dev —
**custom** (build a new jig), **download** (adopt an existing tool), or **manual**
(a habit/config change, nothing to build). The dev may override (e.g. fix says
download but they prefer custom); that's the confirmation step, not a failure.

`fix.what`: in one line, name the concrete thing — for **download**, the specific
tool and which slice of the pattern it kills; for **custom**, what to build; for
**manual**, what to change. Don't invent a download match; only name a tool the
source check actually surfaced.

`gate.kind`: **forge** (used + no tool → build), **dispose** (installed + unused →
retire), **suggest** (used + suboptimal, or a habit change). The join is the engine
of forge *and* dispose candidates. (`fix.approach` and `gate.kind` are related but
distinct: a `forge` candidate is almost always `approach: custom`, a `dispose` has
no fix, and a `suggest` can be `download` or `manual`.)

### Source check — does a fix already exist? (painpoint FIRST, type LAST)

Decide in this order, and **never let the form pre-filter the search**: first hunt
for anything that already addresses the *painpoint*, whatever shape it takes; only if
nothing fits do you commit to building; and only *then* do you pick a form. The old
trap was deciding "this is a skill/memory thing → custom" up front, which stops a
skill-shaped friction from ever being matched against a skill that already exists.

1. **Look up the painpoint (type-agnostic).** Cheapest signal → widest net:
   - **Local inventory — per analyst, no web.** A known tool **installed-but-idle**
     for this pattern (the `lazygit ×0 while git ×38` case) is the strongest match —
     it's already on disk. Flag it for the rollup.
   - **Web pass — over the deduped list, in the rollup.** One agent, one pass, no N×
     duplication. Derive 2–4 terms from `name` + painpoint and search **every**
     relevant registry, not just code hosts:
     - **CLIs / TUIs / apps** — `gh search repos "<terms>" --sort stars --limit 10`;
       `WebFetch https://github.com/trending?since=weekly`.
     - **Skills / agents** — the official skill marketplace: `gh search repos
       "<terms>" --owner anthropics`, or browse the `anthropics/skills` `skills/`
       tree. A skill that already exists is a **download**, not a custom build.
     - **MCP servers** — the MCP registries, when the friction is a missing capability.
   - Match bar: it must actually *solve the painpoint* (not keyword overlap), carry
     real traction (≳1k★, trending, or official), and show recent maintenance.

2. **Evaluate fit → set `fix.approach`.**
   - **Good fit** → `fix.approach: download`, `fix.what` =
     `"<owner/repo or skill> (<traction>) — <what it is>; <slice of the painpoint it kills>"`,
     `fix.tool_type` = that thing's own form. Done — skip the table.
   - **Partial / no fit** → `fix.approach: custom` (or `manual` for a pure habit/config
     change). Don't force a bad match. Now — and only now — pick the form (next section).

Per-lens analysts set `fix.approach` **provisionally** (local signal + judgment); the
rollup's web pass settles it. If `gh` is absent or the web is unreachable, fall back to
local inventory + judgment and mark `gate.confidence` down a notch — never block on the net.

### fix.tool_type — the form the fix takes

A **download** brings its own form (set by the source check above). For **custom** /
**manual**, walk this table top-to-bottom and take the **first** row that fits —
ordered lightest → heaviest; the cheapest form that kills the pattern wins
(disposability). The one place to reach past "lightest" on purpose is the
**`CLI + skill`** pairing below — when the pattern has both a mechanic and a
judgment, that combo is usually the right answer, not over-build.

| If the pattern is… | tool_type | e.g. |
|---|---|---|
| the agent repeatedly **needing the same fact/rule/preference** you keep re-typing | **memory** | a line in `CLAUDE.md` / an output-style |
| a **judgment/procedure** the agent should follow on request | **skill** | a `.claude/skills/<name>` |
| something that must **fire automatically on an event** (pre-commit, on-save, session-start) | **hook** | a `settings.json` hook |
| a **specialized sub-agent** with its own brief/tools | **agent config** | a `.claude/agents/<name>` |
| deterministic **state/mechanics** run on demand (parse, tally, transform) | **script** | a Python script |
| a fitted **command surface** over that mechanic | **CLI** | a small CLI wrapper |
| a fitted **interactive surface** (browse/monitor) | **TUI** | a Textual app / Profile box |
| a pure **shell shortcut** for a verbose command you retype | **alias** | a shell alias |

The **memory** row comes first on purpose: if the friction is the agent not knowing
something (a convention, a path, a preference, a "always do X here"), the fix is a
remembered line, not a built tool — cheapest possible jig. Only escalate to skill /
hook / code when a fact alone won't do it.

**A fix can be a combination.** One pattern often needs several forms working
together — e.g. a `CLAUDE.md` line (the convention) **+** a `skill` (the procedure)
**+** a `hook` (to fire it automatically). When so, set `fix.tool_type` to the combo
as a `+`-joined string, lightest-first: `"memory + skill + hook"`. Use a combo only
when the pieces serve **one** outcome; if they solve two unrelated frictions, that's
two candidates — split them.

**Favor `CLI + skill` — the best of both worlds.** When a painpoint has a *repeatable
mechanical core* (parse, tally, transform, drive a tool — deterministic work) **and**
a *judgment layer* (knowing when and how to apply it), the strong answer is a small
**CLI** carrying the mechanic **+** a **skill** carrying the judgment that invokes it.
The CLI keeps the deterministic part out of the model (cheap, exact, testable); the
skill keeps the agent in control of *when* to run it. Encourage this pairing wherever
it fits — it beats a skill that re-derives mechanics every run, and a bare CLI the
agent never remembers to use. (This is the deterministic/agentic split in miniature:
mechanics in the CLI, judgment in the skill.)

### Rollup → patterns.json

`core.scan` collects + validates every analyst's suggestions into one candidate
list and hands it to the **recommendations rollup** (the registry's `forge`
section, `rollup: true`) inline. You **dedup** (the same idea surfaces in multiple
lenses), run the one **web source-check** over download-eligible candidates, rank by
payback/cumulative cost, and write:

```json
{ "generated": "<ISO8601 at write time>", "patterns": [ <suggestion>, ... ] }
```

The descriptive findings (session shape, swarm/relaunch behaviour, cross-agent
split) are NOT suggestions — they don't go in patterns.json; they go straight into
the Profile sections in phase 3, read from `signals.json`. Don't drop them.

Keep each suggestion's `section` accurate: phase 3 reads `patterns.json` back and
annotates each Profile lens with *its* painpoints (the friction) right beside that
lens's descriptive data. A mis-tagged `section` strands a painpoint under the wrong
mirror.

## Phase 3 — report (agentic — TUI)

Run `build-profile`: one Profile section per **descriptive** registry lens
(`usage`, `sessions`, `context`, `harness`, `shell`), composed from the fixed
components. The `forge` rollup is NOT a Profile section — its ranked candidates
(`patterns.json`) are the **Forge tab's** data, so the Profile (the mirror) doesn't
duplicate them. The TUI then reads only the spec (quarantine).

## After

- Surface the ranked list. For **forge** candidates that clear payback, offer
  `forge-jig`. For **dispose**, offer `dispose-jig`. For **suggest**, just report.
- Add strong forge candidates to the rack as `status="candidate"` (see `forge-jig`).
- **Do not auto-build or auto-delete.** The dev decides.
