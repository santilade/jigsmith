"""Home screen — the launcher.

A full-screen overlay shown at startup (and re-openable with `h`). Displays the
Jigsmith logo and a small dashboard-style menu (label left, key hint right),
centered like a neovim start screen. Picking pops this screen and activates the
chosen tab in the main shell (the default screen, which holds the TabbedContent
and all its infra).
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Center, Middle, Vertical
from textual.screen import Screen
from textual.widgets import Label, ListItem, ListView, Static

LOGO = r"""
    .S   .S    sSSSSs    sSSs   .S_SsS_S.    .S  sdSS_SSSSSSbs   .S    S.
   .SS  .SS   d%%%%SP   d%%SP  .SS~S*S~SS.  .SS  YSSS~S%SSSSSP  .SS    SS.
   S%S  S%S  d%S'      d%S'    S%S `Y' S%S  S%S       S%S       S%S    S%S
   S%S  S%S  S%S       S%|     S%S     S%S  S%S       S%S       S%S    S%S
   S&S  S&S  S&S       S&S     S%S     S%S  S&S       S&S       S%S SSSS%S
   S&S  S&S  S&S       Y&Ss    S&S     S&S  S&S       S&S       S&S  SSS&S
   S&S  S&S  S&S       `S&&S   S&S     S&S  S&S       S&S       S&S    S&S
   S&S  S&S  S&S sSSs    `S*S  S&S     S&S  S&S       S&S       S&S    S&S
   d*S  S*S  S*b `S%%     l*S  S*S     S*S  S*S       S*S       S*S    S*S
  .S*S  S*S  S*S   S%    .S*P  S*S     S*S  S*S       S*S       S*S    S*S
sdSSS   S*S   SS_sSSS  sSS*S   S*S     S*S  S*S       S*S       S*S    S*S
YSSY    S*S    Y~YSSY  YSS'    SSS     S*S  S*S       S*S       SSS    S*S
        SP                             SP   SP        SP               SP
        Y                              Y    Y         Y                Y
"""

# (item id, label, key hint, tab id — None means quit, PALETTE means palette)
PALETTE = "__palette__"
MENU = [
    ("home-profile", "Fingerprint", "1", "tab-profile"),
    ("home-forge", "Forge", "2", "tab-forge"),
    ("home-workbench", "Workbench", "3", "tab-workbench"),
    ("home-palette", "Command palette", "^p", PALETTE),
    ("home-quit", "Quit", "q", None),
]
_PICK = {item_id: tab for item_id, _l, _k, tab in MENU}

_MENU_W = 28  # inner text width for the label/key columns


def _row(label: str, key: str) -> str:
    pad = _MENU_W - len(label) - len(key)
    return f"{label}{' ' * max(1, pad)}[dim]{key}[/dim]"


class HomeScreen(Screen):
    BINDINGS = [
        ("1", "pick('tab-profile')", "Fingerprint"),
        ("2", "pick('tab-forge')", "Forge"),
        ("3", "pick('tab-workbench')", "Workbench"),
        ("q", "app.quit", "Quit"),
        ("escape", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        with Middle(id="home"):
            with Center():
                yield Static(LOGO, id="home-logo")
            with Center():
                with ListView(id="home-menu"):
                    for item_id, label, key, _tab in MENU:
                        yield ListItem(Label(_row(label, key)), id=item_id)
            with Center():
                yield Static(
                    "[b]jig[/b]  [dim]/dʒɪɡ/[/dim]  [i]noun[/i]\n"
                    "a custom-made tool that holds the work and guides another "
                    "tool, so a repetitive task comes out right every time",
                    id="home-tagline")

    def on_mount(self) -> None:
        self.query_one("#home-menu", ListView).focus()

    def action_pick(self, tab_id: str) -> None:
        self.app.open_tab(tab_id)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        tab = _PICK.get(event.item.id)
        if tab == PALETTE:
            self.app.action_command_palette()
        elif tab is None:
            self.app.exit()
        else:
            self.app.open_tab(tab)
