"""Compatibility shim for wide-to-long conversion utilities.

Delegates runtime symbols to canonical backend module:
`src/converters/wide_to_long.py`.
"""

from __future__ import annotations

from src._compat import load_canonical_module

_src_wide_to_long = load_canonical_module(
    current_file=__file__,
    canonical_rel_path="converters/wide_to_long.py",
    alias="prism_backend_converters_wide_to_long",
)

for _name in dir(_src_wide_to_long):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_src_wide_to_long, _name)
