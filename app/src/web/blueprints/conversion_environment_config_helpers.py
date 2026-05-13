from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from flask import request, session
from werkzeug.utils import secure_filename


def handle_build_environment_conversion_config_from_request(
    *,
    resolve_uploaded_or_source_file,
    allowed_suffixes,
    normalize_separator_option,
    form_bool,
    coerce_coord,
    require_existing_project_root,
) -> tuple[dict[str, Any], tempfile.TemporaryDirectory | None]:
    uploaded, upload_error = resolve_uploaded_or_source_file(field_names=("file",))
    if uploaded is None or not getattr(uploaded, "filename", ""):
        raise ValueError(upload_error or "No file provided")

    filename = secure_filename(uploaded.filename or "")
    suffix = Path(filename).suffix.lower()
    if suffix not in allowed_suffixes:
        raise ValueError(f"Unsupported file type '{suffix}'")

    separator_option = normalize_separator_option(request.form.get("separator"))

    timestamp_col = (request.form.get("timestamp_col") or "").strip() or None
    participant_col = (request.form.get("participant_col") or "").strip() or None
    participant_override = (
        request.form.get("participant_override") or ""
    ).strip() or None
    session_col = (request.form.get("session_col") or "").strip() or None
    location_col = (request.form.get("location_col") or "").strip() or None
    lat_col = (request.form.get("lat_col") or "").strip() or None
    lon_col = (request.form.get("lon_col") or "").strip() or None
    session_override = (request.form.get("session_override") or "").strip() or None
    location_label_override = (request.form.get("location_label") or "").strip()
    pilot_random_subject = form_bool(
        request.form.get("pilot_random_subject"), default=False
    )
    convert_in_background = form_bool(
        request.form.get("convert_in_background"), default=False
    )

    if not timestamp_col:
        raise ValueError("Timestamp column is required")
    if not participant_col:
        raise ValueError("Participant ID column is required")
    if not session_col and not session_override:
        raise ValueError("Session is required: choose a column or set manual session")

    lat_manual_text = (request.form.get("lat") or "").strip()
    lon_manual_text = (request.form.get("lon") or "").strip()
    has_global_lat = bool(lat_manual_text)
    has_global_lon = bool(lon_manual_text)
    if has_global_lat != has_global_lon:
        raise ValueError(
            "Provide both global latitude and longitude, or leave both empty."
        )

    lat_manual = coerce_coord(lat_manual_text, lat=True) if has_global_lat else None
    lon_manual = coerce_coord(lon_manual_text, lat=False) if has_global_lon else None
    if has_global_lat and (lat_manual is None or lon_manual is None):
        raise ValueError("Global latitude/longitude values are invalid.")

    project_root = require_existing_project_root(
        session.get("current_project_path"),
        missing_message="No active project selected. Open a project before converting.",
        missing_path_message="The selected project path no longer exists. Reopen the project and retry environment conversion.",
    )

    tmp_dir = tempfile.mkdtemp(prefix="prism_env_convert_")
    input_path = Path(tmp_dir) / filename
    uploaded.save(str(input_path))

    config = {
        "tmp_dir": tmp_dir,
        "input_path": input_path,
        "filename": filename,
        "suffix": suffix,
        "separator_option": separator_option,
        "timestamp_col": timestamp_col,
        "participant_col": participant_col,
        "participant_override": participant_override,
        "session_col": session_col,
        "session_override": session_override,
        "location_col": location_col,
        "lat_col": lat_col,
        "lon_col": lon_col,
        "location_label_override": location_label_override,
        "lat_manual": lat_manual,
        "lon_manual": lon_manual,
        "project_path": str(project_root),
        "pilot_random_subject": pilot_random_subject,
        "convert_in_background": convert_in_background,
    }
    return config, None