"""Wide-to-long table conversion helpers for session-coded columns.

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


def _indicator_uses_structural_delimiters(indicator: str) -> bool:
    return any(char in str(indicator) for char in "_- ")


def _find_indicator_spans(column_name: str, indicator: str) -> list[tuple[int, int]]:
    """Return valid case-insensitive indicator spans for a column name."""
    column_text = str(column_name)
    indicator_text = str(indicator)
    if not indicator_text:
        return []

    spans: list[tuple[int, int]] = []
    for match in re.finditer(re.escape(indicator_text), column_text, re.IGNORECASE):
        start, end = match.span()
        if _indicator_uses_structural_delimiters(indicator_text):
            spans.append((start, end))
            continue

        previous_char = column_text[start - 1] if start > 0 else ""
        next_char = column_text[end] if end < len(column_text) else ""
        previous_ok = start == 0 or not previous_char.isalnum()
        next_ok = end == len(column_text) or not next_char.isalnum()
        if previous_ok and next_ok:
            spans.append((start, end))

    return spans


def _strip_indicator_from_column_name(
    column_name: str,
    indicator: str,
    *,
    span: tuple[int, int] | None = None,
) -> str:
    """Remove one case-insensitive indicator occurrence and normalize separators."""
    column_text = str(column_name)
    indicator_text = str(indicator)
    match_span = span
    if match_span is None:
        spans = _find_indicator_spans(column_text, indicator_text)
        if len(spans) != 1:
            return column_text
        match_span = spans[0]

    start, end = match_span
    before = column_text[:start]
    after = column_text[end:]
    joiner = ""
    if before and after and before[-1].isalnum() and after[0].isalnum():
        if indicator_text.startswith("_") or indicator_text.endswith("_"):
            joiner = "_"
        elif indicator_text.startswith("-") or indicator_text.endswith("-"):
            joiner = "-"

    stripped = before + joiner + after
    stripped = re.sub(r"[_-]{2,}", lambda match: match.group(0)[0], stripped)
    stripped = stripped.strip("_-")
    return stripped or column_text


def inspect_wide_to_long_columns(
    columns: list[str],
    *,
    session_indicators: list[str] | None = None,
    session_prefixes: list[str] | None = None,
) -> dict[str, Any]:
    """Inspect how wide-format columns map to session indicators and output names."""
    indicators = session_indicators or session_prefixes or []
    if not indicators:
        raise ValueError("No session indicators provided for wide-to-long conversion")

    indicator_upper_to_cols: dict[str, list[str]] = {
        indicator.upper(): [] for indicator in indicators
    }
    rename_map: dict[str, str] = {}
    matched_columns: list[dict[str, str]] = []
    ambiguous_columns: list[dict[str, Any]] = []

    for column in columns:
        column_text = str(column)
        unique_matches: list[dict[str, str | tuple[int, int]]] = []
        repeated_indicator_matches: list[dict[str, Any]] = []

        for indicator in indicators:
            spans = _find_indicator_spans(column_text, indicator)
            if len(spans) > 1:
                repeated_indicator_matches.append(
                    {
                        "indicator": indicator,
                        "match_count": len(spans),
                    }
                )
            elif len(spans) == 1:
                unique_matches.append(
                    {
                        "indicator": indicator,
                        "span": spans[0],
                        "output_column": _strip_indicator_from_column_name(
                            column_text,
                            indicator,
                            span=spans[0],
                        ),
                    }
                )

        if repeated_indicator_matches:
            ambiguous_columns.append(
                {
                    "column": column_text,
                    "reason": "indicator-occurs-multiple-times",
                    "details": repeated_indicator_matches,
                }
            )
            continue

        if len(unique_matches) > 1:
            ambiguous_columns.append(
                {
                    "column": column_text,
                    "reason": "multiple-indicators-match",
                    "details": [
                        {
                            "indicator": str(match["indicator"]),
                            "output_column": str(match["output_column"]),
                        }
                        for match in unique_matches
                    ],
                }
            )
            continue

        if not unique_matches:
            continue

        match = unique_matches[0]
        indicator = str(match["indicator"])
        indicator_upper_to_cols[indicator.upper()].append(column_text)
        rename_map[column_text] = str(match["output_column"])
        matched_columns.append(
            {
                "column": column_text,
                "indicator": indicator,
                "output_column": str(match["output_column"]),
            }
        )

    matched_set = set(rename_map)
    shared_cols = [str(column) for column in columns if str(column) not in matched_set]

    return {
        "indicators": list(indicators),
        "indicator_upper_to_cols": indicator_upper_to_cols,
        "rename_map": rename_map,
        "matched_columns": matched_columns,
        "ambiguous_columns": ambiguous_columns,
        "shared_columns": shared_cols,
    }


def _format_ambiguous_indicator_error(ambiguous_columns: list[dict[str, Any]]) -> str:
    examples: list[str] = []
    for item in ambiguous_columns[:3]:
        details = item.get("details") or []
        if item.get("reason") == "indicator-occurs-multiple-times":
            detail_text = ", ".join(
                f"{detail.get('indicator')} x{detail.get('match_count')}"
                for detail in details
            )
            examples.append(f"{item.get('column')} ({detail_text})")
        else:
            detail_text = ", ".join(
                str(detail.get("indicator"))
                for detail in details
                if detail.get("indicator")
            )
            examples.append(f"{item.get('column')} ({detail_text})")

    message = (
        "Ambiguous session indicator matches found. Use a more specific indicator and "
        "check the rename preview."
    )
    if examples:
        message += " Examples: " + "; ".join(examples)
    return message


def convert_wide_to_long_dataframe(
    df: Any,
    *,
    session_indicators: list[str] | None = None,
    session_prefixes: list[str] | None = None,
    session_column_name: str = "session",
    session_value_map: dict[str, str] | None = None,
) -> Any:
    """Convert wide session-coded columns into long rows.

    Example:
    - ``T1_score``, ``T2_score`` -> ``score`` with two rows and ``session`` in {T1,T2}.
    - ``score_T1``, ``score_T2`` also work when using ``session_indicators=["T1", "T2"]``.
    - With ``session_value_map={"T1": "pre", "T2": "post"}``, the session
        values become {pre, post}.
    """
    plan = inspect_wide_to_long_columns(
        [str(col) for col in df.columns],
        session_indicators=session_indicators,
        session_prefixes=session_prefixes,
    )
    indicators = plan["indicators"]
    indicator_upper_to_cols = plan["indicator_upper_to_cols"]
    matched_set = set(plan["rename_map"])
    if plan["ambiguous_columns"]:
        raise ValueError(_format_ambiguous_indicator_error(plan["ambiguous_columns"]))
    if not matched_set:
        raise ValueError(
            "No columns found for the selected session indicators: "
            + ", ".join(indicators)
        )

    shared_cols = plan["shared_columns"]

    long_frames = []
    normalized_value_map = {
        str(key).strip().upper(): str(value).strip()
        for key, value in (session_value_map or {}).items()
        if str(key).strip() and str(value).strip()
    }

    for indicator in indicators:
        indicator_upper = indicator.upper()
        matched_cols = indicator_upper_to_cols[indicator_upper]
        if not matched_cols:
            continue

        sub = df[shared_cols + matched_cols].copy()

        rename_map = {col: plan["rename_map"].get(col, col) for col in matched_cols}

        sub = sub.rename(columns=rename_map)
        stripped_names = set(rename_map.values())
        duplicate_shared = [col for col in shared_cols if col in stripped_names]
        if duplicate_shared:
            sub = sub.drop(columns=duplicate_shared, errors="ignore")

        sub[session_column_name] = normalized_value_map.get(indicator_upper, indicator)
        long_frames.append(sub)

    if not long_frames:
        raise ValueError(
            "No data could be converted. Ensure session indicators match your column names."
        )

    import pandas as pd

    return pd.concat(long_frames, ignore_index=True)
