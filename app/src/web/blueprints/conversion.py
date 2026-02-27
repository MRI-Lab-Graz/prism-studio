"""
Conversion Blueprint for PRISM.
Handles survey, biometrics, and physio conversion routes.
"""

import io
import json
import re
import shutil
import tempfile
import warnings
import zipfile
import base64
from pathlib import Path
from typing import Any
from flask import Blueprint, request, jsonify, send_file, current_app, session
from werkzeug.utils import secure_filename
from src.web.survey_utils import list_survey_template_languages
from src.web.reporting_utils import sanitize_jsonable
from src.web.validation import run_validation

try:
    import defusedxml.ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

# Import shared utilities
from .conversion_utils import (
    participant_json_candidates,
    log_file_head,
    resolve_effective_library_path,
    normalize_filename,
    should_retry_with_official_library,
    is_project_code_library,
    extract_tasks_from_output,
)
from src.web.services.project_registration import register_session_in_project
from .conversion_participants_helpers import (
    _merge_participant_filter_config,
    _load_project_participant_filter_config,
    _normalize_column_name,
    _load_participant_template_columns,
    _load_survey_template_item_ids,
    _detect_repeated_questionnaire_prefixes,
    _is_likely_questionnaire_column,
    _filter_participant_relevant_columns,
    _collect_default_participant_columns,
    _generate_neurobagel_schema,
)


# Import conversion logic
convert_survey_xlsx_to_prism_dataset: Any = None
convert_survey_lsa_to_prism_dataset: Any = None
infer_lsa_metadata: Any = None
MissingIdMappingError: Any = None
UnmatchedGroupsError: Any = None
_NON_ITEM_TOPLEVEL_KEYS: set[str] = set()

try:
    from src.converters.survey import (
        convert_survey_xlsx_to_prism_dataset,
        convert_survey_lsa_to_prism_dataset,
        infer_lsa_metadata,
        MissingIdMappingError,
        UnmatchedGroupsError,
        _NON_ITEM_TOPLEVEL_KEYS,
    )
except ImportError:
    pass

IdColumnNotDetectedError: Any = None
try:
    from src.converters.id_detection import IdColumnNotDetectedError
except ImportError:
    pass

convert_biometrics_table_to_prism_dataset: Any = None
try:
    from src.converters.biometrics import convert_biometrics_table_to_prism_dataset
except ImportError:
    pass

convert_varioport: Any = None
try:
    from helpers.physio.convert_varioport import convert_varioport
except ImportError:
    pass

batch_convert_folder: Any = None
create_dataset_description: Any = None
parse_bids_filename: Any = None
try:
    from src.batch_convert import (
        batch_convert_folder,
        create_dataset_description,
        parse_bids_filename,
    )
except ImportError:
    pass

conversion_bp = Blueprint("conversion", __name__)

# Batch conversion job tracking
_batch_convert_jobs: dict[str, Any] = {}

# Keep backward-compatible wrappers for any internal calls
_participant_json_candidates = participant_json_candidates
_log_file_head = log_file_head
_resolve_effective_library_path = resolve_effective_library_path
_normalize_filename = normalize_filename
_should_retry_with_official_library = should_retry_with_official_library
_is_project_code_library = is_project_code_library
_extract_tasks_from_output = extract_tasks_from_output
_register_session_in_project = register_session_in_project



from .conversion_survey_handlers import (
    _copy_official_templates_to_project,
    _format_unmatched_groups_response,
    _resolve_official_survey_dir,
    _run_survey_with_official_fallback,
    api_save_unmatched_template,
    api_survey_convert,
    api_survey_convert_preview,
    api_survey_convert_validate,
    api_survey_languages,
)


@conversion_bp.route("/api/biometrics-check-library", methods=["GET"])
def api_biometrics_check_library():
    """Check the structure of a biometrics template library folder."""
    library_path = (request.args.get("library_path") or "").strip()
    if not library_path:
        return jsonify({"error": "No library path provided"}), 400

    library_root = Path(library_path)
    # Handle official/library/biometrics structure
    if (library_root / "library" / "biometrics").is_dir():
        biometrics_dir = library_root / "library" / "biometrics"
    else:
        biometrics_dir = library_root / "biometrics"

    # Handle official/library/survey structure
    if (library_root / "library" / "survey").is_dir():
        survey_dir = library_root / "library" / "survey"
    else:
        survey_dir = library_root / "survey"

    participant_candidates = _participant_json_candidates(library_root)
    has_participants = any(p.is_file() for p in participant_candidates)

    structure_info = {
        "has_survey_folder": survey_dir.is_dir(),
        "has_biometrics_folder": biometrics_dir.is_dir(),
        "has_participants_json": has_participants,
        "missing_items": [],
        "template_count": 0,
    }

    if not structure_info["has_biometrics_folder"]:
        structure_info["missing_items"].append("biometrics/")
    if not structure_info["has_participants_json"]:
        structure_info["missing_items"].append(
            "participants.json (or ../participants.json)"
        )
    if biometrics_dir.is_dir():
        structure_info["template_count"] = len(
            list(biometrics_dir.glob("biometrics-*.json"))
        )

    return jsonify({"structure": structure_info})


@conversion_bp.route("/api/biometrics-detect", methods=["POST"])
def api_biometrics_detect():
    """Detect which biometrics tasks are present in the uploaded file."""
    from src.converters.biometrics import detect_biometrics_in_table

    uploaded_file = request.files.get("data") or request.files.get("file")

    if not uploaded_file or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": "Missing input file"}), 400

    # Automatically resolve library path (project first, then global)
    try:
        library_root = _resolve_effective_library_path()
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 400

    filename = secure_filename(uploaded_file.filename)
    tmp_dir = tempfile.mkdtemp(prefix="prism_biometrics_detect_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        biometrics_dir = library_root / "biometrics"
        effective_biometrics_dir = (
            biometrics_dir if biometrics_dir.is_dir() else library_root
        )

        detected_tasks = detect_biometrics_in_table(
            input_path=input_path,
            library_dir=effective_biometrics_dir,
            sheet=(request.form.get("sheet") or "0").strip() or 0,
        )

        return jsonify({"tasks": detected_tasks})
    except zipfile.BadZipFile:
        return (
            jsonify({"error": "❌ Invalid archive file. The file may be corrupted."}),
            400,
        )
    except Exception as e:
        import traceback

        error_msg = str(e) or "Unknown error occurred"
        return jsonify({"error": error_msg, "traceback": traceback.format_exc()}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@conversion_bp.route("/api/biometrics-convert", methods=["POST"])
def api_biometrics_convert():
    """Convert an uploaded biometrics table (.csv or .xlsx) into a PRISM/BIDS-style dataset ZIP."""
    print("[DEBUG] api_biometrics_convert() called")  # DEBUG
    if not convert_biometrics_table_to_prism_dataset:
        print(
            "[DEBUG] convert_biometrics_table_to_prism_dataset not available!"
        )  # DEBUG
        return jsonify({"error": "Biometrics conversion module not available"}), 500

    uploaded_file = request.files.get("data") or request.files.get("file")
    print(f"[DEBUG] uploaded_file: {uploaded_file}")  # DEBUG

    if not uploaded_file or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": "Missing input file"}), 400

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".csv", ".xlsx", ".tsv"}:
        return jsonify({"error": "Supported formats: .csv, .xlsx, .tsv"}), 400

    # Automatically resolve library path (project first, then global)
    try:
        library_root = _resolve_effective_library_path()
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 400

    biometrics_dir = library_root / "biometrics"
    effective_biometrics_dir = (
        biometrics_dir if biometrics_dir.is_dir() else library_root
    )

    biometrics_templates = list(effective_biometrics_dir.glob("biometrics-*.json"))
    if not biometrics_templates:
        return (
            jsonify(
                {
                    "error": f"No biometrics templates found in: {effective_biometrics_dir}"
                }
            ),
            400,
        )

    id_column = (request.form.get("id_column") or "").strip() or None
    session_column = (request.form.get("session_column") or "").strip() or None
    session_override = (request.form.get("session") or "").strip() or None
    sheet = (request.form.get("sheet") or "0").strip() or 0
    unknown = (request.form.get("unknown") or "warn").strip() or "warn"
    dataset_name = (request.form.get("dataset_name") or "").strip() or None
    save_to_project = request.form.get("save_to_project") == "true"
    dry_run = request.form.get("dry_run", "false").lower() == "true"

    # Get tasks to export
    tasks_to_export = request.form.getlist("tasks[]")
    if not tasks_to_export:
        # Fallback to all if none specified (for backward compatibility)
        tasks_to_export = None

    log = []

    def log_msg(message, type="info"):
        log.append({"message": message, "type": type})

    tmp_dir = tempfile.mkdtemp(prefix="prism_biometrics_convert_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        output_root = tmp_dir_path / "prism_dataset"

        if dry_run:
            log_msg("🔍 DRY-RUN MODE - No files will be created", "info")

        log_msg("", "info")
        log_msg(f"Starting biometrics conversion for {filename}", "info")
        log_msg(f"Template library: {effective_biometrics_dir}", "step")
        log_msg(f"Session: {session_override or 'auto-detect'}", "step")
        log_msg(f"Sheet: {sheet}", "step")
        log_msg("", "info")

        # Log the head to help debug delimiter/structure issues
        _log_file_head(input_path, suffix, log_msg)

        log_msg("", "info")
        log_msg("Backend command:", "step")
        log_msg("  convert_biometrics_table_to_prism_dataset(", "info")
        log_msg(f"    input_path='{input_path.name}',", "info")
        log_msg(f"    library_dir='{effective_biometrics_dir}',", "info")
        log_msg(f"    session='{session_override}',", "info")
        log_msg(f"    sheet={sheet},", "info")
        log_msg(f"    unknown='{unknown}'", "info")
        log_msg("  )", "info")
        log_msg("", "info")

        if tasks_to_export:
            log_msg(f"Exporting tasks: {', '.join(tasks_to_export)}", "step")

        result = convert_biometrics_table_to_prism_dataset(
            input_path=input_path,
            library_dir=str(effective_biometrics_dir),
            output_root=output_root,
            id_column=id_column,
            session_column=session_column,
            session=session_override,
            sheet=sheet,
            unknown=unknown,
            force=True,
            name=dataset_name,
            authors=[],
            tasks_to_export=tasks_to_export,
        )

        log_msg(f"Detected ID column: {result.id_column}", "success")
        if result.session_column:
            log_msg(f"Detected session column: {result.session_column}", "success")

        log_msg(f"Included tasks: {', '.join(result.tasks_included)}", "info")

        if result.unknown_columns:
            for col in result.unknown_columns:
                log_msg(f"Unknown column ignored: {col}", "warning")

        # Save to project if requested (but not in dry-run mode)
        if save_to_project and not dry_run:
            project_path = session.get("current_project_path")
            if project_path:
                project_path = Path(project_path)
                if project_path.exists():
                    log_msg(f"Saving output to project: {project_path.name}", "info")
                    # Merge output_root contents into project_path
                    for item in output_root.rglob("*"):
                        if item.is_file():
                            rel_path = item.relative_to(output_root)
                            dest = project_path / rel_path
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(item, dest)
                    log_msg("Project updated successfully!", "success")

                    # Register session in project.json
                    if (
                        session_override
                        and result
                        and getattr(result, "tasks_included", None)
                    ):
                        _register_session_in_project(
                            project_path,
                            session_override,
                            result.tasks_included,
                            "biometrics",
                            filename,
                            "biometrics",
                        )
                        log_msg(
                            f"Registered in project.json: ses-{session_override} → {', '.join(result.tasks_included)}",
                            "info",
                        )
                else:
                    log_msg(f"Project path not found: {project_path}", "error")
            else:
                log_msg(
                    "No project selected in session. Cannot save directly.", "warning"
                )

        # Create ZIP (but not in dry-run mode)
        zip_base64 = None
        if not dry_run:
            mem = io.BytesIO()
            with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                for p in output_root.rglob("*"):
                    if p.is_file():
                        arcname = p.relative_to(output_root)
                        zf.write(p, arcname.as_posix())
            mem.seek(0)

            zip_base64 = base64.b64encode(mem.read()).decode("utf-8")

        # Run validation if requested
        validation = None
        if request.form.get("validate") == "true":
            log_msg("Running PRISM validation on generated dataset...", "step")
            validation = {"errors": [], "warnings": [], "summary": {}}
            try:
                # Use run_validation which is already imported and handles the tuple return
                v_res = run_validation(
                    str(output_root),
                    schema_version="stable",
                    library_path=str(library_root),
                )
                if v_res and isinstance(v_res, tuple):
                    issues = v_res[0]
                    stats = v_res[1]

                    # Format results for the UI
                    from src.web.reporting_utils import format_validation_results

                    formatted = format_validation_results(
                        issues, stats, str(output_root)
                    )

                    # Extract flat lists for the simple log
                    for group in formatted.get("errors", []):
                        for f in group.get("files", []):
                            validation["errors"].append(
                                f"{group['code']}: {f['message']} ({f['file']})"
                            )

                    for group in formatted.get("warnings", []):
                        for f in group.get("files", []):
                            validation["warnings"].append(
                                f"{group['code']}: {f['message']} ({f['file']})"
                            )

                    validation["summary"] = {
                        "files_created": len(
                            list(output_root.rglob("*_biometrics.tsv"))
                        ),
                        "total_errors": formatted.get("summary", {}).get(
                            "total_errors", 0
                        ),
                        "total_warnings": formatted.get("summary", {}).get(
                            "total_warnings", 0
                        ),
                    }

                    # Include the full formatted results for the UI to display properly
                    validation["formatted"] = formatted

                    # Log errors to the web terminal
                    total_err = formatted.get("summary", {}).get("total_errors", 0)
                    total_warn = formatted.get("summary", {}).get("total_warnings", 0)

                    if total_err > 0:
                        log_msg(
                            f"✗ Validation failed with {total_err} error(s)", "error"
                        )
                        # Log the first 20 errors specifically to the terminal
                        count = 0
                        for group in formatted.get("errors", []):
                            for f in group.get("files", []):
                                if count < 20:
                                    # Clean up message for terminal (remove file path if redundant)
                                    msg = f["message"]
                                    if ": " in msg:
                                        msg = msg.split(": ", 1)[1]
                                    log_msg(f"  - {msg}", "error")
                                    count += 1
                        if total_err > 20:
                            log_msg(
                                f"  ... and {total_err - 20} more errors (see details below)",
                                "error",
                            )
                    else:
                        log_msg("✓ PRISM validation passed!", "success")

                    if total_warn > 0:
                        log_msg(f"⚠ {total_warn} warning(s) found", "warning")

            except Exception as val_err:
                log_msg(f"Validation error: {val_err}", "error")

        return jsonify({"log": log, "zip_base64": zip_base64, "validation": validation})

    except IdColumnNotDetectedError as e:
        return (
            jsonify(
                {
                    "error": "id_column_required",
                    "message": str(e),
                    "columns": e.available_columns,
                    "log": log,
                }
            ),
            409,
        )
    except Exception as e:
        return jsonify({"error": str(e), "log": log}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@conversion_bp.route("/api/check-sourcedata-physio", methods=["GET"])
def check_sourcedata_physio():
    """Check if sourcedata/physio folder exists in current project."""
    try:
        current_project_path = session.get("current_project_path")
        if not current_project_path:
            return jsonify({"exists": False, "message": "No project selected"}), 400

        project_path = Path(current_project_path)
        sourcedata_physio = project_path / "sourcedata" / "physio"

        exists = sourcedata_physio.exists() and sourcedata_physio.is_dir()

        if exists:
            # Count .raw and .vpd files (case-insensitive)
            all_files = list(sourcedata_physio.iterdir())
            physio_files = [
                f for f in all_files if f.suffix.lower() in [".raw", ".vpd"]
            ]
            file_count = len(physio_files)
        else:
            file_count = 0

        return (
            jsonify(
                {
                    "exists": exists,
                    "path": str(sourcedata_physio) if exists else None,
                    "message": (
                        f"Found sourcedata/physio folder with {file_count} files"
                        if exists
                        else "sourcedata/physio folder not found"
                    ),
                }
            ),
            200,
        )
    except Exception as e:
        return jsonify({"exists": False, "error": str(e)}), 500


@conversion_bp.route("/api/physio-convert", methods=["POST"])
def api_physio_convert():
    """Convert an uploaded Varioport file (.raw/.vpd) into EDF+ (.edf) + sidecar (.json) and return as ZIP."""
    if convert_varioport is None:
        return jsonify({"error": "Physio conversion (Varioport) not available"}), 500

    uploaded_file = request.files.get("raw") or request.files.get("file")
    if not uploaded_file or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": "Missing input file"}), 400

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".raw", ".vpd"}:
        return (
            jsonify({"error": "Only Varioport .raw and .vpd files are supported"}),
            400,
        )

    task = (request.form.get("task") or "rest").strip() or "rest"
    base_freq = (request.form.get("sampling_rate") or "").strip() or None
    try:
        base_freq_val = float(base_freq) if base_freq is not None else None
    except Exception:
        return jsonify({"error": "sampling_rate must be a number"}), 400

    tmp_dir = tempfile.mkdtemp(prefix="prism_physio_convert_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        out_edf = tmp_dir_path / (input_path.stem + ".edf")
        out_json = tmp_dir_path / (input_path.stem + ".json")

        convert_varioport(
            str(input_path),
            str(out_edf),
            str(out_json),
            task_name=task,
            base_freq=base_freq_val,
        )

        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            if out_edf.exists():
                zf.write(out_edf, out_edf.name)
            if out_json.exists():
                zf.write(out_json, out_json.name)
        mem.seek(0)

        return send_file(
            mem,
            mimetype="application/zip",
            as_attachment=True,
            download_name="varioport_edfplus.zip",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@conversion_bp.route("/api/batch-convert", methods=["POST"])
def api_batch_convert():
    """Batch convert physio/eyetracking files from a flat folder structure."""
    if not batch_convert_folder:
        return jsonify({"error": "Batch conversion not available"}), 500

    logs = []

    def log_callback(message: str, level: str = "info"):
        # Just store the plain message + level
        # Colors will be applied on the frontend based on the level
        logs.append({"message": message, "level": level})

    dataset_name = (request.form.get("dataset_name") or "Converted Dataset").strip()
    modality_filter = request.form.get("modality", "all")
    save_to_project = (request.form.get("save_to_project") or "false").lower() == "true"
    dest_root = (request.form.get("dest_root") or "root").strip().lower()
    if dest_root == "rawdata":
        dest_root = "root"
    if dest_root not in {"root", "sourcedata"}:
        dest_root = "root"
    flat_structure = (request.form.get("flat_structure") or "false").lower() == "true"
    sampling_rate_str = request.form.get("sampling_rate", "").strip()
    dry_run = (request.form.get("dry_run") or "false").lower() == "true"
    folder_path = request.form.get("folder_path", "").strip()

    try:
        sampling_rate = float(sampling_rate_str) if sampling_rate_str else None
    except ValueError:
        return jsonify({"error": "sampling_rate must be a number", "logs": logs}), 400

    files = request.files.getlist("files[]") or request.files.getlist("files")

    # If folder_path is provided, use it directly instead of uploaded files
    if folder_path:
        folder_path_obj = Path(folder_path)
        if not folder_path_obj.exists() or not folder_path_obj.is_dir():
            return (
                jsonify({"error": f"Folder not found: {folder_path}", "logs": logs}),
                400,
            )

        log_callback(f"📂 Using folder: {folder_path}", "info")

        tmp_dir = tempfile.mkdtemp(prefix="prism_batch_convert_")
        try:
            tmp_path = Path(tmp_dir)
            output_dir = tmp_path / "output"
            output_dir.mkdir()

            # Call batch_convert directly with the source folder
            result = batch_convert_folder(
                folder_path_obj,
                output_dir,
                physio_sampling_rate=sampling_rate,
                modality_filter=modality_filter,
                log_callback=log_callback,
                dry_run=dry_run,
            )

            # If not a dry-run, move files to project if save_to_project is true
            if not dry_run and save_to_project:
                p_path = session.get("current_project_path")
                if p_path:
                    project_root = Path(p_path)
                    if project_root.exists():
                        if dest_root == "sourcedata":
                            project_root = project_root / "sourcedata"
                        project_root.mkdir(parents=True, exist_ok=True)
                        # Copy converted files to project
                        for file in output_dir.rglob("*"):
                            if file.is_file():
                                rel_path = file.relative_to(output_dir)
                                dest_file = project_root / rel_path
                                dest_file.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(file, dest_file)

            return jsonify(
                {
                    "converted": result.success_count,
                    "errors": result.error_count,
                    "new_files": result.new_files,
                    "existing_files": result.existing_files,
                    "logs": logs,
                    "dry_run": dry_run,
                }
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    if not files:
        return (
            jsonify(
                {"error": "No files uploaded and no folder path provided", "logs": logs}
            ),
            400,
        )

    # Accept a wider range of extensions for the batch organizer
    valid_extensions = {
        ".raw",
        ".vpd",
        ".edf",
        ".tsv",
        ".tsv.gz",
        ".csv",
        ".txt",
        ".json",
        ".nii",
        ".nii.gz",
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
    }
    validated_files = []
    for f in files:
        if not f or not f.filename:
            continue
        filename = secure_filename(f.filename)

        # Handle .nii.gz and .tsv.gz
        lower_name = filename.lower()
        if lower_name.endswith(".nii.gz"):
            ext = ".nii.gz"
        elif lower_name.endswith(".tsv.gz"):
            ext = ".tsv.gz"
        else:
            ext = Path(filename).suffix.lower()

        if ext in valid_extensions and parse_bids_filename(filename):
            validated_files.append((f, filename))

    if not validated_files:
        return jsonify({"error": "No valid files to convert.", "logs": logs}), 400

    tmp_dir = tempfile.mkdtemp(prefix="prism_batch_convert_")
    warnings = []
    warned_subjects = set()
    try:
        tmp_path = Path(tmp_dir)
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()

        for f, filename in validated_files:
            f.save(str(input_dir / filename))

        result = batch_convert_folder(
            input_dir,
            output_dir,
            physio_sampling_rate=sampling_rate,
            modality_filter=modality_filter,
            log_callback=log_callback,
            dry_run=dry_run,
        )

        if dry_run:
            # For dry run, just return the logs (no file creation)
            return jsonify(
                {
                    "converted": result.success_count,
                    "errors": result.error_count,
                    "new_files": result.new_files,
                    "existing_files": result.existing_files,
                    "logs": logs,
                    "dry_run": True,
                }
            )

        create_dataset_description(output_dir, name=dataset_name)

        # Check for conflicts (files with different content)
        if result.conflicts:
            conflicts_info = [
                {"path": str(c.output_path.relative_to(output_dir)), "reason": c.reason}
                for c in result.conflicts
            ]
            return (
                jsonify(
                    {
                        "error": f"File conflicts detected: {len(result.conflicts)} files already exist with different content. Please use different names or delete existing files.",
                        "conflicts": conflicts_info,
                        "logs": logs,
                    }
                ),
                409,
            )

        project_saved = False
        project_root = None
        if save_to_project:
            p_path = session.get("current_project_path")
            if p_path:
                project_root = Path(p_path)
                if project_root.exists():
                    if dest_root == "sourcedata":
                        project_root = project_root / "sourcedata"
                    project_root.mkdir(parents=True, exist_ok=True)
                else:
                    warnings.append(
                        f"Project path not found: {p_path}. Copy to project skipped."
                    )
                    project_root = None
            else:
                warnings.append("No active project selected; copy to project skipped.")

        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in output_dir.rglob("*"):
                if file_path.is_file():
                    rel_path = file_path.relative_to(output_dir)
                    zf.write(file_path, rel_path)

                    if project_root:
                        # Determine destination path based on flat_structure option
                        if flat_structure and dest_root == "sourcedata":
                            # Flat structure: copy files to sourcedata/modality/ without sub-/ses- hierarchy
                            # Determine modality from filename
                            file_modality = (
                                modality_filter
                                if modality_filter != "all"
                                else "physio"
                            )
                            dest_path = project_root / file_modality / rel_path.name
                            log_callback(
                                f"Flat copy: {rel_path.name} → {dest_root}/{file_modality}/{rel_path.name}"
                            )
                        else:
                            # PRISM structure: preserve sub-XXX/ses-YYY/modality/ hierarchy
                            # Warn if subject folder is being created
                            bids = (
                                parse_bids_filename(rel_path.name)
                                if parse_bids_filename
                                else None
                            )
                            subject_label = None
                            if bids and bids.get("sub"):
                                subject_label = bids.get("sub")
                            else:
                                m = re.search(r"(sub-[A-Za-z0-9]+)", rel_path.name)
                                if m:
                                    subject_label = m.group(1)

                            if subject_label:
                                subject_dir = project_root / subject_label
                                if (
                                    not subject_dir.exists()
                                    and subject_label not in warned_subjects
                                ):
                                    warnings.append(
                                        f"Subject folder {subject_label} did not exist and will be created in project."
                                    )
                                    warned_subjects.add(subject_label)

                            dest_path = project_root / rel_path

                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(file_path, dest_path)
                        project_saved = True

        import base64

        zip_base64 = base64.b64encode(mem.read()).decode("utf-8")

        return jsonify(
            {
                "status": "success",
                "log": "\n".join([log_entry["message"] for log_entry in logs]),
                "zip": zip_base64,
                "converted": result.success_count,
                "errors": result.error_count,
                "project_saved": project_saved,
                "warnings": warnings,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e), "logs": logs}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@conversion_bp.route("/api/physio-rename", methods=["POST"])
def api_physio_rename():
    """Rename uploaded files based on a regex pattern and return a ZIP."""
    pattern = request.form.get("pattern", "")
    replacement = request.form.get("replacement", "")
    dry_run = request.form.get("dry_run", "false").lower() == "true"
    organize = request.form.get("organize", "false").lower() == "true"
    modality = request.form.get("modality", "physio")
    save_to_project = request.form.get("save_to_project", "false").lower() == "true"
    dest_root = (request.form.get("dest_root") or "root").strip().lower()
    if dest_root == "rawdata":
        dest_root = "root"
    if dest_root not in {"root", "sourcedata"}:
        dest_root = "root"
    flat_structure = (request.form.get("flat_structure") or "false").lower() == "true"

    files = request.files.getlist("files[]") or request.files.getlist("files")

    # If dry run, we might just have filenames in a list
    filenames = request.form.getlist("filenames[]") or request.form.getlist("filenames")

    if not files and not filenames and not dry_run:
        return jsonify({"error": "No files or filenames provided"}), 400

    try:
        regex = re.compile(pattern)
    except re.error as e:
        return jsonify({"error": f"Invalid regex: {str(e)}"}), 400

    results = []
    warnings = []
    warned_subjects = set()

    if dry_run:
        # Use filenames if provided, else use uploaded files' names
        source_names = (
            filenames if filenames else [f.filename for f in files if f.filename]
        )
        for fname in source_names:
            try:
                raw_name = Path(fname).name
                new_name = regex.sub(replacement, raw_name)
                new_name = _normalize_filename(new_name)

                # Determine the path within the ZIP (for preview)
                zip_path = new_name
                if organize:
                    bids = None
                    if parse_bids_filename:
                        bids = parse_bids_filename(new_name)

                    if bids:
                        sub = bids.get("sub")
                        ses = bids.get("ses")
                        parts = [sub]
                        if ses:
                            parts.append(ses)
                        parts.append(modality)
                        parts.append(new_name)
                        zip_path = "/".join(parts)

                results.append(
                    {"old": fname, "new": new_name, "path": zip_path, "success": True}
                )
            except Exception as e:
                results.append({"old": fname, "new": str(e), "success": False})
        return jsonify({"results": results, "warnings": warnings})

    # Actual renaming and zipping
    if not files:
        return jsonify({"error": "No files uploaded for renaming"}), 400

    mem = io.BytesIO()
    project_root = None
    if save_to_project:
        p_path = session.get("current_project_path")
        if p_path:
            project_root = Path(p_path)
            if project_root.exists():
                if dest_root == "sourcedata":
                    project_root = project_root / "sourcedata"
                project_root.mkdir(parents=True, exist_ok=True)
            else:
                warnings.append(
                    f"Project path not found: {p_path}. Copy to project skipped."
                )
                project_root = None
        else:
            warnings.append("No active project selected; copy to project skipped.")
    try:
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                if not f or not f.filename:
                    continue
                old_name = Path(f.filename).name

                try:
                    new_name = regex.sub(replacement, old_name)
                    new_name = _normalize_filename(new_name)

                    # Determine the path within the ZIP
                    zip_path = new_name
                    if organize:
                        # Try to parse BIDS components to build structure
                        bids = None
                        if parse_bids_filename:
                            bids = parse_bids_filename(new_name)

                        if bids:
                            sub = bids.get("sub")
                            ses = bids.get("ses")

                            parts = [sub]
                            if ses:
                                parts.append(ses)
                            parts.append(modality)
                            parts.append(new_name)

                            zip_path = "/".join(parts)

                    f_content = f.read()
                    zf.writestr(zip_path, f_content)

                    if project_root:
                        # Determine destination path based on flat_structure option
                        if flat_structure and dest_root == "sourcedata":
                            # Flat structure: copy files to sourcedata/modality/ without sub-/ses- hierarchy
                            dest_path = project_root / modality / new_name
                        else:
                            # PRISM structure: preserve sub-XXX/ses-YYY/modality/ hierarchy
                            dest_path = project_root / Path(zip_path)

                            # Warn if subject folder does not yet exist (but still allow creation)
                            subject_label = None
                            if parse_bids_filename:
                                bids_parts = parse_bids_filename(new_name)
                                if bids_parts:
                                    subject_label = bids_parts.get("sub")
                            if not subject_label:
                                m = re.search(r"(sub-[A-Za-z0-9]+)", new_name)
                                if m:
                                    subject_label = m.group(1)

                            if subject_label:
                                subject_dir = project_root / subject_label
                                if (
                                    not subject_dir.exists()
                                    and subject_label not in warned_subjects
                                ):
                                    warnings.append(
                                        f"Subject folder {subject_label} did not exist and will be created in project."
                                    )
                                    warned_subjects.add(subject_label)

                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(dest_path, "wb") as out_f:
                            out_f.write(f_content)
                    results.append(
                        {
                            "old": old_name,
                            "new": new_name,
                            "success": True,
                            "path": zip_path,
                        }
                    )
                except Exception as e:
                    results.append({"old": old_name, "new": str(e), "success": False})

        mem.seek(0)
        import base64

        zip_base64 = base64.b64encode(mem.read()).decode("utf-8")

        return jsonify(
            {
                "status": "success",
                "results": results,
                "zip": zip_base64,
                "project_saved": bool(project_root),
                "warnings": warnings,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


 
