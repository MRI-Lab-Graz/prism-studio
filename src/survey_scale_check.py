"""Answers outside a survey template's scale, for the conversion preview."""

from __future__ import annotations

from typing import Any, Callable

_EXAMPLES = 5


def _number(text: str) -> float | None:
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def _same_level(text: str, level: str) -> bool:
    a, b = _number(text), _number(level)
    return a == b if a is not None and b is not None else text == level


def find_scale_violations(
    df: Any,
    column: str,
    item_def: dict | None,
    id_column: str,
    is_missing: Callable[[Any], bool],
) -> list[dict]:
    """Issues (``out_of_range`` / ``unexpected_values``) for one survey item column.

    Only items with ``Levels`` are checked. A number beyond the numeric levels is out of
    range; anything else that is not a level (text, 1.5 on a 0-2 scale) is unexpected.
    """
    levels = item_def.get("Levels") if isinstance(item_def, dict) else None
    if not isinstance(levels, dict) or not levels:
        return []
    keys = [str(k).strip() for k in levels]
    numeric_keys = [n for n in (_number(k) for k in keys) if n is not None]
    low, high = (min(numeric_keys), max(numeric_keys)) if len(numeric_keys) == len(keys) else (None, None)

    out_of_range: list[str] = []
    unexpected: list[str] = []
    seen_unexpected: list[str] = []
    for pid, value in zip(df[id_column], df[column]):
        if is_missing(value):
            continue
        text = str(value).strip()
        if any(_same_level(text, key) for key in keys):
            continue
        number = _number(text)
        label = f"{str(pid).strip()}: {text}"
        if number is not None and low is not None and not low <= number <= high:
            out_of_range.append(label)
        else:
            unexpected.append(label)
            if text not in seen_unexpected:
                seen_unexpected.append(text)

    issues: list[dict] = []
    if out_of_range:
        shown = ", ".join(out_of_range[:_EXAMPLES])
        issues.append({
            "type": "out_of_range", "severity": "error", "column": column,
            "range": f"{_fmt(low)}-{_fmt(high)}", "out_of_range_count": len(out_of_range),
            "examples": out_of_range[:_EXAMPLES],
            "message": f"{column}: {len(out_of_range)} answer(s) outside the scale {_fmt(low)}-{_fmt(high)} - {shown}"
            + (" ..." if len(out_of_range) > _EXAMPLES else ""),
        })
    if unexpected:
        shown = ", ".join(unexpected[:_EXAMPLES])
        issues.append({
            "type": "unexpected_values", "severity": "error", "column": column,
            "expected": keys, "unexpected": seen_unexpected[:10], "examples": unexpected[:_EXAMPLES],
            "message": f"{column}: {len(unexpected)} answer(s) are not one of {', '.join(keys)} - {shown}"
            + (" ..." if len(unexpected) > _EXAMPLES else ""),
        })
    return issues


def _fmt(number: float | None) -> str:
    return "?" if number is None else str(int(number)) if float(number).is_integer() else str(number)
