import re
from datetime import date
from pathlib import Path

from flask import jsonify, request

from src.project_structure import get_project_modalities_and_sessions
from src.web.services.project_registration import _normalize_session_id

from .projects_helpers import (
    _resolve_project_root_path,
    _resolve_requested_or_current_project_root,
)


def handle_get_sessions(get_current_project, read_project_json):
    """Read Sessions + TaskDefinitions from project.json."""
    project_path, error_message, status_code = (
        _resolve_requested_or_current_project_root(
            get_current_project,
            request.args.get("project_path"),
        )
    )
    if project_path is None:
        return jsonify({"success": False, "error": error_message}), status_code

    data = read_project_json(project_path)
    if not data:
        return jsonify({"success": False, "error": "project.json not found"}), 404

    return jsonify(
        {
            "success": True,
            "sessions": data.get("Sessions", []),
            "task_definitions": data.get("TaskDefinitions", {}),
        }
    )


def handle_save_sessions(
    get_current_project,
    read_project_json,
    write_project_json,
    validate_recruitment_payload,
):
    """Write Sessions + TaskDefinitions to project.json."""
    current = get_current_project()
    if not current.get("path"):
        return jsonify({"success": False, "error": "No project selected"}), 400

    req = request.get_json()
    if not req:
        return jsonify({"success": False, "error": "No data provided"}), 400

    project_path, error_message, status_code = (
        _resolve_requested_or_current_project_root(
            get_current_project,
            req.get("project_path"),
        )
    )
    if project_path is None:
        return jsonify({"success": False, "error": error_message}), status_code

    recruitment_error = validate_recruitment_payload(req.get("Recruitment"))
    if recruitment_error:
        return jsonify({"success": False, "error": recruitment_error}), 400

    data = read_project_json(project_path)
    if not data:
        return jsonify({"success": False, "error": "project.json not found"}), 404

    if "sessions" in req:
        data["Sessions"] = req["sessions"]
    if "task_definitions" in req:
        data["TaskDefinitions"] = req["task_definitions"]

    write_project_json(project_path, data)
    return jsonify({"success": True, "message": "Sessions saved"})


def handle_get_sessions_declared(get_current_project, read_project_json):
    """Lightweight list of [{id, label}] for converter session picker."""
    explicit_project_path = str(request.args.get("project_path") or "").strip()
    if explicit_project_path:
        project_path = _resolve_project_root_path(explicit_project_path)
        if project_path is None:
            return jsonify({"error": "Invalid project path"}), 400
    else:
        current = get_current_project()
        current_project_path = str((current or {}).get("path") or "").strip()
        if not current_project_path:
            return jsonify({"sessions": []})

        project_path = _resolve_project_root_path(current_project_path)
        if project_path is None:
            return jsonify({"sessions": []})

    data = read_project_json(project_path)
    declared_sessions = data.get("Sessions", []) if isinstance(data, dict) else []

    session_map: dict[str, str] = {}
    for session in declared_sessions:
        session_id = str(session.get("id") or "").strip()
        if not session_id:
            continue
        session_map[session_id] = str(session.get("label") or session_id).strip() or session_id

    try:
        structure = get_project_modalities_and_sessions(project_path)
    except Exception:
        structure = {"sessions": []}

    for session_id in structure.get("sessions", []) or []:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            continue
        session_map.setdefault(normalized_session_id, normalized_session_id)

    return jsonify(
        {
            "sessions": [
                {"id": session_id, "label": label}
                for session_id, label in sorted(session_map.items())
            ]
        }
    )


def handle_register_session(get_current_project, read_project_json, write_project_json):
    """Validate converter session metadata without persisting it to project.json."""
    req = request.get_json()
    if not req:
        return jsonify({"success": False, "error": "No data provided"}), 400

    project_path, error_message, status_code = (
        _resolve_requested_or_current_project_root(
            get_current_project,
            req.get("project_path"),
        )
    )
    if project_path is None:
        return jsonify({"success": False, "error": error_message}), status_code

    session_id = (req.get("session_id") or "").strip()
    tasks = req.get("tasks", [])
    modality = req.get("modality", "survey")
    source_file = req.get("source_file", "")
    converter = req.get("converter", "manual")

    if not session_id:
        return jsonify({"success": False, "error": "session_id is required"}), 400

    session_id = _normalize_session_id(session_id) or ""

    if not re.match(r"^ses-[a-zA-Z0-9]+$", session_id):
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Invalid session ID format: {session_id}",
                }
            ),
            400,
        )

    data = read_project_json(project_path)
    if not data:
        return jsonify({"success": False, "error": "project.json not found"}), 404

    registered_tasks = []
    for task_name in tasks:
        task_value = str(task_name or "").strip()
        if task_value:
            registered_tasks.append(task_value)

    return jsonify(
        {
            "success": True,
            "message": f"Accepted {len(registered_tasks)} task(s) for {session_id}",
            "session_id": session_id,
            "registered_tasks": registered_tasks,
        }
    )
