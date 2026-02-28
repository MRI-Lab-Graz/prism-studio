import os
from pathlib import Path

from flask import jsonify, request, session

from .projects_helpers import _load_recent_projects, _save_recent_projects
from .projects_citation_helpers import _validate_recruitment_payload


def handle_set_current(get_current_project, set_current_project, save_last_project):
    """Set or clear current project in session and persisted settings."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    path = data.get("path")

    if not path:
        session.pop("current_project_path", None)
        session.pop("current_project_name", None)
        save_last_project(None, None)
        return jsonify({"success": True, "current": get_current_project()})

    name = data.get("name")

    if not os.path.exists(path):
        return jsonify({"success": False, "error": "Path does not exist"}), 400

    set_current_project(path, name)
    save_last_project(path, name or Path(path).name)

    return jsonify({"success": True, "current": get_current_project()})


def handle_create_project(project_manager, set_current_project, save_last_project):
    """Create a new PRISM project and set it as current."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"success": False, "error": "Path is required"}), 400

        recruitment_error = _validate_recruitment_payload(data.get("Recruitment"))
        if recruitment_error:
            return jsonify({"success": False, "error": recruitment_error}), 400

        config = {
            "name": data.get("name", Path(path).name),
            "authors": data.get("authors"),
            "license": data.get("license"),
            "doi": data.get("doi"),
            "keywords": data.get("keywords"),
            "acknowledgements": data.get("acknowledgements"),
            "ethics_approvals": data.get("ethics_approvals"),
            "how_to_acknowledge": data.get("how_to_acknowledge"),
            "funding": data.get("funding"),
            "references_and_links": data.get("references_and_links"),
            "hed_version": data.get("hed_version"),
            "dataset_type": data.get("dataset_type"),
            "description": data.get("description"),
            "Basics": data.get("Basics"),
            "Overview": data.get("Overview"),
            "StudyDesign": data.get("StudyDesign"),
            "Recruitment": data.get("Recruitment"),
            "Eligibility": data.get("Eligibility"),
            "DataCollection": data.get("DataCollection"),
            "Procedure": data.get("Procedure"),
            "MissingData": data.get("MissingData"),
            "References": data.get("References"),
            "Conditions": data.get("Conditions"),
        }

        result = project_manager.create_project(path, config)

        if result.get("success"):
            project_name = config.get("name") or Path(path).name
            set_current_project(path, project_name)
            save_last_project(path, project_name)
            project_json_path = str(Path(path) / "project.json")
            result["current_project"] = {
                "path": project_json_path,
                "name": project_name,
            }
            return jsonify(result)

        return jsonify(result), 400
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500


def handle_validate_project(project_manager, set_current_project, save_last_project):
    """Validate existing project.json and set project as current when valid."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"success": False, "error": "Path is required"}), 400

        path_obj = Path(path)
        if not (path_obj.is_file() and path_obj.name == "project.json"):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Invalid selection. You must select the 'project.json' file directly. Folder loading is no longer supported.",
                    }
                ),
                400,
            )

        project_json_path = path
        root_path_obj = path_obj.parent
        root_path = str(root_path_obj)

        if not os.path.exists(root_path):
            return (
                jsonify(
                    {"success": False, "error": f"Path does not exist: {root_path}"}
                ),
                400,
            )

        result = project_manager.validate_structure(root_path)
        result["success"] = True

        project_name = session.get("current_project_name") or root_path_obj.name
        set_current_project(root_path, project_name)
        save_last_project(root_path, project_name)

        result["current_project"] = {"path": project_json_path, "name": project_name}

        return jsonify(result)
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500


def handle_project_path_status():
    """Return lightweight availability info for a project.json path."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        if not isinstance(path, str) or not path.strip():
            return jsonify({"success": False, "error": "Path is required"}), 400

        path_obj = Path(path)
        exists = path_obj.exists()
        is_file = path_obj.is_file()
        is_project_json = is_file and path_obj.name == "project.json"

        return jsonify(
            {
                "success": True,
                "exists": exists,
                "is_file": is_file,
                "is_project_json": is_project_json,
                "available": bool(exists and is_project_json),
            }
        )
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500


def handle_get_recent_projects():
    """Get recent projects from user-scoped settings storage."""
    try:
        projects = _load_recent_projects()
        return jsonify({"success": True, "projects": projects})
    except Exception as error:
        return jsonify({"success": False, "error": str(error), "projects": []}), 500


def handle_set_recent_projects():
    """Replace recent projects list in user-scoped settings storage."""
    data = request.get_json(silent=True) or {}
    projects = data.get("projects")
    if not isinstance(projects, list):
        return jsonify({"success": False, "error": "projects must be a list"}), 400

    try:
        saved = _save_recent_projects(projects)
        return jsonify({"success": True, "projects": saved})
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500


def handle_fix_project(project_manager):
    """Apply fix operations to a project."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"success": False, "error": "Path is required"}), 400

        fix_codes = data.get("fix_codes")
        result = project_manager.apply_fixes(path, fix_codes)
        return jsonify(result)
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500


def handle_get_fixable_issues(project_manager):
    """List fixable issues for the given project path."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"success": False, "error": "Path is required"}), 400

        issues = project_manager.get_fixable_issues(path)
        return jsonify({"success": True, "issues": issues})
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500