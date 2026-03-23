#!/usr/bin/env python3
"""Smoke-test imports from the built PyInstaller bundle.

This catches runtime packaging issues where mirrored app modules recurse while
trying to resolve canonical backend modules.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path


def _require_import(module_name: str) -> None:
    importlib.import_module(module_name)


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test bundled imports")
    parser.add_argument(
        "--bundle-root",
        default="dist/PrismStudio/_internal",
        help="Path containing bundled src/ package",
    )
    args = parser.parse_args()

    bundle_root = Path(args.bundle_root).resolve()
    if not bundle_root.exists() or not bundle_root.is_dir():
        raise SystemExit(f"Bundle root not found: {bundle_root}")

    src_dir = bundle_root / "src"
    if not src_dir.exists() or not src_dir.is_dir():
        raise SystemExit(f"Bundled src directory not found: {src_dir}")

    # Mirror frozen runtime import precedence where bundled modules win.
    sys.path.insert(0, str(bundle_root))

    required_modules = [
        "src.participants_converter",
        "src.web.blueprints.conversion",
        "src.recipes_surveys",
    ]

    for module_name in required_modules:
        _require_import(module_name)

    from src.recipes_surveys import compute_survey_recipes

    if compute_survey_recipes is None:
        raise SystemExit("compute_survey_recipes resolved to None")

    print("[OK] Bundled import smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
