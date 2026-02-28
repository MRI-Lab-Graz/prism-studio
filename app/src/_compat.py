"""Compatibility helpers for loading canonical backend modules from repository `src/`.

These helpers are used by mirrored modules under `app/src/` during migration to
avoid ambiguous package resolution between `app/src` and top-level `src`.
"""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import types
from types import ModuleType


_SYNTHETIC_ROOT = "prism_backend_src"


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


def _default_alias(canonical_rel_path: str) -> str:
    rel_mod = canonical_rel_path.replace(".py", "").replace("/", ".")
    return f"{_SYNTHETIC_ROOT}.{rel_mod}"


def load_canonical_module(*, current_file: str, canonical_rel_path: str, alias: str) -> ModuleType:
    current_path = Path(current_file).resolve()
    repo_root = current_path.parent
    while repo_root.parent != repo_root:
        if (repo_root / "src").is_dir() and (repo_root / "app").is_dir():
            break
        repo_root = repo_root.parent
    canonical_path = repo_root / "src" / canonical_rel_path

    if not canonical_path.exists():
        raise ImportError(f"Canonical module not found: {canonical_path}")

    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)

    module_name = alias if "." in alias else _default_alias(canonical_rel_path)
    module_parts = module_name.split(".")
    if len(module_parts) > 1:
        for depth in range(1, len(module_parts)):
            pkg_name = ".".join(module_parts[:depth])
            rel_parts = module_parts[1:depth]
            pkg_path = (repo_root / "src").joinpath(*rel_parts)
            _ensure_package(pkg_name, pkg_path)

    spec = spec_from_file_location(module_name, canonical_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to create spec for canonical module: {canonical_path}")

    module = module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
