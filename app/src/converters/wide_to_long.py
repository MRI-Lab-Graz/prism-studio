"""Compatibility shim for wide-to-long conversion utilities.

Delegates runtime symbols to canonical backend module:
`src/converters/wide_to_long.py`.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from src._compat import load_canonical_module

if TYPE_CHECKING:

    def detect_wide_session_prefixes(
        columns: list[str], min_count: int = 3
    ) -> list[str]: ...

    def convert_wide_to_long_dataframe(
        df: Any,
        *,
        session_indicators: list[str] | None = None,
        session_prefixes: list[str] | None = None,
        session_column_name: str = "session",
        session_value_map: dict[str, str] | None = None,
    ) -> Any: ...

    def inspect_wide_to_long_columns(
        columns: list[str],
        *,
        session_indicators: list[str] | None = None,
        session_prefixes: list[str] | None = None,
    ) -> dict[str, Any]: ...

else:
    _src_wide_to_long = load_canonical_module(
        current_file=__file__,
        canonical_rel_path="converters/wide_to_long.py",
        alias="prism_backend_converters_wide_to_long",
    )

    for _name in dir(_src_wide_to_long):
        if not _name.startswith("__"):
            globals()[_name] = getattr(_src_wide_to_long, _name)
