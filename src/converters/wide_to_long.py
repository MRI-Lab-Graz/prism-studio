"""Wide-to-long table conversion helpers for session-prefixed columns.

This utility is intentionally generic so it can be used by Web File Management
and future converter pre-processing workflows.
"""

from __future__ import annotations

import re
from typing import Any

_PREFIX_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^(?P<prefix>T\d+)[_-].+", re.IGNORECASE),
    re.compile(r"^(?P<prefix>tp\d+)[_-].+", re.IGNORECASE),
    re.compile(r"^(?P<prefix>wave\d+)[_-].+", re.IGNORECASE),
    re.compile(r"^(?P<prefix>ses-[A-Za-z0-9]+)[_-].+", re.IGNORECASE),
    re.compile(r"^(?P<prefix>pre)[_-].+", re.IGNORECASE),
    re.compile(r"^(?P<prefix>post)[_-].+", re.IGNORECASE),
    re.compile(r"^(?P<prefix>baseline)[_-].+", re.IGNORECASE),
    re.compile(r"^(?P<prefix>fu\d+)[_-].+", re.IGNORECASE),
)


def detect_wide_session_prefixes(columns: list[str], min_count: int = 3) -> list[str]:
    """Return detected session prefixes in wide-format columns.

    Prefixes are retained in first-seen case and must appear at least
    ``min_count`` times to reduce false positives.
    """
    from collections import Counter

    counts: Counter[str] = Counter()
    case_map: dict[str, str] = {}

    for col in columns:
        for pattern in _PREFIX_PATTERNS:
            match = pattern.match(str(col))
            if not match:
                continue
            prefix = match.group("prefix")
            key = prefix.upper()
            counts[key] += 1
            case_map.setdefault(key, prefix)
            break

    return [case_map[key] for key, count in counts.items() if count >= min_count]


def convert_wide_to_long_dataframe(
    df: Any,
    *,
    session_prefixes: list[str],
    session_column_name: str = "session",
    session_value_map: dict[str, str] | None = None,
) -> Any:
    """Convert wide session-prefixed columns into long rows.

    Example:
    - ``T1_score``, ``T2_score`` -> ``score`` with two rows and ``session`` in {T1,T2}.
    - With ``session_value_map={"T1": "pre", "T2": "post"}``, the session
        values become {pre, post}.
    """
    if not session_prefixes:
        raise ValueError("No session prefixes provided for wide-to-long conversion")

    prefix_upper_to_cols: dict[str, list[str]] = {
        p.upper(): [] for p in session_prefixes
    }

    for col in df.columns:
        col_upper = str(col).upper()
        for prefix in session_prefixes:
            prefix_upper = prefix.upper()
            if col_upper.startswith(prefix_upper + "_") or col_upper.startswith(
                prefix_upper + "-"
            ):
                prefix_upper_to_cols[prefix_upper].append(str(col))
                break

    prefixed_set = {col for cols in prefix_upper_to_cols.values() for col in cols}
    if not prefixed_set:
        raise ValueError(
            "No prefixed columns found for the selected prefixes: "
            + ", ".join(session_prefixes)
        )

    shared_cols = [str(col) for col in df.columns if str(col) not in prefixed_set]

    long_frames = []
    normalized_value_map = {
        str(key).strip().upper(): str(value).strip()
        for key, value in (session_value_map or {}).items()
        if str(key).strip() and str(value).strip()
    }

    for prefix in session_prefixes:
        prefix_upper = prefix.upper()
        prefixed_cols = prefix_upper_to_cols[prefix_upper]
        if not prefixed_cols:
            continue

        sub = df[shared_cols + prefixed_cols].copy()

        rename_map: dict[str, str] = {}
        for col in prefixed_cols:
            col_upper = col.upper()
            if col_upper.startswith(prefix_upper + "_") or col_upper.startswith(
                prefix_upper + "-"
            ):
                rename_map[col] = col[len(prefix) + 1 :]
            else:
                rename_map[col] = col

        sub = sub.rename(columns=rename_map)
        stripped_names = set(rename_map.values())
        duplicate_shared = [col for col in shared_cols if col in stripped_names]
        if duplicate_shared:
            sub = sub.drop(columns=duplicate_shared, errors="ignore")

        sub[session_column_name] = normalized_value_map.get(prefix_upper, prefix)
        long_frames.append(sub)

    if not long_frames:
        raise ValueError(
            "No data could be converted. Ensure session prefixes match your column names."
        )

    import pandas as pd

    return pd.concat(long_frames, ignore_index=True)
