"""Answers outside a survey template's scale, for the conversion preview."""

from __future__ import annotations

from typing import Any, Callable

from src.survey_answer_codes import stored_code_as_number

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

    An item with ``Levels`` is checked against them: a number beyond the numeric levels is
    out of range; anything else that is not a level (text, 1.5 on a 0-2 scale) is unexpected.
    An item without labels is checked against its own ``MinValue`` / ``MaxValue`` (the
    validator reads those too, but only after conversion): a number outside is out of range,
    text is unexpected. An item with neither is not checked.
    """
    item_def = item_def if isinstance(item_def, dict) else {}
    levels = item_def.get("Levels")
    if isinstance(levels, dict) and levels:
        keys = [str(k).strip() for k in levels]
        numeric_keys = [n for n in (_number(k) for k in keys) if n is not None]
        low, high = (min(numeric_keys), max(numeric_keys)) if len(numeric_keys) == len(keys) else (None, None)
    else:
        keys = []
        low, high = _number(str(item_def.get("MinValue", ""))), _number(str(item_def.get("MaxValue", "")))
        if low is None and high is None:
            return []
    scale = (
        f"{_fmt(low)}-{_fmt(high)}" if low is not None and high is not None
        else f"at least {_fmt(low)}" if low is not None else f"at most {_fmt(high)}"
    )

    out_of_range: list[str] = []
    unexpected: list[str] = []
    seen_unexpected: list[str] = []
    for pid, value in zip(df[id_column], df[column]):
        if is_missing(value):
            continue
        text = str(stored_code_as_number(value, item_def)).strip()  # ADS0 -> 0, as conversion reads it
        if any(_same_level(text, key) for key in keys):
            continue
        number = _number(text)
        label = f"{str(pid).strip()}: {text}"
        beyond = number is not None and (
            (low is not None and number < low) or (high is not None and number > high)
        )
        if not keys and number is not None and not beyond:
            continue  # inside MinValue..MaxValue
        if beyond:
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
            "range": scale, "out_of_range_count": len(out_of_range),
            "examples": out_of_range[:_EXAMPLES],
            "message": f"{column}: {len(out_of_range)} answer(s) outside the scale {scale} - {shown}"
            + (" ..." if len(out_of_range) > _EXAMPLES else ""),
        })
    if unexpected:
        shown = ", ".join(unexpected[:_EXAMPLES])
        issues.append({
            "type": "unexpected_values", "severity": "error", "column": column,
            "expected": keys, "unexpected": seen_unexpected[:10], "examples": unexpected[:_EXAMPLES],
            "message": f"{column}: {len(unexpected)} answer(s) are not {'one of ' + ', '.join(keys) if keys else 'a number'} - {shown}"
            + (" ..." if len(unexpected) > _EXAMPLES else ""),
        })
    return issues


def _fmt(number: float | None) -> str:
    return "?" if number is None else str(int(number)) if float(number).is_integer() else str(number)
