#!/usr/bin/env python3
"""Smoke-test imports from the built PyInstaller bundle.

This catches runtime packaging issues where mirrored app modules recurse while
trying to resolve canonical backend modules.
"""

from __future__ import annotations

import argparse
import importlib
import sys
import types
from pathlib import Path


def _require_import(module_name: str) -> None:
    importlib.import_module(module_name)


def _install_pandas_smoke_stub() -> None:
    placeholder_type = type("SmokePandasPlaceholder", (), {})

    def _placeholder_callable(*_args, **_kwargs):
        return None

    smoke_module = types.ModuleType("pandas")
    smoke_module.__file__ = "<smoke-stub>"
    smoke_module.DataFrame = placeholder_type
    smoke_module.Series = placeholder_type
    smoke_module.Index = placeholder_type
    smoke_module.NA = None

    def _module_getattr(name: str):
        if name and name[0].isupper():
            return placeholder_type
        return _placeholder_callable

    smoke_module.__getattr__ = _module_getattr  # type: ignore[attr-defined]
    sys.modules["pandas"] = smoke_module


def _prepare_pandas_for_plain_python_import(bundle_root: Path) -> None:
    try:
        pandas_module = importlib.import_module("pandas")
    except ModuleNotFoundError as exc:
        if exc.name != "pandas":
            raise
        print(
            "[WARN] pandas is not directly importable from bundle files under plain Python; "
            "installing a local smoke stub and deferring real pandas validation to the packaged web smoke."
        )
        _install_pandas_smoke_stub()
        return

    if hasattr(pandas_module, "DataFrame"):
        return

    module_file = getattr(pandas_module, "__file__", None)
    module_path = list(getattr(pandas_module, "__path__", []))
    bundled_pandas_entries = sorted(path.name for path in bundle_root.glob("pandas*"))
    bundled_namespace_path = str((bundle_root / "pandas").resolve())

    if module_file is None and bundled_pandas_entries and bundled_namespace_path in module_path:
        print(
            "[WARN] pandas resolved as a namespace-style bundle stub under plain Python; "
            "installing a local smoke stub and deferring real pandas validation to the packaged web smoke. "
            f"path={module_path!r} bundle_entries={bundled_pandas_entries!r}"
        )
        _install_pandas_smoke_stub()
        return

    available_attrs = [
        name
        for name in ("__version__", "Series", "DataFrame", "Index")
        if hasattr(pandas_module, name)
    ]
    raise SystemExit(
        "Bundled pandas import is incomplete outside the PyInstaller bootloader. "
        f"file={module_file!r} path={module_path!r} attrs={available_attrs!r} "
        f"bundle_entries={bundled_pandas_entries!r} sys_path_head={sys.path[:5]!r}"
    )


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _build_isolated_sys_path(bundle_root: Path) -> list[str]:
    repo_root = Path(__file__).resolve().parents[2]
    isolated: list[str] = [str(bundle_root)]

    for archive in sorted(bundle_root.glob("*.zip")):
        archive_text = str(archive.resolve())
        if archive_text not in isolated:
            isolated.append(archive_text)

    for entry in sys.path:
        if not entry:
            continue

        entry_path = Path(entry).resolve()
        entry_text = str(entry_path)
        lowered = entry_text.lower()

        if "site-packages" in lowered or "dist-packages" in lowered:
            continue
        if _is_under(entry_path, repo_root):
            continue
        if entry_text not in isolated:
            isolated.append(entry_text)

    return isolated


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

    # Mirror frozen runtime import precedence while preventing the builder's
    # site-packages from masking missing dependencies in the bundle.
    sys.path[:] = _build_isolated_sys_path(bundle_root)
    _prepare_pandas_for_plain_python_import(bundle_root)

    required_modules = [
        "src.participants_converter",
        "src.recipes_surveys",
        "src.web.validation",
        "src.web.reporting_utils",
    ]

    for module_name in required_modules:
        _require_import(module_name)

    from src.recipes_surveys import compute_survey_recipes
    from src.converters.wide_to_long import detect_wide_session_prefixes

    if compute_survey_recipes is None:
        raise SystemExit("compute_survey_recipes resolved to None")
    if not callable(detect_wide_session_prefixes):
        raise SystemExit("detect_wide_session_prefixes is not callable")

    print("[OK] Bundled import smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
