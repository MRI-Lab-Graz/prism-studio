from flask import Blueprint, current_app, jsonify, request, send_file, session
from pathlib import Path
import atexit
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid
from threading import Lock
from typing import Dict, Optional, Set
from src.cross_platform import safe_path_join
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
_EXPORT_VALIDATION_MODES = {"both", "bids", "prism", "ignore", "none"}
_EXPORT_PRESETS = {"standard", "upload_ready"}


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


def _normalize_export_validation_mode(raw_mode: object) -> str:
    mode = str(raw_mode or "").strip().lower()
    if mode not in _EXPORT_VALIDATION_MODES:
        return "both"
    if mode == "none":
        return "ignore"
    return mode


def _normalize_export_preset(raw_preset: object) -> str:
    preset = str(raw_preset or "").strip().lower()
    if preset not in _EXPORT_PRESETS:
        return "standard"
    return preset


def _normalize_scrub_group_ids(raw_groups: object) -> Optional[Set[str]]:
    if not isinstance(raw_groups, (list, tuple, set)):
        return None
    normalized = {
        str(group).strip().lower() for group in raw_groups if str(group).strip()
    }
    return normalized or None


def _export_validation_flags(validation_mode: str) -> tuple[bool, bool]:
    mode = _normalize_export_validation_mode(validation_mode)
    if mode == "bids":
        return True, False
    if mode == "prism":
        return False, True
    if mode == "ignore":
        return False, False
    return True, True


def _export_validation_mode_label(validation_mode: str) -> str:
    mode = _normalize_export_validation_mode(validation_mode)
    if mode == "bids":
        return "BIDS"
    if mode == "prism":
        return "PRISM"
    if mode == "ignore":
        return "validation"
    return "PRISM + BIDS"


def _count_validation_issues(
    issues: object,
    *,
    dataset_stats: object,
    dataset_path: Path,
    run_bids: bool,
    run_prism: bool,
) -> tuple[int, int]:
    # Reuse the same issue formatting/filtering path as the Validation page,
    # so export blocking mirrors what users see in standard validation results.
    from src.web.utils import format_validation_results
    from src.web.blueprints.validation import _apply_validation_mode_issue_filter

    if isinstance(issues, list):
        normalized_issues = issues
    elif isinstance(issues, tuple):
        normalized_issues = list(issues)
    else:
        normalized_issues = []
    results = format_validation_results(
        normalized_issues,
        dataset_stats,
        str(dataset_path),
    )
    results = _apply_validation_mode_issue_filter(
        results,
        run_bids=run_bids,
        run_prism=run_prism,
    )

    summary = results.get("summary", {}) if isinstance(results, dict) else {}
    total_errors = int(summary.get("total_errors", 0) or 0)
    total_warnings = int(summary.get("total_warnings", 0) or 0)
    return total_errors, total_warnings


def _run_pre_export_validation(project_path: Path, validation_mode: str) -> str | None:
    run_bids, run_prism = _export_validation_flags(validation_mode)
    if not run_bids and not run_prism:
        return None

    from src.web.validation import run_validation

    issues, dataset_stats = run_validation(
        str(project_path),
        verbose=True,
        schema_version="stable",
        run_bids=run_bids,
        run_prism=run_prism,
        project_path=str(project_path),
    )
    error_count, warning_count = _count_validation_issues(
        issues,
        dataset_stats=dataset_stats,
        dataset_path=project_path,
        run_bids=run_bids,
        run_prism=run_prism,
    )
    if error_count == 0:
        return None

    error_label = "error" if error_count == 1 else "errors"
    warning_suffix = ""
    if warning_count:
        warning_label = "warning" if warning_count == 1 else "warnings"
        warning_suffix = f" ({warning_count} {warning_label} also reported)"

    return (
        f"Export blocked: validation found {error_count} {error_label} "
        f"in {_export_validation_mode_label(validation_mode)} checks{warning_suffix}. "
        "Fix the validation errors or choose 'Ignore validation' in the export options."
    )


def _build_export_defacing_warning(
    project_path: Path, scrub_mri_json: bool
) -> Optional[dict]:
    """Build warning-only defacing metadata for async export status payloads.

    This never blocks export. It only surfaces a summary when MRI JSON scrub is
    enabled and anatomical scans appear not defaced or unknown.
    """
    if not scrub_mri_json:
        return None

    try:
        from src.mri_json_scrubber import build_defacing_report

        report = build_defacing_report(project_path)
    except Exception:
        return None

    counts = {"defaced": 0, "not_defaced": 0, "unknown": 0}
    for entry in report:
        status = str(entry.get("status", "unknown"))
        if status not in counts:
            status = "unknown"
        counts[status] += 1

    risk_count = counts["not_defaced"] + counts["unknown"]
    if risk_count <= 0:
        return None

    return {
        "message": (
            "Defacing check: some anatomical scans are not defaced or unknown. "
            "Export continued because this is warning-only."
        ),
        "counts": counts,
        "risk_count": risk_count,
    }


def _run_export_job(
    job_id: str, export_kwargs: dict, filename: str, output_folder: Optional[str] = None
) -> None:
    """Background thread: run export_project and update job store."""
    from src.web.export_project import export_project as do_export

    # Write ZIP to the requested output folder, or next to the project on disk
    project_path: Path = export_kwargs["project_path"]
    if output_folder:
        dest_dir = Path(output_folder)
    else:
        dest_dir = project_path.parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    output_zip = dest_dir / filename

    completed_ok = False
    try:
        job = _export_jobs.get(job_id, {})
        cancel_event = job.get("cancel_event")
        validation_mode = _normalize_export_validation_mode(
            export_kwargs.pop("validation_mode", "both")
        )

        def progress_callback(percent: int, message: str) -> None:
            _update_export_job(
                job_id, percent=percent, message=message, status="running"
            )

        if cancel_event and cancel_event.is_set():
            raise InterruptedError("Export cancelled by user")

        run_bids, run_prism = _export_validation_flags(validation_mode)
        if run_bids or run_prism:
            _update_export_job(
                job_id,
                percent=2,
                message=(
                    f"Running {_export_validation_mode_label(validation_mode)} "
                    "validation before export..."
                ),
                status="running",
            )

            validation_error = _run_pre_export_validation(project_path, validation_mode)
            if validation_error:
                _update_export_job(
                    job_id,
                    status="error",
                    percent=0,
                    message="Export blocked by validation errors",
                    error=validation_error,
                )
                output_zip.unlink(missing_ok=True)
                return

            if cancel_event and cancel_event.is_set():
                raise InterruptedError("Export cancelled by user")

            _update_export_job(
                job_id,
                percent=5,
                message="Validation passed. Starting export...",
                status="running",
            )

        do_export(
            **export_kwargs,
            output_zip=output_zip,
            progress_callback=progress_callback,
            cancelled_flag=cancel_event,
        )

        if cancel_event and cancel_event.is_set():
            _update_export_job(
                job_id, status="cancelled", message="Export cancelled", percent=0
            )
            output_zip.unlink(missing_ok=True)
        else:
            completed_ok = True
            _update_export_job(
                job_id,
                status="complete",
                percent=100,
                message="Export complete",
                zip_path=str(output_zip),
                filename=filename,
            )
    except InterruptedError:
        _update_export_job(
            job_id, status="cancelled", message="Export cancelled", percent=0
        )
        output_zip.unlink(missing_ok=True)
    except Exception as exc:
        _update_export_job(job_id, status="error", message=str(exc), error=str(exc))
        output_zip.unlink(missing_ok=True)
    finally:
        # Nothing extra to clean up — ZIP lives at user-chosen path, not a temp file
        pass


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
    """
    Export the current project as a ZIP file with optional anonymization.

    Expected JSON body:
    {
        "project_path": "/path/to/project",
        "anonymize": true,
        "mask_questions": true,
        "include_derivatives": true,
        "include_code": true,
        "include_analysis": false
    }
    """
    from src.web.export_project import export_project as do_export

    try:
        data = request.get_json() or {}
        if not data:
            return jsonify({"error": "No data provided"}), 400

        project_path = data.get("project_path")
        resolved_project_path = _resolve_project_root_path(project_path)
        if resolved_project_path is None:
            return jsonify({"error": "Invalid project path"}), 400

        project_path = resolved_project_path

        # Get export options
        anonymize = bool(data.get("anonymize", True))
        mask_questions = bool(data.get("mask_questions", True))
        # Keep anonymization settings simple in UI: fixed deterministic IDs when enabled.
        id_length = 8
        deterministic = True
        export_preset = _normalize_export_preset(data.get("export_preset", "standard"))
        include_derivatives = bool(data.get("include_derivatives", True))
        include_sourcedata = bool(data.get("include_sourcedata", False))
        include_code = bool(data.get("include_code", True))
        include_analysis = bool(data.get("include_analysis", False))
        exclude_version_control_metadata = bool(
            data.get("exclude_version_control_metadata", False)
        )
        scrub_mri_json = bool(data.get("scrub_mri_json", False))
        scrub_mri_json_groups = _normalize_scrub_group_ids(
            data.get("scrub_mri_json_groups")
        )

        if export_preset == "upload_ready":
            include_derivatives = False
            include_sourcedata = False
            include_code = False
            include_analysis = False
            exclude_version_control_metadata = True

        # Create temporary file for ZIP
        temp_fd, temp_path = tempfile.mkstemp(suffix=".zip")
        os.close(temp_fd)

        try:
            # Perform export
            do_export(
                project_path=project_path,
                output_zip=Path(temp_path),
                anonymize=anonymize,
                mask_questions=mask_questions,
                id_length=id_length,
                deterministic=deterministic,
                include_derivatives=include_derivatives,
                include_sourcedata=include_sourcedata,
                include_code=include_code,
                include_analysis=include_analysis,
                exclude_version_control_metadata=exclude_version_control_metadata,
                scrub_mri_json=scrub_mri_json,
                scrub_mri_json_groups=scrub_mri_json_groups,
                clean_nifti_gzip_headers=scrub_mri_json,
            )

            # Generate filename
            project_name = project_path.name
            anon_suffix = "_anonymized" if anonymize else ""
            preset_suffix = "_upload_ready" if export_preset == "upload_ready" else ""
            filename = f"{project_name}{anon_suffix}{preset_suffix}_export.zip"

            return _build_zip_stream_response(
                Path(temp_path),
                download_name=filename,
                delete_file_after_send=True,
            )

        except Exception:
            # Clean up temp file on error
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


@projects_export_bp.route("/api/projects/export/browse-folder", methods=["POST"])
def export_browse_folder():
    """Open a native folder-picker dialog and return the chosen path."""
    from src.web.services import file_picker

    outcome = file_picker.pick_folder()
    if outcome.error:
        return jsonify({"folder": None, "error": outcome.error}), outcome.status_code
    return jsonify({"folder": outcome.path or None})


@projects_export_bp.route("/api/projects/export/folder", methods=["POST"])
def export_project_folder():
    """Create a plain folder export without Git/DataLad metadata."""
    try:
        from src.project_manager import ProjectManager

        data = request.get_json() or {}
        project_path_raw = data.get("project_path")
        resolved = _resolve_project_root_path(project_path_raw)
        if resolved is None:
            return jsonify({"success": False, "error": "Invalid project path"}), 400

        output_folder = data.get("output_folder") or None

        manager_kwargs: Dict[str, object] = {
            "output_root": output_folder,
        }

        scope_keys = {
            "include_derivatives",
            "include_sourcedata",
            "include_code",
            "include_analysis",
            "exclude_subjects",
            "exclude_sessions",
            "exclude_modalities",
            "exclude_acq",
            "exclude_tasks",
            "materialize_annex_content",
        }
        if any(key in data for key in scope_keys):
            def _normalize_labels(values: object) -> set[str]:
                if not isinstance(values, (list, tuple, set)):
                    return set()
                normalized = {
                    str(value).strip() for value in values if str(value).strip()
                }
                return normalized

            def _normalize_grouped_labels(values: object) -> Dict[str, set[str]]:
                if not isinstance(values, dict):
                    return {}
                normalized: Dict[str, set[str]] = {}
                for modality, labels in values.items():
                    modality_name = str(modality).strip()
                    if not modality_name:
                        continue
                    normalized_labels = _normalize_labels(labels)
                    if normalized_labels:
                        normalized[modality_name] = normalized_labels
                return normalized

            exclude_subjects = _normalize_labels(data.get("exclude_subjects"))
            exclude_sessions = _normalize_labels(data.get("exclude_sessions"))
            exclude_modalities = _normalize_labels(data.get("exclude_modalities"))
            exclude_acq = _normalize_grouped_labels(data.get("exclude_acq"))
            exclude_tasks = _normalize_grouped_labels(data.get("exclude_tasks"))

            manager_kwargs.update(
                {
                    "include_derivatives": bool(data.get("include_derivatives", True)),
                    "include_sourcedata": bool(data.get("include_sourcedata", False)),
                    "include_code": bool(data.get("include_code", True)),
                    "include_analysis": bool(data.get("include_analysis", True)),
                    "exclude_sessions": exclude_sessions or None,
                    "exclude_modalities": exclude_modalities or None,
                    "exclude_acq": exclude_acq or None,
                    "exclude_tasks": exclude_tasks or None,
                    "materialize_annex_content": bool(
                        data.get("materialize_annex_content", False)
                    ),
                }
            )
            if "exclude_subjects" in data:
                manager_kwargs["exclude_subjects"] = exclude_subjects or None

        manager = ProjectManager()
        result = manager.export_project_to_plain_folder(
            resolved,
            **manager_kwargs,
        )
        if result.get("success"):
            return jsonify(result)
        return jsonify(result), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@projects_export_bp.route("/api/projects/export/annex-availability", methods=["POST"])
def export_project_annex_availability():
    """Preview missing local files for current folder export scope."""
    try:
        from src.project_manager import ProjectManager

        data = request.get_json() or {}
        project_path_raw = data.get("project_path")
        resolved = _resolve_project_root_path(project_path_raw)
        if resolved is None:
            return jsonify({"success": False, "error": "Invalid project path"}), 400

        def _normalize_labels(values: object) -> set[str]:
            if not isinstance(values, (list, tuple, set)):
                return set()
            normalized = {
                str(value).strip() for value in values if str(value).strip()
            }
            return normalized

        def _normalize_grouped_labels(values: object) -> Dict[str, set[str]]:
            if not isinstance(values, dict):
                return {}
            normalized: Dict[str, set[str]] = {}
            for modality, labels in values.items():
                modality_name = str(modality).strip()
                if not modality_name:
                    continue
                normalized_labels = _normalize_labels(labels)
                if normalized_labels:
                    normalized[modality_name] = normalized_labels
            return normalized

        exclude_subjects = _normalize_labels(data.get("exclude_subjects"))
        exclude_sessions = _normalize_labels(data.get("exclude_sessions"))
        exclude_modalities = _normalize_labels(data.get("exclude_modalities"))
        exclude_acq = _normalize_grouped_labels(data.get("exclude_acq"))
        exclude_tasks = _normalize_grouped_labels(data.get("exclude_tasks"))

        manager = ProjectManager()
        manager_kwargs = {
            "include_derivatives": bool(data.get("include_derivatives", True)),
            "include_sourcedata": bool(data.get("include_sourcedata", False)),
            "include_code": bool(data.get("include_code", True)),
            "include_analysis": bool(data.get("include_analysis", True)),
            "exclude_sessions": exclude_sessions or None,
            "exclude_modalities": exclude_modalities or None,
            "exclude_acq": exclude_acq or None,
            "exclude_tasks": exclude_tasks or None,
        }
        if "exclude_subjects" in data:
            manager_kwargs["exclude_subjects"] = exclude_subjects or None

        result = manager.preview_plain_folder_export_availability(
            resolved,
            **manager_kwargs,
        )

        if result.get("success"):
            return jsonify(result)
        return jsonify(result), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@projects_export_bp.route("/api/projects/export/defacing-report", methods=["POST"])
def export_defacing_report():
    """Return a defacing status report for all anatomical scans in the project."""
    try:
        from src.mri_json_scrubber import build_defacing_report

        data = request.get_json() or {}
        project_path_raw = data.get("project_path")
        resolved = _resolve_project_root_path(project_path_raw)
        if resolved is None:
            return jsonify({"error": "Invalid project path"}), 400

        report = build_defacing_report(resolved)
        counts = {"defaced": 0, "not_defaced": 0, "unknown": 0}
        for entry in report:
            status = entry.get("status", "unknown")
            counts[status] = counts.get(status, 0) + 1

        return jsonify({"success": True, "report": report, "counts": counts})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@projects_export_bp.route("/api/projects/export/defacing-preflight", methods=["POST"])
def export_defacing_preflight():
    """Return defacing readiness for current project and environment."""
    try:
        from src.mri_json_scrubber import get_defacing_preflight

        data = request.get_json() or {}
        project_path_raw = data.get("project_path")
        resolved = _resolve_project_root_path(project_path_raw)
        if resolved is None:
            return jsonify({"success": False, "error": "Invalid project path"}), 400

        preflight = get_defacing_preflight(resolved)
        return jsonify({"success": True, **preflight})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@projects_export_bp.route("/api/projects/export/deface", methods=["POST"])
def export_deface_anatomical_scans():
    """Run in-place defacing on anatomical scans in the current project."""
    try:
        from src.mri_json_scrubber import build_defacing_report, deface_anatomical_scans

        data = request.get_json() or {}
        project_path_raw = data.get("project_path")
        resolved = _resolve_project_root_path(project_path_raw)
        if resolved is None:
            return jsonify({"success": False, "error": "Invalid project path"}), 400

        force = bool(data.get("force", False))
        result = deface_anatomical_scans(resolved, force=force)
        post_report = build_defacing_report(resolved)
        counts = {"defaced": 0, "not_defaced": 0, "unknown": 0}
        for entry in post_report:
            status = str(entry.get("status", "unknown"))
            if status not in counts:
                status = "unknown"
            counts[status] += 1

        payload = {
            "success": bool(result.get("success", False)),
            "message": result.get("message") or result.get("error") or "",
            "error": result.get("error"),
            "defacing": {
                "counts": result.get("counts") or {},
                "items": result.get("items") or [],
            },
            "datalad": result.get("datalad") or {},
            "report": post_report,
            "report_counts": counts,
        }
        status_code = 200 if payload["success"] else 400
        return jsonify(payload), status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@projects_export_bp.route("/api/projects/export/start", methods=["POST"])
def export_project_start():
    """Start an async export job. Returns {job_id}."""
    try:
        data = request.get_json() or {}
        if not data:
            return jsonify({"error": "No data provided"}), 400

        project_path_raw = data.get("project_path")
        resolved = _resolve_project_root_path(project_path_raw)
        if resolved is None:
            return jsonify({"error": "Invalid project path"}), 400

        anonymize = bool(data.get("anonymize", True))
        mask_questions = bool(data.get("mask_questions", True))
        export_preset = _normalize_export_preset(data.get("export_preset", "standard"))
        include_derivatives = bool(data.get("include_derivatives", True))
        include_sourcedata = bool(data.get("include_sourcedata", False))
        include_code = bool(data.get("include_code", True))
        include_analysis = bool(data.get("include_analysis", False))
        exclude_version_control_metadata = bool(
            data.get("exclude_version_control_metadata", False)
        )
        scrub_mri_json = bool(data.get("scrub_mri_json", False))
        scrub_mri_json_groups = _normalize_scrub_group_ids(
            data.get("scrub_mri_json_groups")
        )
        validation_mode = _normalize_export_validation_mode(
            data.get("validation_mode", "both")
        )
        output_folder: Optional[str] = data.get("output_folder") or None

        if export_preset == "upload_ready":
            include_derivatives = False
            include_sourcedata = False
            include_code = False
            include_analysis = False
            exclude_version_control_metadata = True

        # Optional session / modality / sublabel filters
        exclude_sessions_list = data.get("exclude_sessions") or []
        exclude_modalities_list = data.get("exclude_modalities") or []
        # exclude_acq: dict of {modality: [acq_label, ...]} from client
        exclude_acq_raw = data.get("exclude_acq") or {}
        exclude_acq = (
            {mod: set(labels) for mod, labels in exclude_acq_raw.items() if labels}
            if exclude_acq_raw
            else None
        )
        # exclude_tasks: dict of {modality: [task_label, ...]} from client
        exclude_tasks_raw = data.get("exclude_tasks") or {}
        exclude_tasks = (
            {mod: set(labels) for mod, labels in exclude_tasks_raw.items() if labels}
            if exclude_tasks_raw
            else None
        )

        project_name = resolved.name
        anon_suffix = "_anonymized" if anonymize else ""
        preset_suffix = "_upload_ready" if export_preset == "upload_ready" else ""
        filename = f"{project_name}{anon_suffix}{preset_suffix}_export.zip"

        export_kwargs = {
            "project_path": resolved,
            "anonymize": anonymize,
            "mask_questions": mask_questions,
            "id_length": 8,
            "deterministic": True,
            "include_derivatives": include_derivatives,
            "include_sourcedata": include_sourcedata,
            "include_code": include_code,
            "include_analysis": include_analysis,
            "exclude_version_control_metadata": exclude_version_control_metadata,
            "scrub_mri_json": scrub_mri_json,
            "scrub_mri_json_groups": scrub_mri_json_groups,
            "clean_nifti_gzip_headers": scrub_mri_json,
            "validation_mode": validation_mode,
            "exclude_sessions": (
                set(exclude_sessions_list) if exclude_sessions_list else None
            ),
            "exclude_modalities": (
                set(exclude_modalities_list) if exclude_modalities_list else None
            ),
            "exclude_acq": exclude_acq,
            "exclude_tasks": exclude_tasks,
        }

        job_id = str(uuid.uuid4())
        _create_export_job(job_id)

        defacing_warning = _build_export_defacing_warning(resolved, scrub_mri_json)
        if defacing_warning:
            _update_export_job(job_id, defacing_warning=defacing_warning)

        t = threading.Thread(
            target=_run_export_job,
            args=(job_id, export_kwargs, filename, output_folder),
            daemon=True,
        )
        t.start()

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
    """
    Export the current project to ANC (Austrian NeuroCloud) compatible format.

    Expected JSON body:
    {
        "project_path": "/path/to/project",
        "convert_to_git_lfs": false,
        "include_ci_examples": false,
        "metadata": {
            "DATASET_NAME": "My Study",
            "CONTACT_EMAIL": "contact@example.com",
            "AUTHOR_GIVEN_NAME": "John",
            "AUTHOR_FAMILY_NAME": "Doe",
            "DATASET_ABSTRACT": "Description of the dataset"
        }
    }
    """
    try:
        data = request.get_json() or {}
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        project_path = data.get("project_path")
        resolved_project_path = _resolve_project_root_path(project_path)
        if resolved_project_path is None:
            return jsonify({"success": False, "error": "Invalid project path"}), 400

        project_path = resolved_project_path

        # Import AND exporter
        from src.converters.anc_export import ANCExporter

        # Get export options
        convert_to_git_lfs = bool(data.get("convert_to_git_lfs", False))
        include_ci_examples = bool(data.get("include_ci_examples", False))
        metadata = data.get("metadata", {})

        # Determine output path
        output_path = project_path.parent / f"{project_path.name}_anc_export"

        # Create exporter
        exporter = ANCExporter(project_path, output_path)

        # Perform export
        result_path = exporter.export(
            metadata=metadata,
            convert_to_git_lfs=convert_to_git_lfs,
            include_ci_examples=include_ci_examples,
            copy_data=True,
        )

        return jsonify(
            {
                "success": True,
                "output_path": str(result_path),
                "message": "ANC export completed successfully",
                "generated_files": {
                    "readme": str(result_path / "README.md"),
                    "citation": str(result_path / "CITATION.cff"),
                    "validator_config": str(
                        result_path / ".bids-validator-config.json"
                    ),
                },
            }
        )

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

        project_path_raw = data.get("project_path")
        resolved_project_path = _resolve_project_root_path(project_path_raw)
        if resolved_project_path is None:
            return jsonify({"success": False, "error": "Invalid project path"}), 400

        project_path = resolved_project_path
        validation_mode = _normalize_export_validation_mode(
            data.get("validation_mode", "both")
        )
        output_folder = str(data.get("output_folder") or "").strip()

        run_bids, run_prism = _export_validation_flags(validation_mode)
        if run_bids or run_prism:
            validation_error = _run_pre_export_validation(project_path, validation_mode)
            if validation_error:
                return jsonify({"success": False, "error": validation_error}), 400

        if output_folder:
            dest_dir = Path(output_folder).expanduser().resolve()
        else:
            dest_dir = project_path.parent
        dest_dir.mkdir(parents=True, exist_ok=True)

        output_zip = dest_dir / f"{project_path.name}_template_export.zip"

        from src.project_template_export import export_project_template_zip

        stats = export_project_template_zip(project_path, output_zip)
        return jsonify(
            {
                "success": True,
                "output_path": str(output_zip),
                "message": "Template export completed successfully",
                "stats": stats,
            }
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@projects_export_bp.route("/api/projects/openminds-tasks", methods=["GET"])
def openminds_get_tasks():
    """Return task names from the current project for the openMINDS pre-flight form."""
    try:
        project_path_value = request.args.get("project_path") or session.get(
            "current_project_path"
        )
        resolved = _resolve_project_root_path(project_path_value)
        if resolved is None:
            return jsonify({"success": False, "error": "No active project"}), 400

        project_json = resolved / "project.json"
        if not project_json.exists():
            return jsonify({"success": True, "tasks": []})

        with open(project_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        task_names = sorted(data.get("TaskDefinitions", {}).keys())
        return jsonify({"success": True, "tasks": task_names})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


def _patch_openminds_descriptions(
    output_path: Path, protocol_descriptions: dict
) -> None:
    """Post-process a bids2openminds .jsonld file to fill in behavioral protocol descriptions."""
    if not output_path.exists() or not protocol_descriptions:
        return

    with open(output_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    modified = False

    def _str_val(v):
        if isinstance(v, str):
            return v
        if isinstance(v, list) and len(v) == 1 and isinstance(v[0], dict):
            return v[0].get("@value", "")
        if isinstance(v, dict):
            return v.get("@value", "")
        return ""

    def _set_val(node, key, new_val):
        old = node[key]
        if isinstance(old, list) and len(old) == 1 and isinstance(old[0], dict):
            old[0]["@value"] = new_val
        elif isinstance(old, dict):
            old["@value"] = new_val
        else:
            node[key] = new_val

    def _patch_node(node):
        nonlocal modified
        if not isinstance(node, dict):
            return

        name_val = None
        desc_key = None

        for k, v in node.items():
            k_lower = k.lower()
            if (
                k_lower in ("name",)
                or k_lower.endswith("/name")
                or k_lower.endswith(":name")
            ):
                sv = _str_val(v)
                if sv:
                    name_val = sv
            if (
                k_lower in ("description",)
                or k_lower.endswith("/description")
                or k_lower.endswith(":description")
            ):
                if _str_val(v) == "To be defined":
                    desc_key = k

        if name_val and desc_key and name_val in protocol_descriptions:
            new_desc = protocol_descriptions[name_val].strip()
            if new_desc:
                _set_val(node, desc_key, new_desc)
                modified = True

    graph = data.get("@graph", [])
    if isinstance(graph, list):
        for node in graph:
            _patch_node(node)
    else:
        _patch_node(data)

    if modified:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


@projects_export_bp.route("/api/projects/openminds-export", methods=["POST"])
def openminds_export_project():
    """
    Export the current project to openMINDS metadata format using bids2openminds.

    Expected JSON body:
    {
        "project_path": "/path/to/project",
        "single_file": true,
        "include_empty": false
    }
    """
    try:
        data = request.get_json() or {}
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        project_path = data.get("project_path")
        resolved_project_path = _resolve_project_root_path(project_path)
        if resolved_project_path is None:
            return jsonify({"success": False, "error": "Invalid project path"}), 400

        project_path = resolved_project_path

        # Locate bids2openminds CLI (prefer same venv as current Python)
        python_bin_dir = Path(sys.executable).parent
        # On Windows the entry-point script has a .exe extension; try both.
        from src.cross_platform import get_executable_extension
        exe_ext = get_executable_extension()
        bids2openminds_cmd = str(python_bin_dir / f"bids2openminds{exe_ext}")
        if not Path(bids2openminds_cmd).is_file():
            # Fall back to PATH
            import shutil

            bids2openminds_cmd = shutil.which("bids2openminds")

        if not bids2openminds_cmd:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": (
                            "bids2openminds is not installed. "
                            "Install it with: pip install bids2openminds"
                        ),
                    }
                ),
                500,
            )

        # Get options
        single_file = bool(data.get("single_file", True))
        include_empty = bool(data.get("include_empty", False))
        supplements = data.get("supplements", {})

        # Determine output path
        project_name = project_path.name
        if single_file:
            output_path = project_path.parent / f"{project_name}_openminds.jsonld"
        else:
            output_path = project_path.parent / f"{project_name}_openminds"

        # Build command
        cmd = [
            bids2openminds_cmd,
            str(project_path),
            "-o",
            str(output_path),
            "--single-file" if single_file else "--multiple-files",
            "--quiet",
        ]
        if include_empty:
            cmd.append("--include-empty-properties")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            error_msg = (
                result.stderr or result.stdout or "bids2openminds conversion failed"
            ).strip()
            return jsonify({"success": False, "error": error_msg}), 500

        # Post-process: patch behavioral protocol descriptions if provided
        protocol_descriptions = supplements.get("protocol_descriptions", {})
        if protocol_descriptions and single_file and output_path.exists():
            _patch_openminds_descriptions(output_path, protocol_descriptions)

        # Write a notes file for ethics/other supplements that can't be auto-patched
        notes = {}
        ethics_category = supplements.get("ethics_category", "").strip()
        if ethics_category:
            notes["ethics_assessment"] = ethics_category
        if notes and single_file:
            notes_path = output_path.parent / (output_path.stem + "_supplements.json")
            with open(notes_path, "w", encoding="utf-8") as f:
                json.dump(notes, f, indent=2, ensure_ascii=False)

        return jsonify(
            {
                "success": True,
                "output_path": str(output_path),
                "single_file": single_file,
                "message": "openMINDS export completed successfully",
                "has_notes": bool(notes),
            }
        )

    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Export timed out (>5 min)"}), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
