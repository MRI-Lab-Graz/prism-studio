"""Block tool requests while the open project is missing required fields."""

from __future__ import annotations

from flask import Flask, jsonify, request, session

from src.project_ready import ProjectNotReadyError, missing_required_fields, not_ready_message

_EXEMPT_PREFIXES = (
    "/static/", "/projects", "/api/projects", "/api/settings", "/api/fs",
    "/api/v1/", "/editor", "/api/template-editor/", "/api/session-map",
    "/api/survey-customizer/",
)
_EXEMPT_PATHS = {
    "/favicon.ico", "/health", "/shutdown", "/specifications", "/api/browse-folder",
    "/api/browse-file", "/api/runtime-capabilities", "/api/list-library-files",
    "/api/config", "/api/filesystem-context",
}


def is_gate_exempt(path: str, method: str) -> bool:
    if path in _EXEMPT_PATHS or path.startswith(_EXEMPT_PREFIXES):
        return True
    # Page views stay open so the user can read why tools are blocked.
    return method in ("GET", "HEAD") and not path.startswith("/api/")


def install_project_ready_guard(app: Flask) -> None:
    @app.before_request
    def _require_project_ready():
        project = session.get("current_project_path")
        if not project or is_gate_exempt(request.path, request.method):
            return None
        try:
            missing = missing_required_fields(project)
        except ProjectNotReadyError as exc:
            return jsonify({"error": str(exc), "code": "project_not_ready", "missing": []}), 409
        if missing:
            return (
                jsonify({"error": not_ready_message(missing), "code": "project_not_ready", "missing": missing}),
                409,
            )
        return None
