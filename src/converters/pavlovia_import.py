"""Pavlovia survey (SurveyJS JSON) -> PRISM survey templates, one per page.

The reverse direction (PRISM -> Pavlovia) lives in ``pavlovia.py``.
"""

from __future__ import annotations

import re
from typing import Any

from src.converters.limesurvey import _task_name, _utc_creation_date

_SPLITS = ("page", "survey")
_DEFAULT_RATING = [1, 2, 3, 4, 5]  # SurveyJS rating without rateValues/rateCount
_LANGUAGE_RE = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")  # the survey schema's Technical.Language


def is_pavlovia_survey(data: Any) -> bool:
    return isinstance(data, dict) and (isinstance(data.get("pages"), list) or isinstance(data.get("elements"), list))


def _pages(survey: dict) -> list[dict]:
    if not is_pavlovia_survey(survey):
        raise ValueError("Not a Pavlovia/SurveyJS survey (expected a 'pages' list)")
    return survey.get("pages") or [{"name": survey.get("title") or "survey", "elements": survey.get("elements", [])}]


def _flatten(elements: list[dict]) -> list[dict]:
    """Questions of a page; panels are unwrapped."""
    out: list[dict] = []
    for el in elements:
        out.extend(_flatten(el.get("elements", [])) if el.get("type") == "panel" else [el])
    return out


def _label(raw: Any) -> tuple[str, str]:
    """(stored value, shown text) of a SurveyJS choice: a plain value or {value, text}."""
    if isinstance(raw, dict):
        value = raw.get("value")
        return str(value), str(raw.get("text") or value)
    return str(raw), str(raw)


def _levels(el: dict, lang: str) -> dict | None:
    kind = el.get("type")
    if kind == "boolean":
        return {"true": {lang: el.get("labelTrue") or "true"}, "false": {lang: el.get("labelFalse") or "false"}}
    raw = el.get("rateValues") if kind == "rating" else el.get("choices")
    if kind == "rating" and not raw:
        raw = list(range(1, int(el.get("rateCount") or 0) + 1)) if el.get("rateCount") else _DEFAULT_RATING
    if not raw:
        return None
    return {value: {lang: text} for value, text in map(_label, raw)}


def _item(el: dict, lang: str) -> dict:
    item: dict[str, Any] = {"Description": {lang: el.get("title") or el["name"]}}
    levels = _levels(el, lang)
    if levels:
        item["Levels"] = levels
    elif el.get("type") == "text":
        numeric = el.get("inputType") == "number"
        whole = all(isinstance(el.get(k, 0), int) for k in ("min", "max", "step"))
        item["DataType"] = ("integer" if whole else "float") if numeric else "string"
        for key, bound in (("min", "MinValue"), ("max", "MaxValue")):
            if numeric and isinstance(el.get(key), (int, float)):
                item[bound] = el[key]
    if el.get("visibleIf"):
        item["Relevance"] = el["visibleIf"]
    item["Mandatory"] = bool(el.get("isRequired"))
    return item


def _build(survey: dict, split: str, language: str | None = None) -> list[tuple[dict, dict]]:
    """[(listing entry, template)] for every questionnaire of the survey.

    The file carries no language, so ``language`` (else its ``locale``, else en) labels every text."""
    if split not in _SPLITS:
        raise ValueError(f"Unknown split mode '{split}'. Use one of: {', '.join(_SPLITS)}")
    if language is not None and not _LANGUAGE_RE.match(language):
        raise ValueError(f"Invalid language '{language}': use a code like de or de-AT")
    locale = survey.get("locale")
    lang = language or (locale if isinstance(locale, str) and len(locale) == 2 else "en")
    survey_name = survey.get("title") or "survey"
    parts = [
        (page.get("name") or f"page {n}", page, _flatten(page.get("elements", [])))
        for n, page in enumerate(_pages(survey), 1)
    ]
    parts = [(name, page, els) for name, page, els in parts if els]
    if split == "survey":
        parts = [(survey_name, {}, [el for _n, _p, els in parts for el in els])]
        keys = ["survey"]
    else:
        keys = [f"p{n}" for n in range(1, len(parts) + 1)]

    results, used = [], set()
    for key, (name, page, els) in zip(keys, parts):
        template: dict[str, Any] = {
            "Technical": {
                "StimulusType": "Questionnaire", "FileFormat": "tsv", "SoftwarePlatform": "Pavlovia",
                "Language": lang, "Respondent": "self", "AdministrationMethod": "online",
            },
            "Study": {},
            "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": _utc_creation_date(), "Creator": "pavlovia_import.py"},
        }
        notes = [page.get("description"), *(el.get("description") for el in els)]
        notes = list(dict.fromkeys(n for n in notes if n))  # unique, in order
        base = task = _task_name(name)
        n = 1
        while task in used:  # pages whose names sanitize alike get base-2, base-3, ...
            n += 1
            task = f"{base}-{n}"
        used.add(task)
        template["Study"] = {
            "TaskName": task, "OriginalName": name, "Version": "1.0",
            "Description": f"Imported from Pavlovia survey: {name}",
            "LicenseID": "Proprietary",
            "License": "Proprietary / Copyright protected. Please ensure you have a valid license for this instrument.",
            "ItemCount": len(els),
            **({"Instructions": {lang: "\n\n".join(notes)}} if notes else {}),
        }
        for el in els:
            if el.get("visible") is False:
                print(f"[PRISM] WARNING {name} / {el['name']}: hidden in Pavlovia (visible:false), imported as a normal item")
            template[el["name"]] = _item(el, lang)
        results.append(({"key": key, "name": name, "item_count": len(els)}, template))
    return results


def list_pavlovia_questionnaires(survey, split="page", source_name="Pavlovia file", project_path=None, match_library=False, language=None):
    results = _build(survey, split, language)
    print(f"[PRISM] Pavlovia import: {source_name}")
    print(f"[PRISM] Split by {split} -> {len(results)} questionnaire(s):")
    for info, _t in results:
        print(f"[PRISM]   {info['key']:<8} {info['name']}  {info['item_count']} item(s)")
    listing = [dict(info) for info, _t in results]
    if match_library:
        from src.converters.library_wording_match import public_library_match
        from src.converters.template_import import match_questionnaire_to_library

        for entry, (info, template) in zip(listing, results):
            entry["library_match"] = public_library_match(match_questionnaire_to_library(template, info["name"], project_path))
    return listing


def pavlovia_questionnaire_template(survey, key, split="page", language=None):
    results = _build(survey, split, language)
    for info, template in results:
        if info["key"] == key:
            print(f"[PRISM] Loading {key} '{info['name']}': {info['item_count']} item(s)")
            return template
    raise ValueError(f"No questionnaire '{key}' (split by {split}). Valid keys: {', '.join(i['key'] for i, _ in results) or 'none'}")
