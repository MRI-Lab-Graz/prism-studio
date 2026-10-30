"""Shared PRISM template (survey/biometrics) schema-validation helpers.

Extracted from app/src/web/blueprints/tools_helpers.py /
tools_template_editor_blueprint.py so the CLI's template save/delete
commands validate a template exactly the way the Studio GUI's Template
Editor does, instead of leaving these pure functions Flask-blueprint-local
and unreachable from the CLI. See
docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md, P2.
"""

from __future__ import annotations

import re

from src.schema_manager import apply_schema_validation_profile

_VALID_SOFTWARE_PLATFORMS = {
    "LimeSurvey",
    "PsychoPy",
    "Pavlovia",
    "Paper and Pencil",
    "Other",
}


def normalize_paper_software_platform(payload: object) -> object:
    """Normalise legacy paper-admin software metadata for schema compatibility."""
    if not isinstance(payload, dict):
        return payload

    technical = payload.get("Technical")
    if not isinstance(technical, dict):
        return payload

    administration_method = str(technical.get("AdministrationMethod", "")).strip().lower()
    software_platform = str(technical.get("SoftwarePlatform", "")).strip()

    if administration_method != "paper":
        return payload

    if software_platform in _VALID_SOFTWARE_PLATFORMS:
        return payload

    normalized_technical = dict(technical)
    normalized_technical["SoftwarePlatform"] = "Paper and Pencil"
    normalized_technical["SoftwareVersion"] = ""

    normalized_payload = dict(payload)
    normalized_payload["Technical"] = normalized_technical
    return normalized_payload


# The severity of a finding in ``SavedTemplate.missing`` (and of the language findings that feed it): the one
# vocabulary. A gate may refuse on SEVERITY_ERROR; SEVERITY_WARNING is shown only.
SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"


def strip_template_editor_internal_keys(template: dict) -> dict:
    """Remove editor-internal metadata keys that are not part of PRISM schemas."""
    if not isinstance(template, dict):
        return template

    cleaned = dict(template)
    cleaned.pop("_aliases", None)
    cleaned.pop("_reverse_aliases", None)
    return cleaned


def relax_schema_for_library_template(schema: dict) -> dict:
    """Return a copy of *schema* for a global/library template: the fields the schema lists in
    ``x-prism.projectOnlyRequired`` (set in the project copy, e.g. Respondent) are not required."""
    return apply_schema_validation_profile(schema, profile="official")


# What a schema regex means, for the people who fill in the form.
_PATTERN_HINTS = {
    "^[a-zA-Z0-9][-a-zA-Z0-9]*$": "use only letters, digits and hyphens, starting with a letter or digit (no spaces or underscores)",
    "^[a-zA-Z0-9][a-zA-Z0-9\\-]*$": "use only letters, digits and hyphens, starting with a letter or digit (no spaces or underscores)",
    "^(ses-[a-zA-Z0-9]+)?$": "use the form ses-<label>, e.g. ses-1",
    "^(run-[a-zA-Z0-9]+)?$": "use the form run-<label>, e.g. run-2",
}


def _readable_errors(err) -> list[dict]:
    """One or more ``{path, message}`` for a jsonschema error.

    "X is not valid under any of the given schemas" (oneOf/anyOf) would print the whole
    instance; instead report what is wrong in the alternative that is closest to matching.
    """
    if err.validator in ("oneOf", "anyOf") and err.context:
        branches: dict[int, list] = {}
        for sub in err.context:
            branches.setdefault(sub.schema_path[0], []).append(sub)
        # An alternative that lacks its required key is the wrong kind of object, not a typo.
        closest = min(
            branches.values(),
            key=lambda errs: (any(e.validator == "required" and not e.path for e in errs), len(errs)),
        )
        return [item for sub in closest for item in _readable_errors_at(sub, list(err.path))]
    return [_error_dict(err, list(err.path))]


def _readable_errors_at(sub, base_path: list) -> list[dict]:
    if sub.validator in ("oneOf", "anyOf") and sub.context:
        return _readable_errors(sub)
    return [_error_dict(sub, base_path + list(sub.path))]


def _error_dict(err, path: list) -> dict:
    hint = _PATTERN_HINTS.get(err.schema.get("pattern")) if err.validator == "pattern" else None
    return {
        "path": "/".join(str(p) for p in path),
        "message": f"'{err.instance}' is not allowed: {hint}" if hint else err.message,
    }


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
        errors.extend(_readable_errors(err))

    # the platform (and so its version) is a project-copy field: a relaxed library schema does not require it
    platform_required = "SoftwarePlatform" in (schema.get("properties", {}).get("Technical", {}).get("required") or [])
    if platform_required and isinstance(normalized_instance, dict) and "Technical" in normalized_instance:
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


_TASK_NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9\-]*")


def with_default_task_name(template: dict, filename: str, modality: str) -> dict:
    """Fill an empty ``Study.TaskName`` from ``<modality>-<task>.json``; the file name is the task name."""
    study = template.get("Study")
    if isinstance(study, dict) and str(study.get("TaskName") or "").strip():
        return template
    task = filename[len(modality) + 1 : -len(".json")] if filename.startswith(f"{modality}-") and filename.endswith(".json") else ""
    if _TASK_NAME.fullmatch(task):
        template = {**template, "Study": {**(study if isinstance(study, dict) else {}), "TaskName": task}}
    return template


_REQUIRED_SECTIONS = ("Technical", "Study", "Metadata", "I18n")
_REQUIRED_PROPERTY = re.compile(r"^'(.+)' is a required property$")


def is_blank(value) -> bool:
    """The one rule for "not filled in": absent, ``None``, empty/whitespace text, an empty list, or a language
    object whose ``en`` is empty. (The template editor's JavaScript applies the same rule.)"""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return not value
    if isinstance(value, dict):
        return is_blank(value.get("en"))
    return False


def missing_required_fields(template: dict, schema: dict) -> list[dict]:
    """One ``{"path": "Technical/Respondent", "message": "Technical/Respondent is missing", "severity": SEVERITY_ERROR}`` per required field of
    Technical, Study, Metadata and I18n (as the given, possibly relaxed, schema lists them) that is not filled in."""
    props = schema.get("properties") if isinstance(schema, dict) else None
    props = props if isinstance(props, dict) else {}
    template = template if isinstance(template, dict) else {}
    missing = []
    for section in _REQUIRED_SECTIONS:
        required = (props.get(section) or {}).get("required") if isinstance(props.get(section), dict) else None
        values = template.get(section)
        values = values if isinstance(values, dict) else {}
        for field in required if isinstance(required, list) else []:
            if is_blank(values.get(field)):
                missing.append({"path": f"{section}/{field}", "message": f"{section}/{field} is missing", "severity": SEVERITY_ERROR})
    return missing


def is_missing_field_error(error: dict, template: dict, missing: list[dict]) -> bool:
    """Which schema errors a save only warns about: those that say a required field of a section the template has
    is missing or empty (it is one of ``missing``, or inside one), or that a whole section is absent (its required
    fields are then all in ``missing``). Everything else (wrong values, wrong types) refuses the save."""
    paths = {m["path"] for m in missing}
    path = str(error.get("path") or "")
    found = _REQUIRED_PROPERTY.match(str(error.get("message") or ""))
    if found and path == "" and found.group(1) in _REQUIRED_SECTIONS:
        return True
    if found and path in _REQUIRED_SECTIONS and isinstance(template.get(path), dict):
        return f"{path}/{found.group(1)}" in paths
    return any(path == p or path.startswith(p + "/") for p in paths)
