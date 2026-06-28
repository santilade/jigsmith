"""Profile components.

Core components live in `components.py` (imported here so their `@component`
decorators register). Custom component *types* you forge go in `forged/` and are
picked up by `discover()`. Content (which boxes, what data) is NOT here — that's
the agent-authored spec in `config/profile.json`.
"""
from __future__ import annotations

import importlib
import pkgutil

# importing components registers the core component types
from tui.panels.components import COMPONENTS, build_box, component  # noqa: F401
from tui.panels.contract import Counter, hbars, note  # noqa: F401


def discover() -> None:
    """Import forged component modules so their @component decorators run."""
    from tui.panels import forged

    for mod in pkgutil.iter_modules(forged.__path__):
        if not mod.name.startswith("_"):
            importlib.import_module(f"tui.panels.forged.{mod.name}")
