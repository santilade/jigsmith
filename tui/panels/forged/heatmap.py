"""Day × hour punchcard — when you drive agents, at a glance.

`histogram` is 1D (one axis). This is the 2D cadence grid: each cell shaded by
intensity. Serves Usage (cadence) and Sessions.

Spec:
    {"component": "heatmap",
     "data": [[0,0,2,5,8,...], ...],     # rows of values (e.g. 7 days × 24 hours)
     "rows": ["Mon","Tue",...],           # optional row labels
     "labels": ["00","02",...],           # optional column-axis labels
     "tone": "regular",                    # optional shade color (default regular)
     "note": "..."}

Intensity → one of " ░▒▓█" by quintile of the grid max. Deterministic ramp; the
agent supplies values, not colors.
"""
from __future__ import annotations

from rich.text import Text

from tui.panels.components import BoxBase, component
from tui.panels.contract import note, tone_colors
from tui.theme import theme_colors

RAMP = " ░▒▓█"


@component("heatmap")
class HeatmapBox(BoxBase):
    def render_box(self):
        c = theme_colors(self.app)
        colors = tone_colors(c)
        grid = self.spec.get("data") or []
        if not grid:
            return Text("(no data)", style="dim")
        rows = self.spec.get("rows") or []
        labw = max([3] + [len(str(r)) for r in rows[:len(grid)]])
        top = max((v or 0) for row in grid for v in row) or 1
        color = colors.get(self.spec.get("tone", "regular"), colors["regular"])

        span = max(1, top - 1)

        def cell(v) -> str:
            v = v or 0
            if v <= 0:
                return RAMP[0]
            idx = 1 + round((len(RAMP) - 2) * (v - 1) / span)
            return RAMP[min(idx, len(RAMP) - 1)]

        out = Text()
        for i, row in enumerate(grid):
            label = (str(rows[i]) if i < len(rows) else "").ljust(labw)
            out.append(label + " ", style=f"bold {c['text']}")
            out.append("".join(cell(v) for v in row), style=color)
            out.append("\n")

        labels = self.spec.get("labels") or []
        if labels:
            axis = [" "] * (labw + 1 + len(grid[0]))
            step = max(1, len(grid[0]) // max(1, len(labels)))
            for k, lab in enumerate(labels):
                pos = labw + 1 + k * step
                for j, ch in enumerate(str(lab)):
                    if pos + j < len(axis):
                        axis[pos + j] = ch
            out.append("".join(axis).rstrip() + "\n", style=c["note"])
        out.append_text(note(self.spec.get("note", ""), c["note"]))
        return out
