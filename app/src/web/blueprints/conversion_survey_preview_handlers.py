import shutil
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path

from flask import current_app, jsonify, request, session
from werkzeug.utils import secure_filename
from src.participants_paths import participants_mapping_candidates
from src.survey_workflow_service import SurveyWorkflowStageService

try:
    import defusedxml.ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

from src.web.survey_utils import list_survey_template_languages
from src.web.validation import run_validation
from .conversion_utils import (
    collect_multivariant_tasks_from_library,
    expected_delimiter_for_suffix,
    merge_selected_survey_filter,
    normalize_separator_option,
    parse_near_item_match_task_allowlist,
    parse_selected_survey_tasks,
    parse_task_value_offsets,
    parse_template_version_overrides,
    resolve_validation_library_path,
)

_resolve_effective_template_version_overrides: (
    Callable[..., list[dict[str, object]]] | None
) = None
try:
    from src.converters.survey import (
        _resolve_effective_template_version_overrides as _survey_resolve_effective_template_version_overrides,
    )

    _resolve_effective_template_version_overrides = (
        _survey_resolve_effective_template_version_overrides
    )
except ImportError:
    pass


def _get_effective_template_version_overrides(
    *,
    project_path: str | Path | None,
    template_version_overrides: object,
):
    if _resolve_effective_template_version_overrides is None:
        return template_version_overrides
    return _resolve_effective_template_version_overrides(
        project_path=project_path,
        template_version_overrides=template_version_overrides,
    )

_SUPPORTED_SURVEY_TABULAR_SUFFIXES = {
    ".xlsx",
    ".csv",
    ".tsv",
    ".sav",
    ".rds",
    ".rdata",
    ".rda",
}
_SUPPORTED_SURVEY_INPUT_SUFFIXES = _SUPPORTED_SURVEY_TABULAR_SUFFIXES | {".lsa"}
_SUPPORTED_SURVEY_INPUT_MESSAGE = (
    "Supported formats: .xlsx, .lsa, .csv, .tsv, .sav, .rds, .rdata, .rda"
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


def _collect_project_template_issues(
    *,
    validate_project_templates_for_tasks,
    tasks: list[str],
    project_path: Path | None,
    schema_version: str = "stable",
) -> list[dict[str, str]]:
    if not project_path:
        return []

    project_template_issues = validate_project_templates_for_tasks(
        tasks=tasks,
        project_path=str(project_path),
        schema_version=schema_version,
    )

    template_dir = project_path / "code" / "library" / "survey"
    if not template_dir.is_dir():
        return project_template_issues

    all_local_tasks = [
        path.stem.replace("survey-", "")
        for path in template_dir.glob("survey-*.json")
        if path.is_file()
    ]
    extra_tasks = [task for task in all_local_tasks if task not in tasks]
    if not extra_tasks:
        return project_template_issues

    extra_issues = validate_project_templates_for_tasks(
        tasks=extra_tasks,
        project_path=str(project_path),
        schema_version=schema_version,
    )
    return project_template_issues + extra_issues


def _collect_task_manual_review_payloads(
    *,
    tasks: list[str],
    validate_task_fn,
    survey_value_out_of_bounds_error_cls,
    format_value_offset_confirmation_response,
) -> dict[str, dict[str, object]]:
    payloads: dict[str, dict[str, object]] = {}

    # Per-task validation is only needed when a specific out-of-bounds
    # exception contract is configured. Otherwise this would duplicate full
    # validation runs with no actionable manual-review payloads.
    if not (
        isinstance(survey_value_out_of_bounds_error_cls, type)
        and issubclass(survey_value_out_of_bounds_error_cls, BaseException)
    ):
        return payloads

    for task in sorted({str(task).strip().lower() for task in tasks if str(task).strip()}):
        try:
            validate_task_fn(task)
        except Exception as error:
            if not (
                isinstance(survey_value_out_of_bounds_error_cls, type)
                and issubclass(survey_value_out_of_bounds_error_cls, BaseException)
                and isinstance(error, survey_value_out_of_bounds_error_cls)
            ):
                continue

            if callable(format_value_offset_confirmation_response):
                payload = format_value_offset_confirmation_response(error)
            else:
                payload = {
                    "error": "value_offset_manual_review_required",
                    "message": str(error),
                    "task": task,
                }
            payload_task = str(payload.get("task") or task).strip().lower()
            payloads[payload_task] = payload

    return payloads


def _build_survey_task_summaries(
    *,
    tasks: list[str],
    task_runs: dict[str, int | None] | None,
    selected_tasks: set[str] | None,
    manual_review_payloads: dict[str, dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    normalized_selected = {
        str(task).strip().lower() for task in (selected_tasks or set()) if str(task).strip()
    }
    normalized_reviews = manual_review_payloads or {}
    normalized_task_runs = task_runs or {}

    for task in sorted({str(task).strip().lower() for task in tasks if str(task).strip()}):
        summary: dict[str, object] = {
            "task": task,
            "selected": True if not normalized_selected else task in normalized_selected,
            "run_count": normalized_task_runs.get(task),
        }

        review_payload = normalized_reviews.get(task)
        if isinstance(review_payload, dict):
            out_of_range = {
                "message": review_payload.get("message"),
                "item_id": review_payload.get("item_id"),
                "raw_value": review_payload.get("raw_value"),
                "expected_levels": review_payload.get("expected_levels") or [],
                "suggested_offsets": review_payload.get("suggested_offsets") or [],
                "configured_offset": review_payload.get("configured_offset"),
                "offset_evidence": review_payload.get("offset_evidence"),
                "manual_action": review_payload.get("manual_action"),
            }
            summary["manual_review_required"] = True
            summary["out_of_range"] = out_of_range
        else:
            summary["manual_review_required"] = False

        summaries.append(summary)

    return summaries


def _is_prepared_workflow_request() -> bool:
    prepared_raw = (request.form.get("prepared_workflow") or "").strip().lower()
    return prepared_raw in {"1", "true", "yes", "on"}


def _format_workflow_preparation_stale_response(
    payload: dict[str, object],
    *,
    log_messages: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    normalized_payload = dict(payload or {})
    blocking_error = str(normalized_payload.get("error") or "").strip()

    if log_messages is not None:
        normalized_payload["log"] = log_messages

    if not _is_prepared_workflow_request() or not blocking_error:
        return normalized_payload

    message = str(normalized_payload.get("message") or "").strip()
    if not message:
        message = "Survey setup changed after preparation."

    if (
        blocking_error
        in {
            "near_item_match_confirmation_required",
            "value_offset_manual_review_required",
        }
        and "Run Preview again" not in message
    ):
        message = (
            f"{message} Run Preview again to refresh setup before continuing."
        )

    normalized_payload["blocking_error"] = blocking_error
    normalized_payload["error"] = "workflow_preparation_stale"
    normalized_payload["message"] = message
    return normalized_payload


def handle_api_survey_languages(participant_json_candidates):
    """List available languages for the selected survey template library folder."""
    library_path = (request.args.get("library_path") or "").strip()
    base_dir = Path(current_app.root_path)

    if not library_path:
        project_path = (session.get("current_project_path") or "").strip()
        if project_path:
            candidate = Path(project_path) / "code" / "library"
            try:
                candidate = candidate.expanduser().resolve()
            except (OSError, ValueError):
                candidate = Path(project_path).resolve() / "code" / "library"

            if candidate.exists() and candidate.is_dir():
                library_path = str(candidate)
            else:
                candidate = Path(project_path) / "library"
                try:
                    candidate = candidate.expanduser().resolve()
                except (OSError, ValueError):
                    candidate = Path(project_path).resolve() / "library"

                if candidate.exists() and candidate.is_dir():
                    library_path = str(candidate)

    if not library_path:
        candidates = [
            base_dir / "library" / "survey_i18n",
            base_dir / "official" / "library",
            base_dir.parent / "official" / "library",
            base_dir / "survey_library",
        ]

        for candidate_path in candidates:
            try:
                candidate_path = candidate_path.resolve()
                if candidate_path.exists() and (
                    any(candidate_path.glob("survey-*.json"))
                    or any(candidate_path.glob("*/survey-*.json"))
                ):
                    library_path = str(candidate_path)
                    break
            except (OSError, ValueError):
                continue

        if not library_path:
            library_path = str((base_dir / "survey_library").resolve())

    try:
        library_root = Path(library_path).resolve()
    except (OSError, ValueError):
        library_root = Path(library_path)

    structure_info = {
        "has_survey_folder": False,
        "has_biometrics_folder": False,
        "has_participants_json": False,
        "missing_items": [],
    }

    survey_dir = None
    for survey_candidate in [
        library_root / "library" / "survey",
        library_root / "survey",
        library_root,
    ]:
        if survey_candidate.exists() and survey_candidate.is_dir():
            if any(survey_candidate.glob("survey-*.json")):
                survey_dir = survey_candidate
                break

    if not survey_dir:
        survey_dir = library_root / "survey"

    biometrics_dir = None
    for biometrics_candidate in [
        library_root / "library" / "biometrics",
        library_root / "biometrics",
    ]:
        if biometrics_candidate.exists() and biometrics_candidate.is_dir():
            biometrics_dir = biometrics_candidate
            break

    if not biometrics_dir:
        biometrics_dir = library_root / "biometrics"

    participant_candidates = participant_json_candidates(library_root)

    structure_info["has_survey_folder"] = survey_dir.is_dir()
    structure_info["has_biometrics_folder"] = biometrics_dir.is_dir()
    structure_info["has_participants_json"] = any(
        candidate.is_file() for candidate in participant_candidates
    )

    if not structure_info["has_survey_folder"]:
        structure_info["missing_items"].append("survey/")
    if not structure_info["has_participants_json"]:
        structure_info["missing_items"].append(
            "participants.json (or ../participants.json)"
        )

    if survey_dir.is_dir():
        effective_survey_dir = str(survey_dir)
    else:
        effective_survey_dir = library_path

    print("[PRISM DEBUG] /api/survey-languages resolved library:")
    print(f"  - library_path: {library_path}")
    print(f"  - survey_dir: {survey_dir}")
    print(f"  - effective_survey_dir: {effective_survey_dir}")
    if survey_dir.is_dir():
        try:
            surveys = list(survey_dir.glob("survey-*.json"))
            print(f"  - found {len(surveys)} survey templates")
        except Exception as error:
            print(f"  - error listing surveys: {error}")

    langs, default, template_count, i18n_count = list_survey_template_languages(
        effective_survey_dir
    )
    return jsonify(
        {
            "languages": langs,
            "default": default,
            "library_path": effective_survey_dir,
            "template_count": template_count,
            "i18n_count": i18n_count,
            "structure": structure_info,
        }
    )


def handle_api_survey_convert_preview(
    *,
    convert_survey_xlsx_to_prism_dataset,
    convert_survey_lsa_to_prism_dataset,
    resolve_effective_library_path,
    run_survey_with_official_fallback,
    validate_project_templates_for_tasks,
    format_unmatched_groups_response,
    id_column_not_detected_error_cls,
    unmatched_groups_error_cls,
    build_template_completion_gate=None,
    survey_value_out_of_bounds_error_cls=None,
    format_value_offset_confirmation_response=None,
    force_validate_preview: bool = False,
):
    """Run a dry-run conversion to preview what will be created without writing files."""
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

    alias_filename = None
    if alias_upload is not None and alias_upload.filename:
        alias_filename = secure_filename(alias_upload.filename)
        alias_suffix = Path(alias_filename).suffix.lower()
        if alias_suffix and alias_suffix not in {".tsv", ".txt"}:
            return (
                jsonify({"error": "Alias file must be a .tsv or .txt mapping file"}),
                400,
            )

    id_map_filename = None
    if id_map_upload is not None and id_map_upload.filename:
        id_map_filename = secure_filename(id_map_upload.filename)
        id_map_suffix = Path(id_map_filename).suffix.lower()
        if id_map_suffix and id_map_suffix not in {".tsv", ".txt", ".csv"}:
            return (
                jsonify({"error": "ID map file must be a .tsv, .csv, or .txt file"}),
                400,
            )

    try:
        library_path = resolve_effective_library_path()
    except FileNotFoundError as error:
        return jsonify({"error": str(error)}), 400

    if (library_path / "survey").is_dir():
        survey_dir = library_path / "survey"
    else:
        survey_dir = library_path

    effective_survey_dir = survey_dir

    print(f"[PRISM DEBUG] DRY-RUN Preview using library: {effective_survey_dir}")
    print(f"[PRISM DEBUG] Session project path: {session.get('current_project_path')}")
    print(
        f"[PRISM DEBUG] Available templates: {list(effective_survey_dir.glob('survey-*.json'))}"
    )

    survey_templates = list(effective_survey_dir.glob("survey-*.json"))
    if not survey_templates:
        # Project library is empty — fall back to official/global library
        # so LSA imports can still match against official templates.
        from .conversion_survey_handlers import _resolve_official_survey_dir

        official_fallback = _resolve_official_survey_dir(
            session.get("current_project_path")
        )
        if official_fallback:
            effective_survey_dir = official_fallback
            survey_templates = list(effective_survey_dir.glob("survey-*.json"))

    if not survey_templates:
        return (
            jsonify({"error": f"No survey templates found in: {effective_survey_dir}"}),
            400,
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
    current_project_path = session.get("current_project_path")
    effective_template_version_overrides = _get_effective_template_version_overrides(
        project_path=current_project_path,
        template_version_overrides=template_version_overrides,
    )
    id_column = (request.form.get("id_column") or "").strip() or None
    session_column = (request.form.get("session_column") or "").strip() or None
    session_override = (request.form.get("session") or "").strip() or None
    run_column = (request.form.get("run_column") or "").strip() or None
    sheet = (request.form.get("sheet") or "0").strip() or 0
    unknown = (request.form.get("unknown") or "warn").strip() or "warn"
    language = (request.form.get("language") or "").strip() or None
    strict_levels_raw = (request.form.get("strict_levels") or "").strip().lower()
    strict_levels = strict_levels_raw in {"1", "true", "yes", "on"}
    allow_near_item_match_raw = (
        request.form.get("allow_near_item_match") or ""
    ).strip().lower()
    allow_near_item_match = allow_near_item_match_raw in {
        "1",
        "true",
        "yes",
        "on",
    }
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
        return (
            jsonify(
                {
                    "error": "No survey tasks selected for near matching.",
                }
            ),
            400,
        )
    validate_raw = (request.form.get("validate") or "").strip().lower()
    validate_preview = force_validate_preview or (
        True if validate_raw == "" else validate_raw in {"1", "true", "yes", "on"}
    )
    duplicate_handling = (request.form.get("duplicate_handling") or "error").strip()
    if duplicate_handling not in {"error", "keep_first", "keep_last", "sessions"}:
        duplicate_handling = "error"
    try:
        separator_option = normalize_separator_option(request.form.get("separator"))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    separator = expected_delimiter_for_suffix(suffix, separator_option)

    tmp_dir = tempfile.mkdtemp(prefix="prism_survey_preview_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        alias_path = None
        if alias_filename and alias_upload is not None:
            alias_path = tmp_dir_path / alias_filename
            alias_upload.save(str(alias_path))

        id_map_path = None
        if id_map_filename and id_map_upload is not None:
            id_map_path = tmp_dir_path / id_map_filename
            id_map_upload.save(str(id_map_path))

        project_path = session.get("current_project_path")
        if project_path:
            project_path = Path(project_path)
            if project_path.is_file():
                project_path = project_path.parent

            mapping_candidates = participants_mapping_candidates(project_path)

            for mapping_file in mapping_candidates:
                if mapping_file.exists():
                    dest_mapping = tmp_dir_path / "code" / "participants_mapping.json"
                    dest_mapping.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(mapping_file, dest_mapping)
                    print(
                        f"[PRISM DEBUG] Using participants mapping from: {mapping_file}"
                    )
                    break

        output_root = tmp_dir_path / "rawdata"

        if suffix in _SUPPORTED_SURVEY_TABULAR_SUFFIXES:
            result = run_survey_with_official_fallback(
                convert_survey_xlsx_to_prism_dataset,
                input_path=input_path,
                library_dir=str(effective_survey_dir),
                output_root=output_root,
                survey=survey_filter,
                id_column=id_column,
                session_column=session_column,
                run_column=run_column,
                session=session_override,
                sheet=sheet,
                unknown=unknown,
                dry_run=True,
                force=True,
                name="preview",
                authors=[],
                language=language,
                alias_file=alias_path,
                id_map_file=id_map_path,
                separator=separator,
                duplicate_handling=duplicate_handling,
                skip_participants=True,
                fallback_project_path=str(project_path) if project_path else None,
                template_version_overrides=effective_template_version_overrides,
                allow_near_item_match=allow_near_item_match,
                near_match_tasks=near_match_tasks,
                task_value_offsets=task_value_offsets,
            )
        elif suffix == ".lsa":
            result = run_survey_with_official_fallback(
                convert_survey_lsa_to_prism_dataset,
                input_path=input_path,
                library_dir=str(effective_survey_dir),
                output_root=output_root,
                survey=survey_filter,
                id_column=id_column,
                session_column=session_column,
                run_column=run_column,
                session=session_override,
                unknown=unknown,
                dry_run=True,
                force=True,
                name="preview",
                authors=[],
                language=language,
                alias_file=alias_path,
                id_map_file=id_map_path,
                strict_levels=True if strict_levels else None,
                duplicate_handling=duplicate_handling,
                skip_participants=True,
                project_path=str(project_path) if project_path else None,
                fallback_project_path=str(project_path) if project_path else None,
                template_version_overrides=template_version_overrides,
                allow_near_item_match=allow_near_item_match,
                near_match_tasks=near_match_tasks,
                task_value_offsets=task_value_offsets,
            )
        else:
            return jsonify({"error": "Unsupported file format"}), 400

        near_match_candidates = list(
            getattr(result, "near_match_candidates", []) or []
        )
        near_match_applied = bool(getattr(result, "near_match_applied", False))
        if near_match_candidates and not allow_near_item_match:
            near_match_payload = (
                SurveyWorkflowStageService.build_near_match_confirmation_payload(
                    near_match_candidates=near_match_candidates
                )
            )
            return (
                jsonify(
                    _format_workflow_preparation_stale_response(
                        near_match_payload
                    )
                ),
                409,
            )

        project_template_issues = _collect_project_template_issues(
            validate_project_templates_for_tasks=validate_project_templates_for_tasks,
            tasks=list(getattr(result, "tasks_included", []) or []),
            project_path=project_path,
            schema_version="stable",
        )

        validation_result = None
        workflow_gate = None
        task_manual_review_payloads: dict[str, dict[str, object]] = {}
        if project_template_issues:
            if callable(build_template_completion_gate):
                workflow_gate = build_template_completion_gate(
                    tasks=list(getattr(result, "tasks_included", []) or []),
                    issues=project_template_issues,
                )
            else:
                task_list = sorted(
                    {
                        str(task).strip().lower()
                        for task in (getattr(result, "tasks_included", []) or [])
                        if str(task).strip()
                    }
                )
                workflow_gate = {
                    "blocked": True,
                    "reason": "project_template_completion_required",
                    "tasks": task_list,
                    "issue_count": len(project_template_issues),
                }

        if validate_preview:
            validate_root = tmp_dir_path / "rawdata_validate"
            validate_root.mkdir(parents=True, exist_ok=True)

            def _validate_single_task(task_name: str):
                task_validate_root = validate_root / task_name
                task_validate_root.mkdir(parents=True, exist_ok=True)

                if suffix in _SUPPORTED_SURVEY_TABULAR_SUFFIXES:
                    return run_survey_with_official_fallback(
                        convert_survey_xlsx_to_prism_dataset,
                        input_path=input_path,
                        library_dir=str(effective_survey_dir),
                        output_root=task_validate_root,
                        survey=task_name,
                        id_column=id_column,
                        session_column=session_column,
                        run_column=run_column,
                        session=session_override,
                        sheet=sheet,
                        unknown=unknown,
                        dry_run=False,
                        force=True,
                        name="preview",
                        authors=[],
                        language=language,
                        alias_file=alias_path,
                        id_map_file=id_map_path,
                        separator=separator,
                        duplicate_handling=duplicate_handling,
                        skip_participants=True,
                        fallback_project_path=(
                            str(project_path) if project_path else None
                        ),
                        template_version_overrides=effective_template_version_overrides,
                        allow_near_item_match=allow_near_item_match,
                        near_match_tasks=near_match_tasks,
                        task_value_offsets=task_value_offsets,
                    )
                if suffix == ".lsa":
                    return run_survey_with_official_fallback(
                        convert_survey_lsa_to_prism_dataset,
                        input_path=input_path,
                        library_dir=str(effective_survey_dir),
                        output_root=task_validate_root,
                        survey=task_name,
                        id_column=id_column,
                        session_column=session_column,
                        run_column=run_column,
                        session=session_override,
                        unknown=unknown,
                        dry_run=False,
                        force=True,
                        name="preview",
                        authors=[],
                        language=language,
                        alias_file=alias_path,
                        id_map_file=id_map_path,
                        strict_levels=True if strict_levels else None,
                        duplicate_handling=duplicate_handling,
                        skip_participants=True,
                        project_path=str(project_path) if project_path else None,
                        fallback_project_path=(
                            str(project_path) if project_path else None
                        ),
                        template_version_overrides=template_version_overrides,
                        allow_near_item_match=allow_near_item_match,
                        near_match_tasks=near_match_tasks,
                        task_value_offsets=task_value_offsets,
                    )
                return None

            task_manual_review_payloads = _collect_task_manual_review_payloads(
                tasks=list(getattr(result, "tasks_included", []) or []),
                validate_task_fn=_validate_single_task,
                survey_value_out_of_bounds_error_cls=survey_value_out_of_bounds_error_cls,
                format_value_offset_confirmation_response=format_value_offset_confirmation_response,
            )

            if not task_manual_review_payloads:
                try:
                    if suffix in _SUPPORTED_SURVEY_TABULAR_SUFFIXES:
                        run_survey_with_official_fallback(
                            convert_survey_xlsx_to_prism_dataset,
                            input_path=input_path,
                            library_dir=str(effective_survey_dir),
                            output_root=validate_root,
                            survey=survey_filter,
                            id_column=id_column,
                            session_column=session_column,
                            run_column=run_column,
                            session=session_override,
                            sheet=sheet,
                            unknown=unknown,
                            dry_run=False,
                            force=True,
                            name="preview",
                            authors=[],
                            language=language,
                            alias_file=alias_path,
                            id_map_file=id_map_path,
                            separator=separator,
                            duplicate_handling=duplicate_handling,
                            skip_participants=True,
                            fallback_project_path=(
                                str(project_path) if project_path else None
                            ),
                            template_version_overrides=effective_template_version_overrides,
                            allow_near_item_match=allow_near_item_match,
                            near_match_tasks=near_match_tasks,
                            task_value_offsets=task_value_offsets,
                        )
                    elif suffix == ".lsa":
                        run_survey_with_official_fallback(
                            convert_survey_lsa_to_prism_dataset,
                            input_path=input_path,
                            library_dir=str(effective_survey_dir),
                            output_root=validate_root,
                            survey=survey_filter,
                            id_column=id_column,
                            session_column=session_column,
                            run_column=run_column,
                            session=session_override,
                            unknown=unknown,
                            dry_run=False,
                            force=True,
                            name="preview",
                            authors=[],
                            language=language,
                            alias_file=alias_path,
                            id_map_file=id_map_path,
                            strict_levels=True if strict_levels else None,
                            duplicate_handling=duplicate_handling,
                            skip_participants=True,
                            project_path=str(project_path) if project_path else None,
                            fallback_project_path=(
                                str(project_path) if project_path else None
                            ),
                            template_version_overrides=template_version_overrides,
                            allow_near_item_match=allow_near_item_match,
                            near_match_tasks=near_match_tasks,
                            task_value_offsets=task_value_offsets,
                        )

                    v_res = run_validation(
                        str(validate_root),
                        schema_version="stable",
                        library_path=str(
                            resolve_validation_library_path(
                                project_path=(str(project_path) if project_path else None),
                                fallback_library_root=library_path,
                            )
                        ),
                        project_path=(str(project_path) if project_path else None),
                    )
                    if v_res and isinstance(v_res, tuple):
                        issues, stats = v_res

                        from src.web.reporting_utils import format_validation_results

                        formatted = format_validation_results(
                            issues, stats, str(validate_root)
                        )

                        validation_result = {"formatted": formatted}
                        validation_result.update(formatted)
                        if project_template_issues:
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
                except Exception as validation_error:
                    if (
                        isinstance(survey_value_out_of_bounds_error_cls, type)
                        and issubclass(
                            survey_value_out_of_bounds_error_cls, BaseException
                        )
                        and isinstance(
                            validation_error, survey_value_out_of_bounds_error_cls
                        )
                    ):
                        validation_confirmation_payload: dict[str, object]
                        if callable(format_value_offset_confirmation_response):
                            validation_confirmation_payload = format_value_offset_confirmation_response(
                                validation_error
                            )
                        else:
                            validation_confirmation_payload = {
                                "error": "value_offset_manual_review_required",
                                "message": str(validation_error),
                            }
                        task_key = str(
                            validation_confirmation_payload.get("task") or ""
                        ).strip().lower()
                        if task_key:
                            task_manual_review_payloads[task_key] = (
                                validation_confirmation_payload
                            )
                    else:
                        validation_result = {"error": str(validation_error)}

        survey_tasks = _build_survey_task_summaries(
            tasks=list(getattr(result, "tasks_included", []) or []),
            task_runs=getattr(result, "task_runs", {}) or {},
            selected_tasks=selected_tasks,
            manual_review_payloads=task_manual_review_payloads,
        )

        response_data = {
            "preview": result.dry_run_preview,
            "tasks_included": result.tasks_included,
            "survey_tasks": survey_tasks,
            "unknown_columns": result.unknown_columns,
            "missing_items_by_task": result.missing_items_by_task,
            "id_column": result.id_column,
            "session_column": result.session_column,
            "run_column": result.run_column,
            "detected_sessions": result.detected_sessions,
            "conversion_warnings": result.conversion_warnings,
            "task_runs": result.task_runs,
            "multivariant_tasks": collect_multivariant_tasks_from_library(
                library_dir=effective_survey_dir,
                tasks=list(result.tasks_included or []),
                selected_versions=effective_template_version_overrides,
            ),
        }

        if getattr(result, "participant_registry_warning", None):
            response_data["participant_registry_warning"] = (
                result.participant_registry_warning
            )

        if near_match_candidates:
            response_data["near_match_candidates"] = near_match_candidates
        if near_match_applied:
            response_data["near_match_applied"] = True
        if getattr(result, "applied_value_offsets", None):
            response_data["applied_value_offsets"] = result.applied_value_offsets
        if getattr(result, "value_offset_application_counts", None):
            response_data["value_offset_application_counts"] = (
                result.value_offset_application_counts
            )

        if validation_result is not None:
            response_data["validation"] = validation_result

        if workflow_gate is not None:
            response_data["workflow_gate"] = workflow_gate
            response_data["requires_template_completion"] = True

        conv_summary = {}
        if result.tasks_included:
            conv_summary["tasks_included"] = result.tasks_included
        if survey_tasks:
            conv_summary["survey_tasks"] = survey_tasks
        if result.task_runs:
            conv_summary["task_runs"] = result.task_runs
        if result.unknown_columns:
            conv_summary["unknown_columns"] = result.unknown_columns
        if getattr(result, "tool_columns", None):
            conv_summary["tool_columns"] = result.tool_columns
        if result.conversion_warnings:
            conv_summary["conversion_warnings"] = result.conversion_warnings
        if getattr(result, "participant_registry_warning", None):
            conv_summary["participant_registry_warning"] = (
                result.participant_registry_warning
            )
        if near_match_candidates:
            conv_summary["near_match_candidates"] = near_match_candidates
        if near_match_applied:
            conv_summary["near_match_applied"] = True
        if getattr(result, "applied_value_offsets", None):
            conv_summary["applied_value_offsets"] = result.applied_value_offsets
        if getattr(result, "value_offset_application_counts", None):
            conv_summary["value_offset_application_counts"] = (
                result.value_offset_application_counts
            )

        if result.template_matches:
            response_data["template_matches"] = result.template_matches
            conv_summary["template_matches"] = result.template_matches

        if conv_summary:
            response_data["conversion_summary"] = conv_summary

        return jsonify(response_data)

    except Exception as error:
        if (
            isinstance(survey_value_out_of_bounds_error_cls, type)
            and issubclass(survey_value_out_of_bounds_error_cls, BaseException)
            and isinstance(error, survey_value_out_of_bounds_error_cls)
        ):
            error_confirmation_payload: dict[str, object]
            if callable(format_value_offset_confirmation_response):
                error_confirmation_payload = format_value_offset_confirmation_response(
                    error
                )
            else:
                error_confirmation_payload = {
                    "error": "value_offset_manual_review_required",
                    "message": str(error),
                }
            return (
                jsonify(
                    _format_workflow_preparation_stale_response(
                        error_confirmation_payload
                    )
                ),
                409,
            )

        if (
            isinstance(id_column_not_detected_error_cls, type)
            and issubclass(id_column_not_detected_error_cls, BaseException)
            and isinstance(error, id_column_not_detected_error_cls)
        ):
            return (
                jsonify(
                    {
                        "error": "id_column_required",
                        "message": str(error),
                        "columns": getattr(error, "available_columns", []),
                    }
                ),
                409,
            )

        if (
            isinstance(unmatched_groups_error_cls, type)
            and issubclass(unmatched_groups_error_cls, BaseException)
            and isinstance(error, unmatched_groups_error_cls)
        ):
            return jsonify(format_unmatched_groups_response(error)), 409

        if isinstance(error, zipfile.BadZipFile):
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

        if isinstance(error, ET.ParseError):
            return (
                jsonify(
                    {
                        "error": f"❌ XML parsing error in LimeSurvey archive.\n\n"
                        f"The survey structure file (.lss) inside the archive is malformed.\n\n"
                        f"Technical details: {str(error)}\n\n"
                        f"💡 Solutions:\n"
                        f"   • Re-export the survey from LimeSurvey\n"
                        f"   • Check for special characters in question text that might cause XML issues"
                    }
                ),
                400,
            )

        error_msg = str(error)
        if "No module named" in error_msg:
            return (
                jsonify(
                    {
                        "error": "❌ Missing required Python module.\n\n"
                        f"{error_msg}\n\n"
                        "Please run setup or install required dependencies."
                    }
                ),
                500,
            )

        return jsonify({"error": error_msg}), 500

    finally:
        try:
            shutil.rmtree(tmp_dir)
        except Exception:
            pass
