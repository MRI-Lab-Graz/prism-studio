"""Sync a project with the lab's DataLad server (the same function as `prism_tools datalad sync`).

"Sync now" runs as an async job (`/start` -> background thread -> `/status` polling -> `/cancel`): it gets the latest
changes from the server, then sends the saved changes, and only if the dataset validates.
"""

import threading
import time
import traceback
import uuid
from pathlib import Path
from threading import Lock
from typing import Dict

from flask import Blueprint, jsonify, request

from src.share_publish import parse_identity, publish_to_server

from .projects_helpers import _resolve_project_root_path

projects_datalad_server_bp = Blueprint("projects_datalad_server", __name__)

# ---------------------------------------------------------------------------
# Async job store for "sync" and "put" jobs
# ---------------------------------------------------------------------------

_jobs: Dict[str, dict] = {}
_lock = Lock()
_JOB_TTL_SECONDS = 2 * 60 * 60
_DONE_STATUSES = {"complete", "error", "cancelled"}


def _now() -> float:
    return float(time.monotonic())


def _prune_jobs_locked() -> None:
    cutoff = _now() - _JOB_TTL_SECONDS
    expired = [
        job_id
        for job_id, job in _jobs.items()
        if job.get("done_at") is not None and float(job["done_at"]) <= cutoff
    ]
    for job_id in expired:
        _jobs.pop(job_id, None)


def _create_job(job_id: str, *, kind: str) -> None:
    with _lock:
        _prune_jobs_locked()
        now = _now()
        _jobs[job_id] = {
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


def _update_job(job_id: str, **kwargs: object) -> None:
    with _lock:
        _prune_jobs_locked()
        job = _jobs.get(job_id)
        if job is None:
            return
        job.update(kwargs)
        now = _now()
        job["updated_at"] = now
        if job.get("status") in _DONE_STATUSES and job.get("done_at") is None:
            job["done_at"] = now


def _get_job(job_id: str) -> dict:
    with _lock:
        _prune_jobs_locked()
        job = _jobs.get(job_id)
        if job is None:
            return {}
        return {k: v for k, v in job.items() if k != "cancel_event"}


def _run_job(job_id: str, label: str, running: str, call) -> None:
    """Run `call(line_callback)` as job `job_id`; its result dict decides complete or error."""
    cancel_event = _jobs.get(job_id, {}).get("cancel_event")
    if cancel_event and cancel_event.is_set():  # a push that has begun is never interrupted
        _update_job(job_id, status="cancelled", message=f"{label} cancelled", percent=0)
        return
    try:
        _update_job(job_id, status="running", percent=10, message=running)
        result = call(lambda line: _update_job(job_id, message=line, status="running"))
        if result.get("success"):
            _update_job(job_id, status="complete", percent=100, message=result["message"], result=result)
        else:
            detail = "\n".join([result.get("message", f"{label} failed."), *result.get("errors", [])[:20]])
            _update_job(job_id, status="error", message=detail, error=detail, result=result)
    except Exception as exc:
        _update_job(job_id, status="error", message=str(exc), error=str(exc))


def _run_sync_job(job_id: str, project_path, sync_kwargs: dict) -> None:
    """The same function as `prism_tools datalad sync`: get the latest, then publish a valid dataset."""
    from src.share_publish import sync_with_server

    _run_job(job_id, "Sync", "Syncing with the server...", lambda line_callback: sync_with_server(
        project_path,
        sibling_name=sync_kwargs.get("sibling_name"),
        identity=sync_kwargs.get("identity"),
        allow_invalid=bool(sync_kwargs.get("allow_invalid")),
        line_callback=line_callback,
    ))


def _run_put_job(job_id: str, project_path, put_kwargs: dict) -> None:
    """The same function as `prism_tools datalad put-on-server`: create the dataset on the server, then publish."""
    from src.share_publish import put_on_server

    _run_job(job_id, "Put on server", "Putting the project on the server...", lambda line_callback: put_on_server(
        project_path,
        str(put_kwargs.get("location") or ""),
        sibling_name=put_kwargs.get("sibling_name"),
        identity=put_kwargs.get("identity"),
        allow_invalid=bool(put_kwargs.get("allow_invalid")),
        line_callback=line_callback,
    ))


def _run_open_job(job_id: str, target, open_kwargs: dict) -> None:
    """The same function as `prism_tools datalad open-from-server`; the result's `path` is the project the page opens."""
    from src.datalad_clone import open_from_server

    _run_job(job_id, "Open from server", "Opening the project from the server...", lambda line_callback: open_from_server(
        str(open_kwargs.get("location") or ""), target, line_callback=line_callback
    ))


def _run_get_job(job_id: str, project_path, get_kwargs: dict) -> None:
    """The same function as `prism_tools datalad get-data`: fetch the data the export's filters choose."""
    from src.datalad_get_data import filters_from_options, get_data

    _run_job(job_id, "Get data", "Fetching data from the server...", lambda line_callback: get_data(
        project_path, line_callback=line_callback, **filters_from_options(get_kwargs.get("options") or {})
    ))


def _start_job(kind: str, runner, *, path_key: str = "project_path", resolve=_resolve_project_root_path) -> tuple:
    try:
        data = request.get_json() or {}
        resolved = resolve(str(data.get(path_key) or ""))
        if resolved is None:
            return jsonify({"error": f"Invalid {path_key.replace('_', ' ')}"}), 400

        identity = None  # the CLI's --as, built exactly as the publish route does
        if data.get("name") or data.get("email"):
            try:
                identity = parse_identity(f'{data.get("name", "")} <{data.get("email", "")}>')
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
        job_kwargs = {
            "identity": identity,
            "sibling_name": data.get("sibling_name") or None,
            "allow_invalid": bool(data.get("allow_invalid")),
            "location": str(data.get("location") or ""),
            "options": data,
        }

        job_id = str(uuid.uuid4())
        _create_job(job_id, kind=kind)

        # The job body runs on a separate thread, which does NOT inherit
        # Flask's request-local app context -- without explicitly pushing
        # one here, ProjectManager._emit_backend_progress's has_app_context()
        # check silently no-ops for the whole sync run, so none of
        # its terminal progress lines (the same live "ACTION/COMMAND" output
        # nested-subdataset registration produces) would ever be printed.
        from flask import current_app

        app_obj = current_app._get_current_object()  # type: ignore[attr-defined]

        def _run_with_app_context(*args, **kwargs):
            with app_obj.app_context():
                runner(*args, **kwargs)

        t = threading.Thread(
            target=_run_with_app_context,
            args=(job_id, resolved, job_kwargs),
            daemon=True,
        )
        t.start()

        return jsonify({"job_id": job_id}), 200
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@projects_datalad_server_bp.route("/api/projects/datalad-server/sync/start", methods=["POST"])
def datalad_server_sync_start():
    return _start_job("sync", _run_sync_job)


@projects_datalad_server_bp.route("/api/projects/datalad/put-on-server", methods=["POST"])
def datalad_put_on_server():
    """Start `prism_tools datalad put-on-server` as a job; poll it with the sync job's status and cancel routes."""
    return _start_job("put", _run_put_job)


@projects_datalad_server_bp.route("/api/projects/datalad/get-data", methods=["POST"])
def datalad_get_data():
    """Start `prism_tools datalad get-data` as a job; poll it with the sync job's status and cancel routes."""
    return _start_job("get", _run_get_job)


@projects_datalad_server_bp.route("/api/projects/datalad/open-from-server", methods=["POST"])
def datalad_open_from_server():
    """Start `prism_tools datalad open-from-server` as a job (no project needed); poll it with the sync job's routes.

    When it completes, the page opens `result.path` through POST /api/projects/current, as opening any project does.
    """
    from src.datalad_clone import target_problem

    problem = target_problem((request.get_json(silent=True) or {}).get("target"))
    if problem:  # the CLI's bad_target, refused before a job starts
        return jsonify({"error": problem}), 400
    return _start_job("open", _run_open_job, path_key="target", resolve=lambda raw: Path(raw))


@projects_datalad_server_bp.route(
    "/api/projects/datalad-server/sync/<job_id>/status", methods=["GET"]
)
def datalad_server_sync_status(job_id: str):
    job = _get_job(job_id)
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
    with _lock:
        job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    cancel_event = job.get("cancel_event")
    if cancel_event:
        cancel_event.set()
    return jsonify({"cancelled": True})


@projects_datalad_server_bp.route("/api/projects/datalad-server/publish", methods=["POST"])
def datalad_server_publish():
    """Validity-gated push of a share dataset (same code path as `prism_tools publish`).

    ponytail: synchronous; move onto the _jobs machinery if share pushes get slow.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "JSON object body required"}), 400
    resolved = _resolve_project_root_path(str(data.get("project_path") or ""))
    if resolved is None:
        return jsonify({"error": "Invalid project path"}), 400
    identity = None
    if data.get("name") or data.get("email"):
        try:
            identity = parse_identity(f'{data.get("name", "")} <{data.get("email", "")}>')
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
    result = publish_to_server(
        resolved,
        sibling_name=data.get("sibling_name") or None,
        identity=identity,
        allow_invalid=bool(data.get("allow_invalid")),
    )
    status = 200 if result["success"] else 409 if result["reason"] == "validation_errors" else 400
    return jsonify(result), status
