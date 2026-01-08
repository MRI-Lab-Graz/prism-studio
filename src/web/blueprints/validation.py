import os
import json
import tempfile
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app, send_file, session
from werkzeug.utils import secure_filename

from src.web import (
    is_system_file,
    format_validation_results,
    run_validation,
    update_progress,
    get_progress,
    process_folder_upload as _process_folder_upload,
    process_zip_upload as _process_zip_upload
)

validation_bp = Blueprint("validation", __name__)

@validation_bp.route("/api/progress/<job_id>")
def get_validation_progress(job_id):
    """Get progress for a validation job (polled by UI)."""
    progress_data = get_progress(job_id)
    return jsonify(progress_data)

@validation_bp.route("/validate")
def validate_dataset():
    """Dataset validation page with upload form"""
    # Get available schema versions
    schema_dir = os.path.join(current_app.root_path, "schemas")
    try:
        from src.schema_manager import get_available_schema_versions
        available_versions = get_available_schema_versions(schema_dir)
    except Exception as e:
        print(f"Warning: Could not load schema versions: {e}")
        available_versions = ["stable"]

    default_library_path = ""
    project_path = session.get("current_project_path")
    if project_path:
        candidate = Path(project_path) / "library"
        if candidate.exists() and candidate.is_dir():
            default_library_path = str(candidate)

    return render_template(
        "index.html",
        schema_versions=available_versions,
        default_library_path=default_library_path,
    )

@validation_bp.route("/upload", methods=["POST"])
def upload_dataset():
    """Handle dataset upload and validation"""
    validation_results = current_app.config.get("VALIDATION_RESULTS", {})

    if "dataset" not in request.files:
        flash("No dataset uploaded", "error")
        return redirect(url_for("validation.validate_dataset"))

    files = request.files.getlist("dataset")
    if not files or (len(files) == 1 and files[0].filename == ""):
        flash("No files selected", "error")
        return redirect(url_for("validation.validate_dataset"))

    schema_version = request.form.get("schema_version", "stable")
    temp_dir = tempfile.mkdtemp(prefix="prism_validator_")

    metadata_paths_json = request.form.get("metadata_paths_json")
    if metadata_paths_json:
        try:
            metadata_paths = json.loads(metadata_paths_json)
        except json.JSONDecodeError:
            metadata_paths = []
    else:
        metadata_paths = request.form.getlist("metadata_paths[]")

    try:
        if len(files) > 1 or (
            len(files) == 1 and not files[0].filename.lower().endswith(".zip")
        ):
            all_files_json = request.form.get("all_files")
            all_files_list = json.loads(all_files_json) if all_files_json else []
            dataset_path = _process_folder_upload(files, temp_dir, metadata_paths, all_files_list)
            filename = f"folder_upload_{len(files)}_files"
        else:
            file = files[0]
            filename = secure_filename(file.filename)
            if not filename.lower().endswith(".zip"):
                flash("Please upload a ZIP file or select a folder", "error")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return redirect(url_for("validation.validate_dataset"))
            dataset_path = _process_zip_upload(file, temp_dir, filename)

        validation_mode = request.form.get("validation_mode", "both")
        run_bids = validation_mode in ["both", "bids"]
        run_prism = validation_mode in ["both", "prism"]
        
        show_bids_warnings = request.form.get("bids_warnings") == "true"
        job_id = request.form.get("job_id", str(uuid.uuid4()))
        library_path = request.form.get("library_path")

        def progress_callback(progress: int, message: str):
            update_progress(job_id, progress, message)

        issues, dataset_stats = run_validation(
            dataset_path,
            verbose=True,
            schema_version=schema_version,
            run_bids=run_bids,
            run_prism=run_prism,
            library_path=library_path,
            progress_callback=progress_callback,
        )

        update_progress(job_id, 100, "Validation complete")

        if not show_bids_warnings:
            issues = [i for i in issues if not (i[0] == "WARNING" and "[BIDS]" in i[1])]

        results = format_validation_results(issues, dataset_stats, dataset_path)
        results["timestamp"] = datetime.now().isoformat()
        results["upload_type"] = "structure_only"
        results["schema_version"] = schema_version
        results["job_id"] = job_id

        manifest_path = os.path.join(dataset_path, ".upload_manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
            results["upload_manifest"] = {
                "metadata_files": len(manifest.get("uploaded_files", [])),
                "placeholder_files": len(manifest.get("placeholder_files", [])),
                "upload_mode": "DataLad-style (structure + metadata only)",
            }

        result_id = f"result_{len(validation_results)}"
        validation_results[result_id] = {
            "results": results,
            "dataset_path": dataset_path,
            "temp_dir": temp_dir,
            "filename": filename,
        }
        current_app.config["VALIDATION_RESULTS"] = validation_results

        return redirect(url_for("validation.show_results", result_id=result_id))

    except Exception as e:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        flash(f"Error processing dataset: {str(e)}", "error")
        return redirect(url_for("validation.validate_dataset"))

@validation_bp.route("/validate_folder", methods=["POST"])
def validate_folder():
    """Handle local folder validation"""
    validation_results = current_app.config.get("VALIDATION_RESULTS", {})
    folder_path = request.form.get("folder_path", "").strip()
    if not folder_path:
        folder_path = (session.get("current_project_path") or "").strip()

    if not folder_path or not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        flash("Invalid folder path", "error")
        return redirect(url_for("validation.validate_dataset"))

    schema_version = request.form.get("schema_version", "stable")
    validation_mode = request.form.get("validation_mode", "both")
    run_bids = validation_mode in ["both", "bids"]
    run_prism = validation_mode in ["both", "prism"]
    
    show_bids_warnings = request.form.get("bids_warnings") == "true"
    job_id = request.form.get("job_id", str(uuid.uuid4()))
    library_path = request.form.get("library_path")

    def progress_callback(progress: int, message: str):
        update_progress(job_id, progress, message)

    try:
        issues, stats = run_validation(
            folder_path,
            verbose=True,
            schema_version=schema_version,
            run_bids=run_bids,
            run_prism=run_prism,
            library_path=library_path,
            progress_callback=progress_callback,
        )

        update_progress(job_id, 100, "Validation complete")

        if not show_bids_warnings:
            issues = [i for i in issues if not (i[0] == "WARNING" and "[BIDS]" in i[1])]

        formatted_results = format_validation_results(issues, stats, folder_path)
        formatted_results["schema_version"] = schema_version

        result_id = f"result_{len(validation_results)}"
        validation_results[result_id] = {
            "results": formatted_results,
            "dataset_path": folder_path,
            "temp_dir": None,
            "filename": os.path.basename(folder_path),
        }
        current_app.config["VALIDATION_RESULTS"] = validation_results

        return redirect(url_for("validation.show_results", result_id=result_id))

    except Exception as e:
        flash(f"Error validating dataset: {str(e)}", "error")
        return redirect(url_for("validation.validate_dataset"))

@validation_bp.route("/results/<result_id>")
def show_results(result_id):
    """Display validation results"""
    validation_results = current_app.config.get("VALIDATION_RESULTS", {})
    if result_id not in validation_results:
        flash("Results not found", "error")
        return redirect(url_for("validation.validate_dataset"))

    data = validation_results[result_id]
    results = data["results"]
    dataset_stats = results.get("dataset_stats")
    
    # Prepare dataset stats for display if needed
    if dataset_stats and not isinstance(dataset_stats, dict):
        try:
            stats_obj = dataset_stats
            session_entries = getattr(stats_obj, "sessions", set()) or set()
            unique_sessions = set()
            for entry in session_entries:
                if isinstance(entry, str) and "/" in entry:
                    unique_sessions.add(entry.split("/", 1)[1])
                elif entry:
                    unique_sessions.add(entry)

            modalities = getattr(stats_obj, "modalities", {}) or {}
            dataset_stats = {
                "total_subjects": len(getattr(stats_obj, "subjects", [])),
                "total_sessions": len(unique_sessions),
                "modalities": dict(sorted(modalities.items())),
                "tasks": sorted(getattr(stats_obj, "tasks", set()) or set()),
                "surveys": sorted(getattr(stats_obj, "surveys", set()) or set()),
                "biometrics": sorted(getattr(stats_obj, "biometrics", set()) or set()),
                "total_files": getattr(stats_obj, "total_files", 0),
                "sidecar_files": getattr(stats_obj, "sidecar_files", 0),
            }
        except Exception as stats_error:
            print(f"⚠️  Failed to prepare dataset stats for display: {stats_error}")
            dataset_stats = None
    
    if not dataset_stats:
        dataset_stats = {
            "total_subjects": 0,
            "total_sessions": 0,
            "modalities": {},
            "tasks": [],
            "surveys": [],
            "biometrics": [],
            "total_files": 0,
            "sidecar_files": 0,
        }

    return render_template(
        "results.html",
        results=results,
        dataset_stats=dataset_stats,
        result_id=result_id,
        filename=data.get("filename", "dataset"),
    )

@validation_bp.route("/download_report/<result_id>")
def download_report(result_id):
    """Download validation report as JSON"""
    validation_results = current_app.config.get("VALIDATION_RESULTS", {})
    if result_id not in validation_results:
        flash("Results not found", "error")
        return redirect(url_for("validation.validate_dataset"))

    data = validation_results[result_id]
    results = data["results"]

    # Create JSON report
    report = {
        "dataset": data["filename"],
        "validation_timestamp": results.get("timestamp", ""),
        "summary": {
            "total_files": len(results.get("valid_files", []))
            + len(results.get("invalid_files", [])),
            "valid_files": len(results.get("valid_files", [])),
            "invalid_files": len(results.get("invalid_files", [])),
            "total_errors": len(results.get("errors", [])),
            "total_warnings": len(results.get("warnings", [])),
        },
        "results": results,
    }

    # Create in-memory file
    import io
    output = io.BytesIO()
    output.write(json.dumps(report, indent=2).encode("utf-8"))
    output.seek(0)

    return send_file(
        output,
        mimetype="application/json",
        as_attachment=True,
        download_name=f"validation_report_{data['filename']}.json",
    )

@validation_bp.route("/cleanup/<result_id>")
def cleanup(result_id):
    """Clean up temporary files"""
    validation_results = current_app.config.get("VALIDATION_RESULTS", {})
    if result_id in validation_results:
        data = validation_results[result_id]
        if data["temp_dir"] and os.path.exists(data["temp_dir"]):
            shutil.rmtree(data["temp_dir"], ignore_errors=True)
        del validation_results[result_id]
        current_app.config["VALIDATION_RESULTS"] = validation_results

    flash("Results cleaned up", "success")
    return redirect(url_for("validation.validate_dataset"))

@validation_bp.route("/api/validate", methods=["POST"])
def api_validate():
    """API endpoint for validation (for programmatic access)"""
    try:
        data = request.get_json()
        if not data or "dataset_path" not in data:
            return jsonify({"error": "Missing dataset_path parameter"}), 400

        dataset_path = data["dataset_path"]
        library_path = data.get("library_path")
        if not os.path.exists(dataset_path):
            return jsonify({"error": "Dataset path does not exist"}), 400

        # Use unified validation function
        issues, stats = run_validation(
            dataset_path, 
            verbose=False,
            library_path=library_path
        )
        results = format_validation_results(issues, stats, dataset_path)

        return jsonify(results)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
