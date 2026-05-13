import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator


def validate_project_templates_for_tasks(
    *,
    tasks: list[str],
    project_path: str | None,
    schema_version: str = "stable",
    normalize_paper_software_platform=None,
) -> list[dict[str, str]]:
    """Validate project survey templates for used tasks and return issues."""
    if not project_path or not tasks:
        return []

    project_root = Path(project_path).expanduser().resolve()
    if project_root.is_file():
        project_root = project_root.parent

    template_dir = project_root / "code" / "library" / "survey"
    if not template_dir.exists():
        return []

    try:
        from src.schema_manager import load_schema

        app_root = Path(__file__).resolve().parents[3]
        schema_dir = app_root / "schemas"
        schema = load_schema("survey", str(schema_dir), version=schema_version)
        if not schema:
            return []
        validator = Draft7Validator(schema)
    except Exception:
        return []

    def _has_multiple_versions(template_payload: dict[str, Any] | None) -> bool:
        if not isinstance(template_payload, dict):
            return False
        study = template_payload.get("Study")
        if not isinstance(study, dict):
            return False
        versions = study.get("Versions")
        return isinstance(versions, list) and len([value for value in versions if value]) > 1

    def _is_missing_version(template_payload: dict[str, Any]) -> bool:
        study = template_payload.get("Study")
        if not isinstance(study, dict):
            return True
        value = study.get("Version")
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip() == ""
        if isinstance(value, dict):
            return not value
        return False

    issues: list[dict[str, str]] = []
    for task in sorted(set(tasks)):
        template_path = template_dir / f"survey-{task}.json"
        if not template_path.exists():
            continue

        try:
            with open(template_path, "r", encoding="utf-8") as file_handle:
                payload = json.load(file_handle)
        except Exception as exc:
            issues.append(
                {
                    "file": str(template_path),
                    "message": f"Template is not valid JSON: {exc}",
                }
            )
            continue

        normalized_payload = payload
        if callable(normalize_paper_software_platform):
            maybe_normalized_payload = normalize_paper_software_platform(payload)
            if isinstance(maybe_normalized_payload, dict):
                normalized_payload = maybe_normalized_payload

        for err in validator.iter_errors(normalized_payload):
            field_path = " -> ".join([str(part) for part in err.path])
            prefix = f"{field_path}: " if field_path else ""
            issues.append(
                {
                    "file": str(template_path),
                    "message": f"{prefix}{err.message}",
                }
            )

        if _has_multiple_versions(normalized_payload) and _is_missing_version(
            normalized_payload
        ):
            issues.append(
                {
                    "file": str(template_path),
                    "message": "Study -> Version: required when multiple instrument versions exist (Study.Versions).",
                }
            )

    return issues


def collect_project_template_warnings_for_tasks(
    *,
    tasks: list[str],
    project_path: str | None,
) -> list[dict[str, str]]:
    """Collect non-blocking template quality warnings for selected tasks."""
    if not project_path or not tasks:
        return []

    project_root = Path(project_path).expanduser().resolve()
    if project_root.is_file():
        project_root = project_root.parent

    template_dir = project_root / "code" / "library" / "survey"
    if not template_dir.exists():
        return []

    warnings: list[dict[str, str]] = []
    non_item_keys = {
        "Technical",
        "Task",
        "Study",
        "Metadata",
        "Scoring",
        "Normative",
        "I18n",
        "_aliases",
        "_reverse_aliases",
    }

    for task in sorted(set(tasks)):
        template_path = template_dir / f"survey-{task}.json"
        if not template_path.exists():
            continue

        try:
            with open(template_path, "r", encoding="utf-8") as file_handle:
                payload = json.load(file_handle)
        except Exception:
            continue

        if not isinstance(payload, dict):
            continue

        task_name = str(payload.get("Study", {}).get("TaskName") or task).strip()
        task_norm = task_name.lower() or task.lower()

        for item_key, item_def in payload.items():
            if item_key in non_item_keys or not isinstance(item_def, dict):
                continue

            has_levels = isinstance(item_def.get("Levels"), dict)
            has_range = "MinValue" in item_def or "MaxValue" in item_def
            if has_levels and has_range:
                warnings.append(
                    {
                        "file": str(template_path),
                        "message": (
                            f"Template '{task_norm}' item '{item_key}' defines both "
                            "Levels and Min/Max; numeric range takes precedence and "
                            "Levels will be treated as labels only."
                        ),
                    }
                )

    return warnings


def build_template_completion_gate(
    *,
    tasks: list[str],
    issues: list[dict[str, str]],
) -> dict[str, Any]:
    task_list = sorted({task for task in tasks if task})
    return {
        "blocked": True,
        "reason": "project_template_completion_required",
        "title": "Template Completion Required",
        "message": (
            "Official templates were copied to your project library. "
            "Some required project-level fields still need to be completed in these templates before importing survey data."
        ),
        "tasks": task_list,
        "issue_count": len(issues),
        "next_steps": [
            "Open Template Editor for the copied survey templates in code/library/survey.",
            "Fill project-specific administration fields in Technical (for example AdministrationMethod, SoftwarePlatform, SoftwareVersion) and any remaining required metadata.",
            "Run Preview again. Import is unlocked automatically after template validation passes.",
        ],
    }