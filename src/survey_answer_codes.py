"""Answer codes a survey author chose (ADS0..ADS3) where the scale has numbers (0..3).

Nothing is recoded unasked. The user gives the codes numbers (pre-filled with a
suggestion); the template then holds the numbers as Levels and, per item,
LimeSurvey.answerCodes (number -> code stored in the data), and conversion reads each
stored code as its number.
"""

from __future__ import annotations

import re

_MISSING = "n/a"


def _codes(item) -> list[str]:
    levels = item.get("Levels") if isinstance(item, dict) else None
    return [k for k in levels if k != _MISSING] if isinstance(levels, dict) else []


def _is_number(code: str) -> bool:
    return re.fullmatch(r"-?\d+", code) is not None


def _suggest(codes: list[str]) -> dict[str, str]:
    """ADS0 -> "0": the number after a prefix all codes share; blank where that does not fit."""
    parts = [re.fullmatch(r"(\D+)(\d+)", c) for c in codes]
    if all(parts) and len({m[1] for m in parts}) == 1 and len({int(m[2]) for m in parts}) == len(codes):
        return {m[0]: str(int(m[2])) for m in parts}
    return {c: "" for c in codes}


def suggest_answer_numbers(template: dict) -> list[dict]:
    """The sets of Levels codes that are not all numbers, each with a suggested number per
    code and the items using that set: [{"codes": {code: number or ""}, "items": [...]}]."""
    groups: dict[tuple, list[str]] = {}
    for key, item in template.items():
        codes = _codes(item)
        if codes and not all(_is_number(c) for c in codes):
            groups.setdefault(tuple(codes), []).append(key)
    return [{"codes": _suggest(list(codes)), "items": items} for codes, items in groups.items()]


def apply_answer_numbers(template: dict, mapping: dict[str, str]) -> list[str]:
    """Give the codes in ``mapping`` (code -> number) their numbers in every item whose
    Levels codes are exactly those codes; returns the changed items. Raises ValueError,
    changing nothing, when a number is not a whole number or used twice."""
    mapping = {str(k).strip(): str(v).strip() for k, v in mapping.items()}
    numbers = list(mapping.values())
    bad = [n for n in numbers if not _is_number(n)]
    if bad or len(set(numbers)) != len(numbers):
        raise ValueError(f"Answer numbers must be distinct whole numbers, got: {', '.join(numbers)}")
    targets = [key for key, item in template.items() if _codes(item) and set(_codes(item)) == set(mapping)]
    if not targets:
        raise ValueError(f"No item has exactly the answer codes {', '.join(mapping)}")
    for key in targets:
        item = template[key]
        item["Levels"] = {mapping.get(code, code): label for code, label in item["Levels"].items()}
        limesurvey = item.setdefault("LimeSurvey", {})
        stored = limesurvey.get("answerCodes") or {}
        limesurvey["answerCodes"] = {number: stored.get(code, code) for code, number in mapping.items()}
    return targets


def stored_code_as_number(value, item: dict):
    """The number the item's template gives this stored answer code (ADS2 -> "2"), else the value."""
    answer_codes = (item.get("LimeSurvey") or {}).get("answerCodes") if isinstance(item, dict) else None
    if not answer_codes:
        return value
    return {code: number for number, code in answer_codes.items()}.get(str(value).strip(), value)
