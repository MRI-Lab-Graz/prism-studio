"""Compatibility shim for shared tabular file reader.

Delegates runtime symbols to canonical backend module:
`src/converters/file_reader.py`.
"""

from __future__ import annotations

from src._compat import load_canonical_module

_src_file_reader = load_canonical_module(
    current_file=__file__,
    canonical_rel_path="converters/file_reader.py",
    alias="prism_backend_converters_file_reader",
)

for _name in dir(_src_file_reader):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_src_file_reader, _name)
