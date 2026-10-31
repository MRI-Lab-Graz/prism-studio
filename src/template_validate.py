"""One template check for Studio's Template Editor "Validate" and `library template-validate`.

Kept out of prism_template_validation.py: that module ships in the validator image, and this one needs the
survey normalisation and the save warnings, which the validator does not.
"""

from __future__ import annotations

import src.prism_template_validation as _p


def load_template_schema(modality: str, *, app_root, schema_version: str) -> dict:
    import os

    from src.schema_manager import load_schema

    schema = load_schema(modality, schema_dir=os.path.join(app_root, "schemas"), version=schema_version)
    if not schema:
        raise FileNotFoundError(f"No schema found for modality={modality} version={schema_version}")
    return schema


def validate_template_document(
    template: dict, *, modality: str, app_root, schema_version: str = "stable", is_global: bool = False
) -> dict:
    """What Studio's Template Editor "Validate" and `library template-validate` answer: schema errors, the
    language and item warnings, and the item rules that are errors. One function, so the two cannot differ."""
    from src.constants import SUPPORTED_MODALITIES
    from src.survey_template_normalization import normalize_survey_template_for_validation
    from src.template_save import template_warnings
    from src.template_validator import TemplateValidator

    if modality not in SUPPORTED_MODALITIES:
        raise ValueError("Invalid modality")
    if not isinstance(template, dict):
        raise ValueError("Template must be a JSON object")
    template = _p.strip_template_editor_internal_keys(template)
    if modality == "survey":
        template = normalize_survey_template_for_validation(template)
    schema = load_template_schema(modality, app_root=app_root, schema_version=schema_version)
    if is_global:
        schema = _p.relax_schema_for_library_template(schema)
    errors = _p.validate_template_against_schema(instance=template, schema=schema)
    language_warnings, item_warnings = template_warnings(template)
    if modality in ("survey", "biometrics"):
        errors += [
            {"path": f["path"], "message": f["message"]}
            for f in TemplateValidator.validate_item_rules_from_data(template)
            if f["severity"] == "error"
        ]
    else:
        item_warnings = []
    return {"ok": not errors, "errors": errors, "language_warnings": language_warnings, "item_warnings": item_warnings}
