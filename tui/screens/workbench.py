"""Workbench — the rack of forged jigs.

The tend surface (Forge births, Workbench tends). Lists every jig on the rack —
active first, then candidates, then retired — with disposability visible. Reads
the rack deterministically (`core.store.rack`); dispose hands the selected jig to
a live `dispose-jig` agent session, and modify hands it to a live `forge-jig`
session to edit the existing tool in place.

This replaces the old cross-assistant config manager (that scope was dropped —
tools like CC Switch own config deploy). Keys: e modify · d dispose · i details
· r reload.
"""
from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Static

from core.store import rack
from tui.theme import theme_colors

COLUMNS = ("jig", "kind", "status", "payback")
_ORDER = {"active": 0, "candidate": 1, "retired": 2}


class WorkbenchScreen(Vertical):
    BINDINGS = [
        ("e", "modify", "Modify"),
        ("d", "dispose", "Dispose"),
        ("i", "toggle_detail", "Details"),
        ("r", "reload", "Reload"),
    ]
    can_focus = True
    _has_jigs = False

    # jig actions are meaningless on an empty rack — hide their footer keys
    _JIG_ACTIONS = {"modify", "dispose", "toggle_detail", "reload"}

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        if action in self._JIG_ACTIONS and not self._has_jigs:
            return False  # False is hidden; None would only dim it (Textual)
        return True

    def compose(self) -> ComposeResult:
        yield Static(id="wb-head")
        yield Static(id="wb-empty", classes="empty-state")
        with Horizontal(id="wb-body"):
            yield DataTable(id="wb-table", cursor_type="row", zebra_stripes=True,
                            classes="inv-table")
            yield Static(classes="inv-detail", id="wb-detail")

    def on_mount(self) -> None:
        tbl = self.query_one(DataTable)
        for c in COLUMNS:
            tbl.add_column(c, key=c)
        detail = self.query_one("#wb-detail", Static)
        detail.border_title = "Jig"
        detail.display = False
        self.load()

    def _rescan(self) -> None:   # called by the app after settings changes
        self.load()

    def action_reload(self) -> None:
        self.load()

    # ---- data ----
    def _jigs(self) -> list[dict]:
        try:
            rows = rack.list_jigs()
        except Exception:
            rows = []
        return sorted(rows, key=lambda r: (_ORDER.get(r.get("status"), 3),
                                           r.get("name", "")))

    def load(self) -> None:
        self.query_one("#wb-head", Static).update(self._head())
        jigs = self._jigs()
        self._has_jigs = bool(jigs)
        self.refresh_bindings()  # footer keys follow rack state
        empty = self.query_one("#wb-empty", Static)
        body = self.query_one("#wb-body", Horizontal)
        if not jigs:
            empty.update(
                "No tools on the rack yet.\n\n"
                "Go to the Forge tab to turn a mined friction point into a "
                "tool — it lands here once built.")
            empty.display = True
            body.display = False
            return
        empty.display = False
        body.display = True
        tbl = self.query_one(DataTable)
        saved = tbl.cursor_row
        tbl.clear()
        self.row_jig: dict[str, dict] = {}
        c = theme_colors(self.app)
        for j in jigs:
            key = j.get("id", j.get("name", "?"))
            status = j.get("status", "active")
            tone = {"active": c["data"], "candidate": c["accent"],
                    "retired": "dim"}.get(status, c["data"])
            tbl.add_row(j.get("name", "(unnamed)"), j.get("kind", "—"),
                        Text(status, style=tone), j.get("payback", "—"), key=key)
            self.row_jig[key] = j
        if tbl.row_count:
            tbl.move_cursor(row=min(saved, tbl.row_count - 1))
        self._show_detail()

    def _head(self) -> Text:
        jigs = self._jigs()
        active = sum(1 for j in jigs if j.get("status") == "active")
        out = Text()
        out.append("Workbench\n", style="bold")
        out.append(
            "View and organize the tools you've built. Drop the ones you no "
            "longer use.",
            style="dim")
        if jigs:
            out.append(f"  ({active} active · {len(jigs)} total)", style="dim")
        out.append("\n")
        return out

    # ---- detail ----
    def _current(self) -> dict | None:
        tbl = self.query_one(DataTable)
        if not tbl.row_count:
            return None
        try:
            key = tbl.coordinate_to_cell_key((tbl.cursor_row, 0)).row_key.value
        except Exception:
            return None
        return self.row_jig.get(key)

    @on(DataTable.RowHighlighted)
    def _on_highlight(self) -> None:
        self._show_detail()

    def action_toggle_detail(self) -> None:
        box = self.query_one("#wb-detail", Static)
        box.display = not box.display
        self._show_detail()

    def _show_detail(self) -> None:
        box = self.query_one("#wb-detail", Static)
        if not box.display:
            return
        j = self._current()
        if not j:
            box.update(Text("(no jig)", style="dim"))
            return
        out = Text()
        out.append(f"{j.get('name', '')}\n", style="bold")
        out.append(f"{j.get('kind', '')} · {j.get('status', '')} · "
                   f"{j.get('payback', '')}\n\n", style="dim")
        for label in ("build_min", "path", "definition"):
            val = j.get(label)
            if val not in (None, "", 0):
                out.append(f"{label.replace('_', ' ')}\n", style="bold")
                out.append(f"{val}\n\n", style="dim")
        box.border_title = j.get("name", "Jig")
        box.update(out)

    # ---- modify (the hand-off) ----
    def action_modify(self) -> None:
        j = self._current()
        if not j:
            self.app.notify("no jig selected", severity="warning", timeout=3)
            return
        self.app.launch_interactive(self._modify_prompt(j), after=self.load)

    @staticmethod
    def _modify_prompt(j: dict) -> str:
        return (
            "Help me modify an existing jig on my rack. Read the forge-jig skill "
            "and follow it to edit the tool in place — keep the same kind unless "
            "I ask otherwise, ask me what to change before editing, and update "
            "the rack entry (and payback) when done.\n\n"
            f"  Jig: {j.get('name', '')}\n"
            f"  Kind: {j.get('kind', '')}\n"
            f"  Status: {j.get('status', '')}\n"
            f"  Payback: {j.get('payback', '')}\n"
            f"  Path: {j.get('path', '')}\n"
        )

    # ---- dispose (the hand-off) ----
    def action_dispose(self) -> None:
        j = self._current()
        if not j:
            self.app.notify("no jig selected", severity="warning", timeout=3)
            return
        self.app.launch_interactive(self._prompt(j), after=self.load)

    @staticmethod
    def _prompt(j: dict) -> str:
        return (
            "Help me dispose of a jig from my rack. Read the dispose-jig skill and "
            "follow it — confirm with me before deleting anything.\n\n"
            f"  Jig: {j.get('name', '')}\n"
            f"  Kind: {j.get('kind', '')}\n"
            f"  Status: {j.get('status', '')}\n"
            f"  Payback: {j.get('payback', '')}\n"
            f"  Path: {j.get('path', '')}\n\n"
            "Decide retire vs delete, clean up artifacts, and update the rack."
        )
