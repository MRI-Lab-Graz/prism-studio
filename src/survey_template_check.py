"""The check Studio runs before a conversion and ``library template-check`` runs from the command line:
are the project's survey templates complete enough to convert with? One function; the rules are the backend gate's."""

import json
from pathlib import Path
from typing import Any

from src.prism_template_validation import normalize_paper_software_platform
from src.template_save import TemplateIncomplete, require_complete_template


def validate_project_templates_for_tasks(
    *,
    tasks: list[str] | None,
    project_path: str | None,
    schema_version: str = "stable",
) -> list[dict[str, str]]:
    """Validate project survey templates for used tasks and return issues (``tasks=None``: every one of them)."""
    if not project_path or (tasks is not None and not tasks):
        return []

    project_root = Path(project_path).expanduser().resolve()
    if project_root.is_file():
        project_root = project_root.parent

    template_dir = project_root / "code" / "library" / "survey"
    if not template_dir.exists():
        return []
    if tasks is None:
        tasks = [p.stem.removeprefix("survey-") for p in template_dir.glob("survey-*.json")]

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

        normalized_payload = normalize_paper_software_platform(payload)

        try:
            require_complete_template(normalized_payload, source=str(template_path), schema_version=schema_version)
        except TemplateIncomplete as incomplete:  # the backend gate: the one set of rules
            issues.extend({"file": str(template_path), "message": e["message"]} for e in incomplete.errors)

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
