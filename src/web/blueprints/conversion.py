"""
Conversion Blueprint for PRISM.
Handles survey, biometrics, and physio conversion routes.
"""

import os
import io
import re
import json
import uuid
import shutil
import tempfile
import zipfile
import base64
from pathlib import Path
from flask import Blueprint, request, jsonify, send_file, render_template, current_app
from werkzeug.utils import secure_filename
from src.web.utils import list_survey_template_languages, sanitize_jsonable
from src.web import run_validation

# Import conversion logic
try:
    from src.converters.survey import (
        convert_survey_xlsx_to_prism_dataset,
        convert_survey_lsa_to_prism_dataset,
        infer_lsa_metadata,
    )
except ImportError:
    convert_survey_xlsx_to_prism_dataset = None
    convert_survey_lsa_to_prism_dataset = None
    infer_lsa_metadata = None

try:
    from src.converters.biometrics import convert_biometrics_table_to_prism_dataset
except ImportError:
    convert_biometrics_table_to_prism_dataset = None

try:
    from helpers.physio.convert_varioport import convert_varioport
except ImportError:
    convert_varioport = None

try:
    from src.batch_convert import (
        batch_convert_folder,
        create_dataset_description,
        parse_bids_filename,
    )
except ImportError:
    batch_convert_folder = None
    create_dataset_description = None
    parse_bids_filename = None

conversion_bp = Blueprint('conversion', __name__)

# Batch conversion job tracking
_batch_convert_jobs = {}

@conversion_bp.route("/api/survey-languages", methods=["GET"])
def api_survey_languages():
    """List available languages for the selected survey template library folder."""
    library_path = (request.args.get("library_path") or "").strip()
    base_dir = Path(current_app.root_path)
    if not library_path:
        preferred = (base_dir / "library" / "survey_i18n").resolve()
        fallback = (base_dir / "survey_library").resolve()
        if preferred.exists() and any(preferred.glob("survey-*.json")):
            library_path = str(preferred)
        else:
            library_path = str(fallback)

    # Check structure of library root
    library_root = Path(library_path)
    structure_info = {
        "has_survey_folder": False,
        "has_biometrics_folder": False,
        "has_participants_json": False,
        "missing_items": [],
    }

    # Check for expected items
    survey_dir = library_root / "survey"
    biometrics_dir = library_root / "biometrics"
    participants_json = library_root / "participants.json"
    # Also check parent directory for participants.json (for project/library/ structure)
    parent_participants_json = library_root.parent / "participants.json"

    structure_info["has_survey_folder"] = survey_dir.is_dir()
    structure_info["has_biometrics_folder"] = biometrics_dir.is_dir()
    # Accept participants.json from library folder OR parent (project root)
    structure_info["has_participants_json"] = (
        participants_json.is_file() or parent_participants_json.is_file()
    )

    # Build missing items list for survey conversion
    if not structure_info["has_survey_folder"]:
        structure_info["missing_items"].append("survey/")
    if not structure_info["has_participants_json"]:
        structure_info["missing_items"].append("participants.json (or ../participants.json)")

    # Determine effective survey directory
    if survey_dir.is_dir():
        effective_survey_dir = str(survey_dir)
    else:
        effective_survey_dir = library_path

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

@conversion_bp.route("/api/survey-convert", methods=["POST"])
def api_survey_convert():
    """Convert an uploaded survey file (.xlsx or .lsa) to a PRISM dataset and return it as a zip."""
    if (
        not convert_survey_xlsx_to_prism_dataset
        and not convert_survey_lsa_to_prism_dataset
    ):
        return jsonify({"error": "Survey conversion module not available"}), 500

    uploaded_file = request.files.get("excel") or request.files.get("file")
    alias_upload = request.files.get("alias") or request.files.get("alias_file")
    library_path = (request.form.get("library_path") or "").strip()

    if not uploaded_file or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": "Missing input file"}), 400

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".xlsx", ".lsa", ".csv", ".tsv"}:
        return jsonify({"error": "Supported formats: .xlsx, .lsa, .csv, .tsv"}), 400

    alias_filename = None
    if alias_upload and getattr(alias_upload, "filename", ""):
        alias_filename = secure_filename(alias_upload.filename)
        alias_suffix = Path(alias_filename).suffix.lower()
        if alias_suffix and alias_suffix not in {".tsv", ".txt"}:
            return jsonify({"error": "Alias file must be a .tsv or .txt mapping file"}), 400

    if not library_path:
        return jsonify({"error": "Survey template library path is required."}), 400

    if not os.path.exists(library_path) or not os.path.isdir(library_path):
        return jsonify({"error": f"Library path is not a directory: {library_path}"}), 400

    library_root = Path(library_path)
    survey_dir = library_root / "survey"
    effective_survey_dir = survey_dir if survey_dir.is_dir() else library_root

    survey_templates = list(effective_survey_dir.glob("survey-*.json"))
    if not survey_templates:
        return jsonify({"error": f"No survey templates found in: {effective_survey_dir}"}), 400

    survey_filter = (request.form.get("survey") or "").strip() or None
    id_column = (request.form.get("id_column") or "").strip() or None
    session_column = (request.form.get("session_column") or "").strip() or None
    session_override = (request.form.get("session") or "").strip() or None
    sheet = (request.form.get("sheet") or "0").strip() or 0
    unknown = (request.form.get("unknown") or "warn").strip() or "warn"
    dataset_name = (request.form.get("dataset_name") or "").strip() or None
    language = (request.form.get("language") or "").strip() or None
    strict_levels_raw = (request.form.get("strict_levels") or "").strip().lower()
    strict_levels = strict_levels_raw in {"1", "true", "yes", "on"}

    tmp_dir = tempfile.mkdtemp(prefix="prism_survey_convert_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        alias_path = None
        if alias_filename:
            alias_path = tmp_dir_path / alias_filename
            alias_upload.save(str(alias_path))

        output_root = tmp_dir_path / "prism_dataset"
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

        if suffix in {".xlsx", ".csv", ".tsv"}:
            convert_survey_xlsx_to_prism_dataset(
                input_path=input_path,
                library_dir=str(effective_survey_dir),
                output_root=output_root,
                survey=survey_filter,
                id_column=id_column,
                session_column=session_column,
                session=session_override,
                sheet=sheet,
                unknown=unknown,
                dry_run=False,
                force=True,
                name=dataset_name,
                authors=["prism-studio"],
                language=language,
                alias_file=alias_path,
            )
        elif suffix == ".lsa":
            convert_survey_lsa_to_prism_dataset(
                input_path=input_path,
                library_dir=str(effective_survey_dir),
                output_root=output_root,
                survey=survey_filter,
                id_column=id_column,
                session_column=session_column,
                session=session_override,
                unknown=unknown,
                dry_run=False,
                force=True,
                name=dataset_name,
                authors=["prism-studio"],
                language=language,
                alias_file=alias_path,
                strict_levels=True if strict_levels else None,
            )

        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in output_root.rglob("*"):
                if p.is_file():
                    arcname = p.relative_to(output_root)
                    zf.write(p, arcname.as_posix())
        mem.seek(0)

        resp = send_file(
            mem,
            mimetype="application/zip",
            as_attachment=True,
            download_name="prism_survey_dataset.zip",
        )

        if detected_language:
            resp.headers["X-Prism-Detected-Language"] = str(detected_language)
        if detected_platform:
            resp.headers["X-Prism-Detected-SoftwarePlatform"] = str(detected_platform)
        if detected_version:
            resp.headers["X-Prism-Detected-SoftwareVersion"] = str(detected_version)

        return resp
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

@conversion_bp.route("/api/survey-convert-validate", methods=["POST"])
def api_survey_convert_validate():
    """Convert survey and run validation immediately, returning results + ZIP as base64."""
    if not convert_survey_xlsx_to_prism_dataset and not convert_survey_lsa_to_prism_dataset:
        return jsonify({"error": "Survey conversion module not available"}), 500

    log_messages = []
    conversion_warnings = []

    def add_log(message, level="info"):
        log_messages.append({"message": message, "level": level})

    uploaded_file = request.files.get("excel") or request.files.get("file")
    alias_upload = request.files.get("alias") or request.files.get("alias_file")
    library_path = (request.form.get("library_path") or "").strip()

    if not uploaded_file or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": "Missing input file", "log": log_messages}), 400

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".xlsx", ".lsa", ".csv", ".tsv"}:
        return jsonify({"error": "Supported formats: .xlsx, .lsa, .csv, .tsv", "log": log_messages}), 400

    if not library_path or not os.path.isdir(library_path):
        return jsonify({"error": "Valid library path is required.", "log": log_messages}), 400

    library_root = Path(library_path)
    survey_dir = library_root / "survey"
    effective_survey_dir = survey_dir if survey_dir.is_dir() else library_root

    survey_templates = list(effective_survey_dir.glob("survey-*.json"))
    if not survey_templates:
        return jsonify({"error": f"No survey templates found in: {effective_survey_dir}", "log": log_messages}), 400

    survey_filter = (request.form.get("survey") or "").strip() or None
    id_column = (request.form.get("id_column") or "").strip() or None
    session_column = (request.form.get("session_column") or "").strip() or None
    session_override = (request.form.get("session") or "").strip() or None
    sheet = (request.form.get("sheet") or "0").strip() or 0
    unknown = (request.form.get("unknown") or "warn").strip() or "warn"
    dataset_name = (request.form.get("dataset_name") or "").strip() or None
    language = (request.form.get("language") or "").strip() or None
    strict_levels_raw = (request.form.get("strict_levels") or "").strip().lower()
    strict_levels = strict_levels_raw in {"1", "true", "yes", "on"}

    tmp_dir = tempfile.mkdtemp(prefix="prism_survey_convert_validate_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        alias_path = None
        if alias_upload and getattr(alias_upload, "filename", ""):
            alias_path = tmp_dir_path / secure_filename(alias_upload.filename)
            alias_upload.save(str(alias_path))

        output_root = tmp_dir_path / "prism_dataset"
        add_log("Starting data conversion...", "info")

        # For text files, log the head to help debug delimiter issues
        if suffix in {".csv", ".tsv"}:
            try:
                with open(input_path, "r", encoding="utf-8", errors="replace") as f:
                    head_lines = []
                    for i in range(4):
                        line = f.readline()
                        if not line:
                            break
                        head_lines.append(f"  [{i+1}] {line.strip()}")
                    if head_lines:
                        add_log("File head (first 4 lines):\n" + "\n".join(head_lines), "info")
            except Exception:
                pass

        if strict_levels:
            add_log("Strict Levels Validation: enabled", "info")

        convert_result = None
        if suffix in {".xlsx", ".csv", ".tsv"}:
            convert_result = convert_survey_xlsx_to_prism_dataset(
                input_path=input_path, library_dir=str(effective_survey_dir),
                output_root=output_root, survey=survey_filter, id_column=id_column,
                session_column=session_column, session=session_override,
                sheet=sheet, unknown=unknown,
                dry_run=False, force=True, name=dataset_name, authors=["prism-studio"],
                language=language, alias_file=alias_path,
            )
        elif suffix == ".lsa":
            convert_result = convert_survey_lsa_to_prism_dataset(
                input_path=input_path, library_dir=str(effective_survey_dir),
                output_root=output_root, survey=survey_filter, id_column=id_column,
                session_column=session_column, session=session_override,
                unknown=unknown, dry_run=False,
                force=True, name=dataset_name, authors=["prism-studio"],
                language=language, alias_file=alias_path,
                strict_levels=True if strict_levels else None,
            )
        add_log("Conversion completed", "success")

        # Process warnings and missing cells
        if convert_result and getattr(convert_result, "missing_cells_by_subject", None):
            missing_counts = {sid: cnt for sid, cnt in convert_result.missing_cells_by_subject.items() if cnt > 0}
            if missing_counts:
                conversion_warnings.append(f"Missing responses normalized: {sum(missing_counts.values())} cells.")

        if convert_result and getattr(convert_result, "conversion_warnings", None):
            conversion_warnings.extend(convert_result.conversion_warnings)

        # Run validation
        add_log("Running validation...", "info")
        validation_result = {"errors": [], "warnings": [], "summary": {}}
        if request.form.get("validate") == "true":
            try:
                v_res = run_validation(
                    str(output_root), 
                    schema_version="stable",
                    library_path=str(effective_survey_dir)
                )
                if v_res and isinstance(v_res, tuple):
                    issues = v_res[0]
                    stats = v_res[1]
                    
                    # Format results for the UI
                    from src.web.reporting_utils import format_validation_results
                    formatted = format_validation_results(issues, stats, str(output_root))
                    
                    # Include the full formatted results for the UI to display properly
                    # We use a new dict to avoid circular references
                    validation_result = {"formatted": formatted}
                    validation_result.update(formatted)
                    
                    # Log errors to the web terminal
                    total_err = formatted.get("summary", {}).get("total_errors", 0)
                    total_warn = formatted.get("summary", {}).get("total_warnings", 0)
                    
                    if total_err > 0:
                        add_log(f"✗ Validation failed with {total_err} error(s)", "error")
                        # Log the first 20 errors specifically to the terminal
                        count = 0
                        for group in formatted.get("errors", []):
                            for f in group.get("files", []):
                                if count < 20:
                                    # Clean up message for terminal
                                    msg = f["message"]
                                    if ": " in msg:
                                        msg = msg.split(": ", 1)[1]
                                    add_log(f"  - {msg}", "error")
                                    count += 1
                        if total_err > 20:
                            add_log(f"  ... and {total_err - 20} more errors (see details below)", "error")
                    else:
                        add_log("✓ PRISM validation passed!", "success")

                    if total_warn > 0:
                        add_log(f"⚠ {total_warn} warning(s) found", "warning")
                
            except Exception as val_err:
                validation_result["warnings"].append(f"Validation error: {str(val_err)}")

        # Add conversion warnings to the final result
        if conversion_warnings:
            if "warnings" not in validation_result:
                validation_result["warnings"] = []
            
            # Add as a group if we have formatted results
            if "formatted" in validation_result:
                conv_group = {
                    "code": "CONVERSION",
                    "message": "Conversion Warnings",
                    "description": "Issues encountered during data conversion",
                    "files": [{"file": filename, "message": w} for w in conversion_warnings],
                    "count": len(conversion_warnings)
                }
                validation_result["warnings"].append(conv_group)
                if "summary" in validation_result:
                    validation_result["summary"]["total_warnings"] += len(conversion_warnings)
            else:
                # Simple string list for non-formatted results
                validation_result["warnings"].extend(conversion_warnings)

        # Create ZIP
        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in output_root.rglob("*"):
                if p.is_file(): zf.write(p, p.relative_to(output_root).as_posix())
        mem.seek(0)
        zip_base64 = base64.b64encode(mem.read()).decode("utf-8")

        return jsonify(sanitize_jsonable({
            "success": True, "log": log_messages,
            "validation": validation_result, "zip_base64": zip_base64,
        }))
    except Exception as e:
        return jsonify({"error": str(e), "log": log_messages}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

@conversion_bp.route("/api/biometrics-check-library", methods=["GET"])
def api_biometrics_check_library():
    """Check the structure of a biometrics template library folder."""
    library_path = (request.args.get("library_path") or "").strip()
    if not library_path: return jsonify({"error": "No library path provided"}), 400

    library_root = Path(library_path)
    biometrics_dir = library_root / "biometrics"
    # Also check parent directory for participants.json (for project/library/ structure)
    has_participants = (
        (library_root / "participants.json").is_file() or
        (library_root.parent / "participants.json").is_file()
    )

    structure_info = {
        "has_survey_folder": (library_root / "survey").is_dir(),
        "has_biometrics_folder": biometrics_dir.is_dir(),
        "has_participants_json": has_participants,
        "missing_items": [],
        "template_count": 0,
    }

    if not structure_info["has_biometrics_folder"]: structure_info["missing_items"].append("biometrics/")
    if not structure_info["has_participants_json"]: structure_info["missing_items"].append("participants.json (or ../participants.json)")
    if biometrics_dir.is_dir():
        structure_info["template_count"] = len(list(biometrics_dir.glob("biometrics-*.json")))

    return jsonify({"structure": structure_info})

@conversion_bp.route("/api/biometrics-detect", methods=["POST"])
def api_biometrics_detect():
    """Detect which biometrics tasks are present in the uploaded file."""
    from src.converters.biometrics import detect_biometrics_in_table

    uploaded_file = request.files.get("data") or request.files.get("file")
    library_path = (request.form.get("library_path") or "").strip()

    if not uploaded_file or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": "Missing input file"}), 400

    if not library_path:
        return jsonify({"error": "Biometrics template library path is required."}), 400

    filename = secure_filename(uploaded_file.filename)
    tmp_dir = tempfile.mkdtemp(prefix="prism_biometrics_detect_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        library_root = Path(library_path)
        biometrics_dir = library_root / "biometrics"
        effective_biometrics_dir = biometrics_dir if biometrics_dir.is_dir() else library_root

        detected_tasks = detect_biometrics_in_table(
            input_path=input_path,
            library_dir=effective_biometrics_dir,
            sheet=(request.form.get("sheet") or "0").strip() or 0
        )

        return jsonify({"tasks": detected_tasks})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

@conversion_bp.route("/api/biometrics-convert", methods=["POST"])
def api_biometrics_convert():
    """Convert an uploaded biometrics table (.csv or .xlsx) into a PRISM/BIDS-style dataset ZIP."""
    if not convert_biometrics_table_to_prism_dataset:
        return jsonify({"error": "Biometrics conversion module not available"}), 500

    uploaded_file = request.files.get("data") or request.files.get("file")
    library_path = (request.form.get("library_path") or "").strip()

    if not uploaded_file or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": "Missing input file"}), 400

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".csv", ".xlsx", ".tsv"}:
        return jsonify({"error": "Supported formats: .csv, .xlsx, .tsv"}), 400

    if not library_path:
        return jsonify({"error": "Biometrics template library path is required."}), 400

    if not os.path.exists(library_path) or not os.path.isdir(library_path):
        return jsonify({"error": f"Library path is not a directory: {library_path}"}), 400

    library_root = Path(library_path)
    biometrics_dir = library_root / "biometrics"
    effective_biometrics_dir = biometrics_dir if biometrics_dir.is_dir() else library_root

    biometrics_templates = list(effective_biometrics_dir.glob("biometrics-*.json"))
    if not biometrics_templates:
        return jsonify({"error": f"No biometrics templates found in: {effective_biometrics_dir}"}), 400

    id_column = (request.form.get("id_column") or "").strip() or None
    session_column = (request.form.get("session_column") or "").strip() or None
    session_override = (request.form.get("session") or "").strip() or None
    sheet = (request.form.get("sheet") or "0").strip() or 0
    unknown = (request.form.get("unknown") or "warn").strip() or "warn"
    dataset_name = (request.form.get("dataset_name") or "").strip() or None
    
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

        log_msg(f"Starting biometrics conversion for {filename}", "info")
        
        # For text files, log the head to help debug delimiter issues
        if suffix in {".csv", ".tsv"}:
            try:
                with open(input_path, "r", encoding="utf-8", errors="replace") as f:
                    head_lines = []
                    for i in range(4):
                        line = f.readline()
                        if not line:
                            break
                        head_lines.append(f"  [{i+1}] {line.strip()}")
                    if head_lines:
                        log_msg("File head (first 4 lines):\n" + "\n".join(head_lines), "info")
            except Exception:
                pass

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
            authors=["prism-studio"],
            tasks_to_export=tasks_to_export
        )

        log_msg(f"Detected ID column: {result.id_column}", "success")
        if result.session_column:
            log_msg(f"Detected session column: {result.session_column}", "success")
        
        log_msg(f"Included tasks: {', '.join(result.tasks_included)}", "info")
        
        if result.unknown_columns:
            for col in result.unknown_columns:
                log_msg(f"Unknown column ignored: {col}", "warning")

        # Create ZIP
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
                    library_path=str(library_root)
                )
                if v_res and isinstance(v_res, tuple):
                    issues = v_res[0]
                    stats = v_res[1]
                    
                    # Format results for the UI
                    from src.web.reporting_utils import format_validation_results
                    formatted = format_validation_results(issues, stats, str(output_root))
                    
                    # Extract flat lists for the simple log
                    for group in formatted.get("errors", []):
                        for f in group.get("files", []):
                            validation["errors"].append(f"{group['code']}: {f['message']} ({f['file']})")
                    
                    for group in formatted.get("warnings", []):
                        for f in group.get("files", []):
                            validation["warnings"].append(f"{group['code']}: {f['message']} ({f['file']})")
                    
                    validation["summary"] = {
                        "files_created": len(list(output_root.rglob("*_biometrics.tsv"))),
                        "total_errors": formatted.get("summary", {}).get("total_errors", 0),
                        "total_warnings": formatted.get("summary", {}).get("total_warnings", 0)
                    }
                    
                    # Include the full formatted results for the UI to display properly
                    validation["formatted"] = formatted
                    
                    # Log errors to the web terminal
                    total_err = formatted.get("summary", {}).get("total_errors", 0)
                    total_warn = formatted.get("summary", {}).get("total_warnings", 0)
                    
                    if total_err > 0:
                        log_msg(f"✗ Validation failed with {total_err} error(s)", "error")
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
                            log_msg(f"  ... and {total_err - 20} more errors (see details below)", "error")
                    else:
                        log_msg("✓ PRISM validation passed!", "success")

                    if total_warn > 0:
                        log_msg(f"⚠ {total_warn} warning(s) found", "warning")
                
            except Exception as val_err:
                log_msg(f"Validation error: {val_err}", "error")

        return jsonify({
            "log": log,
            "zip_base64": zip_base64,
            "validation": validation
        })

    except Exception as e:
        return jsonify({"error": str(e), "log": log}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

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
        return jsonify({"error": "Only Varioport .raw and .vpd files are supported"}), 400

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

    job_id = str(uuid.uuid4())[:8]
    logs = []

    def log_callback(message: str, level: str = "info"):
        logs.append({"message": message, "level": level})

    dataset_name = (request.form.get("dataset_name") or "Converted Dataset").strip()
    modality_filter = request.form.get("modality", "all")
    sampling_rate_str = request.form.get("sampling_rate", "").strip()
    return_format = request.form.get("format", "zip")

    try:
        sampling_rate = float(sampling_rate_str) if sampling_rate_str else None
    except ValueError:
        return jsonify({"error": "sampling_rate must be a number", "logs": logs}), 400

    files = request.files.getlist("files[]") or request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files uploaded", "logs": logs}), 400

    # Accept a wider range of extensions for the batch organizer
    valid_extensions = {".raw", ".vpd", ".edf", ".tsv", ".csv", ".txt", ".json", ".nii", ".nii.gz", ".pdf", ".png", ".jpg", ".jpeg"}
    validated_files = []
    for f in files:
        if not f or not f.filename: continue
        filename = secure_filename(f.filename)
        
        # Handle .nii.gz
        if filename.lower().endswith(".nii.gz"):
            ext = ".nii.gz"
        else:
            ext = Path(filename).suffix.lower()
            
        if ext in valid_extensions and parse_bids_filename(filename):
            validated_files.append((f, filename))

    if not validated_files:
        return jsonify({"error": "No valid files to convert.", "logs": logs}), 400

    tmp_dir = tempfile.mkdtemp(prefix="prism_batch_convert_")
    try:
        tmp_path = Path(tmp_dir)
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir(); output_dir.mkdir()

        for f, filename in validated_files:
            f.save(str(input_dir / filename))

        result = batch_convert_folder(
            input_dir, output_dir,
            physio_sampling_rate=sampling_rate,
            modality_filter=modality_filter,
            log_callback=log_callback,
        )

        create_dataset_description(output_dir, name=dataset_name)

        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in output_dir.rglob("*"):
                if file_path.is_file():
                    zf.write(file_path, file_path.relative_to(output_dir))
        mem.seek(0)

        import base64
        zip_base64 = base64.b64encode(mem.read()).decode('utf-8')
        
        return jsonify({
            "status": "success",
            "log": "\n".join([l["message"] for l in logs]),
            "zip": zip_base64,
            "converted": result.success_count,
            "errors": result.error_count
        })
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
    
    if dry_run:
        # Use filenames if provided, else use uploaded files' names
        source_names = filenames if filenames else [f.filename for f in files if f.filename]
        for fname in source_names:
            try:
                new_name = regex.sub(replacement, fname)
                
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
                        if ses: parts.append(ses)
                        parts.append(modality)
                        parts.append(new_name)
                        zip_path = "/".join(parts)
                
                results.append({"old": fname, "new": new_name, "path": zip_path, "success": True})
            except Exception as e:
                results.append({"old": fname, "new": str(e), "success": False})
        return jsonify({"results": results})

    # Actual renaming and zipping
    if not files:
        return jsonify({"error": "No files uploaded for renaming"}), 400

    mem = io.BytesIO()
    try:
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                if not f or not f.filename: continue
                old_name = secure_filename(f.filename)
                
                try:
                    new_name = regex.sub(replacement, old_name)
                    
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
                    results.append({"old": old_name, "new": new_name, "success": True, "path": zip_path})
                except Exception as e:
                    results.append({"old": old_name, "new": str(e), "success": False})
        
        mem.seek(0)
        import base64
        zip_base64 = base64.b64encode(mem.read()).decode('utf-8')
        
        return jsonify({
            "status": "success",
            "results": results,
            "zip": zip_base64
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
