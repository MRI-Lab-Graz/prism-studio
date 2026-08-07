"""Shared PRISM template (survey/biometrics) schema-validation helpers.

Extracted from app/src/web/blueprints/tools_helpers.py /
tools_template_editor_blueprint.py so the CLI's template save/delete
commands validate a template exactly the way the Studio GUI's Template
Editor does, instead of leaving these pure functions Flask-blueprint-local
and unreachable from the CLI. See
docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md, P2.
"""

from __future__ import annotations

import copy

from src.converters.survey_io import normalize_paper_software_platform

# Fields in Study/Technical that are relaxed when validating a global/library
# template. These are either project-copy-specific (TaskName) or frequently absent
# from official library entries that are still work-in-progress (LicenseID, Citation).
LIBRARY_RELAXED_STUDY_REQUIRED = {"TaskName", "LicenseID", "Citation"}
LIBRARY_RELAXED_TECHNICAL_REQUIRED = {"SoftwarePlatform", "AdministrationMethod"}


def strip_template_editor_internal_keys(template: dict) -> dict:
    """Remove editor-internal metadata keys that are not part of PRISM schemas."""
    if not isinstance(template, dict):
        return template

    cleaned = dict(template)
    cleaned.pop("_aliases", None)
    cleaned.pop("_reverse_aliases", None)
    return cleaned


def relax_schema_for_library_template(schema: dict) -> dict:
    """Return a copy of *schema* with project-local required fields removed.

    Official library templates intentionally omit administration-specific fields
    (TaskName, SoftwarePlatform, AdministrationMethod) that only make sense in a
    project copy. Validating them against the full project-copy schema produces
    misleading errors. This helper strips those fields from the required arrays
    so validators only flag genuine structural problems.
    """
    schema = copy.deepcopy(schema)
    props = schema.get("properties", {})

    study_schema = props.get("Study", {})
    study_required = study_schema.get("required")
    if isinstance(study_required, list):
        study_schema["required"] = [
            f for f in study_required if f not in LIBRARY_RELAXED_STUDY_REQUIRED
        ]

    tech_schema = props.get("Technical", {})
    tech_required = tech_schema.get("required")
    if isinstance(tech_required, list):
        tech_schema["required"] = [
            f for f in tech_required if f not in LIBRARY_RELAXED_TECHNICAL_REQUIRED
        ]

    return schema


def validate_template_against_schema(*, instance: object, schema: dict) -> list[dict]:
    """Validate a PRISM template against a JSON schema.

    Beyond plain jsonschema validation, also enforces that SoftwareVersion is
    present whenever SoftwarePlatform names real software (not "Paper and
    Pencil" / AdministrationMethod="paper") — a PRISM-specific rule not
    expressible in the JSON Schema itself.
    """
    from jsonschema import Draft7Validator

    normalized_instance = normalize_paper_software_platform(instance)

    validator = Draft7Validator(schema)
    errors = []
    for err in sorted(validator.iter_errors(normalized_instance), key=lambda e: list(e.path)):
        path = "/".join(str(p) for p in err.path)
        errors.append({"path": path, "message": err.message})

    if isinstance(normalized_instance, dict) and "Technical" in normalized_instance:
        technical = normalized_instance["Technical"]
        if isinstance(technical, dict):
            admin_method = str(technical.get("AdministrationMethod", "")).strip().lower()
            platform = str(technical.get("SoftwarePlatform", "")).strip()
            version = str(technical.get("SoftwareVersion", "")).strip()
            if (
                admin_method != "paper"
                and platform
                and platform != "Paper and Pencil"
                and not version
            ):
                errors.append(
                    {
                        "path": "Technical/SoftwareVersion",
                        "message": f"SoftwareVersion is required when SoftwarePlatform is '{platform}'",
                    }
                )

    return errors
