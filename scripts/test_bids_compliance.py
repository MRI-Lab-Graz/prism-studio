#!/usr/bin/env python3
"""Compatibility wrapper for moved script.

Use scripts/ci/test_bids_compliance.py as the canonical location.
"""

from pathlib import Path
import runpy


if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "ci" / "test_bids_compliance.py"
    runpy.run_path(str(target), run_name="__main__")
