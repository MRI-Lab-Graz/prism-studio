"""Parser construction helpers for prism_tools CLI.

In Phase 2 this module hosts foundational parser utilities; command
registration will be migrated here incrementally in later phases.
"""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    """Create a base parser for prism_tools.

    Note: command tree migration from app/prism_tools.py is intentionally
    incremental to preserve behavior.
    """
    return argparse.ArgumentParser(
        description="Prism Tools: Utilities for PRISM/BIDS datasets"
    )
