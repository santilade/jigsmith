"""The uniform suggestion shape — the canonical contract + its validator.

Every analyst emits suggestions in ONE shape so the rollup can merge and rank
across lenses. The shape lived only in prose in `scanner/SKILL.md`; it lives here
now so there is a single source of truth the orchestrator can *enforce*, not just
describe. `SHAPE_CONTRACT` is inlined into each analyst prompt; `normalize` /
`normalize_many` validate what comes back (defensive defaults in the spirit of
ai-code-review's `Finding.from_dict`, so one sloppy field never sinks a run).
"""
from __future__ import annotations

APPROACHES = {"custom", "download", "manual"}
KINDS = {"forge", "dispose", "suggest"}
MECH = {"mechanical", "craft"}

# The contract handed to every analyst. Mirror of the shape `normalize` enforces —
# keep the two in lockstep.
SHAPE_CONTRACT = """\
Each suggestion is ONE JSON object with three bands — narrative (what hurts, in
the developer's terms), fix (the proposal), gate (the discipline / scoring):

{
  "name": "Raw git by hand while lazygit sits idle",   // short title
  "section": "<this lens id>",                          // set to YOUR lens

  // — narrative —
  "painpoint": "You drive git from the CLI ~8×/day by hand while a sharper tool sits installed and untouched.",
  "frequency": "git ×38 over 15 active days (~2.5/day); bursty around commits",
  "evidence": "shell verb git ×38; lazygit installed, 0 uses; 94% run during a live session = hand-driven.",

  // — fix: the proposal —
  "fix": {
    "approach": "download",   // custom | download | manual
    "tool_type": "CLI",       // memory | skill | hook | agent config | script | CLI | TUI | alias  (or "+"-joined)
    "summary": "Adopt lazygit for the staging/review flow you do by hand.",
    "what": "lazygit (jesseduffield/lazygit, 50k★) — visual git TUI",
    "why": "covers the ~8×/day nav; zero build cost",
    "where": "global PATH + alias `lg`"
  },

  // — gate: the 90% discipline (a badge, not prose) —
  "gate": {
    "kind": "suggest",                  // forge | dispose | suggest
    "mechanical_or_craft": "mechanical",// mechanical | craft  (never auto-forge over craft)
    "payback": "directional — try lazygit a week",
    "confidence": "medium"              // low | medium | high
  }
}

- fix.approach: download (adopt an existing tool) | custom (build a jig) | manual (a habit/config change, nothing built).
- gate.kind: forge (used + no tool) | dispose (installed + unused) | suggest (used + suboptimal, or a habit change).
- Pick the LIGHTEST tool_type that kills the pattern (memory < skill < hook < agent config < script < CLI < TUI < alias).\
"""


def _s(v) -> str:
    return str(v).strip() if v is not None else ""


def normalize(raw, *, section: str | None = None) -> dict | None:
    """Coerce one raw suggestion into the canonical shape, or None if unusable.

    `section`: force every suggestion to this lens id (per-lens analysts own one
    lens). Pass None to keep the item's own `section` (the rollup, which may
    carry a cross-lens merge). Unknown enum values fall back to a safe default
    rather than dropping the whole suggestion."""
    if not isinstance(raw, dict):
        return None
    name = _s(raw.get("name"))
    painpoint = _s(raw.get("painpoint"))
    if not name or not painpoint:
        return None  # no title or no pain → not a real suggestion

    fix = raw.get("fix") if isinstance(raw.get("fix"), dict) else {}
    gate = raw.get("gate") if isinstance(raw.get("gate"), dict) else {}

    approach = _s(fix.get("approach")).lower()
    if approach not in APPROACHES:
        approach = "custom"
    kind = _s(gate.get("kind")).lower()
    if kind not in KINDS:
        kind = "suggest"
    mech = _s(gate.get("mechanical_or_craft")).lower()
    if mech not in MECH:
        mech = "mechanical"

    sec = section if section is not None else _s(raw.get("section"))
    return {
        "name": name,
        "section": sec,
        "painpoint": painpoint,
        "frequency": _s(raw.get("frequency")),
        "evidence": _s(raw.get("evidence")),
        "fix": {
            "approach": approach,
            "tool_type": _s(fix.get("tool_type")),
            "summary": _s(fix.get("summary")),
            "what": _s(fix.get("what")),
            "why": _s(fix.get("why")),
            "where": _s(fix.get("where")),
        },
        "gate": {
            "kind": kind,
            "mechanical_or_craft": mech,
            "payback": _s(gate.get("payback")),
            "confidence": _s(gate.get("confidence")),
        },
    }


def normalize_many(data, *, section: str | None = None) -> list[dict] | None:
    """Validate a container of suggestions.

    Returns a list (possibly empty — a clean lens) when `data` is a recognizable
    container, or None when it is not (the orchestrator's retry signal). Accepts
    a bare list, or a dict wrapping the list under suggestions/patterns/items."""
    items = None
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        for key in ("suggestions", "patterns", "items"):
            if isinstance(data.get(key), list):
                items = data[key]
                break
    if items is None:
        return None
    out = []
    for raw in items:
        norm = normalize(raw, section=section)
        if norm:
            out.append(norm)
    return out
