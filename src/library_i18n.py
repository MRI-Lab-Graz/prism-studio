from __future__ import annotations

import copy
from typing import Any, List


def _detect_language_from_texts(texts: list[str]) -> str:
    """Heuristic: detect German vs English from content."""

    combined = " ".join([t for t in texts if isinstance(t, str)]).lower()
    if not combined.strip():
        return "en"

    # Umlauts / ß strongly suggest German.
    if any(ch in combined for ch in ["ä", "ö", "ü", "ß"]):
        return "de"

    german_tokens = [
        " nicht ",
        " oder ",
        " keine ",
        " während ",
        " immer ",
        " selten ",
        " meistens ",
        " öfter ",
    ]
    padded = f" {combined} "
    if any(tok in padded for tok in german_tokens):
        return "de"

    return "en"


def _is_lang_map(value: Any) -> bool:
    return isinstance(value, dict) and all(isinstance(k, str) for k in value.keys())


def localize(value: Any, lang: str, fallback_langs: list[str] | None = None) -> Any:
    """Resolve a localized value.

    Accepts either a plain value (returned as-is) or a mapping like {"de": "...", "en": "..."}.

    If the requested language is missing, tries fallback_langs (in order), then the first
    available value.
    """

    if not _is_lang_map(value):
        return value

    lang = (lang or "").strip()
    if lang and lang in value and value[lang] not in (None, ""):
        return value[lang]

    for fb in fallback_langs or []:
        fb = (fb or "").strip()
        if fb and fb in value and value[fb] not in (None, ""):
            return value[fb]

    # last resort: first non-empty
    for v in value.values():
        if v not in (None, ""):
            return v

    # last resort: empty string (keeps schema-valid string fields)
    return ""


def compile_survey_template(
    source: dict, lang: str, fallback_langs: list[str] | None = None
) -> dict:
    """Compile an i18n-capable library template into a PRISM survey sidecar.

    The output is schema-compatible with `schemas/*/survey.schema.json`:
    - item Description is a string
    - Levels mapping values are strings
    - no extra top-level keys

    Notes:
    - The compiler strips the top-level "I18n" block if present.
    - `Technical.Language` is set to `lang`.
    """

    fallback_langs = fallback_langs or []
    out: dict[str, Any] = {}

    # Copy known blocks first, localizing selected fields.
    technical = copy.deepcopy(
        source.get("Technical", {}) if isinstance(source.get("Technical"), dict) else {}
    )
    study = copy.deepcopy(
        source.get("Study", {}) if isinstance(source.get("Study"), dict) else {}
    )
    metadata = copy.deepcopy(
        source.get("Metadata", {}) if isinstance(source.get("Metadata"), dict) else {}
    )

    # Localize potentially user-facing strings inside blocks.
    if "SoftwarePlatform" in technical:
        technical["SoftwarePlatform"] = localize(
            technical.get("SoftwarePlatform"), lang, fallback_langs
        )

    # Force a single BCP-47-ish tag here (schema expects string).
    technical["Language"] = lang

    for key in ["OriginalName", "Description", "Version"]:
        if key in study:
            study[key] = localize(study.get(key), lang, fallback_langs)

    out["Technical"] = technical
    out["Study"] = study
    out["Metadata"] = metadata

    # Items: any other top-level key except known blocks.
    reserved = {"Technical", "Study", "Metadata", "I18n"}
    for item_id, item_def in source.items():
        if item_id in reserved:
            continue
        if not isinstance(item_def, dict):
            continue

        item_out: dict[str, Any] = copy.deepcopy(item_def)

        if "Description" in item_out:
            item_out["Description"] = str(
                localize(item_out.get("Description"), lang, fallback_langs) or ""
            )

        if "Levels" in item_out and isinstance(item_out.get("Levels"), dict):
            levels_out: dict[str, Any] = {}
            for level_key, level_val in item_out["Levels"].items():
                levels_out[str(level_key)] = str(
                    localize(level_val, lang, fallback_langs) or ""
                )
            item_out["Levels"] = levels_out

        out[item_id] = item_out

    return out


def migrate_survey_template_to_i18n(source: dict, languages: list[str]) -> dict:
    """Wrap an existing single-language PRISM survey template into an i18n-capable structure.

    This does NOT translate content. It puts existing strings into the detected language
    (from Technical.Language if present), and leaves other languages empty strings.

    Output keeps the original top-level structure and adds an "I18n" block.
    """

    languages = [str(l).strip() for l in (languages or []) if str(l).strip()]
    if not languages:
        languages = ["de", "en"]

    # Detect language from content (more reliable than Technical.Language in legacy files).
    texts: List[str] = []
    tech_raw = source.get("Technical")
    tech = tech_raw if isinstance(tech_raw, dict) else {}
    study_raw = source.get("Study")
    study = study_raw if isinstance(study_raw, dict) else {}
    for k in ["OriginalName", "Description"]:
        v = study.get(k)
        if isinstance(v, str):
            texts.append(v)

    reserved = {"Technical", "Study", "Metadata", "I18n"}
    for item_id, item_def in source.items():
        if item_id in reserved:
            continue
        if not isinstance(item_def, dict):
            continue
        d = item_def.get("Description")
        if isinstance(d, str):
            texts.append(d)
        levels = item_def.get("Levels")
        if isinstance(levels, dict):
            for lv in levels.values():
                if isinstance(lv, str):
                    texts.append(lv)

    detected = _detect_language_from_texts(texts)
    default_lang = (
        detected if detected in languages else (languages[0] if languages else "de")
    )

    def wrap_str(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        return {lang: (value if lang == default_lang else "") for lang in languages}

    out = copy.deepcopy(source)
    if isinstance(out.get("Technical"), dict):
        out["Technical"]["Language"] = default_lang
    out["I18n"] = {
        "Languages": languages,
        "DefaultLanguage": default_lang,
        "Note": "Generated from single-language template; missing translations are empty strings.",
    }

    # Study block
    if isinstance(out.get("Study"), dict):
        for k in ["OriginalName", "Description", "Version"]:
            if k in out["Study"]:
                out["Study"][k] = wrap_str(out["Study"].get(k))

    # Items
    reserved = {"Technical", "Study", "Metadata", "I18n"}
    for item_id, item_def in list(out.items()):
        if item_id in reserved:
            continue
        if not isinstance(item_def, dict):
            continue

        if "Description" in item_def:
            item_def["Description"] = wrap_str(item_def.get("Description"))

        levels = item_def.get("Levels")
        if isinstance(levels, dict):
            new_levels: dict[str, Any] = {}
            for lk, lv in levels.items():
                new_levels[str(lk)] = wrap_str(lv)
            item_def["Levels"] = new_levels

    return out
