"""Compatibility bridge for mirrored app converter shims.

Some mirrored modules under app/src import `src._compat` to obtain
`load_canonical_module`. In repo-root runtimes, top-level `src` is the backend
package, so this bridge forwards to app/src/_compat.py.
"""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType
from typing import Callable

_APP_COMPAT_ALIAS = "prism_app_src_compat_bridge"


def _load_app_compat_module() -> ModuleType:
    existing = sys.modules.get(_APP_COMPAT_ALIAS)
    if isinstance(existing, ModuleType):
        return existing

    repo_root = Path(__file__).resolve().parents[1]
    app_compat_path = repo_root / "app" / "src" / "_compat.py"
    if not app_compat_path.exists():
        raise ImportError(f"Missing compatibility helper: {app_compat_path}")

    spec = spec_from_file_location(_APP_COMPAT_ALIAS, str(app_compat_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load compatibility helper: {app_compat_path}")

    module = module_from_spec(spec)
    sys.modules[_APP_COMPAT_ALIAS] = module
    spec.loader.exec_module(module)
    return module


_app_compat = _load_app_compat_module()
_load_canonical = getattr(_app_compat, "load_canonical_module", None)
if not callable(_load_canonical):
    raise ImportError("app/src/_compat.py does not export load_canonical_module")

load_canonical_module: Callable[..., ModuleType] = _load_canonical

__all__ = ["load_canonical_module"]
