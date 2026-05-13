from pathlib import Path

from flask import jsonify, request, session
from werkzeug.utils import secure_filename


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
    unmatched_groups_error_cls,
    format_unmatched_groups_response,
    validate_project_templates_for_tasks,
    collect_project_template_warnings_for_tasks,
    collect_multivariant_tasks_from_library,
    get_effective_template_version_overrides,
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
        if suffix not in supported_survey_input_suffixes:
            return jsonify({"error": supported_survey_input_message}), 400

        matching_summary["input_file"] = filename
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
            matching_summary["match_error"] = str(error)
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

    issues = validate_project_templates_for_tasks(
        tasks=tasks,
        project_path=str(project_root),
        schema_version="stable",
    )
    warnings = collect_project_template_warnings_for_tasks(
        tasks=local_templates,
        project_path=str(project_root),
    )
    multivariant_tasks = collect_multivariant_tasks_from_library(
        library_dir=project_root / "code" / "library" / "survey",
        tasks=tasks,
        selected_versions=get_effective_template_version_overrides(
            project_path=project_root,
            template_version_overrides=None,
        ),
    )

    if issues:
        gate = {
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