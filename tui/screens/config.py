"""Settings popups reachable from the command palette.

Two keyboard-first modals over the agent registry (`core.agents`):

  - `InspectModal`      — pick which agents Jigsmith INSPECTS (whose history +
    inventory the mirror reads). Multi-select; dismisses with the chosen id list.
  - `DefaultAgentModal` — pick the single agent that RUNS Jigsmith's agentic flows
    (scanner / forge hand-off). Dismisses with the chosen id.

Both only collect a choice and hand it back; the app applies + persists it.
Cancel dismisses with None.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Checkbox, Label, RadioButton, RadioSet

from core import agents
from core.parsers.shell_history import SHELLS, current_shell, default_shells, has_history
from core.store import settings

_ADD_PROMPT = (
    "I want Jigsmith to support another coding agent (inspect its history "
    "and/or run it as the default). Use the register-agent skill to walk me "
    "through writing its manifest."
)

_ADD_SHELL_PROMPT = (
    "I want Jigsmith to inspect another shell's command history. Use the "
    "register-shell skill to walk me through adding it."
)


def _launch_add_agent(app) -> None:
    """Hand the terminal to a live agent session prefilled to add agent support."""
    app.launch_interactive(_ADD_PROMPT)


def _launch_add_shell(app) -> None:
    """Hand the terminal to a live agent session prefilled to add shell support."""
    app.launch_interactive(_ADD_SHELL_PROMPT)


class InspectModal(ModalScreen):
    """Multi-select the agents to inspect → dismiss with [ids] or None."""

    BINDINGS = [
        ("up,k", "focus_prev", "Up"), ("down,j", "focus_next", "Down"),
        ("space", "toggle", "Toggle"), ("s", "save", "Save"),
        ("a", "add_agent", "Add agent"),
        ("c,escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        self._ids = sorted(agents.all_agents())
        default = [m.id for m in agents.inspectable()] or self._ids
        chosen = set(settings.inspect_agents() or default)
        with Vertical(id="pick-form"):
            yield Label("Agents to inspect", id="pick-title")
            yield Label("whose history + inventory the mirror mines", id="pick-sub")
            yield Label("missing an agent? press a to ask your agent to register "
                        "itself using the register-agent skill", id="pick-note")
            for aid in self._ids:
                m = agents.by_id(aid)
                if m.can_inspect():
                    avail = "history found"
                elif m.installed():
                    avail = "installed · no history yet"
                else:
                    avail = "not installed"
                yield Checkbox(f"{m.tag}  {m.label}   ({avail})",
                               value=aid in chosen, id=f"insp-{aid}")
            yield Label("space toggle · s save · c cancel", id="pick-hint")

    def on_mount(self) -> None:
        try:
            self.query(Checkbox).first().focus()
        except Exception:
            pass

    def action_focus_prev(self) -> None:
        self.focus_previous(Checkbox)

    def action_focus_next(self) -> None:
        self.focus_next(Checkbox)

    def action_toggle(self) -> None:
        if isinstance(self.focused, Checkbox):
            self.focused.toggle()

    def action_save(self) -> None:
        ids = [a for a in self._ids if self.query_one(f"#insp-{a}", Checkbox).value]
        if not ids:
            self.app.notify("keep at least one agent to inspect",
                            severity="warning", timeout=3)
            return
        self.dismiss(ids)

    def action_add_agent(self) -> None:
        app = self.app
        self.dismiss(None)
        _launch_add_agent(app)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ShellModal(ModalScreen):
    """Multi-select the shells to inspect → dismiss with [ids] or None.

    Defaults to the shell Jigsmith is running under ($SHELL) when the developer
    hasn't chosen yet, so the mirror reads the right history out of the box.
    """

    BINDINGS = [
        ("up,k", "focus_prev", "Up"), ("down,j", "focus_next", "Down"),
        ("space", "toggle", "Toggle"), ("s", "save", "Save"),
        ("a", "add_shell", "Add shell"),
        ("c,escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        self._ids = sorted(SHELLS)
        chosen = set(settings.inspect_shells() or default_shells())
        cur = current_shell()
        with Vertical(id="pick-form"):
            yield Label("Shells to inspect", id="pick-title")
            yield Label("whose command history the mirror mines", id="pick-sub")
            yield Label("missing a shell? press a to ask your agent to register "
                        "it using the register-shell skill", id="pick-note")
            for sid in self._ids:
                bits = ["current"] if sid == cur else []
                bits.append("history found" if has_history(sid) else "no history yet")
                avail = " · ".join(bits)
                yield Checkbox(f"{sid}   ({avail})",
                               value=sid in chosen, id=f"shell-{sid}")
            yield Label("space toggle · s save · c cancel", id="pick-hint")

    def on_mount(self) -> None:
        try:
            self.query(Checkbox).first().focus()
        except Exception:
            pass

    def action_focus_prev(self) -> None:
        self.focus_previous(Checkbox)

    def action_focus_next(self) -> None:
        self.focus_next(Checkbox)

    def action_toggle(self) -> None:
        if isinstance(self.focused, Checkbox):
            self.focused.toggle()

    def action_save(self) -> None:
        ids = [s for s in self._ids if self.query_one(f"#shell-{s}", Checkbox).value]
        if not ids:
            self.app.notify("keep at least one shell to inspect",
                            severity="warning", timeout=3)
            return
        self.dismiss(ids)

    def action_add_shell(self) -> None:
        app = self.app
        self.dismiss(None)
        _launch_add_shell(app)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfirmModal(ModalScreen):
    """Yes/no confirmation → dismiss True (y) or False (n / esc).

    Keyboard-only, defaults to no — only an explicit y commits. Used to gate
    destructive actions like clearing the workspace.
    """

    BINDINGS = [
        ("y", "confirm", "Yes"),
        ("n,escape", "cancel", "No"),
    ]

    def __init__(self, title: str, body: str) -> None:
        super().__init__()
        self._title = title
        self._body = body

    def compose(self) -> ComposeResult:
        with Vertical(id="pick-form"):
            yield Label(self._title, id="pick-title")
            yield Label(self._body, id="pick-sub")
            yield Label("y yes · n no", id="pick-hint")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class DefaultAgentModal(ModalScreen):
    """Single-select the default agent (runs the agentic flows) → id or None."""

    BINDINGS = [
        ("s", "save", "Save"), ("a", "add_agent", "Add agent"),
        ("c,escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        self._runs = agents.runnable() or list(agents.all_agents().values())
        cur = agents.default()
        cur_id = cur.id if cur else None
        with Vertical(id="pick-form"):
            yield Label("Default agent", id="pick-title")
            yield Label("runs Jigsmith's agentic flows (scanner, forge)",
                        id="pick-sub")
            yield Label("missing an agent? press a to ask your agent to register "
                        "itself using the register-agent skill", id="pick-note")
            with RadioSet(id="agent-set"):
                for m in self._runs:
                    suffix = "" if m.can_run() else "  (not on PATH)"
                    yield RadioButton(m.label + suffix, value=m.id == cur_id)
            yield Label("enter pick · s save · c cancel", id="pick-hint")

    def on_mount(self) -> None:
        try:
            self.query_one("#agent-set", RadioSet).focus()
        except Exception:
            pass

    def action_save(self) -> None:
        idx = self.query_one("#agent-set", RadioSet).pressed_index
        if idx is None or idx < 0:
            self.app.notify("pick an agent first", severity="warning", timeout=2)
            return
        self.dismiss(self._runs[idx].id)

    def action_add_agent(self) -> None:
        app = self.app
        self.dismiss(None)
        _launch_add_agent(app)

    def action_cancel(self) -> None:
        self.dismiss(None)
