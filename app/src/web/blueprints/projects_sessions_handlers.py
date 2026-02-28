import re
from datetime import date
from pathlib import Path

from flask import jsonify, request


def handle_get_sessions(get_current_project, read_project_json):
    """Read Sessions + TaskDefinitions from project.json."""
    current = get_current_project()
    if not current.get("path"):
        return jsonify({"success": False, "error": "No project selected"}), 400

    project_path = Path(current["path"])
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

    recruitment_error = validate_recruitment_payload(req.get("Recruitment"))
    if recruitment_error:
        return jsonify({"success": False, "error": recruitment_error}), 400

    project_path = Path(current["path"])
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
    current = get_current_project()
    if not current.get("path"):
        return jsonify({"sessions": []})

    project_path = Path(current["path"])
    data = read_project_json(project_path)
    sessions = data.get("Sessions", [])

    return jsonify(
        {
            "sessions": [
                {"id": s.get("id", ""), "label": s.get("label", s.get("id", ""))}
                for s in sessions
            ]
        }
    )


def handle_register_session(get_current_project, read_project_json, write_project_json):
    """Register a conversion result into a session in project.json."""
    current = get_current_project()
    if not current.get("path"):
        return jsonify({"success": False, "error": "No project selected"}), 400

    req = request.get_json()
    if not req:
        return jsonify({"success": False, "error": "No data provided"}), 400

    session_id = (req.get("session_id") or "").strip()
    tasks = req.get("tasks", [])
    modality = req.get("modality", "survey")
    source_file = req.get("source_file", "")
    converter = req.get("converter", "manual")

    if not session_id:
        return jsonify({"success": False, "error": "session_id is required"}), 400

    if not session_id.startswith("ses-"):
        session_id = f"ses-{session_id}"
    num_part = session_id[4:]
    try:
        n = int(num_part)
        session_id = f"ses-{n:02d}"
    except ValueError:
        pass

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

    project_path = Path(current["path"])
    data = read_project_json(project_path)
    if not data:
        return jsonify({"success": False, "error": "project.json not found"}), 404

    if "Sessions" not in data:
        data["Sessions"] = []
    if "TaskDefinitions" not in data:
        data["TaskDefinitions"] = {}

    target_session = None
    for session_obj in data["Sessions"]:
        if session_obj.get("id") == session_id:
            target_session = session_obj
            break

    if target_session is None:
        target_session = {
            "id": session_id,
            "label": session_id,
            "tasks": [],
        }
        data["Sessions"].append(target_session)

    if "tasks" not in target_session:
        target_session["tasks"] = []

    today_iso = date.today().isoformat()
    source_obj = {
        "file": source_file,
        "converter": converter,
        "convertedAt": today_iso,
    }

    registered_tasks = []
    for task_name in tasks:
        existing = None
        for task_obj in target_session["tasks"]:
            if task_obj.get("task") == task_name:
                existing = task_obj
                break

        if existing:
            existing["source"] = source_obj
        else:
            target_session["tasks"].append(
                {
                    "task": task_name,
                    "source": source_obj,
                }
            )

        registered_tasks.append(task_name)

        if task_name not in data["TaskDefinitions"]:
            data["TaskDefinitions"][task_name] = {"modality": modality}

    write_project_json(project_path, data)

    return jsonify(
        {
            "success": True,
            "message": f"Registered {len(registered_tasks)} task(s) in {session_id}",
            "session_id": session_id,
            "registered_tasks": registered_tasks,
        }
    )