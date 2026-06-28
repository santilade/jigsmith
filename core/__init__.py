"""Jigsmith deterministic engine — ingest, signals, inventory, stores.

Agent-agnostic by construction: every source is read by a format parser into one
normalized Event stream, signals are computed off that stream, and the agentic
layer only ever reads the JSON this package writes. See ARCHITECTURE.md.
"""
__version__ = "0.2.0"
