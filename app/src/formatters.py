"""
Proxy module for formatters - delegates to canonical repo root src/formatters.py.
Uses _compat.load_canonical_module so this works in both dev and PyInstaller bundles
(where the real src/ is bundled under backend_bundle/src/).
"""

from __future__ import annotations

from src._compat import load_canonical_module

_real = load_canonical_module(
    current_file=__file__,
    canonical_rel_path="formatters.py",
    alias="prism_backend_src.formatters",
)

# Re-export public API
to_sarif = _real.to_sarif
to_junit_xml = _real.to_junit_xml
to_markdown = _real.to_markdown
to_csv = _real.to_csv
format_output = _real.format_output
FORMATTERS = _real.FORMATTERS
_get_issue_category = _real._get_issue_category
_utc_isoformat_z = _real._utc_isoformat_z
_utc_timestamp_seconds = _real._utc_timestamp_seconds

__all__ = [
    "to_sarif",
    "to_junit_xml",
    "to_markdown",
    "to_csv",
    "format_output",
    "FORMATTERS",
]
