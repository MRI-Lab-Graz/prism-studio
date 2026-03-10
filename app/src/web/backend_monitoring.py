"""Backend action monitoring helpers for PRISM Studio web requests."""

from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path

from flask import session

from src.config import load_app_settings

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_ANSI_GREEN = "\033[32m"
_ANSI_RESET = "\033[0m"
_SUPPRESSED_ENDPOINTS = {
    # Frequent UI probe used for recent-project availability checks.
    "projects.project_path_status",
    # Frequent sync from localStorage cache updates; low diagnostic value.
    "projects.set_recent_projects",
    # Draft validation can fire repeatedly while editing forms.
    "projects.validate_dataset_description_draft",
}
_ENDPOINT_LABELS = {
    "projects.project_path_status": "check project path availability",
    "projects.create_project": "create project",
    "projects.open_project": "open project",
    "projects.validate_project": "validate project",
    "projects.fix_project": "apply project fixes",
    "projects_library.set_backend_monitoring_setting": "update backend monitoring setting",
    "projects_library.set_global_library_settings": "save global library settings",
}


def _compact_path(path_value: str | None) -> str:
    """Return a short, human-friendly path preview for terminal logs."""
    path_text = str(path_value or "").strip()
    if not path_text:
        return ""

    normalized = path_text.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    if len(parts) <= 3:
        return normalized
    return f".../{'/'.join(parts[-3:])}"


def _summarize_payload(req) -> str:
    """Extract small, useful request details without dumping full payloads."""
    try:
        payload = req.get_json(silent=True) or {}
    except Exception:
        payload = {}

    if not isinstance(payload, dict):
        payload = {}

    details: list[str] = []

    for key in ("path", "project_path", "dataset_path", "existing_path"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            details.append(f"{key}={_compact_path(value)}")

    for key in ("name", "project_name", "modality", "survey", "format", "layout"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            details.append(f"{key}={value.strip()}")

    if "backend_monitoring" in payload:
        details.append(f"backend_monitoring={bool(payload.get('backend_monitoring'))}")

    # Add a concise key count if no common fields are present.
    if not details and payload:
        keys = sorted(str(key) for key in payload.keys())
        preview = ", ".join(keys[:4])
        if len(keys) > 4:
            preview += ", ..."
        details.append(f"json_keys=[{preview}]")

    return ", ".join(details)


def _truthy_form_value(value: str | None) -> bool:
    """Interpret common form truthy values used by the frontend."""
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _supports_ansi_color() -> bool:
    """Return True when ANSI coloring is likely supported by current terminal."""
    if os.environ.get("NO_COLOR") is not None:
        return False

    if not getattr(sys.stdout, "isatty", lambda: False)():
        return False

    if os.name != "nt":
        return True

    # Common Windows terminals with ANSI support.
    if os.environ.get("WT_SESSION"):
        return True
    if os.environ.get("ANSICON"):
        return True
    if str(os.environ.get("ConEmuANSI", "")).upper() == "ON":
        return True

    term = str(os.environ.get("TERM", "")).lower()
    return "xterm" in term or "ansi" in term


def _resolve_survey_output_dir(req) -> str:
    """Resolve an output directory for survey CLI command previews."""
    form = req.form

    explicit_output = str(form.get("output", "") or form.get("output_root", "")).strip()
    if explicit_output:
        return explicit_output

    current_project_path = str(session.get("current_project_path", "")).strip()
    if current_project_path:
        return current_project_path

    return "<output-dir>"


def _build_validate_folder_terminal_command(req) -> str:
    """Build the exact validator CLI equivalent for /validate_folder requests."""
    form = req.form
    folder_path = str(form.get("folder_path", "")).strip()
    if not folder_path:
        folder_path = str(session.get("current_project_path", "")).strip()
    if not folder_path:
        return ""

    # Mirror prism.py CLI invocation so users can copy-paste from logs.
    cmd_parts: list[str] = ["python", "prism.py", folder_path]

    schema_version = str(form.get("schema_version", "")).strip()
    if schema_version and schema_version != "stable":
        cmd_parts.extend(["--schema-version", schema_version])

    validation_mode = str(form.get("validation_mode", "both")).strip().lower()
    if validation_mode in {"both", "bids"}:
        cmd_parts.append("--bids")
    if validation_mode == "bids":
        cmd_parts.append("--no-prism")

    if _truthy_form_value(form.get("bids_warnings")):
        cmd_parts.append("--bids-warnings")

    library_path = str(form.get("library_path", "")).strip()
    if library_path:
        cmd_parts.extend(["--library", library_path])

    return " ".join(shlex.quote(part) for part in cmd_parts)


def _build_survey_convert_terminal_command(req, *, dry_run: bool = False) -> str:
    """Build CLI-equivalent survey convert command for survey conversion endpoints."""
    form = req.form
    files = req.files

    uploaded = files.get("excel") or files.get("file")
    filename = ""
    if uploaded is not None:
        filename = str(getattr(uploaded, "filename", "") or "").strip()
    if not filename:
        filename = "<input-file>"

    output_dir = _resolve_survey_output_dir(req)

    cmd_parts: list[str] = [
        "python",
        "prism_tools.py",
        "survey",
        "convert",
        "--input",
        filename,
        "--output",
        output_dir,
    ]

    survey = str(form.get("survey", "")).strip()
    if survey:
        cmd_parts.extend(["--survey", survey])

    id_column = str(form.get("id_column", "")).strip()
    if id_column:
        cmd_parts.extend(["--id-column", id_column])

    session_column = str(form.get("session_column", "")).strip()
    if session_column:
        cmd_parts.extend(["--session-column", session_column])

    sheet = str(form.get("sheet", "")).strip()
    if sheet:
        cmd_parts.extend(["--sheet", sheet])

    unknown = str(form.get("unknown", "")).strip().lower()
    if unknown and unknown != "warn":
        cmd_parts.extend(["--unknown", unknown])

    language = str(form.get("language", "")).strip()
    if language:
        cmd_parts.extend(["--lang", language])

    if dry_run:
        cmd_parts.append("--dry-run")

    cmd_parts.append("--force")
    return " ".join(shlex.quote(part) for part in cmd_parts)


def _build_detect_columns_terminal_command(req) -> str:
    """Build CLI-equivalent command preview for detect-columns uploads."""
    files = req.files
    uploaded = files.get("file")
    filename = ""
    if uploaded is not None:
        filename = str(getattr(uploaded, "filename", "") or "").strip()
    if not filename:
        filename = "<input-file>"

    output_dir = _resolve_survey_output_dir(req)

    # Closest equivalent: run survey conversion as dry-run to trigger
    # parser loading and ID/session auto-detection without writing files.
    cmd_parts: list[str] = [
        "python",
        "prism_tools.py",
        "survey",
        "convert",
        "--input",
        filename,
        "--output",
        output_dir,
        "--dry-run",
        "--force",
    ]
    return " ".join(shlex.quote(part) for part in cmd_parts)


def _build_survey_check_templates_terminal_command(req) -> str:
    """Build command preview for survey template pre-check endpoint."""
    form = req.form
    files = req.files

    uploaded = files.get("excel") or files.get("file")
    filename = ""
    if uploaded is not None:
        filename = str(getattr(uploaded, "filename", "") or "").strip()
    if not filename:
        filename = "<input-file>"

    output_dir = _resolve_survey_output_dir(req)

    cmd_parts: list[str] = [
        "python",
        "prism_tools.py",
        "survey",
        "convert",
        "--input",
        filename,
        "--output",
        output_dir,
        "--dry-run",
        "--force",
    ]

    id_column = str(form.get("id_column", "")).strip()
    if id_column:
        cmd_parts.extend(["--id-column", id_column])

    session_column = str(form.get("session_column", "")).strip()
    if session_column:
        cmd_parts.extend(["--session-column", session_column])

    sheet = str(form.get("sheet", "")).strip()
    if sheet:
        cmd_parts.extend(["--sheet", sheet])

    return " ".join(shlex.quote(part) for part in cmd_parts)


def _build_terminal_command(req) -> str:
    """Return an exact terminal command preview for supported actions."""
    endpoint = req.endpoint or ""
    if endpoint == "validation.validate_folder":
        return _build_validate_folder_terminal_command(req)
    if endpoint == "conversion_survey.api_survey_convert":
        return _build_survey_convert_terminal_command(req, dry_run=False)
    if endpoint in {
        "conversion_survey.api_survey_convert_preview",
        "conversion_survey.api_survey_convert_validate",
    }:
        return _build_survey_convert_terminal_command(req, dry_run=True)
    if endpoint == "conversion_survey.api_survey_check_project_templates":
        return _build_survey_check_templates_terminal_command(req)
    if endpoint == "tools.detect_columns":
        return _build_detect_columns_terminal_command(req)
    return ""


def is_backend_monitoring_enabled(app_root: str) -> bool:
    """Return whether backend monitoring is enabled in app settings."""
    settings = load_app_settings(app_root=app_root)
    return bool(settings.backend_monitoring)


def emit_backend_action(message: str, app_root: str) -> None:
    """Print a backend action line to terminal when monitoring is enabled."""
    if not is_backend_monitoring_enabled(app_root):
        return

    text = str(message or "").strip()
    if not text:
        return

    cmd_idx = text.find("cmd=")
    if cmd_idx >= 0 and _supports_ansi_color():
        head = text[:cmd_idx]
        command_segment = text[cmd_idx:]
        text = f"{head}{_ANSI_GREEN}{command_segment}{_ANSI_RESET}"

    print(f"\n[BACKEND-ACTION] {text}\n")


def emit_backend_request_action(req, app_root: str) -> None:
    """Print backend action line for mutating HTTP requests when enabled."""
    method = (req.method or "").upper()
    if method not in _MUTATING_METHODS:
        return

    path = req.path or "/"
    endpoint = req.endpoint or "unknown"
    if endpoint in _SUPPRESSED_ENDPOINTS:
        return

    label = _ENDPOINT_LABELS.get(endpoint, endpoint.replace("_", " "))
    payload_summary = _summarize_payload(req)

    action = f"{method} {path} -> {label} (endpoint={endpoint})"
    if payload_summary:
        action = f"{action} | {payload_summary}"

    terminal_command = _build_terminal_command(req)
    if terminal_command:
        action = f"{action} | cmd={terminal_command}"

    emit_backend_action(action, app_root=app_root)


def get_app_root_from_current_app(current_app_obj) -> str:
    """Resolve absolute app root path as string from current_app."""
    return str(Path(current_app_obj.root_path))
