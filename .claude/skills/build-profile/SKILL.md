---
name: build-profile
description: Generate or refresh the Jigsmith Profile — write tui/config/profile.json from signals.json + patterns.json. Use after run-miner, as phase 3 of the scanner pipeline, or whenever the developer wants the Profile tab to reflect current data. This is the dynamic content layer; you compose boxes from fixed components with inline data, one section per registry lens.
---

# Build the profile

`tui/config/profile.json` is an agent-authored spec the TUI renders. Fixed: the
top-level tabs (Profile / Workbench) and the component *types*. Everything inside
the Profile is data you write — which boxes per section, layout, inline numbers.

**The sections are the registry lenses, the content is yours.** `sections.json`
fixes the lens list (so the developer can diff themselves over time and each
section has a specialist); within each, compose whatever boxes read best. Don't
invent or drop sections — fill the registry's. If a finding needs a shape no
component renders, run `forge-component` first.

**Values are inline.** Read numbers straight from `signals.json` — never invent
them. They're a snapshot until the next rebuild. Notes are interpretation; charts
are evidence.

## Inputs

Run `run-miner` first if stale. Read `signals.json` (each section is a top-level
key) for the descriptive numbers, and `patterns.json` for the **painpoints**. The
lens map is `sections.json`.

`patterns.json` is dual-purpose: the whole ranked list is the Forge tab's board,
**and** each suggestion's `section` field routes it to a Profile lens. Here you
read it only to **annotate each section with its own painpoints** — filter
`patterns.json[].patterns` where `section == <this lens id>` and render them as a
`blocks` box (below). You still do **not** write a `forge` Profile section — the
full board lives on the Forge tab; here each lens just shows the friction that
belongs to it, next to its data.

## Components (fixed building blocks)

`component` picks the renderer:

| component | shape |
|---|---|
| `counters` | `{"component":"counters","items":[{"value","label","note","hot"}]}` — full-width stat strip |
| `bars` | `{"component":"bars","title","data":[["label",value],...],"note","label_w","bar_w"}` — horizontal bars |
| `histogram` | `{"component":"histogram","title","data":[v0,...],"labels"?,"note"}` — full-width vertical (sizes to width) |
| `blocks` | `{"component":"blocks","title","items":[{rank,name,kind,stack,command,frequency,payback,detail}],"verdict"}` — ranked cards; `"craft":true` → leave-it-alone card. **Also the painpoints box** (below) |
| `prose` | `{"component":"prose","text"}` — the section's own text read (see rule) |

### The painpoints box (per section, from `patterns.json`)

After the data boxes, if this lens has any painpoints in `patterns.json`
(`section == <id>`), render them as a `blocks` box titled `"Painpoints"` so the
mirror shows *what hurts* next to *what's true*. Map each suggestion → a card:

- `name` ← the painpoint's `name`
- `kind` ← `gate.kind` (forge / dispose / suggest)
- `frequency` ← the painpoint's `frequency`
- `payback` ← `gate.payback`
- `command` ← `fix.tool_type` (the suggested form, or `manual`)
- `detail` ← `fix.summary` (the suggested solution, one line)
- `craft: true` when `gate.mechanical_or_craft` starts with "craft" (renders as a
  leave-it-alone card — flagged, not automated)

Skip the box entirely for a lens with zero painpoints — never render an empty one.
The full ranked board (all sections, with the forge hand-off) still lives only on
the Forge tab; this box is just the slice that belongs to this lens.

**Every section carries its own `prose` box — but no section is text-only.** Each
section gets exactly one `prose` box: its narrative read (2–4 sentences: standout
number, the pattern, the so-what for tooling). Place it first, before the data.
Every *other* box still shows data and carries a verbose `note`. A section made of
*only* prose is not allowed — prose interprets the data boxes, it never replaces
them.

## Layout grammar

A section's `boxes` is an ordered list; an entry is a single full-width box or a
row grid `{"row": [box, box]}` (2 or 4 columns). Counters/histograms are always
full width.

## Spec shape

```json
{ "generated": "<YYYY-MM-DD>",
  "sections": [ {"id": "usage", "title": "Usage", "boxes": [ ...box specs... ]}, ... ] }
```

**Every section needs an explicit `id`** — slug-safe, matching the registry
(`usage`, `sessions`, `context`, `harness`, `shell`). It's the TabPane id
+ palette jump target. The loader backfills from title as a net, but write it
explicitly and keep it stable across rebuilds. **Do not write a `forge` section** —
that lens is a rollup that feeds the Forge *tab* (`patterns.json`), not the Profile.

## The sections (from `sections.json`)

| id | title | what it carries (from `signals.<id>`) |
|---|---|---|
| `usage` | Usage | overview + **by_agent split**, tokens, models, temporal, per-project |
| `sessions` | Sessions & orchestration | parallel/swarm, chains/relaunch tax, responsiveness/babysitting |
| `loop` | Loop | tool-calls/turn + leash, explore→edit→verify grammar, delegation fan-out, interrupt/re-steer |
| `context` | Context | memory weight, repeated preambles, MCP surface configured-vs-exercised |
| `harness` | Harness | inventory ⋈ usage — installed-vs-used skills/agents/MCP (dead config) |
| `shell` | Shell & manual work | vocabulary, session correlation, installed-vs-used tools |

The Profile is the **mirror** — these six descriptive lenses only. The `forge`
rollup is NOT a Profile section; its ranked candidates live on the **Forge tab**
(read from `patterns.json`), so the Profile doesn't duplicate them. The cross-agent
`by_agent` read in `usage` and the join reads in `harness` / `shell` are
load-bearing — that's where this developer's workflow shows up.

## Method

1. Per section, lead with the section's own `prose` box (its text read), then a
   `counters` strip of headline numbers, then charts, and **last** the
   `Painpoints` box (from `patterns.json`, this lens's slice) when there is any.
2. Bind each chart to inline data from `signals.json`, and each painpoint card to
   `patterns.json`. Give every data box a verbose `note`. Don't automate the craft
   away — a craft painpoint renders as a leave-it-alone card (`craft: true`).
3. Write `tui/config/profile.json`. Validate it loads:
   ```bash
   uv run python -c "from tui.config import load_profile; print([s['id'] for s in load_profile()])"
   ```

## Rules

- Every section needs an explicit, registry-matching `id`, exactly one `prose`
  box (its own text read, placed first), and at least one data box. No section is
  text-only.
- A section's painpoints come from `patterns.json` (filtered by `section`),
  rendered as a `blocks` box titled `Painpoints`, placed last. Skip it when the
  lens has none — don't fabricate friction to fill it.
- Inline values must match `signals.json` (data) and `patterns.json` (painpoints)
  — read, don't guess.
- **Two rebuild modes:**
  - *Pipeline* (`r` / Run scanner): `report_phase` blanks `profile.json` to an
    empty skeleton first (prior saved as `.bak`) — build FRESH, nothing to merge.
  - *Manual* (this skill run directly): `profile.json` is the developer's — surgical
    update, preserve hand-edits, propose big restructures (`tend-workbench`), but
    always refresh inline numbers (stale values lie).
