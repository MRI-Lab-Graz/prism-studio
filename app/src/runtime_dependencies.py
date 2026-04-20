"""Compatibility shim for runtime dependency probes backend."""

from __future__ import annotations

from src._compat import load_canonical_module

_src_runtime_dependencies = load_canonical_module(
    current_file=__file__,
    canonical_rel_path="runtime_dependencies.py",
    alias="prism_backend_runtime_dependencies",
)

for _name in dir(_src_runtime_dependencies):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_src_runtime_dependencies, _name)

del _name
del _src_runtime_dependencies
