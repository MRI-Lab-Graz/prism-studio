import shutil
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any

from flask import jsonify, request
from werkzeug.utils import secure_filename
from src.datalad_project_copy import copy_files_into_project
from src.system_files import filter_system_files
from src.survey_workflow_service import SurveyWorkflowStageService
from .conversion_job_store import ConversionJobStore

_survey_convert_job_store = ConversionJobStore(log_level_key="level")


def handle_api_survey_convert_validate(
    *,
    convert_survey_xlsx_to_prism_dataset,
    convert_survey_lsa_to_prism_dataset,
    resolve_uploaded_or_source_file,
    resolve_requested_project_root,
    supported_survey_input_suffixes,
    supported_survey_input_message,
    resolve_effective_library_path,
    survey_workflow_stage_service,
    resolve_official_survey_dir,
    parse_selected_survey_tasks,
    merge_selected_survey_filter,
    parse_template_version_overrides,
    get_effective_template_version_overrides,
    parse_near_item_match_task_allowlist,
    parse_task_value_offsets,
    normalize_separator_option,
    expected_delimiter_for_suffix,
    survey_workflow_stage_options_cls,
    run_survey_with_official_fallback,
    validate_project_templates_for_tasks,
    build_template_completion_gate,
    format_workflow_preparation_stale_response,
    format_value_offset_confirmation_response,
    is_value_offset_confirmation_error,
    id_column_not_detected_error_cls,
    missing_id_mapping_error_cls,
    unmatched_groups_error_cls,
    format_unmatched_groups_response,
    participants_mapping_candidates,
    log_file_head,
    resolve_validation_library_path,
    run_validation,
    cleanup_stale_tool_limesurvey_sidecars,
    iter_session_registration_values,
    extract_tasks_from_output,
    register_session_in_project,
    sync_project_survey_recipe_offsets,
    summarize_project_output_paths,
    sanitize_jsonable,
    collect_multivariant_tasks_from_library,
):
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

    uploaded_file, upload_error = resolve_uploaded_or_source_file(
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
    if suffix not in supported_survey_input_suffixes:
        return (
            jsonify({"error": supported_survey_input_message, "log": log_messages}),
            400,
        )

    try:
        project_root = resolve_requested_project_root(require_project=True)
    except (ValueError, FileNotFoundError) as error:
        return jsonify({"error": str(error), "log": log_messages}), 400

    current_project_path = str(project_root) if project_root else None

    try:
        library_path = resolve_effective_library_path()
    except FileNotFoundError as error:
        return jsonify({"error": str(error), "log": log_messages}), 400

    try:
        effective_survey_dir = survey_workflow_stage_service.resolve_effective_survey_dir(
            library_path=library_path,
            fallback_project_path=current_project_path,
            resolve_official_survey_dir=resolve_official_survey_dir,
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
    effective_template_version_overrides = get_effective_template_version_overrides(
        project_path=current_project_path,
        template_version_overrides=template_version_overrides,
    )
    parsed_stage_fields = survey_workflow_stage_service.parse_stage_form_fields(
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
            add_log(f"Using ID map file: {id_map_filename} ({saved_size} bytes)", "info")

        fallback_project_path = current_project_path
        preflight_output_root = tmp_dir_path / "preflight_rawdata"
        try:
            preflight_result = survey_workflow_stage_service.run_stage(
                workflow_runner=run_survey_with_official_fallback,
                tabular_converter=convert_survey_xlsx_to_prism_dataset,
                lsa_converter=convert_survey_lsa_to_prism_dataset,
                options=survey_workflow_stage_options_cls(
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
        except id_column_not_detected_error_cls as error:
            add_log(f"ID column not detected: {str(error)}", "error")
            return (
                jsonify(
                    {
                        "error": "id_column_required",
                        "message": str(error),
                        "columns": error.available_columns,
                        "log": log_messages,
                    }
                ),
                409,
            )
        except missing_id_mapping_error_cls as error:
            add_log(f"ID mapping incomplete: {str(error)}", "error")
            return (
                jsonify(
                    {
                        "error": "id_mapping_incomplete",
                        "message": str(error),
                        "missing_ids": error.missing_ids,
                        "suggestions": error.suggestions,
                        "log": log_messages,
                    }
                ),
                409,
            )
        except unmatched_groups_error_cls as error:
            add_log(f"Unmatched groups: {str(error)}", "error")
            return jsonify(format_unmatched_groups_response(error, log_messages)), 409
        except Exception as error:
            if is_value_offset_confirmation_error(error):
                add_log(
                    "Out-of-range survey values need review before conversion can continue.",
                    "warning",
                )
                return (
                    jsonify(
                        format_workflow_preparation_stale_response(
                            format_value_offset_confirmation_response(error, log_messages),
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
            near_match_payload = survey_workflow_stage_service.build_near_match_confirmation_payload(
                near_match_candidates=preflight_near_match_candidates
            )
            return (
                jsonify(
                    format_workflow_preparation_stale_response(
                        near_match_payload,
                        log_messages=log_messages,
                    )
                ),
                409,
            )

        preflight_tasks = list(getattr(preflight_result, "tasks_included", []) or [])
        project_template_issues = validate_project_templates_for_tasks(
            tasks=preflight_tasks,
            project_path=fallback_project_path,
            schema_version="stable",
        )
        if project_template_issues:
            workflow_gate = build_template_completion_gate(
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
            template_gate_payload = survey_workflow_stage_service.build_template_completion_required_payload(
                workflow_gate=workflow_gate,
                template_issues=project_template_issues,
            )
            return (
                jsonify(
                    format_workflow_preparation_stale_response(
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
                    add_log(f"Using participants mapping from: {mapping_file.name}", "info")
                    break

        output_root = tmp_dir_path / "rawdata"
        output_root.mkdir(parents=True, exist_ok=True)
        add_log("Starting data conversion...", "info")
        copied_output_paths: list[Path] = []

        try:
            log_file_head(input_path, suffix, add_log)
        except Exception as head_error:
            add_log(f"Header preview failed: {head_error}", "warning")

        if strict_levels:
            add_log("Strict Levels Validation: enabled", "info")

        try:
            if suffix == ".lsa":
                add_log(f"Processing LimeSurvey archive: {filename}", "info")
            convert_result = survey_workflow_stage_service.run_stage(
                workflow_runner=run_survey_with_official_fallback,
                tabular_converter=convert_survey_xlsx_to_prism_dataset,
                lsa_converter=convert_survey_lsa_to_prism_dataset,
                options=survey_workflow_stage_options_cls(
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
        except id_column_not_detected_error_cls as error:
            add_log(f"ID column not detected: {str(error)}", "error")
            return (
                jsonify(
                    {
                        "error": "id_column_required",
                        "message": str(error),
                        "columns": error.available_columns,
                        "log": log_messages,
                    }
                ),
                409,
            )
        except missing_id_mapping_error_cls as error:
            add_log(f"ID mapping incomplete: {str(error)}", "error")
            return (
                jsonify(
                    {
                        "error": "id_mapping_incomplete",
                        "message": str(error),
                        "missing_ids": error.missing_ids,
                        "suggestions": error.suggestions,
                        "log": log_messages,
                    }
                ),
                409,
            )
        except unmatched_groups_error_cls as error:
            add_log(f"Unmatched groups: {str(error)}", "error")
            return jsonify(format_unmatched_groups_response(error, log_messages)), 409
        except Exception as conversion_error:
            if is_value_offset_confirmation_error(conversion_error):
                add_log(
                    "Out-of-range survey values need review before conversion can continue.",
                    "warning",
                )
                return (
                    jsonify(
                        format_workflow_preparation_stale_response(
                            format_value_offset_confirmation_response(
                                conversion_error,
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
                f"\n[CONVERSION ERROR] {type(conversion_error).__name__}: {str(conversion_error)}",
                file=sys.stderr,
            )
            print(f"[FULL TRACEBACK]\n{full_trace}", file=sys.stderr)
            add_log(
                f"Conversion engine failed: {type(conversion_error).__name__}: {str(conversion_error)}",
                "error",
            )
            raise conversion_error

        if getattr(convert_result, "missing_cells_by_subject", None):
            missing_counts = {
                subject_id: count
                for subject_id, count in convert_result.missing_cells_by_subject.items()
                if count > 0
            }
            if missing_counts:
                conversion_warnings.append(
                    f"Missing responses normalized: {sum(missing_counts.values())} cells."
                )

        if getattr(convert_result, "conversion_warnings", None):
            conversion_warnings.extend(convert_result.conversion_warnings)

        add_log("Running validation...", "info")
        validation_result = {"errors": [], "warnings": [], "summary": {}}
        if request.form.get("validate") == "true":
            try:
                validation_library_root = resolve_validation_library_path(
                    project_path=current_project_path,
                    fallback_library_root=library_path,
                )
                validation_output = run_validation(
                    str(output_root),
                    schema_version="stable",
                    library_path=str(validation_library_root),
                    project_path=current_project_path,
                )
                if validation_output and isinstance(validation_output, tuple):
                    issues, stats = validation_output

                    from src.web.reporting_utils import format_validation_results

                    formatted = format_validation_results(
                        issues, stats, str(output_root)
                    )
                    validation_result = {"formatted": formatted}
                    validation_result.update(formatted)

                    total_err = formatted.get("summary", {}).get("total_errors", 0)
                    total_warn = formatted.get("summary", {}).get("total_warnings", 0)

                    if total_err > 0:
                        add_log(f"✗ Validation failed with {total_err} error(s)", "error")
                        count = 0
                        for group in formatted.get("errors", []):
                            for file_issue in group.get("files", []):
                                if count < 20:
                                    message = file_issue["message"]
                                    if ": " in message:
                                        message = message.split(": ", 1)[1]
                                    add_log(f"  - {message}", "error")
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

                    project_template_issues = validate_project_templates_for_tasks(
                        tasks=(
                            convert_result.tasks_included
                            if getattr(convert_result, "tasks_included", None)
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
                            add_log(f"  - {Path(issue['file']).name}: {issue['message']}", "warning")
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
                                {"file": issue["file"], "message": issue["message"]}
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
                                    f"{Path(issue['file']).name}: {issue['message']}"
                                    for issue in project_template_issues
                                ]
                            )
                        validation_result.setdefault("summary", {}).setdefault(
                            "total_errors", 0
                        )
                        validation_result["summary"]["total_errors"] += len(
                            project_template_issues
                        )
            except Exception as validation_error:
                validation_result["warnings"].append(
                    f"Validation error: {str(validation_error)}"
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
                        {"file": filename, "message": warning}
                        for warning in conversion_warnings
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
        datalad_copy = None

        if save_to_project:
            dest_root = project_root
            dest_root.mkdir(parents=True, exist_ok=True)
            add_log(
                f"Saving output to project: {project_root.name} (into project root)",
                "info",
            )

            copy_pairs: list[tuple[Path, Path]] = []
            output_rel_paths: set[str] = set()
            for item in output_root.rglob("*"):
                if item.is_file():
                    if not filter_system_files([item.name]):
                        continue
                    rel_path = item.relative_to(output_root)
                    dest = dest_root / rel_path
                    output_rel_paths.add(dest.relative_to(project_root).as_posix())
                    copy_pairs.append((item, dest))

            if archive_sourcedata:
                sourcedata_dir = project_root / "sourcedata"
                archive_dest = sourcedata_dir / filename
                copy_pairs.append((input_path, archive_dest))

            try:
                copy_result = copy_files_into_project(
                    dataset_root=project_root,
                    copy_pairs=copy_pairs,
                    run_message="PRISM: Copy converted survey files into project",
                )
            except ValueError as error:
                return jsonify({"error": str(error), "log": log_messages}), 400

            copied_rel_paths = [
                str(path) for path in list(copy_result.get("copied_paths") or [])
            ]
            copied_output_paths = [
                project_root / rel_path
                for rel_path in copied_rel_paths
                if rel_path in output_rel_paths
            ]
            datalad_copy = copy_result.get("datalad")

            cleanup_stale_tool_limesurvey_sidecars(
                copied_output_paths=copied_output_paths,
                source_suffix=suffix,
                log_fn=add_log,
            )
            add_log("Project updated successfully!", "success")

            if archive_sourcedata:
                add_log(f"Archived original file to sourcedata/{filename}", "info")

            registration_sessions = iter_session_registration_values(
                session_override=session_override,
                detected_sessions=list(getattr(convert_result, "detected_sessions", []) or []),
            )
            if registration_sessions:
                conv_type = "survey-lsa" if suffix == ".lsa" else "survey-xlsx"
                tasks_out = (
                    convert_result.tasks_included
                    if getattr(convert_result, "tasks_included", None)
                    else extract_tasks_from_output(output_root)
                )
                for registration_session in registration_sessions:
                    register_session_in_project(
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

            if callable(sync_project_survey_recipe_offsets):
                applied_offsets = getattr(convert_result, "applied_value_offsets", {}) or {}
                offset_application_counts = (
                    getattr(convert_result, "value_offset_application_counts", {}) or {}
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
                            add_log(f"Recipe offset sync warning: {sync_error}", "warning")
                    except Exception as sync_error:
                        add_log(f"Recipe offset sync warning: {sync_error}", "warning")
        else:
            copied_output_paths = []

        response_payload = {
            "success": True,
            "log": log_messages,
            "validation": validation_result,
            "project_saved": bool(copied_output_paths),
            "project_output_root": str(project_root) if copied_output_paths else None,
            "project_output_paths": [],
            "project_output_path": None,
            "project_output_count": len(copied_output_paths),
            "datalad": datalad_copy,
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
            response_payload["project_output_path"] = output_paths[0] if output_paths else None

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
        response_payload["multivariant_tasks"] = collect_multivariant_tasks_from_library(
            library_dir=effective_survey_dir,
            tasks=list(getattr(convert_result, "tasks_included", []) or []),
            selected_versions=effective_template_version_overrides,
        )

        return jsonify(sanitize_jsonable(response_payload))
    except Exception as error:
        return jsonify({"error": str(error), "log": log_messages}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def handle_api_survey_convert_validate_start(
    *,
    convert_survey_xlsx_to_prism_dataset,
    convert_survey_lsa_to_prism_dataset,
    resolve_uploaded_or_source_file,
    resolve_requested_project_root,
    supported_survey_input_suffixes,
    supported_survey_input_message,
    resolve_effective_library_path,
    survey_workflow_stage_service,
    resolve_official_survey_dir,
    parse_selected_survey_tasks,
    merge_selected_survey_filter,
    parse_template_version_overrides,
    get_effective_template_version_overrides,
    parse_near_item_match_task_allowlist,
    parse_task_value_offsets,
    normalize_separator_option,
    expected_delimiter_for_suffix,
    survey_workflow_stage_options_cls,
    run_survey_with_official_fallback,
    validate_project_templates_for_tasks,
    build_template_completion_gate,
    format_workflow_preparation_stale_response,
    format_value_offset_confirmation_response,
    is_value_offset_confirmation_error,
    id_column_not_detected_error_cls,
    missing_id_mapping_error_cls,
    unmatched_groups_error_cls,
    format_unmatched_groups_response,
    participants_mapping_candidates,
    log_file_head,
    resolve_validation_library_path,
    run_validation,
    cleanup_stale_tool_limesurvey_sidecars,
    iter_session_registration_values,
    extract_tasks_from_output,
    register_session_in_project,
    sync_project_survey_recipe_offsets,
    summarize_project_output_paths,
    sanitize_jsonable,
    collect_multivariant_tasks_from_library,
):
    """Start an async survey conversion+validate job and return its job id for polling."""
    if (
        not convert_survey_xlsx_to_prism_dataset
        and not convert_survey_lsa_to_prism_dataset
    ):
        return jsonify({"error": "Survey conversion module not available"}), 500

    upfront_logs: list[dict[str, str]] = []

    def add_log(message, level="info"):
        upfront_logs.append({"message": message, "level": level})

    uploaded_file, upload_error = resolve_uploaded_or_source_file(
        field_names=("excel", "file")
    )
    alias_upload = request.files.get("alias") or request.files.get("alias_file")
    id_map_upload = request.files.get("id_map")

    if uploaded_file is None or not getattr(uploaded_file, "filename", ""):
        return (
            jsonify({"error": upload_error or "Missing input file", "log": upfront_logs}),
            400,
        )

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in supported_survey_input_suffixes:
        return (
            jsonify({"error": supported_survey_input_message, "log": upfront_logs}),
            400,
        )

    try:
        project_root = resolve_requested_project_root(require_project=True)
    except (ValueError, FileNotFoundError) as error:
        return jsonify({"error": str(error), "log": upfront_logs}), 400

    current_project_path = str(project_root) if project_root else None

    try:
        library_path = resolve_effective_library_path()
    except FileNotFoundError as error:
        return jsonify({"error": str(error), "log": upfront_logs}), 400

    try:
        effective_survey_dir = survey_workflow_stage_service.resolve_effective_survey_dir(
            library_path=library_path,
            fallback_project_path=current_project_path,
            resolve_official_survey_dir=resolve_official_survey_dir,
        )
    except FileNotFoundError as error:
        return jsonify({"error": str(error), "log": upfront_logs}), 400

    raw_survey_filter = (request.form.get("survey") or "").strip() or None
    try:
        selected_tasks = parse_selected_survey_tasks(
            request.form.get("selected_tasks")
        )
        survey_filter = merge_selected_survey_filter(raw_survey_filter, selected_tasks)
    except ValueError as error:
        return jsonify({"error": str(error), "log": upfront_logs}), 400
    try:
        template_version_overrides = parse_template_version_overrides(
            request.form.get("template_versions")
        )
    except ValueError as error:
        return jsonify({"error": str(error), "log": upfront_logs}), 400
    effective_template_version_overrides = get_effective_template_version_overrides(
        project_path=current_project_path,
        template_version_overrides=template_version_overrides,
    )
    parsed_stage_fields = survey_workflow_stage_service.parse_stage_form_fields(
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
        return jsonify({"error": str(error), "log": upfront_logs}), 400
    try:
        task_value_offsets = parse_task_value_offsets(request.form.get("value_offsets"))
    except ValueError as error:
        return jsonify({"error": str(error), "log": upfront_logs}), 400
    if allow_near_item_match and near_match_tasks is not None and not near_match_tasks:
        return (
            jsonify(
                {
                    "error": "No survey tasks selected for near matching.",
                    "log": upfront_logs,
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
                    "log": upfront_logs,
                }
            ),
            400,
        )

    if current_project_path is None:
        return (
            jsonify(
                {
                    "error": "No project selected. Load a project before converting survey data.",
                    "log": upfront_logs,
                }
            ),
            400,
        )
    try:
        separator_option = normalize_separator_option(request.form.get("separator"))
    except ValueError as error:
        return jsonify({"error": str(error), "log": upfront_logs}), 400
    separator = expected_delimiter_for_suffix(suffix, separator_option)

    validate_requested = request.form.get("validate") == "true"
    prepared_workflow_flag = SurveyWorkflowStageService.parse_prepared_workflow_flag(
        request.form.get("prepared_workflow")
    )

    def format_workflow_preparation_stale_response_bound(payload, *, log_messages=None):
        return SurveyWorkflowStageService.format_workflow_preparation_stale_response(
            payload=payload,
            prepared_workflow=prepared_workflow_flag,
            log_messages=log_messages,
        )

    tmp_dir = tempfile.mkdtemp(prefix="prism_survey_convert_validate_job_")
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
            add_log(f"Using ID map file: {id_map_filename} ({saved_size} bytes)", "info")
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise

    config: dict[str, Any] = {
        "tmp_dir": tmp_dir,
        "input_path": input_path,
        "alias_path": alias_path,
        "id_map_path": id_map_path,
        "filename": filename,
        "suffix": suffix,
        "project_root": project_root,
        "current_project_path": current_project_path,
        "library_path": library_path,
        "effective_survey_dir": effective_survey_dir,
        "survey_filter": survey_filter,
        "effective_template_version_overrides": effective_template_version_overrides,
        "id_column": id_column,
        "session_column": session_column,
        "session_override": session_override,
        "run_column": run_column,
        "sheet": sheet,
        "unknown": unknown,
        "dataset_name": dataset_name,
        "language": language,
        "strict_levels": strict_levels,
        "allow_near_item_match": allow_near_item_match,
        "near_match_tasks": near_match_tasks,
        "task_value_offsets": task_value_offsets,
        "save_to_project": save_to_project,
        "archive_sourcedata": archive_sourcedata,
        "duplicate_handling": duplicate_handling,
        "separator": separator,
        "validate_requested": validate_requested,
    }

    deps: dict[str, Any] = {
        "convert_survey_xlsx_to_prism_dataset": convert_survey_xlsx_to_prism_dataset,
        "convert_survey_lsa_to_prism_dataset": convert_survey_lsa_to_prism_dataset,
        "survey_workflow_stage_service": survey_workflow_stage_service,
        "survey_workflow_stage_options_cls": survey_workflow_stage_options_cls,
        "run_survey_with_official_fallback": run_survey_with_official_fallback,
        "validate_project_templates_for_tasks": validate_project_templates_for_tasks,
        "build_template_completion_gate": build_template_completion_gate,
        "format_workflow_preparation_stale_response": format_workflow_preparation_stale_response_bound,
        "format_value_offset_confirmation_response": format_value_offset_confirmation_response,
        "is_value_offset_confirmation_error": is_value_offset_confirmation_error,
        "id_column_not_detected_error_cls": id_column_not_detected_error_cls,
        "missing_id_mapping_error_cls": missing_id_mapping_error_cls,
        "unmatched_groups_error_cls": unmatched_groups_error_cls,
        "format_unmatched_groups_response": format_unmatched_groups_response,
        "participants_mapping_candidates": participants_mapping_candidates,
        "log_file_head": log_file_head,
        "resolve_validation_library_path": resolve_validation_library_path,
        "run_validation": run_validation,
        "cleanup_stale_tool_limesurvey_sidecars": cleanup_stale_tool_limesurvey_sidecars,
        "iter_session_registration_values": iter_session_registration_values,
        "extract_tasks_from_output": extract_tasks_from_output,
        "register_session_in_project": register_session_in_project,
        "sync_project_survey_recipe_offsets": sync_project_survey_recipe_offsets,
        "summarize_project_output_paths": summarize_project_output_paths,
        "sanitize_jsonable": sanitize_jsonable,
        "collect_multivariant_tasks_from_library": collect_multivariant_tasks_from_library,
    }

    job_id = ""
    for _ in range(5):
        candidate = uuid.uuid4().hex
        try:
            _survey_convert_job_store.create(candidate)
            job_id = candidate
            break
        except ValueError:
            continue
    if not job_id:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return jsonify({"error": "Could not allocate conversion job id"}), 500

    for entry in upfront_logs:
        _survey_convert_job_store.append_log(job_id, entry["message"], entry["level"])

    thread = threading.Thread(
        target=_run_survey_convert_validate_job,
        args=(job_id, config, deps),
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id}), 200


def handle_api_survey_convert_validate_status(job_id: str):
    """Get incremental status and logs for an async survey conversion job."""
    try:
        cursor = int(request.args.get("cursor", "0"))
    except ValueError:
        cursor = 0

    payload = _survey_convert_job_store.snapshot(job_id, cursor)
    if payload is None:
        return jsonify({"error": "Job not found"}), 404

    return jsonify(payload), 200


def _run_survey_convert_validate_job(
    job_id: str, config: dict[str, Any], deps: dict[str, Any]
) -> None:
    """Worker thread body for an async survey conversion+validate job."""

    log_messages: list[dict[str, str]] = []
    conversion_warnings: list[str] = []

    def add_log(message, level="info"):
        log_messages.append({"message": message, "level": level})
        _survey_convert_job_store.append_log(job_id, message, level)

    def fail_with_payload(payload: dict[str, Any]) -> None:
        _survey_convert_job_store.update(
            job_id,
            done=True,
            success=False,
            error=payload.get("error"),
            status=str(payload.get("error") or "failed"),
            result=payload,
        )

    convert_survey_xlsx_to_prism_dataset = deps["convert_survey_xlsx_to_prism_dataset"]
    convert_survey_lsa_to_prism_dataset = deps["convert_survey_lsa_to_prism_dataset"]
    survey_workflow_stage_service = deps["survey_workflow_stage_service"]
    survey_workflow_stage_options_cls = deps["survey_workflow_stage_options_cls"]
    run_survey_with_official_fallback = deps["run_survey_with_official_fallback"]
    validate_project_templates_for_tasks = deps["validate_project_templates_for_tasks"]
    build_template_completion_gate = deps["build_template_completion_gate"]
    format_workflow_preparation_stale_response = deps[
        "format_workflow_preparation_stale_response"
    ]
    format_value_offset_confirmation_response = deps[
        "format_value_offset_confirmation_response"
    ]
    is_value_offset_confirmation_error = deps["is_value_offset_confirmation_error"]
    id_column_not_detected_error_cls = deps["id_column_not_detected_error_cls"]
    missing_id_mapping_error_cls = deps["missing_id_mapping_error_cls"]
    unmatched_groups_error_cls = deps["unmatched_groups_error_cls"]
    format_unmatched_groups_response = deps["format_unmatched_groups_response"]
    participants_mapping_candidates = deps["participants_mapping_candidates"]
    log_file_head = deps["log_file_head"]
    resolve_validation_library_path = deps["resolve_validation_library_path"]
    run_validation = deps["run_validation"]
    cleanup_stale_tool_limesurvey_sidecars = deps["cleanup_stale_tool_limesurvey_sidecars"]
    iter_session_registration_values = deps["iter_session_registration_values"]
    extract_tasks_from_output = deps["extract_tasks_from_output"]
    register_session_in_project = deps["register_session_in_project"]
    sync_project_survey_recipe_offsets = deps["sync_project_survey_recipe_offsets"]
    summarize_project_output_paths = deps["summarize_project_output_paths"]
    sanitize_jsonable = deps["sanitize_jsonable"]
    collect_multivariant_tasks_from_library = deps["collect_multivariant_tasks_from_library"]

    tmp_dir = config["tmp_dir"]
    tmp_dir_path = Path(tmp_dir)
    input_path = config["input_path"]
    alias_path = config["alias_path"]
    id_map_path = config["id_map_path"]
    filename = config["filename"]
    suffix = config["suffix"]
    project_root = config["project_root"]
    current_project_path = config["current_project_path"]
    library_path = config["library_path"]
    effective_survey_dir = config["effective_survey_dir"]
    survey_filter = config["survey_filter"]
    effective_template_version_overrides = config["effective_template_version_overrides"]
    id_column = config["id_column"]
    session_column = config["session_column"]
    session_override = config["session_override"]
    run_column = config["run_column"]
    sheet = config["sheet"]
    unknown = config["unknown"]
    dataset_name = config["dataset_name"]
    language = config["language"]
    strict_levels = config["strict_levels"]
    allow_near_item_match = config["allow_near_item_match"]
    near_match_tasks = config["near_match_tasks"]
    task_value_offsets = config["task_value_offsets"]
    save_to_project = config["save_to_project"]
    archive_sourcedata = config["archive_sourcedata"]
    duplicate_handling = config["duplicate_handling"]
    separator = config["separator"]

    try:
        fallback_project_path = current_project_path
        preflight_output_root = tmp_dir_path / "preflight_rawdata"
        try:
            preflight_result = survey_workflow_stage_service.run_stage(
                workflow_runner=run_survey_with_official_fallback,
                tabular_converter=convert_survey_xlsx_to_prism_dataset,
                lsa_converter=convert_survey_lsa_to_prism_dataset,
                options=survey_workflow_stage_options_cls(
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
        except id_column_not_detected_error_cls as error:
            add_log(f"ID column not detected: {str(error)}", "error")
            fail_with_payload(
                {
                    "error": "id_column_required",
                    "message": str(error),
                    "columns": error.available_columns,
                    "log": log_messages,
                },
            )
            return
        except missing_id_mapping_error_cls as error:
            add_log(f"ID mapping incomplete: {str(error)}", "error")
            fail_with_payload(
                {
                    "error": "id_mapping_incomplete",
                    "message": str(error),
                    "missing_ids": error.missing_ids,
                    "suggestions": error.suggestions,
                    "log": log_messages,
                },
            )
            return
        except unmatched_groups_error_cls as error:
            add_log(f"Unmatched groups: {str(error)}", "error")
            fail_with_payload(
                format_unmatched_groups_response(error, log_messages),
            )
            return
        except Exception as error:
            if is_value_offset_confirmation_error(error):
                add_log(
                    "Out-of-range survey values need review before conversion can continue.",
                    "warning",
                )
                fail_with_payload(
                    format_workflow_preparation_stale_response(
                        format_value_offset_confirmation_response(error, log_messages),
                        log_messages=log_messages,
                    ),
                )
                return
            raise

        preflight_near_match_candidates = list(
            getattr(preflight_result, "near_match_candidates", []) or []
        )
        if preflight_near_match_candidates and not allow_near_item_match:
            add_log("Near item matches detected and awaiting confirmation", "warning")
            near_match_payload = survey_workflow_stage_service.build_near_match_confirmation_payload(
                near_match_candidates=preflight_near_match_candidates
            )
            fail_with_payload(
                format_workflow_preparation_stale_response(
                    near_match_payload,
                    log_messages=log_messages,
                ),
            )
            return

        preflight_tasks = list(getattr(preflight_result, "tasks_included", []) or [])
        project_template_issues = validate_project_templates_for_tasks(
            tasks=preflight_tasks,
            project_path=fallback_project_path,
            schema_version="stable",
        )
        if project_template_issues:
            workflow_gate = build_template_completion_gate(
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
            template_gate_payload = survey_workflow_stage_service.build_template_completion_required_payload(
                workflow_gate=workflow_gate,
                template_issues=project_template_issues,
            )
            fail_with_payload(
                format_workflow_preparation_stale_response(
                    template_gate_payload,
                    log_messages=log_messages,
                ),
            )
            return

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
                    add_log(f"Using participants mapping from: {mapping_file.name}", "info")
                    break

        output_root = tmp_dir_path / "rawdata"
        output_root.mkdir(parents=True, exist_ok=True)
        add_log("Starting data conversion...", "info")
        copied_output_paths: list[Path] = []

        try:
            log_file_head(input_path, suffix, add_log)
        except Exception as head_error:
            add_log(f"Header preview failed: {head_error}", "warning")

        if strict_levels:
            add_log("Strict Levels Validation: enabled", "info")

        try:
            if suffix == ".lsa":
                add_log(f"Processing LimeSurvey archive: {filename}", "info")
            convert_result = survey_workflow_stage_service.run_stage(
                workflow_runner=run_survey_with_official_fallback,
                tabular_converter=convert_survey_xlsx_to_prism_dataset,
                lsa_converter=convert_survey_lsa_to_prism_dataset,
                options=survey_workflow_stage_options_cls(
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
        except id_column_not_detected_error_cls as error:
            add_log(f"ID column not detected: {str(error)}", "error")
            fail_with_payload(
                {
                    "error": "id_column_required",
                    "message": str(error),
                    "columns": error.available_columns,
                    "log": log_messages,
                },
            )
            return
        except missing_id_mapping_error_cls as error:
            add_log(f"ID mapping incomplete: {str(error)}", "error")
            fail_with_payload(
                {
                    "error": "id_mapping_incomplete",
                    "message": str(error),
                    "missing_ids": error.missing_ids,
                    "suggestions": error.suggestions,
                    "log": log_messages,
                },
            )
            return
        except unmatched_groups_error_cls as error:
            add_log(f"Unmatched groups: {str(error)}", "error")
            fail_with_payload(
                format_unmatched_groups_response(error, log_messages),
            )
            return
        except Exception as conversion_error:
            if is_value_offset_confirmation_error(conversion_error):
                add_log(
                    "Out-of-range survey values need review before conversion can continue.",
                    "warning",
                )
                fail_with_payload(
                    format_workflow_preparation_stale_response(
                        format_value_offset_confirmation_response(
                            conversion_error,
                            log_messages,
                        ),
                        log_messages=log_messages,
                    ),
                )
                return
            import sys
            import traceback

            full_trace = traceback.format_exc()
            print(
                f"\n[CONVERSION ERROR] {type(conversion_error).__name__}: {str(conversion_error)}",
                file=sys.stderr,
            )
            print(f"[FULL TRACEBACK]\n{full_trace}", file=sys.stderr)
            add_log(
                f"Conversion engine failed: {type(conversion_error).__name__}: {str(conversion_error)}",
                "error",
            )
            raise conversion_error

        if getattr(convert_result, "missing_cells_by_subject", None):
            missing_counts = {
                subject_id: count
                for subject_id, count in convert_result.missing_cells_by_subject.items()
                if count > 0
            }
            if missing_counts:
                conversion_warnings.append(
                    f"Missing responses normalized: {sum(missing_counts.values())} cells."
                )

        if getattr(convert_result, "conversion_warnings", None):
            conversion_warnings.extend(convert_result.conversion_warnings)

        add_log("Running validation...", "info")
        validation_result = {"errors": [], "warnings": [], "summary": {}}
        if config["validate_requested"]:
            try:
                validation_library_root = resolve_validation_library_path(
                    project_path=current_project_path,
                    fallback_library_root=library_path,
                )
                validation_output = run_validation(
                    str(output_root),
                    schema_version="stable",
                    library_path=str(validation_library_root),
                    project_path=current_project_path,
                )
                if validation_output and isinstance(validation_output, tuple):
                    issues, stats = validation_output

                    from src.web.reporting_utils import format_validation_results

                    formatted = format_validation_results(
                        issues, stats, str(output_root)
                    )
                    validation_result = {"formatted": formatted}
                    validation_result.update(formatted)

                    total_err = formatted.get("summary", {}).get("total_errors", 0)
                    total_warn = formatted.get("summary", {}).get("total_warnings", 0)

                    if total_err > 0:
                        add_log(f"✗ Validation failed with {total_err} error(s)", "error")
                        count = 0
                        for group in formatted.get("errors", []):
                            for file_issue in group.get("files", []):
                                if count < 20:
                                    message = file_issue["message"]
                                    if ": " in message:
                                        message = message.split(": ", 1)[1]
                                    add_log(f"  - {message}", "error")
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

                    project_template_issues = validate_project_templates_for_tasks(
                        tasks=(
                            convert_result.tasks_included
                            if getattr(convert_result, "tasks_included", None)
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
                            add_log(f"  - {Path(issue['file']).name}: {issue['message']}", "warning")
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
                                {"file": issue["file"], "message": issue["message"]}
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
                                    f"{Path(issue['file']).name}: {issue['message']}"
                                    for issue in project_template_issues
                                ]
                            )
                        validation_result.setdefault("summary", {}).setdefault(
                            "total_errors", 0
                        )
                        validation_result["summary"]["total_errors"] += len(
                            project_template_issues
                        )
            except Exception as validation_error:
                validation_result["warnings"].append(
                    f"Validation error: {str(validation_error)}"
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
                        {"file": filename, "message": warning}
                        for warning in conversion_warnings
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
        datalad_copy = None

        if save_to_project:
            dest_root = project_root
            dest_root.mkdir(parents=True, exist_ok=True)
            add_log(
                f"Saving output to project: {project_root.name} (into project root)",
                "info",
            )

            copy_pairs: list[tuple[Path, Path]] = []
            output_rel_paths: set[str] = set()
            for item in output_root.rglob("*"):
                if item.is_file():
                    if not filter_system_files([item.name]):
                        continue
                    rel_path = item.relative_to(output_root)
                    dest = dest_root / rel_path
                    output_rel_paths.add(dest.relative_to(project_root).as_posix())
                    copy_pairs.append((item, dest))

            if archive_sourcedata:
                sourcedata_dir = project_root / "sourcedata"
                archive_dest = sourcedata_dir / filename
                copy_pairs.append((input_path, archive_dest))

            try:
                copy_result = copy_files_into_project(
                    dataset_root=project_root,
                    copy_pairs=copy_pairs,
                    run_message="PRISM: Copy converted survey files into project",
                )
            except ValueError as error:
                _survey_convert_job_store.failure(job_id, str(error))
                return

            copied_rel_paths = [
                str(path) for path in list(copy_result.get("copied_paths") or [])
            ]
            copied_output_paths = [
                project_root / rel_path
                for rel_path in copied_rel_paths
                if rel_path in output_rel_paths
            ]
            datalad_copy = copy_result.get("datalad")

            cleanup_stale_tool_limesurvey_sidecars(
                copied_output_paths=copied_output_paths,
                source_suffix=suffix,
                log_fn=add_log,
            )
            add_log("Project updated successfully!", "success")

            if archive_sourcedata:
                add_log(f"Archived original file to sourcedata/{filename}", "info")

            registration_sessions = iter_session_registration_values(
                session_override=session_override,
                detected_sessions=list(getattr(convert_result, "detected_sessions", []) or []),
            )
            if registration_sessions:
                conv_type = "survey-lsa" if suffix == ".lsa" else "survey-xlsx"
                tasks_out = (
                    convert_result.tasks_included
                    if getattr(convert_result, "tasks_included", None)
                    else extract_tasks_from_output(output_root)
                )
                for registration_session in registration_sessions:
                    register_session_in_project(
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

            if callable(sync_project_survey_recipe_offsets):
                applied_offsets = getattr(convert_result, "applied_value_offsets", {}) or {}
                offset_application_counts = (
                    getattr(convert_result, "value_offset_application_counts", {}) or {}
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
                            add_log(f"Recipe offset sync warning: {sync_error}", "warning")
                    except Exception as sync_error:
                        add_log(f"Recipe offset sync warning: {sync_error}", "warning")
        else:
            copied_output_paths = []

        response_payload = {
            "success": True,
            "validation": validation_result,
            "project_saved": bool(copied_output_paths),
            "project_output_root": str(project_root) if copied_output_paths else None,
            "project_output_paths": [],
            "project_output_path": None,
            "project_output_count": len(copied_output_paths),
            "datalad": datalad_copy,
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
            response_payload["project_output_path"] = output_paths[0] if output_paths else None

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
        response_payload["multivariant_tasks"] = collect_multivariant_tasks_from_library(
            library_dir=effective_survey_dir,
            tasks=list(getattr(convert_result, "tasks_included", []) or []),
            selected_versions=effective_template_version_overrides,
        )

        _survey_convert_job_store.success(job_id, sanitize_jsonable(response_payload))
    except Exception as error:
        _survey_convert_job_store.failure(job_id, str(error))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)