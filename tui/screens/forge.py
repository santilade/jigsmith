"""Forge section — pick a mined 90% pattern and hand it to a live agent.

The forge candidates are the ranked patterns the `scanner` pipeline wrote
to `patterns.json` (deterministic read — the TUI never re-derives them). Picking
one is an explicit hand-off across the quarantine boundary: the app suspends,
launches the default assistant's interactive TUI prefilled with a `forge-jig`
first prompt, and on return re-reads the rack. The actual forging stays agentic;
this screen just frames the candidate and starts the session.

Keys: enter/f forge the selected candidate · i details · esc home.
"""
from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Static

from core.store import rack as db
from tui.theme import theme_colors

COLUMNS = ("#", "painpoint", "kind", "form", "approach", "verdict")


class ForgeScreen(Vertical):
    BINDINGS = [
        ("enter,f", "forge", "Forge"),
        ("i", "toggle_detail", "Details"),
    ]
    _has_cands = False

    # forge/details are meaningless with no painpoints — hide their footer keys
    _CAND_ACTIONS = {"forge", "toggle_detail"}

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        if action in self._CAND_ACTIONS and not self._has_cands:
            return False  # False is hidden; None would only dim it (Textual)
        return True

    def compose(self) -> ComposeResult:
        yield Static(id="forge-head")
        yield Static(id="forge-empty", classes="empty-state")
        with Horizontal(id="forge-body"):
            yield DataTable(id="forge-table", cursor_type="row",
                            zebra_stripes=True, classes="inv-table")
            yield Static(classes="inv-detail", id="forge-detail")

    def on_mount(self) -> None:
        tbl = self.query_one(DataTable)
        for c in COLUMNS:
            tbl.add_column(c, key=c)
        detail = self.query_one("#forge-detail", Static)
        detail.border_title = "Pattern"
        detail.display = True            # shown by default; `i` toggles off
        self.load()

    # ---- data ----
    def _candidates(self) -> list[dict]:
        try:
            pats = self.app.store.get("patterns.patterns", []) or []
        except Exception:
            pats = []
        return [p for p in pats if isinstance(p, dict)]

    def load(self) -> None:
        self.query_one("#forge-head", Static).update(self._head())
        cands = self._candidates()
        self._has_cands = bool(cands)
        self.refresh_bindings()  # footer keys follow candidate state
        empty = self.query_one("#forge-empty", Static)
        body = self.query_one("#forge-body", Horizontal)
        if not cands:
            empty.update(
                "No painpoints yet.\n\n"
                "Go to the Fingerprint tab and run the scanner (r) to mine "
                "your history for friction points and their suggested fixes.")
            empty.display = True
            body.display = False
            return
        empty.display = False
        body.display = True
        tbl = self.query_one(DataTable)
        saved = tbl.cursor_row
        tbl.clear()
        self.row_pat: dict[str, dict] = {}
        c = theme_colors(self.app)
        for i, p in enumerate(cands):
            key = str(i)
            craft = self._is_craft(p)
            verdict = Text(self._verdict(p), style="yellow" if craft else c["data"])
            appr = self._approach(p)
            approach = Text(appr or "—",
                            style="cyan" if appr == "download" else c["data"])
            kind = self._kind(p)
            kind_cell = Text(kind or "—",
                             style="yellow" if kind == "dispose" else c["data"])
            tbl.add_row(str(i + 1), p.get("name", "(unnamed)"), kind_cell,
                        self._tool_type(p), approach, verdict, key=key)
            self.row_pat[key] = p
        if tbl.row_count:
            tbl.move_cursor(row=min(saved, tbl.row_count - 1))
        self._show_detail()

    def _head(self) -> Text:
        n = len(self._candidates())
        try:
            racked = len(db.list_jigs())
        except Exception:
            racked = 0
        out = Text()
        out.append("Forge\n", style="bold")
        out.append(
            "Every painpoint the scanner found, with its suggested fix. Pick one "
            "and hand it to an agent — forge a tool, adopt one, or just change a "
            "habit.",
            style="dim")
        if n:
            out.append(f"  ({n} painpoint(s) · {racked} on the rack)", style="dim")
        out.append("\n")
        return out

    # ---- detail panel ----
    def _current(self) -> dict | None:
        tbl = self.query_one(DataTable)
        if not tbl.row_count:
            return None
        try:
            key = tbl.coordinate_to_cell_key((tbl.cursor_row, 0)).row_key.value
        except Exception:
            return None
        return self.row_pat.get(key)

    @on(DataTable.RowHighlighted)
    def _on_highlight(self) -> None:
        self._show_detail()

    def action_toggle_detail(self) -> None:
        box = self.query_one("#forge-detail", Static)
        box.display = not box.display
        self._show_detail()

    def _show_detail(self) -> None:
        box = self.query_one("#forge-detail", Static)
        if not box.display:
            return
        p = self._current()
        if not p:
            box.update(Text("(no candidate)", style="dim"))
            return
        fix = self._fix(p)
        gate = self._gate(p)
        out = Text()
        out.append(f"{p.get('name', '')}\n", style="bold")
        out.append(f"{self._verdict(p)} · {self._tool_type(p)} · "
                   f"{self._approach(p) or '—'} · "
                   f"{gate.get('payback', '')}\n\n", style="dim")

        # narrative bands: what hurts, how often, the proof
        for label, val in (
            ("pain point", p.get("painpoint")),
            ("frequency", p.get("frequency")),
            ("evidence", p.get("evidence")),
        ):
            if val:
                out.append(f"{label}\n", style="bold")
                out.append(f"{val}\n\n", style="dim")

        # the proposal
        if fix:
            out.append("suggested fix", style="bold")
            appr = self._approach(p)
            if appr:
                out.append(f"  ({appr})", style="cyan")
            out.append("\n")
            if fix.get("summary"):
                out.append(f"{fix['summary']}\n", style="dim")
            for lbl in ("what", "why", "where"):
                if fix.get(lbl):
                    out.append(f"  {lbl}: ", style="bold")
                    out.append(f"{fix[lbl]}\n", style="dim")
            out.append("\n")

        if gate.get("confidence"):
            out.append("confidence  ", style="bold")
            out.append(f"{gate['confidence']}\n", style="dim")
        box.border_title = p.get("name", "Pattern")
        box.update(out)

    # ---- forge action (the hand-off) ----
    def action_forge(self) -> None:
        p = self._current()
        if not p:
            self.app.notify("no forge candidate selected", severity="warning",
                            timeout=3)
            return
        self.app.launch_interactive(self._prompt(p), after=self._after_forge)

    def _after_forge(self) -> None:
        # Back from the agent session — it may have racked a new jig. Refresh the
        # Forge board AND the Workbench so both reflect disk without a restart.
        self.load()
        try:
            self.app._rescan_workbench()
        except Exception:
            pass

    # ---- accessors (new nested shape, with flat-shape fallback) ----
    @staticmethod
    def _fix(p: dict) -> dict:
        f = p.get("fix")
        return f if isinstance(f, dict) else {}

    @staticmethod
    def _gate(p: dict) -> dict:
        g = p.get("gate")
        return g if isinstance(g, dict) else {}

    @classmethod
    def _approach(cls, p: dict) -> str:
        # narrative `fix.approach`; fall back to the old top-level `source`.
        return (cls._fix(p).get("approach") or p.get("source") or "").lower()

    @classmethod
    def _kind(cls, p: dict) -> str:
        # gate.kind — forge | dispose | suggest — the board's painpoint class.
        return (cls._gate(p).get("kind") or p.get("kind") or "").lower()

    @classmethod
    def _is_craft(cls, p: dict) -> bool:
        moc = cls._gate(p).get("mechanical_or_craft") or \
            p.get("mechanical_or_craft") or ""
        return moc.lower().startswith("craft")

    @classmethod
    def _verdict(cls, p: dict) -> str:
        # Map the scanner's mechanical/craft call to a plain-language action.
        return "Keep manual" if cls._is_craft(p) else "Automate"

    @classmethod
    def _tool_type(cls, p: dict) -> str:
        # Scanner may emit a single form or a combo (string "memory + skill" or
        # a list). Normalise both to a "+"-joined display string.
        tt = cls._fix(p).get("tool_type") or p.get("tool_type")
        if isinstance(tt, (list, tuple)):
            tt = " + ".join(str(x) for x in tt if x)
        return str(tt).strip() if tt else "—"

    @classmethod
    def _prompt(cls, p: dict) -> str:
        # A briefing + scoping mandate, NOT a build order. The agent must
        # understand the problem, gate on payback/craft, CONFIRM the fix approach
        # (the dev may prefer custom over a suggested download, or vice versa),
        # interview to scope, and get a written go-ahead before building. Forging
        # is human-driven (see README + the forge-jig skill's Phase 0).
        fix, gate = cls._fix(p), cls._gate(p)
        appr = cls._approach(p) or "—"
        return (
            "You're helping me forge a personal dev tool (a \"jig\") for a "
            "recurring pattern Jigsmith mined from my agent history. Read the "
            "forge-jig skill and follow it — but DO NOT build anything yet.\n\n"
            "THE PAIN POINT\n"
            f"  {p.get('name', '')}\n"
            f"  {p.get('painpoint', '')}\n\n"
            "FREQUENCY\n"
            f"  {p.get('frequency', '')}\n\n"
            "EVIDENCE\n"
            f"  {p.get('evidence', '')}\n\n"
            "SUGGESTED FIX\n"
            f"  Approach: {appr} "
            "(custom = forge it · download = adopt an existing tool · "
            "manual = a habit/config change)\n"
            f"  Form: {cls._tool_type(p)}\n"
            f"  Summary: {fix.get('summary', '')}\n"
            f"  What: {fix.get('what', '') or '—'}\n"
            f"  Why: {fix.get('why', '') or '—'}\n"
            f"  Where: {fix.get('where', '') or '—'}\n\n"
            "GATE\n"
            f"  Type: {gate.get('mechanical_or_craft', '')}\n"
            f"  Payback: {gate.get('payback', '')}\n"
            f"  Confidence: {gate.get('confidence', '')}\n\n"
            "YOUR JOB, IN ORDER\n"
            "  1. Understand it. Restate the pain point in your own words so we "
            "agree on what hurts and where.\n"
            "  2. Sanity-check: really mechanical, or craft I shouldn't automate? "
            "Does payback (frequency × per-instance cost) beat build + upkeep? "
            "If not — say so and STOP.\n"
            "  3. Confirm the fix WITH me. The suggested approach above is a "
            "proposal, not a decision — I may prefer a custom jig over the "
            "suggested download (or the reverse, or a manual change). Get my call "
            "on approach + form before scoping.\n"
            "  4. Interview me. Ask what you need to nail scope — exact "
            "inputs/outputs, edge cases, where it lives, what \"done\" is, "
            "naming. One focused round at a time.\n"
            "  5. Converge on a short written spec (one paragraph). Show me. Get "
            "explicit go-ahead.\n"
            "  6. ONLY THEN build it, register it on the rack, tell me what + "
            "where.\n\n"
            "Scale the rigor to the jig: a throwaway one-off needs only a quick "
            "spec-and-go; a daily staple earns the full interview. Start with "
            "step 1 now."
        )
