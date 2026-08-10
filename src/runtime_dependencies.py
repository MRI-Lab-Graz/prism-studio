"""Runtime dependency probes shared by CLI, web, and bundle smoke checks."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any


def _inspect_module_support(
    module_name: str,
    bundle_root: str | Path | None,
    *,
    write_attr: str,
    version_attrs: tuple[str, ...],
    keys: dict[str, str],
) -> dict[str, Any]:
    """Describe whether `module_name` is importable and exposes `write_attr`.

    `keys` maps the generic internal field names (importable, write_support,
    namespace_bundle_stub, module_file, module_path, available_attrs,
    bundle_entries, error) to the actual output dict key names, since
    `inspect_pyreadstat_write_support` and `inspect_pandas_support` use
    different (and only partially symmetric) key-prefixing conventions so
    their results can be dict-merged into one payload without colliding.
    """

    bundle_entries: list[str] = []
    normalized_bundle_root: Path | None = None
    if bundle_root is not None:
        normalized_bundle_root = Path(bundle_root).resolve()
        bundle_entries = sorted(
            path.name for path in normalized_bundle_root.glob(f"{module_name}*")
        )

    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        return {
            keys["importable"]: False,
            keys["write_support"]: False,
            keys["namespace_bundle_stub"]: False,
            keys["module_file"]: None,
            keys["module_path"]: [],
            keys["available_attrs"]: [],
            keys["bundle_entries"]: bundle_entries,
            keys["error"]: f"{type(exc).__name__}: {exc}",
        }
    except Exception as exc:
        return {
            keys["importable"]: False,
            keys["write_support"]: False,
            keys["namespace_bundle_stub"]: False,
            keys["module_file"]: None,
            keys["module_path"]: [],
            keys["available_attrs"]: [],
            keys["bundle_entries"]: bundle_entries,
            keys["error"]: f"{type(exc).__name__}: {exc}",
        }

    module_file = getattr(module, "__file__", None)
    module_path = [str(Path(path).resolve()) for path in getattr(module, "__path__", [])]
    available_attrs = [name for name in version_attrs if hasattr(module, name)]

    namespace_bundle_stub = False
    if normalized_bundle_root is not None and bundle_entries:
        bundled_namespace_path = str((normalized_bundle_root / module_name).resolve())
        namespace_bundle_stub = module_file is None and bundled_namespace_path in module_path

    return {
        keys["importable"]: True,
        keys["write_support"]: hasattr(module, write_attr),
        keys["namespace_bundle_stub"]: namespace_bundle_stub,
        keys["module_file"]: module_file,
        keys["module_path"]: module_path,
        keys["available_attrs"]: available_attrs,
        keys["bundle_entries"]: bundle_entries,
        keys["error"]: None,
    }


def inspect_pyreadstat_write_support(
    bundle_root: str | Path | None = None,
) -> dict[str, Any]:
    """Describe whether pyreadstat is importable and exposes SPSS write support."""
    return _inspect_module_support(
        "pyreadstat",
        bundle_root,
        write_attr="write_sav",
        version_attrs=("__version__", "read_sav", "write_sav", "read_dta", "write_dta"),
        keys={
            "importable": "pyreadstat_importable",
            "write_support": "pyreadstat_write_support",
            "namespace_bundle_stub": "namespace_bundle_stub",
            "module_file": "module_file",
            "module_path": "module_path",
            "available_attrs": "available_attrs",
            "bundle_entries": "bundle_entries",
            "error": "error",
        },
    )


def inspect_pandas_support(bundle_root: str | Path | None = None) -> dict[str, Any]:
    """Describe whether pandas is importable and exposes core dataframe APIs."""
    return _inspect_module_support(
        "pandas",
        bundle_root,
        write_attr="DataFrame",
        version_attrs=("__version__", "DataFrame", "Series", "read_csv"),
        keys={
            "importable": "pandas_importable",
            "write_support": "pandas_dataframe_support",
            "namespace_bundle_stub": "pandas_namespace_bundle_stub",
            "module_file": "pandas_module_file",
            "module_path": "pandas_module_path",
            "available_attrs": "pandas_available_attrs",
            "bundle_entries": "pandas_bundle_entries",
            "error": "pandas_error",
        },
    )


def has_pyreadstat_write_support() -> bool:
    """Return whether pyreadstat can write SPSS .sav files in this runtime."""

    details = inspect_pyreadstat_write_support()
    return bool(details["pyreadstat_write_support"])
