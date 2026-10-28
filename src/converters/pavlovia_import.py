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


_LOCALIZED_KEYS = ("title", "description", "text", "html", "labelTrue", "labelFalse", "otherText", "noneText")
_NOT_A_QUESTION = ("html", "image")
_MULTIPLE = ("checkbox", "tagbox")
_WITH_OTHER = ("radiogroup", "dropdown", *_MULTIPLE)  # the types that can show an "other"/"none" option
_SINGLE_ITEM = ("text", "comment", "radiogroup", "dropdown", "rating", "boolean", "imagepicker", "ranking", "expression")


def _localize(node: Any, lang: str, dropped: set) -> Any:
    """Copy of the survey where a text given per language ({"default": .., "de": ..}) is one string: ``lang``,
    else the default text, else the first. The other language codes are collected in ``dropped``."""
    if isinstance(node, list):
        return [_localize(n, lang, dropped) for n in node]
    if not isinstance(node, dict):
        return node
    out = {}
    for key, value in node.items():
        if key in _LOCALIZED_KEYS and isinstance(value, dict) and value and all(isinstance(v, str) for v in value.values()):
            used = lang if lang in value else "default" if "default" in value else next(iter(value))
            dropped.update(code for code in value if code not in (used, "default"))
            out[key] = value[used]
        else:
            out[key] = _localize(value, lang, dropped)
    return out


def _label(raw: Any) -> tuple[str, str]:
    """(stored value, shown text) of a SurveyJS choice: a plain value or {value, text}."""
    if isinstance(raw, dict):
        value = raw.get("value")
        return str(value), str(raw.get("text") or value)
    return str(raw), str(raw)


def _text(lang: str, value: str) -> Any:
    """A text under its language, or the plain string while the language is not chosen yet."""
    return {lang: value} if lang else value


def _rating_values(el: dict) -> list:
    """SurveyJS rating without rateValues: rateMin (1) to rateMax (else rateCount values, else 5) in rateStep steps."""
    low, step = el.get("rateMin", 1), el.get("rateStep") or 1
    high = el.get("rateMax", low + (el["rateCount"] - 1) * step if el.get("rateCount") else 5)
    return list(range(low, high + 1, step))


def _levels(el: dict, lang: str) -> dict | None:
    kind = el.get("type")
    if kind == "boolean":
        return {"true": _text(lang, el.get("labelTrue") or "true"), "false": _text(lang, el.get("labelFalse") or "false")}
    raw = el.get("rateValues") if kind == "rating" else el.get("choices")
    if kind == "rating" and not raw:
        raw = _rating_values(el)
    levels = {value: _text(lang, text) for value, text in map(_label, raw or [])}
    for flag, value, default in (("showOtherItem", "other", "Other (describe)"), ("showNoneItem", "none", "None")):
        if el.get(flag) and kind in _WITH_OTHER:
            levels[value] = _text(lang, el.get(f"{value}Text") or default)
    return levels or None


def _item(el: dict, lang: str) -> dict:
    item: dict[str, Any] = {"Description": _text(lang, el.get("title") or el["name"])}
    levels = _levels(el, lang)
    if levels:
        item["Levels"] = levels
    else:
        numeric = el.get("type") == "text" and el.get("inputType") == "number"
        whole = all(isinstance(el.get(k, 0), int) for k in ("min", "max", "step"))
        item["DataType"] = ("integer" if whole else "float") if numeric else "string"
        for key, bound in (("min", "MinValue"), ("max", "MaxValue")):
            if numeric and isinstance(el.get(key), (int, float)):
                item[bound] = el[key]
    if el.get("visibleIf"):
        item["Relevance"] = el["visibleIf"]
    item["Mandatory"] = bool(el.get("isRequired"))
    return item


def _expand(el: dict, lang: str, say) -> list[tuple[str, dict]]:
    """[(item ID, item)] of one SurveyJS element: usually one; a matrix row or multiple-text field each;
    none for a block that is no question. ``say(text)`` reports what could not be represented."""
    name, kind = el["name"], el.get("type")
    title = el.get("title") or name
    if el.get("visible") is False:
        say("hidden in Pavlovia (visible:false), imported as a normal item")
    if kind in _NOT_A_QUESTION:
        say(f"is a {kind} block, not a question: skipped")
        return []
    if kind == "matrix":
        columns = {value: _text(lang, text) for value, text in map(_label, el.get("columns") or [])}
        rows = []
        for row in el.get("rows") or []:
            value, text = _label(row)
            item = {**_item({**el, "type": "text"}, lang), "Description": _text(lang, f"{title} - {text}")}
            rows.append((f"{name}_{value}", {**item, "Levels": columns} if columns else item))
        return rows
    if kind == "multipletext":
        return [
            (f"{name}_{f['name']}", {**_item({"name": f["name"]}, lang), "Description": _text(lang, f"{title} - {f.get('title') or f['name']}")})
            for f in el.get("items") or []
        ]
    if kind in _MULTIPLE or (kind == "imagepicker" and el.get("multiSelect")):
        say("several options can be selected; Pavlovia stores them as one list in this column")
    elif kind == "ranking":
        say("is a ranking; Pavlovia stores the order as one list in this column")
    elif kind == "expression":
        say(f"is a calculated value ({el.get('expression')}); the formula was not imported")
    elif kind not in (*_SINGLE_ITEM, *_MULTIPLE):
        say(f"has the type '{kind}', which cannot be represented: imported as one text item")
    if not el.get("choices") and not el.get("rateValues") and (el.get("choicesFromQuestion") or el.get("choicesByUrl")):
        say("takes its choices from another question or a web address; the choices were not imported")
    items = [(name, _item(el, lang))]
    if el.get("showOtherItem") and kind in _WITH_OTHER:
        items.append((f"{name}-Comment", {**_item({"name": name}, lang), "Description": _text(lang, f"{title} - Other (describe)")}))
    return items


def _build(survey: dict, split: str, language: str | None = None) -> list[tuple[dict, dict, list[str]]]:
    """[(listing entry, template, import notes)] for every questionnaire of the survey.

    The file carries no language: ``language`` (else its ``locale``) labels every text; without either the
    texts stay plain strings and ``Technical.Language`` is empty, and the editor asks for the language."""
    if split not in _SPLITS:
        raise ValueError(f"Unknown split mode '{split}'. Use one of: {', '.join(_SPLITS)}")
    if language is not None and not _LANGUAGE_RE.match(language):
        raise ValueError(f"Invalid language '{language}': use a code like de or de-AT")
    locale = survey.get("locale")
    lang = language or (locale if isinstance(locale, str) and len(locale) == 2 else "")
    dropped: set = set()
    survey = _localize(survey, lang, dropped)
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
        notes: list[str] = []
        if dropped:
            notes.append(f"Texts also exist in other languages ({', '.join(sorted(dropped))}); only one language was imported")
        template: dict[str, Any] = {
            "Technical": {
                "StimulusType": "Questionnaire", "FileFormat": "tsv", "SoftwarePlatform": "Pavlovia",
                "Language": lang, "Respondent": "self", "AdministrationMethod": "online",
            },
            "Study": {},
            "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": _utc_creation_date(), "Creator": "pavlovia_import.py"},
        }
        raw_notes = [page.get("description"), *(el.get("description") for el in els)]
        instructions = list(dict.fromkeys(n for n in raw_notes if n))  # unique, in order
        base = task = _task_name(name)
        n = 1
        while task in used:  # pages whose names sanitize alike get base-2, base-3, ...
            n += 1
            task = f"{base}-{n}"
        used.add(task)
        template["Study"] = {
            "TaskName": task, "OriginalName": name, "Version": "1.0",
            "Description": _text(lang, f"Imported from Pavlovia survey: {name}"),
            "LicenseID": "Proprietary",
            "License": "Proprietary / Copyright protected. Please ensure you have a valid license for this instrument.",
            **({"Instructions": _text(lang, "\n\n".join(instructions))} if instructions else {}),
        }
        for el in els:
            for item_id, item in _expand(el, lang, lambda text, el=el: notes.append(f"{name} / '{el['name']}': {text}")):
                template[item_id] = item
        template["Study"]["ItemCount"] = count = len(template) - 3  # not Technical, Study, Metadata
        results.append(({"key": key, "name": name, "item_count": count}, template, notes))
    return results


def list_pavlovia_questionnaires(survey, split="page", source_name="Pavlovia file", project_path=None, match_library=False, language=None):
    results = _build(survey, split, language)
    print(f"[PRISM] Pavlovia import: {source_name}")
    print(f"[PRISM] Split by {split} -> {len(results)} questionnaire(s):")
    for info, _t, _n in results:
        print(f"[PRISM]   {info['key']:<8} {info['name']}  {info['item_count']} item(s)")
    listing = [dict(info) for info, _t, _n in results]
    if match_library:
        from src.converters.library_wording_match import public_library_match
        from src.converters.template_import import match_questionnaire_to_library

        for entry, (info, template, _n) in zip(listing, results):
            entry["library_match"] = public_library_match(match_questionnaire_to_library(template, info["name"], project_path))
    return listing


def pavlovia_questionnaire(survey, key, split="page", language=None):
    """(template, import notes) of one questionnaire of the survey."""
    results = _build(survey, split, language)
    for info, template, notes in results:
        if info["key"] == key:
            print(f"[PRISM] Loading {key} '{info['name']}': {info['item_count']} item(s)")
            return template, notes
    raise ValueError(f"No questionnaire '{key}' (split by {split}). Valid keys: {', '.join(i['key'] for i, _, _ in results) or 'none'}")


def pavlovia_questionnaire_template(survey, key, split="page", language=None):
    return pavlovia_questionnaire(survey, key, split, language)[0]
