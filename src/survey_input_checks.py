"""What Studio's survey page asks about an input table before converting it, and what `library template-check --input`
and `survey detect-version-contexts` answer: which official templates match, whether the project's copies are complete,
which tasks exist in several versions. One implementation for Studio and the CLI; the routes only save the upload."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable

from src.converters.file_reader import expected_delimiter_for_suffix
from src.survey_library_resolution import resolve_survey_library
from src.survey_template_check import project_template_warnings, validate_project_templates_for_tasks
from src.survey_template_sources import (
    build_effective_library,
    copy_templates_to_project,
    infer_technical_defaults,
    is_standard_library,
    run_survey_with_template_sources,
)
from src.survey_workflow_service import SUPPORTED_SURVEY_INPUT_MESSAGE, SUPPORTED_SURVEY_TABULAR_SUFFIXES
from src.system_files import filter_system_files
from src.template_save import TemplateIncomplete


def _converters():
    from src.converters.survey import convert_survey_file_to_prism_dataset, convert_survey_lsa_to_prism_dataset

    return convert_survey_file_to_prism_dataset, convert_survey_lsa_to_prism_dataset


def coerce_template_version_value(raw_value: object) -> str:
    """Collapse template version payloads to a concrete version string."""
    if isinstance(raw_value, str):
        return raw_value.strip()
    if isinstance(raw_value, dict):
        if "version" in raw_value:
            nested = coerce_template_version_value(raw_value.get("version"))
            if nested:
                return nested
        for lang in ("en", "de"):
            candidate = raw_value.get(lang)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        for candidate in raw_value.values():
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return ""


def effective_template_version_overrides(project_path, template_version_overrides):
    """The versions to convert with: the ones asked for, else what the project remembers."""
    from src.converters.survey import _normalize_template_version_overrides, _resolve_effective_template_version_overrides

    effective = _resolve_effective_template_version_overrides(
        project_path=project_path, template_version_overrides=template_version_overrides
    )
    return _normalize_template_version_overrides(effective) or effective


def list_non_system_survey_templates(directory: Path) -> list[Path]:
    candidates = sorted(directory.glob("survey-*.json"))
    allowed = set(filter_system_files([path.name for path in candidates]))
    return [path for path in candidates if path.name in allowed]


def resolve_official_survey_dir(project_path: str | None, app_root: Path) -> Path | None:
    candidates: list[Path] = []
    if project_path:
        project_root = Path(project_path).expanduser().resolve()
        if project_root.is_file():
            project_root = project_root.parent
        official = project_root / "official" / "library"
        candidates.extend([official / "survey", official])
    candidates.append(Path(app_root) / "official" / "library" / "survey")
    candidates.append(Path(app_root) / "official" / "library")
    for candidate in candidates:
        if candidate.is_dir() and list_non_system_survey_templates(candidate):
            return candidate
    return None


def collect_multivariant_tasks_from_library(
    *,
    library_dir: str | Path,
    tasks: list[str] | None = None,
    selected_versions: list[dict[str, object]] | dict[str, str] | None = None,
) -> dict[str, dict]:
    """Return multi-version task metadata for templates in a survey library."""
    survey_dir = Path(library_dir).expanduser().resolve()
    if (survey_dir / "survey").is_dir() and not list(survey_dir.glob("survey-*.json")):
        survey_dir = survey_dir / "survey"
    if not survey_dir.is_dir():
        return {}

    selected_tasks = {str(task).strip().lower() for task in (tasks or []) if str(task).strip()}
    requested_versions: dict[str, str] = {}
    if isinstance(selected_versions, dict):
        requested_versions = {
            str(task).strip().lower(): coerce_template_version_value(version)
            for task, version in selected_versions.items()
            if str(task).strip() and coerce_template_version_value(version)
        }
    elif isinstance(selected_versions, list):
        for entry in selected_versions:
            if not isinstance(entry, dict):
                continue
            task = str(entry.get("task") or "").strip().lower()
            version = coerce_template_version_value(entry.get("version"))
            if not task or not version or entry.get("run") not in {None, ""}:
                continue
            requested_versions[task] = version

    result: dict[str, dict] = {}
    for json_file in sorted(survey_dir.glob("survey-*.json")):
        try:
            payload = json.loads(json_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        study = payload.get("Study", {})
        if not isinstance(study, dict):
            continue
        task_name = str(study.get("TaskName") or json_file.stem.replace("survey-", "")).strip().lower()
        if not task_name or (selected_tasks and task_name not in selected_tasks):
            continue
        versions_raw = study.get("Versions")
        versions = [str(v).strip() for v in versions_raw if str(v).strip()] if isinstance(versions_raw, list) else []
        if len(versions) <= 1:
            continue
        default_version = coerce_template_version_value(study.get("Version")) or versions[0]
        result[task_name] = {
            "versions": versions,
            "default_version": default_version,
            "selected_version": requested_versions.get(task_name, default_version),
            "variant_definitions": study.get("VariantDefinitions", []),
        }
    return result


def collect_project_template_warnings_for_tasks(*, tasks: list[str], project_path: str | None) -> list[dict[str, str]]:
    """Non-blocking quality warnings for the project's templates of the given tasks."""
    if not project_path or not tasks:
        return []
    project_root = Path(project_path).expanduser().resolve()
    if project_root.is_file():
        project_root = project_root.parent
    template_dir = project_root / "code" / "library" / "survey"
    if not template_dir.exists():
        return []

    non_item_keys = {"Technical", "Task", "Study", "Metadata", "Scoring", "Normative", "I18n", "_aliases", "_reverse_aliases"}
    warnings: list[dict[str, str]] = []
    for task in sorted(set(tasks)):
        template_path = template_dir / f"survey-{task}.json"
        if not template_path.exists():
            continue
        try:
            payload = json.loads(template_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        task_norm = str(payload.get("Study", {}).get("TaskName") or task).strip().lower() or task.lower()
        for item_key, item_def in payload.items():
            if item_key in non_item_keys or not isinstance(item_def, dict):
                continue
            if isinstance(item_def.get("Levels"), dict) and ("MinValue" in item_def or "MaxValue" in item_def):
                warnings.append({
                    "file": str(template_path),
                    "message": (
                        f"Template '{task_norm}' item '{item_key}' defines both Levels and Min/Max; numeric range "
                        "takes precedence and Levels will be treated as labels only."
                    ),
                })
    return warnings


def build_template_completion_gate(*, tasks: list[str], issues: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "blocked": True,
        "reason": "project_template_completion_required",
        "title": "Template Completion Required",
        "message": (
            "Official templates were copied to your project library. "
            "Some required project-level fields still need to be completed in these templates before importing survey data."
        ),
        "tasks": sorted({task for task in tasks if task}),
        "issue_count": len(issues),
        "next_steps": [
            "Open Template Editor for the copied survey templates in code/library/survey.",
            "Fill project-specific administration fields in Technical (for example AdministrationMethod, SoftwarePlatform, SoftwareVersion) and any remaining required metadata.",
            "Run Preview again. Import is unlocked automatically after template validation passes.",
        ],
    }


def copy_official_templates_to_project(
    official_dir: Path,
    tasks: list[str],
    project_path: str | None,
    technical_defaults: dict[str, str] | None = None,
    selected_versions: dict[str, str] | None = None,
    log_fn=None,
) -> dict[str, list[str]]:
    if (official_dir / "survey").is_dir() and not list_non_system_survey_templates(official_dir):
        official_dir = official_dir / "survey"
    summary = copy_templates_to_project(
        tasks,
        lambda task: official_dir / f"survey-{task}.json",
        project_path,
        technical_defaults=technical_defaults,
        selected_versions=selected_versions,
        log_fn=log_fn,
    )
    summary["missing_official_tasks"] = summary.pop("missing_tasks")  # the page reads this name
    return summary


def infer_tasks_against_official_templates(
    *,
    input_path: Path,
    project_path: str | None,
    id_column: str | None,
    session_column: str | None,
    sheet: str | int,
    duplicate_handling: str,
    separator_option: str,
    app_root: Path,
) -> dict[str, Any]:
    """Which official templates the table matches; they are copied into the project when it lacks them."""
    input_path = Path(input_path)
    suffix = input_path.suffix.lower()
    official_dir = resolve_official_survey_dir(project_path, app_root)
    if not official_dir:
        return {
            "tasks": [], "copied_tasks": [], "existing_tasks": [], "missing_official_tasks": [],
            "official_template_count": 0, "match_error": "Official survey library could not be resolved.",
        }
    survey_official_dir = official_dir
    if (official_dir / "survey").is_dir() and not list_non_system_survey_templates(official_dir):
        survey_official_dir = official_dir / "survey"
    official_templates = list_non_system_survey_templates(survey_official_dir)
    if not official_templates:
        return {
            "tasks": [], "copied_tasks": [], "existing_tasks": [], "missing_official_tasks": [],
            "official_template_count": 0, "match_error": f"No official survey templates found in: {survey_official_dir}",
        }

    convert_file, convert_lsa = _converters()
    tmp_dir = tempfile.mkdtemp(prefix="prism_survey_template_check_")
    try:
        common = dict(
            input_path=input_path, library_dir=str(survey_official_dir), output_root=Path(tmp_dir) / "preflight_rawdata",
            survey=None, id_column=id_column, session_column=session_column, session=None, unknown="ignore",
            dry_run=True, force=True, name="template_check", authors=[], language=None, alias_file=None,
            id_map_file=None, duplicate_handling=duplicate_handling, skip_participants=True,
            fallback_project_path=project_path, app_root=app_root,
        )
        if suffix in SUPPORTED_SURVEY_TABULAR_SUFFIXES:
            result = run_survey_with_template_sources(
                convert_file, sheet=sheet, separator=expected_delimiter_for_suffix(suffix, separator_option), **common
            )
        elif suffix == ".lsa":
            result = run_survey_with_template_sources(
                convert_lsa, strict_levels=None, project_path=project_path, **common
            )
        else:
            raise ValueError(SUPPORTED_SURVEY_INPUT_MESSAGE)

        tasks = sorted(set(getattr(result, "tasks_included", []) or []))
        copy_summary = copy_official_templates_to_project(
            official_dir=survey_official_dir,
            tasks=tasks,
            project_path=project_path,
            technical_defaults=infer_technical_defaults(input_path.name),
            log_fn=None,
        )
        return {
            "tasks": tasks,
            "copied_tasks": copy_summary.get("copied_tasks", []),
            "existing_tasks": copy_summary.get("existing_tasks", []),
            "missing_official_tasks": copy_summary.get("missing_official_tasks", []),
            "official_template_count": len(official_templates),
            "detected_sessions": list(getattr(result, "detected_sessions", []) or []),
            "task_runs": getattr(result, "task_runs", {}) or {},
            "session_column": getattr(result, "session_column", None),
            "run_column": getattr(result, "run_column", None),
            "match_error": None,
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


EMPTY_MATCHING = {
    "input_file": None, "official_template_count": 0, "matched_tasks": [], "copied_tasks": [], "existing_tasks": [],
    "missing_official_tasks": [], "detected_sessions": [], "task_runs": {}, "session_column": None, "run_column": None,
    "match_error": None,
}


def matching_summary(input_name: str | None, inferred: dict[str, Any] | None) -> dict[str, Any]:
    """The "matching" block of the template check, from the inference (or empty when no table was given)."""
    summary = dict(EMPTY_MATCHING, input_file=input_name)
    if inferred is not None:
        summary.update(
            official_template_count=inferred.get("official_template_count", 0),
            matched_tasks=inferred.get("tasks", []),
            copied_tasks=inferred.get("copied_tasks", []),
            existing_tasks=inferred.get("existing_tasks", []),
            missing_official_tasks=inferred.get("missing_official_tasks", []),
            detected_sessions=inferred.get("detected_sessions", []),
            task_runs=inferred.get("task_runs", {}),
            session_column=inferred.get("session_column"),
            run_column=inferred.get("run_column"),
            match_error=inferred.get("match_error"),
        )
    return summary


def project_warnings(*, tasks: list[str], project_path: str | None) -> list[dict[str, str]]:
    """Everything worth a warning in the project's templates: range-vs-levels clashes, then language and item rules."""
    return collect_project_template_warnings_for_tasks(tasks=tasks, project_path=project_path) + project_template_warnings(
        tasks=tasks, project_path=project_path
    )


def check_project_templates(
    project_root: Path,
    matching: dict[str, Any],
    *,
    schema_version: str = "stable",
    validate: Callable[..., list] = validate_project_templates_for_tasks,
    warn: Callable[..., list] = project_warnings,
) -> dict[str, Any]:
    """Are the project's survey templates complete enough to convert with? (the answer of Studio's template check)"""
    template_dir = project_root / "code" / "library" / "survey"
    template_files = list_non_system_survey_templates(template_dir) if template_dir.is_dir() else []
    local_templates = sorted(
        p.stem[len("survey-"):] for p in template_files if p.stem.startswith("survey-") and len(p.stem) > len("survey-")
    )
    tasks = matching["matched_tasks"] or list(local_templates)
    shared = {
        "template_dir": str(template_dir),
        "template_count": len(template_files),
        "local_templates": local_templates,
        "matching": matching,
        "detected_sessions": matching["detected_sessions"],
        "task_runs": matching["task_runs"],
        "session_column": matching["session_column"],
        "run_column": matching["run_column"],
    }
    if not template_files:
        return {
            "ok": True, "message": "No local survey templates found in project code/library/survey.",
            **shared, "tasks": [], "issues": [], "warnings": [], "multivariant_tasks": {},
        }

    issues = validate(tasks=tasks, project_path=str(project_root), schema_version=schema_version)
    warnings = warn(tasks=local_templates, project_path=str(project_root))
    shared.update(
        tasks=tasks, issues=issues, warnings=warnings,
        multivariant_tasks=collect_multivariant_tasks_from_library(
            library_dir=template_dir, tasks=tasks, selected_versions=effective_template_version_overrides(project_root, None)
        ),
    )
    if issues:
        gate = build_template_completion_gate(tasks=tasks, issues=issues)
        return {"ok": False, "message": gate["message"], **shared, "workflow_gate": gate}
    return {"ok": True, "message": "Project survey templates passed required-field validation.", **shared}


def detect_version_contexts(
    *,
    input_path: Path,
    library_dir: str | Path | None,
    project_path: str | None,
    app_root: Path,
    survey: str | None = None,
    id_column: str | None = None,
    session_column: str | None = None,
    run_column: str | None = None,
    session_override: str | None = None,
    sheet: str | int = 0,
    duplicate_handling: str = "error",
    separator_option: str = "auto",
    template_version_overrides=None,
    allow_near_item_match: bool = False,
    near_match_tasks: set[str] | None = None,
    task_value_offsets: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Which tasks, sessions, runs and template versions a table holds (a dry run; nothing is written)."""
    input_path = Path(input_path)
    suffix = input_path.suffix.lower()
    template_version_overrides = effective_template_version_overrides(project_path, template_version_overrides)
    if library_dir is None:
        try:
            library_dir = resolve_survey_library(project_path, app_root)
        except FileNotFoundError:
            library_dir = resolve_official_survey_dir(project_path, app_root)
            if not library_dir:
                raise FileNotFoundError("No survey template library could be resolved.") from None
    base_library_dir = Path(library_dir)
    if (base_library_dir / "survey").is_dir() and not list(base_library_dir.glob("survey-*.json")):
        base_library_dir = base_library_dir / "survey"

    convert_file, convert_lsa = _converters()
    effective = (  # kept alive below: used_library_dir is inside it
        build_effective_library(project_path, app_root)
        if is_standard_library(base_library_dir, project_path, app_root)
        else None
    )
    used_library_dir = effective.directory if effective and effective.origins else base_library_dir
    tmp_dir = tempfile.mkdtemp(prefix="prism_survey_version_context_")
    try:
        common = dict(
            input_path=input_path, library_dir=str(used_library_dir), output_root=Path(tmp_dir) / "context_rawdata",
            survey=survey, id_column=id_column, session_column=session_column, run_column=run_column,
            session=session_override, unknown="ignore", dry_run=True, force=True, name="version_context", authors=[],
            language=None, alias_file=None, id_map_file=None, duplicate_handling=duplicate_handling,
            skip_participants=True, project_path=project_path, template_version_overrides=template_version_overrides,
            allow_near_item_match=allow_near_item_match, near_match_tasks=near_match_tasks,
            task_value_offsets=task_value_offsets,
        )
        try:
            if suffix in SUPPORTED_SURVEY_TABULAR_SUFFIXES:
                result = convert_file(sheet=sheet, separator=expected_delimiter_for_suffix(suffix, separator_option), **common)
            elif suffix == ".lsa":
                result = convert_lsa(strict_levels=None, **common)
            else:
                raise ValueError(SUPPORTED_SURVEY_INPUT_MESSAGE)
        except TemplateIncomplete:
            # Only looking, nothing is converted: the refusal (naming the project copies to fill in) comes at
            # preview and convert. Until then there is nothing to detect.
            return {
                "tasks_included": [], "detected_sessions": [], "task_runs": {}, "preview_participants": [],
                "session_column": None, "run_column": None, "multivariant_tasks": {},
            }
        tasks_included = list(getattr(result, "tasks_included", []) or [])
        dry_run_preview = getattr(result, "dry_run_preview", None)
        return {
            "tasks_included": tasks_included,
            "detected_sessions": list(getattr(result, "detected_sessions", []) or []),
            "task_runs": getattr(result, "task_runs", {}) or {},
            "preview_participants": list(dry_run_preview.get("participants") or []) if isinstance(dry_run_preview, dict) else [],
            "session_column": getattr(result, "session_column", None),
            "run_column": getattr(result, "run_column", None),
            "multivariant_tasks": collect_multivariant_tasks_from_library(
                library_dir=used_library_dir, tasks=tasks_included, selected_versions=template_version_overrides
            ),
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
