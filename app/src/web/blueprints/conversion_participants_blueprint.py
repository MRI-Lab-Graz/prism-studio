import json
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any

from flask import (
    Blueprint,
    Response,
    current_app,
    has_app_context,
    jsonify,
    request,
    session,
)
from src.participants_id_selection import resolve_participants_id_selection

# merge_neurobagel_schema_for_columns / _rekey_neurobagel_schema_to_output_columns
# below are re-exported (not called directly in this module) so that
# tests/test_neurobagel_merge_no_duplication.py and
# tests/test_web_blueprints_conversion.py::TestParticipantsSchemaMerge can
# assert this module resolves to the one canonical implementation, guarding
# against the duplicate-implementation drift CLAUDE.md warns about.
from src.participants_backend import (
    apply_participants_merge,
    convert_dataset_participants,
    describe_participants_workflow,
    export_participants_merge_conflicts_csv,
    merge_neurobagel_schema_for_columns as _merge_neurobagel_schema_for_columns,  # noqa: F401
    preview_dataset_participants,
    preview_participants_merge,
    save_participant_mapping as save_participant_mapping_backend,
)
from .conversion_participants_helpers import (
    _detect_repeated_questionnaire_prefixes,
    _filter_participant_relevant_columns,
    _generate_neurobagel_schema,
    _is_likely_questionnaire_column,
    _load_project_participant_filter_config,
    _load_survey_template_item_ids,
    _normalize_column_name,
)
from .conversion_participants_io import (
    _detect_mixed_time_style_columns,
    _diagnose_preview_error,
    _expected_delimiter_for_suffix,
    _format_mixed_time_style_message,
    _get_excel_sheet_metadata,
    _normalize_separator_option,
    _read_participants_input_table,
    _resolve_participants_sheet_arg,
    _save_participants_upload_to_temp,
)
from .conversion_participants_mapping import (
    _canonicalize_preview_id_column,
    _collect_preview_column_values,
    _parse_requested_column_list,
    _rekey_neurobagel_schema_to_output_columns,  # noqa: F401 (re-export, see note above)
    _resolve_additional_preview_columns,
    _resolve_web_participant_import_mapping,
)
from .conversion_participants_merge import (
    _build_existing_participants_preview_payload,
    _build_participants_merge_schema_preview,
    _convert_existing_participants_files,
    _parse_participants_merge_request,
    _participants_id_required_response,
    _project_relative_merge_paths,
    _validate_participants_merge_request_context,
)
from .conversion_participants_convert import (
    _check_existing_participants_files,
    _participants_job_store,
    _run_participants_convert_job,
    _write_participants_outputs,
)
from .conversion_utils import resolve_effective_library_path
from .projects_helpers import _resolve_project_root_path

conversion_participants_bp = Blueprint("conversion_participants", __name__)


def _get_session_project_root() -> Path | None:
    """Resolve current project root from session path (folder or project.json path)."""
    current_project_path = session.get("current_project_path")
    if not isinstance(current_project_path, str) or not current_project_path.strip():
        return None
    return _resolve_project_root_path(current_project_path)


@conversion_participants_bp.route("/api/save-participant-mapping", methods=["POST"])
def save_participant_mapping():
    """Save additional-variables mapping JSON file to the project library directory."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        mapping = data.get("mapping")
        library_path = data.get("library_path")
        project_root = _get_session_project_root()
        result = save_participant_mapping_backend(
            mapping,
            project_root=project_root,
            library_path=library_path,
        )
        mapping_file = Path(result["mapping_file"])

        return jsonify(
            {
                "status": "success",
                "file_path": str(mapping_file),
                "library_source": result["library_source"],
                "message": (
                    f"Saved {mapping_file.name}. "
                    "This mapping is applied when you run Extract & Convert."
                ),
            }
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Error saving mapping: {str(e)}"}), 500


@conversion_participants_bp.route("/api/participants-check", methods=["GET"])
def api_participants_check():
    """Check if participants.tsv and participants.json exist in the project/dataset."""
    project_root = _get_session_project_root()
    if not project_root:
        return jsonify({"error": "No project selected"}), 400

    participants_tsv = project_root / "participants.tsv"
    participants_json = project_root / "participants.json"
    has_participants_tsv = participants_tsv.exists()
    has_participants_json = participants_json.exists()
    # A schema-only participants.json (no participants.tsv yet) holds no participant
    # data, so it shouldn't trigger the "existing files will be overwritten" warning.
    exists_root = has_participants_tsv
    workflow = describe_participants_workflow(project_root)

    return jsonify(
        {
            "exists": exists_root,
            "has_participants_tsv": has_participants_tsv,
            "has_participants_json": has_participants_json,
            "can_modify_existing": has_participants_tsv,
            "workflow": workflow,
            "location": ("root" if exists_root else None),
            "files": {
                "participants_tsv": (
                    str(participants_tsv) if has_participants_tsv else None
                ),
                "participants_json": (
                    str(participants_json) if has_participants_json else None
                ),
            },
        }
    )


@conversion_participants_bp.route("/api/participants-detect-id", methods=["POST"])
def api_participants_detect_id():
    """Detect participant ID column for an uploaded participant file."""
    try:
        separator_option = _normalize_separator_option(request.form.get("separator"))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    try:
        upload = _save_participants_upload_to_temp(
            uploaded_file=request.files.get("file"),
            temp_prefix="prism_participants_detect_id_",
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    tmp_dir = str(upload["tmp_dir"])
    try:
        input_path = Path(str(upload["input_path"]))
        suffix = str(upload["suffix"])

        sheet_metadata = (
            _get_excel_sheet_metadata(input_path) if suffix == ".xlsx" else {}
        )
        sheet_arg = _resolve_participants_sheet_arg(
            input_path=input_path,
            suffix=suffix,
            sheet_value=request.form.get("sheet"),
            sheet_metadata=sheet_metadata,
        )

        df = _read_participants_input_table(
            input_path=input_path,
            suffix=suffix,
            sheet_arg=sheet_arg,
            separator_option=separator_option,
        )
        all_sheet_names = (
            list(sheet_metadata.get("sheet_names") or []) if suffix == ".xlsx" else []
        )
        non_empty_sheet_names = (
            list(sheet_metadata.get("non_empty_sheet_names") or [])
            if suffix == ".xlsx"
            else []
        )

        from src.converters.id_detection import (
            detect_id_column as _detect_id,
            has_prismmeta_columns as _has_pm_cols,
        )

        source_columns = [str(col) for col in df.columns]
        source_fmt = suffix.lstrip(".")
        id_resolution = resolve_participants_id_selection(
            columns=source_columns,
            source_format=source_fmt,
            detect_id_fn=_detect_id,
            has_prismmeta=_has_pm_cols(source_columns),
            explicit_id_column=None,
        )
        id_column_for_ui = (
            id_resolution.get("resolved_id_column")
            or id_resolution.get("suggested_id_column")
            or None
        )

        return jsonify(
            {
                "status": "success",
                "id_found": bool(id_column_for_ui),
                "id_column": id_column_for_ui,
                "source_id_column": id_resolution.get("source_id_column"),
                "suggested_id_column": id_resolution.get("suggested_id_column"),
                "participant_id_column": id_resolution.get("participant_id_column"),
                "participant_id_found": bool(id_resolution.get("participant_id_found")),
                "id_selection_required": bool(
                    id_resolution.get("id_selection_required")
                ),
                "columns": source_columns,
                "sheet_count": (
                    len(non_empty_sheet_names) if suffix == ".xlsx" else None
                ),
                "non_empty_sheet_count": (
                    len(non_empty_sheet_names) if suffix == ".xlsx" else None
                ),
                "total_sheet_count": (
                    len(all_sheet_names) if suffix == ".xlsx" else None
                ),
                "sheet_names": non_empty_sheet_names,
                "all_sheet_names": all_sheet_names,
                "show_sheet_selector": (
                    suffix == ".xlsx" and len(non_empty_sheet_names) > 1
                ),
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@conversion_participants_bp.route("/api/participants-preview", methods=["POST"])
def api_participants_preview():
    """Preview participant data extraction from uploaded file."""
    mode = request.form.get("mode", "file")

    if mode == "file":
        try:
            separator_option = _normalize_separator_option(
                request.form.get("separator")
            )
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

        try:
            upload = _save_participants_upload_to_temp(
                uploaded_file=request.files.get("file"),
                temp_prefix="prism_participants_preview_",
            )
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

        tmp_dir = str(upload["tmp_dir"])
        try:
            preview_stage = "initializing preview"
            input_path = Path(str(upload["input_path"]))
            suffix = str(upload["suffix"])

            sheet_arg = _resolve_participants_sheet_arg(
                input_path=input_path,
                suffix=suffix,
                sheet_value=request.form.get("sheet"),
            )

            preview_stage = "reading input file"
            try:
                df = _read_participants_input_table(
                    input_path=input_path,
                    suffix=suffix,
                    sheet_arg=sheet_arg,
                    separator_option=separator_option,
                )
            except ImportError:
                return jsonify({"error": "LimeSurvey support not available"}), 500

            from src.converters.id_detection import (
                detect_id_column as _detect_id,
                has_prismmeta_columns as _has_pm_cols,
            )

            explicit_id_column = request.form.get("id_column", "").strip() or None
            source_columns = [str(col) for col in df.columns]
            source_fmt = suffix.lstrip(".")
            _has_pm = _has_pm_cols(source_columns)
            preview_stage = "detecting participant ID column"
            try:
                id_resolution = resolve_participants_id_selection(
                    columns=source_columns,
                    source_format=source_fmt,
                    detect_id_fn=_detect_id,
                    has_prismmeta=_has_pm,
                    explicit_id_column=explicit_id_column,
                )
            except ValueError as id_error:
                return (
                    jsonify(
                        {
                            "error": str(id_error),
                            "columns": source_columns,
                        }
                    ),
                    400,
                )

            if bool(id_resolution.get("id_selection_required")):
                return _participants_id_required_response(
                    source_columns=source_columns,
                    suggested_id_column=id_resolution.get("suggested_id_column"),
                )

            id_column = str(id_resolution.get("resolved_id_column") or "").strip()
            if not id_column:
                return _participants_id_required_response(source_columns=source_columns)

            source_id_column = str(id_resolution.get("source_id_column") or id_column)

            mixed_time_style_columns = _detect_mixed_time_style_columns(df)
            mixed_time_warning = _format_mixed_time_style_message(
                mixed_time_style_columns
            )

            preview_stage = "resolving template library"
            library_path = resolve_effective_library_path()
            participant_filter_config = _load_project_participant_filter_config(
                session.get("current_project_path")
            )

            preview_stage = "loading survey template IDs"
            template_item_ids = _load_survey_template_item_ids(library_path)
            repeated_prefixes = _detect_repeated_questionnaire_prefixes(
                [str(c) for c in df.columns],
                participant_filter_config=participant_filter_config,
            )
            questionnaire_like_columns = [
                str(col)
                for col in df.columns
                if str(col) != id_column
                and _is_likely_questionnaire_column(
                    str(col),
                    _normalize_column_name(str(col)),
                    template_item_ids,
                    repeated_prefixes,
                )
            ]

            output_columns = _filter_participant_relevant_columns(
                df,
                id_column=id_column,
                library_path=library_path,
                participant_filter_config=participant_filter_config,
                include_template_columns=False,
                allow_nonrelevant_fallback=False,
            )
            excluded_columns = set(
                col
                for col in _parse_requested_column_list(
                    request.form.get("excluded_columns")
                )
                if col != id_column
            )

            additional_columns = _resolve_additional_preview_columns(
                df=df,
                project_root=_get_session_project_root(),
                excluded_columns=excluded_columns,
                extra_columns_json=request.form.get("extra_columns", ""),
            )

            for column_name in additional_columns:
                if column_name not in output_columns:
                    output_columns.append(column_name)

            if excluded_columns:
                output_columns = [
                    col
                    for col in output_columns
                    if col == id_column or col not in excluded_columns
                ]

            if len(output_columns) <= 1:
                if id_column in df.columns:
                    output_df = df[[id_column]]
                    simulation_note = "Detected participant ID only. Additional variables can be added via Add Additional Variables."
                else:
                    output_df = df[list(df.columns)]
                    simulation_note = "Could not detect a participant ID column. Showing raw file structure."
            else:
                output_df = df[output_columns]
                if additional_columns:
                    simulation_note = (
                        f"Simulated output with {len(output_columns)} participant columns "
                        f"(including {len(set(additional_columns))} selected additional variable(s))."
                    )
                else:
                    simulation_note = f"Simulated output with {len(output_columns)} default participant columns."

            output_df, preview_id_column = _canonicalize_preview_id_column(
                output_df,
                id_column,
                keep_session_id_columns=True,
            )

            preview_df = output_df.head(20)
            # Ensure strict JSON payload: replace pandas NaN/NA with None,
            # otherwise browsers can fail parsing response.json() on NaN literals.
            preview_df = preview_df.astype(object).where(preview_df.notna(), None)

            preview_stage = "generating participants schema"
            neurobagel_schema = _generate_neurobagel_schema(
                output_df,
                preview_id_column,
                library_path=library_path,
                participant_filter_config=participant_filter_config,
            )

            return jsonify(
                {
                    "status": "success",
                    "columns": list(output_df.columns),
                    "column_values": _collect_preview_column_values(output_df),
                    "source_columns": source_columns,
                    "questionnaire_like_columns": questionnaire_like_columns,
                    "id_column": preview_id_column,
                    "source_id_column": source_id_column,
                    "suggested_id_column": id_resolution.get("suggested_id_column"),
                    "participant_id_found": bool(
                        id_resolution.get("participant_id_found")
                    ),
                    "id_selection_required": bool(
                        id_resolution.get("id_selection_required")
                    ),
                    "participant_count": len(output_df),
                    "preview_rows": preview_df.to_dict(orient="records"),
                    "library_path": str(library_path),
                    "simulation_note": simulation_note,
                    "total_source_columns": len(df.columns),
                    "extracted_columns": len(output_df.columns),
                    "neurobagel_schema": neurobagel_schema,
                    "format_warnings": (
                        [mixed_time_warning] if mixed_time_warning else []
                    ),
                    "problem_columns": mixed_time_style_columns,
                }
            )

        except Exception as e:
            return _diagnose_preview_error(
                exc=e,
                df=df if "df" in locals() else None,
                input_path=input_path if "input_path" in locals() else None,
                suffix=suffix if "suffix" in locals() else None,
                sheet_arg=sheet_arg if "sheet_arg" in locals() else None,
                separator_option=(
                    separator_option if "separator_option" in locals() else None
                ),
                preview_stage=preview_stage if "preview_stage" in locals() else None,
            )

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    elif mode == "existing":
        project_root = _get_session_project_root()
        if not project_root:
            return jsonify({"error": "No project selected"}), 400

        try:
            excluded_columns = set(
                _parse_requested_column_list(request.form.get("excluded_columns"))
            )
            return jsonify(
                _build_existing_participants_preview_payload(
                    project_root,
                    excluded_columns=excluded_columns,
                )
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    elif mode == "dataset":
        project_root = _get_session_project_root()
        if not project_root:
            return jsonify({"error": "No project selected"}), 400
        extract_from_survey = (
            request.form.get("extract_from_survey", "true").lower() == "true"
        )
        extract_from_biometrics = (
            request.form.get("extract_from_biometrics", "true").lower() == "true"
        )
        try:
            return jsonify(
                preview_dataset_participants(
                    project_root,
                    extract_from_survey=extract_from_survey,
                    extract_from_biometrics=extract_from_biometrics,
                )
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    else:
        return jsonify({"error": f"Unknown mode: {mode}"}), 400


@conversion_participants_bp.route("/api/participants-merge", methods=["POST"])
def api_participants_merge():
    """Preview or apply a safe merge into an existing participants.tsv."""
    project_root = _get_session_project_root()
    if not project_root:
        return jsonify({"error": "No project selected"}), 400
    apply_merge = request.form.get("apply", "false").lower() == "true"

    try:
        merge_request = _parse_participants_merge_request(project_root)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    logs = merge_request["logs"]
    log_msg = merge_request["log_callback"]
    tmp_dir = str(merge_request["tmp_dir"])

    try:
        input_path = Path(str(merge_request["input_path"]))
        sheet_arg = merge_request["sheet_arg"]
        separator = merge_request["separator"]
        preview_limit = int(merge_request["preview_limit"])
        neurobagel_schema = merge_request["neurobagel_schema"]
        harmonization_decisions = merge_request["harmonization_decisions"]
        session_resolution_decisions = merge_request["session_resolution_decisions"]
        mapping = merge_request["mapping"]

        validated_context, error_response = (
            _validate_participants_merge_request_context(merge_request)
        )
        if error_response is not None:
            return error_response

        id_resolution = validated_context["id_resolution"]
        source_columns = validated_context["source_columns"]
        detected_id_col = validated_context["detected_id_col"]
        context = validated_context["context"]

        preview_payload = preview_participants_merge(
            project_root,
            input_path,
            mapping,
            separator=separator,
            sheet=sheet_arg,
            preview_limit=preview_limit,
            neurobagel_schema=neurobagel_schema,
            harmonization_decisions=harmonization_decisions,
            session_resolution_decisions=session_resolution_decisions,
            log_callback=log_msg,
        )

        preview_columns = [str(col) for col in (preview_payload.get("columns") or [])]
        preview_payload.update(
            {
                "merge_mode": True,
                "participant_count": preview_payload.get("merged_participant_count", 0),
                "participants_tsv": str(project_root / "participants.tsv"),
                "participants_json": str(project_root / "participants.json"),
                "id_column": "participant_id",
                "source_id_column": str(
                    id_resolution.get("source_id_column") or detected_id_col
                ),
                "suggested_id_column": id_resolution.get("suggested_id_column"),
                "participant_id_found": bool(id_resolution.get("participant_id_found")),
                "id_selection_required": bool(
                    id_resolution.get("id_selection_required")
                ),
                "source_columns": source_columns,
                "questionnaire_like_columns": context.get("questionnaire_like_columns")
                or [],
                "total_source_columns": len(source_columns),
                "extracted_columns": len(preview_columns),
                "neurobagel_schema": _build_participants_merge_schema_preview(
                    project_root=project_root,
                    columns=preview_columns,
                    neurobagel_schema=neurobagel_schema,
                    mapping=mapping,
                    log_callback=log_msg,
                ),
                "format_warnings": [],
                "problem_columns": [],
                "log": logs,
            }
        )

        if not apply_merge:
            return jsonify(preview_payload)

        if not bool(preview_payload.get("can_apply")):
            preview_payload["error"] = (
                "Merge preview is not apply-ready. Resolve conflicts and session-resolution blockers before applying."
            )
            return jsonify(preview_payload), 409

        apply_payload = apply_participants_merge(
            project_root,
            input_path,
            mapping,
            separator=separator,
            sheet=sheet_arg,
            preview_limit=preview_limit,
            neurobagel_schema=neurobagel_schema,
            harmonization_decisions=harmonization_decisions,
            session_resolution_decisions=session_resolution_decisions,
            log_callback=log_msg,
        )
        apply_payload.update(
            {
                "merge_mode": True,
                "participants_tsv": str(project_root / "participants.tsv"),
                "participants_json": str(project_root / "participants.json"),
                "files_created": _project_relative_merge_paths(
                    project_root, apply_payload.get("files_written")
                ),
                "backup_files": _project_relative_merge_paths(
                    project_root, apply_payload.get("backup_files")
                ),
                "output_directory": str(project_root),
                "log": logs,
            }
        )
        return jsonify(apply_payload)
    except ValueError as error:
        return jsonify({"error": str(error), "log": logs}), 400
    except Exception as error:
        if has_app_context():
            current_app.logger.exception("Participants merge failed")
        log_msg("ERROR", f"Error: {str(error)}")
        return jsonify({"error": str(error), "log": logs}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@conversion_participants_bp.route("/api/participants-merge-conflicts", methods=["POST"])
def api_participants_merge_conflicts():
    """Download the full merge conflict report as CSV."""
    project_root = _get_session_project_root()
    if not project_root:
        return jsonify({"error": "No project selected"}), 400

    try:
        merge_request = _parse_participants_merge_request(project_root)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    logs = merge_request["logs"]
    log_msg = merge_request["log_callback"]
    tmp_dir = str(merge_request["tmp_dir"])

    try:
        validated_context, error_response = (
            _validate_participants_merge_request_context(merge_request)
        )
        if error_response is not None:
            return error_response

        csv_text = export_participants_merge_conflicts_csv(
            project_root,
            Path(str(merge_request["input_path"])),
            merge_request["mapping"],
            separator=merge_request["separator"],
            sheet=merge_request["sheet_arg"],
            preview_limit=int(merge_request["preview_limit"]),
            neurobagel_schema=merge_request["neurobagel_schema"],
            harmonization_decisions=merge_request["harmonization_decisions"],
            session_resolution_decisions=merge_request["session_resolution_decisions"],
            log_callback=log_msg,
        )
        response = Response(csv_text, mimetype="text/csv")
        response.headers["Content-Disposition"] = (
            'attachment; filename="participants_merge_conflicts.csv"'
        )
        return response
    except ValueError as error:
        return jsonify({"error": str(error), "log": logs}), 400
    except Exception as error:
        if has_app_context():
            current_app.logger.exception("Participants merge conflict export failed")
        log_msg("ERROR", f"Error: {str(error)}")
        return jsonify({"error": str(error), "log": logs}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@conversion_participants_bp.route("/api/participants-convert", methods=["POST"])
def api_participants_convert():
    """Convert/extract participant data and create participants.tsv and participants.json."""
    try:
        import json
    except ImportError as e:
        return jsonify({"error": f"Required module not available: {str(e)}"}), 500

    mode = request.form.get("mode", "file")
    force_overwrite = request.form.get("force_overwrite", "false").lower() == "true"
    neurobagel_schema_json = request.form.get("neurobagel_schema")
    try:
        separator_option = _normalize_separator_option(request.form.get("separator"))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    neurobagel_schema = {}
    if neurobagel_schema_json:
        try:
            neurobagel_schema = json.loads(neurobagel_schema_json)
        except json.JSONDecodeError:
            pass
    excluded_columns = set(
        _parse_requested_column_list(request.form.get("excluded_columns"))
    )

    project_root = _get_session_project_root()
    if not project_root:
        return jsonify({"error": "No project selected"}), 400

    participants_tsv, participants_json, existing_files, error_response = (
        _check_existing_participants_files(project_root, mode, force_overwrite)
    )
    if error_response is not None:
        return error_response

    logs = []

    def log_msg(level, message):
        logs.append({"level": level, "message": message})

    try:
        if mode == "file":
            try:
                upload = _save_participants_upload_to_temp(
                    uploaded_file=request.files.get("file"),
                    temp_prefix="prism_participants_convert_",
                )
            except ValueError as error:
                return jsonify({"error": str(error)}), 400

            tmp_dir = str(upload["tmp_dir"])
            try:
                input_path = Path(str(upload["input_path"]))
                filename = str(upload["filename"])
                suffix = str(upload["suffix"])

                sheet_arg = _resolve_participants_sheet_arg(
                    input_path=input_path,
                    suffix=suffix,
                    sheet_value=request.form.get("sheet"),
                )
                converter_separator = (
                    _expected_delimiter_for_suffix(suffix, separator_option) or "auto"
                )

                log_msg("INFO", f"Processing {filename}...")

                try:
                    explicit_id_col = request.form.get("id_column", "").strip() or None
                    extra_columns = _parse_requested_column_list(
                        request.form.get("extra_columns")
                    )
                    context = _resolve_web_participant_import_mapping(
                        project_root=project_root,
                        input_path=input_path,
                        suffix=suffix,
                        sheet_arg=sheet_arg,
                        separator_option=separator_option,
                        explicit_id_column=explicit_id_col,
                        excluded_columns=excluded_columns,
                        extra_columns=extra_columns,
                        log_callback=log_msg,
                    )
                except ValueError as resolve_error:
                    return jsonify({"error": str(resolve_error), "log": logs}), 400

                id_resolution = context.get("id_resolution") or {}
                source_columns = context.get("source_columns") or []
                if bool(id_resolution.get("id_selection_required")):
                    return _participants_id_required_response(
                        source_columns=source_columns,
                        suggested_id_column=id_resolution.get("suggested_id_column"),
                        logs=logs,
                    )

                detected_id_col = str(context.get("detected_id_column") or "").strip()
                if not detected_id_col:
                    return _participants_id_required_response(
                        source_columns=source_columns,
                        logs=logs,
                    )

                mapping = context.get("mapping")
                if not isinstance(mapping, dict):
                    return (
                        jsonify(
                            {
                                "error": "Could not resolve participant mapping",
                                "log": logs,
                            }
                        ),
                        400,
                    )

                try:
                    result = _write_participants_outputs(
                        project_root=project_root,
                        input_path=input_path,
                        mapping=mapping,
                        converter_separator=converter_separator,
                        sheet_arg=sheet_arg,
                        participants_tsv=participants_tsv,
                        participants_json=participants_json,
                        neurobagel_schema=neurobagel_schema,
                        existing_files=existing_files,
                        log_msg=log_msg,
                    )
                except ValueError:
                    return jsonify({"error": "Conversion failed", "log": logs}), 400

                return jsonify({**result, "log": logs})

            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        elif mode == "existing":
            log_msg("INFO", "Updating existing participants.tsv/participants.json...")
            try:
                result = _convert_existing_participants_files(
                    project_root=project_root,
                    neurobagel_schema=neurobagel_schema,
                    excluded_columns=excluded_columns,
                    log_callback=log_msg,
                )
            except ValueError as e:
                return jsonify({"error": str(e), "log": logs}), 400

            return jsonify(
                {
                    **result,
                    "log": logs,
                    "overwrote_existing": bool(existing_files),
                    "overwritten_files": existing_files if existing_files else [],
                }
            )

        elif mode == "dataset":
            extract_from_survey = (
                request.form.get("extract_from_survey", "true").lower() == "true"
            )
            extract_from_biometrics = (
                request.form.get("extract_from_biometrics", "true").lower() == "true"
            )

            log_msg("INFO", "Extracting participant data from dataset...")
            try:
                result = convert_dataset_participants(
                    project_root,
                    neurobagel_schema=neurobagel_schema,
                    extract_from_survey=extract_from_survey,
                    extract_from_biometrics=extract_from_biometrics,
                    log_callback=log_msg,
                )
            except ValueError as e:
                return jsonify({"error": str(e), "log": logs}), 400

            return jsonify({**result, "log": logs})

        else:
            return jsonify({"error": f"Unknown mode: {mode}", "log": logs}), 400

    except Exception as e:
        log_msg("ERROR", f"Error: {str(e)}")
        if has_app_context():
            current_app.logger.exception("Participants conversion failed")
        return jsonify({"error": str(e), "log": logs}), 500


@conversion_participants_bp.route("/api/participants-convert-start", methods=["POST"])
def api_participants_convert_start():
    """Start an async participants conversion job and return its job id for polling."""
    try:
        from src.participants_converter import ParticipantsConverter  # noqa: F401
    except ImportError as e:
        return jsonify({"error": f"Required module not available: {str(e)}"}), 500

    mode = request.form.get("mode", "file")
    force_overwrite = request.form.get("force_overwrite", "false").lower() == "true"
    neurobagel_schema_json = request.form.get("neurobagel_schema")
    try:
        separator_option = _normalize_separator_option(request.form.get("separator"))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    neurobagel_schema = {}
    if neurobagel_schema_json:
        try:
            neurobagel_schema = json.loads(neurobagel_schema_json)
        except json.JSONDecodeError:
            pass
    excluded_columns = set(
        _parse_requested_column_list(request.form.get("excluded_columns"))
    )

    project_root = _get_session_project_root()
    if not project_root:
        return jsonify({"error": "No project selected"}), 400

    participants_tsv, participants_json, existing_files, error_response = (
        _check_existing_participants_files(project_root, mode, force_overwrite)
    )
    if error_response is not None:
        return error_response

    upfront_logs: list[dict[str, str]] = []

    def log_msg(level, message):
        upfront_logs.append({"level": level, "message": message})

    config: dict[str, Any] = {
        "mode": mode,
        "project_root": project_root,
        "participants_tsv": participants_tsv,
        "participants_json": participants_json,
        "existing_files": existing_files,
        "neurobagel_schema": neurobagel_schema,
        "excluded_columns": excluded_columns,
    }

    if mode == "file":
        try:
            upload = _save_participants_upload_to_temp(
                uploaded_file=request.files.get("file"),
                temp_prefix="prism_participants_convert_job_",
            )
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

        tmp_dir = str(upload["tmp_dir"])
        try:
            input_path = Path(str(upload["input_path"]))
            filename = str(upload["filename"])
            suffix = str(upload["suffix"])

            sheet_arg = _resolve_participants_sheet_arg(
                input_path=input_path,
                suffix=suffix,
                sheet_value=request.form.get("sheet"),
            )
            converter_separator = (
                _expected_delimiter_for_suffix(suffix, separator_option) or "auto"
            )

            log_msg("INFO", f"Processing {filename}...")

            explicit_id_col = request.form.get("id_column", "").strip() or None
            extra_columns = _parse_requested_column_list(
                request.form.get("extra_columns")
            )
            try:
                context = _resolve_web_participant_import_mapping(
                    project_root=project_root,
                    input_path=input_path,
                    suffix=suffix,
                    sheet_arg=sheet_arg,
                    separator_option=separator_option,
                    explicit_id_column=explicit_id_col,
                    excluded_columns=excluded_columns,
                    extra_columns=extra_columns,
                    log_callback=log_msg,
                )
            except ValueError as resolve_error:
                return jsonify({"error": str(resolve_error), "log": upfront_logs}), 400

            id_resolution = context.get("id_resolution") or {}
            source_columns = context.get("source_columns") or []
            if bool(id_resolution.get("id_selection_required")):
                return _participants_id_required_response(
                    source_columns=source_columns,
                    suggested_id_column=id_resolution.get("suggested_id_column"),
                    logs=upfront_logs,
                )

            detected_id_col = str(context.get("detected_id_column") or "").strip()
            if not detected_id_col:
                return _participants_id_required_response(
                    source_columns=source_columns,
                    logs=upfront_logs,
                )

            mapping = context.get("mapping")
            if not isinstance(mapping, dict):
                return (
                    jsonify(
                        {
                            "error": "Could not resolve participant mapping",
                            "log": upfront_logs,
                        }
                    ),
                    400,
                )

            config.update(
                {
                    "tmp_dir": tmp_dir,
                    "input_path": input_path,
                    "filename": filename,
                    "sheet_arg": sheet_arg,
                    "converter_separator": converter_separator,
                    "mapping": mapping,
                }
            )
        except Exception:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise

    elif mode == "existing":
        pass

    elif mode == "dataset":
        config["extract_from_survey"] = (
            request.form.get("extract_from_survey", "true").lower() == "true"
        )
        config["extract_from_biometrics"] = (
            request.form.get("extract_from_biometrics", "true").lower() == "true"
        )

    else:
        return jsonify({"error": f"Unknown mode: {mode}"}), 400

    job_id = ""
    for _ in range(5):
        candidate = uuid.uuid4().hex
        try:
            _participants_job_store.create(candidate)
            job_id = candidate
            break
        except ValueError:
            continue
    if not job_id:
        if mode == "file":
            shutil.rmtree(config["tmp_dir"], ignore_errors=True)
        return jsonify({"error": "Could not allocate conversion job id"}), 500

    for entry in upfront_logs:
        _participants_job_store.append_log(job_id, entry["message"], entry["level"])

    thread = threading.Thread(
        target=_run_participants_convert_job, args=(job_id, config), daemon=True
    )
    thread.start()

    return jsonify({"job_id": job_id}), 200


@conversion_participants_bp.route(
    "/api/participants-convert-status/<job_id>", methods=["GET"]
)
def api_participants_convert_status(job_id: str):
    """Get incremental status and logs for an async participants conversion job."""
    try:
        cursor = int(request.args.get("cursor", "0"))
    except ValueError:
        cursor = 0

    payload = _participants_job_store.snapshot(job_id, cursor)
    if payload is None:
        return jsonify({"error": "Job not found"}), 404

    return jsonify(payload), 200
