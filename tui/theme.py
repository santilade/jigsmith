"""Jigsmith brand palette — the template colors, in one place.

Two brand colors (light blue + orange) plus neutrals. Edit these to reskin the
whole TUI: the constants drive the Python render code (bars, counters, blocks),
and `JIGSMITH_THEME` feeds Textual so the CSS `$primary` / `$accent` resolve to
the same values (borders, titles, tab underline).
"""
from __future__ import annotations

from textual.theme import Theme

# --- the two template colors ---
BLUE = "#36c5d0"      # light blue — data, values, borders, focus
ORANGE = "#ff8c42"    # orange — titles, emphasis, the craft card

# --- neutrals ---
GRAY = "#8a8a8a"      # muted notes / the read
WHITE = "#e6e6e6"     # primary text

JIGSMITH_THEME = Theme(
    name="jigsmith",
    primary=BLUE,       # data, values, borders, tab underline
    secondary=ORANGE,
    accent=ORANGE,      # box titles, highlight / hot stats
    warning=ORANGE,     # the craft "leave it alone" card
    foreground=WHITE,
    dark=True,
)


def theme_colors(app) -> dict:
    """Resolve the active theme's semantic roles to concrete colors.

    Render code references roles (data/accent/warning/note/text) so the charts
    inherit whatever theme is active — nothing is hardcoded at the call site.
    """
    v = app.get_css_variables()

    def hexish(value, fallback):
        # CSS vars like text-muted resolve to expressions ("auto 60%") that Rich
        # can't parse; only accept concrete colors, else fall back.
        value = str(value)
        return value if value.startswith("#") else fallback

    return {
        "data": hexish(v.get("primary"), BLUE),      # bars, normal values
        "accent": hexish(v.get("accent"), ORANGE),   # hot stats, emphasis
        "warning": hexish(v.get("warning"), ORANGE), # craft card
        "note": "dim",                               # the read (muted foreground)
        "text": hexish(v.get("foreground"), WHITE),  # primary text
    }
