"""Compatibility shim for biometrics dataset conversion.

Delegates runtime symbols to canonical backend module:
`src/converters/biometrics.py`.
"""

from __future__ import annotations

from src._compat import load_canonical_module

_src_biometrics = load_canonical_module(
    current_file=__file__,
    canonical_rel_path="converters/biometrics.py",
    alias="prism_backend_converters_biometrics",
)

for _name in dir(_src_biometrics):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_src_biometrics, _name)