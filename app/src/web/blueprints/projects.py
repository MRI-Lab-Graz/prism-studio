"""
Flask blueprint for project management functionality.

Provides routes for:
- Creating new PRISM projects
- Validating existing project structures
- Applying fixes to repair issues
- Managing current working project
"""

import json
import os
import re
from datetime import date
from pathlib import Path
from flask import Blueprint, render_template, jsonify, request, session

from src.project_manager import ProjectManager, get_available_modalities
from src.readme_generator import ReadmeGenerator

projects_bp = Blueprint("projects", __name__)

# Shared project manager instance
_project_manager = ProjectManager()


def get_current_project() -> dict:
    """Get the current working project from session."""
    return {
        "path": session.get("current_project_path"),
        "name": session.get("current_project_name"),
    }


def set_current_project(path: str, name: str = None):
    """Set the current working project in session."""
    session["current_project_path"] = path
    session["current_project_name"] = name or Path(path).name


def get_bids_file_path(project_path: Path, filename: str) -> Path:
    """Get path to a BIDS metadata file, checking both root and rawdata/ folder.
    
    BIDS standard says participants.tsv, participants.json, and dataset_description.json
    belong in the dataset ROOT. However, some DataLad-style projects use rawdata/ subfolder.
    This function checks both locations and returns the correct path.
    
    Args:
        project_path: Path to the project root
        filename: Name of the file (e.g., 'participants.json', 'dataset_description.json')
    
    Returns:
        Path to the file (in root if exists, otherwise rawdata/, even if neither exists)
    """
    # Check root first (standard BIDS)
    root_path = project_path / filename
    if root_path.exists():
        return root_path
    
    # Check rawdata/ folder (DataLad-style)
    rawdata_path = project_path / "rawdata" / filename
    if rawdata_path.exists():
        return rawdata_path
    
    # If neither exists, prefer root (standard BIDS for new files)
    return root_path


@projects_bp.route("/projects")
def projects_page():
    """Render the Projects management page."""
    current = get_current_project()
    return render_template(
        "projects.html", modalities=get_available_modalities(), current_project=current
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
        # Also clear from settings
        _save_last_project(None, None)
        return jsonify({"success": True, "current": get_current_project()})

    name = data.get("name")

    if not os.path.exists(path):
        return jsonify({"success": False, "error": "Path does not exist"}), 400

    set_current_project(path, name)

    # Save to settings for persistence across restarts
    _save_last_project(path, name or Path(path).name)

    return jsonify({"success": True, "current": get_current_project()})


def _save_last_project(path: str | None, name: str | None):
    """Save the last project to app settings for persistence."""
    try:
        from flask import current_app
        from src.config import load_app_settings, save_app_settings

        # Determine app root
        app_root = current_app.config.get("BASE_DIR")
        if not app_root:
            app_root = Path(__file__).parent.parent.parent.parent

        settings = load_app_settings(app_root=str(app_root))
        settings.last_project_path = path
        settings.last_project_name = name
        save_app_settings(settings, app_root=str(app_root))

        # Also update the app config so it's immediately available
        current_app.config["LAST_PROJECT_PATH"] = path
        current_app.config["LAST_PROJECT_NAME"] = name
    except Exception as e:
        print(f"[WARN] Could not save last project to settings: {e}")


@projects_bp.route("/api/projects/create", methods=["POST"])
def create_project():
    """
    Create a new PRISM project (YODA layout).

    Expected JSON body:
    {
        "path": "/path/to/project",
        "name": "My Study"
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
            # Optional BIDS metadata
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
        }

        result = _project_manager.create_project(path, config)

        if result.get("success"):
            # Set as current working project (folder path for internal logic)
            project_name = config.get("name") or Path(path).name
            set_current_project(path, project_name)

            # Persist to settings file for restoration after app restart
            _save_last_project(path, project_name)

            # Return the project.json path for the UI to use as handle
            project_json_path = str(Path(path) / "project.json")
            result["current_project"] = {
                "path": project_json_path,
                "name": project_name,
            }
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
        "path": "/path/to/project"  // or /path/to/project.json
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"success": False, "error": "Path is required"}), 400

        # Enforce project.json as the only valid entry point
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
        # Use the parent directory as the project root for validation
        root_path_obj = path_obj.parent
        root_path = str(root_path_obj)

        # Check if path exists
        if not os.path.exists(root_path):
            return (
                jsonify(
                    {"success": False, "error": f"Path does not exist: {root_path}"}
                ),
                400,
            )

        result = _project_manager.validate_structure(root_path)
        result["success"] = True

        # Set as current working project - use the folder for internal logic, but UI will remember the json
        project_name = session.get("current_project_name") or root_path_obj.name
        set_current_project(root_path, project_name)

        # Persist to settings file for restoration after app restart
        _save_last_project(root_path, project_name)

        # Override the return path to be the project.json path so UI stores/reloads via the file
        result["current_project"] = {"path": project_json_path, "name": project_name}

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
        return jsonify({"success": True, "issues": issues})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@projects_bp.route("/api/projects/modalities", methods=["GET"])
def get_modalities():
    """Get list of available PRISM modalities."""
    return jsonify({"success": True, "modalities": get_available_modalities()})


@projects_bp.route("/api/settings/global-library", methods=["GET"])
def get_global_library_settings():
    """Get the global template library settings."""
    from src.config import load_app_settings
    from flask import current_app

    # Always pass app_root to load from the correct consolidated app directory
    app_root = Path(current_app.root_path)
    settings = load_app_settings(app_root=str(app_root))

    # Get effective library path from configuration
    from src.config import get_effective_library_paths

    lib_paths = get_effective_library_paths(
        app_root=str(app_root), app_settings=settings
    )
    default_library_path = lib_paths["global_library_path"] or str(
        app_root / "survey_library"
    )

    return jsonify(
        {
            "success": True,
            "global_template_library_path": settings.global_template_library_path,
            "global_recipes_path": settings.global_recipes_path,
            "default_library_path": default_library_path,
            "default_modalities": settings.default_modalities,
        }
    )


@projects_bp.route("/api/settings/global-library", methods=["POST"])
def set_global_library_settings():
    """Update the global template library settings."""
    from src.config import load_app_settings, save_app_settings
    from flask import current_app

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    # Load current settings from app root
    app_root = Path(current_app.root_path)
    settings = load_app_settings(app_root=str(app_root))

    # Update settings
    if "global_template_library_path" in data:
        path = data["global_template_library_path"]
        # Allow empty/null to clear the setting
        if path and path.strip():
            # Validate path exists
            if not os.path.exists(path):
                return (
                    jsonify(
                        {"success": False, "error": f"Path does not exist: {path}"}
                    ),
                    400,
                )
            settings.global_template_library_path = path
        else:
            settings.global_template_library_path = None

    if "global_recipes_path" in data:
        path = data["global_recipes_path"]
        # Allow empty/null to clear the setting
        if path and path.strip():
            # Validate path exists
            if not os.path.exists(path):
                return (
                    jsonify(
                        {"success": False, "error": f"Path does not exist: {path}"}
                    ),
                    400,
                )
            settings.global_recipes_path = path
        else:
            settings.global_recipes_path = None

    if "default_modalities" in data:
        settings.default_modalities = data["default_modalities"]

    # Save settings to app root
    try:
        app_root = Path(current_app.root_path)
        settings_path = save_app_settings(settings, str(app_root))
        return jsonify(
            {
                "success": True,
                "message": f"Settings saved to {settings_path}",
                "global_template_library_path": settings.global_template_library_path,
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@projects_bp.route("/api/projects/library-path", methods=["GET"])
def get_library_path():
    """Get the library paths for the current project.

    Returns information about both:
    - Global template library (shared, read-only from Nextcloud/GitLab)
    - Project library folder (user's own templates)

    Returns:
        JSON with library paths, project info, and structure flags
    """
    from src.config import get_effective_template_library_path, load_app_settings
    from flask import current_app

    current = get_current_project()
    app_root = Path(current_app.root_path)
    app_settings = load_app_settings(app_root=str(app_root))

    # Get effective library path from configuration
    from src.config import get_effective_library_paths

    lib_paths = get_effective_library_paths(
        app_root=str(app_root), app_settings=app_settings
    )

    # Resolve and validate the global library path
    def resolve_library_path(path_str):
        """Resolve a path and return it only if it exists."""
        if not path_str:
            return None
        p = Path(path_str)
        # Resolve relative paths against app root
        if not p.is_absolute():
            p = (app_root / p).resolve()
        else:
            p = p.resolve()
        return str(p) if p.exists() and p.is_dir() else None

    # Try configured path first, then fallbacks
    effective_global_path = (
        resolve_library_path(app_settings.global_template_library_path)
        or resolve_library_path(lib_paths["global_library_path"])
        or resolve_library_path(str(app_root / "survey_library"))
        or resolve_library_path(str(app_root / "library" / "survey_i18n"))
    )

    if not current.get("path"):
        # No project selected - still return global library
        return jsonify(
            {
                "success": False,
                "message": "No project selected",
                "project_library_path": None,
                "project_library_exists": False,
                "global_library_path": effective_global_path,
                "library_path": effective_global_path,  # Legacy compatibility
            }
        )

    project_path = Path(current["path"])

    # Get effective library paths
    library_info = get_effective_template_library_path(
        str(project_path), app_settings, app_root=str(app_root)
    )

    # Project's own library folder
    # YODA-compliant: code/library (preferred)
    # Legacy: library/ at root (for backward compatibility only)
    yoda_library = project_path / "code" / "library"
    legacy_library = project_path / "library"

    # For legacy compatibility, provide a single "library_path" that works for conversion
    # ALWAYS prefer YODA layout (code/library) if it exists
    legacy_library_path = None
    if yoda_library.exists():
        legacy_library_path = str(yoda_library)
    elif legacy_library.exists():
        legacy_library_path = str(legacy_library)
    elif library_info.get("effective_external_path"):
        legacy_library_path = library_info["effective_external_path"]
    else:
        legacy_library_path = str(project_path)

    return jsonify(
        {
            "success": True,
            "project_path": str(project_path),
            "project_name": current.get("name"),
            # Dual library system
            "project_library_path": (
                str(yoda_library)
                if yoda_library.exists()
                else (str(legacy_library) if legacy_library.exists() else None)
            ),
            "project_library_exists": yoda_library.exists() or legacy_library.exists(),
            "global_library_path": library_info.get("global_library_path")
            or effective_global_path,
            "effective_external_path": library_info.get("effective_external_path"),
            "external_source": library_info.get(
                "source"
            ),  # 'project', 'global', or 'default'
            # Legacy compatibility
            "library_path": legacy_library_path,
            # Structure info
            "structure": {
                "has_project_library": yoda_library.exists() or legacy_library.exists(),
                "has_survey": (
                    (yoda_library / "survey").exists()
                    if yoda_library.exists()
                    else (legacy_library / "survey").exists()
                ),
                "has_biometrics": (
                    (yoda_library / "biometrics").exists()
                    if yoda_library.exists()
                    else (legacy_library / "biometrics").exists()
                ),
                "has_participants": get_bids_file_path(
                    project_path, "participants.json"
                ).exists(),
                "has_external_library": library_info.get("effective_external_path")
                is not None,
            },
        }
    )


@projects_bp.route("/api/projects/participants", methods=["GET"])
def get_participants_schema():
    """Get the participants.json schema for the current project.

    Returns the current participants.json content and structure info.
    """
    import json

    current = get_current_project()
    if not current.get("path"):
        return jsonify({"success": False, "error": "No project selected"}), 400

    project_path = Path(current["path"])
    participants_path = get_bids_file_path(project_path, "participants.json")

    if not participants_path.exists():
        return jsonify(
            {
                "success": True,
                "exists": False,
                "schema": {},
                "project_path": str(project_path),
                "project_name": current.get("name"),
            }
        )

    try:
        with open(participants_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        return jsonify(
            {
                "success": True,
                "exists": True,
                "schema": schema,
                "fields": list(schema.keys()),
                "project_path": str(project_path),
                "project_name": current.get("name"),
            }
        )
    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Failed to read participants.json: {str(e)}",
                }
            ),
            500,
        )


@projects_bp.route("/api/projects/participants", methods=["POST"])
def save_participants_schema():
    """Save the participants.json schema for the current project.

    Expected JSON body:
    {
        "schema": {
            "participant_id": {"Description": "..."},
            "age": {"Description": "...", "Unit": "years"},
            ...
        }
    }
    """
    import json

    current = get_current_project()
    if not current.get("path"):
        return jsonify({"success": False, "error": "No project selected"}), 400

    data = request.get_json()
    if not data or "schema" not in data:
        return jsonify({"success": False, "error": "No schema provided"}), 400

    schema = data["schema"]

    # Validate schema structure
    if not isinstance(schema, dict):
        return jsonify({"success": False, "error": "Schema must be a dictionary"}), 400

    # Ensure participant_id is always included (BIDS requirement)
    if "participant_id" not in schema:
        schema = {
            "participant_id": {"Description": "Unique participant identifier"},
            **schema,
        }

    project_path = Path(current["path"])
    participants_path = get_bids_file_path(project_path, "participants.json")

    try:
        with open(participants_path, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2, ensure_ascii=False)

        return jsonify(
            {
                "success": True,
                "message": "participants.json saved successfully",
                "fields": list(schema.keys()),
                "path": str(participants_path),
            }
        )
    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Failed to save participants.json: {str(e)}",
                }
            ),
            500,
        )


@projects_bp.route("/api/projects/description", methods=["GET"])
def get_dataset_description():
    """Get the dataset_description.json for the current project."""
    import json

    current = get_current_project()
    if not current.get("path"):
        return jsonify({"success": False, "error": "No project selected"}), 400

    project_path = Path(current["path"])
    desc_path = get_bids_file_path(project_path, "dataset_description.json")

    if not desc_path.exists():
        return (
            jsonify({"success": False, "error": "dataset_description.json not found"}),
            404,
        )

    try:
        with open(desc_path, "r", encoding="utf-8") as f:
            description = json.load(f)

        # Validate on load
        issues = _project_manager.validate_dataset_description(description)

        return jsonify({"success": True, "description": description, "issues": issues})
    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Failed to read dataset_description.json: {str(e)}",
                }
            ),
            500,
        )


@projects_bp.route("/api/projects/description", methods=["POST"])
def save_dataset_description():
    """Save the dataset_description.json for the current project."""
    import json

    current = get_current_project()
    if not current.get("path"):
        return jsonify({"success": False, "error": "No project selected"}), 400

    data = request.get_json()
    if not data or "description" not in data:
        return jsonify({"success": False, "error": "No description data provided"}), 400

    description = data["description"]
    project_path = Path(current["path"])
    desc_path = get_bids_file_path(project_path, "dataset_description.json")

    try:
        # Ensure name remains standard BIDS 'Name' (case sensitivity)
        if "Name" not in description and "name" in description:
            description["Name"] = description.pop("name")

        # Basic BIDS validation - ensure Name and BIDSVersion exist
        if "Name" not in description:
            return (
                jsonify({"success": False, "error": "Dataset 'Name' is required"}),
                400,
            )
        if "BIDSVersion" not in description:
            description["BIDSVersion"] = "1.10.1"

        # Validate before saving
        issues = _project_manager.validate_dataset_description(description)

        with open(desc_path, "w", encoding="utf-8") as f:
            json.dump(description, f, indent=2, ensure_ascii=False)

        # If name changed, also update session name for UI consistency
        if "Name" in description:
            set_current_project(str(project_path), description["Name"])
            _save_last_project(str(project_path), description["Name"])

        return jsonify(
            {
                "success": True,
                "message": "dataset_description.json saved successfully",
                "issues": issues,
            }
        )
    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Failed to save dataset_description.json: {str(e)}",
                }
            ),
            500,
        )


@projects_bp.route("/api/projects/participants/columns", methods=["GET"])
def get_participants_columns():
    """Extract unique values from project's participants.tsv."""
    import pandas as pd

    current = get_current_project()
    if not current.get("path"):
        return jsonify({"error": "No project selected"}), 400

    project_path = Path(current["path"])
    tsv_path = get_bids_file_path(project_path, "participants.tsv")

    if not tsv_path.exists():
        return jsonify({"columns": {}})

    try:
        df = pd.read_csv(tsv_path, sep="\t")
        result = {}
        for col in df.columns:
            # Always include the column to signal its availability in TSV
            # but only return unique values for categorical/low-cardinality columns
            if col.lower() not in ["participant_id", "id"] and df[col].nunique() < 50:
                # Filter out NaNs and convert to strings
                unique_vals = [str(v) for v in df[col].dropna().unique().tolist()]
                result[col] = sorted(unique_vals)
            else:
                # Still include the key so frontend knows it exists in TSV
                result[col] = []

        return jsonify({"columns": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@projects_bp.route("/api/projects/sourcedata-files", methods=["GET"])
def get_sourcedata_files():
    """List survey-compatible files in the project's sourcedata/ folder.

    Returns files matching converter-supported extensions (.xlsx, .csv, .tsv, .lsa, .lss)
    found in the sourcedata/ directory (non-recursive).
    """
    current = get_current_project()
    if not current.get("path"):
        return jsonify({"files": [], "sourcedata_exists": False})

    project_path = Path(current["path"])
    sourcedata_dir = project_path / "sourcedata"

    if not sourcedata_dir.exists() or not sourcedata_dir.is_dir():
        return jsonify({"files": [], "sourcedata_exists": False})

    supported_extensions = {".xlsx", ".csv", ".tsv", ".lsa", ".lss"}
    files = []
    for f in sorted(sourcedata_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in supported_extensions:
            files.append(
                {
                    "name": f.name,
                    "path": str(f),
                    "size": f.stat().st_size,
                    "extension": f.suffix.lower(),
                }
            )

    return jsonify({"files": files, "sourcedata_exists": True})


@projects_bp.route("/api/projects/sourcedata-file", methods=["GET"])
def get_sourcedata_file():
    """Serve a file from the project's sourcedata/ folder.

    Query params:
        name: filename to serve (must be in sourcedata/)
    """
    from flask import send_file as _send_file

    current = get_current_project()
    if not current.get("path"):
        return jsonify({"error": "No project selected"}), 400

    filename = request.args.get("name")
    if not filename:
        return jsonify({"error": "No filename provided"}), 400

    project_path = Path(current["path"])
    file_path = (project_path / "sourcedata" / filename).resolve()

    # Security: ensure the resolved path is inside sourcedata/
    sourcedata_dir = (project_path / "sourcedata").resolve()
    if not str(file_path).startswith(str(sourcedata_dir)):
        return jsonify({"error": "Invalid filename"}), 400

    if not file_path.exists() or not file_path.is_file():
        return jsonify({"error": f"File not found: {filename}"}), 404

    return _send_file(str(file_path), as_attachment=True, download_name=filename)


@projects_bp.route("/api/projects/participants/templates", methods=["GET"])
def get_participants_templates():
    """Get predefined BIDS-compatible field templates.

    Returns categorized field definitions with descriptions and levels.
    These are recommendations based on BIDS standard and common research needs.
    """
    # Predefined BIDS-compatible participant fields organized by category
    templates = {
        "required": {
            "participant_id": {
                "Description": "Unique participant identifier",
                "_help": "REQUIRED by BIDS. Format: sub-<label> (e.g., sub-001)",
                "_required": True,
            }
        },
        "demographics": {
            "age": {
                "Description": "Age of participant",
                "Unit": "years",
                "_help": "Recommended. Can be exact age or age range for anonymity.",
            },
            "sex": {
                "Description": "Biological sex",
                "Levels": {
                    "M": "Male",
                    "F": "Female",
                    "O": "Other",
                    "DNS": "Did not say",
                },
                "_help": "BIDS recommended. Biological sex assigned at birth.",
            },
            "gender": {
                "Description": "Gender identity",
                "Levels": {
                    "woman": "Woman",
                    "man": "Man",
                    "non_binary": "Non-binary",
                    "other": "Other",
                    "DNS": "Did not say",
                },
                "_help": "Self-identified gender. Separate from biological sex.",
            },
            "handedness": {
                "Description": "Handedness",
                "Levels": {"R": "Right", "L": "Left", "A": "Ambidextrous"},
                "_help": "BIDS recommended for neuroimaging studies.",
            },
        },
        "education": {
            "education_level": {
                "Description": "Highest completed education level",
                "Levels": {
                    "1": "Primary education",
                    "2": "Secondary education",
                    "3": "Vocational training",
                    "4": "Bachelor's degree",
                    "5": "Master's degree",
                    "6": "Doctorate",
                    "7": "Other",
                },
                "_help": "Categorical education level.",
            },
            "education_years": {
                "Description": "Years of formal education completed",
                "Unit": "years",
                "_help": "Continuous measure of education.",
            },
        },
        "socioeconomic": {
            "employment_status": {
                "Description": "Employment status",
                "Levels": {
                    "employed": "Employed",
                    "self_employed": "Self-employed",
                    "unemployed": "Unemployed",
                    "student": "Student",
                    "retired": "Retired",
                    "other": "Other",
                },
            },
            "marital_status": {
                "Description": "Marital status",
                "Levels": {
                    "single": "Single",
                    "partnered": "Partnered",
                    "married": "Married",
                    "divorced": "Divorced",
                    "widowed": "Widowed",
                },
            },
            "household_size": {
                "Description": "Number of people in the household",
                "Unit": "persons",
            },
        },
        "geographic": {
            "country_of_residence": {
                "Description": "Country of residence",
                "_help": "Use ISO 3166-1 alpha-2 codes (e.g., AT, DE, US).",
            },
            "native_language": {
                "Description": "Native language",
                "_help": "Use ISO 639-1 codes (e.g., de, en, fr).",
            },
        },
        "health": {
            "height": {"Description": "Body height", "Unit": "cm"},
            "weight": {"Description": "Body weight", "Unit": "kg"},
            "bmi": {"Description": "Body mass index", "Unit": "kg/m^2"},
            "smoking_status": {
                "Description": "Smoking status",
                "Levels": {
                    "never": "Never smoked",
                    "former": "Former smoker",
                    "current": "Current smoker",
                },
            },
            "vision": {
                "Description": "Vision status",
                "Levels": {
                    "normal": "Normal/corrected to normal",
                    "impaired": "Impaired",
                },
                "_help": "Important for visual experiments.",
            },
            "hearing": {
                "Description": "Hearing status",
                "Levels": {"normal": "Normal", "impaired": "Impaired"},
                "_help": "Important for auditory experiments.",
            },
        },
        "study": {
            "group": {
                "Description": "Study group assignment",
                "Levels": {
                    "control": "Control group",
                    "experimental": "Experimental group",
                },
                "_help": "Define your study-specific groups.",
            },
            "session_date": {
                "Description": "Date of data collection",
                "Unit": "ISO 8601 date",
                "_help": "Format: YYYY-MM-DD",
            },
        },
    }

    # BIDS compliance tips
    tips = [
        {
            "level": "required",
            "message": "participant_id is REQUIRED by BIDS specification",
            "field": "participant_id",
        },
        {
            "level": "recommended",
            "message": "BIDS recommends including age, sex, and handedness for all datasets",
            "fields": ["age", "sex", "handedness"],
        },
        {
            "level": "info",
            "message": "Use standard units (years, cm, kg) and ISO codes for countries/languages",
            "fields": [],
        },
        {
            "level": "info",
            "message": "Each field should have a Description. Use Levels for categorical data and Units for continuous data.",
            "fields": [],
        },
        {
            "level": "privacy",
            "message": "Consider anonymization: use age ranges instead of exact ages, avoid identifying information",
            "fields": ["age", "country_of_residence"],
        },
    ]

    return jsonify(
        {
            "success": True,
            "templates": templates,
            "tips": tips,
            "categories": list(templates.keys()),
        }
    )


@projects_bp.route("/api/projects/export", methods=["POST"])
def export_project():
    """
    Export the current project as a ZIP file with optional anonymization.

    Expected JSON body:
    {
        "project_path": "/path/to/project",
        "anonymize": true,
        "mask_questions": true,
        "id_length": 8,
        "deterministic": true,
        "include_derivatives": true,
        "include_code": true,
        "include_analysis": false
    }
    """
    import tempfile
    from flask import send_file
    from src.web.export_project import export_project as do_export

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        project_path = data.get("project_path")
        if not project_path or not os.path.exists(project_path):
            return jsonify({"error": "Invalid project path"}), 400

        project_path = Path(project_path)

        # Get export options
        anonymize = bool(data.get("anonymize", True))
        mask_questions = bool(data.get("mask_questions", True))
        id_length = int(data.get("id_length", 8))
        deterministic = bool(data.get("deterministic", True))
        include_derivatives = bool(data.get("include_derivatives", True))
        include_code = bool(data.get("include_code", True))
        include_analysis = bool(data.get("include_analysis", False))

        # Create temporary file for ZIP
        temp_fd, temp_path = tempfile.mkstemp(suffix=".zip")
        os.close(temp_fd)

        try:
            # Perform export
            do_export(
                project_path=project_path,
                output_zip=Path(temp_path),
                anonymize=anonymize,
                mask_questions=mask_questions,
                id_length=id_length,
                deterministic=deterministic,
                include_derivatives=include_derivatives,
                include_code=include_code,
                include_analysis=include_analysis,
            )

            # Generate filename
            project_name = project_path.name
            anon_suffix = "_anonymized" if anonymize else ""
            filename = f"{project_name}{anon_suffix}_export.zip"

            # Send file
            return send_file(
                temp_path,
                mimetype="application/zip",
                as_attachment=True,
                download_name=filename,
            )

        except Exception:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@projects_bp.route("/api/projects/anc-export", methods=["POST"])
def anc_export_project():
    """
    Export the current project to ANC (Austrian NeuroCloud) compatible format.

    Expected JSON body:
    {
        "project_path": "/path/to/project",
        "convert_to_git_lfs": false,
        "include_ci_examples": false,
        "metadata": {
            "DATASET_NAME": "My Study",
            "CONTACT_EMAIL": "contact@example.com",
            "AUTHOR_GIVEN_NAME": "John",
            "AUTHOR_FAMILY_NAME": "Doe",
            "DATASET_ABSTRACT": "Description of the dataset"
        }
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        project_path = data.get("project_path")
        if not project_path or not os.path.exists(project_path):
            return jsonify({"success": False, "error": "Invalid project path"}), 400

        project_path = Path(project_path)

        # Import ANC exporter
        from src.converters.anc_export import ANCExporter

        # Get export options
        convert_to_git_lfs = bool(data.get("convert_to_git_lfs", False))
        include_ci_examples = bool(data.get("include_ci_examples", False))
        metadata = data.get("metadata", {})

        # Determine output path
        output_path = project_path.parent / f"{project_path.name}_anc_export"

        # Create exporter
        exporter = ANCExporter(project_path, output_path)

        # Perform export
        result_path = exporter.export(
            metadata=metadata,
            convert_to_git_lfs=convert_to_git_lfs,
            include_ci_examples=include_ci_examples,
            copy_data=True
        )

        return jsonify({
            "success": True,
            "output_path": str(result_path),
            "message": "ANC export completed successfully",
            "generated_files": {
                "readme": str(result_path / "README.md"),
                "citation": str(result_path / "CITATION.cff"),
                "validator_config": str(result_path / ".bids-validator-config.json")
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =============================================================================
# Session & Procedure Tracking Endpoints
# =============================================================================


def _read_project_json(project_path: Path) -> dict:
    """Read and return project.json content from a project directory."""
    pj = project_path / "project.json"
    if not pj.exists():
        return {}
    with open(pj, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_project_json(project_path: Path, data: dict):
    """Write project.json to disk, updating LastModified metadata if present."""
    from src.cross_platform import CrossPlatformFile

    pj = project_path / "project.json"
    CrossPlatformFile.write_text(
        str(pj), json.dumps(data, indent=2, ensure_ascii=False)
    )


_NA_VALUES = {"na", "n/a", "nan", "", "none", "null", "missing", "n.a."}


def _read_participants_schema(project_path: Path) -> dict:
    """Read participants.json schema if it exists."""
    for candidate in [
        project_path / "rawdata" / "participants.json",
        project_path / "participants.json",
    ]:
        if candidate.exists():
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}


def _resolve_level_label(value: str, levels: dict, lang: str = "en") -> str | None:
    """Map a coded value to its human-readable label using Levels dict.

    Returns None if the value is NA-like.
    """
    from src.reporting import get_i18n_text

    if str(value).strip().lower() in _NA_VALUES:
        return None
    label_obj = levels.get(str(value))
    if label_obj is None:
        return str(value)
    return get_i18n_text(label_obj, lang) or str(value)


def _compute_participant_stats(project_path: Path, lang: str = "en") -> dict | None:
    """Read participants.tsv and compute demographic summary statistics.

    Uses participants.json schema for proper value labels and filtering.

    Returns a dict with keys: n, age_mean, age_sd, age_min, age_max,
    sex_counts, additional_columns.  Returns None when the file is
    missing or unreadable.
    """
    tsv_path = get_bids_file_path(project_path, "participants.tsv")
    if not tsv_path.exists():
        return None

    try:
        import pandas as pd

        df = pd.read_csv(tsv_path, sep="\t")
        if df.empty:
            return None

        schema = _read_participants_schema(project_path)
        stats: dict = {"n": len(df)}

        # --- Age ---
        age_col = None
        for candidate in ["age", "Age", "AGE"]:
            if candidate in df.columns:
                age_col = candidate
                break
        if age_col:
            ages = pd.to_numeric(df[age_col], errors="coerce").dropna()
            if len(ages) > 0:
                stats["age_mean"] = round(float(ages.mean()), 2)
                stats["age_sd"] = (
                    round(float(ages.std(ddof=1)), 2) if len(ages) > 1 else None
                )
                stats["age_min"] = int(ages.min())
                stats["age_max"] = int(ages.max())

        # --- Sex / Gender ---
        sex_col = None
        for candidate in ["sex", "Sex", "SEX", "gender", "Gender"]:
            if candidate in df.columns:
                sex_col = candidate
                break
        if sex_col:
            series = df[sex_col].astype(str)
            # Filter NA-like values
            mask = ~series.str.strip().str.lower().isin(_NA_VALUES)
            series = series[mask]
            counts = series.value_counts()

            # Use schema Levels if available
            sex_schema = schema.get(sex_col) or schema.get(sex_col.lower()) or {}
            sex_levels = sex_schema.get("Levels") or {}

            if sex_levels:
                from src.reporting import get_i18n_text

                mapped: dict[str, int] = {}
                for val, cnt in counts.items():
                    label = _resolve_level_label(val, sex_levels, lang)
                    if label is None:
                        continue
                    mapped[label] = mapped.get(label, 0) + int(cnt)
            else:
                # Fallback: common BIDS code mapping
                label_map = {
                    "M": "male",
                    "m": "male",
                    "1": "male",
                    "F": "female",
                    "f": "female",
                    "2": "female",
                    "O": "other",
                    "o": "other",
                }
                mapped = {}
                for val, cnt in counts.items():
                    sv = str(val).strip()
                    if sv.lower() in _NA_VALUES:
                        continue
                    label = label_map.get(sv, sv)
                    mapped[label] = mapped.get(label, 0) + int(cnt)

            stats["sex_counts"] = dict(sorted(mapped.items(), key=lambda x: -x[1]))

        # --- Additional demographic columns ---
        # Only include columns that have Levels in the schema
        skip_cols = {
            "participant_id",
            "age",
            "sex",
            "gender",
            "session",
            "session_date",
            "group",
        }
        from src.reporting import get_i18n_text

        additional: list[dict] = []
        for col in df.columns:
            if col.lower() in skip_cols:
                continue
            col_schema = schema.get(col) or {}
            col_levels = col_schema.get("Levels") or {}
            if not col_levels:
                continue
            # Get a human-readable column name from schema Description
            col_desc = col_schema.get("Description")
            col_label = (
                get_i18n_text(col_desc, lang) if col_desc else col.replace("_", " ")
            )

            series = df[col].astype(str)
            mask = ~series.str.strip().str.lower().isin(_NA_VALUES)
            series = series[mask]
            if series.empty:
                continue
            counts = series.value_counts()
            distribution: dict[str, int] = {}
            for val, cnt in counts.items():
                label = _resolve_level_label(val, col_levels, lang)
                if label is None:
                    continue
                distribution[label] = distribution.get(label, 0) + int(cnt)
            if distribution:
                additional.append({"name": col_label, "distribution": distribution})

        stats["additional_columns"] = additional[:5]
        return stats
    except Exception:
        return None


@projects_bp.route("/api/projects/sessions", methods=["GET"])
def get_sessions():
    """Read Sessions + TaskDefinitions from project.json."""
    current = get_current_project()
    if not current.get("path"):
        return jsonify({"success": False, "error": "No project selected"}), 400

    project_path = Path(current["path"])
    data = _read_project_json(project_path)
    if not data:
        return jsonify({"success": False, "error": "project.json not found"}), 404

    return jsonify(
        {
            "success": True,
            "sessions": data.get("Sessions", []),
            "task_definitions": data.get("TaskDefinitions", {}),
        }
    )


@projects_bp.route("/api/projects/sessions", methods=["POST"])
def save_sessions():
    """Write Sessions + TaskDefinitions to project.json."""
    current = get_current_project()
    if not current.get("path"):
        return jsonify({"success": False, "error": "No project selected"}), 400

    req = request.get_json()
    if not req:
        return jsonify({"success": False, "error": "No data provided"}), 400

    project_path = Path(current["path"])
    data = _read_project_json(project_path)
    if not data:
        return jsonify({"success": False, "error": "project.json not found"}), 404

    if "sessions" in req:
        data["Sessions"] = req["sessions"]
    if "task_definitions" in req:
        data["TaskDefinitions"] = req["task_definitions"]

    _write_project_json(project_path, data)
    return jsonify({"success": True, "message": "Sessions saved"})


@projects_bp.route("/api/projects/sessions/declared", methods=["GET"])
def get_sessions_declared():
    """Lightweight list of [{id, label}] for converter session picker."""
    current = get_current_project()
    if not current.get("path"):
        return jsonify({"sessions": []})

    project_path = Path(current["path"])
    data = _read_project_json(project_path)
    sessions = data.get("Sessions", [])

    return jsonify(
        {
            "sessions": [
                {"id": s.get("id", ""), "label": s.get("label", s.get("id", ""))}
                for s in sessions
            ]
        }
    )


@projects_bp.route("/api/projects/sessions/register", methods=["POST"])
def register_session():
    """Register a conversion result into a session in project.json.

    Expected JSON body:
    {
        "session_id": "ses-01",
        "tasks": ["panas", "bfi"],
        "modality": "survey",
        "source_file": "survey_baseline.xlsx",
        "converter": "survey-xlsx"
    }
    """
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

    # Normalize session_id to ses-<label> format with zero-padding for numeric values
    if not session_id.startswith("ses-"):
        session_id = f"ses-{session_id}"
    # Ensure zero-padding for numeric session IDs
    num_part = session_id[4:]  # Strip "ses-" prefix
    try:
        n = int(num_part)
        session_id = f"ses-{n:02d}"
    except ValueError:
        pass  # Non-numeric labels pass through as-is

    # Validate session ID pattern
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
    data = _read_project_json(project_path)
    if not data:
        return jsonify({"success": False, "error": "project.json not found"}), 404

    # Ensure Sessions and TaskDefinitions exist
    if "Sessions" not in data:
        data["Sessions"] = []
    if "TaskDefinitions" not in data:
        data["TaskDefinitions"] = {}

    # Find or create session
    target_session = None
    for s in data["Sessions"]:
        if s.get("id") == session_id:
            target_session = s
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
        # Check if task already exists in this session
        existing = None
        for t in target_session["tasks"]:
            if t.get("task") == task_name:
                existing = t
                break

        if existing:
            # Update source provenance
            existing["source"] = source_obj
        else:
            # Add new task entry
            target_session["tasks"].append(
                {
                    "task": task_name,
                    "source": source_obj,
                }
            )

        registered_tasks.append(task_name)

        # Ensure TaskDefinition exists
        if task_name not in data["TaskDefinitions"]:
            data["TaskDefinitions"][task_name] = {"modality": modality}

    _write_project_json(project_path, data)

    return jsonify(
        {
            "success": True,
            "message": f"Registered {len(registered_tasks)} task(s) in {session_id}",
            "session_id": session_id,
            "registered_tasks": registered_tasks,
        }
    )


@projects_bp.route("/api/projects/generate-methods", methods=["POST"])
def generate_methods_section():
    """Generate a publication-ready methods section from project.json metadata.

    Reads project.json, dataset_description.json, and referenced templates to
    produce a comprehensive scientific methods section in both Markdown and HTML.

    Expected JSON body:
    {
        "language": "en"  // "en" or "de"
    }
    """
    from src.reporting import generate_full_methods, _md_to_html
    from src.config import (
        get_effective_template_library_path,
        load_app_settings,
    )
    from flask import current_app

    current = get_current_project()
    if not current.get("path"):
        return jsonify({"success": False, "error": "No project selected"}), 400

    data = request.get_json() or {}
    lang = data.get("language", "en")
    detail_level = data.get("detail_level", "standard")
    continuous = bool(data.get("continuous", False))

    project_path = Path(current["path"])
    project_data = _read_project_json(project_path)
    if not project_data:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "No project metadata available. Fill in your project.json to generate a methods section.",
                }
            ),
            404,
        )

    # Read dataset_description.json
    dataset_desc = None
    desc_path = get_bids_file_path(project_path, "dataset_description.json")
    if desc_path.exists():
        try:
            with open(desc_path, "r", encoding="utf-8") as f:
                dataset_desc = json.load(f)
        except Exception:
            pass

    # Load template data for each TaskDefinition with a template field
    task_defs = project_data.get("TaskDefinitions") or {}
    app_root = Path(current_app.root_path)
    app_settings = load_app_settings(app_root=str(app_root))
    lib_info = get_effective_template_library_path(
        str(project_path), app_settings, app_root=str(app_root)
    )

    # Build search paths for templates: project library first, then global
    search_dirs: list[Path] = []
    yoda_lib = project_path / "code" / "library"
    legacy_lib = project_path / "library"
    if yoda_lib.exists():
        search_dirs.append(yoda_lib)
    elif legacy_lib.exists():
        search_dirs.append(legacy_lib)
    ext_path = lib_info.get("effective_external_path")
    if ext_path:
        search_dirs.append(Path(ext_path))
    global_path = lib_info.get("global_library_path")
    if global_path:
        search_dirs.append(Path(global_path))

    template_data: dict[str, dict] = {}
    for task_name, td in task_defs.items():
        tpl_filename = td.get("template", "")
        if not tpl_filename:
            continue
        for search_dir in search_dirs:
            # Templates may be in modality subfolders (survey/, biometrics/) or root
            candidates = [
                search_dir / tpl_filename,
                search_dir / "survey" / tpl_filename,
                search_dir / "biometrics" / tpl_filename,
            ]
            for candidate in candidates:
                if candidate.exists():
                    try:
                        with open(candidate, "r", encoding="utf-8") as f:
                            template_data[task_name] = json.load(f)
                    except Exception:
                        pass
                    break
            if task_name in template_data:
                break

    # Compute participant demographics from participants.tsv
    participant_stats = _compute_participant_stats(project_path, lang=lang)

    try:
        md_text, sections_used = generate_full_methods(
            project_data,
            dataset_desc,
            template_data,
            participant_stats=participant_stats,
            lang=lang,
            detail_level=detail_level,
            continuous=continuous,
        )
        html_text = _md_to_html(md_text)
        filename_base = f"methods_section_{lang}"

        return jsonify(
            {
                "success": True,
                "md": md_text,
                "html": html_text,
                "filename_base": filename_base,
                "sections_used": sections_used,
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =============================================================================
# Study Metadata & Methods Completeness
# =============================================================================

_EXPERIMENTAL_TYPES = {
    "randomized-controlled-trial",
    "quasi-experimental",
    "case-control",
}

_EDITABLE_SECTIONS = (
    "Overview",
    "StudyDesign",
    "Recruitment",
    "Eligibility",
    "DataCollection",
    "Procedure",
    "MissingData",
    "References",
    "Conditions",
)


def _compute_methods_completeness(
    project_data: dict, dataset_desc: dict | None
) -> dict:
    """Compute weighted completeness score across all fields feeding the methods generator.

    Priority weights: critical=3, important=2, optional=1.
    Returns per-section breakdown with field names, filled status, priority, and hint.
    """
    sd = project_data.get("StudyDesign") or {}
    rec = project_data.get("Recruitment") or {}
    elig = project_data.get("Eligibility") or {}
    dc = project_data.get("DataCollection") or {}
    proc = project_data.get("Procedure") or {}
    cond = project_data.get("Conditions") or {}
    sessions = project_data.get("Sessions") or []
    task_defs = project_data.get("TaskDefinitions") or {}
    dd = dataset_desc or {}

    is_experimental = sd.get("Type", "") in _EXPERIMENTAL_TYPES

    def _filled(val) -> bool:
        if val is None:
            return False
        if isinstance(val, str):
            return bool(val.strip())
        if isinstance(val, (list, dict)):
            return len(val) > 0
        if isinstance(val, (int, float)):
            return True
        return bool(val)

    def _obj_filled(obj, key):
        """Check nested object field."""
        if not isinstance(obj, dict):
            return False
        return _filled(obj.get(key))

    # Define all tracked fields: (section_key, field_name, priority, hint, value)
    fields: list[tuple[str, str, int, str, bool]] = [
        # StudyDesign
        (
            "StudyDesign",
            "Type",
            3,
            "Select the study design type",
            _filled(sd.get("Type")),
        ),
        (
            "StudyDesign",
            "TypeDescription",
            2,
            "Describe the design in detail",
            _filled(sd.get("TypeDescription")),
        ),
        (
            "StudyDesign",
            "Blinding",
            1,
            "Blinding procedure (experimental studies)",
            _filled(sd.get("Blinding")),
        ),
        (
            "StudyDesign",
            "Randomization",
            1,
            "Randomization method",
            _filled(sd.get("Randomization")),
        ),
        # Recruitment
        (
            "Recruitment",
            "Method",
            3,
            "How were participants recruited?",
            _filled(rec.get("Method")),
        ),
        (
            "Recruitment",
            "Location",
            3,
            "Where were participants recruited?",
            _filled(rec.get("Location")),
        ),
        (
            "Recruitment",
            "Period.Start",
            3,
            "When did recruitment begin?",
            _obj_filled(rec.get("Period"), "Start"),
        ),
        (
            "Recruitment",
            "Period.End",
            2,
            "When did recruitment end?",
            _obj_filled(rec.get("Period"), "End"),
        ),
        (
            "Recruitment",
            "Compensation",
            2,
            "Participant compensation",
            _filled(rec.get("Compensation")),
        ),
        (
            "Recruitment",
            "Platform",
            1,
            "Recruitment platform (e.g. Prolific)",
            _filled(rec.get("Platform")),
        ),
        # Eligibility
        (
            "Eligibility",
            "InclusionCriteria",
            3,
            "List inclusion criteria",
            _filled(elig.get("InclusionCriteria")),
        ),
        (
            "Eligibility",
            "ExclusionCriteria",
            3,
            "List exclusion criteria",
            _filled(elig.get("ExclusionCriteria")),
        ),
        (
            "Eligibility",
            "TargetSampleSize",
            1,
            "Planned sample size",
            _filled(elig.get("TargetSampleSize")),
        ),
        (
            "Eligibility",
            "PowerAnalysis",
            1,
            "Power analysis description",
            _filled(elig.get("PowerAnalysis")),
        ),
        # DataCollection
        (
            "DataCollection",
            "Platform",
            3,
            "Data collection platform",
            _filled(dc.get("Platform")),
        ),
        (
            "DataCollection",
            "PlatformVersion",
            1,
            "Platform version",
            _filled(dc.get("PlatformVersion")),
        ),
        (
            "DataCollection",
            "Method",
            3,
            "Collection method (online/in-person/...)",
            _filled(dc.get("Method")),
        ),
        (
            "DataCollection",
            "SupervisionLevel",
            2,
            "Level of supervision",
            _filled(dc.get("SupervisionLevel")),
        ),
        (
            "DataCollection",
            "Setting",
            2,
            "Data collection setting",
            _filled(dc.get("Setting")),
        ),
        (
            "DataCollection",
            "AverageDuration",
            2,
            "Average completion time",
            _obj_filled(dc.get("AverageDuration"), "Value"),
        ),
        # Procedure
        (
            "Procedure",
            "Overview",
            3,
            "Narrative procedure overview",
            _filled(proc.get("Overview")),
        ),
        (
            "Procedure",
            "InformedConsent",
            2,
            "Informed consent procedure",
            _filled(proc.get("InformedConsent")),
        ),
        (
            "Procedure",
            "QualityControl",
            2,
            "Quality control measures",
            _filled(proc.get("QualityControl")),
        ),
        (
            "Procedure",
            "MissingDataHandling",
            1,
            "Missing data handling",
            _filled(proc.get("MissingDataHandling")),
        ),
        (
            "Procedure",
            "Debriefing",
            1,
            "Debriefing procedure",
            _filled(proc.get("Debriefing")),
        ),
        # Conditions (weight depends on experimental design)
        (
            "Conditions",
            "Type",
            2 if is_experimental else 1,
            "Condition type",
            _filled(cond.get("Type")),
        ),
        (
            "Conditions",
            "Groups",
            2 if is_experimental else 1,
            "Define experimental groups",
            _filled(cond.get("Groups")),
        ),
        # Read-only sections: DatasetDescription
        (
            "DatasetDescription",
            "Name",
            3,
            "Dataset name (dataset_description.json)",
            _filled(dd.get("Name")),
        ),
        (
            "DatasetDescription",
            "Authors",
            3,
            "Authors (dataset_description.json)",
            _filled(dd.get("Authors")),
        ),
        (
            "DatasetDescription",
            "Description",
            2,
            "Dataset description text",
            _filled(dd.get("Description")),
        ),
        (
            "DatasetDescription",
            "EthicsApprovals",
            2,
            "Ethics approvals",
            _filled(dd.get("EthicsApprovals")),
        ),
        (
            "DatasetDescription",
            "License",
            2,
            "Data license",
            _filled(dd.get("License")),
        ),
        (
            "DatasetDescription",
            "Keywords",
            1,
            "Keywords for discoverability",
            _filled(dd.get("Keywords")),
        ),
        # Read-only: Sessions & Tasks
        (
            "SessionsTasks",
            "Sessions",
            3,
            "Define at least one session",
            len(sessions) > 0,
        ),
        (
            "SessionsTasks",
            "TaskDefinitions",
            3,
            "Define at least one task",
            len(task_defs) > 0,
        ),
    ]

    # Build per-section summary
    sections_map: dict[str, dict] = {}
    total_weight = 0
    filled_weight = 0
    total_fields = 0
    filled_fields = 0

    for section_key, field_name, priority, hint, is_filled in fields:
        if section_key not in sections_map:
            sections_map[section_key] = {
                "fields": [],
                "filled": 0,
                "total": 0,
                "weight_filled": 0,
                "weight_total": 0,
                "read_only": section_key in ("DatasetDescription", "SessionsTasks"),
            }
        sec = sections_map[section_key]
        sec["fields"].append(
            {
                "name": field_name,
                "filled": is_filled,
                "priority": priority,
                "hint": hint,
            }
        )
        sec["total"] += 1
        sec["weight_total"] += priority
        total_weight += priority
        total_fields += 1
        if is_filled:
            sec["filled"] += 1
            sec["weight_filled"] += priority
            filled_weight += priority
            filled_fields += 1

    score = round(filled_weight / total_weight * 100) if total_weight else 0

    return {
        "score": score,
        "filled_fields": filled_fields,
        "total_fields": total_fields,
        "sections": sections_map,
    }


def _auto_detect_study_hints(project_path: Path, project_data: dict) -> dict:
    """Scan project files to auto-detect study metadata from existing data.

    Returns a dict of detected hints keyed by section.field path, e.g.
    ``{"DataCollection.Platform": {"value": "LimeSurvey", "source": "task sidecar"}}``
    """
    hints: dict[str, dict] = {}
    rawdata = project_path / "rawdata"

    # --- Scan task sidecars for platform / method / language ---
    platforms: list[str] = []
    versions: list[str] = []
    methods: list[str] = []
    languages: list[str] = []

    if rawdata.is_dir():
        for sidecar in rawdata.glob("task-*_survey.json"):
            try:
                with open(sidecar, "r", encoding="utf-8") as f:
                    sc = json.load(f)
                tech = sc.get("Technical") or {}
                if tech.get("SoftwarePlatform"):
                    platforms.append(tech["SoftwarePlatform"])
                if tech.get("SoftwareVersion"):
                    versions.append(tech["SoftwareVersion"])
                method = (
                    tech.get("CollectionMethod")
                    or tech.get("AdministrationMethod")
                    or ""
                )
                if method:
                    methods.append(method)
                lang = tech.get("Language") or ""
                if lang:
                    languages.append(lang)
            except Exception:
                pass
        # Also check tool sidecars (tool-limesurvey_survey.json)
        for sidecar in rawdata.glob("tool-*_survey.json"):
            try:
                with open(sidecar, "r", encoding="utf-8") as f:
                    sc = json.load(f)
                tech = sc.get("Technical") or {}
                if tech.get("SoftwarePlatform"):
                    platforms.append(tech["SoftwarePlatform"])
                if tech.get("SoftwareVersion"):
                    versions.append(tech["SoftwareVersion"])
            except Exception:
                pass

    if platforms:
        # Use most common platform
        from collections import Counter

        top_platform = Counter(platforms).most_common(1)[0][0]
        hints["DataCollection.Platform"] = {
            "value": top_platform,
            "source": "task sidecar",
        }
    if versions:
        from collections import Counter

        top_version = Counter(versions).most_common(1)[0][0]
        hints["DataCollection.PlatformVersion"] = {
            "value": top_version,
            "source": "task sidecar",
        }
    if methods:
        from collections import Counter

        top_method = Counter(methods).most_common(1)[0][0]
        hints["DataCollection.Method"] = {
            "value": top_method,
            "source": "task sidecar",
        }

    # Infer method from platform if not directly detected
    if "DataCollection.Method" not in hints and platforms:
        online_platforms = {
            "limesurvey",
            "qualtrics",
            "redcap",
            "surveymonkey",
            "prolific",
            "mturk",
            "gorilla",
            "pavlovia",
            "formr",
            "sosci",
            "soscisurvey",
            "unipark",
        }
        if any(p.lower().replace(" ", "") in online_platforms for p in platforms):
            hints["DataCollection.Method"] = {
                "value": "online",
                "source": "inferred from platform",
            }

    # --- Infer converter-based platform from provenance ---
    if "DataCollection.Platform" not in hints:
        converter_platforms = {
            "survey-lsa": "LimeSurvey",
        }
        sessions = project_data.get("Sessions") or []
        for s in sessions:
            for t in s.get("tasks") or []:
                src = t.get("source") or {}
                conv = src.get("converter", "")
                if conv in converter_platforms:
                    hints["DataCollection.Platform"] = {
                        "value": converter_platforms[conv],
                        "source": "conversion provenance",
                    }
                    if not hints.get("DataCollection.Method"):
                        hints["DataCollection.Method"] = {
                            "value": "online",
                            "source": "inferred from converter",
                        }
                    break
            if "DataCollection.Platform" in hints:
                break

    # --- Sample size from sub-* directories ---
    if rawdata.is_dir():
        sub_dirs = [
            d for d in rawdata.iterdir() if d.is_dir() and d.name.startswith("sub-")
        ]
        if sub_dirs:
            hints["Eligibility.ActualSampleSize"] = {
                "value": len(sub_dirs),
                "source": "rawdata sub-* folders",
            }

    # --- Sample size from participants.tsv ---
    tsv_path = get_bids_file_path(project_path, "participants.tsv")
    if tsv_path.exists():
        try:
            import pandas as pd

            df = pd.read_csv(tsv_path, sep="\t")
            hints["Eligibility.ActualSampleSize"] = {
                "value": len(df),
                "source": "participants.tsv",
            }
            # Check for group column → condition hints
            for col in ["group", "Group", "GROUP"]:
                if col in df.columns:
                    groups = df[col].dropna().unique().tolist()
                    if len(groups) > 1:
                        hints["Conditions.Groups"] = {
                            "value": [
                                {
                                    "id": str(g).lower().replace(" ", "_"),
                                    "label": str(g),
                                    "description": "",
                                }
                                for g in sorted(groups)
                            ],
                            "source": "participants.tsv group column",
                        }
                        hints["Conditions.Type"] = {
                            "value": "between-subjects",
                            "source": "inferred from group column",
                        }
                    break
        except Exception:
            pass

    # --- Recruitment period from conversion dates ---
    earliest_date = None
    latest_date = None
    sessions = project_data.get("Sessions") or []
    for s in sessions:
        for t in s.get("tasks") or []:
            src = t.get("source") or {}
            conv_date = src.get("convertedAt", "")
            if conv_date:
                if earliest_date is None or conv_date < earliest_date:
                    earliest_date = conv_date
                if latest_date is None or conv_date > latest_date:
                    latest_date = conv_date
    if earliest_date:
        hints["Recruitment.Period.Start"] = {
            "value": earliest_date[:7],  # YYYY-MM
            "source": "earliest conversion date",
        }
    if latest_date:
        hints["Recruitment.Period.End"] = {
            "value": latest_date[:7],
            "source": "latest conversion date",
        }

    # --- Study design hints from sessions ---
    if len(sessions) > 1:
        hints["StudyDesign.Type"] = {
            "value": "longitudinal",
            "source": f"{len(sessions)} sessions detected",
        }
    elif len(sessions) == 1:
        hints["StudyDesign.Type"] = {
            "value": "cross-sectional",
            "source": "single session detected",
        }

    return hints


@projects_bp.route("/api/projects/study-metadata", methods=["GET"])
def get_study_metadata():
    """Read study-level editable sections from project.json with completeness info."""
    current = get_current_project()
    if not current.get("path"):
        return jsonify({"success": False, "error": "No project selected"}), 400

    project_path = Path(current["path"])
    data = _read_project_json(project_path)
    if not data:
        return jsonify({"success": False, "error": "project.json not found"}), 404

    # Extract editable sections
    study_metadata = {}
    for key in _EDITABLE_SECTIONS:
        study_metadata[key] = data.get(key, {})

    # Read dataset_description for completeness calculation
    dataset_desc = None
    desc_path = get_bids_file_path(project_path, "dataset_description.json")
    if desc_path.exists():
        try:
            with open(desc_path, "r", encoding="utf-8") as f:
                dataset_desc = json.load(f)
        except Exception:
            pass

    completeness = _compute_methods_completeness(data, dataset_desc)
    hints = _auto_detect_study_hints(project_path, data)

    return jsonify(
        {
            "success": True,
            "study_metadata": study_metadata,
            "completeness": completeness,
            "hints": hints,
            "has_sessions": len(data.get("Sessions", [])) > 0,
            "has_tasks": len(data.get("TaskDefinitions", {})) > 0,
        }
    )


@projects_bp.route("/api/projects/study-metadata", methods=["POST"])
def save_study_metadata():
    """Save study-level editable sections to project.json, preserving other keys."""
    current = get_current_project()
    if not current.get("path"):
        return jsonify({"success": False, "error": "No project selected"}), 400

    req = request.get_json()
    if not req:
        return jsonify({"success": False, "error": "No data provided"}), 400

    project_path = Path(current["path"])
    data = _read_project_json(project_path)
    if not data:
        return jsonify({"success": False, "error": "project.json not found"}), 404

    # Merge only editable section keys
    for key in _EDITABLE_SECTIONS:
        if key in req:
            data[key] = req[key]

    # Update LastModified
    meta = data.get("Metadata")
    if isinstance(meta, dict):
        meta["LastModified"] = date.today().isoformat()

    _write_project_json(project_path, data)

    # Recompute completeness
    dataset_desc = None
    desc_path = get_bids_file_path(project_path, "dataset_description.json")
    if desc_path.exists():
        try:
            with open(desc_path, "r", encoding="utf-8") as f:
                dataset_desc = json.load(f)
        except Exception:
            pass

    completeness = _compute_methods_completeness(data, dataset_desc)

    return jsonify(
        {
            "success": True,
            "message": "Study metadata saved",
            "completeness": completeness,
        }
    )


@projects_bp.route("/api/projects/procedure/status", methods=["GET"])
def get_procedure_status():
    """Completeness check: declared sessions/tasks vs. data on disk."""
    current = get_current_project()
    if not current.get("path"):
        return jsonify({"success": False, "error": "No project selected"}), 400

    project_path = Path(current["path"])
    data = _read_project_json(project_path)
    sessions = data.get("Sessions", [])
    task_defs = data.get("TaskDefinitions", {})

    if not sessions:
        return jsonify(
            {
                "success": True,
                "status": "empty",
                "message": "No sessions declared in project.json",
                "declared": [],
                "on_disk": [],
                "missing": [],
                "undeclared": [],
            }
        )

    # Build declared set
    declared = set()
    for s in sessions:
        sid = s.get("id", "")
        for t in s.get("tasks", []):
            declared.add((sid, t.get("task", "")))

    # Build on-disk set by scanning rawdata/
    rawdata = project_path / "rawdata"
    on_disk = set()
    if rawdata.is_dir():
        for sub_dir in rawdata.iterdir():
            if not sub_dir.is_dir() or not sub_dir.name.startswith("sub-"):
                continue
            for ses_dir in sub_dir.iterdir():
                if not ses_dir.is_dir() or not ses_dir.name.startswith("ses-"):
                    continue
                ses_id = ses_dir.name
                for mod_dir in ses_dir.iterdir():
                    if not mod_dir.is_dir():
                        continue
                    for f in mod_dir.iterdir():
                        if f.is_file() and "_task-" in f.name:
                            m = re.search(r"_task-([a-zA-Z0-9]+)", f.name)
                            if m:
                                on_disk.add((ses_id, m.group(1)))

    missing = sorted(declared - on_disk)
    undeclared = sorted(on_disk - declared)

    return jsonify(
        {
            "success": True,
            "status": "ok" if not missing and not undeclared else "mismatch",
            "declared": sorted(declared),
            "on_disk": sorted(on_disk),
            "missing": [{"session": s, "task": t} for s, t in missing],
            "undeclared": [{"session": s, "task": t} for s, t in undeclared],
        }
    )


@projects_bp.route("/api/projects/generate-readme", methods=["POST"])
def generate_readme():
    """Generate README.md from project.json study metadata."""
    current = get_current_project()
    if not current.get("path"):
        return jsonify({"success": False, "error": "No project selected"}), 400

    project_path = Path(current["path"])
    
    # Check if project.json exists
    if not (project_path / "project.json").exists():
        return jsonify({"success": False, "error": "project.json not found"}), 404
    
    try:
        # Generate README
        generator = ReadmeGenerator(project_path)
        output_path = generator.save()
        
        return jsonify({
            "success": True,
            "message": "README.md generated successfully",
            "path": str(output_path),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@projects_bp.route("/api/projects/preview-readme", methods=["GET"])
def preview_readme():
    """Preview README.md content without saving."""
    current = get_current_project()
    if not current.get("path"):
        return jsonify({"success": False, "error": "No project selected"}), 400

    project_path = Path(current["path"])
    
    # Check if project.json exists
    if not (project_path / "project.json").exists():
        return jsonify({"success": False, "error": "project.json not found"}), 404
    
    try:
        # Generate README content
        generator = ReadmeGenerator(project_path)
        content = generator.generate()
        
        return jsonify({
            "success": True,
            "content": content,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
