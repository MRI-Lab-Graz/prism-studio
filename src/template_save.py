"""Saving a template into a library: one function for ``library template-save`` and Studio's Save button."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.personal_library import personal_library_folder
from src.prism_template_validation import (
    SEVERITY_ERROR,
    is_missing_field_error,
    missing_required_fields,
    relax_schema_for_library_template,
    strip_template_editor_internal_keys,
    validate_template_against_schema,
    with_default_task_name,
)
from src.schema_manager import apply_schema_validation_profile, load_schema
from src.survey_export_settings import strip_export_settings
from src.survey_template_normalization import normalize_survey_template_for_validation
from src.utils.io import dump_json_text


@dataclass
class SavedTemplate:
    """What a save did: the file, the problems it does not refuse over (``{path, message, severity}``; severity is
    SEVERITY_ERROR or SEVERITY_WARNING from ``src.prism_template_validation``), and what it stripped."""

    path: Path
    missing: list[dict]
    removed: list[str]


class TemplateInvalid(Exception):
    def __init__(self, errors: list[dict]):
        self.errors = errors
        super().__init__("; ".join(f"{e.get('path')}: {e.get('message')}" for e in errors))


class TemplateExists(Exception):
    def __init__(self, path: Path):
        self.path = path
        super().__init__(f"{path.name} already exists")


class TemplateIncomplete(TemplateInvalid):
    """A template used for converting or exporting lacks required fields; the message has one line per field."""

    def __init__(self, errors: list[dict]):
        self.errors = errors
        Exception.__init__(self, "\n".join(e["message"] for e in errors))


_MISSING_HINTS = {"Technical/Respondent": " – set who answered the questionnaire (self, parent, clinician, …)"}


def require_complete_template(
    template: dict, *, source: str, app_root=None, schema_version: str = "stable", project: bool = True
) -> None:
    """Raise ``TemplateIncomplete`` unless ``template`` has every field the survey schema requires and no
    declared-language error. Saving never needs this; using a template does. A template used in a project
    (``project=True``, converting data) is a project copy and needs the project-level fields (Respondent,
    AdministrationMethod, SoftwarePlatform) too; an export of a template (``project=False``) needs the global
    fields only."""
    schema = apply_schema_validation_profile(
        load_schema(
            "survey",
            **({"schema_dir": str(Path(app_root) / "schemas")} if app_root else {}),
            version=schema_version,
        ),
        profile="project",
    )
    if not project:
        schema = relax_schema_for_library_template(schema)
    template = with_default_task_name(template, Path(source).name, "survey")  # the file name is the task name
    found = [*missing_required_fields(template, schema), *_language_findings(template)]
    errors = [
        {"path": f["path"], "message": f"{f['message']} in {source}{_MISSING_HINTS.get(f['path'], '')}"}
        for f in found
        if f["severity"] == SEVERITY_ERROR
    ]
    if errors:
        raise TemplateIncomplete(errors)


def save_template(
    modality: str,
    filename: str,
    template: dict,
    *,
    target: str,
    project_root,
    app_root,
    schema_version: str = "stable",
    relaxed: bool = False,
    allow_overwrite: bool = False,
) -> SavedTemplate:
    """Validate ``template`` and write it into the project's ``code/library/<modality>`` (``target="project"``) or
    the personal library (``"personal"``). ``relaxed`` validates it as a library template (not a project copy), as
    every personal one is: the project-only fields are optional, the task name never is.

    Export settings are stripped from a survey template first. Required fields that are missing or empty, and
    language findings (``I18n.Languages`` against the texts), do not refuse the save: the file is written and they
    come back in ``SavedTemplate.missing``. Every other schema error raises TemplateInvalid.

    Raises ValueError (bad filename or template), TemplateInvalid, TemplateExists, RuntimeError (no project or
    personal library to save into) and FileNotFoundError (no schema).
    """
    filename = str(filename or "").strip()
    if not filename or "/" in filename or "\\" in filename:
        raise ValueError("Invalid filename: it must be a bare filename (no path separators)")
    if not filename.lower().endswith(".json"):
        filename += ".json"
    if not isinstance(template, dict):
        raise ValueError("Template must be a JSON object")

    template = strip_template_editor_internal_keys(template)
    removed: list[str] = []
    if modality == "survey":
        template, removed = strip_export_settings(template)
        template = normalize_survey_template_for_validation(template)

    schema = load_schema(modality, schema_dir=str(Path(app_root) / "schemas"), version=schema_version)
    if not schema:
        raise FileNotFoundError(f"No schema found for modality={modality} version={schema_version}")
    relaxed = relaxed or target == "personal"
    if relaxed:
        schema = relax_schema_for_library_template(schema)
    errors = list(validate_template_against_schema(instance=template, schema=schema))
    missing = missing_required_fields(template, schema)
    refused = [e for e in errors if not is_missing_field_error(e, template, missing)]
    if refused:
        raise TemplateInvalid(refused)
    missing += _language_findings(template)

    if target == "personal":
        folder = personal_library_folder(modality, app_root)
    elif project_root is None:
        raise RuntimeError("Select a project first; templates are saved into the project's code/library.")
    else:
        folder = Path(project_root) / "code" / "library" / modality
    path = folder / filename
    if path.exists() and not allow_overwrite:
        raise TemplateExists(path)
    folder.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json_text(template), encoding="utf-8")
    return SavedTemplate(path=path, missing=missing, removed=removed)


def _language_findings(template: dict) -> list[dict]:
    from src.template_validator import TemplateValidator

    findings = TemplateValidator.validate_language_consistency_from_data(template, supersede_declared=True)
    return [{"path": f["path"], "message": f["message"], "severity": f["severity"]} for f in findings]
