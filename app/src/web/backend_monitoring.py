"""Backend action monitoring helpers for PRISM Studio web requests."""

from __future__ import annotations

import shlex
from pathlib import Path

from flask import session

from src.config import load_app_settings

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
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


def _build_terminal_command(req) -> str:
    """Return an exact terminal command preview for supported actions."""
    endpoint = req.endpoint or ""
    if endpoint == "validation.validate_folder":
        return _build_validate_folder_terminal_command(req)
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
