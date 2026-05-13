from __future__ import annotations

import io
import json
import shutil
import tempfile
import threading
import uuid
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from flask import jsonify, request
from werkzeug.utils import secure_filename


def _run_environment_backend_command(command_fn, **kwargs):
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    exit_code = 0
    with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
        try:
            command_fn(SimpleNamespace(**kwargs))
        except SystemExit as exc:
            try:
                exit_code = int(exc.code)
            except Exception:
                exit_code = 1
    raw_output = stdout_buffer.getvalue().strip()
    stderr_output = stderr_buffer.getvalue().strip()

    payload: dict[str, Any]
    if raw_output:
        try:
            payload = json.loads(raw_output)
        except Exception:
            payload = {"error": raw_output}
    elif stderr_output:
        payload = {"error": stderr_output}
    elif exit_code == 0:
        payload = {}
    else:
        payload = {"error": "Environment backend command failed"}

    return payload, exit_code


def _environment_command_http_status(exit_code: int) -> int:
    return 400 if exit_code == 2 else 500


def handle_api_environment_preview(
    *,
    resolve_uploaded_or_source_file,
    allowed_suffixes,
    normalize_separator_option,
):
    """Read an uploaded tabular file and return column names + sample rows."""
    uploaded, upload_error = resolve_uploaded_or_source_file(field_names=("file",))
    if uploaded is None or not getattr(uploaded, "filename", ""):
        return jsonify({"error": upload_error or "No file provided"}), 400

    filename = secure_filename(uploaded.filename or "")
    suffix = Path(filename).suffix.lower()
    if suffix not in allowed_suffixes:
        return (
            jsonify(
                {
                    "error": (
                        f"Unsupported file type '{suffix}'. Use .xlsx, .csv, .tsv, .sav, "
                        ".rds, .rdata, or .rda"
                    )
                }
            ),
            400,
        )

    try:
        separator_option = normalize_separator_option(request.form.get("separator"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    from src.cli.commands.environment import cmd_environment_preview

    tmp_dir = tempfile.mkdtemp(prefix="prism_env_preview_")
    try:
        input_path = Path(tmp_dir) / filename
        uploaded.save(str(input_path))
        payload, exit_code = _run_environment_backend_command(
            cmd_environment_preview,
            input=str(input_path),
            separator=separator_option,
            json=True,
        )
        if exit_code != 0:
            return jsonify(payload), _environment_command_http_status(exit_code)
        return jsonify(payload)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def handle_api_environment_convert_start(
    *,
    build_environment_conversion_config_from_request,
    start_environment_detached_job,
    logger,
    environment_job_store,
    append_environment_job_log,
    run_environment_job,
):
    """Start an async environment conversion job."""
    try:
        config, _ = build_environment_conversion_config_from_request()
    except (ValueError, FileNotFoundError) as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    if bool(config.get("convert_in_background", False)):
        try:
            job_id, pid, log_path, result_path = start_environment_detached_job(config)
        except Exception as exc:
            shutil.rmtree(config["tmp_dir"], ignore_errors=True)
            logger.exception("Failed to start detached environment conversion")
            return jsonify({"error": str(exc)}), 500

        return (
            jsonify(
                {
                    "job_id": job_id,
                    "background": True,
                    "pid": pid,
                    "log_path": str(log_path),
                    "result_path": str(result_path),
                }
            ),
            200,
        )

    job_id = ""
    for _ in range(5):
        candidate = uuid.uuid4().hex
        try:
            environment_job_store.create(candidate)
            job_id = candidate
            break
        except ValueError:
            continue
    if not job_id:
        shutil.rmtree(config["tmp_dir"], ignore_errors=True)
        return jsonify({"error": "Could not allocate conversion job id"}), 500

    append_environment_job_log(job_id, "🌍 Environment conversion job started", "info")

    thread = threading.Thread(
        target=run_environment_job, args=(job_id, config), daemon=True
    )
    thread.start()

    return jsonify({"job_id": job_id}), 200


def handle_api_environment_convert_cancel(
    *,
    job_id: str,
    mark_environment_job_cancelled,
    append_environment_job_log,
    environment_detached_jobs_lock,
    environment_detached_jobs,
):
    """Cancel an async environment conversion job."""
    if mark_environment_job_cancelled(job_id):
        append_environment_job_log(job_id, "⏹️ User requested cancellation", "warning")
        return (
            jsonify(
                {
                    "message": "Cancellation requested for job",
                    "job_id": job_id,
                    "status": "cancelling",
                }
            ),
            200,
        )

    with environment_detached_jobs_lock:
        detached_job = environment_detached_jobs.get(job_id)

    if detached_job:
        cancel_path = Path(detached_job["cancel_path"])
        cancel_path.parent.mkdir(parents=True, exist_ok=True)
        cancel_path.write_text("cancelled", encoding="utf-8")
        log_path = Path(detached_job["log_path"])
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("warning\t⏹️ User requested cancellation\n")
        return (
            jsonify(
                {
                    "message": "Cancellation requested for detached job",
                    "job_id": job_id,
                    "status": "cancelling",
                    "background": True,
                    "pid": detached_job.get("pid"),
                }
            ),
            200,
        )

    return jsonify({"error": "Job not found or already finished"}), 404


def handle_api_environment_convert_metrics(
    *,
    environment_job_store,
    environment_detached_jobs_lock,
    environment_detached_jobs,
):
    """Return in-memory environment conversion metrics for debugging/monitoring."""
    payload = environment_job_store.metrics()
    with environment_detached_jobs_lock:
        payload["detached_jobs"] = len(environment_detached_jobs)
    return jsonify(payload), 200


def handle_api_environment_convert_status(
    *,
    job_id: str,
    environment_job_store,
    environment_detached_jobs_lock,
    environment_detached_jobs,
    parse_detached_log_lines,
):
    """Get incremental status and logs for an async environment conversion job."""
    try:
        cursor = int(request.args.get("cursor", "0"))
    except ValueError:
        cursor = 0

    payload = environment_job_store.snapshot(job_id, cursor)
    if payload is not None:
        return jsonify(payload), 200

    with environment_detached_jobs_lock:
        detached_job = environment_detached_jobs.get(job_id)
        if not detached_job:
            return jsonify({"error": "Job not found"}), 404

    log_path = Path(detached_job["log_path"])
    result_path = Path(detached_job["result_path"])
    logs, next_cursor = parse_detached_log_lines(log_path, cursor)

    if not result_path.exists():
        return (
            jsonify(
                {
                    "logs": logs,
                    "next_cursor": next_cursor,
                    "done": False,
                    "status": "running",
                    "progress_pct": None,
                    "success": None,
                    "result": None,
                    "error": None,
                    "background": True,
                    "pid": detached_job.get("pid"),
                }
            ),
            200,
        )

    try:
        final_state = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception as exc:
        final_state = {
            "done": True,
            "success": False,
            "result": None,
            "error": f"Could not read detached result: {exc}",
        }

    with environment_detached_jobs_lock:
        environment_detached_jobs.pop(job_id, None)

    return (
        jsonify(
            {
                "logs": logs,
                "next_cursor": next_cursor,
                "done": bool(final_state.get("done", True)),
                "status": (
                    "cancelled"
                    if final_state.get("error") == "Conversion cancelled by user"
                    else ("completed" if final_state.get("success") else "failed")
                ),
                "progress_pct": 100 if final_state.get("success") else None,
                "success": final_state.get("success"),
                "result": final_state.get("result"),
                "error": final_state.get("error"),
                "background": True,
                "pid": detached_job.get("pid"),
            }
        ),
        200,
    )