"""Survey i18n/localization helpers."""

from __future__ import annotations

from copy import deepcopy
import re


_LANGUAGE_KEY_RE = re.compile(r"^[a-z]{2}(?:-[a-z]{2})?$", re.IGNORECASE)


def _normalize_language(lang: str | None) -> str | None:
    if not lang:
        return None
    norm = str(lang).strip().lower()
    return norm or None


def _default_language_from_template(template: dict) -> str:
    i18n = template.get("I18n")
    if isinstance(i18n, dict):
        default = i18n.get("DefaultLanguage") or i18n.get("defaultlanguage")
        if default:
            return str(default).strip().lower() or "en"

    tech = template.get("Technical")
    if isinstance(tech, dict):
        lang = tech.get("Language")
        if lang:
            return str(lang).strip().lower() or "en"

    return "en"


def _is_language_dict(value: dict) -> bool:
    if not value:
        return False
    return all(_LANGUAGE_KEY_RE.match(str(k)) for k in value.keys())


def _pick_language_value(value: dict, language: str) -> object:
    preference = [language, language.split("-")[0] if "-" in language else language]
    for candidate in preference:
        if candidate in value and value[candidate] not in (None, ""):
            return value[candidate]

    for fallback in value.values():
        if fallback not in (None, ""):
            return fallback
    return next(iter(value.values()))


def _localize_survey_template(template: dict, language: str | None) -> dict:
    if not isinstance(template, dict):
        return template

    lang = _normalize_language(language) or _default_language_from_template(template)

    def _recurse(value):
        if isinstance(value, dict):
            if _is_language_dict(value):
                return _pick_language_value(value, lang)
            return {k: _recurse(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_recurse(v) for v in value]
        return value

    return _recurse(deepcopy(template))
