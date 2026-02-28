"""
Biometrics conversion logic for the Prism Web UI.
Extracted from conversion.py to reduce module size.
"""

import io
import re
import shutil
import tempfile
import zipfile
import base64
import logging
from pathlib import Path
from typing import Any
from flask import request, jsonify, session
from werkzeug.utils import secure_filename
from src.web.validation import run_validation

# Shared utilities
from .conversion_utils import (
    participant_json_candidates,
    log_file_head,
    resolve_effective_library_path,
)
from src.web.services.project_registration import register_session_in_project

# Safe imports for optional dependencies
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

    participant_candidates = participant_json_candidates(library_root)
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


def api_biometrics_detect():
    """Detect which biometrics tasks are present in the uploaded file."""
    # Local import to avoid circular dependencies if any
    try:
        from src.converters.biometrics import detect_biometrics_in_table
    except ImportError:
        return jsonify({"error": "Biometrics conversion module not available"}), 500

    uploaded_file = request.files.get("data") or request.files.get("file")

    if not uploaded_file or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": "Missing input file"}), 400

    # Automatically resolve library path (project first, then global)
    try:
        library_root = resolve_effective_library_path()
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
        library_root = resolve_effective_library_path()
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
        log_file_head(input_path, suffix, log_msg)

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
                        register_session_in_project(
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
