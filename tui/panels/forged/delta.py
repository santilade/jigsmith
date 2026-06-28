"""Delta — value + arrow + change vs the prior window.

The N=1-vs-itself comparison is the point (diff yourself over time) and none of the
core components show it. One row per metric: label, value, then the trend.

Spec:
    {"component": "delta",
     "items": [
        {"label": "tokens",   "value": "120k", "change": "+18%", "dir": "up"},
        {"label": "sessions", "value": "34",   "change": "-5%",  "dir": "down"},
        {"label": "ctx avg",  "value": "62k",  "change": "0%",   "dir": "flat",
         "tone": "warn"}],     # optional per-item tone override
     "note": "..."}

`dir` picks the arrow (up ▲ / down ▼ / flat ▬). Tone defaults by direction
(up→regular, down→dim, flat→dim) unless the agent overrides — the agent decides
whether a rise is good or bad.
"""
from __future__ import annotations

from rich.text import Text

from tui.panels.components import BoxBase, component
from tui.panels.contract import note, tone_colors
from tui.theme import theme_colors

ARROW = {"up": "▲", "down": "▼", "flat": "▬"}
DEFAULT_TONE = {"up": "regular", "down": "dim", "flat": "dim"}


@component("delta")
class DeltaBox(BoxBase):
    def render_box(self):
        c = theme_colors(self.app)
        colors = tone_colors(c)
        items = self.spec.get("items") or []
        if not items:
            return Text("(no data)", style="dim")
        labw = max(len(str(it.get("label", ""))) for it in items)
        valw = max(len(str(it.get("value", ""))) for it in items)

        out = Text()
        for it in items:
            d = it.get("dir", "flat")
            tone = it.get("tone") or DEFAULT_TONE.get(d, "dim")
            color = colors.get(tone, colors["regular"])
            out.append(str(it.get("label", "")).ljust(labw) + "  ",
                       style=f"bold {c['text']}")
            out.append(str(it.get("value", "")).rjust(valw) + "  ",
                       style=f"bold {c['data']}")
            out.append(ARROW.get(d, "▬") + " ", style=color)
            out.append(str(it.get("change", "")), style=color)
            out.append("\n")
        out.append_text(note(self.spec.get("note", ""), c["note"]))
        return out
