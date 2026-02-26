#!/usr/bin/env python3
"""Compatibility wrapper for moved script.

Use scripts/maintenance/generate_recipes.py as the canonical location.
"""

from pathlib import Path
import runpy


if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "maintenance" / "generate_recipes.py"
    runpy.run_path(str(target), run_name="__main__")
