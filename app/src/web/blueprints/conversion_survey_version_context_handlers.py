from pathlib import Path

from flask import jsonify, request
from werkzeug.utils import secure_filename


def handle_api_survey_detect_version_context(
    *,
    resolve_uploaded_or_source_file,
    supported_survey_input_suffixes,
    supported_survey_input_message,
    resolve_requested_project_root,
    parse_selected_survey_tasks,
    merge_selected_survey_filter,
    parse_template_version_overrides,
    parse_near_item_match_task_allowlist,
    parse_task_value_offsets,
    survey_workflow_stage_service,
    normalize_separator_option,
    get_effective_template_version_overrides,
    resolve_effective_library_path,
    resolve_official_survey_dir,
    detect_survey_version_contexts,
    id_column_not_detected_error_cls,
    missing_id_mapping_error_cls,
    unmatched_groups_error_cls,
    format_unmatched_groups_response,
):
    uploaded_file, upload_error = resolve_uploaded_or_source_file(
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
    if suffix not in supported_survey_input_suffixes:
        return jsonify({"error": supported_survey_input_message}), 400

    try:
        requested_project_root = resolve_requested_project_root(require_project=False)
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

    parsed_stage_fields = survey_workflow_stage_service.parse_stage_form_fields(
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
    effective_template_version_overrides = get_effective_template_version_overrides(
        project_path=project_path,
        template_version_overrides=template_version_overrides,
    )

    try:
        library_path = resolve_effective_library_path()
    except FileNotFoundError:
        library_path = resolve_official_survey_dir(project_path)
        if not library_path:
            return (
                jsonify({"error": "No survey template library could be resolved."}),
                400,
            )

    try:
        context = detect_survey_version_contexts(
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
    except id_column_not_detected_error_cls as error:
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
    except missing_id_mapping_error_cls as error:
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
    except unmatched_groups_error_cls as error:
        return jsonify(format_unmatched_groups_response(error)), 409
    except Exception as error:
        return jsonify({"error": str(error)}), 400

    return jsonify({"ok": True, **context})