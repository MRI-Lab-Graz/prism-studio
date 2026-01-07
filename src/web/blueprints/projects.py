"""
Flask blueprint for project management functionality.

Provides routes for:
- Creating new PRISM projects
- Validating existing project structures
- Applying fixes to repair issues
- Managing current working project
"""

import os
from pathlib import Path
from flask import Blueprint, render_template, jsonify, request, session

from src.project_manager import ProjectManager, get_available_modalities

projects_bp = Blueprint("projects", __name__)

# Shared project manager instance
_project_manager = ProjectManager()


def get_current_project() -> dict:
    """Get the current working project from session."""
    return {
        "path": session.get("current_project_path"),
        "name": session.get("current_project_name")
    }


def set_current_project(path: str, name: str = None):
    """Set the current working project in session."""
    session["current_project_path"] = path
    session["current_project_name"] = name or Path(path).name


@projects_bp.route("/projects")
def projects_page():
    """Render the Projects management page."""
    current = get_current_project()
    return render_template(
        "projects.html",
        modalities=get_available_modalities(),
        current_project=current
    )


@projects_bp.route("/api/projects/current", methods=["GET"])
def get_current():
    """Get the current working project."""
    return jsonify(get_current_project())


@projects_bp.route("/api/projects/current", methods=["POST"])
def set_current():
    """Set or clear the current working project."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    path = data.get("path")

    # Allow clearing the current project by passing null/empty path
    if not path:
        session.pop("current_project_path", None)
        session.pop("current_project_name", None)
        return jsonify({"success": True, "current": get_current_project()})

    name = data.get("name")

    if not os.path.exists(path):
        return jsonify({"success": False, "error": "Path does not exist"}), 400

    set_current_project(path, name)
    return jsonify({"success": True, "current": get_current_project()})


@projects_bp.route("/api/projects/create", methods=["POST"])
def create_project():
    """
    Create a new PRISM project.

    Expected JSON body:
    {
        "path": "/path/to/project",
        "name": "My Study",
        "sessions": 2,
        "modalities": ["survey", "biometrics"],
        "create_example": true
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"success": False, "error": "Path is required"}), 400

        # Build config from request
        config = {
            "name": data.get("name", Path(path).name),
            "sessions": data.get("sessions", 0),
            "modalities": data.get("modalities", ["survey", "biometrics"]),
            "create_example": data.get("create_example", True)
        }

        result = _project_manager.create_project(path, config)

        if result.get("success"):
            # Set as current working project
            set_current_project(path, config.get("name"))
            result["current_project"] = get_current_project()
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@projects_bp.route("/api/projects/validate", methods=["POST"])
def validate_project():
    """
    Validate an existing project structure.

    Expected JSON body:
    {
        "path": "/path/to/project"
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"success": False, "error": "Path is required"}), 400

        # Check if path exists
        if not os.path.exists(path):
            return jsonify({
                "success": False,
                "error": f"Path does not exist: {path}"
            }), 400

        result = _project_manager.validate_structure(path)
        result["success"] = True

        # Set as current working project
        set_current_project(path)
        result["current_project"] = get_current_project()

        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@projects_bp.route("/api/projects/fix", methods=["POST"])
def fix_project():
    """
    Apply fixes to a project.

    Expected JSON body:
    {
        "path": "/path/to/project",
        "fix_codes": ["PRISM001", "PRISM501"]  // optional, null = fix all
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"success": False, "error": "Path is required"}), 400

        fix_codes = data.get("fix_codes")  # None means fix all

        result = _project_manager.apply_fixes(path, fix_codes)
        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@projects_bp.route("/api/projects/fixable", methods=["POST"])
def get_fixable_issues():
    """
    Get list of fixable issues for a project.

    Expected JSON body:
    {
        "path": "/path/to/project"
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"success": False, "error": "Path is required"}), 400

        issues = _project_manager.get_fixable_issues(path)
        return jsonify({
            "success": True,
            "issues": issues
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@projects_bp.route("/api/projects/modalities", methods=["GET"])
def get_modalities():
    """Get list of available PRISM modalities."""
    return jsonify({
        "success": True,
        "modalities": get_available_modalities()
    })
