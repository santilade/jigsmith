"""Shared render helpers + the box chrome base.

The TUI's Profile is built from a small set of generic, reusable *components*
(see components.py) driven entirely by an agent-authored spec (config/profile.json).
Nothing here reads the miner JSON — values arrive inline in the spec. This module
holds only the dumb rendering primitives the components compose.
"""
from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from tui.theme import theme_colors


def tone_colors(c: dict) -> dict:
    """Map a spec tone name to a color. The AGENT chooses each bar's tone in the
    spec (judgment — what to highlight / dim); this only resolves names to the
    active theme. Default tone is `regular`."""
    return {
        "warn": c["warning"], "high": c["warning"], "hot": c["warning"],
        "regular": c["data"], "mid": c["data"], "data": c["data"],
        "dim": c["note"], "low": c["note"], "mute": c["note"],
    }


def hbars(rows, *, label_w: int = 18, bar_w: int = 24, colors: dict,
          default: str = "regular") -> Text:
    """Horizontal bars. Each row is [label, value] or [label, value, tone];
    `tone` (warn/regular/dim) is the agent's call, resolved via `colors`."""
    if not rows:
        return Text("(no data)", style="dim")
    norm = []
    for r in rows:
        if isinstance(r, dict):
            norm.append((str(r.get("name", r.get("label", "?"))),
                         r.get("value", r.get("count", 0)) or 0,
                         r.get("tone", default)))
        else:
            norm.append((str(r[0]), r[1] or 0, r[2] if len(r) > 2 else default))
    top = max(v for _, v, _ in norm) or 1
    out = Text()
    for name, val, tone in norm:
        label = name[:label_w].ljust(label_w)
        fill = int(round(bar_w * val / top))
        out.append(label + " ", style="bold")
        out.append("█" * fill, style=colors.get(tone, colors[default]))
        out.append("·" * (bar_w - fill), style="dim")
        out.append(f" {val}\n")
    return out


def note(text: str, color: str) -> Text:
    """A box's inline read — muted, one blank line above."""
    return Text(f"\n{text}", style=color) if text else Text("")


class Counter(Static):
    """A single stat box (one cell of a counters strip).

    Top line: value (highlight) + label (white). Below: a note in gray.
    """

    def __init__(self, value, label, note_text: str = "", hot: bool = False,
                 **kwargs) -> None:
        super().__init__("", **kwargs)
        self._value = value
        self._label = label
        self._note = note_text
        self._hot = hot

    def on_mount(self) -> None:
        self.refresh_style()

    def refresh_style(self) -> None:
        """(Re)render with the active theme's colors. Called on theme change."""
        c = theme_colors(self.app)
        t = Text()
        t.append(f"{self._value} ", style="bold " + (c["warning"] if self._hot else c["data"]))
        t.append(str(self._label), style=f"bold {c['text']}")
        if self._note:
            t.append(f"\n{self._note}", style=c["note"])
        self.update(t)
