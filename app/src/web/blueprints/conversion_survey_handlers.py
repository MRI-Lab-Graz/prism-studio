"""Survey conversion handlers extracted from the conversion blueprint."""

import shutil
import tempfile
from pathlib import Path
from typing import Any

from flask import current_app, has_app_context, jsonify, request, session
from werkzeug.utils import secure_filename
from src.participants_paths import participants_mapping_candidates
from src.session_map import SessionsNotMappedError
from src.template_save import TemplateIncomplete
from src.survey_workflow_service import (
    SUPPORTED_SURVEY_INPUT_MESSAGE,
    SUPPORTED_SURVEY_INPUT_SUFFIXES,
    SUPPORTED_SURVEY_TABULAR_SUFFIXES,
    SurveyWorkflowStageOptions,
    SurveyWorkflowStageService,
)

from src.web.reporting_utils import sanitize_jsonable
from src.web.validation import run_validation
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
    resolve_validation_library_path,
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
    handle_api_survey_convert_validate_start,
    handle_api_survey_convert_validate_status,
)
from .conversion_survey_official_template_helpers import (
    app_root,
    infer_tasks_against_official_templates,
    resolve_official_survey_dir,
)
from .conversion_survey_template_check_handlers import (
    handle_api_survey_check_project_templates,
)
from .conversion_survey_response_helpers import (
    build_prepare_workflow_payload,
    coerce_flask_response,
    format_value_offset_confirmation_response,
)
from .conversion_survey_template_helpers import (
    build_template_completion_gate,
    collect_project_template_warnings_for_tasks,
    validate_project_templates_for_tasks,
)

convert_survey_file_to_prism_dataset: Any = None
convert_survey_lsa_to_prism_dataset: Any = None
infer_lsa_metadata: Any = None
from .conversion_survey_version_context_handlers import (
    handle_api_survey_detect_version_context,
)
MissingIdMappingError: Any = None
SurveyValueOutOfBoundsError: Any = None
_resolve_effective_template_version_overrides: Any = None
_normalize_template_version_overrides_for_requests: Any = None
_NON_ITEM_TOPLEVEL_KEYS: set[str] = set()
_SUPPORTED_SURVEY_INPUT_MESSAGE = SUPPORTED_SURVEY_INPUT_MESSAGE
_SUPPORTED_SURVEY_INPUT_SUFFIXES = SUPPORTED_SURVEY_INPUT_SUFFIXES
_SUPPORTED_SURVEY_TABULAR_SUFFIXES = SUPPORTED_SURVEY_TABULAR_SUFFIXES
_survey_workflow_stage_service = SurveyWorkflowStageService(
    tabular_suffixes=_SUPPORTED_SURVEY_TABULAR_SUFFIXES,
)

try:
    from src.converters import survey as _survey

    MissingIdMappingError = _survey.MissingIdMappingError
    _NON_ITEM_TOPLEVEL_KEYS = _survey._NON_ITEM_TOPLEVEL_KEYS
    convert_survey_lsa_to_prism_dataset = _survey.convert_survey_lsa_to_prism_dataset
    convert_survey_file_to_prism_dataset = _survey.convert_survey_file_to_prism_dataset
    infer_lsa_metadata = _survey.infer_lsa_metadata
except (ImportError, AttributeError):
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
    )


def _detect_survey_version_contexts(*, uploaded_file, filename: str, **options) -> dict[str, Any]:
    from src.survey_input_checks import detect_version_contexts

    tmp_dir = tempfile.mkdtemp(prefix="prism_survey_upload_")
    try:
        input_path = Path(tmp_dir) / filename
        uploaded_file.save(str(input_path))
        return detect_version_contexts(input_path=input_path, app_root=app_root(), **options)
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
    """Studio's Convert triggers the same backend runner as `survey convert`."""
    from src.survey_template_sources import run_survey_with_template_sources

    app_root = Path(current_app.root_path).parent if has_app_context() else Path(__file__).resolve().parents[4]
    return run_survey_with_template_sources(
        converter_fn, library_dir=library_dir, fallback_project_path=fallback_project_path,
        app_root=app_root, log_fn=log_fn, **kwargs,
    )


def api_survey_prepare_workflow():
    """Run the survey setup phase without starting preview or conversion output."""
    try:
        preview_response = handle_api_survey_convert_preview(
            convert_survey_file_to_prism_dataset=convert_survey_file_to_prism_dataset,
            convert_survey_lsa_to_prism_dataset=convert_survey_lsa_to_prism_dataset,
            resolve_effective_library_path=_resolve_effective_library_path,
            run_survey_with_official_fallback=_run_survey_with_official_fallback,
            validate_project_templates_for_tasks=_validate_project_templates_for_tasks,
            build_template_completion_gate=_build_template_completion_gate,
            id_column_not_detected_error_cls=IdColumnNotDetectedError,
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
        validate_project_templates_for_tasks=_validate_project_templates_for_tasks,
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
        detect_survey_version_contexts=_detect_survey_version_contexts,
        id_column_not_detected_error_cls=IdColumnNotDetectedError,
        missing_id_mapping_error_cls=MissingIdMappingError,
        sessions_not_mapped_error_cls=SessionsNotMappedError,
    )


def api_survey_convert_preview():
    return handle_api_survey_convert_preview(
        convert_survey_file_to_prism_dataset=convert_survey_file_to_prism_dataset,
        convert_survey_lsa_to_prism_dataset=convert_survey_lsa_to_prism_dataset,
        resolve_effective_library_path=_resolve_effective_library_path,
        run_survey_with_official_fallback=_run_survey_with_official_fallback,
        validate_project_templates_for_tasks=_validate_project_templates_for_tasks,
        build_template_completion_gate=_build_template_completion_gate,
        id_column_not_detected_error_cls=IdColumnNotDetectedError,
        survey_value_out_of_bounds_error_cls=SurveyValueOutOfBoundsError,
        format_value_offset_confirmation_response=_format_value_offset_confirmation_response,
    )


def api_survey_convert():
    return handle_api_survey_convert(
        convert_survey_file_to_prism_dataset=convert_survey_file_to_prism_dataset,
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
        id_column_not_detected_error_cls=IdColumnNotDetectedError,
        missing_id_mapping_error_cls=MissingIdMappingError,
    )


def api_survey_convert_validate():
    return handle_api_survey_convert_validate(
        convert_survey_file_to_prism_dataset=convert_survey_file_to_prism_dataset,
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
        participants_mapping_candidates=participants_mapping_candidates,
        log_file_head=_log_file_head,
        resolve_validation_library_path=_resolve_validation_library_path,
        run_validation=run_validation,
        summarize_project_output_paths=summarize_project_output_paths,
        sanitize_jsonable=sanitize_jsonable,
        collect_multivariant_tasks_from_library=collect_multivariant_tasks_from_library,
    )


def api_survey_convert_validate_start():
    return handle_api_survey_convert_validate_start(
        convert_survey_file_to_prism_dataset=convert_survey_file_to_prism_dataset,
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
        participants_mapping_candidates=participants_mapping_candidates,
        log_file_head=_log_file_head,
        resolve_validation_library_path=_resolve_validation_library_path,
        run_validation=run_validation,
        summarize_project_output_paths=summarize_project_output_paths,
        sanitize_jsonable=sanitize_jsonable,
        collect_multivariant_tasks_from_library=collect_multivariant_tasks_from_library,
    )


def api_survey_convert_validate_status(job_id: str):
    return handle_api_survey_convert_validate_status(job_id)


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
