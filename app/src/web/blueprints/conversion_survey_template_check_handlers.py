from pathlib import Path

from flask import jsonify, request, session
from werkzeug.utils import secure_filename
from src.survey_input_checks import check_project_templates, matching_summary


def handle_api_survey_check_project_templates(
    *,
    require_existing_project_root,
    resolve_uploaded_or_source_file,
    survey_workflow_stage_service,
    normalize_separator_option,
    supported_survey_input_suffixes,
    supported_survey_input_message,
    infer_tasks_against_official_templates,
    id_column_not_detected_error_cls,
    missing_id_mapping_error_cls,
    validate_project_templates_for_tasks,
):
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

    uploaded_file, upload_error = resolve_uploaded_or_source_file(
        field_names=("excel", "file")
    )
    parsed_stage_fields = survey_workflow_stage_service.parse_stage_form_fields(
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

    inferred = None
    input_name = None

    if uploaded_file and getattr(uploaded_file, "filename", ""):
        filename = secure_filename(uploaded_file.filename)
        suffix = Path(filename).suffix.lower()
        if suffix not in supported_survey_input_suffixes:
            return jsonify({"error": supported_survey_input_message}), 400

        input_name = filename
        try:
            inferred = infer_tasks_against_official_templates(
                uploaded_file=uploaded_file,
                filename=filename,
                project_path=str(project_root),
                id_column=id_column,
                session_column=session_column,
                sheet=sheet,
                duplicate_handling=duplicate_handling,
                separator_option=separator_option,
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
        except Exception as error:
            inferred = {"match_error": str(error)}
    elif upload_error and upload_error != "Missing input file":
        return jsonify({"error": upload_error}), 400

    return jsonify(
        check_project_templates(
            project_root,
            matching_summary(input_name, inferred),
            validate=validate_project_templates_for_tasks,
        )
    )
