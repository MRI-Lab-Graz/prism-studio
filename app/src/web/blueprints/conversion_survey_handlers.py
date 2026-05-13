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
from .tools_generation_handlers import handle_detect_columns
from .tools_limesurvey_handlers import handle_limesurvey_to_prism
from .tools_post_conversion_handlers import handle_limesurvey_save_to_project

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
from .conversion_request_helpers import (
    format_workflow_preparation_stale_response as _format_workflow_preparation_stale_response,
    resolve_requested_project_root as _shared_resolve_requested_project_root,
    resolve_uploaded_or_source_file as _resolve_uploaded_or_source_file,
)
from .conversion_survey_convert_handlers import (
    handle_api_survey_convert,
)
from .conversion_survey_convert_validate_handlers import (
    handle_api_survey_convert_validate,
)
from .conversion_survey_official_template_helpers import (
    copy_official_templates_to_project,
    infer_project_template_technical_defaults,
    infer_tasks_against_official_templates,
    prepare_project_survey_template_from_official,
    resolve_official_survey_dir,
)
from .conversion_survey_template_check_handlers import (
    handle_api_survey_check_project_templates,
)
from .conversion_survey_response_helpers import (
    build_prepare_workflow_payload,
    coerce_flask_response,
    format_unmatched_groups_response,
    format_value_offset_confirmation_response,
)
from .conversion_survey_template_helpers import (
    build_template_completion_gate,
    collect_project_template_warnings_for_tasks,
    validate_project_templates_for_tasks,
)

convert_survey_xlsx_to_prism_dataset: Any = None
convert_survey_lsa_to_prism_dataset: Any = None
infer_lsa_metadata: Any = None
from .conversion_survey_version_context_handlers import (
    handle_api_survey_detect_version_context,
)
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


def _requested_project_path() -> str | None:
    raw_value = (
        request.form.get("project_path")
        or request.args.get("project_path")
        or ""
    )
    normalized = str(raw_value).strip()
    return normalized or None


def _resolve_requested_project_root(*, require_project: bool) -> Path | None:
    return _shared_resolve_requested_project_root(
        require_project=require_project,
        missing_message="No project selected. Load a project before converting survey data.",
        missing_path_message=(
            "The selected project path no longer exists. Reopen the project and retry survey conversion."
        ),
    )


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
    return format_value_offset_confirmation_response(
        error,
        log_messages=log_messages,
    )


def _is_value_offset_confirmation_error(error: Exception) -> bool:
    return (
        isinstance(SurveyValueOutOfBoundsError, type)
        and issubclass(SurveyValueOutOfBoundsError, BaseException)
        and isinstance(error, SurveyValueOutOfBoundsError)
    )


def _resolve_official_survey_dir(project_path: str | None) -> Path | None:
    return resolve_official_survey_dir(project_path)


def _infer_project_template_technical_defaults(
    *, input_path: str | Path | None = None
) -> dict[str, str]:
    return infer_project_template_technical_defaults(input_path=input_path)


def _prepare_project_survey_template_from_official(
    payload: Any,
    *,
    task: str,
    technical_defaults: dict[str, str] | None = None,
    selected_version: str | None = None,
) -> Any:
    return prepare_project_survey_template_from_official(
        payload,
        task=task,
        technical_defaults=technical_defaults,
        selected_version=selected_version,
    )


def _copy_official_templates_to_project(
    official_dir: Path,
    tasks: list[str],
    project_path: str | None,
    technical_defaults: dict[str, str] | None = None,
    selected_versions: dict[str, str] | None = None,
    log_fn=None,
) -> dict[str, list[str]]:
    return copy_official_templates_to_project(
        official_dir,
        tasks,
        project_path,
        technical_defaults=technical_defaults,
        selected_versions=selected_versions,
        log_fn=log_fn,
    )


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
    return infer_tasks_against_official_templates(
        uploaded_file=uploaded_file,
        filename=filename,
        project_path=project_path,
        id_column=id_column,
        session_column=session_column,
        sheet=sheet,
        duplicate_handling=duplicate_handling,
        separator_option=separator_option,
        supported_survey_tabular_suffixes=_SUPPORTED_SURVEY_TABULAR_SUFFIXES,
        supported_survey_input_message=_SUPPORTED_SURVEY_INPUT_MESSAGE,
        convert_survey_xlsx_to_prism_dataset=convert_survey_xlsx_to_prism_dataset,
        convert_survey_lsa_to_prism_dataset=convert_survey_lsa_to_prism_dataset,
        run_survey_with_official_fallback=_run_survey_with_official_fallback,
    )


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
    return coerce_flask_response(response_value)


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
        return jsonify(build_prepare_workflow_payload(payload))
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
    return validate_project_templates_for_tasks(
        tasks=tasks,
        project_path=project_path,
        schema_version=schema_version,
        normalize_paper_software_platform=normalize_paper_software_platform,
    )


def _collect_project_template_warnings_for_tasks(
    *,
    tasks: list[str],
    project_path: str | None,
) -> list[dict[str, str]]:
    return collect_project_template_warnings_for_tasks(
        tasks=tasks,
        project_path=project_path,
    )


def _build_template_completion_gate(
    *,
    tasks: list[str],
    issues: list[dict[str, str]],
) -> dict[str, Any]:
    return build_template_completion_gate(tasks=tasks, issues=issues)


def _format_unmatched_groups_response(uge, log_messages=None):
    return format_unmatched_groups_response(
        uge,
        non_item_toplevel_keys=_NON_ITEM_TOPLEVEL_KEYS,
        log_messages=log_messages,
    )


def api_survey_languages():
    return handle_api_survey_languages(
        participant_json_candidates=_participant_json_candidates,
    )


def api_survey_detect_columns():
    return handle_detect_columns()


def api_survey_generate_templates():
    return handle_limesurvey_to_prism()


def api_survey_save_to_project():
    return handle_limesurvey_save_to_project(
        project_path=session.get("current_project_path"),
        data=request.get_json(),
    )


def api_survey_check_project_templates():
    return handle_api_survey_check_project_templates(
        require_existing_project_root=require_existing_project_root,
        resolve_uploaded_or_source_file=_resolve_uploaded_or_source_file,
        survey_workflow_stage_service=_survey_workflow_stage_service,
        normalize_separator_option=normalize_separator_option,
        supported_survey_input_suffixes=_SUPPORTED_SURVEY_INPUT_SUFFIXES,
        supported_survey_input_message=_SUPPORTED_SURVEY_INPUT_MESSAGE,
        infer_tasks_against_official_templates=_infer_tasks_against_official_templates,
        id_column_not_detected_error_cls=IdColumnNotDetectedError,
        missing_id_mapping_error_cls=MissingIdMappingError,
        unmatched_groups_error_cls=UnmatchedGroupsError,
        format_unmatched_groups_response=_format_unmatched_groups_response,
        validate_project_templates_for_tasks=_validate_project_templates_for_tasks,
        collect_project_template_warnings_for_tasks=_collect_project_template_warnings_for_tasks,
        collect_multivariant_tasks_from_library=collect_multivariant_tasks_from_library,
        get_effective_template_version_overrides=_get_effective_template_version_overrides,
    )


def api_survey_detect_version_context():
    return handle_api_survey_detect_version_context(
        resolve_uploaded_or_source_file=_resolve_uploaded_or_source_file,
        supported_survey_input_suffixes=_SUPPORTED_SURVEY_INPUT_SUFFIXES,
        supported_survey_input_message=_SUPPORTED_SURVEY_INPUT_MESSAGE,
        resolve_requested_project_root=_resolve_requested_project_root,
        parse_selected_survey_tasks=parse_selected_survey_tasks,
        merge_selected_survey_filter=merge_selected_survey_filter,
        parse_template_version_overrides=parse_template_version_overrides,
        parse_near_item_match_task_allowlist=parse_near_item_match_task_allowlist,
        parse_task_value_offsets=parse_task_value_offsets,
        survey_workflow_stage_service=_survey_workflow_stage_service,
        normalize_separator_option=normalize_separator_option,
        get_effective_template_version_overrides=_get_effective_template_version_overrides,
        resolve_effective_library_path=_resolve_effective_library_path,
        resolve_official_survey_dir=_resolve_official_survey_dir,
        detect_survey_version_contexts=_detect_survey_version_contexts,
        id_column_not_detected_error_cls=IdColumnNotDetectedError,
        missing_id_mapping_error_cls=MissingIdMappingError,
        unmatched_groups_error_cls=UnmatchedGroupsError,
        format_unmatched_groups_response=_format_unmatched_groups_response,
    )


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
    return handle_api_survey_convert(
        convert_survey_xlsx_to_prism_dataset=convert_survey_xlsx_to_prism_dataset,
        convert_survey_lsa_to_prism_dataset=convert_survey_lsa_to_prism_dataset,
        resolve_uploaded_or_source_file=_resolve_uploaded_or_source_file,
        resolve_requested_project_root=_resolve_requested_project_root,
        supported_survey_input_suffixes=_SUPPORTED_SURVEY_INPUT_SUFFIXES,
        supported_survey_input_message=_SUPPORTED_SURVEY_INPUT_MESSAGE,
        resolve_effective_library_path=_resolve_effective_library_path,
        survey_workflow_stage_service=_survey_workflow_stage_service,
        resolve_official_survey_dir=_resolve_official_survey_dir,
        parse_selected_survey_tasks=parse_selected_survey_tasks,
        merge_selected_survey_filter=merge_selected_survey_filter,
        parse_template_version_overrides=parse_template_version_overrides,
        get_effective_template_version_overrides=_get_effective_template_version_overrides,
        parse_near_item_match_task_allowlist=parse_near_item_match_task_allowlist,
        parse_task_value_offsets=parse_task_value_offsets,
        normalize_separator_option=normalize_separator_option,
        expected_delimiter_for_suffix=expected_delimiter_for_suffix,
        survey_workflow_stage_options_cls=SurveyWorkflowStageOptions,
        run_survey_with_official_fallback=_run_survey_with_official_fallback,
        validate_project_templates_for_tasks=_validate_project_templates_for_tasks,
        build_template_completion_gate=_build_template_completion_gate,
        infer_lsa_metadata=infer_lsa_metadata,
        is_value_offset_confirmation_error=_is_value_offset_confirmation_error,
        format_workflow_preparation_stale_response=_format_workflow_preparation_stale_response,
        format_value_offset_confirmation_response=_format_value_offset_confirmation_response,
        extract_tasks_from_output=_extract_tasks_from_output,
        iter_session_registration_values=_iter_session_registration_values,
        register_session_in_project=_register_session_in_project,
        sync_project_survey_recipe_offsets=sync_project_survey_recipe_offsets,
        id_column_not_detected_error_cls=IdColumnNotDetectedError,
        missing_id_mapping_error_cls=MissingIdMappingError,
        unmatched_groups_error_cls=UnmatchedGroupsError,
        format_unmatched_groups_response=_format_unmatched_groups_response,
    )


def api_survey_convert_validate():
    return handle_api_survey_convert_validate(
        convert_survey_xlsx_to_prism_dataset=convert_survey_xlsx_to_prism_dataset,
        convert_survey_lsa_to_prism_dataset=convert_survey_lsa_to_prism_dataset,
        resolve_uploaded_or_source_file=_resolve_uploaded_or_source_file,
        resolve_requested_project_root=_resolve_requested_project_root,
        supported_survey_input_suffixes=_SUPPORTED_SURVEY_INPUT_SUFFIXES,
        supported_survey_input_message=_SUPPORTED_SURVEY_INPUT_MESSAGE,
        resolve_effective_library_path=_resolve_effective_library_path,
        survey_workflow_stage_service=_survey_workflow_stage_service,
        resolve_official_survey_dir=_resolve_official_survey_dir,
        parse_selected_survey_tasks=parse_selected_survey_tasks,
        merge_selected_survey_filter=merge_selected_survey_filter,
        parse_template_version_overrides=parse_template_version_overrides,
        get_effective_template_version_overrides=_get_effective_template_version_overrides,
        parse_near_item_match_task_allowlist=parse_near_item_match_task_allowlist,
        parse_task_value_offsets=parse_task_value_offsets,
        normalize_separator_option=normalize_separator_option,
        expected_delimiter_for_suffix=expected_delimiter_for_suffix,
        survey_workflow_stage_options_cls=SurveyWorkflowStageOptions,
        run_survey_with_official_fallback=_run_survey_with_official_fallback,
        validate_project_templates_for_tasks=_validate_project_templates_for_tasks,
        build_template_completion_gate=_build_template_completion_gate,
        format_workflow_preparation_stale_response=_format_workflow_preparation_stale_response,
        format_value_offset_confirmation_response=_format_value_offset_confirmation_response,
        is_value_offset_confirmation_error=_is_value_offset_confirmation_error,
        id_column_not_detected_error_cls=IdColumnNotDetectedError,
        missing_id_mapping_error_cls=MissingIdMappingError,
        unmatched_groups_error_cls=UnmatchedGroupsError,
        format_unmatched_groups_response=_format_unmatched_groups_response,
        participants_mapping_candidates=participants_mapping_candidates,
        log_file_head=_log_file_head,
        resolve_validation_library_path=_resolve_validation_library_path,
        run_validation=run_validation,
        cleanup_stale_tool_limesurvey_sidecars=_cleanup_stale_tool_limesurvey_sidecars,
        iter_session_registration_values=_iter_session_registration_values,
        extract_tasks_from_output=_extract_tasks_from_output,
        register_session_in_project=_register_session_in_project,
        sync_project_survey_recipe_offsets=sync_project_survey_recipe_offsets,
        summarize_project_output_paths=summarize_project_output_paths,
        sanitize_jsonable=sanitize_jsonable,
        collect_multivariant_tasks_from_library=collect_multivariant_tasks_from_library,
    )


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
