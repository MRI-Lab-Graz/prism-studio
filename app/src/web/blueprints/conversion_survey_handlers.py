"""Survey conversion handlers extracted from the conversion blueprint."""

from copy import deepcopy
import inspect
import io
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from jsonschema import Draft7Validator

from flask import current_app, has_app_context, jsonify, request, send_file, session
from werkzeug.utils import secure_filename
from src.participants_paths import participants_mapping_candidates
from src.survey_workflow_service import (
    SUPPORTED_SURVEY_INPUT_MESSAGE,
    SUPPORTED_SURVEY_INPUT_SUFFIXES,
    SUPPORTED_SURVEY_TABULAR_SUFFIXES,
    SurveyWorkflowStageOptions,
    SurveyWorkflowStageService,
)

try:
    import defusedxml.ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

from src.web.reporting_utils import sanitize_jsonable
from src.web.validation import run_validation
from src.web.services.project_registration import register_session_in_project
from .conversion_survey_preview_handlers import (
    handle_api_survey_convert_preview,
    handle_api_survey_languages,
)

from .conversion_utils import (
    collect_multivariant_tasks_from_library,
    expected_delimiter_for_suffix,
    extract_tasks_from_output,
    log_file_head,
    merge_selected_survey_filter,
    normalize_separator_option,
    normalize_filename,
    parse_near_item_match_task_allowlist,
    parse_selected_survey_tasks,
    parse_task_value_offsets,
    parse_template_version_overrides,
    participant_json_candidates,
    require_existing_project_root,
    resolve_effective_library_path,
    resolve_existing_project_root,
    resolve_validation_library_path,
    should_retry_with_official_library,
    summarize_project_output_paths,
)

convert_survey_xlsx_to_prism_dataset: Any = None
convert_survey_lsa_to_prism_dataset: Any = None
infer_lsa_metadata: Any = None
MissingIdMappingError: Any = None
UnmatchedGroupsError: Any = None
SurveyValueOutOfBoundsError: Any = None
_resolve_effective_template_version_overrides: Any = None
_normalize_template_version_overrides_for_requests: Any = None
sync_project_survey_recipe_offsets: Any = None
_NON_ITEM_TOPLEVEL_KEYS: set[str] = set()
normalize_paper_software_platform: Any = None
_SUPPORTED_SURVEY_INPUT_MESSAGE = SUPPORTED_SURVEY_INPUT_MESSAGE
_SUPPORTED_SURVEY_INPUT_SUFFIXES = SUPPORTED_SURVEY_INPUT_SUFFIXES
_SUPPORTED_SURVEY_TABULAR_SUFFIXES = SUPPORTED_SURVEY_TABULAR_SUFFIXES
_survey_workflow_stage_service = SurveyWorkflowStageService(
    tabular_suffixes=_SUPPORTED_SURVEY_TABULAR_SUFFIXES,
)

try:
    from src.converters.survey import (
        MissingIdMappingError,
        UnmatchedGroupsError,
        _NON_ITEM_TOPLEVEL_KEYS,
        convert_survey_lsa_to_prism_dataset,
        convert_survey_xlsx_to_prism_dataset,
        infer_lsa_metadata,
    )
except ImportError:
    pass

try:
    from src.converters.survey import (
        SurveyValueOutOfBoundsError as _SurveyValueOutOfBoundsErrorFromSurvey,
    )

    SurveyValueOutOfBoundsError = _SurveyValueOutOfBoundsErrorFromSurvey
except ImportError:
    try:
        from src.converters.survey_processing import (
            SurveyValueOutOfBoundsError as _SurveyValueOutOfBoundsErrorFromProcessing,
        )

        SurveyValueOutOfBoundsError = _SurveyValueOutOfBoundsErrorFromProcessing
    except ImportError:
        pass

try:
    from src.converters.survey import (
        sync_project_survey_recipe_offsets as _sync_project_survey_recipe_offsets,
    )

    sync_project_survey_recipe_offsets = _sync_project_survey_recipe_offsets
except ImportError:
    pass

try:
    from src.converters.survey import (
        _normalize_template_version_overrides as _survey_normalize_template_version_overrides,
        _resolve_effective_template_version_overrides as _survey_resolve_effective_template_version_overrides,
    )

    _normalize_template_version_overrides_for_requests = (
        _survey_normalize_template_version_overrides
    )
    _resolve_effective_template_version_overrides = (
        _survey_resolve_effective_template_version_overrides
    )
except ImportError:
    pass

try:
    from src.converters.survey_io import (
        normalize_paper_software_platform as _normalize_paper_software_platform,
    )

    normalize_paper_software_platform = _normalize_paper_software_platform
except ImportError:
    pass

IdColumnNotDetectedError: Any = None
try:
    from src.converters.id_detection import IdColumnNotDetectedError as _IdColumnError

    IdColumnNotDetectedError = _IdColumnError
except ImportError:
    pass

_participant_json_candidates = participant_json_candidates
_log_file_head = log_file_head
_resolve_effective_library_path = resolve_effective_library_path
_resolve_validation_library_path = resolve_validation_library_path
_normalize_filename = normalize_filename
_should_retry_with_official_library = should_retry_with_official_library
_extract_tasks_from_output = extract_tasks_from_output
_register_session_in_project = register_session_in_project


def _get_effective_template_version_overrides(
    *,
    project_path: str | Path | None,
    template_version_overrides: object,
):
    if _resolve_effective_template_version_overrides is None:
        effective_overrides = template_version_overrides
    else:
        effective_overrides = _resolve_effective_template_version_overrides(
            project_path=project_path,
            template_version_overrides=template_version_overrides,
        )

    if callable(_normalize_template_version_overrides_for_requests):
        normalized_overrides = _normalize_template_version_overrides_for_requests(
            effective_overrides
        )
        if normalized_overrides:
            return normalized_overrides
    return effective_overrides


def _is_prepared_workflow_request() -> bool:
    return _survey_workflow_stage_service.parse_prepared_workflow_flag(
        request.form.get("prepared_workflow")
    )


def _format_workflow_preparation_stale_response(
    payload: dict[str, object],
    *,
    log_messages: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return _survey_workflow_stage_service.format_workflow_preparation_stale_response(
        payload=payload,
        prepared_workflow=_is_prepared_workflow_request(),
        log_messages=log_messages,
    )


def _requested_project_path() -> str | None:
    raw_value = (
        request.form.get("project_path")
        or request.args.get("project_path")
        or ""
    )
    normalized = str(raw_value).strip()
    return normalized or None


def _resolve_requested_project_root(*, require_project: bool) -> Path | None:
    missing_message = "No project selected. Load a project before converting survey data."
    missing_path_message = (
        "The selected project path no longer exists. Reopen the project and retry survey conversion."
    )

    requested_project_path = _requested_project_path()
    if requested_project_path:
        return require_existing_project_root(
            requested_project_path,
            missing_message=missing_message,
            missing_path_message=missing_path_message,
        )

    session_project_path = session.get("current_project_path")
    if require_project:
        return require_existing_project_root(
            session_project_path,
            missing_message=missing_message,
            missing_path_message=missing_path_message,
        )

    return resolve_existing_project_root(session_project_path)


def _iter_session_registration_values(
    *,
    session_override: str | None,
    detected_sessions: list[str] | None,
) -> list[str]:
    normalized_override = str(session_override or "").strip()
    if not normalized_override:
        return []
    if normalized_override.lower() != "all":
        return [normalized_override]

    values: list[str] = []
    seen: set[str] = set()
    for raw_value in detected_sessions or []:
        candidate = str(raw_value or "").strip()
        if not candidate or candidate.lower() == "all" or candidate in seen:
            continue
        seen.add(candidate)
        values.append(candidate)
    return values


def _cleanup_stale_tool_limesurvey_sidecars(
    *,
    copied_output_paths: list[Path],
    source_suffix: str,
    log_fn=None,
) -> list[Path]:
    """Remove stale tool-limesurvey sidecars for non-LimeSurvey imports.

    When converting non-LSA/LSS sources, older buggy runs may have left
    `*_tool-limesurvey_survey.{tsv,json}` files in project survey folders.
    If the current run does not emit such files, clean stale leftovers in the
    survey directories touched by this save operation.
    """

    normalized_suffix = str(source_suffix or "").strip().lower()
    if normalized_suffix in {".lsa", ".lss"}:
        return []

    if any("_tool-limesurvey_survey" in path.name for path in copied_output_paths):
        return []

    touched_survey_dirs = {
        path.parent for path in copied_output_paths if path.parent.name == "survey"
    }
    removed_paths: list[Path] = []

    for survey_dir in sorted(touched_survey_dirs):
        for pattern in (
            "*_tool-limesurvey_survey.tsv",
            "*_tool-limesurvey_survey.json",
        ):
            for stale_path in survey_dir.glob(pattern):
                if not stale_path.is_file():
                    continue
                try:
                    stale_path.unlink()
                    removed_paths.append(stale_path)
                except OSError:
                    continue

    if removed_paths and callable(log_fn):
        log_fn(
            "Removed "
            f"{len(removed_paths)} stale tool-limesurvey sidecar file(s) "
            "for non-LimeSurvey import.",
            "info",
        )

    return removed_paths


def _format_value_offset_confirmation_response(
    error: Exception,
    log_messages: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    task = str(getattr(error, "task", "") or "").strip().lower()
    item_id = str(getattr(error, "item_id", "") or "").strip()
    raw_value = getattr(error, "raw_value", None)
    subject_id = str(getattr(error, "sub_id", "") or "").strip()
    expected_levels = list(getattr(error, "expected_levels", []) or [])

    suggested_offsets: list[float | int] = []
    for raw_offset in list(getattr(error, "suggested_offsets", []) or []):
        try:
            numeric = float(raw_offset)
        except (TypeError, ValueError):
            continue
        rounded = round(numeric)
        if abs(numeric - rounded) < 1e-9:
            suggested_offsets.append(int(rounded))
        else:
            suggested_offsets.append(round(numeric, 6))

    configured_offset = getattr(error, "configured_offset", None)
    adjusted_value = getattr(error, "adjusted_value", None)
    raw_value_valid_without_offset = getattr(
        error, "raw_value_valid_without_offset", None
    )
    offset_evidence = getattr(error, "offset_evidence", None)
    evidence_classification = ""
    if isinstance(offset_evidence, dict):
        evidence_classification = str(
            offset_evidence.get("classification") or ""
        ).strip().lower()

    fallback_message = (
        "Survey values are outside template levels. Review and fix out-of-range source values before continuing."
    )
    review_message = str(error).strip() or fallback_message
    if configured_offset is None and evidence_classification in {
        "item_issues_likely",
        "structural_offset_likely",
    }:
        if evidence_classification == "structural_offset_likely":
            review_message = (
                "Sampled out-of-range values may reflect a task-wide shifted scale, but this is not proof."
            )
        else:
            review_message = (
                "Sampled out-of-range values do not support treating this as a task-wide scale shift."
            )
    if configured_offset is not None:
        review_message += (
            " Review the manual task value offset in Advanced options only if you are certain the entire task uses a shifted scale, then run Preview again."
        )
        if raw_value_valid_without_offset is True:
            review_message += (
                " This sampled value is already valid without offset; verify offset direction and template version selection."
            )
    else:
        review_message += (
            " Required first: validate and correct out-of-range source values, then run Preview again."
            " Advanced-only fallback: use a manual task value offset only with independent evidence of a full-task scale shift (for example, every item is 1-4 while the template is 0-3)."
            " Do not use offsets to bypass item-level data errors."
        )
    payload: dict[str, Any] = {
        "error": "value_offset_manual_review_required",
        "message": review_message,
        "task": task,
        "item_id": item_id,
        "raw_value": raw_value,
        "expected_levels": expected_levels,
        "suggested_offsets": suggested_offsets,
    }
    if subject_id:
        payload["subject_id"] = subject_id
    if configured_offset is not None:
        payload["configured_offset"] = configured_offset
    if adjusted_value is not None:
        payload["adjusted_value"] = adjusted_value
    if isinstance(raw_value_valid_without_offset, bool):
        payload["raw_value_valid_without_offset"] = raw_value_valid_without_offset
    if isinstance(offset_evidence, dict):
        payload["offset_evidence"] = offset_evidence
    payload["manual_action"] = "advanced_value_offsets"
    if log_messages is not None:
        payload["log"] = log_messages
    return payload


def _is_value_offset_confirmation_error(error: Exception) -> bool:
    return (
        isinstance(SurveyValueOutOfBoundsError, type)
        and issubclass(SurveyValueOutOfBoundsError, BaseException)
        and isinstance(error, SurveyValueOutOfBoundsError)
    )


class _LocalPathUpload:
    """Minimal upload-like wrapper backed by a local filesystem path."""

    def __init__(self, source_path: Path):
        self._source_path = source_path
        self.filename = source_path.name

    def save(self, destination: str):
        shutil.copy2(self._source_path, destination)


def _resolve_uploaded_or_source_file(*, field_names: tuple[str, ...]):
    for field_name in field_names:
        upload = request.files.get(field_name)
        if upload is not None and upload.filename:
            return upload, None

    source_file_path = (
        (request.form.get("source_file_path") or "").strip()
        or (request.args.get("source_file_path") or "").strip()
    )
    if not source_file_path:
        return None, "Missing input file"

    source_path = Path(source_file_path).expanduser().resolve()
    if not source_path.exists() or not source_path.is_file():
        return None, f"File not found: {source_file_path}"

    return _LocalPathUpload(source_path), None


def _resolve_official_survey_dir(project_path: str | None) -> Path | None:
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
        # Test/runtime fallback when no Flask app context is active.
        base_dir = Path(__file__).resolve().parents[4]
    candidates.append(base_dir / "official" / "library" / "survey")
    candidates.append(base_dir / "official" / "library")

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            if list(candidate.glob("survey-*.json")):
                return candidate
    return None


def _infer_project_template_technical_defaults(
    *, input_path: str | Path | None = None
) -> dict[str, str]:
    """Infer project-local administration defaults when the source format makes them unambiguous."""
    if not input_path:
        return {}

    suffix = Path(input_path).suffix.lower()
    if suffix in {".lsa", ".lss"}:
        return {
            "SoftwarePlatform": "LimeSurvey",
            "AdministrationMethod": "online",
        }

    return {}


def _prepare_project_survey_template_from_official(
    payload: Any,
    *,
    task: str,
    technical_defaults: dict[str, str] | None = None,
    selected_version: str | None = None,
) -> Any:
    """Convert an official instrument template into a project-local administration template.

    Official templates keep canonical instrument metadata. Project copies must also carry
    administration-specific metadata describing how that instrument was actually run in the
    project. When the import source is unambiguous (for example LimeSurvey archives), seed the
    corresponding Technical fields automatically; otherwise leave placeholders for review.
    """
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


def _copy_official_templates_to_project(
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

    if (official_dir / "survey").is_dir() and not list(
        official_dir.glob("survey-*.json")
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
            with open(src, "r", encoding="utf-8") as f:
                payload = json.load(f)

            if isinstance(payload, dict):
                payload = _prepare_project_survey_template_from_official(
                    payload,
                    task=task,
                    technical_defaults=technical_defaults,
                    selected_version=(selected_versions or {}).get(task),
                )

                with open(dest, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False)
            else:
                shutil.copy2(src, dest)
        except Exception:
            shutil.copy2(src, dest)

        summary["copied_tasks"].append(task)

    copied = len(summary["copied_tasks"])
    if copied:
        msg = f"Copied {copied} official survey template(s) into project library."
        if log_fn:
            log_fn(msg, "info")
        else:
            print(f"[PRISM DEBUG] {msg}")

    return summary


def _infer_tasks_against_official_templates(
    *,
    uploaded_file,
    filename: str,
    project_path: str | None,
    id_column: str | None,
    session_column: str | None,
    sheet: str | int,
    duplicate_handling: str,
    separator_option: str,
) -> dict[str, Any]:
    suffix = Path(filename).suffix.lower()
    official_dir = _resolve_official_survey_dir(project_path)
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
    if (official_dir / "survey").is_dir() and not list(
        official_dir.glob("survey-*.json")
    ):
        survey_official_dir = official_dir / "survey"

    official_templates = sorted(survey_official_dir.glob("survey-*.json"))
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
        if suffix in _SUPPORTED_SURVEY_TABULAR_SUFFIXES:
            result = _run_survey_with_official_fallback(
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
            result = _run_survey_with_official_fallback(
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
            raise ValueError(_SUPPORTED_SURVEY_INPUT_MESSAGE)

        tasks = sorted(set(getattr(result, "tasks_included", []) or []))
        copy_summary = _copy_official_templates_to_project(
            official_dir=survey_official_dir,
            tasks=tasks,
            project_path=project_path,
            technical_defaults=_infer_project_template_technical_defaults(
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


def _detect_survey_version_contexts(
    *,
    uploaded_file,
    filename: str,
    library_dir: str | Path,
    project_path: str | None,
    survey: str | None,
    id_column: str | None,
    session_column: str | None,
    run_column: str | None,
    session_override: str | None,
    sheet: str | int,
    duplicate_handling: str,
    separator_option: str,
    template_version_overrides: dict[str, str] | list[dict[str, object]] | None,
    allow_near_item_match: bool = False,
    near_match_tasks: set[str] | None = None,
    task_value_offsets: dict[str, float] | None = None,
) -> dict[str, Any]:
    suffix = Path(filename).suffix.lower()
    official_dir = _resolve_official_survey_dir(project_path)

    base_library_dir = Path(library_dir)
    if (base_library_dir / "survey").is_dir() and not list(
        base_library_dir.glob("survey-*.json")
    ):
        base_library_dir = base_library_dir / "survey"

    tmp_dir = tempfile.mkdtemp(prefix="prism_survey_version_context_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))
        output_root = tmp_dir_path / "context_rawdata"
        separator = expected_delimiter_for_suffix(suffix, separator_option)

        def _run_detection(candidate_library_dir: Path):
            if suffix in _SUPPORTED_SURVEY_TABULAR_SUFFIXES:
                return convert_survey_xlsx_to_prism_dataset(
                    input_path=input_path,
                    library_dir=str(candidate_library_dir),
                    output_root=output_root,
                    survey=survey,
                    id_column=id_column,
                    session_column=session_column,
                    run_column=run_column,
                    session=session_override,
                    sheet=sheet,
                    unknown="ignore",
                    dry_run=True,
                    force=True,
                    name="version_context",
                    authors=[],
                    language=None,
                    alias_file=None,
                    id_map_file=None,
                    separator=separator,
                    duplicate_handling=duplicate_handling,
                    skip_participants=True,
                    project_path=project_path,
                    template_version_overrides=template_version_overrides,
                    allow_near_item_match=allow_near_item_match,
                    near_match_tasks=near_match_tasks,
                    task_value_offsets=task_value_offsets,
                )
            if suffix == ".lsa":
                return convert_survey_lsa_to_prism_dataset(
                    input_path=input_path,
                    library_dir=str(candidate_library_dir),
                    output_root=output_root,
                    survey=survey,
                    id_column=id_column,
                    session_column=session_column,
                    run_column=run_column,
                    session=session_override,
                    unknown="ignore",
                    dry_run=True,
                    force=True,
                    name="version_context",
                    authors=[],
                    language=None,
                    alias_file=None,
                    id_map_file=None,
                    strict_levels=None,
                    duplicate_handling=duplicate_handling,
                    skip_participants=True,
                    project_path=project_path,
                    template_version_overrides=template_version_overrides,
                    allow_near_item_match=allow_near_item_match,
                    near_match_tasks=near_match_tasks,
                    task_value_offsets=task_value_offsets,
                )
            raise ValueError(_SUPPORTED_SURVEY_INPUT_MESSAGE)

        try:
            used_library_dir = base_library_dir
            result = _run_detection(used_library_dir)
        except Exception as exc:
            if not _should_retry_with_official_library(exc):
                raise
            if not official_dir:
                raise
            used_library_dir = Path(official_dir)
            if (used_library_dir / "survey").is_dir() and not list(
                used_library_dir.glob("survey-*.json")
            ):
                used_library_dir = used_library_dir / "survey"
            if used_library_dir.resolve() == base_library_dir.resolve():
                raise
            result = _run_detection(used_library_dir)

        tasks_included = list(getattr(result, "tasks_included", []) or [])
        preview_participants = []
        dry_run_preview = getattr(result, "dry_run_preview", None)
        if isinstance(dry_run_preview, dict):
            preview_participants = list(dry_run_preview.get("participants") or [])
        return {
            "tasks_included": tasks_included,
            "detected_sessions": list(getattr(result, "detected_sessions", []) or []),
            "task_runs": getattr(result, "task_runs", {}) or {},
            "preview_participants": preview_participants,
            "session_column": getattr(result, "session_column", None),
            "run_column": getattr(result, "run_column", None),
            "multivariant_tasks": collect_multivariant_tasks_from_library(
                library_dir=used_library_dir,
                tasks=tasks_included,
                selected_versions=template_version_overrides,
            ),
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _coerce_flask_response(response_value):
    """Normalize a Flask view return value to a response object and status code."""

    response = response_value
    status_code = None
    if isinstance(response_value, tuple):
        response = response_value[0]
        if len(response_value) > 1:
            status_code = response_value[1]
    if status_code is None:
        status_code = getattr(response, "status_code", 200)
    return response, status_code


def _run_survey_with_official_fallback(
    converter_fn,
    *,
    library_dir: str | Path,
    fallback_project_path: str | None,
    log_fn=None,
    **kwargs,
):
    technical_defaults = _infer_project_template_technical_defaults(
        input_path=kwargs.get("input_path")
    )
    template_version_overrides = kwargs.get("template_version_overrides") or {}
    if fallback_project_path:
        kwargs.setdefault("project_path", fallback_project_path)

    converter_kwargs = dict(kwargs)
    try:
        signature = inspect.signature(converter_fn)
        accepts_var_kwargs = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        )
        if not accepts_var_kwargs:
            accepted_names = set(signature.parameters.keys())
            unsupported = sorted(
                key for key in converter_kwargs.keys() if key not in accepted_names
            )
            if unsupported:
                converter_name = str(getattr(converter_fn, "__name__", "converter"))
                msg = (
                    f"Converter '{converter_name}' does not accept options "
                    f"{', '.join(unsupported)}; skipping unsupported options."
                )
                if log_fn:
                    log_fn(msg, "warning")
                else:
                    print(f"[PRISM WARN] {msg}")
                converter_kwargs = {
                    key: value
                    for key, value in converter_kwargs.items()
                    if key in accepted_names
                }
    except (TypeError, ValueError):
        pass

    result = None
    try:
        result = converter_fn(library_dir=str(library_dir), **converter_kwargs)
        tasks_included = getattr(result, "tasks_included", []) or []
        _copy_official_templates_to_project(
            official_dir=Path(library_dir),
            tasks=list(tasks_included),
            project_path=fallback_project_path,
            technical_defaults=technical_defaults,
            selected_versions=template_version_overrides,
            log_fn=log_fn,
        )
        return result
    except Exception as exc:
        if _should_retry_with_official_library(exc):
            # Step 1: Try project's local code/library/survey first (project-specific templates).
            if fallback_project_path:
                project_root = Path(fallback_project_path).expanduser()
                if project_root.is_file():
                    project_root = project_root.parent
                project_local_dir = project_root / "code" / "library" / "survey"
                if (
                    project_local_dir.is_dir()
                    and list(project_local_dir.glob("survey-*.json"))
                    and project_local_dir.resolve() != Path(library_dir).resolve()
                ):
                    msg = "Template not found in current library; retrying with project local library."
                    if log_fn:
                        log_fn(msg, "info")
                    else:
                        print(f"[PRISM DEBUG] {msg}")
                    try:
                        result = converter_fn(
                            library_dir=str(project_local_dir), **converter_kwargs
                        )
                        return result
                    except Exception:
                        pass  # fall through to official library

            # Step 2: Try official library (standard templates, then copy to project).
            official_dir = _resolve_official_survey_dir(fallback_project_path)
            if (
                official_dir
                and Path(official_dir).resolve() != Path(library_dir).resolve()
            ):
                msg = (
                    "No matches in project templates; retrying with official templates."
                )
                if log_fn:
                    log_fn(msg, "info")
                else:
                    print(f"[PRISM DEBUG] {msg}")
                result = converter_fn(
                    library_dir=str(official_dir), **converter_kwargs
                )
                tasks_included = getattr(result, "tasks_included", []) or []
                _copy_official_templates_to_project(
                    official_dir=official_dir,
                    tasks=list(tasks_included),
                    project_path=fallback_project_path,
                    technical_defaults=technical_defaults,
                    selected_versions=template_version_overrides,
                    log_fn=log_fn,
                )
                return result

            msg = "No matches in project templates and no official templates found to fall back to."
            if log_fn:
                log_fn(msg, "warning")
            else:
                print(f"[PRISM DEBUG] {msg}")
        raise


def api_survey_prepare_workflow():
    """Run the survey setup phase without starting preview or conversion output."""
    try:
        preview_response = handle_api_survey_convert_preview(
            convert_survey_xlsx_to_prism_dataset=convert_survey_xlsx_to_prism_dataset,
            convert_survey_lsa_to_prism_dataset=convert_survey_lsa_to_prism_dataset,
            resolve_effective_library_path=_resolve_effective_library_path,
            run_survey_with_official_fallback=_run_survey_with_official_fallback,
            validate_project_templates_for_tasks=_validate_project_templates_for_tasks,
            build_template_completion_gate=_build_template_completion_gate,
            format_unmatched_groups_response=_format_unmatched_groups_response,
            id_column_not_detected_error_cls=IdColumnNotDetectedError,
            unmatched_groups_error_cls=UnmatchedGroupsError,
            survey_value_out_of_bounds_error_cls=SurveyValueOutOfBoundsError,
            format_value_offset_confirmation_response=_format_value_offset_confirmation_response,
        )

        response, status_code = _coerce_flask_response(preview_response)
        if status_code != 200:
            return preview_response

        payload = response.get_json(silent=True) or {}
        preview_payload = (
            payload.get("preview") if isinstance(payload.get("preview"), dict) else {}
        )
        prepared_payload: dict[str, Any] = {
            "ok": True,
            "tasks_included": list(payload.get("tasks_included") or []),
            "detected_sessions": list(payload.get("detected_sessions") or []),
            "task_runs": payload.get("task_runs") or {},
            "session_column": payload.get("session_column"),
            "run_column": payload.get("run_column"),
            "multivariant_tasks": payload.get("multivariant_tasks") or {},
            "preview_participants": list(preview_payload.get("participants") or []),
            "applied_value_offsets": payload.get("applied_value_offsets") or {},
            "value_offset_application_counts": payload.get(
                "value_offset_application_counts"
            )
            or {},
            "requires_template_completion": bool(
                payload.get("requires_template_completion")
            ),
        }
        if payload.get("workflow_gate") is not None:
            prepared_payload["workflow_gate"] = payload.get("workflow_gate")
        if payload.get("near_match_applied"):
            prepared_payload["near_match_applied"] = True

        return jsonify(prepared_payload)
    except Exception as error:
        if has_app_context():
            current_app.logger.exception("Survey workflow preparation failed")
        message = str(error).strip() or "Survey workflow preparation failed."
        return jsonify({"error": message}), 500


def api_survey_workflow_command():
    """Dispatch survey workflow commands through one adapter endpoint."""
    json_payload = request.get_json(silent=True)
    if not isinstance(json_payload, dict):
        json_payload = {}

    raw_command = (
        request.form.get("workflow_command")
        or request.form.get("command")
        or request.form.get("mode")
        or json_payload.get("workflow_command")
        or json_payload.get("command")
        or json_payload.get("mode")
        or ""
    )
    normalized_command = str(raw_command).strip().lower()
    command_aliases = {
        "prepare": "prepare",
        "setup": "prepare",
        "preview": "preview",
        "dry-run": "preview",
        "dry_run": "preview",
        "convert": "convert",
        "validate": "convert",
    }
    resolved_command = command_aliases.get(normalized_command)

    if resolved_command == "prepare":
        return api_survey_prepare_workflow()
    if resolved_command == "preview":
        return api_survey_convert_preview()
    if resolved_command == "convert":
        return api_survey_convert_validate()

    return (
        jsonify(
            {
                "error": "Unsupported survey workflow command. Use prepare, preview, or convert.",
                "workflow_command": normalized_command,
            }
        ),
        400,
    )


def _validate_project_templates_for_tasks(
    *,
    tasks: list[str],
    project_path: str | None,
    schema_version: str = "stable",
) -> list[dict[str, str]]:
    """Validate project survey templates for used tasks and return issues.

    Validation is project-local only. Official templates may be copied into the
    project beforehand, but checks must evaluate only project template content.
    """
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
        return isinstance(versions, list) and len([v for v in versions if v]) > 1

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
            with open(template_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
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
            field_path = " -> ".join([str(p) for p in err.path])
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


def _collect_project_template_warnings_for_tasks(
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
            with open(template_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            # JSON parse problems are handled as blocking issues elsewhere.
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


def _build_template_completion_gate(
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


def _format_unmatched_groups_response(uge, log_messages=None):
    """Build the JSON response dict for an UnmatchedGroupsError."""

    def _safe_prism_json(value):
        if isinstance(value, dict):
            return value
        return {}

    payload = {
        "error": "unmatched_groups",
        "message": str(uge),
        "unmatched": [
            {
                "group_name": g["group_name"],
                "task_key": g["task_key"],
                "item_count": len(
                    [
                        k
                        for k in _safe_prism_json(g.get("prism_json"))
                        if k not in _NON_ITEM_TOPLEVEL_KEYS
                        and isinstance(
                            _safe_prism_json(g.get("prism_json")).get(k), dict
                        )
                    ]
                ),
                "item_codes": sorted(g.get("item_codes", []))[:10],
                "prism_json": _safe_prism_json(g.get("prism_json")),
            }
            for g in uge.unmatched
        ],
    }
    if log_messages is not None:
        payload["log"] = log_messages
    return payload


def api_survey_languages():
    return handle_api_survey_languages(
        participant_json_candidates=_participant_json_candidates,
    )


def api_survey_check_project_templates():
    """Validate local project survey templates and optionally seed from official templates."""
    requested_project_path = (request.form.get("project_path") or "").strip() or None
    try:
        project_root = require_existing_project_root(
            requested_project_path or session.get("current_project_path"),
            missing_message="No project selected",
            missing_path_message="The selected project path no longer exists. Reopen the project and retry template check.",
        )
    except (ValueError, FileNotFoundError) as error:
        return jsonify({"error": str(error)}), 400

    uploaded_file, upload_error = _resolve_uploaded_or_source_file(
        field_names=("excel", "file")
    )
    parsed_stage_fields = _survey_workflow_stage_service.parse_stage_form_fields(
        form=request.form
    )
    id_column = parsed_stage_fields.id_column
    session_column = parsed_stage_fields.session_column
    sheet = parsed_stage_fields.sheet
    duplicate_handling = parsed_stage_fields.duplicate_handling
    try:
        separator_option = normalize_separator_option(request.form.get("separator"))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    matching_summary = {
        "input_file": None,
        "official_template_count": 0,
        "matched_tasks": [],
        "copied_tasks": [],
        "existing_tasks": [],
        "missing_official_tasks": [],
        "detected_sessions": [],
        "task_runs": {},
        "session_column": None,
        "run_column": None,
        "match_error": None,
    }

    if uploaded_file and getattr(uploaded_file, "filename", ""):
        filename = secure_filename(uploaded_file.filename)
        suffix = Path(filename).suffix.lower()
        if suffix not in _SUPPORTED_SURVEY_INPUT_SUFFIXES:
            return jsonify({"error": _SUPPORTED_SURVEY_INPUT_MESSAGE}), 400

        matching_summary["input_file"] = filename
        try:
            inferred = _infer_tasks_against_official_templates(
                uploaded_file=uploaded_file,
                filename=filename,
                project_path=str(project_root),
                id_column=id_column,
                session_column=session_column,
                sheet=sheet,
                duplicate_handling=duplicate_handling,
                separator_option=separator_option,
            )
            matching_summary["official_template_count"] = inferred.get(
                "official_template_count", 0
            )
            matching_summary["matched_tasks"] = inferred.get("tasks", [])
            matching_summary["copied_tasks"] = inferred.get("copied_tasks", [])
            matching_summary["existing_tasks"] = inferred.get("existing_tasks", [])
            matching_summary["missing_official_tasks"] = inferred.get(
                "missing_official_tasks", []
            )
            matching_summary["detected_sessions"] = inferred.get(
                "detected_sessions", []
            )
            matching_summary["task_runs"] = inferred.get("task_runs", {})
            matching_summary["session_column"] = inferred.get("session_column")
            matching_summary["run_column"] = inferred.get("run_column")
            matching_summary["match_error"] = inferred.get("match_error")
        except IdColumnNotDetectedError as e:
            return (
                jsonify(
                    {
                        "error": "id_column_required",
                        "message": str(e),
                        "columns": e.available_columns,
                    }
                ),
                409,
            )
        except MissingIdMappingError as mie:
            return (
                jsonify(
                    {
                        "error": "id_mapping_incomplete",
                        "message": str(mie),
                        "missing_ids": mie.missing_ids,
                        "suggestions": mie.suggestions,
                    }
                ),
                409,
            )
        except UnmatchedGroupsError as uge:
            return jsonify(_format_unmatched_groups_response(uge)), 409
        except Exception as exc:
            matching_summary["match_error"] = str(exc)
    elif upload_error and upload_error != "Missing input file":
        return jsonify({"error": upload_error}), 400

    template_dir = project_root / "code" / "library" / "survey"
    template_files = (
        sorted(template_dir.glob("survey-*.json")) if template_dir.is_dir() else []
    )
    tasks = sorted(
        {
            file_path.stem[len("survey-") :]
            for file_path in template_files
            if file_path.stem.startswith("survey-")
            and len(file_path.stem) > len("survey-")
        }
    )
    local_templates = list(tasks)

    if matching_summary["matched_tasks"]:
        tasks = matching_summary["matched_tasks"]

    if not template_files:
        return jsonify(
            {
                "ok": True,
                "message": "No local survey templates found in project code/library/survey.",
                "template_dir": str(template_dir),
                "template_count": 0,
                "local_templates": [],
                "tasks": [],
                "issues": [],
                "warnings": [],
                "matching": matching_summary,
                "multivariant_tasks": {},
                "detected_sessions": matching_summary["detected_sessions"],
                "task_runs": matching_summary["task_runs"],
                "session_column": matching_summary["session_column"],
                "run_column": matching_summary["run_column"],
            }
        )

    issues = _validate_project_templates_for_tasks(
        tasks=tasks,
        project_path=str(project_root),
        schema_version="stable",
    )
    warnings = _collect_project_template_warnings_for_tasks(
        tasks=local_templates,
        project_path=str(project_root),
    )
    multivariant_tasks = collect_multivariant_tasks_from_library(
        library_dir=project_root / "code" / "library" / "survey",
        tasks=tasks,
        selected_versions=_get_effective_template_version_overrides(
            project_path=project_root,
            template_version_overrides=None,
        ),
    )

    if issues:
        gate = _build_template_completion_gate(tasks=tasks, issues=issues)
        return jsonify(
            {
                "ok": False,
                "message": gate["message"],
                "template_dir": str(template_dir),
                "template_count": len(template_files),
                "local_templates": local_templates,
                "tasks": tasks,
                "issues": issues,
                "warnings": warnings,
                "workflow_gate": gate,
                "matching": matching_summary,
                "multivariant_tasks": multivariant_tasks,
                "detected_sessions": matching_summary["detected_sessions"],
                "task_runs": matching_summary["task_runs"],
                "session_column": matching_summary["session_column"],
                "run_column": matching_summary["run_column"],
            }
        )

    return jsonify(
        {
            "ok": True,
            "message": "Project survey templates passed required-field validation.",
            "template_dir": str(template_dir),
            "template_count": len(template_files),
            "local_templates": local_templates,
            "tasks": tasks,
            "issues": [],
            "warnings": warnings,
            "matching": matching_summary,
            "multivariant_tasks": multivariant_tasks,
            "detected_sessions": matching_summary["detected_sessions"],
            "task_runs": matching_summary["task_runs"],
            "session_column": matching_summary["session_column"],
            "run_column": matching_summary["run_column"],
        }
    )


def api_survey_detect_version_context():
    uploaded_file, upload_error = _resolve_uploaded_or_source_file(
        field_names=("excel", "file")
    )
    if uploaded_file is None:
        if upload_error == "Missing input file":
            return jsonify({"ok": True, "multivariant_tasks": {}, "task_runs": {}})
        return jsonify({"error": upload_error}), 400

    if not getattr(uploaded_file, "filename", ""):
        return jsonify({"ok": True, "multivariant_tasks": {}, "task_runs": {}})

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in _SUPPORTED_SURVEY_INPUT_SUFFIXES:
        return jsonify({"error": _SUPPORTED_SURVEY_INPUT_MESSAGE}), 400

    try:
        requested_project_root = _resolve_requested_project_root(require_project=False)
    except (ValueError, FileNotFoundError) as error:
        return jsonify({"error": str(error)}), 400

    requested_project_path = (
        str(requested_project_root) if requested_project_root else None
    )

    raw_survey_filter = (request.form.get("survey") or "").strip() or None
    try:
        selected_tasks = parse_selected_survey_tasks(
            request.form.get("selected_tasks")
        )
        survey_filter = merge_selected_survey_filter(raw_survey_filter, selected_tasks)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    try:
        template_version_overrides = parse_template_version_overrides(
            request.form.get("template_versions")
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    allow_near_item_match = request.form.get("allow_near_item_match") == "true"
    near_match_tasks: set[str] | None = None
    if allow_near_item_match:
        try:
            near_match_tasks = parse_near_item_match_task_allowlist(
                request.form.get("near_match_tasks")
            )
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        if near_match_tasks is not None and not near_match_tasks:
            return jsonify({"error": "No survey tasks selected for near matching."}), 400

    try:
        task_value_offsets = parse_task_value_offsets(request.form.get("value_offsets"))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    parsed_stage_fields = _survey_workflow_stage_service.parse_stage_form_fields(
        form=request.form
    )
    id_column = parsed_stage_fields.id_column
    session_column = parsed_stage_fields.session_column
    run_column = parsed_stage_fields.run_column
    session_override = parsed_stage_fields.session_override
    sheet = parsed_stage_fields.sheet
    duplicate_handling = parsed_stage_fields.duplicate_handling
    try:
        separator_option = normalize_separator_option(request.form.get("separator"))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    project_path = requested_project_path
    effective_template_version_overrides = _get_effective_template_version_overrides(
        project_path=project_path,
        template_version_overrides=template_version_overrides,
    )

    library_path = None
    try:
        library_path = _resolve_effective_library_path()
    except FileNotFoundError:
        library_path = _resolve_official_survey_dir(project_path)
        if not library_path:
            return (
                jsonify({"error": "No survey template library could be resolved."}),
                400,
            )

    try:
        context = _detect_survey_version_contexts(
            uploaded_file=uploaded_file,
            filename=filename,
            library_dir=library_path,
            project_path=project_path,
            survey=survey_filter,
            id_column=id_column,
            session_column=session_column,
            run_column=run_column,
            session_override=session_override,
            sheet=sheet,
            duplicate_handling=duplicate_handling,
            separator_option=separator_option,
            template_version_overrides=effective_template_version_overrides,
            allow_near_item_match=allow_near_item_match,
            near_match_tasks=near_match_tasks,
            task_value_offsets=task_value_offsets,
        )
    except IdColumnNotDetectedError as error:
        return (
            jsonify(
                {
                    "error": "id_column_required",
                    "message": str(error),
                    "columns": error.available_columns,
                }
            ),
            409,
        )
    except MissingIdMappingError as error:
        return (
            jsonify(
                {
                    "error": "id_mapping_incomplete",
                    "message": str(error),
                    "missing_ids": error.missing_ids,
                    "suggestions": error.suggestions,
                }
            ),
            409,
        )
    except UnmatchedGroupsError as error:
        return jsonify(_format_unmatched_groups_response(error)), 409
    except Exception as error:
        return jsonify({"error": str(error)}), 400

    return jsonify({"ok": True, **context})


def api_survey_convert_preview():
    return handle_api_survey_convert_preview(
        convert_survey_xlsx_to_prism_dataset=convert_survey_xlsx_to_prism_dataset,
        convert_survey_lsa_to_prism_dataset=convert_survey_lsa_to_prism_dataset,
        resolve_effective_library_path=_resolve_effective_library_path,
        run_survey_with_official_fallback=_run_survey_with_official_fallback,
        validate_project_templates_for_tasks=_validate_project_templates_for_tasks,
        build_template_completion_gate=_build_template_completion_gate,
        format_unmatched_groups_response=_format_unmatched_groups_response,
        id_column_not_detected_error_cls=IdColumnNotDetectedError,
        unmatched_groups_error_cls=UnmatchedGroupsError,
        survey_value_out_of_bounds_error_cls=SurveyValueOutOfBoundsError,
        format_value_offset_confirmation_response=_format_value_offset_confirmation_response,
    )


def api_survey_convert():
    """Run full survey conversion and return ZIP output."""
    if (
        not convert_survey_xlsx_to_prism_dataset
        and not convert_survey_lsa_to_prism_dataset
    ):
        return jsonify({"error": "Survey conversion module not available"}), 500

    uploaded_file, upload_error = _resolve_uploaded_or_source_file(
        field_names=("excel", "file")
    )
    alias_upload = request.files.get("alias") or request.files.get("alias_file")
    id_map_upload = request.files.get("id_map")

    if uploaded_file is None or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": upload_error or "Missing input file"}), 400

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in _SUPPORTED_SURVEY_INPUT_SUFFIXES:
        return jsonify({"error": _SUPPORTED_SURVEY_INPUT_MESSAGE}), 400

    try:
        requested_project_root = _resolve_requested_project_root(require_project=False)
    except (ValueError, FileNotFoundError) as error:
        return jsonify({"error": str(error)}), 400

    requested_project_path = (
        str(requested_project_root) if requested_project_root else None
    )

    alias_filename = None
    if alias_upload and getattr(alias_upload, "filename", ""):
        alias_filename = secure_filename(alias_upload.filename)
        alias_suffix = Path(alias_filename).suffix.lower()
        if alias_suffix and alias_suffix not in {".tsv", ".txt"}:
            return (
                jsonify({"error": "Alias file must be a .tsv or .txt mapping file"}),
                400,
            )

    id_map_filename = None
    if id_map_upload and getattr(id_map_upload, "filename", ""):
        id_map_filename = secure_filename(id_map_upload.filename)
        id_map_suffix = Path(id_map_filename).suffix.lower()
        if id_map_suffix and id_map_suffix not in {".tsv", ".csv", ".txt"}:
            return (
                jsonify({"error": "ID map file must be a .tsv, .csv, or .txt file"}),
                400,
            )

    try:
        library_path = _resolve_effective_library_path()
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 400

    try:
        effective_survey_dir = _survey_workflow_stage_service.resolve_effective_survey_dir(
            library_path=library_path,
            fallback_project_path=(
                requested_project_path or session.get("current_project_path")
            ),
            resolve_official_survey_dir=_resolve_official_survey_dir,
        )
    except FileNotFoundError as error:
        return jsonify({"error": str(error)}), 400

    raw_survey_filter = (request.form.get("survey") or "").strip() or None
    try:
        selected_tasks = parse_selected_survey_tasks(
            request.form.get("selected_tasks")
        )
        survey_filter = merge_selected_survey_filter(raw_survey_filter, selected_tasks)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    try:
        template_version_overrides = parse_template_version_overrides(
            request.form.get("template_versions")
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    current_project_path = requested_project_path or session.get("current_project_path")
    effective_template_version_overrides = _get_effective_template_version_overrides(
        project_path=current_project_path,
        template_version_overrides=template_version_overrides,
    )
    parsed_stage_fields = _survey_workflow_stage_service.parse_stage_form_fields(
        form=request.form
    )
    id_column = parsed_stage_fields.id_column
    session_column = parsed_stage_fields.session_column
    session_override = parsed_stage_fields.session_override
    run_column = parsed_stage_fields.run_column
    sheet = parsed_stage_fields.sheet
    unknown = parsed_stage_fields.unknown
    dataset_name = parsed_stage_fields.dataset_name
    language = parsed_stage_fields.language
    strict_levels = parsed_stage_fields.strict_levels
    allow_near_item_match = parsed_stage_fields.allow_near_item_match
    try:
        near_match_tasks = parse_near_item_match_task_allowlist(
            request.form.get("near_match_tasks")
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    try:
        task_value_offsets = parse_task_value_offsets(request.form.get("value_offsets"))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    if allow_near_item_match and near_match_tasks is not None and not near_match_tasks:
        return jsonify({"error": "No survey tasks selected for near matching."}), 400
    save_to_project = request.form.get("save_to_project") == "true"
    archive_sourcedata = request.form.get("archive_sourcedata") == "true"
    project_root = None
    current_project_path = None
    if save_to_project:
        if requested_project_root is not None:
            project_root = requested_project_root
        else:
            try:
                project_root = _resolve_requested_project_root(require_project=True)
            except (ValueError, FileNotFoundError) as error:
                return jsonify({"error": str(error)}), 400
        current_project_path = str(project_root)
    duplicate_handling = parsed_stage_fields.duplicate_handling
    try:
        separator_option = normalize_separator_option(request.form.get("separator"))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    separator = expected_delimiter_for_suffix(suffix, separator_option)

    tmp_dir = tempfile.mkdtemp(prefix="prism_survey_convert_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        fallback_project_path = current_project_path or session.get(
            "current_project_path"
        )

        alias_path = None
        if alias_filename:
            alias_path = tmp_dir_path / alias_filename
            alias_upload.save(str(alias_path))

        id_map_path = None
        if id_map_filename:
            id_map_path = tmp_dir_path / id_map_filename
            id_map_upload.save(str(id_map_path))

        preflight_output_root = tmp_dir_path / "preflight_rawdata"
        preflight_result = None
        try:
            preflight_result = _survey_workflow_stage_service.run_stage(
                workflow_runner=_run_survey_with_official_fallback,
                tabular_converter=convert_survey_xlsx_to_prism_dataset,
                lsa_converter=convert_survey_lsa_to_prism_dataset,
                options=SurveyWorkflowStageOptions(
                    suffix=suffix,
                    input_path=input_path,
                    library_dir=Path(effective_survey_dir),
                    output_root=preflight_output_root,
                    survey=survey_filter,
                    id_column=id_column,
                    session_column=session_column,
                    run_column=run_column,
                    session=session_override,
                    sheet=sheet,
                    unknown=unknown,
                    dry_run=True,
                    force=True,
                    name="preflight",
                    language=language,
                    alias_file=alias_path,
                    id_map_file=id_map_path,
                    strict_levels=strict_levels,
                    separator=separator,
                    duplicate_handling=duplicate_handling,
                    skip_participants=True,
                    project_path=current_project_path,
                    fallback_project_path=fallback_project_path,
                    template_version_overrides=effective_template_version_overrides,
                    allow_near_item_match=allow_near_item_match,
                    near_match_tasks=near_match_tasks,
                    task_value_offsets=task_value_offsets,
                ),
            )
        except IdColumnNotDetectedError as e:
            return (
                jsonify(
                    {
                        "error": "id_column_required",
                        "message": str(e),
                        "columns": e.available_columns,
                    }
                ),
                409,
            )
        except MissingIdMappingError as mie:
            return (
                jsonify(
                    {
                        "error": "id_mapping_incomplete",
                        "message": str(mie),
                        "missing_ids": mie.missing_ids,
                        "suggestions": mie.suggestions,
                    }
                ),
                409,
            )
        except UnmatchedGroupsError as uge:
            return jsonify(_format_unmatched_groups_response(uge)), 409
        except Exception as error:
            if _is_value_offset_confirmation_error(error):
                return (
                    jsonify(
                        _format_workflow_preparation_stale_response(
                            _format_value_offset_confirmation_response(error)
                        )
                    ),
                    409,
                )
            raise

        preflight_near_match_candidates = list(
            getattr(preflight_result, "near_match_candidates", []) or []
        )
        if preflight_near_match_candidates and not allow_near_item_match:
            near_match_payload = _survey_workflow_stage_service.build_near_match_confirmation_payload(
                near_match_candidates=preflight_near_match_candidates
            )
            return (
                jsonify(
                    _format_workflow_preparation_stale_response(
                        near_match_payload
                    )
                ),
                409,
            )

        preflight_tasks = list(getattr(preflight_result, "tasks_included", []) or [])
        project_template_issues = _validate_project_templates_for_tasks(
            tasks=preflight_tasks,
            project_path=fallback_project_path,
            schema_version="stable",
        )
        if project_template_issues:
            workflow_gate = _build_template_completion_gate(
                tasks=preflight_tasks,
                issues=project_template_issues,
            )
            template_gate_payload = _survey_workflow_stage_service.build_template_completion_required_payload(
                workflow_gate=workflow_gate,
                template_issues=project_template_issues,
            )
            return (
                jsonify(
                    _format_workflow_preparation_stale_response(
                        template_gate_payload
                    )
                ),
                409,
            )

        output_root = tmp_dir_path / "rawdata"
        detected_language = None
        detected_platform = None
        detected_version = None

        if suffix == ".lsa" and infer_lsa_metadata:
            try:
                meta = infer_lsa_metadata(input_path)
                detected_language = meta.get("language")
                detected_platform = meta.get("software_platform")
                detected_version = meta.get("software_version")
            except Exception:
                pass

        try:
            convert_result = _survey_workflow_stage_service.run_stage(
                workflow_runner=_run_survey_with_official_fallback,
                tabular_converter=convert_survey_xlsx_to_prism_dataset,
                lsa_converter=convert_survey_lsa_to_prism_dataset,
                options=SurveyWorkflowStageOptions(
                    suffix=suffix,
                    input_path=input_path,
                    library_dir=Path(effective_survey_dir),
                    output_root=output_root,
                    survey=survey_filter,
                    id_column=id_column,
                    session_column=session_column,
                    run_column=run_column,
                    session=session_override,
                    sheet=sheet,
                    unknown=unknown,
                    dry_run=False,
                    force=True,
                    name=dataset_name,
                    language=language,
                    alias_file=alias_path,
                    id_map_file=id_map_path,
                    strict_levels=strict_levels,
                    separator=separator,
                    duplicate_handling=duplicate_handling,
                    skip_participants=True,
                    project_path=current_project_path,
                    fallback_project_path=fallback_project_path,
                    template_version_overrides=effective_template_version_overrides,
                    allow_near_item_match=allow_near_item_match,
                    near_match_tasks=near_match_tasks,
                    task_value_offsets=task_value_offsets,
                ),
            )
        except IdColumnNotDetectedError as e:
            return (
                jsonify(
                    {
                        "error": "id_column_required",
                        "message": str(e),
                        "columns": e.available_columns,
                    }
                ),
                409,
            )
        except MissingIdMappingError as mie:
            return (
                jsonify(
                    {
                        "error": "id_mapping_incomplete",
                        "message": str(mie),
                        "missing_ids": mie.missing_ids,
                        "suggestions": mie.suggestions,
                    }
                ),
                409,
            )
        except UnmatchedGroupsError as uge:
            return jsonify(_format_unmatched_groups_response(uge)), 409
        except Exception as error:
            if _is_value_offset_confirmation_error(error):
                return (
                    jsonify(
                        _format_workflow_preparation_stale_response(
                            _format_value_offset_confirmation_response(error)
                        )
                    ),
                    409,
                )
            raise

        if save_to_project:
            dest_root = project_root
            dest_root.mkdir(parents=True, exist_ok=True)

            for item in output_root.rglob("*"):
                if item.is_file():
                    rel_path = item.relative_to(output_root)
                    dest = dest_root / rel_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest)

            if archive_sourcedata:
                sourcedata_dir = project_root / "sourcedata"
                sourcedata_dir.mkdir(parents=True, exist_ok=True)
                archive_dest = sourcedata_dir / filename
                shutil.copy2(input_path, archive_dest)

            registration_sessions = _iter_session_registration_values(
                session_override=session_override,
                detected_sessions=(
                    list(getattr(convert_result, "detected_sessions", []) or [])
                    if convert_result
                    else []
                ),
            )
            if registration_sessions:
                conv_type = "survey-lsa" if suffix == ".lsa" else "survey-xlsx"
                tasks_out = _extract_tasks_from_output(output_root)
                for registration_session in registration_sessions:
                    _register_session_in_project(
                        project_root,
                        registration_session,
                        tasks_out,
                        "survey",
                        filename,
                        conv_type,
                        template_version_overrides=effective_template_version_overrides,
                    )

            if (
                convert_result
                and callable(sync_project_survey_recipe_offsets)
            ):
                applied_offsets = (
                    getattr(convert_result, "applied_value_offsets", {}) or {}
                )
                offset_application_counts = (
                    getattr(convert_result, "value_offset_application_counts", {})
                    or {}
                )
                if applied_offsets:
                    try:
                        sync_project_survey_recipe_offsets(
                            project_root=project_root,
                            task_value_offsets=applied_offsets,
                            offset_application_counts=offset_application_counts,
                        )
                    except Exception:
                        # Recipe metadata sync is best-effort and must not block import.
                        pass

        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in output_root.rglob("*"):
                if p.is_file():
                    arcname = p.relative_to(output_root)
                    zf.write(p, arcname.as_posix())
        mem.seek(0)

        resp = send_file(
            mem,
            mimetype="application/zip",
            as_attachment=True,
            download_name="prism_survey_dataset.zip",
        )

        if detected_language:
            resp.headers["X-Prism-Detected-Language"] = str(detected_language)
        if detected_platform:
            resp.headers["X-Prism-Detected-SoftwarePlatform"] = str(detected_platform)
        if detected_version:
            resp.headers["X-Prism-Detected-SoftwareVersion"] = str(detected_version)

        return resp
    except zipfile.BadZipFile:
        return (
            jsonify(
                {
                    "error": "❌ Invalid or corrupted archive file.\n\n"
                    "The .lsa file appears to be damaged or not a valid LimeSurvey Archive.\n\n"
                    "💡 Solutions:\n"
                    "   • Re-export the survey from LimeSurvey\n"
                    "   • Ensure the file was completely downloaded\n"
                    "   • Try uploading from a different location"
                }
            ),
            400,
        )
    except ET.ParseError as e:
        return (
            jsonify(
                {
                    "error": f"❌ XML parsing error in LimeSurvey archive.\n\n"
                    f"The survey structure file (.lss) inside the archive is malformed.\n\n"
                    f"Technical details: {str(e)}\n\n"
                    f"💡 Solutions:\n"
                    f"   • Re-export the survey from LimeSurvey\n"
                    f"   • Check for special characters in question text that might cause XML issues"
                }
            ),
            400,
        )
    except Exception as e:
        error_msg = str(e)
        if "No module named" in error_msg:
            error_msg = f"❌ Missing Python package: {error_msg}\n\n💡 Run the setup script to install dependencies."
        elif "Permission denied" in error_msg:
            error_msg = f"❌ File access denied: {error_msg}\n\n💡 Check file permissions and try again."
        elif "not found" in error_msg.lower() and "column" not in error_msg.lower():
            error_msg = f"❌ File or resource not found: {error_msg}"
        elif not error_msg:
            error_msg = "❌ An unknown error occurred during conversion. Check server logs for details."

        if has_app_context():
            current_app.logger.exception("Survey conversion failed")
        return jsonify({"error": error_msg}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def api_survey_convert_validate():
    """Convert survey, save to the active project, and return validation results."""
    if (
        not convert_survey_xlsx_to_prism_dataset
        and not convert_survey_lsa_to_prism_dataset
    ):
        return jsonify({"error": "Survey conversion module not available"}), 500

    log_messages = []
    conversion_warnings = []

    def add_log(message, level="info"):
        log_messages.append({"message": message, "level": level})

    uploaded_file, upload_error = _resolve_uploaded_or_source_file(
        field_names=("excel", "file")
    )
    alias_upload = request.files.get("alias") or request.files.get("alias_file")
    id_map_upload = request.files.get("id_map")

    if uploaded_file is None or not getattr(uploaded_file, "filename", ""):
        return (
            jsonify({"error": upload_error or "Missing input file", "log": log_messages}),
            400,
        )

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in _SUPPORTED_SURVEY_INPUT_SUFFIXES:
        return (
            jsonify(
                {
                    "error": _SUPPORTED_SURVEY_INPUT_MESSAGE,
                    "log": log_messages,
                }
            ),
            400,
        )

    try:
        project_root = _resolve_requested_project_root(require_project=True)
    except (ValueError, FileNotFoundError) as error:
        return (
            jsonify(
                {
                    "error": str(error),
                    "log": log_messages,
                }
            ),
            400,
        )

    current_project_path = str(project_root) if project_root else None

    try:
        library_path = _resolve_effective_library_path()
    except FileNotFoundError as e:
        return jsonify({"error": str(e), "log": log_messages}), 400

    try:
        effective_survey_dir = _survey_workflow_stage_service.resolve_effective_survey_dir(
            library_path=library_path,
            fallback_project_path=current_project_path,
            resolve_official_survey_dir=_resolve_official_survey_dir,
        )
    except FileNotFoundError as error:
        return jsonify({"error": str(error), "log": log_messages}), 400

    raw_survey_filter = (request.form.get("survey") or "").strip() or None
    try:
        selected_tasks = parse_selected_survey_tasks(
            request.form.get("selected_tasks")
        )
        survey_filter = merge_selected_survey_filter(raw_survey_filter, selected_tasks)
    except ValueError as error:
        return jsonify({"error": str(error), "log": log_messages}), 400
    try:
        template_version_overrides = parse_template_version_overrides(
            request.form.get("template_versions")
        )
    except ValueError as error:
        return jsonify({"error": str(error), "log": log_messages}), 400
    effective_template_version_overrides = _get_effective_template_version_overrides(
        project_path=current_project_path,
        template_version_overrides=template_version_overrides,
    )
    parsed_stage_fields = _survey_workflow_stage_service.parse_stage_form_fields(
        form=request.form
    )
    id_column = parsed_stage_fields.id_column
    session_column = parsed_stage_fields.session_column
    session_override = parsed_stage_fields.session_override
    run_column = parsed_stage_fields.run_column
    sheet = parsed_stage_fields.sheet
    unknown = parsed_stage_fields.unknown
    dataset_name = parsed_stage_fields.dataset_name
    language = parsed_stage_fields.language
    strict_levels = parsed_stage_fields.strict_levels
    allow_near_item_match = parsed_stage_fields.allow_near_item_match
    try:
        near_match_tasks = parse_near_item_match_task_allowlist(
            request.form.get("near_match_tasks")
        )
    except ValueError as error:
        return jsonify({"error": str(error), "log": log_messages}), 400
    try:
        task_value_offsets = parse_task_value_offsets(request.form.get("value_offsets"))
    except ValueError as error:
        return jsonify({"error": str(error), "log": log_messages}), 400
    if allow_near_item_match and near_match_tasks is not None and not near_match_tasks:
        return (
            jsonify(
                {
                    "error": "No survey tasks selected for near matching.",
                    "log": log_messages,
                }
            ),
            400,
        )
    save_to_project = request.form.get("save_to_project", "true") == "true"
    archive_sourcedata = request.form.get("archive_sourcedata") == "true"
    duplicate_handling = parsed_stage_fields.duplicate_handling

    if not save_to_project:
        return (
            jsonify(
                {
                    "error": "Project-only mode is enabled. Set save_to_project=true.",
                    "log": log_messages,
                }
            ),
            400,
        )

    if current_project_path is None:
        return (
            jsonify(
                {
                    "error": "No project selected. Load a project before converting survey data.",
                    "log": log_messages,
                }
            ),
            400,
        )
    try:
        separator_option = normalize_separator_option(request.form.get("separator"))
    except ValueError as error:
        return jsonify({"error": str(error), "log": log_messages}), 400
    separator = expected_delimiter_for_suffix(suffix, separator_option)

    tmp_dir = tempfile.mkdtemp(prefix="prism_survey_convert_validate_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        alias_path = None
        if alias_upload and getattr(alias_upload, "filename", ""):
            alias_path = tmp_dir_path / secure_filename(alias_upload.filename)
            alias_upload.save(str(alias_path))

        id_map_path = None
        if id_map_upload and getattr(id_map_upload, "filename", ""):
            id_map_filename = secure_filename(id_map_upload.filename)
            id_map_path = tmp_dir_path / id_map_filename
            id_map_upload.save(str(id_map_path))
            saved_size = id_map_path.stat().st_size if id_map_path.exists() else 0
            add_log(
                f"Using ID map file: {id_map_filename} ({saved_size} bytes)", "info"
            )

        fallback_project_path = current_project_path
        preflight_output_root = tmp_dir_path / "preflight_rawdata"
        preflight_result = None
        try:
            preflight_result = _survey_workflow_stage_service.run_stage(
                workflow_runner=_run_survey_with_official_fallback,
                tabular_converter=convert_survey_xlsx_to_prism_dataset,
                lsa_converter=convert_survey_lsa_to_prism_dataset,
                options=SurveyWorkflowStageOptions(
                    suffix=suffix,
                    input_path=input_path,
                    library_dir=Path(effective_survey_dir),
                    output_root=preflight_output_root,
                    survey=survey_filter,
                    id_column=id_column,
                    session_column=session_column,
                    run_column=run_column,
                    session=session_override,
                    sheet=sheet,
                    unknown=unknown,
                    dry_run=True,
                    force=True,
                    name="preflight",
                    language=language,
                    alias_file=alias_path,
                    id_map_file=id_map_path,
                    strict_levels=strict_levels,
                    separator=separator,
                    duplicate_handling=duplicate_handling,
                    skip_participants=True,
                    project_path=current_project_path,
                    fallback_project_path=fallback_project_path,
                    log_fn=add_log,
                    template_version_overrides=effective_template_version_overrides,
                    allow_near_item_match=allow_near_item_match,
                    near_match_tasks=near_match_tasks,
                    task_value_offsets=task_value_offsets,
                ),
            )
        except IdColumnNotDetectedError as e:
            add_log(f"ID column not detected: {str(e)}", "error")
            return (
                jsonify(
                    {
                        "error": "id_column_required",
                        "message": str(e),
                        "columns": e.available_columns,
                        "log": log_messages,
                    }
                ),
                409,
            )
        except MissingIdMappingError as mie:
            add_log(f"ID mapping incomplete: {str(mie)}", "error")
            return (
                jsonify(
                    {
                        "error": "id_mapping_incomplete",
                        "message": str(mie),
                        "missing_ids": mie.missing_ids,
                        "suggestions": mie.suggestions,
                        "log": log_messages,
                    }
                ),
                409,
            )
        except UnmatchedGroupsError as uge:
            add_log(f"Unmatched groups: {str(uge)}", "error")
            return (
                jsonify(_format_unmatched_groups_response(uge, log_messages)),
                409,
            )
        except Exception as error:
            if _is_value_offset_confirmation_error(error):
                add_log(
                    "Out-of-range survey values need review before conversion can continue.",
                    "warning",
                )
                return (
                    jsonify(
                        _format_workflow_preparation_stale_response(
                            _format_value_offset_confirmation_response(
                                error,
                                log_messages,
                            ),
                            log_messages=log_messages,
                        )
                    ),
                    409,
                )
            raise

        preflight_near_match_candidates = list(
            getattr(preflight_result, "near_match_candidates", []) or []
        )
        if preflight_near_match_candidates and not allow_near_item_match:
            add_log("Near item matches detected and awaiting confirmation", "warning")
            near_match_payload = _survey_workflow_stage_service.build_near_match_confirmation_payload(
                near_match_candidates=preflight_near_match_candidates
            )
            return (
                jsonify(
                    _format_workflow_preparation_stale_response(
                        near_match_payload,
                        log_messages=log_messages,
                    )
                ),
                409,
            )

        preflight_tasks = list(getattr(preflight_result, "tasks_included", []) or [])
        project_template_issues = _validate_project_templates_for_tasks(
            tasks=preflight_tasks,
            project_path=fallback_project_path,
            schema_version="stable",
        )
        if project_template_issues:
            workflow_gate = _build_template_completion_gate(
                tasks=preflight_tasks,
                issues=project_template_issues,
            )
            add_log("✗ Import blocked until project templates are completed", "error")
            add_log(workflow_gate["message"], "error")
            for issue in project_template_issues[:20]:
                add_log(f"  - {Path(issue['file']).name}: {issue['message']}", "error")
            if len(project_template_issues) > 20:
                add_log(
                    f"  ... and {len(project_template_issues) - 20} more template issue(s)",
                    "error",
                )
            template_gate_payload = _survey_workflow_stage_service.build_template_completion_required_payload(
                workflow_gate=workflow_gate,
                template_issues=project_template_issues,
            )
            return (
                jsonify(
                    _format_workflow_preparation_stale_response(
                        template_gate_payload,
                        log_messages=log_messages,
                    )
                ),
                409,
            )

        project_path = current_project_path
        if project_path and save_to_project:
            project_path = Path(project_path)
            if project_path.is_file():
                project_path = project_path.parent

            mapping_candidates = participants_mapping_candidates(project_path)

            for mapping_file in mapping_candidates:
                if mapping_file.exists():
                    dest_mapping = tmp_dir_path / "code" / "participants_mapping.json"
                    dest_mapping.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(mapping_file, dest_mapping)
                    add_log(
                        f"Using participants mapping from: {mapping_file.name}", "info"
                    )
                    break

        output_root = tmp_dir_path / "rawdata"
        output_root.mkdir(parents=True, exist_ok=True)
        add_log("Starting data conversion...", "info")
        copied_output_paths: list[Path] = []

        try:
            _log_file_head(input_path, suffix, add_log)
        except Exception as head_err:
            add_log(f"Header preview failed: {head_err}", "warning")

        if strict_levels:
            add_log("Strict Levels Validation: enabled", "info")

        convert_result = None
        try:
            if suffix == ".lsa":
                add_log(f"Processing LimeSurvey archive: {filename}", "info")
            convert_result = _survey_workflow_stage_service.run_stage(
                workflow_runner=_run_survey_with_official_fallback,
                tabular_converter=convert_survey_xlsx_to_prism_dataset,
                lsa_converter=convert_survey_lsa_to_prism_dataset,
                options=SurveyWorkflowStageOptions(
                    suffix=suffix,
                    input_path=input_path,
                    library_dir=Path(effective_survey_dir),
                    output_root=output_root,
                    survey=survey_filter,
                    id_column=id_column,
                    session_column=session_column,
                    run_column=run_column,
                    session=session_override,
                    sheet=sheet,
                    unknown=unknown,
                    dry_run=False,
                    force=True,
                    name=dataset_name,
                    language=language,
                    alias_file=alias_path,
                    id_map_file=id_map_path,
                    strict_levels=strict_levels,
                    separator=separator,
                    duplicate_handling=duplicate_handling,
                    skip_participants=True,
                    project_path=current_project_path,
                    fallback_project_path=current_project_path,
                    log_fn=add_log,
                    template_version_overrides=effective_template_version_overrides,
                    allow_near_item_match=allow_near_item_match,
                    near_match_tasks=near_match_tasks,
                    task_value_offsets=task_value_offsets,
                ),
            )
            add_log("Conversion completed successfully", "success")
        except IdColumnNotDetectedError as e:
            add_log(f"ID column not detected: {str(e)}", "error")
            return (
                jsonify(
                    {
                        "error": "id_column_required",
                        "message": str(e),
                        "columns": e.available_columns,
                        "log": log_messages,
                    }
                ),
                409,
            )
        except MissingIdMappingError as mie:
            add_log(f"ID mapping incomplete: {str(mie)}", "error")
            return (
                jsonify(
                    {
                        "error": "id_mapping_incomplete",
                        "message": str(mie),
                        "missing_ids": mie.missing_ids,
                        "suggestions": mie.suggestions,
                        "log": log_messages,
                    }
                ),
                409,
            )
        except UnmatchedGroupsError as uge:
            add_log(f"Unmatched groups: {str(uge)}", "error")
            return (
                jsonify(_format_unmatched_groups_response(uge, log_messages)),
                409,
            )
        except Exception as conv_err:
            if _is_value_offset_confirmation_error(conv_err):
                add_log(
                    "Out-of-range survey values need review before conversion can continue.",
                    "warning",
                )
                return (
                    jsonify(
                        _format_workflow_preparation_stale_response(
                            _format_value_offset_confirmation_response(
                                conv_err,
                                log_messages,
                            ),
                            log_messages=log_messages,
                        )
                    ),
                    409,
                )
            import sys
            import traceback

            full_trace = traceback.format_exc()
            print(
                f"\n[CONVERSION ERROR] {type(conv_err).__name__}: {str(conv_err)}",
                file=sys.stderr,
            )
            print(f"[FULL TRACEBACK]\n{full_trace}", file=sys.stderr)
            add_log(
                f"Conversion engine failed: {type(conv_err).__name__}: {str(conv_err)}",
                "error",
            )
            raise conv_err

        if convert_result and getattr(convert_result, "missing_cells_by_subject", None):
            missing_counts = {
                sid: cnt
                for sid, cnt in convert_result.missing_cells_by_subject.items()
                if cnt > 0
            }
            if missing_counts:
                conversion_warnings.append(
                    f"Missing responses normalized: {sum(missing_counts.values())} cells."
                )

        if convert_result and getattr(convert_result, "conversion_warnings", None):
            conversion_warnings.extend(convert_result.conversion_warnings)

        add_log("Running validation...", "info")
        validation_result = {"errors": [], "warnings": [], "summary": {}}
        if request.form.get("validate") == "true":
            try:
                validation_library_root = _resolve_validation_library_path(
                    project_path=current_project_path,
                    fallback_library_root=library_path,
                )
                v_res = run_validation(
                    str(output_root),
                    schema_version="stable",
                    library_path=str(validation_library_root),
                    project_path=current_project_path,
                )
                if v_res and isinstance(v_res, tuple):
                    issues = v_res[0]
                    stats = v_res[1]

                    from src.web.reporting_utils import format_validation_results

                    formatted = format_validation_results(
                        issues, stats, str(output_root)
                    )

                    validation_result = {"formatted": formatted}
                    validation_result.update(formatted)

                    total_err = formatted.get("summary", {}).get("total_errors", 0)
                    total_warn = formatted.get("summary", {}).get("total_warnings", 0)

                    if total_err > 0:
                        add_log(
                            f"✗ Validation failed with {total_err} error(s)", "error"
                        )
                        count = 0
                        for group in formatted.get("errors", []):
                            for f in group.get("files", []):
                                if count < 20:
                                    msg = f["message"]
                                    if ": " in msg:
                                        msg = msg.split(": ", 1)[1]
                                    add_log(f"  - {msg}", "error")
                                    count += 1
                        if total_err > 20:
                            add_log(
                                f"  ... and {total_err - 20} more errors (see details below)",
                                "error",
                            )
                    else:
                        add_log("✓ PRISM validation passed!", "success")

                    if total_warn > 0:
                        add_log(f"⚠ {total_warn} warning(s) found", "warning")

                    project_template_issues = _validate_project_templates_for_tasks(
                        tasks=(
                            convert_result.tasks_included
                            if convert_result
                            and getattr(convert_result, "tasks_included", None)
                            else []
                        ),
                        project_path=current_project_path,
                        schema_version="stable",
                    )
                    if project_template_issues:
                        add_log(
                            f"Project template check found {len(project_template_issues)} item(s) to complete",
                            "warning",
                        )
                        for issue in project_template_issues[:20]:
                            add_log(
                                f"  - {Path(issue['file']).name}: {issue['message']}",
                                "warning",
                            )
                        if len(project_template_issues) > 20:
                            add_log(
                                f"  ... and {len(project_template_issues) - 20} more template item(s)",
                                "warning",
                            )

                        template_group = {
                            "code": "PRISM301-TEMPLATE",
                            "message": "Project templates need completion",
                            "description": "Used project templates still need required project-level fields.",
                            "files": [
                                {
                                    "file": issue["file"],
                                    "message": issue["message"],
                                }
                                for issue in project_template_issues
                            ],
                            "count": len(project_template_issues),
                        }
                        validation_result.setdefault("formatted", {}).setdefault(
                            "errors", []
                        ).append(template_group)
                        # Keep formatted error groups homogeneous for the frontend UI.
                        # Appending plain strings here would be rendered as "undefined" cards.
                        if "formatted" not in validation_result:
                            validation_result.setdefault("errors", []).extend(
                                [
                                    f"{Path(i['file']).name}: {i['message']}"
                                    for i in project_template_issues
                                ]
                            )
                        validation_result.setdefault("summary", {}).setdefault(
                            "total_errors", 0
                        )
                        validation_result["summary"]["total_errors"] += len(
                            project_template_issues
                        )

            except Exception as val_err:
                validation_result["warnings"].append(
                    f"Validation error: {str(val_err)}"
                )

        if conversion_warnings:
            if "warnings" not in validation_result:
                validation_result["warnings"] = []

            if "formatted" in validation_result:
                conv_group = {
                    "code": "CONVERSION",
                    "message": "Conversion Warnings",
                    "description": "Issues encountered during data conversion",
                    "files": [
                        {"file": filename, "message": w} for w in conversion_warnings
                    ],
                    "count": len(conversion_warnings),
                }
                validation_result["warnings"].append(conv_group)
                if "summary" in validation_result:
                    validation_result["summary"]["total_warnings"] += len(
                        conversion_warnings
                    )
            else:
                validation_result["warnings"].extend(conversion_warnings)

        recipe_offset_sync_summary: dict[str, list[str]] | None = None

        if save_to_project:
            dest_root = project_root
            dest_root.mkdir(parents=True, exist_ok=True)
            add_log(
                f"Saving output to project: {project_root.name} (into project root)",
                "info",
            )

            for item in output_root.rglob("*"):
                if item.is_file():
                    rel_path = item.relative_to(output_root)
                    dest = dest_root / rel_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest)
                    copied_output_paths.append(dest)

            _cleanup_stale_tool_limesurvey_sidecars(
                copied_output_paths=copied_output_paths,
                source_suffix=suffix,
                log_fn=add_log,
            )
            add_log("Project updated successfully!", "success")

            if archive_sourcedata:
                sourcedata_dir = project_root / "sourcedata"
                sourcedata_dir.mkdir(parents=True, exist_ok=True)
                archive_dest = sourcedata_dir / filename
                shutil.copy2(input_path, archive_dest)
                add_log(f"Archived original file to sourcedata/{filename}", "info")

            registration_sessions = _iter_session_registration_values(
                session_override=session_override,
                detected_sessions=(
                    list(getattr(convert_result, "detected_sessions", []) or [])
                    if convert_result
                    else []
                ),
            )
            if registration_sessions:
                conv_type = "survey-lsa" if suffix == ".lsa" else "survey-xlsx"
                tasks_out = (
                    convert_result.tasks_included
                    if convert_result
                    and getattr(convert_result, "tasks_included", None)
                    else _extract_tasks_from_output(output_root)
                )
                for registration_session in registration_sessions:
                    _register_session_in_project(
                        project_root,
                        registration_session,
                        tasks_out,
                        "survey",
                        filename,
                        conv_type,
                        template_version_overrides=effective_template_version_overrides,
                    )
                add_log(
                    "Registered in project.json: "
                    f"{', '.join(registration_sessions)} → {', '.join(tasks_out)}",
                    "info",
                )

            if convert_result and callable(sync_project_survey_recipe_offsets):
                applied_offsets = (
                    getattr(convert_result, "applied_value_offsets", {}) or {}
                )
                offset_application_counts = (
                    getattr(convert_result, "value_offset_application_counts", {})
                    or {}
                )
                if applied_offsets:
                    try:
                        recipe_offset_sync_summary = sync_project_survey_recipe_offsets(
                            project_root=project_root,
                            task_value_offsets=applied_offsets,
                            offset_application_counts=offset_application_counts,
                        )
                        updated = recipe_offset_sync_summary.get("updated_tasks", [])
                        missing = recipe_offset_sync_summary.get("missing_tasks", [])
                        errors = recipe_offset_sync_summary.get("errors", [])
                        if updated:
                            add_log(
                                "Updated survey recipe offset metadata for: "
                                + ", ".join(updated),
                                "info",
                            )
                        if missing:
                            add_log(
                                "No matching survey recipe file found for: "
                                + ", ".join(missing),
                                "warning",
                            )
                        for sync_error in errors:
                            add_log(
                                f"Recipe offset sync warning: {sync_error}",
                                "warning",
                            )
                    except Exception as sync_err:
                        add_log(
                            f"Recipe offset sync warning: {sync_err}",
                            "warning",
                        )

        response_payload = {
            "success": True,
            "log": log_messages,
            "validation": validation_result,
            "project_saved": bool(copied_output_paths),
            "project_output_root": str(project_root) if copied_output_paths else None,
            "project_output_paths": [],
            "project_output_path": None,
            "project_output_count": len(copied_output_paths),
        }
        if recipe_offset_sync_summary is not None:
            response_payload["recipe_offset_sync"] = recipe_offset_sync_summary

        if copied_output_paths:
            output_paths = summarize_project_output_paths(
                copied_output_paths,
                project_root=project_root,
                limit=50,
            )
            response_payload["project_output_paths"] = output_paths
            response_payload["project_output_path"] = (
                output_paths[0] if output_paths else None
            )

        if convert_result:
            summary = {}
            if getattr(convert_result, "template_matches", None):
                summary["template_matches"] = convert_result.template_matches
            if getattr(convert_result, "tasks_included", None):
                summary["tasks_included"] = convert_result.tasks_included
            if getattr(convert_result, "task_runs", None):
                summary["task_runs"] = convert_result.task_runs
            if getattr(convert_result, "unknown_columns", None):
                summary["unknown_columns"] = convert_result.unknown_columns
            if getattr(convert_result, "tool_columns", None):
                summary["tool_columns"] = convert_result.tool_columns
            if getattr(convert_result, "near_match_candidates", None):
                summary["near_match_candidates"] = convert_result.near_match_candidates
            if getattr(convert_result, "near_match_applied", False):
                summary["near_match_applied"] = True
            if getattr(convert_result, "applied_value_offsets", None):
                summary["applied_value_offsets"] = convert_result.applied_value_offsets
            if getattr(convert_result, "value_offset_application_counts", None):
                summary["value_offset_application_counts"] = (
                    convert_result.value_offset_application_counts
                )
            if recipe_offset_sync_summary is not None:
                summary["recipe_offset_sync"] = recipe_offset_sync_summary
            if conversion_warnings:
                summary["conversion_warnings"] = conversion_warnings
            if getattr(convert_result, "participant_registry_warning", None):
                summary["participant_registry_warning"] = (
                    convert_result.participant_registry_warning
                )
            if summary:
                response_payload["conversion_summary"] = summary
            if getattr(convert_result, "participant_registry_warning", None):
                response_payload["participant_registry_warning"] = (
                    convert_result.participant_registry_warning
                )
            response_payload["multivariant_tasks"] = (
                collect_multivariant_tasks_from_library(
                    library_dir=effective_survey_dir,
                    tasks=list(getattr(convert_result, "tasks_included", []) or []),
                    selected_versions=effective_template_version_overrides,
                )
            )

        return jsonify(sanitize_jsonable(response_payload))
    except Exception as e:
        return jsonify({"error": str(e), "log": log_messages}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def api_save_unmatched_template():
    """Save a generated template for an unmatched group to the project library."""
    try:
        project_root = require_existing_project_root(
            session.get("current_project_path"),
            missing_message="No project selected",
            missing_path_message="The selected project path no longer exists.",
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 400

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON payload. Expected an object."}), 400

    task_key = secure_filename(str(data.get("task_key") or "").strip())
    prism_json = data.get("prism_json")
    if not task_key or not isinstance(prism_json, dict):
        return jsonify({"error": "Missing task_key or prism_json"}), 400

    from src.converters.survey_templates import _strip_run_suffix

    clean = {}
    for k, v in prism_json.items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict) and k not in _NON_ITEM_TOPLEVEL_KEYS:
            base, _ = _strip_run_suffix(k)
            if base not in clean:
                clean[base] = v
        else:
            clean[k] = v

    library_path = Path(project_root) / "code" / "library" / "survey"
    library_path.mkdir(parents=True, exist_ok=True)

    filename = f"survey-{task_key}.json"
    filepath = library_path / filename

    from src.utils.io import write_json

    write_json(filepath, clean)

    return jsonify(
        {
            "success": True,
            "path": str(filepath),
            "filename": filename,
        }
    )
