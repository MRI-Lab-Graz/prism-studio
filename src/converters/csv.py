"""Compatibility layer for survey CSV processing.

Re-exports public symbols from the existing converter implementation under
`app/src/converters/csv.py` via file-path loading, keeping historical
`src.converters.csv` imports functional during modularization.
"""

from __future__ import annotations

import sys
import types
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _ensure_package(module_name: str, package_path: Path) -> None:
    existing = sys.modules.get(module_name)
    if existing is not None:
        if not hasattr(existing, "__path__"):
            existing.__path__ = [str(package_path)]
        return

    package_module = types.ModuleType(module_name)
    package_module.__path__ = [str(package_path)]
    package_module.__package__ = module_name
    sys.modules[module_name] = package_module


def _load_impl_module():
    repo_root = Path(__file__).resolve().parents[2]
    impl_path = repo_root / "app" / "src" / "converters" / "csv.py"
    _ensure_package("app", repo_root / "app")
    _ensure_package("app.src", repo_root / "app" / "src")
    _ensure_package("app.src.converters", repo_root / "app" / "src" / "converters")

    module_name = "app.src.converters.csv"
    spec = spec_from_file_location(module_name, impl_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load CSV converter implementation: {impl_path}")
    module = module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_impl = _load_impl_module()

for _name in dir(_impl):
    if _name.startswith("_"):
        continue
    globals()[_name] = getattr(_impl, _name)

__all__ = [name for name in globals() if not name.startswith("_")]
