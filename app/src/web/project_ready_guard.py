"""Block tool requests while the open project is missing required fields."""

from __future__ import annotations

from flask import Flask, jsonify, request, session

from src.project_ready import ProjectNotReadyError, missing_required_fields, not_ready_message

_EXEMPT_PREFIXES = (
    "/static/", "/projects", "/api/projects", "/api/settings", "/api/fs",
    "/api/v1/", "/editor", "/api/template-editor/", "/api/session-map",
    "/api/survey-customizer/",
    "/api/spec/",  # a project's own specification is configuration, like the templates
    "/api/environment",  # like the CLI: environment commands stay open
)
_EXEMPT_PATHS = {
    "/favicon.ico", "/health", "/shutdown", "/specifications",
    "/api/runtime-capabilities", "/api/list-library-files",
    "/api/config", "/api/filesystem-context",
    # the survey generator does not work on the open project
    "/api/generate-lss", "/api/generate-boilerplate", "/api/generate-pavlovia",
    "/api/list-library-files-merged",
}
# Inside the open /api/projects area, what exports, publishes or writes project data is a tool:
# gated exactly like its CLI twin. Opening, creating, inspecting and fixing the project, job
# status/cancel routes, diagnostics and saving stay open.
_GATED_PROJECT_PATHS = {"/api/projects/export"}
_GATED_PROJECT_PREFIXES = (
    "/api/projects/anc-export", "/api/projects/openminds-export", "/api/projects/template-export",
    "/api/projects/export/start", "/api/projects/export/deface", "/api/projects/export/git-lfs",
    "/api/projects/datalad-server/publish", "/api/projects/datalad-server/sync/start",
    "/api/projects/datalad-server/finalize/start", "/api/projects/datalad/remove-scans-tsv",
)


def is_gate_exempt(path: str, method: str) -> bool:
    if path in _GATED_PROJECT_PATHS or path.startswith(_GATED_PROJECT_PREFIXES):
        return False
    if path == "/api/projects/participants" and method not in ("GET", "HEAD"):
        return False  # saving the participants schema is the CLI's `participants save-schema`
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
            return jsonify({"success": False, "error": str(exc), "code": "project_not_ready", "missing": []}), 409
        if missing:
            return (
                jsonify({"success": False, "error": not_ready_message(missing), "code": "project_not_ready", "missing": missing}),
                409,
            )
        return None
