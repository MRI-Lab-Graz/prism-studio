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
import re

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


def missing_task_name_error(template: dict) -> dict | None:
    """Every template needs a task name (the library relaxation only covers the other project fields)."""
    study = template.get("Study")
    if isinstance(study, dict) and str(study.get("TaskName") or "").strip():
        return None
    return {"path": "Study/TaskName", "message": "Every template needs a task name (letters, digits and hyphens, e.g. 'pss')"}
