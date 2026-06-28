"""Columnar table — the inventory ⋈ usage join made legible.

`bars`/`blocks` can't render aligned columns. This one does: installed | used |
last-seen | verdict, one row per tool. Serves Harness (dead config) and Shell
(installed-vs-used).

Spec:
    {"component": "table",
     "columns": ["tool", "used", "last", "verdict"],
     "rows": [["skill: bash", "12x", "2d", "keep"],
              ["skill: vault", "0x", "-", "DISPOSE"]],
     "tones": ["regular", "warn", ...],   # optional, one per row
     "align": ["left", "right", ...],     # optional, one per column
     "note": "..."}
"""
from __future__ import annotations

from rich.text import Text

from tui.panels.components import BoxBase, component
from tui.panels.contract import note, tone_colors
from tui.theme import theme_colors


@component("table")
class TableBox(BoxBase):
    def render_box(self):
        c = theme_colors(self.app)
        colors = tone_colors(c)
        cols = [str(x) for x in (self.spec.get("columns") or [])]
        rows = self.spec.get("rows") or []
        if not cols and not rows:
            return Text("(no data)", style="dim")
        norm = [[str(cell) for cell in row] for row in rows]
        ncol = max([len(cols)] + [len(r) for r in norm]) or 1
        cols += [""] * (ncol - len(cols))
        for r in norm:
            r += [""] * (ncol - len(r))
        widths = [max([len(cols[i])] + [len(r[i]) for r in norm])
                  for i in range(ncol)]
        align = self.spec.get("align") or []
        tones = self.spec.get("tones") or []

        def fmt(cell: str, i: int) -> str:
            a = align[i] if i < len(align) else ("right" if i else "left")
            return cell.rjust(widths[i]) if a == "right" else cell.ljust(widths[i])

        out = Text()
        out.append("  ".join(fmt(cols[i], i) for i in range(ncol)) + "\n",
                   style=f"bold {c['text']}")
        out.append("  ".join("─" * widths[i] for i in range(ncol)) + "\n",
                   style="dim")
        for j, r in enumerate(norm):
            tone = tones[j] if j < len(tones) else "regular"
            out.append("  ".join(fmt(r[i], i) for i in range(ncol)) + "\n",
                       style=colors.get(tone, colors["regular"]))
        out.append_text(note(self.spec.get("note", ""), c["note"]))
        return out
