"""Shared survey-template normalization applied before schema validation.

These are "fill in what's derivable" steps — not relaxations that hide real
errors — so both entry points that validate a survey template's JSON
against the PRISM schema should apply them first:

- The Studio GUI's Template Editor Validate/Save actions
  (app/src/web/blueprints/tools_template_editor_blueprint.py).
- The CLI's `survey validate` (app/src/library_validator.py::check_uniqueness).

Before this module existed, only the GUI applied these steps, so a
template could pass validation in the Template Editor and then fail
`survey validate` on the same file for the exact reasons this module
compensates for (an omitted single-version VariantID, an empty optional
variant placeholder, an implicit numeric Levels range) — see
docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md, P1-4.
"""

from __future__ import annotations

from src.converters.survey_io import normalize_paper_software_platform
from src.survey_scale_inference import apply_implicit_numeric_level_ranges

_METADATA_SECTION_KEYS = {
    "Technical",
    "Study",
    "Metadata",
    "I18n",
    "LimeSurvey",
    "Scoring",
    "Normative",
}


def is_blank_localized_value(value: object) -> bool:
    """True if *value* is empty/whitespace, recursively for dict/list values."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, dict):
        return all(is_blank_localized_value(v) for v in value.values())
    if isinstance(value, list):
        return all(is_blank_localized_value(v) for v in value)
    return False


def is_empty_variant_definition_placeholder(entry: object) -> bool:
    """True if *entry* is a VariantDefinitions row with nothing filled in."""
    if not isinstance(entry, dict):
        return False

    variant_id = str(entry.get("VariantID") or "").strip()
    item_count = entry.get("ItemCount")
    scale_type = str(entry.get("ScaleType") or "").strip().lower()
    description = entry.get("Description")
    extra_keys = set(entry.keys()) - {
        "VariantID",
        "ItemCount",
        "ScaleType",
        "Description",
    }

    return (
        not variant_id
        and item_count in {None, "", 0}
        and scale_type in {"", "likert"}
        and is_blank_localized_value(description)
        and all(is_blank_localized_value(entry.get(key)) for key in extra_keys)
    )


def autofill_single_version_variant_ids(template: dict) -> dict:
    """Fill empty VariantID values when the template has exactly one version.

    A template with a single Version doesn't need per-variant IDs spelled
    out everywhere, but the schema still requires VariantID to be
    non-empty wherever a VariantScales/VariantDefinitions entry exists.
    """
    if not isinstance(template, dict):
        return template

    study = template.get("Study")
    if not isinstance(study, dict):
        return template

    versions = [
        str(v).strip()
        for v in (study.get("Versions") or [])
        if isinstance(v, str) and str(v).strip()
    ]
    fallback_version = ""
    if len(versions) == 1:
        fallback_version = versions[0]
    elif len(versions) == 0:
        singular = study.get("Version")
        if isinstance(singular, str) and singular.strip():
            fallback_version = singular.strip()

    if not fallback_version:
        return template

    variant_defs = study.get("VariantDefinitions")
    if isinstance(variant_defs, list):
        for entry in variant_defs:
            if (
                isinstance(entry, dict)
                and not str(entry.get("VariantID") or "").strip()
            ):
                entry["VariantID"] = fallback_version

    for key, value in template.items():
        if key in _METADATA_SECTION_KEYS:
            continue
        if not isinstance(value, dict):
            continue
        variant_scales = value.get("VariantScales")
        if not isinstance(variant_scales, list):
            continue
        for entry in variant_scales:
            if (
                isinstance(entry, dict)
                and not str(entry.get("VariantID") or "").strip()
            ):
                entry["VariantID"] = fallback_version

    return template


def prune_optional_variant_placeholders(template: dict) -> dict:
    """Drop empty VariantDefinitions rows that only make sense with >1 version."""
    if not isinstance(template, dict):
        return template

    study = template.get("Study")
    if not isinstance(study, dict):
        return template

    versions = [
        str(value).strip()
        for value in (study.get("Versions") or [])
        if isinstance(value, str) and str(value).strip()
    ]
    has_multiple_versions = len(versions) > 1
    variant_definitions = study.get("VariantDefinitions")

    if not isinstance(variant_definitions, list):
        return template

    filtered_definitions = []
    for entry in variant_definitions:
        if not has_multiple_versions and is_empty_variant_definition_placeholder(
            entry
        ):
            continue
        filtered_definitions.append(entry)

    if filtered_definitions:
        study["VariantDefinitions"] = filtered_definitions
    else:
        study.pop("VariantDefinitions", None)

    return template


def normalize_survey_template_for_validation(template: dict) -> dict:
    """Apply the full survey-template normalization pipeline before validation.

    Order matters: platform normalization first (may add/adjust Technical
    fields), then variant-ID/placeholder cleanup, then implicit numeric
    level range inference last (works off the now-stable item structure).
    """
    normalized = normalize_paper_software_platform(template)
    if isinstance(normalized, dict):
        template = normalized
    template = autofill_single_version_variant_ids(template)
    template = prune_optional_variant_placeholders(template)
    template = apply_implicit_numeric_level_ranges(template)
    return template
