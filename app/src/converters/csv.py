"""Compatibility shim for survey CSV conversion.

Delegates runtime symbols to canonical backend module:
`src/converters/csv.py`.
"""

from __future__ import annotations

from src._compat import load_canonical_module

_src_csv = load_canonical_module(
    current_file=__file__,
    canonical_rel_path="converters/csv.py",
    alias="prism_backend_converters_csv",
)

for _name in dir(_src_csv):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_src_csv, _name)