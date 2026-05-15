from copy import deepcopy
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from flask import current_app, has_app_context
from src.system_files import filter_system_files

from .conversion_utils import expected_delimiter_for_suffix, resolve_existing_project_root


def _list_non_system_survey_templates(directory: Path) -> list[Path]:
    candidates = sorted(directory.glob("survey-*.json"))
    allowed_names = set(filter_system_files([path.name for path in candidates]))
    return [path for path in candidates if path.name in allowed_names]


def resolve_official_survey_dir(project_path: str | None) -> Path | None:
    candidates: list[Path] = []

    if project_path:
        project_root = Path(project_path).expanduser().resolve()
        if project_root.is_file():
            project_root = project_root.parent

        project_official = project_root / "official" / "library"
        candidates.extend([project_official / "survey", project_official])

    if has_app_context():
        base_dir = Path(current_app.root_path).parent.resolve()
    else:
        base_dir = Path(__file__).resolve().parents[4]
    candidates.append(base_dir / "official" / "library" / "survey")
    candidates.append(base_dir / "official" / "library")

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            if _list_non_system_survey_templates(candidate):
                return candidate
    return None


def infer_project_template_technical_defaults(
    *, input_path: str | Path | None = None
) -> dict[str, str]:
    """Infer project-local administration defaults when the source format is unambiguous."""
    if not input_path:
        return {}

    suffix = Path(input_path).suffix.lower()
    if suffix in {".lsa", ".lss"}:
        return {
            "SoftwarePlatform": "LimeSurvey",
            "AdministrationMethod": "online",
        }

    return {}


def prepare_project_survey_template_from_official(
    payload: Any,
    *,
    task: str,
    technical_defaults: dict[str, str] | None = None,
    selected_version: str | None = None,
) -> Any:
    """Convert an official instrument template into a project-local administration template."""
    if not isinstance(payload, dict):
        return payload

    out = deepcopy(payload)

    technical = out.get("Technical")
    if not isinstance(technical, dict):
        technical = {}
        out["Technical"] = technical

    technical.setdefault("StimulusType", "Questionnaire")
    technical.setdefault("FileFormat", "tsv")
    technical.setdefault("Language", "")
    technical.setdefault("Respondent", "")
    technical.setdefault("AdministrationMethod", "")
    technical.setdefault("SoftwarePlatform", "")
    technical.setdefault("SoftwareVersion", "")

    for key, value in (technical_defaults or {}).items():
        if not value:
            continue
        existing = technical.get(key)
        if isinstance(existing, str) and existing.strip():
            continue
        technical[key] = value

    study = out.get("Study")
    if not isinstance(study, dict):
        study = {}
        out["Study"] = study

    study.setdefault("TaskName", task)
    study.setdefault("LicenseID", "unknown")
    if isinstance(selected_version, str) and selected_version.strip():
        study["Version"] = selected_version.strip()

    return out


def copy_official_templates_to_project(
    official_dir: Path,
    tasks: list[str],
    project_path: str | None,
    technical_defaults: dict[str, str] | None = None,
    selected_versions: dict[str, str] | None = None,
    log_fn=None,
) -> dict[str, list[str]]:
    summary: dict[str, Any] = {
        "copied_tasks": [],
        "existing_tasks": [],
        "missing_official_tasks": [],
    }
    if not project_path or not tasks:
        return summary
    project_root = resolve_existing_project_root(project_path)
    if project_root is None:
        return summary

    if (official_dir / "survey").is_dir() and not _list_non_system_survey_templates(
        official_dir
    ):
        official_dir = official_dir / "survey"

    dest_dir = project_root / "code" / "library" / "survey"
    dest_dir.mkdir(parents=True, exist_ok=True)

    for task in tasks:
        src = official_dir / f"survey-{task}.json"
        dest = dest_dir / f"survey-{task}.json"
        if not src.exists():
            summary["missing_official_tasks"].append(task)
            continue

        if dest.exists():
            summary["existing_tasks"].append(task)
            continue

        try:
            with open(src, "r", encoding="utf-8") as file_handle:
                payload = json.load(file_handle)

            if isinstance(payload, dict):
                payload = prepare_project_survey_template_from_official(
                    payload,
                    task=task,
                    technical_defaults=technical_defaults,
                    selected_version=(selected_versions or {}).get(task),
                )

                with open(dest, "w", encoding="utf-8") as file_handle:
                    json.dump(payload, file_handle, indent=2, ensure_ascii=False)
            else:
                shutil.copy2(src, dest)
        except Exception:
            shutil.copy2(src, dest)

        summary["copied_tasks"].append(task)

    copied = len(summary["copied_tasks"])
    if copied:
        message = f"Copied {copied} official survey template(s) into project library."
        if log_fn:
            log_fn(message, "info")
        else:
            print(f"[PRISM DEBUG] {message}")

    return summary


def infer_tasks_against_official_templates(
    *,
    uploaded_file,
    filename: str,
    project_path: str | None,
    id_column: str | None,
    session_column: str | None,
    sheet: str | int,
    duplicate_handling: str,
    separator_option: str,
    supported_survey_tabular_suffixes: set[str] | tuple[str, ...],
    supported_survey_input_message: str,
    convert_survey_xlsx_to_prism_dataset,
    convert_survey_lsa_to_prism_dataset,
    run_survey_with_official_fallback,
) -> dict[str, Any]:
    suffix = Path(filename).suffix.lower()
    official_dir = resolve_official_survey_dir(project_path)
    if not official_dir:
        return {
            "tasks": [],
            "copied_tasks": [],
            "existing_tasks": [],
            "missing_official_tasks": [],
            "official_template_count": 0,
            "match_error": "Official survey library could not be resolved.",
        }

    survey_official_dir = official_dir
    if (official_dir / "survey").is_dir() and not _list_non_system_survey_templates(
        official_dir
    ):
        survey_official_dir = official_dir / "survey"

    official_templates = _list_non_system_survey_templates(survey_official_dir)
    if not official_templates:
        return {
            "tasks": [],
            "copied_tasks": [],
            "existing_tasks": [],
            "missing_official_tasks": [],
            "official_template_count": 0,
            "match_error": f"No official survey templates found in: {survey_official_dir}",
        }

    tmp_dir = tempfile.mkdtemp(prefix="prism_survey_template_check_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        preflight_output_root = tmp_dir_path / "preflight_rawdata"
        if suffix in supported_survey_tabular_suffixes:
            result = run_survey_with_official_fallback(
                convert_survey_xlsx_to_prism_dataset,
                input_path=input_path,
                library_dir=str(survey_official_dir),
                output_root=preflight_output_root,
                survey=None,
                id_column=id_column,
                session_column=session_column,
                session=None,
                sheet=sheet,
                unknown="ignore",
                dry_run=True,
                force=True,
                name="template_check",
                authors=[],
                language=None,
                alias_file=None,
                id_map_file=None,
                separator=expected_delimiter_for_suffix(suffix, separator_option),
                duplicate_handling=duplicate_handling,
                skip_participants=True,
                fallback_project_path=project_path,
            )
        elif suffix == ".lsa":
            result = run_survey_with_official_fallback(
                convert_survey_lsa_to_prism_dataset,
                input_path=input_path,
                library_dir=str(survey_official_dir),
                output_root=preflight_output_root,
                survey=None,
                id_column=id_column,
                session_column=session_column,
                session=None,
                unknown="ignore",
                dry_run=True,
                force=True,
                name="template_check",
                authors=[],
                language=None,
                alias_file=None,
                id_map_file=None,
                strict_levels=None,
                duplicate_handling=duplicate_handling,
                skip_participants=True,
                project_path=project_path,
                fallback_project_path=project_path,
            )
        else:
            raise ValueError(supported_survey_input_message)

        tasks = sorted(set(getattr(result, "tasks_included", []) or []))
        copy_summary = copy_official_templates_to_project(
            official_dir=survey_official_dir,
            tasks=tasks,
            project_path=project_path,
            technical_defaults=infer_project_template_technical_defaults(
                input_path=filename,
            ),
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