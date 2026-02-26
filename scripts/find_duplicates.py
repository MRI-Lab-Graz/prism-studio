#!/usr/bin/env python3
"""Compatibility wrapper for moved script.

Use scripts/dev/find_duplicates.py as the canonical location.
"""

from pathlib import Path
import runpy


if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "dev" / "find_duplicates.py"
    runpy.run_path(str(target), run_name="__main__")
