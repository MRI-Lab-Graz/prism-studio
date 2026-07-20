"""Push a finished PRISM/DataLad project to a central DataLad sibling
(a RIA store, or a plain SSH/local sibling for a server that was never set
up with a RIA layout -- see `run_datalad_create_sibling` in
datalad_execution.py).

Two distinct operations, mirroring the async job pattern used by the Export
feature (`/start` -> background thread -> `/status` polling -> `/cancel`):

- "Sync now": connect (idempotent) + push. Safe to run repeatedly throughout
  a study; the sibling stays registered as an ongoing backup. An optional
  `verify` flag additionally confirms every annexed key actually reached
  the sibling before reporting success -- useful before treating the local
  copy as safe to delete, without going through a full finalize/disconnect.
- "Finalize & disconnect": one last push, a verification step, then removes
  the local sibling registration. Local files are kept. Disconnect only
  happens if verification passes, so a failed/partial run can be retried.
"""

import threading
import time
import traceback
import uuid
from threading import Lock
from typing import Dict, Optional

from flask import Blueprint, jsonify, request

from .projects_helpers import _resolve_project_root_path

projects_datalad_server_bp = Blueprint("projects_datalad_server", __name__)

# ---------------------------------------------------------------------------
# Async job store (shared shape for both "sync" and "finalize" jobs)
# ---------------------------------------------------------------------------

_ria_jobs: Dict[str, dict] = {}
_ria_lock = Lock()
_RIA_JOB_TTL_SECONDS = 2 * 60 * 60
_RIA_DONE_STATUSES = {"complete", "error", "cancelled"}


def _ria_now() -> float:
    return float(time.monotonic())


def _prune_ria_jobs_locked() -> None:
    cutoff = _ria_now() - _RIA_JOB_TTL_SECONDS
    expired = [
        job_id
        for job_id, job in _ria_jobs.items()
        if job.get("done_at") is not None and float(job["done_at"]) <= cutoff
    ]
    for job_id in expired:
        _ria_jobs.pop(job_id, None)


def _create_ria_job(job_id: str, *, kind: str) -> None:
    with _ria_lock:
        _prune_ria_jobs_locked()
        now = _ria_now()
        _ria_jobs[job_id] = {
            "kind": kind,
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


def _update_ria_job(job_id: str, **kwargs: object) -> None:
    with _ria_lock:
        _prune_ria_jobs_locked()
        job = _ria_jobs.get(job_id)
        if job is None:
            return
        job.update(kwargs)
        now = _ria_now()
        job["updated_at"] = now
        if job.get("status") in _RIA_DONE_STATUSES and job.get("done_at") is None:
            job["done_at"] = now


def _get_ria_job(job_id: str) -> dict:
    with _ria_lock:
        _prune_ria_jobs_locked()
        job = _ria_jobs.get(job_id)
        if job is None:
            return {}
        return {k: v for k, v in job.items() if k != "cancel_event"}


def _run_sync_job(job_id: str, project_path, ria_kwargs: dict) -> None:
    from src.project_manager import ProjectManager

    job = _ria_jobs.get(job_id, {})
    cancel_event = job.get("cancel_event")

    def progress_callback(percent: int, message: str) -> None:
        _update_ria_job(job_id, percent=percent, message=message, status="running")

    def is_cancelled() -> bool:
        return bool(cancel_event and cancel_event.is_set())

    try:
        manager = ProjectManager()
        result = manager.sync_project_to_ria(
            project_path,
            progress_callback=progress_callback,
            is_cancelled=is_cancelled,
            **ria_kwargs,
        )
        if is_cancelled():
            _update_ria_job(job_id, status="cancelled", message="Sync cancelled", percent=0)
            return
        if result.get("success"):
            _update_ria_job(
                job_id,
                status="complete",
                percent=100,
                message=result.get("message", "Sync complete."),
                result=result,
            )
        else:
            _update_ria_job(
                job_id,
                status="error",
                message=result.get("message", "Sync failed."),
                error=result.get("message", "Sync failed."),
                result=result,
            )
    except Exception as exc:
        _update_ria_job(job_id, status="error", message=str(exc), error=str(exc))


def _run_finalize_job(job_id: str, project_path, ria_kwargs: dict) -> None:
    from src.project_manager import ProjectManager

    job = _ria_jobs.get(job_id, {})
    cancel_event = job.get("cancel_event")

    def progress_callback(percent: int, message: str) -> None:
        _update_ria_job(job_id, percent=percent, message=message, status="running")

    def is_cancelled() -> bool:
        return bool(cancel_event and cancel_event.is_set())

    try:
        manager = ProjectManager()
        result = manager.finalize_project_upload(
            project_path,
            progress_callback=progress_callback,
            is_cancelled=is_cancelled,
            **ria_kwargs,
        )
        if is_cancelled() and not result.get("success"):
            _update_ria_job(job_id, status="cancelled", message="Finalize cancelled", percent=0)
            return
        if result.get("success"):
            _update_ria_job(
                job_id,
                status="complete",
                percent=100,
                message=result.get("message", "Finalize complete."),
                result=result,
            )
        else:
            _update_ria_job(
                job_id,
                status="error",
                message=result.get("message", "Finalize failed."),
                error=result.get("message", "Finalize failed."),
                result=result,
            )
    except Exception as exc:
        _update_ria_job(job_id, status="error", message=str(exc), error=str(exc))


def _start_ria_job(kind: str, runner) -> tuple:
    try:
        data = request.get_json() or {}
        project_path_raw = data.get("project_path")
        resolved = _resolve_project_root_path(str(project_path_raw or ""))
        if resolved is None:
            return jsonify({"error": "Invalid project path"}), 400

        ria_kwargs = {
            "ria_url": (data.get("ria_url") or None),
            "sibling_name": (data.get("sibling_name") or None),
            "alias": (data.get("alias") or None),
        }
        if kind == "sync":
            ria_kwargs["verify"] = bool(data.get("verify", False))
        if kind == "finalize":
            ria_kwargs["verify_mode"] = str(data.get("verify_mode") or "fast").strip().lower()
            ria_kwargs["mark_annex_dead"] = bool(data.get("mark_annex_dead", False))

        job_id = str(uuid.uuid4())
        _create_ria_job(job_id, kind=kind)

        t = threading.Thread(
            target=runner,
            args=(job_id, resolved, ria_kwargs),
            daemon=True,
        )
        t.start()

        return jsonify({"job_id": job_id}), 200
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@projects_datalad_server_bp.route("/api/projects/datalad-server/status", methods=["GET"])
def datalad_server_status():
    """Synchronous status check for the "Push to DataLad Server" panel."""
    from src.project_manager import ProjectManager

    project_path_raw = request.args.get("project_path")
    resolved = _resolve_project_root_path(project_path_raw)
    if resolved is None:
        return jsonify({"error": "Invalid project path"}), 400

    manager = ProjectManager()
    status = manager.get_ria_status(resolved)
    return jsonify(status)


@projects_datalad_server_bp.route("/api/projects/datalad-server/config", methods=["POST"])
def datalad_server_save_config():
    """Save the per-project RIA URL/sibling name/alias into .prismrc.json."""
    from pathlib import Path

    from src.config import load_config, save_config

    data = request.get_json() or {}
    project_path_raw = data.get("project_path")
    resolved = _resolve_project_root_path(project_path_raw)
    if resolved is None:
        return jsonify({"error": "Invalid project path"}), 400

    config = load_config(str(resolved))
    config.datalad_ria_store_url = str(data.get("ria_url") or "").strip() or None
    config.datalad_sibling_name = str(data.get("sibling_name") or "").strip() or "ria-store"
    config.datalad_sibling_alias = str(data.get("alias") or "").strip() or None

    filename = Path(config._config_path).name if config._config_path else ".prismrc.json"
    saved_path = save_config(config, str(resolved), filename=filename)

    return jsonify(
        {
            "success": True,
            "ria_url": config.datalad_ria_store_url,
            "sibling_name": config.datalad_sibling_name,
            "sibling_alias": config.datalad_sibling_alias,
            "config_path": saved_path,
        }
    )


@projects_datalad_server_bp.route("/api/projects/datalad-server/sync/start", methods=["POST"])
def datalad_server_sync_start():
    return _start_ria_job("sync", _run_sync_job)


@projects_datalad_server_bp.route(
    "/api/projects/datalad-server/sync/<job_id>/status", methods=["GET"]
)
def datalad_server_sync_status(job_id: str):
    job = _get_ria_job(job_id)
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


@projects_datalad_server_bp.route(
    "/api/projects/datalad-server/sync/<job_id>/cancel", methods=["DELETE"]
)
def datalad_server_sync_cancel(job_id: str):
    with _ria_lock:
        job = _ria_jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    cancel_event = job.get("cancel_event")
    if cancel_event:
        cancel_event.set()
    return jsonify({"cancelled": True})


@projects_datalad_server_bp.route("/api/projects/datalad-server/finalize/start", methods=["POST"])
def datalad_server_finalize_start():
    return _start_ria_job("finalize", _run_finalize_job)


@projects_datalad_server_bp.route(
    "/api/projects/datalad-server/finalize/<job_id>/status", methods=["GET"]
)
def datalad_server_finalize_status(job_id: str):
    job = _get_ria_job(job_id)
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


@projects_datalad_server_bp.route(
    "/api/projects/datalad-server/finalize/<job_id>/cancel", methods=["DELETE"]
)
def datalad_server_finalize_cancel(job_id: str):
    with _ria_lock:
        job = _ria_jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    cancel_event = job.get("cancel_event")
    if cancel_event:
        cancel_event.set()
    return jsonify({"cancelled": True})
