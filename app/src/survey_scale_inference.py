"""Helpers for inferring bounded numeric survey scales from item metadata."""

from __future__ import annotations

from typing import Any

_NON_ITEM_TEMPLATE_KEYS = {
    "Technical",
    "Study",
    "Metadata",
    "Questions",
    "Items",
    "I18n",
    "LimeSurvey",
    "Scoring",
    "Normative",
    "StudyMetadata",
    "LimesurveyID",
    "_aliases",
    "_reverse_aliases",
}


def get_survey_item_map(template: Any) -> dict[str, Any]:
    """Return survey items keyed by item ID across canonical and legacy shapes."""
    if not isinstance(template, dict):
        return {}

    questions = template.get("Questions")
    if isinstance(questions, dict):
        return questions

    items = template.get("Items")
    if isinstance(items, list):
        mapped: dict[str, Any] = {}
        for idx, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("ItemID") or "").strip() or f"item{idx}"
            mapped[item_id] = item
        return mapped

    return {
        key: value
        for key, value in template.items()
        if key not in _NON_ITEM_TEMPLATE_KEYS and isinstance(value, dict)
    }


def infer_contiguous_numeric_levels_range(levels: Any) -> tuple[int, int] | None:
    """Return min/max when Levels keys form a contiguous integer-coded range."""
    if not isinstance(levels, dict) or len(levels) < 2:
        return None

    numeric_keys: list[int] = []
    for key in levels.keys():
        try:
            numeric = float(str(key).strip())
        except (TypeError, ValueError, AttributeError):
            return None
        if not numeric.is_integer():
            return None
        numeric_keys.append(int(numeric))

    unique_keys = sorted(set(numeric_keys))
    if len(unique_keys) != len(numeric_keys):
        return None

    expected = list(range(unique_keys[0], unique_keys[-1] + 1))
    if unique_keys != expected:
        return None

    return unique_keys[0], unique_keys[-1]


def apply_inferred_min_max_from_levels(item_def: Any) -> Any:
    """Fill missing MinValue/MaxValue from contiguous numeric Levels."""
    if not isinstance(item_def, dict):
        return item_def

    inferred = infer_contiguous_numeric_levels_range(item_def.get("Levels"))
    if inferred is not None:
        min_value, max_value = inferred
        if item_def.get("MinValue") in (None, ""):
            item_def["MinValue"] = min_value
        if item_def.get("MaxValue") in (None, ""):
            item_def["MaxValue"] = max_value

    variant_scales = item_def.get("VariantScales")
    if isinstance(variant_scales, list):
        for entry in variant_scales:
            if not isinstance(entry, dict):
                continue
            inferred_variant = infer_contiguous_numeric_levels_range(
                entry.get("Levels")
            )
            if inferred_variant is None:
                continue
            min_value, max_value = inferred_variant
            if entry.get("MinValue") in (None, ""):
                entry["MinValue"] = min_value
            if entry.get("MaxValue") in (None, ""):
                entry["MaxValue"] = max_value

    return item_def


def apply_implicit_numeric_level_ranges(template: Any) -> Any:
    """Fill missing numeric bounds across survey items in a template payload."""
    if not isinstance(template, dict):
        return template

    items_src = get_survey_item_map(template)

    for value in items_src.values():
        apply_inferred_min_max_from_levels(value)

    return template
