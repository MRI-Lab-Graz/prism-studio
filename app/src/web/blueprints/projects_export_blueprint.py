from flask import Blueprint, current_app, jsonify, request, session
from pathlib import Path
import atexit
import os
import tempfile
import threading
import time
import traceback
import uuid
from threading import Lock
from typing import Dict, Optional
from src.export_options import (
    ExportBlocked,
    build_export_defacing_warning as _build_export_defacing_warning,
    build_export_kwargs,
    export_zip_name,
    run_anc_export,
    run_annex_availability,
    run_folder_export,
    run_git_lfs_export,
    run_project_export,
    run_template_export,
)
from src.export_openminds import OpenMindsError, openminds_tasks, run_openminds_export
from src.export_defacing import defacing_preflight, defacing_report, run_defacing
from .projects_helpers import _resolve_project_root_path

projects_export_bp = Blueprint("projects_export", __name__)

# ---------------------------------------------------------------------------
# Async export job store
# ---------------------------------------------------------------------------

_export_jobs: Dict[str, dict] = {}
_export_lock = Lock()
_EXPORT_JOB_TTL_SECONDS = 2 * 60 * 60
_EXPORT_JOB_PRUNE_INTERVAL_SECONDS = 30.0
_EXPORT_DONE_STATUSES = {"complete", "error", "cancelled"}
_last_export_prune_at = 0.0


def _export_now() -> float:
    return float(time.monotonic())


def _prune_export_jobs_locked(*, force: bool = False) -> None:
    global _last_export_prune_at

    now = _export_now()
    if (
        not force
        and _EXPORT_JOB_PRUNE_INTERVAL_SECONDS > 0
        and (now - _last_export_prune_at) < _EXPORT_JOB_PRUNE_INTERVAL_SECONDS
    ):
        return

    cutoff = now - _EXPORT_JOB_TTL_SECONDS
    expired_job_ids = []
    for job_id, job in _export_jobs.items():
        done_at = job.get("done_at")
        if done_at is None:
            continue
        if float(done_at) <= cutoff:
            expired_job_ids.append(job_id)

    for job_id in expired_job_ids:
        _export_jobs.pop(job_id, None)

    _last_export_prune_at = now


def _cleanup_all_export_temps() -> None:
    """Called at process exit: remove any cancelled/errored ZIP leftovers."""
    with _export_lock:
        _prune_export_jobs_locked(force=True)
        for job in _export_jobs.values():
            if job.get("status") in ("cancelled", "error"):
                zip_path = job.get("zip_path")
                if zip_path and os.path.exists(zip_path):
                    try:
                        os.unlink(zip_path)
                    except OSError:
                        pass


atexit.register(_cleanup_all_export_temps)


def _create_export_job(job_id: str) -> None:
    with _export_lock:
        _prune_export_jobs_locked(force=True)
        now = _export_now()
        _export_jobs[job_id] = {
            "status": "pending",
            "percent": 0,
            "message": "Starting...",
            "zip_path": None,
            "filename": None,
            "error": None,
            "cancel_event": threading.Event(),
            "created_at": now,
            "updated_at": now,
            "done_at": None,
        }


def _update_export_job(job_id: str, **kwargs: object) -> None:
    with _export_lock:
        _prune_export_jobs_locked()
        if job_id in _export_jobs:
            job = _export_jobs[job_id]
            job.update(kwargs)
            now = _export_now()
            job["updated_at"] = now
            if (
                job.get("status") in _EXPORT_DONE_STATUSES
                and job.get("done_at") is None
            ):
                job["done_at"] = now


def _get_export_job(job_id: str) -> dict:
    with _export_lock:
        _prune_export_jobs_locked()
        job = _export_jobs.get(job_id)
        if job is None:
            return {}
        return {k: v for k, v in job.items() if k not in ("cancel_event",)}


def _run_export_job(job_id: str, project_path: Path, data: dict, filename: str, output_folder: Optional[str] = None) -> None:
    """Background thread: run the shared export (validation gate, then export) and update the job store."""
    # Write the ZIP to the requested output folder, or next to the project on disk
    dest_dir = Path(output_folder) if output_folder else project_path.parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    output_zip = dest_dir / filename
    cancel_event = _export_jobs.get(job_id, {}).get("cancel_event")

    def progress_callback(percent: int, message: str) -> None:
        _update_export_job(job_id, percent=percent, message=message, status="running")

    try:
        run_project_export(project_path, output_zip, data, progress_callback=progress_callback, cancelled_flag=cancel_event)
        if cancel_event and cancel_event.is_set():
            _update_export_job(job_id, status="cancelled", message="Export cancelled", percent=0)
            output_zip.unlink(missing_ok=True)
        else:
            _update_export_job(
                job_id, status="complete", percent=100, message="Export complete", zip_path=str(output_zip), filename=filename
            )
    except ExportBlocked as exc:
        _update_export_job(job_id, status="error", percent=0, message="Export blocked by validation errors", error=str(exc))
        output_zip.unlink(missing_ok=True)
    except InterruptedError:
        _update_export_job(job_id, status="cancelled", message="Export cancelled", percent=0)
        output_zip.unlink(missing_ok=True)
    except Exception as exc:
        _update_export_job(job_id, status="error", message=str(exc), error=str(exc))
        output_zip.unlink(missing_ok=True)


def _build_zip_stream_response(
    zip_path: Path,
    *,
    download_name: str,
    delete_file_after_send: bool = False,
    cleanup_callback=None,
):
    """Stream a ZIP file and run cleanup exactly after the stream finishes."""

    def _iter_file():
        try:
            with open(zip_path, "rb") as file_handle:
                while True:
                    chunk = file_handle.read(64 * 1024)
                    if not chunk:
                        break
                    yield chunk
        finally:
            if delete_file_after_send:
                try:
                    zip_path.unlink(missing_ok=True)
                except OSError:
                    pass
            if cleanup_callback is not None:
                cleanup_callback()

    response = current_app.response_class(_iter_file(), mimetype="application/zip")
    try:
        response.headers["Content-Length"] = str(zip_path.stat().st_size)
    except OSError:
        pass
    response.headers.set("Content-Disposition", "attachment", filename=download_name)
    return response


@projects_export_bp.route("/api/projects/export", methods=["POST"])
def export_project():
    """Export the current project as a ZIP download (same options and validation gate as `export project`)."""
    try:
        data = request.get_json() or {}
        if not data:
            return jsonify({"error": "No data provided"}), 400
        project_path = _resolve_project_root_path(data.get("project_path"))
        if project_path is None:
            return jsonify({"error": "Invalid project path"}), 400

        temp_fd, temp_path = tempfile.mkstemp(suffix=".zip")
        os.close(temp_fd)
        try:
            run_project_export(project_path, Path(temp_path), data)
            kwargs = build_export_kwargs(data)
            filename = export_zip_name(project_path.name, kwargs["anonymize"], data.get("export_preset", "standard"))
            return _build_zip_stream_response(Path(temp_path), download_name=filename, delete_file_after_send=True)
        except ExportBlocked as exc:
            os.unlink(temp_path)
            return jsonify({"error": str(exc)}), 409
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@projects_export_bp.route("/api/projects/export/structure", methods=["POST"])
def export_project_structure():
    """Return available sessions and modalities for the given project."""
    try:
        from src.project_structure import get_project_modalities_and_sessions

        data = request.get_json() or {}
        project_path_raw = data.get("project_path")
        resolved = _resolve_project_root_path(project_path_raw)
        if resolved is None:
            return jsonify({"error": "Invalid project path"}), 400
        structure = get_project_modalities_and_sessions(resolved)
        return jsonify({"success": True, **structure})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@projects_export_bp.route("/api/projects/export/folder", methods=["POST"])
def export_project_folder():
    """Create a plain folder export without Git/DataLad metadata."""
    try:
        data = request.get_json() or {}
        resolved = _resolve_project_root_path(data.get("project_path"))
        if resolved is None:
            return jsonify({"success": False, "error": "Invalid project path"}), 400
        result = run_folder_export(resolved, data)
        return jsonify(result) if result.get("success") else (jsonify(result), 400)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@projects_export_bp.route("/api/projects/export/git-lfs", methods=["POST"])
def export_project_git_lfs():
    """Create a one-way Git LFS export snapshot (folder + optionally initialized repo)."""
    try:
        data = request.get_json() or {}
        resolved = _resolve_project_root_path(data.get("project_path"))
        if resolved is None:
            return jsonify({"success": False, "error": "Invalid project path"}), 400
        result = run_git_lfs_export(resolved, data)
        return jsonify(result) if result.get("success") else (jsonify(result), 400)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@projects_export_bp.route("/api/projects/export/annex-availability", methods=["POST"])
def export_project_annex_availability():
    """Preview missing local files for current folder export scope."""
    try:
        data = request.get_json() or {}
        resolved = _resolve_project_root_path(data.get("project_path"))
        if resolved is None:
            return jsonify({"success": False, "error": "Invalid project path"}), 400
        result = run_annex_availability(resolved, data)
        return jsonify(result) if result.get("success") else (jsonify(result), 400)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@projects_export_bp.route("/api/projects/export/defacing-report", methods=["POST"])
def export_defacing_report():
    """Return a defacing status report for all anatomical scans in the project."""
    try:
        data = request.get_json() or {}
        resolved = _resolve_project_root_path(data.get("project_path"))
        if resolved is None:
            return jsonify({"error": "Invalid project path"}), 400
        return jsonify(defacing_report(resolved, data))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@projects_export_bp.route("/api/projects/export/defacing-preflight", methods=["POST"])
def export_defacing_preflight():
    """Return defacing readiness for current project and environment."""
    try:
        data = request.get_json() or {}
        resolved = _resolve_project_root_path(data.get("project_path"))
        if resolved is None:
            return jsonify({"success": False, "error": "Invalid project path"}), 400
        return jsonify(defacing_preflight(resolved))
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@projects_export_bp.route("/api/projects/export/deface", methods=["POST"])
def export_deface_anatomical_scans():
    """Run export-aware defacing on an export copy of the project (never on the project itself)."""
    try:
        data = request.get_json() or {}
        resolved = _resolve_project_root_path(data.get("project_path"))
        if resolved is None:
            return jsonify({"success": False, "error": "Invalid project path"}), 400
        payload, ok = run_defacing(resolved, data)
        return jsonify(payload), 200 if ok else 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@projects_export_bp.route("/api/projects/export/start", methods=["POST"])
def export_project_start():
    """Start an async export job. Returns {job_id}."""
    try:
        data = request.get_json() or {}
        if not data:
            return jsonify({"error": "No data provided"}), 400
        resolved = _resolve_project_root_path(data.get("project_path"))
        if resolved is None:
            return jsonify({"error": "Invalid project path"}), 400

        kwargs = build_export_kwargs(data)
        filename = export_zip_name(resolved.name, kwargs["anonymize"], data.get("export_preset", "standard"))
        job_id = str(uuid.uuid4())
        _create_export_job(job_id)

        defacing_warning = _build_export_defacing_warning(
            resolved, exclude_subjects=kwargs["exclude_subjects"], exclude_sessions=kwargs["exclude_sessions"]
        )
        if defacing_warning:
            _update_export_job(job_id, defacing_warning=defacing_warning)

        threading.Thread(
            target=_run_export_job,
            args=(job_id, resolved, data, filename, data.get("output_folder") or None),
            daemon=True,
        ).start()
        return jsonify({"job_id": job_id})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@projects_export_bp.route("/api/projects/export/<job_id>/status", methods=["GET"])
def export_job_status(job_id: str):
    """Poll export job status. Returns {status, percent, message, zip_path}."""
    job = _get_export_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(
        {
            "status": job.get("status"),
            "percent": job.get("percent", 0),
            "message": job.get("message", ""),
            "error": job.get("error"),
            "zip_path": job.get("zip_path"),
            "defacing_warning": job.get("defacing_warning"),
        }
    )


@projects_export_bp.route("/api/projects/export/<job_id>/download", methods=["GET"])
def export_job_download(job_id: str):
    """Download the completed export ZIP and clean up job metadata."""
    job = _get_export_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    if job.get("status") != "complete":
        return jsonify({"error": "Export not complete"}), 400

    zip_path = job.get("zip_path")
    filename = job.get("filename", "export.zip")

    if not zip_path or not os.path.exists(zip_path):
        return jsonify({"error": "Export file not found"}), 404

    def _cleanup() -> None:
        with _export_lock:
            _prune_export_jobs_locked()
            _export_jobs.pop(job_id, None)

    return _build_zip_stream_response(
        Path(zip_path),
        download_name=filename,
        cleanup_callback=_cleanup,
    )


@projects_export_bp.route("/api/projects/export/<job_id>/cancel", methods=["DELETE"])
def export_job_cancel(job_id: str):
    """Request cancellation of a running export job."""
    with _export_lock:
        job = _export_jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    cancel_event = job.get("cancel_event")
    if cancel_event:
        cancel_event.set()
    return jsonify({"cancelled": True})


@projects_export_bp.route("/api/projects/anc-export", methods=["POST"])
def anc_export_project():
    """Export the current project to the ANC (Austrian NeuroCloud) layout."""
    try:
        data = request.get_json() or {}
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        resolved = _resolve_project_root_path(data.get("project_path"))
        if resolved is None:
            return jsonify({"success": False, "error": "Invalid project path"}), 400
        return jsonify(run_anc_export(resolved, data))
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@projects_export_bp.route("/api/projects/template-export", methods=["POST"])
def template_export_project():
    """Create a project template ZIP while excluding participant-specific content."""
    try:
        data = request.get_json() or {}
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        resolved = _resolve_project_root_path(data.get("project_path"))
        if resolved is None:
            return jsonify({"success": False, "error": "Invalid project path"}), 400
        try:
            stats = run_template_export(resolved, data)
        except ExportBlocked as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
        return jsonify({
            "success": True,
            "output_path": stats["output_zip"],
            "message": "Template export completed successfully",
            "stats": stats,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@projects_export_bp.route("/api/projects/openminds-tasks", methods=["GET"])
def openminds_get_tasks():
    """Return task names from the current project for the openMINDS pre-flight form."""
    try:
        resolved = _resolve_project_root_path(request.args.get("project_path") or session.get("current_project_path"))
        if resolved is None:
            return jsonify({"success": False, "error": "No active project"}), 400
        return jsonify({"success": True, "tasks": openminds_tasks(resolved)})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@projects_export_bp.route("/api/projects/openminds-export", methods=["POST"])
def openminds_export_project():
    """Export the current project to openMINDS metadata format using bids2openminds."""
    try:
        data = request.get_json() or {}
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        resolved = _resolve_project_root_path(data.get("project_path"))
        if resolved is None:
            return jsonify({"success": False, "error": "Invalid project path"}), 400
        try:
            return jsonify(run_openminds_export(resolved, data))
        except OpenMindsError as exc:
            return jsonify({"success": False, "error": str(exc)}), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
