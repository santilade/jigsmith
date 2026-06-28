"""Profile tab (home) — renders the agent-authored spec (config/profile.json).

Fully data-driven: the agent writes the sections (sub-tabs) and each section's
boxes in the spec, using generic components with inline data. The renderer just
loops the spec — sub-tabs, titles, order, and boxes all come from the JSON, and
it reads only the spec, never the miner JSON.
"""
from __future__ import annotations

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Static, TabbedContent, TabPane

from tui.panels import build_box


class ProfileScreen(Vertical):
    # `r` runs the full scanner pipeline. Bound here (not on the app) so it
    # is only live on the Profile tab — the scanner is run from the Profile, not
    # the Workbench/Forge. The action is qualified `app.run_miner` because an
    # unqualified action runs on THIS widget's namespace and does NOT bubble to
    # the app, where action_run_miner actually lives.
    # Bindings are only active when this screen (or a descendant) holds focus, so
    # we make it focusable and grab focus whenever the Profile pane is shown.
    can_focus = True
    BINDINGS = [
        ("r", "app.run_miner", "Run scanner"),
        # up/down scroll the active section; left/right switch section sub-tabs.
        # Kept off the footer — arrow navigation is intuitive enough.
        Binding("up", "scroll(-1)", "Scroll up", show=False),
        Binding("down", "scroll(1)", "Scroll down", show=False),
        Binding("left", "cycle_section(-1)", "Prev section", show=False),
        Binding("right", "cycle_section(1)", "Next section", show=False),
    ]

    def on_show(self, event: events.Show) -> None:
        self.focus()

    def _active_scroll(self) -> VerticalScroll | None:
        try:
            tabs = self.query_one("#section-tabs", TabbedContent)
            pane = tabs.get_pane(tabs.active)
            return pane.query_one(VerticalScroll)
        except Exception:
            return None

    def action_scroll(self, direction: int) -> None:
        scroller = self._active_scroll()
        if scroller is None:
            return
        if direction < 0:
            scroller.scroll_up()
        else:
            scroller.scroll_down()

    def action_cycle_section(self, step: int) -> None:
        if not self.sections:
            return
        ids = [f"sec-{sec['id']}" for sec in self.sections]
        try:
            tabs = self.query_one("#section-tabs", TabbedContent)
            idx = ids.index(tabs.active)
            tabs.active = ids[(idx + step) % len(ids)]
        except Exception:
            pass

    def __init__(self, sections, **kwargs) -> None:
        super().__init__(**kwargs)
        self.sections = sections

    def _head(self) -> Text:
        out = Text()
        out.append("Fingerprint\n", style="bold")
        out.append(
            "How you work with your agents — the patterns that are distinctly "
            "yours and the friction points worth fixing.",
            style="dim")
        if self.sections:
            out.append(f"  ({len(self.sections)} section lens(es))", style="dim")
        out.append("\n")
        return out

    def compose(self) -> ComposeResult:
        yield Static(self._head(), id="profile-head")
        if not self.sections:
            yield Static(
                "No reports yet.\n\n"
                "Run the scanner (press r) to mine your history for how you work "
                "— your print lands here once it's built.",
                id="empty-profile", classes="empty-state")
            return
        with TabbedContent(id="section-tabs"):
            for sec in self.sections:
                with TabPane(sec.get("title", sec.get("id", "?")),
                             id=f"sec-{sec['id']}"):
                    with VerticalScroll():
                        yield from self._compose_boxes(sec.get("boxes", []))

    def _compose_boxes(self, boxes) -> ComposeResult:
        """Each entry is a full-width box spec, or {"row": [box, ...]} grid."""
        for entry in boxes:
            row = entry.get("row") if isinstance(entry.get("row"), list) else None
            if row:
                with Horizontal(classes="panel-row"):
                    for box in row:
                        yield build_box(box)
            else:
                yield build_box(entry)

    def update_sections(self, sections) -> None:
        """Swap in a freshly-rebuilt spec and re-render (after a pipeline run)."""
        self.sections = sections
        self.refresh(recompose=True)

    def show_section(self, section_id: str) -> None:
        try:
            self.query_one("#section-tabs", TabbedContent).active = f"sec-{section_id}"
        except Exception:
            pass
