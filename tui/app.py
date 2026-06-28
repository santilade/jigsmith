"""JigsmithApp — the shell.

Three primary tabs (Fingerprint, Forge, Workbench) plus room for dynamic, closeable
feature tabs. Navigation + quick actions via the command palette. The app owns
the single DataStore and the explicit miner-run action (the quarantine
boundary: the agent/miner writes JSON at an action, the UI only reads).
"""
from __future__ import annotations

import shutil
import subprocess
import threading

from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.command import DiscoveryHit, Hit, Hits, Provider
from textual.widgets import Footer, Header, Static, TabbedContent, Tabs, TabPane
from textual.widgets._footer import FooterKey

from core import agents
from core.store import rack as db
from core.store import settings
from tui.config import load_profile
from tui.data.store import DataStore, REPO_ROOT
from tui.panels import discover
from tui.theme import JIGSMITH_THEME
from tui.screens.profile import ProfileScreen
from tui.screens.workbench import WorkbenchScreen
from tui.screens.pipeline import PipelineProgress
from tui.screens.home import HomeScreen
from tui.screens.forge import ForgeScreen


class JigHeader(Header):
    """Header that doesn't toggle tall/short when clicked."""

    def _on_click(self, event: events.Click) -> None:  # noqa: D401
        event.stop()


class JigFooter(Footer):
    """Footer that docks the esc + quit keys to the right edge."""

    _PINNED = ("home", "quit")  # esc → home, q → quit

    def compose(self) -> ComposeResult:
        if not self._bindings_ready:
            return
        active = self.screen.active_bindings
        pinned: list[FooterKey] = []
        for _node, binding, enabled, tooltip in active.values():
            if not binding.show:
                continue
            key = FooterKey(
                binding.key,
                self.app.get_key_display(binding),
                binding.description,
                binding.action,
                disabled=not enabled,
                tooltip=tooltip,
            ).data_bind(compact=Footer.compact)
            if binding.action in self._PINNED:
                pinned.append(key)
            else:
                yield key

        # spacer eats the slack so the pinned keys sit at the right edge
        yield Static("", classes="footer-spacer")
        yield from pinned

        if self.show_command_palette and self.app.ENABLE_COMMAND_PALETTE:
            try:
                _n, binding, enabled, tooltip = active[self.app.COMMAND_PALETTE_BINDING]
            except KeyError:
                pass
            else:
                yield FooterKey(
                    binding.key,
                    self.app.get_key_display(binding),
                    binding.description,
                    binding.action,
                    classes="-command-palette",
                    disabled=not enabled,
                    tooltip=binding.tooltip or binding.description,
                )


class JigsmithCommands(Provider):
    """Command-palette entries: run the miner, configure assistants, jump views.

    Implements both `discover` (the empty-input listing) and `search` (filtered)
    so the commands show up before you type, not only after. The list is rebuilt
    each call, so the assistant on/off + current-default labels stay live.
    """

    def _commands(self) -> list[tuple[str, str, callable]]:
        app = self.app
        return [
            ("Agent run",
             "Make Jigsmith your own — ask the agent to change or add "
             "functionality to the Jigsmith TUI",
             app.open_code_assistant),
            ("Agent default",
             "Choose the agent that runs Jigsmith's agentic flows (miner, forge)",
             app.open_default_runner_picker),
            ("Agent list",
             "Choose which agents' history + inventory the mirror mines",
             app.open_inspect_picker),
            # keys + theme always go last (see COMMANDS — single provider so this
            # insertion order is the displayed order)
            ("Keys",
             "Show help for the focused widget and a summary of available keys",
             app.action_show_help_panel),
            ("Theme",
             "Change the current theme",
             app.action_change_theme),
        ]

    async def discover(self) -> Hits:
        for name, help_text, callback in self._commands():
            yield DiscoveryHit(name, callback, help=help_text)

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for name, help_text, callback in self._commands():
            score = matcher.match(name)
            if score > 0:
                yield Hit(score, matcher.highlight(name), callback, help=help_text)


class JigsmithApp(App):
    CSS_PATH = "jigsmith.tcss"
    TITLE = "Jigsmith"
    SUB_TITLE = ""
    # single provider → palette order is exactly JigsmithCommands' insertion order
    # (keys + theme last). Drops the built-in system provider too, so no
    # Maximize/Quit/Screenshot/Theme leaking in out of order.
    COMMANDS = {JigsmithCommands}
    BINDINGS = [
        ("escape", "home", "Home"),
        ("q", "quit", "Quit"),
        # number keys jump between primary tabs — hidden from the footer
        Binding("1", "tab('tab-profile')", "Fingerprint", show=False),
        Binding("2", "tab('tab-forge')", "Forge", show=False),
        Binding("3", "tab('tab-workbench')", "Workbench", show=False),
    ]

    def action_tab(self, tab_id: str) -> None:
        self.open_tab(tab_id)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        discover()          # register any forged component types
        db.init()           # ensure the rack table exists (+ seed if empty)
        settings.init()     # ensure the settings table exists
        self.register_theme(JIGSMITH_THEME)
        self.theme = "jigsmith"   # saved theme applied in on_mount (themes ready)
        self.store = DataStore()
        self.sections = load_profile()

    def compose(self) -> ComposeResult:
        yield JigHeader()
        with TabbedContent(initial="tab-profile", id="tabs"):
            with TabPane("Fingerprint", id="tab-profile"):
                yield ProfileScreen(self.sections, id="profile")
            with TabPane("Forge", id="tab-forge"):
                yield ForgeScreen(id="forge")
            with TabPane("Workbench", id="tab-workbench"):
                yield WorkbenchScreen(id="workbench")
        yield JigFooter()

    # ---- scanner (explicit action) ----
    # `r` runs the FULL pipeline (phases 1-3) and shows a progress popup. Phases
    # 2-3 are agentic (shell out to the claude CLI) — the one documented
    # quarantine exception (see CLAUDE.md). The palette also offers a phase-1-only
    # deterministic run.
    def action_run_miner(self) -> None:
        self.run_scanner()

    def run_scanner(self) -> None:
        # Shared cancel token: the modal sets it (c key), the worker + the agent
        # subprocess poll it. Phase 1 (in-process mine) is checked between phases,
        # not interruptible mid-run; phases 2-3 kill the agent on cancel.
        self._cancel = threading.Event()
        self._progress = PipelineProgress(cancel=self._cancel)
        self.push_screen(self._progress)
        self._run_pipeline_worker()

    def run_miner(self) -> None:
        """Phase-1-only deterministic refresh (fast, no agent)."""
        self.notify("Refreshing aggregates (phase 1)…", timeout=2)
        self._run_miner_worker()

    @work(thread=True, exclusive=True)
    def _run_pipeline_worker(self) -> None:
        cancel = self._cancel
        # Tail the agent's live steps into the modal's log pane. The worker runs
        # off the UI thread, so marshal each line back through call_from_thread.
        def log(line: str) -> None:
            self.call_from_thread(self._progress.append_log, line)
        # Three steps, driven one at a time so the popup can show per-phase state.
        # Agentic phases take the cancel token so a force-exit kills the agent.
        steps = [
            ("Mine", self.store.run_miner),
            ("Analyze", lambda: self.store.analyze_phase(cancel=cancel, on_line=log)),
            ("Report", lambda: self.store.report_phase(cancel=cancel, on_line=log)),
        ]
        ok = True
        last = ""
        for i, (_name, fn) in enumerate(steps):
            if cancel.is_set():
                ok, last = False, "cancelled"
                for j in range(i, len(steps)):
                    self.call_from_thread(self._progress.set_phase, j, "skipped")
                break
            self.call_from_thread(self._progress.set_phase, i, "running")
            step_ok, msg = fn()
            last = msg
            self.call_from_thread(
                self._progress.set_phase, i, "done" if step_ok else "error", msg)
            if not step_ok:
                ok = False
                # mark the rest skipped
                for j in range(i + 1, len(steps)):
                    self.call_from_thread(self._progress.set_phase, j, "skipped")
                break
        self.call_from_thread(self._after_pipeline, ok, last)

    @work(thread=True, exclusive=True)
    def _run_miner_worker(self) -> None:
        ok, msg = self.store.run_miner()
        self.call_from_thread(self._after_miner, ok, msg)

    def _after_pipeline(self, ok: bool, msg: str) -> None:
        # On success the agent rewrote patterns.json + profile.json; reload the
        # spec, re-render, jump to the Profile tab, and auto-close the progress
        # popup so the fresh dashboards just appear — no keypress needed.
        if ok:
            self.sections = load_profile()
            try:
                if isinstance(self.screen, HomeScreen):
                    self.pop_screen()
                self.query_one("#profile", ProfileScreen).update_sections(self.sections)
                # patterns.json was rewritten too — refresh the Forge board in the
                # background so its candidates are current the moment the user tabs
                # over (the screen mounts once; a tab switch won't reload it).
                self.query_one("#forge", ForgeScreen).load()
                self.query_one("#tabs", TabbedContent).active = "tab-profile"
            except Exception:
                pass
            self._progress.finish(ok, "scan complete — showing Fingerprint")
            # brief beat so the ✓ is visible, then dismiss to reveal the dashboards
            self.set_timer(1.0, self._dismiss_progress)
            self.notify("Scan complete — Fingerprint updated", timeout=3)
            return
        # On failure keep the popup up so the error stays readable.
        self._progress.finish(ok, f"stopped: {msg}")

    def _dismiss_progress(self) -> None:
        """Close the pipeline popup if it's still up (user may have closed it)."""
        try:
            if self._progress in self.screen_stack:
                self._progress.dismiss()
        except Exception:
            pass

    # ---- settings (palette → popup pickers) ----
    def open_inspect_picker(self) -> None:
        from tui.screens.config import InspectModal

        def done(ids) -> None:
            if ids:
                self._apply_inspect(ids)

        self.push_screen(InspectModal(), done)

    def open_default_runner_picker(self) -> None:
        from tui.screens.config import DefaultAgentModal

        def done(aid) -> None:
            if aid:
                settings.set_default_agent(aid)
                self.notify(f"default agent: {agents.label(aid)}", timeout=2)

        self.push_screen(DefaultAgentModal(), done)

    def _apply_inspect(self, ids: list[str]) -> None:
        """Persist the agents-to-inspect set + refresh."""
        settings.set_inspect_agents(ids)
        self.notify("agents to inspect updated — run the miner (r) to refresh",
                    timeout=3)

    def _rescan_workbench(self) -> None:
        try:
            self.query_one("#workbench")._rescan()
        except Exception:
            pass

    def _after_miner(self, ok: bool, msg: str) -> None:
        # Phase 1 refreshes raw aggregates only. The Profile is inline spec, so it
        # stays as-is until phases 2-3 rebuild config/profile.json.
        self.notify(
            (("Aggregates refreshed — " if ok else "Phase 1 issues — ") + msg
             + "  ·  run the full scanner (r) for analyze + report"),
            severity="information" if ok else "warning",
        )

    # ---- interactive agent hand-off (the Forge launcher) ----
    # Like the `r` pipeline, this is an explicit, user-triggered crossing of the
    # quarantine boundary (see CLAUDE.md): the developer picks a forge candidate,
    # we suspend the TUI and hand the terminal to a live agent session prefilled
    # with the first prompt. The agent writes to disk; on return the deterministic
    # TUI only re-reads (rack/profile refresh). Never per-frame, never implicit.
    def launch_interactive(self, prompt: str | None = None, *, after=None) -> None:
        asst = agents.default()
        if asst is None or not asst.can_run():
            self.notify("default agent CLI not on PATH — can't launch",
                        severity="error", timeout=4)
            return
        argv = asst.interactive_argv(prompt, add_dir=REPO_ROOT)
        if not argv:
            self.notify(f"{asst.label} has no interactive launcher",
                        severity="warning", timeout=4)
            return
        binary = shutil.which(argv[0])
        try:
            with self.suspend():            # Textual releases the terminal
                subprocess.run([binary, *argv[1:]], cwd=REPO_ROOT)
        except Exception as e:              # noqa: BLE001 - never crash the UI
            self.notify(f"session error: {e}", severity="error", timeout=5)
            return
        self.notify("back from agent session", timeout=2)
        if after:
            after()

    def open_code_assistant(self) -> None:
        """Open the default assistant on the Jigsmith repo to tend the bench.

        A plain interactive session (no prefilled prompt) so the developer can
        ask the agent to change or extend the TUI itself.
        """
        self.launch_interactive()

    # ---- navigation ----
    @staticmethod
    def _tab_bar(tabbed: TabbedContent) -> Tabs:
        """The TabbedContent's own tab bar (a ContentTabs, i.e. Tabs subclass).

        First Tabs in DOM order is this container's bar; nested sub-tab bars
        come later, so `.first()` is always the right one.
        """
        return tabbed.query(Tabs).first()

    def on_mount(self) -> None:
        # Re-style Rich-text boxes whenever the theme changes, and once after the
        # first paint — boxes bake theme colors at render, so anything painted
        # before the theme settled (a startup race) must be recolored.
        self.theme_changed_signal.subscribe(self, self._on_theme_change)
        self.call_after_refresh(self._restyle)
        # apply the saved theme now that the registry is populated (validate first
        # so a stale/removed theme name can't blow up startup)
        saved = settings.theme()
        if saved != self.theme and saved in self.available_themes:
            self.theme = saved
        # first run → onboarding wizard (default agent → agents to inspect), then
        # the launcher; otherwise straight to the launcher.
        if self._needs_onboarding():
            self._onboard()
        else:
            self.push_screen(HomeScreen())

    # ---- onboarding (first run) ----
    def _needs_onboarding(self) -> bool:
        """No agent config saved yet — neither a default nor an inspect set."""
        return (settings.default_agent() is None
                and settings.inspect_agents() is None)

    def _onboard(self) -> None:
        """Ask default agent, then agents to inspect, then reveal the launcher.

        Always persists a value at each step (the auto default if the user just
        confirms/cancels) so onboarding completes and never re-fires.
        """
        from tui.screens.config import DefaultAgentModal, InspectModal

        def finish() -> None:
            self.push_screen(HomeScreen())
            self.notify("Setup done — press r on the Fingerprint to mine your history",
                        timeout=6)

        def after_inspect(ids) -> None:
            chosen = ids or [m.id for m in agents.inspectable()] or ["claude"]
            settings.set_inspect_agents(chosen)
            finish()

        def after_default(aid) -> None:
            default = agents.default()
            settings.set_default_agent(aid or (default.id if default else "claude"))
            self.notify("Step 2/2 — which agents should Jigsmith inspect?", timeout=4)
            self.push_screen(InspectModal(), after_inspect)

        self.notify("Welcome to Jigsmith · Step 1/2 — pick your default agent",
                    timeout=4)
        self.push_screen(DefaultAgentModal(), after_default)

    # ---- home launcher ----
    def action_home(self) -> None:
        """Re-open the launcher (no-op if it's already on top)."""
        if not isinstance(self.screen, HomeScreen):
            self.push_screen(HomeScreen())

    def open_tab(self, tab_id: str) -> None:
        """Reveal the main shell on the chosen tab (called from the launcher).

        The primary tab bar is hidden (CSS) — navigation between sections is the
        home launcher. So we focus the section's own content, not the hidden bar.
        """
        if isinstance(self.screen, HomeScreen):
            self.pop_screen()
        self.query_one("#tabs", TabbedContent).active = tab_id
        self._focus_section(tab_id)

    def _focus_section(self, tab_id: str) -> None:
        """Focus the right widget for the active section after a reveal."""
        try:
            if tab_id == "tab-profile":
                profile = self.query_one("#profile", ProfileScreen)
                try:
                    # the section sub-tabs are the only visible tab bar
                    self._tab_bar(
                        profile.query_one("#section-tabs", TabbedContent)).focus()
                except Exception:
                    # empty profile (no sections yet) → no sub-tab bar exists;
                    # focus the screen itself so its `r` (run scanner) binding lives
                    profile.focus()
            elif tab_id == "tab-workbench":
                from textual.widgets import DataTable
                self.query_one("#workbench").query(DataTable).first().focus()
            elif tab_id == "tab-forge":
                from textual.widgets import DataTable
                self.query_one("#forge").query(DataTable).first().focus()
        except Exception:
            pass

    def _on_theme_change(self, _theme) -> None:
        # Theme is changed from the command palette; persist it so it's remembered.
        self._restyle()
        try:
            settings.set_theme(self.theme)
        except Exception:
            pass

    def _restyle(self) -> None:
        from tui.panels.components import BoxBase
        from tui.panels.contract import Counter

        for box in self.query(BoxBase):
            box.refresh_style()
        for counter in self.query(Counter):
            counter.refresh_style()

    def goto_view(self, view_id: str) -> None:
        self.query_one("#tabs", TabbedContent).active = "tab-profile"
        self.query_one("#profile", ProfileScreen).show_section(view_id)

    # ---- dynamic feature tabs (palette/promotion target) ----
    def open_feature_tab(self, title: str, widget, tab_id: str) -> None:
        """Promote a heavy feature into its own closeable tab.

        Light, contextual features should stay as drawers/modals; use this only
        when a feature needs full width + sustained focus.
        """
        tabs = self.query_one("#tabs", TabbedContent)
        tabs.add_pane(TabPane(title, widget, id=tab_id))
        tabs.active = tab_id


if __name__ == "__main__":
    JigsmithApp().run()
