#!/usr/bin/env python3
"""Compatibility wrapper for moved script."""

import os
import runpy
import sys


def main():
    target = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "ci",
        "test_web_config.py",
    )
    if not os.path.exists(target):
        print(f"Moved script not found: {target}")
        sys.exit(1)
    sys.path.insert(0, os.path.dirname(target))
    runpy.run_path(target, run_name="__main__")


if __name__ == "__main__":
    main()
