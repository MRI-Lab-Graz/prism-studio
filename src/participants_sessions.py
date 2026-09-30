"""Session helpers for the participants importer (longitudinal source files).

Session labels are free-form strings ("1", "01" and "baseline" are different
labels): they are compared exactly and never normalized. The one concession is
a whole-number float such as ``1.0``, a spreadsheet data-type artifact of the
integer ``1``, not a different label.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

_SESSION_COLUMN_ALIASES = {"ses", "session", "sessionid", "visit", "timepoint", "wave"}


def session_label(value: Any) -> str:
    """Exact string label of a session cell ('' for missing)."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _looks_like_session_column(name: Any) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "", str(name).strip().lower())
    return normalized in _SESSION_COLUMN_ALIASES or normalized.startswith("session")


def _label_sort_key(label: str) -> tuple[int, float, str]:
    try:
        return (0, float(label), label)
    except ValueError:
        return (1, 0.0, label)


def find_session_candidates(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Session-like columns that hold at least two different session labels."""
    candidates: list[dict[str, Any]] = []
    for column in df.columns:
        if not _looks_like_session_column(column):
            continue
        labels = {session_label(value) for value in df[column]}
        labels.discard("")
        if len(labels) >= 2:
            candidates.append(
                {"column": str(column), "values": sorted(labels, key=_label_sort_key)}
            )
    return candidates


def filter_rows_to_session(df: pd.DataFrame, column: str, value: str) -> pd.DataFrame:
    """Rows whose ``column`` holds exactly the session label ``value``."""
    if column not in df.columns:
        raise ValueError(f"Session column '{column}' not found in the file")
    mask = df[column].map(session_label) == str(value).strip()
    if not mask.any():
        raise ValueError(f"Session '{value}' not found in column '{column}'")
    return df[mask].copy()


def scope_to_session(
    df: pd.DataFrame, column: str = "", value: str = ""
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    """Session candidates of the whole file plus the rows of the chosen session.

    Without both ``column`` and ``value`` every row is kept. Used by the GUI
    preview and the CLI so both apply the same rule.
    """
    candidates = find_session_candidates(df)
    if column and value:
        df = filter_rows_to_session(df, column, value)
    return candidates, df
