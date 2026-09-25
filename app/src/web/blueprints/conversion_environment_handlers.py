"""
Flask routes and job orchestration for the Studio Environment tab.

The conversion engine itself lives in `src/environment_conversion.py`
(shared with `prism_tools.py environment ...`); this module only parses
requests, runs jobs in threads/detached processes, and reports status.
"""

from __future__ import annotations

import logging
import shutil
import subprocess  # noqa: F401 - patched by tests via this module
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any

import requests
from flask import request, jsonify, session

from src.environment_conversion import (
    ALLOWED_SUFFIXES,
    GEOCODING_TIMEOUT_SECONDS,
    GEOCODING_URL,
    EnvironmentConversionCancelledError,
    _coerce_coord,
    perform_environment_conversion as _perform_environment_conversion,
)
from src.environment_mri_scan import (
    build_mri_acquisition_table,
    resolve_bids_rawdata_root,
)
from .conversion_job_store import ConversionJobStore
from .conversion_environment_route_handlers import (
    handle_api_environment_convert_cancel,
    handle_api_environment_convert_metrics,
    handle_api_environment_convert_start,
    handle_api_environment_convert_status,
    handle_api_environment_preview,
)
from .conversion_environment_job_handlers import (
    handle_run_environment_detached_job,
    handle_run_environment_job,
    handle_start_environment_detached_job,
)
from .conversion_environment_config_helpers import (
    handle_build_environment_conversion_config_from_request,
)
from .conversion_request_helpers import (
    resolve_uploaded_or_source_file as _shared_resolve_uploaded_or_source_file,
)
from .conversion_utils import (
    normalize_separator_option,
    require_existing_project_root,
)

logger = logging.getLogger(__name__)

_environment_job_store = ConversionJobStore(log_level_key="type")
_environment_jobs_lock = _environment_job_store.lock
_environment_jobs = _environment_job_store.jobs
_environment_detached_jobs_lock = threading.Lock()
_environment_detached_jobs: dict[str, dict[str, Any]] = {}


def _resolve_uploaded_or_source_file(*, field_names: tuple[str, ...]):
    return _shared_resolve_uploaded_or_source_file(
        field_names=field_names,
        missing_input_message="No file provided",
    )


def _form_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    return default


def _parse_detached_log_lines(
    log_path: Path, cursor: int
) -> tuple[list[dict[str, str]], int]:
    if not log_path.exists():
        return [], cursor

    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    bounded_cursor = max(0, min(cursor, len(lines)))
    new_lines = lines[bounded_cursor:]
    parsed: list[dict[str, str]] = []
    for line in new_lines:
        if "\t" in line:
            level, message = line.split("\t", 1)
            level_norm = level.strip().lower() or "info"
        else:
            level_norm = "info"
            message = line
        parsed.append({"type": level_norm, "message": message})

    return parsed, len(lines)


def _append_environment_job_log(job_id: str, message: str, level: str = "info") -> None:
    _environment_job_store.append_log(job_id, message, level)


def _is_environment_job_cancelled(job_id: str) -> bool:
    """Check if job has been marked for cancellation."""
    return _environment_job_store.is_cancelled(job_id)


def _mark_environment_job_cancelled(job_id: str) -> bool:
    """Mark job as cancelled. Returns True if job existed."""
    return _environment_job_store.cancel(job_id)


def _run_environment_detached_job(config_path: str) -> None:
    handle_run_environment_detached_job(
        config_path=config_path,
        perform_environment_conversion=_perform_environment_conversion,
        environment_conversion_cancelled_error_cls=EnvironmentConversionCancelledError,
        logger=logger,
    )


def _start_environment_detached_job(
    config: dict[str, Any],
) -> tuple[str, int, Path, Path]:
    return handle_start_environment_detached_job(
        config=config,
        environment_detached_jobs_lock=_environment_detached_jobs_lock,
        environment_detached_jobs=_environment_detached_jobs,
    )


def _run_environment_job(job_id: str, config: dict[str, Any]) -> None:
    handle_run_environment_job(
        job_id=job_id,
        config=config,
        is_environment_job_cancelled=_is_environment_job_cancelled,
        append_environment_job_log=_append_environment_job_log,
        environment_job_store=_environment_job_store,
        perform_environment_conversion=_perform_environment_conversion,
        environment_conversion_cancelled_error_cls=EnvironmentConversionCancelledError,
        logger=logger,
    )


def trigger_automatic_environment_enrichment(project_root: Path) -> str | None:
    """Auto-run environment enrichment from MRI acquisition metadata already in
    rawdata/, in a background thread. Returns the job id, or None if there was
    no MRI acquisition data to enrich.

    Reuses the same MRI-scan + conversion pipeline as the manual "Scan Project
    MRI Data" flow in the Environment converter tab, just without a user
    driving it through the UI.
    """
    df, _stats = build_mri_acquisition_table(resolve_bids_rawdata_root(project_root))
    if df.empty:
        return None

    tmp_dir = tempfile.mkdtemp(prefix="prism_env_auto_")
    input_path = Path(tmp_dir) / "mri_acquisitions.tsv"
    df.to_csv(input_path, sep="\t", index=False)

    config: dict[str, Any] = {
        "tmp_dir": tmp_dir,
        "input_path": input_path,
        "filename": input_path.name,
        "suffix": ".tsv",
        "separator_option": "auto",
        "timestamp_col": "timestamp",
        "participant_col": "participant_id",
        "participant_override": None,
        "session_col": "session_id",
        "session_override": None,
        "location_col": "location",
        "lat_col": None,
        "lon_col": None,
        "location_label_override": "",
        "lat_manual": None,
        "lon_manual": None,
        "project_path": str(project_root),
        "pilot_random_subject": False,
        "convert_in_background": False,
    }

    job_id = ""
    for _ in range(5):
        candidate = uuid.uuid4().hex
        try:
            _environment_job_store.create(candidate)
            job_id = candidate
            break
        except ValueError:
            continue
    if not job_id:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return None

    _append_environment_job_log(
        job_id, "🌍 Auto-enrichment: MRI acquisition data found, starting environment conversion", "info"
    )
    thread = threading.Thread(target=_run_environment_job, args=(job_id, config), daemon=True)
    thread.start()
    return job_id


def _build_environment_conversion_config_from_request() -> (
    tuple[dict[str, Any], tempfile.TemporaryDirectory | None]
):
    return handle_build_environment_conversion_config_from_request(
        resolve_uploaded_or_source_file=_resolve_uploaded_or_source_file,
        allowed_suffixes=ALLOWED_SUFFIXES,
        normalize_separator_option=normalize_separator_option,
        form_bool=_form_bool,
        coerce_coord=_coerce_coord,
        require_existing_project_root=require_existing_project_root,
    )


# ── API endpoints ──────────────────────────────────────────────────────────────


def api_environment_location_search():
    """Search known locations and return selectable coordinates."""
    query = (request.args.get("q") or "").strip()
    if len(query) < 2:
        return jsonify({"error": "Query too short"}), 400

    params = {
        "name": query,
        "count": 8,
        "language": "en",
        "format": "json",
    }

    try:
        response = requests.get(
            GEOCODING_URL,
            params=params,
            timeout=GEOCODING_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        raw_results = payload.get("results") or []
        results: list[dict[str, Any]] = []
        for item in raw_results:
            name = (item.get("name") or "").strip()
            admin1 = (item.get("admin1") or "").strip()
            country = (item.get("country") or "").strip()
            label_parts = [part for part in [name, admin1, country] if part]
            label = ", ".join(label_parts) if label_parts else name
            lat = item.get("latitude")
            lon = item.get("longitude")
            if lat is None or lon is None:
                continue
            results.append(
                {
                    "name": name,
                    "display_name": label,
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "timezone": item.get("timezone") or "",
                }
            )
        return jsonify({"results": results})
    except requests.RequestException as exc:
        return jsonify({"error": str(exc)}), 502


def api_environment_scan_mri_acquisition():
    """Scan the current project's rawdata for MRI acquisition timestamps and
    scanner-site location tags, returning a server-side TSV path that can be
    fed into the existing preview/convert flow like any uploaded survey file.
    """
    project_path = (
        request.form.get("project_path")
        or request.args.get("project_path")
        or session.get("current_project_path")
    )
    try:
        project_root = require_existing_project_root(
            project_path,
            missing_message="No active project selected. Open a project before scanning for MRI acquisition data.",
            missing_path_message="The selected project path no longer exists. Reopen the project and retry.",
        )
    except (ValueError, FileNotFoundError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    df, stats = build_mri_acquisition_table(resolve_bids_rawdata_root(project_root))
    if df.empty:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "No MRI acquisition timestamps found in this project's rawdata.",
                    "stats": stats,
                }
            ),
            400,
        )

    tmp_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".tsv", prefix="prism_env_mri_scan_", delete=False
    )
    tmp_file.close()
    output_path = Path(tmp_file.name)
    df.to_csv(output_path, sep="\t", index=False)

    return jsonify(
        {
            "success": True,
            "source_file_path": str(output_path),
            "row_count": int(len(df)),
            "stats": stats,
        }
    )


def api_environment_rescan_mri():
    """One-click re-scan: re-run MRI acquisition discovery + environment
    enrichment for the current project's rawdata in the background, without
    requiring the user to re-map columns or click through preview/convert.
    Returns a job id that can be polled with the existing
    /api/environment-convert-status/<job_id> endpoint.
    """
    project_path = (
        request.form.get("project_path")
        or request.args.get("project_path")
        or session.get("current_project_path")
    )
    try:
        project_root = require_existing_project_root(
            project_path,
            missing_message="No active project selected. Open a project before rescanning MRI data.",
            missing_path_message="The selected project path no longer exists. Reopen the project and retry.",
        )
    except (ValueError, FileNotFoundError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    job_id = trigger_automatic_environment_enrichment(project_root)
    if job_id is None:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "No MRI acquisition timestamps found in this project's rawdata.",
                }
            ),
            400,
        )

    return jsonify({"success": True, "job_id": job_id})


def api_environment_preview():
    return handle_api_environment_preview(
        resolve_uploaded_or_source_file=_resolve_uploaded_or_source_file,
        allowed_suffixes=ALLOWED_SUFFIXES,
        normalize_separator_option=normalize_separator_option,
    )


def api_environment_convert_start():
    return handle_api_environment_convert_start(
        build_environment_conversion_config_from_request=_build_environment_conversion_config_from_request,
        start_environment_detached_job=_start_environment_detached_job,
        logger=logger,
        environment_job_store=_environment_job_store,
        append_environment_job_log=_append_environment_job_log,
        run_environment_job=_run_environment_job,
    )


def api_environment_convert_cancel(job_id: str):
    return handle_api_environment_convert_cancel(
        job_id=job_id,
        mark_environment_job_cancelled=_mark_environment_job_cancelled,
        append_environment_job_log=_append_environment_job_log,
        environment_detached_jobs_lock=_environment_detached_jobs_lock,
        environment_detached_jobs=_environment_detached_jobs,
    )


def api_environment_convert_metrics():
    return handle_api_environment_convert_metrics(
        environment_job_store=_environment_job_store,
        environment_detached_jobs_lock=_environment_detached_jobs_lock,
        environment_detached_jobs=_environment_detached_jobs,
    )


def api_environment_convert_status(job_id: str):
    return handle_api_environment_convert_status(
        job_id=job_id,
        environment_job_store=_environment_job_store,
        environment_detached_jobs_lock=_environment_detached_jobs_lock,
        environment_detached_jobs=_environment_detached_jobs,
        parse_detached_log_lines=_parse_detached_log_lines,
    )
