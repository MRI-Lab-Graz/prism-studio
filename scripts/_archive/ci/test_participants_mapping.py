#!/usr/bin/env python3
"""Deprecated shim. Use tests/test_participants_mapping.py instead."""

import os
import sys


def main():
    target = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "tests",
        "test_participants_mapping.py",
    )
    if os.path.exists(target):
        os.execv(sys.executable, [sys.executable, target] + sys.argv[1:])
    print("Moved to tests/test_participants_mapping.py")
    sys.exit(1)


if __name__ == "__main__":
    main()
