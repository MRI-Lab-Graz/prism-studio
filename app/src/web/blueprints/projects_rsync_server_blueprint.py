"""Push a project to a plain remote destination via rsync, for users not using DataLad.

A simpler sibling of the "Push to DataLad Server" feature
(`projects_datalad_server_blueprint.py`): a single "Sync now" action that
copies the project to an SSH target or local/mounted path with `rsync -a`.
There is no sibling/connection state to register or disconnect — each sync
is just a copy, optionally followed by a checksum verification pass.
"""

import threading
import time
import traceback
import uuid
from threading import Lock
from typing import Dict

from flask import Blueprint, jsonify, request

from .projects_helpers import _resolve_project_root_path

projects_rsync_server_bp = Blueprint("projects_rsync_server", __name__)

# ---------------------------------------------------------------------------
# Async job store (same shape as the RIA sync/finalize job store)
# ---------------------------------------------------------------------------

_rsync_jobs: Dict[str, dict] = {}
_rsync_lock = Lock()
_RSYNC_JOB_TTL_SECONDS = 2 * 60 * 60
_RSYNC_DONE_STATUSES = {"complete", "error", "cancelled"}


def _rsync_now() -> float:
    return float(time.monotonic())


def _prune_rsync_jobs_locked() -> None:
    cutoff = _rsync_now() - _RSYNC_JOB_TTL_SECONDS
    expired = [
        job_id
        for job_id, job in _rsync_jobs.items()
        if job.get("done_at") is not None and float(job["done_at"]) <= cutoff
    ]
    for job_id in expired:
        _rsync_jobs.pop(job_id, None)


def _create_rsync_job(job_id: str) -> None:
    with _rsync_lock:
        _prune_rsync_jobs_locked()
        now = _rsync_now()
        _rsync_jobs[job_id] = {
            "status": "pending",
            "percent": 0,
            "message": "Starting...",
            "result": None,
            "error": None,
            "cancel_event": threading.Event(),
            "created_at": now,
            "updated_at": now,
            "done_at": None,
        }


def _update_rsync_job(job_id: str, **kwargs: object) -> None:
    with _rsync_lock:
        _prune_rsync_jobs_locked()
        job = _rsync_jobs.get(job_id)
        if job is None:
            return
        job.update(kwargs)
        now = _rsync_now()
        job["updated_at"] = now
        if job.get("status") in _RSYNC_DONE_STATUSES and job.get("done_at") is None:
            job["done_at"] = now


def _get_rsync_job(job_id: str) -> dict:
    with _rsync_lock:
        _prune_rsync_jobs_locked()
        job = _rsync_jobs.get(job_id)
        if job is None:
            return {}
        return {k: v for k, v in job.items() if k != "cancel_event"}


def _run_sync_job(job_id: str, project_path, sync_kwargs: dict) -> None:
    from src.project_manager import ProjectManager

    job = _rsync_jobs.get(job_id, {})
    cancel_event = job.get("cancel_event")

    def progress_callback(percent: int, message: str) -> None:
        _update_rsync_job(job_id, percent=percent, message=message, status="running")

    def is_cancelled() -> bool:
        return bool(cancel_event and cancel_event.is_set())

    try:
        manager = ProjectManager()
        result = manager.sync_project_to_remote(
            project_path,
            progress_callback=progress_callback,
            is_cancelled=is_cancelled,
            **sync_kwargs,
        )
        if is_cancelled() and not result.get("success"):
            _update_rsync_job(job_id, status="cancelled", message="Sync cancelled", percent=0)
            return
        if result.get("success"):
            _update_rsync_job(
                job_id,
                status="complete",
                percent=100,
                message=result.get("message", "Sync complete."),
                result=result,
            )
        else:
            _update_rsync_job(
                job_id,
                status="error",
                message=result.get("message", "Sync failed."),
                error=result.get("message", "Sync failed."),
                result=result,
            )
    except Exception as exc:
        _update_rsync_job(job_id, status="error", message=str(exc), error=str(exc))


@projects_rsync_server_bp.route("/api/projects/rsync-server/status", methods=["GET"])
def rsync_server_status():
    """Synchronous status check for the "Push to Remote Server" panel."""
    from src.project_manager import ProjectManager

    project_path_raw = request.args.get("project_path")
    resolved = _resolve_project_root_path(project_path_raw)
    if resolved is None:
        return jsonify({"error": "Invalid project path"}), 400

    manager = ProjectManager()
    status = manager.get_rsync_status(resolved)
    return jsonify(status)


@projects_rsync_server_bp.route("/api/projects/rsync-server/config", methods=["POST"])
def rsync_server_save_config():
    """Save the per-project remote target/label into .prismrc.json."""
    from pathlib import Path

    from src.config import load_config, save_config

    data = request.get_json() or {}
    project_path_raw = data.get("project_path")
    resolved = _resolve_project_root_path(project_path_raw)
    if resolved is None:
        return jsonify({"error": "Invalid project path"}), 400

    config = load_config(str(resolved))
    config.rsync_remote_target = str(data.get("remote_target") or "").strip() or None
    config.rsync_remote_label = str(data.get("remote_label") or "").strip() or None

    filename = Path(config._config_path).name if config._config_path else ".prismrc.json"
    saved_path = save_config(config, str(resolved), filename=filename)

    return jsonify(
        {
            "success": True,
            "remote_target": config.rsync_remote_target,
            "remote_label": config.rsync_remote_label,
            "config_path": saved_path,
        }
    )


@projects_rsync_server_bp.route("/api/projects/rsync-server/sync/start", methods=["POST"])
def rsync_server_sync_start():
    try:
        data = request.get_json() or {}
        project_path_raw = data.get("project_path")
        resolved = _resolve_project_root_path(project_path_raw)
        if resolved is None:
            return jsonify({"error": "Invalid project path"}), 400

        sync_kwargs = {
            "remote_target": (data.get("remote_target") or None),
            "remote_label": (data.get("remote_label") or None),
            "verify": bool(data.get("verify", False)),
        }

        job_id = str(uuid.uuid4())
        _create_rsync_job(job_id)

        t = threading.Thread(
            target=_run_sync_job,
            args=(job_id, resolved, sync_kwargs),
            daemon=True,
        )
        t.start()

        return jsonify({"job_id": job_id}), 200
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@projects_rsync_server_bp.route(
    "/api/projects/rsync-server/sync/<job_id>/status", methods=["GET"]
)
def rsync_server_sync_status(job_id: str):
    job = _get_rsync_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(
        {
            "status": job.get("status"),
            "percent": job.get("percent", 0),
            "message": job.get("message", ""),
            "error": job.get("error"),
            "result": job.get("result"),
        }
    )


@projects_rsync_server_bp.route(
    "/api/projects/rsync-server/sync/<job_id>/cancel", methods=["DELETE"]
)
def rsync_server_sync_cancel(job_id: str):
    with _rsync_lock:
        job = _rsync_jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    cancel_event = job.get("cancel_event")
    if cancel_event:
        cancel_event.set()
    return jsonify({"cancelled": True})
