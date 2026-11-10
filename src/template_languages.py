"""Remove a language from a survey template: Studio's "Remove Language" and `library template-remove-language`.

Only what a participant sees is per-language: item descriptions, answer levels and the instructions. The general
header (OriginalName, Description, Citation, ...) is not touched, so removing a language can never empty a required
field. One function, so Studio and the CLI cannot differ.
"""

from __future__ import annotations

import copy

from src.converters.template_import import TEMPLATE_SECTIONS

NOT_ITEMS = TEMPLATE_SECTIONS | {"@context", "_aliases", "_reverse_aliases"}


def _drop(texts: dict, code: str, key: str) -> None:
    """Remove `code` from texts[key]; one language left becomes a plain string, none left a blank one."""
    value = texts.get(key)
    if not isinstance(value, dict):
        return
    value.pop(code, None)
    if len(value) == 1:
        texts[key] = next(iter(value.values()))
    elif not value:
        texts[key] = ""


def _drop_levels(levels: dict, code: str) -> None:
    for level in list(levels):
        _drop(levels, code, level)


def remove_language(template: dict, code: str) -> dict:
    """A copy of `template` without language `code` in items, levels, instructions and I18n."""
    if not isinstance(template, dict):
        raise ValueError("Template must be a JSON object")
    code = code.strip() if isinstance(code, str) else ""
    if not code:
        raise ValueError("No language given")
    tpl = copy.deepcopy(template)

    for key, item in tpl.items():
        if key in NOT_ITEMS or not isinstance(item, dict):
            continue
        _drop(item, code, "Description")
        if isinstance(item.get("Levels"), dict):
            _drop_levels(item["Levels"], code)
        for scale in item.get("VariantScales") or []:
            if isinstance(scale, dict) and isinstance(scale.get("Levels"), dict):
                _drop_levels(scale["Levels"], code)

    instructions = (tpl.get("Study") or {}).get("Instructions")
    if isinstance(instructions, dict) and set(instructions) - {code}:
        instructions.pop(code, None)

    i18n = tpl.get("I18n")
    if isinstance(i18n, dict) and isinstance(i18n.get("Languages"), list):
        remaining = [x for x in i18n.get("Languages") or [] if x != code]
        i18n["Languages"] = remaining
        if i18n.get("DefaultLanguage") == code:
            if remaining:
                i18n["DefaultLanguage"] = remaining[0]
            else:
                del i18n["DefaultLanguage"]
    return tpl
