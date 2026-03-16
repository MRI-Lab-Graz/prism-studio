from flask import jsonify, request

from src.web.services import file_picker


def handle_api_browse_file():
    """Open a system dialog to select a file (filtering for project.json)."""
    project_json_only = (request.args.get("project_json_only") or "1").strip() != "0"
    outcome = file_picker.pick_file(project_json_only=project_json_only)
    if outcome.error is not None:
        return jsonify({"error": outcome.error}), outcome.status_code
    return jsonify({"path": outcome.path})


def handle_api_browse_folder():
    """Open a system dialog to select a folder."""
    outcome = file_picker.pick_folder()
    if outcome.error is not None:
        return jsonify({"error": outcome.error}), outcome.status_code
    return jsonify({"path": outcome.path})
