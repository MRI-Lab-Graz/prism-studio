import io
import shutil
import tempfile
import zipfile
from pathlib import Path

from flask import current_app, has_app_context, jsonify, request, send_file, session
from werkzeug.utils import secure_filename
from src.system_files import filter_system_files

try:
    import defusedxml.ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET


def handle_api_survey_convert(
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
    infer_lsa_metadata,
    is_value_offset_confirmation_error,
    format_workflow_preparation_stale_response,
    format_value_offset_confirmation_response,
    extract_tasks_from_output,
    iter_session_registration_values,
    register_session_in_project,
    sync_project_survey_recipe_offsets,
    id_column_not_detected_error_cls,
    missing_id_mapping_error_cls,
    unmatched_groups_error_cls,
    format_unmatched_groups_response,
):
    """Run full survey conversion and return ZIP output."""
    if (
        not convert_survey_xlsx_to_prism_dataset
        and not convert_survey_lsa_to_prism_dataset
    ):
        return jsonify({"error": "Survey conversion module not available"}), 500

    uploaded_file, upload_error = resolve_uploaded_or_source_file(
        field_names=("excel", "file")
    )
    alias_upload = request.files.get("alias") or request.files.get("alias_file")
    id_map_upload = request.files.get("id_map")

    if uploaded_file is None or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": upload_error or "Missing input file"}), 400

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
        library_path = resolve_effective_library_path()
    except FileNotFoundError as error:
        return jsonify({"error": str(error)}), 400

    try:
        effective_survey_dir = survey_workflow_stage_service.resolve_effective_survey_dir(
            library_path=library_path,
            fallback_project_path=(
                requested_project_path or session.get("current_project_path")
            ),
            resolve_official_survey_dir=resolve_official_survey_dir,
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
                project_root = resolve_requested_project_root(require_project=True)
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
                    template_version_overrides=effective_template_version_overrides,
                    allow_near_item_match=allow_near_item_match,
                    near_match_tasks=near_match_tasks,
                    task_value_offsets=task_value_offsets,
                ),
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
            if is_value_offset_confirmation_error(error):
                return (
                    jsonify(
                        format_workflow_preparation_stale_response(
                            format_value_offset_confirmation_response(error)
                        )
                    ),
                    409,
                )
            raise

        preflight_near_match_candidates = list(
            getattr(preflight_result, "near_match_candidates", []) or []
        )
        if preflight_near_match_candidates and not allow_near_item_match:
            near_match_payload = survey_workflow_stage_service.build_near_match_confirmation_payload(
                near_match_candidates=preflight_near_match_candidates
            )
            return (
                jsonify(
                    format_workflow_preparation_stale_response(near_match_payload)
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
            template_gate_payload = survey_workflow_stage_service.build_template_completion_required_payload(
                workflow_gate=workflow_gate,
                template_issues=project_template_issues,
            )
            return (
                jsonify(
                    format_workflow_preparation_stale_response(template_gate_payload)
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
                    fallback_project_path=fallback_project_path,
                    template_version_overrides=effective_template_version_overrides,
                    allow_near_item_match=allow_near_item_match,
                    near_match_tasks=near_match_tasks,
                    task_value_offsets=task_value_offsets,
                ),
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
            if is_value_offset_confirmation_error(error):
                return (
                    jsonify(
                        format_workflow_preparation_stale_response(
                            format_value_offset_confirmation_response(error)
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
                    if not filter_system_files([item.name]):
                        continue
                    rel_path = item.relative_to(output_root)
                    dest = dest_root / rel_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest)

            if archive_sourcedata:
                sourcedata_dir = project_root / "sourcedata"
                sourcedata_dir.mkdir(parents=True, exist_ok=True)
                archive_dest = sourcedata_dir / filename
                shutil.copy2(input_path, archive_dest)

            registration_sessions = iter_session_registration_values(
                session_override=session_override,
                detected_sessions=(
                    list(getattr(convert_result, "detected_sessions", []) or [])
                    if convert_result
                    else []
                ),
            )
            if registration_sessions:
                conv_type = "survey-lsa" if suffix == ".lsa" else "survey-xlsx"
                tasks_out = extract_tasks_from_output(output_root)
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

            if convert_result and callable(sync_project_survey_recipe_offsets):
                applied_offsets = (
                    getattr(convert_result, "applied_value_offsets", {}) or {}
                )
                offset_application_counts = (
                    getattr(convert_result, "value_offset_application_counts", {}) or {}
                )
                if applied_offsets:
                    try:
                        sync_project_survey_recipe_offsets(
                            project_root=project_root,
                            task_value_offsets=applied_offsets,
                            offset_application_counts=offset_application_counts,
                        )
                    except Exception:
                        pass

        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in output_root.rglob("*"):
                if path.is_file():
                    if not filter_system_files([path.name]):
                        continue
                    arcname = path.relative_to(output_root)
                    archive.write(path, arcname.as_posix())
        mem.seek(0)

        response = send_file(
            mem,
            mimetype="application/zip",
            as_attachment=True,
            download_name="prism_survey_dataset.zip",
        )

        if detected_language:
            response.headers["X-Prism-Detected-Language"] = str(detected_language)
        if detected_platform:
            response.headers["X-Prism-Detected-SoftwarePlatform"] = str(
                detected_platform
            )
        if detected_version:
            response.headers["X-Prism-Detected-SoftwareVersion"] = str(detected_version)

        return response
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
    except ET.ParseError as error:
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
    except Exception as error:
        error_msg = str(error)
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