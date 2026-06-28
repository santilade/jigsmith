"""Pattern-miner progress popup.

A modal that shows the three pipeline phases and their live state while the
agent runs. The app's worker thread drives it via `set_phase()` /
`finish()` (called through `call_from_thread`). Pure view — it never runs the
pipeline itself.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Log, Static

# phase index -> (short name, what it does)
PHASES = [
    ("Mine", "deterministic · tally your history"),
    ("Analyze", "agent · name + rank the 90% patterns"),
    ("Report", "agent · rebuild the Fingerprint"),
]

# which phases shell out to the agent — only these get a live log pane
_AGENTIC = {i for i, (_, d) in enumerate(PHASES) if d.startswith("agent")}

# state -> (glyph, css class)
_STATE = {
    "pending": ("·", "ph-pending"),
    "running": ("◐", "ph-running"),
    "done": ("✓", "ph-done"),
    "error": ("✗", "ph-error"),
    "skipped": ("–", "ph-pending"),
}
_SPINNER = "◐◓◑◒"


class PipelineProgress(ModalScreen):
    BINDINGS = [
        ("escape", "dismiss_if_done", "Close"),
        ("enter", "dismiss_if_done", "Close"),
        ("c", "cancel_run", "Cancel"),
    ]

    def __init__(self, cancel=None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._cancel = cancel
        self._cancelling = False
        self._state = ["pending"] * len(PHASES)
        self._detail = [PHASES[i][1] for i in range(len(PHASES))]
        self._done = False
        self._spin = 0
        self._active_log = None  # index of the agentic phase whose log is showing

    def compose(self) -> ComposeResult:
        with Vertical(id="pipeline-dialog") as dlg:
            dlg.border_title = "Scanner"
            for i in range(len(PHASES)):
                yield Static(id=f"phase-{i}")
                # Agentic phases get a live tail right under their row — hidden
                # until the phase runs, hidden again the moment it ends.
                if i in _AGENTIC:
                    log = Log(id=f"log-{i}", max_lines=500, auto_scroll=True)
                    log.display = False
                    yield log
            yield Static("", id="pipeline-status")

    def on_mount(self) -> None:
        for i in range(len(PHASES)):
            self._render_row(i)
        self._set_status("Running… press c to cancel.")
        # animate the spinner glyph on whichever phase is running
        self.set_interval(0.2, self._tick)

    # ---- driven by the worker thread (via call_from_thread) ----
    def set_phase(self, index: int, state: str, detail: str | None = None) -> None:
        self._state[index] = state
        if detail is not None:
            self._detail[index] = detail
        self._render_row(index)
        if index in _AGENTIC:
            self._toggle_log(index, state)

    def _toggle_log(self, index: int, state: str) -> None:
        """Show this agentic phase's log while it runs; hide + reset otherwise."""
        try:
            log = self.query_one(f"#log-{index}", Log)
        except Exception:
            return
        if state == "running":
            log.clear()
            log.display = True
            self._active_log = index
        else:
            log.display = False
            if self._active_log == index:
                self._active_log = None

    def append_log(self, line: str) -> None:
        """Append one parsed agent step to the running phase's tail (worker → here)."""
        if self._active_log is None:
            return
        try:
            self.query_one(f"#log-{self._active_log}", Log).write_line(line)
        except Exception:
            pass

    def finish(self, ok: bool, summary: str) -> None:
        self._done = True
        self._set_status(
            ("✓ " if ok else "✗ ") + summary + "   ·   press enter/esc to close")

    # ---- internals ----
    def _tick(self) -> None:
        if self._done:
            return
        self._spin = (self._spin + 1) % len(_SPINNER)
        for i, st in enumerate(self._state):
            if st == "running":
                self._render_row(i)

    def _render_row(self, i: int) -> None:
        st = self._state[i]
        glyph, cls = _STATE[st]
        if st == "running":
            glyph = _SPINNER[self._spin]
        try:
            w = self.query_one(f"#phase-{i}", Static)
        except Exception:
            return
        w.set_classes(["phase-row", cls])
        w.update(f"{glyph}  Phase {i + 1} · {PHASES[i][0]}   [dim]{self._detail[i]}[/dim]")

    def _set_status(self, text: str) -> None:
        try:
            self.query_one("#pipeline-status", Static).update(text)
        except Exception:
            pass

    def action_dismiss_if_done(self) -> None:
        if self._done:
            self.dismiss()

    def action_cancel_run(self) -> None:
        """Force-exit the run: signal the worker + agent to stop. Popup stays up
        until the worker unwinds and reports 'cancelled' via finish()."""
        if self._done or self._cancelling or self._cancel is None:
            return
        self._cancelling = True
        self._cancel.set()
        self._set_status("cancelling… killing agent, finishing current phase")
