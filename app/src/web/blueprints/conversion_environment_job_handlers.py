from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any


def handle_run_environment_detached_job(
    *,
    config_path: str,
    perform_environment_conversion,
    environment_conversion_cancelled_error_cls,
    logger,
):
    config_file = Path(config_path)
    payload = json.loads(config_file.read_text(encoding="utf-8"))

    log_path = Path(payload["log_path"])
    result_path = Path(payload["result_path"])
    cancel_path = Path(payload["cancel_path"])
    config = payload["config"]

    def log_callback(message: str, level: str = "info") -> None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(f"{level}\t{message}\n")

    config["input_path"] = Path(config["input_path"])
    log_callback("🌍 Environment conversion job started", "info")

    result_payload: dict[str, Any]
    try:
        result = perform_environment_conversion(
            input_path=config["input_path"],
            filename=config["filename"],
            suffix=config["suffix"],
            separator_option=config["separator_option"],
            timestamp_col=config["timestamp_col"],
            participant_col=config["participant_col"],
            participant_override=config["participant_override"],
            session_col=config["session_col"],
            session_override=config["session_override"],
            location_col=config["location_col"],
            lat_col=config["lat_col"],
            lon_col=config["lon_col"],
            location_label_override=config["location_label_override"],
            lat_manual=config["lat_manual"],
            lon_manual=config["lon_manual"],
            project_path=config["project_path"],
            pilot_random_subject=bool(config.get("pilot_random_subject", False)),
            log_callback=log_callback,
            cancel_check=lambda: cancel_path.exists(),
        )
        result_payload = {
            "done": True,
            "success": True,
            "result": result,
            "error": None,
        }
    except environment_conversion_cancelled_error_cls as exc:
        result_payload = {
            "done": True,
            "success": False,
            "result": None,
            "error": str(exc),
        }
    except ValueError as exc:
        result_payload = {
            "done": True,
            "success": False,
            "result": None,
            "error": str(exc),
        }
    except Exception as exc:
        logger.exception("Detached environment conversion failed")
        result_payload = {
            "done": True,
            "success": False,
            "result": None,
            "error": str(exc),
        }
    finally:
        tmp_dir = config.get("tmp_dir")
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result_payload), encoding="utf-8")


def handle_start_environment_detached_job(
    *,
    config: dict[str, Any],
    environment_detached_jobs_lock,
    environment_detached_jobs,
):
    project_root_path = Path(config["project_path"])
    if project_root_path.is_file():
        project_root_path = project_root_path.parent

    jobs_dir = project_root_path / ".prism" / "environment_jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)

    job_id = uuid.uuid4().hex
    log_path = jobs_dir / f"{job_id}.log"
    result_path = jobs_dir / f"{job_id}.result.json"
    cancel_path = jobs_dir / f"{job_id}.cancel"

    app_root = Path(__file__).resolve().parents[3]
    prism_tools_script = app_root / "prism_tools.py"
    python_exec = sys.executable or "python"
    command = [
        python_exec,
        str(prism_tools_script),
        "environment",
        "convert",
        "--input",
        str(config["input_path"]),
        "--project",
        str(config["project_path"]),
        "--separator",
        str(config["separator_option"]),
        "--timestamp-col",
        str(config["timestamp_col"]),
        "--participant-col",
        str(config["participant_col"]),
        "--json",
        "--log-file",
        str(log_path),
        "--result-file",
        str(result_path),
        "--cancel-file",
        str(cancel_path),
    ]

    if config.get("participant_override"):
        command.extend(["--participant-override", str(config["participant_override"])])
    if config.get("session_col"):
        command.extend(["--session-col", str(config["session_col"])])
    if config.get("session_override"):
        command.extend(["--session-override", str(config["session_override"])])
    if config.get("location_col"):
        command.extend(["--location-col", str(config["location_col"])])
    if config.get("lat_col"):
        command.extend(["--lat-col", str(config["lat_col"])])
    if config.get("lon_col"):
        command.extend(["--lon-col", str(config["lon_col"])])
    if config.get("location_label_override"):
        command.extend(["--location-label", str(config["location_label_override"])])
    if config.get("lat_manual") is not None:
        command.extend(["--lat", str(config["lat_manual"])])
    if config.get("lon_manual") is not None:
        command.extend(["--lon", str(config["lon_manual"])])
    if bool(config.get("pilot_random_subject", False)):
        command.append("--pilot-random-subject")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as log_file:
        log_file.write(f"info\tDetached command: {' '.join(command)}\n")
        process = subprocess.Popen(  # noqa: S603,S607
            command,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )

    with environment_detached_jobs_lock:
        environment_detached_jobs[job_id] = {
            "pid": int(process.pid),
            "log_path": str(log_path),
            "result_path": str(result_path),
            "cancel_path": str(cancel_path),
        }

    return job_id, int(process.pid), log_path, result_path


def handle_run_environment_job(
    *,
    job_id: str,
    config: dict[str, Any],
    is_environment_job_cancelled,
    append_environment_job_log,
    environment_job_store,
    perform_environment_conversion,
    environment_conversion_cancelled_error_cls,
    logger,
):
    if is_environment_job_cancelled(job_id):
        append_environment_job_log(
            job_id, "⏹️ Environment conversion cancelled (before start)", "warning"
        )
        environment_job_store.failure(
            job_id,
            "Cancelled by user",
            status="cancelled",
        )
        return

    try:
        progress_callback = None
        if not bool(config.get("pilot_random_subject", False)):
            progress_callback = lambda pct: environment_job_store.update(
                job_id,
                progress_pct=max(0, min(100, int(pct))),
            )

        result = perform_environment_conversion(
            input_path=config["input_path"],
            filename=config["filename"],
            suffix=config["suffix"],
            separator_option=config["separator_option"],
            timestamp_col=config["timestamp_col"],
            participant_col=config["participant_col"],
            participant_override=config["participant_override"],
            session_col=config["session_col"],
            session_override=config["session_override"],
            location_col=config["location_col"],
            lat_col=config["lat_col"],
            lon_col=config["lon_col"],
            location_label_override=config["location_label_override"],
            lat_manual=config["lat_manual"],
            lon_manual=config["lon_manual"],
            project_path=config["project_path"],
            pilot_random_subject=bool(config.get("pilot_random_subject", False)),
            log_callback=lambda message, level="info": append_environment_job_log(
                job_id, message, level
            ),
            progress_callback=progress_callback,
            job_id=job_id,
            cancel_check=lambda: is_environment_job_cancelled(job_id),
        )
        environment_job_store.success(job_id, result)
    except environment_conversion_cancelled_error_cls as exc:
        environment_job_store.failure(job_id, str(exc), status="cancelled")
    except ValueError as exc:
        environment_job_store.failure(job_id, str(exc))
    except Exception as exc:
        logger.exception("Environment conversion failed")
        environment_job_store.failure(job_id, str(exc))
    finally:
        shutil.rmtree(config["tmp_dir"], ignore_errors=True)