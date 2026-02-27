"""Value normalization helpers for survey conversion."""

from __future__ import annotations


def _normalize_item_value(val, *, missing_token: str) -> str:
    from pandas import isna

    if isna(val) or (isinstance(val, str) and str(val).strip() == ""):
        return missing_token
    if isinstance(val, bool):
        return str(val).lower()
    if isinstance(val, int):
        return str(int(val))
    if isinstance(val, float):
        if val.is_integer():
            return str(int(val))
        return str(val)
    return str(val)
