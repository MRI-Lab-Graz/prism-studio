"""Add or remove a language of a survey template: Studio's "Add Language" / "Remove Language" and
`library template-add-language` / `library template-remove-language`.

Only what a participant sees is per-language: item descriptions, answer levels and the instructions. The general
header (OriginalName, Description, Citation, ...) is not touched, so changing the languages can never empty a
required field. One function each, so Studio and the CLI cannot differ.
"""

from __future__ import annotations

import copy
import re

from src.converters.template_import import TEMPLATE_SECTIONS

NOT_ITEMS = TEMPLATE_SECTIONS | {"@context", "_aliases", "_reverse_aliases"}
LANG_CODE_RE = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")


def section(tpl: dict, name: str) -> dict:
    """tpl[name] when it is an object, else an empty one: a hand-edited template can hold anything there."""
    value = tpl.get(name)
    return value if isinstance(value, dict) else {}


def _text_slots(tpl: dict):
    """(container, key) of every per-language text of the items: each Description and each answer level."""
    for key, item in tpl.items():
        if key in NOT_ITEMS or not isinstance(item, dict):
            continue
        yield item, "Description"
        variants = item.get("VariantScales")
        level_sets = [item.get("Levels")] + [s.get("Levels") for s in variants if isinstance(s, dict)] if isinstance(variants, list) else [item.get("Levels")]
        for levels in level_sets:
            if isinstance(levels, dict):
                for level in levels:
                    yield levels, level


def template_languages(tpl: dict) -> list[str]:
    """Languages the template declares or has text in (items, levels, instructions), sorted."""
    found = {c for c in section(tpl, "I18n").get("Languages") or [] if isinstance(c, str) and LANG_CODE_RE.match(c)}
    instructions = section(tpl, "Study").get("Instructions")
    for texts in [instructions] + [box[key] for box, key in _text_slots(tpl) if key in box]:
        if isinstance(texts, dict):
            found.update(c for c in texts if LANG_CODE_RE.match(c))
    return sorted(found)


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


def _check(template, code, *, strict: bool = False) -> str:
    if not isinstance(template, dict):
        raise ValueError("Template must be a JSON object")
    code = code.strip() if isinstance(code, str) else ""
    if not code or (strict and not LANG_CODE_RE.match(code)):
        raise ValueError(f"'{code}' is not a language code like 'en' or 'de-AT'" if code else "No language given")
    return code


def remove_language(template: dict, code: str) -> dict:
    """A copy of `template` without language `code` in items, levels, instructions and I18n."""
    code = _check(template, code)
    tpl = copy.deepcopy(template)

    for box, key in _text_slots(tpl):
        _drop(box, code, key)

    instructions = section(tpl, "Study").get("Instructions")
    if isinstance(instructions, dict) and set(instructions) - {code}:
        instructions.pop(code, None)

    i18n = section(tpl, "I18n")
    if isinstance(i18n.get("Languages"), list):
        remaining = [x for x in i18n.get("Languages") or [] if x != code]
        i18n["Languages"] = remaining
        if i18n.get("DefaultLanguage") == code:
            if remaining:
                i18n["DefaultLanguage"] = remaining[0]
            else:
                del i18n["DefaultLanguage"]
    return tpl


def add_language(template: dict, code: str) -> dict:
    """A copy of `template` with an empty text in `code` for every item, level and the instructions, declared in I18n.

    A plain text becomes an entry of the original language (Technical.Language, else en); with no original language
    set, the added one becomes it."""
    code = _check(template, code, strict=True)
    tpl = copy.deepcopy(template)
    original = section(tpl, "Technical").get("Language") or "en"

    has_items = False
    for box, key in _text_slots(tpl):
        if key not in box:
            continue
        has_items = True
        if isinstance(box[key], str):
            box[key] = {original: box[key]}
        if isinstance(box[key], dict):
            box[key].setdefault(code, "")

    instructions = section(tpl, "Study").get("Instructions")
    if isinstance(instructions, dict):
        instructions.setdefault(code, "")

    i18n = section(tpl, "I18n")
    declared = [c for c in i18n.get("Languages") or [] if isinstance(c, str)] if isinstance(i18n.get("Languages"), list) else []
    tpl["I18n"] = {**i18n, "Languages": list(dict.fromkeys([*declared, *template_languages(tpl), code]))}
    if has_items and not section(tpl, "Technical").get("Language"):
        tpl["Technical"] = {**section(tpl, "Technical"), "Language": code}
    return tpl
