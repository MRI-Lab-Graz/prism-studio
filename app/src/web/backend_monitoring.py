"""Backend action monitoring helpers for PRISM Studio web requests."""

from __future__ import annotations

from pathlib import Path

from src.config import load_app_settings

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


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
    action = f"{method} {path} (endpoint={endpoint})"
    emit_backend_action(action, app_root=app_root)


def get_app_root_from_current_app(current_app_obj) -> str:
    """Resolve absolute app root path as string from current_app."""
    return str(Path(current_app_obj.root_path))
