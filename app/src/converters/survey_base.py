"""Compatibility shim for base survey converter helpers.

Delegates runtime symbols to canonical backend module:
`src/converters/survey_base.py`.
"""

from __future__ import annotations

from src._compat import load_canonical_module

_src_survey_base = load_canonical_module(
	current_file=__file__,
	canonical_rel_path="converters/survey_base.py",
	alias="prism_backend_converters_survey_base",
)

for _name in dir(_src_survey_base):
	if not _name.startswith("__"):
		globals()[_name] = getattr(_src_survey_base, _name)
