"""Compatibility helpers for loading canonical backend modules from repository `src/`.

These helpers are used by mirrored modules under `app/src/` during migration to
avoid ambiguous package resolution between `app/src` and top-level `src`.
"""

from __future__ import annotations

import inspect
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import types
from types import ModuleType
import warnings

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


def _resolve_canonical_path(current_path: Path, canonical_rel_path: str) -> Path | None:
    # Prefer an ancestor that actually contains the requested canonical file.
    for parent in [current_path.parent, *current_path.parents]:
        candidate = parent / "src" / canonical_rel_path
        if candidate.resolve() == current_path.resolve():
            continue
        if candidate.exists() and candidate.is_file():
            return candidate

    # Fallback: scan sys.path for editable/dev installs where cwd ancestry is not enough.
    for entry in sys.path:
        try:
            base = Path(entry).resolve()
        except Exception:
            continue
        candidate = base / "src" / canonical_rel_path
        if candidate.exists() and candidate.is_file():
            return candidate

    return None


def _caller_module_fallback() -> ModuleType:
    # Let mirrored app/src modules continue using their in-file implementation
    # when canonical src/ modules are unavailable in a packaged/runtime context.
    frame = inspect.currentframe()
    caller_frame = frame.f_back if frame is not None else None
    grandcaller_frame = caller_frame.f_back if caller_frame is not None else None
    caller_globals = (
        grandcaller_frame.f_globals if grandcaller_frame is not None else {}
    )
    caller_name = str(caller_globals.get("__name__") or "")
    existing_module = sys.modules.get(caller_name)
    if isinstance(existing_module, ModuleType):
        return existing_module

    module = types.ModuleType(caller_name or "__main__")
    module.__dict__.update(caller_globals)
    sys.modules[module.__name__] = module
    return module


def load_canonical_module(
    *, current_file: str, canonical_rel_path: str, alias: str
) -> ModuleType:
    current_path = Path(current_file).resolve()
    canonical_path = _resolve_canonical_path(current_path, canonical_rel_path)

    if canonical_path is None:
        warnings.warn(
            (
                "Canonical module not found for "
                f"'{canonical_rel_path}'. Using mirrored module implementation."
            ),
            RuntimeWarning,
            stacklevel=2,
        )
        return _caller_module_fallback()

    # Canonical path is always repo_root/src/<canonical_rel_path>.
    repo_root = canonical_path.parent.parent

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
        raise ImportError(
            f"Unable to create spec for canonical module: {canonical_path}"
        )

    module = module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
