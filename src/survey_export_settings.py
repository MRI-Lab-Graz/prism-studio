"""A survey template holds no export settings: an item's ``LimeSurvey`` block keeps only what is data
(``columnName``, ``answerCodes``). Settings with a generic item field move there (never overwriting a
value already set); the rest (question type, widths, design attributes, ...) is derived at export time.
"""

from __future__ import annotations

import copy

from src.converters.template_import import TEMPLATE_SECTIONS

KEPT_LIMESURVEY_KEYS = ("columnName", "answerCodes")

# Top-level keys that are never items (the section set the importers share, plus editor-internal keys).
_NOT_ITEMS = TEMPLATE_SECTIONS | {"@context", "_aliases", "_reverse_aliases"}


def _move_to_generic(item: dict, ls: dict) -> None:
    def put(field, value):
        if item.get(field) is None:
            item[field] = value

    if "mandatory" in ls:
        put("Mandatory", ls["mandatory"])
    validation = ls.get("validation")
    if isinstance(validation, dict):
        if validation.get("min") is not None:
            put("MinValue", validation["min"])
        if validation.get("max") is not None:
            put("MaxValue", validation["max"])
    if ls.get("relevance") not in (None, "", "1"):
        put("Relevance", ls["relevance"])
    if ls.get("helpText"):
        put("Help", ls["helpText"])
    if ls.get("other") is True:
        put("OtherOption", {"enabled": True})


def strip_export_settings(template: dict) -> tuple[dict, list[str]]:
    """Return ``(new template, report)``; ``report`` has one ``"<item>: key, key"`` entry per changed item."""
    out = copy.deepcopy(template)
    report: list[str] = []
    for name, item in out.items():
        if name in _NOT_ITEMS or not isinstance(item, dict):
            continue
        ls = item.get("LimeSurvey")
        if not isinstance(ls, dict):
            continue
        removed = sorted(k for k in ls if k not in KEPT_LIMESURVEY_KEYS)
        if not removed:
            continue
        _move_to_generic(item, ls)
        kept = {k: ls[k] for k in KEPT_LIMESURVEY_KEYS if k in ls}
        if kept:
            item["LimeSurvey"] = kept
        else:
            del item["LimeSurvey"]
        report.append(f"{name}: {', '.join(removed)}")
    return out, report
