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
from textual.widgets import Static

# phase index -> (short name, what it does)
PHASES = [
    ("Mine", "deterministic · tally your history"),
    ("Analyze", "agent · name + rank the 90% patterns"),
    ("Report", "agent · rebuild the Fingerprint"),
]

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
    BINDINGS = [("escape", "dismiss_if_done", "Close"), ("enter", "dismiss_if_done", "Close")]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._state = ["pending"] * len(PHASES)
        self._detail = [PHASES[i][1] for i in range(len(PHASES))]
        self._done = False
        self._spin = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="pipeline-dialog") as dlg:
            dlg.border_title = "Scanner"
            for i in range(len(PHASES)):
                yield Static(id=f"phase-{i}")
            yield Static("", id="pipeline-status")

    def on_mount(self) -> None:
        for i in range(len(PHASES)):
            self._render_row(i)
        self._set_status("Running… do not quit.")
        # animate the spinner glyph on whichever phase is running
        self.set_interval(0.2, self._tick)

    # ---- driven by the worker thread (via call_from_thread) ----
    def set_phase(self, index: int, state: str, detail: str | None = None) -> None:
        self._state[index] = state
        if detail is not None:
            self._detail[index] = detail
        self._render_row(index)

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
