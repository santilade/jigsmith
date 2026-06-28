---
name: forge-component
description: Add a new reusable Profile component TYPE to Jigsmith (rare). Use only when no existing component (counters, bars, histogram, blocks, prose) can render a finding the developer wants. Most Profile work is data, not code — prefer build-profile. This adds Python in tui/panels/forged/.
---

# Forge a component

Components are the **fixed building blocks** the Profile is composed from. You
rarely need a new one — the existing set (`counters`, `bars`, `histogram`,
`blocks`, `prose`) covers most findings, and new content is just a box spec
(`build-profile`). Add a component type only for a genuinely new *shape* of box.

## Contract

A component is a box renderer driven entirely by its inline spec — it never reads
the miner JSON (quarantine). Most subclass `BoxBase` (bordered chrome) and
implement `render_box(self) -> Rich renderable`. Register with `@component`.

```python
# tui/panels/forged/heatmap.py
from rich.text import Text
from tui.panels.components import BoxBase, component
from tui.panels.contract import GRAY

@component("heatmap")
class HeatmapBox(BoxBase):
    def render_box(self):
        grid = self.spec.get("data") or []      # inline data from the spec
        out = Text()
        # ... render grid ...
        return out
```

- For a **full-width, width-responsive** box (like `histogram`), override
  `render(self)` instead and read `self.content_size.width`; set `border_title`
  in `on_mount`.
- For a **multi-widget** box (like `counters`), subclass a container
  (`Horizontal`) and mount children in `on_mount`.

## Steps

1. Add the module under `tui/panels/forged/<name>.py` with `@component("<name>")`.
   `discover()` imports it automatically.
2. Verify it registers:
   ```bash
   uv run python -c "from tui.panels import discover; from tui.panels.components import COMPONENTS; discover(); print('<name>' in COMPONENTS)"
   ```
3. Use it from `tui/config/profile.json` via `build-profile`:
   `{"component": "<name>", ...}`.

## Rules

- Components are deterministic and inline-only — no store/agent access at render.
- `render_box` must not raise on missing keys; degrade gracefully.
- Disposable: delete the module + any spec entries that reference it.
