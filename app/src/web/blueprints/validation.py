import io
import os
import json
import tempfile
import shutil
import uuid
import time
import threading
from datetime import datetime
from pathlib import Path

from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    flash,
    redirect,
    url_for,
    current_app,
    send_file,
    session,
)
from werkzeug.utils import secure_filename

from src.web.utils import format_validation_results
from src.web.validation import (
    run_validation,
    update_progress,
    complete_progress,
    fail_progress,
    get_progress,
    clear_progress,
)
from src.web.upload import (
    process_folder_upload as _process_folder_upload,
    process_zip_upload as _process_zip_upload,
)

validation_bp = Blueprint("validation", __name__)

# Thread-safe in-memory store for validation results (keyed by UUID result_id)
_validation_results: dict = {}
_validation_results_lock = threading.Lock()

_RESULT_TTL_SECONDS = 2 * 60 * 60  # 2 hours


def _expire_old_results():
    """Evict entries older than _RESULT_TTL_SECONDS. Must be called under lock."""
    now = time.time()
    expired = [
        rid
        for rid, d in _validation_results.items()
        if now - d.get("created_at", now) > _RESULT_TTL_SECONDS
    ]
    for rid in expired:
        data = _validation_results.pop(rid)
        tmp = data.get("temp_dir")
        if tmp and os.path.exists(tmp):
            shutil.rmtree(tmp, ignore_errors=True)


@validation_bp.route("/api/progress/<job_id>")
def get_validation_progress(job_id):
    """Get progress for a validation job (polled by UI)."""
    progress_data = get_progress(job_id)
    return jsonify(progress_data)


def _request_wants_json_response() -> bool:
    """Return True when the caller expects an AJAX/JSON response."""
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _safe_expand_validation_path(path_value: str) -> Path:
    """Expand and resolve validation paths without breaking network-style locations."""
    candidate = Path(path_value).expanduser()
    try:
        return candidate.resolve()
    except (OSError, RuntimeError, ValueError):
        return candidate


def _get_global_validation_library_path() -> str:
    """Return the configured global validation library fallback."""
    from src.config import get_effective_library_paths

    lib_paths = get_effective_library_paths(app_root=str(current_app.root_path))
    configured_path = lib_paths.get("global_library_path")
    if configured_path:
        candidate = _safe_expand_validation_path(configured_path)
        if candidate.exists() and candidate.is_dir():
            return str(candidate)

    return str(_safe_expand_validation_path(str(Path(current_app.root_path) / "survey_library")))


def _get_default_validation_library_path(project_path: str | None = None) -> str:
    """Resolve the library path used when the user does not override it."""
    if project_path:
        project_root = _safe_expand_validation_path(project_path)
        if project_root.is_file():
            project_root = project_root.parent

        for candidate in (project_root / "library", project_root / "code" / "library"):
            if candidate.exists() and candidate.is_dir():
                return str(candidate)

    return _get_global_validation_library_path()


def _resolve_requested_validation_library_path(
    requested_library_path: str | None,
    *,
    project_path: str | None = None,
) -> str:
    """Use an explicit override when valid, otherwise fall back to the default validation library."""
    trimmed = (requested_library_path or "").strip()
    if trimmed:
        candidate = _safe_expand_validation_path(trimmed)
        if not candidate.exists() or not candidate.is_dir():
            raise ValueError("Invalid template library path")
        return str(candidate)

    return _get_default_validation_library_path(project_path)


def _validation_error_response(message: str, status_code: int = 400):
    """Return JSON for AJAX callers and redirect+flash otherwise."""
    if _request_wants_json_response():
        return jsonify({"error": message}), status_code
    flash(message, "error")
    return redirect(url_for("validation.validate_dataset"))


def _apply_bids_warning_display_filter(
    results: dict, show_bids_warnings: bool
) -> dict:
    """Hide verbose BIDS warning groups while preserving their counts."""
    if show_bids_warnings:
        return results

    bids_warn_groups = {
        k: v for k, v in results.get("warning_groups", {}).items() if k.startswith("BIDS")
    }
    hidden_count = sum(g.get("count", 0) for g in bids_warn_groups.values())
    if hidden_count:
        results["warning_groups"] = {
            k: v
            for k, v in results.get("warning_groups", {}).items()
            if not k.startswith("BIDS")
        }
        results["warnings"] = [
            warning
            for warning in results.get("warnings", [])
            if not str(warning.get("code", "")).startswith("BIDS")
        ]
        results["bids_warnings_hidden"] = hidden_count
    return results


def _store_validation_result(
    results: dict,
    dataset_path: str,
    temp_dir: str | None,
    filename: str,
) -> str:
    """Persist validation results and return the generated result id."""
    result_id = str(uuid.uuid4())
    with _validation_results_lock:
        _expire_old_results()
        _validation_results[result_id] = {
            "results": results,
            "dataset_path": dataset_path,
            "temp_dir": temp_dir,
            "filename": filename,
            "created_at": time.time(),
        }
    return result_id


def _build_validation_results_payload(
    *,
    issues,
    dataset_stats,
    dataset_path: str,
    schema_version: str,
    job_id: str,
    library_path: str | None,
    run_bids: bool,
    run_prism: bool,
    show_bids_warnings: bool,
    upload_type: str | None = None,
    manifest_path: str | None = None,
) -> dict:
    """Format and annotate validation results for storage and UI rendering."""
    results = format_validation_results(issues, dataset_stats, dataset_path)
    results = _apply_bids_warning_display_filter(results, show_bids_warnings)
    results["timestamp"] = datetime.now().isoformat()
    results["schema_version"] = schema_version
    results["job_id"] = job_id
    results["library_path"] = library_path or ""
    results["run_bids"] = run_bids
    results["run_prism"] = run_prism
    results["show_bids_warnings"] = show_bids_warnings

    if upload_type:
        results["upload_type"] = upload_type

    if manifest_path and os.path.exists(manifest_path):
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        results["upload_manifest"] = {
            "metadata_files": len(manifest.get("uploaded_files", [])),
            "placeholder_files": len(manifest.get("placeholder_files", [])),
            "upload_mode": "DataLad-style (structure + metadata only)",
        }

    return results


def _execute_validation_job(
    *,
    app_obj,
    job_id: str,
    dataset_path: str,
    filename: str,
    temp_dir: str | None,
    schema_version: str,
    run_bids: bool,
    run_prism: bool,
    library_path: str | None,
    show_bids_warnings: bool,
    project_path: str | None = None,
    upload_type: str | None = None,
    manifest_path: str | None = None,
) -> str:
    """Run one validation job end-to-end and store its result."""

    def _phase_for_message(message: str) -> tuple[str, str]:
        normalized = (message or "").strip().lower()
        if "running bids validator" in normalized:
            return "bids", "estimated"
        if normalized.startswith("loading") or normalized.startswith("starting"):
            return "preparing", "determinate"
        if normalized.startswith("checking") or normalized.startswith("validating"):
            return "validation", "determinate"
        return "validation", "determinate"

    def progress_callback(progress: int, message: str):
        phase, progress_mode = _phase_for_message(message)
        update_progress(
            job_id,
            progress,
            message,
            status="running",
            phase=phase,
            progress_mode=progress_mode,
        )

    update_progress(
        job_id,
        0,
        "Starting validation...",
        status="running",
        phase="preparing",
        progress_mode="determinate",
    )

    issues, dataset_stats = run_validation(
        dataset_path,
        verbose=True,
        schema_version=schema_version,
        run_bids=run_bids,
        run_prism=run_prism,
        library_path=library_path,
        project_path=project_path,
        progress_callback=progress_callback,
    )

    results = _build_validation_results_payload(
        issues=issues,
        dataset_stats=dataset_stats,
        dataset_path=dataset_path,
        schema_version=schema_version,
        job_id=job_id,
        library_path=library_path,
        run_bids=run_bids,
        run_prism=run_prism,
        show_bids_warnings=show_bids_warnings,
        upload_type=upload_type,
        manifest_path=manifest_path,
    )

    result_id = _store_validation_result(results, dataset_path, temp_dir, filename)
    with app_obj.test_request_context():
        redirect_url = url_for("validation.show_results", result_id=result_id)
    complete_progress(
        job_id,
        "Validation complete",
        result_id=result_id,
        redirect_url=redirect_url,
    )
    return result_id


def _run_validation_job_async(**kwargs) -> None:
    """Background wrapper that updates progress state on failure."""
    temp_dir = kwargs.get("temp_dir")
    job_id = kwargs.get("job_id", "")
    try:
        _execute_validation_job(**kwargs)
    except Exception as exc:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        fail_progress(job_id, f"Validation failed: {exc}", error=str(exc))


def _launch_validation_job(**kwargs):
    """Start a background validation thread and return job metadata."""
    job_id = kwargs["job_id"]
    update_progress(
        job_id,
        0,
        "Queued validation job...",
        status="pending",
        phase="pending",
        progress_mode="determinate",
    )
    worker = threading.Thread(
        target=_run_validation_job_async,
        kwargs=kwargs,
        daemon=True,
    )
    worker.start()
    return {
        "job_id": job_id,
        "progress_url": url_for("validation.get_validation_progress", job_id=job_id),
        "status": "started",
    }


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

    project_path = session.get("current_project_path")
    default_library_path = _get_default_validation_library_path(project_path)

    return render_template(
        "index.html",
        schema_versions=available_versions,
        default_library_path=default_library_path,
    )


def _cleanup_old_validation_reports():
    """Delete old validation reports from Downloads folder to prevent confusion.

    Removes validation_report_*.json files older than 1 hour from the user's
    Downloads folder. This prevents users from accidentally opening stale
    validation reports after making fixes and re-validating.
    """
    try:
        downloads_path = Path.home() / "Downloads"
        if downloads_path.exists():
            # Delete validation_report_*.json files older than 1 hour
            for report_file in downloads_path.glob("validation_report_*.json"):
                try:
                    # Check if file is older than 1 hour
                    age_seconds = time.time() - report_file.stat().st_mtime
                    if age_seconds > 3600:  # 1 hour
                        report_file.unlink()
                except Exception:
                    pass  # Ignore errors for individual files
    except Exception:
        pass  # Silently fail if we can't clean up


@validation_bp.route("/upload", methods=["POST"])
def upload_dataset():
    """Handle dataset upload and validation"""
    # Clean up old validation reports from Downloads to avoid confusion
    _cleanup_old_validation_reports()

    if "dataset" not in request.files:
        return _validation_error_response("No dataset uploaded")

    files = request.files.getlist("dataset")
    if not files or (len(files) == 1 and files[0].filename == ""):
        return _validation_error_response("No files selected")

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
            dataset_path = _process_folder_upload(
                files, temp_dir, metadata_paths, all_files_list
            )
            filename = f"folder_upload_{len(files)}_files"
        else:
            file = files[0]
            filename = secure_filename(file.filename)
            if not filename.lower().endswith(".zip"):
                shutil.rmtree(temp_dir, ignore_errors=True)
                return _validation_error_response(
                    "Please upload a ZIP file or select a folder"
                )
            dataset_path = _process_zip_upload(file, temp_dir, filename)

        validation_mode = request.form.get("validation_mode", "both")
        run_bids = validation_mode in ["both", "bids"]
        run_prism = validation_mode in ["both", "prism"]

        show_bids_warnings = request.form.get("bids_warnings") == "true"
        job_id = request.form.get("job_id", str(uuid.uuid4()))
        try:
            library_path = _resolve_requested_validation_library_path(
                request.form.get("library_path"),
                project_path=dataset_path,
            )
        except ValueError as exc:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return _validation_error_response(str(exc))
        manifest_path = os.path.join(dataset_path, ".upload_manifest.json")

        job_kwargs = {
            "app_obj": current_app._get_current_object(),
            "job_id": job_id,
            "dataset_path": dataset_path,
            "filename": filename,
            "temp_dir": temp_dir,
            "schema_version": schema_version,
            "run_bids": run_bids,
            "run_prism": run_prism,
            "library_path": library_path,
            "show_bids_warnings": show_bids_warnings,
            "project_path": dataset_path,
            "upload_type": "structure_only",
            "manifest_path": manifest_path,
        }

        if _request_wants_json_response():
            payload = _launch_validation_job(**job_kwargs)
            return jsonify(payload), 202

        result_id = _execute_validation_job(**job_kwargs)
        return redirect(url_for("validation.show_results", result_id=result_id))

    except Exception as e:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        return _validation_error_response(f"Error processing dataset: {str(e)}", 500)


@validation_bp.route("/validate_folder", methods=["POST"])
def validate_folder():
    """Handle local folder validation"""
    # Clean up old validation reports from Downloads to avoid confusion
    _cleanup_old_validation_reports()

    folder_path = request.form.get("folder_path", "").strip()
    if not folder_path:
        folder_path = (session.get("current_project_path") or "").strip()

    if (
        not folder_path
        or not os.path.exists(folder_path)
        or not os.path.isdir(folder_path)
    ):
        return _validation_error_response("Invalid folder path")

    schema_version = request.form.get("schema_version", "stable")
    validation_mode = request.form.get("validation_mode", "both")
    run_bids = validation_mode in ["both", "bids"]
    run_prism = validation_mode in ["both", "prism"]

    show_bids_warnings = request.form.get("bids_warnings") == "true"
    job_id = request.form.get("job_id", str(uuid.uuid4()))
    try:
        library_path = _resolve_requested_validation_library_path(
            request.form.get("library_path"),
            project_path=folder_path,
        )
    except ValueError as exc:
        return _validation_error_response(str(exc))

    try:
        job_kwargs = {
            "app_obj": current_app._get_current_object(),
            "job_id": job_id,
            "dataset_path": folder_path,
            "filename": os.path.basename(folder_path),
            "temp_dir": None,
            "schema_version": schema_version,
            "run_bids": run_bids,
            "run_prism": run_prism,
            "library_path": library_path,
            "show_bids_warnings": show_bids_warnings,
            "project_path": folder_path,
            "upload_type": None,
            "manifest_path": None,
        }

        if _request_wants_json_response():
            payload = _launch_validation_job(**job_kwargs)
            return jsonify(payload), 202

        result_id = _execute_validation_job(**job_kwargs)
        return redirect(url_for("validation.show_results", result_id=result_id))

    except Exception as e:
        return _validation_error_response(f"Error validating dataset: {str(e)}", 500)


@validation_bp.route("/results/<result_id>")
def show_results(result_id):
    """Display validation results"""
    if result_id not in _validation_results:
        flash("Results not found", "error")
        return redirect(url_for("validation.validate_dataset"))

    data = _validation_results[result_id]
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
            raw_acq = getattr(stats_obj, "acq_labels", {}) or {}
            dataset_stats = {
                "total_subjects": len(getattr(stats_obj, "subjects", [])),
                "total_sessions": len(unique_sessions),
                "modalities": dict(sorted(modalities.items())),
                "acq_labels": {k: sorted(v) for k, v in raw_acq.items()},
                "tasks": sorted(getattr(stats_obj, "tasks", set()) or set()),
                "eyetracking": sorted(
                    getattr(stats_obj, "eyetracking", set()) or set()
                ),
                "physio": sorted(getattr(stats_obj, "physio", set()) or set()),
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
    if result_id not in _validation_results:
        flash("Results not found", "error")
        return redirect(url_for("validation.validate_dataset"))

    data = _validation_results[result_id]
    results = data["results"]

    # Create JSON report
    report = {
        "dataset": data["filename"],
        "validation_timestamp": results.get("timestamp", ""),
        "summary": results.get(
            "summary",
            {
                "total_files": 0,
                "valid_files": 0,
                "invalid_files": 0,
                "total_errors": 0,
                "total_warnings": 0,
            },
        ),
        "results": results,
    }

    output = io.BytesIO()
    output.write(json.dumps(report, indent=2).encode("utf-8"))
    output.seek(0)

    return send_file(
        output,
        mimetype="application/json",
        as_attachment=True,
        download_name=f"validation_report_{data['filename']}.json",
    )


@validation_bp.route("/revalidate/<result_id>", methods=["POST"])
def revalidate(result_id):
    """Re-validate the same dataset to check if fixes worked"""
    with _validation_results_lock:
        data = _validation_results.get(result_id)
    if not data:
        flash("Original validation results not found", "error")
        return redirect(url_for("validation.validate_dataset"))

    dataset_path = data.get("dataset_path")

    if not dataset_path or not os.path.exists(dataset_path):
        flash("Dataset path no longer exists", "error")
        return redirect(url_for("validation.validate_dataset"))

    try:
        # Restore original validation settings so re-runs are identical in mode
        original_results = data["results"]
        schema_version = original_results.get("schema_version", "stable")
        library_path = original_results.get("library_path") or None
        run_bids = original_results.get("run_bids", False)
        run_prism = original_results.get("run_prism", True)
        show_bids_warnings = bool(original_results.get("show_bids_warnings", False))

        # Run validation again
        issues, dataset_stats = run_validation(
            dataset_path,
            verbose=True,
            schema_version=schema_version,
            run_bids=run_bids,
            run_prism=run_prism,
            library_path=library_path,
        )

        results = format_validation_results(issues, dataset_stats, dataset_path)
        results = _apply_bids_warning_display_filter(results, show_bids_warnings)
        results["timestamp"] = datetime.now().isoformat()
        results["schema_version"] = schema_version
        results["library_path"] = library_path or ""
        results["run_bids"] = run_bids
        results["run_prism"] = run_prism
        results["show_bids_warnings"] = show_bids_warnings
        results["revalidation"] = True
        results["previous_errors"] = original_results.get("summary", {}).get(
            "total_errors", 0
        )

        # Create new result entry
        new_result_id = str(uuid.uuid4())
        with _validation_results_lock:
            _expire_old_results()
            _validation_results[new_result_id] = {
                "results": results,
                "dataset_path": dataset_path,
                "temp_dir": data.get("temp_dir"),
                "filename": data.get("filename"),
                "created_at": time.time(),
            }

        # Show comparison message
        new_errors = results.get("summary", {}).get("total_errors", 0)
        prev_errors = results.get("previous_errors", 0)
        if new_errors == 0:
            flash("🎉 Perfect! No errors found!", "success")
        elif new_errors < prev_errors:
            flash(
                f"✓ Progress! Errors reduced from {prev_errors} to {new_errors}",
                "success",
            )
        elif new_errors > prev_errors:
            flash(f"⚠ Errors increased from {prev_errors} to {new_errors}", "warning")
        else:
            flash(f"Errors unchanged: {new_errors}", "info")

        return redirect(url_for("validation.show_results", result_id=new_result_id))

    except Exception as e:
        flash(f"Error during re-validation: {str(e)}", "error")
        return redirect(url_for("validation.show_results", result_id=result_id))


@validation_bp.route("/cleanup/<result_id>", methods=["POST"])
def cleanup(result_id):
    """Clean up temporary files"""
    with _validation_results_lock:
        if result_id in _validation_results:
            data = _validation_results.pop(result_id)
            if data.get("temp_dir") and os.path.exists(data["temp_dir"]):
                shutil.rmtree(data["temp_dir"], ignore_errors=True)

    flash("Results cleaned up", "success")
    return redirect(url_for("validation.validate_dataset"))


@validation_bp.route("/api/validate", methods=["POST"])
def api_validate():
    """API endpoint for validation (for programmatic access)"""
    try:
        data = request.get_json()
        if not data or "dataset_path" not in data:
            return jsonify({"error": "Missing dataset_path parameter"}), 400

        dataset_path = os.path.normpath(os.path.abspath(data["dataset_path"]))
        library_path = data.get("library_path")
        if not os.path.isdir(dataset_path):
            return (
                jsonify({"error": "Dataset path does not exist or is not a directory"}),
                400,
            )

        # Use unified validation function
        issues, stats = run_validation(
            dataset_path, verbose=False, library_path=library_path
        )
        results = format_validation_results(issues, stats, dataset_path)

        return jsonify(results)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
