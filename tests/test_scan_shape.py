"""Validator tests for the uniform suggestion shape.

Dependency-free (no pytest yet): run with `uv run python tests/test_scan_shape.py`.
Covers the defensive normalization the scanner leans on so one sloppy analyst
field never sinks a run.
"""
from __future__ import annotations

import sys

from core.scan import shape

FULL = {
    "name": "Raw git by hand",
    "section": "ignored-when-forced",
    "painpoint": "drive git by hand daily",
    "frequency": "x38",
    "evidence": "git x38; lazygit idle",
    "fix": {"approach": "download", "tool_type": "CLI", "summary": "adopt lazygit",
            "what": "lazygit", "why": "covers it", "where": "PATH"},
    "gate": {"kind": "suggest", "mechanical_or_craft": "mechanical",
             "payback": "directional", "confidence": "medium"},
}


def test_full_roundtrips():
    n = shape.normalize(FULL, section="shell")
    assert n is not None
    assert n["section"] == "shell"            # forced to the lens
    assert n["fix"]["approach"] == "download"
    assert n["gate"]["kind"] == "suggest"


def test_bad_enums_default_not_drop():
    raw = {"name": "X", "painpoint": "p",
           "fix": {"approach": "weird"}, "gate": {"kind": "nope", "mechanical_or_craft": "?"}}
    n = shape.normalize(raw, section="loop")
    assert n["fix"]["approach"] == "custom"
    assert n["gate"]["kind"] == "suggest"
    assert n["gate"]["mechanical_or_craft"] == "mechanical"


def test_missing_core_fields_drop():
    assert shape.normalize({"painpoint": "p"}, section="loop") is None   # no name
    assert shape.normalize({"name": "n"}, section="loop") is None        # no painpoint
    assert shape.normalize("not a dict", section="loop") is None


def test_section_none_keeps_own():
    raw = dict(FULL, section="harness")
    n = shape.normalize(raw, section=None)
    assert n["section"] == "harness"          # rollup keeps the item's own lens


def test_normalize_many_container_forms():
    assert shape.normalize_many([], section="loop") == []                # clean lens
    assert shape.normalize_many("garbage", section="loop") is None       # retry signal
    assert shape.normalize_many(None, section="loop") is None
    assert len(shape.normalize_many([FULL, FULL], section="loop")) == 2
    assert len(shape.normalize_many({"suggestions": [FULL]}, section="loop")) == 1
    assert len(shape.normalize_many({"patterns": [FULL]}, section=None)) == 1


def test_normalize_many_drops_only_bad_items():
    items = [FULL, {"name": "no pain"}, dict(FULL, name="ok2")]
    out = shape.normalize_many(items, section="loop")
    assert len(out) == 2                       # the nameless-pain one dropped, rest kept


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  ok  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
