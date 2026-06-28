"""The reusable Profile components — the fixed building blocks.

Each component is a dumb renderer: it draws whatever inline data the agent put in
its box spec (config/profile.json). The agent reads the miner output, decides the
findings, and writes specs using these components — no bespoke Python per finding.
Adding a brand-new component *type* is the only thing that touches this file.

Box spec shape (one entry in a section's `boxes`):
    {"component": "bars", "title": "...", "data": [["Sun", 8798], ...], "note": "..."}

Layout: a section's `boxes` is a list; an entry is either a single full-width box
spec, or {"row": [box, box]} for a side-by-side grid (2 or 4 columns).
"""
from __future__ import annotations

from rich.text import Text
from textual.containers import Horizontal
from textual.widgets import Static

from tui.panels.contract import Counter, hbars, note, tone_colors
from tui.theme import theme_colors

COMPONENTS: dict[str, type] = {}


def component(name: str):
    def deco(cls):
        cls.component_name = name
        COMPONENTS[name] = cls
        return cls
    return deco


def build_box(spec: dict):
    """Instantiate the component named by `spec['component']`."""
    cls = COMPONENTS.get(spec.get("component", ""))
    if cls is None:
        return ProseBox({"text": f"(unknown component: {spec.get('component')!r})"})
    return cls(spec)


class BoxBase(Static):
    """Bordered box chrome. Subclasses implement `render_box() -> renderable`."""

    def __init__(self, spec: dict, **kwargs) -> None:
        super().__init__("", **kwargs)
        self.spec = spec

    def on_mount(self) -> None:
        if self.spec.get("title"):
            self.border_title = self.spec["title"]
        try:
            self.update(self.render_box())
        except Exception as e:  # noqa: BLE001 - a bad box must not kill the UI
            self.update(Text(f"box error: {e}", style="red"))

    def render_box(self):
        return Text("(empty box)", style="dim")

    def refresh_style(self) -> None:
        """Re-render with the active theme's colors. Called on theme change."""
        self.update(self.render_box())


@component("bars")
class BarsBox(BoxBase):
    """Horizontal bar chart from inline [[label, value], ...] data."""

    def render_box(self):
        c = theme_colors(self.app)
        out = Text()
        out.append_text(hbars(self.spec.get("data") or [],
                              label_w=self.spec.get("label_w", 16),
                              bar_w=self.spec.get("bar_w", 24),
                              colors=tone_colors(c)))
        out.append_text(note(self.spec.get("note", ""), c["note"]))
        return out


@component("histogram")
class HistogramBox(BoxBase):
    """Full-width vertical bar chart, sized to the box, from inline values.

    spec: {"data": [v0, v1, ...], "labels": ["00", ...]?,
           "tones": ["regular", "high", "dim", ...]?, "note": "..."}

    Per-column color is the AGENT's call: an optional `tones` list, one tone name
    per bar (warn/high/hot, regular/data, dim/low/mute), resolved via the active
    theme. Missing/short → the rest default to `regular`. No deterministic ranking.
    """

    def on_mount(self) -> None:
        if self.spec.get("title"):
            self.border_title = self.spec["title"]
        # render() is overridden for live width; nothing to update() here.

    def refresh_style(self) -> None:
        self.refresh()  # re-invokes render() with the active theme

    def render(self):
        try:
            return self._build()
        except Exception as e:  # noqa: BLE001
            return Text(f"box error: {e}", style="red")

    def _build(self):
        vals = [v or 0 for v in (self.spec.get("data") or [])]
        if not vals:
            return Text("(no data)", style="dim")
        c = theme_colors(self.app)
        colors = tone_colors(c)
        n = len(vals)
        width = self.content_size.width or 80
        top = max(vals) or 1
        slot = max(2, width // n)
        barw = max(1, slot - 1)
        height = self.spec.get("height", 7)
        tones = self.spec.get("tones") or []
        col_color = [colors.get(tones[i] if i < len(tones) else "regular",
                                colors["regular"]) for i in range(n)]

        out = Text()
        for row in range(height, 0, -1):
            thresh = top * row / height
            for v, color in zip(vals, col_color):
                out.append("█" * barw if v >= thresh else " " * barw, style=color)
                out.append(" " * (slot - barw))
            out.append("\n")

        labels = self.spec.get("labels") or [f"{i:02d}" for i in range(n)]
        every = 1 if slot >= 3 else 3
        axis = [" "] * (slot * n)
        for i in range(0, n, every):
            for j, ch in enumerate(str(labels[i])):
                if i * slot + j < len(axis):
                    axis[i * slot + j] = ch
        out.append("".join(axis).rstrip(), style=c["note"])
        out.append_text(note(self.spec.get("note", ""), c["note"]))
        return out


@component("counters")
class CountersBox(Horizontal):
    """Full-width strip of Counter boxes from inline items."""

    def __init__(self, spec: dict, **kwargs) -> None:
        super().__init__(**kwargs)
        self.spec = spec

    def on_mount(self) -> None:
        for it in self.spec.get("items", []):
            self.mount(Counter(it.get("value", ""), it.get("label", ""),
                               it.get("note", ""), it.get("hot", False),
                               classes="counter"))


@component("blocks")
class BlocksBox(BoxBase):
    """Ranked cards (forge candidates) + optional verdict, all inline."""

    def render_box(self):
        c = theme_colors(self.app)
        out = Text()
        for p in self.spec.get("items", []):
            craft = bool(p.get("craft")) or p.get("mechanical_or_craft") == "craft"
            accent = c["warning"] if craft else c["data"]
            if craft:
                out.append("✋ LEAVE IT ALONE   ", style=f"bold {accent}")
                out.append(f"{p.get('name', '')}\n", style=f"bold {c['text']}")
            else:
                out.append(f"#{p.get('rank', '?')}  ", style=f"bold {accent}")
                out.append(p.get("name", ""), style=f"bold {c['text']}")
                tags = " · ".join(x for x in [p.get("kind"), p.get("stack")] if x)
                if tags:
                    out.append(f"   [{tags}]\n", style=c["note"])
                else:
                    out.append("\n")
            if p.get("command"):
                out.append(f"   {p['command']}\n", style=accent)
            meta = "   ".join(x for x in [p.get("frequency"), p.get("payback")] if x)
            if meta:
                out.append(f"   {meta}\n", style=c["note"])
            if p.get("detail"):
                out.append(f"   {p['detail']}\n", style=c["note"])
            out.append("\n")
        if self.spec.get("verdict"):
            out.append("The minimal rack  ", style="bold")
            out.append(self.spec["verdict"], style=c["note"])
        return out


@component("prose")
class ProseBox(BoxBase):
    """A plain text/read box."""

    def render_box(self):
        return Text(self.spec.get("text", ""), style=theme_colors(self.app)["text"])
