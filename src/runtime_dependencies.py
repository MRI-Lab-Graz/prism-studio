"""Runtime dependency probes shared by CLI, web, and bundle smoke checks."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any


def inspect_pyreadstat_write_support(
    bundle_root: str | Path | None = None,
) -> dict[str, Any]:
    """Describe whether pyreadstat is importable and exposes SPSS write support."""

    bundle_entries: list[str] = []
    normalized_bundle_root: Path | None = None
    if bundle_root is not None:
        normalized_bundle_root = Path(bundle_root).resolve()
        bundle_entries = sorted(path.name for path in normalized_bundle_root.glob("pyreadstat*"))

    try:
        pyreadstat_module = importlib.import_module("pyreadstat")
    except ModuleNotFoundError as exc:
        return {
            "pyreadstat_importable": False,
            "pyreadstat_write_support": False,
            "namespace_bundle_stub": False,
            "module_file": None,
            "module_path": [],
            "available_attrs": [],
            "bundle_entries": bundle_entries,
            "error": f"{type(exc).__name__}: {exc}",
        }
    except Exception as exc:
        return {
            "pyreadstat_importable": False,
            "pyreadstat_write_support": False,
            "namespace_bundle_stub": False,
            "module_file": None,
            "module_path": [],
            "available_attrs": [],
            "bundle_entries": bundle_entries,
            "error": f"{type(exc).__name__}: {exc}",
        }

    module_file = getattr(pyreadstat_module, "__file__", None)
    module_path = [str(Path(path).resolve()) for path in getattr(pyreadstat_module, "__path__", [])]
    available_attrs = [
        name
        for name in ("__version__", "read_sav", "write_sav", "read_dta", "write_dta")
        if hasattr(pyreadstat_module, name)
    ]

    namespace_bundle_stub = False
    if normalized_bundle_root is not None and bundle_entries:
        bundled_namespace_path = str((normalized_bundle_root / "pyreadstat").resolve())
        namespace_bundle_stub = module_file is None and bundled_namespace_path in module_path

    return {
        "pyreadstat_importable": True,
        "pyreadstat_write_support": hasattr(pyreadstat_module, "write_sav"),
        "namespace_bundle_stub": namespace_bundle_stub,
        "module_file": module_file,
        "module_path": module_path,
        "available_attrs": available_attrs,
        "bundle_entries": bundle_entries,
        "error": None,
    }


def has_pyreadstat_write_support() -> bool:
    """Return whether pyreadstat can write SPSS .sav files in this runtime."""

    details = inspect_pyreadstat_write_support()
    return bool(details["pyreadstat_write_support"])